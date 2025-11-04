"""Main window for Super WebApp.

This module provides the main window UI for managing webapps,
including the list view, search, and management actions.
"""

from typing import Optional
from pathlib import Path
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk, Gdk, Pango

from ..core.webapp_manager import WebAppManager
from ..data.models import WebApp
from ..utils.i18n import gettext as _, subscribe as i18n_subscribe, unsubscribe as i18n_unsubscribe
from ..utils.logger import get_logger
from ..webengine.profile_manager import ProfileManager

logger = get_logger(__name__)

_STYLE_PROVIDER: Gtk.CssProvider | None = None


def _ensure_styles_loaded() -> None:
    """Load shared CSS tweaks to align visuals with Super Download."""
    global _STYLE_PROVIDER
    if _STYLE_PROVIDER is not None:
        return

    css = """
    .super-webapp-search {
        min-height: 44px;
        border-radius: 12px;
        padding: 0 12px;
        border: 1px solid alpha(@borders, 0.45);
        background-color: alpha(@view_bg_color, 0.9);
    }

    .super-webapp-search:focus-within {
        border-color: alpha(@accent_color, 0.75);
        box-shadow: 0 0 0 3px alpha(@accent_color, 0.2);
    }

    .super-webapp-row {
        padding: 12px;
        border-radius: 14px;
        border: 1px solid alpha(@borders, 0.4);
        background-color: @card_bg_color;
    }

    .super-webapp-row .image {
        border-radius: 12px;
    }

    .super-webapp-button-box button {
        min-height: 36px;
        min-width: 36px;
    }

    .super-webapp-button-box button.destructive-action {
        background-color: alpha(@destructive_bg_color, 0.55);
        border-color: alpha(@destructive_bg_color, 0.6);
        color: @destructive_fg_color;
    }

    .super-webapp-button-box button.destructive-action:hover {
        background-color: alpha(@destructive_bg_color, 0.75);
    }

    .super-webapp-list row {
        padding: 0;
        border: none;
        background-color: transparent;
    }
    """

    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))

    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
    _STYLE_PROVIDER = provider


class MainWindow(Adw.ApplicationWindow):
    """Main application window.

    Shows list of webapps with search and management capabilities.
    """

    def __init__(
        self,
        application: Adw.Application,
        webapp_manager: WebAppManager,
        profile_manager: ProfileManager,
        **kwargs
    ) -> None:
        """Initialize main window.

        Args:
            application: GTK Application instance
            webapp_manager: WebAppManager for business logic
            profile_manager: ProfileManager for webapp profiles
            **kwargs: Additional arguments for Adw.ApplicationWindow
        """
        super().__init__(application=application, **kwargs)

        self.webapp_manager = webapp_manager
        self.profile_manager = profile_manager

        self.set_default_size(900, 600)
        _ensure_styles_loaded()

        # Set application icon
        icon_path = Path(__file__).parent.parent / "data" / "icon.png"
        if icon_path.exists():
            try:
                from gi.repository import GdkPixbuf
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path), 48, 48, True
                )
                # Note: GTK4 sets icon via desktop file, but we try anyway
                logger.debug(f"Main window icon loaded from {icon_path}")
            except Exception as e:
                logger.debug(f"Could not load main window icon: {e}")

        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)

        self._build_ui()
        self._load_webapps()
        self._apply_translations()

        self.connect("destroy", self._on_destroy)

        logger.debug("MainWindow initialized")

    def _build_ui(self) -> None:
        """Build the main window UI."""
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(header_bar)

        # Add button for new webapp
        new_button = Gtk.Button()
        new_button.add_css_class("suggested-action")
        new_button.connect("clicked", self._on_new_webapp_clicked)
        header_bar.pack_end(new_button)
        self.new_button = new_button

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._create_menu())
        header_bar.pack_end(menu_button)
        self.menu_button = menu_button

        title_label = Gtk.Label()
        title_label.add_css_class("title-4")
        title_label.set_hexpand(True)
        title_label.set_xalign(0.5)
        header_bar.set_title_widget(title_label)
        self.title_label = title_label

        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)

        # Search bar
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.add_css_class("super-webapp-search")
        self.search_entry.connect("search-changed", self._on_search_changed)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_margin_top(12)
        search_box.set_margin_bottom(12)
        search_box.set_margin_start(12)
        search_box.set_margin_end(12)
        search_box.append(self.search_entry)
        content_box.append(search_box)

        # Scrolled window for webapp list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_margin_start(12)
        scrolled.set_margin_end(12)
        scrolled.set_margin_bottom(12)

        # List box for webapps
        self.list_box = Gtk.ListBox()
        self.list_box.add_css_class("boxed-list")
        self.list_box.add_css_class("super-webapp-list")
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.connect("row-activated", self._on_row_activated)

        # Placeholder for empty state
        placeholder = Adw.StatusPage()
        placeholder.set_icon_name("applications-internet-symbolic")
        self.status_placeholder = placeholder
        self.list_box.set_placeholder(self.status_placeholder)

        scrolled.set_child(self.list_box)
        content_box.append(scrolled)

        toolbar_view.set_content(content_box)

    def _create_menu(self) -> Gio.Menu:
        """Create application menu.

        Returns:
            Gio.Menu instance
        """
        menu = Gio.Menu()

        menu.append(_("menu.preferences"), "app.preferences")
        menu.append(_("menu.about"), "app.about")
        menu.append(_("menu.quit"), "app.quit")

        return menu

    def _load_webapps(self) -> None:
        """Load webapps from database and populate list."""
        # Clear existing items
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)

        # Load and add webapps
        webapps = self.webapp_manager.get_all_webapps()

        for webapp in webapps:
            row = self._create_webapp_row(webapp)
            self.list_box.append(row)

        logger.debug(f"Loaded {len(webapps)} webapps")
        self._apply_translations()

    def _create_webapp_row(self, webapp: WebApp) -> Gtk.ListBoxRow:
        """Create list row for a webapp.

        Args:
            webapp: WebApp to create row for

        Returns:
            Gtk.ListBoxRow widget
        """
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.set_selectable(False)
        row.set_margin_top(4)
        row.set_margin_bottom(4)

        # Store webapp ID in row data
        row.webapp_id = webapp.id

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.add_css_class("super-webapp-row")
        main_box.add_css_class("card")
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_hexpand(True)
        row.set_child(main_box)

        # Icon
        if webapp.icon_path:
            icon = Gtk.Image.new_from_file(webapp.icon_path)
        else:
            icon = Gtk.Image.new_from_icon_name("applications-internet-symbolic")

        icon.set_pixel_size(48)
        icon.set_valign(Gtk.Align.CENTER)
        main_box.append(icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_hexpand(True)
        main_box.append(info_box)

        name_label = Gtk.Label(label=webapp.name, xalign=0)
        name_label.add_css_class("title-4")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(name_label)

        url_label = Gtk.Label(label=webapp.url, xalign=0)
        url_label.add_css_class("dim-label")
        url_label.set_ellipsize(Pango.EllipsizeMode.END)
        url_label.set_wrap(True)
        info_box.append(url_label)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.add_css_class("super-webapp-button-box")
        button_box.set_valign(Gtk.Align.CENTER)
        main_box.append(button_box)

        # Launch button
        launch_button = Gtk.Button()
        launch_button.set_icon_name("media-playback-start-symbolic")
        launch_button.set_tooltip_text(_("main.launch.tooltip"))
        launch_button.connect("clicked", self._on_launch_clicked, webapp.id)
        button_box.append(launch_button)
        row.launch_button = launch_button  # type: ignore[attr-defined]

        # Settings button
        settings_button = Gtk.Button()
        settings_button.set_icon_name("emblem-system-symbolic")
        settings_button.set_tooltip_text(_("main.settings.tooltip"))
        settings_button.connect("clicked", self._on_settings_clicked, webapp.id)
        button_box.append(settings_button)
        row.settings_button = settings_button  # type: ignore[attr-defined]

        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.set_tooltip_text(_("main.delete.tooltip"))
        delete_button.add_css_class("destructive-action")
        delete_button.connect("clicked", self._on_delete_clicked, webapp.id)
        button_box.append(delete_button)
        row.delete_button = delete_button  # type: ignore[attr-defined]

        for button in (launch_button, settings_button, delete_button):
            button.set_valign(Gtk.Align.CENTER)

        row.name_label = name_label  # type: ignore[attr-defined]
        row.url_label = url_label  # type: ignore[attr-defined]
        row.icon_widget = icon  # type: ignore[attr-defined]

        return row

    def _apply_translations(self) -> None:
        """Apply translated strings to UI elements."""
        self.set_title(_("app.title"))
        if hasattr(self, "title_label"):
            self.title_label.set_label(_("app.title"))
        self.new_button.set_label(_("main.new_webapp"))
        self.search_entry.set_placeholder_text(_("main.search_placeholder"))
        self.status_placeholder.set_title(_("main.status.title"))
        self.status_placeholder.set_description(_("main.status.description"))

        row_widget = self.list_box.get_first_child()
        while row_widget:
            if isinstance(row_widget, Gtk.ListBoxRow):
                launch_btn = getattr(row_widget, "launch_button", None)
                if isinstance(launch_btn, Gtk.Button):
                    launch_btn.set_tooltip_text(_("main.launch.tooltip"))
                settings_btn = getattr(row_widget, "settings_button", None)
                if isinstance(settings_btn, Gtk.Button):
                    settings_btn.set_tooltip_text(_("main.settings.tooltip"))
                delete_btn = getattr(row_widget, "delete_button", None)
                if isinstance(delete_btn, Gtk.Button):
                    delete_btn.set_tooltip_text(_("main.delete.tooltip"))
            row_widget = row_widget.get_next_sibling()

        # Update menu labels
        if hasattr(self, "menu_button"):
            menu_model = self._create_menu()
            self.menu_button.set_menu_model(menu_model)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change notification."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Cleanup callbacks on destroy."""
        if self._language_subscription:
            i18n_unsubscribe(self._language_subscription)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text changed.

        Args:
            entry: Search entry widget
        """
        query = entry.get_text()
        logger.debug(f"Search query: {query}")

        # Clear list
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)

        # Search and populate
        webapps = self.webapp_manager.search_webapps(query)

        for webapp in webapps:
            row = self._create_webapp_row(webapp)
            self.list_box.append(row)

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Handle row activation (double-click or Enter).

        Args:
            list_box: List box widget
            row: Activated row
        """
        if hasattr(row, "webapp_id"):
            self.launch_webapp(row.webapp_id)

    def _on_new_webapp_clicked(self, button: Gtk.Button) -> None:
        """Handle new webapp button clicked.

        Args:
            button: Button widget
        """
        logger.info("New webapp button clicked")
        from .add_dialog import AddWebAppDialog

        dialog = AddWebAppDialog(
            self, self.webapp_manager, on_saved=self._load_webapps
        )
        dialog.present(self)

    def _on_launch_clicked(self, button: Gtk.Button, webapp_id: str) -> None:
        """Handle launch button clicked.

        Args:
            button: Button widget
            webapp_id: WebApp ID to launch
        """
        self.launch_webapp(webapp_id)

    def launch_webapp(self, webapp_id: str) -> None:
        """Launch webapp in separate process."""
        logger.info(f"Launching webapp in separate process: {webapp_id}")

        self.webapp_manager.record_webapp_opened(webapp_id)

        webapp = self.webapp_manager.get_webapp(webapp_id)
        if not webapp:
            logger.error(f"WebApp not found: {webapp_id}")
            return

        # Launch webapp in separate process
        try:
            cmd = [
                sys.executable,
                "-m",
                "app.standalone_webapp",
                webapp_id,
            ]

            # Add debug flag if in debug mode
            from ..utils.logger import Logger
            if Logger.is_debug_mode():
                cmd.append("--debug")

            # Start subprocess (don't wait for it)
            process = subprocess.Popen(
                cmd,
                start_new_session=True,  # Detach from parent process
                stdout=subprocess.DEVNULL if not Logger.is_debug_mode() else None,
                stderr=subprocess.DEVNULL if not Logger.is_debug_mode() else None,
            )

            logger.info(f"Webapp launched in separate process (PID: {process.pid})")

        except Exception as e:
            logger.error(f"Failed to launch webapp in separate process: {e}", exc_info=True)

    def _on_settings_clicked(self, button: Gtk.Button, webapp_id: str) -> None:
        """Handle settings button clicked.

        Args:
            button: Button widget
            webapp_id: WebApp ID
        """
        logger.info(f"Settings clicked for webapp: {webapp_id}")
        # Get webapp
        webapp = self.webapp_manager.get_webapp(webapp_id)
        if not webapp:
            return

        # Open edit dialog
        from .add_dialog import AddWebAppDialog

        dialog = AddWebAppDialog(
            self, self.webapp_manager, webapp=webapp, on_saved=self._load_webapps
        )
        dialog.present(self)

    def _on_delete_clicked(self, button: Gtk.Button, webapp_id: str) -> None:
        """Handle delete button clicked.

        Args:
            button: Button widget
            webapp_id: WebApp ID
        """
        logger.info(f"Delete clicked for webapp: {webapp_id}")

        # Get webapp
        webapp = self.webapp_manager.get_webapp(webapp_id)
        if not webapp:
            return

        # Show confirmation dialog
        dialog = Adw.AlertDialog()
        dialog.set_heading(f"Delete {webapp.name}?")
        dialog.set_body(
            "This will permanently delete the webapp and all its data, "
            "including cookies, cache, and settings. This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        # Handle response
        def on_response(dialog, response):
            if response == "delete":
                try:
                    self.webapp_manager.delete_webapp(webapp_id)
                    self.close_webapp(webapp_id)
                    logger.info(f"WebApp deleted: {webapp_id}")
                    # Refresh list
                    self._load_webapps()
                except Exception as e:
                    logger.error(f"Error deleting webapp: {e}", exc_info=True)

        dialog.connect("response", on_response)
        dialog.present(self)


    def close_webapp(self, webapp_id: str) -> bool:
        """Close webapp (webapps now run in separate processes)."""
        logger.info(f"Request to close webapp: {webapp_id}")
        try:
            closed = self.webapp_manager.close_running_webapp(webapp_id)
            if closed:
                logger.debug("Signal enviado para encerrar webapp %s", webapp_id)
            else:
                logger.debug("Nenhum processo ativo encontrado para %s", webapp_id)
            return closed
        except Exception as exc:
            logger.error("Erro ao tentar fechar webapp %s: %s", webapp_id, exc)
            return False
