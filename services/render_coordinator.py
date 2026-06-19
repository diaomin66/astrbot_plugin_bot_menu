from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from .render_cache import MenuRenderCache
from .storage import MenuStorage

RenderMenuCallable = Callable[[dict[str, Any]], Awaitable[str]]


class MenuRenderCoordinator:
    """Coordinates background render-cache tasks for menu images."""

    def __init__(
        self,
        *,
        storage: MenuStorage,
        cache: MenuRenderCache,
        render_menu: RenderMenuCallable,
        render_width: Callable[[], int],
        render_scale: Callable[[], int],
        logger: logging.Logger | None = None,
    ) -> None:
        self.storage = storage
        self.cache = cache
        self.render_menu = render_menu
        self.render_width = render_width
        self.render_scale = render_scale
        self.logger = logger or logging.getLogger(__name__)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._task_fingerprints: dict[str, str] = {}

    def get_cached_path(self, menu: dict[str, Any]) -> str | None:
        return self.cache.get_cached_path(
            menu,
            render_width=self.render_width(),
            render_scale=self.render_scale(),
        )

    def status_for_menu(self, menu: dict[str, Any]) -> dict[str, Any]:
        menu_id = str(menu.get("id") or "")
        render_width = self.render_width()
        render_scale = self.render_scale()
        fingerprint = self.cache.fingerprint(menu, render_width=render_width, render_scale=render_scale)
        task = self._tasks.get(menu_id)
        is_rendering = bool(task and not task.done() and self._task_fingerprints.get(menu_id) == fingerprint)
        return self.cache.get_status(
            menu,
            render_width=render_width,
            render_scale=render_scale,
            is_rendering=is_rendering,
        )

    def status_for_menu_id(self, menu_id: str) -> dict[str, Any] | None:
        menu = self.storage.get_menu(menu_id)
        if not menu:
            return None
        return self.status_for_menu(menu)

    def schedule_prewarm(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.prewarm())

    async def prewarm(self) -> None:
        await asyncio.sleep(0)
        for menu in self.storage.list_menus():
            if not self.get_cached_path(menu):
                self.schedule(menu)

    def schedule(self, menu: dict[str, Any]) -> bool:
        menu_id = str(menu.get("id") or "")
        if not menu_id:
            return False

        render_width = self.render_width()
        render_scale = self.render_scale()
        fingerprint = self.cache.fingerprint(menu, render_width=render_width, render_scale=render_scale)
        if self.cache.get_cached_path(menu, render_width=render_width, render_scale=render_scale):
            return False

        current_task = self._tasks.get(menu_id)
        if current_task and not current_task.done():
            if self._task_fingerprints.get(menu_id) == fingerprint:
                return True
            current_task.cancel()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        self.cache.mark_rendering(menu, render_width=render_width, render_scale=render_scale)
        self._task_fingerprints[menu_id] = fingerprint
        self._tasks[menu_id] = loop.create_task(
            self._render(menu, fingerprint, render_width=render_width, render_scale=render_scale)
        )
        return True

    async def _render(
        self,
        menu: dict[str, Any],
        fingerprint: str,
        *,
        render_width: int,
        render_scale: int,
    ) -> None:
        menu_id = str(menu.get("id") or "")
        try:
            rendered_path = await self.render_menu(menu)
            path = Path(rendered_path)
            if not path.is_file():
                raise RuntimeError(f"cached render did not produce a local file: {rendered_path}")
            latest_menu = self.storage.get_menu(menu_id)
            latest_fingerprint = (
                self.cache.fingerprint(latest_menu, render_width=render_width, render_scale=render_scale)
                if latest_menu
                else ""
            )
            if latest_fingerprint != fingerprint:
                return
            cached_path = self.cache.store_rendered(
                menu,
                path,
                render_width=render_width,
                render_scale=render_scale,
            )
            self.logger.info("Bot menu cached render ready: %s -> %s", menu_id, cached_path)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - cache render should not break chat commands
            self.logger.exception("Bot menu cached render failed: %s", menu_id)
            self.cache.mark_error(menu, str(exc), render_width=render_width, render_scale=render_scale)
        finally:
            if self._tasks.get(menu_id) is asyncio.current_task():
                self._tasks.pop(menu_id, None)
                self._task_fingerprints.pop(menu_id, None)
