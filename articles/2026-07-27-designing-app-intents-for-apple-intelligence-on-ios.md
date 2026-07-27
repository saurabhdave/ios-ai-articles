# Designing App Intents for Apple Intelligence on iOS

When Siri or system search calls into your app and nothing happens, the issue is rarely in UI code—it’s in the contracts you didn’t define. Teams ship features that users can’t discover because there’s no `AppIntent`, or they crash when run without UI because `perform()` touches UI-only singletons. These problems often appear after rollout when the system invokes your code in the background.

> Treat `AppIntent` as a public API that executes without your UI, on an unpredictable schedule, across a wide device range.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams
App Intents are an entry point for discovery and voice/automation flows. If you don’t model the jobs your app performs, the system has little to call or match. Features can remain effectively invisible without a `DisplayRepresentation`, or cause unnecessary clarifying questions when untyped `String` parameters force follow-ups.

Poorly scoped intents can also create privacy review friction for overbroad parameters and lead to terminations when background execution touches UI-only globals. Manual tests tend to exercise screens, not headless runs, so these issues slip through QA. Renaming a `@Parameter` or changing an `AppEntity` identifier after release can break saved shortcuts, creating support churn. Design this surface deliberately.

## 1. Map Jobs-To-Be-Done Into App Intents
### From Buckets To Atomic Goals
A common anti-pattern is a single “do-everything” `AppIntent` with optional parameters for many side effects. This can make matching and confirmations less clear. Prefer one intent per focused user goal: “Add Task,” “Start Timer,” “Share Note.” Each intent should own explicit parameters and a clear `DisplayRepresentation`.

```swift
import AppIntents

struct AddTaskIntent: AppIntent {
    static var title: LocalizedStringResource = "Add Task"
    static var description = IntentDescription("Create a new task in a specified list.")

    @Parameter(title: "Title")
    var taskTitle: String

    @Parameter(title: "List", default: nil)
    var list: TaskListEntity?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let created = try await TaskService.shared.createTask(title: taskTitle, listID: list?.id)
        return .result(dialog: "Added “\(created.title)”")
    }
}

struct TaskShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AddTaskIntent(),
            phrases: ["Add a task in \(.applicationName)"],
            shortTitle: "Add Task",
            systemImageName: "plus.circle"
        )
    }
}
```

When user goals are distinct, create multiple small intents. When the outcome is the same and parameters only scope it, use a single intent with parameters. Missing `ProvidesDialog` or vague confirmations can lead to awkward flows—write dialogs like status banners: short, past tense, with the key noun.

Operationally, keep `AppShortcutsProvider` titles and phrases stable. Avoid volatile dynamic strings; unstable metadata can make matching less consistent over time.

## 2. Model Domain With Entities And Queries
### Typed Entities Beat Free-Form Strings
Using `String` for values like “list” or “project” often pushes disambiguation to users and limits system assistance. Implement `AppEntity` and an `EntityQuery` so the system can prefetch, resolve, and suggest efficiently.

```swift
import AppIntents

struct TaskListEntity: AppEntity, Identifiable, Hashable {
    typealias ID = String
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Task List")
    static var defaultQuery = Query()

    struct Query: EntityQuery {
        func entities(for identifiers: [TaskListEntity.ID]) async throws -> [TaskListEntity] {
            try await TaskListStore.shared.fetch(byIDs: identifiers)
        }
        func suggestedEntities() async throws -> [TaskListEntity] {
            try await TaskListStore.shared.fetchRecent(limit: 15)
        }
        func defaultResult() async -> TaskListEntity? {
            await TaskListStore.shared.mostUsed()
        }
    }

    var id: String
    var name: String
    var displayRepresentation: DisplayRepresentation { .init(title: "\(name)") }
}

actor TaskListStore {
    static let shared = TaskListStore()
    func fetch(byIDs ids: [String]) async throws -> [TaskListEntity] { [] }
    func fetchRecent(limit: Int) async throws -> [TaskListEntity] { [] }
    func mostUsed() async -> TaskListEntity? { nil }
}```

When values are reference-like and stable, define an `AppEntity`. When values are ephemeral or truly free-form (e.g., a quick memo), use scalar parameters. During suggestion and resolution, returning very large sets can increase memory and make disambiguation harder—keep `suggestedEntities()` small (for example, 10–20), ranked by recency or usage.

Operationally, make `EntityQuery` async and cancellable. Avoid blocking the main actor with storage or network fetches; respond to cancellation promptly to conserve resources.

## 3. Execution, Concurrency, And UI Boundaries
### Keep Intents Headless And Deterministic
`perform()` may run while your app is backgrounded or not running. Avoid singletons that assume a live UI scene. Isolate mutable state with `actor`s and keep sensitive storage and networking off the main actor unless UI is required.

```swift
import AppIntents
import OSLog

struct StartTimerIntent: AppIntent {
    static var title: LocalizedStringResource = "Start Timer"

    @Parameter(title: "Duration (minutes)")
    var minutes: Int

    private let signposter = OSSignposter(subsystem: "com.example.app", category: "Intents")

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let state = signposter.beginInterval("StartTimer.perform")
        defer { signposter.endInterval("StartTimer.perform", state) }

        let token = try await SecureTokenStore.shared.readAccessToken()
        let seconds = minutes * 60
        _ = try await TimerService.shared.startRemoteTimer(seconds: seconds, authToken: token)

        return .result(dialog: "Timer started for \(minutes) minutes.")
    }
}

actor SecureTokenStore {
    static let shared = SecureTokenStore()
    func readAccessToken() async throws -> String { "token" }
}

actor TimerService {
    static var shared = TimerService()
    func startRemoteTimer(seconds: Int, authToken: String) async throws -> String { "id" }
}
```

When you must bridge to UI (for example, presenting a live activity), mark only that code `@MainActor`. For headless handlers, avoid annotating the entire intent as `@MainActor`. Concurrency matters: a Siri request can overlap with a foreground operation. Actor isolation helps prevent data races and makes cancellation more predictable.

Operationally, validate timeouts and cancellation paths in tests. Long-running tasks that don’t respond to cancellation can keep work alive after the user has moved on.

## 4. Backward Compatibility And Rollout
### Dual-Path Carefully, Then Sunset
If you support older systems, maintain legacy shortcuts while introducing `AppIntents`. Teach the system the new names, ship behind a flag, and stage rollout via beta cohorts. Pitfall to avoid: renaming a `@Parameter` or changing an `AppEntity.id` after release—saved shortcuts may no longer resolve.

```swift
// Legacy — kept only while older systems justify the QA cost.
final class LegacyDonation {
    func donateAddTask(title: String) {
        // Represent a previous donation path to guide users; do not expand it.
        // Replace with your prior donation mechanism if still required by older OSes.
    }
}
```

When older-system usage justifies the maintenance cost, run a dual path. When adoption drops below your support threshold, remove the legacy code to reduce surface area. If you must change parameter names, keep deprecated aliases for at least one full release so existing shortcuts can continue to work during transition.

Operationally, treat rollout as a feature: use a configuration flag that lets you reduce query sizes or disable a problematic intent quickly if errors spike.

## 5. Shipping With Flags And Cohorts
### Feature Flags In The Intent Path
Introduce a thin guard so `perform()` can fail fast or reduce scope under incident response. This helps prevent cascading timeouts and unnecessary background work when dependencies are degraded.

```swift
import AppIntents

enum RemoteConfig {
    static func isIntentEnabled(_ name: String) -> Bool { true }
}

struct ShareNoteIntent: AppIntent {
    static var title: LocalizedStringResource = "Share Note"

    @Parameter(title: "Note")
    var note: NoteEntity

    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard RemoteConfig.isIntentEnabled("ShareNote") else {
            throw CancellationError()
        }
        // Normal sharing flow…
        return .result(dialog: "Shared “\(note.title)”")
    }
}
```

For instant rollback, use server-driven flags. For developer betas and TestFlight cohorts, local kill switches can be sufficient. Keep the guard at the top of `perform()` to avoid side effects when disabled.

Operationally, create cohorts for each new intent and monitor error rates and latency during ramp—not just UI crash-free metrics.

## Tradeoffs And Pitfalls
- Precision versus coverage: too many fine-grained intents increase maintenance and can make matching less clear. Start with a small set of core jobs and expand based on usage.
- Entity richness versus performance: detailed `DisplayRepresentation` (titles, subtitles, images) improves clarity but can add overhead when suggesting many entities. Prefer text-first, add images selectively for high-value suggestions.
- Caching versus staleness: aggressive caches in `EntityQuery` are snappy but can surface deleted or renamed items. Add TTLs and invalidate on write paths.
- Background execution versus user feedback: map backend failures to actionable dialogs. For example, turn authorization failures into guidance like “Please sign in again.”

## Validation And Observability
Mark async boundaries with `OSSignposter` so you can tie failures to intents in Instruments. Use system diagnostics to capture crashes and hangs for the intent path. Add structured `os_log` with categories per intent, and write `XCTest` that stubs `EntityQuery` and network to keep CI deterministic.

- Use Instruments Time Profiler to confirm `EntityQuery` work does not block the main actor.
- Monitor diagnostics grouped by hardware/OS to catch device-specific issues.
- Alert on intent-level latency and errors; couple alerts to feature flags to enable fast rollback.

## Practical Checklist
- [ ] Define 3–5 atomic user goals and implement one `AppIntent` per goal with explicit `@Parameter` types.
- [ ] Model `AppEntity` with stable `id`; write an async, cancellable `EntityQuery` capped to a small, useful suggestion set.
- [ ] Author `DisplayRepresentation` with unambiguous, stable titles and minimal phrasing; avoid volatile dynamic strings.
- [ ] Keep `perform()` headless: isolate mutable state with `actor`s; avoid `@MainActor` except for UI bridges.
- [ ] Add `OSSignposter` intervals around `perform()` and key async operations; use structured `os_log` categories.
- [ ] Write `XCTest` for happy path, invalid parameters, cancellation, and offline scenarios with stubbed services.
- [ ] Gate intents behind feature flags; stage via cohorts; monitor error rates and latency during ramp.
- [ ] Freeze parameter names and entity identifiers; if renaming, keep aliases for one release before removal.

## Closing Takeaway
Design `AppIntent` as a product surface, not glue code. Use typed `AppEntity` models and bounded, cancellable `EntityQuery` to make resolution fast and reliable. Keep handlers deterministic and headless, with actor isolation where state exists. Instrument the path end to end and roll out behind flags so you can react to real-world signals. A small, stable set of well-modeled intents will make your features more discoverable and trustworthy across voice, search, and system surfaces.

## Swift/SwiftUI Code Example

_A code example for this topic is not included in this edition._

## References

- [TestFlight Update](https://developer.apple.com/news/releases/?id=07212026a)
- [TestFlight 4.3](https://developer.apple.com/news/releases/?id=07212026b)
- [Xcode 27 beta 4 (27A5228h)](https://developer.apple.com/news/releases/?id=07202026m)
- [AppIntent](https://developer.apple.com/documentation/appintents/appintent)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
