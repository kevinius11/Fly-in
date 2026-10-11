from dataclasses import dataclass

from src.domain.models import Connection


@dataclass(frozen=True)
class Transit:
    """
    Represent a drone travelling through a connection.

    A transit stores the connection occupied by a drone, its destination
    endpoint, and the number of turns remaining before arrival.

    Attributes:
        connection: Connection currently occupied by the drone.
        destination: Name of the destination zone.
        turns_remaining: Number of turns remaining before arrival.
    """
    connection: Connection
    destination: str
    turns_remaining: int

    def __post_init__(self) -> None:
        """
        Validate the transit's duration and destination.

        Raises:
            ValueError: If the remaining duration is not positive or the
                destination is not one of the connection's endpoints.
        """
        if self.turns_remaining <= 0:
            raise ValueError(
                "Turns remaining in connection to a restricted zone,"
                f" cannot be less or equal to 0, got {self.turns_remaining}"
            )

        if (self.destination != self.connection.zone_a
                and self.destination != self.connection.zone_b):
            raise ValueError(
                "Destination does not match the destination from"
                " the connection object."
            )


@dataclass
class Drone:
    """
    Represent a drone and its current simulation state.

    Attributes:
        drone_id: Unique positive identifier of the drone.
        path: Ordered sequence of zones defining the planned route.
        path_index: Index of the last zone reached by the drone.
        transit: Active transit, or None if the drone is in a zone.
    """

    drone_id: int
    path: tuple[str, ...]
    path_index: int = 0
    transit: Transit | None = None

    def __post_init__(self) -> None:
        """
        Validate the drone's initial state.
        """
        if self.drone_id <= 0:
            raise ValueError(
                f"Drone ID must be positive, got {self.drone_id}"
            )

        if not self.path:
            raise ValueError(
                "Path cannot be empty."
            )

        if not (0 <= self.path_index < len(self.path)):
            raise ValueError(
                f"Path index is out of path bounds, got {self.path_index}"
            )

        if self.transit is not None:
            if not (self.path_index + 1 < len(self.path)):
                raise ValueError(
                    "There is no possible next step in the route."
                )

            expected_destination = self.path[self.path_index + 1]
            if not (self.transit.destination == expected_destination):
                raise ValueError(
                    f"Transit destination '{self.transit.destination}' does "
                    f"not match next planned zone '{expected_destination}'."
                )

            current_zone = self.path[self.path_index]
            conn_zones = {
                self.transit.connection.zone_a,
                self.transit.connection.zone_b
            }
            if conn_zones != {current_zone, expected_destination}:
                raise ValueError(
                    f"Connection {conn_zones} does not connect current zone "
                    f"'{current_zone}'to destination '{expected_destination}'."
                )

    @property
    def current_zone(self) -> str | None:
        """
        """
        if self.transit is not None:
            return None
        return self.path[self.path_index]
