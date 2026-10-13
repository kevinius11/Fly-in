import pytest

from src.domain.models import Connection
from src.simulation.models import Transit, Drone, MoveKind, PlannedMove


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


def test_drone_accepts_valid_initial_state() -> None:
    """Accept a drone with a valid route and initial state."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
    )

    assert drone.drone_id == 1
    assert drone.path == ("start", "corridor", "goal")
    assert drone.path_index == 0
    assert drone.transit is None


def test_drone_accepts_valid_transit(
    connection: Connection,
) -> None:
    """Accept a transit matching the next zone in the route."""
    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=1,
    )

    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "restricted", "goal"),
        path_index=1,
        transit=transit,
    )

    assert drone.path_index == 1
    assert drone.transit is transit


@pytest.mark.parametrize("drone_id", [0, -1])
def test_drone_rejects_non_positive_id(drone_id: int) -> None:
    """Reject zero or negative drone identifiers."""
    with pytest.raises(ValueError, match="Drone ID must be positive"):
        Drone(
            drone_id=drone_id,
            path=("start", "goal"),
        )


def test_drone_rejects_empty_path() -> None:
    """Reject a drone without a route."""
    with pytest.raises(ValueError, match="Path cannot be empty"):
        Drone(
            drone_id=1,
            path=(),
        )


@pytest.mark.parametrize("path_index", [-1, 2])
def test_drone_rejects_invalid_path_index(
    path_index: int,
) -> None:
    """Reject indices outside the route boundaries."""
    with pytest.raises(ValueError, match="Path index is out of path bounds"):
        Drone(
            drone_id=1,
            path=("start", "goal"),
            path_index=path_index,
        )


def test_drone_rejects_transit_without_next_step() -> None:
    """Reject an active transit when the route has ended."""
    connection = Connection(
        zone_a="start",
        zone_b="goal",
        max_link_capacity=1,
    )

    transit = Transit(
        connection=connection,
        destination="goal",
        turns_remaining=1,
    )

    with pytest.raises(
        ValueError,
        match="There is no possible next step",
    ):
        Drone(
            drone_id=1,
            path=("start", "goal"),
            path_index=1,
            transit=transit,
        )


def test_drone_rejects_unexpected_transit_destination(
    connection: Connection,
) -> None:
    """Reject a transit whose destination differs
    from the planned next zone."""
    transit = Transit(
        connection=connection,
        destination="corridor",
        turns_remaining=1,
    )

    with pytest.raises(
        ValueError,
        match="does not match next planned zone",
    ):
        Drone(
            drone_id=1,
            path=("start", "corridor", "restricted", "goal"),
            path_index=1,
            transit=transit,
        )


def test_drone_rejects_incompatible_transit_connection() -> None:
    """Reject a connection that does not join the current and next zones."""
    connection = Connection(
        zone_a="other",
        zone_b="restricted",
        max_link_capacity=1,
    )

    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=1,
    )

    with pytest.raises(
        ValueError,
        match="does not connect current zone",
    ):
        Drone(
            drone_id=1,
            path=("start", "corridor", "restricted", "goal"),
            path_index=1,
            transit=transit,
        )


def test_current_zone_returns_first_zone() -> None:
    """Return the first zone when the drone starts its route."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
    )

    assert drone.current_zone == "start"


def test_current_zone_returns_zone_at_current_index() -> None:
    """Return the zone corresponding to the current path index."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
        path_index=1,
    )

    assert drone.current_zone == "corridor"


def test_current_zone_returns_none_during_transit(
    connection: Connection,
) -> None:
    """Return None while the drone is travelling through a connection."""
    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=1,
    )

    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "restricted", "goal"),
        path_index=1,
        transit=transit,
    )

    assert drone.current_zone is None


def test_current_zone_returns_destination_after_arrival() -> None:
    """Return the destination zone after the drone arrives."""
    drone = Drone(
        drone_id=1,
        path=("start", "goal"),
        path_index=1,
    )

    assert drone.current_zone == "goal"


def test_next_zone_returns_first_destination() -> None:
    """Return the next zone when the drone is at the start."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
    )

    assert drone.next_zone == "corridor"


def test_next_zone_returns_zone_after_current_index() -> None:
    """Return the next zone from an intermediate position."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "restricted", "goal"),
        path_index=1,
    )

    assert drone.next_zone == "restricted"


def test_next_zone_returns_none_during_transit(
    connection: Connection,
) -> None:
    """Return None while the drone is already in transit."""
    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=1,
    )

    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "restricted", "goal"),
        path_index=1,
        transit=transit,
    )

    assert drone.next_zone is None


def test_next_zone_returns_none_at_end_of_route() -> None:
    """Return None when the drone has reached the last zone."""
    drone = Drone(
        drone_id=1,
        path=("start", "goal"),
        path_index=1,
    )

    assert drone.next_zone is None


def test_next_zone_returns_none_for_single_zone_route() -> None:
    """Return None when the route contains only one zone."""
    drone = Drone(
        drone_id=1,
        path=("goal",),
    )

    assert drone.next_zone is None


def test_is_delivered_returns_false_at_start() -> None:
    """A drone at the start has not completed its route."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
    )

    assert drone.is_delivered is False


def test_is_delivered_returns_false_at_intermediate_zone() -> None:
    """A drone at an intermediate zone is not delivered."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
        path_index=1,
    )

    assert drone.is_delivered is False


def test_is_delivered_returns_false_during_transit(
    connection: Connection,
) -> None:
    """A drone in transit has not reached its destination zone."""
    transit = Transit(
        connection=connection,
        destination="restricted",
        turns_remaining=1,
    )

    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "restricted", "goal"),
        path_index=1,
        transit=transit,
    )

    assert drone.is_delivered is False


def test_is_delivered_returns_true_at_destination() -> None:
    """A drone at the final zone with no active transit is delivered."""
    drone = Drone(
        drone_id=1,
        path=("start", "corridor", "goal"),
        path_index=2,
    )

    assert drone.is_delivered is True


def test_is_delivered_returns_true_for_single_zone_route() -> None:
    """A drone with a single-zone route is already at the end."""
    drone = Drone(
        drone_id=1,
        path=("goal",),
    )

    assert drone.is_delivered is True


def test_planned_move_represents_normal_movement() -> None:
    """Represent an ordinary movement between two zones."""
    connection = Connection(
        zone_a="A",
        zone_b="B",
        max_link_capacity=1,
    )

    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.MOVE,
        origin="A",
        destination="B",
        connection=connection,
    )

    assert move.drone_id == 1
    assert move.kind is MoveKind.MOVE
    assert move.origin == "A"
    assert move.destination == "B"
    assert move.connection == connection


def test_planned_move_represents_transit_start(
    connection: Connection,
) -> None:
    """Represent the beginning of a restricted-zone transit."""
    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.START_TRANSIT,
        origin="corridor",
        destination="restricted",
        connection=connection,
    )

    assert move.drone_id == 1
    assert move.kind is MoveKind.START_TRANSIT
    assert move.origin == "corridor"
    assert move.destination == "restricted"
    assert move.connection == connection


def test_planned_move_represents_transit_completion(
    connection: Connection,
) -> None:
    """Represent the completion of an active transit."""
    move = PlannedMove(
        drone_id=1,
        kind=MoveKind.COMPLETE_TRANSIT,
        origin=None,
        destination="restricted",
        connection=connection,
    )

    assert move.drone_id == 1
    assert move.kind is MoveKind.COMPLETE_TRANSIT
    assert move.origin is None
    assert move.destination == "restricted"
    assert move.connection == connection
