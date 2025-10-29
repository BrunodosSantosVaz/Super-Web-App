"""Notification permission management.

This module handles web notification permissions on a per-webapp basis,
integrating with xdg-desktop-portal for native notifications.
"""

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit

from ..data.models import WebAppSettings
from ..utils.logger import get_logger
from ..webengine.profile_manager import ProfileManager

logger = get_logger(__name__)


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

        # Check if notifications are disabled for this webapp
        if not settings.enable_notif:
            logger.debug("Notifications disabled in settings, denying")
            request.deny()
            return True

        # Check if we already have a saved decision
        permissions = self.profile_manager.get_permissions(webapp_id)
        if "notifications" in permissions:
            decision = permissions["notifications"]
            logger.debug(f"Using saved decision: {decision}")

            if decision:
                request.allow()
            else:
                request.deny()

            return True

        # No saved decision, need to ask user
        # This will be handled by UI layer showing a dialog
        logger.debug("No saved decision, need user input")
        return False

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
