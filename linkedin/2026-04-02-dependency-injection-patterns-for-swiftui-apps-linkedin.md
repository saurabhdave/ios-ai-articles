Converting globals to injectables often surfaces runtime surprises: missing `@Environment` values, duplicated `ObservableObject` owners, or cache/state mismatches that only appear down rare navigation paths.

- Use `Environment` for small, UI-bound values (formatters, layout flags); add tests that inject controlled `EnvironmentValues` and validate common composition roots.
- Prefer constructor injection for view-owned state (`ObservableObject`) so lifecycle and mutation intent are explicit; include navigation tests that exercise creation and deallocation paths.
- Use a lightweight `AppContainer` with factory closures for runtime swapping and scoped factories; keep registries rare and documented.
- Mark UI-facing mutable state with `@MainActor` or encapsulate shared state in an `actor` to clarify concurrency boundaries and reduce unexpected contention.

Choose view-level constructor injection when the model should follow the View lifecycle; choose app-scoped singletons only when you truly need a single source of truth.

Instrument resolver and lifecycle events with signpost-style tracing and validate behavior on device with Instruments (Time Profiler, Allocations).

How have you validated service ownership and lifecycle across navigation paths in a large SwiftUI codebase? Share specific tests, tracing tactics, or debugging patterns you've found reliable.

#SwiftUI #iOSDev #Architecture #Concurrency #iOS
