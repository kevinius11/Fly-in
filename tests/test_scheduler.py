from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType
from src.simulation.models import Drone, MoveKind, Transit
from src.simulation.scheduler import Scheduler


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
