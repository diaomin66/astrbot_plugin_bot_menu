from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any


def render_menu_image(
    menu: dict[str, Any],
    output_dir: str | Path,
    *,
    default_width: int = 900,
    output_scale: int = 2,
) -> str:
    """Render a menu to a high-quality local PNG file without relying on AstrBot's remote T2I service."""

    from PIL import Image, ImageDraw

    output_path = _build_output_path(menu, output_dir)
    try:
        from .renderer import preview_width_for_menu

        base_width = preview_width_for_menu(menu, default_width=default_width)
    except Exception:
        base_width = _clamp_int(menu.get("style", {}).get("width"), default=default_width, minimum=520, maximum=1400)
    output_scale = _clamp_int(output_scale, default=2, minimum=1, maximum=4)

    # SSAA (Super Sampling Anti-Aliasing) scale factor
    scale = max(2, output_scale)
    width = base_width * scale
    style = menu.get("style", {})
    primary = _color(style.get("primary_color"), "#7c3aed")
    bg = _color(style.get("background_color"), "#f8fafc")
    card = _color(style.get("card_color"), "#ffffff")
    text = _color(style.get("text_color"), "#111827")
    muted = _color(style.get("muted_color"), "#6b7280")
    radius = _clamp_int(style.get("radius"), default=24, minimum=0, maximum=48) * scale
    foreground_opacity = _clamp_int(style.get("foreground_opacity"), default=92, minimum=0, maximum=100) / 100
    columns = _clamp_int(style.get("columns"), default=2, minimum=1, maximum=4)

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
    item_area_width = content_width - 44 * scale
    item_width = (item_area_width - item_gap * max(0, columns - 1)) // columns

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
        rows = _layout_item_rows(section.get("items", []), columns)

        row_heights = []
        for row in rows:
            row_width = _row_item_width(row, item_area_width, item_gap, columns)
            row_heights.append(max(_item_height(item, row_width, font_mono, font_small, scale) for item in row))
        section_height = 22 * scale + 30 * scale + 16 * scale + sum(row_heights) + item_gap * max(0, len(row_heights) - 1) + 22 * scale
        section_layouts.append({"section": section, "rows": rows, "row_heights": row_heights, "height": int(section_height)})
        y += section_height + 18 * scale

    footer_text = str(menu.get("footer") or "")
    y += 26 * scale if footer_text or style.get("show_updated_at", True) else 0
    height = int(y + margin + shell_pad)

    image = Image.new("RGBA", (width, height), (*bg, 255))
    _paste_custom_background(image, style, width, height, scale)
    draw = ImageDraw.Draw(image)
    if not style.get("background_image"):
        _draw_soft_background(draw, width, height, primary, bg, scale)
    shell = (margin, margin, width - margin, height - margin)
    
    # Soft shadow
    _draw_shadow(image, shell, radius, blur=12 * scale, offset_y=8 * scale, color=_mix(muted, bg, 0.4))
    
    _draw_translucent_rounded_rectangle(
        image,
        shell,
        radius=radius,
        fill=(255, 255, 255),
        opacity=foreground_opacity,
        outline=_mix(muted, (255, 255, 255), 0.72),
        width=1 * scale,
    )
    _draw_translucent_rectangle(
        image,
        (margin, margin, width - margin, margin + 8 * scale),
        fill=primary,
        opacity=foreground_opacity,
    )

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
        _draw_translucent_rounded_rectangle(
            image,
            (x, top, x + content_width, bottom),
            radius=radius,
            fill=card,
            opacity=foreground_opacity,
            outline=_mix(muted, (255, 255, 255), 0.75),
        )
        draw.rounded_rectangle((x + 22 * scale, y + 22 * scale, x + 32 * scale, y + 50 * scale), radius=5 * scale, fill=primary)
        draw.text((x + 44 * scale, y + 20 * scale), str(section.get("title") or "分组"), font=font_section, fill=text)
        y += 68 * scale
        for row, row_height in zip(layout["rows"], layout["row_heights"], strict=False):
            item_x = x + 22 * scale
            row_width = _row_item_width(row, item_area_width, item_gap, columns)
            for item in row:
                _draw_item(image, item, item_x, y, row_width, row_height, radius, primary, text, muted, font_icon, font_label, font_mono, font_small, scale, foreground_opacity)
                item_x += row_width + item_gap
            y += row_height + item_gap
        y = bottom + 18 * scale

    if footer_text or style.get("show_updated_at", True):
        footer_y = height - margin - shell_pad - 6 * scale
        draw.text((x, footer_y), footer_text, font=font_small, fill=muted)
        if style.get("show_updated_at", True):
            updated = _format_time(menu.get("updated_at"))
            right = f"更新：{updated}"
            draw.text((x + content_width - _text_width(font_small, right), footer_y), right, font=font_small, fill=muted)

    target_width = base_width * output_scale
    target_height = int(height * output_scale / scale)
    if image.size != (target_width, target_height):
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = image.convert("RGB")
    image.save(output_path, format="PNG")
    return str(output_path)


def image_file_to_data_url(path: str | Path) -> str:
    """Convert a rendered local image file into a browser-displayable data URL."""

    image_path = Path(path)
    raw = image_path.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def render_menu_via_browser(
    menu: dict[str, Any],
    output_dir: str | Path,
    html_content: str,
    *,
    default_width: int = 900,
    viewport_width: int | None = None,
    device_scale_factor: int = 4,
) -> str:
    """Render a menu to a high-quality local PNG using a cross-platform Chromium browser."""

    output_path = _build_output_path(menu, output_dir, prefix="browser")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_path.resolve()

    html_path = output_path.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")

    width = _clamp_int(viewport_width, default=default_width, minimum=520, maximum=1400)
    height = _estimate_preview_height(menu)
    scale = _clamp_int(device_scale_factor, default=4, minimum=1, maximum=4)

    try:
        _render_menu_via_playwright(
            html_content,
            screenshot_path,
            width=width,
            height=height,
            device_scale_factor=scale,
        )
    except Exception as playwright_exc:
        browser_path = _find_browser_executable()

        if not browser_path:
            raise RuntimeError(
                "No suitable Chromium browser found for local rendering. "
                f"Playwright failed first: {_decode_process_output(str(playwright_exc))}"
            ) from playwright_exc

        cmd = _build_browser_screenshot_command(
            browser_path,
            screenshot_path,
            html_path,
            width=width,
            height=height,
            device_scale_factor=scale,
        )

        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        except subprocess.CalledProcessError as exc:
            stderr = _decode_process_output(exc.stderr)
            stdout = _decode_process_output(exc.stdout)
            detail = stderr or stdout or str(exc)
            raise RuntimeError(f"Browser screenshot failed: {detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Browser screenshot timed out.") from exc
        else:
            if not screenshot_path.is_file():
                stderr = _decode_process_output(completed.stderr)
                stdout = _decode_process_output(completed.stdout)
                detail = stderr or stdout or "browser did not create the screenshot file"
                raise RuntimeError(f"Browser screenshot failed: {detail}")
    else:
        if not screenshot_path.is_file():
            raise RuntimeError("Playwright did not create the screenshot file")
    finally:
        try:
            html_path.unlink(missing_ok=True)
        except OSError:
            pass

    try:
        _crop_transparent_padding(output_path)
    except Exception:
        pass

    return str(output_path)


def _render_menu_via_playwright(
    html_content: str,
    screenshot_path: Path,
    *,
    width: int,
    height: int,
    device_scale_factor: int,
) -> None:
    """Render HTML through Playwright's Chromium API when available.

    This avoids OS-specific browser command-line behavior and keeps the output
    aligned with the Page preview because both paths use Chromium layout.
    """

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    launch_args = [
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--default-background-color=00000000",
    ]
    scale = _clamp_int(device_scale_factor, default=4, minimum=1, maximum=4)
    last_error: Exception | None = None

    with sync_playwright() as playwright:
        launchers: list[dict[str, Any]] = [{"args": launch_args}]
        for channel in ("chrome", "msedge", "chromium"):
            launchers.append({"channel": channel, "args": launch_args})

        for launch_options in launchers:
            browser = None
            try:
                browser = playwright.chromium.launch(headless=True, **launch_options)
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale,
                    is_mobile=False,
                    has_touch=False,
                )
                page = context.new_page()
                page.set_content(html_content, wait_until="load", timeout=15000)
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except PlaywrightError:
                    pass
                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                    omit_background=True,
                    animations="disabled",
                    timeout=15000,
                )
                context.close()
                return
            except Exception as exc:
                last_error = exc
            finally:
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass

    if last_error:
        raise RuntimeError(f"Playwright Chromium render failed: {last_error}") from last_error
    raise RuntimeError("Playwright Chromium render failed")


def _build_browser_screenshot_command(
    browser_path: str,
    screenshot_path: Path,
    html_path: Path,
    *,
    width: int,
    height: int,
    device_scale_factor: int,
) -> list[str]:
    scale = _clamp_int(device_scale_factor, default=4, minimum=1, maximum=4)
    return [
        browser_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=1000",
        f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}",
        "--default-background-color=00000000",
        f"--screenshot={screenshot_path}",
        html_path.resolve().as_uri(),
    ]


def _find_browser_executable() -> str | None:
    env_browser = os.environ.get("BOT_MENU_BROWSER") or os.environ.get("BROWSER")
    if env_browser and Path(env_browser).exists():
        return env_browser
    if env_browser:
        found = shutil.which(env_browser)
        if found:
            return found

    for name in (
        "msedge",
        "msedge.exe",
        "microsoft-edge",
        "microsoft-edge-stable",
        "chrome",
        "chrome.exe",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium.exe",
        "chromium-browser",
        "brave",
        "brave-browser",
    ):
        found = shutil.which(name)
        if found:
            return found

    browser_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/usr/bin/brave-browser",
        "/snap/bin/chromium",
    ]
    return next((path for path in browser_paths if os.path.exists(path)), None)


def _estimate_preview_height(menu: dict[str, Any]) -> int:
    item_count = 0
    section_count = 0
    text_units = 0
    for section in menu.get("sections", []):
        section_count += 1
        text_units += len(str(section.get("title") or ""))
        for item in section.get("items", []):
            item_count += 1
            text_units += len(str(item.get("label") or ""))
            text_units += len(str(item.get("command") or ""))
            text_units += len(str(item.get("description") or ""))

    estimated = 260 + section_count * 90 + item_count * 95 + (text_units // 28) * 24
    return max(900, min(30000, estimated))


def _crop_transparent_padding(path: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        return

    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        bbox = rgba.getbbox()
        if not bbox or bbox == (0, 0, rgba.width, rgba.height):
            return
        rgba.crop(bbox).save(path, format="PNG")


def _decode_process_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value.decode("utf-8", errors="replace").strip()


def _paste_custom_background(image, style: dict[str, Any], width: int, height: int, scale: int) -> None:
    source = str(style.get("background_image") or "")
    if not source.startswith("data:image/"):
        return
    try:
        header, payload = source.split(",", 1)
        if ";base64" not in header:
            return
        from PIL import Image

        with Image.open(io.BytesIO(base64.b64decode(payload))) as bg_image:
            bg_image = bg_image.convert("RGB")
            image_width_pct = _clamp_int(style.get("background_image_width"), default=100, minimum=10, maximum=600)
            target_width = max(1, int(width * image_width_pct / 100))
            target_height = max(1, int(target_width * bg_image.height / bg_image.width))
            bg_image = bg_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            x = int(width * _clamp_int(style.get("background_image_x"), default=0, minimum=-300, maximum=300) / 100)
            y = int(height * _clamp_int(style.get("background_image_y"), default=0, minimum=-300, maximum=300) / 100)
            image.paste(bg_image, (x, y))
    except Exception:
        return


def _draw_translucent_rounded_rectangle(
    image,
    box,
    *,
    radius: int,
    fill: tuple[int, int, int],
    opacity: float,
    outline: tuple[int, int, int] | None = None,
    width: int = 1,
) -> None:
    from PIL import Image, ImageDraw

    alpha = max(0, min(255, int(255 * opacity)))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    outline_rgba = (*outline, alpha) if outline else None
    overlay_draw.rounded_rectangle(box, radius=radius, fill=(*fill, alpha), outline=outline_rgba, width=width)
    image.alpha_composite(overlay)


def _draw_translucent_rectangle(
    image,
    box,
    *,
    fill: tuple[int, int, int],
    opacity: float,
) -> None:
    from PIL import Image, ImageDraw

    alpha = max(0, min(255, int(255 * opacity)))
    if alpha <= 0:
        return
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(box, fill=(*fill, alpha))
    image.alpha_composite(overlay)


def _layout_item_rows(items: list[dict[str, Any]], columns: int) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = []
    for item in items:
        if _card_size(item.get("card_size")) == "banner":
            if current_row:
                rows.append(current_row)
                current_row = []
            rows.append([item])
            continue
        current_row.append(item)
        if len(current_row) == columns:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    return rows


def _row_item_width(row: list[dict[str, Any]], item_area_width: int, item_gap: int, columns: int) -> int:
    if len(row) == 1 and _card_size(row[0].get("card_size")) == "banner":
        return item_area_width
    return max(1, (item_area_width - item_gap * max(0, columns - 1)) // columns)


def _card_size(value: Any) -> str:
    size = str(value or "standard").strip().lower()
    return size if size in {"compact", "standard", "large", "banner"} else "standard"


def _draw_item(image, item, x, y, width, height, radius, primary, text, muted, font_icon, font_label, font_mono, font_small, scale, opacity) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    enabled = item.get("enabled", True)
    fill = (246, 248, 252) if enabled else (238, 240, 244)
    fg = text if enabled else _mix(text, (255, 255, 255), 0.45)
    sub = muted if enabled else _mix(muted, (255, 255, 255), 0.5)
    size = _card_size(item.get("card_size"))
    icon_size = 36 * scale if size == "compact" else 44 * scale
    icon_left = x + (10 if size == "compact" else 14) * scale
    icon_top = y + (11 if size == "compact" else 14) * scale
    text_x = x + (56 if size == "compact" else 70) * scale
    line_y = y + (10 if size == "compact" else 14) * scale
    _draw_translucent_rounded_rectangle(
        image,
        (x, y, x + width, y + height),
        radius=max(12 * scale, radius - 8 * scale),
        fill=fill,
        opacity=opacity,
        outline=_mix(muted, (255, 255, 255), 0.82),
    )
    _draw_translucent_rounded_rectangle(
        image,
        (icon_left, icon_top, icon_left + icon_size, icon_top + icon_size),
        radius=12 * scale,
        fill=_mix(primary, (255, 255, 255), 0.88),
        opacity=opacity,
    )
    draw.text((icon_left + 8 * scale, icon_top + 7 * scale), str(item.get("icon") or "•")[:2], font=font_icon, fill=primary)
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
    size = _card_size(item.get("card_size"))
    text_width = width - (70 if size != "compact" else 56) * scale - 14 * scale
    desc_lines = len(_wrap(str(item.get("description") or ""), font_small, text_width, max_lines=3))
    command_lines = len(_wrap(str(item.get("command") or ""), font_mono, text_width, max_lines=2))
    min_height = {"compact": 58, "standard": 88, "large": 104, "banner": 112}[size] * scale
    vertical_pad = {"compact": 20, "standard": 28, "large": 34, "banner": 34}[size] * scale
    return max(min_height, vertical_pad + 28 * scale + command_lines * 22 * scale + desc_lines * 22 * scale)


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


def _build_output_path(menu: dict[str, Any], output_dir: str | Path, prefix: str = "menu") -> Path:
    raw = json.dumps(menu, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    safe_id = "".join(ch for ch in str(menu.get("id") or "menu") if ch.isalnum() or ch in ("_", "-")) or "menu"
    return Path(output_dir) / "rendered" / f"{safe_id}-{prefix}-{digest}.png"
