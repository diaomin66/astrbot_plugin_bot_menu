from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .menu_model import (
    DEFAULT_MENU_ID,
    MenuValidationError,
    default_menu,
    normalize_menu_collection,
    touch_menu,
)


class MenuStorage:
    """JSON-backed storage for menu schemes."""

    def __init__(self, data_dir: str | Path, filename: str = "menus.json") -> None:
        self.data_dir = Path(data_dir)
        self.file_path = self.data_dir / filename
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def list_menus(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._read()["menus"])

    def get_menu(self, menu_id: str) -> dict[str, Any] | None:
        with self._lock:
            for menu in self._read()["menus"]:
                if menu["id"] == menu_id:
                    return menu
        return None

    def first_menu_id(self) -> str:
        with self._lock:
            menus = self._read()["menus"]
            return menus[0]["id"] if menus else DEFAULT_MENU_ID

    def save_menu(self, raw_menu: dict[str, Any]) -> dict[str, Any]:
        menu = touch_menu(raw_menu)
        with self._lock:
            data = self._read()
            replaced = False
            for index, existing in enumerate(data["menus"]):
                if existing["id"] == menu["id"]:
                    menu["created_at"] = existing.get("created_at") or menu["created_at"]
                    data["menus"][index] = menu
                    replaced = True
                    break
            if not replaced:
                data["menus"].append(menu)
            self._write(data)
        return menu

    def delete_menu(self, menu_id: str) -> None:
        with self._lock:
            data = self._read()
            menus = [menu for menu in data["menus"] if menu["id"] != menu_id]
            if len(menus) == len(data["menus"]):
                raise MenuValidationError(f"menu not found: {menu_id}")
            if not menus:
                raise MenuValidationError("cannot delete the last menu")
            data["menus"] = menus
            self._write(data)

    def import_menus(self, raw_menus: Any, *, mode: str = "merge") -> list[dict[str, Any]]:
        incoming = normalize_menu_collection(raw_menus)
        mode = mode if mode in {"merge", "replace"} else "merge"
        with self._lock:
            if mode == "replace":
                data = {"version": 1, "menus": incoming}
            else:
                data = self._read()
                by_id = {menu["id"]: menu for menu in data["menus"]}
                for menu in incoming:
                    by_id[menu["id"]] = menu
                data["menus"] = list(by_id.values())
            self._write(data)
            return list(data["menus"])

    def export_data(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def _ensure_file(self) -> None:
        if self.file_path.exists():
            try:
                data = self._read()
                if data["menus"]:
                    return
            except Exception:
                backup = self.file_path.with_suffix(".invalid.json")
                self.file_path.replace(backup)
        self._write({"version": 1, "menus": [default_menu()]})

    def _read(self) -> dict[str, Any]:
        with self.file_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        raw_menus = raw.get("menus") if isinstance(raw, dict) else None
        menus = normalize_menu_collection(raw_menus)
        return {"version": 1, "menus": menus}

    def _write(self, data: dict[str, Any]) -> None:
        menus = normalize_menu_collection(data.get("menus"))
        payload = {"version": 1, "menus": menus}
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(self.file_path)
