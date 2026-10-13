from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType
from src.simulation.models import Drone, MoveKind, Transit
from src.simulation.scheduler import Scheduler, PlannedMove

import pytest


def _build_graph(
    zone_types: dict[str, ZoneType],
    connection_specs: list[tuple[str, str, int]],
    start_name: str,
    end_name: str,
) -> Graph:
    """Build a graph from zone types and connection specifications."""
    zones: dict[str, Zone] = {
        name: Zone(
            name=name,
            x=index,
            y=0,
            zone_type=zone_type,
            max_drones=1,
            is_start=name == start_name,
            is_end=name == end_name,
        )
        for index, (name, zone_type) in enumerate(zone_types.items())
    }

    connections = [
        Connection(
            zone_a=zone_a,
            zone_b=zone_b,
            max_link_capacity=capacity,
        )
        for zone_a, zone_b, capacity in connection_specs
    ]

    map_data = MapData(
        nb_drones=1,
        zones=zones,
        connections=connections,
        start_hub=zones[start_name],
        end_hub=zones[end_name],
    )

    return Graph(map_data)


def test_collect_candidates_normal_move() -> None:
    """Collect a normal movement toward a normal zone."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )

    scheduler = Scheduler(graph)
    drone = Drone(
        drone_id=1,
        path=("A", "B"),
    )

    candidates = scheduler._collect_candidates([drone])

    assert len(candidates) == 1

    move = candidates[0]
    assert move.drone_id == 1
    assert move.kind is MoveKind.MOVE
    assert move.origin == "A"
    assert move.destination == "B"
    assert move.connection.zone_a == "A"
    assert move.connection.zone_b == "B"


def test_collect_candidates_priority_zone() -> None:
    """Treat movement toward a priority zone as a normal move."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.PRIORITY,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )

    scheduler = Scheduler(graph)
    drone = Drone(
        drone_id=1,
        path=("A", "B"),
    )

    candidates = scheduler._collect_candidates([drone])

    assert len(candidates) == 1
    assert candidates[0].kind is MoveKind.MOVE
    assert candidates[0].destination == "B"


def test_collect_candidates_restricted_zone() -> None:
    """Start a transit when the next zone is restricted."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )

    scheduler = Scheduler(graph)
    drone = Drone(
        drone_id=1,
        path=("A", "B", "C"),
    )

    candidates = scheduler._collect_candidates([drone])

    assert len(candidates) == 1

    move = candidates[0]
    assert move.drone_id == 1
    assert move.kind is MoveKind.START_TRANSIT
    assert move.origin == "A"
    assert move.destination == "B"
    assert move.connection.zone_a == "A"
    assert move.connection.zone_b == "B"


def test_collect_candidates_ignores_delivered_drone() -> None:
    """Do not generate candidates for a delivered drone."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )

    scheduler = Scheduler(graph)
    drone = Drone(
        drone_id=1,
        path=("A", "B"),
        path_index=1,
    )

    candidates = scheduler._collect_candidates([drone])

    assert candidates == []


def test_collect_candidates_completes_transit() -> None:
    """Collect a completion movement when one turn remains."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )

    connection = Connection(
        zone_a="A",
        zone_b="B",
        max_link_capacity=1,
    )
    transit = Transit(
        connection=connection,
        destination="B",
        turns_remaining=1,
    )
    drone = Drone(
        drone_id=1,
        path=("A", "B", "C"),
        path_index=0,
        transit=transit,
    )

    scheduler = Scheduler(graph)
    candidates = scheduler._collect_candidates([drone])

    assert len(candidates) == 1

    move = candidates[0]
    assert move.drone_id == 1
    assert move.kind is MoveKind.COMPLETE_TRANSIT
    assert move.origin is None
    assert move.destination == "B"
    assert move.connection == connection


def test_collect_candidates_does_not_complete_transit_early() -> None:
    """Do not complete a transit that still has two turns remaining."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )

    connection = Connection(
        zone_a="A",
        zone_b="B",
        max_link_capacity=1,
    )
    transit = Transit(
        connection=connection,
        destination="B",
        turns_remaining=2,
    )
    drone = Drone(
        drone_id=1,
        path=("A", "B", "C"),
        path_index=0,
        transit=transit,
    )

    scheduler = Scheduler(graph)
    candidates = scheduler._collect_candidates([drone])

    assert candidates == []


def test_calculate_occupancy_for_normal_move() -> None:
    """Count the origin departure and destination arrival."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    drone = Drone(drone_id=1, path=("A", "B"))
    connection = graph.get_neighbors("A")[0].connection

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="A",
        destination="B",
        connection=connection,
    )

    result = scheduler._calculate_final_zone_occupancy(
        [move], [drone]
    )

    assert result == {"A": 0, "B": 1}


def test_calculate_occupancy_for_transit_start() -> None:
    """Free the origin without occupying the restricted destination."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    drone = Drone(drone_id=1, path=("A", "B"))
    connection = graph.get_neighbors("A")[0].connection

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.START_TRANSIT,
        origin="A",
        destination="B",
        connection=connection,
    )

    result = scheduler._calculate_final_zone_occupancy(
        [move], [drone]
    )

    assert result == {"A": 0, "B": 0}


def test_calculate_occupancy_for_transit_completion() -> None:
    """Count arrival when a drone completes its transit."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    connection = graph.get_neighbors("A")[0].connection

    transit = Transit(
        connection=connection,
        destination="B",
        turns_remaining=1,
    )
    drone = Drone(
        drone_id=1,
        path=("A", "B"),
        transit=transit,
    )
    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.COMPLETE_TRANSIT,
        origin=None,
        destination="B",
        connection=connection,
    )

    result = scheduler._calculate_final_zone_occupancy(
        [move], [drone]
    )

    assert result == {"A": 0, "B": 1}


def test_calculate_occupancy_for_simultaneous_moves() -> None:
    """Account for a departure and arrival in the same turn."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    drone_1 = Drone(drone_id=1, path=("A", "B"))
    drone_2 = Drone(drone_id=2, path=("B", "C"))

    connection_ab = next(
        edge.connection
        for edge in graph.get_neighbors("A")
        if edge.target.name == "B"
    )
    connection_bc = next(
        edge.connection
        for edge in graph.get_neighbors("B")
        if edge.target.name == "C"
    )

    moves = [
        PlannedMove(
            drone_id=1,
            kind=MoveKind.MOVE,
            origin="A",
            destination="B",
            connection=connection_ab,
        ),
        PlannedMove(
            drone_id=2,
            kind=MoveKind.MOVE,
            origin="B",
            destination="C",
            connection=connection_bc,
        ),
    ]

    result = scheduler._calculate_final_zone_occupancy(
        moves, [drone_1, drone_2]
    )

    assert result == {"A": 0, "B": 1, "C": 1}


def test_calculate_occupancy_rejects_unknown_transit_destination() -> None:
    """Reject a transit start targeting a nonexistent zone."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    drone = Drone(
        drone_id=1,
        path=("A", "B"),
    )
    connection = graph.get_neighbors("A")[0].connection

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.START_TRANSIT,
        origin="A",
        destination="UNKNOWN",
        connection=connection,
    )

    with pytest.raises(
        ValueError,
        match="Destination zone 'UNKNOWN'",
    ):
        scheduler._calculate_final_zone_occupancy(
            [move],
            [drone],
        )


def test_calculate_occupancy_rejects_missing_origin() -> None:
    """Reject a movement that requires an origin but has none."""
    graph = _build_graph(
        zone_types={"A": ZoneType.NORMAL, "B": ZoneType.NORMAL},
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    drone = Drone(drone_id=1, path=("A", "B"))
    connection = graph.get_neighbors("A")[0].connection

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin=None,
        destination="B",
        connection=connection,
    )

    with pytest.raises(ValueError, match="must have a valid origin zone"):
        scheduler._calculate_final_zone_occupancy([move], [drone])


def test_zone_capacities_respected_within_limits() -> None:
    """Accept occupancy that stays within zone capacities."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 1, "B": 1, "C": 1}

    assert scheduler._zone_capacities_respected(occupancy) is True


def test_zone_capacities_reject_over_capacity() -> None:
    """Reject occupancy exceeding a normal zone's capacity."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 0, "B": 2, "C": 0}

    assert scheduler._zone_capacities_respected(occupancy) is False


def test_zone_capacities_reject_negative_occupancy() -> None:
    """Reject a negative final zone occupancy."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 0, "B": -1, "C": 0}

    assert scheduler._zone_capacities_respected(occupancy) is False


def test_start_and_end_zones_ignore_normal_capacity_limits() -> None:
    """Allow multiple drones in start and end zones."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 5, "B": 0, "C": 4}

    assert scheduler._zone_capacities_respected(occupancy) is True


def test_connection_capacity_accepts_single_move() -> None:
    """Accept one movement through a connection with capacity one."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    connection = graph.get_neighbors("A")[0].connection

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="A",
        destination="B",
        connection=connection,
    )

    assert scheduler._connection_capacities_respected(
        [move], []
    ) is True


def test_connection_capacity_rejects_opposite_moves() -> None:
    """Reject two simultaneous movements through the same link."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
        },
        connection_specs=[("A", "B", 1)],
        start_name="A",
        end_name="B",
    )
    scheduler = Scheduler(graph)
    connection = graph.get_neighbors("A")[0].connection

    moves = [
        PlannedMove(
            drone_id=1,
            kind=MoveKind.MOVE,
            origin="A",
            destination="B",
            connection=connection,
        ),
        PlannedMove(
            drone_id=2,
            kind=MoveKind.MOVE,
            origin="B",
            destination="A",
            connection=connection,
        ),
    ]

    assert scheduler._connection_capacities_respected(
        moves, []
    ) is False


def test_active_transit_counts_toward_connection_capacity() -> None:
    """Count existing transit when evaluating a new movement."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)
    connection = next(
        edge.connection
        for edge in graph.get_neighbors("A")
        if edge.target.name == "B"
    )

    transit = Transit(
        connection=connection,
        destination="B",
        turns_remaining=1,
    )
    drone = Drone(
        drone_id=1,
        path=("A", "B", "C"),
        transit=transit,
    )

    candidate = PlannedMove(
        drone_id=2,
        kind=MoveKind.START_TRANSIT,
        origin="A",
        destination="B",
        connection=connection,
    )

    assert scheduler._connection_capacities_respected(
        [candidate], [drone]
    ) is False


def test_completed_transit_is_not_counted_twice() -> None:
    """Count an active transit once when its arrival is scheduled."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.RESTRICTED,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)
    connection = next(
        edge.connection
        for edge in graph.get_neighbors("A")
        if edge.target.name == "B"
    )

    transit = Transit(
        connection=connection,
        destination="B",
        turns_remaining=1,
    )
    drone = Drone(
        drone_id=1,
        path=("A", "B", "C"),
        transit=transit,
    )

    completion = PlannedMove(
        drone_id=1,
        kind=MoveKind.COMPLETE_TRANSIT,
        origin=None,
        destination="B",
        connection=connection,
    )

    assert scheduler._connection_capacities_respected(
        [completion], [drone]
    ) is True


def test_find_zone_violation_returns_none_when_valid() -> None:
    """Return None when all zones respect their capacities."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 1, "B": 1, "C": 1}

    assert scheduler._find_zone_capacity_violation(occupancy) is None


def test_find_zone_violation_returns_over_capacity_zone() -> None:
    """Return the name of a zone exceeding its capacity."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 0, "B": 2, "C": 0}

    assert scheduler._find_zone_capacity_violation(occupancy) == "B"


def test_find_zone_violation_returns_negative_occupancy_zone() -> None:
    """Return the name of a zone with negative occupancy."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 0, "B": -1, "C": 0}

    assert scheduler._find_zone_capacity_violation(occupancy) == "B"


def test_find_zone_violation_ignores_start_end_capacity_limits() -> None:
    """Do not apply ordinary capacity limits to start and end zones."""
    graph = _build_graph(
        zone_types={
            "A": ZoneType.NORMAL,
            "B": ZoneType.NORMAL,
            "C": ZoneType.NORMAL,
        },
        connection_specs=[
            ("A", "B", 1),
            ("B", "C", 1),
        ],
        start_name="A",
        end_name="C",
    )
    scheduler = Scheduler(graph)

    occupancy = {"A": 5, "B": 0, "C": 4}

    assert scheduler._find_zone_capacity_violation(occupancy) is None
