"""Data models for WebApps Manager.

This module defines the domain models using dataclasses for type safety
and immutability where appropriate.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class WebApp:
    """Represents a web application.

    Attributes:
        id: Unique identifier (UUID)
        name: Display name of the webapp
        url: Initial URL to load
        icon_path: Path to the webapp's icon
        category: Category for organization (e.g., 'Social', 'Productivity')
        created_at: Timestamp when the webapp was created
        last_opened: Timestamp of last access (None if never opened)
        open_count: Number of times the webapp has been opened
    """

    id: str
    name: str
    url: str
    icon_path: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_opened: Optional[datetime] = None
    open_count: int = 0

    @staticmethod
    def generate_id() -> str:
        """Generate a unique UUID for a new webapp.

        Returns:
            String representation of a UUID4
        """
        return str(uuid4())

    @property
    def has_custom_icon(self) -> bool:
        """Check if webapp has a custom icon.

        Returns:
            True if icon_path is set, False otherwise
        """
        return self.icon_path is not None and len(self.icon_path) > 0


@dataclass
class WebAppSettings:
    """Settings specific to a web application.

    Attributes:
        webapp_id: Foreign key to WebApp.id
        allow_tabs: Whether to allow multiple tabs
        allow_popups: Whether to allow popup windows
        run_background: Keep running when window is closed
        show_tray: Show icon in system tray
        enable_notif: Allow web notifications
        user_agent: Custom user agent string (optional)
        javascript: Enable JavaScript execution
        zoom_level: Zoom level (1.0 = 100%)
        window_width: Last known window width
        window_height: Last known window height
        window_x: Last known window X position
        window_y: Last known window Y position
    """

    webapp_id: str
    allow_tabs: bool = True
    allow_popups: bool = True
    run_background: bool = False
    show_tray: bool = False
    enable_notif: bool = True
    user_agent: Optional[str] = None
    javascript: bool = True
    zoom_level: float = 1.0
    window_width: int = 1280
    window_height: int = 720
    window_x: Optional[int] = None
    window_y: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if self.zoom_level <= 0:
            raise ValueError("Zoom level must be positive")
        if self.window_width <= 0 or self.window_height <= 0:
            raise ValueError("Window dimensions must be positive")


@dataclass
class AppSettings:
    """Global application settings.

    Attributes:
        theme: UI theme ('default', 'dark', 'light')
        startup_behavior: What to do on startup
        shared_network_process: Whether to share WebKit network process
        language: UI language code (e.g., 'pt', 'en')
    """

    theme: str = "default"
    startup_behavior: str = "main_window"
    shared_network_process: bool = True
    language: str = "pt"

    VALID_THEMES = {"default", "dark", "light"}
    VALID_STARTUP_BEHAVIORS = {"main_window", "hidden", "restore_session"}
    VALID_LANGUAGES = {"pt", "en"}

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if self.theme not in self.VALID_THEMES:
            raise ValueError(f"Invalid theme: {self.theme}")
        if self.startup_behavior not in self.VALID_STARTUP_BEHAVIORS:
            raise ValueError(f"Invalid startup behavior: {self.startup_behavior}")
        if self.language not in self.VALID_LANGUAGES:
            raise ValueError(f"Invalid language: {self.language}")


@dataclass
class WebAppSession:
    """Represents a saved session for a webapp (tabs, etc).

    This is used to restore the webapp state when reopened.

    Attributes:
        webapp_id: Foreign key to WebApp.id
        active_tab_index: Index of the currently active tab
        tabs: List of URLs open in tabs
    """

    webapp_id: str
    active_tab_index: int = 0
    tabs: list[str] = field(default_factory=lambda: [])

    def __post_init__(self) -> None:
        """Validate session after initialization."""
        if self.tabs and self.active_tab_index >= len(self.tabs):
            raise ValueError("Active tab index out of range")

    @property
    def has_tabs(self) -> bool:
        """Check if session has any tabs.

        Returns:
            True if there are tabs, False otherwise
        """
        return len(self.tabs) > 0


@dataclass(frozen=True)
class WebAppCategory:
    """Represents a webapp category (immutable).

    Attributes:
        id: Unique identifier
        name: Display name
        icon: Icon name (from icon theme)
    """

    id: str
    name: str
    icon: str


# Predefined categories
DEFAULT_CATEGORIES: list[WebAppCategory] = [
    WebAppCategory("social", "Social", "system-users-symbolic"),
    WebAppCategory("messaging", "Messaging", "user-available-symbolic"),
    WebAppCategory("productivity", "Productivity", "document-edit-symbolic"),
    WebAppCategory("entertainment", "Entertainment", "emblem-music-symbolic"),
    WebAppCategory("news", "News", "emblem-documents-symbolic"),
    WebAppCategory("development", "Development", "applications-engineering-symbolic"),
    WebAppCategory("finance", "Finance", "emblem-money-symbolic"),
    WebAppCategory("other", "Other", "applications-other-symbolic"),
]
