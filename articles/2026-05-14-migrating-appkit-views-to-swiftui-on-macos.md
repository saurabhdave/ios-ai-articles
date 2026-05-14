# Migrating AppKit Views to SwiftUI on macOS

Converting a shipped macOS surface to SwiftUI frequently surfaces runtime differences between the AppKit and SwiftUI stacks: responder-chain delivery, first-responder timing, and layout or performance regressions that only appear on-device. This note focuses on failures that surface under scroll-heavy workloads and offers a low-risk migration pattern to stop excessive re-rendering during interactive use. The guidance is pragmatic: inventory contracts, choose interop boundaries deliberately, centralize state, and validate on real hardware.

## Why This Matters
AppKit and SwiftUI use different runtime models for responder delivery, window semantics, and view lifecycle. Treating SwiftUI as a drop-in replacement for `NSView` or `NSViewController` without accounting for those differences may surface regressions such as broken keyboard shortcuts, lost keyboard focus, or increased CPU work under interactive workloads. Teams must balance long-term maintainability against short-term release risk because choices around interop, state ownership, and rollout determine how many issues appear during and after migration.

> Embed SwiftUI incrementally behind `NSHostingView` and centralize shared state; that single change often eliminates duplicated updates and the worst scroll-time regressions.

## 1. Inventory Existing AppKit Surface
### Catalog Views, Controllers, And Contracts
Record each `NSView`, `NSViewController`, and `NSWindow` boundary and the external contracts they rely on. Include notifications subscribed to, responder-chain assumptions, delegate callbacks, and any window-level behaviors that callers expect. Choose incremental replacement when a UI surface is encapsulated and its inputs are separable; choose a larger refactor when state is globally coupled and tightly interwoven with AppKit controllers. Add structured logs around responder changes to detect silent regressions during canary releases, and validate keyboard and menu behavior on device to expose missing dependencies that often manifest as broken menu shortcuts or lost first responder.

When building your inventory, include who owns each subscription and whether `@Published` publishers are wired to `NSViewController` lifetimes. Validate cancellation paths before rollout because a task that cannot be cancelled leaks CPU and battery. Write a small integration harness that swaps a single non‑critical view into an `NSHostingView` and manually exercise keyboard shortcuts, menu activation, and dragging behavior on a device build.

## 2. Design Interop Patterns
### Embed With `NSHostingView` Or Keep Native `NSView`
Use `NSHostingView` to host SwiftUI when the surface does not require deep `NSWindow` semantics. Keep a native `NSView` when you need custom `NSWindow` dragging, low-level event handling, or precise responder delivery. Choose `NSHostingView` when data inputs are separable and you can centralize state; choose `NSView` when window-level behaviors must remain intact and precise responder timing is required. Map responder expectations from AppKit into the hosted SwiftUI surface and validate focus, menu, and accessibility behavior on device since subtle focus loss under resizing or heavy scroll can expose timing differences.

Instrument the boundary: add signposts and structured logs at the hosting boundary to correlate user actions with SwiftUI updates. During canary rollouts, watch for menu shortcut regressions and lost first responder events and revert the hosting boundary to `NSView` for that surface if those regressions are critical.

## 3. State Management And Data Flow
### Centralize Shared State With `ObservableObject` And Actors
Convert app-level shared state to `ObservableObject` models and consider actor isolation for background work. Pass those shared models into `NSHostingView` instances rather than scattering `@State` across many fragments. Choose multiple local `@State` when state is view-scoped and ephemeral; choose a single `ObservableObject` when many fragments need synchronous shared state. When the same observable instance is held by multiple ancestor views or recreated in many places, duplicated updates can cause excessive re-rendering; centralizing ownership in a controller and injecting the instance into hosting views reduces redundant updates.

Validate lifetime coupling between Combine-style publishers and `NSViewController` ownership to avoid leaks or cancelled subscriptions. Actor isolation helps prevent UI races; add unit tests that assert an owned `ObservableObject` instance produces a bounded update rate under heavy mutation and profile to confirm it does not trigger repeated layout passes.

```swift
@MainActor
final class FeedModel: ObservableObject {
    @Published var items = [String]()
}
let hosting = NSHostingView(rootView: FeedView(model: feedModel))
```

## 4. Validation, Observability, And Testing
### Tests, Traces, And Device Profiling
Add signposting markers around rendering and data-update boundaries to correlate UI stalls with backend work. Use `XCTest` async expectations to encode lifecycle ordering and detect races between `NSViewController` and SwiftUI updates. Profile on device with `Instruments` (`Time Profiler`, `Allocations`); simulator runs can miss device-specific layout or GPU behavior that appears on real hardware. Run unit and integration tests that assert invariants before canary releases, instrument rendering paths with structured logs for rollout gates, and collect telemetry to spot regressions after release.

Create synthetic stress tests that exercise heavy scroll and rapid state mutations on a physical machine. Correlate telemetry with signposts to identify whether regressions are CPU-bound recomputation, GPU layout churn, or subscription churn from duplicated observers. When regressions appear, correlate user-reported stalls with signposted traces and `Instruments` profiles to prioritize fixes and consider reverting to a native `NSView` for the affected surface while you iterate on state ownership.

## 5. Rollout Strategy And Failure Handling
### Canary Releases, Feature Flags, And Logs
Gate migration behind feature flags and run canary releases to a small percentage of users. Choose a broad rollout when the canary shows stable metrics; choose rollback and further isolation when telemetry shows regressions. Collect structured logs that include responder-chain changes, first-responder timing, and signposts around major rendering phases. If regressions appear, revert the hosting boundary to `NSView` for that surface and iterate on state ownership and subscription lifecycle.

Prioritize fixes by correlation: map telemetry spikes to signpost intervals and `Time Profiler` hot paths. Use small, iterative rollouts and ensure your rollback path is tested as part of release automation so you can quickly isolate and remediate problematic surfaces.

## Tradeoffs And Pitfalls
Rewriting large swaths of UI reduces long-term maintenance but increases short-term QA cost and release risk. Mixing AppKit and SwiftUI reduces rewrite scope but introduces ongoing complexity: you must test responder-chain boundaries, `NSWindow` semantics, and focus behavior across both systems. Performance pitfalls are common because SwiftUI can surface expensive recomputation or layout work in ways not obvious during development. Backward compatibility is another area to monitor; changes to shared state or preferences may require migration paths or careful rollout strategies.

Operationally, be wary of duplicated `ObservableObject` instances or `@State` fragments that trigger redundant updates; these are frequent sources of scroll-time regressions. Validate lifetimes for Combine subscriptions and ensure actors used for background work do not introduce hidden contention with the main thread.

## Practical Checklist
- [ ] Audit and document every `NSView`/`NSViewController` boundary and its external dependencies (notifications, responder-chain, delegates).
- [ ] Prototype embedding with `NSHostingView` for one non-critical screen and validate focus, menus, and accessibility behavior on device.
- [ ] Add `XCTest` cases with async expectations that encode UI invariants and lifecycle ordering.
- [ ] Instrument rendering paths with signposting and structured logs.
- [ ] Convert shared app state to `ObservableObject` and consider actor isolation for background work.
- [ ] Gate rollout with feature flags and canary releases; collect telemetry and structured logs to detect regressions.
- [ ] Run `Instruments` (`Time Profiler`, `Allocations`) on device for migration candidates.

## Closing Takeaway
Migrate incrementally and validate on device. Start with a low-risk surface, embed it with `NSHostingView` when appropriate, centralize shared state into `ObservableObject` models (and use actors where helpful), and validate with `XCTest`, signposting, and `Instruments`. Use canary releases and structured logs to surface subtle runtime failures before broad rollout; this sequence limits incidents and keeps release risk manageable.

## Swift/SwiftUI Code Example

_A code example for this topic is not included in this edition._

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
