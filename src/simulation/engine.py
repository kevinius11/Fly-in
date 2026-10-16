"""Orchestrate simulation turns and record immutable state snapshots."""

from src.simulation.models import (
    Drone,
    DroneSnapshot,
    MoveKind,
    PlannedMove,
    Transit,
)

from src.simulation.scheduler import Scheduler


class Engine:
    """Execute scheduled moves and maintain simulation state and history."""

    def __init__(
            self,
            scheduler: Scheduler,
            drones: list[Drone],
    ) -> None:
        """Create an engine with a scheduler and unique drone identifiers.

        Args:
            scheduler: Planner that selects capacity-safe moves per turn.
            drones: Initial drone states for the simulation.

        Raises:
            ValueError: If no drones are supplied or their IDs are duplicated.
        """
        if not drones:
            raise ValueError("Engine requires at least one drone.")
        drone_ids = [drone.drone_id for drone in drones]
        if len(drone_ids) != len(set(drone_ids)):
            raise ValueError("Drone IDs must be unique.")

        self._scheduler = scheduler
        self._drones = list(drones)
        self._turns_elapsed = 0
        self._history: list[list[PlannedMove]] = []
        self._state_history = [self.drone_states]

    def _apply_moves(
            self,
            moves: list[PlannedMove],
    ) -> None:
        """Validate and apply approved movements atomically.

        Args:
            moves: Moves approved by the scheduler for this turn.

        Raises:
            ValueError: If a move is duplicated, invalid, or inconsistent
                with the drone's route or transit state.
        """
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
                if self._scheduler.is_blocked_zone(move.destination):
                    raise ValueError(
                        "Cannot move into a blocked destination "
                        f"for D{move.drone_id}."
                    )
                destination_is_restricted = (
                    self._scheduler.is_restricted_zone(move.destination)
                )
                if (move.kind == MoveKind.START_TRANSIT
                        and not destination_is_restricted):
                    raise ValueError(
                        f"START_TRANSIT requires a restricted destination "
                        f"for D{move.drone_id}."
                    )
                if (move.kind == MoveKind.MOVE
                        and destination_is_restricted):
                    raise ValueError(
                        f"MOVE cannot enter a restricted destination for "
                        f"D{move.drone_id}."
                    )
            elif move.kind == MoveKind.COMPLETE_TRANSIT:
                if drone.transit is None:
                    raise ValueError(f"D{move.drone_id} has no transit.")
                if move.origin is not None:
                    raise ValueError(
                        "COMPLETE_TRANSIT origin must be None "
                        f"for D{move.drone_id}."
                    )
                next_route_zone = (
                    drone.path[drone.path_index + 1]
                    if drone.path_index + 1 < len(drone.path)
                    else None
                )
                if next_route_zone != drone.transit.destination:
                    raise ValueError(
                        "Active transit destination does not match "
                        f"the route for D{drone.drone_id}."
                    )
                if drone.transit.turns_remaining != 1:
                    raise ValueError(
                        f"Drone D{drone.drone_id} cannot complete "
                        f"transit with {drone.transit.turns_remaining} "
                        "turns remaining."
                    )
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
                drone.transit = None
                drone.path_index += 1

    def _advance_transits(self) -> None:
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
        if self.all_drones_delivered():
            return

        moves = self._scheduler.plan_turn(self._drones)
        self._apply_moves(moves)
        # _apply_moves() validates its move set atomically. The complete
        # turn is not transactional if advancing transit fails afterward.
        self._advance_transits()

        self._history.append(list(moves))
        self._turns_elapsed += 1
        self._state_history.append(self.drone_states)

    def all_drones_delivered(self) -> bool:
        """Check whether every drone has reached its destination.

        Returns:
            True when all drones are delivered; otherwise False.
        """
        return all(drone.is_delivered for drone in self._drones)

    @property
    def turns_elapsed(self) -> int:
        """Get the number of completed simulation turns.

        Returns:
            Number of turns recorded by the engine.
        """
        return self._turns_elapsed

    @property
    def history(self) -> list[list[PlannedMove]]:
        """Get a copy of the recorded movement history.

        Returns:
            Per-turn move lists detached from the engine's internal lists.
        """
        return [turn.copy() for turn in self._history]

    @property
    def drone_states(self) -> tuple[DroneSnapshot, ...]:
        """Get an immutable snapshot of every drone's current state.

        Returns:
            A tuple of read-only drone state snapshots.
        """
        snapshots: list[DroneSnapshot] = []
        for drone in self._drones:
            transit = drone.transit
            transit_connection = None
            transit_origin = None
            transit_destination = None
            transit_turns_remaining = None
            if transit is not None:
                transit_connection = (
                    transit.connection.zone_a,
                    transit.connection.zone_b,
                )
                transit_origin = drone.path[drone.path_index]
                transit_destination = transit.destination
                transit_turns_remaining = transit.turns_remaining

            snapshots.append(DroneSnapshot(
                drone_id=drone.drone_id,
                current_zone=drone.current_zone,
                next_zone=drone.next_zone,
                is_delivered=drone.is_delivered,
                transit_origin=transit_origin,
                transit_connection=transit_connection,
                transit_destination=transit_destination,
                transit_turns_remaining=transit_turns_remaining,
            ))
        return tuple(snapshots)

    @property
    def last_moves(self) -> tuple[PlannedMove, ...]:
        """Get the moves recorded in the most recent simulation turn.

        Returns:
            A tuple of moves, or an empty tuple before the first turn.
        """
        if not self._history:
            return ()
        return tuple(self._history[-1])

    @property
    def state_history(self) -> tuple[tuple[DroneSnapshot, ...], ...]:
        """Get immutable drone snapshots from turn zero through the current
        turn.

        Returns:
            A tuple containing one tuple of snapshots per recorded state.
        """
        return tuple(self._state_history)

    def run(self) -> list[list[PlannedMove]]:
        """Advance turns until all drones are delivered or deadlocked.

        Returns:
            A copy of the movement history.

        Raises:
            RuntimeError: If a turn does not change any drone state before
                all drones are delivered.
        """
        while not self.all_drones_delivered():
            state_before = [
                (drone.drone_id, drone.path_index, drone.transit)
                for drone in self._drones
            ]

            self.advance_turn()

            state_after = [
                (drone.drone_id, drone.path_index, drone.transit)
                for drone in self._drones
            ]
            if (state_before == state_after
                    and not self.all_drones_delivered()):
                raise RuntimeError(
                    "Simulation is deadlocked: no drone state changed."
                )

        return self.history

    def step(self) -> None:
        """Backward-compatible alias for :meth:`advance_turn`."""
        self.advance_turn()
