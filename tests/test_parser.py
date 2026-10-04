import pytest
from src.parser.exceptions import ParsingError
from src.parser.map_parser import MapParser


def test_valid_parsing(tmp_path):
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


def test_invalid_order_error(tmp_path):
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
    assert "Cannot define zones after connection declarations" in str(exc_info.value)


def test_self_connection_error(tmp_path):
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
