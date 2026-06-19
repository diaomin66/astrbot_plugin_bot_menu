from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.menu_model import MenuValidationError, normalize_menu
from services.local_image import (
    _build_browser_screenshot_command,
    _crop_transparent_padding_png,
    _find_browser_executable,
    image_file_to_data_url,
    render_menu_image,
)
from services.render_cache import MenuRenderCache
from services.render_coordinator import MenuRenderCoordinator
from services.renderer import build_preview_html, preview_width_for_menu
from services.storage import MenuStorage


class MenuModelTests(unittest.TestCase):
    def test_normalize_menu_accepts_valid_payload(self):
        menu = normalize_menu(
            {
                "id": "main",
                "name": "主菜单",
                "title": "菜单",
                "sections": [
                    {
                        "title": "功能",
                        "items": [{"label": "帮助", "command": "/help"}],
                    }
                ],
            }
        )
        self.assertEqual(menu["id"], "main")
        self.assertTrue(menu["sections"][0]["items"][0]["enabled"])
        self.assertEqual(menu["style"]["width_mode"], "auto")
        self.assertEqual(menu["style"]["columns"], 2)
        self.assertEqual(menu["sections"][0]["items"][0]["card_size"], "standard")

    def test_normalize_menu_accepts_layout_and_card_size(self):
        menu = normalize_menu(
            {
                "id": "main",
                "style": {
                    "width_mode": "custom",
                    "width": 680,
                    "columns": 3,
                    "foreground_opacity": 45,
                    "background_image": "data:image/png;base64,AAAA",
                    "background_image_x": -12,
                    "background_image_y": 18,
                    "background_image_width": 150,
                    "section_gap_mode": "custom",
                    "section_gap": 0,
                },
                "sections": [
                    {
                        "title": "功能",
                        "items": [{"label": "公告", "card_size": "banner"}],
                    }
                ],
            }
        )
        self.assertEqual(menu["style"]["width_mode"], "custom")
        self.assertEqual(menu["style"]["width"], 680)
        self.assertEqual(menu["style"]["columns"], 3)
        self.assertEqual(menu["style"]["foreground_opacity"], 45)
        self.assertEqual(menu["style"]["background_image_x"], -12)
        self.assertEqual(menu["style"]["background_image_y"], 18)
        self.assertEqual(menu["style"]["background_image_width"], 150)
        self.assertEqual(menu["style"]["section_gap_mode"], "custom")
        self.assertEqual(menu["style"]["section_gap"], 0)
        self.assertTrue(menu["style"]["background_image"].startswith("data:image/png"))
        self.assertEqual(menu["sections"][0]["items"][0]["card_size"], "banner")

    def test_normalize_menu_rejects_invalid_id(self):
        with self.assertRaises(MenuValidationError):
            normalize_menu({"id": "中文", "sections": [{"title": "x", "items": [{"label": "y"}]}]})

    def test_normalize_menu_requires_item_label(self):
        with self.assertRaises(MenuValidationError):
            normalize_menu({"id": "main", "sections": [{"title": "x", "items": [{"label": ""}]}]})


class MenuStorageTests(unittest.TestCase):
    def test_storage_creates_default_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menus = storage.list_menus()
            self.assertEqual(len(menus), 1)
            self.assertEqual(menus[0]["id"], "default")

    def test_save_and_delete_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            storage.save_menu({"id": "main", "name": "主菜单", "sections": [{"title": "功能", "items": [{"label": "帮助"}]}]})
            self.assertIsNotNone(storage.get_menu("main"))
            storage.delete_menu("main")
            self.assertIsNone(storage.get_menu("main"))

    def test_import_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menus = storage.import_menus(
                [{"id": "imported", "sections": [{"title": "功能", "items": [{"label": "帮助"}]}]}],
                mode="replace",
            )
            self.assertEqual([menu["id"] for menu in menus], ["imported"])

    def test_local_renderer_writes_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            path = render_menu_image(storage.get_menu("default"), tmp)
            self.assertTrue(path.endswith(".png"))
            with open(path, "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_rendered_png_can_be_embedded_in_web_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            path = render_menu_image(storage.get_menu("default"), tmp)
            data_url = image_file_to_data_url(path)
            self.assertTrue(data_url.startswith("data:image/png;base64,"))

    def test_render_cache_stores_and_invalidates_by_menu_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            rendered_path = render_menu_image(menu, tmp)
            cache = MenuRenderCache(tmp)
            cached_path = cache.store_rendered(menu, rendered_path, render_width=900, render_scale=4)
            self.assertEqual(cache.get_cached_path(menu, render_width=900, render_scale=4), cached_path)
            changed_menu = {**menu, "title": "修改后的菜单"}
            self.assertIsNone(cache.get_cached_path(changed_menu, render_width=900, render_scale=4))
            self.assertTrue(Path(cached_path).is_file())

    def test_render_status_reports_missing_rendering_ready_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            cache = MenuRenderCache(tmp)
            self.assertEqual(cache.get_status(menu, render_width=900, render_scale=4)["status"], "missing")

            cache.mark_rendering(menu, render_width=900, render_scale=4)
            self.assertEqual(cache.get_status(menu, render_width=900, render_scale=4)["status"], "rendering")

            rendered_path = render_menu_image(menu, tmp)
            cache.store_rendered(menu, rendered_path, render_width=900, render_scale=4)
            ready = cache.get_status(menu, render_width=900, render_scale=4)
            self.assertEqual(ready["status"], "ready")
            self.assertIsNotNone(ready["rendered_at"])

            changed_menu = {**menu, "title": "修改后的菜单"}
            self.assertEqual(cache.get_status(changed_menu, render_width=900, render_scale=4)["status"], "missing")
            cache.mark_error(changed_menu, "boom", render_width=900, render_scale=4)
            error = cache.get_status(changed_menu, render_width=900, render_scale=4)
            self.assertEqual(error["status"], "error")
            self.assertEqual(error["error"], "boom")

    def test_render_coordinator_schedules_cache_generation(self):
        import asyncio

        async def run_case():
            with tempfile.TemporaryDirectory() as tmp:
                storage = MenuStorage(tmp)
                menu = storage.get_menu("default")
                cache = MenuRenderCache(tmp)

                async def render_menu(_menu):
                    return render_menu_image(_menu, tmp)

                coordinator = MenuRenderCoordinator(
                    storage=storage,
                    cache=cache,
                    render_menu=render_menu,
                    render_width=lambda: 900,
                    render_scale=lambda: 4,
                )
                self.assertTrue(coordinator.schedule(menu))
                self.assertEqual(coordinator.status_for_menu(menu)["status"], "rendering")
                await asyncio.sleep(0.1)
                self.assertEqual(coordinator.status_for_menu(menu)["status"], "ready")

        asyncio.run(run_case())

    def test_commands_use_cached_render_before_scheduling_background_render(self):
        main_py = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("cached_path = self.render_coordinator.get_cached_path(menu)", main_py)
        self.assertIn("yield event.image_result(cached_path)", main_py)
        self.assertIn("self.render_coordinator.schedule(menu)", main_py)
        self.assertLess(
            main_py.index("cached_path = self.render_coordinator.get_cached_path(menu)"),
            main_py.index("yield event.image_result(cached_path)"),
        )
        self.assertIn("self.render_coordinator.schedule(menu)", main_py[main_py.index("async def api_save_menu") :])
        self.assertIn("menus/render-status/<menu_id>", main_py)

    def test_pillow_renderer_can_output_high_resolution_png(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            path = render_menu_image(menu, tmp, output_scale=3)
            with Image.open(path) as image:
                self.assertEqual(image.width, preview_width_for_menu(menu) * 3)

    def test_pillow_renderer_uses_auto_width_columns_and_banner_cards(self):
        from PIL import Image

        menu = normalize_menu(
            {
                "id": "layout",
                "style": {"width_mode": "auto", "columns": 4, "foreground_opacity": 0},
                "sections": [
                    {
                        "title": "功能",
                        "items": [
                            {"label": "横幅", "card_size": "banner"},
                            *({"label": f"功能{i}", "card_size": "compact"} for i in range(4)),
                        ],
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = render_menu_image(menu, tmp, output_scale=2)
            with Image.open(path) as image:
                self.assertEqual(image.width, preview_width_for_menu(menu) * 2)

    def test_release_metadata_readme_changelog_and_logo_are_consistent(self):
        import re

        metadata = Path("metadata.yaml").read_text(encoding="utf-8")
        readme = Path("README.md").read_text(encoding="utf-8")
        changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
        version = re.search(r"^version:\s*(.+)$", metadata, re.MULTILINE).group(1)
        author = re.search(r"^author:\s*(.+)$", metadata, re.MULTILINE).group(1)
        self.assertEqual(version, "0.3.0")
        self.assertEqual(author, "雪碧bir")
        self.assertIn(f"当前版本：`{version}`", readme)
        self.assertIn(f"## {version} -", changelog)
        with open("logo.png", "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_page_editor_exposes_v030_editing_features(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        index_html = Path("pages/menu-editor/index.html").read_text(encoding="utf-8")
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")

        self.assertIn("DRAFT_PREFIX", app_js)
        self.assertIn("beforeunload", app_js)
        self.assertIn("validateMenu", app_js)
        self.assertIn("collapsedKeys", app_js)
        self.assertIn("copyStyleToMenus", app_js)
        self.assertIn("backgroundImageWidth", app_js)
        self.assertIn("sectionGapForMenu", app_js)
        self.assertIn("menus/render-status", app_js)
        self.assertNotIn('id="templateBtn"', index_html)
        self.assertIn('id="itemSearch"', index_html)
        self.assertIn('id="backgroundImageX"', index_html)
        self.assertIn('id="sectionGapMode"', index_html)
        self.assertIn('id="sectionGap" type="number" min="0" max="200"', index_html)
        self.assertIn("theme-preset-cards", css)
        self.assertIn("validation-summary", css)
        self.assertIn("discardUnsavedMenu", app_js)
        self.assertIn("backgroundEditMode", app_js)
        self.assertIn("toggleBackgroundEditMode", app_js)
        self.assertIn('id="backgroundEditToggleBtn"', index_html)
        self.assertIn("is-bg-editing", css)
        self.assertNotIn("serverPreview", app_js + index_html + css)
        self.assertNotIn("menus/preview", app_js)

    def test_server_preview_api_is_removed(self):
        main_py = Path("main.py").read_text(encoding="utf-8")
        self.assertNotIn("menus/preview", main_py)
        self.assertNotIn("api_preview_menu", main_py)
        self.assertNotIn("_preview_image_url", main_py)

    def test_browser_screenshot_command_uses_high_scale_factor(self):
        command = _build_browser_screenshot_command(
            "browser.exe",
            Path("out.png"),
            Path("preview.html"),
            width=660,
            height=900,
            device_scale_factor=4,
        )
        self.assertIn("--force-device-scale-factor=4", command)

    def test_browser_discovery_uses_cross_platform_command_names(self):
        import os
        import shutil
        from unittest.mock import patch

        command_names: list[str] = []

        def fake_which(name):
            command_names.append(name)
            return "/usr/bin/chromium-browser" if name == "chromium-browser" else None

        with patch.dict(os.environ, {}, clear=True), patch.object(shutil, "which", side_effect=fake_which):
            self.assertEqual(_find_browser_executable(), "/usr/bin/chromium-browser")
        self.assertIn("google-chrome", command_names)
        self.assertIn("chromium-browser", command_names)

    def test_png_crop_fallback_removes_transparent_browser_tail_without_pillow(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tail.png"
            image = Image.new("RGBA", (8, 10), (0, 0, 0, 0))
            for y in range(6):
                for x in range(8):
                    image.putpixel((x, y), (250, 250, 255, 255))
            image.save(path, format="PNG")

            self.assertTrue(_crop_transparent_padding_png(path))
            with Image.open(path) as cropped:
                self.assertEqual(cropped.size, (8, 6))

    def test_preview_html_uses_page_preview_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            width = preview_width_for_menu(menu)
            html = build_preview_html(menu)
            self.assertIn('class="preview-card"', html)
            self.assertLess(width, 900)
            self.assertIn(f"--preview-width:{width}px", html)
            self.assertIn("--preview-columns:2", html)
            self.assertIn("--preview-foreground-opacity:0.920", html)
            self.assertIn('class="preview-inner"', html)
            self.assertIn('class="preview-item size-standard', html)
            self.assertIn("实时预览", html)
            self.assertNotIn("更新：", html)

    def test_preview_width_can_be_customized(self):
        menu = normalize_menu(
            {
                "id": "wide",
                "style": {"width_mode": "custom", "width": 720, "columns": 1},
                "sections": [{"title": "功能", "items": [{"label": "帮助"}]}],
            }
        )
        self.assertEqual(preview_width_for_menu(menu), 720)
        self.assertIn("--preview-columns:1", build_preview_html(menu))

    def test_preview_html_embeds_custom_background(self):
        menu = normalize_menu(
            {
                "id": "bg",
                "style": {
                    "background_image": "data:image/png;base64,AAAA",
                    "background_image_x": 10,
                    "background_image_y": -5,
                    "background_image_width": 120,
                    "foreground_opacity": 60,
                },
                "sections": [{"title": "功能", "items": [{"label": "帮助"}]}],
            }
        )
        html = build_preview_html(menu)
        self.assertIn('class="preview-bg-image"', html)
        self.assertIn("left:10%;top:-5%;width:120%", html)
        self.assertIn("--preview-foreground-opacity:0.600", html)

    def test_preview_html_uses_custom_section_gap(self):
        menu = normalize_menu(
            {
                "id": "gap",
                "style": {"section_gap_mode": "custom", "section_gap": 0},
                "sections": [
                    {"title": "分组1", "items": [{"label": "帮助"}]},
                    {"title": "分组2", "items": [{"label": "菜单"}]},
                ],
            }
        )
        html = build_preview_html(menu)
        self.assertIn("--preview-section-gap:0px", html)
        self.assertIn('class="preview-sections"', html)

    def test_page_reload_does_not_realign_saved_background_to_top(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        self.assertNotIn("fitBackgroundToCover(false)", app_js)
        self.assertIn("fitBackgroundToCover(true)", app_js)

    def test_editor_preview_column_has_independent_scroll_pane(self):
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")
        self.assertIn(".preview-stage {\n  min-width: 0;\n  min-height: 0;\n  height: 100%;\n  overflow-y: auto;", css)
        self.assertIn(".preview-panel {\n  min-height: 100%;\n  display: flex;\n  flex-direction: column;\n  overflow: visible;", css)
        self.assertIn(".app {\n  height: 100vh;\n  height: 100dvh;\n  min-height: 0;\n  overflow: hidden;", css)
        self.assertIn("overscroll-behavior: contain;", css)

    def test_preview_width_grows_with_columns(self):
        one_column = normalize_menu(
            {
                "id": "one",
                "style": {"width_mode": "auto", "columns": 1},
                "sections": [{"title": "功能", "items": [{"label": "帮助"}]}],
            }
        )
        four_columns = normalize_menu(
            {
                "id": "four",
                "style": {"width_mode": "auto", "columns": 4},
                "sections": [{"title": "功能", "items": [{"label": "帮助"} for _ in range(4)]}],
            }
        )
        self.assertLess(preview_width_for_menu(one_column), preview_width_for_menu(four_columns))


if __name__ == "__main__":
    unittest.main()
