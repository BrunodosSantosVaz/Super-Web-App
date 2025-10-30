"""XDG Base Directory utilities.

This module provides helpers for working with XDG directories,
following the freedesktop.org Base Directory specification.
"""

import os
import re
from pathlib import Path
from typing import Optional

# Application ID following reverse DNS notation
APP_ID = "br.com.infinity.webapps"

_ID_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9_]")


def build_app_instance_suffix(webapp_id: str) -> str:
    """Return a D-Bus safe suffix for per-webapp identifiers."""
    sanitized = _ID_SANITIZE_PATTERN.sub("_", webapp_id)
    return f"webapp_{sanitized}"


def build_app_instance_id(webapp_id: str) -> str:
    """Return the full application ID used for standalone webapps."""
    return f"{APP_ID}.{build_app_instance_suffix(webapp_id)}"


def build_desktop_filename(webapp_id: str) -> str:
    """Return the .desktop filename for a webapp (without path)."""
    return f"{build_app_instance_id(webapp_id)}.desktop"


def build_icon_filename(webapp_id: str) -> str:
    """Return the icon filename (PNG) for a webapp."""
    return f"{build_app_instance_id(webapp_id)}.png"


class XDGDirectories:
    """Provides access to XDG standard directories.

    Implements the XDG Base Directory Specification for proper
    Linux desktop integration.
    """

    @staticmethod
    def get_config_dir() -> Path:
        """Get XDG config directory for the application.

        Returns:
            Path to config directory (creates if doesn't exist)
        """
        base = os.environ.get("XDG_CONFIG_HOME")
        if not base:
            base = str(Path.home() / ".config")

        config_dir = Path(base) / APP_ID
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @staticmethod
    def get_data_dir() -> Path:
        """Get XDG data directory for the application.

        Returns:
            Path to data directory (creates if doesn't exist)
        """
        base = os.environ.get("XDG_DATA_HOME")
        if not base:
            base = str(Path.home() / ".local" / "share")

        data_dir = Path(base) / APP_ID
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def get_cache_dir() -> Path:
        """Get XDG cache directory for the application.

        Returns:
            Path to cache directory (creates if doesn't exist)
        """
        base = os.environ.get("XDG_CACHE_HOME")
        if not base:
            base = str(Path.home() / ".cache")

        cache_dir = Path(base) / APP_ID
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @staticmethod
    def get_runtime_dir() -> Path:
        """Get XDG runtime directory for the application.

        Returns:
            Path to runtime directory (creates if doesn't exist)

        Raises:
            RuntimeError: If XDG_RUNTIME_DIR is not set
        """
        base = os.environ.get("XDG_RUNTIME_DIR")
        if not base:
            raise RuntimeError("XDG_RUNTIME_DIR not set")

        runtime_dir = Path(base) / APP_ID
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return runtime_dir

    @classmethod
    def get_runtime_sessions_dir(cls) -> Path:
        """Directory used to track runtime session metadata."""
        sessions_dir = cls.get_runtime_dir() / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir

    @classmethod
    def get_webapp_pid_file(cls, webapp_id: str) -> Path:
        """Return control file path that stores the PID of a running webapp."""
        return cls.get_runtime_sessions_dir() / f"{webapp_id}.pid"

    @classmethod
    def get_database_path(cls) -> Path:
        """Get path to SQLite database file.

        Returns:
            Path to database file
        """
        return cls.get_config_dir() / "webapps.db"

    @classmethod
    def get_profiles_dir(cls) -> Path:
        """Get directory for WebKit profiles.

        Returns:
            Path to profiles directory (creates if doesn't exist)
        """
        profiles_dir = cls.get_data_dir() / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        return profiles_dir

    @classmethod
    def get_icons_dir(cls) -> Path:
        """Get directory for webapp icons.

        Returns:
            Path to icons directory (creates if doesn't exist)
        """
        icons_dir = cls.get_data_dir() / "icons"
        icons_dir.mkdir(parents=True, exist_ok=True)
        return icons_dir

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Get directory for log files.

        Returns:
            Path to logs directory (creates if doesn't exist)
        """
        logs_dir = cls.get_cache_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    @classmethod
    def get_launchers_dir(cls) -> Path:
        """Get directory for launcher helper scripts."""
        launchers_dir = cls.get_data_dir() / "launchers"
        launchers_dir.mkdir(parents=True, exist_ok=True)
        return launchers_dir

    @classmethod
    def get_profile_dir(cls, webapp_id: str) -> Path:
        """Get profile directory for a specific webapp.

        Args:
            webapp_id: UUID of the webapp

        Returns:
            Path to webapp profile directory (creates if doesn't exist)
        """
        profile_dir = cls.get_profiles_dir() / webapp_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    @classmethod
    def get_icon_path(cls, webapp_id: str, extension: str = "png") -> Path:
        """Get path to icon file for a webapp.

        Args:
            webapp_id: UUID of the webapp
            extension: File extension (default: png)

        Returns:
            Path to icon file
        """
        return cls.get_icons_dir() / f"{webapp_id}.{extension}"

    @staticmethod
    def get_applications_dir() -> Path:
        """Get directory for .desktop files.

        Returns:
            Path to applications directory (creates if doesn't exist)
        """
        base = os.environ.get("XDG_DATA_HOME")
        if not base:
            base = str(Path.home() / ".local" / "share")

        apps_dir = Path(base) / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        return apps_dir

    @staticmethod
    def _normalize_user_dir_path(value: str) -> Path:
        """Normalize paths from XDG user-dirs configuration entries."""
        cleaned = value.strip().strip('"')
        cleaned = cleaned.replace("$HOME", str(Path.home()))
        return Path(os.path.expandvars(cleaned)).expanduser()

    @classmethod
    def _get_user_dir(cls, key: str) -> Optional[Path]:
        """Lookup user directory from environment or user-dirs config."""
        env_key = f"XDG_{key}_DIR"
        env_value = os.environ.get(env_key)
        if env_value:
            return cls._normalize_user_dir_path(env_value)

        user_dirs_file = Path.home() / ".config" / "user-dirs.dirs"
        if user_dirs_file.exists():
            for line in user_dirs_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith(f"{env_key}="):
                    _, value = stripped.split("=", 1)
                    return cls._normalize_user_dir_path(value)
        return None

    @classmethod
    def get_user_desktop_dir(cls) -> Optional[Path]:
        """Get the user's desktop directory if available."""
        desktop_dir = cls._get_user_dir("DESKTOP")

        if not desktop_dir:
            # Try common fallbacks used in localized environments
            fallbacks = [
                Path.home() / "Desktop",
                Path.home() / "Área de trabalho",
            ]
            for candidate in fallbacks:
                if candidate.exists():
                    desktop_dir = candidate
                    break

        if not desktop_dir:
            # Final fallback: assume standard Desktop path
            desktop_dir = Path.home() / "Desktop"

        try:
            desktop_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        return desktop_dir

    @classmethod
    def get_user_desktop_file_path(cls, webapp_id: str) -> Optional[Path]:
        """Get path to desktop shortcut for a webapp."""
        desktop_dir = cls.get_user_desktop_dir()
        if not desktop_dir:
            return None
        return desktop_dir / build_desktop_filename(webapp_id)

    @classmethod
    def get_launcher_script_path(cls, webapp_id: str) -> Path:
        """Get path to helper launcher script for a webapp."""
        return cls.get_launchers_dir() / f"{webapp_id}.sh"

    @classmethod
    def get_desktop_file_path(cls, webapp_id: str) -> Path:
        """Get path to .desktop file for a webapp.

        Args:
            webapp_id: UUID of the webapp

        Returns:
            Path to .desktop file
        """
        return cls.get_applications_dir() / build_desktop_filename(webapp_id)

    @staticmethod
    def is_flatpak() -> bool:
        """Check if running inside Flatpak sandbox.

        Returns:
            True if running in Flatpak, False otherwise
        """
        return Path("/.flatpak-info").exists()
