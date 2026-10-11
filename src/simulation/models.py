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
