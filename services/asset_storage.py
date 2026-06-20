from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .menu_model import MenuValidationError

DATA_URL_PATTERN = re.compile(r"^data:(image/[A-Za-z0-9.+-]+);base64,(.*)$", re.DOTALL)
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class AssetStorage:
    """Hash-deduplicated local storage for uploaded menu assets."""

    def __init__(self, data_dir: str | Path, filename: str = "assets.json") -> None:
        self.data_dir = Path(data_dir)
        self.assets_dir = self.data_dir / "assets"
        self.file_path = self.data_dir / filename
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def list_assets(self, menus: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        references = self.reference_map(menus or [])
        with self._lock:
            assets = list(self._read()["assets"].values())
        for asset in assets:
            asset["references"] = references.get(asset["id"], [])
            asset["used"] = bool(asset["references"])
        return sorted(assets, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def save_data_url(self, data_url: str, *, name: str = "") -> dict[str, Any]:
        mime_type, content = self._decode_data_url(data_url)
        digest = hashlib.sha256(content).hexdigest()
        asset_id = digest[:24]
        extension = EXTENSIONS.get(mime_type, ".img")
        path = self.assets_dir / f"{asset_id}{extension}"
        now = _now_iso()
        with self._lock:
            if not path.is_file():
                tmp_path = path.with_suffix(path.suffix + ".tmp")
                tmp_path.write_bytes(content)
                tmp_path.replace(path)
            data = self._read()
            assets = data.setdefault("assets", {})
            existing = assets.get(asset_id) if isinstance(assets.get(asset_id), dict) else {}
            entry = {
                "id": asset_id,
                "sha256": digest,
                "name": str(name or existing.get("name") or f"asset{extension}")[:160],
                "mime_type": mime_type,
                "size": len(content),
                "path": str(path),
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
            assets[asset_id] = entry
            self._write(data)
        return dict(entry)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._read()["assets"].get(str(asset_id or ""))
        return dict(entry) if isinstance(entry, dict) else None

    def data_url_for_asset(self, asset_id: str) -> str:
        asset = self.get_asset(asset_id)
        if not asset:
            raise MenuValidationError(f"asset not found: {asset_id}")
        path = Path(str(asset.get("path") or ""))
        if not path.is_file():
            raise MenuValidationError(f"asset file missing: {asset_id}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{asset.get('mime_type') or 'image/png'};base64,{encoded}"

    def delete_asset(self, asset_id: str, menus: list[dict[str, Any]] | None = None) -> bool:
        references = self.reference_map(menus or [])
        if references.get(asset_id):
            raise MenuValidationError(f"asset is still used by menus: {', '.join(references[asset_id])}")
        with self._lock:
            data = self._read()
            entry = data.get("assets", {}).pop(asset_id, None)
            if not entry:
                return False
            self._write(data)
        path = Path(str(entry.get("path") or ""))
        try:
            if path.is_file() and path.parent == self.assets_dir:
                path.unlink()
        except OSError:
            pass
        return True

    def cleanup_unused(self, menus: list[dict[str, Any]]) -> dict[str, Any]:
        references = self.reference_map(menus)
        removed: list[str] = []
        with self._lock:
            data = self._read()
            for asset_id, entry in list(data.get("assets", {}).items()):
                if references.get(asset_id):
                    continue
                removed.append(asset_id)
                data["assets"].pop(asset_id, None)
                path = Path(str(entry.get("path") or ""))
                try:
                    if path.is_file() and path.parent == self.assets_dir:
                        path.unlink()
                except OSError:
                    pass
            self._write(data)
        return {"removed": removed, "count": len(removed)}

    @staticmethod
    def reference_map(menus: list[dict[str, Any]]) -> dict[str, list[str]]:
        references: dict[str, list[str]] = {}
        for menu in menus:
            style = menu.get("style") if isinstance(menu.get("style"), dict) else {}
            asset_id = str(style.get("background_image_asset_id") or "").strip()
            if asset_id:
                references.setdefault(asset_id, []).append(str(menu.get("id") or ""))
        return references

    def _decode_data_url(self, data_url: str) -> tuple[str, bytes]:
        match = DATA_URL_PATTERN.match(str(data_url or "").strip())
        if not match:
            raise MenuValidationError("asset data_url must be an inline image data URL")
        mime_type = match.group(1).lower()
        if not mime_type.startswith("image/"):
            raise MenuValidationError("asset must be an image")
        try:
            content = base64.b64decode(match.group(2), validate=True)
        except Exception as exc:  # noqa: BLE001
            raise MenuValidationError("asset data_url is not valid base64") from exc
        if not content:
            raise MenuValidationError("asset cannot be empty")
        return mime_type, content

    def _read(self) -> dict[str, Any]:
        if not self.file_path.is_file():
            return {"version": 1, "assets": {}}
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {"version": 1, "assets": {}}
        assets = raw.get("assets") if isinstance(raw, dict) else None
        return {"version": 1, "assets": assets if isinstance(assets, dict) else {}}

    def _write(self, data: dict[str, Any]) -> None:
        payload = {"version": 1, "assets": data.get("assets") if isinstance(data.get("assets"), dict) else {}}
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
