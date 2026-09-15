"""config package - application settings."""

from .logger import get_logger
from .settings import get_settings, settings

__all__ = ["get_logger", "get_settings", "settings"]
    