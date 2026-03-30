Modifiers that capture mutable state can cause UI surprises under navigation and `List` reuse — treat them as small library contracts, not syntactic sugar.

- Define `ViewModifier` types with explicit inputs, value semantics, and documented invariants; test them inside `List` and during navigation to exercise reuse paths.
- Avoid capturing view‑models or singletons in modifiers; instead pass plain values (IDs, strings) and forward lifecycle callbacks (`onAppear`/`onDisappear`) so behavior remains observable.
- Encode constraints in types (use `Sendable` where appropriate) and validate at construction to reduce runtime surprises.
- During migrations, consider `UIViewRepresentable` shims to compare pixel and behavioral differences on device before switching to a native modifier.
- Choose strict typing when a modifier affects layout or accessibility; choose simpler ergonomics for purely decorative helpers.
- Instrument initialization and expensive work with signposts and structured logging so traces can be correlated with user reports.

Would your team benefit from a modifier audit that includes snapshot tests and signpost instrumentation? Tell me one pain point you see in your modifiers and let’s compare notes.

#SwiftUI #iOSDev #MobileEngineering #iOS #Swift
