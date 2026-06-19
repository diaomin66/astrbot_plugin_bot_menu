from __future__ import annotations

import hashlib
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MenuRenderCache:
    """File-backed cache for rendered menu images."""

    def __init__(self, data_dir: str | Path, filename: str = "render_cache.json") -> None:
        self.data_dir = Path(data_dir)
        self.file_path = self.data_dir / filename
        self.rendered_dir = self.data_dir / "rendered"
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rendered_dir.mkdir(parents=True, exist_ok=True)

    def fingerprint(self, menu: dict[str, Any], *, render_width: int, render_scale: int) -> str:
        payload = {
            "cache_version": 1,
            "renderer": "browser-cache",
            "render_width": render_width,
            "render_scale": render_scale,
            "menu": menu,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get_cached_path(self, menu: dict[str, Any], *, render_width: int, render_scale: int) -> str | None:
        fingerprint = self.fingerprint(menu, render_width=render_width, render_scale=render_scale)
        with self._lock:
            entry = self._read().get("menus", {}).get(str(menu.get("id") or ""))
        if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
            return None
        path = Path(str(entry.get("path") or ""))
        if path.is_file():
            return str(path)
        return None

    def cache_path_for_menu(self, menu: dict[str, Any]) -> Path:
        safe_id = "".join(ch for ch in str(menu.get("id") or "menu") if ch.isalnum() or ch in ("_", "-")) or "menu"
        return self.rendered_dir / f"{safe_id}-cached.png"

    def store_rendered(
        self,
        menu: dict[str, Any],
        rendered_path: str | Path,
        *,
        render_width: int,
        render_scale: int,
    ) -> str:
        source = Path(rendered_path)
        if not source.is_file():
            raise FileNotFoundError(f"rendered image not found: {source}")
        target = self.cache_path_for_menu(menu)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(".tmp")
        shutil.copyfile(source, tmp_path)
        tmp_path.replace(target)

        entry = {
            "fingerprint": self.fingerprint(menu, render_width=render_width, render_scale=render_scale),
            "path": str(target),
            "rendered_at": _now_iso(),
            "status": "ready",
        }
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            menus[str(menu.get("id") or "")] = entry
            self._write(data)
        return str(target)

    def mark_error(
        self,
        menu: dict[str, Any],
        message: str,
        *,
        render_width: int,
        render_scale: int,
    ) -> None:
        entry = {
            "fingerprint": self.fingerprint(menu, render_width=render_width, render_scale=render_scale),
            "path": str(self.cache_path_for_menu(menu)),
            "rendered_at": _now_iso(),
            "status": "error",
            "error": message[:500],
        }
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            menus[str(menu.get("id") or "")] = entry
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.file_path.is_file():
            return {"version": 1, "menus": {}}
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {"version": 1, "menus": {}}
        if not isinstance(raw, dict) or not isinstance(raw.get("menus"), dict):
            return {"version": 1, "menus": {}}
        return {"version": 1, "menus": raw["menus"]}

    def _write(self, data: dict[str, Any]) -> None:
        payload = {"version": 1, "menus": data.get("menus") if isinstance(data.get("menus"), dict) else {}}
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(self.file_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
