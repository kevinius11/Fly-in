from domain.graph import Graph

import heapq


def find_shortest_path(
        graph: Graph,
        start_name: str,
        end_name: str,
) -> list[str] | None:
    """
    """
    nodes = len(graph._map_data.zones)

    heap = []
    dist = [float('inf')] * nodes
    adj = graph._adj

    dist[start_name] = 0
    heapq.heappush(heap, (0, start_name))

    while heap:
        d, u = heapq.heappop(heap)

        if d > dist[u]:
            continue

        for v, w in adj[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))
    return None
