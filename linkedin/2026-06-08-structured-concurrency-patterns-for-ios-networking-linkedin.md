Converting callbacks to `async`/`await` is a semantics change — not just a syntax rewrite. Cancellation, lifetimes, and concurrency boundaries can change runtime behavior and allow network work to continue past a view's lifetime.

Tie UI requests to lifecycle-scoped `Task` (cancel on dismiss) or use `TaskGroup` for bounded fan-out; avoid spawning anonymous `Task` from view controllers when you expect strict cancellation.

Propagate `Task` cancellation into the underlying `URLSessionTask` using `withTaskCancellationHandler` or explicit cancel calls, and consider both cooperative timeouts and `URLSessionConfiguration` timeouts to bound request duration.

Use `TaskGroup` or a bounded worker pool pattern to limit in-flight requests and collect partial results as `Result` values so successes are preserved while failures are reported.

Make shared caches `actor`-owned to reduce data races and publish UI state via observable patterns so views can react to changes safely.

Choose detached work (e.g., retries that must outlive UI dismissal) and lifecycle-bound `Task` when you require strict cancellation on teardown — pick the model that matches lifetime requirements.

Validate changes with async XCTest cancellation tests and add instrumentation around `URLSession` calls and `withCheckedThrowingContinuation` boundaries to observe cancellation and resource usage.

Question for the thread: how have you validated cancellation and resource limits when migrating networking paths to structured concurrency?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
