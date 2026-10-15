
import pytest

from src.algorithms.pathfinding import find_shortest_path
from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType


def _build_graph(
    zone_types: dict[str, ZoneType],
    connection_specs: list[tuple[str, str, int]],
    start_name: str,
    end_name: str,
) -> Graph:
    """Build a Graph from zone types and connection specifications.

    Args:
        zone_types: Mapping of zone names to their types.
        connection_specs: Tuples containing the names of the connected
            zones and the connection capacity.
        start_name: Name of the start zone.
        end_name: Name of the end zone.

    Returns:
        A Graph ready for pathfinding tests.
    """
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


def test_find_shortest_path_direct() -> None:
    """Find the shortest path when the zones are directly connected."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    path = find_shortest_path(graph, "start", "goal")

    assert path == ["start", "goal"]


def test_find_shortest_path_minimizes_total_cost() -> None:
    """Prefer a cheaper path even when it contains more edges.

    The direct alternative through restricted zones costs five turns.
    The longer route through normal zones costs four turns.
    """
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "r1": ZoneType.RESTRICTED,
            "r2": ZoneType.RESTRICTED,
            "a": ZoneType.NORMAL,
            "b": ZoneType.NORMAL,
            "c": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "r1", 1),
            ("r1", "r2", 1),
            ("r2", "goal", 1),
            ("start", "a", 1),
            ("a", "b", 1),
            ("b", "c", 1),
            ("c", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    path = find_shortest_path(graph, "start", "goal")

    assert path == ["start", "a", "b", "c", "goal"]


def test_find_shortest_path_prefers_priority_when_costs_tie() -> None:
    """Prefer more priority zones only when total movement cost ties."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "a": ZoneType.NORMAL,
            "priority": ZoneType.PRIORITY,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "a", 1),
            ("a", "goal", 1),
            ("start", "priority", 1),
            ("priority", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    assert find_shortest_path(graph, "start", "goal") == [
        "start", "priority", "goal",
    ]


def test_find_shortest_path_cost_precedes_priority_preference() -> None:
    """A cheaper route wins even if the longer route has priority zones."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "a": ZoneType.NORMAL,
            "priority": ZoneType.PRIORITY,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "a", 1),
            ("a", "goal", 1),
            ("start", "priority", 1),
            ("priority", "a", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    assert find_shortest_path(graph, "start", "goal") == [
        "start", "a", "goal",
    ]


def test_find_shortest_path_avoids_blocked_zones() -> None:
    """Find an alternative route instead of entering a blocked zone."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "blocked": ZoneType.BLOCKED,
            "detour": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "blocked", 1),
            ("blocked", "goal", 1),
            ("start", "detour", 1),
            ("detour", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    path = find_shortest_path(graph, "start", "goal")

    assert path == ["start", "detour", "goal"]


def test_find_shortest_path_unreachable() -> None:
    """Return None when no path connects the start and destination."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "a": ZoneType.NORMAL,
            "b": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "a", 1),
            ("b", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    path = find_shortest_path(graph, "start", "goal")

    assert path is None


def test_find_shortest_path_start_equals_end() -> None:
    """Return a single-zone path when start and destination are equal."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
        },
        connection_specs=[],
        start_name="start",
        end_name="start",
    )

    path = find_shortest_path(graph, "start", "start")

    assert path == ["start"]


def test_find_shortest_path_unknown_start_raises_value_error() -> None:
    """Raise ValueError when the starting zone does not exist."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    with pytest.raises(ValueError, match="Start zone"):
        find_shortest_path(graph, "unknown", "goal")


def test_find_shortest_path_unknown_end_raises_value_error() -> None:
    """Raise ValueError when the destination zone does not exist."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    with pytest.raises(ValueError, match="End zone"):
        find_shortest_path(graph, "start", "unknown")


def test_find_shortest_path_returns_correct_order() -> None:
    """Return the path from start to destination, not in reverse."""
    graph = _build_graph(
        zone_types={
            "start": ZoneType.NORMAL,
            "a": ZoneType.NORMAL,
            "b": ZoneType.NORMAL,
            "goal": ZoneType.NORMAL,
        },
        connection_specs=[
            ("start", "a", 1),
            ("a", "b", 1),
            ("b", "goal", 1),
        ],
        start_name="start",
        end_name="goal",
    )

    path = find_shortest_path(graph, "start", "goal")

    assert path == ["start", "a", "b", "goal"]
    assert path[0] == "start"
    assert path[-1] == "goal"
