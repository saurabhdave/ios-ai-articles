I chased a feed that re-rendered repeatedly during scrolling — the root cause was multiple ancestor views each observing the same mutable model and causing redundant diffs.

- Use a single shared `@Observable` model injected via the environment for domain state. Keep ephemeral UI state in `@State`/`@StateObject` so you don't create duplicate observers that trigger repeated renders.
- Prefer a declarative `NavigationStack` for serializable, URL-like routing; when you must interoperate with existing view-controller flows, add a focused bridge and gate it behind a feature flag.
- Replace ad-hoc `DispatchQueue` callbacks with structured concurrency (`Task`, `@MainActor`) so cancellation and lifecycle semantics become easier to reason about and test.
- Instrument render, fetch, and commit boundaries with signposts (os_signpost/os_signpost API) and collect profiler traces during canary rollouts to compare rollout signals.

Choose `NavigationStack` when you want deterministic deep-link behavior; choose an incremental bridge when interoperability is the priority.

What tradeoff surprised you most when moving shared domain state into an `@Observable

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
