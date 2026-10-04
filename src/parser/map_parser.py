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
        """
        Extract the statement prefix and optional metadata block.

        Metadata must appear inside a single pair of square brackets
        at the end of the line. The method validates bracket structure
        before returning the separated components.

        Args:
            line: Normalized input line to inspect.
            line_num: Original line number used for error reporting.

        Returns:
            A tuple containing the statement prefix and metadata content.
            The metadata value is None when no metadata block is present.

        Raises:
            ParsingError: If the metadata brackets are malformed, repeated,
                misplaced, or empty.
        """
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
        """
        Parse metadata tokens into a key-value dictionary.

        Each metadata token must follow the 'key=value' format.
        Keys must be unique and both keys and values must be non-empty.

        Args:
            raw_metadata: Metadata content extracted from a square brackets,
                or None when the line has no metadata.
            line_num: Original line number used for error reporting.

        Returns:
            A dictionary mapping metadata keys to their string valuese.

        Raises:
            ParsingError: If a metadata token is malformed, empty, or
                duplicated.
        """
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
        """
        Parse one normalized line according to its statement keyword.

        The method extracts metadata, identifies the statement keyword,
        validates the current parser state, and delegates detailed parsing
        to the corresponding specialized method.

        Args:
            line: Normalized non-empty input line.
            line_num: Original line number used for error reporting.

        Returns:
            None

        Raises:
            ParsingError: If the line syntax is invalid, the keyword is
                unknown, or the statement is not valid in the current
                parser state.
        """
        prefix, raw_metadata = self._extract_metadata_str(line, line_num)
        kv = self._parse_metadata_kv(raw_metadata, line_num)

        if ":" not in prefix:
            raise ParsingError(
                line_num,
                f"Malformed line syntax: '{prefix}'. "
                "Missing ':' keyword separator"
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
            if self._state == ParserState.HEADER:
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

    def _parse_nb_drones(
            self,
            body: str,
            kv: dict[str, str],
            line_num: int
    ) -> None:
        """
        Parse and validate the number of drones declaration.

        The declaration must contain a single positive integer and
        cannot contain metadata. The parsed value is stored in the
        parser state.

        Args:
            body: Text appearing after the 'nb_drones:' keyword.
            kv: Metadata key-value pairs extracted from the current line.
            line_num: Original line number used for error reporting.

        Returns:
            None

        Raises:
            ParsingError: If the declaration is duplicated, contains
                metadata, has no value, or does not contain a positive
                integer.
        """
        if self._nb_drones is not None:
            raise ParsingError(
                line_num,
                "Duplicate 'nb_drones' definition."
            )

        if kv:
            raise ParsingError(
                line_num,
                "'nb_drones' statement cannot have metadata."
            )

        if not body:
            raise ParsingError(
                line_num,
                "Missing value for 'nb_drones'."
            )

        if not body.isdigit() or int(body) <= 0:
            raise ParsingError(
                line_num,
                f"'nb_drones' must be a positive integer, got {body}"
            )

        self._nb_drones = int(body)

    def _parse_zone(
            self,
            keyword: str,
            body: str,
            kv: dict[str, str],
            line_num: int
    ) -> None:
        """"""
        tokens = body.split()
        if len(tokens) != 3:
            raise ParsingError(
                line_num,
                f"Zone definition requires '<name> <x> <y>', got {body}"
            )

        name, x_str, y_str = tokens[0], tokens[1], tokens[2]

        if "-" in name or " " in name:
            raise ParsingError(
                line_num,
                f"Zone name '{name}' contains forbidden characters "
                "('-' or spaces)."
            )

        if name in self._zones:
            raise ParsingError(
                line_num,
                f"Duplicate zone name '{name}'."
            )

        try:
            x, y = int(x_str), int(y_str)
        except ValueError:
            raise ParsingError(
                line_num,
                "Coordinates must be integers, "
                f"got x='{x_str}' and y='{y_str}'."
            )

        for k in kv:
            if k not in ("zone", "color", "max_drones"):
                raise ParsingError(
                    line_num,
                    f"Unknown zone metadata key '{k}'."
                )

        zone_type = ZoneType.NORMAL
        if "zone" in kv:
            try:
                zone_type = ZoneType(kv["zone"])
            except ValueError:
                raise ParsingError(
                    line_num,
                    f"Invalid zone type '{kv['zone']}'."
                )

        max_drones = 1
        if "max_drones" in kv:
            if not kv["max_drones"].isdigit() or int(kv["max_drones"]) <= 0:
                raise ParsingError(
                    line_num,
                    "'max_drones' must be a positive integer, "
                    f"got '{kv['max_drones']}'."
                )

        color = kv.get("color")
        is_start = keyword == "start_hub"
        is_end = keyword == "end_hub"

        if is_start and self._start_hub is not None:
            raise ParsingError(
                line_num,
                "Multiple 'start_hub' zones defined. "
                "Exactly one is required."
            )

        if is_end and self._end_hub is not None:
            raise ParsingError(
                line_num,
                "Mutiple 'end_hub' zones defined. "
                "Exactly one is required."
            )

        zone = Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            max_drones=max_drones,
            color=color,
            is_start=is_start,
            is_end=is_end,
        )

        self._zones[name] = zone
        if is_start:
            self._start_hub = zone
        if is_end:
            self._end_hub = zone

    def _parse_connection(
            self,
            body: str,
            kv: dict[str, str],
            line_num: int
    ) -> None:
        """"""
        if "-" not in body:
            raise ParsingError(
                line_num,
                f"Invalid connection format '{body}'. "
                "Expected 'zone1-zone2'"
            )

        parts = body.split("-")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ParsingError(
                line_num,
                f"Invalid connection syntax '{body}'."
            )

        z1, z2 = parts[0].strip(), parts[1].strip()

        if z1 == z2:
            raise ParsingError(
                line_num,
                f"Self-connection on zone '{z1}' is forbidden."
            )

        if z1 not in self._zones:
            raise ParsingError(
                line_num,
                f"Connection references undefined zone '{z1}'."
            )

        if z2 not in self._zones:
            raise ParsingError(
                line_num,
                f"Connection references undefined zone '{z2}'."
            )

        pair = tuple(sorted((z1, z2)))
        if pair in self._seen_connection_pairs:
            raise ParsingError(
                line_num,
                f"Duplicate connection between '{z1}' and '{z2}'."
            )

        for k in kv:
            if k != "max_link_capacity":
                raise ParsingError(
                    line_num,
                    f"Unknown connection metadata key '{k}'."
                )

        max_cap = 1
        if "max_link_capacity" in kv:
            if (not kv["max_link_capacity"].isdigit()
               or int(kv["max_link_capacity"]) <= 0):
                raise ParsingError(
                    line_num,
                    "'max_link_capacity' must be positive integer. "
                    f"got '{kv['max_link_capacity']}'."
                )
            max_cap = int(kv["max_link_capacity"])

        self._seen_connection_pairs.add(pair)
        self._connections.append(Connection(
            zone_a=z1,
            zone_b=z2,
            max_link_capacity=max_cap
        ))

    def _validate_final_state(self) -> None:
        """"""
        if self._nb_drones is None:
            raise ParsingError(
                0,
                "Missing 'nb_drones' header."
            )

        if self._start_hub is None:
            raise ParsingError(
                0,
                "Missing mandatory 'start_hub' zone."
            )

        if self._end_hub is None:
            raise ParsingError(
                0,
                "Missing mandatory 'end_hub' zone."
            )
