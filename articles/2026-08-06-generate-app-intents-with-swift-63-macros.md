# Generate App Intents with Swift 6.3 Macros

Builds quietly pass on your laptop, then your intents extension misses a release because a macro target fails on CI. Or worse, a generated member hides an entitlement or lifecycle issue and your intent execution fails with little signal. The cost isn’t theory — it’s a broken discovery surface, flatlined Shortcuts usage, and a missed train.

Swift macros let us generate the boring parts of AppIntent and AppEntity without handing control of behavior to codegen. The key is drawing a non-negotiable boundary: generate the shape and metadata; keep side effects explicit and testable.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams
AppIntent drives Siri, Shortcuts, and Spotlight. When teams skip intents or ship them inconsistently, they reduce the discovery they already earned with features. It’s common to see identical functionality ship with and without intents across targets; users engage the former and forget the latter.

Macros participate directly in your build. That’s powerful and brittle. Mis-scoped generation can create ambiguous members and CI-only failures. Thoughtful generation of the repetitive 80% (titles, summaries, display) reduces drift and improves localization coverage across modules — but only if you keep business logic human-written.

> Generate the metadata and shape, never the side effects — you want a generator, not a ghostwriter.

## 1. Map The Surface Area: What To Generate And What To Keep Hand-Written
### What To Generate
Generate static AppIntent and AppEntity metadata: title, description, parameterSummary, and DisplayRepresentation. Generate glue for @Parameter names and summaries. Do not generate perform() or identity.

```swift
import AppIntents

struct AddTaskIntent: AppIntent {
  static var title: LocalizedStringResource { "Add Task" }
  static var description: IntentDescription { IntentDescription("Create a new task.") }

  @Parameter(title: "Title")
  var titleParam: String

  @Parameter(title: "Due Date")
  var dueDate: Date?

  static var parameterSummary: some ParameterSummary {
    Summary("Add \(\.$titleParam) due \(\.$dueDate)")
  }

  func perform() async throws -> some IntentResult {
    // Keep side effects explicit and testable.
    try await TaskService.shared.create(title: titleParam, due: dueDate)
    return .result()
  }
}
```

### Anti-Pattern To Preferred Pattern
- Anti-pattern: Copy-pasting title and parameterSummary across dozens of intents, forgetting localizations and causing drift.
- Preferred: Macros generate consistent metadata while engineers hand-write perform() with tests.

### Operational Note
A generated perform() often “works until it doesn’t” in extension contexts. Keep perform() explicit so entitlement, capability, and `@MainActor` crossings remain visible in code review and incident response.

## 2. Attached Macros For Intent Types
### Synthesis: Where It Fits
Use attached macros to synthesize metadata when your shapes are uniform. When every intent in a group follows the same pattern, use synthesis. If a type needs specialized wording, availability, or gating, write manual members.

```swift
import Foundation
import AppIntents

actor ProjectService {
    static let shared = ProjectService()
    func archive(id: String) async throws {}
}

struct ArchiveProjectIntent: AppIntent {
    static var title: LocalizedStringResource = "Archive Project"

    @Parameter(title: "Project ID")
    var projectID: String

    init() {}

    func perform() async throws -> some IntentResult {
        try await ProjectService.shared.archive(id: projectID)
        return .result()
    }
}```

### Before → After Contrast
- Before: Each intent manually repeats identical metadata.
- After: The macro generates title, description, and parameterSummary; you maintain perform() and any availability gates.

### Operational Note
Conflicts between synthesized and manual members can produce compile-time errors. If one intent needs custom title or parameterSummary, give it an explicit opt-out your macro recognizes and skips. Keep synthesized and manual members clearly separated to simplify diffs and lints.

## 3. Entities, Queries, And Identity
### Stable Identity And Representation
Treat AppEntity identity as schema. Shortcuts and related systems may cache identifiers; the wrong id can yield stale rows and confusing resolution. Generate DisplayRepresentation when fields are consistent, but keep id and fetch paths manual.

```swift
import AppIntents
import Foundation

struct ProjectEntity: AppEntity {
  typealias ID = String

  static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Project")
  static var defaultQuery = ProjectQuery()

  var id: ID
  var name: String
  var colorHex: String

  var displayRepresentation: DisplayRepresentation {
    DisplayRepresentation(
      title: "\(name)",
      subtitle: "ID \(id)",
      image: .init(systemName: "folder.fill")
    )
  }
}

struct ProjectQuery: AppIntents.EntityQuery {
  typealias Entity = ProjectEntity

  func entities(for identifiers: [ProjectEntity.ID]) async throws -> [ProjectEntity] {
    await ProjectService.shared.fetch(ids: identifiers).map {
      ProjectEntity(id: $0.id, name: $0.name, colorHex: $0.color)
    }
  }

  func suggestedEntities() async throws -> [ProjectEntity] {
    await ProjectService.shared.recents(limit: 10).map {
      ProjectEntity(id: $0.id, name: $0.name, colorHex: $0.color)
    }
  }
}

actor ProjectService {
  static let shared = ProjectService()

  struct Record { let id: String; let name: String; let color: String }

  func fetch(ids: [String]) async -> [Record] {
    ids.map { Record(id: $0, name: "Project \($0)", color: "#FF9500") }
  }

  func recents(limit: Int) async -> [Record] {
    (1...limit).map { Record(id: "\($0)", name: "Project \($0)", color: "#34C759") }
  }
}```

### Choose Generation When…
- Titles, descriptions, and display formatting are uniform across a family of entities.

Choose manual wiring when…
- A feature uses composite keys or a distinct backing store, or when migration is in flight.

### Operational Note
Changing display assets can leave older visuals in some UI surfaces until caches refresh. Announce the change internally, bump any capability or schema marker you maintain, and verify cards after release.

## 4. Designing The Macro: Boundaries, Opt-Outs, And Tests
### A Minimal Attached Macro Shape
Define a single annotation that synthesizes metadata and respects per-type opt-outs. Keep behavior members off-limits.

```swift
import AppIntents
import Foundation

struct DeleteAccountIntent: AppIntent {
  static var title: LocalizedStringResource = "Delete Account"

  @Parameter(title: "Confirmation Code")
  var code: String

  static var parameterSummary: some ParameterSummary { Summary("Delete account") }

  func perform() async throws -> some IntentResult {
    try await AccountService.shared.delete(code: code)
    return .result()
  }
}

actor AccountService {
  static let shared = AccountService()
  func delete(code: String) async throws { _ = code }
}```

### Before → After Contrast
- Before: Ad-hoc extensions re-declare title or description, creating subtle collisions.
- After: One macro owns metadata; explicit annotations tell it when to skip.

### Operational Note
Build your macro plugin with the same toolchain your release lane uses. Keep a fallback path until you’ve shipped stable releases with the macro in place.

## 5. Migration And Rollout Strategy
### Gate And Gradually Roll
Gate generation behind a compile-time flag and keep a manual path for your highest-usage intents during rollout.

```swift
#if USE_INTENT_MACROS
@IntentMetadata
struct CreateNoteIntent: AppIntent {
  // generated metadata + manual perform
  @Parameter(title: "Title") var title: String
  func perform() async throws -> some IntentResult {
    try await Notes.shared.create(title: title)
    return .result()
  }
}
#else
// Manual fallback
struct CreateNoteIntent: AppIntent {
  static var title: LocalizedStringResource { "Create Note" }
  static var description: IntentDescription { IntentDescription("Create a new note.") }
  @Parameter(title: "Title") var title: String
  static var parameterSummary: some ParameterSummary { Summary("Create \(\.$title)") }
  func perform() async throws -> some IntentResult {
    try await Notes.shared.create(title: title)
    return .result()
  }
}
#endif
```

### Choose Phased Rollout When…
- CI/build farms are in transition or you have multiple intent extensions across targets.

Choose immediate adoption when…
- You own the full toolchain version and can revert quickly.

### Operational Note
Monitor extension stability after enabling macros. If the macro path fails in a lane, your fallback ensures registration still happens, and your Shortcuts don’t disappear for a subset of users.

## Tradeoffs And Pitfalls
Generating metadata accelerates coverage and localization, but narrows escape hatches. When a few intents need bespoke parameterSummary formatting, the generator may fight you; prioritize explicit overrides with deterministic opt-outs.

Ownership blurs when “the macro did it.” On-call debugging slows if engineers can’t tell where a member came from. Keep a single source of truth per intent and add a lint to flag shadowed synthesized members.

Conflicts during refactors can arise if manual extensions re-declare synthesized properties. Avoid this by agreeing on which source owns each member and keeping them separate.

AppEntity identity changes do not always fail loudly. Treat them like schema migrations: design a compatibility map, plan cache invalidation behavior, and stage the rollout.

## Validation And Observability
Encode the contract with tests and runtime signals so failures are obvious and attributable.

- XCTest fixtures should instantiate generated AppIntent/AppEntity, exercise parameterSummary, and round-trip parameters without crashing.

- Use signposts around perform() and EntityQuery to measure intent latency and surface N+1 fetches in Instruments.
- Feed crash diagnostics into dashboards and gate releases when the extension crash rate spikes.
- Prefer structured logs; include parameter counts and high-level error categories, but avoid logging raw identifiers. Redact or hash when needed.
- Add a UI test that invokes a minimal intent to ensure the extension binary loads and registers on device and simulator. This catches flakiness that unit tests miss.
- Keep a smoke test lane that builds the macro plugin and a control lane without it. Divergence here is a release risk signal.

## Practical Checklist
- [ ] Inventory AppIntent and AppEntity types; mark which metadata is safe to generate and which identities/queries stay manual.
- [ ] Create attached macros that synthesize title, description, parameterSummary, and DisplayRepresentation, with an explicit opt-out.
- [ ] Wrap macro usage behind a compile-time flag and keep manual fallbacks for your top intents during rollout.
- [ ] Add XCTest fixtures that instantiate generated intents, assert summaries, and verify DisplayRepresentation.
- [ ] Instrument perform() and queries with signposts; record latency baselines before rollout.
- [ ] Run CI lanes on the upgraded toolchain for macro compilation and keep a parallel lane on the prior toolchain until multiple stable releases pass.
- [ ] Stage the rollout; monitor crash diagnostics and logs for entitlement or registration regressions.

## Closing Takeaway
Swift macros are well-suited to generating the static 80% of AppIntent and AppEntity. Keep perform() and entity identity hand-written, readable, and covered by tests. Gate adoption, validate with fixtures, and roll out incrementally with observability in place. When something breaks — and something will — you want to know quickly, attribute it to either the macro or the hand-written code, and fix it in one commit without missing your train.

## Swift/SwiftUI Code Example

```swift
import AppIntents
import Foundation

actor TodoStore {
    static let shared = TodoStore()
    private var open: Set<String> = ["A1", "B2", "C3"]
    func complete(id: String) async throws {
        guard open.remove(id) != nil else { throw NSError(domain: "Todo", code: 1) }
    }
    func suggest(prefix: String?) async -> [Todo] {
        let ids = open.filter { p in prefix.map { p.hasPrefix($0) } ?? true }
        return ids.map { Todo(id: $0) }
    }
}

struct Todo: AppEntity, Identifiable, Hashable, Sendable {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "To‑Do")
    static var defaultQuery = Query()
    var id: String
    var displayRepresentation: DisplayRepresentation { .init(title: "\(id)") }
    struct Query: EntityQuery {
        func entities(for identifiers: [String]) async throws -> [Todo] { identifiers.map { .init(id: $0) } }
        func suggestedEntities() async throws -> [Todo] { await TodoStore.shared.suggest(prefix: nil) }
        func defaultResult() async -> Todo? { try? await suggestedEntities().first }
    }
}

struct CompleteTodoIntent: AppIntent {
    static var title: LocalizedStringResource = "Complete To‑Do"
    static var description = IntentDescription("Marks a to‑do as complete.")
    @Parameter(title: "To‑Do") var todo: Todo
    static var parameterSummary: some ParameterSummary { Summary("Complete \(\.$todo)") }
    func perform() async throws -> some IntentResult {
        try await TodoStore.shared.complete(id: todo.id)
        return .result()
    }
}
```

## References

- [What's new in Swift: June 2026 Edition](https://swift.org/blog/whats-new-in-swift-june-2026/)
- [@MainActor in Swift explained with code examples](https://www.avanderlee.com/swift/mainactor-dispatch-main-thread/)
- [AppIntent](https://developer.apple.com/documentation/appintents/appintent)
- [Swift Macros](https://developer.apple.com/documentation/swift/macros)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
