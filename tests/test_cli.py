"""Tests for the standard command-line simulation output."""

import sys
from pathlib import Path

import pytest

from main import main


def test_cli_prints_only_moved_drone_tokens_per_turn(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Use the required compact zone-token output for each turn."""
    map_file = tmp_path / "linear.map"
    map_file.write_text(
        "nb_drones: 2\n"
        "start_hub: start 0 0\n"
        "hub: middle 1 0\n"
        "end_hub: goal 2 0\n"
        "connection: start-middle\n"
        "connection: middle-goal\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["main.py", str(map_file)])

    result = main()

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == (
        "D1-middle\n"
        "D1-goal D2-middle\n"
        "D2-goal\n"
    )
    assert captured.err == ""


def test_cli_reports_restricted_connection_during_transit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Show the connection at transit start and zone on arrival."""
    map_file = tmp_path / "restricted.map"
    map_file.write_text(
        "nb_drones: 1\n"
        "start_hub: start 0 0\n"
        "hub: slow 1 0 [zone=restricted]\n"
        "end_hub: goal 2 0\n"
        "connection: start-slow\n"
        "connection: slow-goal\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["main.py", str(map_file)])

    result = main()

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == "D1-start-slow\nD1-slow\nD1-goal\n"
    assert captured.err == ""


def test_cli_reports_no_route_as_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Do not pass an unreachable route to the engine or traceback."""
    map_file = tmp_path / "unreachable.map"
    map_file.write_text(
        "nb_drones: 1\n"
        "start_hub: start 0 0\n"
        "end_hub: goal 1 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["main.py", str(map_file)])

    result = main()

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert "Error: No route exists" in captured.err
