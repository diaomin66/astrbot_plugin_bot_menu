from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.menu_model import MenuValidationError, normalize_menu
from services.local_image import _build_browser_screenshot_command, _find_browser_executable, image_file_to_data_url, render_menu_image
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

    def test_pillow_renderer_can_output_high_resolution_png(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            path = render_menu_image(storage.get_menu("default"), tmp, output_scale=3)
            with Image.open(path) as image:
                self.assertEqual(image.width, storage.get_menu("default")["style"]["width"] * 3)

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

    def test_page_reload_does_not_realign_saved_background_to_top(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        self.assertNotIn("fitBackgroundToCover(false)", app_js)
        self.assertIn("fitBackgroundToCover(true)", app_js)

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
