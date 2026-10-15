import heapq

from src.domain.graph import Graph
from src.domain.models import ZoneType


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
    zone_names = graph.get_zone_names()

    if start_name not in zone_names:
        raise ValueError(
            f"Start zone '{start_name}' does not exist in the graph."
        )

    if end_name not in zone_names:
        raise ValueError(
            f"End zone '{end_name}' does not exist in the graph."
        )

    best_score: dict[str, tuple[int, int] | None] = {
        name: None for name in zone_names
    }
    previous: dict[str, str | None] = {
        node: None
        for node in zone_names
    }

    # Scores are ordered by movement cost first, then by descending number
    # of priority zones (stored as a negative count for tuple ordering).
    best_score[start_name] = (0, 0)
    pq: list[tuple[int, int, str]] = [(0, 0, start_name)]

    while pq:
        cost, negative_priority_count, node = heapq.heappop(pq)
        score = (cost, negative_priority_count)

        if score != best_score[node]:
            continue

        if node == end_name:  # Si el nodo que acaba de salir es el destino
            break

        for edge in graph.get_neighbors(node):
            neighbor = edge.target.name
            new_score = (
                cost + edge.movement_cost,
                negative_priority_count
                - int(edge.target.zone_type == ZoneType.PRIORITY),
            )

            current_score = best_score[neighbor]
            if current_score is None or new_score < current_score:
                best_score[neighbor] = new_score
                previous[neighbor] = node
                heapq.heappush(
                    pq,
                    (new_score[0], new_score[1], neighbor),
                )

    # El destino es inalcanzable
    if best_score[end_name] is None:
        return None

    # Reconstruccion del camino path, usando BACKTRACKING
    path: list[str] = []
    curr: str | None = end_name

    while curr is not None:
        path.append(curr)
        curr = previous[curr]

    path.reverse()
    return path
