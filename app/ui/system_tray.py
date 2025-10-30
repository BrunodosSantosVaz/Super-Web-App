"""Manage external tray helper process for webapps."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

HELPER_MODULE = "app.ui.tray_helper"
APP_INDICATOR_AVAILABLE = True  # Helper validates availability


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class TrayManager:
    """Controls the external tray helper lifetime."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen[str]] = None
        self._config: Optional[Dict[str, Any]] = None
        self._available = APP_INDICATOR_AVAILABLE

    def ensure_icon(
        self,
        app_id: str,
        title: str,
        icon_path: Optional[str],
        open_label: str,
        quit_label: str,
        open_cmd: List[str],
        quit_cmd: List[str],
        *,
        force: bool = False,
    ) -> None:
        if not self._available:
            return

        config: Dict[str, Any] = {
            "app_id": app_id,
            "title": title,
            "icon_path": icon_path,
            "open_label": open_label,
            "quit_label": quit_label,
            "open_cmd": open_cmd,
            "quit_cmd": quit_cmd,
        }

        if (not force) and self._config == config and self._process and self._process.poll() is None:
            return

        self._spawn(config)

    def refresh_labels(self, open_label: str, quit_label: str) -> None:
        if not self._config or not self._available:
            return
        self._config["open_label"] = open_label
        self._config["quit_label"] = quit_label
        self._spawn(self._config)

    def update_icon(self, icon_path: Optional[str]) -> None:
        if not self._config or not self._available:
            return
        self._config["icon_path"] = icon_path
        self._spawn(self._config)

    def destroy(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
        self._process = None
        self._config = None

    def _spawn(self, config: Dict[str, Any]) -> None:
        self.destroy()

        helper_args = json.dumps(config)
        cmd = [sys.executable, "-m", HELPER_MODULE, helper_args]
        env = os.environ.copy()
        project_path = str(_project_root())
        existing = env.get("PYTHONPATH")
        if existing:
            env["PYTHONPATH"] = project_path + os.pathsep + existing
        else:
            env["PYTHONPATH"] = project_path

        try:
            self._process = subprocess.Popen(cmd, env=env, text=True)
            self._config = dict(config)
            self._available = True
            logger.debug("Processo de bandeja iniciado")
        except FileNotFoundError:
            logger.warning(
                "AppIndicator não disponível. Instale libayatana-appindicator-gtk3 para habilitar a bandeja."
            )
            self._available = False
        except Exception as exc:
            logger.error("Falha ao iniciar helper da bandeja: %s", exc)
            self._available = False


__all__ = ["TrayManager", "APP_INDICATOR_AVAILABLE"]
