"""Tests for the optional terminal dashboard."""

from dataclasses import replace
from io import StringIO
from pathlib import Path
import re
from typing import cast

from main import create_engine
from src.domain.models import MapData
from src.display.visualizer import TerminalVisualizer
from src.parser.map_parser import MapParser


def _load_map(tmp_path: Path) -> MapData:
    map_file = tmp_path / "neon.map"
    map_file.write_text(
        "nb_drones: 1\n"
        "start_hub: start 0 0 [color=cyan]\n"
        "hub: priority 1 1 [zone=priority color=magenta max_drones=2]\n"
        "hub: slow 2 0 [zone=restricted color=orange max_drones=1]\n"
        "hub: blocked 1 -1 [zone=blocked color=red]\n"
        "end_hub: goal 3 0 [color=green]\n"
        "connection: start-priority\n"
        "connection: priority-slow [max_link_capacity=1]\n"
        "connection: slow-goal\n"
        "connection: priority-blocked\n",
        encoding="utf-8",
    )
    return MapParser().parse_file(str(map_file))


def test_render_shows_topology_zone_types_metadata_colors_and_position(
    tmp_path: Path,
) -> None:
    map_data = _load_map(tmp_path)
    engine = create_engine(map_data)
    visualizer = TerminalVisualizer(map_data, engine)

    frame = visualizer.render(color=True)

    assert "FLY-IN // NEON CONTROL" in frame
    assert "start <-> priority" in frame
    assert "[normal]" in frame
    assert "[priority]" in frame
    assert "[restricted]" in frame
    assert "[blocked]" in frame
    assert "D01 AT start" in frame
    plain_frame = re.sub(r"\033\[[0-9;]*m", "", frame)
    assert "\n    1" in plain_frame
    assert "0/2" in frame
    assert "0/1" in frame
    assert "\033[38;5;208m" in frame  # El metadato naranja usa su color ANSI.


def test_render_shows_actual_restricted_transit_and_connection_load(
    tmp_path: Path,
) -> None:
    map_data = _load_map(tmp_path)
    engine = create_engine(map_data)
    engine.advance_turn()
    engine.advance_turn()

    frame = TerminalVisualizer(map_data, engine).render()

    assert "IN TRANSIT 01" in frame
    assert "D01 priority -> slow TRANSIT 1/2" in frame
    assert "priority <-> slow  1/1" in frame
    slow_capacity = next(
        line for line in frame.splitlines()
        if line.strip().startswith("slow ")
    )
    assert "0/1" in slow_capacity
    assert "D01 ENTERS priority -> slow (restricted transit 1/2)" in frame


def test_normal_move_counts_as_current_turn_connection_capacity(
    tmp_path: Path,
) -> None:
    map_data = _load_map(tmp_path)
    engine = create_engine(map_data)
    engine.advance_turn()

    frame = TerminalVisualizer(map_data, engine).render()

    assert "start <-> priority  1/1" in frame


def test_missing_coordinates_use_a_stable_fallback_layout(
    tmp_path: Path,
) -> None:
    original = _load_map(tmp_path)
    zones = {
        name: replace(zone, x=cast(int, None), y=cast(int, None))
        for name, zone in original.zones.items()
    }
    map_without_coordinates = MapData(
        nb_drones=original.nb_drones,
        zones=zones,
        connections=original.connections,
        start_hub=zones[original.start_hub.name],
        end_hub=zones[original.end_hub.name],
    )
    engine = create_engine(original)

    first = TerminalVisualizer(
        map_without_coordinates, engine
    ).render()
    second = TerminalVisualizer(
        map_without_coordinates, engine
    ).render()

    assert first == second
    assert "NODES" in first
    assert "blocked [blocked]" in first
    assert "goal [normal] END" in first


def test_non_interactive_visualizer_runs_without_waiting_for_input(
    tmp_path: Path,
) -> None:
    map_data = _load_map(tmp_path)
    engine = create_engine(map_data)
    output = StringIO()
    visualizer = TerminalVisualizer(
        map_data,
        engine,
        input_stream=StringIO(),
        output_stream=output,
    )

    visualizer.run()

    rendered = output.getvalue()
    assert engine.all_drones_delivered()
    assert "TURN 000" in rendered
    assert "TURN 004" in rendered
    assert "\033[" not in rendered
