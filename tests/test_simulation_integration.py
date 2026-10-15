"""End-to-end tests for Scheduler and Engine working together."""

import pytest

from main import create_engine
from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType
from src.simulation.engine import Engine
from src.simulation.models import Drone, MoveKind
from src.simulation.scheduler import Scheduler


def _build_engine(
    zones: list[Zone],
    connections: list[Connection],
    drones: list[Drone],
) -> Engine:
    zone_map = {zone.name: zone for zone in zones}
    start = next(zone for zone in zones if zone.is_start)
    end = next(zone for zone in zones if zone.is_end)
    map_data = MapData(
        nb_drones=len(drones),
        zones=zone_map,
        connections=connections,
        start_hub=start,
        end_hub=end,
    )
    return Engine(Scheduler(Graph(map_data)), drones)


def _zone(
    name: str,
    x: int,
    *,
    capacity: int = 1,
    zone_type: ZoneType = ZoneType.NORMAL,
    start: bool = False,
    end: bool = False,
) -> Zone:
    return Zone(
        name=name,
        x=x,
        y=0,
        zone_type=zone_type,
        max_drones=capacity,
        is_start=start,
        is_end=end,
    )


def test_single_drone_completes_normal_route_and_records_turns() -> None:
    drone = Drone(1, ("start", "middle", "end"))
    engine = _build_engine(
        [_zone("start", 0, start=True), _zone("middle", 1),
         _zone("end", 2, end=True)],
        [Connection("start", "middle", 1),
         Connection("middle", "end", 1)],
        [drone],
    )

    history = engine.run()

    assert drone.is_delivered
    assert engine.turns_elapsed == 2
    assert len(history) == 2
    assert [turn[0].destination for turn in history] == ["middle", "end"]


def test_two_drones_share_capacity_one_bottleneck_and_both_deliver() -> None:
    drones = [
        Drone(1, ("start", "bottleneck", "end")),
        Drone(2, ("start", "bottleneck", "end")),
    ]
    engine = _build_engine(
        [_zone("start", 0, start=True),
         _zone("bottleneck", 1, capacity=1),
         _zone("end", 2, end=True)],
        [Connection("start", "bottleneck", 1),
         Connection("bottleneck", "end", 1)],
        drones,
    )

    history = engine.run()

    assert all(drone.is_delivered for drone in drones)
    assert engine.turns_elapsed == 3
    assert len(history) == 3
    assert [move.drone_id for move in history[0]] == [1]
    assert {move.drone_id for move in history[1]} == {1, 2}
    assert [move.destination for move in history[1]] == ["end", "bottleneck"]
    assert all(move.kind is MoveKind.MOVE for turn in history for move in turn)


def test_restricted_transit_capacity_reserves_arrivals_for_competing_drones(
) -> None:
    drones = [
        Drone(1, ("start", "restricted", "end")),
        Drone(2, ("start", "restricted", "end")),
    ]
    engine = _build_engine(
        [_zone("start", 0, start=True),
         _zone("restricted", 1, capacity=1,
               zone_type=ZoneType.RESTRICTED),
         _zone("end", 2, end=True)],
        [Connection("start", "restricted", 1),
         Connection("restricted", "end", 1)],
        drones,
    )

    history = engine.run()

    assert all(drone.is_delivered for drone in drones)
    assert engine.turns_elapsed == 5
    assert len(history) == 5
    starts = [
        (turn_number, move.drone_id)
        for turn_number, turn in enumerate(history, start=1)
        for move in turn
        if move.kind is MoveKind.START_TRANSIT
    ]
    completions = [
        (turn_number, move.drone_id)
        for turn_number, turn in enumerate(history, start=1)
        for move in turn
        if move.kind is MoveKind.COMPLETE_TRANSIT
    ]
    assert starts == [(1, 1), (3, 2)]
    assert completions == [(2, 1), (4, 2)]
    assert all(
        sum(move.destination == "restricted" for move in turn) <= 1
        for turn in history
    )


def test_unusable_route_raises_controlled_deadlock_error() -> None:
    drone = Drone(1, ("start", "blocked", "end"))
    engine = _build_engine(
        [_zone("start", 0, start=True),
         _zone("blocked", 1, zone_type=ZoneType.BLOCKED),
         _zone("end", 2, end=True)],
        [Connection("start", "blocked", 1),
         Connection("blocked", "end", 1)],
        [drone],
    )

    with pytest.raises(RuntimeError, match="deadlocked"):
        engine.run()

    assert engine.turns_elapsed == 1
    assert drone.path_index == 0
    assert engine.history == [[]]


def test_pathfinding_initialization_runs_route_through_engine() -> None:
    zones = [
        _zone("start", 0, start=True),
        _zone("middle", 1),
        _zone("end", 2, end=True),
    ]
    map_data = MapData(
        nb_drones=1,
        zones={zone.name: zone for zone in zones},
        connections=[
            Connection("start", "middle", 1),
            Connection("middle", "end", 1),
        ],
        start_hub=zones[0],
        end_hub=zones[2],
    )

    engine = create_engine(map_data)
    history = engine.run()

    assert engine.all_drones_delivered()
    assert engine.turns_elapsed == 2
    assert [move.destination for turn in history for move in turn] == [
        "middle", "end",
    ]


def test_pathfinding_initialization_rejects_unreachable_end() -> None:
    zones = [
        _zone("start", 0, start=True),
        _zone("end", 1, end=True),
    ]
    map_data = MapData(
        nb_drones=1,
        zones={zone.name: zone for zone in zones},
        connections=[],
        start_hub=zones[0],
        end_hub=zones[1],
    )

    with pytest.raises(ValueError, match="No route exists"):
        create_engine(map_data)
