"""WebKit to native notification bridge.

This module intercepts web notifications and forwards them to the
native Linux notification system via D-Bus.
"""

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit
from weakref import WeakKeyDictionary

from ..utils.logger import get_logger

logger = get_logger(__name__)


class NotificationBridge:
    """Bridges WebKit web notifications to native Linux notifications.

    Intercepts show-notification signals from WebViews and forwards
    them to the NativeNotificationHandler.
    """

    def __init__(self, notification_manager) -> None:
        """Initialize notification bridge.

        Args:
            notification_manager: NotificationManager instance with native_handler
        """
        self._notification_manager = notification_manager
        self._webview_data: "WeakKeyDictionary[WebKit.WebView, dict]" = WeakKeyDictionary()
        logger.debug("NotificationBridge initialized")

    def setup_webview(
        self,
        webview: WebKit.WebView,
        webapp_id: str,
        webapp_name: str,
        icon_path: str = None
    ) -> None:
        """Setup notification interception for a WebView.

        Args:
            webview: WebView to monitor for notifications
            webapp_id: WebApp ID
            webapp_name: WebApp name (for notification display)
            icon_path: Optional path to webapp icon
        """
        # Store webapp data for this webview
        self._webview_data[webview] = {
            "webapp_id": webapp_id,
            "webapp_name": webapp_name,
            "icon_path": icon_path,
        }

        # Connect to show-notification signal
        try:
            webview.connect("show-notification", self._on_show_notification)
            logger.debug(f"Notification bridge connected for webapp: {webapp_id}")
        except Exception as e:
            logger.warning(f"Failed to connect notification signal: {e}")

    def _on_show_notification(
        self,
        webview: WebKit.WebView,
        notification: WebKit.Notification
    ) -> bool:
        """Handle show-notification signal from WebView.

        Args:
            webview: WebView showing the notification
            notification: WebKit notification object

        Returns:
            True to prevent default WebKit notification, False otherwise
        """
        try:
            # Get webapp data
            data = self._webview_data.get(webview)
            if not data:
                logger.warning("Notification from unknown webview")
                return False

            # Extract notification details
            title = notification.get_title() or "Notificação"
            body = notification.get_body() or ""

            logger.info(
                f"Web notification from {data['webapp_name']}: {title}"
            )

            # Send via native notification handler
            if self._notification_manager and self._notification_manager.native_handler:
                self._notification_manager.native_handler.send_notification(
                    webapp_name=data["webapp_name"],
                    title=title,
                    body=body,
                    icon_path=data.get("icon_path")
                )

            # Return True to prevent WebKit from showing its own notification
            # We're handling it natively instead
            return True

        except Exception as e:
            logger.error(f"Error handling web notification: {e}", exc_info=True)
            return False
