# Scroll Animations & Hero Background — Design Spec

## Context

The iOS AI Articles Jekyll blog has a polished "Noir Editorial" dark theme with basic scroll-reveal animations (fade-up on cards). The user wants to elevate the visual experience with:
1. A cinematic hero background image with parallax scrolling
2. Richer scroll choreography across all pages (progress bar, directional reveals, nav transitions)

The blog is hosted on GitHub Pages — no server-side processing, no custom Jekyll plugins, no external JS libraries.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Hero image structure | `<picture>` with `<img>` tag | Allows `transform: translate3d` for GPU parallax; `background-attachment: fixed` is broken on iOS Safari |
| Parallax method | JS `requestAnimationFrame` + passive scroll listener | Cross-browser reliable; CSS Scroll-Driven Animations API lacks Safari support |
| Progress bar method | JS scroll listener + `transform: scaleX()` | Same reasoning; shared scroll handler keeps it efficient |
| Directional reveals | `data-reveal` attributes on elements | Extends existing IntersectionObserver; keeps HTML semantic |
| Smooth anchor scrolling | CSS `scroll-padding-top: 76px` | No JS needed; handles browser back/forward natively |
| Image format | WebP primary + JPEG fallback, committed to repo | GitHub Pages serves static assets; Unsplash is free for use |

## Feature Details

### 1. Hero Background with Parallax (Homepage Only)

**Markup** — Add inside `.hero` in `home.html`, before `.container`:

```html
<section class="hero hero--home">
  <div class="hero-bg" aria-hidden="true">
    <picture>
      <source srcset="{{ '/assets/images/hero-bg.webp' | relative_url }}" type="image/webp">
      <img src="{{ '/assets/images/hero-bg.jpg' | relative_url }}" alt="" class="hero-bg-img" loading="eager" decoding="async" width="2560" height="1440">
    </picture>
    <div class="hero-bg-overlay"></div>
  </div>
  <div class="container"> ...existing content... </div>
</section>
```

**CSS** — New styles for `.hero--home`, `.hero-bg`, `.hero-bg-img`, `.hero-bg-overlay`:
- `.hero--home` removes the dot-grid `background-image`
- `.hero-bg` is absolutely positioned, `overflow: hidden`
- `.hero-bg-img` has `height: 120%` for parallax travel room, `will-change: transform`, `object-fit: cover`
- `.hero-bg-overlay` provides a dark gradient (dark mode: 70%→55%→85% opacity; light mode: 78%→60%→90%) for text readability
- `.hero--home .container` gets `position: relative; z-index: 2` to sit above the image

**JS** — Parallax in unified scroll handler:
- Applies `transform: translate3d(0, scrollY * 0.35, 0)` to `.hero-bg-img`
- Only runs when `scrollY < hero section height`
- Skips entirely if `prefers-reduced-motion: reduce`

**Preload** — Conditional `<link rel="preload">` in `default.html` when `page.layout == 'home'`

**Image** — Dark abstract Unsplash photo, 2560px wide, WebP (quality 80, target <200KB) + JPEG fallback. Saved to `assets/images/hero-bg.webp` and `assets/images/hero-bg.jpg`.

### 2. Nav Scroll Transition (All Pages)

**Behavior:**
- Pages with `.hero`: nav starts transparent, transitions to glassmorphism on scroll (threshold: 20px)
- Pages without `.hero`: nav starts in glass state immediately (`.nav--scrolled` added on load)

**CSS changes to `.nav`:**
- Base state: `background: transparent; backdrop-filter: none; border-bottom: 1px solid transparent`
- `.nav--scrolled`: current glass styles (`background: rgba(8,9,13,0.90); backdrop-filter: blur(22px) saturate(160%); border-color: var(--border)`)
- `transition: background 0.3s, backdrop-filter 0.3s, border-color 0.3s`
- Light mode variants for both states

**JS** — In unified scroll handler: toggle `.nav--scrolled` class based on `scrollY > 20`. If no `.hero` on page, add `.nav--scrolled` immediately.

### 3. Reading Progress Bar (Article + Newsletter Pages)

**Markup** — `<div class="reading-progress-bar" aria-hidden="true"></div>` added at top of `post.html` and `newsletter.html` layouts.

**CSS:**
- `position: fixed; top: 60px; left: 0; right: 0; height: 2px`
- `background: var(--gradient)` (amber→teal)
- `transform-origin: left; transform: scaleX(0)`
- `z-index: 99; pointer-events: none; will-change: transform`

**JS** — In unified scroll handler: `progressBar.style.transform = 'scaleX(' + (scrollY / (docHeight - windowHeight)) + ')'`

### 4. Directional Scroll Reveals (All Pages)

**New CSS keyframes:**
- `reveal-from-left`: `translateX(-32px)` → `0`
- `reveal-from-right`: `translateX(32px)` → `0`
- `reveal-scale`: `scale(0.92)` → `1`
- `reveal-code`: `translateX(-16px)` → `0`

**CSS selectors:** `.reveal.visible[data-reveal="left"]` etc. override `animation-name` on the existing `.reveal.visible` base.

**HTML attribute assignments:**

| Element | `data-reveal` | Pages |
|---------|---------------|-------|
| Section headings (`.section-header`) | `left` | home, newsletter listing |
| Featured cards | `scale` | home, newsletter listing |
| Article grid cards | (default up, staggered via `data-reveal-idx`) | home |
| Post header | `left` | post, newsletter |
| Feed header | `left` | posts (LinkedIn listing) |
| Feed cards | (default up, staggered) | posts |
| Code blocks (`pre`) in articles | `code` | post (added dynamically by JS) |
| Article body `h2`/`h3` | `left` | post (added dynamically by JS) |

**JS changes:**
- Extend existing IntersectionObserver to read `data-reveal` and apply `--reveal-delay` from `data-reveal-idx`
- On article pages (`.post-body` exists): dynamically add `.reveal` + `data-reveal` to `pre`, `h2`, `h3` elements
- Use `animationend` listener to clean up classes after animation completes

### 5. Stats Counter → Scroll-Triggered

Replace `setTimeout(500ms)` with IntersectionObserver on `.hero-stats`. Counter animates (700ms cubic ease) when stats section enters viewport at 30% threshold.

### 6. Smooth Anchor Scrolling

Add `scroll-padding-top: 76px` to `html` rule in CSS (60px nav + 16px breathing room). The existing `scroll-behavior: smooth` handles the rest.

### 7. Reduced Motion

All new features respect `prefers-reduced-motion: reduce`:
- JS parallax handler: checks media query, returns early if reduced
- CSS: existing `@media (prefers-reduced-motion)` block extended with `.hero-bg-img { will-change: auto }` and `.reading-progress-bar { display: none }`
- All new keyframes inherit the `animation-duration: 0.01ms !important` override

## Files Changed

| File | Changes |
|------|---------|
| `_layouts/home.html` | Add `.hero--home` class, hero bg image markup, `data-reveal` attributes on section headers and featured cards |
| `_layouts/default.html` | Conditional `<link rel="preload">` for hero image on home layout |
| `_layouts/post.html` | Add progress bar element, `data-reveal="left"` on post header |
| `_layouts/newsletter.html` | Add progress bar element, `data-reveal="left"` on post header |
| `posts.html` | Add `.reveal` + `data-reveal-idx` to feed cards, `data-reveal="left"` to feed header |
| `newsletter.html` | Add `data-reveal` attributes to section headers and featured card |
| `assets/css/main.css` | Hero bg styles + overlay (dark/light), nav transparent→glass transition, progress bar, directional keyframes + selectors, `scroll-padding-top`, updated `prefers-reduced-motion` |
| `assets/js/main.js` | Unified scroll handler (parallax + nav + progress bar), extended IntersectionObserver (directional reveals + dynamic post body elements), scroll-triggered stats counter |
| `assets/images/hero-bg.webp` | **New** — dark abstract hero image (WebP, <200KB) |
| `assets/images/hero-bg.jpg` | **New** — JPEG fallback |

## Verification

1. **Local preview**: `bundle install && bundle exec jekyll serve` — check homepage hero, scroll through articles
2. **Homepage**: Hero image visible with parallax effect, nav transitions from transparent to glass, cards reveal with stagger, featured cards scale up, stats animate on scroll
3. **Article page**: Progress bar fills on scroll, headings reveal from left, code blocks slide in, nav starts in glass state
4. **Newsletter/LinkedIn listings**: Cards reveal with stagger, section headers from left
5. **Light mode**: Toggle theme — hero overlay adjusts, nav glass state uses light colors, all reveals work
6. **Reduced motion**: Enable in OS settings — no parallax, no progress bar, reveals instant
7. **Mobile (responsive)**: Check at 768px and 480px breakpoints — parallax still smooth, progress bar visible, nav transition works
8. **Safari**: Parallax uses `translate3d` (not `background-attachment: fixed`), so it should work correctly
