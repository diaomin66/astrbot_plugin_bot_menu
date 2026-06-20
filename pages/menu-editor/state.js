(function () {
  function createStatePatch(patch) {
    return Object.assign({}, patch || {});
  }

  window.MenuEditorState = {
    createStatePatch: createStatePatch,
  };
})();
