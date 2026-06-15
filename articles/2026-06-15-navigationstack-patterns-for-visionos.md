# NavigationStack Patterns for visionOS

Spatial navigation in visionOS looks effortless until 2D windows, 3D spaces, and scene timing fall out of sync. When focus shifts, spaces open or dismiss, and restoration replays, the weakest link is state, not buttons. Treat routes as data and coordinate lifecycles so transitions become deterministic rather than emergent.

*All code in this article targets visionOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters
Directly porting iPad navigation by dropping a `NavigationStack` into each window runs into real-world friction: focus changes across multiple windows, immersive entry and exit, and restoration on reactivation. `NavigationSplitView` selections can reset, non-`Codable` `NavigationPath` elements can break replay, and firing `openImmersiveSpace` while pushing a stack can leave a space open behind the “current” window. Viewing navigation as a state machine with one route source of truth keeps deep links, multi-window focus, and immersive transitions coherent and testable under load.

## 1. Stack Vs. Split For Spatial UIs
### The Anti-Pattern: Nesting Stacks To Fake Master–Detail
Nesting a `NavigationStack` inside a `NavigationLink` looks harmless but often resets `List` `selection` when a window regains focus or after `dismissImmersiveSpace`.

### Prefer One Container Per Window
Choose `NavigationSplitView` when persistent context must survive activations; choose a single `NavigationStack` for short, linear flows. Avoid mixing containers within a window and keep exactly one selection owner.

Set `columnVisibility` to `.automatic` so layout adapts during presentation changes. Under activation churn and space exits, mixed containers can clear `selection`; verify stability by scripting rapid activate/deactivate cycles and confirming back gestures remain available.

Decision criterion:
- Choose `NavigationSplitView` when a window outlives a single task and must preserve context.
- Choose `NavigationStack` when the route is short and focused.
- Do not combine them in a single window.

> One window, one navigation container. If you need both linear flow and persistent context, use `NavigationSplitView` and host a stack in the detail column.

## 2. Programmatic Routing With `NavigationPath`
### Model Routes, Not Views
Ad-hoc booleans and imperative pushes drift. Define a small `Codable` route model and make it the only way to mutate `NavigationPath`.

```swift
import SwiftUI
import Observation

@MainActor
@Observable
final class Router {
  var path: NavigationPath = .init()
  enum Route: Hashable, Codable {
    case item(id: UUID)
    case settings
    case help(anchor: String)
  }
  func push(_ r: Route) { path.append(r) }
  func popToRoot() { path.removeLast(path.count) }
}```

### Drive Navigation From One Source Of Truth
Map every route to a destination in one place with `navigationDestination(for:)`. Keep heavy context in feature models keyed by IDs rather than embedding it in `Route`.

Validate replay by injecting a recorded path at cold start and asserting view models rehydrate from IDs. Choose `Codable` payloads when you need reliable restoration and deep links; if payloads are not `Codable`, expect brittle restoration and plan explicit adapters with a safe root fallback.

## 3. Coordinating With Immersive Spaces
### Coordinate The Bridge Between 2D And 3D
Combining `openImmersiveSpace` with a `NavigationStack` push in the same tap handler can race, leaving a space open behind an apparently “current” window. Serialize transitions so only one immersive action happens at a time.

```swift
@MainActor @Observable
final class ImmersionCoordinator {
  enum Phase { case idle, opening, open, dismissing }
  var phase: Phase = .idle
  func go(_ r: Router.Route,
          open: OpenImmersiveSpaceAction,
          dismiss: DismissImmersiveSpaceAction,
          router: Router) async {
    if needsImmersion(r), phase == .idle { phase = .opening; _ = await open(id: "inspect"); phase = .open }
    if !needsImmersion(r), phase == .open { phase = .dismissing; await dismiss(); phase = .idle }
    router.push(r)
  }
  private func needsImmersion(_ r: Router.Route) -> Bool { if case .item = r { true } else { false } }
}
```

Debounce rapid taps and queue or drop redundant transitions rather than allowing partial opens. Choose serialized transitions when a route may open or close a space; choose direct pushes only for routes guaranteed to remain 2D. Stress-test with rapid double-taps and scroll-induced taps to confirm the phase returns to `.idle` or `.open` deterministically.

## 4. State Restoration And Deep Linking
### Snapshot Per-Window Paths
Persist a window’s `NavigationPath` with `@SceneStorage`, convert external intents from `onOpenURL` or `onContinueUserActivity` into validated routes, and replay only those that remain safe under current permissions and resources.

Choose per-window `@SceneStorage` when each window owns its journey; choose a shared store only if multiple windows must coordinate a single logical path. When prerequisites like camera access are missing, redirect immersive-first routes to a safe 2D fallback and show guidance; guard these cases in `canReplay(_:)` to avoid dead ends.

## 5. Focus, Gestures, And Multi-Window
### Keep A Single Selection Owner
When one window uses `NavigationStack` and another uses `NavigationSplitView`, activation churn can desynchronize `selection` and back gestures. Each window should own its `selection` and `path`; cross-window hops must be explicit route mutations, not incidental gesture effects.

### Gate Interactions During Activation Changes
Pause interactive navigation while the scene transitions between active and background states to reduce the chance that a back-swipe targets the wrong window.

```swift
struct WindowRoot: View {
  @Environment(\.scenePhase) private var phase
  @State private var enabled = true
  @State private var router = Router()
  var body: some View {
    NavigationStack(path: $router.path) { ContentView(disableInteractions: !enabled) }
      .onChange(of: phase) { _, p in enabled = (p == .active) }
  }
}
```

Choose gesture-driven pops only when the scene is `.active` and stable; choose explicit back buttons with `navigationBarBackButtonHidden(true)` and a custom action while activation is in flux. If diagnostics suggest back-swipe overlaps with activation changes, temporarily disable gesture pops and rely on router-backed actions.

## Tradeoffs And Pitfalls
- Centralized routing adds ceremony. Keep `Router.Route` focused on identity and intent; once it mirrors views, the coupling is wrong.
- `NavigationSplitView` preserves context but can overwhelm in compact layouts. Prefer `.automatic` for `columnVisibility` and adapt detail density as needed.
- Immersive transitions complicate undo and redo. Define explicit exit routes (for example, a `.home` case) so dismissing a space maps to a real route change.
- Multiple windows increase gesture contention. If back-swipes can target the background window, pause interactions on activation changes and use explicit actions during transitions.
- High-volume logging during space transitions can affect performance. Sample logs, gate behind build flags, and avoid high-cardinality fields on the hot path.

## Validation And Observability
Good spatial navigation is about timing and back pressure. Encode invariants with `XCTest`, including async tests that stimulate the `ImmersionCoordinator` with rapid interactions; assert that only one `openImmersiveSpace` attempt succeeds at a time and that phase settles. Mark async boundaries with `OSSignposter`: add intervals for `router.push`, `router.popToRoot`, `openImmersiveSpace`, and `dismissImmersiveSpace`, then correlate with frame time in Instruments to spot heavy destinations or synchronous asset loads. Start with Time Profiler and follow with Allocations; if the first render of a 3D-heavy screen is costly with multiple windows active, prewarm assets on a low-priority `Task` before navigating. Roll out with guardrails by sampling logs in release and watching MetricKit for spikes in hangs or animation issues during space transitions.

## Practical Checklist
- [ ] Define a `Route` enum that is `Codable`, small, and keyed by identity.
- [ ] Own one `NavigationStack` or one `NavigationSplitView` per window; never nest stacks.
- [ ] Create a `@MainActor`, `@Observable` router that exposes `push` and `pop` and backs a `NavigationPath`.
- [ ] Map every `Route` in a single `navigationDestination(for:)`; keep view construction light.
- [ ] Bridge 2D and 3D with an `ImmersionCoordinator` that serializes `openImmersiveSpace` and `dismissImmersiveSpace`.
- [ ] Persist per-window paths with `@SceneStorage`; validate restored routes before replay.
- [ ] Pause gesture-driven navigation during scene activation changes to avoid cross-window pops.
- [ ] Instrument route changes and space open or dismiss with `OSSignposter`; verify in Instruments before release.

## Closing Takeaway
Treat visionOS navigation as a state machine that coordinates exactly one window container and one immersive lifecycle. Centralize intent in a `Codable` route model and drive all UI transitions from it. Serialize 2D and 3D moves through a coordinator so timing bugs become test cases, not production defects. Persist and validate paths per window to make deep links and restoration predictable. The wow should come from your content; routing should stay steady.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

enum Route: Hashable, Codable {
    case list
    case detail(id: UUID)
}

@MainActor @Observable final class Router {
    var path: [Route] = []
    private var immersiveID: String? = nil

    func set(
        routes: [Route],
        immersive: String?,
        open: @escaping (String) async -> Void,
        close: @escaping () async -> Void
    ) async {
        if immersiveID != immersive {
            if let id = immersive {
                immersiveID = id
                await open(id)
            } else {
                immersiveID = nil
                await close()
            }
        }
        path = routes.filter {
            if case .list = $0 { return false } else { return true }
        }
    }
}

struct CatalogView: View {
    @State private var router = Router()
    #if os(visionOS)
    @Environment(\.openImmersiveSpace) private var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) private var dismissImmersiveSpace
    #endif

    var body: some View {
        NavigationStack(
            path: Binding(
                get: { router.path },
                set: { router.path = $0 }
            )
        ) {
            List {
                Button("Open Detail + Enter Immersive") {
                    let id = UUID()
                    Task {
                        #if os(visionOS)
                        await router.set(
                            routes: [.detail(id: id)],
                            immersive: "SolarSystem",
                            open: { spaceID in _ = await openImmersiveSpace(id: spaceID) },
                            close: { await dismissImmersiveSpace() }
                        )
                        #else
                        await router.set(
                            routes: [.detail(id: id)],
                            immersive: nil,
                            open: { _ in },
                            close: { }
                        )
                        #endif
                    }
                }
                Button("Back To List + Exit Immersive") {
                    Task {
                        #if os(visionOS)
                        await router.set(
                            routes: [.list],
                            immersive: nil,
                            open: { _ in },
                            close: { await dismissImmersiveSpace() }
                        )
                        #else
                        await router.set(
                            routes: [.list],
                            immersive: nil,
                            open: { _ in },
                            close: { }
                        )
                        #endif
                    }
                }
            }
            .navigationTitle("Items")
        }
        .navigationDestination(for: Route.self) { route in
            switch route {
            case .detail(let id):
                Text("Detail \(id.uuidString.prefix(6))")
            case .list:
                EmptyView()
            }
        }
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
