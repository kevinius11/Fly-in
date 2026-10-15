"""Compare route assignment policies on every map.

Run from the repository root with:
``python -m scripts.compare_routing_policies``.

The harness computes at most two Yen routes once per map and gives that same
ordered candidate set to each policy. ``shared`` assigns the cheapest route
to every drone; ``grouped`` assigns contiguous groups; ``round_robin`` and
``reverse_round_robin`` alternate the route order.

``turns`` is ``Engine.turns_elapsed``: every completed ``advance_turn`` call
counts once, including an empty turn that exposes a deadlock. A call that
raises before recording a turn is not counted. ``zone_wait_events`` counts
each undelivered drone that begins a turn in a zone, is not in transit, and
receives no move in that turn. Transit progress and delivered drones are
excluded, so this event count is not equivalent to time lost.

Statuses are ``complete``, ``deadlock`` (a turn leaves all drone states
unchanged), ``no_route`` (pathfinding returns no candidates), or
``error:<type>`` (simulation raises ``RuntimeError`` or ``ValueError``).
"""

from pathlib import Path

from src.algorithms.pathfinding import find_k_shortest_paths
from src.domain.graph import Graph
from src.domain.models import MapData
from src.parser.map_parser import MapParser
from src.simulation.engine import Engine
from src.simulation.models import Drone, Transit
from src.simulation.scheduler import Scheduler


POLICIES = ("shared", "grouped", "round_robin", "reverse_round_robin")


def _assigned_routes(
        routes: list[list[str]],
        drone_count: int,
        policy: str,
) -> list[tuple[str, ...]]:
    """Assign candidate routes to drones using one named static policy."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown route assignment policy: {policy}")
    if not routes:
        return []

    assigned: list[tuple[str, ...]] = []
    for index in range(drone_count):
        if policy == "shared":
            route_index = 0
        elif policy == "grouped":
            route_index = index * len(routes) // drone_count
        elif policy == "round_robin":
            route_index = index % len(routes)
        else:
            route_index = (index + 1) % len(routes)
        assigned.append(tuple(routes[route_index]))
    return assigned


def _simulation_state(
        engine: Engine,
) -> list[tuple[int, int, Transit | None]]:
    """Snapshot drone route progress for deadlock detection."""
    return [
        (drone.drone_id, drone.path_index, drone.transit)
        for drone in engine._drones
    ]


def _run_policy(
        map_data: MapData,
        graph: Graph,
        routes: list[list[str]],
        policy: str,
) -> tuple[int, int, int, str]:
    """Return delivered count, elapsed turns, and total zone wait events."""
    assigned = _assigned_routes(routes, map_data.nb_drones, policy)
    drones = [
        Drone(drone_id=index + 1, path=route)
        for index, route in enumerate(assigned)
    ]
    engine = Engine(Scheduler(graph), drones)
    zone_waits = 0
    status = "complete"

    while not engine.all_drones_delivered():
        state_before = _simulation_state(engine)
        active_in_zones = {
            drone.drone_id
            for drone in engine._drones
            if drone.transit is None and not drone.is_delivered
        }

        try:
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
    return delivered, engine.turns_elapsed, zone_waits, status


def _benchmark_map(map_path: Path) -> list[tuple[str, int, int, int, str]]:
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
            (policy, 0, 0, 0, "no_route")
            for policy in POLICIES
        ]

    rows = []
    for policy in POLICIES:
        delivered, turns, waits, status = _run_policy(
            map_data,
            graph,
            routes,
            policy,
        )
        rows.append((policy, delivered, turns, waits, status))
    return rows


def main() -> None:
    """Print CSV metrics for each map and assignment policy."""
    map_paths = sorted(Path("maps").rglob("*.txt"))
    print("map,policy,delivered,turns,zone_wait_events,status")
    for map_path in map_paths:
        rows = _benchmark_map(map_path)
        for policy, delivered, turns, waits, status in rows:
            print(
                f"{map_path},{policy},{delivered},{turns},{waits},{status}"
            )


if __name__ == "__main__":
    main()
