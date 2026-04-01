# iOS AI Articles

Automated technical articles for senior iOS engineers, generated 2x/week (Monday & Thursday) by the [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer) pipeline and published at **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**.

Topics focus on production-grade Swift and SwiftUI: architecture decisions, migration strategies, performance, and risk-aware rollout patterns.

## Blog

Live at → **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**

Built with Jekyll (custom dark theme) and deployed to GitHub Pages via GitHub Actions on every push.

RSS feed available at **[saurabhdave.github.io/ios-ai-articles/feed.xml](https://saurabhdave.github.io/ios-ai-articles/feed.xml)** — works in Reeder, NetNewsWire, Feedly, and any RSS reader.

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
| 2026-03-31 | [Speed Xcode Builds with Explicit Swift Modules](articles/2026-03-31-speed-xcode-builds-with-explicit-swift-modules.md) | [Post](linkedin/2026-03-31-speed-xcode-builds-with-explicit-swift-modules-linkedin.md) |
| 2026-03-31 | [Automating Dynamic Type Tests in Xcode](articles/2026-03-31-automating-dynamic-type-tests-in-xcode.md) | [Post](linkedin/2026-03-31-automating-dynamic-type-tests-in-xcode-linkedin.md) |
| 2026-03-30 | [Verified SwiftUI Modifiers for Safer App UI](articles/2026-03-30-verified-swiftui-modifiers-for-safer-app-ui.md) | [Post](linkedin/2026-03-30-verified-swiftui-modifiers-for-safer-app-ui-linkedin.md) |
| 2026-03-29 | [Custom Layouts Using SwiftUI's Layout Protocol](articles/2026-03-29-custom-layouts-using-swiftuis-layout-protocol.md) | [Post](linkedin/2026-03-29-custom-layouts-using-swiftuis-layout-protocol-linkedin.md) |
| 2026-03-27 | [Profiling SwiftUI Rendering in Instruments](articles/2026-03-27-profiling-swiftui-rendering-in-instruments.md) | [Post](linkedin/2026-03-27-profiling-swiftui-rendering-in-instruments-linkedin.md) |
| 2026-03-26 | [Structured Concurrency Patterns for Production Swift Apps](articles/2026-03-26-structured-concurrency-patterns-for-production-swift-apps.md) | [Post](linkedin/2026-03-26-structured-concurrency-patterns-for-production-swift-apps-linkedin.md) |
| 2026-03-22 | [Dependency Injection Patterns for Production SwiftUI](articles/2026-03-22-dependency-injection-patterns-for-production-swiftui.md) | [Post](linkedin/2026-03-22-dependency-injection-patterns-for-production-swiftui-linkedin.md) |
| 2026-03-21 | [Privacy-First Telemetry with Swift Concurrency](articles/2026-03-21-privacy-first-telemetry-with-swift-concurrency.md) | [Post](linkedin/2026-03-21-privacy-first-telemetry-with-swift-concurrency-linkedin.md) |
| 2026-03-16 | [Migrate URLSession to Swift async/await](articles/2026-03-16-migrate-urlsession-to-swift-asyncawait.md) | [Post](linkedin/2026-03-16-migrate-urlsession-to-swift-asyncawait-linkedin.md) |
| 2026-03-16 | [Migrate Combine to Swift async/await](articles/2026-03-16-migrate-combine-to-swift-async.md) | [Post](linkedin/2026-03-16-migrate-combine-to-swift-async-linkedin.md) |

> Showing 10 of 11 articles — [1 more on the blog](https://saurabhdave.github.io/ios-ai-articles)
<!-- ARTICLES_TABLE_END -->

## Article Format

Each article follows a consistent long-form engineering format:

1. **Understanding Parity** — API comparison, UIKit vs SwiftUI tooling
2. **Migration Strategy** — incremental vs full rewrite, hosting techniques
3. **Interactions & Advanced Behaviors** — gestures, editing, compositional layouts
4. **Performance, Lifecycle & Memory** — Instruments usage, pitfalls, thresholds
5. **Validation, Testing & Rollout** — XCTest, feature flags, canary strategy

Recent articles typically include Apple API callouts, explicit tradeoffs, and testing or observability guidance tuned for production iOS work.

## Editorial Gate

Pushes with new or changed published artifacts trigger an automated editorial review (`scripts/editorial_gate.py`) that enforces these hard rules:

| # | Rule | Action |
|---|------|--------|
| 1 | Article must have a validated Swift code snippet (`codegen path ≠ "omitted"`) | Remove article + companions |
| 2 | No banned deprecated APIs (`@Published`, `@ObservableObject`, `os_signpost(`) in Swift code blocks | Remove article + companions |
| 3 | Article H1 must be present and not obviously malformed/truncated | Remove article + companions |
| 4 | No duplicate topic — Jaccard similarity > 0.5 against other article titles | Remove the weaker changed duplicate |
| 5 | Newsletter Big Story title must match an existing article H1 | Remove orphaned newsletter |

The gate scopes strict checks to changed artifacts, while still comparing new article titles against the full archive for duplicates. Follow-up fixes are committed automatically by the editorial workflow. The same gate logic also exists upstream in the writer pipeline, so most issues are caught before they reach this repo.

### Advisory check — code logic review

After the hard rules, the gate runs an OpenAI-powered review of Swift code blocks in changed articles for issues `swiftc` cannot catch (data races, wrong `@Bindable` usage, misleading concurrency patterns, missing actor isolation). This check is **advisory only** — it never removes files; it prints `[CODE-REVIEW]` warnings to the log and writes all findings to `outputs/code_review_log.json`. The workflow step appends a formatted table to the GitHub Actions job summary.

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `OPENAI_API_KEY` | _(none)_ | Repository secret. If absent the check is silently skipped. |
| `CODE_REVIEW_ENABLED` | `true` | Set to `false` to disable the check without removing the secret. |

## Automation

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `editorial-review.yml` | Push to `articles/**`, `newsletter/**`, `codegen/**`, `linkedin/**` | Runs editorial gate, refreshes README, and commits any follow-up removals/docs updates |
| `jekyll.yml` | Push to `main` | Runs `prep_jekyll.py` → Jekyll build → deploys to GitHub Pages; ignores README-only bot commits |

## Source

Articles are generated by [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer). Swift code samples are validated against Swift 6.2.4 via `swiftc`; the `codegen/` JSON files record diagnostics and repair attempts for each run.
