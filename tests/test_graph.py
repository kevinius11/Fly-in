from src.domain.graph import Graph
from src.domain.models import Connection, MapData, Zone, ZoneType


def test_graph_blocked_isolation():
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.BLOCKED, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(1, {"A": z_a, "B": z_b}, [conn], z_a, z_a)

    graph = Graph(map_data)
    assert len(graph.get_neighbors("A")) == 0
    assert len(graph.get_neighbors("B")) == 0


def test_graph_asymmetric_costs():
    z_a = Zone("A", 0, 0, ZoneType.NORMAL, 1)
    z_b = Zone("B", 1, 1, ZoneType.RESTRICTED, 1)
    conn = Connection("A", "B", 1)
    map_data = MapData(1, {"A": z_a, "B": z_b}, [conn], z_a, z_a)

    graph = Graph(map_data)

    # A -> B cost should be 2 (target B is RESTRICTED)
    a_edges = graph.get_neighbors("A")
    assert len(a_edges) == 1
    assert a_edges[0].movement_cost == 2

    # B -> A cost should be 1 (target A is NORMAL)
    b_edges = graph.get_neighbors("B")
    assert len(b_edges) == 1
    assert b_edges[0].movement_cost == 1
