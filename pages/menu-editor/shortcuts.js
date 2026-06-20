(function () {
  function isTypingTarget(target) {
    return Boolean(target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
  }

  window.MenuEditorShortcuts = {
    isTypingTarget: isTypingTarget,
  };
})();
