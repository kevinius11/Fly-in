from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType


def test_graph_blocked_isolation() -> None:
    """Ensure blocked zones have no incoming or outgoing edges."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.BLOCKED, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    assert len(graph.get_neighbors("A")) == 0
    assert len(graph.get_neighbors("B")) == 0


def test_graph_asymmetric_costs() -> None:
    """Verify that movement cost depends on the destination zone."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.RESTRICTED, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    # A -> B costs 2 because B is RESTRICTED.
    a_edges = graph.get_neighbors("A")
    assert len(a_edges) == 1
    assert a_edges[0].movement_cost == 2

    # B -> A costs 1 because A is NORMAL.
    b_edges = graph.get_neighbors("B")
    assert len(b_edges) == 1
    assert b_edges[0].movement_cost == 1

    # Each edge must point to the correct destination.
    assert a_edges[0].target is z_b
    assert b_edges[0].target is z_a

    # Both directions use the same physical connection.
    assert a_edges[0].connection is conn
    assert b_edges[0].connection is conn


def test_graph_is_bidirectional() -> None:
    """Ensure a normal connection creates edges in both directions."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    a_edges = graph.get_neighbors("A")
    b_edges = graph.get_neighbors("B")

    assert len(a_edges) == 1
    assert len(b_edges) == 1
    assert a_edges[0].target is z_b
    assert b_edges[0].target is z_a


def test_graph_priority_cost_is_one() -> None:
    """Ensure entering a priority zone costs one turn."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.PRIORITY, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    a_edges = graph.get_neighbors("A")

    assert len(a_edges) == 1
    assert a_edges[0].movement_cost == 1
    assert a_edges[0].target is z_b


def test_graph_normal_cost_is_one() -> None:
    """Ensure entering a normal zone costs one turn."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    a_edges = graph.get_neighbors("A")

    assert len(a_edges) == 1
    assert a_edges[0].movement_cost == 1


def test_graph_restricted_cost_is_two() -> None:
    """Ensure entering a restricted zone costs two turns."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.RESTRICTED, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    a_edges = graph.get_neighbors("A")

    assert len(a_edges) == 1
    assert a_edges[0].movement_cost == 2


def test_graph_preserves_connection_capacity() -> None:
    """Ensure edge objects preserve the original connection capacity."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    conn = Connection("A", "B", 7)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    a_edges = graph.get_neighbors("A")
    b_edges = graph.get_neighbors("B")

    assert len(a_edges) == 1
    assert len(b_edges) == 1
    assert a_edges[0].connection.max_link_capacity == 7
    assert b_edges[0].connection.max_link_capacity == 7
    assert a_edges[0].connection is conn
    assert b_edges[0].connection is conn


def test_graph_keeps_blocked_zone_as_node() -> None:
    """Ensure blocked zones remain in the adjacency dictionary."""
    z_a = Zone("A", 0, 0, ZoneType.BLOCKED, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [conn],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    assert graph.get_neighbors("A") == []
    assert graph.get_neighbors("B") == []


def test_graph_unknown_zone_returns_empty_neighbors() -> None:
    """Ensure unknown zones return an empty neighbor list."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    assert graph.get_neighbors("UNKNOWN") == []


def test_graph_get_zone_returns_correct_zone() -> None:
    """Ensure get_zone returns the expected Zone object."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    assert graph.get_zone("A") is z_a
    assert graph.get_zone("B") is z_b


def test_graph_get_zone_unknown_raises_key_error() -> None:
    """Ensure get_zone raises KeyError for an unknown zone."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    map_data = MapData(
        1,
        {"A": z_a, "B": z_b},
        [],
        z_a,
        z_b,
    )

    graph = Graph(map_data)

    try:
        graph.get_zone("UNKNOWN")
        assert False, "Expected KeyError was not raised."
    except KeyError:
        pass


def test_graph_get_zone_names() -> None:
    """Ensure get_zone_names returns every zone name."""
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.NORMAL, 1)
    z_c = Zone("C", 2, 2, ZoneType.RESTRICTED, 1)

    map_data = MapData(
        1,
        {
            "A": z_a,
            "B": z_b,
            "C": z_c,
        },
        [],
        z_a,
        z_c,
    )

    graph = Graph(map_data)

    zone_names = graph.get_zone_names()

    assert zone_names == ["A", "B", "C"]
