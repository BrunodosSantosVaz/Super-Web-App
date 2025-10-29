"""WebApp window with WebView.

This module provides the window that displays a webapp using WebKit WebView.
"""

from pathlib import Path
from typing import Optional
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gtk, WebKit

from ..core.webapp_manager import WebAppManager
from ..data.models import WebApp, WebAppSettings
from ..utils.i18n import gettext as _, subscribe as i18n_subscribe, unsubscribe as i18n_unsubscribe
from ..utils.logger import get_logger
from ..utils.xdg import APP_ID
from ..webengine.popup_handler import PopupHandler
from ..webengine.profile_manager import ProfileManager
from ..webengine.webview_manager import WebViewManager
from .system_tray import APP_INDICATOR_AVAILABLE, TrayManager

logger = get_logger(__name__)


class WebAppWindow(Adw.ApplicationWindow):
    """Window for displaying a webapp with WebView."""

    def __init__(
        self,
        application: Adw.Application,
        webapp: WebApp,
        settings: WebAppSettings,
        webapp_manager: WebAppManager,
        profile_manager: ProfileManager,
        **kwargs
    ) -> None:
        """Initialize webapp window.

        Args:
            application: GTK Application instance
            webapp: WebApp to display
            settings: WebApp settings
            webapp_manager: WebAppManager instance
            profile_manager: ProfileManager instance
            **kwargs: Additional arguments
        """
        super().__init__(application=application, **kwargs)

        self.webapp = webapp
        self.settings = settings
        self.webapp_manager = webapp_manager
        self.profile_manager = profile_manager
        self.tray_manager = TrayManager() if APP_INDICATOR_AVAILABLE else None

        # Set window properties
        self.set_title(webapp.name)
        self.set_default_size(settings.window_width, settings.window_height)

        if settings.window_x is not None and settings.window_y is not None:
            # Note: GTK4 doesn't have move(), position is managed by compositor
            pass

        self._build_ui()
        self._load_webapp()
        self._init_tray_icon()

        # Connect close signal to save window state
        self.connect("close-request", self._on_close_request)

        logger.info(f"WebAppWindow created for {webapp.name}")
        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)
        self._apply_translations()
        self.connect("destroy", self._on_destroy)

    def _build_ui(self) -> None:
        """Build the window UI."""
        # Header bar
        header_bar = Adw.HeaderBar()

        # Back button
        back_button = Gtk.Button()
        back_button.set_icon_name("go-previous-symbolic")
        back_button.set_tooltip_text("")
        back_button.connect("clicked", self._on_back_clicked)
        header_bar.pack_start(back_button)

        # Forward button
        forward_button = Gtk.Button()
        forward_button.set_icon_name("go-next-symbolic")
        forward_button.set_tooltip_text("")
        forward_button.connect("clicked", self._on_forward_clicked)
        header_bar.pack_start(forward_button)

        # Reload button
        reload_button = Gtk.Button()
        reload_button.set_icon_name("view-refresh-symbolic")
        reload_button.set_tooltip_text("")
        reload_button.connect("clicked", self._on_reload_clicked)
        header_bar.pack_start(reload_button)

        # Store buttons for later use
        self.back_button = back_button
        self.forward_button = forward_button
        self.reload_button = reload_button

        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Tab view (if tabs are enabled)
        if self.settings.allow_tabs:
            self.tab_view = Adw.TabView()
            self.tab_view.set_vexpand(True)

            # Tab bar
            tab_bar = Adw.TabBar()
            tab_bar.set_view(self.tab_view)
            content_box.append(tab_bar)
            content_box.append(self.tab_view)
        else:
            self.tab_view = None

        # Toolbar view
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.set_content(content_box)

        self.set_content(toolbar_view)

    def _apply_translations(self) -> None:
        """Update translated strings for UI elements."""
        self.back_button.set_tooltip_text(_("webapp.back.tooltip"))
        self.forward_button.set_tooltip_text(_("webapp.forward.tooltip"))
        self.reload_button.set_tooltip_text(_("webapp.reload.tooltip"))

        if self.tab_view:
            page = self.tab_view.get_selected_page()
            if page and page.get_loading():
                page.set_title(_("webapp.tab.loading"))

        if self.tray_manager:
            self.tray_manager.refresh_labels(_("tray.open"), _("tray.quit"))

    def _load_webapp(self) -> None:
        """Load the webapp URL in WebView."""
        # Create WebView manager
        webview_manager = WebViewManager(self.profile_manager)

        # Setup popup handler
        popup_handler = PopupHandler(
            settings=self.settings,
            on_new_tab=self._on_new_tab if self.settings.allow_tabs else None,
            on_new_window=self._on_new_window if self.settings.allow_popups else None,
        )

        # Create WebView
        webview = webview_manager.create_webview_with_popup_handler(
            self.webapp.id, self.settings, popup_handler
        )

        # Connect navigation signals
        webview.connect("notify::uri", self._on_uri_changed)
        webview.connect("notify::title", self._on_title_changed)
        webview.connect("load-changed", self._on_load_changed)

        # Store webview
        self.webview = webview

        if self.settings.allow_tabs:
            # Add as first tab
            page = self.tab_view.append(webview)
            page.set_title(self.webapp.name)
            page.set_loading(True)
        else:
            # Add directly to content
            toolbar_view = self.get_content()
            toolbar_view.set_content(webview)

        # Load initial URL
        webview.load_uri(self.webapp.url)

        logger.debug(f"Loading URL: {self.webapp.url}")

    def _init_tray_icon(self) -> None:
        """Create tray icon if the platform supports it and setting enabled."""
        if not self.tray_manager or not self.settings.show_tray:
            return

        icon_path: Optional[str] = None
        if self.webapp.icon_path and Path(self.webapp.icon_path).exists():
            icon_path = self.webapp.icon_path

        open_cmd = [
            sys.executable,
            "-m",
            "app.main",
            "--webapp",
            self.webapp.id,
            "--show-main-window",
        ]
        quit_cmd = [
            sys.executable,
            "-m",
            "app.main",
            "--quit",
        ]

        self.tray_manager.ensure_icon(
            app_id=f"{APP_ID}.{self.webapp.id}",
            title=self.webapp.name,
            icon_path=icon_path,
            open_label=_("tray.open"),
            quit_label=_("tray.quit"),
            open_cmd=open_cmd,
            quit_cmd=quit_cmd,
        )

    def _on_new_tab(self, webview: WebKit.WebView, uri: str) -> None:
        """Handle new tab request.

        Args:
            webview: New WebView
            uri: URI to load
        """
        if not self.tab_view:
            return

        page = self.tab_view.append(webview)
        page.set_title(_("webapp.tab.loading"))
        page.set_loading(True)

        # Connect signals for new tab
        webview.connect("notify::title", self._on_title_changed)
        webview.connect("load-changed", self._on_load_changed)

        logger.debug(f"New tab created: {uri}")

    def _on_new_window(self, webview: WebKit.WebView, uri: str) -> None:
        """Handle new window request.

        Args:
            webview: New WebView
            uri: URI to load
        """
        # Create new window for popup
        popup_window = Gtk.Window()
        popup_window.set_title(_("webapp.popup.title"))
        popup_window.set_default_size(800, 600)
        popup_window.set_child(webview)
        popup_window.present()

        logger.debug(f"New popup window created: {uri}")

    def _on_uri_changed(self, webview: WebKit.WebView, param) -> None:
        """Handle URI changed."""
        uri = webview.get_uri()
        logger.debug(f"URI changed: {uri}")

    def _on_title_changed(self, webview: WebKit.WebView, param) -> None:
        """Handle title changed."""
        title = webview.get_title()
        if title:
            # Update window title if main webview
            if webview == self.webview:
                self.set_title(f"{title} - {self.webapp.name}")

            # Update tab title if in tab view
            if self.tab_view:
                page = self.tab_view.get_page(webview)
                if page:
                    page.set_title(title)

    def _on_load_changed(self, webview: WebKit.WebView, load_event: WebKit.LoadEvent) -> None:
        """Handle load changed."""
        if load_event == WebKit.LoadEvent.FINISHED:
            # Update navigation buttons
            self.back_button.set_sensitive(webview.can_go_back())
            self.forward_button.set_sensitive(webview.can_go_forward())

            # Update tab loading state
            if self.tab_view:
                page = self.tab_view.get_page(webview)
                if page:
                    page.set_loading(False)

    def _on_back_clicked(self, button: Gtk.Button) -> None:
        """Handle back button clicked."""
        if self.webview.can_go_back():
            self.webview.go_back()

    def _on_forward_clicked(self, button: Gtk.Button) -> None:
        """Handle forward button clicked."""
        if self.webview.can_go_forward():
            self.webview.go_forward()

    def _on_reload_clicked(self, button: Gtk.Button) -> None:
        """Handle reload button clicked."""
        self.webview.reload()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Handle window close request.

        Returns:
            False to allow close, True to prevent
        """
        # Save window position and size
        width = self.get_width()
        height = self.get_height()

        # Note: GTK4 doesn't have get_position(), it's managed by compositor
        # We can only save size
        self.webapp_manager.update_window_state(
            self.webapp.id, width, height, 0, 0
        )

        logger.debug(f"Window state saved for {self.webapp.name}")

        # Allow close
        return False

    def _on_language_changed(self, _language: str) -> None:
        """React to language change events."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Clean up translation subscription."""
        if hasattr(self, "_language_subscription") and self._language_subscription:
            i18n_unsubscribe(self._language_subscription)
        if self.tray_manager:
            self.tray_manager.destroy()
