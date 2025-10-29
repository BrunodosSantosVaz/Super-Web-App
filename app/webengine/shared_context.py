"""Shared WebKit context for resource optimization.

This module provides a singleton WebContext that is shared across
all webapps to minimize memory usage while maintaining security
through isolated profiles.
"""

from typing import Optional

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SharedWebContext:
    """Singleton WebContext shared across all webapps.

    This provides a shared network process while maintaining
    isolation through separate WebsiteDataManagers (profiles).
    """

    _instance: Optional[WebKit.WebContext] = None

    @classmethod
    def get_instance(cls) -> WebKit.WebContext:
        """Get or create the shared WebContext instance.

        Returns:
            Shared WebKit.WebContext instance
        """
        if cls._instance is None:
            logger.info("Creating shared WebContext")
            cls._instance = WebKit.WebContext.new()
            logger.info("WebContext created successfully")

        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the shared context (for testing purposes).

        Warning: This should only be used in tests.
        """
        cls._instance = None
        logger.debug("Shared WebContext reset")
