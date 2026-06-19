const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);

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
  cardColor: $("cardColor"),
  width: $("width"),
  radius: $("radius"),
  showUpdatedAt: $("showUpdatedAt"),
  serverPreview: $("serverPreview"),
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

  [
    "menuId",
    "menuName",
    "menuTitle",
    "menuSubtitle",
    "menuFooter",
    "theme",
    "primaryColor",
    "backgroundColor",
    "cardColor",
    "width",
    "radius",
    "showUpdatedAt",
  ].forEach((id) => {
    $(id).addEventListener("input", () => {
      syncFormToMenu();
      renderAll();
    });
  });
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
  els.cardColor.value = toColor(style.card_color, "#ffffff");
  els.width.value = style.width || 900;
  els.radius.value = style.radius ?? 24;
  els.showUpdatedAt.checked = style.show_updated_at !== false;
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
    width: Number(els.width.value) || 900,
    radius: Number(els.radius.value) || 0,
    show_updated_at: els.showUpdatedAt.checked,
  };
  state.dirty = true;
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
          <button type="button" data-action="add-item">添加项</button>
          <button type="button" data-action="remove-section" class="danger">删除分组</button>
        </div>
      </div>
      <div class="items-editor"></div>`;
    const titleInput = card.querySelector("input");
    titleInput.addEventListener("input", () => {
      section.title = titleInput.value;
      state.dirty = true;
      renderPreview();
    });
    card.querySelector('[data-action="add-item"]').addEventListener("click", () => addItem(sectionIndex));
    card.querySelector('[data-action="remove-section"]').addEventListener("click", () => removeSection(sectionIndex));
    const itemsEl = card.querySelector(".items-editor");
    section.items.forEach((item, itemIndex) => itemsEl.append(renderItemEditor(item, sectionIndex, itemIndex)));
    els.sections.append(card);
  });
}

function renderItemEditor(item, sectionIndex, itemIndex) {
  const card = document.createElement("article");
  card.className = "item-card";
  card.innerHTML = `
    <div class="item-head"><strong>菜单项 ${itemIndex + 1}</strong><button type="button" class="danger">删除</button></div>
    <div class="item-grid">
      <label class="field"><span>图标</span><input data-key="icon" value="${escapeAttr(item.icon || "")}" /></label>
      <label class="field"><span>名称</span><input data-key="label" value="${escapeAttr(item.label || "")}" /></label>
      <label class="field"><span>指令</span><input data-key="command" value="${escapeAttr(item.command || "")}" /></label>
      <label class="field wide"><span>描述</span><input data-key="description" value="${escapeAttr(item.description || "")}" /></label>
    </div>
    <label class="check"><input data-key="enabled" type="checkbox" ${item.enabled !== false ? "checked" : ""} /> 启用</label>`;
  card.querySelector("button").addEventListener("click", () => removeItem(sectionIndex, itemIndex));
  card.querySelectorAll("input[data-key]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.key;
      item[key] = input.type === "checkbox" ? input.checked : input.value;
      state.dirty = true;
      renderPreview();
    });
  });
  return card;
}

function renderPreview() {
  const menu = state.menu;
  const style = ensureStyle(menu);
  els.preview.innerHTML = `
    <div class="preview-card" style="--preview-primary:${style.primary_color};--preview-bg:${style.background_color};--preview-card:${style.card_color};--preview-text:${style.text_color || "#111827"};--preview-muted:${style.muted_color || "#6b7280"};--preview-radius:${style.radius || 24}px;--preview-width:${style.width || 760}px">
      <div class="preview-inner">
        <div class="kicker">📋 ${escapeHtml(menu.name || menu.id)}</div>
        <h1 class="preview-title">${escapeHtml(menu.title || "Bot 功能菜单")}</h1>
        <div class="preview-sub">${escapeHtml(menu.subtitle || "")}</div>
        ${menu.sections.map((section) => `
          <section class="preview-section">
            <h3>${escapeHtml(section.title || "分组")}</h3>
            <div class="preview-items">
              ${section.items.map((item) => `
                <div class="preview-item ${item.enabled === false ? "disabled" : ""}">
                  <div>${escapeHtml(item.icon || "•")}</div>
                  <div><strong>${escapeHtml(item.label || "未命名")}</strong><div class="preview-command">${escapeHtml(item.command || "")}</div><div class="preview-desc">${escapeHtml(item.description || "")}</div></div>
                </div>`).join("")}
            </div>
          </section>`).join("")}
        <div class="preview-footer"><span>${escapeHtml(menu.footer || "")}</span><span>${style.show_updated_at === false ? "" : "实时预览"}</span></div>
      </div>
    </div>`;
}

function addSection() {
  state.menu.sections.push({
    title: "新分组",
    items: [{ label: "新功能", command: "/command", description: "功能说明", icon: "✨", enabled: true }],
  });
  state.dirty = true;
  renderAll();
}

function removeSection(index) {
  if (state.menu.sections.length <= 1) return setStatus("至少保留一个分组。");
  state.menu.sections.splice(index, 1);
  state.dirty = true;
  renderAll();
}

function addItem(sectionIndex) {
  state.menu.sections[sectionIndex].items.push({
    label: "新功能",
    command: "/command",
    description: "功能说明",
    icon: "✨",
    enabled: true,
  });
  state.dirty = true;
  renderAll();
}

function removeItem(sectionIndex, itemIndex) {
  const items = state.menu.sections[sectionIndex].items;
  if (items.length <= 1) return setStatus("每个分组至少保留一个菜单项。");
  items.splice(itemIndex, 1);
  state.dirty = true;
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
    sections: [{ title: "常用功能", items: [{ label: "菜单", command: "/menu", description: "查看菜单", icon: "📋", enabled: true }] }],
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

function ensureStyle(menu) {
  menu.style ||= defaultStyle();
  return menu.style;
}

function defaultStyle() {
  return {
    theme: "aurora",
    primary_color: "#7c3aed",
    background_color: "#f8fafc",
    card_color: "#ffffff",
    text_color: "#111827",
    muted_color: "#6b7280",
    radius: 24,
    width: 900,
    show_updated_at: true,
  };
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
