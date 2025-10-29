"""WebApp management and lifecycle.

This module is the core business logic for managing webapps,
handling CRUD operations, lifecycle, and coordination between
database, profiles, and UI.
"""

from datetime import datetime
from typing import List, Optional

from ..data.database import Database
from ..data.models import WebApp, WebAppSettings
from ..utils.logger import get_logger
from ..utils.validators import validate_url, validate_webapp_name
from ..utils.xdg import XDGDirectories
from ..webengine.profile_manager import ProfileManager

logger = get_logger(__name__)


class WebAppManager:
    """Manages webapp lifecycle and operations.

    This is the main business logic class that coordinates:
    - Database operations
    - Profile management
    - Desktop integration
    - Validation
    """

    def __init__(self, database: Database, profile_manager: ProfileManager) -> None:
        """Initialize webapp manager.

        Args:
            database: Database instance for persistence
            profile_manager: ProfileManager for webkit profiles
        """
        self.db = database
        self.profile_manager = profile_manager
        logger.info("WebAppManager initialized")

    def create_webapp(
        self, name: str, url: str, category: Optional[str] = None
    ) -> tuple[WebApp, WebAppSettings]:
        """Create a new webapp.

        Args:
            name: Display name for the webapp
            url: Initial URL to load
            category: Optional category ID

        Returns:
            Tuple of (WebApp, WebAppSettings) created

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Creating new webapp: {name}")

        # Validate inputs
        name_valid, name_error = validate_webapp_name(name)
        if not name_valid:
            raise ValueError(f"Invalid name: {name_error}")

        url_valid, normalized_url = validate_url(url)
        if not url_valid:
            raise ValueError(f"Invalid URL: {url}")

        # Generate unique ID
        webapp_id = WebApp.generate_id()

        # Create WebApp model
        webapp = WebApp(
            id=webapp_id,
            name=name.strip(),
            url=normalized_url,
            category=category,
            created_at=datetime.now(),
        )

        # Create default settings
        settings = WebAppSettings(webapp_id=webapp_id)

        # Save to database
        self.db.create_webapp(webapp, settings)

        # Create profile directory
        XDGDirectories.get_profile_dir(webapp_id)

        logger.info(f"WebApp created successfully: {webapp_id}")
        return webapp, settings

    def get_webapp(self, webapp_id: str) -> Optional[WebApp]:
        """Get webapp by ID.

        Args:
            webapp_id: Unique identifier

        Returns:
            WebApp instance or None if not found
        """
        return self.db.get_webapp(webapp_id)

    def get_all_webapps(self) -> List[WebApp]:
        """Get all webapps.

        Returns:
            List of all WebApp instances
        """
        return self.db.get_all_webapps()

    def update_webapp(
        self,
        webapp_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        icon_path: Optional[str] = None,
        category: Optional[str] = None,
    ) -> WebApp:
        """Update webapp information.

        Args:
            webapp_id: Unique identifier
            name: New name (if provided)
            url: New URL (if provided)
            icon_path: New icon path (if provided)
            category: New category (if provided)

        Returns:
            Updated WebApp instance

        Raises:
            ValueError: If webapp not found or validation fails
        """
        webapp = self.get_webapp(webapp_id)
        if not webapp:
            raise ValueError(f"WebApp not found: {webapp_id}")

        logger.info(f"Updating webapp: {webapp_id}")

        # Update fields if provided
        if name is not None:
            name_valid, name_error = validate_webapp_name(name)
            if not name_valid:
                raise ValueError(f"Invalid name: {name_error}")
            webapp.name = name.strip()

        if url is not None:
            url_valid, normalized_url = validate_url(url)
            if not url_valid:
                raise ValueError(f"Invalid URL: {url}")
            webapp.url = normalized_url

        if icon_path is not None:
            webapp.icon_path = icon_path

        if category is not None:
            webapp.category = category

        # Save to database
        self.db.update_webapp(webapp)

        logger.debug(f"WebApp updated: {webapp_id}")
        return webapp

    def delete_webapp(self, webapp_id: str) -> None:
        """Delete a webapp and all its data.

        Args:
            webapp_id: Unique identifier

        Raises:
            ValueError: If webapp not found
        """
        webapp = self.get_webapp(webapp_id)
        if not webapp:
            raise ValueError(f"WebApp not found: {webapp_id}")

        logger.warning(f"Deleting webapp: {webapp_id}")

        # Delete from database (CASCADE will delete settings)
        self.db.delete_webapp(webapp_id)

        # Clear profile data
        self.profile_manager.clear_profile(webapp_id)

        # Delete icon if exists
        icon_path = XDGDirectories.get_icon_path(webapp_id)
        if icon_path.exists():
            icon_path.unlink()

        # Delete .desktop file if exists
        desktop_file = XDGDirectories.get_desktop_file_path(webapp_id)
        if desktop_file.exists():
            desktop_file.unlink()

        logger.info(f"WebApp deleted: {webapp_id}")

    def get_webapp_settings(self, webapp_id: str) -> Optional[WebAppSettings]:
        """Get settings for a webapp.

        Args:
            webapp_id: Unique identifier

        Returns:
            WebAppSettings instance or None if not found
        """
        return self.db.get_webapp_settings(webapp_id)

    def update_webapp_settings(self, settings: WebAppSettings) -> None:
        """Update webapp settings.

        Args:
            settings: Updated settings

        Raises:
            ValueError: If validation fails
        """
        logger.debug(f"Updating settings for webapp: {settings.webapp_id}")
        self.db.update_webapp_settings(settings)

    def record_webapp_opened(self, webapp_id: str) -> None:
        """Record that a webapp was opened (for statistics).

        Args:
            webapp_id: Unique identifier
        """
        webapp = self.get_webapp(webapp_id)
        if not webapp:
            return

        webapp.last_opened = datetime.now()
        webapp.open_count += 1

        self.db.update_webapp(webapp)
        logger.debug(f"Recorded open for webapp: {webapp_id}")

    def search_webapps(self, query: str) -> List[WebApp]:
        """Search webapps by name.

        Args:
            query: Search string

        Returns:
            List of matching WebApp instances
        """
        if not query or not query.strip():
            return self.get_all_webapps()

        return self.db.search_webapps(query.strip())

    def get_webapps_by_category(self, category: str) -> List[WebApp]:
        """Get webapps in a specific category.

        Args:
            category: Category ID

        Returns:
            List of WebApp instances in category
        """
        return self.db.get_webapps_by_category(category)

    def get_recent_webapps(self, limit: int = 5) -> List[WebApp]:
        """Get recently opened webapps.

        Args:
            limit: Maximum number of results

        Returns:
            List of recently opened WebApp instances
        """
        return self.db.get_recent_webapps(limit)

    def update_window_state(
        self, webapp_id: str, width: int, height: int, x: int, y: int
    ) -> None:
        """Update webapp window position and size.

        Args:
            webapp_id: Unique identifier
            width: Window width
            height: Window height
            x: Window X position
            y: Window Y position
        """
        settings = self.get_webapp_settings(webapp_id)
        if not settings:
            return

        settings.window_width = width
        settings.window_height = height
        settings.window_x = x
        settings.window_y = y

        self.update_webapp_settings(settings)
        logger.debug(f"Window state updated for webapp: {webapp_id}")
