Converting callback-heavy networking to Swift Concurrency can push cancellation, isolation, and scheduling issues into production — many of these problems only appear under real load.

- Audit `actor` boundaries: use `actor` for long‑lived mutable caches and reserve `@MainActor` for UI‑critical code to avoid unexpected main‑thread serialization.
- Treat `Task.detached` as an escape hatch; prefer `TaskGroup` for structured parallelism so cancellation and priority are more likely to propagate predictably.
- Bridge incrementally with `withCheckedThrowingContinuation` shims and gate changes behind feature flags so you can roll back quickly if needed.
- Add `XCTest` `async` tests that assert cancellation behavior, and correlate test failures with `OSSignposter` spans and Instruments traces during pilot rollouts.

When modules mix concurrency models, prefer incremental, observable rollouts unless you can audit and instrument the full call chain end‑to‑end.

Callouts to use: `TaskGroup`, `OSSignposter`, and Instruments `Time Profiler` for measurement and correlation.

Are you running a migration pilot now? What signal triggered your last rollback?

#Swift #iOSDev #Concurrency #MobileEngineering #iOS
