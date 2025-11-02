"""Dialog for adding/editing webapps.

This module provides a dialog for creating new webapps or editing
existing ones with all configuration options.
"""

from typing import Optional
import threading
import uuid
from urllib.parse import urlparse
from pathlib import Path
import shutil

from PIL import Image

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from ..core.desktop_integration import DesktopIntegration
from ..core.icon_fetcher import IconFetcher
from ..core.webapp_manager import WebAppManager
from ..data.models import DEFAULT_CATEGORIES, WebApp
from ..utils.i18n import (
    gettext as _,
    get_category_label,
    subscribe as i18n_subscribe,
    unsubscribe as i18n_unsubscribe,
)
from ..utils.logger import get_logger
from ..utils.xdg import XDGDirectories

logger = get_logger(__name__)


class AddWebAppDialog(Adw.Dialog):
    """Dialog for adding a new webapp."""

    def __init__(
        self,
        parent: Gtk.Window,
        webapp_manager: WebAppManager,
        webapp: Optional[WebApp] = None,
        on_saved=None,
    ) -> None:
        """Initialize add webapp dialog.

        Args:
            parent: Parent window
            webapp_manager: WebAppManager for creating webapp
            webapp: Optional WebApp to edit (None for new)
            on_saved: Optional callback to call after successfully saving
        """
        super().__init__()

        self.webapp_manager = webapp_manager
        self.webapp = webapp
        self.icon_fetcher = IconFetcher()
        self.fetched_icon_path: Optional[str] = None
        self.on_saved = on_saved
        self._is_edit = webapp is not None
        self._icon_button_status = "default"
        self._language_subscription = None
        self._language_subscription = i18n_subscribe(self._on_language_changed)
        self._url_change_timeout_id: Optional[int] = None
        self._is_fetching_icon = False
        self._updating_name_field = False
        self._name_was_edited_manually = False
        self._file_dialog: Optional[Gtk.FileDialog] = None
        self._custom_icon_selected = False
        self._custom_icon_selected_before_fetch = False
        self._metadata_refresh_pending = self._is_edit

        self.set_title(_("dialog.edit_title") if self._is_edit else _("dialog.new_title"))
        self.set_content_width(600)
        self.set_content_height(700)

        self._build_ui()

        if webapp:
            self._load_webapp_data()

        self._apply_translations()
        self.connect("destroy", self._on_destroy)

        logger.debug("AddWebAppDialog initialized")

    def _build_ui(self) -> None:
        """Build dialog UI."""
        # Main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)

        # Toolbar header
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        # Cancel button
        cancel_button = Gtk.Button()
        cancel_button.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_button)
        self.cancel_button = cancel_button

        # Create/Save button
        self.save_button = Gtk.Button()
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(self.save_button)

        # Basic information group
        basic_group = Adw.PreferencesGroup()
        self.basic_group = basic_group

        # URL entry
        self.url_entry = Adw.EntryRow()
        self.url_entry.connect("changed", self._on_input_changed)
        self.url_entry.connect("changed", self._on_url_changed)
        self.url_entry.connect("entry-activated", self._on_url_entry_activated)
        basic_group.add(self.url_entry)
        url_child = self.url_entry.get_child()
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_url_focus_enter)
        if isinstance(url_child, Gtk.Widget):
            url_child.add_controller(focus_controller)
        else:
            self.url_entry.add_controller(focus_controller)

        # Name entry
        self.name_entry = Adw.EntryRow()
        self.name_entry.connect("changed", self._on_name_changed)
        basic_group.add(self.name_entry)

        # Category dropdown
        category_row = Adw.ComboRow()
        self.category_row = category_row

        # Create string list for categories
        self.categories_list = Gtk.StringList()
        for cat in DEFAULT_CATEGORIES:
            self.categories_list.append(get_category_label(cat.id))

        category_row.set_model(self.categories_list)
        category_row.set_selected(0)
        basic_group.add(category_row)

        content_box.append(basic_group)

        # Icon group
        icon_group = Adw.PreferencesGroup()
        self.icon_group = icon_group

        icon_button_row = Adw.ActionRow()
        icon_button_row.set_activatable(True)
        icon_button_row.connect("activated", self._on_icon_row_activated)
        self.icon_button_row = icon_button_row

        # Icon image display
        self.icon_image = Gtk.Image()
        self.icon_image.set_pixel_size(48)
        self.icon_image.set_from_icon_name("image-x-generic-symbolic")
        icon_button_row.add_prefix(self.icon_image)

        image_gesture = Gtk.GestureClick()
        image_gesture.connect("released", self._on_icon_image_clicked)
        self.icon_image.add_controller(image_gesture)

        icon_group.add(icon_button_row)
        content_box.append(icon_group)

        # Navigation group
        nav_group = Adw.PreferencesGroup()
        self.nav_group = nav_group

        # Allow tabs
        self.tabs_switch = Adw.SwitchRow()
        self.tabs_switch.set_active(True)
        nav_group.add(self.tabs_switch)

        # Allow popups
        self.popups_switch = Adw.SwitchRow()
        self.popups_switch.set_active(True)
        nav_group.add(self.popups_switch)

        content_box.append(nav_group)

        # System integration group
        system_group = Adw.PreferencesGroup()
        self.system_group = system_group

        # Notifications
        self.notif_switch = Adw.SwitchRow()
        self.notif_switch.set_active(True)
        system_group.add(self.notif_switch)

        # Show in tray
        self.tray_switch = Adw.SwitchRow()
        self.tray_switch.set_active(False)
        system_group.add(self.tray_switch)

        # Use Super Download integration
        self.super_download_switch = Adw.SwitchRow()
        self.super_download_switch.set_active(False)
        system_group.add(self.super_download_switch)

        content_box.append(system_group)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(content_box)
        scrolled.set_vexpand(True)

        # Toolbar view
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(scrolled)

        self.set_child(toolbar_view)

    def _apply_translations(self) -> None:
        """Apply localized strings to widgets."""
        self.set_title(_("dialog.edit_title") if self._is_edit else _("dialog.new_title"))
        self.cancel_button.set_label(_("dialog.cancel"))
        self.save_button.set_label(_("dialog.save") if self._is_edit else _("dialog.create"))
        self.basic_group.set_title(_("dialog.group.basic"))
        self.name_entry.set_title(_("dialog.field.name"))
        self.url_entry.set_title(_("dialog.field.url"))
        self.category_row.set_title(_("dialog.field.category"))
        self.icon_group.set_title(_("dialog.group.icon"))
        self.icon_button_row.set_title(_("dialog.icon.fetch_auto"))
        self.icon_button_row.set_subtitle(
            _("dialog.icon.fetch_loading") if self._icon_button_status == "loading"
            else _("dialog.icon.fetch_success") if self._icon_button_status == "success"
            else _("dialog.icon.custom_selected") if self._icon_button_status == "custom"
            else _("dialog.icon.fetch_failure") if self._icon_button_status == "failure"
            else _("dialog.icon.fetch_error") if self._icon_button_status == "error"
            else ""
        )
        self.nav_group.set_title(_("dialog.group.navigation"))
        self.tabs_switch.set_title(_("dialog.navigation.allow_tabs"))
        self.tabs_switch.set_subtitle(_("dialog.navigation.allow_tabs_desc"))
        self.popups_switch.set_title(_("dialog.navigation.allow_popups"))
        self.popups_switch.set_subtitle(_("dialog.navigation.allow_popups_desc"))
        self.system_group.set_title(_("dialog.group.system"))
        self.notif_switch.set_title(_("dialog.system.allow_notifications"))
        self.notif_switch.set_subtitle(_("dialog.system.allow_notifications_desc"))
        self.tray_switch.set_title(_("dialog.system.show_tray"))
        self.tray_switch.set_subtitle(_("dialog.system.show_tray_desc"))
        self.super_download_switch.set_title(_("dialog.system.use_super_download"))
        self.super_download_switch.set_subtitle(_("dialog.system.use_super_download_desc"))

        selected = self.category_row.get_selected()
        self.categories_list = Gtk.StringList()
        for cat in DEFAULT_CATEGORIES:
            self.categories_list.append(get_category_label(cat.id))
        self.category_row.set_model(self.categories_list)
        if 0 <= selected < self.categories_list.get_n_items():
            self.category_row.set_selected(selected)
        else:
            self.category_row.set_selected(0)

    def _load_webapp_data(self) -> None:
        """Load webapp data into form (for editing)."""
        if not self.webapp:
            return

        self._updating_name_field = True
        self.name_entry.set_text(self.webapp.name)
        self._updating_name_field = False
        self.url_entry.set_text(self.webapp.url)
        self._name_was_edited_manually = True

        # Find and set category
        if self.webapp.category:
            for i, cat in enumerate(DEFAULT_CATEGORIES):
                if cat.id == self.webapp.category:
                    self.category_row.set_selected(i)
                    break

        # Load icon if exists
        if self.webapp.icon_path:
            from pathlib import Path
            if Path(self.webapp.icon_path).exists():
                self.fetched_icon_path = self.webapp.icon_path
                self.icon_image.set_from_file(self.webapp.icon_path)
                self._icon_button_status = "success"

        # Load settings
        settings = self.webapp_manager.get_webapp_settings(self.webapp.id)
        if settings:
            self.tabs_switch.set_active(settings.allow_tabs)
            self.popups_switch.set_active(settings.allow_popups)
            self.notif_switch.set_active(settings.enable_notif)
            self.tray_switch.set_active(settings.show_tray)
            self.super_download_switch.set_active(settings.use_super_download)

    def _on_language_changed(self, _language: str) -> None:
        """React to global language changes."""
        self._apply_translations()

    def _on_destroy(self, *_args) -> None:
        """Cleanup translation listeners on destroy."""
        if self._language_subscription:
            i18n_unsubscribe(self._language_subscription)

    def _on_input_changed(self, entry: Adw.EntryRow) -> None:
        """Handle input changed.

        Args:
            entry: Entry that changed
        """
        # Enable save button only if name and URL are filled
        name = self.name_entry.get_text().strip()
        url = self.url_entry.get_text().strip()

        self.save_button.set_sensitive(len(name) > 0 and len(url) > 0)

    def _on_name_changed(self, entry: Adw.EntryRow) -> None:
        """Track manual edits on the name field."""
        if self._updating_name_field:
            self._on_input_changed(entry)
            return

        self._name_was_edited_manually = True
        self._on_input_changed(entry)

    def _on_url_changed(self, entry: Adw.EntryRow) -> None:
        """Handle URL changed - automatically fetch icon after delay.

        Args:
            entry: URL entry that changed
        """
        # Cancel previous timeout if exists
        if self._url_change_timeout_id is not None:
            GLib.source_remove(self._url_change_timeout_id)
            self._url_change_timeout_id = None

        url = entry.get_text().strip()
        if url and not self._is_edit:
            self._custom_icon_selected = False

        if url and not self._is_edit:
            fallback_name = self._derive_name_from_url(url)
            if fallback_name:
                self._set_name_from_title(fallback_name)

        # Only fetch automatically for new webapps; edits use explicit refresh
        if url and url.startswith(("http://", "https://")) and not self._is_edit:
            # Wait 1.5 seconds after user stops typing
            self._url_change_timeout_id = GLib.timeout_add(1500, self._auto_fetch_icon)

    def _on_url_focus_enter(
        self, _controller: Gtk.EventControllerFocus, *_args
    ) -> None:
        """Refresh metadata when the URL field gains focus during edit."""
        if not self._is_edit or not self._metadata_refresh_pending:
            return
        self._metadata_refresh_pending = False
        self._request_metadata_refresh(force=True)

    def _on_url_entry_activated(self, *_args) -> None:
        """Trigger metadata refresh when user presses Enter on URL field."""
        self._request_metadata_refresh(force=True)

    def _auto_fetch_icon(self) -> bool:
        """Automatically fetch icon in background."""
        self._url_change_timeout_id = None

        if not self._is_fetching_icon:
            self._fetch_icon_async(force=False)

        return False  # Don't repeat timeout

    def _fetch_icon_async(self, *, force: bool = False) -> None:
        """Fetch icon in background thread to avoid blocking UI."""
        url = self.url_entry.get_text().strip()

        if not url:
            return

        self._custom_icon_selected_before_fetch = self._custom_icon_selected
        self._is_fetching_icon = True
        self._icon_button_status = "loading"
        self._apply_translations()

        def fetch_in_thread():
            try:
                # Use webapp ID if editing, or generate unique temp ID for new webapp
                icon_id = self.webapp.id if self._is_edit else f"temp_{uuid.uuid4()}"
                icon_path, page_title = self.icon_fetcher.fetch_icon_and_title(
                    url, icon_id
                )
                icon_path_str = str(icon_path) if icon_path else None
                GLib.idle_add(self._on_icon_fetched, icon_path_str, page_title, force)
            except Exception as e:
                logger.error(f"Error fetching icon: {e}", exc_info=True)
                GLib.idle_add(self._on_icon_fetch_error)

        thread = threading.Thread(target=fetch_in_thread, daemon=True)
        thread.start()

    def _on_icon_fetched(
        self, icon_path: Optional[str], page_title: Optional[str], force_name: bool
    ) -> bool:
        """Handle icon fetch completion in main thread."""
        self._is_fetching_icon = False
        user_override_during_fetch = (
            self._custom_icon_selected and not self._custom_icon_selected_before_fetch
        )

        if icon_path:
            if user_override_during_fetch:
                logger.debug(
                    "Usuário escolheu ícone personalizado durante a busca; mantendo seleção"
                )
            elif self._custom_icon_selected and not force_name:
                logger.debug("Ícone personalizado já definido; mantendo seleção existente")
            else:
                self.fetched_icon_path = str(icon_path)
                self._icon_button_status = "success"
                self.icon_image.set_from_file(str(icon_path))
                self._custom_icon_selected = False
                logger.info("Icon fetched successfully")
        elif not self._custom_icon_selected:
            self._icon_button_status = "failure"
            self.icon_image.set_from_icon_name("image-missing-symbolic")
            logger.warning("Failed to fetch icon")
        else:
            logger.debug("Mantendo ícone personalizado após falha na busca")

        if page_title and (force_name or not self._name_was_edited_manually):
            self._set_name_from_title(page_title, force=force_name)
        elif force_name:
            fallback = self._derive_name_from_url(self.url_entry.get_text().strip())
            if fallback:
                self._set_name_from_title(fallback, force=True)

        self._custom_icon_selected_before_fetch = False
        self._apply_translations()
        return False

    def _request_metadata_refresh(self, force: bool) -> None:
        """Internal helper to request metadata refresh for current URL."""
        url = self.url_entry.get_text().strip()
        if not url:
            return

        self._custom_icon_selected_before_fetch = self._custom_icon_selected

        if force:
            self._custom_icon_selected = False
            self._name_was_edited_manually = False

        if self._url_change_timeout_id is not None:
            GLib.source_remove(self._url_change_timeout_id)
            self._url_change_timeout_id = None

        self._fetch_icon_async(force=force)

    def _on_icon_fetch_error(self) -> bool:
        """Handle icon fetch error in main thread."""
        self._is_fetching_icon = False
        if self._custom_icon_selected:
            logger.debug("Ignoring fetch error because a custom icon is in use")
        elif self._custom_icon_selected_before_fetch and self.fetched_icon_path:
            try:
                self.icon_image.set_from_file(self.fetched_icon_path)
                self._custom_icon_selected = True
                self._icon_button_status = "custom"
                logger.debug("Restored previous custom icon after fetch error")
            except Exception as exc:
                logger.warning("Could not restore previous custom icon: %s", exc)
                self._icon_button_status = "error"
                self.icon_image.set_from_icon_name("dialog-error-symbolic")
        else:
            self._icon_button_status = "error"
            self.icon_image.set_from_icon_name("dialog-error-symbolic")
        self._custom_icon_selected_before_fetch = False
        self._apply_translations()
        return False

    def _set_name_from_title(self, title: Optional[str], *, force: bool = False) -> None:
        """Update the name field with an automatically detected title."""
        if not title:
            return

        if not force and (self._is_edit or self._name_was_edited_manually):
            return

        normalized = " ".join(title.split()).strip()
        if not normalized:
            return

        current = self.name_entry.get_text().strip()
        if current.lower() == normalized.lower():
            return

        self._updating_name_field = True
        self.name_entry.set_text(normalized)
        self._updating_name_field = False
        self._on_input_changed(self.name_entry)

    def _derive_name_from_url(self, url: str) -> Optional[str]:
        """Suggest a name based on the URL's hostname."""
        if not url:
            return None

        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.hostname or ""
        if not host:
            return None

        host = host.strip()
        if host.startswith("www."):
            host = host[4:]

        host = host.split(":")[0]
        if not host:
            return None

        parts = [part for part in host.split(".") if part]
        if not parts:
            return None

        candidate = parts[0]
        generic_parts = {"www", "app", "web", "site"}
        if candidate in generic_parts and len(parts) > 1:
            candidate = parts[1]

        candidate = candidate.replace("-", " ").replace("_", " ").strip()
        if not candidate:
            return None

        return candidate.title()

    def _on_icon_row_activated(self, _row: Adw.ActionRow, *_args) -> None:
        """Handle clicks on the icon row."""
        self._show_icon_file_dialog()

    def _on_icon_image_clicked(
        self, _gesture: Gtk.GestureClick, _n_press: int, _x: float, _y: float
    ) -> None:
        """Allow clicking directly on the icon preview."""
        self._show_icon_file_dialog()

    def _show_icon_file_dialog(self) -> None:
        """Open file chooser to select a custom icon."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("dialog.icon.choose_title"))
        dialog.set_modal(True)

        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("dialog.icon.file_filter"))
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/jpeg")
        image_filter.add_mime_type("image/svg+xml")
        image_filter.add_mime_type("image/webp")
        image_filter.add_mime_type("image/x-icon")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)

        self._file_dialog = dialog

        from pathlib import Path

        candidates = [
            Path.home() / ".local" / "share" / "icons" / "hicolor" / "48x48" / "apps",
            Path.home() / ".local" / "share" / "icons",
            Path("/usr/share/icons/hicolor/48x48/apps"),
            Path("/usr/share/icons"),
        ]

        for base in candidates:
            if base.exists():
                try:
                    dialog.set_initial_folder(Gio.File.new_for_path(str(base)))
                except Exception as exc:
                    logger.debug("Não foi possível definir pasta inicial do seletor de ícones: %s", exc)
                break

        parent_window = self.get_root()
        if not isinstance(parent_window, Gtk.Window):
            parent_window = None

        dialog.open(parent_window, None, self._on_icon_file_dialog_response)

    def _on_icon_file_dialog_response(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        """Handle the result from the icon file chooser."""
        try:
            gio_file = dialog.open_finish(result)
        except GLib.Error as err:
            if err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                logger.debug("Icon selection cancelled by user")
            else:
                logger.warning(f"Failed to open icon file: {err}")
            return
        finally:
            self._file_dialog = None

        if gio_file is None:
            return

        path = gio_file.get_path()
        if not path:
            logger.warning("Selected icon file has no accessible path")
            return

        self._apply_custom_icon(path)

    def _persist_icon(self, webapp_id: str) -> Optional[str]:
        """Copy current icon to the app icon directory and return its path."""
        if not self.fetched_icon_path:
            return None

        source = Path(self.fetched_icon_path)
        if not source.exists():
            logger.warning("Icon source does not exist: %s", source)
            return None

        icons_dir = XDGDirectories.get_icons_dir()
        final_path = icons_dir / f"{webapp_id}.png"

        try:
            image = Image.open(source)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            image.save(final_path, "PNG", optimize=True)

            if "temp_" in source.stem:
                try:
                    source.unlink()
                except OSError as exc:
                    logger.debug("Could not remove temp icon: %s", exc)

            self.fetched_icon_path = str(final_path)
            return str(final_path)

        except Exception as exc:
            logger.warning("Failed to persist icon for %s: %s", webapp_id, exc)
            try:
                if source.suffix.lower() == ".png":
                    shutil.copy2(source, final_path)
                    self.fetched_icon_path = str(final_path)
                    return str(final_path)
            except Exception:
                pass
            return self.fetched_icon_path

    def _apply_custom_icon(self, path: str) -> None:
        """Set a custom icon chosen by the user."""
        try:
            self.icon_image.set_from_file(path)
        except Exception as exc:
            logger.warning(f"Failed to load custom icon: {exc}")
            self._icon_button_status = "failure"
            self.icon_image.set_from_icon_name("image-missing-symbolic")
            self._apply_translations()
            return

        self._is_fetching_icon = False
        self._custom_icon_selected = True
        self._custom_icon_selected_before_fetch = False
        self.fetched_icon_path = path
        self._icon_button_status = "custom"
        self._apply_translations()

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        """Handle save button clicked.

        Args:
            button: Button widget
        """
        name = self.name_entry.get_text().strip()
        url = self.url_entry.get_text().strip()

        if not name or not url:
            logger.warning("Cannot save: name or URL is empty")
            return

        # Get selected category
        selected_index = self.category_row.get_selected()
        category = DEFAULT_CATEGORIES[selected_index].id

        try:
            if self.webapp:
                # Prepare icon source before deletion
                temp_icon_path: Optional[Path] = None
                if self.fetched_icon_path:
                    source_path = Path(self.fetched_icon_path)
                    if source_path.exists():
                        temp_icon_path = (
                            XDGDirectories.get_icons_dir()
                            / f"temp_edit_{uuid.uuid4()}.png"
                        )
                        try:
                            shutil.copy2(source_path, temp_icon_path)
                            self.fetched_icon_path = str(temp_icon_path)
                        except Exception as exc:
                            logger.warning(
                                "Could not prepare temporary icon for edit: %s", exc
                            )

                # Close and delete current webapp
                self.webapp_manager.close_running_webapp(self.webapp.id)
                self.webapp_manager.delete_webapp(self.webapp.id)

                # Create new webapp with updated data
                new_webapp, new_settings = self.webapp_manager.create_webapp(
                    name, url, category
                )

                new_settings.allow_tabs = self.tabs_switch.get_active()
                new_settings.allow_popups = self.popups_switch.get_active()
                new_settings.enable_notif = self.notif_switch.get_active()
                new_settings.show_tray = self.tray_switch.get_active()
                new_settings.use_super_download = self.super_download_switch.get_active()
                self.webapp_manager.update_webapp_settings(new_settings)

                icon_path = self._persist_icon(new_webapp.id)
                if icon_path:
                    updated = self.webapp_manager.update_webapp(
                        new_webapp.id, icon_path=icon_path
                    )
                    if updated:
                        new_webapp = updated

                DesktopIntegration.create_desktop_file(new_webapp)

                # Ensure no temp icon is left behind if it still exists
                if temp_icon_path and temp_icon_path.exists():
                    try:
                        temp_icon_path.unlink()
                    except OSError:
                        pass

                self.webapp = new_webapp
                logger.info("WebApp replaced with new instance: %s", new_webapp.id)
            else:
                # Create new webapp
                webapp, settings = self.webapp_manager.create_webapp(
                    name, url, category
                )

                # Update settings with form values
                settings.allow_tabs = self.tabs_switch.get_active()
                settings.allow_popups = self.popups_switch.get_active()
                settings.enable_notif = self.notif_switch.get_active()
                settings.show_tray = self.tray_switch.get_active()
                settings.use_super_download = self.super_download_switch.get_active()
                self.webapp_manager.update_webapp_settings(settings)

                # If icon was fetched, move it to the webapp's final icon path
                icon_path = self._persist_icon(webapp.id)
                if icon_path:
                    webapp = self.webapp_manager.update_webapp(webapp.id, icon_path=icon_path)
                    if not webapp:
                        webapp = self.webapp_manager.get_webapp(webapp.id)

                # Create .desktop file for launcher integration
                DesktopIntegration.create_desktop_file(webapp)

                logger.info(f"WebApp created: {webapp.id}")

            # Close dialog
            self.close()

            # Notify parent to refresh
            if self.on_saved:
                self.on_saved()

        except Exception as e:
            logger.error(f"Error saving webapp: {e}", exc_info=True)
            # TODO: Show error dialog
