from src.domain.graph import Graph

import heapq


def find_shortest_path(
        graph: Graph,
        start_name: str,
        end_name: str,
) -> list[str] | None:
    """
    Find the shortest path between two zones using Dijkstra's algorithm

    Computes the path with the minimum cumulative movement cost from the
    start zone to the target end zone over the provided graph topology.

    Args:
        graph: The graph instance representing the map topology and edge costs.
        start_name: The name of the starting zone.
        end_name: The name of the destination zone.

    Returns:
        A list of zone names forming the ordered path from start_name to
        end name, or None if the destination is unreachable.

    Raises:
        ValueError: If start_name or end_name does not exist in the graph.
    """
    if not graph.get_zone(start_name):
        raise ValueError(
            f"Start zone: '{start_name}' does not exist in graph."
            )

    if not graph.get_zone(end_name):
        raise ValueError(
            f"End zone: '{end_name}' does not exist in graph."
            )

    dist: dict[str, float] = {
        name: float("inf")
        for name in graph.get_zone_names()
    }
    previous: dict[str, str | None] = {
        node: None
        for node in graph.get_zone_names()
    }

    dist[start_name] = 0
    pq: list[tuple[float, str]] = [(0, start_name)]  # (distance, node)

    while pq:
        d, node = heapq.heappop(pq)

        if d > dist[node]:
            continue

        if node == end_name:  # Si el nodo que acaba de salir es el destino
            break

        for edge in graph.get_neighbors(node):
            neighbor = edge.target.name
            new_dist = d + edge.movement_cost

            if new_dist < dist[neighbor]:
                dist[neighbor] = new_dist
                previous[neighbor] = node
                heapq.heappush(pq, (new_dist, neighbor))

    # El destino es inalcanzable
    if dist[end_name] == float("inf"):
        return None

    # Reconstruccion del camino path, usando BACKTRACKING
    path: list[str] = []
    curr: str | None = end_name

    while curr is not None:
        path.append(curr)
        curr = previous[curr]

    path.reverse()
    return path
