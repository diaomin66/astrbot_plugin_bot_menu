from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .services import (
    MenuStorage,
    MenuValidationError,
    build_preview_html,
    build_render_payload,
    image_file_to_data_url,
    normalize_menu,
    preview_width_for_menu,
    render_menu_image,
    render_menu_via_browser,
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
        self._register_web_apis(context)

    @filter.command("menu", alias={"菜单"})
    async def show_menu(self, event: AstrMessageEvent, menu_id: str = ""):
        """显示机器人菜单图片。用法：/menu 或 /menu <方案ID>。"""
        menu_id = (menu_id or "").strip() or self._effective_default_menu_id()
        try:
            menu = self.storage.get_menu(menu_id)
            if not menu:
                available = ", ".join(menu["id"] for menu in self.storage.list_menus())
                yield event.plain_result(f"未找到菜单方案：{menu_id}\n可用方案：{available}")
                return
            image_url = await self._render_menu(menu)
            yield event.image_result(image_url)
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
        raw_menu = payload.get("menu") if isinstance(payload, dict) else None
        if raw_menu is None:
            raw_menu = payload
        try:
            menu = self.storage.save_menu(raw_menu)
            return json_response({"menu": menu, "menus": self.storage.list_menus()})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_delete_menu(self):
        payload = await read_json_body(default={})
        menu_id = str(payload.get("id", "")).strip() if isinstance(payload, dict) else ""
        if not menu_id:
            return error_response("missing menu id", status_code=400)
        try:
            self.storage.delete_menu(menu_id)
            return json_response(
                {
                    "deleted": True,
                    "menus": self.storage.list_menus(),
                    "default_menu_id": self._effective_default_menu_id(),
                }
            )
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def api_preview_menu(self):
        payload = await read_json_body(default={})
        try:
            if isinstance(payload, dict) and isinstance(payload.get("menu"), dict):
                menu = normalize_menu(payload["menu"])
            else:
                menu_id = str(payload.get("id", "")).strip() if isinstance(payload, dict) else ""
                menu = self.storage.get_menu(menu_id or self._effective_default_menu_id())
                if not menu:
                    return error_response("menu not found", status_code=404)
            image_url = await self._render_menu(menu)
            return json_response({"url": self._preview_image_url(image_url)})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bot menu preview failed")
            return error_response(f"render failed: {exc}", status_code=500)

    async def api_export_menus(self):
        return json_response(self.storage.export_data())

    async def api_import_menus(self):
        payload = await read_json_body(default={})
        try:
            if isinstance(payload, dict):
                raw_menus = payload.get("menus")
                mode = str(payload.get("mode", "merge"))
            else:
                raw_menus = payload
                mode = "merge"
            menus = self.storage.import_menus(raw_menus, mode=mode)
            return json_response({"menus": menus})
        except MenuValidationError as exc:
            return error_response(str(exc), status_code=400)

    async def _render_menu(self, menu: dict[str, Any], *, render_mode: str | None = None) -> str:
        default_width = self._config_int("render_width", 900)
        render_scale = max(1, min(4, self._config_int("render_scale", 4)))
        if not render_mode:
            render_mode = str(self._config_get("render_mode", "browser") or "browser").strip().lower()

        if render_mode == "pillow":
            return render_menu_image(menu, self.storage.data_dir, default_width=default_width, output_scale=render_scale)

        if render_mode in {"browser", "local", "auto"}:  # local is fallback mapping to browser for old configs
            try:
                html_content = build_preview_html(menu, default_width=default_width)
                viewport_width = preview_width_for_menu(menu, default_width=default_width)
                return render_menu_via_browser(
                    menu,
                    self.storage.data_dir,
                    html_content,
                    default_width=default_width,
                    viewport_width=viewport_width,
                    device_scale_factor=render_scale,
                )
            except Exception as exc:
                import traceback
                if render_mode == "auto":
                    logger.warning("Local browser rendering failed, falling back to remote HTML render: %s\n%s", exc, traceback.format_exc())
                else:
                    logger.warning("Local browser rendering failed, falling back to Pillow PNG: %s\n%s", exc, traceback.format_exc())
                    return render_menu_image(menu, self.storage.data_dir, default_width=default_width, output_scale=render_scale)

        template, data, options = build_render_payload(menu, default_width=default_width)
        try:
            return await self.html_render(template, data, return_url=True, options=options)
        except Exception as exc:
            if render_mode == "remote":
                raise
            logger.warning("Remote menu rendering failed, falling back to Pillow PNG: %s", exc)
            return render_menu_image(menu, self.storage.data_dir, default_width=default_width, output_scale=render_scale)

    def _preview_image_url(self, image_url_or_path: str) -> str:
        """Return a URL that can be rendered inside the plugin Page iframe."""

        if image_url_or_path.startswith(("http://", "https://", "data:")):
            return image_url_or_path
        path = Path(image_url_or_path)
        if path.is_file():
            return image_file_to_data_url(path)
        return image_url_or_path

    def _register_web_apis(self, context: Context) -> None:
        routes = [
            (f"/{PLUGIN_NAME}/menus", self.api_list_menus, ["GET"], "List bot menus"),
            (f"/{PLUGIN_NAME}/menus/save", self.api_save_menu, ["POST"], "Save bot menu"),
            (f"/{PLUGIN_NAME}/menus/delete", self.api_delete_menu, ["POST"], "Delete bot menu"),
            (f"/{PLUGIN_NAME}/menus/preview", self.api_preview_menu, ["POST"], "Preview bot menu"),
            (f"/{PLUGIN_NAME}/menus/<menu_id>", self.api_get_menu, ["GET"], "Get bot menu"),
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

    def _effective_default_menu_id(self) -> str:
        configured = str(self._config_get("default_menu_id", "default") or "default").strip()
        if configured and self.storage.get_menu(configured):
            return configured
        return self.storage.first_menu_id()

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
