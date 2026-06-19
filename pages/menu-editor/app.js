const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);

const CARD_TEMPLATES = {
  compact: { label: "紧凑", icon: "•", title: "快捷项", command: "/cmd", description: "", width: 190 },
  standard: { label: "标准", icon: "✨", title: "新功能", command: "/command", description: "功能说明", width: 230 },
  large: { label: "大卡", icon: "⭐", title: "重点功能", command: "/feature", description: "适合放较长描述或主推功能", width: 285 },
  banner: { label: "横幅", icon: "📌", title: "公告入口", command: "/notice", description: "横跨整行，用于公告、主入口或高优先级操作", width: 360 },
};

const THEME_PRESETS = {
  aurora: { label: "极光紫", primary_color: "#7c3aed", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#6b7280" },
  minimal: { label: "清爽蓝", primary_color: "#2563eb", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#64748b" },
  midnight: { label: "午夜蓝", primary_color: "#38bdf8", background_color: "#111827", card_color: "#1f2937", text_color: "#f8fafc", muted_color: "#cbd5e1" },
  forest: { label: "森林绿", primary_color: "#059669", background_color: "#ecfdf5", card_color: "#ffffff", text_color: "#064e3b", muted_color: "#64748b" },
  sunrise: { label: "日出橙", primary_color: "#ea580c", background_color: "#fff7ed", card_color: "#ffffff", text_color: "#1f2937", muted_color: "#78716c" },
};

const MENU_TEMPLATES = [
  {
    key: "basic",
    name: "基础功能菜单",
    menu: {
      name: "基础功能菜单",
      title: "Bot 功能菜单",
      subtitle: "常用指令一眼可见，发送指令即可使用",
      footer: "请选择需要的功能入口",
      sections: [
        { title: "常用功能", items: [
          { label: "菜单", command: "/menu", description: "查看当前功能菜单", icon: "📋", card_size: "standard", enabled: true },
          { label: "帮助", command: "/help", description: "查看机器人帮助信息", icon: "❓", card_size: "standard", enabled: true },
        ] },
      ],
    },
  },
  {
    key: "admin",
    name: "管理员工具菜单",
    menu: {
      name: "管理员工具菜单",
      title: "管理员工具箱",
      subtitle: "面向群管和运维的高频操作集合",
      footer: "请谨慎执行管理类指令",
      sections: [
        { title: "群管理", items: [
          { label: "禁言", command: "/mute @成员 10m", description: "临时禁言成员", icon: "🔇", card_size: "standard", enabled: true },
          { label: "公告", command: "/notice 内容", description: "发布群公告或提醒", icon: "📌", card_size: "banner", enabled: true },
        ] },
        { title: "运维", items: [
          { label: "状态", command: "/status", description: "查看机器人运行状态", icon: "🧭", card_size: "standard", enabled: true },
          { label: "重载", command: "/reload", description: "重新加载插件或配置", icon: "♻️", card_size: "standard", enabled: true },
        ] },
      ],
    },
  },
  {
    key: "community",
    name: "社群/群聊常用菜单",
    menu: {
      name: "社群常用菜单",
      title: "社群服务导航",
      subtitle: "新人引导、活动信息与常用查询集中展示",
      footer: "欢迎参与讨论，文明交流",
      sections: [
        { title: "新人引导", items: [
          { label: "群规", command: "/rules", description: "查看群聊规则和注意事项", icon: "📜", card_size: "large", enabled: true },
          { label: "FAQ", command: "/faq", description: "常见问题与资料索引", icon: "💡", card_size: "standard", enabled: true },
        ] },
        { title: "互动", items: [
          { label: "签到", command: "/checkin", description: "每日签到领取积分", icon: "✅", card_size: "compact", enabled: true },
          { label: "活动", command: "/events", description: "查看近期社群活动", icon: "🎉", card_size: "standard", enabled: true },
        ] },
      ],
    },
  },
];

const STYLE_COPY_KEYS = [
  "theme", "primary_color", "background_color", "background_image", "background_image_name",
  "background_image_x", "background_image_y", "background_image_width", "card_color", "text_color",
  "muted_color", "foreground_opacity", "radius", "width_mode", "width", "columns", "show_updated_at",
];
const MENU_ID_PATTERN = /^[A-Za-z0-9_-]{1,48}$/;
const DRAFT_PREFIX = "astrbot_plugin_bot_menu:draft:";
const COLLAPSE_PREFIX = "astrbot_plugin_bot_menu:collapsed:";

const state = {
  menus: [],
  defaultMenuId: "default",
  currentId: null,
  menu: null,
  dirty: false,
  saveState: "saved",
  itemSearch: "",
  restoredDraftIds: new Set(),
  renderStatusTimer: 0,
};

const els = {
  schemeSelect: $("schemeSelect"),
  status: $("status"),
  saveState: $("saveState"),
  saveBtn: $("saveBtn"),
  renderStatus: $("renderStatus"),
  validationSummary: $("validationSummary"),
  sections: $("sections"),
  preview: $("preview"),
  menuId: $("menuId"),
  menuName: $("menuName"),
  menuTitle: $("menuTitle"),
  menuSubtitle: $("menuSubtitle"),
  menuFooter: $("menuFooter"),
  theme: $("theme"),
  themePresetCards: $("themePresetCards"),
  primaryColor: $("primaryColor"),
  backgroundColor: $("backgroundColor"),
  backgroundImageInput: $("backgroundImageInput"),
  backgroundImageName: $("backgroundImageName"),
  backgroundImageWidth: $("backgroundImageWidth"),
  backgroundWidthValue: $("backgroundWidthValue"),
  backgroundImageX: $("backgroundImageX"),
  backgroundImageY: $("backgroundImageY"),
  centerBackgroundBtn: $("centerBackgroundBtn"),
  coverBackgroundBtn: $("coverBackgroundBtn"),
  clearBackgroundBtn: $("clearBackgroundBtn"),
  cardColor: $("cardColor"),
  textColor: $("textColor"),
  mutedColor: $("mutedColor"),
  foregroundOpacity: $("foregroundOpacity"),
  foregroundOpacityValue: $("foregroundOpacityValue"),
  widthMode: $("widthMode"),
  columns: $("columns"),
  width: $("width"),
  radius: $("radius"),
  showUpdatedAt: $("showUpdatedAt"),
  itemSearch: $("itemSearch"),
  serverPreview: $("serverPreview"),
  previewMeta: $("previewMeta"),
};

await bridge.ready();
bindEvents();
await loadMenus();

function bindEvents() {
  els.schemeSelect.addEventListener("change", async () => {
    const nextId = els.schemeSelect.value;
    if (!(await confirmLeaveDirty())) {
      els.schemeSelect.value = state.currentId || "";
      return;
    }
    await selectMenu(nextId);
  });
  $("newBtn").addEventListener("click", async () => { if (await confirmLeaveDirty()) newMenu(); });
  $("templateBtn").addEventListener("click", async () => { if (await confirmLeaveDirty()) newMenuFromTemplate(); });
  $("copyBtn").addEventListener("click", async () => { if (await confirmLeaveDirty()) copyMenu(); });
  $("deleteBtn").addEventListener("click", deleteMenu);
  $("saveBtn").addEventListener("click", saveMenu);
  $("copyStyleBtn").addEventListener("click", copyStyleToMenus);
  $("resetStyleBtn").addEventListener("click", resetCurrentStyle);
  $("addSectionBtn").addEventListener("click", addSection);
  $("serverPreviewBtn").addEventListener("click", serverPreview);
  $("exportBtn").addEventListener("click", exportMenus);
  $("importInput").addEventListener("change", importMenus);
  if (window.ResizeObserver) {
    new ResizeObserver(fitPreviewToStage).observe(els.preview);
  } else {
    window.addEventListener("resize", fitPreviewToStage);
  }

  [
    "menuId",
    "menuName",
    "menuTitle",
    "menuSubtitle",
    "menuFooter",
    "primaryColor",
    "backgroundColor",
    "cardColor",
    "textColor",
    "mutedColor",
    "foregroundOpacity",
    "widthMode",
    "columns",
    "width",
    "radius",
    "showUpdatedAt",
  ].forEach((id) => {
    $(id).addEventListener("input", () => {
      syncFormToMenu();
      renderAll();
    });
  });

  els.theme.addEventListener("input", () => {
    applyThemePreset(els.theme.value);
    syncFormToMenu();
    renderAll();
  });
  els.backgroundImageInput.addEventListener("change", handleBackgroundUpload);
  els.backgroundImageWidth.addEventListener("input", updateBackgroundFromControls);
  els.backgroundImageX.addEventListener("input", updateBackgroundFromControls);
  els.backgroundImageY.addEventListener("input", updateBackgroundFromControls);
  els.centerBackgroundBtn.addEventListener("click", centerBackgroundImage);
  els.coverBackgroundBtn.addEventListener("click", () => fitBackgroundToCover(true));
  els.clearBackgroundBtn.addEventListener("click", clearBackgroundImage);
  els.itemSearch.addEventListener("input", () => {
    state.itemSearch = els.itemSearch.value.trim().toLowerCase();
    saveSearchState();
    renderSectionsEditor();
  });
  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
  renderThemePresetCards();
  updateSaveState("saved");
}

async function loadMenus(preferredId) {
  try {
    setStatus("正在加载菜单...");
    const data = await bridge.apiGet("menus");
    state.menus = data.menus || [];
    state.defaultMenuId = data.default_menu_id || "default";
    const target = preferredId || state.currentId || state.defaultMenuId || state.menus[0]?.id;
    refreshSchemeSelect();
    await selectMenu(target);
    setStatus("已加载。聊天中发送 /menu 可查看默认菜单，/menu 方案ID 可查看指定方案。");
  } catch (error) {
    setStatus(`加载失败：${error.message}`);
  }
}

async function selectMenu(id) {
  const menu = state.menus.find((item) => item.id === id) || state.menus[0];
  if (!menu) return;
  state.currentId = menu.id;
  const serverMenu = structuredClone(menu);
  state.menu = maybeRestoreDraft(serverMenu);
  state.dirty = state.menu !== serverMenu;
  loadSearchState();
  refreshSchemeSelect();
  fillForm();
  renderAll();
  updateSaveState(state.dirty ? "dirty" : "saved");
  clearRenderStatus();
}

function refreshSchemeSelect() {
  els.schemeSelect.innerHTML = "";
  state.menus.forEach((menu) => {
    const option = document.createElement("option");
    option.value = menu.id;
    option.textContent = `${menu.name || menu.id} (${menu.id})${menu.id === state.defaultMenuId ? " · 默认" : ""}`;
    els.schemeSelect.append(option);
  });
  if (state.currentId) els.schemeSelect.value = state.currentId;
}

function fillForm() {
  const menu = state.menu;
  els.menuId.value = menu.id || "";
  els.menuName.value = menu.name || "";
  els.menuTitle.value = menu.title || "";
  els.menuSubtitle.value = menu.subtitle || "";
  els.menuFooter.value = menu.footer || "";
  const style = ensureStyle(menu);
  els.theme.value = style.theme || "aurora";
  els.primaryColor.value = toColor(style.primary_color, "#7c3aed");
  els.backgroundColor.value = toColor(style.background_color, "#f8fafc");
  els.backgroundImageName.textContent = style.background_image ? (style.background_image_name || "Custom background") : "No background image";
  syncBackgroundControls();
  els.cardColor.value = toColor(style.card_color, "#ffffff");
  els.textColor.value = toColor(style.text_color, "#111827");
  els.mutedColor.value = toColor(style.muted_color, "#6b7280");
  els.foregroundOpacity.value = style.foreground_opacity ?? 92;
  els.foregroundOpacityValue.textContent = `${els.foregroundOpacity.value}%`;
  els.widthMode.value = style.width_mode || "auto";
  els.columns.value = style.columns || 2;
  els.width.value = style.width || 760;
  els.radius.value = style.radius ?? 24;
  els.showUpdatedAt.checked = style.show_updated_at !== false;
  syncWidthControl();
  if (els.itemSearch) els.itemSearch.value = state.itemSearch || "";
}

function syncFormToMenu({ mark = true } = {}) {
  if (!state.menu) return;
  Object.assign(state.menu, {
    id: els.menuId.value.trim(),
    name: els.menuName.value.trim(),
    title: els.menuTitle.value.trim(),
    subtitle: els.menuSubtitle.value.trim(),
    footer: els.menuFooter.value.trim(),
  });
  state.menu.style = {
    ...ensureStyle(state.menu),
    theme: els.theme.value,
    primary_color: els.primaryColor.value,
    background_color: els.backgroundColor.value,
    background_image_x: Number(els.backgroundImageX.value) || 0,
    background_image_y: Number(els.backgroundImageY.value) || 0,
    background_image_width: Number(els.backgroundImageWidth.value) || 100,
    card_color: els.cardColor.value,
    text_color: els.textColor.value,
    muted_color: els.mutedColor.value,
    foreground_opacity: Number(els.foregroundOpacity.value) || 0,
    width_mode: els.widthMode.value,
    columns: Number(els.columns.value) || 2,
    width: Number(els.width.value) || 760,
    radius: Number(els.radius.value) || 0,
    show_updated_at: els.showUpdatedAt.checked,
  };
  markDirty();
  els.foregroundOpacityValue.textContent = `${state.menu.style.foreground_opacity}%`;
  syncWidthControl();
  els.serverPreview.hidden = true;
}

function renderAll() {
  renderSectionsEditor();
  renderPreview();
}

function renderSectionsEditor() {
  els.sections.innerHTML = "";
  const query = state.itemSearch || "";
  let visibleItems = 0;
  state.menu.sections.forEach((section, sectionIndex) => {
    const sectionCollapsed = isCollapsed("section", sectionIndex);
    const matchingIndexes = section.items
      .map((item, itemIndex) => ({ item, itemIndex }))
      .filter(({ item }) => !query || itemMatchesSearch(item, query));
    if (query && matchingIndexes.length === 0) return;

    const card = document.createElement("section");
    card.className = `section-card ${sectionCollapsed ? "is-collapsed" : ""}`;
    card.dataset.errorKey = `section-${sectionIndex}`;
    card.innerHTML = `
      <div class="section-head">
        <button type="button" class="collapse-toggle" data-action="toggle-section">${sectionCollapsed ? "展开" : "折叠"}</button>
        <input data-error-key="section-${sectionIndex}-title" value="${escapeAttr(section.title)}" aria-label="分组标题" />
        <div class="actions">
          <button type="button" data-action="move-up" ${sectionIndex === 0 ? "disabled" : ""}>上移</button>
          <button type="button" data-action="move-down" ${sectionIndex === state.menu.sections.length - 1 ? "disabled" : ""}>下移</button>
          <button type="button" data-action="copy-section">复制</button>
          <button type="button" data-action="remove-section" class="danger">删除分组</button>
        </div>
      </div>
      <div class="section-body" ${sectionCollapsed ? "hidden" : ""}>
        <div class="template-actions">
          ${Object.entries(CARD_TEMPLATES).map(([key, template]) => `<button type="button" data-template="${key}">${template.label}</button>`).join("")}
        </div>
        <div class="items-editor"></div>
      </div>`;
    const titleInput = card.querySelector("input");
    titleInput.addEventListener("input", () => {
      section.title = titleInput.value;
      markDirty();
      els.serverPreview.hidden = true;
      renderPreview();
      validateMenu({ silent: true });
    });
    card.querySelector('[data-action="toggle-section"]').addEventListener("click", () => {
      setCollapsed("section", sectionIndex, null, !sectionCollapsed);
      renderSectionsEditor();
    });
    card.querySelectorAll("[data-template]").forEach((button) => {
      button.addEventListener("click", () => addItem(sectionIndex, button.dataset.template));
    });
    card.querySelector('[data-action="move-up"]').addEventListener("click", () => moveSection(sectionIndex, -1));
    card.querySelector('[data-action="move-down"]').addEventListener("click", () => moveSection(sectionIndex, 1));
    card.querySelector('[data-action="copy-section"]').addEventListener("click", () => copySection(sectionIndex));
    card.querySelector('[data-action="remove-section"]').addEventListener("click", () => removeSection(sectionIndex));
    const itemsEl = card.querySelector(".items-editor");
    matchingIndexes.forEach(({ item, itemIndex }) => {
      visibleItems += 1;
      itemsEl.append(renderItemEditor(item, sectionIndex, itemIndex));
    });
    els.sections.append(card);
  });
  if (query && visibleItems === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-search";
    empty.textContent = "没有匹配的菜单项，搜索不会改变实际菜单数据。";
    els.sections.append(empty);
  }
  validateMenu({ silent: true });
}

function renderItemEditor(item, sectionIndex, itemIndex) {
  const card = document.createElement("article");
  const currentSize = cardSize(item.card_size);
  const itemCollapsed = isCollapsed("item", sectionIndex, itemIndex);
  card.className = `item-card size-${currentSize} ${itemCollapsed ? "is-collapsed" : ""}`;
  card.dataset.errorKey = `item-${sectionIndex}-${itemIndex}`;
  card.innerHTML = `
    <div class="item-head">
      <button type="button" class="collapse-toggle" data-action="toggle-item">${itemCollapsed ? "展开" : "折叠"}</button>
      <strong>${CARD_TEMPLATES[currentSize].label}卡片 ${itemIndex + 1} · ${escapeHtml(item.label || "未命名")}</strong>
      <div class="actions">
        <button type="button" data-action="move-up" ${itemIndex === 0 ? "disabled" : ""}>上移</button>
        <button type="button" data-action="move-down" ${itemIndex === state.menu.sections[sectionIndex].items.length - 1 ? "disabled" : ""}>下移</button>
        <button type="button" data-action="copy-item">复制</button>
        <button type="button" data-action="remove-item" class="danger">删除</button>
      </div>
    </div>
    <div class="item-body" ${itemCollapsed ? "hidden" : ""}>
      <div class="item-grid">
        <label class="field"><span>图标</span><input data-error-key="item-${sectionIndex}-${itemIndex}-icon" data-key="icon" value="${escapeAttr(item.icon || "")}" /></label>
        <label class="field"><span>模板</span><select data-key="card_size">${cardSizeOptions(currentSize)}</select></label>
        <label class="field"><span>名称</span><input data-error-key="item-${sectionIndex}-${itemIndex}-label" data-key="label" value="${escapeAttr(item.label || "")}" /></label>
        <label class="field"><span>指令</span><input data-error-key="item-${sectionIndex}-${itemIndex}-command" data-key="command" value="${escapeAttr(item.command || "")}" /></label>
        <label class="field wide"><span>描述</span><input data-error-key="item-${sectionIndex}-${itemIndex}-description" data-key="description" value="${escapeAttr(item.description || "")}" /></label>
      </div>
      <label class="check"><input data-key="enabled" type="checkbox" ${item.enabled !== false ? "checked" : ""} /> 启用</label>
    </div>`;
  card.querySelector('[data-action="toggle-item"]').addEventListener("click", () => {
    setCollapsed("item", sectionIndex, itemIndex, !itemCollapsed);
    renderSectionsEditor();
  });
  card.querySelector('[data-action="move-up"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, -1));
  card.querySelector('[data-action="move-down"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, 1));
  card.querySelector('[data-action="copy-item"]').addEventListener("click", () => copyItem(sectionIndex, itemIndex));
  card.querySelector('[data-action="remove-item"]').addEventListener("click", () => removeItem(sectionIndex, itemIndex));
  card.querySelectorAll("[data-key]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.key;
      item[key] = input.type === "checkbox" ? input.checked : input.value;
      markDirty();
      els.serverPreview.hidden = true;
      if (key === "card_size") renderSectionsEditor();
      renderPreview();
      validateMenu({ silent: true });
    });
  });
  return card;
}

function renderPreview() {
  const menu = state.menu;
  const style = ensureStyle(menu);
  const layout = previewLayout(menu);
  const previewStyle = [
    `--preview-primary:${style.primary_color}`,
    `--preview-bg:${style.background_color}`,
    `--preview-card:${style.card_color}`,
    `--preview-text:${style.text_color || "#111827"}`,
    `--preview-muted:${style.muted_color || "#6b7280"}`,
    `--preview-radius:${style.radius || 24}px`,
    `--preview-width:${layout.width}px`,
    `--preview-columns:${layout.columns}`,
    `--preview-foreground-opacity:${clampNumber(style.foreground_opacity, 0, 100, 92) / 100}`,
  ].join(";");
  const backgroundMarkup = style.background_image ? `
        <img class="preview-bg-image" alt="" src="${escapeAttr(style.background_image)}" style="left:${style.background_image_x || 0}%;top:${style.background_image_y || 0}%;width:${style.background_image_width || 100}%;" />
        <div class="background-transform-box" aria-label="Background crop box">
          <span class="resize-handle nw" data-handle="nw"></span>
          <span class="resize-handle ne" data-handle="ne"></span>
          <span class="resize-handle sw" data-handle="sw"></span>
          <span class="resize-handle se" data-handle="se"></span>
        </div>` : "";
  els.preview.innerHTML = `
    <div class="preview-fit" style="--preview-scale:1">
      <div class="preview-card" style="${previewStyle}">
        ${backgroundMarkup}
        <div class="preview-inner">
          <div class="kicker">📋 ${escapeHtml(menu.name || menu.id)}</div>
          <h1 class="preview-title">${escapeHtml(menu.title || "Bot 功能菜单")}</h1>
          <div class="preview-sub">${escapeHtml(menu.subtitle || "")}</div>
          ${menu.sections.map((section) => `
            <section class="preview-section">
              <h3>${escapeHtml(section.title || "分组")}</h3>
              <div class="preview-items">
                ${section.items.map((item) => `
                  <div class="preview-item size-${cardSize(item.card_size)} ${item.enabled === false ? "disabled" : ""}">
                    <div>${escapeHtml(item.icon || "•")}</div>
                    <div><strong>${escapeHtml(item.label || "未命名")}</strong><div class="preview-command">${escapeHtml(item.command || "")}</div><div class="preview-desc">${escapeHtml(item.description || "")}</div></div>
                  </div>`).join("")}
              </div>
            </section>`).join("")}
          <div class="preview-footer"><span>${escapeHtml(menu.footer || "")}</span><span>${style.show_updated_at === false ? "" : "实时预览"}</span></div>
        </div>
      </div>
    </div>`;
  els.previewMeta.textContent = `${layout.width}px · 每行 ${layout.columns} 张 · ${layout.itemCount} 项`;
  attachBackgroundEditor();
  fitPreviewToStage();
}

function fitPreviewToStage() {
  requestAnimationFrame(() => {
    const fit = els.preview.querySelector(".preview-fit");
    const card = els.preview.querySelector(".preview-card");
    if (!fit || !card) return;
    fit.style.setProperty("--preview-scale", "1");
    const previewStyles = getComputedStyle(els.preview);
    const horizontalPadding = parseFloat(previewStyles.paddingLeft) + parseFloat(previewStyles.paddingRight);
    const availableWidth = Math.max(1, els.preview.clientWidth - horizontalPadding);
    const naturalWidth = card.offsetWidth || parseFloat(getComputedStyle(card).width) || availableWidth;
    const scale = Math.min(1, availableWidth / naturalWidth);
    fit.style.setProperty("--preview-scale", scale.toFixed(4));
    els.preview.classList.toggle("is-scaled", scale < 0.999);
  });
}

function addSection() {
  state.menu.sections.push({
    title: "新分组",
    items: [createItemFromTemplate("standard")],
  });
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function removeSection(index) {
  if (state.menu.sections.length <= 1) return setStatus("至少保留一个分组。");
  state.menu.sections.splice(index, 1);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function moveSection(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= state.menu.sections.length) return;
  const [section] = state.menu.sections.splice(index, 1);
  state.menu.sections.splice(target, 0, section);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function copySection(index) {
  const copy = structuredClone(state.menu.sections[index]);
  copy.title = `${copy.title || "分组"} 副本`;
  state.menu.sections.splice(index + 1, 0, copy);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function addItem(sectionIndex, templateKey = "standard") {
  state.menu.sections[sectionIndex].items.push(createItemFromTemplate(templateKey));
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function moveItem(sectionIndex, itemIndex, direction) {
  const items = state.menu.sections[sectionIndex].items;
  const target = itemIndex + direction;
  if (target < 0 || target >= items.length) return;
  const [item] = items.splice(itemIndex, 1);
  items.splice(target, 0, item);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function copyItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  const copy = structuredClone(items[itemIndex]);
  copy.label = `${copy.label || "菜单项"} 副本`;
  items.splice(itemIndex + 1, 0, copy);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

function removeItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  if (items.length <= 1) return setStatus("每个分组至少保留一个菜单项。");
  items.splice(itemIndex, 1);
  markDirty();
  els.serverPreview.hidden = true;
  renderAll();
}

async function saveMenu() {
  const draftIdBeforeSave = currentDraftId();
  syncFormToMenu({ mark: false });
  if (!validateMenu({ scroll: true })) {
    setStatus("请先修正表单错误，再保存菜单。", "error");
    return;
  }
  try {
    updateSaveState("saving");
    setStatus("正在保存...");
    const result = await bridge.apiPost("menus/save", { menu: state.menu });
    state.menus = result.menus || [result.menu];
    state.currentId = result.menu.id;
    state.menu = structuredClone(result.menu);
    state.dirty = false;
    clearDraft(state.currentId);
    if (draftIdBeforeSave !== state.currentId) clearDraft(draftIdBeforeSave);
    refreshSchemeSelect();
    fillForm();
    renderAll();
    updateSaveState("saved");
    setStatus("保存成功，后台正在刷新渲染缓存。", "success");
    pollRenderStatus(state.currentId);
  } catch (error) {
    updateSaveState("dirty");
    setStatus(`保存失败：${error.message}`, "error");
  }
}

function newMenu() {
  const id = uniqueId("menu");
  state.menu = {
    id,
    name: "新菜单",
    title: "Bot 功能菜单",
    subtitle: "发送下列指令即可使用对应功能",
    footer: "",
    style: defaultStyle(),
    sections: [{ title: "常用功能", items: [{ label: "菜单", command: "/menu", description: "查看菜单", icon: "📋", card_size: "standard", enabled: true }] }],
  };
  state.currentId = id;
  if (mark) markDirty();
  fillForm();
  renderAll();
  setStatus("已创建本地新菜单，保存后生效。");
}

function newMenuFromTemplate() {
  const choices = MENU_TEMPLATES.map((template, index) => `${index + 1}. ${template.name}`).join("\n");
  const answer = prompt(`选择模板编号：\n${choices}`, "1");
  const index = Math.max(0, Math.min(MENU_TEMPLATES.length - 1, Number(answer || 1) - 1));
  const template = MENU_TEMPLATES[index] || MENU_TEMPLATES[0];
  const id = uniqueId(template.key);
  state.menu = {
    id,
    style: defaultStyle(),
    ...structuredClone(template.menu),
    id,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  state.currentId = id;
  markDirty();
  fillForm();
  renderAll();
  setStatus(`已从「${template.name}」创建本地新菜单，保存后生效。`);
}

function copyMenu() {
  const copy = structuredClone(state.menu);
  copy.id = uniqueId(`${copy.id || "menu"}_copy`);
  copy.name = `${copy.name || "菜单"} 副本`;
  state.menu = copy;
  state.currentId = copy.id;
  markDirty();
  fillForm();
  renderAll();
  setStatus("已复制为新菜单，保存后生效。");
}

async function deleteMenu() {
  if (!state.currentId) return;
  if (!confirm(`确定删除菜单方案 ${state.currentId}？`)) return;
  try {
    const result = await bridge.apiPost("menus/delete", { id: state.currentId });
    state.menus = result.menus || [];
    state.currentId = result.default_menu_id || state.menus[0]?.id;
    await selectMenu(state.currentId);
    setStatus("删除成功。");
  } catch (error) {
    setStatus(`删除失败：${error.message}`);
  }
}

async function serverPreview() {
  syncFormToMenu({ mark: false });
  try {
    setStatus("正在请求服务端渲染...");
    const result = await bridge.apiPost("menus/preview", { menu: state.menu });
    els.serverPreview.src = result.url;
    els.serverPreview.hidden = false;
    setStatus("服务端渲染完成。");
  } catch (error) {
    setStatus(`服务端预览失败：${error.message}`);
  }
}

async function exportMenus() {
  const data = await bridge.apiGet("export");
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "bot-menus.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

async function importMenus(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    const menus = Array.isArray(data) ? data : data.menus;
    const result = await bridge.apiPost("import", { menus, mode: "merge" });
    state.menus = result.menus || [];
    refreshSchemeSelect();
    await selectMenu(state.menus[0]?.id);
    setStatus("导入成功。");
  } catch (error) {
    setStatus(`导入失败：${error.message}`);
  } finally {
    event.target.value = "";
  }
}

async function handleBackgroundUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("请选择图片文件作为背景。");
    event.target.value = "";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    setStatus("背景图文件较大，可能影响保存和加载速度，但不会限制上传尺寸。", "warning");
  }
  const dataUrl = await readFileAsDataUrl(file);
  const style = ensureStyle(state.menu);
  Object.assign(style, {
    background_image: dataUrl,
    background_image_name: file.name,
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  markDirty();
  els.backgroundImageName.textContent = file.name;
  syncBackgroundControls();
  els.serverPreview.hidden = true;
  renderAll();
  fitBackgroundToCover(true);
  event.target.value = "";
}

function clearBackgroundImage() {
  const style = ensureStyle(state.menu);
  Object.assign(style, {
    background_image: "",
    background_image_name: "",
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  markDirty();
  els.backgroundImageName.textContent = "No background image";
  syncBackgroundControls();
  els.serverPreview.hidden = true;
  renderAll();
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Failed to read background image"));
    reader.readAsDataURL(file);
  });
}

function attachBackgroundEditor() {
  const style = ensureStyle(state.menu);
  const img = els.preview.querySelector(".preview-bg-image");
  const box = els.preview.querySelector(".background-transform-box");
  const card = els.preview.querySelector(".preview-card");
  if (!img || !box || !card) return;

  const updateBox = () => {
    box.style.left = `${img.offsetLeft}px`;
    box.style.top = `${img.offsetTop}px`;
    box.style.width = `${img.offsetWidth}px`;
    box.style.height = `${img.offsetHeight}px`;
  };

  const updateImage = () => {
    img.style.left = `${style.background_image_x || 0}%`;
    img.style.top = `${style.background_image_y || 0}%`;
    img.style.width = `${style.background_image_width || 100}%`;
    requestAnimationFrame(updateBox);
  };

  if (img.complete) updateBox();
  img.addEventListener("load", () => {
    updateBox();
  }, { once: true });

  box.addEventListener("pointerdown", (event) => {
    const handle = event.target.dataset.handle;
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = Number(style.background_image_x) || 0;
    const startTop = Number(style.background_image_y) || 0;
    const startWidth = Number(style.background_image_width) || 100;
    const cardRect = card.getBoundingClientRect();
    box.setPointerCapture(event.pointerId);
    box.classList.add("is-moving");

    const onMove = (moveEvent) => {
      const dxPct = ((moveEvent.clientX - startX) / cardRect.width) * 100;
      const dyPct = ((moveEvent.clientY - startY) / cardRect.height) * 100;
      if (handle) {
        const fromLeft = handle.includes("w");
        const nextWidth = clampNumber(startWidth + (fromLeft ? -dxPct : dxPct), 10, 600, startWidth);
        style.background_image_width = nextWidth;
        if (fromLeft) style.background_image_x = clampNumber(startLeft + (startWidth - nextWidth), -300, 300, startLeft);
        if (handle.includes("n")) style.background_image_y = clampNumber(startTop + dyPct, -300, 300, startTop);
      } else {
        style.background_image_x = clampNumber(startLeft + dxPct, -300, 300, startLeft);
        style.background_image_y = clampNumber(startTop + dyPct, -300, 300, startTop);
      }
      markDirty();
      syncBackgroundControls();
      els.serverPreview.hidden = true;
      updateImage();
    };

    const onUp = () => {
      box.classList.remove("is-moving");
      box.removeEventListener("pointermove", onMove);
      box.removeEventListener("pointerup", onUp);
      box.removeEventListener("pointercancel", onUp);
    };

    box.addEventListener("pointermove", onMove);
    box.addEventListener("pointerup", onUp);
    box.addEventListener("pointercancel", onUp);
  });
}

function fitBackgroundToCover(forceReset) {
  const style = ensureStyle(state.menu);
  const img = els.preview.querySelector(".preview-bg-image");
  const card = els.preview.querySelector(".preview-card");
  if (!img || !card || !style.background_image) return;
  if (!img.complete || !img.naturalWidth || !img.naturalHeight) {
    img.addEventListener("load", () => fitBackgroundToCover(forceReset), { once: true });
    return;
  }
  const requiredWidth = Math.max(100, (card.clientHeight * img.naturalWidth * 100) / (card.clientWidth * img.naturalHeight));
  if (!forceReset && Number(style.background_image_width) >= requiredWidth) return;
  style.background_image_width = clampNumber(requiredWidth, 10, 600, 100);
  style.background_image_x = clampNumber((100 - style.background_image_width) / 2, -300, 300, 0);
  style.background_image_y = 0;
  markDirty();
  syncBackgroundControls();
  renderPreview();
}


function updateBackgroundFromControls() {
  const style = ensureStyle(state.menu);
  style.background_image_width = clampNumber(els.backgroundImageWidth.value, 10, 600, 100);
  style.background_image_x = clampNumber(els.backgroundImageX.value, -300, 300, 0);
  style.background_image_y = clampNumber(els.backgroundImageY.value, -300, 300, 0);
  syncBackgroundControls();
  markDirty();
  els.serverPreview.hidden = true;
  renderPreview();
}

function syncBackgroundControls() {
  if (!state.menu || !els.backgroundImageWidth) return;
  const style = ensureStyle(state.menu);
  const width = clampNumber(style.background_image_width, 10, 600, 100);
  const x = clampNumber(style.background_image_x, -300, 300, 0);
  const y = clampNumber(style.background_image_y, -300, 300, 0);
  els.backgroundImageWidth.value = width;
  els.backgroundWidthValue.textContent = `${width}%`;
  els.backgroundImageX.value = x;
  els.backgroundImageY.value = y;
}

function centerBackgroundImage() {
  const style = ensureStyle(state.menu);
  style.background_image_width = clampNumber(style.background_image_width, 10, 600, 100);
  style.background_image_x = clampNumber((100 - style.background_image_width) / 2, -300, 300, 0);
  style.background_image_y = 0;
  syncBackgroundControls();
  markDirty();
  renderPreview();
}

function renderThemePresetCards() {
  if (!els.themePresetCards) return;
  els.themePresetCards.innerHTML = Object.entries(THEME_PRESETS).map(([key, preset]) => `
    <button type="button" class="theme-card" data-theme="${key}" style="--swatch-primary:${preset.primary_color};--swatch-bg:${preset.background_color};--swatch-card:${preset.card_color};--swatch-text:${preset.text_color}">
      <span class="theme-swatch"><i></i></span><strong>${preset.label}</strong><small>${key}</small>
    </button>`).join("");
  els.themePresetCards.querySelectorAll("[data-theme]").forEach((button) => {
    button.addEventListener("click", () => {
      els.theme.value = button.dataset.theme;
      applyThemePreset(els.theme.value);
      syncFormToMenu();
      renderAll();
    });
  });
}

async function copyStyleToMenus() {
  if (!state.menu) return;
  syncFormToMenu({ mark: false });
  const otherMenus = state.menus.filter((menu) => menu.id !== state.currentId);
  if (!otherMenus.length) return setStatus("没有其他菜单可复制样式。", "warning");
  const answer = prompt(`输入目标菜单 ID，多个用逗号分隔，或输入 all：\n${otherMenus.map((menu) => menu.id).join(", ")}`, "all");
  if (!answer) return;
  const targets = answer.trim().toLowerCase() === "all"
    ? otherMenus
    : otherMenus.filter((menu) => answer.split(",").map((id) => id.trim()).includes(menu.id));
  if (!targets.length) return setStatus("未找到目标菜单。", "error");
  const stylePatch = pickStyleForCopy(ensureStyle(state.menu));
  try {
    setStatus("正在复制样式到其他菜单...");
    let latestMenus = null;
    for (const target of targets) {
      const nextMenu = structuredClone(target);
      nextMenu.style = { ...ensureStyle(nextMenu), ...stylePatch };
      const result = await bridge.apiPost("menus/save", { menu: nextMenu });
      latestMenus = result.menus || latestMenus;
    }
    if (latestMenus) {
      state.menus = latestMenus;
      refreshSchemeSelect();
    }
    setStatus(`已复制样式到 ${targets.length} 个菜单。`, "success");
  } catch (error) {
    setStatus(`复制样式失败：${error.message}`, "error");
  }
}

function pickStyleForCopy(style) {
  return STYLE_COPY_KEYS.reduce((copy, key) => {
    copy[key] = structuredClone(style[key]);
    return copy;
  }, {});
}

function resetCurrentStyle() {
  if (!confirm("确定重置当前菜单样式？菜单内容不会被删除。")) return;
  state.menu.style = defaultStyle();
  fillForm();
  markDirty();
  renderAll();
  setStatus("已重置样式，保存后生效。", "success");
}

function itemMatchesSearch(item, query) {
  return [item.label, item.command, item.description]
    .some((value) => String(value || "").toLowerCase().includes(query));
}

function markDirty() {
  if (!state.menu) return;
  state.dirty = true;
  updateSaveState("dirty");
  saveDraft();
}

function updateSaveState(nextState) {
  state.saveState = nextState;
  const labels = { dirty: "已修改", saving: "保存中", saved: "已保存" };
  if (els.saveState) els.saveState.textContent = labels[nextState] || labels.saved;
  if (els.saveBtn) els.saveBtn.textContent = nextState === "saving" ? "保存中..." : (nextState === "dirty" ? "保存（已修改）" : "保存");
  if (els.saveBtn) els.saveBtn.disabled = nextState === "saving";
}

async function confirmLeaveDirty() {
  if (!state.dirty) return true;
  return confirm("当前菜单有未保存修改，离开会丢失这些修改。确定继续？");
}

function currentDraftId() {
  return state.currentId || state.menu?.id || "new";
}

function draftKey(id) {
  return `${DRAFT_PREFIX}${id}`;
}

function saveDraft() {
  try {
    const id = currentDraftId();
    if (!id || !state.menu) return;
    localStorage.setItem(draftKey(id), JSON.stringify({ saved_at: Date.now(), menu: state.menu }));
  } catch (error) {
    console.warn("failed to save menu draft", error);
  }
}

function clearDraft(id) {
  try { localStorage.removeItem(draftKey(id)); } catch (error) { console.warn("failed to clear draft", error); }
}

function maybeRestoreDraft(menu) {
  const id = menu.id;
  if (!id || state.restoredDraftIds.has(id)) return menu;
  state.restoredDraftIds.add(id);
  try {
    const raw = localStorage.getItem(draftKey(id));
    if (!raw) return menu;
    const draft = JSON.parse(raw);
    const serverTime = Date.parse(menu.updated_at || menu.created_at || "") || 0;
    if (!draft?.menu || Number(draft.saved_at || 0) <= serverTime) return menu;
    if (confirm(`发现「${menu.name || id}」有较新的本地草稿，是否恢复？`)) {
      setStatus("已恢复本地草稿，保存后会覆盖服务端菜单。", "warning");
      return draft.menu;
    }
    if (confirm("是否丢弃该本地草稿？")) clearDraft(id);
  } catch (error) {
    console.warn("failed to restore draft", error);
  }
  return menu;
}

function collapseKey(type, sectionIndex, itemIndex = null) {
  const id = currentDraftId();
  return `${COLLAPSE_PREFIX}${id}:${type}:${sectionIndex}${itemIndex === null ? "" : `:${itemIndex}`}`;
}

function isCollapsed(type, sectionIndex, itemIndex = null) {
  try { return localStorage.getItem(collapseKey(type, sectionIndex, itemIndex)) === "1"; }
  catch { return false; }
}

function setCollapsed(type, sectionIndex, itemIndex, collapsed) {
  try {
    const key = collapseKey(type, sectionIndex, itemIndex);
    if (collapsed) localStorage.setItem(key, "1");
    else localStorage.removeItem(key);
  } catch (error) {
    console.warn("failed to save collapse state", error);
  }
}

function saveSearchState() {
  try { localStorage.setItem(`${COLLAPSE_PREFIX}${currentDraftId()}:search`, state.itemSearch || ""); } catch {}
}

function loadSearchState() {
  try { state.itemSearch = localStorage.getItem(`${COLLAPSE_PREFIX}${currentDraftId()}:search`) || ""; } catch { state.itemSearch = ""; }
}

function validateMenu({ scroll = false, silent = false } = {}) {
  if (!state.menu) return true;
  const errors = [];
  const add = (key, message) => errors.push({ key, message });
  const menu = state.menu;
  if (!MENU_ID_PATTERN.test(menu.id || "")) add("menuId", "方案 ID 只能包含 1-48 位英文字母、数字、_ 或 -。");
  if (!String(menu.title || "").trim()) add("menuTitle", "标题不能为空。");
  if (String(menu.name || "").length > 80) add("menuName", "方案名称最多 80 个字符。");
  if (String(menu.title || "").length > 120) add("menuTitle", "标题最多 120 个字符。");
  if (String(menu.subtitle || "").length > 240) add("menuSubtitle", "副标题最多 240 个字符。");
  if (String(menu.footer || "").length > 240) add("menuFooter", "页脚最多 240 个字符。");
  if (!Array.isArray(menu.sections) || menu.sections.length < 1) add("sections", "至少需要 1 个分组。");
  (menu.sections || []).forEach((section, sectionIndex) => {
    if (!String(section.title || "").trim()) add(`section-${sectionIndex}-title`, "分组标题不能为空。");
    if (String(section.title || "").length > 80) add(`section-${sectionIndex}-title`, "分组标题最多 80 个字符。");
    if (!Array.isArray(section.items) || section.items.length < 1) add(`section-${sectionIndex}`, "每个分组至少需要 1 个菜单项。");
    (section.items || []).forEach((item, itemIndex) => {
      if (!String(item.label || "").trim()) add(`item-${sectionIndex}-${itemIndex}-label`, "菜单项名称不能为空。");
      if (String(item.label || "").length > 80) add(`item-${sectionIndex}-${itemIndex}-label`, "名称最多 80 个字符。");
      if (String(item.command || "").length > 120) add(`item-${sectionIndex}-${itemIndex}-command`, "指令最多 120 个字符。");
      if (String(item.description || "").length > 240) add(`item-${sectionIndex}-${itemIndex}-description`, "描述最多 240 个字符。");
      if (String(item.icon || "").length > 12) add(`item-${sectionIndex}-${itemIndex}-icon`, "图标最多 12 个字符。");
    });
  });
  renderValidation(errors);
  if (errors.length && scroll) scrollToFirstError(errors[0].key);
  if (!silent && errors.length) setStatus(errors[0].message, "error");
  return errors.length === 0;
}

function renderValidation(errors) {
  document.querySelectorAll(".is-invalid").forEach((node) => node.classList.remove("is-invalid"));
  document.querySelectorAll(".error-text").forEach((node) => node.remove());
  errors.forEach((error) => {
    const node = document.querySelector(`[data-error-key="${cssEscape(error.key)}"]`) || $(error.key);
    if (!node) return;
    node.classList.add("is-invalid");
    const message = document.createElement("small");
    message.className = "error-text";
    message.textContent = error.message;
    (node.closest("label") || node).append(message);
  });
  if (els.validationSummary) {
    els.validationSummary.hidden = errors.length === 0;
    els.validationSummary.textContent = errors.length ? `发现 ${errors.length} 个问题：${errors[0].message}` : "";
  }
}

function scrollToFirstError(key) {
  let node = document.querySelector(`[data-error-key="${cssEscape(key)}"]`) || $(key);
  if (!node && state.itemSearch) {
    state.itemSearch = "";
    saveSearchState();
    if (els.itemSearch) els.itemSearch.value = "";
    renderSectionsEditor();
    node = document.querySelector(`[data-error-key="${cssEscape(key)}"]`) || $(key);
  }
  if (node && node.offsetParent === null) {
    const match = key.match(/^(section|item)-(\d+)(?:-(\d+))?/);
    if (match) {
      const sectionIndex = Number(match[2]);
      const itemIndex = match[1] === "item" ? Number(match[3]) : null;
      setCollapsed("section", sectionIndex, null, false);
      if (itemIndex !== null) setCollapsed("item", sectionIndex, itemIndex, false);
      renderSectionsEditor();
      node = document.querySelector(`[data-error-key="${cssEscape(key)}"]`) || $(key);
    }
  }
  node = node || els.validationSummary;
  node?.scrollIntoView({ behavior: "smooth", block: "center" });
  if (typeof node?.focus === "function") node.focus({ preventScroll: true });
}

function cssEscape(value) {
  return String(value).replace(/"/g, "\\\"");
}

function clearRenderStatus() {
  if (state.renderStatusTimer) clearTimeout(state.renderStatusTimer);
  state.renderStatusTimer = 0;
  if (els.renderStatus) els.renderStatus.hidden = true;
}

async function pollRenderStatus(menuId, attempt = 0) {
  clearRenderStatus();
  if (!menuId) return;
  try {
    const status = await bridge.apiGet(`menus/render-status/${encodeURIComponent(menuId)}`);
    showRenderStatus(status);
    if (status.status === "rendering" && attempt < 30) {
      state.renderStatusTimer = window.setTimeout(() => pollRenderStatus(menuId, attempt + 1), 1200);
    }
  } catch (error) {
    showRenderStatus({ status: "error", error: error.message });
  }
}

function showRenderStatus(status) {
  if (!els.renderStatus) return;
  const text = {
    rendering: "缓存生成中",
    ready: "缓存已更新",
    error: "缓存生成失败，指令暂不可直接发送",
    missing: "缓存尚未生成",
  }[status.status] || "缓存状态未知";
  els.renderStatus.hidden = false;
  els.renderStatus.className = `render-status is-${status.status}`;
  els.renderStatus.textContent = status.error ? `${text}：${status.error}` : (status.rendered_at ? `${text}（${status.rendered_at}）` : text);
}

function ensureStyle(menu) {
  menu.style = { ...defaultStyle(), ...(menu.style || {}) };
  return menu.style;
}

function defaultStyle() {
  return {
    theme: "aurora",
    primary_color: "#7c3aed",
    background_color: "#f8fafc",
    background_image: "",
    background_image_name: "",
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
    card_color: "#ffffff",
    text_color: "#111827",
    muted_color: "#6b7280",
    foreground_opacity: 92,
    radius: 24,
    width_mode: "auto",
    width: 760,
    columns: 2,
    show_updated_at: true,
  };
}

function syncWidthControl() {
  const isAuto = els.widthMode.value !== "custom";
  els.width.disabled = isAuto;
  els.width.closest(".field")?.classList.toggle("is-disabled", isAuto);
}

function applyThemePreset(theme) {
  const preset = THEME_PRESETS[theme] || THEME_PRESETS.aurora;
  els.primaryColor.value = preset.primary_color;
  els.backgroundColor.value = preset.background_color;
  els.cardColor.value = preset.card_color;
  els.textColor.value = preset.text_color;
  els.mutedColor.value = preset.muted_color;
}

function previewLayout(menu) {
  const style = ensureStyle(menu);
  const columns = clampNumber(style.columns, 1, 4, 2);
  const itemCount = menu.sections.reduce((total, section) => total + section.items.length, 0);
  if (style.width_mode === "custom") {
    return { width: clampNumber(style.width, 520, 1400, 760), columns, itemCount };
  }

  let desiredCardWidth = 190;
  menu.sections.forEach((section) => {
    section.items.forEach((item) => {
      const template = CARD_TEMPLATES[cardSize(item.card_size)];
      const textUnits = Math.max(
        String(item.label || "").length,
        String(item.command || "").length,
        Math.floor(String(item.description || "").length / 2),
      );
      desiredCardWidth = Math.max(desiredCardWidth, template.width, 150 + Math.min(150, textUnits * 6));
    });
  });

  const sectionTitleUnits = menu.sections.reduce((longest, section) => Math.max(longest, String(section.title || "").length), 0);
  const contentUnits = Math.max(
    String(menu.title || "").length,
    Math.floor(String(menu.subtitle || "").length / 2),
    sectionTitleUnits,
  );
  const chromeWidth = 24 * 2 + 22 * 2 + 15 * 2;
  const gridWidth = columns * desiredCardWidth + Math.max(0, columns - 1) * 10;
  const titleWidth = 260 + Math.min(260, contentUnits * 10);
  return { width: clampNumber(Math.max(gridWidth + chromeWidth, titleWidth), 520, 1200, 760), columns, itemCount };
}

function createItemFromTemplate(templateKey) {
  const key = cardSize(templateKey);
  const template = CARD_TEMPLATES[key];
  return {
    label: template.title,
    command: template.command,
    description: template.description,
    icon: template.icon,
    card_size: key,
    enabled: true,
  };
}

function cardSize(value) {
  return CARD_TEMPLATES[value] ? value : "standard";
}

function cardSizeOptions(selected) {
  return Object.entries(CARD_TEMPLATES)
    .map(([key, template]) => `<option value="${key}" ${key === selected ? "selected" : ""}>${template.label}</option>`)
    .join("");
}

function clampNumber(value, min, max, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, Math.round(number)));
}

function uniqueId(prefix) {
  const base = prefix.toLowerCase().replace(/[^a-z0-9_-]/g, "_").slice(0, 32) || "menu";
  let id = base;
  let i = 2;
  while (state.menus.some((menu) => menu.id === id)) id = `${base}_${i++}`;
  return id;
}

function toColor(value, fallback) {
  return /^#[0-9a-f]{6}$/i.test(value || "") ? value : fallback;
}

function setStatus(message, tone = "info") {
  els.status.textContent = message;
  els.status.dataset.tone = tone;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[ch]));
}

function escapeAttr(value) {
  return escapeHtml(value);
}
