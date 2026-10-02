from enum import Enum, auto

from src.domain.models import Connection, MapData, Zone, ZoneType
from src.parser.exceptions import ParsingError


class ParserState(Enum):
    """Represent the current structural section of the map parser."""
    HEADER = auto()
    ZONES = auto()
    CONNECTIONS = auto()


class MapParser:
    """Strict line-by-line state-machine parser for Fly-in map files."""

    def __init__(self) -> None:
        """
        Initialize a MapParser with an empty parsing state.

        The parser starts in HEADER state and contains no parsed
        drones, zones, connections, start hub, or end hub.

        Returns:
            None.
        """
        self._reset()

    def _reset(self) -> None:
        """
        Reset all parser state to its initial values.

        This method makes the parser reusable across multiple input files
        without retaining data from previous parser operations.

        Returns:
            None.
        """
        self._state = ParserState.HEADER
        self._nb_drones: int | None = None  # None represents not parsed yet...
        self._zones: dict[str, Zone] = {}  # O(1) lookup "A": Zone(...)
        self._connections: list[Connection] = []  # ("A", "B")A-BB-AO(1)HASHSET
        self._seen_connection_pairs: set[tuple[str, str]] = set()
        self._start_hub: Zone | None = None
        self._end_hub: Zone | None = None

    def parse_file(self, file_path: str) -> MapData:
        """
        Parse a Fly-In map file and return its validated domain model.

        The file is processed line by line. Comments and blank lines are
        ignored, while each meaningful line is validated according to the
        current parser state.

        Args:
            file_path: Path to the map file to parse.

        Returns:
            A validated MapData instance containing drones, zones,
            connections, start hub, and end hub.

        Raises:
            ParsingError: If the file cannot be read or contains invalid
                syntax or semantic data.

        """
        self._reset()
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

        if (
            self._nb_drones is None
            or self._start_hub is None
            or self._end_hub is None
        ):
            raise ParsingError(
                0, "Incomplete map definition."
            )

        return MapData(
            nb_drones=self._nb_drones,
            zones=self._zones,
            connections=self._connections,
            start_hub=self._start_hub,
            end_hub=self._end_hub,
        )

    def _strip_comment(self, line: str) -> str:
        """
        Remove comment portion from a raw input line.

        A comment begins at the first '#' character and continues until
        the end of the line.

        Args:
            line: Raw line read from the map file.

        Returns:
            The line content appearing before the first '#' character.
        """
        return line.split("#", 1)[0]  # O(L) complexity

    def _extract_metadata_str(
            self,
            line: str,
            line_num: int
    ) -> tuple[str, str | None]:
        """"""
        has_open = "[" in line
        has_close = "]" in line

        if has_open != has_close:
            raise ParsingError(
                line_num, "Mismatched metadata brackets '[' or ']'."
            )

        if not has_open:
            return line.strip(), None

        if line.count("[") > 1 or line.count("]") > 1:
            raise ParsingError(
                line_num, "Multiple metadata blocks in one line."
                )

        open_idx = line.index("[")
        close_idx = line.index("]")

        if close_idx < open_idx:
            raise ParsingError(
                line_num, "Bracket '[' appears before bracket ']'."
            )

        if close_idx != len(line) - 1:
            raise ParsingError(
                line_num, "Trailing characters after metadata brackets."
            )

        prefix = line[:open_idx].strip()
        metadata_content = line[open_idx + 1: close_idx].strip()

        if not metadata_content:
            raise ParsingError(
                line_num, "Empty metadata brackets '[]' are not allowed."
            )

        return prefix, metadata_content

    def _parse_metadata_kv(
            self,
            raw_metadata: str | None,
            line_num: int
    ) -> dict[str, str]:
        """"""
        if not raw_metadata:
            return {}

        result: dict[str, str] = {}
        tokens = raw_metadata.split()
        for token in tokens:
            if "=" not in token:
                raise ParsingError(
                    line_num,
                    f"Invalid metadata token '{token}'. Must be key=value."
                )
            key, val = token.split("=", 1)
            key, val = key.strip(), val.strip()
            if not key or not val:
                raise ParsingError(
                    line_num,
                    f"Empty key or value in metadata token '{token}'."
                )
            if key in result:
                raise ParsingError(
                    line_num, f"Duplicate metadata key '{key}'."
                )
            result[key] = val
        return result

    def _parse_line(self, line: str, line_num: int) -> None:
        """"""
        prefix, raw_metadata = self._extract_metadata_str(line, line_num)
        kv = self._parse_metadata_kv(raw_metadata, line_num)

        if ":" not in prefix:
            raise ParsingError(
                line_num,
                f"Malformed line syntax: '{prefix}'. Missing ':' keyword separator"
            )

        keyword, body = prefix.split(":", 1)
        keyword, body = keyword.strip(), body.strip()

        if keyword == "nb_drones":
            if self._state != ParserState.HEADER:
                raise ParsingError(
                    line_num,
                    "'nb_drones' must be defined at the begining of the file."
                )
            self._parse_nb_drones(body, kv, line_num)
            self._state = ParserState.ZONES

        elif keyword in ("start_hub", "end_hub", "hub"):
            if self._state ==  ParserState.HEADER:
                raise ParsingError(
                    line_num,
                    "'nb_drones' header must be defined before any zones."
                )
            if self._state == ParserState.CONNECTIONS:
                raise ParsingError(
                    line_num,
                    "Cannot define zones after connection declarations."
                )
            self._parse_zone(keyword, body, kv, line_num)

        elif keyword == "connection":
            if self._state == ParserState.HEADER:
                raise ParsingError(
                    line_num,
                    "Map contains no zones before connections."
                )
            self._state = ParserState.CONNECTIONS
            self._parse_connection(body, kv, line_num)

        else:
            raise ParsingError(
                line_num,
                f"Unknown statement keyword '{keyword}'."
            )
