# Debugging App Intents Responses in Xcode

Shortcuts shows the wrong dialog, your `AppEntity` renders a blank icon, and logs insist everything is fine. The bug isn’t in your copy—it’s in which process you’re debugging and the timing of parameter resolution. When `@Parameter` defaults, `EntityQuery`, and `perform()` don’t agree, your response text can drift across Shortcuts, Siri, and Spotlight.

> If Shortcuts shows one thing and your logs say another, trust Shortcuts. Then instrument your intent until both line up.

*All code in this article targets watchOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters
App Intents drive system surfaces your users treat as truth: Shortcuts, Siri, Spotlight, and widgets. A string mismatch or missing icon in one of those contexts erodes trust quickly—and it often reproduces only on device. Background invocations have limited time and resources on cold start, especially when launched by a host process. `EntityQuery` resolution may time out or be cancelled under load during background launches when caches are cold or the device is under memory pressure. A run that looks perfect in Simulator with the app frontmost can fail when launched by the Shortcuts host in the background on device.

The highest-risk gap: testing your intent inside the app process, then shipping responses that actually execute in an extension host. Timing, I/O, and suspension behavior differ. To ship confidently, you need stable debugger attachment, lean structured logging, cache-first entity resolution, and a feedback loop that proves your actual dialog and visuals.

## 1. Attach The Debugger To The Right Process
### Use “Wait For Executable” And Trigger From Shortcuts
The anti-pattern is launching the app, sprinkling `print`, and invoking the intent from there. That path can miss the extension host entirely. Configure your Xcode scheme to “Wait for the executable to be launched,” run, then trigger the intent from Shortcuts. You’ll attach to the correct host at process spin-up.

When you’re validating lifecycle and timing, use attach-on-launch. If you already know the host process and need to swap targets during a run, attach manually.

Keep logs structured and light—background hosts can terminate under heavy I/O if you emit large payloads or very frequent logs. Prefer `Logger` with `.info` for start/stop and `.debug` around suspicious branches.

```swift
import AppIntents
import OSLog

private let log = Logger(subsystem: "com.example.myapp", category: "AppIntents")

struct AddTaskIntent: AppIntent {
  static var title: LocalizedStringResource = "Add Task"

  @Parameter(title: "Title") var title: String

  func perform() async throws -> some IntentResult {
    log.info("AddTaskIntent start title=\(self.title, privacy: .public)")
    // Do minimal, cancel-safe work here.
    log.debug("AddTaskIntent finishing")
    return .result(dialog: IntentDialog("Added “\(title)”."))
  }
}
```

Open Console.app filtering by your bundle identifier and category to verify you’re in the extension host before you reproduce. If logs stall or disappear during a background trigger, you likely attached to the app, not the host.

## 2. Prove Parameter And Entity State
### Lock Down `DisplayRepresentation` And Avoid Network In Resolution
When response text is assembled ad hoc inside `perform()`, surfaces drift. Define `displayRepresentation` on each `AppEntity` so titles, subtitles, and icons stay consistent across Shortcuts cards and Spotlight results.

Choose a non-optional `@Parameter` only if you can satisfy it without depending on network or long-latency queries. Optional parameters with sensible defaults are often safer than “required but resolved later” patterns that can collapse into empty dialogs when timing slips during background launches or connectivity is unreliable.

```swift
import AppIntents
import SwiftUI

struct Project: AppEntity {
  static var typeDisplayRepresentation =
    TypeDisplayRepresentation(name: "Project")

  static var defaultQuery = ProjectQuery()

  var id: String
  var name: String
  var color: Color

  var displayRepresentation: DisplayRepresentation {
    DisplayRepresentation(
      title: "\(name)",
      subtitle: "Project",
      image: .init(systemName: "folder.fill")
    )
  }
}

struct ProjectQuery: EntityQuery {
  func entities(for identifiers: [Project.ID]) async throws -> [Project] {
    // Return from cache; avoid blocking on network.
    identifiers.compactMap { Project(id: $0, name: "Inbox", color: .blue) }
  }

  func suggestedEntities() async throws -> [Project] {
    [Project(id: "inbox", name: "Inbox", color: .blue)]
  }
}
```

Test parameter resolution in three runs—Simulator, on-device foreground, and on-device background (triggered by Shortcuts with the app terminated). Differences here catch most “works on my phone” misses.

## 3. Build Responses That Match The Surface
### Prefer Dialogs And Snippets Over Opening The App
Defaulting to opening the app interrupts voice and automation flows and may behave differently on other platforms. Prefer returning `IntentResult.success()` with an `IntentDialog` for straightforward confirmations. Use a `SnippetView` for compact state—counts, progress, or a single item summary.

When the user only needs confirmation, use `IntentDialog`. If added context improves comprehension, use `SnippetView`. Open the app only when a foreground UI step is truly required.

```swift
import AppIntents
import SwiftUI

struct AddedTaskSnippet: View, SnippetView {
  let title: String
  let project: String

  var body: some View {
    HStack {
      Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
      VStack(alignment: .leading) {
        Text("Added “\(title)”")
        Text(project).font(.caption).foregroundStyle(.secondary)
      }
    }
    .padding(.vertical, 4)
  }
}

struct AddTaskIntent: AppIntent {
  static var title: LocalizedStringResource = "Add Task"

  @Parameter(title: "Title") var title: String
  @Parameter(title: "Project") var project: String

  func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
    .result(
      dialog: IntentDialog("Added “\(title)” to \(project)."),
      view: AddedTaskSnippet(title: title, project: project)
    )
  }

  static var openAppWhenRun: Bool { false }

  static var parameterSummary: some ParameterSummary {
    Summary("Add \(\.$title) to \(\.$project)")
  }
}```

Keep snippet construction cheap. Aim for minimal work and avoid blocking I/O before you create the result. Snippet `body` must be pure; initiating work there can stall the host.

## 4. Instrument The Hot Path Without Blowing Your Budget
### Use `OSSignposter` To Bound Time And Reduce Guessing
Instead of verbose logging in hot loops, mark phases with `OSSignposter`. You get precise spans in Instruments’ Points of Interest without flooding I/O.

When you need timing truth, use signposts. If you only need sparse shape and IDs, use logs. Combining both—a signpost per phase plus a single `Logger.info` for run boundaries—sharpens triage on background launches and helps spot cold-start issues.

```swift
import OSLog

private let signposter = OSSignposter(subsystem: "com.example.myapp", category: "AppIntents")

func runIntentWork(title: String) async {
  let state = signposter.beginInterval("AddTask.perform", id: .exclusive)
  defer { signposter.endInterval("AddTask.perform", state) }

  let resolve = signposter.beginInterval("Resolve Parameters", id: .exclusive)
  // Resolve parameters/entities...
  signposter.endInterval("Resolve Parameters", resolve)

  let work = signposter.beginInterval("Persist Task", id: .exclusive)
  // Persist task...
  signposter.endInterval("Persist Task", work)

  let assemble = signposter.beginInterval("Assemble Response", id: .exclusive)
  // Build dialog/snippet...
  signposter.endInterval("Assemble Response", assemble)
}
```

Gate extra signposts and debug logs behind a runtime flag read from an app group container so you can enable field diagnostics selectively without rebuilding.

## 5. Assert The Contract Of `perform()`
### Treat The Intent Like A Boundary You Can Test
`perform()` is business logic with a user-facing contract. Write tests that construct the intent, set parameters, await `perform()`, and assert dialog contents and result shape. Even a text-contains check helps prevent accidental drift.

When you own the result types, use white-box accessors. If you need light coupling, use description-based assertions.

```swift
import Foundation
import XCTest

enum Color { case blue }

struct Project: Equatable {
  var id: String
  var name: String
  var color: Color
}

struct AddTaskResult: CustomStringConvertible {
  let dialog: String
  let snippet: String
  var description: String { "\(dialog) — \(snippet)" }
}

struct AddTaskIntent {
  var title: String?
  var project: Project?
  func perform() async throws -> AddTaskResult {
    let t = title ?? ""
    let p = project?.name ?? ""
    return AddTaskResult(dialog: "Added task: \(t)", snippet: "Project: \(p)")
  }
}

final class AddTaskIntentTests: XCTestCase {
  func testPerformProducesDialogAndSnippet() async throws {
    var intent = AddTaskIntent()
    intent.title = "Buy milk"
    intent.project = Project(id: "inbox", name: "Inbox", color: .blue)

    let result = try await intent.perform()
    let description = String(describing: result)

    XCTAssertTrue(description.contains("Buy milk"))
    XCTAssertTrue(description.contains("Inbox"))
  }
}```

After you have a passing test and a reproducible case with the debugger attached, re-run on device with the debugger detached. Background scheduling can expose races that disappear under debug.

## Tradeoffs And Pitfalls
- `SnippetView` improves comprehension but adds maintenance across iPhone, iPad, and watchOS. Validate Dynamic Type and contrast; small screens can truncate captions unexpectedly.
- Attaching a debugger changes timing. Expect slower cold starts under debug, and verify behavior again with the debugger detached.
- Network-bound `EntityQuery` resolution may exceed background budgets on poor connectivity. Prefer cached IDs and refine later out of band.
- Excessive structured logs in background can create I/O back-pressure. Even modest bursts can push a cold start over background time limits.
- Building response strings in `perform()` without `displayRepresentation` invites cross-surface drift. Centralize representation in the entity.

## Validation And Observability
- Write `XCTest` async expectations that cover success, missing parameters, and fallback dialogs. Encode the user-visible contract so refactors can’t silently change it.
- Use Instruments’ Points of Interest with `OSSignposter` to verify `resolve → work → assemble` stays within a reasonable envelope on device. Correlate spans with allocations to catch accidental work inside `SnippetView`.
- Profile with Time Profiler to confirm you aren’t doing network I/O or heavy parsing in parameter resolution. If you need remote state, hydrate a cache beforehand during app foreground time.
- Adopt `Logger(subsystem: "<bundle-id>", category: "AppIntents")` and include key identifiers (for example, intent IDs and context) so you can slice anomalies quickly.
- Consider monitoring system diagnostics (for example, crash and hang reports) that implicate Shortcuts or Siri hosts. Spikes can correlate with heavy logging or slow entity queries.
- Roll out behind a runtime switch: start with simple `IntentDialog`, then enable `SnippetView` via remote config once telemetry is clean.

## Practical Checklist
- [ ] Configure the scheme to “Wait for the executable to be launched” and trigger the intent from Shortcuts on device.
- [ ] Use `Logger(subsystem: "<bundle-id>", category: "AppIntents")` for start/stop and critical branches; avoid large payloads.
- [ ] Define `displayRepresentation` on every `AppEntity`; verify titles, subtitles, and icons in Shortcuts and Spotlight.
- [ ] Keep `EntityQuery` cache-backed and fast; avoid blocking on network during resolution.
- [ ] Prefer `IntentDialog` and `SnippetView`; open the app only when a foreground step is mandatory.
- [ ] Mark `resolve`, core work, and `assemble` with `OSSignposter`, and validate in Instruments.
- [ ] Write tests that call `perform()` directly and assert on dialog text and result shape.
- [ ] Reproduce on device with the debugger detached to expose scheduling-sensitive bugs.
- [ ] Gate verbose logs and signposts behind a runtime flag; ship with minimal diagnostics enabled.

## Closing Takeaway
Treat App Intents as first-class product surfaces, not just plumbing for Shortcuts. Attach the debugger to the correct host, keep logs structured and lean, and centralize display via `displayRepresentation`. Build responses that stand alone—dialogs and snippets—so background flows stay uninterrupted. Prove the contract of `perform()` with tests and timelines, then watch your telemetry. When Shortcuts, Siri, and Spotlight all present the same text and visuals, users stop noticing the machinery and start trusting your app.

## Swift/SwiftUI Code Example

```swift
import Foundation
import AppIntents
import OSLog

struct MyItem: AppEntity, Identifiable, Hashable, Codable {
    static var typeDisplayRepresentation: TypeDisplayRepresentation = .init(name: "Item")
    static var defaultQuery = MyItemQuery()
    let id: UUID
    let name: String
    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: LocalizedStringResource(stringLiteral: name))
    }
}

struct MyItemQuery: EntityQuery {
    static let log = Logger(subsystem: "com.example.intents", category: "EntityQuery")
    static let signposter = OSSignposter(subsystem: "com.example.intents", category: "EntityQuery")

    func suggestedEntities() async throws -> [MyItem] {
        let interval = Self.signposter.beginInterval("suggestedEntities")
        defer { Self.signposter.endInterval("suggestedEntities", interval) }
        Self.log.info("Host: \(ProcessInfo.processInfo.processName, privacy: .public) suggesting defaults")
        return [MyItem(id: UUID(), name: "Fallback")]
    }

    func entities(for identifiers: [UUID]) async throws -> [MyItem] {
        let interval = Self.signposter.beginInterval("entities(for:)")
        defer { Self.signposter.endInterval("entities(for:)", interval) }
        Self.log.info("Resolving \(identifiers.count) identifiers")
        return identifiers.map { MyItem(id: $0, name: "Item-\($0.uuidString.prefix(4))") }
    }
}

struct ShowItemIntent: AppIntent {
    static var title: LocalizedStringResource = "Show Item"
    static var description = IntentDescription("Demonstrates aligning Shortcuts UI with logs using host-aware instrumentation.")

    @Parameter(title: "Item")
    var item: MyItem?

    static let log = Logger(subsystem: "com.example.intents", category: "Perform")
    static let signposter = OSSignposter(subsystem: "com.example.intents", category: "Perform")

    func perform() async throws -> some IntentResult {
        let host = ProcessInfo.processInfo.processName
        let interval = Self.signposter.beginInterval("perform")
        defer { Self.signposter.endInterval("perform", interval) }

        Self.log.info("Host: \(host, privacy: .public) — raw @Parameter: \(self.item?.name ?? "nil", privacy: .public)")

        let resolved: MyItem = try await {
            if let chosen = item { return chosen }
            let suggested = try await MyItemQuery().suggestedEntities()
            return suggested.first ?? MyItem(id: UUID(), name: "Generated")
        }()

        Self.log.info("Resolved item: \(resolved.name, privacy: .public)")
        return .result(dialog: "Host: \(host). Showing \(resolved.name).")
    }
}
```

## References

- [Xcode 26.6 RC 2 (17F113)](https://developer.apple.com/news/releases/?id=06182026a)
- [AppIntent](https://developer.apple.com/documentation/appintents/appintent)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
