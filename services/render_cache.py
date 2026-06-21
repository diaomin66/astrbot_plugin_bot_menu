from __future__ import annotations

import hashlib
import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fonts import FontRegistry


class MenuRenderCache:
    """File-backed cache for rendered menu images."""

    CACHE_VERSION = 5

    def __init__(self, data_dir: str | Path, filename: str = "render_cache.json") -> None:
        self.data_dir = Path(data_dir)
        self.file_path = self.data_dir / filename
        self.rendered_dir = self.data_dir / "rendered"
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rendered_dir.mkdir(parents=True, exist_ok=True)

    def fingerprint(
        self,
        menu: dict[str, Any],
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
    ) -> str:
        style = menu.get("style") if isinstance(menu.get("style"), dict) else {}
        payload = {
            "cache_version": self.CACHE_VERSION,
            "renderer": str(render_engine or "typst"),
            "render_width": render_width,
            "render_scale": render_scale,
            "font_signature": FontRegistry(self.data_dir).signature_for(style.get("font_family")),
            "menu": menu,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get_cached_path(
        self,
        menu: dict[str, Any],
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
    ) -> str | None:
        fingerprint = self.fingerprint(
            menu,
            render_width=render_width,
            render_scale=render_scale,
            render_engine=render_engine,
        )
        with self._lock:
            entry = self._read().get("menus", {}).get(str(menu.get("id") or ""))
        if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
            return None
        path = Path(str(entry.get("path") or ""))
        if path.is_file():
            return str(path)
        return None

    def get_status(
        self,
        menu: dict[str, Any],
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
        is_rendering: bool = False,
    ) -> dict[str, Any]:
        """Return the render cache status for the current menu fingerprint."""

        fingerprint = self.fingerprint(
            menu,
            render_width=render_width,
            render_scale=render_scale,
            render_engine=render_engine,
        )
        if is_rendering:
            with self._lock:
                entry = self._read().get("menus", {}).get(str(menu.get("id") or ""))
            attempts = entry.get("attempts", 0) if isinstance(entry, dict) else 0
            queued_at = entry.get("queued_at") if isinstance(entry, dict) else None
            return {
                "status": "rendering",
                "rendered_at": None,
                "error": None,
                "queued_at": queued_at,
                "attempts": attempts,
                "fingerprint": fingerprint,
                "cache_size": None,
            }

        with self._lock:
            entry = self._read().get("menus", {}).get(str(menu.get("id") or ""))
        if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
            return self._missing_status(fingerprint)

        status = str(entry.get("status") or "missing")
        if status == "ready":
            path = Path(str(entry.get("path") or ""))
            if path.is_file():
                return {
                    "status": "ready",
                    "rendered_at": entry.get("rendered_at") or None,
                    "error": None,
                    "queued_at": entry.get("queued_at") or None,
                    "attempts": entry.get("attempts", 0),
                    "fingerprint": fingerprint,
                    "cache_size": path.stat().st_size,
                }
            return self._missing_status(fingerprint)
        if status == "rendering":
            return {
                "status": "rendering",
                "rendered_at": None,
                "error": None,
                "queued_at": entry.get("queued_at") or None,
                "attempts": entry.get("attempts", 0),
                "fingerprint": fingerprint,
                "cache_size": None,
            }
        if status == "error":
            return {
                "status": "error",
                "rendered_at": entry.get("rendered_at") or None,
                "error": entry.get("error") or None,
                "queued_at": entry.get("queued_at") or None,
                "attempts": entry.get("attempts", 0),
                "fingerprint": fingerprint,
                "cache_size": None,
            }
        return self._missing_status(fingerprint)

    def cache_path_for_menu(self, menu: dict[str, Any], *, fingerprint: str = "") -> Path:
        safe_id = "".join(ch for ch in str(menu.get("id") or "menu") if ch.isalnum() or ch in ("_", "-")) or "menu"
        suffix = f"-{fingerprint[:16]}" if fingerprint else ""
        return self.rendered_dir / f"{safe_id}-cached{suffix}.png"

    def store_rendered(
        self,
        menu: dict[str, Any],
        rendered_path: str | Path,
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
    ) -> str:
        source = Path(rendered_path)
        if not source.is_file():
            raise FileNotFoundError(f"rendered image not found: {source}")
        fingerprint = self.fingerprint(
            menu,
            render_width=render_width,
            render_scale=render_scale,
            render_engine=render_engine,
        )
        target = self.cache_path_for_menu(menu, fingerprint=fingerprint)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(".tmp")
        shutil.copyfile(source, tmp_path)
        tmp_path.replace(target)

        entry = {
            "fingerprint": fingerprint,
            "path": str(target),
            "rendered_at": _now_iso(),
            "status": "ready",
            "cache_size": target.stat().st_size,
        }
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            previous = menus.get(str(menu.get("id") or ""))
            if isinstance(previous, dict):
                entry["queued_at"] = previous.get("queued_at")
                entry["attempts"] = previous.get("attempts", 0)
                previous_path = Path(str(previous.get("path") or ""))
                if previous_path != target:
                    self._unlink_rendered_path(previous_path)
            menus[str(menu.get("id") or "")] = entry
            self._write(data)
        return str(target)

    def mark_rendering(
        self,
        menu: dict[str, Any],
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
    ) -> None:
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            previous = menus.get(str(menu.get("id") or ""))
            previous_attempts = previous.get("attempts", 0) if isinstance(previous, dict) else 0
            fingerprint = self.fingerprint(
                menu,
                render_width=render_width,
                render_scale=render_scale,
                render_engine=render_engine,
            )
            entry = {
                "fingerprint": fingerprint,
                "path": str(self.cache_path_for_menu(menu, fingerprint=fingerprint)),
                "rendered_at": None,
                "queued_at": _now_iso(),
                "attempts": previous_attempts + 1,
                "status": "rendering",
            }
            menus[str(menu.get("id") or "")] = entry
            self._write(data)

    def mark_error(
        self,
        menu: dict[str, Any],
        message: str,
        *,
        render_width: int,
        render_scale: int,
        render_engine: str = "typst",
    ) -> None:
        fingerprint = self.fingerprint(
            menu,
            render_width=render_width,
            render_scale=render_scale,
            render_engine=render_engine,
        )
        entry = {
            "fingerprint": fingerprint,
            "path": str(self.cache_path_for_menu(menu, fingerprint=fingerprint)),
            "rendered_at": _now_iso(),
            "queued_at": None,
            "attempts": 1,
            "status": "error",
            "error": message[:500],
        }
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            previous = menus.get(str(menu.get("id") or ""))
            if isinstance(previous, dict):
                entry["queued_at"] = previous.get("queued_at")
                entry["attempts"] = previous.get("attempts", 0)
            menus[str(menu.get("id") or "")] = entry
            self._write(data)

    def _unlink_rendered_path(self, path: Path) -> None:
        try:
            if path.is_file() and path.parent.resolve() == self.rendered_dir.resolve():
                path.unlink()
        except OSError:
            pass

    def cleanup(self, active_menu_ids: set[str], *, max_total_bytes: int | None = None) -> dict[str, Any]:
        removed: list[str] = []
        with self._lock:
            data = self._read()
            menus = data.setdefault("menus", {})
            for menu_id, entry in list(menus.items()):
                if menu_id in active_menu_ids:
                    continue
                removed.append(menu_id)
                menus.pop(menu_id, None)
                path = Path(str(entry.get("path") or "")) if isinstance(entry, dict) else None
                try:
                    if path and path.is_file() and path.parent == self.rendered_dir:
                        path.unlink()
                except OSError:
                    pass
            if max_total_bytes is not None:
                ready_entries = [
                    (menu_id, entry)
                    for menu_id, entry in menus.items()
                    if isinstance(entry, dict) and Path(str(entry.get("path") or "")).is_file()
                ]
                total = sum(Path(str(entry.get("path"))).stat().st_size for _, entry in ready_entries)
                for menu_id, entry in sorted(ready_entries, key=lambda pair: str(pair[1].get("rendered_at") or "")):
                    if total <= max_total_bytes:
                        break
                    path = Path(str(entry.get("path") or ""))
                    size = path.stat().st_size
                    try:
                        path.unlink()
                    except OSError:
                        pass
                    menus.pop(menu_id, None)
                    removed.append(menu_id)
                    total -= size
            self._write(data)
        return {"removed": removed, "count": len(removed)}

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

    def _missing_status(self, fingerprint: str) -> dict[str, Any]:
        return {
            "status": "missing",
            "rendered_at": None,
            "error": None,
            "queued_at": None,
            "attempts": 0,
            "fingerprint": fingerprint,
            "cache_size": None,
        }

    def _write(self, data: dict[str, Any]) -> None:
        payload = {"version": 1, "menus": data.get("menus") if isinstance(data.get("menus"), dict) else {}}
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(self.file_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
