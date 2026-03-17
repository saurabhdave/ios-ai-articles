# Custom SwiftUI Layouts with the Layout Protocol

Build custom SwiftUI layouts with the Layout protocol when you need deterministic, reusable spatial rules that standard stacks and grids can’t express reliably across varying content sizes and accessibility settings. This article explains what you implement, when to choose a custom layout, practical patterns teams ship, and how to test and observe layouts before wider rollout.

## Why This Matters For iOS Teams Right Now

Teams adopting SwiftUI often face two tensions: the desire to use concise built-in containers for readability, and the need for predictable placement and performance across Dynamic Type sizes, orientations, and diverse content. The Layout protocol (available since iOS 16) gives explicit measurement and placement hooks so you can centralize layout math into a single component rather than scattering GeometryReader or preference-key workarounds. That centralization improves testability and makes performance tradeoffs visible.

> Centralize spatial rules where determinism matters; favor built-ins when clarity is more important than control.

## 1. Anatomy Of A Custom Layout

### What You Implement
A minimal custom layout implements two methods: one that measures children and returns an aggregate size, and one that places subviews inside the provided rectangle. Optionally, you can provide a cache factory and an update hook to retain computed metrics across layout passes.

### Key Concepts
- Inspect measurements via each subview’s dimensions.
- Use bounded proposals to avoid overmeasuring.
- Place children with explicit coordinates and anchors to guarantee hit-test and clipping behavior.

### Decision Criterion
Choose a custom layout when:
- The same spatial rule is used across multiple screens.
- You must guarantee consistent behavior across accessibility settings (for example, very large Dynamic Type).
- Existing stack composition, nested geometry readers, or preference keys are fragile or difficult to test.

## 2. Patterns Teams Will Actually Use

### Common Patterns
Teams commonly implement custom layouts for:
- Responsive column and masonry-like grids that compute column widths based on available width.
- Tag or chip flows that wrap lines predictably when content changes.
- Galleries and staggered rows that require per-item offset math.
- Small components (cards, badges) that need consistent visual balance across contexts.

### Practical Guidance
- Prefer a custom Layout for reusable components that appear in many places.
- Prefer composition of HStack/VStack/LazyGrid for single-use, simple layouts to preserve readability.
- Use the cache APIs when per-subview computations are repeated across size passes.

### Quick Checklist
- Is it shared across screens? → Consider a Layout.
- Is the math repeated or expensive? → Add cache.
- Are accessibility variants required? → Test with large Dynamic Type.

## 3. Tradeoffs And Pitfalls

### Common Pitfalls
- Overly permissive measurement proposals cause extra measurements and higher CPU or allocations.
- Omitting or misusing caching leads to repeated expensive computations.
- Incorrect placement math or anchors produces clipping, wrong hit areas, or animation artifacts.

### Operational Tradeoffs
- Predictability vs. simplicity: custom layouts buy control but increase implementation surface and maintenance.
- Reuse vs. local clarity: a shared Layout reduces duplication but must be documented and tested so future maintainers understand the rules.

### Mitigations
- Use bounded proposals and conservative measurement strategies.
- Cache per-subview metrics when computations are non-trivial.
- Validate placement against hit-testing and animation scenarios.

## 4. Testing And Observability For Layouts

### Unit And Visual Tests
- Unit-test the layout math where possible: feed synthetic dimensions and assert positions.
- Create snapshot tests across key breakpoints (compact/regular width, several Dynamic Type sizes) to detect regressions.

### Runtime Profiling
- Instrument heavy code paths with signposts and profile with Instruments (Time Profiler, Allocations).
- Run profiling under realistic content to reveal pathological cases (very long tag lists, many children, large images).

### Production Monitoring
- Gaterollouts (feature flags, phased releases) and monitor existing telemetry for regressions.
- Include accessibility scenarios in CI or manual test runs to ensure large-type and VoiceOver do not break assumptions.

## 5. Implementation Checklist Before Rolling Out A Custom Layout

### Implementation Steps
- Implement the measurement and placement methods; add cache creation and update hooks when needed.
- Use each subview’s dimensions and provide bounded proposals to children.
- Keep non-UI-heavy computations outside the view tree where they can be unit tested.

### Performance And QA Steps
- Add lightweight instrumentation around expensive computations to aid profiling.
- Write unit tests for deterministic geometry decisions and snapshot tests for visual regressions.
- Profile with Instruments on realistic device targets and data sets.

### Rollout And Observability
- Gate the rollout and monitor for CPU and memory regressions.
- Validate VoiceOver and large Dynamic Type settings early and repeatedly.
- Document the layout’s contract and the intended content shapes so future changes are safer.

- Minimal scanning checklist:
 1. Shared behavior? → Layout.
 2. Heavy math? → Cache.
 3. Accessibility required? → Test across sizes.

## Closing Takeaway

Use the Layout protocol to turn fragile spatial logic into a single, testable component when determinism, reuse, or precise measurement control is required. For many straightforward cases, built-in stacks remain the simpler and safer choice. Wherever you adopt a custom layout, invest in caching, tests, and profiling upfront—and stage the rollout so any performance or accessibility regressions are caught early.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

// Simple observable model to drive demo content
@Observable class LabelModel {
    var title: String
    var value: String

    init(title: String = "Account", value: String = "$1,234.56") {
        self.title = title
        self.value = value
    }

    func toggleLongValue() {
        if value.count > 20 {
            value = "$1,234.56"
        } else {
            value = "Recurring payment • Next: March 28 • 12 payments left"
        }
    }

    func toggleLongTitle() {
        if title.count > 20 {
            title = "Account"
        } else {
            title = "Primary Savings — Joint Account (Employer Match)"
        }
    }
}

// Adaptive label layout:
// - Tries to place title and value on one line with flexible spacing.
// - If available width is insufficient for both, places value below title.
// - Respects subview intrinsic sizes and dynamic type.
struct AdaptiveLabelLayout: Layout {
    var spacing: CGFloat = 8

    // Simple cache storing the last measured widths for heuristics (optional)
    struct Cache {
        var lastTitleWidth: CGFloat = 0
        var lastValueWidth: CGFloat = 0
    }

    func makeCache(subviews: Subviews) -> Cache {
        Cache()
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize {
        guard subviews.count >= 2 else {
            // fallback to single child sizing
            return subviews.first?.sizeThatFits(proposal) ?? .zero
        }

        let title = subviews[0]
        let value = subviews[1]

        // Ask children for their ideal sizes with unconstrained width to know natural widths.
        let unconstrainedHeight = proposal.replacingUnspecifiedDimensions().height
        let titleSize = title.sizeThatFits(ProposedViewSize(width: .infinity, height: unconstrainedHeight))
        let valueSize = value.sizeThatFits(ProposedViewSize(width: .infinity, height: unconstrainedHeight))

        cache.lastTitleWidth = titleSize.width
        cache.lastValueWidth = valueSize.width

        let maxWidth = proposal.width ?? (titleSize.width + spacing + valueSize.width)

        // If both fit horizontally within proposed width, return a single-line size.
        if titleSize.width + spacing + valueSize.width <= maxWidth {
            let height = max(titleSize.height, valueSize.height)
            return CGSize(width: min(maxWidth, titleSize.width + spacing + valueSize.width), height: height)
        } else {
            // Stack vertically
            let width = min(maxWidth, max(titleSize.width, valueSize.width))
            let height = titleSize.height + spacing + valueSize.height
            return CGSize(width: width, height: height)
        }
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) {
        guard subviews.count >= 2 else {
            // Place a single child centered
            if let child = subviews.first {
                let childSize = child.sizeThatFits(proposal)
                let origin = CGPoint(x: bounds.minX + (bounds.width - childSize.width) / 2,
                                     y: bounds.minY + (bounds.height - childSize.height) / 2)
                child.place(at: origin, anchor: .topLeading, proposal: ProposedViewSize(width: childSize.width, height: childSize.height))
            }
            return
        }

        let title = subviews[0]
        let value = subviews[1]

        // Measure natural sizes (unconstrained width) to decide layout
        let unconstrainedHeight = proposal.replacingUnspecifiedDimensions().height
        let titleSize = title.sizeThatFits(ProposedViewSize(width: .infinity, height: unconstrainedHeight))
        let valueSize = value.sizeThatFits(ProposedViewSize(width: .infinity, height: unconstrainedHeight))

        let availableWidth = proposal.width ?? bounds.width
        let fitsHorizontally = titleSize.width + spacing + valueSize.width <= availableWidth

        if fitsHorizontally {
            // Place side by side, vertically centered within bounds
            let y = bounds.minY + (bounds.height - max(titleSize.height, valueSize.height)) / 2
            let titleOrigin = CGPoint(x: bounds.minX, y: y)
            title.place(at: titleOrigin, anchor: .topLeading, proposal: ProposedViewSize(width: titleSize.width, height: titleSize.height))

            let valueOrigin = CGPoint(x: bounds.minX + titleSize.width + spacing, y: y)
            value.place(at: valueOrigin, anchor: .topLeading, proposal: ProposedViewSize(width: valueSize.width, height: valueSize.height))
        } else {
            // Stack vertically, left-aligned
            let titleOrigin = CGPoint(x: bounds.minX, y: bounds.minY)
            title.place(at: titleOrigin, anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: titleSize.height))

            let valueOrigin = CGPoint(x: bounds.minX, y: bounds.minY + titleSize.height + spacing)
            value.place(at: valueOrigin, anchor: .topLeading, proposal: ProposedViewSize(width: bounds.width, height: valueSize.height))
        }
    }
}
```

## References

- [SwiftUI](https://developer.apple.com/documentation/swiftui)
- [Swift Documentation](https://www.swift.org/documentation/)
