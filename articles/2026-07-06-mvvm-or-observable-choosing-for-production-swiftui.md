# MVVM or Observable? Choosing for Production SwiftUI

A feed that jitters on device but “looks fine” in Simulator often isn’t a layout bug—it can be invalidations fanning out across your view tree. I hit a case where a single `@Observable` instance, retained by two ancestors, noticeably increased `body` executions during a scroll. Simulator traces were quiet; device profiling made the cascades obvious.

> The UI thread is a budget, not a right—observation either keeps you in budget or quietly taxes your frames.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams

Most apps ship to a mixed OS fleet while evolving features. Your model layer needs to tolerate changes in navigation, ownership, and async boundaries without fragile coupling. Swift’s observation model influences how SwiftUI tracks change and where you pay invalidation costs. If you pick the wrong pattern for your ownership graph, QA cycles can expand, UI tests can become flaky, and you may burn CPU during hot gestures like scroll and type-ahead under list-heavy views. The failure mode is subtle: the UI “feels heavy,” and device captures with Time Profiler, signposts, and metrics reveal the truth.

## 1. What Changes With `@Observable` Versus Legacy MVVM

### How Observation Works

`@Observable` can synthesize change tracking for stored properties. SwiftUI observes reads and invalidates views that depend on those properties. You get less glue and compiler-checked state, while avoiding manual notifier boilerplate.

```swift
import SwiftUI
import Observation

@Observable
@MainActor
final class FeedModel {
    var items: [String] = []
    var isLoading: Bool = false

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        do {
            try await Task.sleep(nanoseconds: 200_000_000)
            items = (0..<30).map { "Item \($0)" }
        } catch {
            items = []
        }
    }
}

struct FeedView: View {
    @State private var model = FeedModel() // This view owns the model

    var body: some View {
        List {
            if model.isLoading { ProgressView() }
            ForEach(model.items, id: \.self) { Text($0) }
        }
        .task { await model.refresh() }
        .refreshable { await model.refresh() }
    }
}
```

### Choose When To Adopt

- When you can keep a single owner per instance and pass references explicitly down the view tree, adopting `@Observable` can simplify code and make invalidation behavior easier to reason about.
- Keep legacy MVVM facades where cross-platform modules or non-SwiftUI surfaces require them; isolate the adapter at the boundary.

### Failure Mode To Avoid

Storing one `@Observable` instance in multiple ancestors couples siblings’ invalidation scopes. Under scroll, seemingly minor state flips can amplify `body` work. Track ownership in code review and verify with development-only diagnostics (for example, prints from `body`) to spot unexpected churn. Remove tracing before shipping.

## 2. Model Ownership Beats Abstraction

### Prefer One Owner, Explicit References

Implicitly shared state hides who mutates what and blurs test seams. A feature root should construct and own its model; children receive a reference via initializers. Keep mutators `@MainActor` to serialize UI-affecting state.

```swift
import Observation

@Observable
@MainActor
final class ProfileModel {
    var name: String = ""
    var isSaving = false

    func save() async {
        guard !isSaving else { return }
        isSaving = true
        defer { isSaving = false }
        // Persist and update derived fields atomically.
    }
}

struct ProfileRoot: View {
    @State private var model = ProfileModel()

    var body: some View {
        ProfileDetails(model: model)
    }
}

struct ProfileDetails: View {
    let model: ProfileModel

    var body: some View {
        TextField("Name", text: $model.name)
        Button("Save") { Task { await model.save() } }
    }
}
```

### Anti-Pattern → Preferred Pattern

- Anti-pattern: global injection and environment state read from many places with incidental lifetimes.
- Preferred: a feature root owns the `@Observable` and passes it down. Cross-feature reads go through a narrow protocol façade at the feature boundary.

### Operational Note

Navigation changes often create new entry paths. If a boundary forgets to provide a dependency, you may see sporadic nils or staleness only on some routes. Centralize construction in one place and write route-coverage tests to exercise every entry point.

## 3. Rendering Budgets: Measure And Keep Them Bounded

### Instrument Mutations

You can’t eyeball invalidation scope. Add signposts to correlate model mutations with SwiftUI work.

```swift
import OSLog

let signposter = OSSignposter(subsystem: "com.example.app", category: "Feed")

@Observable
@MainActor
final class PagedFeedModel {
    var items: [String] = []
    var isLoading = false

    func loadNextPage() async {
        let state = signposter.beginInterval("loadNextPage")
        isLoading = true
        defer {
            isLoading = false
            signposter.endInterval("loadNextPage", state)
        }
        // Fetch and append...
    }
}
```

### Bound Renders In Tests

Wrap small views with a simple counter to keep render costs in check across refactors.

```swift
struct RenderCountView<Content: View>: View {
    @State private var count = 0
    let content: () -> Content

    var body: some View {
        DispatchQueue.main.async { count += 1 }
        return VStack {
            Text("renders: \(count)")
            content()
        }
    }
}
```

Use `XCTest` to drive a gesture sequence, await model completion, and assert the counter remains within a reasonable budget for your views. If identical state is set twice, assert idempotence: no extra renders.

### Decision Point

- Prefer scoping reads narrowly in views and moving derived formatting into helpers to keep invalidations targeted.
- Avoid broad reads (for example, passing the entire model) unless the child actually needs it.

### Operational Note

Always profile on device with Time Profiler. Simulator scheduling can differ from devices and may under-report invalidation cascades during interactions like scroll and type-ahead.

## 4. Migration Without Rewrite

### Hide The Swap Behind A Façade

Keep your view layer stable while replacing internals. A single provider decides which implementation is active.

```swift
import Observation

protocol FeedProviding: Sendable {
    func makeFeedModel() -> any FeedModeling
}

protocol FeedModeling: AnyObject, Sendable {
    var items: [String] { get }
    var isLoading: Bool { get }
    func refresh() async
}

@Observable
@MainActor
final class FeedModelV2: FeedModeling {
    var items: [String] = []
    var isLoading = false
    func refresh() async { /* ... */ }
}

struct FeedProvider: FeedProviding {
    func makeFeedModel() -> any FeedModeling {
        FeedModelV2()
    }
}
```

### Choose Where To Gate

- Gate at the feature provider, not call sites. This avoids drift where one route uses the new model and another quietly uses the old.
- Keep constructors `internal` to discourage accidental direct use. Expose only the façade.

### Operational Note

Make the migration reversible for a period with a feature flag. If post-release metrics regress, you can flip back while you investigate.

## 5. Decisions That De‑Risk Rollout

### Tighten Read Scopes

Treat every property read in `body` as a subscription. Narrow the reads in each view to only what’s rendered. Move expensive computed formatting out of `body` and cache as stored properties updated in mutators.

```swift
@Observable
@MainActor
final class CartModel {
    var items: [LineItem] = [] {
        didSet { subtotal = items.reduce(0) { $0 + $1.price } }
    }
    var subtotal: Decimal = 0
}
```

### Contrast And Consequence

- Broad reads (“just pass the whole model”) can make siblings re-render unexpectedly and blur blame in profiles.
- Targeted reads plus precomputed derived state add a little structure but help keep invalidations surgical and reduce unnecessary `body` recomputes.

### Operational Note

Codify these choices in PR checklists: one owner per model, no re-wrapping models in ancestors, and avoid computed proxies that hide mutations from observation.

## Tradeoffs And Pitfalls

- `@Observable` tracks stored property mutations. If you refactor a stored property into a computed property that proxies elsewhere, you may lose notifications. Prefer stored properties updated in mutators, or explicitly reassign a stored property when underlying data changes.
- Sharing a single `@Observable` across siblings couples their lifetimes and invalidation scopes. If you must share, make the shared type immutable and pass a separate mutable model per feature root.
- Mixing legacy reference models with `@Observable` via ad-hoc adapters can swallow updates. Validate bindings in focused tests, especially in forms where partial updates are common.
- Legacy MVVM with many per-field notifiers can increase re-entrancy risk. If you keep it during migration, assert main-thread access at mutation sites and coalesce updates in one mutator to avoid render ping-pong.
- Simulator profiling can under-report invalidations. Treat device captures as the source of truth for interactive workloads.

## Validation And Observability

- `XCTest` async expectations:
 - Drive taps, scrolls, and refresh actions; await model completion; assert a bounded render count using a test wrapper like `RenderCountView`.
 - Assert idempotence: setting unchanged state does not emit extra renders.
- Instruments:
 - Time Profiler on device: correlate signposted “mutate → render” waves; watch for repeated `body` cascades per user event on list-heavy screens.
 - Allocations: ensure navigation cycles don’t retain closures or buffers after model swaps.
- Logging and metrics:
 - Use signposts for mutators (`refresh`, `apply`, `loadNextPage`) to find fan-out hotspots.
 - Use structured logging with feature categories to trace entry/exit and attribute slow frames to the right model.
 - Gate rollout with crash and performance diagnostics; if metrics worsen after enabling `@Observable`, pause and inspect signposts before expanding.

## Practical Checklist

- [ ] Define one owner per `@Observable` model; pass references downward via initializers.
- [ ] Audit ancestors for hidden caches of the same model; remove re-wrapping and duplicate storage.
- [ ] Scope view reads narrowly; precompute derived state in mutators, not in `body`.
- [ ] Add render-count tests for hot gestures and ensure idempotence for no-op updates.
- [ ] Wrap mutators with signposts; profile on device using Time Profiler and Allocations.
- [ ] Introduce a single feature provider that chooses the implementation; keep constructors `internal`.
- [ ] Wire rollout gates to performance diagnostics; halt expansion on CPU or hang regressions.
- [ ] Document a reversible migration plan and test every navigation route to the feature.

## Closing Takeaway

Both legacy MVVM and `@Observable` can ship, but `@Observable` with explicit ownership often makes render scope easier to reason about as your app evolves. Default to explicit ownership, narrow reads, and device-first profiling. Hide migrations behind a façade, roll out with metrics, and keep a backout switch. If renders spike under scroll on real devices, fix ownership and invalidation scope before touching layout.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation
import OSLog

// ❌ Before — a single shared model instance was retained by multiple ancestors.
// Any property change fanned out invalidations across distant views, spiking
// body evaluations during fast scroll on device.

// ✅ After — scope the observable to a single owner; pass value types downward.
// Rows render from immutable item values and mutate via intents to avoid
// cross-tree observation fans.

struct Item: Identifiable, Hashable {
    let id: UUID
    var title: String
    var isLiked: Bool
}

@MainActor
@Observable
final class FeedModel {
    private let signposter = OSSignposter(subsystem: "Feed", category: "Model")
    var items: [Item] = []
    func load() async {
        let state = signposter.beginInterval("load")
        try? await Task.sleep(nanoseconds: 200_000_000)
        items = (0..<60).map { i in Item(id: UUID(), title: "Row \(i)", isLiked: false) }
        signposter.endInterval("load", state)
    }
    func toggleLike(id: UUID) {
        if let i = items.firstIndex(where: { $0.id == id }) { items[i].isLiked.toggle() }
    }
}

struct FeedView: View {
    @State private var model = FeedModel() // single owner; no sharing across ancestors
    var body: some View {
        List(model.items) { item in
            FeedRow(item: item) { model.toggleLike(id: item.id) }
        }
        .task { await model.load() }
    }
}

struct FeedRow: View {
    let item: Item
    let onToggle: () -> Void
    var body: some View {
        HStack {
            Text(item.title)
            Spacer()
            Button(item.isLiked ? "Liked" : "Like", action: onToggle)
        }
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [Managing model data in your app](https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
