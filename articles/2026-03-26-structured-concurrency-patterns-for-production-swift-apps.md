# Structured Concurrency Patterns for Production Swift Apps

Converting completion-handler flows to structured-concurrency primitives can shift cancellation semantics in ways that only surface at runtime: leaked child tasks, sockets left open, and inconsistent UI state under load. This article gives practical, production-minded patterns to migrate incrementally, observe effects, and roll back safely when a change causes regressions.

## Why This Matters For iOS Teams

Mixing callback-based networking, `Combine` pipelines, and `async`/`await` can create subtle compatibility gaps. Those gaps may show up as resource leaks, increased latency, and UI stalls that occur only under realistic traffic or on constrained devices. Observability and deterministic tests help detect regressions quickly and reduce mean time to recovery during staged rollouts.

> Small, incremental migrations with tracing and bounded rollouts reduce blast radius far more than a one-time big refactor.

## 1. Structured Concurrency Fundamentals

### Task Ownership And Grouping
Use `Task` for a unit of work owned by a lifecycle object and `TaskGroup` for fan-out/fan-in that should cancel together. Avoid `Task.detached` from UI code because it removes actor isolation and detaches work from owner-controlled lifetimes.

Anti-pattern:
```swift
Task.detached {
 try await performHeavyWork()
}
```

Preferred pattern:
```swift
class ViewModel {
 var task: Task<Void, Error>?

 func load() {
 task = Task { @MainActor in
 try await fetchAndUpdate()
 }
 }

 deinit { task?.cancel() }
}
```

Choose `Task` when work must be cancellable by a specific owner (for example, a view model); choose `TaskGroup` when you need parallel requests and aggregated results with automatic cancellation on first failure. Validate cancellation paths before rollout; a task that cannot be cooperatively cancelled can continue consuming CPU and other resources. Instrument entry and exit of groups (for example, with signposts) to correlate dropped work with lifecycle events.

## 2. Cancellation And Lifetimes

### Cooperative Cancellation And Cleanup
Cancellation in structured concurrency is cooperative. Use `withTaskCancellationHandler`, propagate `CancellationError` where appropriate, and call `Task.cancel()` from owners to request cancellation and allow cleanup to run.

Anti-pattern:
```swift
class ViewModel {
 var task: Task<Void, Never>?
 deinit { /* assume task stops */ }
}
```

Preferred pattern:
```swift
task = Task {
 await withTaskCancellationHandler {
 // cleanup: close sockets, release resources
 } operation: {
 try Task.checkCancellation()
 try await performNetworkWork()
 }
}
```

Choose explicit cancellation from navigation handlers when an owner is torn down; choose graceful cooperative cancellation when tasks hold resources that require cleanup. Add async `XCTest` tests to simulate navigation and confirm cancellation triggers cleanup within a bounded timeout so regressions are caught early.

## 3. Interop With Legacy Callbacks And Combine

### Checked Continuations And Main-Actor Boundaries
Bridging callbacks can be a source of deadlocks and double-resumes. Use `withCheckedThrowingContinuation` or `withCheckedContinuation` to ensure single-resume semantics, and mark UI entry points with `@MainActor` (or ensure state updates occur on the main actor) to preserve main-thread invariants.

Anti-pattern:
```swift
func load(completion: @escaping (Result<Data, Error>) -> Void) { /* legacy */ }
```

Preferred pattern:
```swift
func fetchLegacyData() async throws -> Data {
 try await withCheckedThrowingContinuation { continuation in
 legacyFetch { result in
 switch result {
 case .success(let data): continuation.resume(returning: data)
 case .failure(let error): continuation.resume(throwing: error)
 }
 }
 }
}
```

Choose `withCheckedThrowingContinuation` when the callback can return an error; choose `withCheckedContinuation` for non-throwing bridges. Run wrapper tests under Thread Sanitizer and with deterministic fake network stubs to catch double-resume and never-resume bugs before rollout. Mark the async wrapper `@MainActor` if it mutates UI-visible state and add unit tests that exercise every callback path.

## 4. Networking, Backpressure, And Resource Patterns

### Bounded Concurrency And Retry Strategies
Unbounded parallel requests can exhaust sockets and battery. Prefer `URLSession.data(for:)` and `withThrowing`TaskGroup`` or a bounded queue to control concurrency. Implement retry strategies with backoff and jitter where appropriate.

Preferred pattern:
```swift
await withThrowingTaskGroup(of: Data.self) { group in
 for endpoint in endpoints {
 group.addTask { try await URLSession.shared.data(for: endpoint).0 }
 }
 for try await data in group { process(data) }
}
```

Choose `TaskGroup` when you need structured cancellation across multiple requests; choose a bounded semaphore or custom queue when the number of endpoints can be large. Instrument retry and cancellation counts in telemetry so you can detect increases in socket errors or retries after a change. Gate heavy tracing and high-cardinality metrics behind a rollout flag to avoid telemetry noise during incremental deployment.

## Tradeoffs And Pitfalls

Structured concurrency improves ownership clarity but can surface latent issues during refactor. Watch for synchronous logging inside hot async paths — it can induce contention and obscure real latency. Avoid creating global long-lived `Task` instances without explicit owners; they bypass lifecycle controls and are hard to cancel.

Failure modes to plan for:
- Orphaned tasks continuing to consume sockets and CPU.
- Double-resume or never-resume continuations causing hangs.
- Priority inversion when background tasks use inappropriate Quality of Service settings.

Prepare rollback criteria and dashboards before shipping so a staged rollback can be executed quickly if post-release signals indicate a regression.

## Validation & Observability

### Traces, Logs, And Post-Release Signals
Instrument async handoffs and hot paths. Use signposts for boundary marks, structured logging for correlated events, and collect post-release telemetry to detect regressions. Run Instruments on CI for early regressions where feasible.

Decision guidance: add signposts around entry, start of fan-out, completion of fan-in, and cancellation. Run Time Profiler and Allocations traces on CI smoke runs to catch CPU and heap regressions before delivery. Correlate signpost events with log identifiers in dashboards so you can answer "who started this task, who cancelled it, and why" without guessing from sparse logs. Gate heavy traces and high-cardinality metrics with rollout flags to reduce noise and limit privacy exposure.

Add async `XCTest` tests that assert both completion and cancellation within bounded timeouts, and collect post-release telemetry after staged deploys to detect increased CPU, memory, or crashes.

## Practical Checklist

- [ ] Identify UI and background entry points and mark UI entry points with `@MainActor` or ensure observer-state updates occur on the main actor.
- [ ] Replace critical callback paths with `withCheckedThrowingContinuation` wrappers and add unit tests covering resume and error paths.
- [ ] Introduce `TaskGroup` or a bounded concurrency queue for parallel work and cancel outstanding tasks on `deinit` or navigation.
- [ ] Add signpost trace points and structured logs for key async handoffs; gate telemetry with a rollout flag.
- [ ] Create async `XCTest` tests asserting cancellation behavior and time-bounded completion; run Instruments (Time Profiler, Allocations) on CI smoke runs where feasible.
- [ ] Define rollout gates and dashboards that use post-release telemetry and traces to detect regressions.

## Closing Takeaway

Structured concurrency clarifies ownership and reduces many classes of race conditions, but migration is an operational effort that must be incremental. Start by wrapping a single critical callback with a checked continuation, add trace points and async `XCTest` coverage, and gate rollout with telemetry-backed dashboards. These small, measurable steps reduce release risk and make regressions easier to reproduce and investigate.

## Swift/SwiftUI Code Example

```swift
import Foundation
import Observation
import SwiftUI

// ❌ Before — legacy callback API that returns a cancellable token (pseudo)
// func loadResource(url: URL, completion: @escaping (Result<Data,Error>)->Void) -> CancellableToken

// ✅ After — structured-concurrency adapter that honours Task cancellation
protocol CancellableToken { func cancel() }
final class LegacyClient {
    // Simulated legacy API (not used directly here)
    func loadResource(url: URL, completion: @escaping (Result<Data, Error>) -> Void) -> CancellableToken { DummyToken() }
    private class DummyToken: CancellableToken { func cancel() {} }
}

@Observable final class ResourceLoader {
    var data: Data? = nil
    var error: String? = nil

    private let client = LegacyClient()

    @MainActor func load(url: URL) async {
        do {
            let result = try await adaptLegacyLoad(url: url)
            data = result
            error = nil
        } catch {
            data = nil
            error = "\(error)"
        }
    }

    private func adaptLegacyLoad(url: URL) async throws -> Data {
        try await withTaskCancellationHandler {
            // on cancel: nothing here — cancellation handled by continuation's onCancel below
        } operation: {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Data, Error>) in
                let token = client.loadResource(url: url) { result in
                    switch result {
                    case .success(let d): continuation.resume(returning: d)
                    case .failure(let e): continuation.resume(throwing: e)
                    }
                }
                Task { @MainActor in
                    // observe Task cancellation and cancel underlying token to avoid leaks
                    await Task.yield()
                    if Task.isCancelled { token.cancel() }
                }
            }
        }
    }
}

struct LoaderView: View {
    @State private var loader = ResourceLoader()
    @Bindable private var _loader = ResourceLoader() // @Bindable only in view (illustrative)
    var body: some View { Text("Demo") }
}
```

## References

- [Swift 6.3](https://www.swift.org/blog/swift-6.3-released/)
- [Swift 6.3 Released](https://swift.org/blog/swift-6.3-released/)
- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [Swift Documentation](https://www.swift.org/documentation/)
