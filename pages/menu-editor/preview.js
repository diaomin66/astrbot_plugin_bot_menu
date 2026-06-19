(function () {
  function formatPreviewMeta(deviceLabel, layout) {
    return deviceLabel + " · " + layout.width + "px · 每行 " + layout.columns + " 张 · " + layout.itemCount + " 项";
  }

  window.MenuEditorPreview = {
    formatPreviewMeta: formatPreviewMeta,
  };
})();
