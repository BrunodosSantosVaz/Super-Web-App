"""WebKit profile management for isolated webapp data.

This module manages isolated profiles (cookies, cache, storage) for each
webapp, similar to Firefox profiles but using WebKit's WebsiteDataManager.
"""

import json
from pathlib import Path
from typing import Dict, Optional

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit

from ..data.models import WebAppSettings
from ..utils.logger import get_logger
from ..utils.xdg import XDGDirectories
from .shared_context import SharedWebContext

logger = get_logger(__name__)


def _safe_call(obj, method: str, *args) -> None:
    """Call attribute if available, logging when not supported."""
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args)
        except Exception as exc:
            logger.debug("Método %s falhou: %s", method, exc)
    else:
        logger.debug("Método %s indisponível nesta versão do WebKit", method)


class ProfileManager:
    """Manages isolated WebKit profiles for webapps.

    Each webapp gets its own profile with isolated:
    - Cookies
    - LocalStorage
    - IndexedDB
    - Cache
    - Permissions
    """

    def __init__(self) -> None:
        """Initialize profile manager."""
        self._profiles: Dict[str, Path] = {}
        self._sessions: Dict[str, WebKit.NetworkSession] = {}
        logger.debug("ProfileManager initialized")

    def get_profile_dir(self, webapp_id: str) -> Path:
        """Get or create profile directory for a webapp.

        Args:
            webapp_id: Unique identifier of the webapp

        Returns:
            Path to profile directory
        """
        if webapp_id in self._profiles:
            return self._profiles[webapp_id]

        profile_dir = XDGDirectories.get_profile_dir(webapp_id)
        self._profiles[webapp_id] = profile_dir
        return profile_dir

    def _get_network_session(self, webapp_id: str) -> WebKit.NetworkSession:
        """Get or create WebKit NetworkSession scoped to a webapp."""
        if webapp_id in self._sessions:
            return self._sessions[webapp_id]

        profile_dir = self.get_profile_dir(webapp_id)
        cache_dir = profile_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        session = WebKit.NetworkSession.new(
            data_directory=str(profile_dir),
            cache_directory=str(cache_dir),
        )
        self._sessions[webapp_id] = session
        logger.debug(f"NetworkSession created for {webapp_id} at {profile_dir}")
        return session

    def create_webview(
        self, webapp_id: str, settings: WebAppSettings
    ) -> WebKit.WebView:
        """Create WebView with isolated profile and shared context.

        Args:
            webapp_id: Unique identifier of the webapp
            settings: WebApp settings to apply

        Returns:
            Configured WebKit.WebView instance
        """
        logger.info(f"Creating WebView for webapp {webapp_id}")

        # Get shared context (network process)
        context = SharedWebContext.get_instance()

        # Ensure profile directories and network session
        profile_dir = self.get_profile_dir(webapp_id)
        session = self._get_network_session(webapp_id)

        logger.debug(f"Profile directory prepared at {profile_dir}")

        # Create WebView with shared context and per-webapp network session
        webview = WebKit.WebView(
            web_context=context,
            network_session=session,
        )

        # Apply settings
        self._apply_settings(webview, settings)

        logger.debug(f"WebView created for webapp {webapp_id}")
        return webview

    def _apply_settings(
        self, webview: WebKit.WebView, settings: WebAppSettings
    ) -> None:
        """Apply webapp settings to WebView.

        Args:
            webview: WebView to configure
            settings: Settings to apply
        """
        webkit_settings = webview.get_settings()

        # JavaScript
        _safe_call(webkit_settings, "set_enable_javascript", settings.javascript)

        # Zoom level
        _safe_call(webview, "set_zoom_level", settings.zoom_level)

        # User agent (if custom)
        if settings.user_agent:
            _safe_call(webkit_settings, "set_user_agent", settings.user_agent)

        # Additional security settings
        _safe_call(webkit_settings, "set_enable_developer_extras", False)
        _safe_call(webkit_settings, "set_enable_page_cache", True)

        # Block mixed content (HTTPS pages loading HTTP resources)
        _safe_call(webkit_settings, "set_allow_mixed_content", False)

        # WebGL and WebAudio (needed for modern webapps)
        _safe_call(webkit_settings, "set_enable_webgl", True)
        _safe_call(webkit_settings, "set_enable_webaudio", True)

        # Disable plugins (Flash, Java, etc)
        _safe_call(webkit_settings, "set_enable_plugins", False)

        # Media support (WebRTC, DRM)
        _safe_call(webkit_settings, "set_enable_media_stream", True)
        _safe_call(webkit_settings, "set_enable_encrypted_media", True)

        # Hardware acceleration
        policy_enum = getattr(WebKit, "HardwareAccelerationPolicy", None)
        if policy_enum is not None:
            policy_value = getattr(policy_enum, "ON_DEMAND", None)
            if policy_value is not None:
                _safe_call(
                    webkit_settings,
                    "set_hardware_acceleration_policy",
                    policy_value,
                )
            else:
                logger.debug(
                    "Valor ON_DEMAND indisponível em HardwareAccelerationPolicy"
                )
        else:
            logger.debug("Enum HardwareAccelerationPolicy não disponível no WebKit atual")

        # Enable smooth scrolling
        _safe_call(webkit_settings, "set_enable_smooth_scrolling", True)

        # Enable fullscreen API
        _safe_call(webkit_settings, "set_enable_fullscreen", True)

        logger.debug("WebView settings applied")

    def clear_profile(self, webapp_id: str) -> None:
        """Clear all data for a webapp profile.

        Args:
            webapp_id: Unique identifier of the webapp
        """
        logger.warning(f"Clearing profile data for webapp {webapp_id}")

        profile_dir = XDGDirectories.get_profile_dir(webapp_id)

        # Remove from cache
        self._profiles.pop(webapp_id, None)
        self._sessions.pop(webapp_id, None)

        # Delete profile directory
        if profile_dir.exists():
            import shutil

            shutil.rmtree(profile_dir)
            logger.info(f"Profile directory removed: {profile_dir}")

    def get_permissions(self, webapp_id: str) -> Dict[str, bool]:
        """Get saved permissions for a webapp.

        Args:
            webapp_id: Unique identifier of the webapp

        Returns:
            Dictionary of permission name to boolean value
        """
        profile_dir = XDGDirectories.get_profile_dir(webapp_id)
        permissions_file = profile_dir / "permissions.json"

        if not permissions_file.exists():
            return {}

        try:
            with open(permissions_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load permissions: {e}")
            return {}

    def save_permission(
        self, webapp_id: str, permission: str, granted: bool
    ) -> None:
        """Save permission decision for a webapp.

        Args:
            webapp_id: Unique identifier of the webapp
            permission: Permission name (e.g., 'notifications', 'geolocation')
            granted: Whether permission was granted
        """
        profile_dir = XDGDirectories.get_profile_dir(webapp_id)
        permissions_file = profile_dir / "permissions.json"

        # Load existing permissions
        permissions = self.get_permissions(webapp_id)

        # Update permission
        permissions[permission] = granted

        # Save back to file
        try:
            with open(permissions_file, "w") as f:
                json.dump(permissions, f, indent=2)
            logger.debug(f"Permission '{permission}' saved for webapp {webapp_id}")
        except Exception as e:
            logger.error(f"Failed to save permission: {e}")
