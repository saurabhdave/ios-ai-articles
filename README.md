# iOS AI Articles

Automated technical articles for senior iOS engineers, generated 2x/week (Monday & Thursday) by the [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer) pipeline and published at **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**.

Topics focus on senior-level Swift and SwiftUI: architecture decisions, migration strategies, performance, and risk-aware rollout patterns.

## Blog

Live at → **[saurabhdave.github.io/ios-ai-articles](https://saurabhdave.github.io/ios-ai-articles)**

Built with Jekyll (custom "Mainframe" editorial theme — warm-paper palette with full light/dark mode, self-hosted Geist + Source Serif 4 type (both OFL), and a mouse-scrubbed video hero on the homepage) and deployed to GitHub Pages via GitHub Actions on every push.

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
scripts/      editorial_gate.py  — quality gate (see below)
              swift_lint.py      — regex guard for never-valid Swift APIs (ubuntu)
              swift_typecheck.py — compiles every Swift block via swiftc (macOS)
              update_readme.py   — auto-updates this table
              prep_jekyll.py     — bridges articles/ to Jekyll _posts/
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
| 2026-06-18 | [Update Sign in with Apple Domains Without Breaking Login](articles/2026-06-18-update-sign-in-with-apple-domains-without-breaking-login.md) | [Post](linkedin/2026-06-18-update-sign-in-with-apple-domains-without-breaking-login-linkedin.md) |
| 2026-06-15 | [NavigationStack Patterns for visionOS](articles/2026-06-15-navigationstack-patterns-for-visionos.md) | [Post](linkedin/2026-06-15-navigationstack-patterns-for-visionos-linkedin.md) |
| 2026-06-12 | [Xcode 27 Tooling Updates From WWDC 2026](articles/2026-06-12-xcode-27-tooling-updates-from-wwdc-2026.md) | [Post](linkedin/2026-06-12-xcode-27-tooling-updates-from-wwdc-2026-linkedin.md) |
| 2026-06-12 | [What the WWDC 2026 Keynote Means for iOS Teams](articles/2026-06-12-what-the-wwdc-2026-keynote-means-for-ios-teams.md) | [Post](linkedin/2026-06-12-what-the-wwdc-2026-keynote-means-for-ios-teams-linkedin.md) |
| 2026-06-12 | [SwiftUI Changes From WWDC 2026 Worth Adopting Now](articles/2026-06-12-swiftui-changes-from-wwdc-2026-worth-adopting-now.md) | [Post](linkedin/2026-06-12-swiftui-changes-from-wwdc-2026-worth-adopting-now-linkedin.md) |
| 2026-06-12 | [Swift Concurrency Updates Announced at WWDC 2026](articles/2026-06-12-swift-concurrency-updates-announced-at-wwdc-2026.md) | [Post](linkedin/2026-06-12-swift-concurrency-updates-announced-at-wwdc-2026-linkedin.md) |
| 2026-06-12 | [macOS 27 Menu Redesign Impact for Mac App Teams](articles/2026-06-12-macos-27-menu-redesign-impact-for-mac-app-teams.md) | [Post](linkedin/2026-06-12-macos-27-menu-redesign-impact-for-mac-app-teams-linkedin.md) |
| 2026-06-11 | [Scalable Dynamic Type in SwiftUI](articles/2026-06-11-scalable-dynamic-type-in-swiftui.md) | [Post](linkedin/2026-06-11-scalable-dynamic-type-in-swiftui-linkedin.md) |
| 2026-06-09 | [Getting Your iOS App Ready for iOS 27 Betas](articles/2026-06-09-getting-your-ios-app-ready-for-ios-27-betas.md) | [Post](linkedin/2026-06-09-getting-your-ios-app-ready-for-ios-27-betas-linkedin.md) |
| 2026-06-08 | [Structured Concurrency Patterns for iOS Networking](articles/2026-06-08-structured-concurrency-patterns-for-ios-networking.md) | [Post](linkedin/2026-06-08-structured-concurrency-patterns-for-ios-networking-linkedin.md) |

> Showing 10 of 32 articles — [22 more on the blog](https://saurabhdave.github.io/ios-ai-articles)
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
| 2b | No never-valid Swift API patterns in code blocks — high-precision regex guard (`scripts/swift_lint.py`) | Remove article + companions |
| 3 | Article H1 must be present and not obviously malformed/truncated | Remove article + companions |
| 4 | No duplicate topic — Jaccard similarity > 0.5 against other article titles | Remove the weaker changed duplicate |
| 5 | Newsletter Big Story title must match an existing article H1 | Remove orphaned newsletter |

Check 2b (`scripts/swift_lint.py`) encodes the specific hallucination/API-misuse classes that have shipped before — wrong `OSSignposter` overloads (`endInterval(id:)`, `OSSignposter(logger: OSLog(…))`, `.emit(`), `@MainActor actor`, invented AppIntents `ValidationResult`, RealityKit `Entity.destroy()`, `Task.Handle`, `import OSSignpost`, SwiftUI `Color.windowBackgroundColor`, `systemLayoutSizeFitting(traitCollection:)`, … — as deterministic, zero-dependency regexes (comments and string literals are ignored). `error`-severity findings remove the article; `warning`-severity findings (deprecated `@_implementationOnly`, MetricKit on watchOS, …) are printed only. It runs on ubuntu, so it needs no Xcode.

The gate scopes strict checks to changed artifacts, while still comparing new article titles against the full archive for duplicates. Follow-up fixes are committed automatically by the editorial workflow. The same gate logic also exists upstream in the writer pipeline, so most issues are caught before they reach this repo.

### Advisory check — code logic review

After the hard rules, the gate runs an OpenAI-powered review of Swift code blocks in changed articles for issues `swiftc` cannot catch (data races, wrong `@Bindable` usage, misleading concurrency patterns, missing actor isolation). This check is **advisory only** — it never removes files; it prints `[CODE-REVIEW]` warnings to the log and writes all findings to `outputs/code_review_log.json`. The workflow step appends a formatted table to the GitHub Actions job summary.

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `OPENAI_API_KEY` | _(none)_ | Repository secret. If absent the check is silently skipped. |
| `CODE_REVIEW_ENABLED` | `true` | Set to `false` to disable the check without removing the secret. |
| `CODE_REVIEW_MODEL` | `gpt-5` | OpenAI model for the review. GPT-5/o-series automatically run without the `temperature` override. At this repo's volume the cost is a few cents/month for any model. |

### Swift compile gate (`scripts/swift_typecheck.py`)

The highest-fidelity check actually compiles **every** ```swift block (not just the one canonical example) with `swiftc -typecheck` against the real iOS / macOS / watchOS SDK. It needs Xcode, so it runs on macOS via the `swift-typecheck.yml` workflow (and locally: `python scripts/swift_typecheck.py articles/`).

It is **stub-tolerant**: illustrative snippets reference undefined helper symbols on purpose, so "cannot find … in scope" diagnostics (and their cascades) are ignored, and an SDK-appropriate import preamble is injected so import-less fragments resolve. What remains — wrong argument labels, nonexistent members/overloads/modules, failed conformances — fails the gate. Mode-sensitive actor-isolation diagnostics are reported as non-blocking warnings unless `--strict-concurrency` is passed; `--swift6` selects Swift 6 language mode. Pseudocode blocks are skipped.

## Automation

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `editorial-review.yml` | Push to `articles/**`, `newsletter/**`, `codegen/**`, `linkedin/**` | Runs editorial gate (incl. the `swift_lint.py` regex guard), refreshes README, and commits any follow-up removals/docs updates |
| `swift-typecheck.yml` | Push to `articles/**`; manual dispatch | Compiles the changed articles' Swift blocks against the real SDK on macOS (`swift_typecheck.py --changed`; manual dispatch checks all). Writes a job summary and, on failure, files/updates a **"Swift type-check failures"** GitHub issue — a backstop for anything that slips the writer's in-pipeline strip guard. Consumes macOS Actions minutes (~10× ubuntu); remove the `push` trigger to make it manual-only |
| `jekyll.yml` | Push to `main` | Runs `prep_jekyll.py` → Jekyll build → deploys to GitHub Pages; ignores README-only bot commits |

## Source

Articles are generated by [ios-dev-ai-writer](https://github.com/saurabhdave/ios-dev-ai-writer). Swift code samples are validated against Swift 6.2.4 via `swiftc`; the `codegen/` JSON files record diagnostics and repair attempts for each run. On the repo side, the Editorial Gate's regex guard (`swift_lint.py`) and the macOS compile gate (`swift_typecheck.py`) re-validate **every** code block — not just the one canonical example — so inline section snippets are covered too.
