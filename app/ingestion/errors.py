class IngestionError(RuntimeError):
    """Base error raised for recoverable ingestion failures."""


class FetchError(IngestionError):
    """An HTTP request could not be completed successfully."""


class MalformedContentError(IngestionError):
    """A source returned content that cannot be parsed as expected."""
