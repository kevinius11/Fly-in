from pathlib import Path

import pytest

from src.domain.models import ZoneType
from src.parser.exceptions import ParsingError
from src.parser.map_parser import MapParser


def test_valid_parsing(tmp_path: Path) -> None:
    """Parse a valid map and verify its main domain values."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: mid 5 5 [zone=restricted max_drones=2]
connection: start-mid
connection: mid-goal [max_link_capacity=3]
"""
    f = tmp_path / "valid.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.nb_drones == 2
    assert len(data.zones) == 3
    assert len(data.connections) == 2
    assert data.start_hub.name == "start"
    assert data.end_hub.name == "goal"
    assert data.zones["mid"].zone_type == ZoneType.RESTRICTED
    assert data.zones["mid"].max_drones == 2
    assert data.connections[1].max_link_capacity == 3


def test_any_number_of_drones(tmp_path: Path) -> None:
    """Accept a map containing an arbitrarily large positive drone count."""
    map_content = """nb_drones: 100000
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "many_drones.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.nb_drones == 100000


def test_missing_nb_drones_error(tmp_path: Path) -> None:
    """Reject a zone declaration appearing before nb_drones."""
    map_content = """start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "missing_header.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "'nb_drones' header must be defined before any zones" in str(
        exc_info.value
    )


def test_zero_drones_error(tmp_path: Path) -> None:
    """Reject a zero drone count."""
    map_content = """nb_drones: 0
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "zero_drones.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "'nb_drones' must be a positive integer" in str(
        exc_info.value
    )


def test_negative_drones_error(tmp_path: Path) -> None:
    """Reject a negative drone count."""
    map_content = """nb_drones: -5
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "negative_drones.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "'nb_drones' must be a positive integer" in str(
        exc_info.value
    )


def test_duplicate_start_hub_error(tmp_path: Path) -> None:
    """Reject maps containing more than one start hub."""
    map_content = """nb_drones: 2
start_hub: start 0 0
start_hub: another_start 5 5
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "duplicate_start.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Multiple 'start_hub' zones defined" in str(exc_info.value)


def test_duplicate_end_hub_error(tmp_path: Path) -> None:
    """Reject maps containing more than one end hub."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
end_hub: another_goal 20 20
connection: start-goal
"""
    f = tmp_path / "duplicate_end.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Multiple 'end_hub' zones defined" in str(exc_info.value)


def test_missing_start_hub_error(tmp_path: Path) -> None:
    """Reject maps that do not define a start hub."""
    map_content = """nb_drones: 2
hub: middle 5 5
end_hub: goal 10 10
connection: middle-goal
"""
    f = tmp_path / "missing_start.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Missing mandatory 'start_hub' zone" in str(exc_info.value)


def test_missing_end_hub_error(tmp_path: Path) -> None:
    """Reject maps that do not define an end hub."""
    map_content = """nb_drones: 2
start_hub: start 0 0
hub: middle 5 5
connection: start-middle
"""
    f = tmp_path / "missing_end.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Missing mandatory 'end_hub' zone" in str(exc_info.value)


def test_duplicate_zone_name_error(tmp_path: Path) -> None:
    """Reject duplicate zone names."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: start 5 5
connection: start-goal
"""
    f = tmp_path / "duplicate_zone.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Duplicate zone name 'start'" in str(exc_info.value)


def test_invalid_coordinates_error(tmp_path: Path) -> None:
    """Reject zones whose coordinates are not integers."""
    map_content = """nb_drones: 2
start_hub: start zero 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "invalid_coordinates.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Coordinates must be integers" in str(exc_info.value)


def test_zone_name_with_dash_error(tmp_path: Path) -> None:
    """Reject zone names containing dashes."""
    map_content = """nb_drones: 2
start_hub: start-zone 0 0
end_hub: goal 10 10
connection: start-zone-goal
"""
    f = tmp_path / "dash_zone.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "contains forbidden characters" in str(exc_info.value)


def test_zone_name_with_space_error(tmp_path: Path) -> None:
    """Reject zone declarations whose names contain spaces."""
    map_content = """nb_drones: 2
start_hub: start zone 0 0
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "space_zone.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Zone definition requires" in str(exc_info.value)


def test_undefined_zone_in_connection_error(tmp_path: Path) -> None:
    """Reject connections referencing undefined zones."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-middle
"""
    f = tmp_path / "undefined_zone.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Connection references undefined zone 'middle'" in str(
        exc_info.value
    )


def test_connection_to_later_zone_error(tmp_path: Path) -> None:
    """Reject connections referencing zones defined later in the file."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-middle
hub: middle 5 5
"""
    f = tmp_path / "later_zone.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Connection references undefined zone 'middle'" in str(
        exc_info.value
    )


def test_duplicate_connection_same_direction_error(
    tmp_path: Path,
) -> None:
    """Reject the same connection when declared twice."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
connection: start-goal
"""
    f = tmp_path / "duplicate_connection.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Duplicate connection" in str(exc_info.value)


def test_duplicate_connection_reverse_direction_error(
    tmp_path: Path,
) -> None:
    """Treat A-B and B-A as the same connection."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
connection: goal-start
"""
    f = tmp_path / "reverse_connection.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Duplicate connection" in str(exc_info.value)


def test_self_connection_error(tmp_path: Path) -> None:
    """Reject connections that link a zone to itself."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-start
"""
    f = tmp_path / "self_conn.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Self-connection" in str(exc_info.value)


def test_valid_zone_types(tmp_path: Path) -> None:
    """Accept every zone type defined by the project."""
    map_content = """nb_drones: 4
start_hub: start 0 0
end_hub: goal 10 10
hub: normal_zone 1 1 [zone=normal]
hub: blocked_zone 2 2 [zone=blocked]
hub: restricted_zone 3 3 [zone=restricted]
hub: priority_zone 4 4 [zone=priority]
connection: start-normal_zone
connection: normal_zone-blocked_zone
connection: blocked_zone-restricted_zone
connection: restricted_zone-priority_zone
connection: priority_zone-goal
"""
    f = tmp_path / "zone_types.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.zones["normal_zone"].zone_type == ZoneType.NORMAL
    assert data.zones["blocked_zone"].zone_type == ZoneType.BLOCKED
    assert data.zones["restricted_zone"].zone_type == ZoneType.RESTRICTED
    assert data.zones["priority_zone"].zone_type == ZoneType.PRIORITY


def test_invalid_zone_type_error(tmp_path: Path) -> None:
    """Reject zone types outside the supported ZoneType values."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [zone=banana]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "invalid_zone_type.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Invalid zone type 'banana'" in str(exc_info.value)


def test_valid_zone_capacity(tmp_path: Path) -> None:
    """Accept a positive max_drones value on a normal zone."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [max_drones=10]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "valid_capacity.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.zones["middle"].max_drones == 10


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "abc"],
)
def test_invalid_zone_capacity_error(
    tmp_path: Path,
    value: str,
) -> None:
    """Reject zero, negative, and non-numeric zone capacities."""
    map_content = f"""nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [max_drones={value}]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "invalid_capacity.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "'max_drones' must be a positive integer" in str(
        exc_info.value
    )


def test_start_end_ignore_max_drones(tmp_path: Path) -> None:
    """Ignore max_drones values on start and end hubs."""
    map_content = """nb_drones: 5
start_hub: start 0 0 [max_drones=999]
end_hub: goal 10 10 [max_drones=500]
hub: middle 5 5 [max_drones=3]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "ignored_capacity.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.zones["start"].max_drones == 1
    assert data.zones["goal"].max_drones == 1
    assert data.zones["middle"].max_drones == 3


def test_valid_connection_capacity(tmp_path: Path) -> None:
    """Accept a positive max_link_capacity value."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal [max_link_capacity=5]
"""
    f = tmp_path / "link_capacity.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.connections[0].max_link_capacity == 5


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "abc"],
)
def test_invalid_connection_capacity_error(
    tmp_path: Path,
    value: str,
) -> None:
    """Reject invalid connection capacity values."""
    map_content = f"""nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal [max_link_capacity={value}]
"""
    f = tmp_path / "invalid_link_capacity.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "max_link_capacity" in str(exc_info.value)


def test_valid_metadata(tmp_path: Path) -> None:
    """Parse valid metadata for zones and connections."""
    map_content = """nb_drones: 2
start_hub: start 0 0 [color=green]
end_hub: goal 10 10 [color=red]
hub: middle 5 5 [zone=priority color=blue max_drones=4]
connection: start-middle [max_link_capacity=3]
connection: middle-goal [max_link_capacity=2]
"""
    f = tmp_path / "metadata.map"
    f.write_text(map_content)

    parser = MapParser()
    data = parser.parse_file(str(f))

    assert data.zones["start"].color == "green"
    assert data.zones["goal"].color == "red"
    assert data.zones["middle"].zone_type == ZoneType.PRIORITY
    assert data.zones["middle"].color == "blue"
    assert data.zones["middle"].max_drones == 4
    assert data.connections[0].max_link_capacity == 3
    assert data.connections[1].max_link_capacity == 2


@pytest.mark.parametrize(
    "metadata",
    [
        "[",
        "]",
        "[]",
        "[zone=normal",
        "zone=normal]",
        "[zone=normal] extra",
        "[zone=normal] [color=red]",
    ],
)
def test_invalid_metadata_syntax_error(
    tmp_path: Path,
    metadata: str,
) -> None:
    """Reject malformed metadata blocks."""
    map_content = f"""nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 {metadata}
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "invalid_metadata.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError):
        parser.parse_file(str(f))


def test_metadata_token_without_equals_error(
    tmp_path: Path,
) -> None:
    """Reject metadata tokens that do not use key=value syntax."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [zone=normal color]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "invalid_metadata_token.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Must be key=value" in str(exc_info.value)


def test_unknown_zone_metadata_error(tmp_path: Path) -> None:
    """Reject metadata keys unsupported by zone declarations."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [speed=fast]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "unknown_metadata.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Unknown zone metadata key 'speed'" in str(exc_info.value)


def test_unknown_connection_metadata_error(
    tmp_path: Path,
) -> None:
    """Reject metadata keys unsupported by connections."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal [capacity=5]
"""
    f = tmp_path / "unknown_connection_metadata.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Unknown connection metadata key 'capacity'" in str(
        exc_info.value
    )


def test_duplicate_metadata_key_error(tmp_path: Path) -> None:
    """Reject duplicate metadata keys."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
hub: middle 5 5 [zone=normal zone=priority]
connection: start-middle
connection: middle-goal
"""
    f = tmp_path / "duplicate_metadata.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Duplicate metadata key 'zone'" in str(exc_info.value)


def test_invalid_order_error(tmp_path: Path) -> None:
    """Reject zone declarations after connection declarations."""
    map_content = """nb_drones: 2
start_hub: start 0 0
end_hub: goal 10 10
connection: start-goal
hub: late_hub 5 5
"""
    f = tmp_path / "invalid_order.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    assert "Cannot define zones after connection declarations" in str(
        exc_info.value
    )


def test_error_contains_line_number_and_cause(
    tmp_path: Path,
) -> None:
    """Include the source line number and cause in parsing errors."""
    map_content = """nb_drones: 2
start_hub: start 0 0
hub: middle invalid 5
end_hub: goal 10 10
connection: start-goal
"""
    f = tmp_path / "line_error.map"
    f.write_text(map_content)

    parser = MapParser()

    with pytest.raises(ParsingError) as exc_info:
        parser.parse_file(str(f))

    error_message = str(exc_info.value)

    assert "line 3" in error_message
    assert "Coordinates must be integers" in error_message
