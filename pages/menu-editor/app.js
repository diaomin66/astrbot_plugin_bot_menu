const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);

const CARD_TEMPLATES = {
  compact: { label: "紧凑", icon: "•", title: "快捷项", command: "/cmd", description: "", width: 190 },
  standard: { label: "标准", icon: "✨", title: "新功能", command: "/command", description: "功能说明", width: 230 },
  large: { label: "大卡", icon: "⭐", title: "重点功能", command: "/feature", description: "适合放较长描述或主推功能", width: 285 },
  banner: { label: "横幅", icon: "📌", title: "公告入口", command: "/notice", description: "横跨整行，用于公告、主入口或高优先级操作", width: 360 },
};

const THEME_PRESETS = {
  aurora: { primary_color: "#7c3aed", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#6b7280" },
  minimal: { primary_color: "#2563eb", background_color: "#f8fafc", card_color: "#ffffff", text_color: "#111827", muted_color: "#64748b" },
  midnight: { primary_color: "#38bdf8", background_color: "#111827", card_color: "#1f2937", text_color: "#f8fafc", muted_color: "#cbd5e1" },
  forest: { primary_color: "#059669", background_color: "#ecfdf5", card_color: "#ffffff", text_color: "#064e3b", muted_color: "#64748b" },
  sunrise: { primary_color: "#ea580c", background_color: "#fff7ed", card_color: "#ffffff", text_color: "#1f2937", muted_color: "#78716c" },
};

const state = {
  menus: [],
  defaultMenuId: "default",
  currentId: null,
  menu: null,
  dirty: false,
};

const els = {
  schemeSelect: $("schemeSelect"),
  status: $("status"),
  sections: $("sections"),
  preview: $("preview"),
  menuId: $("menuId"),
  menuName: $("menuName"),
  menuTitle: $("menuTitle"),
  menuSubtitle: $("menuSubtitle"),
  menuFooter: $("menuFooter"),
  theme: $("theme"),
  primaryColor: $("primaryColor"),
  backgroundColor: $("backgroundColor"),
  backgroundImageInput: $("backgroundImageInput"),
  backgroundImageName: $("backgroundImageName"),
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
  serverPreview: $("serverPreview"),
  previewMeta: $("previewMeta"),
};

await bridge.ready();
bindEvents();
await loadMenus();

function bindEvents() {
  els.schemeSelect.addEventListener("change", () => selectMenu(els.schemeSelect.value));
  $("newBtn").addEventListener("click", newMenu);
  $("copyBtn").addEventListener("click", copyMenu);
  $("deleteBtn").addEventListener("click", deleteMenu);
  $("saveBtn").addEventListener("click", saveMenu);
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
  els.clearBackgroundBtn.addEventListener("click", clearBackgroundImage);
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
  state.menu = structuredClone(menu);
  state.dirty = false;
  refreshSchemeSelect();
  fillForm();
  renderAll();
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
}

function syncFormToMenu() {
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
  state.dirty = true;
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
  state.menu.sections.forEach((section, sectionIndex) => {
    const card = document.createElement("section");
    card.className = "section-card";
    card.innerHTML = `
      <div class="section-head">
        <input value="${escapeAttr(section.title)}" aria-label="分组标题" />
        <div class="actions">
          <button type="button" data-action="move-up" ${sectionIndex === 0 ? "disabled" : ""}>上移</button>
          <button type="button" data-action="move-down" ${sectionIndex === state.menu.sections.length - 1 ? "disabled" : ""}>下移</button>
          <button type="button" data-action="copy-section">复制</button>
          <button type="button" data-action="remove-section" class="danger">删除分组</button>
        </div>
      </div>
      <div class="template-actions">
        ${Object.entries(CARD_TEMPLATES).map(([key, template]) => `<button type="button" data-template="${key}">${template.label}</button>`).join("")}
      </div>
      <div class="items-editor"></div>`;
    const titleInput = card.querySelector("input");
    titleInput.addEventListener("input", () => {
      section.title = titleInput.value;
      state.dirty = true;
      els.serverPreview.hidden = true;
      renderPreview();
    });
    card.querySelectorAll("[data-template]").forEach((button) => {
      button.addEventListener("click", () => addItem(sectionIndex, button.dataset.template));
    });
    card.querySelector('[data-action="move-up"]').addEventListener("click", () => moveSection(sectionIndex, -1));
    card.querySelector('[data-action="move-down"]').addEventListener("click", () => moveSection(sectionIndex, 1));
    card.querySelector('[data-action="copy-section"]').addEventListener("click", () => copySection(sectionIndex));
    card.querySelector('[data-action="remove-section"]').addEventListener("click", () => removeSection(sectionIndex));
    const itemsEl = card.querySelector(".items-editor");
    section.items.forEach((item, itemIndex) => itemsEl.append(renderItemEditor(item, sectionIndex, itemIndex)));
    els.sections.append(card);
  });
}

function renderItemEditor(item, sectionIndex, itemIndex) {
  const card = document.createElement("article");
  const currentSize = cardSize(item.card_size);
  card.className = `item-card size-${currentSize}`;
  card.innerHTML = `
    <div class="item-head">
      <strong>${CARD_TEMPLATES[currentSize].label}卡片 ${itemIndex + 1}</strong>
      <div class="actions">
        <button type="button" data-action="move-up" ${itemIndex === 0 ? "disabled" : ""}>上移</button>
        <button type="button" data-action="move-down" ${itemIndex === state.menu.sections[sectionIndex].items.length - 1 ? "disabled" : ""}>下移</button>
        <button type="button" data-action="copy-item">复制</button>
        <button type="button" data-action="remove-item" class="danger">删除</button>
      </div>
    </div>
    <div class="item-grid">
      <label class="field"><span>图标</span><input data-key="icon" value="${escapeAttr(item.icon || "")}" /></label>
      <label class="field"><span>模板</span><select data-key="card_size">${cardSizeOptions(currentSize)}</select></label>
      <label class="field"><span>名称</span><input data-key="label" value="${escapeAttr(item.label || "")}" /></label>
      <label class="field"><span>指令</span><input data-key="command" value="${escapeAttr(item.command || "")}" /></label>
      <label class="field wide"><span>描述</span><input data-key="description" value="${escapeAttr(item.description || "")}" /></label>
    </div>
    <label class="check"><input data-key="enabled" type="checkbox" ${item.enabled !== false ? "checked" : ""} /> 启用</label>`;
  card.querySelector('[data-action="move-up"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, -1));
  card.querySelector('[data-action="move-down"]').addEventListener("click", () => moveItem(sectionIndex, itemIndex, 1));
  card.querySelector('[data-action="copy-item"]').addEventListener("click", () => copyItem(sectionIndex, itemIndex));
  card.querySelector('[data-action="remove-item"]').addEventListener("click", () => removeItem(sectionIndex, itemIndex));
  card.querySelectorAll("[data-key]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.key;
      item[key] = input.type === "checkbox" ? input.checked : input.value;
      state.dirty = true;
      els.serverPreview.hidden = true;
      if (key === "card_size") renderSectionsEditor();
      renderPreview();
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
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function removeSection(index) {
  if (state.menu.sections.length <= 1) return setStatus("至少保留一个分组。");
  state.menu.sections.splice(index, 1);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function moveSection(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= state.menu.sections.length) return;
  const [section] = state.menu.sections.splice(index, 1);
  state.menu.sections.splice(target, 0, section);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function copySection(index) {
  const copy = structuredClone(state.menu.sections[index]);
  copy.title = `${copy.title || "分组"} 副本`;
  state.menu.sections.splice(index + 1, 0, copy);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function addItem(sectionIndex, templateKey = "standard") {
  state.menu.sections[sectionIndex].items.push(createItemFromTemplate(templateKey));
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function moveItem(sectionIndex, itemIndex, direction) {
  const items = state.menu.sections[sectionIndex].items;
  const target = itemIndex + direction;
  if (target < 0 || target >= items.length) return;
  const [item] = items.splice(itemIndex, 1);
  items.splice(target, 0, item);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function copyItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  const copy = structuredClone(items[itemIndex]);
  copy.label = `${copy.label || "菜单项"} 副本`;
  items.splice(itemIndex + 1, 0, copy);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

function removeItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  if (items.length <= 1) return setStatus("每个分组至少保留一个菜单项。");
  items.splice(itemIndex, 1);
  state.dirty = true;
  els.serverPreview.hidden = true;
  renderAll();
}

async function saveMenu() {
  syncFormToMenu();
  try {
    setStatus("正在保存...");
    const result = await bridge.apiPost("menus/save", { menu: state.menu });
    state.menus = result.menus || [result.menu];
    state.currentId = result.menu.id;
    state.menu = structuredClone(result.menu);
    state.dirty = false;
    refreshSchemeSelect();
    fillForm();
    renderAll();
    setStatus("保存成功。");
  } catch (error) {
    setStatus(`保存失败：${error.message}`);
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
  fillForm();
  renderAll();
  setStatus("已创建本地新菜单，保存后生效。");
}

function copyMenu() {
  const copy = structuredClone(state.menu);
  copy.id = uniqueId(`${copy.id || "menu"}_copy`);
  copy.name = `${copy.name || "菜单"} 副本`;
  state.menu = copy;
  state.currentId = copy.id;
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
  syncFormToMenu();
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
  const dataUrl = await readFileAsDataUrl(file);
  const style = ensureStyle(state.menu);
  Object.assign(style, {
    background_image: dataUrl,
    background_image_name: file.name,
    background_image_x: 0,
    background_image_y: 0,
    background_image_width: 100,
  });
  state.dirty = true;
  els.backgroundImageName.textContent = file.name;
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
  state.dirty = true;
  els.backgroundImageName.textContent = "No background image";
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
      state.dirty = true;
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
  state.dirty = true;
  renderPreview();
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

function setStatus(message) {
  els.status.textContent = message;
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
