Converting callback-heavy flows to structured concurrency often changes cancellation and lifetime semantics — and those differences frequently show up at runtime as leaked tasks, lingering requests, or UI races.

- Use `withTaskGroup` to bind children to the caller and aggregate results; add unit tests that assert group cancellation and result ordering.
- Bridge single-callback APIs with `withCheckedThrowingContinuation` and guard against multiple resumes to avoid retained continuations.
- Add cooperative checks with `Task.isCancelled` and validate that cancelled flows stop network/timer work.
- Limit concurrency with batching or a `DispatchSemaphore` around `withTaskGroup` to avoid spikes in memory or CPU.
- Instrument async boundaries with signposts, structured logs, and focused Instruments runs as you migrate pieces of code.

Prefer `Task.detached` only when work truly must outlive the caller.

How have you validated cancellation and lifetime behavior during an incremental migration to structured concurrency? What test or instrumentation caught the hardest bug for you?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
