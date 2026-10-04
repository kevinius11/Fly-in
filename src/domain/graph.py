from dataclasses import dataclass
from src.domain.models import Connection, MapData, Zone, ZoneType


@dataclass(frozen=True)
class Edge:
    target: Zone
    connection: Connection
    movement_cost: int


class Graph:
    """Adjacency list representation of the map graph."""

    def __init__(self, map_data: MapData) -> None:
        self._map_data = map_data
        self._adj: dict[str, list[Edge]] = {
            name: [] for name in map_data.zones}
        self._build_graph()

    def _get_movement_cost(self, target_zone: Zone) -> int:
        """"""
        if target_zone.zone_type == ZoneType.BLOCKED:
            return -1  # Inaccessible
        if target_zone.zone_type == ZoneType.RESTRICTED:
            return 2
        return 1  # NORMAL and PRIORITY cost 1

    def _build_graph(self) -> None:
        """"""
        for conn in self._map_data.connections:
            z_a = self._map_data.zones[conn.zone_a]
            z_b = self._map_data.zones[conn.zone_b]

            # Direct connection A -> B (valid if both A and B are NOT blocked)
            if (z_a.zone_type != ZoneType.BLOCKED
               and z_b.zone_type != ZoneType.BLOCKED):
                cost_b = self._get_movement_cost(z_b)
                self._adj[conn.zone_a].append(
                    Edge(target=z_b, connection=conn, movement_cost=cost_b)
                )

                cost_a = self._get_movement_cost(z_a)
                self._adj[conn.zone_b].append(
                    Edge(target=z_a, connection=conn, movement_cost=cost_a)
                )

    def get_neighbors(self, zone_name: str) -> list[Edge]:
        """"""
        return self._adj.get(zone_name, [])

    def get_zone(self, zone_name: str) -> Zone:
        """"""
        return self._map_data.zones[zone_name]
