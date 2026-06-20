(function () {
  function modalIsOpen(modal) {
    return Boolean(modal && !modal.hidden);
  }

  window.MenuEditorModal = {
    modalIsOpen: modalIsOpen,
  };
})();
