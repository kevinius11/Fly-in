from src.simulation.models import Drone, MoveKind, PlannedMove, Transit

from src.simulation.scheduler import Scheduler


class Engine:
    """Execute planned movements and maintain simulation state"""

    def __init__(
            self,
            scheduler: Scheduler,
            drones: list[Drone],
    ) -> None:
        self._scheduler = scheduler
        self._drones = drones
        self._turns_elapsed = 0
        self._history: list[list[PlannedMove]] = []

    def _apply_moves(
            self,
            moves: list[PlannedMove],
    ) -> None:
        """Apply approved movements to the corresponding drones."""
        seen_drone_ids: set[int] = set()
        validated_actions: list[tuple[Drone, PlannedMove]] = []

        for move in moves:
            if move.drone_id in seen_drone_ids:
                raise ValueError(f"Duplicate move for D{move.drone_id}.")
            seen_drone_ids.add(move.drone_id)

            # Localizamos el dron por ID
            drone = next(
                (d for d in self._drones if d.drone_id == move.drone_id),
                None
            )

            if drone is None:
                raise ValueError(f"D{move.drone_id} not found.")

            # Ejecutamos el tipo de movimiento (Fase de validación pura)
            movement_from_zone = (
                MoveKind.MOVE,
                MoveKind.START_TRANSIT,
            )
            if move.kind in movement_from_zone:
                if drone.transit is not None:
                    raise ValueError(f"D{move.drone_id} is in transit.")
                if move.origin is None or move.origin != drone.current_zone:
                    raise ValueError(f"Origin mismatch for D{move.drone_id}.")
                if move.destination != drone.next_zone:
                    raise ValueError(f"Dest mismatch for D{move.drone_id}.")
                connection_zones = {
                    move.connection.zone_a,
                    move.connection.zone_b,
                }
                if connection_zones != {move.origin, move.destination}:
                    raise ValueError(
                        f"Connection mismatch for D{move.drone_id}."
                    )
            elif move.kind == MoveKind.COMPLETE_TRANSIT:
                if drone.transit is None:
                    raise ValueError(f"D{move.drone_id} has no transit.")
                if move.destination != drone.transit.destination:
                    raise ValueError(f"Dest mismatch for D{move.drone_id}.")
                if move.connection != drone.transit.connection:
                    raise ValueError(f"Conn mismatch for D{move.drone_id}.")
            else:
                raise ValueError(f"Unknown MoveKind for D{move.drone_id}.")

            validated_actions.append((drone, move))

        for drone, move in validated_actions:
            if move.kind == MoveKind.MOVE:
                drone.path_index += 1

            elif move.kind == MoveKind.START_TRANSIT:
                drone.transit = Transit(
                    connection=move.connection,
                    destination=move.destination,
                    turns_remaining=2,
                )

            elif move.kind == MoveKind.COMPLETE_TRANSIT:
                transit = drone.transit
                if transit is None:
                    raise ValueError(f"D{move.drone_id} has no transit.")
                if transit.turns_remaining != 1:
                    raise ValueError(
                        f"Drone D{drone.drone_id} cannot complete "
                        f"transit with {transit.turns_remaining}"
                        " turns remaining"
                    )
                drone.transit = None
                drone.path_index += 1

    def advance_transit(self) -> None:
        """Reduce the turns_remaining counter for active transit"""
        for drone in self._drones:
            if (drone.transit is not None
                    and drone.transit.turns_remaining <= 1):
                raise ValueError(
                    f"Drone D{drone.drone_id} should have completed "
                    "its transit before advancing the counter."
                )

        for drone in self._drones:
            if drone.transit is not None:
                transit = drone.transit
                drone.transit = Transit(
                    connection=transit.connection,
                    destination=transit.destination,
                    turns_remaining=transit.turns_remaining - 1,
                )

    def advance_turn(self) -> None:
        """Plan and execute one complete simulation turn."""
        moves = self._scheduler.plan_turn(self._drones)
        self._apply_moves(moves)
        self.advance_transit()

        self._history.append(list(moves))
        self._turns_elapsed += 1

    def all_drones_delivered(self) -> bool:
        """Return whether all drones have reached their destination."""
        return all(drone.is_delivered for drone in self._drones)

    @property
    def turns_elapsed(self) -> int:
        """Return the number of elapsed simulation turns."""
        return self._turns_elapsed

    @property
    def history(self) -> list[list[PlannedMove]]:
        """Return the recorded movements for each turn."""
        return self._history

    def step(self) -> None:
        """Backward-compatible alias for :meth:`advance_turn`."""
        self.advance_turn()
