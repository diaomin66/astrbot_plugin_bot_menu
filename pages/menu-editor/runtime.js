(function () {
  function cloneData(value) {
    if (typeof structuredClone === "function") return structuredClone(value);
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function safeStorageGet(key, fallback) {
    try {
      return window.localStorage && window.localStorage.getItem(key) !== null
        ? window.localStorage.getItem(key)
        : (fallback || "");
    } catch (error) {
      console.warn("localStorage get failed", error);
      return fallback || "";
    }
  }

  function safeStorageSet(key, value) {
    try {
      if (window.localStorage) window.localStorage.setItem(key, value);
    } catch (error) {
      console.warn("localStorage set failed", error);
    }
  }

  function safeStorageRemove(key) {
    try {
      if (window.localStorage) window.localStorage.removeItem(key);
    } catch (error) {
      console.warn("localStorage remove failed", error);
    }
  }

  function replaceChildrenSafe(node) {
    if (!node) return;
    var children = Array.prototype.slice.call(arguments, 1);
    if (typeof node.replaceChildren === "function") {
      node.replaceChildren.apply(node, children);
      return;
    }
    while (node.firstChild) node.removeChild(node.firstChild);
    children.forEach(function (child) { node.append(child); });
  }

  function runAction(label, handler, setStatus) {
    try {
      var result = handler();
      if (result && typeof result.catch === "function") {
        result.catch(function (error) {
          console.error("menu editor action failed: " + label, error);
          if (typeof setStatus === "function") setStatus(label + "失败：" + (error.message || error), "error");
        });
      }
      return result;
    } catch (error) {
      console.error("menu editor action failed: " + label, error);
      if (typeof setStatus === "function") setStatus(label + "失败：" + (error.message || error), "error");
      return null;
    }
  }

  function bindClick(control, label, handler, setStatus) {
    if (!control) return;
    control.addEventListener("click", function (event) {
      return runAction(label, function () { return handler(event); }, setStatus);
    });
  }

  window.MenuEditorRuntime = {
    cloneData: cloneData,
    safeStorageGet: safeStorageGet,
    safeStorageSet: safeStorageSet,
    safeStorageRemove: safeStorageRemove,
    replaceChildrenSafe: replaceChildrenSafe,
    runAction: runAction,
    bindClick: bindClick,
  };
})();
