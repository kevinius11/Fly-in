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
        self._drones = Drone
        self._turns_elapsed = 0
        self._history: list[list[PlannedMove]] = []

        def _apply_moves(
                self,
                moves: list[PlannedMove],
        ) -> None:
            """"""
            raise NotImplementedError
