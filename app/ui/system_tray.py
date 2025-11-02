"""StatusNotifierItem (DBus) tray integration for webapps."""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib

from ..utils.logger import get_logger

logger = get_logger(__name__)

SNI_INTERFACE = "org.kde.StatusNotifierItem"
SNI_PATH = "/StatusNotifierItem"
DBUS_MENU_INTERFACE = "com.canonical.dbusmenu"
MENU_OBJECT_PATH = "/MenuBar"


class TrayIndicator:
    """Expose tray menu via StatusNotifierItem/DBusMenu."""

    OPEN_ITEM_ID = 1
    SEPARATOR_ITEM_ID = 2
    QUIT_ITEM_ID = 3

    def __init__(
        self,
        *,
        app_id: str,
        title: str,
        icon_name: str,
        on_activate: Callable[[], None],
        on_quit: Callable[[], None],
        open_label: str,
        quit_label: str,
    ) -> None:
        self._app_id = app_id
        self._title = title
        self._icon_name = icon_name or "applications-internet"
        self._status = "Active"
        self._on_activate = on_activate
        self._on_quit = on_quit
        self._open_label = open_label
        self._quit_label = quit_label
        self._menu_revision = 1

        self._connection: Optional[Gio.DBusConnection] = None
        self._registration_id: Optional[int] = None
        self._menu_registration_id: Optional[int] = None
        self._available = False

        try:
            self._setup_dbus()
        except Exception as exc:
            logger.warning("Bandeja desabilitada: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._available

    def update_title(self, title: str) -> None:
        if title == self._title:
            return
        self._title = title
        self._emit_property_changed("Title", GLib.Variant("s", self._title))

    def update_icon(self, icon_name: str) -> None:
        if not icon_name:
            icon_name = "applications-internet"
        if icon_name == self._icon_name:
            return
        self._icon_name = icon_name
        self._emit_property_changed("IconName", GLib.Variant("s", self._icon_name))

    def update_labels(self, open_label: str, quit_label: str) -> None:
        changed = False
        if open_label and open_label != self._open_label:
            self._open_label = open_label
            changed = True
        if quit_label and quit_label != self._quit_label:
            self._quit_label = quit_label
            changed = True
        if changed:
            self._menu_revision += 1
            self._emit_layout_updated()

    def destroy(self) -> None:
        if not self._connection:
            return
        if self._registration_id:
            self._connection.unregister_object(self._registration_id)
            self._registration_id = None
        if self._menu_registration_id:
            self._connection.unregister_object(self._menu_registration_id)
            self._menu_registration_id = None
        self._available = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _setup_dbus(self) -> None:
        self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._register_with_watcher()
        self._register_status_notifier()
        self._register_menu()
        self._available = True
        logger.info("Bandeja registrada via StatusNotifierItem")

    def _register_with_watcher(self) -> None:
        if not self._connection:
            return
        try:
            proxy = Gio.DBusProxy.new_sync(
                self._connection,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                None,
            )
            bus_name = self._connection.get_unique_name()
            proxy.call_sync(
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (bus_name,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            logger.debug("Registrado no StatusNotifierWatcher")
        except Exception as exc:
            logger.debug("StatusNotifierWatcher indisponível: %s", exc)

    def _register_status_notifier(self) -> None:
        if not self._connection:
            return
        introspection_xml = """
        <node>
          <interface name="org.kde.StatusNotifierItem">
            <property name="Category" type="s" access="read"/>
            <property name="Id" type="s" access="read"/>
            <property name="Title" type="s" access="read"/>
            <property name="Status" type="s" access="read"/>
            <property name="IconName" type="s" access="read"/>
            <property name="Menu" type="o" access="read"/>
            <method name="Activate">
              <arg name="x" type="i" direction="in"/>
              <arg name="y" type="i" direction="in"/>
            </method>
            <method name="ContextMenu">
              <arg name="x" type="i" direction="in"/>
              <arg name="y" type="i" direction="in"/>
            </method>
          </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(introspection_xml)
        interface_info = node_info.lookup_interface(SNI_INTERFACE)
        if not interface_info:
            raise RuntimeError("Não foi possível registrar interface StatusNotifierItem")
        self._registration_id = self._connection.register_object(
            SNI_PATH,
            interface_info,
            self._handle_method_call,
            self._handle_get_property,
            None,
        )

    def _register_menu(self) -> None:
        if not self._connection:
            return
        introspection_xml = """
        <node>
          <interface name="com.canonical.dbusmenu">
            <method name="GetLayout">
              <arg name="parentId" type="i" direction="in"/>
              <arg name="recursionDepth" type="i" direction="in"/>
              <arg name="propertyNames" type="as" direction="in"/>
              <arg name="revision" type="u" direction="out"/>
              <arg name="layout" type="(ia{sv}av)" direction="out"/>
            </method>
            <method name="Event">
              <arg name="id" type="i" direction="in"/>
              <arg name="eventId" type="s" direction="in"/>
              <arg name="data" type="v" direction="in"/>
              <arg name="timestamp" type="u" direction="in"/>
            </method>
            <signal name="LayoutUpdated">
              <arg name="revision" type="u"/>
              <arg name="parent" type="i"/>
            </signal>
          </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(introspection_xml)
        interface_info = node_info.lookup_interface(DBUS_MENU_INTERFACE)
        if not interface_info:
            raise RuntimeError("Não foi possível registrar interface DBusMenu")
        self._menu_registration_id = self._connection.register_object(
            MENU_OBJECT_PATH,
            interface_info,
            self._handle_menu_method_call,
            None,
            None,
        )

    # ------------------------------------------------------------------
    # DBus call handlers
    # ------------------------------------------------------------------
    def _handle_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        _parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == "Activate":
            GLib.idle_add(self._safe_activate)
            invocation.return_value(None)
        elif method_name == "ContextMenu":
            invocation.return_value(None)

    def _handle_get_property(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
    ) -> GLib.Variant:
        if property_name == "Category":
            return GLib.Variant("s", "ApplicationStatus")
        if property_name == "Id":
            return GLib.Variant("s", self._app_id)
        if property_name == "Title":
            return GLib.Variant("s", self._title)
        if property_name == "Status":
            return GLib.Variant("s", self._status)
        if property_name == "IconName":
            return GLib.Variant("s", self._icon_name)
        if property_name == "Menu":
            return GLib.Variant("o", MENU_OBJECT_PATH)
        return GLib.Variant("s", "")

    def _handle_menu_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        if method_name == "GetLayout":
            layout = self._build_layout()
            invocation.return_value(
                GLib.Variant("(u(ia{sv}av))", (self._menu_revision, layout))
            )
            return

        if method_name == "Event":
            item_id = parameters[0]
            event_id = parameters[1]

            if event_id == "clicked":
                if item_id == self.OPEN_ITEM_ID:
                    GLib.idle_add(self._safe_activate)
                elif item_id == self.QUIT_ITEM_ID:
                    GLib.idle_add(self._safe_quit)
            invocation.return_value(None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> tuple[int, dict[str, GLib.Variant], list[GLib.Variant]]:
        item_open = (
            self.OPEN_ITEM_ID,
            {
                "label": GLib.Variant("s", self._open_label),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            },
            [],
        )

        item_separator = (
            self.SEPARATOR_ITEM_ID,
            {
                "type": GLib.Variant("s", "separator"),
                "visible": GLib.Variant("b", True),
            },
            [],
        )

        item_quit = (
            self.QUIT_ITEM_ID,
            {
                "label": GLib.Variant("s", self._quit_label),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            },
            [],
        )

        root_menu = (
            0,
            {"children-display": GLib.Variant("s", "submenu")},
            [
                GLib.Variant("(ia{sv}av)", item_open),
                GLib.Variant("(ia{sv}av)", item_separator),
                GLib.Variant("(ia{sv}av)", item_quit),
            ],
        )
        return root_menu

    def _safe_activate(self) -> bool:
        try:
            self._on_activate()
        except Exception as exc:  # pragma: no cover
            logger.debug("Falha ao ativar webapp via bandeja: %s", exc)
        return False

    def _safe_quit(self) -> bool:
        try:
            self._on_quit()
        except Exception as exc:  # pragma: no cover
            logger.debug("Falha ao sair via bandeja: %s", exc)
        return False

    def _emit_property_changed(self, name: str, value: GLib.Variant) -> None:
        if not self._connection or not self._available:
            return
        try:
            self._connection.emit_signal(
                None,
                SNI_PATH,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant(
                    "(sa{sv}as)",
                    (SNI_INTERFACE, {name: value}, []),
                ),
            )
        except Exception as exc:
            logger.debug("Falha ao emitir PropertiesChanged: %s", exc)

    def _emit_layout_updated(self) -> None:
        if not self._connection or not self._available:
            return
        try:
            self._connection.emit_signal(
                None,
                MENU_OBJECT_PATH,
                DBUS_MENU_INTERFACE,
                "LayoutUpdated",
                GLib.Variant("(ui)", (self._menu_revision, 0)),
            )
        except Exception as exc:
            logger.debug("Falha ao emitir LayoutUpdated: %s", exc)


__all__ = ["TrayIndicator"]
