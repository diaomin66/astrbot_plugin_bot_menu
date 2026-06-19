from __future__ import annotations

import tempfile
import unittest

from services.menu_model import MenuValidationError, normalize_menu
from services.local_image import image_file_to_data_url, render_menu_image
from services.renderer import build_preview_html
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

    def test_preview_html_uses_page_preview_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            html = build_preview_html(storage.get_menu("default"))
            self.assertIn('class="preview-card"', html)
            self.assertIn("--preview-width:900px", html)
            self.assertIn('class="preview-inner"', html)
            self.assertIn('class="preview-item', html)
            self.assertIn("实时预览", html)
            self.assertNotIn("更新：", html)


if __name__ == "__main__":
    unittest.main()
