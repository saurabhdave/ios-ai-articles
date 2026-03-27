# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role of This Repository

This is the **output destination** for the automated pipeline at https://github.com/saurabhdave/ios-dev-ai-writer. Content is generated and pushed here via GitHub Actions 2x/week (Monday, Thursday at 10:00 UTC). Do not manually create or edit article files — they are machine-generated and committed by the writer pipeline.

## Upstream Pipeline (ios-dev-ai-writer)

Eight-phase automated pipeline:

1. **Trend Discovery** — aggregates signals from 9 sources (HackerNews, Reddit r/iOSProgramming, Apple Developer feeds, WWDC sessions, Google News RSS web search, social/dev.to/Medium, viral web/social, platforms, custom sources)
2. **Topic Generation** — GPT-based (gpt-5-mini), deduped by word-overlap (>50% = reject) and semantic similarity (threshold 0.80); family rotation sampler de-weights recently used topic families; falls back to curated topics on failure
3. **Outline + Article** — quality-gated: requires ≥2 Apple signals + ≥3 practical signals + decision language ("when to", "vs"); loaded from `prompts/article_prompt.txt`; optional anti-pattern sub-point per section
4. **Code Generation** — Swift 6.2.4 via `swiftc` compile validation; minimum deployment target iOS 18 / Swift 6; up to 2 repair cycles; 35-line max per snippet; enforces `@Observable`, `OSSignposter`, and other modern APIs; no deprecated APIs (`@Published`, `@ObservableObject`, `os_signpost` are all rejected)
5. **Editorial Pass** — Medium-format polish; max 2 passes; quality score ≥8; deterministic Swift API backtick formatting and "Operational note:" label stripping applied post-generation
6. **Review/QA** — self-review with running JSON history; optional fact-grounding (1 pass max)
7. **LinkedIn Generation** — 3-stage pipeline (generate → constrain → fact-ground); 1,700-character limit; auto hashtag management
8. **Newsletter Generation** — SwiftTribune-style weekly digest with 6 sections (Opening hook, Big Story, Trend Signals, Swift Snippet of the Week, Community Picks, Closing CTA); output as Markdown + email-safe HTML; issue number auto-increments

## Output Structure

Four directories, all files date-prefixed:

```
articles/YYYY-MM-DD-<topic-slug>.md
linkedin/YYYY-MM-DD-<topic-slug>-linkedin.md
codegen/YYYY-MM-DD-<topic-slug>-codegen.json
newsletter/YYYY-MM-DD-issue-N.md
newsletter/YYYY-MM-DD-issue-N.html
```

## Article Format

Five sections, each with up to four subsections:
- **Apple API / Tool Callout** — specific UIKit vs SwiftUI APIs at stake
- **When to choose which** — decision guidance with named tiers (Simple / Moderate / Advanced), or before/after contrast for patterns/practices topics
- **Operational / Observability note** — metrics, traces, lifecycle logging guidance (label stripped deterministically; integrated as natural prose)
- **Anti-pattern** (optional) — common mistake and how to avoid it

Each core section includes one `swift` code block (4–10 lines). Patterns/practices topics may relax the Instruments/MetricKit observability requirement.

Sections:
1. Understanding Parity
2. Migration Strategy for Large Codebases
3. Interactions, Editing, and Advanced Behaviors
4. Performance, Lifecycle, and Memory
5. Validation, Testing, and Rollout

Ends with a **Closing Takeaway** and an **Implementation Checklist**.

## Codegen JSON Schema

```json
{
  "topic": "string",
  "generated_at_utc": "ISO 8601 timestamp",
  "path": "string (may be 'omitted' if validation failed)",
  "repair_attempts": 0,
  "swift_language_version": "6.2.4",
  "swift_language_mode": "6",
  "diagnostics_excerpt": "string (compiler errors or validation notes)"
}
```

## LinkedIn Post Format

- ~1,700 characters max
- Opening hook → 3–4 actionable bullet points → optional 4–6 line code snippet → engagement question (CTA)
- 5–6 hashtags: `#iOS #Swift #SwiftUI #Architecture #EngineeringLeadership #MobileDev`

## Content Standards

- Target audience: all iOS engineers, written from a senior perspective; previously gated to senior/production apps only
- Tone: risk-aware and practical; trade-offs must be explicit, not just benefits; benefit-driven title framing is allowed for patterns/practices topics
- Decision frameworks required (e.g., "Simple / Moderate / Advanced" classification), or before/after contrast structure
- Apple API callouts must specify UIKit vs. SwiftUI tooling explicitly
- iOS 18 / Swift 6 minimum — no pre-iOS 18 API patterns; no `os_signpost` (use `OSSignposter`); no `@Published`/`@ObservableObject`

## Editorial Gate

A two-layer automated quality gate prevents low-quality or policy-violating content from reaching the blog.

### Layer 1 — Pre-push (ios-dev-ai-writer pipeline)
`scripts/editorial_gate.py` in ios-dev-ai-writer runs after generation and before syncing to this repo. Failing articles are moved to `outputs/quarantine/` and never pushed.

### Layer 2 — Post-push (this repo)
`scripts/editorial_gate.py` here runs on every push via `.github/workflows/editorial-review.yml`. It removes any violations that slipped through and auto-commits the cleanup with `[skip ci]`. `update_readme.py` is also run inline (since `[skip ci]` suppresses the normal readme workflow).

### Gate rules (both layers enforce the same four checks)

| # | Check | Failure condition | Action |
|---|-------|-------------------|--------|
| 1 | Validated Swift code | `codegen.json` `path == "omitted"` | Remove article + linkedin + codegen |
| 2 | No banned deprecated APIs | `@Published`, `@ObservableObject`, or `os_signpost(` in ` ```swift ` blocks | Same |
| 3 | No duplicate topic | Jaccard > 0.5 on stopword-filtered H1 tokens vs all other articles | Remove weaker duplicate (prefer code-validated; prefer newer on tie) |
| 4 | Newsletter not orphaned | Newsletter Big Story title matches an existing article H1 | Remove `.md` + `.html` pair |

### Running locally

```bash
# Dry-run — report only, no deletions
python scripts/editorial_gate.py --dry-run

# Live run
python scripts/editorial_gate.py
```

Exit 0 = all clear. Exit 1 = files removed (CI will commit the removals).

## Jekyll Blog

The repo publishes a blog at `https://saurabhdave.github.io/ios-ai-articles` via GitHub Pages.

**How it works:**
- `scripts/prep_jekyll.py` — called by the Jekyll workflow; copies `articles/*.md` → `_posts/` with injected YAML front matter (layout, title, date, categories). `_posts/` is gitignored — never edit files there.
- `.github/workflows/jekyll.yml` — triggers on every push to `main`; runs `prep_jekyll.py`, builds with `bundle exec jekyll build`, deploys via `actions/deploy-pages`
- `.github/workflows/update-readme.yml` — triggers on push to `articles/**` or `linkedin/**`; regenerates the articles table in README.md between `<!-- ARTICLES_TABLE_START -->` and `<!-- ARTICLES_TABLE_END -->` markers
- `_config.yml` — custom dark theme (layouts in `_layouts/`, styles in `assets/css/main.css`), permalink: `/articles/:year/:month/:day/:title/`
- `Gemfile` — `github-pages` gem + `webrick`

**Local preview:** `bundle install && bundle exec jekyll serve`

**Do not commit:** `_posts/`, `_site/`, `.jekyll-cache/`, `Gemfile.lock` — all gitignored.

## Git Commit Pattern

```
article: YYYY-MM-DD
```
