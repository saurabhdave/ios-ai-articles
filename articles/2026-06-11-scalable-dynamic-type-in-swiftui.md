# Scalable Dynamic Type in SwiftUI

I shipped a feed view that re-rendered multiple times per scroll tick because a single `@Observable` model instance was captured by many ancestor views. The runtime symptoms were stuttery scrolling, unexpected layout shifts, and poor responsiveness on constrained devices. The patterns below show how I reduced unnecessary invalidation, rolled out Dynamic Type changes safely, and kept typography scalable across mixed `SwiftUI`/`UIKit` hierarchies.

## Why This Matters For iOS Teams

Design often expects pixel precision; accessibility requires scalable text. Those goals can conflict when font metrics, spacing, and shared state interact across many views. Mis-scaled text causes clipping, layout shifts, and interaction regressions that users notice.

Dynamic Type and typography are a cross-cutting concern: component APIs, state ownership, testing, and runtime observability all influence whether a change is safe to ship. Consider the entire stack, not only individual label styles, when planning migration and rollout.

## 1. Semantic Scaling Versus Manual Math

### Prefer System Semantics For Font Scaling
Read `@Environment(\.sizeCategory)` in leaf views and use semantic `Font` variants instead of scattering point arithmetic. Use `@ScaledMetric` for non-font geometry such as icon sizes and spacing to keep scaling consistent with system behavior.

Choose semantic `Font` when you want consistent, system-driven scaling; choose manual point math when a designer demands pixel-matching and you accept ongoing maintenance cost. Validate components at representative `DynamicTypeSize` values using `XCTest` snapshots and include at least one accessibility size during testing.

Example component:
```swift
import SwiftUI

struct LabelRow: View {
    @Environment(\.sizeCategory) private var sizeCategory
    @ScaledMetric private var iconSize: CGFloat = 20

    let title: String

    var body: some View {
        HStack(spacing: iconSize / 2) {
            Image(systemName: "star.fill")
                .resizable()
                .frame(width: iconSize, height: iconSize)
            Text(title)
                .font(.title3)
                .lineLimit(2)
        }
        .accessibilityIdentifier("LabelRow_\(title)")
    }
}
```

When adding pixel-specific sizes, snapshot the component at multiple `DynamicTypeSize` values and gate the change behind a staged rollout to limit user impact while you verify visual parity.

## 2. Environment-Driven Components And State Locality

### Read Environment At The Leaf, Keep State Local
Avoid passing a mutable global scale object or a shared `@Observable` instance deep into the view tree when unnecessary. That pattern becomes a single point of invalidation: small mutations can cause many ancestors to re-render.

Choose local `@Environment` reads and immutable props when the component is simple; choose a shared `@Observable` when state genuinely affects most of the UI. Convert shared mutable state into immutable props where possible, and expose `Binding` only where mutation is required. Profile on device and add signposts around suspect view boundaries to correlate state changes with render hotspots so you can detect high invalidation fan-out quickly.

When migrating legacy `UIKit` metric logic, wrap it behind an adapter rather than changing public component APIs directly. Precompute expensive layout values outside of `View.body` and memoize where possible to keep body execution cheap.

## 3. Component Adapters For Mixed UIKit/SwiftUI Hierarchies

### Bridge `UIFontMetrics` To SwiftUI
`UIFontMetrics` behavior can differ from `SwiftUI` `Font` for non-font geometry. Implement narrow adapter wrappers that encode `UIFontMetrics` and expose a `SwiftUI`-friendly API so visual drift can be assessed during staged migration.

Choose adapters when you need visual parity during incremental migration; choose full migration to `Font` and `@ScaledMetric` once the surface area is small or fully tested. Keep adapters temporary and track visual results before removing them. Wrap `UIKit` scaling in narrow, testable functions and include visual regression snapshots as part of the adapter removal plan.

Adapter sketch:
```swift
import SwiftUI
import UIKit

struct UIFontMetricsAdapter {
    static func scaled(_ base: CGFloat, for textStyle: UIFont.TextStyle) -> CGFloat {
        let metrics = UIFontMetrics(forTextStyle: textStyle)
        return metrics.scaledValue(for: base)
    }
}
```

Run snapshot tests that compare adapter-based views to pure `Font`/`@ScaledMetric` implementations at several `DynamicTypeSize` values. Stage rollout with telemetry and feature flags so you can revert or tweak the adapter if visual drift appears.

## 4. Avoid Unbounded View Invalidations

### Split Observables And Minimize Fan-Out
A common failure mode is many descendants capturing the same `@Observable` instance; an unrelated mutation can re-render whole subtrees and hurt scrolling. Split observable models or pass immutable props to reduce fan-out when appropriate.

Choose value types and local observability when state changes frequently at the cell or row level; choose shared observables when changes genuinely affect broad UI regions. Keep heavy layout computation out of `View.body`; precompute sizes, memoize results, and minimize `GeometryReader` usage for layouts that can be expressed with flexible primitives. Use `PreferenceKey` sparingly and consider debouncing measurement updates if they are expensive.

Profile with `Instruments` (Time Profiler and Allocations) and correlate hotspots with OSSignposter traces so that expensive layout work is visible in traces. Add structured logs around view invalidation events and correlate them with user-reported performance regressions during staged rollouts.

> Avoid letting a single observable leak into many ancestors. That pattern increases the chance of unnecessary re-rendering.

## 5. Validation And Observability

### Test, Profile, And Stage Releases
Validate with `XCTest` snapshot assertions across representative `DynamicTypeSize` values and include at least one accessibility size. Profile on device with `Instruments` and correlate hotspots with OSSignposter signposts to see whether layout or state updates are the cause. Add low-cardinality telemetry and structured logs for staged rollouts so you can detect layout regressions without generating high-cardinality noise.

When rolling out changes, gate telemetry behind feature flags and stage releases to limit exposure while validating behavior. Use signposting to mark expensive layout work for inspection in `Instruments`, and include snapshot diffs in CI when changing font metrics or adapters so regressions are caught early.

Run allocation and time profiles on representative devices and test interaction sequences that exercise scrolling, cell reuse, and state mutations to uncover invalidation fan-out under load.

## Tradeoffs And Pitfalls

- Semantics vs pixel control: Using semantic `Font` improves accessibility behavior but may diverge from strict designer pixel specs. If pixel-perfect rendering is required, plan for the maintenance cost of explicit design tokens and additional snapshot coverage.
- Tests vs maintenance: Expanding snapshot coverage across many `DynamicTypeSize` variants reduces regressions but increases CI time and maintenance. Prioritize a subset of sizes that exercise typical and accessibility scenarios.
- Adapters vs long-term cleanup: Adapters reduce release risk but create dual-maintenance. Use them when the risk of visual regression is high, and time-box the migration to remove them when safe.

## Practical Checklist

- [ ] Inventory screens/components by exposure to text scaling and mark high-risk surfaces.
- [ ] Replace hard-coded sizes with semantic `Font` where possible and use `@ScaledMetric` for icon sizes and spacing.
- [ ] Add `XCTest` snapshot tests for a prioritized set of `DynamicTypeSize` variants, including at least one accessibility size.
- [ ] Profile on device with `Instruments` and correlate with OSSignposter traces.
- [ ] Implement temporary adapter wrappers around `UIFontMetrics` for mixed hierarchies when visual parity is required.
- [ ] Split large `@Observable` models to reduce invalidation fan-out; pass immutable props where mutation is unnecessary.
- [ ] Gate visual changes behind feature flags and stage releases with targeted telemetry.

## Closing Takeaway

Scalable Dynamic Type touches component APIs, state ownership, testing, and runtime observability. Default to semantic `Font` scaling and `@ScaledMetric` for non-font geometry when possible, and localize observable state to avoid broad invalidation. Use narrow adapters for mixed hierarchies during migration, validate behavior on device with `Instruments` and signposts, and stage rollouts with telemetry to minimize risk.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

@Observable class FeedStore {
    var items: [FeedItem] = [
        .init(id: UUID(), title: "Welcome", subtitle: "Scalable Dynamic Type"),
        .init(id: UUID(), title: "SwiftUI Tip", subtitle: "Read sizeCategory at leaf")
    ]
}

struct FeedItem: Identifiable, Equatable {
    let id: UUID
    var title: String
    var subtitle: String
}

struct FeedListView: View {
    @State private var store = FeedStore()
    var body: some View {
        List(store.items) { item in
            FeedRow(item: item)
        }
        .listStyle(.plain)
    }
}

struct FeedRow: View {
    let item: FeedItem
    @Environment(\.sizeCategory) private var sizeCategory
    var body: some View {
        VStack(alignment: .leading, spacing: spacing(for: sizeCategory)) {
            Text(item.title)
                .font(.title)
                .fontWeight(.semibold)
            Text(item.subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 8)
    }
    private func spacing(for size: ContentSizeCategory) -> CGFloat {
        switch size {
        case .accessibilityExtraExtraExtraLarge, .accessibilityExtraExtraLarge:
            return 12
        case .accessibilityExtraLarge:
            return 10
        default:
            return 6
        }
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
