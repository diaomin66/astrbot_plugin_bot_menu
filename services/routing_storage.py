from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class RoutingStorage:
    """Context default menu routing rules backed by routing.json."""

    def __init__(self, data_dir: str | Path, filename: str = "routing.json") -> None:
        self.data_dir = Path(data_dir)
        self.file_path = self.data_dir / filename
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_rules(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def save_rules(self, raw_rules: dict[str, Any]) -> dict[str, Any]:
        rules = normalize_routing(raw_rules)
        with self._lock:
            self._write(rules)
        return rules

    def resolve_default(self, *, platform: str = "", group_id: str = "", global_default: str = "") -> str:
        rules = self.get_rules()
        contexts = rules.get("contexts", {}) if isinstance(rules.get("contexts"), dict) else {}
        platform_key = str(platform or "").strip()
        group_key = str(group_id or "").strip()
        if group_key:
            scoped = f"{platform_key}:{group_key}" if platform_key else group_key
            if contexts.get(scoped):
                return str(contexts[scoped])
            if contexts.get(group_key):
                return str(contexts[group_key])
        platforms = rules.get("platforms", {}) if isinstance(rules.get("platforms"), dict) else {}
        if platform_key and platforms.get(platform_key):
            return str(platforms[platform_key])
        return str(rules.get("global_default") or global_default or "")

    def _read(self) -> dict[str, Any]:
        if not self.file_path.is_file():
            return {"version": 1, "global_default": "", "platforms": {}, "contexts": {}}
        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {"version": 1, "global_default": "", "platforms": {}, "contexts": {}}
        return normalize_routing(raw if isinstance(raw, dict) else {})

    def _write(self, rules: dict[str, Any]) -> None:
        self._rotate_backup()
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(self.file_path)

    def _rotate_backup(self) -> None:
        if not self.file_path.is_file():
            return
        try:
            self.file_path.with_suffix(".bak.json").write_bytes(self.file_path.read_bytes())
        except OSError:
            pass


def normalize_routing(raw_rules: dict[str, Any]) -> dict[str, Any]:
    def clean_mapping(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        cleaned: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key or "").strip()[:120]
            menu_id = str(raw_value or "").strip()[:48]
            if key and menu_id:
                cleaned[key] = menu_id
        return cleaned

    return {
        "version": 1,
        "global_default": str(raw_rules.get("global_default") or "").strip()[:48],
        "platforms": clean_mapping(raw_rules.get("platforms")),
        "contexts": clean_mapping(raw_rules.get("contexts")),
    }
