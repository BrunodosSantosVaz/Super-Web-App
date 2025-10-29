"""Database layer for WebApps Manager.

This module provides a clean interface to SQLite database operations,
following the Repository pattern for separation of concerns.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from .models import AppSettings, WebApp, WebAppSettings


class DatabaseError(Exception):
    """Base exception for database operations."""

    pass


class Database:
    """SQLite database wrapper with connection pooling and migrations.

    This class handles all database operations and ensures proper
    connection management and error handling.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_database_exists()
        self._run_migrations()

    def _ensure_database_exists(self) -> None:
        """Create database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection (context manager).

        Yields:
            SQLite connection with row factory enabled

        Raises:
            DatabaseError: If connection fails
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise DatabaseError(f"Database error: {e}") from e
        finally:
            if conn:
                conn.close()

    def _run_migrations(self) -> None:
        """Run database migrations to create/update schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create webapps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webapps (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    icon_path TEXT,
                    category TEXT,
                    created_at INTEGER NOT NULL,
                    last_opened INTEGER,
                    open_count INTEGER DEFAULT 0
                )
            """)

            # Create webapp_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webapp_settings (
                    webapp_id TEXT PRIMARY KEY,
                    allow_tabs BOOLEAN DEFAULT 1,
                    allow_popups BOOLEAN DEFAULT 1,
                    run_background BOOLEAN DEFAULT 0,
                    show_tray BOOLEAN DEFAULT 0,
                    enable_notif BOOLEAN DEFAULT 1,
                    user_agent TEXT,
                    javascript BOOLEAN DEFAULT 1,
                    zoom_level REAL DEFAULT 1.0,
                    window_width INTEGER DEFAULT 1280,
                    window_height INTEGER DEFAULT 720,
                    window_x INTEGER,
                    window_y INTEGER,
                    FOREIGN KEY (webapp_id) REFERENCES webapps(id) ON DELETE CASCADE
                )
            """)

            # Create app_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Create indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webapps_category
                ON webapps(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webapps_last_opened
                ON webapps(last_opened DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_webapps_name
                ON webapps(name COLLATE NOCASE)
            """)

    # WebApp CRUD operations

    def create_webapp(self, webapp: WebApp, settings: WebAppSettings) -> None:
        """Create a new webapp with its settings.

        Args:
            webapp: WebApp instance to create
            settings: Settings for the webapp

        Raises:
            DatabaseError: If creation fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert webapp
            cursor.execute(
                """
                INSERT INTO webapps
                (id, name, url, icon_path, category, created_at, last_opened, open_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    webapp.id,
                    webapp.name,
                    webapp.url,
                    webapp.icon_path,
                    webapp.category,
                    int(webapp.created_at.timestamp()),
                    int(webapp.last_opened.timestamp()) if webapp.last_opened else None,
                    webapp.open_count,
                ),
            )

            # Insert settings
            cursor.execute(
                """
                INSERT INTO webapp_settings
                (webapp_id, allow_tabs, allow_popups, run_background, show_tray,
                 enable_notif, user_agent, javascript, zoom_level,
                 window_width, window_height, window_x, window_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    settings.webapp_id,
                    settings.allow_tabs,
                    settings.allow_popups,
                    settings.run_background,
                    settings.show_tray,
                    settings.enable_notif,
                    settings.user_agent,
                    settings.javascript,
                    settings.zoom_level,
                    settings.window_width,
                    settings.window_height,
                    settings.window_x,
                    settings.window_y,
                ),
            )

    def get_webapp(self, webapp_id: str) -> Optional[WebApp]:
        """Get a webapp by ID.

        Args:
            webapp_id: UUID of the webapp

        Returns:
            WebApp instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM webapps WHERE id = ?", (webapp_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_webapp(row)

    def get_all_webapps(self) -> list[WebApp]:
        """Get all webapps.

        Returns:
            List of WebApp instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM webapps ORDER BY name COLLATE NOCASE")
            rows = cursor.fetchall()
            return [self._row_to_webapp(row) for row in rows]

    def update_webapp(self, webapp: WebApp) -> None:
        """Update an existing webapp.

        Args:
            webapp: WebApp instance with updated data

        Raises:
            DatabaseError: If update fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE webapps
                SET name = ?, url = ?, icon_path = ?, category = ?,
                    last_opened = ?, open_count = ?
                WHERE id = ?
                """,
                (
                    webapp.name,
                    webapp.url,
                    webapp.icon_path,
                    webapp.category,
                    int(webapp.last_opened.timestamp()) if webapp.last_opened else None,
                    webapp.open_count,
                    webapp.id,
                ),
            )

    def delete_webapp(self, webapp_id: str) -> None:
        """Delete a webapp and its settings (CASCADE).

        Args:
            webapp_id: UUID of the webapp to delete

        Raises:
            DatabaseError: If deletion fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM webapps WHERE id = ?", (webapp_id,))

    # WebAppSettings operations

    def get_webapp_settings(self, webapp_id: str) -> Optional[WebAppSettings]:
        """Get settings for a webapp.

        Args:
            webapp_id: UUID of the webapp

        Returns:
            WebAppSettings instance or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM webapp_settings WHERE webapp_id = ?", (webapp_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_settings(row)

    def update_webapp_settings(self, settings: WebAppSettings) -> None:
        """Update webapp settings.

        Args:
            settings: WebAppSettings instance with updated data

        Raises:
            DatabaseError: If update fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE webapp_settings
                SET allow_tabs = ?, allow_popups = ?, run_background = ?,
                    show_tray = ?, enable_notif = ?, user_agent = ?,
                    javascript = ?, zoom_level = ?, window_width = ?,
                    window_height = ?, window_x = ?, window_y = ?
                WHERE webapp_id = ?
                """,
                (
                    settings.allow_tabs,
                    settings.allow_popups,
                    settings.run_background,
                    settings.show_tray,
                    settings.enable_notif,
                    settings.user_agent,
                    settings.javascript,
                    settings.zoom_level,
                    settings.window_width,
                    settings.window_height,
                    settings.window_x,
                    settings.window_y,
                    settings.webapp_id,
                ),
            )

    # AppSettings operations

    def get_app_settings(self) -> AppSettings:
        """Get global application settings.

        Returns:
            AppSettings instance with current settings
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_settings")
            rows = cursor.fetchall()

            settings_dict = {row["key"]: row["value"] for row in rows}

            language = settings_dict.get("language", "pt")
            return AppSettings(
                theme=settings_dict.get("theme", "default"),
                startup_behavior=settings_dict.get("startup_behavior", "main_window"),
                shared_network_process=settings_dict.get("shared_network_process", "true")
                == "true",
                language=language if language in AppSettings.VALID_LANGUAGES else "pt",
            )

    def update_app_settings(self, settings: AppSettings) -> None:
        """Update global application settings.

        Args:
            settings: AppSettings instance with updated data

        Raises:
            DatabaseError: If update fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            settings_map = {
                "theme": settings.theme,
                "startup_behavior": settings.startup_behavior,
                "shared_network_process": str(settings.shared_network_process).lower(),
                "language": settings.language,
            }

            for key, value in settings_map.items():
                cursor.execute(
                    """
                    INSERT INTO app_settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )

    # Search and filter operations

    def search_webapps(self, query: str) -> list[WebApp]:
        """Search webapps by name.

        Args:
            query: Search string (case-insensitive)

        Returns:
            List of matching WebApp instances
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM webapps
                WHERE name LIKE ?
                ORDER BY name COLLATE NOCASE
                """,
                (f"%{query}%",),
            )
            rows = cursor.fetchall()
            return [self._row_to_webapp(row) for row in rows]

    def get_webapps_by_category(self, category: str) -> list[WebApp]:
        """Get all webapps in a category.

        Args:
            category: Category ID

        Returns:
            List of WebApp instances in the category
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM webapps
                WHERE category = ?
                ORDER BY name COLLATE NOCASE
                """,
                (category,),
            )
            rows = cursor.fetchall()
            return [self._row_to_webapp(row) for row in rows]

    def get_recent_webapps(self, limit: int = 5) -> list[WebApp]:
        """Get recently opened webapps.

        Args:
            limit: Maximum number of results

        Returns:
            List of WebApp instances sorted by last_opened DESC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM webapps
                WHERE last_opened IS NOT NULL
                ORDER BY last_opened DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._row_to_webapp(row) for row in rows]

    # Helper methods

    @staticmethod
    def _row_to_webapp(row: sqlite3.Row) -> WebApp:
        """Convert database row to WebApp instance.

        Args:
            row: SQLite row object

        Returns:
            WebApp instance
        """
        return WebApp(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            icon_path=row["icon_path"],
            category=row["category"],
            created_at=datetime.fromtimestamp(row["created_at"]),
            last_opened=datetime.fromtimestamp(row["last_opened"])
            if row["last_opened"]
            else None,
            open_count=row["open_count"],
        )

    @staticmethod
    def _row_to_settings(row: sqlite3.Row) -> WebAppSettings:
        """Convert database row to WebAppSettings instance.

        Args:
            row: SQLite row object

        Returns:
            WebAppSettings instance
        """
        return WebAppSettings(
            webapp_id=row["webapp_id"],
            allow_tabs=bool(row["allow_tabs"]),
            allow_popups=bool(row["allow_popups"]),
            run_background=bool(row["run_background"]),
            show_tray=bool(row["show_tray"]),
            enable_notif=bool(row["enable_notif"]),
            user_agent=row["user_agent"],
            javascript=bool(row["javascript"]),
            zoom_level=float(row["zoom_level"]),
            window_width=int(row["window_width"]),
            window_height=int(row["window_height"]),
            window_x=int(row["window_x"]) if row["window_x"] else None,
            window_y=int(row["window_y"]) if row["window_y"] else None,
        )

    def close(self) -> None:
        """Close database connection if open."""
        if self._connection:
            self._connection.close()
            self._connection = None
