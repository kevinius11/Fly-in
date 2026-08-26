import re
from typing import Dict, Tuple

from src.domain.models import Connection, MapData, Zone, ZoneType
from src.parser.exceptions import ParsingError


class MapParser:
    """Strict line-by-line state-machine parser for Fly-in map files."""

    def __init__(self) -> None:
        self._nb_drones: int | None = None
        self._zones: dict[str, Zone] = {}
        self._connections: list[Connection] = []
        self._seen_connection_pairs: set[tuple[str, str]] = set()
        self._start_hub: Zone | None = None
        self._end_hub: Zone | None = None

    def parse_file(self, file_path: str) -> MapData:
        """Read file and return validated MapData or raise ParsingError."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as err:
            raise ParsingError(0, f"Could not read map file: {err}") from err

        for idx, raw_line in enumerate(lines, start=1):
            line = self._strip_comment(raw_line).strip()
            if not line:
                continue
            self._parse_line(line, idx)

        self._validate_final_state()

        assert self._nb_drones is not None
        assert self._start_hub is not None
        assert self._end_hub is not None

        return MapData(
            nb_drones=self._nb_drones,
            zones=self._zones,
            connections=self._connections,
            start_hub=self._start_hub,
            end_hub=self._end_hub,
        )

    