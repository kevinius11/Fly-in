import pytest

from src.domain.models import Connection
from src.simulation.models import Transit


@pytest.fixture
def connection() -> Connection:
    """Create a connection between two zones for testing."""
    return Connection(
        zone_a="corridor",
        zone_b="restricted",
        max_link_capacity=1,
    )


def test_transit_accepts_zone_a_as_destination(
    connection: Connection,
) -> None:
    """Accept the first endpoint as the destination."""
    transit = Transit(
        connection=connection,
        destination="corridor",
        turns_remaining=1,
    )

    assert transit.connection == connection
    assert transit.destination == "corridor"
    assert transit.turns_remaining == 1


def test_transit_accepts_zone_b_as_destination(
    connection: Connection,
) -> None:
    """Accept the second endpoint as the destination."""
    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=2,
    )

    assert transit.connection == connection
    assert transit.destination == "restricted"
    assert transit.turns_remaining == 2


def test_transit_rejects_invalid_destination(
    connection: Connection,
) -> None:
    """Reject a destination that is not a connection endpoint."""
    with pytest.raises(ValueError, match="Destination"):
        Transit(
            connection=connection,
            destination="goal",
            turns_remaining=1,
        )


@pytest.mark.parametrize("turns_remaining", [0, -1])
def test_transit_rejects_non_positive_duration(
    connection: Connection,
    turns_remaining: int,
) -> None:
    """Reject a transit with zero or negative remaining turns."""
    with pytest.raises(ValueError, match="Turns remaining"):
        Transit(
            connection=connection,
            destination="restricted",
            turns_remaining=turns_remaining,
        )
