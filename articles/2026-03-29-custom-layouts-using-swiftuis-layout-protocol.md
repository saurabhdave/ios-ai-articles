# Custom Layouts Using SwiftUI's Layout Protocol

Converting ad-hoc layout math scattered across view bodies into reusable types frequently exposes nondeterministic behavior: frames jump during rotation, dynamic type breaks alignment, or measurement errors cascade into CPU pressure in lists. This article targets those symptoms and shows how to adopt the `Layout` protocol in a controlled, testable way that limits blast radius during migration.

## Why This Matters For iOS Teams

Large apps accumulate bespoke placement rules inside view controllers or deeply nested stacks. Moving that logic into reusable `Layout` types centralizes spatial rules, improving reuse and enabling unit tests against `sizeThatFits` and `placeSubviews`. Choose extraction when multiple screens share spatial behavior or when a view’s intrinsic measurement depends on sibling content; choose inline stacking when the logic is isolated to a single screen and adds no reuse value. Validate extracted `Layout` behavior with deterministic tests so you reduce maintenance rather than increase integration risk.

> Extract placement math into a focused `Layout` only when you can document its cache semantics and test its `sizeThatFits` outcomes — otherwise you're moving a hard-to-reason-about problem into a shared surface.

## 1. Layout Protocol Basics

### Core Methods And Cache Pattern
`Layout` exposes `sizeThatFits(proposal:subviews:cache:)` and `placeSubviews(in:proposal:subviews:cache:)`. Implement a `Cache` associated type to retain intermediate measurements between those calls and avoid repeating expensive work during a layout pass.

Choose a simple cache when measurements are cheap and derived from inputs; choose a richer cache when you must avoid repeated expensive `sizeThatFits` calls across many subviews. Tests should assert `sizeThatFits` results for representative `ProposedViewSize` inputs so changes in cache logic fail fast in CI.

Example compact `Layout` pattern demonstrating a minimal `Cache` and measurement call:

```swift
struct TwoColLayout: Layout {
 typealias Cache = [CGSize]
 func sizeThatFits(_ proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize {
 cache = subviews.map { $0.sizeThatFits(.init(width: proposal.width.map { $0/2 }, height: nil)) }
 return CGSize(width: proposal.width ?? 800, height: cache.map { $0.height }.max() ?? 0)
 }
 func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) {}
}
```

Integrate unit tests that call `sizeThatFits` with fixed `ProposedViewSize` values to assert deterministic sizing. Avoid `UIScreen.main.bounds` inside `sizeThatFits` so tests remain deterministic.

## 2. Building Reusable Custom Layouts

### Consumer API And Parameter Surface
Expose a `Layout` via a small consumer API that uses `@ViewBuilder` for content composition when appropriate. Document each parameter and the conditions that must trigger cache invalidation (for example: content changes, font scaling, orientation).

Choose a minimal parameter surface when layout rules are stable across screens; choose a configurable surface when downstream teams need to adjust spacing or alignment. Integrate instrumentation points around `sizeThatFits` and `placeSubviews` so telemetry can capture regressions during early rollouts.

When you provide a `Cache`, document what invalidates it and provide deterministic invalidation paths tied to accessible properties or environment values such as `\ .sizeCategory`.

## 3. Integration And Migration Strategy

### Incremental Embedding With UIKit Interop
When migrating a `UIViewController` to SwiftUI, embed small SwiftUI views that use custom `Layout` types via `UIHostingController` or wrap existing `UIView` components with `UIViewRepresentable`. Incremental embedding limits blast radius and makes rollback easier.

Choose full rewrite when the UI surface is small and internal ownership is clear; choose incremental embedding when the screen is large, third-party `UIView`s exist, or you need quick rollback. Smoke-test safe-area and trait interactions in the hosting environment; validate orientation changes and navigation transitions with your `Layout` inside `UIHostingController` before broad rollout.

## 4. Performance And Memory Considerations

### Lazy Composition And Cache Invalidation
For large collections, avoid measuring every child eagerly. Combine `Layout` with lazy containers such as `LazyVStack` or `LazyHStack` for long lists, and design a `Cache` that records only the data you need.

Choose eager measurement when subview count is small and measurements are trivial; choose lazy measurement with a minimal `Cache` when rendering many subviews. Profile with `Instruments` (for example, Time Profiler and Allocations) to find hotspots before optimizing. Ensure cache invalidation covers inputs like dynamic type changes and orientation to prevent stale placements and extra layout passes.

When caches get out of sync, incorrect placement or repeated layout passes are common symptoms. Add lightweight timing instrumentation around `sizeThatFits` and `placeSubviews` during development to detect expensive calls.

## Tradeoffs & Pitfalls

Custom `Layout` types improve composability and testability but can complicate handling screen-specific exceptions. Tradeoffs to consider:
- Composability vs. Predictability: small, well-documented `Layout` types are easier to reason about than a single catch-all type.
- Observability Burden: adding telemetry increases signal volume and requires decisions about what to monitor.
- Migration Surface: incremental embedding reduces blast radius but requires interoperability tests across safe-area, trait collection, and animation boundaries.

Known failure modes include layout loops caused by inconsistent measurement and stale caches when trait or environment changes are not accounted for. Plan explicit invalidation surfaces and test them.

## Validation And Observability

### Tests, Instruments, And Runtime Signals
Validate across multiple layers. Use `XCTest` unit tests to assert `sizeThatFits` behavior for specific `ProposedViewSize` inputs and expected intrinsic sizes. Profile with `Instruments` to locate expensive layout calls and memory retention.

- Mark important layout boundaries with lightweight instrumentation to capture timing for `sizeThatFits` and `placeSubviews`.
- Collect runtime logs or telemetry from canary releases to correlate regressions with changes.
- Gate rollout behind feature flags and run within a limited cohort to observe real-world effects before broad deployment.

Encode alignment and intrinsic-height invariants in tests so regressions fail fast in CI.

## Practical Checklist

- [ ] Add `XCTest` unit and snapshot tests covering `sizeThatFits` and placement for each custom `Layout`.
- [ ] Instrument critical layout paths and capture perf baselines with `Instruments`.
- [ ] Implement a minimal `Cache` strategy in `sizeThatFits` and document explicit invalidation points for content, font scale, and orientation.
- [ ] Prototype integration with `UIHostingController` and smoke-test safe-area, orientation, and accessibility font scaling scenarios.
- [ ] Gate rollout behind feature flags and collect telemetry from limited cohorts during early releases.
- [ ] Document public `Layout` parameters, defaults, and a deprecation path for future changes.

## Closing Takeaway

Move placement math into small, focused `Layout` types when reuse and testability outweigh integration risk. Keep caches minimal, document invalidation, and validate `sizeThatFits` behavior with deterministic `XCTest` inputs. Roll out incrementally via `UIHostingController`, instrument hotspots with `Instruments`, and gate changes behind feature flags so you can detect and mitigate issues early.

## Swift/SwiftUI Code Example

```swift
import SwiftUI

struct TwoColumnLayout: Layout {
    struct Cache { var leadingWidth: CGFloat = 0 }
    var spacing: CGFloat

    func makeCache(subviews: Subviews) -> Cache { Cache() }

    func updateCache(_ cache: inout Cache, subviews: Subviews) {
        // deterministic measurement: use the intrinsic size of leading column
        if let leading = subviews.first {
            let proposed = ProposedViewSize(width: .infinity, height: .infinity)
            cache.leadingWidth = leading.sizeThatFits(proposed).width
        }
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize {
        guard subviews.count >= 2 else { return .zero }
        let trailing = subviews[1].sizeThatFits(proposal)
        let leading = CGSize(width: cache.leadingWidth, height: subviews[0].sizeThatFits(proposal).height)
        let width = leading.width + spacing + trailing.width
        let height = max(leading.height, trailing.height)
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) {
        guard subviews.count >= 2 else { return }
        let leadingSize = subviews[0].sizeThatFits(ProposedViewSize(width: cache.leadingWidth, height: bounds.height))
        let trailingSize = subviews[1].sizeThatFits(ProposedViewSize(width: bounds.width - cache.leadingWidth - spacing, height: bounds.height))
        let yLeading = bounds.minY + (bounds.height - leadingSize.height) / 2
        let yTrailing = bounds.minY + (bounds.height - trailingSize.height) / 2
        subviews[0].place(at: CGPoint(x: bounds.minX, y: yLeading), anchor: .topLeading, proposal: ProposedViewSize(leadingSize))
        subviews[1].place(at: CGPoint(x: bounds.minX + cache.leadingWidth + spacing, y: yTrailing), anchor: .topLeading, proposal: ProposedViewSize(trailingSize))
    }
}

struct TwoColumnExample: View {
    var body: some View {
        TwoColumnLayout(spacing: 12) {
            Text("Flexible leading column that determines measured width")
                .font(.headline)
            VStack(alignment: .leading) {
                Text("Item A")
                Text("Item B")
            }
        }
        .padding()
        .border(.gray)
        .frame(maxWidth: 400)
    }
}
```

## References

- [SwiftUI](https://developer.apple.com/documentation/swiftui)
- [Swift Documentation](https://www.swift.org/documentation/)
