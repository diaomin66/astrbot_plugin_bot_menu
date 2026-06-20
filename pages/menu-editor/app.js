const $ = (id) => document.getElementById(id);
let bridge = null;
const editorRuntime = window.MenuEditorRuntime || {};
const editorApi = window.MenuEditorApi || {};
const editorBackground = window.MenuEditorBackground || {};
const editorPreview = window.MenuEditorPreview || {};
const editorModal = window.MenuEditorModal || {};
const editorShortcuts = window.MenuEditorShortcuts || {};
const editorValidation = window.MenuEditorValidation || {};

function cloneData(value) {
  if (editorRuntime.cloneData) return editorRuntime.cloneData(value);
  if (typeof structuredClone === "function") return structuredClone(value);
  if (value === undefined) return undefined;
  return JSON.parse(JSON.stringify(value));
}

function safeStorageGet(key, fallback = "") {
  if (editorRuntime.safeStorageGet) return editorRuntime.safeStorageGet(key, fallback);
  try {
    return window.localStorage?.getItem(key) ?? fallback;
  } catch (error) {
    console.warn("localStorage get failed", error);
    return fallback;
  }
}

function safeStorageSet(key, value) {
  if (editorRuntime.safeStorageSet) return editorRuntime.safeStorageSet(key, value);
  try {
    window.localStorage?.setItem(key, value);
  } catch (error) {
    console.warn("localStorage set failed", error);
  }
}

function safeStorageRemove(key) {
  if (editorRuntime.safeStorageRemove) return editorRuntime.safeStorageRemove(key);
  try {
    window.localStorage?.removeItem(key);
  } catch (error) {
    console.warn("localStorage remove failed", error);
  }
}

function replaceChildrenSafe(node, ...children) {
  if (editorRuntime.replaceChildrenSafe) return editorRuntime.replaceChildrenSafe(node, ...children);
  if (!node) return;
  if (typeof node.replaceChildren === "function") {
    node.replaceChildren(...children);
    return;
  }
  while (node.firstChild) node.removeChild(node.firstChild);
  children.forEach((child) => node.append(child));
}

const CARD_TEMPLATES = {
  compact: { label: "紧凑", icon: "•", title: "快捷项", command: "/cmd", description: "", width: 190 },
  standard: { label: "标准", icon: "✨", title: "新功能", command: "/command", description: "功能说明", width: 230 },
  large: { label: "大卡", icon: "⭐", title: "重点功能", command: "/feature", description: "适合放较长描述或主推功能", width: 285 },
  banner: { label: "横幅", icon: "📌", title: "公告入口", command: "/notice", description: "横跨整行，用于公告、主入口或高优先级操作", width: 360 },
};

const THEME_PRESETS = {
  aurora: { label: "极光紫", primary_color: "#7c3aed", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#6b7280" },
  minimal: { label: "清爽蓝", primary_color: "#2563eb", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#64748b" },
  forest: { label: "森林绿", primary_color: "#059669", background_color: "#ecfdf5", card_color: "#ffffff", text_color: "#064e3b", muted_color: "#64748b" },
  sunrise: { label: "日出橙", primary_color: "#ea580c", background_color: "#fff7ed", card_color: "#ffffff", text_color: "#1f2937", muted_color: "#78716c" },
  morandi: { label: "莫兰迪雾", primary_color: "#8f9d8a", background_color: "#f1eee8", card_color: "#fbfaf6", text_color: "#3f4640", muted_color: "#7b8179" },
  sage: { label: "鼠尾草绿", primary_color: "#91a58f", background_color: "#eef3ed", card_color: "#fbfdf8", text_color: "#34403a", muted_color: "#73806f" },
  macaron: { label: "马卡龙粉", primary_color: "#f29ca3", background_color: "#fff1f3", card_color: "#ffffff", text_color: "#4a3a3f", muted_color: "#9b737b" },
  lavender: { label: "薰衣草奶", primary_color: "#a78bfa", background_color: "#f4f0ff", card_color: "#ffffff", text_color: "#3e3558", muted_color: "#83779e" },
  butter: { label: "奶油杏", primary_color: "#e8b86d", background_color: "#fff8e8", card_color: "#fffef9", text_color: "#4d4030", muted_color: "#917f62" },
  seaSalt: { label: "海盐薄荷", primary_color: "#5bb8a8", background_color: "#eefbf8", card_color: "#ffffff", text_color: "#264844", muted_color: "#6f8b86" },
};

const STYLE_COPY_KEYS = [
  "theme", "primary_color", "background_color", "background_image", "background_image_asset_id", "background_image_name",
  "background_image_x", "background_image_y", "background_image_width", "background_overlay", "background_blur", "background_brightness", "card_color", "text_color",
  "muted_color", "foreground_opacity", "radius", "width_mode", "width", "columns",
  "section_gap_mode", "section_gap", "font_family", "card_gap", "section_padding", "shadow_strength", "border_strength", "watermark", "show_updated_at",
];
const MENU_ID_PATTERN = editorValidation.MENU_ID_PATTERN || /^[A-Za-z0-9_-]{1,48}$/;
const DRAFT_PREFIX = "astrbot_plugin_bot_menu:draft:";
const COLLAPSE_PREFIX = "astrbot_plugin_bot_menu:collapsed:";
const HISTORY_LIMIT = 20;
const FIXED_DENSITY = "compact";

const state = {
  menus: [],
  serverMenuIds: new Set(),
  defaultMenuId: "default",
  currentId: null,
  menu: null,
  switchingMenu: false,
  dirty: false,
  saveState: "saved",
  itemSearch: "",
  restoredDraftIds: new Set(),
  collapsedKeys: new Set(),
  unsavedMenuIds: new Set(),
  selectedKeys: new Set(),
  history: [],
  historyIndex: -1,
  historyPaused: false,
  modalCloseHandler: null,
  renderStatusTimer: 0,
  backgroundEditMode: false,
  pendingBackgroundAsset: null,
};

const els = {
  schemeSelect: $("schemeSelect"),
  status: $("status"),
  saveState: $("saveState"),
  saveBtn: $("saveBtn"),
  undoBtn: $("undoBtn"),
  redoBtn: $("redoBtn"),
  deleteBtn: $("deleteBtn"),
  historyBtn: $("historyBtn"),
  backgroundEditToggleBtn: $("backgroundEditToggleBtn"),
  renderStatus: $("renderStatus"),
  validationSummary: $("validationSummary"),
  batchToolbar: $("batchToolbar"),
  batchCount: $("batchCount"),
  batchEnableBtn: $("batchEnableBtn"),
  batchDisableBtn: $("batchDisableBtn"),
  batchCopyBtn: $("batchCopyBtn"),
  batchDeleteBtn: $("batchDeleteBtn"),
  batchMoveUpBtn: $("batchMoveUpBtn"),
  batchMoveDownBtn: $("batchMoveDownBtn"),
  batchClearBtn: $("batchClearBtn"),
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
  sectionGapMode: $("sectionGapMode"),
  sectionGap: $("sectionGap"),
  radius: $("radius"),
  showUpdatedAt: $("showUpdatedAt"),
  itemSearch: $("itemSearch"),
  previewMeta: $("previewMeta"),
  editorModal: $("editorModal"),
  modalTitle: $("modalTitle"),
  modalBody: $("modalBody"),
  modalFooter: $("modalFooter"),
};

window.addEventListener("error", (event) => {
  const message = event.error?.message || event.message || "未知脚本错误";
  console.error("bot menu editor runtime error", event.error || event);
  setStatus(`页面脚本错误：${message}`, "error");
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason?.message || event.reason || "未知异步错误";
  console.error("bot menu editor async error", event.reason || event);
  setStatus(`页面异步错误：${reason}`, "error");
});

initializeEditor();

async function initializeEditor() {
  try {
    bindEvents();
    bridge = await resolvePageBridge();
    await loadMenus();
  } catch (error) {
    console.error("failed to initialize bot menu editor", error);
    setStatus(`页面初始化失败：${error.message || error}`, "error");
    updateSaveState("saved");
  }
}

function bindEvents() {
  els.schemeSelect.addEventListener("change", async () => {
    const nextId = els.schemeSelect.value;
    await switchMenu(nextId, { reason: "select" });
  });
  bindClick($("newBtn"), "新建菜单", newMenu);
  bindClick($("copyBtn"), "复制菜单", copyMenu);
  bindClick(els.deleteBtn, "删除菜单", deleteMenu);
  bindClick(els.undoBtn, "撤销", undoMenuChange);
  bindClick(els.redoBtn, "重做", redoMenuChange);
  bindClick(els.historyBtn, "打开历史版本", openHistoryPanel);
  bindClick(els.backgroundEditToggleBtn, "切换背景编辑模式", toggleBackgroundEditMode);
  bindClick($("saveBtn"), "保存菜单", saveMenu);
  bindClick($("copyStyleBtn"), "复制样式", copyStyleToMenus);
  bindClick($("resetStyleBtn"), "重置样式", resetCurrentStyle);
  bindClick($("addSectionBtn"), "添加分组", addSection);
  bindClick($("exportBtn"), "导出菜单", exportMenus);
  $("importInput").addEventListener("change", importMenus);
  bindClick(els.batchEnableBtn, "批量启用", () => batchSetEnabled(true));
  bindClick(els.batchDisableBtn, "批量禁用", () => batchSetEnabled(false));
  bindClick(els.batchCopyBtn, "批量复制", batchCopySelection);
  bindClick(els.batchDeleteBtn, "批量删除", batchDeleteSelection);
  bindClick(els.batchMoveUpBtn, "批量上移", () => batchMoveSelection(-1));
  bindClick(els.batchMoveDownBtn, "批量下移", () => batchMoveSelection(1));
  bindClick(els.batchClearBtn, "清除选择", clearSelection);
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
    "sectionGapMode",
    "sectionGap",
    "radius",
    "showUpdatedAt",
  ].forEach((id) => {
    bindValueChange($(id), () => {
      syncFormToMenu();
      renderAll();
    });
  });

  bindValueChange(els.theme, () => {
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
  bindValueChange(els.itemSearch, () => {
    state.itemSearch = els.itemSearch.value.trim().toLowerCase();
    saveSearchState();
    renderAll();
  });
  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
  syncThemeSelectOptions();
  renderThemePresetCards();
  bindPreviewInteractions();
  bindModalChrome();
  bindGlobalShortcuts();
  applyDensity();
  updateSaveState("saved");
}

function bindValueChange(control, handler) {
  if (!control) return;
  const events = control.type === "file" ? ["change"] : ["input", "change"];
  let lastValue = controlValueSignature(control);
  const emitChange = () => {
    const nextValue = controlValueSignature(control);
    if (nextValue === lastValue) return;
    lastValue = nextValue;
    handler(control);
  };
  events.forEach((eventName) => control.addEventListener(eventName, emitChange));
}

function controlValueSignature(control) {
  if (!control) return "";
  if (control.type === "checkbox") return control.checked ? "1" : "0";
  if (control.type === "file") return [...(control.files || [])].map((file) => `${file.name}:${file.size}:${file.lastModified}`).join("|");
  return String(control.value ?? "");
}

async function resolvePageBridge() {
  if (editorApi.resolvePageBridge) return editorApi.resolvePageBridge({ timeoutMs: 6000, sleep });
  const rawBridge = await waitForPageBridge();
  if (typeof rawBridge.ready === "function") {
    await rawBridge.ready();
  }
  return normalizePageBridge(rawBridge);
}

async function waitForPageBridge(timeoutMs = 6000) {
  const startedAt = Date.now();
  let pageBridge = findPageBridge();
  while (!pageBridge) {
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error("未检测到 AstrBot 页面桥接对象，请在 AstrBot Pages 中打开本页面。");
    }
    await sleep(40);
    pageBridge = findPageBridge();
  }
  return pageBridge;
}

function findPageBridge() {
  const candidates = [
    window.AstrBotPluginPage,
    window.AstrBotPage,
    window.PluginPage,
    window.astrBotPluginPage,
    window.astrbotPluginPage,
    window.astrbot?.pluginPage,
    window.astrbot?.page,
  ];
  try {
    if (window.parent && window.parent !== window) {
      candidates.push(
        window.parent.AstrBotPluginPage,
        window.parent.AstrBotPage,
        window.parent.PluginPage,
        window.parent.astrbot?.pluginPage,
        window.parent.astrbot?.page,
      );
    }
  } catch {
    // Cross-origin parent access can fail in some WebViews; polling local candidates is enough.
  }
  return candidates.find((candidate) => candidate && typeof candidate === "object") || null;
}

function normalizePageBridge(rawBridge) {
  const apiGet = rawBridge.apiGet || rawBridge.get || rawBridge.GET;
  const apiPost = rawBridge.apiPost || rawBridge.post || rawBridge.POST;
  if (typeof apiGet !== "function" || typeof apiPost !== "function") {
    throw new Error("AstrBot 页面桥接缺少 apiGet/apiPost，请升级 AstrBot 或刷新页面。");
  }
  return {
    apiGet: async (path) => unwrapBridgeResponse(await apiGet.call(rawBridge, path)),
    apiPost: async (path, payload) => unwrapBridgeResponse(await apiPost.call(rawBridge, path, payload)),
  };
}

function unwrapBridgeResponse(response) {
  if (editorApi.unwrapBridgeResponse) return editorApi.unwrapBridgeResponse(response);
  if (response && typeof response === "object" && "status" in response) {
    if (response.status === "ok") return response.data ?? {};
    if (response.status === "error") throw new Error(response.message || "请求失败");
  }
  return response ?? {};
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function runAction(label, handler) {
  if (editorRuntime.runAction) return editorRuntime.runAction(label, handler, setStatus);
  try {
    const result = handler();
    if (result && typeof result.catch === "function") {
      result.catch((error) => {
        console.error(`menu editor action failed: ${label}`, error);
        setStatus(`${label}失败：${error.message || error}`, "error");
      });
    }
    return result;
  } catch (error) {
    console.error(`menu editor action failed: ${label}`, error);
    setStatus(`${label}失败：${error.message || error}`, "error");
    return null;
  }
}

function bindClick(control, label, handler) {
  if (editorRuntime.bindClick) return editorRuntime.bindClick(control, label, handler, setStatus);
  if (!control) return;
  control.addEventListener("click", (event) => runAction(label, () => handler(event)));
}

async function loadMenus(preferredId) {
  try {
    setStatus("正在加载菜单...");
    const data = await bridge.apiGet("menus");
    state.menus = data.menus || [];
    setServerMenuIds(state.menus);
    state.unsavedMenuIds.clear();
    state.defaultMenuId = data.default_menu_id || "default";
    const target = preferredId || state.currentId || state.defaultMenuId || state.menus[0]?.id;
    refreshSchemeSelect();
    await selectMenu(target);
    setStatus("已加载。聊天中发送 /menu 可查看默认菜单，/menu 方案ID 可查看指定方案。");
  } catch (error) {
    setStatus(`加载失败：${error.message}`);
  }
}

function setServerMenuIds(menus) {
  state.serverMenuIds = new Set((menus || []).map((menu) => menu?.id).filter(Boolean));
}

async function switchMenu(id, { reason = "select" } = {}) {
  if (!id || state.switchingMenu) {
    refreshSchemeSelect();
    return false;
  }
  if (id === state.currentId) {
    refreshSchemeSelect();
    return true;
  }
  state.switchingMenu = true;
  const hadDirtyWork = state.dirty;
  try {
    stashActiveMenu();
    await selectMenu(id);
    if (hadDirtyWork && reason === "select") {
      setStatus("已切换菜单，上一份未保存修改已保留为本地草稿。", "warning");
    }
    return true;
  } catch (error) {
    console.error("failed to switch menu", error);
    setStatus(`切换菜单失败：${error.message || error}`, "error");
    refreshSchemeSelect();
    return false;
  } finally {
    state.switchingMenu = false;
  }
}

function stashActiveMenu() {
  if (!state.menu || !state.currentId) return;
  syncFormToMenu({ mark: false });
  if (!state.dirty && !state.unsavedMenuIds.has(state.currentId)) return;
  const previousId = state.currentId;
  const nextId = String(state.menu.id || previousId).trim() || previousId;
  state.menu.id = nextId;
  state.currentId = nextId;
  const keepPrevious = state.serverMenuIds.has(previousId) && previousId !== nextId;
  upsertMenuEntry(state.menu, { unsaved: true, previousId: keepPrevious ? "" : previousId });
  saveDraft();
  refreshSchemeSelect();
}

async function selectMenu(id) {
  const menu = state.menus.find((item) => item.id === id) || state.menus[0];
  if (!menu) return;
  state.currentId = menu.id;
  state.backgroundEditMode = false;
  discardPendingBackgroundAsset();
  const sourceMenu = cloneData(menu);
  const isUnsaved = state.unsavedMenuIds.has(menu.id);
  state.menu = isUnsaved ? sourceMenu : maybeRestoreDraft(sourceMenu);
  state.dirty = isUnsaved || state.menu !== sourceMenu;
  loadSearchState();
  refreshSchemeSelect();
  fillForm();
  resetLocalHistory(state.menu);
  state.selectedKeys.clear();
  renderAll();
  updateSaveState(state.dirty ? "dirty" : "saved");
  clearRenderStatus();
}

function refreshSchemeSelect() {
  els.schemeSelect.innerHTML = "";
  state.menus.forEach((menu) => {
    const option = document.createElement("option");
    option.value = menu.id;
    const badges = [];
    if (menu.id === state.defaultMenuId) badges.push("默认");
    if (state.unsavedMenuIds.has(menu.id)) badges.push("未保存");
    option.textContent = `${menu.name || menu.id} (${menu.id})${badges.length ? ` · ${badges.join(" · ")}` : ""}`;
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
  els.sectionGapMode.value = style.section_gap_mode || "auto";
  els.sectionGap.value = style.section_gap ?? 14;
  els.radius.value = style.radius ?? 24;
  els.showUpdatedAt.checked = style.show_updated_at !== false;
  syncWidthControl();
  syncSectionGapControl();
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
    section_gap_mode: els.sectionGapMode.value,
    section_gap: clampNumber(els.sectionGap.value, 0, 200, 14),
    radius: Number(els.radius.value) || 0,
    show_updated_at: els.showUpdatedAt.checked,
  };
  if (mark) markDirty();
  els.foregroundOpacityValue.textContent = `${state.menu.style.foreground_opacity}%`;
  syncWidthControl();
  syncSectionGapControl();
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
    bindDragSort(card, selectionKey("section", sectionIndex));
    card.innerHTML = `
      <div class="section-head">
        <label class="select-check" title="选择分组"><input type="checkbox" data-action="select-section" ${state.selectedKeys.has(selectionKey("section", sectionIndex)) ? "checked" : ""} /></label>
        <button type="button" class="collapse-toggle" data-action="toggle-section" aria-expanded="${!sectionCollapsed}" title="${sectionCollapsed ? "展开分组" : "折叠分组"}">${sectionCollapsed ? "▸" : "▾"}</button>
        <input class="section-title-input" data-error-key="section-${sectionIndex}-title" value="${escapeAttr(section.title)}" aria-label="分组标题" />
        <div class="actions">
          <button type="button" data-action="add-item">添加菜单项</button>
          <button type="button" data-action="move-up" ${sectionIndex === 0 ? "disabled" : ""}>上移</button>
          <button type="button" data-action="move-down" ${sectionIndex === state.menu.sections.length - 1 ? "disabled" : ""}>下移</button>
          <button type="button" data-action="copy-section">复制</button>
          <button type="button" data-action="remove-section" class="danger">删除分组</button>
        </div>
      </div>
      <div class="section-body" ${sectionCollapsed ? "hidden" : ""}>
        <div class="items-editor"></div>
      </div>`;
    const titleInput = card.querySelector("input");
    bindValueChange(titleInput, () => {
      section.title = titleInput.value;
      markDirty();
      renderPreview();
      validateMenu({ silent: true });
    });
    card.querySelector('[data-action="toggle-section"]').addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      setCollapsed("section", sectionIndex, null, !sectionCollapsed);
      renderSectionsEditor();
    });
    card.querySelector('[data-action="select-section"]').addEventListener("change", (event) => {
      event.stopPropagation();
      toggleSelection(selectionKey("section", sectionIndex), event.target.checked);
    });
    card.querySelector('[data-action="add-item"]').addEventListener("click", () => addItem(sectionIndex, "standard"));
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
  updateBatchToolbar();
}

function renderItemEditor(item, sectionIndex, itemIndex) {
  const card = document.createElement("article");
  const currentSize = cardSize(item.card_size);
  const itemCollapsed = isCollapsed("item", sectionIndex, itemIndex);
  card.className = `item-card size-${currentSize} ${itemCollapsed ? "is-collapsed" : ""}`;
  card.dataset.errorKey = `item-${sectionIndex}-${itemIndex}`;
  bindDragSort(card, selectionKey("item", sectionIndex, itemIndex));
    card.innerHTML = `
    <div class="item-head">
      <label class="select-check" title="选择卡片"><input type="checkbox" data-action="select-item" ${state.selectedKeys.has(selectionKey("item", sectionIndex, itemIndex)) ? "checked" : ""} /></label>
      <button type="button" class="collapse-toggle" data-action="toggle-item" aria-expanded="${!itemCollapsed}" title="${itemCollapsed ? "展开菜单项" : "折叠菜单项"}">${itemCollapsed ? "▸" : "▾"}</button>
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
        <label class="field"><span>卡片样式</span><select data-key="card_size">${cardSizeOptions(currentSize)}</select></label>
        <label class="field"><span>名称</span><input data-error-key="item-${sectionIndex}-${itemIndex}-label" data-key="label" value="${escapeAttr(item.label || "")}" /></label>
        <label class="field"><span>指令</span><input data-error-key="item-${sectionIndex}-${itemIndex}-command" data-key="command" value="${escapeAttr(item.command || "")}" /></label>
        <label class="field wide"><span>描述</span><input data-error-key="item-${sectionIndex}-${itemIndex}-description" data-key="description" value="${escapeAttr(item.description || "")}" /></label>
      </div>
      <label class="check"><input data-key="enabled" type="checkbox" ${item.enabled !== false ? "checked" : ""} /> 启用</label>
    </div>`;
  card.querySelector('[data-action="toggle-item"]').addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    setCollapsed("item", sectionIndex, itemIndex, !itemCollapsed);
    renderSectionsEditor();
  });
  card.querySelector('[data-action="select-item"]').addEventListener("change", (event) => {
    event.stopPropagation();
    toggleSelection(selectionKey("item", sectionIndex, itemIndex), event.target.checked);
  });
  card.querySelector('[data-action="move-up"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, -1));
  card.querySelector('[data-action="move-down"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, 1));
  card.querySelector('[data-action="copy-item"]').addEventListener("click", () => copyItem(sectionIndex, itemIndex));
  card.querySelector('[data-action="remove-item"]').addEventListener("click", () => removeItem(sectionIndex, itemIndex));
  card.querySelectorAll("[data-key]").forEach((input) => {
    bindValueChange(input, () => {
      const key = input.dataset.key;
      item[key] = input.type === "checkbox" ? input.checked : input.value;
      markDirty();
      if (key === "card_size") renderSectionsEditor();
      renderPreview();
      validateMenu({ silent: true });
    });
  });
  return card;
}


function bindPreviewInteractions() {
  if (!els.preview) return;
  els.preview.addEventListener("click", (event) => {
    if (!state.menu || event.defaultPrevented) return;
    if (event.target.closest(".background-transform-box, .resize-handle")) return;
    if (state.backgroundEditMode) {
      event.preventDefault();
      event.stopPropagation();
      setStatus("当前处于背景图编辑模式。请先点击“锁定背景图”再编辑卡片。", "warning");
      return;
    }
    const target = event.target.closest("[data-edit]");
    if (!target || !els.preview.contains(target)) return;
    event.preventDefault();
    event.stopPropagation();
    const sectionIndex = Number(target.dataset.sectionIndex);
    const itemIndex = Number(target.dataset.itemIndex);
    if (target.dataset.edit === "item") return openItemEditor(sectionIndex, itemIndex);
    if (target.dataset.edit === "section") return openSectionEditor(sectionIndex);
    if (target.dataset.edit === "menu") return openMenuEditor();
    openStyleEditor();
  });
}

function bindModalChrome() {
  if (!els.editorModal) return;
  els.editorModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-modal]")) closeModal();
  });
  window.addEventListener("keydown", (event) => {
    const isOpen = editorModal.modalIsOpen ? editorModal.modalIsOpen(els.editorModal) : !els.editorModal.hidden;
    if (event.key === "Escape" && isOpen) closeModal();
  });
}

function bindGlobalShortcuts() {
  window.addEventListener("keydown", (event) => {
    const target = event.target;
    const isTyping = editorShortcuts.isTypingTarget ? editorShortcuts.isTypingTarget(target) : (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveMenu();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) redoMenuChange();
      else undoMenuChange();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
      event.preventDefault();
      redoMenuChange();
      return;
    }
    if (event.key === "/" && !isTyping) {
      event.preventDefault();
      els.itemSearch?.focus();
      return;
    }
  });
}

function openModal(title, body, actions = [], options = {}) {
  if (state.modalCloseHandler) {
    const previousCloseHandler = state.modalCloseHandler;
    state.modalCloseHandler = null;
    previousCloseHandler();
  }
  state.modalCloseHandler = typeof options.onClose === "function" ? options.onClose : null;
  els.modalTitle.textContent = title;
  replaceChildrenSafe(els.modalBody, body);
  replaceChildrenSafe(els.modalFooter);
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    if (action.className) button.className = action.className;
    button.disabled = Boolean(action.disabled);
    button.addEventListener("click", action.onClick);
    els.modalFooter.append(button);
  });
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "关闭";
  close.addEventListener("click", closeModal);
  els.modalFooter.append(close);
  els.editorModal.hidden = false;
}

function closeModal() {
  if (els.editorModal) els.editorModal.hidden = true;
  const handler = state.modalCloseHandler;
  state.modalCloseHandler = null;
  if (handler) handler();
}

function resolveAndCloseModal(resolve, value) {
  state.modalCloseHandler = null;
  resolve(value);
  closeModal();
}

function confirmDialog(title, message, { confirmLabel = "确定", cancelLabel = "取消", danger = false } = {}) {
  return new Promise((resolve) => {
    const body = document.createElement("div");
    body.className = "confirm-dialog";
    const text = document.createElement("p");
    text.textContent = message;
    body.append(text);
    openModal(title, body, [
      { label: cancelLabel, onClick: () => resolveAndCloseModal(resolve, false) },
      { label: confirmLabel, className: danger ? "danger" : "primary", onClick: () => resolveAndCloseModal(resolve, true) },
    ], { onClose: () => resolve(false) });
  });
}

function commitMenuChange({ keepModal = true } = {}) {
  markDirty();
  fillForm();
  renderAll();
  validateMenu({ silent: true });
  if (!keepModal) closeModal();
}

function field(label, control, { wide = false, hint = "", errorKey = "" } = {}) {
  const wrap = document.createElement("label");
  wrap.className = `field${wide ? " wide" : ""}`;
  const span = document.createElement("span");
  span.textContent = label;
  wrap.append(span, control);
  if (errorKey) control.dataset.errorKey = errorKey;
  if (hint) {
    const small = document.createElement("small");
    small.textContent = hint;
    wrap.append(small);
  }
  return wrap;
}

function textInput(value, onInput, attrs = {}) {
  const input = document.createElement(attrs.multiline ? "textarea" : "input");
  if (!attrs.multiline) input.type = attrs.type || "text";
  input.value = value || "";
  Object.entries(attrs).forEach(([key, value]) => {
    if (["type", "multiline"].includes(key) || value === undefined || value === false) return;
    if (value === true) input.setAttribute(key, "");
    else input.setAttribute(key, value);
  });
  bindValueChange(input, () => onInput(input.value, input));
  return input;
}

function selectInput(value, options, onInput) {
  const select = document.createElement("select");
  select.innerHTML = options.map((option) => `<option value="${escapeAttr(option.value)}" ${String(option.value) === String(value) ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("");
  let lastValue = String(select.value);
  const emitChange = () => {
    const nextValue = String(select.value);
    if (nextValue === lastValue) return;
    lastValue = nextValue;
    onInput(select.value, select);
  };
  select.addEventListener("input", emitChange);
  select.addEventListener("change", emitChange);
  return select;
}

function checkboxInput(checked, onInput) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = checked;
  bindValueChange(input, () => onInput(input.checked, input));
  return input;
}

function actionRow(actions) {
  const row = document.createElement("div");
  row.className = "action-row";
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    if (action.className) button.className = action.className;
    button.disabled = Boolean(action.disabled);
    button.addEventListener("click", action.onClick);
    row.append(button);
  });
  return row;
}

function appendLayoutFields(body, style = ensureStyle(state.menu)) {
  const controls = createLayoutControls(style);
  body.append(
    field("宽度模式", controls.widthMode),
    field("每行卡片", controls.columns),
    field("手动宽度", controls.width),
    field("分组间距", controls.sectionGapMode),
    field("间距数值", controls.sectionGap),
  );
  controls.syncDisabled();
  return controls;
}

function createLayoutControls(initialStyle = ensureStyle(state.menu)) {
  let widthInput;
  let sectionGapInput;
  const getStyle = () => ensureStyle(state.menu);

  const commitLayoutChange = () => {
    commitMenuChange();
    const style = getStyle();
    syncLayoutControlDisabled(widthInput, style.width_mode !== "custom");
    syncLayoutControlDisabled(sectionGapInput, style.section_gap_mode !== "custom");
  };

  const widthModeSelect = selectInput(
    initialStyle.width_mode || "auto",
    [{ value: "auto", label: "智能自动" }, { value: "custom", label: "手动指定" }],
    (value) => {
      const style = getStyle();
      setLayoutWidthMode(style, value);
      if (widthInput) widthInput.value = style.width || 760;
      commitLayoutChange();
    },
  );
  const columnsSelect = selectInput(
    initialStyle.columns || 2,
    [1, 2, 3, 4].map((value) => ({ value, label: `${value} 张` })),
    (value) => {
      const style = getStyle();
      style.columns = clampNumber(value, 1, 4, 2);
      commitLayoutChange();
    },
  );
  widthInput = textInput(initialStyle.width || 760, (value) => {
    const style = getStyle();
    style.width = clampNumber(value, 520, 1400, 760);
    commitLayoutChange();
  }, { type: "number", min: 520, max: 1400, disabled: initialStyle.width_mode !== "custom" });

  const sectionGapModeSelect = selectInput(
    initialStyle.section_gap_mode || "auto",
    [{ value: "auto", label: "智能" }, { value: "custom", label: "自定义" }],
    (value) => {
      const style = getStyle();
      setLayoutSectionGapMode(style, value);
      if (sectionGapInput) sectionGapInput.value = style.section_gap ?? 14;
      commitLayoutChange();
    },
  );
  sectionGapInput = textInput(
    initialStyle.section_gap_mode === "custom" ? initialStyle.section_gap : autoSectionGapForMenu(state.menu),
    (value) => {
      const style = getStyle();
      style.section_gap = clampNumber(value, 0, 200, 14);
      commitLayoutChange();
    },
    { type: "number", min: 0, max: 200, disabled: initialStyle.section_gap_mode !== "custom" },
  );

  return {
    widthMode: widthModeSelect,
    columns: columnsSelect,
    width: widthInput,
    sectionGapMode: sectionGapModeSelect,
    sectionGap: sectionGapInput,
    syncDisabled: () => {
      const style = getStyle();
      syncLayoutControlDisabled(widthInput, style.width_mode !== "custom");
      syncLayoutControlDisabled(sectionGapInput, style.section_gap_mode !== "custom");
    },
  };
}

function setLayoutWidthMode(style, value) {
  const nextMode = value === "custom" ? "custom" : "auto";
  if (nextMode === "custom" && style.width_mode !== "custom") {
    style.width = autoWidthForMenu(state.menu);
  } else {
    style.width = clampNumber(style.width, 520, 1400, 760);
  }
  style.width_mode = nextMode;
}

function setLayoutSectionGapMode(style, value) {
  const nextMode = value === "custom" ? "custom" : "auto";
  if (nextMode === "custom" && style.section_gap_mode !== "custom") {
    style.section_gap = autoSectionGapForMenu(state.menu);
  } else {
    style.section_gap = clampNumber(style.section_gap, 0, 200, 14);
  }
  style.section_gap_mode = nextMode;
}

function autoWidthForMenu(menu) {
  return previewLayout({ ...menu, style: styleSnapshot(menu, { width_mode: "auto" }) }).width;
}

function autoSectionGapForMenu(menu) {
  return sectionGapForMenu({ ...menu, style: styleSnapshot(menu, { section_gap_mode: "auto" }) });
}

function styleSnapshot(menu, patch = {}) {
  return { ...defaultStyle(), ...(menu?.style || {}), ...patch };
}

function syncLayoutControlDisabled(control, disabled) {
  if (!control) return;
  control.disabled = disabled;
  control.closest(".field")?.classList.toggle("is-disabled", disabled);
}

function openMenuEditor() {
  const menu = state.menu;
  const body = document.createElement("div");
  body.className = "modal-grid";
  body.append(
    field("方案 ID", textInput(menu.id, (value) => { menu.id = value.trim(); commitMenuChange(); }, { maxlength: 48 }), { errorKey: "menuId" }),
    field("方案名称", textInput(menu.name, (value) => { menu.name = value; commitMenuChange(); }, { maxlength: 80 }), { errorKey: "menuName" }),
    field("别名（逗号分隔）", textInput((menu.aliases || []).join(", "), (value) => { menu.aliases = value.split(",").map((item) => item.trim()).filter(Boolean); commitMenuChange(); }, { maxlength: 220 }), { wide: true }),
    field("标题", textInput(menu.title, (value) => { menu.title = value; commitMenuChange(); }, { maxlength: 120 }), { wide: true, errorKey: "menuTitle" }),
    field("副标题", textInput(menu.subtitle, (value) => { menu.subtitle = value; commitMenuChange(); }, { maxlength: 240 }), { wide: true, errorKey: "menuSubtitle" }),
    field("页脚", textInput(menu.footer, (value) => { menu.footer = value; commitMenuChange(); }, { maxlength: 240 }), { wide: true, errorKey: "menuFooter" }),
  );
  appendLayoutFields(body, ensureStyle(menu));
  const list = document.createElement("div");
  list.className = "entity-list wide";
  list.dataset.errorKey = "sections";
  menu.sections.forEach((section, index) => {
    const row = document.createElement("article");
    row.className = "entity-row";
    row.innerHTML = `<div class="entity-title"><strong>${escapeHtml(section.title || "未命名分组")}</strong><small>${section.items?.length || 0} 张卡片 · 点击“编辑卡片”进入单分组编辑</small></div>`;
    row.append(actionRow([
      { label: "编辑卡片", onClick: () => openSectionEditor(index) },
      { label: "上移", disabled: index === 0, onClick: () => { moveSection(index, -1); openMenuEditor(); } },
      { label: "下移", disabled: index === menu.sections.length - 1, onClick: () => { moveSection(index, 1); openMenuEditor(); } },
      { label: "复制", onClick: () => { copySection(index); openMenuEditor(); } },
      { label: "删除", className: "danger", disabled: menu.sections.length <= 1, onClick: () => { if (confirm("确定删除这个分组？")) { removeSection(index); openMenuEditor(); } } },
    ]));
    list.append(row);
  });
  body.append(list);
  openModal("编辑基础信息与全部分组", body, [
    { label: "添加分组", className: "primary", onClick: () => { addSection(); openMenuEditor(); } },
    { label: "主题与背景", onClick: openStyleEditor },
  ]);
}

function openSectionEditor(sectionIndex) {
  const section = state.menu.sections?.[sectionIndex];
  if (!section) return openMenuEditor();
  const body = document.createElement("div");
  body.className = "modal-grid";
  body.append(
    field("分组标题", textInput(section.title, (value) => { section.title = value; commitMenuChange(); }, { maxlength: 80 }), { wide: true, errorKey: `section-${sectionIndex}-title` }),
  );
  const list = document.createElement("div");
  list.className = "entity-list wide";
  list.dataset.errorKey = `section-${sectionIndex}`;
  (section.items || []).forEach((item, itemIndex) => {
    const row = document.createElement("article");
    row.className = "entity-row";
    row.innerHTML = `<div class="entity-title"><strong>${escapeHtml(item.icon || "?")} ${escapeHtml(item.label || "未命名卡片")}</strong><small>${escapeHtml(item.command || "无指令")} · ${escapeHtml(CARD_TEMPLATES[cardSize(item.card_size)].label)}</small></div>`;
    row.append(actionRow([
      { label: "编辑内容", onClick: () => openItemEditor(sectionIndex, itemIndex) },
      { label: "上移", disabled: itemIndex === 0, onClick: () => { moveItem(sectionIndex, itemIndex, -1); openSectionEditor(sectionIndex); } },
      { label: "下移", disabled: itemIndex === section.items.length - 1, onClick: () => { moveItem(sectionIndex, itemIndex, 1); openSectionEditor(sectionIndex); } },
      { label: "复制", onClick: () => { copyItem(sectionIndex, itemIndex); openSectionEditor(sectionIndex); } },
      { label: "删除", className: "danger", disabled: section.items.length <= 1, onClick: () => { if (confirm("确定删除这张卡片？")) { removeItem(sectionIndex, itemIndex); openSectionEditor(sectionIndex); } } },
    ]));
    list.append(row);
  });
  body.append(list);
  openModal(`编辑分组：${section.title || "未命名"}`, body, [
    { label: "添加卡片", className: "primary", onClick: () => { addItem(sectionIndex, "standard"); openSectionEditor(sectionIndex); } },
    { label: "编辑全部分组", onClick: openMenuEditor },
  ]);
}

function openItemEditor(sectionIndex, itemIndex) {
  const section = state.menu.sections?.[sectionIndex];
  const item = section?.items?.[itemIndex];
  if (!item) return openSectionEditor(sectionIndex);
  const body = document.createElement("div");
  body.className = "modal-grid";
  body.append(
    field("图标", textInput(item.icon, (value) => { item.icon = value; commitMenuChange(); }, { maxlength: 12 }), { errorKey: `item-${sectionIndex}-${itemIndex}-icon` }),
    field("卡片样式", selectInput(cardSize(item.card_size), Object.entries(CARD_TEMPLATES).map(([value, template]) => ({ value, label: template.label })), (value) => { item.card_size = value; commitMenuChange(); }), { errorKey: `item-${sectionIndex}-${itemIndex}-card_size` }),
    field("名称", textInput(item.label, (value) => { item.label = value; commitMenuChange(); }, { maxlength: 80 }), { wide: true, errorKey: `item-${sectionIndex}-${itemIndex}-label` }),
    field("指令", textInput(item.command, (value) => { item.command = value; commitMenuChange(); }, { maxlength: 120 }), { wide: true, errorKey: `item-${sectionIndex}-${itemIndex}-command` }),
    field("描述", textInput(item.description, (value) => { item.description = value; commitMenuChange(); }, { multiline: true, maxlength: 240 }), { wide: true, errorKey: `item-${sectionIndex}-${itemIndex}-description` }),
  );
  const check = document.createElement("label");
  check.className = "check wide";
  check.append(checkboxInput(item.enabled !== false, (checked) => { item.enabled = checked; commitMenuChange(); }), document.createTextNode("启用这张卡片"));
  body.append(check);
  openModal(`编辑卡片：${item.label || "未命名"}`, body, [
    { label: "复制卡片", onClick: () => { copyItem(sectionIndex, itemIndex); openSectionEditor(sectionIndex); } },
    { label: "删除卡片", className: "danger", disabled: section.items.length <= 1, onClick: () => { if (confirm("确定删除这张卡片？")) { removeItem(sectionIndex, itemIndex); openSectionEditor(sectionIndex); } } },
    { label: "返回分组", onClick: () => openSectionEditor(sectionIndex) },
  ]);
}

function openStyleEditor() {
  const style = ensureStyle(state.menu);
  const updateStyle = (mutator) => {
    mutator(ensureStyle(state.menu));
    commitMenuChange();
  };
  const body = document.createElement("div");
  body.className = "modal-grid";
  const themeCards = document.createElement("div");
  themeCards.className = "theme-preset-cards wide";
  Object.entries(THEME_PRESETS).forEach(([key, preset]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `theme-card${(style.theme || "aurora") === key ? " is-active" : ""}`;
    button.style.cssText = `--swatch-primary:${preset.primary_color};--swatch-bg:${preset.background_color};--swatch-card:${preset.card_color};--swatch-text:${preset.text_color}`;
    button.innerHTML = `<span class="theme-swatch"></span><strong>${escapeHtml(preset.label)}</strong>`;
    button.addEventListener("click", () => {
      updateStyle((currentStyle) => Object.assign(currentStyle, { theme: key }, themeStylePatch(preset)));
      openStyleEditor();
    });
    themeCards.append(button);
  });
  body.append(themeCards);
  body.append(
    field("主题", selectInput(style.theme || "aurora", Object.entries(THEME_PRESETS).map(([value, preset]) => ({ value, label: preset.label })), (value) => { updateStyle((currentStyle) => Object.assign(currentStyle, { theme: value }, themeStylePatch(THEME_PRESETS[value] || THEME_PRESETS.aurora))); openStyleEditor(); })),
    field("主色", textInput(toColor(style.primary_color, "#7c3aed"), (value) => { updateStyle((currentStyle) => { currentStyle.primary_color = value; }); }, { type: "color" })),
    field("背景色", textInput(toColor(style.background_color, "#f8fafc"), (value) => { updateStyle((currentStyle) => { currentStyle.background_color = value; }); }, { type: "color" })),
    field("卡片色", textInput(toColor(style.card_color, "#ffffff"), (value) => { updateStyle((currentStyle) => { currentStyle.card_color = value; }); }, { type: "color" })),
    field("文字色", textInput(toColor(style.text_color, "#111827"), (value) => { updateStyle((currentStyle) => { currentStyle.text_color = value; }); }, { type: "color" })),
    field("辅助文字", textInput(toColor(style.muted_color, "#6b7280"), (value) => { updateStyle((currentStyle) => { currentStyle.muted_color = value; }); }, { type: "color" })),
    field("字体族", textInput(style.font_family || "", (value) => { updateStyle((currentStyle) => { currentStyle.font_family = value; }); }, { placeholder: "例如：Noto Sans CJK SC, Microsoft YaHei" }), { wide: true }),
  );
  const opacity = textInput(clampNumber(style.foreground_opacity, 0, 100, 92), (value, input) => {
    updateStyle((currentStyle) => {
      currentStyle.foreground_opacity = clampNumber(value, 0, 100, 92);
      if (input.previousElementSibling) input.previousElementSibling.textContent = `前景菜单透明度 ${currentStyle.foreground_opacity}%`;
    });
  }, { type: "range", min: 0, max: 100, step: 1 });
  body.append(field(`前景菜单透明度 ${clampNumber(style.foreground_opacity, 0, 100, 92)}%`, opacity, { wide: true }));
  appendLayoutFields(body, style);
  body.append(
    field("圆角", textInput(style.radius ?? 24, (value) => { updateStyle((currentStyle) => { currentStyle.radius = clampNumber(value, 0, 48, 24); }); }, { type: "number", min: 0, max: 48 })),
    field("卡片间距", textInput(style.card_gap ?? 10, (value) => { updateStyle((currentStyle) => { currentStyle.card_gap = clampNumber(value, 0, 60, 10); }); }, { type: "number", min: 0, max: 60 })),
    field("分组内边距", textInput(style.section_padding ?? 15, (value) => { updateStyle((currentStyle) => { currentStyle.section_padding = clampNumber(value, 0, 80, 15); }); }, { type: "number", min: 0, max: 80 })),
    field("阴影强度", textInput(style.shadow_strength ?? 1, (value) => { updateStyle((currentStyle) => { currentStyle.shadow_strength = clampNumber(value, 0, 5, 1); }); }, { type: "number", min: 0, max: 5 })),
    field("边框强度", textInput(style.border_strength ?? 1, (value) => { updateStyle((currentStyle) => { currentStyle.border_strength = clampNumber(value, 0, 5, 1); }); }, { type: "number", min: 0, max: 5 })),
    field("水印文本", textInput(style.watermark || "", (value) => { updateStyle((currentStyle) => { currentStyle.watermark = value; }); }, { maxlength: 80 }), { wide: true }),
  );
  const updatedAt = document.createElement("label");
  updatedAt.className = "check wide";
  updatedAt.append(checkboxInput(style.show_updated_at !== false, (checked) => { updateStyle((currentStyle) => { currentStyle.show_updated_at = checked; }); }), document.createTextNode("显示实时预览/更新时间"));
  body.append(updatedAt);

  const file = document.createElement("input");
  file.type = "file";
  file.accept = "image/*";
  file.addEventListener("change", async () => {
    const selected = file.files?.[0];
    if (selected) await applyBackgroundFile(selected);
    openStyleEditor();
  });
  body.append(field("自定义背景图（不限制尺寸）", file, { wide: true, hint: style.background_image ? (style.background_image_name || "Custom background") : "未设置背景图" }));
  body.append(
    field("背景缩放", textInput(clampNumber(style.background_image_width, 10, 600, 100), (value) => { updateStyle((currentStyle) => { currentStyle.background_image_width = clampNumber(value, 10, 600, 100); }); }, { type: "range", min: 10, max: 600, step: 1 }), { wide: true }),
    field("背景 X(%)", textInput(style.background_image_x || 0, (value) => { updateStyle((currentStyle) => { currentStyle.background_image_x = clampNumber(value, -300, 300, 0); }); }, { type: "number", min: -300, max: 300 })),
    field("背景 Y(%)", textInput(style.background_image_y || 0, (value) => { updateStyle((currentStyle) => { currentStyle.background_image_y = clampNumber(value, -300, 300, 0); }); }, { type: "number", min: -300, max: 300 })),
    field("背景遮罩(%)", textInput(style.background_overlay || 0, (value) => { updateStyle((currentStyle) => { currentStyle.background_overlay = clampNumber(value, 0, 100, 0); }); }, { type: "number", min: 0, max: 100 })),
    field("背景模糊(px)", textInput(style.background_blur || 0, (value) => { updateStyle((currentStyle) => { currentStyle.background_blur = clampNumber(value, 0, 40, 0); }); }, { type: "number", min: 0, max: 40 })),
    field("背景亮度(%)", textInput(style.background_brightness ?? 100, (value) => { updateStyle((currentStyle) => { currentStyle.background_brightness = clampNumber(value, 20, 200, 100); }); }, { type: "number", min: 20, max: 200 })),
  );
  body.append(actionRow([
    { label: "居中背景", onClick: () => { centerBackgroundImage(); openStyleEditor(); } },
    { label: "铺满背景", onClick: () => { fitBackgroundToCover(true); openStyleEditor(); } },
    { label: "适应背景", onClick: () => { fitBackgroundToContain(); openStyleEditor(); } },
    { label: "重置背景", onClick: () => { clearBackgroundImage(); openStyleEditor(); } },
  ]));
  openModal("编辑主题、背景与布局", body, [
    { label: "复制样式到其他菜单", onClick: copyStyleToMenus },
    { label: "一键修复颜色", onClick: () => { fixContrastColors(); openStyleEditor(); } },
    { label: "一键重置样式", className: "danger", onClick: () => { resetCurrentStyle(); openStyleEditor(); } },
    { label: "编辑全部分组", onClick: openMenuEditor },
  ]);
  const contrast = contrastWarningText(style);
  if (contrast) setStatus(contrast, "warning");
}

function themeStylePatch(preset) {
  const { label, ...stylePatch } = preset;
  return stylePatch;
}

async function applyBackgroundFile(file) {
  if (!file.type.startsWith("image/")) {
    setStatus("请选择图片文件作为背景。", "error");
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    setStatus("背景图文件较大，可能影响保存和加载速度，但不会限制上传尺寸。", "warning");
  }
  const pending = await createPendingBackgroundAsset(file);
  discardPendingBackgroundAsset();
  state.pendingBackgroundAsset = pending;
  Object.assign(ensureStyle(state.menu), {
    background_image: pending.previewUrl,
    background_image_asset_id: "",
    background_image_name: file.name,
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  commitMenuChange();
  fitBackgroundToCover(true);
}

async function createPendingBackgroundAsset(file) {
  if (editorBackground.createPendingBackground) {
    const pending = editorBackground.createPendingBackground(file);
    return {
      ...pending,
      previewUrl: pending.objectUrl || await pending.dataUrlPromise,
    };
  }
  const dataUrl = await readFileAsDataUrl(file);
  return {
    name: file.name || "background",
    size: file.size || 0,
    type: file.type || "",
    objectUrl: "",
    previewUrl: dataUrl,
    dataUrlPromise: Promise.resolve(dataUrl),
  };
}

function discardPendingBackgroundAsset() {
  if (!state.pendingBackgroundAsset) return;
  if (editorBackground.revokePendingBackground) editorBackground.revokePendingBackground(state.pendingBackgroundAsset);
  state.pendingBackgroundAsset = null;
}

async function flushPendingBackgroundAsset() {
  const pending = state.pendingBackgroundAsset;
  if (!pending || !state.menu) return;
  const style = ensureStyle(state.menu);
  const shouldFlush = style.background_image === pending.previewUrl || style.background_image === pending.objectUrl;
  if (!shouldFlush) {
    discardPendingBackgroundAsset();
    return;
  }
  const dataUrl = await pending.dataUrlPromise;
  const asset = await saveBackgroundAsset(dataUrl, pending.name);
  style.background_image = dataUrl;
  style.background_image_asset_id = asset?.id || "";
  style.background_image_name = pending.name;
  discardPendingBackgroundAsset();
  syncBackgroundControls();
  renderPreview();
}

function renderPreview() {
  const menu = state.menu;
  if (!menu) return;
  const style = ensureStyle(menu);
  const layout = previewLayout(menu);
  const deviceLabel = applyPreviewDeviceLayout(layout);
  const query = state.itemSearch || "";
  const previewStyle = [
    `--preview-primary:${style.primary_color}`,
    `--preview-bg:${style.background_color}`,
    `--preview-card:${style.card_color}`,
    `--preview-text:${style.text_color || "#111827"}`,
    `--preview-muted:${style.muted_color || "#6b7280"}`,
    `--preview-radius:${style.radius || 24}px`,
    `--preview-font-family:${style.font_family ? `"${String(style.font_family).replace(/"/g, "")}", sans-serif` : "inherit"}`,
    `--preview-width:${layout.width}px`,
    `--preview-columns:${layout.columns}`,
    `--preview-section-gap:${sectionGapForMenu(menu)}px`,
    `--preview-card-gap:${clampNumber(style.card_gap, 0, 60, 10)}px`,
    `--preview-section-padding:${clampNumber(style.section_padding, 0, 80, 15)}px`,
    `--preview-shadow-strength:${clampNumber(style.shadow_strength, 0, 5, 1)}`,
    `--preview-border-strength:${clampNumber(style.border_strength, 0, 5, 1)}`,
    `--preview-bg-overlay:${clampNumber(style.background_overlay, 0, 100, 0) / 100}`,
    `--preview-bg-blur:${clampNumber(style.background_blur, 0, 40, 0)}px`,
    `--preview-bg-brightness:${clampNumber(style.background_brightness, 20, 200, 100) / 100}`,
    `--preview-foreground-opacity:${clampNumber(style.foreground_opacity, 0, 100, 92) / 100}`,
  ].join(";");
  const backgroundMarkup = style.background_image ? `
        <img class="preview-bg-image" alt="" src="${escapeAttr(style.background_image)}" style="left:${style.background_image_x || 0}%;top:${style.background_image_y || 0}%;width:${style.background_image_width || 100}%;" />
        ${state.backgroundEditMode ? `<div class="background-transform-box" aria-label="拖动或拉伸背景图">
          <span class="resize-handle nw" data-handle="nw"></span>
          <span class="resize-handle ne" data-handle="ne"></span>
          <span class="resize-handle sw" data-handle="sw"></span>
          <span class="resize-handle se" data-handle="se"></span>
        </div>` : ""}` : "";
  els.preview.innerHTML = `
    <div class="preview-fit" style="--preview-scale:1">
      <div class="preview-card ${state.backgroundEditMode ? "is-bg-editing" : ""}" data-edit="style" data-layer-label="主题 / 背景 / 布局" style="${previewStyle}">
        ${backgroundMarkup}
        <div class="preview-bg-overlay"></div>
        <div class="preview-inner" data-edit="menu" data-layer-label="基础信息 / 全部分组">
          <div class="kicker">Menu ${escapeHtml(menu.name || menu.id)}</div>
          <h1 class="preview-title">${escapeHtml(menu.title || "Bot 功能菜单")}</h1>
          <div class="preview-sub">${escapeHtml(menu.subtitle || "")}</div>
          <div class="preview-sections">
          ${menu.sections.map((section, sectionIndex) => `
            <section class="preview-section" data-edit="section" data-section-index="${sectionIndex}" data-layer-label="编辑分组">
              <h3>${escapeHtml(section.title || "分组")}</h3>
              <div class="preview-items">
                ${section.items.map((item, itemIndex) => {
                  const matched = !query || itemMatchesSearch(item, query);
                  const searchClass = query ? (matched ? "is-search-match" : "is-search-dim") : "";
                  return `
                  <div class="preview-item size-${cardSize(item.card_size)} ${item.enabled === false ? "disabled" : ""} ${searchClass}" data-edit="item" data-section-index="${sectionIndex}" data-item-index="${itemIndex}" data-layer-label="编辑卡片">
                    <div class="preview-icon">${escapeHtml(item.icon || "?")}</div>
                    <div class="preview-item-main">
                      <div class="preview-command">${escapeHtml(item.command || "")}</div>
                      <strong class="preview-item-title">${escapeHtml(item.label || "未命名")}</strong>
                      <div class="preview-desc">${escapeHtml(item.description || "")}</div>
                    </div>
                  </div>`;
                }).join("")}
              </div>
            </section>`).join("")}
          </div>
          <div class="preview-footer"><span>${escapeHtml(menu.footer || "")}</span><span>${style.show_updated_at === false ? "" : "实时预览"}</span></div>
        </div>
        ${style.watermark ? `<div class="preview-watermark">${escapeHtml(style.watermark)}</div>` : ""}
      </div>
    </div>`;
  els.previewMeta.textContent = editorPreview.formatPreviewMeta
    ? editorPreview.formatPreviewMeta(deviceLabel, layout)
    : `${deviceLabel} · ${layout.width}px · 每行 ${layout.columns} 张 · ${layout.itemCount} 项`;
  updateBackgroundEditToggle();
  attachBackgroundEditor();
  fitPreviewToStage();
}

function toggleBackgroundEditMode() {
  if (!state.menu) return;
  const style = ensureStyle(state.menu);
  if (!style.background_image) {
    state.backgroundEditMode = false;
    updateBackgroundEditToggle();
    setStatus("当前菜单还没有背景图。请点击外框打开主题与背景设置后上传背景图。", "warning");
    return;
  }
  state.backgroundEditMode = !state.backgroundEditMode;
  renderPreview();
  setStatus(
    state.backgroundEditMode
      ? "已进入背景图编辑模式：拖动背景或拉伸边框，卡片编辑已暂时锁定。"
      : "已锁定背景图：现在可以点击分组和卡片进行编辑。",
    state.backgroundEditMode ? "warning" : "success",
  );
}

function updateBackgroundEditToggle() {
  if (!els.backgroundEditToggleBtn) return;
  const hasBackground = Boolean(state.menu && ensureStyle(state.menu).background_image);
  if (!hasBackground) state.backgroundEditMode = false;
  els.backgroundEditToggleBtn.hidden = !hasBackground;
  els.backgroundEditToggleBtn.textContent = state.backgroundEditMode ? "锁定背景图" : "编辑背景图";
  els.backgroundEditToggleBtn.setAttribute("aria-pressed", state.backgroundEditMode ? "true" : "false");
  els.backgroundEditToggleBtn.classList.toggle("is-active", state.backgroundEditMode);
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
  renderAll();
}

function removeSection(index) {
  if (state.menu.sections.length <= 1) return setStatus("至少保留一个分组。");
  state.menu.sections.splice(index, 1);
  markDirty();
  renderAll();
}

function moveSection(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= state.menu.sections.length) return;
  const [section] = state.menu.sections.splice(index, 1);
  state.menu.sections.splice(target, 0, section);
  markDirty();
  renderAll();
}

function copySection(index) {
  const copy = cloneData(state.menu.sections[index]);
  copy.title = `${copy.title || "分组"} 副本`;
  state.menu.sections.splice(index + 1, 0, copy);
  markDirty();
  renderAll();
}

function addItem(sectionIndex, templateKey = "standard") {
  state.menu.sections[sectionIndex].items.push(createItemFromTemplate(templateKey));
  markDirty();
  renderAll();
}

function moveItem(sectionIndex, itemIndex, direction) {
  const items = state.menu.sections[sectionIndex].items;
  const target = itemIndex + direction;
  if (target < 0 || target >= items.length) return;
  const [item] = items.splice(itemIndex, 1);
  items.splice(target, 0, item);
  markDirty();
  renderAll();
}

function copyItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  const copy = cloneData(items[itemIndex]);
  copy.label = `${copy.label || "菜单项"} 副本`;
  items.splice(itemIndex + 1, 0, copy);
  markDirty();
  renderAll();
}

function removeItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  if (items.length <= 1) return setStatus("每个分组至少保留一个菜单项。");
  items.splice(itemIndex, 1);
  markDirty();
  renderAll();
}

async function saveMenu() {
  const draftIdBeforeSave = currentDraftId();
  await flushPendingBackgroundAsset();
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
    setServerMenuIds(state.menus);
    state.unsavedMenuIds.clear();
    state.currentId = result.menu.id;
    state.menu = cloneData(result.menu);
    state.unsavedMenuIds.delete(draftIdBeforeSave);
    state.unsavedMenuIds.delete(state.currentId);
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

function createDefaultMenu(id) {
  return {
    id,
    name: "新菜单",
    title: "Bot 功能菜单",
    subtitle: "发送下列指令即可使用对应功能",
    footer: "",
    style: defaultStyle(),
    sections: [{ title: "常用功能", items: [{ label: "菜单", command: "/menu", description: "查看菜单", icon: "📋", card_size: "standard", enabled: true }] }],
  };
}

function activateLocalMenu(menu, { dirty = true, statusText = "" } = {}) {
  discardPendingBackgroundAsset();
  state.menu = cloneData(menu);
  state.currentId = state.menu.id;
  state.backgroundEditMode = false;
  state.dirty = Boolean(dirty);
  state.selectedKeys.clear();
  upsertMenuEntry(state.menu, { unsaved: dirty });
  loadSearchState();
  fillForm();
  refreshSchemeSelect();
  resetLocalHistory(state.menu);
  renderAll();
  updateSaveState(state.dirty ? "dirty" : "saved");
  clearRenderStatus();
  if (state.dirty) saveDraft();
  if (statusText) setStatus(statusText, state.dirty ? "warning" : "success");
}

function newMenu() {
  stashActiveMenu();
  const id = uniqueId("menu");
  activateLocalMenu(createDefaultMenu(id), { dirty: true, statusText: "已创建本地新菜单，上一菜单修改已自动保留为草稿。" });
}

function copyMenu() {
  if (!state.menu) return newMenu();
  stashActiveMenu();
  const copy = cloneData(state.menu);
  copy.id = uniqueId(`${copy.id || "menu"}_copy`);
  copy.name = `${copy.name || "菜单"} 副本`;
  copy.updated_at = "";
  copy.created_at = "";
  activateLocalMenu(copy, { dirty: true, statusText: "已复制为新的本地菜单，保存后生效。" });
}

async function deleteMenu() {
  if (!state.menu) {
    setStatus("没有可删除的菜单。", "warning");
    return;
  }
  syncFormToMenu({ mark: false });
  const currentId = state.currentId || state.menu.id;
  const isSavedMenu = state.serverMenuIds.has(currentId);
  if (!isSavedMenu) {
    const confirmed = await confirmDialog(
      "丢弃本地菜单？",
      `当前菜单方案 ${currentId || "未命名"} 尚未保存，只会丢弃本地草稿。`,
      { confirmLabel: "丢弃草稿", danger: true },
    );
    if (!confirmed) {
      setStatus("已取消删除。");
      return;
    }
    await discardUnsavedMenu(currentId);
    return;
  }
  if (state.serverMenuIds.size <= 1) {
    setStatus("至少保留一个菜单方案，无法删除最后一个菜单。", "warning");
    return;
  }
  const confirmed = await confirmDialog(
    "删除菜单方案？",
    `确定删除菜单方案 ${currentId}？未保存修改会一并丢弃，删除前会由后端保留历史快照。`,
    { confirmLabel: "确认删除", danger: true },
  );
  if (!confirmed) {
    setStatus("已取消删除。");
    return;
  }
  const fallbackId = chooseFallbackMenuId(currentId);
  try {
    setStatus("正在删除菜单...");
    const result = await bridge.apiPost("menus/delete", { id: currentId });
    state.menus = result.menus || state.menus.filter((menu) => menu.id !== currentId);
    setServerMenuIds(state.menus);
    state.unsavedMenuIds.delete(currentId);
    clearDraft(currentId);
    const nextId = chooseExistingMenuId(result.default_menu_id, fallbackId, state.menus[0]?.id);
    state.dirty = false;
    if (nextId) await selectMenu(nextId);
    refreshSchemeSelect();
    updateSaveState("saved");
    setStatus("删除成功。", "success");
  } catch (error) {
    setStatus(`删除失败：${error.message}`, "error");
  }
}

function chooseExistingMenuId(...ids) {
  for (const id of ids) {
    if (id && state.menus.some((menu) => menu.id === id)) return id;
  }
  return state.menus[0]?.id || "";
}

function chooseFallbackMenuId(excludingId) {
  const currentIndex = state.menus.findIndex((menu) => menu.id === excludingId);
  const ordered = [
    state.menus[currentIndex + 1]?.id,
    state.menus[currentIndex - 1]?.id,
    state.defaultMenuId !== excludingId ? state.defaultMenuId : "",
    ...state.menus.map((menu) => menu.id),
  ];
  return chooseExistingMenuId(...ordered.filter((id) => id && id !== excludingId));
}

async function discardUnsavedMenu(menuId) {
  clearDraft(menuId);
  removeMenuEntry(menuId);
  state.unsavedMenuIds.delete(menuId);
  refreshSchemeSelect();
  const nextId = chooseFallbackMenuId(menuId);
  state.dirty = false;
  if (nextId) {
    await selectMenu(nextId);
    setStatus("已丢弃未保存菜单草稿。", "success");
  } else {
    newMenu();
    setStatus("已丢弃未保存菜单草稿，并创建新的本地菜单。", "warning");
  }
}

async function exportMenus() {
  try {
    const data = await bridge.apiGet("export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "bot-menus.json";
    link.style.display = "none";
    document.body.append(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
    setStatus("已导出菜单 JSON。", "success");
  } catch (error) {
    setStatus(`导出失败：${error.message}`, "error");
  }
}

async function importMenus(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const hadDirtyWork = state.dirty;
  stashActiveMenu();
  if (hadDirtyWork) setStatus("已先保留当前未保存内容为本地草稿，再继续导入。", "warning");
  try {
    const data = JSON.parse(await file.text());
    const menus = Array.isArray(data) ? data : data.menus;
    const incoming = Array.isArray(menus) ? menus : [];
    const existingIds = new Set(state.menus.map((menu) => menu.id));
    const added = incoming.filter((menu) => menu?.id && !existingIds.has(menu.id)).map((menu) => menu.id);
    const overwritten = incoming.filter((menu) => menu?.id && existingIds.has(menu.id)).map((menu) => menu.id);
    const invalid = incoming.filter((menu) => !menu?.id).length;
    const summary = [
      `新增：${added.length}${added.length ? `（${added.join(", ")}）` : ""}`,
      `覆盖：${overwritten.length}${overwritten.length ? `（${overwritten.join(", ")}）` : ""}`,
      `无效项：${invalid}`,
      `内联资产：${Array.isArray(data.assets) ? data.assets.length : 0}`,
    ].join("\n");
    const confirmed = await confirmDialog("导入菜单包？", `导入预览：\n${summary}\n\n继续导入后会合并到当前菜单列表。`, {
      confirmLabel: "确认导入",
    });
    if (!confirmed) {
      setStatus("已取消导入。");
      return;
    }
    setStatus("正在导入菜单包...");
    const result = await bridge.apiPost("import", {
      menus,
      assets: Array.isArray(data.assets) ? data.assets : [],
      mode: "merge",
    });
    state.menus = result.menus || [];
    setServerMenuIds(state.menus);
    state.unsavedMenuIds.clear();
    refreshSchemeSelect();
    const preferredId = chooseExistingMenuId(added[0], overwritten[0], state.currentId, state.menus[0]?.id);
    if (preferredId) await selectMenu(preferredId);
    showImportResult({
      added,
      overwritten,
      invalid,
      assetCount: Array.isArray(data.assets) ? data.assets.length : 0,
      activeCount: state.menus.length,
      importedCount: result.imported_count ?? incoming.length,
    });
    setStatus(`导入成功：新增 ${added.length}，覆盖 ${overwritten.length}，当前可用菜单 ${state.menus.length} 个。`, "success");
  } catch (error) {
    setStatus(`导入失败：${error.message}`, "error");
  } finally {
    event.target.value = "";
  }
}

function showImportResult({ added, overwritten, invalid, assetCount, activeCount, importedCount }) {
  const body = document.createElement("div");
  body.className = "import-result";
  body.innerHTML = `
    <p><strong>导入完成</strong>：读取 ${importedCount} 个菜单，当前可用 ${activeCount} 个菜单。</p>
    <ul>
      <li>新增：${escapeHtml(added.length ? added.join(", ") : "无")}</li>
      <li>覆盖：${escapeHtml(overwritten.length ? overwritten.join(", ") : "无")}</li>
      <li>无效项：${invalid}</li>
      <li>内联资产：${assetCount}</li>
    </ul>`;
  openModal("导入结果", body, [{ label: "知道了", className: "primary", onClick: closeModal }]);
}

async function openHistoryPanel() {
  const body = document.createElement("div");
  body.className = "history-panel";
  openModal("历史与恢复", body, [{ label: "刷新", onClick: openHistoryPanel }]);
  try {
    const menuData = await bridge.apiGet("menus");
    const deletedMenus = menuData.deleted_menus || [];
    const historyData = state.currentId
      ? await bridge.apiGet(`menus/history/${encodeURIComponent(state.currentId)}`)
      : { history: [] };
    replaceChildrenSafe(body);
    body.append(
      historySectionTitle("当前菜单快照", state.currentId ? `菜单 ID：${state.currentId}` : "尚未选择菜单"),
      renderSnapshotList(historyData.history || []),
      historySectionTitle("已删除菜单", deletedMenus.length ? "可从这里恢复误删菜单" : "暂无已删除菜单"),
      renderDeletedMenuList(deletedMenus),
    );
  } catch (error) {
    body.textContent = `历史加载失败：${error.message}`;
  }
}

function historySectionTitle(title, subtitle) {
  const wrap = document.createElement("div");
  wrap.className = "history-section-title";
  wrap.innerHTML = `<strong>${escapeHtml(title)}</strong><small>${escapeHtml(subtitle || "")}</small>`;
  return wrap;
}

function renderSnapshotList(history) {
  const list = document.createElement("div");
  list.className = "entity-list";
  if (!history.length) {
    list.append(emptyState("暂无当前菜单快照。保存、删除或恢复菜单前会自动创建快照。"));
    return list;
  }
  history.forEach((snapshot) => {
    const row = document.createElement("article");
    row.className = "entity-row";
    row.innerHTML = `<div class="entity-title"><strong>${escapeHtml(snapshot.menu?.title || snapshot.menu_id)}</strong><small>${escapeHtml(snapshot.created_at || "")} · ${escapeHtml(historyReasonLabel(snapshot.reason))}</small></div>`;
    row.append(actionRow([
      { label: "恢复此版本", className: "primary", onClick: async () => restoreSnapshot(snapshot) },
    ]));
    list.append(row);
  });
  return list;
}

function renderDeletedMenuList(deletedMenus) {
  const list = document.createElement("div");
  list.className = "entity-list";
  if (!deletedMenus.length) {
    list.append(emptyState("暂无已删除菜单。删除菜单后会出现在这里。"));
    return list;
  }
  deletedMenus.forEach((menu) => {
    const row = document.createElement("article");
    row.className = "entity-row deleted-row";
    row.innerHTML = `<div class="entity-title"><strong>${escapeHtml(menu.name || menu.title || menu.id)}</strong><small>${escapeHtml(menu.id)} · 删除于 ${escapeHtml(menu.deleted_at || "")}</small></div>`;
    row.append(actionRow([
      { label: "恢复菜单", className: "primary", onClick: async () => restoreDeletedMenu(menu.id) },
      { label: "查看快照", onClick: async () => selectDeletedHistory(menu.id) },
    ]));
    list.append(row);
  });
  return list;
}

function emptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function historyReasonLabel(reason) {
  return { save: "保存前快照", delete: "删除前快照", restore: "恢复前快照" }[reason] || reason || "快照";
}

async function restoreSnapshot(snapshot) {
  const confirmed = await confirmDialog(
    "恢复历史版本？",
    "确定恢复此历史版本？当前内容会先创建快照，恢复后需要等待后台刷新缓存。",
    { confirmLabel: "恢复版本" },
  );
  if (!confirmed) return;
  const result = await bridge.apiPost("menus/restore", { menu_id: snapshot.menu_id, snapshot_id: snapshot.id });
  state.menus = result.menus || state.menus;
  setServerMenuIds(state.menus);
  await selectMenu(result.menu?.id || snapshot.menu_id);
  setStatus("历史版本已恢复，后台正在刷新缓存。", "success");
  closeModal();
}

async function restoreDeletedMenu(menuId) {
  const confirmed = await confirmDialog(
    "恢复已删除菜单？",
    `确定恢复菜单 ${menuId}？恢复后会重新出现在菜单方案列表。`,
    { confirmLabel: "恢复菜单" },
  );
  if (!confirmed) return;
  const result = await bridge.apiPost("menus/restore", { menu_id: menuId, deleted: true });
  state.menus = result.menus || state.menus;
  setServerMenuIds(state.menus);
  await selectMenu(result.menu?.id || menuId);
  setStatus("已恢复删除的菜单。", "success");
  closeModal();
}

async function selectDeletedHistory(menuId) {
  const data = await bridge.apiGet(`menus/history/${encodeURIComponent(menuId)}`);
  const body = document.createElement("div");
  body.className = "history-panel";
  body.append(
    historySectionTitle("已删除菜单快照", `菜单 ID：${menuId}`),
    renderSnapshotList(data.history || []),
  );
  openModal("已删除菜单快照", body, [{ label: "返回历史", onClick: openHistoryPanel }]);
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
  const pending = await createPendingBackgroundAsset(file);
  discardPendingBackgroundAsset();
  state.pendingBackgroundAsset = pending;
  const style = ensureStyle(state.menu);
  Object.assign(style, {
    background_image: pending.previewUrl,
    background_image_asset_id: "",
    background_image_name: file.name,
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  markDirty();
  els.backgroundImageName.textContent = file.name;
  syncBackgroundControls();
  renderAll();
  fitBackgroundToCover(true);
  event.target.value = "";
}

async function saveBackgroundAsset(dataUrl, name) {
  try {
    const result = await bridge.apiPost("assets", { data_url: dataUrl, name });
    state.assets = result.assets || state.assets;
    return result.asset || null;
  } catch (error) {
    setStatus(`背景已用于预览，但保存到资产库失败：${error.message}`, "warning");
    return null;
  }
}

function clearBackgroundImage() {
  const style = ensureStyle(state.menu);
  discardPendingBackgroundAsset();
  state.backgroundEditMode = false;
  Object.assign(style, {
    background_image: "",
    background_image_asset_id: "",
    background_image_name: "",
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  markDirty();
  els.backgroundImageName.textContent = "No background image";
  syncBackgroundControls();
  renderAll();
}

function readFileAsDataUrl(file) {
  if (editorBackground.readFileAsDataUrl) return editorBackground.readFileAsDataUrl(file);
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

function fitBackgroundToContain() {
  const style = ensureStyle(state.menu);
  const img = els.preview.querySelector(".preview-bg-image");
  const card = els.preview.querySelector(".preview-card");
  if (!img || !card || !style.background_image) return;
  if (!img.complete || !img.naturalWidth || !img.naturalHeight) {
    img.addEventListener("load", fitBackgroundToContain, { once: true });
    return;
  }
  const widthByHeight = (card.clientHeight * img.naturalWidth * 100) / (card.clientWidth * img.naturalHeight);
  style.background_image_width = clampNumber(Math.min(100, widthByHeight), 10, 600, 100);
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
  syncThemeSelectOptions();
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

function syncThemeSelectOptions() {
  if (!els.theme) return;
  const currentValue = els.theme.value || state.menu?.style?.theme || "aurora";
  els.theme.innerHTML = Object.entries(THEME_PRESETS)
    .map(([key, preset]) => `<option value="${escapeAttr(key)}">${escapeHtml(preset.label)}</option>`)
    .join("");
  els.theme.value = THEME_PRESETS[currentValue] ? currentValue : "aurora";
}

async function copyStyleToMenus() {
  if (!state.menu) return;
  await flushPendingBackgroundAsset();
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
      const nextMenu = cloneData(target);
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
    copy[key] = cloneData(style[key]);
    return copy;
  }, {});
}

function resetCurrentStyle() {
  if (!confirm("确定重置当前菜单样式？菜单内容不会被删除。")) return;
  discardPendingBackgroundAsset();
  state.menu.style = defaultStyle();
  fillForm();
  markDirty();
  renderAll();
  setStatus("已重置样式，保存后生效。", "success");
}

function contrastWarningText(style = ensureStyle(state.menu)) {
  const ratio = contrastRatio(style.text_color || "#111827", style.card_color || "#ffffff");
  return ratio < 4.5 ? `文字与卡片背景对比度不足（${ratio.toFixed(2)}），建议一键修复颜色。` : "";
}

function fixContrastColors() {
  const style = ensureStyle(state.menu);
  const bg = hexToRgb(style.card_color || "#ffffff");
  if (!bg) return;
  const luminance = relativeLuminance(bg);
  style.text_color = luminance > 0.42 ? "#111827" : "#f8fafc";
  style.muted_color = luminance > 0.42 ? "#475569" : "#cbd5e1";
  markDirty();
  renderAll();
  setStatus("已自动修复文字对比度。", "success");
}

function contrastRatio(colorA, colorB) {
  const a = hexToRgb(colorA);
  const b = hexToRgb(colorB);
  if (!a || !b) return 21;
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function relativeLuminance({ r, g, b }) {
  const transform = (value) => {
    const channel = value / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * transform(r) + 0.7152 * transform(g) + 0.0722 * transform(b);
}

function hexToRgb(value) {
  const match = String(value || "").trim().match(/^#?([0-9a-f]{6})$/i);
  if (!match) return null;
  const raw = match[1];
  return {
    r: parseInt(raw.slice(0, 2), 16),
    g: parseInt(raw.slice(2, 4), 16),
    b: parseInt(raw.slice(4, 6), 16),
  };
}

function itemMatchesSearch(item, query) {
  return [item.label, item.command, item.description]
    .some((value) => String(value || "").toLowerCase().includes(query));
}

function selectionKey(type, sectionIndex, itemIndex = null) {
  return itemIndex === null ? `${type}:${sectionIndex}` : `${type}:${sectionIndex}:${itemIndex}`;
}

function parseSelectionKey(key) {
  const [type, sectionRaw, itemRaw] = String(key).split(":");
  return { type, sectionIndex: Number(sectionRaw), itemIndex: itemRaw === undefined ? null : Number(itemRaw) };
}

function toggleSelection(key, selected) {
  if (selected) state.selectedKeys.add(key);
  else state.selectedKeys.delete(key);
  updateBatchToolbar();
}

function clearSelection() {
  state.selectedKeys.clear();
  renderSectionsEditor();
}

function selectedEntries() {
  return [...state.selectedKeys]
    .map(parseSelectionKey)
    .filter((entry) => Number.isInteger(entry.sectionIndex) && entry.sectionIndex >= 0);
}

function updateBatchToolbar() {
  if (!els.batchToolbar) return;
  const count = state.selectedKeys.size;
  els.batchToolbar.hidden = count === 0;
  if (els.batchCount) els.batchCount.textContent = `已选择 ${count} 项`;
}

function batchSetEnabled(enabled) {
  const entries = selectedEntries().filter((entry) => entry.type === "item");
  if (!entries.length) return setStatus("请先选择需要启用/禁用的卡片。", "warning");
  entries.forEach(({ sectionIndex, itemIndex }) => {
    const item = state.menu.sections?.[sectionIndex]?.items?.[itemIndex];
    if (item) item.enabled = enabled;
  });
  markDirty();
  renderAll();
}

function batchCopySelection() {
  const entries = selectedEntries();
  if (!entries.length) return;
  const sectionIndexes = entries
    .filter((entry) => entry.type === "section")
    .map((entry) => entry.sectionIndex)
    .sort((a, b) => b - a);
  sectionIndexes.forEach((sectionIndex) => {
    const section = state.menu.sections?.[sectionIndex];
    if (!section) return;
    const copy = cloneData(section);
    copy.title = `${copy.title || "分组"} 副本`;
    state.menu.sections.splice(sectionIndex + 1, 0, copy);
  });

  const itemEntries = entries
    .filter((entry) => entry.type === "item")
    .sort((a, b) => b.sectionIndex - a.sectionIndex || b.itemIndex - a.itemIndex);
  itemEntries.forEach(({ sectionIndex, itemIndex }) => {
    const items = state.menu.sections?.[sectionIndex]?.items;
    const item = items?.[itemIndex];
    if (!items || !item) return;
    const copy = cloneData(item);
    copy.label = `${copy.label || "菜单项"} 副本`;
    items.splice(itemIndex + 1, 0, copy);
  });
  state.selectedKeys.clear();
  markDirty();
  renderAll();
}

function batchDeleteSelection() {
  if (!state.selectedKeys.size) return;
  if (!confirm(`确定删除选中的 ${state.selectedKeys.size} 项？`)) return;
  const entries = selectedEntries();
  const sectionIndexes = entries
    .filter((entry) => entry.type === "section")
    .map((entry) => entry.sectionIndex)
    .sort((a, b) => b - a);
  const deletedSections = new Set(sectionIndexes);
  entries
    .filter((entry) => entry.type === "item" && !deletedSections.has(entry.sectionIndex))
    .sort((a, b) => b.sectionIndex - a.sectionIndex || b.itemIndex - a.itemIndex)
    .forEach(({ sectionIndex, itemIndex }) => {
      const items = state.menu.sections?.[sectionIndex]?.items;
      if (items && items.length > 1) items.splice(itemIndex, 1);
    });
  sectionIndexes.forEach((sectionIndex) => {
    if (state.menu.sections.length > 1) state.menu.sections.splice(sectionIndex, 1);
  });
  state.selectedKeys.clear();
  markDirty();
  renderAll();
}

function batchMoveSelection(direction) {
  const entries = selectedEntries();
  if (entries.length !== 1) return setStatus("上移/下移一次只支持选择 1 个分组或 1 张卡片。", "warning");
  const entry = entries[0];
  if (entry.type === "section") moveSection(entry.sectionIndex, direction);
  if (entry.type === "item") moveItem(entry.sectionIndex, entry.itemIndex, direction);
  state.selectedKeys.clear();
}

function bindDragSort(node, key) {
  node.draggable = true;
  node.dataset.dragKey = key;
  node.addEventListener("dragstart", (event) => {
    if (event.target.closest("input, textarea, select, button, label")) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", key);
    node.classList.add("is-dragging");
  });
  node.addEventListener("dragend", () => {
    node.classList.remove("is-dragging");
    document.querySelectorAll(".is-drag-over").forEach((item) => item.classList.remove("is-drag-over"));
  });
  node.addEventListener("dragover", (event) => {
    event.preventDefault();
    node.classList.add("is-drag-over");
  });
  node.addEventListener("dragleave", () => node.classList.remove("is-drag-over"));
  node.addEventListener("drop", (event) => {
    event.preventDefault();
    node.classList.remove("is-drag-over");
    const sourceKey = event.dataTransfer.getData("text/plain");
    if (!sourceKey || sourceKey === key) return;
    moveDraggedEntry(sourceKey, key);
  });
}

function moveDraggedEntry(sourceKey, targetKey) {
  const source = parseSelectionKey(sourceKey);
  const target = parseSelectionKey(targetKey);
  if (source.type !== target.type) return;
  if (source.type === "section") {
    const [section] = state.menu.sections.splice(source.sectionIndex, 1);
    let targetIndex = target.sectionIndex;
    if (source.sectionIndex < targetIndex) targetIndex -= 1;
    state.menu.sections.splice(targetIndex, 0, section);
  }
  if (source.type === "item") {
    const sourceItems = state.menu.sections?.[source.sectionIndex]?.items;
    const targetItems = state.menu.sections?.[target.sectionIndex]?.items;
    if (!sourceItems || !targetItems) return;
    const [item] = sourceItems.splice(source.itemIndex, 1);
    let targetIndex = target.itemIndex;
    if (source.sectionIndex === target.sectionIndex && source.itemIndex < targetIndex) targetIndex -= 1;
    targetItems.splice(targetIndex, 0, item);
  }
  state.selectedKeys.clear();
  markDirty();
  renderAll();
}

function resetLocalHistory(menu) {
  state.history = [cloneData(menu)];
  state.historyIndex = 0;
  updateHistoryButtons();
}

function captureLocalHistory() {
  if (state.historyPaused || !state.menu) return;
  const snapshot = cloneData(state.menu);
  const current = state.history[state.historyIndex];
  if (current && JSON.stringify(current) === JSON.stringify(snapshot)) return;
  if (state.historyIndex < state.history.length - 1) {
    state.history.splice(state.historyIndex + 1);
  }
  state.history.push(snapshot);
  while (state.history.length > HISTORY_LIMIT) state.history.shift();
  state.historyIndex = state.history.length - 1;
  updateHistoryButtons();
}

function undoMenuChange() {
  if (state.historyIndex <= 0) return;
  state.historyPaused = true;
  state.historyIndex -= 1;
  state.menu = cloneData(state.history[state.historyIndex]);
  state.currentId = state.menu.id;
  fillForm();
  markDirty();
  renderAll();
  state.historyPaused = false;
  updateHistoryButtons();
}

function redoMenuChange() {
  if (state.historyIndex >= state.history.length - 1) return;
  state.historyPaused = true;
  state.historyIndex += 1;
  state.menu = cloneData(state.history[state.historyIndex]);
  state.currentId = state.menu.id;
  fillForm();
  markDirty();
  renderAll();
  state.historyPaused = false;
  updateHistoryButtons();
}

function updateHistoryButtons() {
  if (els.undoBtn) els.undoBtn.disabled = state.historyIndex <= 0;
  if (els.redoBtn) els.redoBtn.disabled = state.historyIndex >= state.history.length - 1;
}

function upsertMenuEntry(menu, { unsaved = false, previousId = "" } = {}) {
  if (!menu?.id) return;
  if (previousId && previousId !== menu.id) {
    removeMenuEntry(previousId);
    state.unsavedMenuIds.delete(previousId);
  }
  const snapshot = cloneData(menu);
  const index = state.menus.findIndex((item) => item.id === snapshot.id);
  if (index >= 0) state.menus[index] = snapshot;
  else state.menus.push(snapshot);
  if (unsaved) state.unsavedMenuIds.add(snapshot.id);
  else state.unsavedMenuIds.delete(snapshot.id);
}

function removeMenuEntry(menuId) {
  if (!menuId) return;
  state.menus = state.menus.filter((menu) => menu.id !== menuId);
}

function syncUnsavedMenuEntry() {
  if (!state.menu || !state.currentId || !state.unsavedMenuIds.has(state.currentId)) return;
  const previousId = state.currentId;
  const nextId = String(state.menu.id || previousId).trim() || previousId;
  state.menu.id = nextId;
  state.currentId = nextId;
  upsertMenuEntry(state.menu, { unsaved: true, previousId });
  refreshSchemeSelect();
}

function syncWorkingMenuEntry() {
  if (!state.menu || !state.currentId) return;
  const previousId = state.currentId;
  const nextId = String(state.menu.id || previousId).trim() || previousId;
  state.menu.id = nextId;
  state.currentId = nextId;
  const keepPrevious = state.serverMenuIds.has(previousId) && previousId !== nextId;
  upsertMenuEntry(state.menu, { unsaved: true, previousId: keepPrevious ? "" : previousId });
  refreshSchemeSelect();
}

function markDirty() {
  if (!state.menu) return;
  state.dirty = true;
  syncWorkingMenuEntry();
  captureLocalHistory();
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
    const draftMenu = cloneData(state.menu);
    const pending = state.pendingBackgroundAsset;
    const style = draftMenu.style || {};
    if (pending && (style.background_image === pending.previewUrl || style.background_image === pending.objectUrl)) {
      style.background_image = "";
      style.background_image_asset_id = "";
      pending.dataUrlPromise.then((dataUrl) => {
        if (state.pendingBackgroundAsset !== pending || currentDraftId() !== id || !state.menu) return;
        const resolvedDraft = cloneData(state.menu);
        resolvedDraft.style = { ...(resolvedDraft.style || {}), background_image: dataUrl, background_image_asset_id: "" };
        safeStorageSet(draftKey(id), JSON.stringify({ saved_at: Date.now(), menu: resolvedDraft }));
      }).catch((error) => console.warn("failed to persist pending background draft", error));
    }
    safeStorageSet(draftKey(id), JSON.stringify({ saved_at: Date.now(), menu: draftMenu }));
  } catch (error) {
    console.warn("failed to save menu draft", error);
  }
}

function clearDraft(id) {
  safeStorageRemove(draftKey(id));
}

function maybeRestoreDraft(menu) {
  const id = menu.id;
  if (!id || state.restoredDraftIds.has(id)) return menu;
  state.restoredDraftIds.add(id);
  try {
    const raw = safeStorageGet(draftKey(id), "");
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
  const key = collapseKey(type, sectionIndex, itemIndex);
  if (state.collapsedKeys.has(key)) return true;
  try {
    const collapsed = safeStorageGet(key, "") === "1";
    if (collapsed) state.collapsedKeys.add(key);
    return collapsed;
  } catch {
    return false;
  }
}

function setCollapsed(type, sectionIndex, itemIndex, collapsed) {
  const key = collapseKey(type, sectionIndex, itemIndex);
  if (collapsed) state.collapsedKeys.add(key);
  else state.collapsedKeys.delete(key);
  try {
    if (collapsed) safeStorageSet(key, "1");
    else safeStorageRemove(key);
  } catch (error) {
    console.warn("failed to save collapse state", error);
  }
}

function saveSearchState() {
  safeStorageSet(`${COLLAPSE_PREFIX}${currentDraftId()}:search`, state.itemSearch || "");
}

function loadSearchState() {
  state.itemSearch = safeStorageGet(`${COLLAPSE_PREFIX}${currentDraftId()}:search`, "") || "";
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
    openEditorForError(key);
    const match = key.match(/^(section|item)-(\d+)(?:-(\d+))?/);
    if (match) {
      const sectionIndex = Number(match[2]);
      const itemIndex = match[1] === "item" ? Number(match[3]) : null;
      setCollapsed("section", sectionIndex, null, false);
      if (itemIndex !== null) setCollapsed("item", sectionIndex, itemIndex, false);
      renderSectionsEditor();
    }
    requestAnimationFrame(() => validateMenu({ silent: true }));
    node = document.querySelector(`[data-error-key="${cssEscape(key)}"]`) || $(key);
  }
  node = node || els.validationSummary;
  node?.scrollIntoView({ behavior: "smooth", block: "center" });
  if (typeof node?.focus === "function") node.focus({ preventScroll: true });
}

function openEditorForError(key) {
  if (/^item-(\d+)-(\d+)/.test(key)) {
    const [, sectionIndex, itemIndex] = key.match(/^item-(\d+)-(\d+)/);
    openItemEditor(Number(sectionIndex), Number(itemIndex));
    return;
  }
  if (/^section-(\d+)/.test(key)) {
    const [, sectionIndex] = key.match(/^section-(\d+)/);
    openSectionEditor(Number(sectionIndex));
    return;
  }
  openMenuEditor();
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
    background_image_asset_id: "",
    background_image_name: "",
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
    background_overlay: 0,
    background_blur: 0,
    background_brightness: 100,
    card_color: "#ffffff",
    text_color: "#111827",
    muted_color: "#6b7280",
    font_family: "",
    foreground_opacity: 92,
    radius: 24,
    width_mode: "auto",
    width: 760,
    columns: 2,
    section_gap_mode: "auto",
    section_gap: 14,
    card_gap: 10,
    section_padding: 15,
    shadow_strength: 1,
    border_strength: 1,
    watermark: "",
    show_updated_at: true,
  };
}

function syncWidthControl() {
  const isAuto = els.widthMode.value !== "custom";
  els.width.disabled = isAuto;
  els.width.closest(".field")?.classList.toggle("is-disabled", isAuto);
}

function syncSectionGapControl() {
  const isAuto = els.sectionGapMode.value !== "custom";
  els.sectionGap.disabled = isAuto;
  els.sectionGap.closest(".field")?.classList.toggle("is-disabled", isAuto);
  if (isAuto && state.menu) {
    els.sectionGap.value = sectionGapForMenu(state.menu);
  }
}

function sectionGapForMenu(menu) {
  const style = ensureStyle(menu);
  if (style.section_gap_mode === "custom") {
    return clampNumber(style.section_gap, 0, 200, 14);
  }
  const sectionCount = Math.max(1, menu.sections?.length || 1);
  const itemCount = (menu.sections || []).reduce((total, section) => total + (section.items?.length || 0), 0);
  const density = sectionCount * 1.8 + itemCount * 0.35;
  return clampNumber(20 - density, 8, 20, 14);
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

function applyPreviewDeviceLayout(layout) {
  return "原比例预览";
}

function applyDensity() {
  document.documentElement.dataset.density = FIXED_DENSITY;
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
