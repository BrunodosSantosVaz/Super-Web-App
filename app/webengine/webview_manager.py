"""WebView lifecycle and management.

This module provides high-level WebView management including
creation, configuration, and lifecycle management.
"""

from typing import Optional

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import GObject, WebKit

from ..data.models import WebAppSettings
from ..utils.logger import get_logger
from .popup_handler import NavigationHandler, PopupHandler
from .profile_manager import ProfileManager
from .security_manager import SecurityManager

logger = get_logger(__name__)


class WebViewManager:
    """Manages WebView lifecycle and configuration.

    This class provides a high-level interface for creating and
    managing WebViews with proper configuration.
    """

    def __init__(self, profile_manager: ProfileManager) -> None:
        """Initialize WebView manager.

        Args:
            profile_manager: ProfileManager instance for webapp profiles
        """
        self.profile_manager = profile_manager
        logger.debug("WebViewManager initialized")

    def create_webview(
        self, webapp_id: str, settings: WebAppSettings
    ) -> WebKit.WebView:
        """Create and configure a WebView for a webapp.

        Args:
            webapp_id: Unique identifier of the webapp
            settings: Settings to apply to the WebView

        Returns:
            Configured WebKit.WebView instance
        """
        logger.info(f"Creating WebView for webapp {webapp_id}")

        # Create WebView with isolated profile
        webview = self.profile_manager.create_webview(webapp_id, settings)

        # Apply security configuration
        SecurityManager.configure_webview_security(webview)

        # Setup navigation handling
        nav_handler = NavigationHandler(settings)
        nav_handler.setup_webview(webview)

        # Connect lifecycle signals
        self._connect_signals(webview)

        logger.debug(f"WebView created and configured for {webapp_id}")
        return webview

    def create_webview_with_popup_handler(
        self, webapp_id: str, settings: WebAppSettings, popup_handler: PopupHandler
    ) -> WebKit.WebView:
        """Create WebView with custom popup handler.

        Args:
            webapp_id: Unique identifier of the webapp
            settings: Settings to apply to the WebView
            popup_handler: PopupHandler instance

        Returns:
            Configured WebKit.WebView instance
        """
        webview = self.create_webview(webapp_id, settings)

        # Setup popup handling
        popup_handler.setup_webview(webview)

        return webview

    def _connect_signals(self, webview: WebKit.WebView) -> None:
        """Connect WebView signals for monitoring and handling.

        Args:
            webview: WebView to connect signals to
        """
        def _connect_if_available(obj: GObject.GObject, signal: str, handler) -> None:
            if GObject.signal_lookup(signal, obj.__class__):
                obj.connect(signal, handler)
                logger.debug("Connected WebView signal: %s", signal)
            else:
                logger.debug("Signal %s não disponível nesta versão do WebKit", signal)

        # Page load signals
        _connect_if_available(webview, "load-changed", self._on_load_changed)
        _connect_if_available(webview, "load-failed", self._on_load_failed)

        # Title changed (for tab labels)
        _connect_if_available(webview, "notify::title", self._on_title_changed)

        # Favicon changed (for tab icons)
        _connect_if_available(webview, "notify::favicon", self._on_favicon_changed)

        # Permission requests
        _connect_if_available(webview, "permission-request", self._on_permission_request)

        # Download requests (not available in older GTK WebKit releases)
        _connect_if_available(webview, "download-started", self._on_download_started)

        logger.debug("WebView signals connected (com fallback)")

    def _on_load_changed(
        self, webview: WebKit.WebView, load_event: WebKit.LoadEvent
    ) -> None:
        """Handle page load state changes.

        Args:
            webview: WebView that changed
            load_event: Load event type
        """
        uri = webview.get_uri()

        if load_event == WebKit.LoadEvent.STARTED:
            logger.debug(f"Page load started: {uri}")
        elif load_event == WebKit.LoadEvent.COMMITTED:
            logger.debug(f"Page load committed: {uri}")
        elif load_event == WebKit.LoadEvent.FINISHED:
            logger.info(f"Page load finished: {uri}")

    def _on_load_failed(
        self,
        webview: WebKit.WebView,
        load_event: WebKit.LoadEvent,
        failing_uri: str,
        error: gi.repository.GLib.Error,
    ) -> bool:
        """Handle page load failures.

        Args:
            webview: WebView that failed
            load_event: Load event type
            failing_uri: URI that failed to load
            error: Error details

        Returns:
            True if error was handled, False otherwise
        """
        logger.error(f"Failed to load {failing_uri}: {error.message}")

        # TODO: Show error page
        # For now, let WebKit show default error page
        return False

    def _on_title_changed(
        self, webview: WebKit.WebView, param: gi.repository.GObject.ParamSpec
    ) -> None:
        """Handle page title changes.

        Args:
            webview: WebView that changed
            param: Parameter specification
        """
        title = webview.get_title()
        if title:
            logger.debug(f"Page title changed: {title}")
            # Signal to update tab/window title

    def _on_favicon_changed(
        self, webview: WebKit.WebView, param: gi.repository.GObject.ParamSpec
    ) -> None:
        """Handle favicon changes.

        Args:
            webview: WebView that changed
            param: Parameter specification
        """
        logger.debug("Favicon changed")
        # Signal to update tab/window icon

    def _on_permission_request(
        self, webview: WebKit.WebView, request: WebKit.PermissionRequest
    ) -> bool:
        """Handle permission requests (notifications, camera, mic, etc).

        Args:
            webview: WebView making the request
            request: Permission request

        Returns:
            True if handled, False otherwise
        """
        # This will be handled by NotificationManager in the Core layer
        # For now, deny by default
        logger.info(f"Permission request: {type(request).__name__}")
        request.deny()
        return True

    def _on_download_started(
        self, webview: WebKit.WebView, download: WebKit.Download
    ) -> None:
        """Handle download started.

        Args:
            webview: WebView that started the download
            download: Download object
        """
        uri = download.get_request().get_uri()
        logger.info(f"Download started: {uri}")

        # TODO: Setup download handling (progress, completion, etc)
        # For now, let WebKit handle it with default behavior

    def suspend_webview(self, webview: WebKit.WebView) -> None:
        """Suspend a WebView to save resources.

        Used when webapp is minimized and run_background is False.

        Args:
            webview: WebView to suspend
        """
        logger.debug("Suspending WebView")
        # WebKit doesn't have explicit suspend, but we can stop loading
        webview.stop_loading()

    def resume_webview(self, webview: WebKit.WebView) -> None:
        """Resume a suspended WebView.

        Args:
            webview: WebView to resume
        """
        logger.debug("Resuming WebView")
        # Reload current page
        webview.reload()
