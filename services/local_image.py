from __future__ import annotations

import base64
import hashlib
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any


def render_menu_image(menu: dict[str, Any], output_dir: str | Path, *, default_width: int = 900) -> str:
    """Render a menu to a high-quality local PNG file without relying on AstrBot's remote T2I service."""

    from PIL import Image, ImageDraw

    output_path = _build_output_path(menu, output_dir)
    base_width = _clamp_int(menu.get("style", {}).get("width"), default=default_width, minimum=520, maximum=1400)
    
    # SSAA (Super Sampling Anti-Aliasing) scale factor
    scale = 2
    width = base_width * scale
    style = menu.get("style", {})
    primary = _color(style.get("primary_color"), "#7c3aed")
    bg = _color(style.get("background_color"), "#f8fafc")
    card = _color(style.get("card_color"), "#ffffff")
    text = _color(style.get("text_color"), "#111827")
    muted = _color(style.get("muted_color"), "#6b7280")
    radius = _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48) * scale

    font_regular = _font(20 * scale)
    font_small = _font(17 * scale)
    font_mono = _font(17 * scale)
    font_title = _font(46 * scale, weight="bold")
    font_section = _font(25 * scale, weight="bold")
    font_label = _font(22 * scale, weight="bold")
    font_badge = _font(18 * scale, weight="bold")
    font_icon = _font(28 * scale, emoji=True)

    margin = 28 * scale
    shell_pad = 30 * scale
    inner_width = width - margin * 2
    content_width = inner_width - shell_pad * 2
    item_gap = 12 * scale
    item_width = (content_width - item_gap) // 2

    # Measure dynamic height first, then paint once.
    y = margin + shell_pad + 12 * scale
    y += 38 * scale  # badge
    y += 16 * scale + _text_height(font_title, menu.get("title") or "Bot 功能菜单", content_width, 52 * scale)
    subtitle = str(menu.get("subtitle") or "")
    if subtitle:
        y += 8 * scale + _wrapped_height(subtitle, font_regular, content_width, 27 * scale)
    y += 24 * scale

    section_layouts: list[dict[str, Any]] = []
    for section in menu.get("sections", []):
        rows: list[list[dict[str, Any]]] = []
        current_row: list[dict[str, Any]] = []
        for item in section.get("items", []):
            current_row.append(item)
            if len(current_row) == 2:
                rows.append(current_row)
                current_row = []
        if current_row:
            rows.append(current_row)

        row_heights = []
        for row in rows:
            row_heights.append(max(_item_height(item, item_width, font_mono, font_small, scale) for item in row))
        section_height = 22 * scale + 30 * scale + 16 * scale + sum(row_heights) + item_gap * max(0, len(row_heights) - 1) + 22 * scale
        section_layouts.append({"section": section, "rows": rows, "row_heights": row_heights, "height": int(section_height)})
        y += section_height + 18 * scale

    footer_text = str(menu.get("footer") or "")
    y += 26 * scale if footer_text or style.get("show_updated_at", True) else 0
    height = int(y + margin + shell_pad)

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    _draw_soft_background(draw, width, height, primary, bg, scale)
    shell = (margin, margin, width - margin, height - margin)
    
    # Soft shadow
    _draw_shadow(image, shell, radius, blur=12 * scale, offset_y=8 * scale, color=_mix(muted, bg, 0.4))
    
    draw.rounded_rectangle(shell, radius=radius, fill=(255, 255, 255), outline=_mix(muted, (255, 255, 255), 0.72), width=1 * scale)
    draw.rounded_rectangle((margin, margin, width - margin, margin + 8 * scale + radius), radius=radius, fill=primary)
    draw.rectangle((margin, margin + 8 * scale, width - margin, margin + 8 * scale + radius), fill=(255, 255, 255))

    x = margin + shell_pad
    y = margin + shell_pad + 12 * scale
    badge_text = f"📋 {menu.get('name') or menu.get('id') or '菜单'}"
    badge_w = min(content_width, _text_width(font_badge, badge_text) + 26 * scale)
    draw.rounded_rectangle((x, y, x + badge_w, y + 38 * scale), radius=19 * scale, fill=_mix(primary, (255, 255, 255), 0.88))
    draw.text((x + 13 * scale, y + 8 * scale), badge_text, font=font_badge, fill=primary)
    y += 54 * scale

    y = _draw_wrapped(draw, menu.get("title") or "Bot 功能菜单", (x, y), font_title, text, content_width, 52 * scale)
    if subtitle:
        y += 8 * scale
        y = _draw_wrapped(draw, subtitle, (x, y), font_regular, muted, content_width, 29 * scale)
    y += 24 * scale

    for layout in section_layouts:
        section = layout["section"]
        top = y
        bottom = y + layout["height"]
        draw.rounded_rectangle((x, top, x + content_width, bottom), radius=radius, fill=card, outline=_mix(muted, (255, 255, 255), 0.75))
        draw.rounded_rectangle((x + 22 * scale, y + 22 * scale, x + 32 * scale, y + 50 * scale), radius=5 * scale, fill=primary)
        draw.text((x + 44 * scale, y + 20 * scale), str(section.get("title") or "分组"), font=font_section, fill=text)
        y += 68 * scale
        for row, row_height in zip(layout["rows"], layout["row_heights"], strict=False):
            item_x = x + 22 * scale
            for item in row:
                _draw_item(draw, item, item_x, y, item_width, row_height, radius, primary, text, muted, font_icon, font_label, font_mono, font_small, scale)
                item_x += item_width + item_gap
            y += row_height + item_gap
        y = bottom + 18 * scale

    if footer_text or style.get("show_updated_at", True):
        footer_y = height - margin - shell_pad - 6 * scale
        draw.text((x, footer_y), footer_text, font=font_small, fill=muted)
        if style.get("show_updated_at", True):
            updated = _format_time(menu.get("updated_at"))
            right = f"更新：{updated}"
            draw.text((x + content_width - _text_width(font_small, right), footer_y), right, font=font_small, fill=muted)

    if scale > 1:
        image = image.resize((base_width, int(height / scale)), Image.Resampling.LANCZOS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return str(output_path)


def image_file_to_data_url(path: str | Path) -> str:
    """Convert a rendered local image file into a browser-displayable data URL."""

    image_path = Path(path)
    raw = image_path.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def _draw_item(draw, item, x, y, width, height, radius, primary, text, muted, font_icon, font_label, font_mono, font_small, scale) -> None:
    enabled = item.get("enabled", True)
    fill = (246, 248, 252) if enabled else (238, 240, 244)
    fg = text if enabled else _mix(text, (255, 255, 255), 0.45)
    sub = muted if enabled else _mix(muted, (255, 255, 255), 0.5)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=max(14 * scale, radius - 8 * scale), fill=fill, outline=_mix(muted, (255, 255, 255), 0.82))
    draw.rounded_rectangle((x + 14 * scale, y + 14 * scale, x + 58 * scale, y + 58 * scale), radius=14 * scale, fill=_mix(primary, (255, 255, 255), 0.88))
    draw.text((x + 22 * scale, y + 21 * scale), str(item.get("icon") or "•")[:2], font=font_icon, fill=primary)
    text_x = x + 70 * scale
    line_y = y + 14 * scale
    label = str(item.get("label") or "未命名")
    draw.text((text_x, line_y), label, font=font_label, fill=fg)
    command = str(item.get("command") or "")
    if command:
        command_y = line_y + 28 * scale
        command_lines = _wrap(command, font_mono, width - 84 * scale, max_lines=2)
        for line in command_lines:
            draw.text((text_x, command_y), line, font=font_mono, fill=primary if enabled else sub)
            command_y += 22 * scale
        line_y = command_y + 2 * scale
    else:
        line_y += 32 * scale
    desc = str(item.get("description") or "")
    for line in _wrap(desc, font_small, width - 84 * scale, max_lines=3):
        draw.text((text_x, line_y), line, font=font_small, fill=sub)
        line_y += 22 * scale


def _item_height(item, width, font_mono, font_small, scale) -> int:
    desc_lines = len(_wrap(str(item.get("description") or ""), font_small, width - 84 * scale, max_lines=3))
    command_lines = len(_wrap(str(item.get("command") or ""), font_mono, width - 84 * scale, max_lines=2))
    return max(88 * scale, 28 * scale + 28 * scale + command_lines * 22 * scale + desc_lines * 22 * scale)


def _draw_shadow(image, box, radius, blur, offset_y, color):
    from PIL import Image, ImageDraw, ImageFilter
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = box
    shadow_draw.rounded_rectangle((x0, y0 + offset_y, x1, y1 + offset_y), radius=radius, fill=color)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    image.paste(shadow, (0, 0), shadow)


def _draw_soft_background(draw, width, height, primary, bg, scale) -> None:
    for i in range(0, 260 * scale, 8 * scale):
        ratio = i / (260 * scale)
        color = _mix(primary, bg, 0.65 + ratio * 0.35)
        draw.ellipse((-120 * scale - i // 3, -140 * scale - i // 3, 280 * scale + i, 260 * scale + i), outline=color, width=8 * scale)


def _draw_wrapped(draw, text: str, pos: tuple[int, int], font, fill, width: int, line_height: int) -> int:
    x, y = pos
    for line in _wrap(text, font, width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _wrapped_height(text: str, font, width: int, line_height: int) -> int:
    return len(_wrap(text, font, width)) * line_height


def _text_height(font, text: str, width: int, line_height: int) -> int:
    return len(_wrap(text, font, width)) * line_height


def _wrap(text: str, font, max_width: int, *, max_lines: int | None = None) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if current and _text_width(font, candidate) > max_width:
                lines.append(current)
                current = ch
                if max_lines and len(lines) >= max_lines:
                    return _ellipsize(lines, font, max_width)
            else:
                current = candidate
        if current:
            lines.append(current)
            if max_lines and len(lines) >= max_lines:
                return _ellipsize(lines, font, max_width)
    return lines or textwrap.wrap(text, width=20)


def _ellipsize(lines: list[str], font, max_width: int) -> list[str]:
    if not lines:
        return lines
    last = lines[-1]
    while last and _text_width(font, f"{last}…") > max_width:
        last = last[:-1]
    lines[-1] = f"{last}…" if last else "…"
    return lines


def _font(size: int, *, emoji: bool = False, weight: str = "normal"):
    from PIL import ImageFont

    candidates = []
    if emoji:
        candidates.extend([r"C:\Windows\Fonts\seguiemj.ttf", r"C:\Windows\Fonts\msyh.ttc"])
    else:
        if weight == "bold":
            candidates.extend([r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"])
        else:
            candidates.extend([r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"])
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def _text_width(font, text: str) -> int:
    try:
        return int(font.getlength(text))
    except Exception:
        return len(text) * 12


def _color(value: Any, fallback: str) -> tuple[int, int, int]:
    raw = str(value or fallback).strip()
    if raw.startswith("#") and len(raw) == 7:
        try:
            return tuple(int(raw[i : i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return _color(fallback, "#000000") if raw != fallback else (0, 0, 0)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], b_ratio: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - b_ratio) + b[i] * b_ratio) for i in range(3))


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _format_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    return value.replace("T", " ").replace("+00:00", " UTC")[:19]


def _build_output_path(menu: dict[str, Any], output_dir: str | Path) -> Path:
    raw = json.dumps(menu, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    safe_id = "".join(ch for ch in str(menu.get("id") or "menu") if ch.isalnum() or ch in ("_", "-")) or "menu"
    return Path(output_dir) / "rendered" / f"{safe_id}-{digest}.png"
