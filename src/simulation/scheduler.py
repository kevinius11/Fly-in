"""Plan simultaneous drone movements while respecting map capacities."""

from src.domain.graph import Graph, Edge
from src.domain.models import ZoneType, Connection

from src.simulation.models import Drone, PlannedMove, MoveKind


class Scheduler:
    """Choose valid movement plans for one simulation turn.

    The scheduler reads static graph data and current drone states. It does
    not mutate drones; the engine applies the approved plan.
    """
    def __init__(self, graph: Graph) -> None:
        """Initialize the scheduler with the map graph.

        Args:
            graph: Static graph used to inspect zones, links, and capacities.
        """
        self._graph = graph

    def is_restricted_zone(self, zone_name: str) -> bool:
        """Check whether a zone requires a two-turn transit.

        Args:
            zone_name: Name of the zone to inspect.

        Returns:
            True when the zone is restricted; otherwise False.
        """
        return self._graph.get_zone(zone_name).zone_type == ZoneType.RESTRICTED

    def is_blocked_zone(self, zone_name: str) -> bool:
        """Check whether a zone is inaccessible to drones.

        Args:
            zone_name: Name of the zone to inspect.

        Returns:
            True when the zone is blocked; otherwise False.
        """
        return self._graph.get_zone(zone_name).zone_type == ZoneType.BLOCKED

    def plan_turn(
            self,
            drones: list[Drone],
    ) -> list[PlannedMove]:
        """Plan movements that satisfy zone and link capacities.

        Args:
            drones: Current drone states to plan movements for.

        Returns:
            Approved moves for the turn, in scheduling order.
        """
        candidates = self._collect_candidates(drones)
        approved_moves = self._select_compatible_moves(candidates, drones)
        return approved_moves

    def _collect_candidates(
            self,
            drones: list[Drone],
    ) -> list[PlannedMove]:
        """Create movement candidates for drones that can advance.

        Args:
            drones: Current drone states to inspect.

        Returns:
            Candidate moves, including due transit completions.
        """
        candidates: list[PlannedMove] = []

        for dron in drones:
            # Los drones entregados no necesitan más movimientos.
            if dron.is_delivered:
                continue

            # El tránsito activo conserva su conexión hasta completarse.
            if dron.transit is not None:
                if dron.transit.turns_remaining == 1:
                    # El tránsito termina cuando queda un turno.
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

            # La ruta debe coincidir con una conexión accesible del grafo.
            target_edge: Edge | None = None
            for edge in self._graph.get_neighbors(origin):
                if edge.target.name == destination:
                    target_edge = edge
                    break

            if target_edge is None:
                continue

            # Entrar en una zona restringida inicia un tránsito de dos turnos.
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
        """Select movements that respect zone and connection capacities.

        Args:
            candidates: Potential moves collected for this turn.
            drones: Current drone states used to calculate occupancy.

        Returns:
            A compatible subset of candidates.
        """
        approved_movements: list[PlannedMove] = []

        complete_transits = [
            m for m in candidates if m.kind == MoveKind.COMPLETE_TRANSIT
        ]

        ordinary_moves = [
            m for m in candidates if m.kind != MoveKind.COMPLETE_TRANSIT
        ]

        # Las llegadas liberan conexiones antes de evaluar movimientos nuevos.
        approved_movements.extend(complete_transits)

        # Se evalúan los demás candidatos respetando su orden de planificación.
        for candidate in ordinary_moves:
            test_moves = approved_movements + [candidate]

            # La capacidad del enlace incluye los tránsitos que siguen activos.
            if not self._connection_capacities_respected(test_moves, drones):
                continue

            # Se proyecta la ocupación y se reservan llegadas futuras.
            projected_occupancy = self._calculate_final_zone_occupancy(
                test_moves, drones
            )

            future_reservations = self._calculate_reserved_arrivals(
                test_moves, drones
            )

            # La ocupación más las reservas no puede superar la capacidad.
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

            # Solo se aprueban movimientos compatibles con ambas capacidades.
            approved_movements.append(candidate)

        return approved_movements

    def _calculate_final_zone_occupancy(
            self,
            moves: list[PlannedMove],
            drones: list[Drone],
    ) -> dict[str, int]:
        """Calculate zone occupancy after simultaneous movements.

        Args:
            moves: Moves considered for the turn.
            drones: Current drone states before those moves are applied.

        Returns:
            Projected occupancy indexed by zone name.

        Raises:
            ValueError: If a move references an unknown origin or destination,
                or requires an origin but does not provide one.
        """
        occupancy: dict[str, int] = {}

        # Los entregados y los que viajan no ocupan una zona intermedia.
        for name in self._graph.get_zone_names():
            occupancy[name] = sum(
                1 for d in drones
                if d.current_zone == name and not d.is_delivered
            )

        # Se aplican primero las salidas y luego las entradas proyectadas.
        for move in moves:
            if move.destination not in occupancy:
                raise ValueError(
                    f"Destination zone '{move.destination}' for drone "
                    f"{move.drone_id} does not exist in the map graph."
                )
            # Salir de una zona libera su plaza en este turno.
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

            # Entrar o completar tránsito ocupa la plaza de destino.
            if move.kind in (MoveKind.MOVE, MoveKind.COMPLETE_TRANSIT):
                occupancy[move.destination] += 1

        return occupancy

    def _zone_capacities_respected(
            self,
            occupancy: dict[str, int],
    ) -> bool:
        """Check whether projected occupancy respects zone capacities.

        Args:
            occupancy: Projected drone count for each zone.

        Returns:
            True if all counts satisfy the applicable capacity limits.
        """
        for zone_name, count in occupancy.items():
            if count < 0:  # Una zona no puede tener ocupación negativa.
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
        """Check whether planned connection use respects link capacity.

        Args:
            moves: Moves being evaluated.
            drones: Current drones, including any active transits.

        Returns:
            True if no connection exceeds its capacity.
        """
        return self._find_connection_capacity_violation(moves, drones) is None

    def _find_zone_capacity_violation(
        self,
        occupancy: dict[str, int],
    ) -> str | None:
        """Find the first zone that violates occupancy constraints.

        Args:
            occupancy: Projected drone count for each zone.

        Returns:
            The violating zone name, or None when occupancy is valid.
        """
        for zone_name, count in occupancy.items():
            # Una ocupación negativa indica una salida inválida.
            if count < 0:
                return zone_name

            zone = self._graph.get_zone(zone_name)

            # Los hubs no tienen límite de ocupación en el planificador.
            if zone.is_start or zone.is_end:
                continue

            # Las demás zonas respetan su capacidad declarada.
            if count > zone.max_drones:
                return zone_name

        return None

    def _find_connection_capacity_violation(
        self,
        moves: list[PlannedMove],
        drones: list[Drone],
    ) -> Connection | None:
        """Find a connection whose projected use exceeds its capacity.

        Args:
            moves: Moves being evaluated.
            drones: Current drones, including any active transits.

        Returns:
            The violating connection, or None when all links are valid.
        """
        connection_usage: dict[frozenset[str], int] = {}
        connection_capacities: dict[frozenset[str], int] = {}
        connections: dict[frozenset[str], Connection] = {}

        # Se cuentan primero los drones que ya ocupan cada conexión.
        for drone in drones:
            if drone.transit is not None:
                conn = drone.transit.connection
                key = frozenset((conn.zone_a, conn.zone_b))
                connection_usage[key] = connection_usage.get(key, 0) + 1
                connection_capacities[key] = conn.max_link_capacity
                connections[key] = conn

        # Los movimientos aprobados también consumen capacidad del enlace.
        for move in moves:
            if move.kind in (MoveKind.MOVE, MoveKind.START_TRANSIT):
                conn = move.connection
                key = frozenset((conn.zone_b, conn.zone_a))
                connection_usage[key] = connection_usage.get(key, 0) + 1
                connection_capacities[key] = conn.max_link_capacity
                connections[key] = conn

        # Se rechaza el conjunto si algún enlace supera su límite.
        for key, usage in connection_usage.items():
            if usage > connection_capacities[key]:
                return connections[key]

        return None

    def _calculate_reserved_arrivals(
        self,
        moves: list[PlannedMove],
        drones: list[Drone],
    ) -> dict[str, int]:
        """Count zone arrivals reserved by active and planned transits.

        Args:
            moves: Moves planned for the current turn.
            drones: Current drones and their active transits.

        Returns:
            Future arrival counts indexed by destination zone name.
        """
        # Cada zona empieza con cero llegadas reservadas.
        reserved: dict[str, int] = {
            zone_name: 0
            for zone_name in self._graph.get_zone_names()
        }

        # Los tránsitos pendientes mantienen reservado su destino.
        for drone in drones:
            if (drone.transit is not None
               and drone.transit.turns_remaining > 1):
                dest = drone.transit.destination
                if dest in reserved:
                    reserved[dest] += 1

        # Un nuevo tránsito reserva su zona de destino para el siguiente turno.
        for move in moves:
            if move.kind == MoveKind.START_TRANSIT:
                dest = move.destination
                if dest in reserved:
                    reserved[dest] += 1

        return reserved
