"""Popup and new window handling.

This module handles window.open(), target="_blank", and other
popup requests from webapps.
"""

from typing import Callable, Optional

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit

from ..data.models import WebAppSettings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PopupHandler:
    """Handles popup windows and new tab creation for webapps.

    Popups can be opened as:
    1. New tabs (if allow_tabs is True)
    2. New windows (if allow_popups is True but not allow_tabs)
    3. Blocked (if allow_popups is False)
    """

    def __init__(
        self,
        settings: WebAppSettings,
        on_new_tab: Optional[Callable[[WebKit.WebView, str], None]] = None,
        on_new_window: Optional[Callable[[WebKit.WebView, str], None]] = None,
        download_handler: Optional[Callable[[WebKit.WebView, str], bool]] = None,
    ) -> None:
        """Initialize popup handler.

        Args:
            settings: WebApp settings (controls popup behavior)
            on_new_tab: Callback when new tab should be created
            on_new_window: Callback when new window should be created
            download_handler: Optional callback when popup should be treated as download
        """
        self.settings = settings
        self.on_new_tab = on_new_tab
        self.on_new_window = on_new_window
        self._download_handler = download_handler

        logger.debug(
            f"PopupHandler initialized (tabs={settings.allow_tabs}, "
            f"popups={settings.allow_popups})"
        )

    def setup_webview(self, webview: WebKit.WebView) -> None:
        """Setup popup handling for a WebView.

        Args:
            webview: WebView to configure
        """
        webview.connect("create", self._on_create_popup)
        logger.debug("Popup handler connected to WebView")

    def _on_create_popup(
        self, webview: WebKit.WebView, navigation_action: WebKit.NavigationAction
    ) -> Optional[WebKit.WebView]:
        """Handle popup creation request.

        Args:
            webview: Parent WebView
            navigation_action: Navigation action that triggered popup

        Returns:
            New WebView if popup is allowed, None to block
        """
        if not self.settings.allow_popups:
            logger.info("Popup blocked (allow_popups=False)")
            return None

        # Get the URI being requested
        uri = navigation_action.get_request().get_uri()
        logger.info(f"Popup requested: {uri}")

        if self._download_handler and uri:
            try:
                handled = self._download_handler(webview, uri)
            except Exception as exc:  # pragma: no cover - defensive safeguard
                logger.error("Erro ao encaminhar download via popup: %s", exc, exc_info=True)
                handled = False

            if handled:
                logger.debug("Popup convertido em download via handler; não abrindo nova aba/janela")
                return None

        # Create related WebView (shares session with parent)
        new_webview = self._create_related_webview(webview)

        # Decide how to present the popup
        if self.settings.allow_tabs and self.on_new_tab:
            # Open as new tab
            logger.debug("Opening popup as new tab")
            self.on_new_tab(new_webview, uri)
        elif self.on_new_window:
            # Open as new window
            logger.debug("Opening popup as new window")
            self.on_new_window(new_webview, uri)
        else:
            logger.warning("No handler for popup, blocking")
            return None

        return new_webview

    def _create_related_webview(self, parent: WebKit.WebView) -> WebKit.WebView:
        """Create WebView related to parent (shares session).

        Args:
            parent: Parent WebView

        Returns:
            New WebView with shared session
        """
        create_with_related = getattr(WebKit.WebView, "new_with_related_view", None)
        if create_with_related:
            new_webview = create_with_related(parent)
            logger.debug("Created related WebView for popup (shared session)")
            return new_webview

        # Fallback for WebKit builds without new_with_related_view
        logger.debug(
            "Método new_with_related_view indisponível; criando WebView independente para popup"
        )
        new_webview = WebKit.WebView()

        try:
            parent_settings = parent.get_settings()
            new_settings = new_webview.get_settings()
            new_settings.set_enable_javascript(parent_settings.get_enable_javascript())
            if hasattr(new_settings, "set_allow_mixed_content"):
                new_settings.set_allow_mixed_content(
                    parent_settings.get_allow_mixed_content()
                )
        except Exception as exc:  # pragma: no cover - defensive safeguard
            logger.debug("Não foi possível copiar configurações para popup: %s", exc)

        return new_webview

    def set_download_handler(
        self, handler: Optional[Callable[[WebKit.WebView, str], bool]]
    ) -> None:
        """Configure download handler used to intercept popup URLs."""
        self._download_handler = handler


class NavigationHandler:
    """Handles navigation decisions and link opening behavior."""

    def __init__(
        self,
        settings: WebAppSettings,
        download_handler: Optional[Callable[[WebKit.WebView, str], bool]] = None,
    ) -> None:
        """Initialize navigation handler.

        Args:
            settings: WebApp settings
            download_handler: Optional callback invoked when a download is requested
        """
        self.settings = settings
        self.download_handler = download_handler
        logger.debug("NavigationHandler initialized")

    def setup_webview(self, webview: WebKit.WebView) -> None:
        """Setup navigation handling for a WebView.

        Args:
            webview: WebView to configure
        """
        webview.connect("decide-policy", self._on_decide_policy)
        logger.debug("Navigation handler connected to WebView")

    def _on_decide_policy(
        self,
        webview: WebKit.WebView,
        decision: WebKit.PolicyDecision,
        decision_type: WebKit.PolicyDecisionType,
    ) -> bool:
        """Handle navigation policy decisions.

        Args:
            webview: WebView making the decision
            decision: Policy decision object
            decision_type: Type of decision being made

        Returns:
            True if handled, False otherwise
        """
        if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            nav_decision = decision
            action = nav_decision.get_navigation_action()

            # Get mouse button and modifiers
            mouse_button = action.get_mouse_button()
            modifiers = action.get_modifiers()

            # Handle middle-click or Ctrl+click -> new tab
            if mouse_button == 2 or (
                mouse_button == 1
                and modifiers & gi.repository.Gdk.ModifierType.CONTROL_MASK
            ):
                # User wants new tab
                uri = action.get_request().get_uri()
                logger.debug(f"Opening link in new tab: {uri}")
                # TODO: Signal to open in new tab
                decision.ignore()
                return True

        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            response_decision = decision
            request = response_decision.get_request()
            uri = request.get_uri() if request else None

            is_supported_fn = getattr(response_decision, "is_mime_type_supported", None)
            should_download = (
                not is_supported_fn()
                if callable(is_supported_fn)
                else True  # assume download if API missing
            )

            if self.download_handler and uri and should_download:
                handled = self.download_handler(webview, uri)
                if handled:
                    response_decision.ignore()
                    return True

            if should_download:
                response_decision.download()
                return True

        # Let WebKit handle normally
        decision.use()
        return False
