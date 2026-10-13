import pytest

from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType
from src.simulation.engine import Engine
from src.simulation.models import Drone, MoveKind, PlannedMove, Transit
from src.simulation.scheduler import Scheduler


def _build_engine(
    drones: list[Drone],
) -> tuple[Engine, dict[str, Connection]]:
    """Build an Engine with a small map for unit tests."""
    start = Zone(
        name="start",
        x=0,
        y=0,
        zone_type=ZoneType.NORMAL,
        max_drones=1,
        is_start=True,
    )
    middle = Zone(
        name="middle",
        x=1,
        y=0,
        zone_type=ZoneType.NORMAL,
        max_drones=1,
    )
    restricted = Zone(
        name="restricted",
        x=1,
        y=1,
        zone_type=ZoneType.RESTRICTED,
        max_drones=1,
    )
    end = Zone(
        name="end",
        x=2,
        y=0,
        zone_type=ZoneType.NORMAL,
        max_drones=1,
        is_end=True,
    )

    zones = {
        "start": start,
        "middle": middle,
        "restricted": restricted,
        "end": end,
    }

    connections = {
        "start-middle": Connection(
            zone_a="start",
            zone_b="middle",
            max_link_capacity=1,
        ),
        "start-restricted": Connection(
            zone_a="start",
            zone_b="restricted",
            max_link_capacity=1,
        ),
        "restricted-end": Connection(
            zone_a="restricted",
            zone_b="end",
            max_link_capacity=1,
        ),
        "middle-end": Connection(
            zone_a="middle",
            zone_b="end",
            max_link_capacity=1,
        ),
    }

    map_data = MapData(
        nb_drones=max(1, len(drones)),
        zones=zones,
        connections=list(connections.values()),
        start_hub=start,
        end_hub=end,
    )

    scheduler = Scheduler(Graph(map_data))
    return Engine(scheduler, drones), connections


def test_apply_moves_executes_normal_move() -> None:
    """A normal move advances the drone's path index."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, connections = _build_engine([drone])

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="start",
        destination="middle",
        connection=connections["start-middle"],
    )

    engine._apply_moves([move])

    assert drone.path_index == 1
    assert drone.current_zone == "middle"
    assert drone.transit is None


def test_apply_moves_starts_transit_without_advancing_path() -> None:
    """Starting a transit creates a two-turn transit."""
    drone = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
    )
    engine, connections = _build_engine([drone])

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.START_TRANSIT,
        origin="start",
        destination="restricted",
        connection=connections["start-restricted"],
    )

    engine._apply_moves([move])

    assert drone.path_index == 0
    assert drone.transit is not None
    assert drone.transit.destination == "restricted"
    assert drone.transit.turns_remaining == 2
    assert drone.current_zone is None


def test_apply_moves_completes_transit() -> None:
    """Completing a transit advances the drone to its destination."""
    connections = {
        "start-restricted": Connection(
            zone_a="start",
            zone_b="restricted",
            max_link_capacity=1,
        ),
    }
    transit = Transit(
        connection=connections["start-restricted"],
        destination="restricted",
        turns_remaining=1,
    )
    drone = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
        transit=transit,
    )
    engine, _ = _build_engine([drone])

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.COMPLETE_TRANSIT,
        origin=None,
        destination="restricted",
        connection=transit.connection,
    )

    engine._apply_moves([move])

    assert drone.transit is None
    assert drone.path_index == 1
    assert drone.current_zone == "restricted"


def test_apply_moves_rejects_duplicate_drone_moves_atomically() -> None:
    """Reject duplicate moves without changing any drone."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, connections = _build_engine([drone])

    first_move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="start",
        destination="middle",
        connection=connections["start-middle"],
    )
    second_move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="start",
        destination="middle",
        connection=connections["start-middle"],
    )

    with pytest.raises(ValueError, match="Duplicate"):
        engine._apply_moves([first_move, second_move])

    assert drone.path_index == 0
    assert drone.transit is None


def test_apply_moves_rejects_unknown_drone_atomically() -> None:
    """An invalid later move must not partially execute the plan."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, connections = _build_engine([drone])

    valid_move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="start",
        destination="middle",
        connection=connections["start-middle"],
    )
    invalid_move = PlannedMove(
        drone_id=99,
        kind=MoveKind.MOVE,
        origin="start",
        destination="middle",
        connection=connections["start-middle"],
    )

    with pytest.raises(ValueError, match="not found"):
        engine._apply_moves([valid_move, invalid_move])

    assert drone.path_index == 0
    assert drone.current_zone == "start"
    assert drone.transit is None


def test_apply_moves_rejects_wrong_destination_atomically() -> None:
    """Reject a destination that does not match the planned path."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, connections = _build_engine([drone])

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="start",
        destination="end",
        connection=connections["start-middle"],
    )

    with pytest.raises(ValueError, match="Dest mismatch"):
        engine._apply_moves([move])

    assert drone.path_index == 0
    assert drone.current_zone == "start"
    assert drone.transit is None
