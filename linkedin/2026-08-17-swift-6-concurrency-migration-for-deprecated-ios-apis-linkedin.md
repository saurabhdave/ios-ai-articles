Swift concurrency turns “good enough” callbacks into runtime risk. The hard part of migration isn’t syntax—it’s ownership, cancellation, and isolation. If you can’t say where work runs, when it cancels, and who owns the state, you have a raffle, not concurrency.

- Bridge legacy once-only callbacks with `withCheckedThrowingContinuation`; use `AsyncStream` for multi-event delegates. Centralize the bridge and map `Task` cancellation to the underlying work.
- Replace ad‑hoc `DispatchQueue` hops with `Task`/`TaskGroup` scoped to a view or model. Carry

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
