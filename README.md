# AstrBot Bot 菜单插件

用于在 AstrBot 中维护多套 Bot 菜单：在 Page 页面可视化编辑、实时预览，保存后通过聊天命令发送渲染后的菜单图片。

- 当前版本：`0.5.0`
- 作者：雪碧bir
- 交流与反馈：[点击加入 QQ 群 1081773675](https://qm.qq.com/q/Qr45Vz0a8o)

## 当前渲染策略

插件现在只有一条图片渲染链路：Typst。

- Page 保存时会固化当前完整预览 PNG 到 `render_snapshot.raster`。
- 后端优先直接把这份 PNG 写入渲染缓存，不重新排版、不重新测量文字、不重采样。
- 聊天侧 `/menu` 优先发送缓存文件；缓存命中时是毫秒级路径。
- 旧菜单没有完整预览 PNG 时，才使用 Typst 的几何兼容渲染；要获得像素级一致性，请重新打开 Page 并保存一次。
- 不再保留其它图像渲染模式或降级路径。

## 功能

- 插件 Page：`menu-editor`
- 多菜单方案：新建、复制、删除、切换、导入、导出。
- 可视化编辑：标题、副标题、分组、菜单项、图标、指令、描述、启用状态。
- 样式配置：主题、主色、背景图、透明度、卡片色、文字色、字体、阴影、边框、水印、宽度、列数、间距、圆角、更新时间。
- 用户字体：运行数据目录自动创建 `fonts/`，支持 `.ttf/.otf/.ttc/.woff/.woff2`。
- 缓存状态：Page 轮询 `menus/render-status/<menu_id>`，聊天侧避免重复生成同一张图。

## 安装

把本目录放入 AstrBot 的 `data/plugins/` 下，然后在 AstrBot WebUI 中启用或重载插件。

```text
AstrBot/data/plugins/astrbot_plugin_bot_menu/
```

插件依赖由 `requirements.txt` 声明，目前只需要 Typst Python 包。

## 使用

1. 打开 AstrBot WebUI。
2. 进入插件详情页，打开 `Bot 菜单` 的 `menu-editor` 页面。
3. 编辑菜单方案并保存。
4. 在聊天中发送 `/menu` 或 `/menu default` 查看菜单图片。

常用命令：

- `/menu`：发送上下文默认菜单。
- `/menu <方案ID|别名>`：发送指定菜单。
- `/menu list`：列出菜单、别名与缓存状态。
- `/menu search <关键词>`：搜索菜单项。
- `/menu refresh [方案ID|别名]`：刷新缓存。

## 配置

`_conf_schema.json` 提供：

- `default_menu_id`：默认菜单方案 ID。
- `render_width`：旧菜单兼容渲染的默认宽度。
- `render_scale`：旧菜单兼容渲染的输出倍率；完整预览 PNG 会直接复用保存结果。
- `show_render_error_detail`：调试时在聊天侧显示详细渲染错误。

## 数据目录

```text
data/plugin_data/astrbot_plugin_bot_menu/menus.json
data/plugin_data/astrbot_plugin_bot_menu/assets.json
data/plugin_data/astrbot_plugin_bot_menu/routing.json
data/plugin_data/astrbot_plugin_bot_menu/history.json
data/plugin_data/astrbot_plugin_bot_menu/assets/
data/plugin_data/astrbot_plugin_bot_menu/fonts/
data/plugin_data/astrbot_plugin_bot_menu/rendered/
```

`menus.json`、`assets.json`、`routing.json` 使用原子写入；删除菜单前会自动创建历史快照。

## 进一步说明

- Typst 链路：`docs/typst-renderer.md`
- 字体系统：`docs/font-system.md`
- Page 保存验证：`docs/page-editor-verification.md`
- 更新日志：`CHANGELOG.md`
