from __future__ import annotations

import tempfile
import unittest
import re
from html.parser import HTMLParser
from pathlib import Path

from services.asset_storage import AssetStorage
from services.fonts import FontRegistry
from services.history_storage import MenuHistoryStorage
from services.menu_model import DEFAULT_STYLE, MenuValidationError, normalize_menu
from services.local_image import (
    _build_browser_screenshot_command,
    _crop_transparent_padding_png,
    _find_browser_executable,
    _playwright_error_looks_like_missing_browser,
    image_file_to_data_url,
    render_menu_image,
)
from services.render_cache import MenuRenderCache
from services.render_coordinator import MenuRenderCoordinator
from services.renderer import build_preview_html, build_render_payload, preview_width_for_menu
from services.routing_storage import RoutingStorage
from services.storage import MenuStorage


class _PreviewCardStyleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.style = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.style or tag != "div":
            return
        attr_map = dict(attrs)
        if attr_map.get("class") == "preview-card":
            self.style = attr_map.get("style") or ""


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
                "aliases": ["管理", "main"],
                "style": {
                    "width_mode": "custom",
                    "width": 680,
                    "columns": 3,
                    "background_image_asset_id": "asset123",
                    "font_family": "Noto Sans CJK SC",
                    "card_gap": 6,
                    "section_padding": 12,
                    "shadow_strength": 2,
                    "border_strength": 3,
                    "background_overlay": 15,
                    "background_blur": 4,
                    "watermark": "demo",
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
        self.assertEqual(menu["aliases"], ["管理"])
        self.assertEqual(menu["style"]["width_mode"], "custom")
        self.assertEqual(menu["style"]["width"], 680)
        self.assertEqual(menu["style"]["columns"], 3)
        self.assertEqual(menu["style"]["background_image_asset_id"], "asset123")
        self.assertEqual(menu["style"]["font_family"], "Noto Sans CJK SC")
        self.assertEqual(menu["style"]["card_gap"], 6)
        self.assertEqual(menu["style"]["section_padding"], 12)
        self.assertEqual(menu["style"]["shadow_strength"], 2)
        self.assertEqual(menu["style"]["border_strength"], 3)
        self.assertEqual(menu["style"]["background_overlay"], 15)
        self.assertEqual(menu["style"]["background_blur"], 4)
        self.assertEqual(menu["style"]["watermark"], "demo")
        self.assertEqual(menu["style"]["foreground_opacity"], 45)
        self.assertEqual(menu["style"]["background_image_x"], -12)
        self.assertEqual(menu["style"]["background_image_y"], 18)
        self.assertEqual(menu["style"]["background_image_width"], 150)
        self.assertEqual(menu["style"]["section_gap_mode"], "custom")
        self.assertEqual(menu["style"]["section_gap"], 0)
        self.assertTrue(menu["style"]["background_image"].startswith("data:image/png"))
        self.assertEqual(menu["sections"][0]["items"][0]["card_size"], "banner")

    def test_normalize_menu_accepts_per_card_content_layout(self):
        menu = normalize_menu(
            {
                "id": "layout",
                "sections": [
                    {
                        "title": "功能",
                        "items": [
                            {
                                "label": "帮助",
                                "command": "/help",
                                "description": "说明",
                                "content_order": ["description", "command", "label"],
                                "content_gap": 9,
                                "command_font_size": 18.4,
                                "label_font_size": 13,
                                "description_font_size": 10.2,
                            }
                        ],
                    }
                ],
            }
        )
        item = menu["sections"][0]["items"][0]
        self.assertEqual(item["content_order"], ["description", "command", "label"])
        self.assertEqual(item["content_gap"], 9)
        self.assertEqual(item["command_font_size"], 18.5)
        self.assertEqual(item["label_font_size"], 13)
        self.assertEqual(item["description_font_size"], 10)

    def test_normalize_menu_rejects_invalid_id(self):
        with self.assertRaises(MenuValidationError):
            normalize_menu({"id": "中文", "sections": [{"title": "x", "items": [{"label": "y"}]}]})

    def test_normalize_menu_requires_item_label(self):
        with self.assertRaises(MenuValidationError):
            normalize_menu({"id": "main", "sections": [{"title": "x", "items": [{"label": ""}]}]})


class MenuEditorSourceTests(unittest.TestCase):
    def test_layout_mode_controls_handle_webview_change_events_without_resetting_style(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        self.assertIn('select.addEventListener("change", emitChange);', app_js)
        self.assertIn('function styleSnapshot(menu, patch = {})', app_js)
        self.assertIn('styleSnapshot(menu, { width_mode: "auto" })', app_js)
        self.assertIn('styleSnapshot(menu, { section_gap_mode: "auto" })', app_js)
        self.assertNotIn('style: { ...ensureStyle(menu), width_mode: "auto" }', app_js)
        self.assertNotIn('style: { ...ensureStyle(menu), section_gap_mode: "auto" }', app_js)

    def test_page_buttons_use_resilient_bridge_and_change_events(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")

        self.assertIn("async function resolvePageBridge()", app_js)
        self.assertIn("function normalizePageBridge(rawBridge)", app_js)
        self.assertIn('const events = control.type === "file" ? ["change"] : ["input", "change"];', app_js)
        self.assertNotIn("controlValueSignature", app_js)
        self.assertNotIn("let lastValue = controlValueSignature(control)", app_js)
        self.assertIn("bindValueChange(input, () => onInput(input.value, input));", app_js)
        self.assertIn("bindValueChange(input, () => onInput(input.checked, input));", app_js)
        self.assertIn('state.unsavedMenuIds.add(snapshot.id);', app_js)
        self.assertIn('badges.push("未保存");', app_js)
        self.assertIn("function switchMenu(id", app_js)
        self.assertIn("function stashActiveMenu()", app_js)
        self.assertIn("function activateLocalMenu(menu", app_js)
        self.assertIn("const isSavedMenu = state.serverMenuIds.has(currentId);", app_js)
        self.assertIn("function confirmDialog(title, message", app_js)
        self.assertIn("const confirmed = await confirmDialog(", app_js)
        self.assertIn("renderDeletedMenuList", app_js)
        self.assertIn("restoreDeletedMenu", app_js)
        self.assertIn('assets: Array.isArray(data.assets) ? data.assets : []', app_js)
        self.assertIn('label: "一键重置样式"', app_js)

    def test_save_uses_complete_state_snapshot_without_replaying_stale_modal_controls(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")

        self.assertIn("function flushLiveEditorControls()", app_js)
        self.assertIn("function dispatchEditorControlEvent(control, eventName)", app_js)
        self.assertNotIn('els.editorModal.querySelectorAll("input, select, textarea")', app_js)
        self.assertIn('if (active.type !== "file")', app_js)
        self.assertIn('dispatchEditorControlEvent(active, "input");', app_js)
        self.assertIn('dispatchEditorControlEvent(active, "change");', app_js)
        self.assertIn('event.initEvent(eventName, true, false);', app_js)
        save_body = app_js.split("async function saveMenu()", 1)[1].split("function createDefaultMenu", 1)[0]
        self.assertIn("const menuSnapshot = buildMenuSaveSnapshot();", save_body)
        self.assertNotIn("syncFormToMenu({ mark: false });", save_body)
        self.assertLess(save_body.index("flushLiveEditorControls();"), save_body.index("buildMenuSaveSnapshot();"))
        self.assertLess(save_body.index("buildMenuSaveSnapshot();"), save_body.index('bridge.apiPost("menus/save", { menu: menuSnapshot })'))
        self.assertIn("function buildMenuSaveSnapshot()", app_js)

    def test_page_destructive_actions_use_in_page_dialogs(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")

        self.assertNotIn("confirm(", app_js)
        self.assertNotIn("prompt(", app_js)
        self.assertIn("function promptDialog(", app_js)
        self.assertIn("function confirmDialog(", app_js)
        self.assertIn('"删除卡片？"', app_js)
        self.assertIn('"删除分组？"', app_js)
        self.assertIn('"批量删除？"', app_js)
        self.assertIn('promptDialog(', app_js)
        self.assertIn("await maybeRestoreDraft(sourceMenu)", app_js)

    def test_editor_exposes_single_and_batch_card_layout_controls(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        index_html = Path("pages/menu-editor/index.html").read_text(encoding="utf-8")
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")
        self.assertIn('const CONTENT_BLOCKS = [', app_js)
        self.assertIn('function appendItemLayoutFields(', app_js)
        self.assertIn('function openBatchLayoutEditor()', app_js)
        self.assertIn('function selectedItemEntries()', app_js)
        self.assertIn('style="${itemPreviewStyle(item)}"', app_js)
        self.assertIn('renderItemContentBlocks(item)', app_js)
        self.assertIn('id="batchLayoutBtn"', index_html)
        self.assertIn('id="batchSelectToggleBtn"', index_html)
        self.assertIn('id="batchSelectAllBtn"', index_html)
        self.assertIn("function toggleBatchSelectMode()", app_js)
        self.assertIn("function selectAllBatchCards()", app_js)
        self.assertIn("function selectableBatchItemKeys()", app_js)
        self.assertIn("state.batchSelectMode", app_js)
        self.assertIn('class="preview-select-marker"', app_js)
        self.assertNotIn('selectedClass ? "✓" : ""', app_js)
        self.assertIn('els.batchToolbar.hidden = !state.batchSelectMode && count === 0;', app_js)
        self.assertIn('els.batchSelectAllBtn.textContent = state.itemSearch ? `全选结果(${selectableCount})` : `全选卡片(${selectableCount})`;', app_js)
        self.assertIn(".preview-card.is-batch-selecting", css)
        self.assertIn(".preview-item.is-selected .preview-select-marker", css)
        self.assertIn("mutator(ensureStyle(state.menu));", app_js)

    def test_editor_modal_has_resize_handle(self):
        index_html = Path("pages/menu-editor/index.html").read_text(encoding="utf-8")
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")
        self.assertIn('class="modal-resize-grip"', index_html)
        self.assertIn("resize: both;", css)
        self.assertIn(".modal-resize-grip", css)

    def test_page_simplifies_operations_console_and_keeps_core_editing_features(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        index_html = Path("pages/menu-editor/index.html").read_text(encoding="utf-8")
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")

        for token in ('id="undoBtn"', 'id="redoBtn"', 'id="historyBtn"', 'id="newBtn"', 'id="copyBtn"', 'id="deleteBtn"', 'id="batchToolbar"'):
            self.assertIn(token, index_html)

        for removed in (
            'id="commandPaletteBtn"',
            'id="assetCenterBtn"',
            'id="trashBtn"',
            'id="routingBtn"',
            'id="densitySelect"',
            'id="previewDevice"',
            "openCommandPalette",
            "openAssetCenter",
            "openTrashPanel",
            "openRoutingPanel",
            "setDensity",
            "setPreviewDevice",
            "command-palette",
            "asset-grid",
        ):
            self.assertNotIn(removed, app_js + index_html + css)

        for token in (
            "bindGlobalShortcuts",
            "undoMenuChange",
            "redoMenuChange",
            "batchSetEnabled",
            "batchCopySelection",
            "openHistoryPanel",
            "switchMenu",
            "stashActiveMenu",
            "activateLocalMenu",
            "createDefaultMenu",
            "chooseFallbackMenuId",
            "showImportResult",
            "syncThemeSelectOptions",
            "morandi",
            "macaron",
            "seaSalt",
            "contrastWarningText",
            "fixContrastColors",
            "background_image_asset_id",
            "font_family",
            "card_gap",
            "section_padding",
            "shadow_strength",
            "background_overlay",
            "background_blur",
            "watermark",
        ):
            self.assertIn(token, app_js)
        theme_block = app_js.split("const THEME_PRESETS = {", 1)[1].split("};", 1)[0]
        self.assertEqual(len(re.findall(r"^\s+[A-Za-z0-9_]+:\s+\{ label:", theme_block, re.MULTILINE)), 10)
        self.assertNotIn("midnight", app_js + index_html)
        self.assertNotIn("午" + "夜蓝", app_js + index_html)

        for token in ("batch-toolbar", "preview-watermark", "data-density", "panel-in", "hint-pill.strong", "confirm-dialog", "history-panel", "import-result"):
            self.assertIn(token, css)



    def test_page_uses_native_module_split_and_compat_bootstrap(self):
        page_dir = Path("pages/menu-editor")
        index_html = (page_dir / "index.html").read_text(encoding="utf-8")
        app_js = (page_dir / "app.js").read_text(encoding="utf-8")

        for module_name in (
            "runtime.js",
            "state.js",
            "api.js",
            "preview.js",
            "modal.js",
            "background.js",
            "validation.js",
            "shortcuts.js",
        ):
            self.assertTrue((page_dir / module_name).is_file())
            self.assertIn(f'src="./{module_name}" defer', index_html)

        self.assertIn('src="./app.js?v=20260621-fonts" defer', index_html)
        self.assertNotIn('<script type="module" src="./app.js"', index_html)
        self.assertNotIn("await resolvePageBridge();", app_js.split("function initializeEditor", 1)[0])
        self.assertIn("function cloneData", app_js)
        self.assertIn("editorRuntime.cloneData", app_js)
        self.assertIn("createPendingBackgroundAsset", app_js)
        self.assertIn("flushPendingBackgroundAsset", app_js)


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
            self.assertIsNotNone(storage.get_menu_including_deleted("main"))

    def test_save_persists_complete_page_snapshot_for_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            saved = storage.save_menu(
                {
                    "id": "snapshot",
                    "name": "Snapshot Menu",
                    "title": "Saved Title",
                    "subtitle": "Saved Subtitle",
                    "footer": "Saved Footer",
                    "style": {
                        "theme": "macaron",
                        "primary_color": "#2563eb",
                        "background_color": "#fef3c7",
                        "background_image": "data:image/png;base64,AAAA",
                        "background_image_asset_id": "asset-complete",
                        "background_image_name": "moved-bg.png",
                        "background_image_x": 17,
                        "background_image_y": -43,
                        "background_image_width": 188,
                        "background_overlay": 37,
                        "background_blur": 6,
                        "background_brightness": 132,
                        "card_color": "#f1f5f9",
                        "text_color": "#020617",
                        "muted_color": "#475569",
                        "font_family": "Noto Sans CJK SC",
                        "foreground_opacity": 64,
                        "radius": 9,
                        "width_mode": "custom",
                        "width": 820,
                        "columns": 3,
                        "section_gap_mode": "custom",
                        "section_gap": 0,
                        "card_gap": 7,
                        "section_padding": 13,
                        "shadow_strength": 4,
                        "border_strength": 3,
                        "watermark": "demo mark",
                        "show_updated_at": False,
                    },
                    "sections": [
                        {
                            "title": "Saved Section",
                            "items": [
                                {
                                    "label": "Saved Card",
                                    "command": "/saved",
                                    "description": "Saved Description",
                                    "icon": "★",
                                    "enabled": False,
                                    "card_size": "banner",
                                    "content_order": ["description", "label", "command"],
                                    "content_gap": 9,
                                    "command_font_size": 18,
                                    "label_font_size": 13.5,
                                    "description_font_size": 10,
                                }
                            ],
                        }
                    ],
                }
            )
            reloaded = storage.get_menu("snapshot")
            self.assertEqual(reloaded, saved)
            style = reloaded["style"]
            self.assertEqual(style["background_image_y"], -43)
            self.assertEqual(style["background_image_x"], 17)
            self.assertEqual(style["background_image_width"], 188)
            self.assertEqual(style["card_gap"], 7)
            self.assertEqual(style["section_padding"], 13)
            self.assertFalse(style["show_updated_at"])
            item = reloaded["sections"][0]["items"][0]
            self.assertEqual(item["content_order"], ["description", "label", "command"])
            self.assertEqual(item["content_gap"], 9)
            self.assertFalse(item["enabled"])

            preview_html = build_preview_html(reloaded)
            render_template, render_data, render_options = build_render_payload(reloaded)
            self.assertEqual(render_template, preview_html)
            self.assertEqual(render_data, {})
            self.assertEqual(render_options["type"], "png")
            self.assertIn("left:17%;top:-43%;width:188%", render_template)
            self.assertIn("--preview-card-gap:7px", render_template)
            self.assertIn("--preview-section-padding:13px", render_template)
            self.assertIn("--preview-bg-overlay:0.370", render_template)
            self.assertIn("--item-content-gap:9px", render_template)
            self.assertIn('class="preview-item size-banner disabled"', render_template)

    def test_storage_resolves_aliases_and_restores_soft_deleted_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            storage.save_menu(
                {
                    "id": "admin",
                    "name": "管理菜单",
                    "aliases": ["管理", "tools"],
                    "sections": [{"title": "功能", "items": [{"label": "帮助"}]}],
                }
            )
            self.assertEqual(storage.resolve_menu("管理")["id"], "admin")
            storage.delete_menu("admin")
            self.assertIsNone(storage.resolve_menu("管理"))
            restored = storage.restore_menu("admin")
            self.assertEqual(restored["id"], "admin")
            self.assertEqual(storage.resolve_menu("tools")["id"], "admin")

    def test_asset_storage_deduplicates_and_tracks_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AssetStorage(tmp)
            data_url = "data:image/png;base64,iVBORw0KGgo="
            first = storage.save_data_url(data_url, name="bg.png")
            second = storage.save_data_url(data_url, name="again.png")
            self.assertEqual(first["id"], second["id"])
            menus = [{"id": "main", "style": {"background_image_asset_id": first["id"]}}]
            assets = storage.list_assets(menus)
            self.assertEqual(assets[0]["references"], ["main"])
            with self.assertRaises(MenuValidationError):
                storage.delete_asset(first["id"], menus)

    def test_history_snapshot_restore_and_routing_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = MenuHistoryStorage(tmp)
            menu = normalize_menu({"id": "main", "title": "旧标题", "sections": [{"title": "功能", "items": [{"label": "帮助"}]}]})
            snapshot = history.snapshot(menu, reason="save")
            self.assertEqual(history.restore_snapshot("main", snapshot["id"])["title"], "旧标题")

            routing = RoutingStorage(tmp)
            routing.save_rules(
                {
                    "global_default": "main",
                    "platforms": {"telegram": "tg"},
                    "contexts": {"aiocqhttp:10001": "group-menu", "10002": "plain-group"},
                }
            )
            self.assertEqual(routing.resolve_default(platform="aiocqhttp", group_id="10001", global_default="default"), "group-menu")
            self.assertEqual(routing.resolve_default(platform="telegram", group_id="", global_default="default"), "tg")
            self.assertEqual(routing.resolve_default(platform="qq", group_id="", global_default="default"), "main")

    def test_import_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menus = storage.import_menus(
                [{"id": "imported", "sections": [{"title": "功能", "items": [{"label": "帮助"}]}]}],
                mode="replace",
            )
            self.assertEqual([menu["id"] for menu in menus], ["imported"])

    def test_import_merge_returns_active_menus_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            storage.save_menu({"id": "old", "sections": [{"title": "功能", "items": [{"label": "帮助"}]}]})
            storage.delete_menu("old")
            menus = storage.import_menus(
                [{"id": "new", "sections": [{"title": "功能", "items": [{"label": "菜单"}]}]}],
                mode="merge",
            )
            self.assertEqual({menu["id"] for menu in menus}, {"default", "new"})
            self.assertEqual([menu["id"] for menu in storage.list_deleted_menus()], ["old"])

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

    def test_render_cache_uses_fingerprinted_paths_for_layout_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            cache = MenuRenderCache(tmp)
            first_render = render_menu_image(menu, tmp)
            first_cached = cache.store_rendered(menu, first_render, render_width=900, render_scale=4)

            changed_menu = normalize_menu(
                {
                    **menu,
                    "style": {
                        **menu["style"],
                        "width_mode": "custom",
                        "width": 720,
                        "columns": 1,
                        "section_gap_mode": "custom",
                        "section_gap": 0,
                        "card_gap": 2,
                    },
                }
            )
            self.assertIsNone(cache.get_cached_path(changed_menu, render_width=900, render_scale=4))
            second_render = render_menu_image(changed_menu, tmp)
            second_cached = cache.store_rendered(changed_menu, second_render, render_width=900, render_scale=4)

            self.assertNotEqual(first_cached, second_cached)
            self.assertIn(cache.fingerprint(changed_menu, render_width=900, render_scale=4)[:16], Path(second_cached).name)
            self.assertEqual(cache.get_cached_path(changed_menu, render_width=900, render_scale=4), second_cached)
            self.assertIsNone(cache.get_cached_path(menu, render_width=900, render_scale=4))
            self.assertFalse(Path(first_cached).exists())

    def test_render_cache_fingerprint_tracks_every_style_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            cache = MenuRenderCache(tmp)
            base_fingerprint = cache.fingerprint(menu, render_width=900, render_scale=4)
            data_url = "data:image/png;base64,iVBORw0KGgo="
            replacements = {
                "theme": "macaron",
                "primary_color": "#2563eb",
                "background_color": "#fef3c7",
                "background_image": data_url,
                "background_image_asset_id": "asset-style-test",
                "background_image_name": "bg-test.png",
                "background_image_x": 12,
                "background_image_y": -18,
                "background_image_width": 160,
                "background_overlay": 35,
                "background_blur": 8,
                "background_brightness": 135,
                "card_color": "#f1f5f9",
                "text_color": "#020617",
                "muted_color": "#475569",
                "font_family": "Noto Sans CJK SC",
                "foreground_opacity": 61,
                "radius": 8,
                "width_mode": "custom",
                "width": 980,
                "columns": 3,
                "section_gap_mode": "custom",
                "section_gap": 0,
                "card_gap": 26,
                "section_padding": 32,
                "shadow_strength": 4,
                "border_strength": 3,
                "watermark": "demo",
                "show_updated_at": False,
            }
            self.assertEqual(set(DEFAULT_STYLE), set(replacements))
            for key, value in replacements.items():
                changed_menu = normalize_menu({**menu, "style": {**menu["style"], key: value}})
                with self.subTest(style_key=key):
                    self.assertNotEqual(
                        base_fingerprint,
                        cache.fingerprint(changed_menu, render_width=900, render_scale=4),
                    )

    def test_render_status_reports_missing_rendering_ready_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            cache = MenuRenderCache(tmp)
            missing = cache.get_status(menu, render_width=900, render_scale=4)
            self.assertEqual(missing["status"], "missing")
            self.assertIn("fingerprint", missing)

            cache.mark_rendering(menu, render_width=900, render_scale=4)
            rendering = cache.get_status(menu, render_width=900, render_scale=4)
            self.assertEqual(rendering["status"], "rendering")
            self.assertEqual(rendering["attempts"], 1)

            rendered_path = render_menu_image(menu, tmp)
            cache.store_rendered(menu, rendered_path, render_width=900, render_scale=4)
            ready = cache.get_status(menu, render_width=900, render_scale=4)
            self.assertEqual(ready["status"], "ready")
            self.assertIsNotNone(ready["rendered_at"])
            self.assertGreater(ready["cache_size"], 0)

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
        self.assertIn("self.storage.resolve_menu(menu_id)", main_py)
        self.assertIn('command.casefold() == "list"', main_py)
        self.assertIn('command.casefold() == "search"', main_py)
        self.assertIn('command.casefold() == "refresh"', main_py)
        self.assertIn("assets/<asset_id>", main_py)
        self.assertIn("api_list_fonts", main_py)
        self.assertIn("/fonts", main_py)
        self.assertIn("menus/history/<menu_id>", main_py)
        self.assertIn("menus/render-refresh", main_py)
        self.assertIn("routing", main_py)

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

    def test_pillow_renderer_uses_spacing_and_visual_style_fields(self):
        from PIL import Image

        base_menu = normalize_menu(
            {
                "id": "spacing",
                "style": {"width_mode": "custom", "width": 760, "columns": 2, "show_updated_at": False},
                "sections": [
                    {
                        "title": "功能",
                        "items": [
                            {"label": "帮助", "command": "/help", "description": "查看帮助"},
                            {"label": "菜单", "command": "/menu", "description": "查看菜单"},
                            {"label": "状态", "command": "/status", "description": "查看状态"},
                        ],
                    }
                ],
            }
        )
        spacious_menu = normalize_menu(
            {
                **base_menu,
                "style": {
                    **base_menu["style"],
                    "card_gap": 60,
                    "section_padding": 60,
                    "shadow_strength": 5,
                    "border_strength": 4,
                    "background_overlay": 40,
                    "background_brightness": 150,
                    "background_blur": 4,
                    "watermark": "demo",
                },
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            base_path = render_menu_image(base_menu, tmp, output_scale=1)
            spacious_path = render_menu_image(spacious_menu, tmp, output_scale=1)
            with Image.open(base_path) as base_image, Image.open(spacious_path) as spacious_image:
                self.assertEqual(base_image.width, spacious_image.width)
                self.assertGreater(spacious_image.height, base_image.height)
                self.assertNotEqual(base_image.tobytes(), spacious_image.tobytes())

    def test_release_metadata_readme_changelog_and_logo_are_consistent(self):
        import re

        metadata = Path("metadata.yaml").read_text(encoding="utf-8")
        readme = Path("README.md").read_text(encoding="utf-8")
        changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
        version = re.search(r"^version:\s*(.+)$", metadata, re.MULTILINE).group(1)
        author = re.search(r"^author:\s*(.+)$", metadata, re.MULTILINE).group(1)
        self.assertEqual(version, "0.5.0")
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

    def test_playwright_missing_browser_error_is_detected(self):
        error = RuntimeError(
            "BrowserType.launch: Executable doesn't exist at "
            "/root/.cache/ms-playwright/chromium_headless_shell-1123/chrome-linux/headless_shell\n"
            "Please run the following command: playwright install"
        )
        self.assertTrue(_playwright_error_looks_like_missing_browser(error))
        self.assertFalse(_playwright_error_looks_like_missing_browser(RuntimeError("navigation timeout")))

    def test_playwright_chromium_installer_runs_playwright_install(self):
        import subprocess
        from unittest.mock import patch

        import services.local_image as local_image

        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"installed", stderr=b"")
        with (
            patch.object(local_image, "_PLAYWRIGHT_CHROMIUM_INSTALL_ATTEMPTED", False),
            patch.object(local_image.subprocess, "run", return_value=completed) as run,
        ):
            installed, detail = local_image._install_playwright_chromium()

        self.assertTrue(installed)
        self.assertIn("installed", detail)
        run.assert_called_once_with(
            [local_image.sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            timeout=300,
        )

    def test_browser_render_auto_installs_missing_playwright_chromium_once(self):
        from unittest.mock import patch

        import services.local_image as local_image

        calls: list[str] = []

        def fake_playwright_render(_html, screenshot_path, **_kwargs):
            calls.append(str(screenshot_path))
            if len(calls) == 1:
                raise RuntimeError(
                    "BrowserType.launch: Executable doesn't exist at "
                    "/root/.cache/ms-playwright/chromium_headless_shell-1123/chrome-linux/headless_shell"
                )
            Path(screenshot_path).write_bytes(b"\x89PNG\r\n\x1a\nfake")

        with tempfile.TemporaryDirectory() as tmp:
            storage = MenuStorage(tmp)
            menu = storage.get_menu("default")
            html = build_preview_html(menu)
            with (
                patch.object(local_image, "_render_menu_via_playwright", side_effect=fake_playwright_render),
                patch.object(local_image, "_install_playwright_chromium", return_value=(True, "installed")) as install,
                patch.object(local_image, "_find_browser_executable") as find_browser,
            ):
                path = local_image.render_menu_via_browser(menu, tmp, html)
                self.assertTrue(Path(path).is_file())

        self.assertEqual(len(calls), 2)
        install.assert_called_once()
        find_browser.assert_not_called()

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
            parser = _PreviewCardStyleParser()
            parser.feed(html)
            self.assertIn("--preview-font-family:", parser.style)
            self.assertIn(f"--preview-width:{width}px", parser.style)
            self.assertIn("--preview-columns:2", parser.style)
            self.assertIn("--preview-foreground-opacity:0.920", parser.style)
            self.assertIn('class="preview-inner"', html)
            self.assertIn('class="preview-item size-standard', html)
            self.assertIn('class="preview-icon"', html)
            self.assertIn('class="preview-item-main"', html)
            command_index = html.index('class="preview-item-title preview-command-title"')
            title_index = html.index('class="preview-item-name"')
            desc_index = html.index('class="preview-desc"')
            self.assertLess(command_index, title_index)
            self.assertLess(title_index, desc_index)
            self.assertIn("实时预览", html)
            self.assertNotIn("更新：", html)

    def test_preview_html_uses_custom_card_content_layout(self):
        menu = normalize_menu(
            {
                "id": "cardlayout",
                "sections": [
                    {
                        "title": "功能",
                        "items": [
                            {
                                "label": "帮助",
                                "command": "/help",
                                "description": "查看帮助",
                                "content_order": ["description", "label", "command"],
                                "content_gap": 8,
                                "command_font_size": 18,
                                "label_font_size": 13.5,
                                "description_font_size": 10,
                            }
                        ],
                    }
                ],
            }
        )
        html = build_preview_html(menu)
        desc_index = html.index('class="preview-desc"')
        title_index = html.index('class="preview-item-name"')
        command_index = html.index('class="preview-item-title preview-command-title"')
        self.assertLess(desc_index, title_index)
        self.assertLess(title_index, command_index)
        self.assertIn("--item-content-gap:8px", html)
        self.assertIn("--item-command-size:18px", html)
        self.assertIn("--item-label-size:13.5px", html)
        self.assertIn("--item-description-size:10px", html)

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

    def test_preview_html_uses_v040_style_fields(self):
        menu = normalize_menu(
            {
                "id": "ops",
                "style": {
                    "font_family": "Noto Sans CJK SC",
                    "card_gap": 6,
                    "section_padding": 12,
                    "shadow_strength": 2,
                    "border_strength": 3,
                    "background_overlay": 15,
                    "background_blur": 4,
                    "background_brightness": 88,
                    "watermark": "demo",
                },
                "sections": [{"title": "功能", "items": [{"label": "帮助"}]}],
            }
        )
        html = build_preview_html(menu)
        self.assertIn("--preview-font-family:", html)
        self.assertIn("--preview-card-gap:6px", html)
        self.assertIn("--preview-section-padding:12px", html)
        self.assertIn("--preview-shadow-strength:2", html)
        self.assertIn("var(--preview-shadow-strength, 1)", html)
        self.assertIn("--preview-border-strength:3", html)
        self.assertIn("--preview-bg-overlay:0.150", html)
        self.assertIn("--preview-bg-blur:4px", html)
        self.assertIn("--preview-bg-brightness:0.880", html)
        self.assertIn('class="preview-watermark"', html)

    def test_font_registry_lists_user_fonts_by_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            font_path = Path(tmp) / "fonts" / "brand" / "DemoFont.ttf"
            font_path.parent.mkdir(parents=True)
            font_path.write_bytes(b"demo-font")

            registry = FontRegistry(tmp)
            fonts = registry.list_fonts()

            self.assertEqual(len(fonts), 1)
            self.assertEqual(fonts[0].name, "DemoFont")
            self.assertEqual(fonts[0].relative_path, "brand/DemoFont.ttf")
            self.assertNotIn(str(Path(tmp)), fonts[0].as_dict()["relative_path"])
            self.assertIsNotNone(registry.resolve("brand/DemoFont.ttf"))
            self.assertIsNotNone(registry.resolve("DemoFont"))

    def test_preview_html_embeds_selected_user_font_face(self):
        with tempfile.TemporaryDirectory() as tmp:
            font_path = Path(tmp) / "fonts" / "DemoFont.woff2"
            font_path.parent.mkdir(parents=True)
            font_path.write_bytes(b"demo-font")
            registry = FontRegistry(tmp)
            menu = normalize_menu(
                {
                    "id": "font",
                    "style": {"font_family": "DemoFont"},
                    "sections": [{"title": "鍔熻兘", "items": [{"label": "甯姪"}]}],
                }
            )

            html = build_preview_html(menu, font_registry=registry)

            self.assertIn("@font-face", html)
            self.assertIn("data:font/woff2;base64,", html)
            self.assertIn("BotMenuUserFont-", html)
            self.assertNotIn(str(Path(tmp)), html)

    def test_render_cache_fingerprint_changes_when_selected_font_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            font_path = Path(tmp) / "fonts" / "DemoFont.ttf"
            font_path.parent.mkdir(parents=True)
            font_path.write_bytes(b"demo-font-1")
            cache = MenuRenderCache(tmp)
            menu = normalize_menu(
                {
                    "id": "fontcache",
                    "style": {"font_family": "DemoFont"},
                    "sections": [{"title": "鍔熻兘", "items": [{"label": "甯姪"}]}],
                }
            )
            first = cache.fingerprint(menu, render_width=900, render_scale=4)

            font_path.write_bytes(b"demo-font-2-changed")
            second = cache.fingerprint(menu, render_width=900, render_scale=4)

            self.assertNotEqual(first, second)

    def test_page_reload_does_not_realign_saved_background_to_top(self):
        app_js = Path("pages/menu-editor/app.js").read_text(encoding="utf-8")
        index_html = Path("pages/menu-editor/index.html").read_text(encoding="utf-8")
        css = Path("pages/menu-editor/style.css").read_text(encoding="utf-8")
        renderer_py = Path("services/renderer.py").read_text(encoding="utf-8")
        self.assertNotIn("fitBackgroundToCover(false)", app_js)
        self.assertIn("fitBackgroundToCover(true)", app_js)
        self.assertIn("function backgroundTransformSnapshot(style)", app_js)
        self.assertIn("function backgroundTransformMatches(style, snapshot)", app_js)
        self.assertIn("if (expectedTransform && !backgroundTransformMatches(style, expectedTransform)) return;", app_js)
        self.assertIn("const transformBeforeLoad = expectedTransform || backgroundTransformSnapshot(style);", app_js)
        self.assertIn('img.addEventListener("load", () => fitBackgroundToCover(forceReset, transformBeforeLoad), { once: true });', app_js)
        self.assertNotIn('img.addEventListener("load", () => fitBackgroundToCover(forceReset), { once: true });', app_js)
        self.assertIn("const startStyle = ensureStyle(state.menu);", app_js)
        self.assertIn("function ensureStyle(menu)", app_js)
        self.assertIn("Object.entries(defaults).forEach", app_js)
        self.assertNotIn("menu.style = { ...defaultStyle(), ...(menu.style || {}) };", app_js)
        self.assertIn("./app.js?v=20260621-fonts", index_html)
        self.assertIn('style="${escapeAttr(previewStyle)}"', app_js)
        self.assertIn('const DEFAULT_FONT_STACK_CSS', app_js)
        self.assertIn('await loadFonts();', app_js)
        self.assertIn('bridge.apiGet("fonts")', app_js)
        self.assertIn("function fontFamilyCss(value)", app_js)
        self.assertIn(".preview-title { margin: 12px 0 4px; font-size: 34px; line-height: 1.1; }", css)
        self.assertIn("font-size: 12px;", renderer_py)
        self.assertIn("padding: 18px;", renderer_py)
        self.assertIn("padding: 16px;", renderer_py)
        self.assertIn(".preview-section h3 {{ margin: 0 0 10px; }}", renderer_py)

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
