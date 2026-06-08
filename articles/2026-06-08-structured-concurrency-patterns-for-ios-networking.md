# Structured Concurrency Patterns for iOS Networking

Converting completion-handler networking into `async`/`await` often shifts runtime semantics: cancellation may no longer reach `URLSession` tasks, requests can outlive view lifecycles, and unbounded concurrency increases resource pressure. These are the failure modes we targeted when migrating a heavy `URLSession` layer—fixes focused on cancellation propagation, lifetime semantics, and bounded concurrency rather than only syntactic changes.

## Why This Matters For iOS Teams

`async`/`await`, `Task`, and `TaskGroup` clarify control flow but move cancellation, lifetime, and affinity decisions into the Swift concurrency runtime. A naive migration can leave `URLSessionTask` instances running after UI elements are dismissed, increase concurrent connections, or change request ordering under load. Instrumentation and staged rollouts with cancellation-focused tests are essential to detect timing-dependent regressions that appear only under production-like traffic.

> Treat the migration as a semantics change: ensure cancellation and lifetimes map to your runtime expectations, not just your source shape.

## 1. Understanding Structured Concurrency Basics

### Task Lifetimes And View Scopes
API: `Task`, `TaskGroup`, `URLSession`

Scattering anonymous `Task` blocks inside view controllers is an anti-pattern because requests can outlive the intended UI lifecycle. Choose `Task` attached to a lifecycle owner when UI-driven requests must cancel on dismissal; choose `TaskGroup` when you need bounded fan-out work whose lifetime should be tied to a parent scope.

Attach `Task` instances to a lifecycle owner (for SwiftUI, create `Task` in lifecycle callbacks tied to observable state and cancel in `onDisappear`) or use structured `TaskGroup` for fan-out work that must be bounded. Validate with XCTest async tests that assert cancellation behavior and add tracing on request start and cancel so short-lived UI-driven launches do not persist after the view disappears before a wider rollout.

## 2. Cancellation, Timeouts, And Resource Management

### Propagating Cancellation To URLSession
API: `Task.isCancelled`, `withTaskCancellationHandler`, `URLSession.dataTask(with:)`

Assuming that `Task` cancellation automatically closes the underlying `URLSessionTask` is an anti-pattern. Choose explicit propagation when requests are UI-facing and must cancel on dismissal; choose detached tasks with explicit QoS and cancellation semantics for background retries or work that should outlive the immediate UI.

Explicitly cancel the `URLSessionTask` when the surrounding `Task` is cancelled and add timeouts at both `URLSessionConfiguration` and cooperative `Task` levels. Use `withTaskCancellationHandler` or check `Task.isCancelled` inside long-running logic and call `URLSessionTask.cancel()` promptly. Set `timeoutIntervalForRequest` and `timeoutIntervalForResource` in `URLSessionConfiguration` to bound OS-level resources. Validate cancellation paths with unit tests and tracing so a task that cannot be cancelled does not leak CPU or battery.

Example adapter demonstrating cancellation propagation:
```swift
import Foundation

actor NetworkClient {
  let session: URLSession

  init(session: URLSession = .shared) {
    self.session = session
  }

  func fetchData(from url: URL) async throws -> (Data, URLResponse) {
    try await withCheckedThrowingContinuation { continuation in
      let task = session.dataTask(with: url) { data, response, error in
        if let error = error {
          continuation.resume(throwing: error)
          return
        }
        guard let data = data, let response = response else {
          continuation.resume(throwing: URLError(.badServerResponse))
          return
        }
        continuation.resume(returning: (data, response))
      }

      // Cooperatively cancel the URLSessionTask if the surrounding Task is cancelled.
      Task {
        if Task.isCancelled {
          task.cancel()
        }
      }

      task.resume()
    }
  }
}
```

Test adapters for every continuation path: ensure continuations are never resumed more than once and are always resumed on error paths.

## 3. Composition Patterns And Error Handling

### Bounded Parallelism With `TaskGroup`
API: `TaskGroup`, `Result`

Launching many async calls ad-hoc and awaiting each independently is an anti-pattern because it can blow out concurrent connections and resource usage. Choose `TaskGroup` when you want automatic sibling cancellation on a fatal error and deterministic aggregation; choose a bounded worker pool or semaphore-like approach when you must strictly limit in-flight connections to avoid connection pressure.

`TaskGroup` cancels remaining children automatically when a child throws if you propagate the error; design your aggregation to preserve partial successes using a typed enum or `Result` collection. Add tests that assert `TaskGroup` cancels remaining children when one child fails and verify that aggregated results preserve partial successes where appropriate. Run profiling during stress tests to validate CPU and connection limits.

## 4. Adapters And Incremental Migration

### Wrapping Legacy Callbacks Safely
API: `withCheckedThrowingContinuation`

Replacing an entire networking layer in a single change is an anti-pattern. Choose an incremental adapter approach when you need low-risk rollout; choose a full rewrite only when you can afford the broad integration testing and observability lift.

Wrap legacy callback APIs at module boundaries with `withCheckedThrowingContinuation` and convert consumers module-by-module. Unit test continuations with negative tests that simulate cancellation, double-resume, and never-resume cases. Annotate adapters with correlation identifiers in logs and traces so you can follow a request through mixed legacy and `async`/`await` call chains in production traces.

## 5. Actor Isolation And Shared State

### Making Caches Safe With Actors
API: `actor`, `@Observable`

Shared mutable caches accessed from concurrent `Task`s without protection are an anti-pattern. Choose an `actor` when the cache is mutated by multiple concurrent tasks; choose read-through or copy-on-read strategies inside the actor for read-heavy workloads to reduce contention.

Make the cache an `actor` and push mutation behind the actor boundary; publish UI-observed state through observable patterns such as `@Observable`. Add unit tests that simulate concurrent access and use profiling tools during stress testing to detect contention or unexpected thread switching. Instrument contention hotspots and validate under load before rolling changes wide.

## Tradeoffs & Pitfalls

Structured concurrency reduces callback nesting but increases coupling to the concurrency runtime. Maintaining both legacy callback paths and new `async`/`await` adapters increases maintenance cost; plan a migration timeline that balances risk and developer velocity. Tracing and structured logs add operational noise—balance fidelity with storage and alerting costs. Over-abstraction of concurrency layers can hide lifecycle coupling and create leaks. If you use `Task.detached`, set QoS explicitly to make task intentions clear. Missing observability is a common root cause of production regressions after migration.

## Validation And Observability

Instrument converted paths before rollout. Write XCTest async tests that assert cancellation and ordering invariants, including negative cases that simulate early cancellation. Add tracing to mark request start, cancel, and finish boundaries so traces span async hops. Emit structured logs with a correlation id to connect logs to traces. Run profiling for time and allocation to detect CPU spikes and leaks during stress testing. Use canary rollout metrics and logs as a gate to catch latency or failure-rate regressions before wide release. Require tracing and metric coverage for any converted network path before wider rollout.

## Practical Checklist

- [ ] Wrap legacy callback APIs with `withCheckedThrowingContinuation` at module boundaries.
- [ ] Tie UI requests to lifecycle-scoped `Task` and cancel in `onDisappear` / equivalent.
- [ ] Propagate `Task` cancellation to `URLSessionTask` and set `URLSessionConfiguration` timeouts.
- [ ] Use `TaskGroup` or bounded worker pools to limit concurrent connections.
- [ ] Make shared caches an `actor`; publish UI state with `@Observable`.
- [ ] Add tracing spans and structured log correlation ids before canary rollout.
- [ ] Include XCTest cancellation and ordering tests plus profiling runs in pre-rollout validation.

## Closing Takeaway

Migrating to structured concurrency is a semantics migration as much as a code rewrite. Treat cancellation propagation, actor isolation, and observability as first-class design points and gate rollouts on tracing and metrics. With deliberate adapter boundaries, explicit cancellation, and bounded concurrency, `async`/`await` can deliver clearer code with predictable runtime behavior.

## Swift/SwiftUI Code Example

```swift
import Foundation
import SwiftUI
import Observation

@Observable
@MainActor
class NetworkViewModel {
    var data: Data?
    var error: Error?
    private var currentTask: Task<Void, Never>?

    func load(_ url: URL) {
        currentTask?.cancel()
        currentTask = Task { [weak self] in
            guard let self = self else { return }
            do {
                let (fetchedData, _) = try await URLSession.shared.data(from: url)
                self.data = fetchedData
            } catch {
                if Task.isCancelled { return }
                self.error = error
            }
        }
    }

    func cancel() {
        currentTask?.cancel()
        currentTask = nil
    }
}

struct NetworkView: View {
    @State private var viewModel = NetworkViewModel()
    let url: URL

    var body: some View {
        VStack {
            if let data = viewModel.data {
                Text("Loaded \(data.count) bytes")
            } else if viewModel.error != nil {
                Text("Failed")
            } else {
                Text("Idle")
            }
        }
        .task(id: url) {
            viewModel.load(url)
        }
        .onDisappear {
            viewModel.cancel()
        }
    }
}
```

## References

- [Announcing the Networking Workgroup](https://swift.org/blog/announcing-networking-workgroup/)
- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [URLSession](https://developer.apple.com/documentation/foundation/urlsession)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
