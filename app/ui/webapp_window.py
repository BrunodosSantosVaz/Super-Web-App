"""WebApp window with WebView.

This module provides the window that displays a webapp using WebKit WebView.
"""

from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, GLib, GObject, Gtk, WebKit, Gdk, GdkPixbuf

from ..core.webapp_manager import WebAppManager
from ..data.models import WebApp, WebAppSettings
from ..utils.i18n import gettext as _, subscribe as i18n_subscribe, unsubscribe as i18n_unsubscribe
from ..utils.logger import get_logger
from ..utils.xdg import build_app_instance_id
from ..webengine.popup_handler import PopupHandler
from ..webengine.profile_manager import ProfileManager
from ..webengine.webview_manager import WebViewManager
from .system_tray import TrayIndicator
from .tab_manager import TabManager

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
        on_window_closed: Optional[Callable[[str], None]] = None,
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
        self._on_window_closed = on_window_closed
        self.tray_indicator: Optional[TrayIndicator] = None
        self._force_close = False
        self._app_instance_id = build_app_instance_id(webapp.id)
        self.tab_manager = None  # Will be initialized if tabs are enabled

        # Set window properties
        self.set_title(webapp.name)
        self.set_default_size(settings.window_width, settings.window_height)

        # Set unique WM_CLASS for this webapp window to separate from main app
        # This helps compositor distinguish this webapp from the main app and other webapps
        webapp_wm_class = self._app_instance_id

        # Try to set WM_CLASS for X11 (doesn't work in Wayland)
        try:
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            if display:
                # Set startup ID to help window manager
                startup_id = f"{webapp_wm_class}_{webapp.id}"
                logger.debug(f"Setting webapp window class: {webapp_wm_class}")
        except Exception as e:
            logger.debug(f"Could not set WM_CLASS: {e}")

        # Set window icon from webapp icon
        self._apply_window_icon()

        if settings.window_x is not None and settings.window_y is not None:
            # Note: GTK4 doesn't have move(), position is managed by compositor
            pass

        self._build_ui()
        self._load_webapp()

        # Delay tray icon initialization to ensure DBus actions are fully registered
        GLib.timeout_add(1500, self._init_tray_icon)

        # Connect close signal to save window state
        self.connect("close-request", self._on_close_request)
        self.connect("notify::minimized", self._on_notify_minimized)

        logger.info(f"WebAppWindow created for {webapp.name}")
        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)
        self._apply_translations()
        self.connect("destroy", self._on_destroy)

    def _apply_window_icon(self) -> None:
        """Apply current webapp icon to the window."""
        if not self.webapp.icon_path:
            return

        icon_path = Path(self.webapp.icon_path)
        if not icon_path.exists():
            return

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(icon_path), 64, 64, True
            )
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            self.set_icon_name(None)
            if hasattr(self, "set_icon_texture"):
                self.set_icon_texture(texture)
        except Exception as exc:
            logger.debug("Could not set window icon: %s", exc)

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

        # Toolbar view
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)

        # Tab view (if tabs are enabled)
        if self.settings.allow_tabs:
            self.tab_view = Adw.TabView()
            self.tab_view.set_vexpand(True)

            # Tab bar
            self.tab_bar = Adw.TabBar()
            self.tab_bar.set_view(self.tab_view)
            self.tab_bar.set_autohide(False)  # Always show tab bar, even with 1 tab
            self.tab_bar.set_expand_tabs(True)  # Expand tabs to fill available space

            # Add "New Tab" button to the end of tab bar
            new_tab_button = Gtk.Button()
            new_tab_button.set_icon_name("tab-new-symbolic")
            new_tab_button.set_tooltip_text("")  # Will be set by translations
            new_tab_button.connect("clicked", self._on_new_tab_clicked)
            new_tab_button.add_css_class("flat")
            self.tab_bar.set_end_action_widget(new_tab_button)

            # Store button for later use
            self.new_tab_button = new_tab_button

            # Put TabBar in the center of HeaderBar (replaces title)
            header_bar.set_title_widget(self.tab_bar)

            # Set TabView as content
            toolbar_view.set_content(self.tab_view)
        else:
            self.tab_view = None
            self.tab_bar = None
            self.new_tab_button = None

            # No tabs - content will be set later when WebView is created
            pass

        self.set_content(toolbar_view)

    def _apply_translations(self) -> None:
        """Update translated strings for UI elements."""
        self.back_button.set_tooltip_text(_("webapp.back.tooltip"))
        self.forward_button.set_tooltip_text(_("webapp.forward.tooltip"))
        self.reload_button.set_tooltip_text(_("webapp.reload.tooltip"))

        if self.new_tab_button:
            self.new_tab_button.set_tooltip_text(_("webapp.tab.new_tooltip"))

        if self.tab_view:
            page = self.tab_view.get_selected_page()
            if page and page.get_loading():
                page.set_title(_("webapp.tab.loading"))

        if self.tray_indicator and self.tray_indicator.available:
            self.tray_indicator.update_labels(_("tray.open"), _("tray.quit"))

    def _load_webapp(self) -> None:
        """Load the webapp URL in WebView."""
        # Create WebView manager
        webview_manager = WebViewManager(self.profile_manager)

        if self.settings.allow_tabs:
            # Setup popup handler for tabs
            popup_handler = PopupHandler(
                settings=self.settings,
                on_new_tab=self._on_popup_new_tab,
                on_new_window=self._on_new_window if self.settings.allow_popups else None,
            )

            # Create TabManager
            self.tab_manager = TabManager(
                tab_view=self.tab_view,
                tab_bar=self.tab_bar,
                webapp=self.webapp,
                settings=self.settings,
                profile_manager=self.profile_manager,
                webview_manager=webview_manager,
                popup_handler=popup_handler,
                on_title_changed_callback=self._on_title_changed,
                on_load_changed_callback=self._on_load_changed,
            )

            # Create first tab
            page = self.tab_manager.create_new_tab(self.webapp.url)
            if page:
                # Get the webview from the tab manager
                self.webview = self.tab_manager.get_active_webview()
            else:
                logger.error("Failed to create initial tab")

            logger.debug(f"Loaded webapp with tabs: {self.webapp.url}")

        else:
            # Setup popup handler without tabs
            popup_handler = PopupHandler(
                settings=self.settings,
                on_new_tab=None,
                on_new_window=self._on_new_window if self.settings.allow_popups else None,
            )

            # Create single WebView
            webview = webview_manager.create_webview_with_popup_handler(
                self.webapp.id, self.settings, popup_handler
            )

            # Connect navigation signals
            webview.connect("notify::uri", self._on_uri_changed)
            webview.connect("notify::title", self._on_title_changed)
            webview.connect("load-changed", self._on_load_changed)

            # Store webview
            self.webview = webview

            # Add directly to content
            toolbar_view = self.get_content()
            toolbar_view.set_content(webview)

            # Load initial URL
            webview.load_uri(self.webapp.url)

            logger.debug(f"Loaded webapp without tabs: {self.webapp.url}")

    def _init_tray_icon(self) -> bool:
        """Create tray icon if enabled for this webapp."""
        if not self.settings.show_tray:
            return False

        self._update_tray_icon()
        return False

    def _update_tray_icon(self) -> None:
        """Refresh tray icon configuration."""
        self._ensure_tray_indicator()
        if self.tray_indicator and self.tray_indicator.available:
            self.tray_indicator.update_title(self.webapp.name)
            self.tray_indicator.update_icon(self._tray_icon_name())
            self.tray_indicator.update_labels(_("tray.open"), _("tray.quit"))

    def _ensure_tray_indicator(self) -> None:
        """Create StatusNotifierItem indicator if needed."""
        if not self.settings.show_tray:
            return

        if self.tray_indicator and self.tray_indicator.available:
            return

        if self.tray_indicator:
            self.tray_indicator.destroy()
            self.tray_indicator = None

        indicator = TrayIndicator(
            app_id=self._app_instance_id,
            title=self.webapp.name,
            icon_name=self._tray_icon_name(),
            open_label=_("tray.open"),
            quit_label=_("tray.quit"),
            on_activate=self._on_tray_activate,
            on_quit=self._on_tray_quit,
        )

        if indicator.available:
            self.tray_indicator = indicator
        else:
            indicator.destroy()
            self.tray_indicator = None

    def _tray_icon_name(self) -> str:
        """Return icon name registered for this webapp."""
        if self.webapp.icon_path and Path(self.webapp.icon_path).exists():
            return self._app_instance_id
        return "applications-internet"

    def _on_tray_activate(self) -> None:
        """Present window when tray icon activated."""
        self.set_visible(True)
        self.present()

    def _on_tray_quit(self) -> None:
        """Exit webapp when Quit selected from tray."""
        self._force_close = True
        app = self.get_application()
        if app:
            app.quit()
        else:
            self.close()

    def _on_new_tab_clicked(self, button: Gtk.Button) -> None:
        """Handle new tab button clicked.

        Args:
            button: The button that was clicked
        """
        if self.tab_manager:
            self.tab_manager.create_new_tab()
            logger.debug("New tab button clicked")

    def _on_popup_new_tab(self, webview: WebKit.WebView, uri: str) -> None:
        """Handle new tab request from popup handler.

        Args:
            webview: New WebView (created by popup handler)
            uri: URI to load
        """
        if not self.tab_manager:
            return

        # The popup handler already created the webview, but we need to
        # let TabManager create and manage it properly
        self.tab_manager.create_new_tab(uri)
        logger.debug(f"New tab created from popup: {uri}")

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
            # Update navigation buttons for active webview
            active_webview = self.tab_manager.get_active_webview() if self.tab_manager else self.webview
            if active_webview:
                self.back_button.set_sensitive(active_webview.can_go_back())
                self.forward_button.set_sensitive(active_webview.can_go_forward())

            # Update tab loading state (handled by TabManager if tabs enabled)
            if not self.tab_manager and self.tab_view:
                page = self.tab_view.get_page(webview)
                if page:
                    page.set_loading(False)

    def _on_back_clicked(self, button: Gtk.Button) -> None:
        """Handle back button clicked."""
        # Get active webview (from tab manager if tabs enabled)
        webview = self.tab_manager.get_active_webview() if self.tab_manager else self.webview
        if webview and webview.can_go_back():
            webview.go_back()

    def _on_forward_clicked(self, button: Gtk.Button) -> None:
        """Handle forward button clicked."""
        # Get active webview (from tab manager if tabs enabled)
        webview = self.tab_manager.get_active_webview() if self.tab_manager else self.webview
        if webview and webview.can_go_forward():
            webview.go_forward()

    def _on_reload_clicked(self, button: Gtk.Button) -> None:
        """Handle reload button clicked."""
        # Get active webview (from tab manager if tabs enabled)
        webview = self.tab_manager.get_active_webview() if self.tab_manager else self.webview
        if webview:
            webview.reload()

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

        if self._force_close:
            self._force_close = False
            return False

        if self.settings.show_tray and self.tray_indicator and self.tray_indicator.available:
            self.hide()
            return True

        # Allow close
        return False

    def _on_language_changed(self, _language: str) -> None:
        """React to language change events."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Clean up translation subscription."""
        if hasattr(self, "_language_subscription") and self._language_subscription:
            i18n_unsubscribe(self._language_subscription)
        if self.tab_manager:
            self.tab_manager.cleanup()
        if self.tray_indicator:
            self.tray_indicator.destroy()
            self.tray_indicator = None
        if self._on_window_closed:
            try:
                self._on_window_closed(self.webapp.id)
            except Exception as exc:
                logger.debug("Erro ao notificar fechamento de janela: %s", exc)

    def _on_notify_minimized(self, window: Gtk.Window, _param: GObject.ParamSpec) -> None:
        """Hide window when minimized if tray integration is enabled."""
        if (
            self.settings.show_tray
            and self.tray_indicator
            and self.tray_indicator.available
            and window.get_property("minimized")
        ):
            window.hide()

    def refresh_branding(self, webapp: WebApp) -> None:
        """Refresh window, tray icon, and associated metadata after update."""
        logger.info("Refreshing branding for webapp %s", webapp.id)
        self.webapp = webapp
        self.set_title(webapp.name)
        self._apply_window_icon()

        updated_settings = self.webapp_manager.get_webapp_settings(webapp.id)
        if updated_settings:
            self.settings = updated_settings

        if self.settings.show_tray:
            self._update_tray_icon()
        elif self.tray_indicator:
            self.tray_indicator.destroy()
            self.tray_indicator = None
