"""Notification permission management.

This module handles web notification permissions on a per-webapp basis,
integrating with xdg-desktop-portal for native notifications.
"""

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import GLib, WebKit

from ..data.models import WebAppSettings
from ..utils.logger import get_logger
from ..webengine.profile_manager import ProfileManager

logger = get_logger(__name__)


class NativeNotificationHandler:
    """Handles native Linux notifications via D-Bus.

    Uses the org.freedesktop.Notifications D-Bus interface which is
    compatible with KDE, GNOME, and other desktop environments.
    """

    def __init__(self):
        """Initialize notification handler."""
        self._app_name = "Super WebApp"
        self._dbus_connection = None
        self._notification_counter = 0

        try:
            self._dbus_connection = gi.repository.Gio.bus_get_sync(
                gi.repository.Gio.BusType.SESSION, None
            )
            logger.debug("D-Bus connection established for notifications")
        except Exception as e:
            logger.error(f"Failed to connect to D-Bus: {e}")

    def send_notification(
        self,
        webapp_name: str,
        title: str,
        body: str,
        icon_path: str = None
    ) -> None:
        """Send a native notification via D-Bus.

        Args:
            webapp_name: Name of the webapp sending the notification
            title: Notification title
            body: Notification body
            icon_path: Optional path to icon file
        """
        if not self._dbus_connection:
            logger.warning("D-Bus not available, cannot send notification")
            return

        try:
            import subprocess

            # Build notify-send command
            command = ["notify-send"]

            # Add app name
            command.extend(["--app-name", self._app_name])

            # Add icon if available
            if icon_path:
                command.extend(["--icon", icon_path])

            # Add title (with webapp name as prefix)
            full_title = f"{webapp_name}: {title}" if title else webapp_name
            command.append(full_title)

            # Add body
            if body:
                command.append(body)

            logger.info(f"Sending notification: {command}")

            # Execute notify-send
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                logger.info(f"Notification sent successfully: {title}")
            else:
                logger.error(f"notify-send failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)


class NotificationManager:
    """Manages notification permissions for webapps.

    Provides granular control over which webapps can send notifications
    and persists user decisions.
    """

    def __init__(self, profile_manager: ProfileManager) -> None:
        """Initialize notification manager.

        Args:
            profile_manager: ProfileManager for accessing permissions
        """
        self.profile_manager = profile_manager
        self.native_handler = NativeNotificationHandler()
        logger.debug("NotificationManager initialized")

    def handle_permission_request(
        self,
        webview: WebKit.WebView,
        request: WebKit.NotificationPermissionRequest,
        webapp_id: str,
        settings: WebAppSettings,
    ) -> bool:
        """Handle notification permission request.

        Args:
            webview: WebView making the request
            request: Permission request object
            webapp_id: WebApp ID
            settings: WebApp settings

        Returns:
            True if handled, False otherwise
        """
        logger.info(f"Notification permission requested by webapp: {webapp_id}")

        # If enable_notif is True, ALWAYS allow automatically
        if settings.enable_notif:
            logger.info(f"Auto-granting notification permission (enable_notif=True): {webapp_id}")
            # Save permission if not already saved
            permissions = self.profile_manager.get_permissions(webapp_id)
            if "notifications" not in permissions:
                self.save_permission_decision(webapp_id, True)
            request.allow()
            return True

        # If enable_notif is False, check saved decision
        permissions = self.profile_manager.get_permissions(webapp_id)
        if "notifications" in permissions:
            decision = permissions["notifications"]
            logger.debug(f"Using saved decision: {decision}")

            if decision:
                request.allow()
            else:
                request.deny()

            return True

        # No saved decision and notifications disabled
        logger.debug("Notifications disabled, denying")
        request.deny()
        return True

    def save_permission_decision(
        self, webapp_id: str, granted: bool
    ) -> None:
        """Save user's permission decision.

        Args:
            webapp_id: WebApp ID
            granted: Whether permission was granted
        """
        logger.info(
            f"Saving notification permission for {webapp_id}: {granted}"
        )
        self.profile_manager.save_permission(webapp_id, "notifications", granted)

    def is_notification_enabled(
        self, webapp_id: str, settings: WebAppSettings
    ) -> bool:
        """Check if notifications are enabled for a webapp.

        Args:
            webapp_id: WebApp ID
            settings: WebApp settings

        Returns:
            True if notifications are enabled, False otherwise
        """
        if not settings.enable_notif:
            return False

        permissions = self.profile_manager.get_permissions(webapp_id)
        return permissions.get("notifications", False)

    def revoke_notification_permission(self, webapp_id: str) -> None:
        """Revoke notification permission for a webapp.

        Args:
            webapp_id: WebApp ID
        """
        logger.info(f"Revoking notification permission for {webapp_id}")
        self.profile_manager.save_permission(webapp_id, "notifications", False)

    def ensure_permission_if_enabled(
        self, webapp_id: str, settings: WebAppSettings
    ) -> None:
        """Ensure notification permission is granted if enabled in settings.

        This should be called when a webapp is created or settings are updated.

        Args:
            webapp_id: WebApp ID
            settings: WebApp settings
        """
        if settings.enable_notif:
            permissions = self.profile_manager.get_permissions(webapp_id)
            if "notifications" not in permissions:
                logger.info(
                    f"Setting initial notification permission for {webapp_id} "
                    f"(enable_notif=True)"
                )
                self.save_permission_decision(webapp_id, True)
