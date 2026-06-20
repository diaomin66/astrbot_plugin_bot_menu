(function () {
  function unwrapBridgeResponse(response) {
    if (response && typeof response === "object" && "status" in response) {
      if (response.status === "ok") return response.data || {};
      if (response.status === "error") throw new Error(response.message || "请求失败");
    }
    return response || {};
  }

  function findPageBridge() {
    var candidates = [
      window.AstrBotPluginPage,
      window.AstrBotPage,
      window.PluginPage,
      window.astrBotPluginPage,
      window.astrbotPluginPage,
      window.astrbot && window.astrbot.pluginPage,
      window.astrbot && window.astrbot.page,
    ];
    try {
      if (window.parent && window.parent !== window) {
        candidates.push(
          window.parent.AstrBotPluginPage,
          window.parent.AstrBotPage,
          window.parent.PluginPage,
          window.parent.astrbot && window.parent.astrbot.pluginPage,
          window.parent.astrbot && window.parent.astrbot.page
        );
      }
    } catch (error) {
      // Cross-origin parent access can fail in embedded WebViews.
    }
    return candidates.find(function (candidate) { return candidate && typeof candidate === "object"; }) || null;
  }

  function normalizePageBridge(rawBridge) {
    var apiGet = rawBridge.apiGet || rawBridge.get || rawBridge.GET;
    var apiPost = rawBridge.apiPost || rawBridge.post || rawBridge.POST;
    if (typeof apiGet !== "function" || typeof apiPost !== "function") {
      throw new Error("AstrBot 页面桥接缺少 apiGet/apiPost，请升级 AstrBot 或刷新页面。");
    }
    return {
      apiGet: async function (path) { return unwrapBridgeResponse(await apiGet.call(rawBridge, path)); },
      apiPost: async function (path, payload) { return unwrapBridgeResponse(await apiPost.call(rawBridge, path, payload)); },
    };
  }

  async function resolvePageBridge(options) {
    var timeoutMs = options && options.timeoutMs ? options.timeoutMs : 6000;
    var sleep = options && options.sleep ? options.sleep : function (ms) { return new Promise(function (resolve) { window.setTimeout(resolve, ms); }); };
    var startedAt = Date.now();
    var pageBridge = findPageBridge();
    while (!pageBridge) {
      if (Date.now() - startedAt > timeoutMs) {
        throw new Error("未检测到 AstrBot 页面桥接对象，请在 AstrBot Pages 中打开本页面。");
      }
      await sleep(40);
      pageBridge = findPageBridge();
    }
    if (typeof pageBridge.ready === "function") await pageBridge.ready();
    return normalizePageBridge(pageBridge);
  }

  window.MenuEditorApi = {
    unwrapBridgeResponse: unwrapBridgeResponse,
    findPageBridge: findPageBridge,
    normalizePageBridge: normalizePageBridge,
    resolvePageBridge: resolvePageBridge,
  };
})();
