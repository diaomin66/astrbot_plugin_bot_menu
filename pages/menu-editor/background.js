(function () {
  function readFileAsDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result || "")); };
      reader.onerror = function () { reject(reader.error || new Error("Failed to read background image")); };
      reader.readAsDataURL(file);
    });
  }

  function createPendingBackground(file) {
    var objectUrl = "";
    if (window.URL && typeof window.URL.createObjectURL === "function") {
      objectUrl = window.URL.createObjectURL(file);
    }
    return {
      name: file.name || "background",
      size: file.size || 0,
      type: file.type || "",
      objectUrl: objectUrl,
      dataUrlPromise: readFileAsDataUrl(file),
    };
  }

  function revokePendingBackground(pending) {
    if (!pending || !pending.objectUrl || !window.URL || typeof window.URL.revokeObjectURL !== "function") return;
    try { window.URL.revokeObjectURL(pending.objectUrl); } catch (error) { console.warn("failed to revoke background object URL", error); }
  }

  window.MenuEditorBackground = {
    readFileAsDataUrl: readFileAsDataUrl,
    createPendingBackground: createPendingBackground,
    revokePendingBackground: revokePendingBackground,
  };
})();
