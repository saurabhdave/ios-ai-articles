/* Subscribe modal — shared by the homepage and all default-layout pages.
   Progressive enhancement: [data-subscribe] links fall back to /feed.xml without JS. */
(function () {
  "use strict";
  var modal = document.getElementById("subscribeModal");
  if (!modal) return;

  var lastFocus = null;
  function focusables() {
    return Array.prototype.slice.call(
      modal.querySelectorAll('a[href], button:not([disabled])')
    ).filter(function (el) { return el.offsetParent !== null; });
  }
  function open() {
    lastFocus = document.activeElement;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    var f = document.getElementById("subCopy") || focusables()[0];
    if (f) f.focus();
  }
  function close() {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-subscribe]");
    if (trigger) { e.preventDefault(); open(); return; }
    if (e.target.closest("[data-sub-close]")) close();
  });

  document.addEventListener("keydown", function (e) {
    if (!modal.classList.contains("open")) return;
    if (e.key === "Escape") { close(); return; }
    if (e.key === "Tab") {
      var f = focusables();
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  var copy = document.getElementById("subCopy");
  if (copy) copy.addEventListener("click", function () {
    var url = (document.getElementById("subUrl").textContent || "").trim();
    navigator.clipboard.writeText(url).then(function () {
      copy.textContent = "Copied!";
      copy.classList.add("copied");
      setTimeout(function () { copy.textContent = "Copy"; copy.classList.remove("copied"); }, 1600);
    }).catch(function () {});
  });
})();
