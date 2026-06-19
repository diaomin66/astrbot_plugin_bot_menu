# AstrBot Bot 菜单插件

一个用于自定义机器人菜单的 AstrBot 插件：在 WebUI 中编辑多套菜单方案，实时预览，并通过聊天指令发送渲染后的菜单图片。

## 功能

- 插件 Pages 页面：`menu-editor`
- 多菜单方案：支持新建、复制、删除、导入、导出
- 可视化编辑：标题、副标题、分组、菜单项、图标、指令、描述、启用状态
- 样式配置：主题、主色、背景色、卡片色、宽度、圆角、更新时间
- 聊天指令：
  - `/menu`：发送默认菜单
  - `/menu <方案ID>`：发送指定菜单
  - `/菜单`、`/菜单 <方案ID>`：中文别名

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 下，然后在 AstrBot WebUI 中启用或重载插件。

```text
AstrBot/data/plugins/astrbot_plugin_bot_menu/
```

插件本地 PNG 渲染依赖 `Pillow`，AstrBot 安装插件依赖时会读取 `requirements.txt` 自动安装。

## 使用

1. 打开 AstrBot WebUI。
2. 进入插件详情页，打开 `Bot 菜单` 的 `menu-editor` 页面。
3. 编辑菜单方案并保存。
4. 在聊天中发送 `/menu` 或 `/menu default` 查看菜单图片。

## 配置

插件提供 `_conf_schema.json`：

- `default_menu_id`：默认菜单方案 ID。
- `render_width`：默认渲染宽度。
- `render_mode`：菜单图片渲染模式，默认 `browser`（调用系统 Edge/Chrome），可选 `auto`、`remote` 或 `pillow`。
- `show_render_error_detail`：调试时在聊天侧显示详细渲染错误。

菜单正文数据保存在：

```text
data/plugin_data/astrbot_plugin_bot_menu/menus.json
```

## 说明

本插件默认调用 Windows 系统内置的 Edge 浏览器或 Chrome 进行无头高清截图（`browser` 模式），复用 Page 实时预览的同款 HTML 结构和 CSS 排版，并且不受 AstrBot 远程 T2I 服务波动影响。若使用 `auto`，会先尝试 browser，同款截图失败后再尝试 AstrBot 远程 T2I，最后回退到纯 Python 的 Pillow 绘制引擎。插件 Web API 兼容带 `astrbot.api.web` 的新版 AstrBot，以及仍使用 Quart 插件路由的 AstrBot 4.25.x。
