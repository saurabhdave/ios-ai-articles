# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role of This Repository

This is the **output destination** for the automated pipeline at https://github.com/saurabhdave/ios-dev-ai-writer. Content is generated and pushed here via GitHub Actions 2x/week (Monday, Thursday at 10:00 UTC). Do not manually create or edit article files — they are machine-generated and committed by the writer pipeline.

## Upstream Pipeline (ios-dev-ai-writer)

Seven-phase automated pipeline:

1. **Trend Discovery** — aggregates signals from 8 sources (HackerNews, Reddit r/iOSProgramming, Apple Developer feeds, WWDC sessions, Google News RSS, social/dev.to/Medium, custom sources)
2. **Topic Generation** — GPT-based, deduped by word-overlap (>60% = reject) and semantic similarity (threshold 0.88); falls back to curated topics on failure
3. **Outline + Article** — quality-gated: requires ≥2 Apple signals + ≥3 practical signals + decision language ("when to", "vs"); loaded from `prompts/article_prompt.txt`
4. **Code Generation** — Swift 6.2.4 via `swiftc` compile validation; up to 2 repair cycles; flags deprecated patterns (`@Published`, `@ObservableObject`) and enforces `@Observable`
5. **Editorial Pass** — Medium-format polish; max 2 passes; quality score ≥8
6. **Review/QA** — self-review with running JSON history; optional fact-grounding (1 pass max)
7. **LinkedIn Generation** — 3-stage pipeline (generate → constrain → fact-ground); 1,700-character limit; auto hashtag management

## Output Structure

Four directories, all files date-prefixed:

```
articles/YYYY-MM-DD-<topic-slug>.md
linkedin/YYYY-MM-DD-<topic-slug>-linkedin.md
codegen/YYYY-MM-DD-<topic-slug>-codegen.json
images/YYYY-MM-DD-<topic-slug>.png       ← cover image (Google Imagen 3, 16:9)
```

Articles may include an optional YAML frontmatter block at the top when a cover image was generated:

```markdown
---
cover_image: images/YYYY-MM-DD-<topic-slug>.png
---
```

`scripts/prep_jekyll.py` detects this partial frontmatter and merges it with the full Jekyll frontmatter (layout, title, date, categories).

## Article Format

Five sections, each with three subsections:
- **Apple API / Tool Callout** — specific UIKit vs SwiftUI APIs at stake
- **When to choose which** — decision guidance with named tiers (Simple / Moderate / Advanced)
- **Operational / Observability note** — metrics, traces, lifecycle logging guidance

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

- Target audience: senior iOS engineers on production/mission-critical apps
- Tone: risk-aware and practical; trade-offs must be explicit, not just benefits
- Decision frameworks required (e.g., "Simple / Moderate / Advanced" classification)
- Apple API callouts must specify UIKit vs. SwiftUI tooling explicitly

## Jekyll Blog

The repo publishes a blog at `https://saurabhdave.github.io/ios-ai-articles` via GitHub Pages.

**How it works:**
- `scripts/prep_jekyll.py` — called by the Jekyll workflow; copies `articles/*.md` → `_posts/` with injected YAML front matter (layout, title, date, categories). `_posts/` is gitignored — never edit files there.
- `.github/workflows/jekyll.yml` — triggers on every push to `main`; runs `prep_jekyll.py`, builds with `bundle exec jekyll build`, deploys via `actions/deploy-pages`
- `.github/workflows/update-readme.yml` — triggers on push to `articles/**` or `linkedin/**`; regenerates the articles table in README.md between `<!-- ARTICLES_TABLE_START -->` and `<!-- ARTICLES_TABLE_END -->` markers
- `_config.yml` — minima theme, permalink: `/articles/:year/:month/:day/:title/`
- `Gemfile` — `github-pages` gem + `webrick`

**Local preview:** `bundle install && bundle exec jekyll serve`

**Do not commit:** `_posts/`, `_site/`, `.jekyll-cache/`, `Gemfile.lock` — all gitignored.

## Git Commit Pattern

```
article: YYYY-MM-DD
```
