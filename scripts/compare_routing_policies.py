"""Compare route assignment policies on every map.

Run from the repository root with:
``python -m scripts.compare_routing_policies``.

The harness computes at most two Yen routes once per map and gives that same
ordered candidate set to each policy. ``shared`` assigns the cheapest route
to every drone; ``grouped`` assigns contiguous groups; ``round_robin`` and
``reverse_round_robin`` alternate the route order. ``congestion_greedy``
assigns each drone to the route with the smallest increase in squared
capacity-normalized resource work. Connection demand uses movement duration;
intermediate-zone demand counts one visit. Yen's route order breaks ties.
``time_aware_greedy`` builds tentative turn calendars for each assignment,
including connection durations, connection capacities, zone occupancy, and
arrival reservations.

``turns`` is ``Engine.turns_elapsed``: every completed ``advance_turn`` call
counts once, including an empty turn that exposes a deadlock. A call that
raises before recording a turn is not counted. ``zone_wait_events`` counts
each undelivered drone that begins a turn in a zone, is not in transit, and
receives no move in that turn. Transit progress and delivered drones are
excluded, so this event count is not equivalent to time lost.
``capacity_violations`` counts distinct connection capacity excesses and
zone occupancy or reservation constraints exceeded in each planned turn.

Statuses are ``complete``, ``deadlock`` (a turn leaves all drone states
unchanged), ``no_route`` (pathfinding returns no candidates), or
``error:<type>`` (simulation raises ``RuntimeError`` or ``ValueError``).
"""

from collections import Counter
from pathlib import Path

from src.algorithms.pathfinding import find_k_shortest_paths
from src.domain.graph import Graph
from src.domain.models import MapData
from src.parser.map_parser import MapParser
from src.simulation.engine import Engine
from src.simulation.models import Drone, MoveKind, PlannedMove, Transit
from src.simulation.scheduler import Scheduler


POLICIES = (
    "shared",
    "grouped",
    "round_robin",
    "reverse_round_robin",
    "congestion_greedy",
    "time_aware_greedy",
)


def _route_resources(
        graph: Graph,
        route: list[str],
) -> dict[tuple[str, ...], tuple[int, int]]:
    """Estimate resource work as (capacity, drone-turn demand) per route."""
    resources: dict[tuple[str, ...], tuple[int, int]] = {}
    for origin, destination in zip(route, route[1:]):
        edge = next(
            edge
            for edge in graph.get_neighbors(origin)
            if edge.target.name == destination
        )
        connection_key = (
            "connection",
            *sorted((edge.connection.zone_a, edge.connection.zone_b)),
        )
        resources[connection_key] = (
            edge.connection.max_link_capacity,
            edge.movement_cost,
        )

        zone = edge.target
        if not zone.is_start and not zone.is_end:
            resources[("zone", zone.name)] = (zone.max_drones, 1)
    return resources


def _estimate_route_schedule(
        graph: Graph,
        route: list[str],
        connection_calendar: dict[frozenset[str], dict[int, int]],
        zone_calendar: dict[str, dict[int, int]],
        horizon: int,
) -> tuple[int, int] | None:
    """Reserve a route's earliest feasible estimated turns in calendars."""
    elapsed = 0
    wait_events = 0

    for origin, destination in zip(route, route[1:]):
        edge = next(
            edge
            for edge in graph.get_neighbors(origin)
            if edge.target.name == destination
        )
        connection_key = frozenset((
            edge.connection.zone_a,
            edge.connection.zone_b,
        ))
        origin_zone = graph.get_zone(origin)
        destination_zone = graph.get_zone(destination)
        start_turn = elapsed + 1

        while start_turn <= horizon:
            arrival_turn = start_turn + edge.movement_cost - 1
            connection_available = all(
                connection_calendar.get(connection_key, {}).get(turn, 0)
                < edge.connection.max_link_capacity
                for turn in range(start_turn, arrival_turn + 1)
            )
            destination_available = (
                destination_zone.is_start
                or destination_zone.is_end
                or zone_calendar.get(destination, {}).get(arrival_turn, 0)
                < destination_zone.max_drones
            )
            origin_wait_available = (
                origin_zone.is_start
                or origin_zone.is_end
                or all(
                    zone_calendar.get(origin, {}).get(turn, 0)
                    < origin_zone.max_drones
                    for turn in range(elapsed + 1, start_turn)
                )
            )
            if (connection_available and destination_available
                    and origin_wait_available):
                break
            start_turn += 1
        else:
            return None

        arrival_turn = start_turn + edge.movement_cost - 1
        wait_events += start_turn - elapsed - 1
        if not origin_zone.is_start and not origin_zone.is_end:
            for turn in range(elapsed + 1, start_turn):
                zone_calendar.setdefault(origin, {})[turn] = (
                    zone_calendar.get(origin, {}).get(turn, 0) + 1
                )
        for turn in range(start_turn, arrival_turn + 1):
            connection_calendar.setdefault(connection_key, {})[turn] = (
                connection_calendar.get(connection_key, {}).get(turn, 0) + 1
            )
        if not destination_zone.is_start and not destination_zone.is_end:
            zone_calendar.setdefault(destination, {})[arrival_turn] = (
                zone_calendar.get(destination, {}).get(arrival_turn, 0) + 1
            )
        elapsed = arrival_turn

    return elapsed, wait_events


def _assigned_routes(
        routes: list[list[str]],
        drone_count: int,
        policy: str,
        graph: Graph,
) -> list[tuple[str, ...]]:
    """Assign candidate routes to drones using one named static policy."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown route assignment policy: {policy}")
    if not routes:
        return []

    assigned: list[tuple[str, ...]] = []
    route_resources = [
        _route_resources(graph, route)
        for route in routes
    ]
    assigned_work: dict[tuple[str, ...], int] = {}
    connection_calendar: dict[frozenset[str], dict[int, int]] = {}
    zone_calendar: dict[str, dict[int, int]] = {}
    estimated_finishes: list[int] = []
    estimated_waits = 0
    schedule_horizon = (
        max(
            sum(demand for _, demand in resources.values())
            for resources in route_resources
        )
        * (drone_count + 1)
        * 4
        + 10
    )

    for index in range(drone_count):
        if policy == "shared":
            route_index = 0
        elif policy == "grouped":
            route_index = index * len(routes) // drone_count
        elif policy == "round_robin":
            route_index = index % len(routes)
        elif policy == "congestion_greedy":
            def marginal_congestion(candidate_index: int) -> float:
                marginal = 0.0
                for key, (capacity, demand) in route_resources[
                        candidate_index
                ].items():
                    current_load = assigned_work.get(key, 0)
                    marginal += (
                        ((current_load + demand) / capacity) ** 2
                        - (current_load / capacity) ** 2
                    )
                return marginal

            route_index = min(
                range(len(routes)),
                key=lambda candidate_index: (
                    marginal_congestion(candidate_index),
                    candidate_index,
                ),
            )
        elif policy == "time_aware_greedy":
            scheduled_candidates = []
            for candidate_index, route in enumerate(routes):
                candidate_connections = {
                    key: slots.copy()
                    for key, slots in connection_calendar.items()
                }
                candidate_zones = {
                    key: slots.copy()
                    for key, slots in zone_calendar.items()
                }
                estimate = _estimate_route_schedule(
                    graph,
                    route,
                    candidate_connections,
                    candidate_zones,
                    schedule_horizon,
                )
                if estimate is None:
                    continue
                finish, waits = estimate
                projected_makespan = max(
                    max(estimated_finishes, default=0),
                    finish,
                )
                scheduled_candidates.append((
                    projected_makespan,
                    estimated_waits + waits,
                    finish,
                    candidate_index,
                    candidate_connections,
                    candidate_zones,
                ))

            if not scheduled_candidates:
                raise ValueError(
                    "Could not schedule any candidate route within the "
                    "time-aware benchmark horizon."
                )
            (
                _,
                waits,
                finish,
                route_index,
                connection_calendar,
                zone_calendar,
            ) = min(scheduled_candidates, key=lambda item: item[:4])
            estimated_finishes.append(finish)
            estimated_waits = waits
        else:
            route_index = (index + 1) % len(routes)
        assigned.append(tuple(routes[route_index]))
        if policy == "congestion_greedy":
            for key, (_, demand) in route_resources[route_index].items():
                assigned_work[key] = assigned_work.get(key, 0) + demand
    return assigned


def _simulation_state(
        engine: Engine,
) -> list[tuple[int, int, Transit | None]]:
    """Snapshot drone route progress for deadlock detection."""
    return [
        (drone.drone_id, drone.path_index, drone.transit)
        for drone in engine._drones
    ]


def _capacity_violations(
        map_data: MapData,
        drones: list[Drone],
        moves: list[PlannedMove],
) -> int:
    """Count over-capacity zones, future arrivals, and connections."""
    occupancy: Counter[str] = Counter(
        drone.current_zone
        for drone in drones
        if drone.current_zone is not None and not drone.is_delivered
    )
    reservations: Counter[str] = Counter(
        drone.transit.destination
        for drone in drones
        if drone.transit is not None and drone.transit.turns_remaining > 1
    )
    connection_usage: Counter[frozenset[str]] = Counter(
        frozenset((drone.transit.connection.zone_a,
                   drone.transit.connection.zone_b))
        for drone in drones
        if drone.transit is not None
    )
    connection_capacities: dict[frozenset[str], int] = {}

    for move in moves:
        if move.kind in (MoveKind.MOVE, MoveKind.START_TRANSIT):
            if move.origin is not None:
                occupancy[move.origin] -= 1
            key = frozenset((move.connection.zone_a, move.connection.zone_b))
            connection_usage[key] += 1
            connection_capacities[key] = move.connection.max_link_capacity
        if move.kind in (MoveKind.MOVE, MoveKind.COMPLETE_TRANSIT):
            occupancy[move.destination] += 1
        if move.kind is MoveKind.START_TRANSIT:
            reservations[move.destination] += 1

    for drone in drones:
        if drone.transit is not None:
            key = frozenset((
                drone.transit.connection.zone_a,
                drone.transit.connection.zone_b,
            ))
            connection_capacities[key] = (
                drone.transit.connection.max_link_capacity
            )

    violations = sum(
        usage > connection_capacities[key]
        for key, usage in connection_usage.items()
    )
    for zone_name, zone in map_data.zones.items():
        if zone.is_start or zone.is_end:
            continue
        if occupancy[zone_name] < 0:
            violations += 1
        if occupancy[zone_name] + reservations[zone_name] > zone.max_drones:
            violations += 1
    return violations


def _run_policy(
        map_data: MapData,
        graph: Graph,
        routes: list[list[str]],
        policy: str,
) -> tuple[int, int, int, int, str]:
    """Return delivered count, elapsed turns, and total zone wait events."""
    assigned = _assigned_routes(
        routes,
        map_data.nb_drones,
        policy,
        graph,
    )
    drones = [
        Drone(drone_id=index + 1, path=route)
        for index, route in enumerate(assigned)
    ]
    engine = Engine(Scheduler(graph), drones)
    zone_waits = 0
    capacity_violations = 0
    status = "complete"

    while not engine.all_drones_delivered():
        state_before = _simulation_state(engine)
        active_in_zones = {
            drone.drone_id
            for drone in engine._drones
            if drone.transit is None and not drone.is_delivered
        }

        try:
            moves = engine._scheduler.plan_turn(engine._drones)
            capacity_violations += _capacity_violations(
                map_data,
                engine._drones,
                moves,
            )
            engine.advance_turn()
        except (RuntimeError, ValueError) as error:
            status = f"error:{type(error).__name__}"
            break
        moved_ids = {
            move.drone_id
            for move in engine.history[-1]
        }
        zone_waits += len(active_in_zones - moved_ids)

        if state_before == _simulation_state(engine):
            status = "deadlock"
            break

    delivered = sum(drone.is_delivered for drone in engine._drones)
    return (
        delivered,
        engine.turns_elapsed,
        zone_waits,
        capacity_violations,
        status,
    )


def _benchmark_map(
        map_path: Path,
) -> list[tuple[str, int, int, int, int, str]]:
    """Run each assignment policy and return comparable metric rows."""
    map_data = MapParser().parse_file(str(map_path))
    graph = Graph(map_data)
    routes = find_k_shortest_paths(
        graph,
        map_data.start_hub.name,
        map_data.end_hub.name,
        k=2,
    )
    if not routes:
        return [
            (policy, 0, 0, 0, 0, "no_route")
            for policy in POLICIES
        ]

    rows = []
    for policy in POLICIES:
        delivered, turns, waits, violations, status = _run_policy(
            map_data,
            graph,
            routes,
            policy,
        )
        rows.append((policy, delivered, turns, waits, violations, status))
    return rows


def main() -> None:
    """Print CSV metrics for each map and assignment policy."""
    map_paths = sorted(Path("maps").rglob("*.txt"))
    print(
        "map,policy,delivered,turns,zone_wait_events,"
        "capacity_violations,status"
    )
    for map_path in map_paths:
        rows = _benchmark_map(map_path)
        for policy, delivered, turns, waits, violations, status in rows:
            print(
                f"{map_path},{policy},{delivered},{turns},{waits},"
                f"{violations},{status}"
            )


if __name__ == "__main__":
    main()
