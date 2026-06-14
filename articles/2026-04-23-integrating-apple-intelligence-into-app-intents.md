# Integrating Apple Intelligence into App Intents

Converting loosely typed intent inputs to `AppIntent` often reveals issues only after broad usage: shortcuts run unexpectedly, background work spikes, and support tickets surface classification problems. Treat intent integration as a migration with observable gates, deterministic tests, and typed parameters that reduce ambiguous routing. The guidance that follows frames engineering choices—typing, telemetry, testing, and rollout—to keep regressions out of customers' hands.

## 1. Why This Matters For iOS Teams

System-driven suggestion and routing can dramatically increase how often your app’s actions are discovered and invoked. That increased surface makes misclassification an operational concern as well as an API change. When a migration exposes a catch-all `String` slot to the system parser, the system may supply inputs you did not test, and your app can receive unexpected or sensitive inputs.

Treat `AppIntent` integration as a product migration: reduce ambiguity with typed parameters, instrument parsing and execution signals, and gate rollout so you can observe and adjust without a large-scale incident. Maintain `INIntent` fallbacks during the transition to avoid breaking existing shortcuts for users on older OS versions.

App Intents is also the surface Apple Intelligence and Siri use to discover and run your actions. For assistant-driven behaviors specifically, App Intents layers on assistant schemas — the `@AssistantIntent(schema:)` macro and the `AssistantSchema` domains — that map your intents onto categories the system understands. The typing, telemetry, and rollout discipline in this article is the prerequisite for adopting those schemas safely; this piece focuses on getting that foundation right rather than on any single schema.

> Replace ambiguous free-form slots with typed parameters early; your telemetry will thank you.

## 2. App Intent Export Surface And Fallbacks

### Export Surface And When To Use Catch-All Versus Dedicated Types
`AppIntent` types influence how the system indexes and suggests actions, and the `@Parameter` shapes coercion. Choose a single catch-all `AppIntent` when you control upstream prompts and need polymorphism; choose small, dedicated `AppIntent` types when you need predictable parsing and lower operational risk. Choose `String` with validation when you truly need arbitrary user prose; choose typed parameters such as `Int`, `Date`, `URL`, or enums when your domain has structured identifiers or finite choices. (`@Parameter` does not support `UUID` directly — wrap it in an `AppEntity` if you need one.)

Map each `INIntent` to a corresponding `AppIntent` with explicit metadata and localized titles to control discoverability. Keep legacy `INIntent` handlers available during the transition and use a server-side feature flag to route a control cohort to legacy behavior without shipping a client rollback.

## 3. Parameter Design And Prompt Strategy

### Typed Parameters, Validation, And Prompt Titles
Prefer `Int`, `Date`, `URL`, and enums over free-form `String` where the domain allows. Annotate parameters with `@Parameter` and localized titles to keep system prompts predictable and reduce follow-up disambiguation. Validate coercion paths during CI and add guard clauses to fail fast when inputs cannot be coerced.

Example minimal intent:
```swift
import AppIntents

struct SendReportIntent: AppIntent {
  static var title: LocalizedStringResource = "Send Report"
  // @Parameter supports Int/String/Bool/Double/Date/URL/AppEnum/AppEntity — not
  // UUID. Use Int (or wrap the UUID in an AppEntity) for a typed identifier.
  @Parameter(title: "Report ID") var reportID: Int
  func perform() async throws -> some IntentResult { .result() }
}
```

Run unit tests that assert valid and invalid coercions, and add redaction rules for any parameter that may surface sensitive content. Test prompt paraphrases and system reformulations; prepare to roll back schema changes if rephrasing increases follow-up dialogs or false positives.

## 4. Testing, Observability, And Instrumentation

### Signposts, Tests, And Aggregated Signals
Use `XCTest` for deterministic parsing and synthetic prompt tests, and use `OSSignposter` signposts to correlate work across processes and Instruments templates. Choose end-to-end synthetic tests when you need real-world routing behavior; choose unit-level coercion tests when you need fast feedback in CI. For runtime validation, assert parameter parsing in `XCTest` async expectations and include synthetic heavy-load scenarios in nightly performance runs.

Annotate intent execution start/end with `OSSignposter` signposting for `Instruments` correlation. Export aggregated signals to `MetricKit` and keep `os_log` entries structured and non-sensitive, logging error codes, intent identifiers, and durations only. Ensure signpost IDs and `MetricKit` payloads exclude raw user content and use hashed identifiers where necessary. If parse latency or classification error rates exceed thresholds, automatically reduce rollout percentage or flip the server-side feature flag.

## 5. Rollout Strategy And Backward Compatibility

### Gate, Observe, And When To Revert
Gate wide releases with percentage rollouts or server-side feature flags and map feature gates to automated rollback triggers. Choose an immediate full cutover only when you have exhaustive `XCTest`, synthetic tests, strong observability, and a tested rollback path; choose staged percentage rollout when you need to observe real prompts across OS versions. Maintain `INIntent` fallbacks for a transition window and publish migration notes that explain expected routing changes.

Validate cancellation and timeout handling before expanding the rollout to avoid leaked CPU or battery during background work. Prepare a server-side toggle that can return control-group behavior to legacy code paths without requiring a client release.

## 6. Tradeoffs And Pitfalls

### Common Mistakes And How To Avoid Them
Declarative `AppIntent` exposure increases surface area for discovery but can also widen the chance of unintended activations. Tight parameter schemas reduce flexibility but lower false positives; permissive `String` slots increase ambiguity and support burden. Common pitfalls:
- Overly permissive `String` slots that cause ambiguous parsing and unexpected follow-ups.
- Missing `OSSignposter` or `MetricKit` signals that prevent attributing latency to parsing, app execution, or backend services.
- Removing `INIntent` handlers too early and breaking existing shortcuts for users on older OS versions.
Treat any free-text parameter as a privacy surface requiring review: redaction, hashing, and an updated telemetry policy.

## 7. Validation & Observability

### Concrete Signals, Tools, And Thresholds
Combine offline tests, runtime signposts, and post-release aggregation:
- Use `XCTest` async expectations to assert parsing edge cases and follow-up dialogues.
- Annotate intent execution start/end with `OSSignposter` and correlate in `Instruments`.
- Run `Instruments` templates (Time Profiler, Allocations) against synthetic load to surface tail latency and memory behaviors.
- Export aggregated signals to `MetricKit` for post-release crash and performance trends.
- Keep `os_log` structured and non-sensitive; log error codes, intent identifiers, and durations only.

Map alerts to actionable thresholds such as classification error rate or parse latency percentiles. For cross-process attribution, use fine-grained signposting and correlate logs with hashed identifiers. Where trends indicate regressions, adjust rollout percentages or revert to legacy `INIntent` behavior via server-side controls.

## 8. Practical Checklist

- [ ] Inventory `INIntent` handlers and map them to `AppIntent` equivalents with explicit parameter schemas.
- [ ] Replace ambiguous `String` slots with typed `@Parameter` fields where possible.
- [ ] Add `XCTest` coverage for parsing paths and synthetic prompt variations.
- [ ] Annotate intent execution start/end with `OSSignposter` and correlate in `Instruments`.
- [ ] Export aggregated signals to `MetricKit` and keep `os_log` entries non-sensitive.
- [ ] Gate `AppIntent` exposure with feature flags or percentage rollouts and verify automated rollback paths.
- [ ] Maintain `INIntent` fallbacks during migration and publish clear migration notes.
- [ ] Add redaction and hashing rules for any telemetry that could contain user content.

## 9. Closing Takeaway

Integrating system-driven suggestion and routing via `AppIntent` is an operational migration as much as an API change. Replace ambiguous `String` slots with typed `@Parameter` fields where possible, add deterministic `XCTest` coverage and `OSSignposter` signposting, and gate rollout so you can observe and revert without a crisis. These steps turn surprises from system-driven inputs into manageable engineering work.

## Swift/SwiftUI Code Example

```swift
import AppIntents
import Observation
import os

// An enum used as an @Parameter must conform to AppEnum, not just Codable/Sendable.
enum SearchScope: String, AppEnum {
    case all, messages, files

    static var typeDisplayRepresentation: TypeDisplayRepresentation { "Search Scope" }
    static var caseDisplayRepresentations: [SearchScope: DisplayRepresentation] {
        [.all: "All", .messages: "Messages", .files: "Files"]
    }

    static func parse(_ raw: String) -> SearchScope? {
        let normalized = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return Self(rawValue: normalized) ?? (normalized.contains("msg") ? .messages : nil)
    }
}

// An actor counter is reachable from the nonisolated intent context and from a
// static initializer; mutate isolated state through methods, since you cannot do
// `await x.prop += 1` across the actor boundary.
actor IntentTelemetry {
    private(set) var parseFailures = 0
    private(set) var executions = 0
    func recordExecution() { executions += 1 }
    func recordParseFailure() { parseFailures += 1 }
}

struct SearchIntent: AppIntent {
    static var title: LocalizedStringResource { "Search" }
    @Parameter(title: "Scope") var scope: SearchScope?
    static var parameterSummary: some ParameterSummary { Summary("Search in \(\.$scope)") }

    private let logger = Logger(subsystem: "com.example.app", category: "intents")
    static let telemetry = IntentTelemetry()

    func perform() async throws -> some IntentResult {
        await Self.telemetry.recordExecution()
        guard rolloutGateEnabled() else {
            logger.log("Intent blocked by rollout gate")
            return .result()
        }
        let finalScope = scope ?? parseFallbackFromContext()
        guard let scope = finalScope else {
            await Self.telemetry.recordParseFailure()
            logger.warning("Failed to parse scope")
            return .result()
        }
        logger.log("Executing search in \(scope.rawValue)")
        return .result()
    }

    private func parseFallbackFromContext() -> SearchScope? {
        let rawInput = ExternalIntentContext.shared.sharedLooseInput
        return SearchScope.parse(rawInput)
    }

    private func rolloutGateEnabled() -> Bool {
        return RemoteConfig.shared.bool(forKey: "intents.search.enabled", defaultValue: true)
    }
}

// Minimal stubs
final class RemoteConfig {
    static let shared = RemoteConfig()
    func bool(forKey: String, defaultValue: Bool) -> Bool { defaultValue }
}
final class ExternalIntentContext { static let shared = ExternalIntentContext(); var sharedLooseInput: String = "" }
```

## References

- [iOS 26.4.2 (23E261)](https://developer.apple.com/news/releases/?id=04222026a)
- [iPadOS 26.4.2 (23E261)](https://developer.apple.com/news/releases/?id=04222026b)
- [iOS 18.7.8 (22H352)](https://developer.apple.com/news/releases/?id=04222026c)
- [Hello Developer: April 2026](https://developer.apple.com/news/?id=e1ssia6m)
- [How Infold Games fashioned an open world for Infinity Nikki](https://developer.apple.com/news/?id=9mgkwjnm)
- [Q&amp;A: How Plane Finder set itself up for the long haul](https://developer.apple.com/news/?id=cmd9p4g7)
- [AppIntent](https://developer.apple.com/documentation/appintents/appintent)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
