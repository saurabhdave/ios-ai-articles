# iOS AI Articles

Automated technical articles for senior iOS engineers, generated 2x/week (Monday & Thursday) by the [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer) pipeline and published at **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**.

Topics focus on production-grade Swift and SwiftUI: architecture decisions, migration strategies, performance, and risk-aware rollout patterns.

## Blog

Live at → **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**

Built with Jekyll (custom dark theme) and deployed to GitHub Pages via GitHub Actions on every push.

### Local preview

```bash
bundle install
bundle exec jekyll serve
```

## Structure

```
articles/     Full long-form articles — source of truth, pushed by the writer pipeline
linkedin/     LinkedIn-optimized posts (~1,700 chars) for each article
codegen/      Swift code generation metadata (compilation results, diagnostics)
newsletter/   Weekly iOS Dev Weekly newsletter — Markdown + email-safe HTML per issue
scripts/      editorial_gate.py — quality gate (see below)
              update_readme.py  — auto-updates this table
              prep_jekyll.py    — bridges articles/ to Jekyll _posts/
```

All content files share a date-prefixed naming convention:

```
YYYY-MM-DD-<topic-slug>.md
YYYY-MM-DD-<topic-slug>-linkedin.md
YYYY-MM-DD-<topic-slug>-codegen.json
YYYY-MM-DD-issue-N.md
YYYY-MM-DD-issue-N.html
```

## Recent Articles

Latest 10 — full list at **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**.

<!-- ARTICLES_TABLE_START -->
| Date | Article | LinkedIn |
|------|---------|----------|
| 2026-03-27 | [Structured Concurrency Patterns for Swift 6.3](articles/2026-03-27-structured-concurrency-patterns-for-swift-63.md) | [Post](linkedin/2026-03-27-structured-concurrency-patterns-for-swift-63-linkedin.md) |
| 2026-03-26 | [Structured Concurrency Patterns for Production Swift Apps](articles/2026-03-26-structured-concurrency-patterns-for-production-swift-apps.md) | [Post](linkedin/2026-03-26-structured-concurrency-patterns-for-production-swift-apps-linkedin.md) |
| 2026-03-23 | [Profile SwiftUI Rendering with Instruments](articles/2026-03-23-profile-swiftui-rendering-with-instruments.md) | [Post](linkedin/2026-03-23-profile-swiftui-rendering-with-instruments-linkedin.md) |
| 2026-03-22 | [Dependency Injection Patterns for Production SwiftUI](articles/2026-03-22-dependency-injection-patterns-for-production-swiftui.md) | [Post](linkedin/2026-03-22-dependency-injection-patterns-for-production-swiftui-linkedin.md) |
| 2026-03-21 | [Privacy-First Telemetry with Swift Concurrency](articles/2026-03-21-privacy-first-telemetry-with-swift-concurrency.md) | [Post](linkedin/2026-03-21-privacy-first-telemetry-with-swift-concurrency-linkedin.md) |
| 2026-03-17 | [Custom SwiftUI Layouts with the Layout Protocol](articles/2026-03-17-custom-swiftui-layouts-with-the-layout-protocol.md) | [Post](linkedin/2026-03-17-custom-swiftui-layouts-with-the-layout-protocol-linkedin.md) |
| 2026-03-16 | [Migrate URLSession to Swift async/await](articles/2026-03-16-migrate-urlsession-to-swift-asyncawait.md) | [Post](linkedin/2026-03-16-migrate-urlsession-to-swift-asyncawait-linkedin.md) |
| 2026-03-16 | [Migrate Combine to Swift async/](articles/2026-03-16-migrate-combine-to-swift-async.md) | [Post](linkedin/2026-03-16-migrate-combine-to-swift-async-linkedin.md) |
| 2026-03-14 | [Migrate ViewController Navigation to SwiftUI NavigationStack](articles/2026-03-14-migrate-viewcontroller-navigation-to-swiftui-navigationstack.md) | [Post](linkedin/2026-03-14-migrate-viewcontroller-navigation-to-swiftui-navigationstack-linkedin.md) |
<!-- ARTICLES_TABLE_END -->

## Article Format

Each article follows a consistent 5-section structure:

1. **Understanding Parity** — API comparison, UIKit vs SwiftUI tooling
2. **Migration Strategy** — incremental vs full rewrite, hosting techniques
3. **Interactions & Advanced Behaviors** — gestures, editing, compositional layouts
4. **Performance, Lifecycle & Memory** — Instruments usage, pitfalls, thresholds
5. **Validation, Testing & Rollout** — XCTest, feature flags, canary strategy

Each section includes: Apple API callouts, a decision framework (Simple / Moderate / Advanced), and observability guidance.

## Editorial Gate

Every push to this repo triggers an automated editorial review (`scripts/editorial_gate.py`) that enforces four hard rules:

| # | Rule | Action |
|---|------|--------|
| 1 | Article must have a validated Swift code snippet (`codegen path ≠ "omitted"`) | Remove article + companions |
| 2 | No banned deprecated APIs (`@Published`, `@ObservableObject`, `os_signpost(`) in Swift code blocks | Remove article + companions |
| 3 | No duplicate topic — Jaccard similarity > 0.5 against other article titles | Remove the weaker duplicate |
| 4 | Newsletter Big Story title must match an existing article H1 | Remove orphaned newsletter |

Failures are committed automatically with `[skip ci]`. The same gate also runs in the upstream pipeline ([ios-dev-ai-writer#1](https://github.com/saurabhdave/ios-dev-ai-writer/pull/1)) as a pre-push quarantine step, so most issues are caught before they ever reach this repo.

## Automation

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `editorial-review.yml` | Push to `articles/**`, `newsletter/**`, `codegen/**`, `linkedin/**` | Runs editorial gate; auto-removes violations and refreshes README |
| `update-readme.yml` | Push to `articles/**` or `linkedin/**` | Regenerates the articles table above |
| `jekyll.yml` | Push to `main` | Runs `prep_jekyll.py` → Jekyll build → deploys to GitHub Pages |

## Source

Articles are generated by [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer) (v1.4.0). Swift code samples are validated against Swift 6.2.4 via `swiftc`; the `codegen/` JSON files record diagnostics and repair attempts for each run.
