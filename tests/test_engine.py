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


def test_advance_turn_executes_planned_move_and_records_turn() -> None:
    """A turn applies the scheduler's move and updates engine bookkeeping."""
    drone = Drone(drone_id=1, path=("start", "middle", "end"))
    engine, _ = _build_engine([drone])

    engine.advance_turn()

    assert drone.current_zone == "middle"
    assert drone.path_index == 1
    assert engine._turns_elapsed == 1
    assert len(engine._history) == 1
    assert len(engine._history[0]) == 1
    assert engine._history[0][0].kind == MoveKind.MOVE


def test_advance_turn_completes_restricted_transit_on_following_turn() -> None:
    """A restricted connection is entered, counted down, then completed."""
    drone = Drone(drone_id=1, path=("start", "restricted", "end"))
    engine, _ = _build_engine([drone])

    engine.advance_turn()

    assert drone.current_zone is None
    assert drone.transit is not None
    assert drone.transit.turns_remaining == 1
    assert drone.path_index == 0

    engine.advance_turn()

    assert drone.transit is None
    assert drone.current_zone == "restricted"
    assert drone.path_index == 1
    assert engine._turns_elapsed == 2
    assert [moves[0].kind for moves in engine._history] == [
        MoveKind.START_TRANSIT,
        MoveKind.COMPLETE_TRANSIT,
    ]


def test_advance_transit_decrements_active_and_leaves_idle_drone() -> None:
    """Only active transits are decremented, preserving their other fields."""
    transit_connection = Connection(
        zone_a="start", zone_b="restricted", max_link_capacity=1,
    )
    transit = Transit(
        connection=transit_connection,
        destination="restricted",
        turns_remaining=3,
    )
    travelling = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
        transit=transit,
    )
    idle = Drone(drone_id=2, path=("start", "middle"))
    engine, _ = _build_engine([travelling, idle])

    engine.advance_transit()

    assert travelling.transit == Transit(
        connection=transit_connection,
        destination="restricted",
        turns_remaining=2,
    )
    assert idle.transit is None


def test_advance_transit_rejects_ready_to_complete_transit() -> None:
    """A one-turn transit must be completed by a planned move."""
    transit_connection = Connection(
        zone_a="start", zone_b="restricted", max_link_capacity=1,
    )
    ready = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
        transit=Transit(
            connection=transit_connection,
            destination="restricted",
            turns_remaining=1,
        ),
    )
    engine, _ = _build_engine([ready])

    with pytest.raises(ValueError, match="should have completed"):
        engine.advance_transit()

    assert ready.transit is not None
    assert ready.transit.turns_remaining == 1


def test_advance_transit_validates_all_transits_before_decrementing() -> None:
    """A rejected transit must not leave earlier drones partially advanced."""
    connection = Connection(
        zone_a="start", zone_b="restricted", max_link_capacity=1,
    )
    first = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
        transit=Transit(connection, "restricted", 3),
    )
    ready = Drone(
        drone_id=2,
        path=("start", "restricted", "end"),
        transit=Transit(connection, "restricted", 1),
    )
    engine, _ = _build_engine([first, ready])

    with pytest.raises(ValueError, match="should have completed"):
        engine.advance_transit()

    assert first.transit is not None
    assert first.transit.turns_remaining == 3
    assert ready.transit is not None
    assert ready.transit.turns_remaining == 1


def test_step_delegates_to_advance_turn() -> None:
    """The existing step entry point retains its complete-turn behavior."""
    drone = Drone(drone_id=1, path=("start", "middle"))
    engine, _ = _build_engine([drone])

    engine.step()

    assert drone.current_zone == "middle"
    assert engine._turns_elapsed == 1


def test_all_drones_delivered_returns_true() -> None:
    """Return True when every drone has reached the end."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
        path_index=2,
    )
    engine, _ = _build_engine([drone])

    assert engine.all_drones_delivered() is True


def test_all_drones_delivered_returns_false() -> None:
    """Return False when a drone has not reached the end."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, _ = _build_engine([drone])

    assert engine.all_drones_delivered() is False


def test_drone_in_transit_is_not_delivered() -> None:
    """A drone in transit must not count as delivered."""
    connection = Connection(
        zone_a="start",
        zone_b="restricted",
        max_link_capacity=1,
    )
    drone = Drone(
        drone_id=1,
        path=("start", "restricted", "end"),
        transit=Transit(
            connection=connection,
            destination="restricted",
            turns_remaining=1,
        ),
    )
    engine, _ = _build_engine([drone])

    assert engine.all_drones_delivered() is False


def test_engine_starts_with_empty_state() -> None:
    """Initialize turn count and history to zero and empty."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, _ = _build_engine([drone])

    assert engine.turns_elapsed == 0
    assert engine.history == []


def test_advance_turn_updates_counter_and_history() -> None:
    """Record each completed turn and increment the turn counter."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, _ = _build_engine([drone])

    engine.advance_turn()

    assert engine.turns_elapsed == 1
    assert len(engine.history) == 1
    assert engine.history[0][0].kind == MoveKind.MOVE


def test_history_property_returns_independent_copy() -> None:
    """Prevent external modifications from changing internal history."""
    drone = Drone(
        drone_id=1,
        path=("start", "middle", "end"),
    )
    engine, _ = _build_engine([drone])

    engine.advance_turn()

    history_copy = engine.history
    history_copy[0].clear()
    history_copy.clear()

    assert len(engine.history) == 1
    assert len(engine.history[0]) == 1
