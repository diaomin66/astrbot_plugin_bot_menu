from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .menu_model import MenuValidationError, normalize_menu


class MenuHistoryStorage:
    """Rolling menu snapshots for safer saves and one-click restore."""

    def __init__(self, data_dir: str | Path, filename: str = "history.json", max_snapshots_per_menu: int = 20) -> None:
        self.data_dir = Path(data_dir)
        self.file_path = self.data_dir / filename
        self.max_snapshots_per_menu = max(1, max_snapshots_per_menu)
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, menu: dict[str, Any] | None, *, reason: str = "save") -> dict[str, Any] | None:
        if not menu:
            return None
        normalized = normalize_menu(menu)
        menu_id = normalized["id"]
        entry = {
            "id": _snapshot_id(menu_id),
            "menu_id": menu_id,
            "reason": str(reason or "save")[:40],
            "created_at": _now_iso(),
            "menu": copy.deepcopy(normalized),
        }
        with self._lock:
            data = self._read()
            snapshots = data.setdefault("menus", {}).setdefault(menu_id, [])
            snapshots.insert(0, entry)
            del snapshots[self.max_snapshots_per_menu :]
            self._write(data)
        return copy.deepcopy(entry)

    def list_history(self, menu_id: str) -> list[dict[str, Any]]:
        with self._lock:
            snapshots = self._read().get("menus", {}).get(menu_id, [])
        return [copy.deepcopy(snapshot) for snapshot in snapshots if isinstance(snapshot, dict)]

    def restore_snapshot(self, menu_id: str, snapshot_id: str | None = None) -> dict[str, Any]:
        snapshots = self.list_history(menu_id)
        if not snapshots:
            raise MenuValidationError(f"history not found: {menu_id}")
        if snapshot_id:
            for snapshot in snapshots:
                if snapshot.get("id") == snapshot_id:
                    return normalize_menu(snapshot.get("menu"))
            raise MenuValidationError(f"snapshot not found: {snapshot_id}")
        return normalize_menu(snapshots[0].get("menu"))

    def _read(self) -> dict[str, Any]:
        if not self.file_path.is_file():
            return {"version": 1, "menus": {}}
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {"version": 1, "menus": {}}
        menus = raw.get("menus") if isinstance(raw, dict) else None
        return {"version": 1, "menus": menus if isinstance(menus, dict) else {}}

    def _write(self, data: dict[str, Any]) -> None:
        payload = {"version": 1, "menus": data.get("menus") if isinstance(data.get("menus"), dict) else {}}
        self._rotate_backup()
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(self.file_path)

    def _rotate_backup(self) -> None:
        if not self.file_path.is_file():
            return
        try:
            self.file_path.with_suffix(".bak.json").write_bytes(self.file_path.read_bytes())
        except OSError:
            pass


def _snapshot_id(menu_id: str) -> str:
    return f"{menu_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
