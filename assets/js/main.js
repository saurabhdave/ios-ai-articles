/* ── Theme toggle ─────────────────────────────────────────── */
document.getElementById('theme-toggle').addEventListener('click', function () {
  var t = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
});

/* ── Share dropdown ──────────────────────────────────────── */
(function () {
  var dd = null;
  function getDD() {
    if (dd) return dd;
    dd = document.createElement('div');
    dd.className = 'share-dropdown';
    dd.setAttribute('role', 'menu');
    dd.innerHTML =
      '<a class="share-option" id="sd-li" href="#" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>' +
        'LinkedIn' +
      '</a>' +
      '<a class="share-option" id="sd-tw" href="#" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.742l7.432-8.502L2.01 2.25H8.08l4.262 5.638 5.902-5.638zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>' +
        'Twitter / X' +
      '</a>' +
      '<a class="share-option" id="sd-hn" href="#" target="_blank" rel="noopener noreferrer">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M0 24V0h24v24H0zM6.951 5.896l4.112 7.708v5.064h1.583v-4.972l4.148-7.799h-1.749l-2.457 4.875c-.372.745-.688 1.434-.688 1.434s-.297-.708-.651-1.434L8.831 5.896H6.95z"/></svg>' +
        'Hacker News' +
      '</a>' +
      '<button class="share-option" id="sd-copy">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>' +
        'Copy post' +
      '</button>';
    document.body.appendChild(dd);
    dd.querySelector('#sd-copy').addEventListener('click', function (e) {
      e.stopPropagation();
      var bodyEl = document.querySelector('.post-body') || document.querySelector('.lp-body');
      var html = bodyEl ? bodyEl.innerHTML : dd.dataset.url;
      var text = bodyEl ? bodyEl.innerText : dd.dataset.url;
      var btn = dd.querySelector('#sd-copy');
      function onCopied() {
        btn.classList.add('share-option-copied');
        btn.lastChild.textContent = ' Copied!';
        setTimeout(function () { btn.classList.remove('share-option-copied'); btn.lastChild.textContent = ' Copy post'; close(); }, 1400);
      }
      if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
        navigator.clipboard.write([
          new ClipboardItem({
            'text/html': new Blob([html], { type: 'text/html' }),
            'text/plain': new Blob([text], { type: 'text/plain' })
          })
        ]).then(onCopied).catch(function () {
          navigator.clipboard.writeText(text).then(onCopied).catch(function () {
            var ta = document.createElement('textarea');
            ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
            document.body.appendChild(ta); ta.select(); document.execCommand('copy');
            document.body.removeChild(ta); onCopied();
          });
        });
      } else {
        navigator.clipboard.writeText(text).then(onCopied).catch(function () {
          var ta = document.createElement('textarea');
          ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
          document.body.appendChild(ta); ta.select(); document.execCommand('copy');
          document.body.removeChild(ta); onCopied();
        });
      }
    });
    return dd;
  }
  function close() { if (dd) dd.classList.remove('open'); }
  function open(btn, url, title) {
    var el = getDD();
    el.dataset.url = url;
    el.querySelector('#sd-li').href = 'https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(url);
    el.querySelector('#sd-tw').href = 'https://twitter.com/intent/tweet?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent(title);
    el.querySelector('#sd-hn').href = 'https://news.ycombinator.com/submitlink?u=' + encodeURIComponent(url) + '&t=' + encodeURIComponent(title);
    var r = btn.getBoundingClientRect();
    el.style.top = (r.bottom + 6) + 'px';
    var rightSpace = window.innerWidth - r.right;
    if (rightSpace >= 190) { el.style.left = r.left + 'px'; el.style.right = 'auto'; el.style.transformOrigin = 'top left'; }
    else { el.style.right = (window.innerWidth - r.right) + 'px'; el.style.left = 'auto'; el.style.transformOrigin = 'top right'; }
    el.classList.add('open');
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-share]');
    if (btn) {
      e.preventDefault(); e.stopPropagation();
      var url = btn.dataset.shareUrl || window.location.href;
      var title = btn.dataset.shareTitle || document.title;
      if (navigator.share) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
      if (dd && dd.classList.contains('open')) { close(); return; }
      open(btn, url, title);
      return;
    }
    if (dd && !dd.contains(e.target)) close();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
})();

/* ── Scroll-reveal ───────────────────────────────────────── */
(function () {
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target;
      io.unobserve(el);
      if (reducedMotion) { el.classList.remove('reveal'); return; }
      el.classList.add('visible');
      el.addEventListener('animationend', function done() {
        el.removeEventListener('animationend', done);
        el.classList.remove('reveal', 'visible');
      });
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -32px 0px' });

  document.querySelectorAll('.reveal').forEach(function (el) {
    var idx = parseInt(el.dataset.revealIdx) || 0;
    el.style.setProperty('--reveal-delay', (idx * 80) + 'ms');
    io.observe(el);
  });

  // Dynamically add reveal to post body headings and code blocks
  var postBody = document.querySelector('.post-body');
  if (postBody) {
    postBody.querySelectorAll('h2, h3').forEach(function (h) {
      if (reducedMotion) return;
      if (h.getBoundingClientRect().top <= window.innerHeight) return; // already in viewport
      h.classList.add('reveal');
      h.dataset.reveal = 'left';
      io.observe(h);
    });
    postBody.querySelectorAll('pre').forEach(function (pre, i) {
      if (reducedMotion) return;
      if (pre.getBoundingClientRect().top <= window.innerHeight) return; // already in viewport
      pre.classList.add('reveal');
      pre.dataset.reveal = 'code';
      pre.style.setProperty('--reveal-delay', (i * 60) + 'ms');
      io.observe(pre);
    });
  }
})();

/* ── Stats counter ───────────────────────────────────────── */
(function () {
  function animCount(el, target, dur) {
    var start = null;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var ease = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(ease * target);
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = target;
    }
    requestAnimationFrame(step);
  }
  var statsContainer = document.querySelector('.hero-stats');
  if (!statsContainer) return;
  var statsTriggered = false;
  var statsObs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting && !statsTriggered) {
        statsTriggered = true;
        statsObs.unobserve(e.target);
        e.target.querySelectorAll('.stat-val').forEach(function (el) {
          var raw = el.textContent.trim();
          var num = parseInt(raw, 10);
          if (!isNaN(num) && num > 1) { animCount(el, num, 700); }
        });
      }
    });
  }, { threshold: 0.3 });
  statsObs.observe(statsContainer);
})();

/* ── Code block copy button ──────────────────────────────── */
(function () {
  document.querySelectorAll('.post-body pre, .lp-body pre').forEach(function (pre) {
    var btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.setAttribute('aria-label', 'Copy code');
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
    pre.style.position = 'relative';
    pre.appendChild(btn);
    btn.addEventListener('click', function () {
      var code = pre.querySelector('code');
      if (!code) return;
      navigator.clipboard.writeText(code.textContent).then(function () {
        btn.classList.add('copied');
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
        }, 2000);
      });
    });
  });
})();

/* ── Unified scroll handler: parallax + nav + progress ──── */
(function () {
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nav = document.querySelector('.nav');
  var heroImg = document.querySelector('.hero-bg-img');
  var heroSection = document.querySelector('.hero--home');
  var progressBar = document.querySelector('.reading-progress-bar');
  var ticking = false;

  // On non-hero pages, nav starts already scrolled (added via HTML).
  // On hero pages, remove nav--scrolled so it starts transparent.
  if (heroSection && nav) {
    nav.classList.remove('nav--scrolled');
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var scrollY = window.scrollY || window.pageYOffset;

      // Parallax
      if (heroImg && heroSection && !reducedMotion) {
        var heroH = heroSection.offsetHeight;
        if (scrollY < heroH) {
          heroImg.style.transform = 'translate3d(0,' + (scrollY * 0.35) + 'px,0)';
        } else {
          heroImg.style.transform = 'translate3d(0,0,0)';
        }
      }

      // Nav scroll state
      if (nav) {
        if (scrollY > 20) {
          nav.classList.add('nav--scrolled');
        } else {
          // Only remove scrolled state on hero pages (transparent nav over image)
          if (heroSection) nav.classList.remove('nav--scrolled');
        }
      }

      // Reading progress bar
      if (progressBar) {
        var docH = document.documentElement.scrollHeight - window.innerHeight;
        var progress = docH > 0 ? Math.min(scrollY / docH, 1) : 0;
        progressBar.style.transform = 'scaleX(' + progress + ')';
      }

      ticking = false;
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll(); // Run once on load to set initial state
})();
