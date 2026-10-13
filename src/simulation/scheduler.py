from src.domain.graph import Graph, Edge
from src.domain.models import ZoneType

from src.simulation.models import Drone, PlannedMove, MoveKind


class Scheduler:
    """
    """
    def __init__(self, graph: Graph) -> None:
        """Initialize the scheduler with the map graph."""
        self._graph = graph

    def plan_turn(
            self,
            drones: list[Drone],
    ) -> list[PlannedMove]:
        """Plan valid movements for the current simulation turn."""
        raise NotImplementedError(
            "Turn planning has not been implemented yet."
        )

    def _collect_candidates(
            self,
            drones: list[Drone],
    ) -> list[PlannedMove]:
        """
        """
        candidates: list[PlannedMove] = []

        for dron in drones:
            # Ignoramos drones que ya han llegado al destino
            if dron.is_delivered:
                continue

            # Gestionamos transitos activos
            if dron.transit is not None:
                if dron.transit.turns_remaining == 1:
                    # Trannsito listo para completar
                    complete_move = PlannedMove(
                        drone_id=dron.drone_id,
                        origin=None,
                        destination=dron.transit.destination,
                        connection=dron.transit.connection,
                        kind=MoveKind.COMPLETE_TRANSIT
                    )
                    candidates.append(complete_move)

            origin = dron.current_zone
            destination = dron.next_zone

            if origin is None or destination is None:
                continue

            # Localizamos el edge de la conexion
            target_edge: Edge | None = None
            for edge in self._graph.get_neighbors(origin):
                if edge.target.name == destination:
                    target_edge = edge
                    break

            if target_edge is None:
                continue

            # Chequeamos el tipo de movimiento segun el destino
            target_zone = target_edge.target
            is_restricted = target_zone.zone_type == ZoneType.RESTRICTED
            move_kind = (MoveKind.START_TRANSIT
                         if is_restricted
                         else MoveKind.MOVE)

            planned_move = PlannedMove(
                drone_id=dron.drone_id,
                origin=origin,
                destination=destination,
                connection=target_edge.connection,
                kind=move_kind,
            )

            candidates.append(planned_move)

        return candidates
