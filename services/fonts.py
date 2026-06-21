from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_FONTS_DIRNAME = "fonts"
SUPPORTED_FONT_EXTENSIONS = {".otf", ".ttc", ".ttf", ".woff", ".woff2"}
DEFAULT_FONT_STACK = ("Inter", "PingFang SC", "Microsoft YaHei", "sans-serif")
DEFAULT_MONO_FONT_STACK = ("Consolas", "JetBrains Mono", "monospace")

_FONT_MIME_TYPES = {
    ".otf": "font/otf",
    ".ttc": "font/collection",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


@dataclass(frozen=True)
class UserFont:
    family: str
    name: str
    relative_path: str
    suffix: str
    path: Path
    fingerprint: str

    def as_dict(self) -> dict[str, str]:
        return {
            "family": self.family,
            "name": self.name,
            "relative_path": self.relative_path,
            "suffix": self.suffix,
            "fingerprint": self.fingerprint,
        }


class FontRegistry:
    """Finds user-provided fonts from the plugin data directory.

    The registry never stores environment-specific absolute paths in menu data.
    Users select fonts by display name, generated family, or path relative to
    the plugin's ``fonts`` directory.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.fonts_dir = self.data_dir / USER_FONTS_DIRNAME
        self.fonts_dir.mkdir(parents=True, exist_ok=True)

    def list_fonts(self) -> list[UserFont]:
        fonts: list[UserFont] = []
        if not self.fonts_dir.is_dir():
            return fonts
        for path in sorted(self.fonts_dir.rglob("*"), key=lambda item: _relative_font_path(self.fonts_dir, item).casefold()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_FONT_EXTENSIONS:
                continue
            relative_path = _relative_font_path(self.fonts_dir, path)
            fingerprint = _font_file_fingerprint(path, relative_path)
            family = f"BotMenuUserFont-{fingerprint[:12]}"
            fonts.append(
                UserFont(
                    family=family,
                    name=path.stem,
                    relative_path=relative_path,
                    suffix=path.suffix.lower().lstrip("."),
                    path=path,
                    fingerprint=fingerprint,
                )
            )
        return fonts

    def resolve(self, value: Any) -> UserFont | None:
        raw = str(value or "").strip().strip("\"'")
        if not raw:
            return None
        raw_folded = _normal_font_key(raw)
        for font in self.list_fonts():
            values = {
                font.family,
                font.name,
                font.relative_path,
                Path(font.relative_path).as_posix(),
                Path(font.relative_path).stem,
            }
            if raw_folded in {_normal_font_key(value) for value in values}:
                return font
        return None

    def css_for(self, value: Any) -> str:
        font = self.resolve(value)
        if not font:
            return ""
        mime = _FONT_MIME_TYPES.get(font.path.suffix.lower(), "application/octet-stream")
        data = base64.b64encode(font.path.read_bytes()).decode("ascii")
        return (
            "@font-face{"
            f"font-family:{css_string(font.family)};"
            f"src:url(data:{mime};base64,{data}) format('{_css_font_format(font.path.suffix)}');"
            "font-display:swap;"
            "}"
        )

    def css_for_all(self) -> str:
        blocks: list[str] = []
        for font in self.list_fonts():
            blocks.append(self.css_for(font.family))
        return "\n".join(block for block in blocks if block)

    def css_font_family(self, value: Any) -> str:
        font = self.resolve(value)
        raw = str(value or "").strip().strip("\"'")
        if font:
            return font_stack_css((font.family, *DEFAULT_FONT_STACK))
        if raw:
            return font_stack_css((raw, *DEFAULT_FONT_STACK))
        return font_stack_css(DEFAULT_FONT_STACK)

    def signature_for(self, value: Any) -> str:
        font = self.resolve(value)
        return font.fingerprint if font else ""


def font_stack_css(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(_css_font_token(value) for value in values if str(value or "").strip())


def css_string(value: Any) -> str:
    return '"' + str(value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def default_font_stack_css() -> str:
    return font_stack_css(DEFAULT_FONT_STACK)


def default_mono_font_stack_css() -> str:
    return font_stack_css(DEFAULT_MONO_FONT_STACK)


def _css_font_token(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}:
        return raw
    return css_string(raw)


def _css_font_format(suffix: str) -> str:
    normalized = suffix.lower().lstrip(".")
    return "truetype" if normalized == "ttf" else normalized


def _font_file_fingerprint(path: Path, relative_path: str) -> str:
    stat = path.stat()
    payload = f"{relative_path}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _relative_font_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _normal_font_key(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()
