"""Exceptions raised while reading and validating map files."""


class ParsingError(Exception):
    """Carry a parsing failure's source line and explanation.

    Attributes:
        line_number: One-based source line where parsing failed.
        cause: Human-readable explanation of the invalid input.
    """

    def __init__(self, line_number: int, cause: str) -> None:
        """Create a parsing error for one source line.

        Args:
            line_number: One-based line number in the map file.
            cause: Explanation of the parsing or validation failure.
        """
        self.line_number = line_number
        self.cause = cause
        super().__init__(f"Parsing error at line {line_number}: {cause}")
