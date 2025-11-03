"""WebView lifecycle and management.

This module provides high-level WebView management including
creation, configuration, and lifecycle management.
"""

import base64
import binascii
import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4
from weakref import WeakKeyDictionary

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import GObject, WebKit

from ..data.models import WebAppSettings
from ..utils.logger import Logger, get_logger
from ..utils.validators import sanitize_filename
from ..utils.xdg import XDGDirectories
from .popup_handler import NavigationHandler, PopupHandler
from .profile_manager import ProfileManager
from .security_manager import SecurityManager

logger = get_logger(__name__)

_frames_enum = getattr(WebKit, "UserContentInjectedFrames", None)
if _frames_enum is not None and hasattr(_frames_enum, "ALL_FRAMES") and not hasattr(_frames_enum, "ALL"):
    setattr(_frames_enum, "ALL", _frames_enum.ALL_FRAMES)

_injection_enum = getattr(WebKit, "UserScriptInjectionTime", None)
if _injection_enum is not None and hasattr(_injection_enum, "START") and not hasattr(_injection_enum, "DOCUMENT_START"):
    setattr(_injection_enum, "DOCUMENT_START", _injection_enum.START)


@dataclass(frozen=True)
class BlobDownloadPayload:
    file_path: str
    filename: str
    origin_url: Optional[str] = None
    mime_type: Optional[str] = None
    source_app: Optional[str] = None


BLOB_CAPTURE_JS = """
(function () {
  const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.superDownload;
  if (!handler || typeof handler.postMessage !== "function") {
    return;
  }

  const fetchBlobAndSend = async (href, suggestedName) => {
    try {
      const response = await fetch(href);
      const blob = await response.blob();

      const reader = new FileReader();
      reader.onload = () => {
        try {
          handler.postMessage({
            type: "blob-download",
            href,
            filename: suggestedName || null,
            mimeType: blob.type || "",
            dataUrl: reader.result,
          });
        } catch (error) {
          console.error("superDownload: failed to post message", error);
        }
      };
      reader.readAsDataURL(blob);
    } catch (error) {
      console.error("superDownload: failed to fetch blob", error);
    }
  };

  const shouldIntercept = (anchor) => {
    if (!anchor) {
      return false;
    }
    const href = anchor.getAttribute("href") || "";
    if (!href.startsWith("blob:")) {
      return false;
    }
    return anchor.hasAttribute("download") || anchor.getAttribute("download") !== null;
  };

  document.addEventListener(
    "click",
    (event) => {
      const anchor = event.target && event.target.closest ? event.target.closest("a") : null;
      if (!shouldIntercept(anchor)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const suggestedName = anchor.getAttribute("download") || anchor.textContent || null;
      fetchBlobAndSend(anchor.href, suggestedName);
    },
    true
  );
})();
"""


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
        base = self._get_command_base()
        if not base:
            logger.warning("Super Download não encontrado; usando fluxo padrão.")
            return False

        command = [*base, uri]
        return self._spawn(command, f"Download encaminhado para Super Download: {uri}")

    def forward_blob(self, payload: BlobDownloadPayload) -> bool:
        base = self._get_command_base()
        if not base:
            logger.warning(
                "Super Download não encontrado; fluxo padrão aplicado ao blob %s",
                payload.filename,
            )
            return False

        command: list[str] = [
            *base,
            "--ingest-file",
            payload.file_path,
            "--filename",
            payload.filename,
        ]

        if payload.origin_url:
            command.extend(["--origin-url", payload.origin_url])
        if payload.mime_type:
            command.extend(["--mime-type", payload.mime_type])
        if payload.source_app:
            command.extend(["--source-app", payload.source_app])

        return self._spawn(command, f"Download blob encaminhado para Super Download: {payload.filename}")

    def _get_command_base(self) -> Optional[list[str]]:
        if self._cached_command:
            return self._cached_command

        env_command = os.environ.get(self.ENV_COMMAND)
        if env_command:
            try:
                parsed = shlex.split(env_command)
                if parsed:
                    self._cached_command = parsed
                    return self._cached_command
            except ValueError as exc:
                logger.error(
                    "Variável %s inválida (%s); ignorando.",
                    self.ENV_COMMAND,
                    exc,
                )

        if shutil.which(self.FLATPAK_BINARY):
            self._cached_command = [self.FLATPAK_BINARY, "run", self.FLATPAK_APP_ID]
            return self._cached_command

        if shutil.which(self.HOST_BINARY):
            self._cached_command = [self.HOST_BINARY]
            return self._cached_command

        return None

    def _spawn(self, command: list[str], success_message: str) -> bool:
        try:
            stdout = None if Logger.is_debug_mode() else subprocess.DEVNULL
            stderr = None if Logger.is_debug_mode() else subprocess.DEVNULL
            subprocess.Popen(
                command,
                start_new_session=True,
                stdout=stdout,
                stderr=stderr,
            )
            logger.info(success_message)
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
        self._webview_ids: "WeakKeyDictionary[WebKit.WebView, str]" = WeakKeyDictionary()
        self._user_scripts_installed: "WeakKeyDictionary[WebKit.WebView, bool]" = WeakKeyDictionary()
        self._message_handlers: "WeakKeyDictionary[WebKit.WebView, int]" = WeakKeyDictionary()
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
        self._webview_ids[webview] = webapp_id

        if settings.use_super_download:
            self._install_blob_capture(webview, webapp_id)

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

    def _install_blob_capture(self, webview: WebKit.WebView, webapp_id: str) -> None:
        manager = getattr(webview, "get_user_content_manager", lambda: None)()
        if manager is None:
            logger.debug("UserContentManager indisponível; captura de blob ignorada.")
            return

        if self._user_scripts_installed.get(webview):
            return

        try:
            manager.unregister_script_message_handler("superDownload")
        except Exception:
            pass

        try:
            manager.register_script_message_handler("superDownload")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Falha ao registrar handler superDownload: %s", exc)
            return

        handler_id = manager.connect(
            "script-message-received::superDownload",
            self._on_blob_script_message,
            webview,
            webapp_id,
        )
        self._user_scripts_installed[webview] = True
        self._message_handlers[webview] = handler_id

        try:
            script = WebKit.UserScript.new(
                BLOB_CAPTURE_JS,
                getattr(WebKit.UserContentInjectedFrames, "ALL_FRAMES", 0),
                getattr(WebKit.UserScriptInjectionTime, "START", 0),
                [],
                [],
            )
            manager.add_script(script)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error(
                "Falha ao registrar script de captura de blob: %s", exc, exc_info=True
            )
            return

        logger.debug("Script de captura de blob instalado para webapp %s", webapp_id)

    def _on_blob_script_message(
        self,
        manager: WebKit.UserContentManager,
        message,
        webview: WebKit.WebView,
        webapp_id: str,
    ) -> None:
        if not self._use_super_download.get(webview, False):
            logger.debug("Mensagem de blob recebida, mas Super Download está desativado.")
            return

        logger.debug(
            "Mensagem de blob recebida: message=%s webview=%s",
            type(message).__name__,
            type(webview).__name__,
        )

        js_payload_source = message
        get_js_value = getattr(message, "get_js_value", None)
        if callable(get_js_value):
            try:
                js_payload_source = get_js_value()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error("Falha ao obter js_value da mensagem de blob: %s", exc, exc_info=True)
                js_payload_source = None
        elif hasattr(message, "get_value"):
            try:
                js_payload_source = message.get_value()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error("Falha ao obter value da mensagem de blob: %s", exc, exc_info=True)
                js_payload_source = None

        if js_payload_source is None:
            logger.error("Mensagem de blob sem js_value legível.")
            return

        payload = self._deserialize_blob_message(js_payload_source)
        if payload is None:
            return

        data_url = payload.get("dataUrl")
        if not data_url or not isinstance(data_url, str) or "base64," not in data_url:
            logger.warning("Mensagem de blob sem dataUrl válido.")
            return

        base64_data = data_url.split("base64,", 1)[1]
        binary = self._decode_blob_base64(base64_data)
        if binary is None:
            return

        filename_raw = payload.get("filename") or "blob-download"
        filename = sanitize_filename(filename_raw)
        origin_url = payload.get("href") or getattr(webview, "get_uri", lambda: None)()
        mime_type = payload.get("mimeType") or None

        cache_dir = XDGDirectories.get_cache_dir() / "blob-downloads"
        cache_dir.mkdir(parents=True, exist_ok=True)
        temp_path = cache_dir / f"{uuid4().hex}_{filename}"

        if not self._write_blob_to_path(temp_path, binary):
            return

        payload_obj = BlobDownloadPayload(
            file_path=str(temp_path),
            filename=filename,
            origin_url=origin_url,
            mime_type=mime_type,
            source_app=webapp_id,
        )

        if self._download_bridge.forward_blob(payload_obj):
            logger.info("Blob encaminhado para Super Download: %s", filename)
        else:
            logger.warning(
                "Falha ao encaminhar blob %s; arquivo permanece em %s",
                filename,
                temp_path,
            )

    @staticmethod
    def _decode_blob_base64(data: str) -> Optional[bytes]:
        try:
            return base64.b64decode(data, validate=True)
        except (ValueError, binascii.Error) as exc:
            logger.error("Falha ao decodificar blob em base64: %s", exc)
            return None

    @staticmethod
    def _write_blob_to_path(path: Path, content: bytes) -> bool:
        try:
            path.write_bytes(content)
            return True
        except OSError as exc:
            logger.error("Falha ao gravar blob interceptado em %s: %s", path, exc)
            return False

    @staticmethod
    def _deserialize_blob_message(js_value) -> Optional[dict]:
        try:
            if hasattr(js_value, "to_json"):
                payload_raw = js_value.to_json(0)
            elif hasattr(js_value, "to_string"):
                payload_raw = js_value.to_string()
            else:
                logger.error("Objeto JS recebido não suporta serialização.")
                return None
            payload = json.loads(payload_raw)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Falha ao decodificar mensagem de blob: %s", exc, exc_info=True)
            return None

        if not isinstance(payload, dict) or payload.get("type") != "blob-download":
            logger.debug("Mensagem de blob ignorada (payload inesperado): %s", payload)
            return None
        return payload

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
