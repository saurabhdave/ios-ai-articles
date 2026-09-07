Actors eliminate data races, not retain cycles. If your actor stores a `Task` whose body captures `self`, you just built a memory leak that won’t crash — it will quietly persist.

- Keep cancellation close to creation: only store a `Task` when you must call `cancel()` across scopes; otherwise make it local and let scope exit drop it.
- Prefer `AsyncStream` for repeating push sources; set `continuation.onTermination` and expose a `stop()` that finishes the stream and removes `NotificationCenter` observers.
- Use `nonisolated` only for methods that truly don’t touch actor state; bounce back into the actor with `await self.method()` when mutation is required.
- Bridge legacy callbacks with `withCheckedThrowingContinuation` and avoid capturing the actor; resume exactly once to prevent pinning tasks.
- Validate lifecycle: add `deinit` that cancels timers/loops (`Task.sleep`) and nils stored closures; assert deallocation in `XCTest`.

Choose a stored `Task` only when you require cross‑scope cancellation; otherwise keep work local to avoid owning lifetimes you can’t reliably terminate.

Trace with `OSSignposter` and `Instruments`, and monitor field behavior

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
