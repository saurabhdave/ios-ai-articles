# Custom SwiftUI Layouts with the Layout Protocol

SwiftUI’s `Layout` protocol turns layout from a set of hacks into a clear contract you can reason about. When stacks and geometry tricks start to jank during scroll, a purpose-built `Layout` often restores determinism and performance without sacrificing design intent.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams

Complex screens encode shared rules: wrapping flows, equal-height columns, weighted distribution, and baseline alignment. Capturing those once as `Layout` types reduces ad‑hoc math and keeps measurement logic local to the container instead of scattered through `PreferenceKey` plumbing. Teams gain testable primitives that are easier to profile and reason about.

Release risk is real. Bad measuring clips or overflows, and disagreements between `sizeThatFits` and `placeSubviews` surface only with large content or right‑to‑left. Simulator timing can diverge from device behavior, so verify on hardware and gate rollouts when stakes are high.

> Measure once, place once, and make it observable—predictability is the antidote to layout jank.

## 1. When To Use `Layout` Over Stacks And Grids

### Recognize When Stacks Stop Helping

Use `HStack`, `VStack`, `Grid`, or `ViewThatFits` when uniform spacing and built-in alignments fully describe the rules. Choose stacks when you don’t need multi-pass logic; choose a custom `Layout` when you must measure children to compute line breaks, proportional widths, or contextual spacing, or when baseline alignment varies per item.

A common anti-pattern is `GeometryReader` plus `PreferenceKey` to bubble sizes up for a second pass. Prefer a `Layout` that computes once, caches intentionally, and places deterministically. If the design pushes you to “measure twice,” it likely wants to be a `Layout` type.

```swift
struct WeightedRow: View {
  @State private var useNew = true
  var items: [AnyView]
  var body: some View {
    Group {
      useNew ? AnyView(WeightedHFlow(spacing: 8, lineSpacing: 8).callAsFunction { items })
             : AnyView(FlowFallback(spacing: 8, lineSpacing: 8).callAsFunction { items })
    }
  }
}
```

### Rollout Strategy

Keep a fallback for risky screens and flip with a remote flag, not compile-time. Validate on-device inside `ScrollView` and `List`, where extra passes can appear during diffing.

Choose a gradual rollout when the new `Layout` changes measurement semantics; choose an immediate cutover only when screens are simple and verified with snapshots and perf budgets.

## 2. Implementing A Custom Layout Correctly

### Make `sizeThatFits` And `placeSubviews` Agree

The contract is simple: implement `sizeThatFits(proposal:subviews:cache:)` and `placeSubviews(in:proposal:subviews:cache:)`. Use `.unspecified` when you want intrinsic sizing without circular dependencies; use a constrained `ProposedViewSize` when you intend to clamp children and control expansion. Introduce a cache when reuse pays off, and invalidate when environment changes that impact geometry occur, such as content size category, locale, or size class.

```swift
struct Flow: Layout {
  func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Void) -> CGSize {
    let maxW = proposal.width ?? 1_000_000
    let sizes = subviews.map { $0.sizeThatFits(.unspecified) }
    return CGSize(width: min(maxW, sizes.map(\.width).reduce(0, +)),
                  height: sizes.map(\.height).max() ?? 0)
  }
  func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Void) { /* match math */ }
}
```

Choose explicit clamping when overflowing content must wrap predictably; choose intrinsic sizing when content dictates size and the parent will trim or scroll. Test both compact and regular environments to ensure placement matches the reported size.

### Determinism Under Constraints

When `proposal.width` is `nil`, cap it or compute an intrinsic width and let the parent clamp you. Small differences in font metrics or image decoding can swing layout cost; profiling on device prevents surprises during rapid scroll. Keep math pure and avoid reading state that can change mid-pass.

## 3. Spacing, Alignment, And Child-Provided Values

### Use `LayoutValueKey` For Local Hints

Children can provide hints via `LayoutValueKey`. Use `LayoutValueKey` when a per-item value (weight, spacing, baseline offset) informs local policy; use top-level `Layout` properties when a global rule applies to every subview.

Choose child-provided weights when siblings need proportional growth; choose fixed widths when pixel-fitting or iconography depends on intrinsic sizes. Ensure the widths returned from `sizeThatFits` match actual placements or you will see clipping and misalignment, particularly with large dynamic type.

### Weights Versus Intrinsic

When content can stretch (for example, text labels with room to grow), weights distribute spare width. When content must remain intrinsic, treat weight `0` as fixed and leave the measured size intact. Compute baselines or reused dimensions once per pass to avoid re-measurement in dense `List` or `ScrollView` containers.

## 4. Backward Compatibility And Migration Without Behavior Drift

### Share Tests Across Old And New Paths

Even if you default to the new layout, you may keep a fallback for legacy screens. Use identical APIs and mirror the geometry rules so behavior won’t drift. Snapshot tests catch spacing and ordering shifts before they ship, and unit tests verify `sizeThatFits` invariants for representative datasets.

Choose to keep both paths wired into the same test suite to prevent entropy; choose removal only after metrics hold steady and snapshots stay green across locales and content sizes.

### Accessibility Parity

Reading order, grouping, and hit frames should match between old and new. Preserve `Group` structure and `.accessibilityElement(children:)` settings unless you also update VoiceOver expectations and tests. Roll out behind a remote flag so you can revert if live accessibility metrics regress.

## 5. Guardrails For Correctness Under Load

### Bound Proposals

Two failures are common. Unbounded proposals: a parent passes `nil` for width, and your layout expands children unexpectedly. Cap proposals to a safe maximum or compute intrinsic width first. Recursive sizing: computing a child’s proposal using the same child’s just-measured size in the same pass, which causes extra work and instability.

```swift
enum LayoutGuard {
  static func bounded(_ value: CGFloat?, fallback: CGFloat) -> CGFloat {
    min(value ?? fallback, 1_000_000)
  }
}
let boundedWidth = LayoutGuard.bounded(proposal.width, fallback: 320)
```

### Load Testing In Scroll

Run worst-case datasets in a `ScrollView` or `List`: large text, long strings, images that appear late. Choose `.unspecified` when intrinsic sizing suffices; choose explicit `ProposedViewSize` only when clamping is intended. Validate on device, because small timing differences can trigger additional layout passes during diffing and prefetch.

## Tradeoffs And Pitfalls

- Math must match between `sizeThatFits` and `placeSubviews`. A missing spacing or alignment term produces clipping or overflow in certain locales or with dynamic type.
- Caching is sharp. Cache too aggressively and geometry goes stale when the environment changes; under‑cache and you burn cycles. Prefer caches that are cheap to invalidate.
- Hidden costs show up in `List` and `ScrollView`. These containers may trigger more passes than expected. Keep complexity linear in subviews and avoid quadratic per-item work.
- Feature flags drift without discipline. Bind both paths to the same tests and reviews to keep behavior aligned.
- Accessibility regressions are quiet. Confirm reading order and `.accessibilityElement(children:)` semantics before enabling new layouts broadly.

## Validation & Observability

Measure before merging and after shipping. Use `Instruments` with `Time Profiler` on device and watch `sizeThatFits` and `placeSubviews` hot spots during rapid scrolling. Annotate passes with `OSSignposter` so spikes in measure or place are attributable to specific screens or data.

Add `XCTest` performance tests and enforce budgets with `XCTOSSignpostMetric` so pull requests that inflate layout time fail fast. Emit structured `os_log` breadcrumbs for unexpected fallbacks or cache invalidations to spot churn. Collect diagnostics with `MetricKit` to verify that smoothness and CPU remain stable. Keep a remote flag to throttle rollout or revert quickly when metrics move in the wrong direction.

## Practical Checklist

- [ ] Match math between `sizeThatFits` and `placeSubviews`, including spacing and alignment.
- [ ] Cap unbounded `ProposedViewSize` values; avoid recursive sizing and prefer `.unspecified` unless you intend to clamp.
- [ ] Add caches only when profiling shows benefit; invalidate on content size category, locale, and size class changes.
- [ ] Use `LayoutValueKey` for per-item hints with safe defaults; avoid re-measuring the same values during a pass.
- [ ] Maintain a feature‑flagged fallback with identical API; bind both paths to the same unit and snapshot tests.
- [ ] Signpost measure/place and enforce `XCTOSSignpostMetric` budgets in CI.
- [ ] Profile on device with worst-case datasets in `ScrollView` or `List`.
- [ ] Verify accessibility parity: reading order, grouping, and activation frames.
- [ ] Plan deprecation and remove the fallback once metrics hold and tests stay green.

## Closing Takeaway

`Layout` puts geometry rules where they belong: explicit, reusable, and observable. By separating measurement from placement and keeping proposals sane, you avoid preference ping‑pong and the over-measurement that causes jank. Treat each layout as a design‑system primitive backed by tests, flags, and signposts. Ship incrementally, profile on device, and keep behavior deterministic across locales and data scales. That is how custom layouts scale across teams and screens.

## Swift/SwiftUI Code Example

```swift
import SwiftUI

struct WeightedHStack: Layout {
    struct WeightKey: LayoutValueKey { static let defaultValue: CGFloat = 0 }
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let w = proposal.width
        let sp = CGFloat(max(subviews.count - 1, 0)) * spacing
        if w == nil {
            var totalW: CGFloat = sp, maxH: CGFloat = 0
            for s in subviews {
                let sz = s.sizeThatFits(.unspecified)
                totalW += sz.width; maxH = max(maxH, sz.height)
            }
            return CGSize(width: totalW, height: maxH)
        }
        let weights = subviews.map { $0[WeightKey.self] }
        let totalWeight = weights.reduce(0,+)
        var naturalNonWeighted: CGFloat = 0
        var idealSizes = Array(repeating: CGSize.zero, count: subviews.count)
        for i in subviews.indices where weights[i] == 0 {
            let sz = subviews[i].sizeThatFits(.unspecified)
            idealSizes[i] = sz; naturalNonWeighted += sz.width
        }
        let remaining = max(w! - sp - naturalNonWeighted, 0)
        var laidOutHeights: [CGFloat] = []
        for i in subviews.indices {
            let allocW = weights[i] > 0 && totalWeight > 0 ? remaining * (weights[i] / totalWeight) : idealSizes[i].width
            let childSize = subviews[i].sizeThatFits(.init(width: allocW, height: proposal.height))
            idealSizes[i] = CGSize(width: max(allocW, childSize.width), height: childSize.height)
            laidOutHeights.append(childSize.height)
        }
        return CGSize(width: w!, height: laidOutHeights.max() ?? 0)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let w = bounds.width, sp = spacing
        let weights = subviews.map { $0[WeightKey.self] }
        let totalWeight = weights.reduce(0,+)
        var naturalNonWeighted: CGFloat = 0
        var widths = Array(repeating: CGFloat(0), count: subviews.count)
        for i in subviews.indices where weights[i] == 0 {
            let sz = subviews[i].sizeThatFits(.unspecified)
            widths[i] = sz.width; naturalNonWeighted += sz.width
        }
        let remaining = max(w - sp * CGFloat(max(subviews.count - 1, 0)) - naturalNonWeighted, 0)
        for i in subviews.indices where weights[i] > 0 && totalWeight > 0 {
            widths[i] = remaining * (weights[i] / totalWeight)
        }
        let maxH = subviews.indices.map { subviews[$0].sizeThatFits(.init(width: widths[$0], height: proposal.height)).height }.max() ?? 0
        var x = bounds.minX
        for i in subviews.indices {
            let sz = subviews[i].sizeThatFits(.init(width: widths[i], height: proposal.height))
            let y = bounds.minY + (maxH - sz.height)/2
            subviews[i].place(at: CGPoint(x: x, y: y), proposal: .init(width: widths[i], height: sz.height))
            x += widths[i] + sp
        }
    }
}

extension View {
    func layoutWeight(_ weight: CGFloat) -> some View { layoutValue(key: WeightedHStack.WeightKey.self, value: weight) }
}

struct WeightedHStackDemo: View {
    var body: some View {
        WeightedHStack(spacing: 12) {
            Text("Leading").padding(8).background(.blue.opacity(0.1)).clipShape(.rect(cornerRadius: 6))
            Text("Expands").layoutWeight(2).padding(8).background(.green.opacity(0.1)).clipShape(.rect(cornerRadius: 6))
            Image(systemName: "wifi").resizable().scaledToFit().layoutWeight(1).frame(height: 20).foregroundStyle(.secondary)
            Text("Fixed").padding(8).background(.orange.opacity(0.1)).clipShape(.rect(cornerRadius: 6))
        }
        .frame(maxWidth: .infinity)
        .padding()
    }
}
```

## References

- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
