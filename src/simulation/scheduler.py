from src.domain.graph import Graph, Edge
from src.domain.models import ZoneType, Connection

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
        candidates = self._collect_candidates(drones)
        approved_moves = self._select_compatible_moves(candidates, drones)
        return approved_moves

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
                    # Transito listo para completar
                    complete_move = PlannedMove(
                        drone_id=dron.drone_id,
                        origin=None,
                        destination=dron.transit.destination,
                        connection=dron.transit.connection,
                        kind=MoveKind.COMPLETE_TRANSIT
                    )
                    candidates.append(complete_move)
                    continue

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

    def _select_compatible_moves(
            self,
            candidates: list[PlannedMove],
            drones: list[Drone],
    ) -> list[PlannedMove]:
        """Select movements that respect zone and connectionn capacities"""
        approved_movements: list[PlannedMove] = []

        complete_transits = [
            m for m in candidates if m.kind == MoveKind.COMPLETE_TRANSIT
        ]

        ordinary_moves = [
            m for m in candidates if m.kind != MoveKind.COMPLETE_TRANSIT
        ]

        # Aprobar primero todos los transitos completados
        approved_movements.extend(complete_transits)

        # Evaluamos candidatos ordinarios en secuencia
        for candidate in ordinary_moves:
            test_moves = approved_movements + [candidate]

            # Verificamos capacidad de conexiones para el conjunto
            if not self._connection_capacities_respected(test_moves, drones):
                continue

            # Calculamos la ocupacion y posibles reservas
            projected_occupancy = self._calculate_final_zone_occupancy(
                test_moves, drones
            )

            future_reservations = self._calculate_reserved_arrivals(
                test_moves, drones
            )

            # Comprobamos formula Op + FutReservas <= CapacidadZona
            violates_zone_capacity = False
            for zone_name, count in projected_occupancy.items():
                zone = self._graph.get_zone(zone_name)
                if zone.is_start or zone.is_end:
                    continue

                total_demand = count + future_reservations.get(zone_name, 0)
                if total_demand > zone.max_drones:
                    violates_zone_capacity = True
                    break

            if violates_zone_capacity:
                continue

            # Si pasa las comprobaciones
            approved_movements.append(candidate)

        return approved_movements

    def _calculate_final_zone_occupancy(
            self,
            moves: list[PlannedMove],
            drones: list[Drone],
    ) -> dict[str, int]:
        """Calculate zone occupancy after a simultaneous set of movements."""
        occupancy: dict[str, int] = {}

        # Contamos drones menos los que esten entregados o en transito
        for name in self._graph.get_zone_names():
            occupancy[name] = sum(
                1 for d in drones
                if d.current_zone == name and not d.is_delivered
            )

        # Ajustamos segun salidas y entradas
        for move in moves:
            if move.destination not in occupancy:
                raise ValueError(
                    f"Destination zone '{move.destination}' for drone "
                    f"{move.drone_id} does not exist in the map graph."
                )
            # Si el dron sale de normal/restrictesd liberamos plaza
            if move.kind in (MoveKind.MOVE, MoveKind.START_TRANSIT):
                if move.origin is None:
                    raise ValueError(
                        f"Malformed PlannedMove  of type {move.kind.name}: "
                        f"drone {move.drone_id} must have a valid origin zone."
                    )
                if move.origin not in occupancy:
                    raise ValueError(
                        f"Origin zone '{move.origin}' for drone "
                        f"{move.drone_id} does not exist in the map graph."
                    )
                occupancy[move.origin] -= 1

            # Si el dron entra o completa un transito incrementa plaza
            if move.kind in (MoveKind.MOVE, MoveKind.COMPLETE_TRANSIT):
                occupancy[move.destination] += 1

        return occupancy

    def _zone_capacities_respected(
            self,
            occupancy: dict[str, int],
    ) -> bool:
        """Check whether final zone occupancy respects zone capacities."""
        for zone_name, count in occupancy.items():
            if count < 0:  # Ocupacion negativa
                return False

            zone = self._graph.get_zone(zone_name)

            if zone.is_start or zone.is_end:
                continue

            if count > zone.max_drones:
                return False

        return True

    def _connection_capacities_respected(
        self,
        moves: list[PlannedMove],
        drones: list[Drone],
    ) -> bool:
        """Check whether connection usage respects link capacities."""
        return self._find_connection_capacity_violation(moves, drones) is None

    def _find_zone_capacity_violation(
        self,
        occupancy: dict[str, int],
    ) -> str | None:
        """Return a zone violating occupancy constraints, if any."""
        for zone_name, count in occupancy.items():
            # Chequeo negativos
            if count < 0:
                return zone_name

            zone = self._graph.get_zone(zone_name)

            # Chequeamos inicio y fin
            if zone.is_start or zone.is_end:
                continue

            # Comprobamos capacidad
            if count > zone.max_drones:
                return zone_name

        return None

    def _find_connection_capacity_violation(
        self,
        moves: list[PlannedMove],
        drones: list[Drone],
    ) -> Connection | None:
        """Return an over-capacity connection, if any."""
        connection_usage: dict[frozenset[str], int] = {}
        connection_capacities: dict[frozenset[str], int] = {}
        connections: dict[frozenset[str], Connection] = {}

        # Chequeamos cuantos drones ya estabana activos antes del turno
        for drone in drones:
            if drone.transit is not None:
                conn = drone.transit.connection
                key = frozenset((conn.zone_a, conn.zone_b))
                connection_usage[key] = connection_usage.get(key, 0) + 1
                connection_capacities[key] = conn.max_link_capacity
                connections[key] = conn

        # Chequeamos posibles candidatos MoveKind
        for move in moves:
            if move.kind in (MoveKind.MOVE, MoveKind.START_TRANSIT):
                conn = move.connection
                key = frozenset((conn.zone_b, conn.zone_a))
                connection_usage[key] = connection_usage.get(key, 0) + 1
                connection_capacities[key] = conn.max_link_capacity
                connections[key] = conn

        # Chequeamos si se supera la capacidad de conexion
        for key, usage in connection_usage.items():
            if usage > connection_capacities[key]:
                return connections[key]

        return None

    def _calculate_reserved_arrivals(
        self,
        moves: list[PlannedMove],
        drones: list[Drone],
    ) -> dict[str, int]:
        """Count future arrivals reserved by active and planned transits."""
        # Iniciamos contador a 0 para todas las zonas del grafo
        reserved: dict[str, int] = {
            zone_name: 0
            for zone_name in self._graph.get_zone_names()
        }

        # Contamos transitos que no se completan en este turno
        for drone in drones:
            if (drone.transit is not None
               and drone.transit.turns_remaining > 1):
                dest = drone.transit.destination
                if dest in reserved:
                    reserved[dest] += 1

        # Contar reservas para los posibles nuevos movimientos de transito
        for move in moves:
            if move.kind == MoveKind.START_TRANSIT:
                dest = move.destination
                if dest in reserved:
                    reserved[dest] += 1

        return reserved
