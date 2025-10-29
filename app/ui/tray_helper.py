"""Helper process that shows an AppIndicator tray icon."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
from pathlib import Path

import gi

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
except (ValueError, ImportError) as exc:  # pragma: no cover
    print("AppIndicator3 not available:", exc, file=sys.stderr)
    sys.exit(1)

try:
    gi.require_version("Gtk", "3.0")
except ValueError:
    pass

from gi.repository import Gtk


class TrayApplication:
    """Encapsulates the tray indicator logic."""

    def __init__(self, config: dict[str, object]) -> None:
        self.config = config
        self.open_cmd = list(config.get("open_cmd", []))  # type: ignore[arg-type]
        self.quit_cmd = list(config.get("quit_cmd", []))  # type: ignore[arg-type]
        icon_path = config.get("icon_path") or "applications-internet"
        title = str(config.get("title", "WebApp"))

        self.indicator = AppIndicator3.Indicator.new(
            str(config.get("app_id", "webapp")),
            icon_path if icon_path else "applications-internet",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )

        if icon_path and Path(str(icon_path)).exists():
            self.indicator.set_icon_full(str(icon_path), title)
        else:
            self.indicator.set_icon_full("applications-internet", title)

        self.indicator.set_title(title)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()

        self.open_item = Gtk.MenuItem()
        self.open_item.connect("activate", self.on_open)
        menu.append(self.open_item)

        self.quit_item = Gtk.MenuItem()
        self.quit_item.connect("activate", self.on_quit)
        menu.append(self.quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)
        self.refresh_labels()

    def refresh_labels(self) -> None:
        self.open_item.set_label(str(self.config.get("open_label", "Open")))
        self.quit_item.set_label(str(self.config.get("quit_label", "Quit")))

    def on_open(self, *_args) -> None:
        if self.open_cmd:
            try:
                subprocess.Popen(self.open_cmd)
            except Exception as exc:  # pragma: no cover
                print(f"Failed to execute open command: {exc}", file=sys.stderr)

    def on_quit(self, *_args) -> None:
        if self.quit_cmd:
            try:
                subprocess.Popen(self.quit_cmd)
            except Exception as exc:  # pragma: no cover
                print(f"Failed to execute quit command: {exc}", file=sys.stderr)
        Gtk.main_quit()

    def run(self) -> None:
        Gtk.main()

    def stop(self) -> None:
        self.indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
        Gtk.main_quit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Tray helper")
    parser.add_argument("config", help="JSON encoded configuration")
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        if not isinstance(config, dict):
            raise ValueError("config must be a dict")
    except Exception as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 1

    app = TrayApplication(config)

    def _stop(_signum, _frame) -> None:
        app.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
