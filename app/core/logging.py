import logging

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure a small, predictable logging setup for the service."""
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
