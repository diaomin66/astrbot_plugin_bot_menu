from __future__ import annotations

import tempfile
import unittest

from services.menu_model import MenuValidationError, normalize_menu
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


if __name__ == "__main__":
    unittest.main()
