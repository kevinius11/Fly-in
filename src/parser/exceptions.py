class ParsingError(Exception):
    """Exception raised for errors during map parsing."""

    def __init__(self, line_number: int, cause: str) -> None:
        self.line_number = line_number
        self.cause = cause
        super().__init__(f"Parsing error at line {line_number}: {cause}")
