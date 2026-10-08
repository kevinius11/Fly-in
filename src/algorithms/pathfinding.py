from domain.graph import Graph

import heapq


def find_shortest_path(
        graph: Graph,
        start_name: str,
        end_name: str,
) -> list[str] | None:
    """
    """
    dist = {
        node: float("inf")
        for node in graph.get_zone_names()
    }
    dist[start_name] = 0
    pq = [(0, start_name)]  # (distance, node)

    while pq:
        d, node = heapq.heappop(pq)
        if d > dist[node]:
            continue

        for neighbor, weight in graph[node]:
            new_dist = d + weight
            if new_dist < dist[neighbor]:
                dist[neighbor] = new_dist
                heapq.heappush(pq, (new_dist, neighbor))
    return dist
