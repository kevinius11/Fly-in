"""Pygame visualizer helpers consume real Engine snapshots."""

from dataclasses import replace
from pathlib import Path

from main import create_engine
from src.domain.models import MapData
from src.display.pygame_visualizer import (
    connection_usage,
    drone_position,
    has_visible_display,
    map_positions,
    metadata_color,
)
from src.parser.map_parser import MapParser


def _map_data(tmp_path: Path) -> MapData:
    map_file = tmp_path / "pygame.map"
    map_file.write_text(
        "nb_drones: 1\n"
        "start_hub: start 0 0 [color=green]\n"
        "hub: slow 1 0 [zone=restricted color=orange]\n"
        "end_hub: goal 2 0\n"
        "connection: start-slow\n"
        "connection: slow-goal\n",
        encoding="utf-8",
    )
    return MapParser().parse_file(str(map_file))


def test_map_positions_use_coordinates_and_deterministic_overlap_fallback(
    tmp_path: Path,
) -> None:
    map_data = _map_data(tmp_path)
    area = (0, 0, 800, 500)
    positions = map_positions(map_data, area)
    assert positions["start"][0] < positions["slow"][0] < positions["goal"][0]

    zones = dict(map_data.zones)
    zones["slow"] = replace(zones["slow"], x=0, y=0)
    overlapping = replace(map_data, zones=zones)
    fallback = map_positions(overlapping, area)
    assert len(set(fallback.values())) == len(zones)
    assert fallback == map_positions(overlapping, area)


def test_metadata_color_overrides_zone_type_color(tmp_path: Path) -> None:
    map_data = _map_data(tmp_path)
    assert metadata_color(map_data.zones["slow"]) == (255, 141, 69)
    assert metadata_color(map_data.zones["goal"]) != (255, 64, 94)


def test_offscreen_sdl_driver_is_not_reported_as_visible() -> None:
    assert has_visible_display("x11")
    assert has_visible_display("wayland")
    assert not has_visible_display("offscreen")
    assert not has_visible_display("dummy")


def test_drone_position_tracks_engine_zone_and_restricted_transit(
    tmp_path: Path,
) -> None:
    map_data = _map_data(tmp_path)
    engine = create_engine(map_data)
    engine.run()
    positions = map_positions(map_data, (0, 0, 800, 500))
    history = engine.state_history
    in_transit = next(
        state for frame in history for state in frame
        if state.transit_connection is not None
    )
    expected = (
        (positions["start"][0] + positions["slow"][0]) / 2,
        (positions["start"][1] + positions["slow"][1]) / 2,
    )
    assert drone_position(in_transit, positions) == expected
    assert connection_usage((in_transit,))[("slow", "start")] == 1
    at_start = history[0][0]
    assert drone_position(at_start, positions) == positions["start"]
