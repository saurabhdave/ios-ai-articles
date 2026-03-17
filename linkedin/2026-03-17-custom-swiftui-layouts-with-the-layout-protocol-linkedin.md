If your UI breaks at large Dynamic Type or your GeometryReader-based hacks are hard to maintain, consider moving spatial rules into a single custom SwiftUI Layout.

The Layout protocol provides explicit measure/place hooks so you can centralize deterministic layout math, improve testability, and make layout costs easier to reason about.

Practical takeaways:
- Centralize repeated spatial rules in a custom Layout to reduce duplication and surface area for bugs.
- Use bounded ProposedViewSize and the Layout cache to avoid overmeasuring and repeated work.
- Snapshot a few key breakpoints (compact/regular, several Dynamic Type sizes) and profile with Instruments before rollout.
- For simple, one-off compositions, prefer HStack/VStack/LazyGrid to keep code readable.

Tradeoff: custom Layouts increase implementation surface. Choose them when reuse, accessibility stability, or predictable performance make the added maintenance worthwhile.

Curious how you decide when to extract a Layout versus composing stacks—what rules do you use?

#SwiftUI #iOSDev #Accessibility #Architecture #Instruments
