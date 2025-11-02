"""WebView lifecycle and management.

This module provides high-level WebView management including
creation, configuration, and lifecycle management.
"""

import os
import shlex
import shutil
import subprocess
from typing import Optional
from weakref import WeakKeyDictionary

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import GObject, WebKit

from ..data.models import WebAppSettings
from ..utils.logger import Logger, get_logger
from .popup_handler import NavigationHandler, PopupHandler
from .profile_manager import ProfileManager
from .security_manager import SecurityManager

logger = get_logger(__name__)


class SuperDownloadBridge:
    """Dispatch downloads to the Super Download application if available."""

    ENV_COMMAND = "SUPER_DOWNLOAD_COMMAND"
    FLATPAK_APP_ID = "br.com.superdownload"
    FLATPAK_BINARY = "flatpak"
    HOST_BINARY = "super-download"

    def __init__(self) -> None:
        self._cached_command: Optional[list[str]] = None

    def forward(self, uri: str) -> bool:
        """Forward the download URI to Super Download.

        Returns:
            True when the hand-off succeeded, False otherwise.
        """
        command = self._resolve_command(uri)
        if not command:
            logger.warning("Super Download não encontrado; usando fluxo padrão.")
            return False

        try:
            stdout = None if Logger.is_debug_mode() else subprocess.DEVNULL
            stderr = None if Logger.is_debug_mode() else subprocess.DEVNULL
            subprocess.Popen(
                command,
                start_new_session=True,
                stdout=stdout,
                stderr=stderr,
            )
            logger.info("Download encaminhado para Super Download: %s", uri)
            return True
        except FileNotFoundError:
            logger.error(
                "Comando configurado para Super Download não encontrado: %s", command[0]
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Falha ao encaminhar download para Super Download: %s", exc, exc_info=True
            )
        return False

    def _resolve_command(self, uri: str) -> Optional[list[str]]:
        if self._cached_command:
            return [*self._cached_command, uri]

        env_command = os.environ.get(self.ENV_COMMAND)
        if env_command:
            try:
                parsed = shlex.split(env_command)
                if parsed:
                    self._cached_command = parsed
                    return [*parsed, uri]
            except ValueError as exc:
                logger.error(
                    "Variável %s inválida (%s); ignorando.",
                    self.ENV_COMMAND,
                    exc,
                )

        if shutil.which(self.FLATPAK_BINARY):
            self._cached_command = [
                self.FLATPAK_BINARY,
                "run",
                self.FLATPAK_APP_ID,
            ]
            return [*self._cached_command, uri]

        if shutil.which(self.HOST_BINARY):
            self._cached_command = [self.HOST_BINARY]
            return [*self._cached_command, uri]

        return None


class WebViewManager:
    """Manages WebView lifecycle and configuration.

    This class provides a high-level interface for creating and
    managing WebViews with proper configuration.
    """

    def __init__(
        self,
        profile_manager: ProfileManager,
        download_bridge: Optional[SuperDownloadBridge] = None,
    ) -> None:
        """Initialize WebView manager.

        Args:
            profile_manager: ProfileManager instance for webapp profiles
        """
        self.profile_manager = profile_manager
        self._download_bridge = download_bridge or SuperDownloadBridge()
        self._use_super_download = WeakKeyDictionary()
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
        nav_handler = NavigationHandler(
            settings,
            download_handler=self._handle_download_policy,
        )
        nav_handler.setup_webview(webview)

        # Connect lifecycle signals
        self._connect_signals(webview)
        self._use_super_download[webview] = settings.use_super_download

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
        if hasattr(popup_handler, "set_download_handler"):
            popup_handler.set_download_handler(self._handle_popup_download)
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
        uri_request = download.get_request()
        uri = uri_request.get_uri() if uri_request else None
        logger.info("Download iniciado: %s", uri or "<desconhecido>")

        if not uri:
            logger.debug("Download sem URI detectada; mantendo fluxo padrão do WebKit.")
            return

        if not self._forward_download(webview, uri):
            return

        logger.debug("Cancelando download interno do WebKit após encaminhamento.")
        download.cancel()

    def _handle_download_policy(self, webview: WebKit.WebView, uri: str) -> bool:
        """Handle download interception triggered by navigation policy."""
        logger.info("Download solicitado por política: %s", uri or "<desconhecido>")
        if not uri:
            return False

        forwarded = self._forward_download(webview, uri)
        if forwarded:
            logger.debug("Bloqueando download interno após encaminhamento via política.")
        return forwarded

    def _handle_popup_download(self, webview: WebKit.WebView, uri: str) -> bool:
        """Handle downloads triggered directly from popup requests."""
        logger.info("Download solicitado via popup: %s", uri or "<desconhecido>")
        if not uri:
            return False
        return self._forward_download(webview, uri)

    def _forward_download(self, webview: WebKit.WebView, uri: str) -> bool:
        """Forward download to Super Download if enabled for this webview."""
        if not self._use_super_download.get(webview, False):
            logger.debug(
                "Super Download desativado para este webapp; mantendo fluxo padrão."
            )
            return False

        return self._download_bridge.forward(uri)

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
