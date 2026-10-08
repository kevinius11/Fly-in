from dataclasses import dataclass
from src.domain.models import Connection, MapData, Zone, ZoneType


@dataclass(frozen=True)
class Edge:
    """
    Represent a possible directed movement between two zones.

    An edge keeps the destination zone, the physical connection used
    for the movement, and the cost of entering the destination.

    Attributes:
        target: Zone reached after taking the edge.
        connection: Physical connection used by the movement.
        movement_cost: Number of turns required to enter the target.
    """
    target: Zone
    connection: Connection
    movement_cost: int


class Graph:
    """
    Represent the static map as an adjacency-list graph.

    The graph converts the connections stored in MapData into directed
    edges so that movement costs can differ depending on the destination
    zone type. Dynamic simulation state, such as drones and occupancy,
    does not belong in this class.
    """

    def __init__(self, map_data: MapData) -> None:
        """
        Build a graph from the parsed map data.

        Args:
            map_data: Validated static map containing zones and
                connections.

        Returns:
            None.
        """
        self._map_data = map_data
        self._adj: dict[str, list[Edge]] = {
            name: [] for name in map_data.zones}
        self._build_graph()

    def _get_movement_cost(self, target_zone: Zone) -> int:
        """
        Calculate the cost of entering a destination zone.

        Normal and priority zones require one turn to enter. Restricted
        zones require two turns. Blocked zones are inaccessible and
        therefore return a negative value.

        Args:
            target_zone: Zone being entered by the movement.

        Returns:
            One for normal or priority zones, two for restricted zones,
            or -1 when the destination is blocked.
        """
        if target_zone.zone_type == ZoneType.BLOCKED:
            return -1  # Inaccessible
        if target_zone.zone_type == ZoneType.RESTRICTED:
            return 2
        return 1  # NORMAL and PRIORITY cost 1

    def _build_graph(self) -> None:
        """
        Build bidirectional adjacency lists from map connections.

        Each physical connection can generate two directed edges. The
        cost of each edge depends on its destination zone. Connections
        involving blocked zones are excluded in both directions.

        Returns:
            None.
        """
        for conn in self._map_data.connections:
            z_a = self._map_data.zones[conn.zone_a]
            z_b = self._map_data.zones[conn.zone_b]

            # A blocked zone cannot be entered or left.
            if (
                z_a.zone_type == ZoneType.BLOCKED
                or z_b.zone_type == ZoneType.BLOCKED
            ):
                continue

            cost_b = self._get_movement_cost(z_b)
            if cost_b > 0:
                self._adj[z_a.name].append(
                    Edge(
                        target=z_b,
                        connection=conn,
                        movement_cost=cost_b,
                    )
                )

            cost_a = self._get_movement_cost(z_a)
            if cost_a > 0:
                self._adj[z_b.name].append(
                    Edge(
                        target=z_a,
                        connection=conn,
                        movement_cost=cost_a,
                    )
                )

    def get_neighbors(self, zone_name: str) -> list[Edge]:
        """
        Return accessible outgoing edges from a zone.

        Args:
            zone_name: Name of the zone whose outgoing edges are
                requested.

        Returns:
            List of accessible outgoing edges. An unknown zone returns
            an empty list.
        """
        return self._adj.get(zone_name, [])

    def get_zone(self, zone_name: str) -> Zone:
        """
        Return a zone from the original map by name.

        Args:
            zone_name: Name of the requested zone.

        Returns:
            The corresponding Zone object.

        Raises:
            KeyError: If the requested zone does not exist.
        """
        return self._map_data.zones[zone_name]

    def get_zone_names(self) -> list[str]:
        """
        Return the names of all zones in the graph.

        Returns:
            A list containing the name of every zone in the graph.
        """
        return list(self._map_data.zones.keys())
