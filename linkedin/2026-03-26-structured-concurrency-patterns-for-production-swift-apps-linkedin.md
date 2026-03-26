Structured-concurrency migrations can change cancellation semantics in subtle ways — those differences often surface under load as leaked tasks, open sockets, or UI inconsistencies.

Start small: wrap a critical callback with `withCheckedThrowingContinuation`, add unit tests for both resume and never-resume paths, then run Instruments and Thread Sanitizer while exercising those tests.

Use an owner-bound `Task` for per-view lifetimes and `TaskGroup` (or a bounded queue) for fan-out; cancel owner tasks in `deinit` or navigation handlers to avoid orphaned work.

Instrument async handoffs with `OSSignpost` and structured logs. Gate high-cardinality telemetry behind rollout flags so you can detect regressions without overwhelming noise.

Add async `XCTest` assertions for completion and cooperative cancellation within time bounds, and correlate CI test failures with runtime traces after release.

Prefer `Task` when work must be owned and cancellable by a lifecycle object; prefer `TaskGroup` when a set of parallel requests should cancel together.

What migration surprised you most — hidden resource leaks, unexpected cancellation behavior, or resume issues? Share the metric, signal, or dashboard you used to catch it.

#Swift #iOSDev #Concurrency #SwiftUI #iOS
