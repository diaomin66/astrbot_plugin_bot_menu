from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .services import (
    AssetStorage,
    MenuHistoryStorage,
    MenuStorage,
    MenuRenderCache,
    MenuRenderCoordinator,
    MenuValidationError,
    FontRegistry,
    RoutingStorage,
    build_preview_html,
    materialize_saved_preview_raster,
    render_menu_via_typst,
)

PLUGIN_NAME = "astrbot_plugin_bot_menu"
logger = logging.getLogger("astrbot")

try:
    from astrbot.api.web import (
        error_response as _astrbot_error_response,
        json_response as _astrbot_json_response,
        request as _astrbot_request,
    )
except ModuleNotFoundError:
    _astrbot_request = None

    from quart import jsonify, request as _quart_request

    def json_response(
        data: Any = None,
        *,
        status_code: int = 200,
    ):
        response = jsonify({"status": "ok", "data": {} if data is None else data})
        response.status_code = status_code
        return response

    def error_response(
        message: str,
        *,
        status_code: int = 400,
        data: Any = None,
    ):
        # AstrBot 4.25.x's plugin-page bridge reads the JSON error envelope
        # from successful HTTP responses.  Returning 4xx here makes axios
        # reject before the bridge can forward the actual message.
        return jsonify({"status": "error", "message": message, "data": data})

    async def read_json_body(default: Any = None) -> Any:
        try:
            payload = await _quart_request.get_json(silent=True)
        except Exception:
            return default
        return default if payload is None else payload

else:

    def json_response(
        data: Any = None,
        *,
        status_code: int = 200,
    ):
        return _astrbot_json_response(data, status_code=status_code)

    def error_response(
        message: str,
        *,
        status_code: int = 400,
        data: Any = None,
    ):
        return _astrbot_error_response(message, status_code=status_code, data=data)

    async def read_json_body(default: Any = None) -> Any:
        return await _astrbot_request.json(default=default)


class BotMenuPlugin(Star):
    """自定义 Bot 菜单插件。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        self.config = config or {}
        self.storage = MenuStorage(self._resolve_data_dir())
        self.assets = AssetStorage(self.storage.data_dir)
        self.history = MenuHistoryStorage(self.storage.data_dir)
        self.routing = RoutingStorage(self.storage.data_dir)
        self.fonts = FontRegistry(self.storage.data_dir)
        self.render_cache = MenuRenderCache(self.storage.data_dir)
        self.render_coordinator = MenuRenderCoordinator(
            storage=self.storage,
            cache=self.render_cache,
            render_menu=self._render_menu_for_cache,
            render_width=lambda: self._config_int("render_width", 900),
            render_scale=lambda: max(1, min(4, self._config_int("render_scale", 4))),
            render_engine=self._render_cache_engine,
            logger=logger,
        )
        self._register_web_apis(context)
        self.render_coordinator.schedule_prewarm()

    @filter.command("menu", alias={"菜单"})
    async def show_menu(self, event: AstrMessageEvent, menu_id: str = "", keyword: str = ""):
        """显示机器人菜单图片。用法：/menu、/menu <ID|别名>、/menu list/search/refresh。"""
        command = (menu_id or "").strip()
        try:
            if command.casefold() == "list":
                yield event.plain_result(self._format_menu_list())
                return
            if command.casefold() == "search":
                term = (keyword or "").strip()
                yield event.plain_result(self._search_menu_items(term))
                return
            if command.casefold() == "refresh":
                target = (keyword or "").strip() or self._effective_default_menu_id(event)
                menu = self.storage.resolve_menu(target)
                if not menu:
                    yield event.plain_result(f"未找到菜单方案：{target}")
                    return
                self.render_coordinator.schedule(menu, force=True)
                yield event.plain_result(f"已提交菜单缓存刷新：{menu['id']}")
                return

            menu_id = command or self._effective_default_menu_id(event)
            menu = self.storage.resolve_menu(menu_id)
            if not menu:
                available = ", ".join(menu["id"] for menu in self.storage.list_menus())
                yield event.plain_result(f"未找到菜单方案：{menu_id}\n可用方案：{available}")
                return
            cached_path = self.render_coordinator.get_cached_path(menu)
            if cached_path:
                yield event.image_result(cached_path)
                return
            self.render_coordinator.schedule(menu)
            yield event.plain_result("菜单图片缓存正在后台生成，请稍后再试。")
        except Exception as exc:  # noqa: BLE001 - plugin should degrade gracefully in chat
            logger.exception("Bot menu render failed")
            if self._config_bool("show_render_error_detail", False):
                yield event.plain_result(f"菜单渲染失败：{exc}")
            else:
                yield event.plain_result("菜单渲染失败，请稍后重试或联系管理员。")

    async def api_list_menus(self):
        return json_response(
            {
                "menus": self.storage.list_menus(),
                "deleted_menus": self.storage.list_deleted_menus(),
                "default_menu_id": self._effective_default_menu_id(),
            }
        )

    async def api_get_menu(self, menu_id: str):
        menu = self.storage.get_menu(menu_id)
        if not menu:
            return error_response(f"menu not found: {menu_id}", status_code=404)
        return json_response({"menu": menu})

    async def api_save_menu(self):
        payload = await read_json_body(default={})
        if not isinstance(payload, dict) or not isinstance(payload.get("menu"), dict):
            return error_response("missing complete menu payload", status_code=400)
        raw_menu = payload["menu"]
        try:
            existing = self.storage.get_menu_including_deleted(str(raw_menu.get("id", "")).strip())
            self.history.snapshot(existing, reason="save")
            menu = self.storage.save_menu(raw_menu)
            if not await self._store_saved_typst_preview_cache(menu):
                self.render_coordinator.schedule(menu)
            return json_response({"menu": menu, "menus": self.storage.list_menus()})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_render_status(self, menu_id: str):
        status = self.render_coordinator.status_for_menu_id(str(menu_id or "").strip())
        if status is None:
            return error_response(f"menu not found: {menu_id}", status_code=404)
        return json_response(status)

    async def api_delete_menu(self):
        payload = await read_json_body(default={})
        menu_id = str(payload.get("id", "")).strip() if isinstance(payload, dict) else ""
        permanent = bool(payload.get("permanent")) if isinstance(payload, dict) else False
        if not menu_id:
            return error_response("missing menu id", status_code=400)
        try:
            self.history.snapshot(self.storage.get_menu(menu_id), reason="delete")
            if permanent:
                self.storage.permanent_delete_menu(menu_id)
            else:
                self.storage.delete_menu(menu_id)
            return json_response(
                {
                    "deleted": True,
                    "menus": self.storage.list_menus(),
                    "deleted_menus": self.storage.list_deleted_menus(),
                    "default_menu_id": self._effective_default_menu_id(),
                }
            )
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_export_menus(self):
        data = self.storage.export_data()
        assets: list[dict[str, Any]] = []
        for asset in self.assets.list_assets(self.storage.list_menus()):
            try:
                assets.append({**asset, "data_url": self.assets.data_url_for_asset(asset["id"])})
            except MenuValidationError:
                assets.append(asset)
        data["assets"] = assets
        data["asset_bundle"] = "inline"
        return json_response(data)

    async def api_import_menus(self):
        payload = await read_json_body(default={})
        try:
            if isinstance(payload, dict):
                raw_menus = payload.get("menus")
                mode = str(payload.get("mode", "merge"))
                for asset in payload.get("assets") or []:
                    if isinstance(asset, dict) and asset.get("data_url"):
                        self.assets.save_data_url(str(asset.get("data_url")), name=str(asset.get("name") or ""))
            else:
                raw_menus = payload
                mode = "merge"
            raw_import_count = len(raw_menus) if isinstance(raw_menus, list) else 0
            imported_menus = self.storage.import_menus(raw_menus, mode=mode)
            active_menus = self.storage.list_menus()
            active_ids = {menu["id"] for menu in active_menus}
            for menu in active_menus:
                self.render_coordinator.schedule(menu)
            return json_response(
                {
                    "menus": active_menus,
                    "deleted_menus": self.storage.list_deleted_menus(),
                    "default_menu_id": self._effective_default_menu_id(),
                    "imported_count": raw_import_count,
                    "active_imported_count": sum(1 for menu in imported_menus if menu["id"] in active_ids),
                }
            )
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_list_assets(self):
        assets = []
        for asset in self.assets.list_assets(self.storage.list_menus()):
            try:
                asset = {**asset, "data_url": self.assets.data_url_for_asset(asset["id"])}
            except MenuValidationError:
                pass
            assets.append(asset)
        return json_response({"assets": assets})

    async def api_list_fonts(self):
        return json_response(
            {
                "fonts_dir": "fonts",
                "fonts": [font.as_dict() for font in self.fonts.list_fonts()],
                "css": self.fonts.css_for_all(),
            }
        )

    async def api_save_asset(self):
        payload = await read_json_body(default={})
        try:
            if not isinstance(payload, dict):
                raise MenuValidationError("asset payload must be an object")
            asset = self.assets.save_data_url(str(payload.get("data_url") or ""), name=str(payload.get("name") or ""))
            return json_response({"asset": asset, "assets": self.assets.list_assets(self.storage.list_menus())})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_delete_asset(self, asset_id: str):
        try:
            deleted = self.assets.delete_asset(str(asset_id or "").strip(), self.storage.list_menus())
            return json_response({"deleted": deleted, "assets": self.assets.list_assets(self.storage.list_menus())})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_menu_history(self, menu_id: str):
        return json_response({"history": self.history.list_history(str(menu_id or "").strip())})

    async def api_restore_menu(self):
        payload = await read_json_body(default={})
        try:
            menu_id = str(payload.get("menu_id") or payload.get("id") or "").strip() if isinstance(payload, dict) else ""
            snapshot_id = str(payload.get("snapshot_id") or "").strip() if isinstance(payload, dict) else ""
            if not menu_id:
                raise MenuValidationError("missing menu id")
            if payload.get("deleted") if isinstance(payload, dict) else False:
                menu = self.storage.restore_menu(menu_id)
                self.render_coordinator.schedule(menu, force=True)
                return json_response({"menu": menu, "menus": self.storage.list_menus(), "deleted_menus": self.storage.list_deleted_menus()})
            restored = self.history.restore_snapshot(menu_id, snapshot_id or None)
            self.history.snapshot(self.storage.get_menu_including_deleted(menu_id), reason="restore")
            menu = self.storage.save_menu(restored)
            self.render_coordinator.schedule(menu, force=True)
            return json_response({"menu": menu, "menus": self.storage.list_menus()})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_reorder_menus(self):
        payload = await read_json_body(default={})
        ordered_ids = payload.get("ids") if isinstance(payload, dict) else None
        if not isinstance(ordered_ids, list):
            return error_response("ids must be a list", status_code=400)
        menus = self.storage.reorder_menus([str(menu_id).strip() for menu_id in ordered_ids])
        return json_response({"menus": menus})

    async def api_get_routing(self):
        return json_response({"routing": self.routing.get_rules()})

    async def api_save_routing(self):
        payload = await read_json_body(default={})
        if not isinstance(payload, dict):
            return error_response("routing payload must be an object", status_code=400)
        routing = self.routing.save_rules(payload.get("routing") if isinstance(payload.get("routing"), dict) else payload)
        return json_response({"routing": routing})

    async def api_render_refresh(self):
        payload = await read_json_body(default={})
        target = str(payload.get("id") or payload.get("menu_id") or "").strip() if isinstance(payload, dict) else ""
        menus = [self.storage.resolve_menu(target)] if target else self.storage.list_menus()
        scheduled: list[str] = []
        for menu in menus:
            if not menu:
                continue
            self.render_coordinator.schedule(menu, force=True)
            scheduled.append(menu["id"])
        return json_response({"scheduled": scheduled})

    async def api_cleanup(self):
        menus = self.storage.list_menus()
        cache = self.render_cache.cleanup({menu["id"] for menu in menus})
        assets = self.assets.cleanup_unused(menus)
        return json_response({"cache": cache, "assets": assets})

    async def _render_menu_for_cache(self, menu: dict[str, Any]) -> str:
        return await self._render_menu_uncached(menu)

    async def _store_saved_typst_preview_cache(self, menu: dict[str, Any]) -> bool:
        if self._render_cache_engine() != "typst":
            return False
        render_width = self._config_int("render_width", 900)
        render_scale = max(1, min(4, self._config_int("render_scale", 4)))
        source_path = await asyncio.to_thread(
            materialize_saved_preview_raster,
            menu,
            self.storage.data_dir,
            output_scale=render_scale,
        )
        if not source_path:
            return False
        try:
            self.render_cache.store_rendered(
                menu,
                source_path,
                render_width=render_width,
                render_scale=render_scale,
                render_engine="typst",
            )
            return True
        except Exception:
            logger.exception("Bot menu saved preview raster cache failed: %s", menu.get("id"))
            return False
        finally:
            try:
                Path(source_path).unlink(missing_ok=True)
            except Exception:
                logger.debug("failed to remove temporary saved preview raster: %s", source_path, exc_info=True)

    async def _render_menu_uncached(self, menu: dict[str, Any], *, render_mode: str | None = None) -> str:
        menu = self._menu_with_resolved_assets(menu)
        default_width = self._config_int("render_width", 900)
        render_scale = max(1, min(4, self._config_int("render_scale", 4)))
        render_mode = (render_mode or self._render_cache_engine()).strip().lower()
        if render_mode != "typst":
            logger.warning("Unsupported render_mode=%s ignored; Typst is the only render path", render_mode)

        return await asyncio.to_thread(
            render_menu_via_typst,
            menu,
            self.storage.data_dir,
            default_width=default_width,
            output_scale=render_scale,
            font_registry=self.fonts,
        )

    def _render_cache_engine(self) -> str:
        return "typst"

    def _register_web_apis(self, context: Context) -> None:
        routes = [
            (f"/{PLUGIN_NAME}/menus", self.api_list_menus, ["GET"], "List bot menus"),
            (f"/{PLUGIN_NAME}/menus/save", self.api_save_menu, ["POST"], "Save bot menu"),
            (f"/{PLUGIN_NAME}/menus/delete", self.api_delete_menu, ["POST"], "Delete bot menu"),
            (f"/{PLUGIN_NAME}/menus/render-status/<menu_id>", self.api_render_status, ["GET"], "Get bot menu render cache status"),
            (f"/{PLUGIN_NAME}/menus/history/<menu_id>", self.api_menu_history, ["GET"], "Get bot menu history"),
            (f"/{PLUGIN_NAME}/menus/restore", self.api_restore_menu, ["POST"], "Restore bot menu history"),
            (f"/{PLUGIN_NAME}/menus/reorder", self.api_reorder_menus, ["POST"], "Reorder bot menus"),
            (f"/{PLUGIN_NAME}/menus/render-refresh", self.api_render_refresh, ["POST"], "Refresh bot menu render cache"),
            (f"/{PLUGIN_NAME}/menus/<menu_id>", self.api_get_menu, ["GET"], "Get bot menu"),
            (f"/{PLUGIN_NAME}/assets", self.api_list_assets, ["GET"], "List bot menu assets"),
            (f"/{PLUGIN_NAME}/assets", self.api_save_asset, ["POST"], "Save bot menu asset"),
            (f"/{PLUGIN_NAME}/assets/<asset_id>", self.api_delete_asset, ["DELETE", "POST"], "Delete bot menu asset"),
            (f"/{PLUGIN_NAME}/fonts", self.api_list_fonts, ["GET"], "List bot menu fonts"),
            (f"/{PLUGIN_NAME}/routing", self.api_get_routing, ["GET"], "Get bot menu routing"),
            (f"/{PLUGIN_NAME}/routing", self.api_save_routing, ["POST"], "Save bot menu routing"),
            (f"/{PLUGIN_NAME}/cleanup", self.api_cleanup, ["POST"], "Clean bot menu cache and assets"),
            (f"/{PLUGIN_NAME}/export", self.api_export_menus, ["GET"], "Export bot menus"),
            (f"/{PLUGIN_NAME}/import", self.api_import_menus, ["POST"], "Import bot menus"),
        ]
        for route, handler, methods, desc in routes:
            context.register_web_api(route, handler, methods, desc)

    def _resolve_data_dir(self) -> Path:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            base = Path(get_astrbot_data_path())
        except Exception:  # pragma: no cover - only used outside AstrBot runtime
            base = Path.cwd() / "data"
        return base / "plugin_data" / PLUGIN_NAME

    def _format_menu_list(self) -> str:
        lines = ["可用菜单："]
        for menu in self.storage.list_menus():
            status = self.render_coordinator.status_for_menu(menu)
            aliases = ", ".join(menu.get("aliases") or [])
            suffix = f"；别名：{aliases}" if aliases else ""
            lines.append(f"- {menu['id']}｜{menu.get('name') or menu['id']}｜缓存：{status['status']}{suffix}")
        return "\n".join(lines)

    def _search_menu_items(self, keyword: str) -> str:
        term = str(keyword or "").strip().casefold()
        if not term:
            return "请提供搜索关键词，例如：/menu search 帮助"
        matches: list[str] = []
        for menu in self.storage.list_menus():
            for section in menu.get("sections", []):
                for item in section.get("items", []):
                    haystack = " ".join(
                        str(item.get(key) or "")
                        for key in ("label", "command", "description")
                    ).casefold()
                    if term not in haystack:
                        continue
                    command = f"｜{item.get('command')}" if item.get("command") else ""
                    matches.append(f"[{menu['id']}/{section.get('title')}] {item.get('label')}{command}\n{item.get('description') or ''}".strip())
                    if len(matches) >= 12:
                        return "搜索结果（前 12 条）：\n" + "\n".join(matches)
        return "没有找到匹配的菜单项。"

    def _effective_default_menu_id(self, event: AstrMessageEvent | None = None) -> str:
        platform, group_id = self._event_context(event)
        routed = self.routing.resolve_default(
            platform=platform,
            group_id=group_id,
            global_default=str(self._config_get("default_menu_id", "default") or "default").strip(),
        )
        if routed and self.storage.resolve_menu(routed):
            return self.storage.resolve_menu(routed)["id"]
        configured = str(self._config_get("default_menu_id", "default") or "default").strip()
        resolved = self.storage.resolve_menu(configured)
        if resolved:
            return resolved["id"]
        return self.storage.first_menu_id()

    def _event_context(self, event: AstrMessageEvent | None) -> tuple[str, str]:
        if event is None:
            return "", ""
        platform = ""
        group_id = ""
        for attr in ("get_platform_name", "get_platform"):
            getter = getattr(event, attr, None)
            if callable(getter):
                try:
                    platform = str(getter() or "")
                    break
                except Exception:
                    pass
        for attr in ("get_group_id", "get_session_id", "get_sender_id"):
            getter = getattr(event, attr, None)
            if callable(getter):
                try:
                    value = str(getter() or "")
                    if value:
                        group_id = value
                        break
                except Exception:
                    pass
        return platform, group_id

    def _menu_with_resolved_assets(self, menu: dict[str, Any]) -> dict[str, Any]:
        cloned = dict(menu)
        style = dict(cloned.get("style") or {})
        asset_id = str(style.get("background_image_asset_id") or "").strip()
        if asset_id and not style.get("background_image"):
            try:
                style["background_image"] = self.assets.data_url_for_asset(asset_id)
            except MenuValidationError:
                pass
        cloned["style"] = style
        return cloned

    def _config_get(self, key: str, default: Any = None) -> Any:
        getter = getattr(self.config, "get", None)
        if callable(getter):
            return getter(key, default)
        return default

    def _config_int(self, key: str, default: int) -> int:
        try:
            return int(self._config_get(key, default))
        except (TypeError, ValueError):
            return default

    def _config_bool(self, key: str, default: bool) -> bool:
        value = self._config_get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
