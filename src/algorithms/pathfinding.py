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
    _validate_endpoints(graph, start_name, end_name)
    return _shortest_path(
        graph,
        start_name,
        end_name,
        excluded_nodes=set(),
        excluded_edges=set(),
    )


def find_k_shortest_paths(
        graph: Graph,
        start_name: str,
        end_name: str,
        k: int = 2,
) -> list[list[str]]:
    """Return up to ``k`` unique simple paths ordered by route score.

    Yen's algorithm generates alternatives without enumerating every path.
    Route score minimizes movement cost first and prefers more priority
    zones only when movement costs tie.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}.")
    _validate_endpoints(graph, start_name, end_name)

    first_path = _shortest_path(
        graph,
        start_name,
        end_name,
        excluded_nodes=set(),
        excluded_edges=set(),
    )
    if first_path is None:
        return []

    shortest_paths = [first_path]
    accepted = {tuple(first_path)}
    candidates: list[tuple[int, int, tuple[str, ...]]] = []
    queued = set()

    while len(shortest_paths) < k:
        previous_path = shortest_paths[-1]
        for spur_index in range(len(previous_path) - 1):
            root_path = previous_path[:spur_index + 1]
            spur_node = root_path[-1]
            excluded_edges = {
                (path[spur_index], path[spur_index + 1])
                for path in shortest_paths
                if len(path) > spur_index + 1
                and path[:spur_index + 1] == root_path
            }
            spur_path = _shortest_path(
                graph,
                spur_node,
                end_name,
                excluded_nodes=set(root_path[:-1]),
                excluded_edges=excluded_edges,
            )
            if spur_path is None:
                continue

            candidate = tuple(root_path[:-1] + spur_path)
            if candidate in accepted or candidate in queued:
                continue
            candidate_cost, negative_priority_count = _path_score(
                graph, candidate
            )
            heapq.heappush(
                candidates,
                (candidate_cost, negative_priority_count, candidate),
            )
            queued.add(candidate)

        if not candidates:
            break

        _, _, next_path = heapq.heappop(candidates)
        queued.remove(next_path)
        accepted.add(next_path)
        shortest_paths.append(list(next_path))

    return shortest_paths


def _validate_endpoints(
        graph: Graph,
        start_name: str,
        end_name: str,
) -> None:
    """Raise ValueError when either endpoint is absent from the graph."""
    zone_names = graph.get_zone_names()
    if start_name not in zone_names:
        raise ValueError(
            f"Start zone '{start_name}' does not exist in the graph."
        )
    if end_name not in zone_names:
        raise ValueError(
            f"End zone '{end_name}' does not exist in the graph."
        )


def _shortest_path(
        graph: Graph,
        start_name: str,
        end_name: str,
        excluded_nodes: set[str],
        excluded_edges: set[tuple[str, str]],
) -> list[str] | None:
    """Find the best path while omitting selected nodes and directed edges."""
    if start_name in excluded_nodes or end_name in excluded_nodes:
        return None

    zone_names = graph.get_zone_names()
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
            if (neighbor in excluded_nodes
                    or (node, neighbor) in excluded_edges):
                continue
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


def _path_score(graph: Graph, path: tuple[str, ...]) -> tuple[int, int]:
    """Return movement cost and negative priority-zone count for a path."""
    cost = 0
    priority_count = 0
    for origin, destination in zip(path, path[1:]):
        edge = next(
            edge
            for edge in graph.get_neighbors(origin)
            if edge.target.name == destination
        )
        cost += edge.movement_cost
        priority_count += int(edge.target.zone_type == ZoneType.PRIORITY)
    return cost, -priority_count
