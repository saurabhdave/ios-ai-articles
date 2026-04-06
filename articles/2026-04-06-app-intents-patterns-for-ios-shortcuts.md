# App Intents Patterns for iOS Shortcuts

Shortcuts that “do nothing” in production often trace back to a few concrete failures: an `AppIntent` that stops resolving, a permission prompt that never appears, or long-running work that the system suspends. These silent failures increase support load and frustrate users. The guidance below focuses on design, execution, migration, and observability decisions that reduce those incidents.

## Why This Matters For iOS Teams
Shortcuts touch automation, background work, and user data; a breaking change can disable many automations without an obvious error. If a shortcut invocation cannot be correlated to a traceable client or server action, diagnosing failures becomes prolonged and uncertain. Invest early in predictable parameter contracts, quick intent execution, and structured observability so rollouts behave like feature flags rather than opaque incidents.

> Design `AppIntent` contracts for resolution stability first; observability makes the rest diagnosable.

## 1. Intent Design & Parameters
### Typed Parameters Over Freeform Parsing
Prefer `AppIntent` typed parameters instead of parsing a single freeform `String`. Define inputs with `@Parameter` and explicit types such as `Date` or an `enum`. Typed parameters improve resolution behavior and surface relevant suggestions to the user through the system.

Choose typed parameters when the input shape is known and stable; choose freeform `String` when user intent is genuinely ambiguous and cannot be described by concrete types. Add unit tests that serialize and deserialize parameter payloads and validate localized labels so label changes don't break resolution. Validate parameter migration paths in CI by loading archived shortcut metadata and asserting that resolution still succeeds with legacy labels.

Example pattern:
```swift
import AppIntents
import Foundation

struct SetReminderIntent: AppIntent {
  static var title: LocalizedStringResource = "Set Reminder"

  @Parameter(title: "Title")
  var title: String

  @Parameter(title: "When")
  var date: Date

  func perform() async throws -> some IntentResult {
    // Quick synchronous acknowledgment; offload long work elsewhere.
    return .result(value: "Reminder scheduled")
  }
}
```

## 2. Execution Context & Background Work
### Keep `perform()` Fast; Handoff Long Work
`AppIntent.perform()` executes in a constrained system context; multi-second network flows and long uploads may be suspended or terminated by the system under resource pressure. Run quick, synchronous work in `perform()` and hand off persistent or long-running tasks to your app via background scheduling or background work APIs.

Choose to complete short, idempotent work in `perform()` when you can finish within the system's execution window; choose a background worker when work requires retries, large uploads, or cross-device coordination. Implement idempotency keys and retry logic in the background worker, and return an explicit synchronous result like "Upload pending" when deferring work so users see that the intent accepted the request. Validate cancellation and retry paths before rollout; a task that cannot be cancelled leaks CPU and battery.

## 3. Error Handling, User Feedback & Privacy
### Localized Errors And Permission Expectations
Return actionable errors with localized failure reasons and clear recovery instructions instead of opaque messages. Declare which system permission prompts an intent may require and avoid triggering prompts unexpectedly during background runs. For transient backend failures, log internally and provide a clear retry path.

Choose to surface user-visible errors when recovery is possible; choose silent logging when an error is transient and a retry will resolve it automatically. Preserve error shapes where compatibility matters to avoid breaking existing automations, and stage permission-flow changes behind feature flags while documenting them in release notes. When an intent may request a permission, surface that during an interactive flow and log the expected prompt so support and diagnostics teams know what to expect.

## 4. Migration, Versioning & Rollout
### Preserve Identifiers And Migrate Gradually
Intent identifiers, parameter names, and localized labels used in installed shortcuts can be brittle. Renaming or removing them in a single release can cause existing shortcuts to stop resolving or behave differently. Keep identifiers and parameter keys stable; if a change is required, implement a compatibility shim that accepts both old and new values, gate the change with a feature flag, and run a staged rollout.

Choose incremental migration when many users have existing shortcuts; choose immediate change only for security or legal reasons where the old shape is untenable. Test migrations by loading archived shortcut metadata in CI and validate resolution against both legacy and new schemas. Provide a deprecation plan and a recovery path for users whose shortcuts break, and include recovery tooling or a follow-up intent to repair metadata where feasible.

## Tradeoffs And Pitfalls
Typed parameters reduce runtime parsing errors but increase migration overhead when data shapes evolve. More observability yields useful traces but increases storage and noise; use sampling and gated, high-volume logs. Offloading work to background tasks reduces perceived latency but introduces scheduling uncertainty, retry complexity, and potential device resource costs under load.

A common failure mode is tight typing plus localized label changes causing Shortcuts to stop resolving existing automations. Mitigate this by mapping legacy labels to current enum cases inside `perform()` and keeping a short-lived compatibility layer. Also avoid surprising automation by ensuring permission prompts are documented and surfaced only in interactive flows.

## Validation & Observability
Instrument and test intents so you can trace a shortcut invocation end-to-end. Use `XCTest` async expectations for parameter parsing, edge inputs, and expected error shapes, and encode invariants in CI-run tests. Mark intent entry/exit and long I/O boundaries with `OSSignposter` so these signposts correlate with Instruments traces. Emit structured events with `os_log` including correlation IDs at intent start and end.

Use Instruments during internal rollouts to surface latency or memory regressions and platform-level diagnostics for post-release crash and performance signals. Gate verbose logging behind a feature flag to avoid production excess, and consider returning a correlation ID in the intent result when appropriate so support engineers can stitch client traces to backend logs.

- Use `XCTest` to assert parameter round-trips and migration behavior.
- Use `OSSignposter` to mark boundaries and correlate with Instruments.
- Include correlation IDs in all logs and return them when useful for debugging.

## Practical Checklist
- [ ] Define each `AppIntent` with explicit `@Parameter` types and localized labels.
- [ ] Add `XCTest` cases that validate parameter parsing, edge inputs, and error shapes.
- [ ] Instrument intent entry/exit with `OSSignposter` and write `os_log` structured events with correlation IDs.
- [ ] Gate identifier or parameter changes with feature flags and staged releases.
- [ ] Implement clear localized error messages and user recovery steps for permission or data errors.
- [ ] Provide migration shims for legacy identifiers and document breaking changes in release notes.
- [ ] Return explicit synchronous results when work is deferred and expose a follow-up intent to check completion.

## Closing Takeaway
Make `AppIntent` contracts typed, keep the `perform()` entry point short-running, and instrument intents so invocations are traceable. Offload work that cannot finish synchronously, preserve legacy shapes during migration, and stage breaking changes behind feature flags. These practices turn Shortcuts rollouts from opaque incidents into controlled, diagnosable releases.

## Swift/SwiftUI Code Example

```swift
import Foundation
import AppIntents
import Observation
import os

@MainActor @Observable final class ShortcutInvocationLog {
    var entries: [String] = []
    func record(_ entry: String) {
        entries.append("\(Date()): \(entry)")
    }
}

let SharedShortcutLogger = ShortcutInvocationLog()
let signposter = OSSignposter()
let logger = Logger(subsystem: "com.example.shortcuts", category: "AppIntent")

struct SubmitReportIntent: AppIntent {
    static var title: LocalizedStringResource = "Submit Report"

    @Parameter(title: "Report date") var date: Date
    @Parameter(title: "Summary") var summary: String

    static var parameterSummary: some ParameterSummary {
        Summary("Submit a summary for the specified date")
    }

    func perform() async throws -> some IntentResult {
        let signpostID = signposter.makeSignpostID()
        signposter.beginInterval("SubmitReport", id: signpostID)
        logger.log("Shortcut invoked: SubmitReport (date: \(date), summary: \(summary))")

        await MainActor.run {
            SharedShortcutLogger.record("Invoked SubmitReport — date:\(date), summary:\(summary)")
        }

        try await Task.sleep(nanoseconds: 50_000_000) // 50ms

        signposter.endInterval("SubmitReport", id: signpostID)
        return .result()
    }
}
```

## References

- [AppIntent](https://developer.apple.com/documentation/appintents/appintent)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
