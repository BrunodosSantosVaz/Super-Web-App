"""Input validation utilities.

This module provides validation functions for user input,
URLs, and other data to ensure data integrity.
"""

import re
from typing import Tuple
from urllib.parse import urlparse

try:
    import validators as external_validators  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback used in limited envs
    class _SimpleValidators:
        """Fallback validator em caso de ausência da dependência externa."""

        @staticmethod
        def url(value: str) -> bool:
            if not value:
                return False

            try:
                parsed = urlparse(value)
            except Exception:
                return False

            if parsed.scheme not in ("http", "https"):
                return False

            if not parsed.netloc:
                return False

            # Evita domínios sem letras/números (ex: "http://")
            if not re.search(r"[a-zA-Z0-9]", parsed.netloc):
                return False

            return True

    external_validators = _SimpleValidators()


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate if string is a valid URL.

    Args:
        url: URL string to validate

    Returns:
        Tuple of (is_valid, normalized_url)
    """
    if not url or not url.strip():
        return False, ""

    url = url.strip()

    # Add https:// if no scheme provided
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Validate using external library
    if not external_validators.url(url):
        return False, url

    # Parse URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, url
    except Exception:
        return False, url

    return True, url


def validate_webapp_name(name: str) -> Tuple[bool, str]:
    """Validate webapp name.

    Args:
        name: Name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Name cannot be empty"

    name = name.strip()

    if len(name) < 2:
        return False, "Name must be at least 2 characters"

    if len(name) > 50:
        return False, "Name must be at most 50 characters"

    return True, ""


def validate_user_agent(user_agent: str) -> bool:
    """Validate user agent string.

    Args:
        user_agent: User agent string

    Returns:
        True if valid, False otherwise
    """
    if not user_agent:
        return True  # Empty is valid (will use default)

    # Basic validation: check length and characters
    if len(user_agent) > 500:
        return False

    # Must contain alphanumeric characters
    if not re.search(r"[a-zA-Z0-9]", user_agent):
        return False

    return True


def validate_zoom_level(zoom: float) -> bool:
    """Validate zoom level.

    Args:
        zoom: Zoom level (1.0 = 100%)

    Returns:
        True if valid, False otherwise
    """
    return 0.25 <= zoom <= 5.0


def validate_window_dimensions(width: int, height: int) -> bool:
    """Validate window dimensions.

    Args:
        width: Window width in pixels
        height: Window height in pixels

    Returns:
        True if valid, False otherwise
    """
    MIN_WIDTH = 400
    MIN_HEIGHT = 300
    MAX_WIDTH = 7680  # 8K resolution
    MAX_HEIGHT = 4320

    if not (MIN_WIDTH <= width <= MAX_WIDTH):
        return False

    if not (MIN_HEIGHT <= height <= MAX_HEIGHT):
        return False

    return True


def is_https(url: str) -> bool:
    """Check if URL uses HTTPS.

    Args:
        url: URL to check

    Returns:
        True if HTTPS, False otherwise
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https"
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem operations.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove or replace dangerous characters
    dangerous_chars = '<>:"/\\|?*'
    for char in dangerous_chars:
        filename = filename.replace(char, "_")

    # Remove leading/trailing whitespace and dots
    filename = filename.strip(". ")

    # Limit length
    if len(filename) > 255:
        filename = filename[:255]

    return filename or "unnamed"


def validate_category_id(category_id: str) -> bool:
    """Validate category ID.

    Args:
        category_id: Category identifier

    Returns:
        True if valid, False otherwise
    """
    if not category_id:
        return False

    # Must be lowercase alphanumeric with underscores
    pattern = r"^[a-z0-9_]+$"
    return bool(re.match(pattern, category_id))
