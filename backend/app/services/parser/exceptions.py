class ParserError(Exception):
    """Base parser error."""


class UnsupportedFileTypeError(ParserError):
    """File không phải CSV hoặc Excel."""


class BlockedImportError(ParserError):
    """
    File thiếu columns quan trọng đến mức không thể parse.
    can_continue_mode = 'blocked'
    """
    def __init__(self, missing_columns: list[str]) -> None:
        self.missing_columns = missing_columns
        super().__init__(f"Missing required columns: {missing_columns}")


class EncodingDetectionError(ParserError):
    """Không detect được encoding của file."""
