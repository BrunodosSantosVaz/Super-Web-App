"""Logging system for WebApps Manager.

This module provides a structured logging system with file rotation
and different log levels for development and production.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .xdg import XDGDirectories


class Logger:
    """Centralized logging configuration.

    Provides both file and console logging with proper formatting
    and rotation.
    """

    _instance: Optional[logging.Logger] = None
    _debug_mode: bool = False

    @classmethod
    def get_logger(cls, name: str = "webapps-manager") -> logging.Logger:
        """Get or create logger instance (singleton pattern).

        Args:
            name: Logger name (default: webapps-manager)

        Returns:
            Configured logger instance
        """
        if cls._instance is None:
            cls._instance = cls._setup_logger(name)
        return cls._instance

    @classmethod
    def _setup_logger(cls, name: str) -> logging.Logger:
        """Setup logger with file and console handlers.

        Args:
            name: Logger name

        Returns:
            Configured logger
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        simple_formatter = logging.Formatter(
            fmt="%(levelname)-8s | %(message)s",
        )

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

        # File handler with rotation
        try:
            log_file = XDGDirectories.get_logs_dir() / "app.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to setup file logging: {e}")

        return logger

    @classmethod
    def set_debug_mode(cls, enabled: bool = True) -> None:
        """Enable or disable debug mode.

        Args:
            enabled: True to enable debug logging on console
        """
        cls._debug_mode = enabled
        if cls._instance:
            for handler in cls._instance.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(logging.DEBUG if enabled else logging.INFO)

    @classmethod
    def is_debug_mode(cls) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if debug mode is enabled
        """
        return cls._debug_mode


# Convenience functions
def get_logger(name: str = "webapps-manager") -> logging.Logger:
    """Get logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return Logger.get_logger(name)


def debug(message: str) -> None:
    """Log debug message.

    Args:
        message: Message to log
    """
    get_logger().debug(message)


def info(message: str) -> None:
    """Log info message.

    Args:
        message: Message to log
    """
    get_logger().info(message)


def warning(message: str) -> None:
    """Log warning message.

    Args:
        message: Message to log
    """
    get_logger().warning(message)


def error(message: str, exc_info: bool = False) -> None:
    """Log error message.

    Args:
        message: Message to log
        exc_info: Include exception traceback
    """
    get_logger().error(message, exc_info=exc_info)


def critical(message: str, exc_info: bool = True) -> None:
    """Log critical message.

    Args:
        message: Message to log
        exc_info: Include exception traceback
    """
    get_logger().critical(message, exc_info=exc_info)
