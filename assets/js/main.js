/* ===================================================================
   iOS AI Articles — "Mainframe" theme interactions
   (shared by all default-layout pages; the homepage has its own script)
   =================================================================== */
(function () {
  "use strict";

  /* ---- Mobile menu ---- */
  var nav = document.getElementById("nav");
  var hamburger = document.getElementById("hamburger");
  var overlay = document.getElementById("mobileOverlay");
  if (nav && hamburger && overlay) {
    var setMenu = function (open) {
      nav.classList.toggle("menu-open", open);
      overlay.classList.toggle("open", open);
      hamburger.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.style.overflow = open ? "hidden" : "";
    };
    hamburger.addEventListener("click", function () {
      setMenu(!nav.classList.contains("menu-open"));
    });
    overlay.addEventListener("click", function () { setMenu(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("menu-open")) setMenu(false);
    });
  }

  /* ---- Theme toggle ---- */
  var themeToggle = document.getElementById("themeToggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  /* Subscribe modal lives in assets/js/subscribe.js (shared with the homepage). */

  var prose = document.querySelector(".prose");

  /* ---- Enhance code blocks: language bar + copy button ---- */
  if (prose) {
    prose.querySelectorAll("div.highlighter-rouge").forEach(function (block) {
      var langClass = (block.className.match(/language-([\w-]+)/) || [])[1] || "";
      var lang = langClass && langClass !== "plaintext"
        ? langClass.charAt(0).toUpperCase() + langClass.slice(1)
        : "Code";

      var bar = document.createElement("div");
      bar.className = "code-bar";
      var label = document.createElement("span");
      label.className = "lang";
      label.textContent = lang;
      var btn = document.createElement("button");
      btn.className = "code-copy";
      btn.type = "button";
      btn.textContent = "Copy";
      bar.appendChild(label);
      bar.appendChild(btn);
      block.insertBefore(bar, block.firstChild);

      btn.addEventListener("click", function () {
        var code = block.querySelector("code");
        if (!code) return;
        navigator.clipboard.writeText(code.innerText).then(function () {
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = "Copy"; }, 1400);
        }).catch(function () {});
      });
    });

    /* ---- Decorate a plain "Checklist" list (skip GFM task-lists, which already
           render native checkboxes — decorating those double-stacks the marker). ---- */
    prose.querySelectorAll("h2, h3").forEach(function (h) {
      if (!/checklist/i.test(h.textContent)) return;
      var sib = h.nextElementSibling;
      while (sib && sib.tagName !== "UL" && sib.tagName !== "H2") sib = sib.nextElementSibling;
      if (sib && sib.tagName === "UL" && !sib.querySelector('input[type="checkbox"]')) {
        sib.classList.add("checklist");
      }
    });

    /* ---- Make GFM task-list checkboxes interactive + remember progress per article ---- */
    var tasks = prose.querySelectorAll("input.task-list-item-checkbox");
    if (tasks.length) {
      var key = "tasks:" + location.pathname;
      var saved = {};
      try { saved = JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) {}
      tasks.forEach(function (box, i) {
        box.disabled = false;
        box.removeAttribute("disabled");
        var li = box.closest(".task-list-item");
        var setDone = function (on) { if (li) li.classList.toggle("done", on); };
        if (saved[i]) { box.checked = true; setDone(true); }
        box.addEventListener("change", function () {
          saved[i] = box.checked;
          try { localStorage.setItem(key, JSON.stringify(saved)); } catch (e) {}
          setDone(box.checked);
        });
      });
    }
  }

  /* ---- Table of contents + scrollspy ---- */
  var tocNav = document.getElementById("toc");
  var heads = prose ? Array.prototype.slice.call(prose.querySelectorAll("h2[id]")) : [];
  if (tocNav && heads.length >= 2) {
    heads.forEach(function (h) {
      var a = document.createElement("a");
      a.href = "#" + h.id;
      a.textContent = h.textContent.replace(/^\d+\.\s*/, "");
      tocNav.appendChild(a);
    });
    var tocLinks = Array.prototype.slice.call(tocNav.querySelectorAll("a"));
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var id = e.target.id;
        tocLinks.forEach(function (a) {
          a.classList.toggle("active", a.getAttribute("href") === "#" + id);
        });
      });
    }, { rootMargin: "-100px 0px -65% 0px", threshold: 0 });
    heads.forEach(function (h) { spy.observe(h); });
  } else {
    var aside = document.querySelector("aside.toc");
    if (aside) aside.style.display = "none";
    var grid = document.querySelector(".article-grid");
    if (grid) grid.style.gridTemplateColumns = "1fr";
  }

  /* ---- Reading progress bar ---- */
  var bar = document.getElementById("progress");
  if (bar && prose) {
    var onScroll = function () {
      var rect = prose.getBoundingClientRect();
      var total = rect.height - window.innerHeight;
      var passed = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
      bar.style.width = (total > 0 ? (passed / total) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
})();

/* ===================================================================
   Share dropdown (LinkedIn / X / Hacker News / copy link)
   =================================================================== */
(function () {
  var dd = null;
  function getDD() {
    if (dd) return dd;
    dd = document.createElement("div");
    dd.className = "share-dropdown";
    dd.setAttribute("role", "menu");
    dd.innerHTML =
      '<a class="share-option" id="sd-li" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>' +
        "LinkedIn</a>" +
      '<a class="share-option" id="sd-tw" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.742l7.432-8.502L2.01 2.25H8.08l4.262 5.638 5.902-5.638zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>' +
        "X / Twitter</a>" +
      '<a class="share-option" id="sd-hn" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M0 24V0h24v24H0zM6.951 5.896l4.112 7.708v5.064h1.583v-4.972l4.148-7.799h-1.749l-2.457 4.875c-.372.745-.688 1.434-.688 1.434s-.297-.708-.651-1.434L8.831 5.896H6.95z"/></svg>' +
        "Hacker News</a>" +
      '<button class="share-option" id="sd-copy">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>' +
        "<span>Copy link</span></button>";
    document.body.appendChild(dd);
    dd.querySelector("#sd-copy").addEventListener("click", function (e) {
      e.stopPropagation();
      var btn = dd.querySelector("#sd-copy");
      var span = btn.querySelector("span");
      navigator.clipboard.writeText(dd.dataset.url).then(function () {
        btn.classList.add("share-option-copied");
        span.textContent = "Copied!";
        setTimeout(function () { btn.classList.remove("share-option-copied"); span.textContent = "Copy link"; close(); }, 1400);
      }).catch(function () {});
    });
    return dd;
  }
  function close() { if (dd) dd.classList.remove("open"); }
  function open(btn, url, title) {
    var el = getDD();
    el.dataset.url = url;
    el.querySelector("#sd-li").href = "https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(url);
    el.querySelector("#sd-tw").href = "https://twitter.com/intent/tweet?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(title);
    el.querySelector("#sd-hn").href = "https://news.ycombinator.com/submitlink?u=" + encodeURIComponent(url) + "&t=" + encodeURIComponent(title);
    var r = btn.getBoundingClientRect();
    el.style.top = (r.bottom + 6) + "px";
    if (window.innerWidth - r.right >= 190) { el.style.left = r.left + "px"; el.style.right = "auto"; el.style.transformOrigin = "top left"; }
    else { el.style.right = (window.innerWidth - r.right) + "px"; el.style.left = "auto"; el.style.transformOrigin = "top right"; }
    el.classList.add("open");
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-share]");
    if (btn) {
      e.preventDefault(); e.stopPropagation();
      var url = btn.dataset.shareUrl || window.location.href;
      var title = btn.dataset.shareTitle || document.title;
      if (navigator.share) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
      if (dd && dd.classList.contains("open")) { close(); return; }
      open(btn, url, title);
      return;
    }
    if (dd && !dd.contains(e.target)) close();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
})();

/* ===================================================================
   Scroll reveal (portfolio sections) — progressive, reduced-motion safe.
   CSS only hides .reveal when html.js is set AND motion is allowed, so
   content is never stuck hidden without JS or with reduced-motion.
   =================================================================== */
(function () {
  var els = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
  if (!els.length) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) {
    els.forEach(function (el) { el.classList.add("is-visible"); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.05 });
  els.forEach(function (el) { io.observe(el); });
})();
