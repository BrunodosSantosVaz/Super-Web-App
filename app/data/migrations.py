"""Database migration system.

This module handles schema migrations for future versions.
Each migration is a function that takes a connection and applies changes.
"""

import sqlite3
from typing import Callable

# Migration type: function that takes connection and applies changes
Migration = Callable[[sqlite3.Connection], None]


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version.

    Args:
        conn: SQLite connection

    Returns:
        Current schema version number
    """
    cursor = conn.cursor()

    # Create version table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )
    """)

    cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    row = cursor.fetchone()

    return row[0] if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set schema version.

    Args:
        conn: SQLite connection
        version: New version number
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def migration_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Example migration: add new column (for future use).

    Args:
        conn: SQLite connection
    """
    # Example: Add a new column to webapps table
    # cursor = conn.cursor()
    # cursor.execute("ALTER TABLE webapps ADD COLUMN new_field TEXT")
    pass


# Registry of all migrations
MIGRATIONS: dict[int, Migration] = {
    # 1: migration_v1_to_v2,
    # Add future migrations here
}


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all pending migrations.

    Args:
        conn: SQLite connection
    """
    current_version = get_schema_version(conn)

    for version, migration in sorted(MIGRATIONS.items()):
        if version > current_version:
            migration(conn)
            set_schema_version(conn, version)
            conn.commit()
