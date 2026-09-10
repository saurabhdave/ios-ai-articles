Real-time SwiftUI can stutter under bursty feeds due to unbounded buffers, main-actor hot paths, or tasks that outlive their owners. Model each live source as an `AsyncSequence` with explicit buffering, cancellation, and isolation.

- Expose feeds via `AsyncStream`/`AsyncThrowingStream` with `.bufferingOldest(N)`; call `finish()` on teardown and test “no emit after cancel.”
- Consume in views with `task(id:)`; keep mutations on the `@MainActor` and check `Task.isCancelled` inside loops.
- Bridge delegates and legacy publishers at repository boundaries into `AsyncStream` so views subscribe to one model.
- Coalesce and parse off-main; hop back only for UI. Add `OSSignposter` around parse → diff → render to spot stalls.
- 🧪 Add async tests for cancel-after-start and run burst scenarios in Instruments;

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
