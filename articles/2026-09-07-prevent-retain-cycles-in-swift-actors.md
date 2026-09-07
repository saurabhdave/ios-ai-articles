# Prevent Retain Cycles in Swift Actors

Actors make race conditions vanish, but they won’t manage object graphs for you. Subtle retain cycles can pin actors in memory long after a feature ends, especially when tasks, timers, or closures capture `self` under the hood. The fixes are design choices: who owns cancellation, how termination happens, and how you prove it in tests and profiling.

> Actors eliminate data races for their isolated state, not responsibility for object lifetimes. You still own the lifecycle graph.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters
Retain cycles inside actors rarely produce crashes or loud failures. They manifest as silent memory growth, delayed resource tear‑down, and background work that never stops. After adopting `async/await`, cancellation semantics and task ownership often shift; long‑lived `Task`s can outlive their owners if you store them without clear shutdown rules. Detached loops and background producers are particularly risky, because they keep strong references until explicitly canceled.

Be disciplined about ownership. Decide which work you cancel, how you terminate it, and how you verify `deinit` runs in reliable tests and profiling sessions.

## 1. How Retain Cycles Happen With Actors
### Store Only The Work You Must Control
A common antipattern is storing a `Task` property whose body strongly captures the actor. The actor retains the `Task`; the `Task` retains `self`; nothing is released. `URLSession` calls that never finish and loops that never cancel are typical symptoms.

```swift
// ❌ Before: stored task body captures the actor
actor DownloadCoordinator {
  private var inFlight: Task<Void, Never>?

  func start(url: URL) {
    inFlight = Task { [weak self] in
      guard let self else { return }
      try? await self.performDownload(url)
    }
  }

  private func performDownload(_ url: URL) async throws {
    _ = try await URLSession.shared.data(from: url)
  }
}
```

Prefer keeping `Task {}` locals when you don’t need `cancel()` or observation. Choose a local `Task` when the work can be abandoned with scope exit; choose a stored `Task` handle when you must cancel or observe completion across scopes. Validate teardown on both success and cancellation paths before rollout; a task that cannot be canceled leaks CPU and battery.

```swift
// ✅ After: store handle, isolate work outside the actor
actor DownloadCoordinator {
  private var inFlight: Task<Void, Never>?

  func start(url: URL) {
    inFlight = Task { [weak self] in
      guard let self else { return }
      try? await Self.download(url: url, onResult: { data in
        await self.didDownload(data)
      })
    }
  }

  private static func download(
    url: URL,
    onResult: @Sendable (Data) async -> Void
  ) async throws {
    let (data, _) = try await URLSession.shared.data(from: url)
    await onResult(data)
  }

  private func didDownload(_ data: Data) {
    // mutate actor state
  }

  func shutdown() {
    inFlight?.cancel()
    inFlight = nil
  }
}
```

## 2. Breaking Cycles Inside Actor Internals
### Use `nonisolated` Sparingly And Teardown Deterministically
If a callback doesn’t need actor state, mark it `nonisolated` to avoid capturing `self`. For stored closures that must touch state, capture weakly and bounce back into the actor with `await`. Keep `deinit` focused on canceling and nil‑ing references so Instruments shows timely deallocation.

```swift
actor Heartbeat {
  private var tick: Task<Void, Never>?
  var onBeat: (@Sendable () -> Void)?

  nonisolated func didConnect() {
    // no actor state here
  }

  func start() {
    tick = Task { [weak self] in
      guard let self else { return }
      while !Task.isCancelled {
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        await self.emit()
      }
    }
  }

  private func emit() async {
    onBeat?()
  }

  deinit {
    tick?.cancel()
    onBeat = nil
  }
}
```

Choose `nonisolated` when a method never reads or writes isolated state; choose an isolated funnel method (for example, `await self.method()`) when state mutations are required. Audit `nonisolated` during review to catch accidental state access that compilers won’t always flag, and ensure `deinit` consistently cancels periodic work like `Task.sleep` loops.

## 3. Interop With Timers, Notifications, And Streams
### Prefer `AsyncStream` With Explicit Termination
Timer‑like producers and `NotificationCenter` often retain their handlers. Keep them outside the actor or capture weakly, and ensure termination is explicit via `AsyncStream` and `onTermination`. That way, teardown can remove observers and finish streams when the feature ends.

```swift
actor LocationBroker {
  private var streamTask: Task<Void, Never>?
  private var stopStream: (() -> Void)?

  func start() {
    let (stream, stopper) = Self.makeNotificationStream(name: .NSSystemTimeZoneDidChange)
    stopStream = stopper
    streamTask = Task { [weak self] in
      guard let self else { return }
      for await _ in stream {
        await self.refresh()
      }
    }
  }

  func stop() {
    streamTask?.cancel()
    stopStream?()
    streamTask = nil
    stopStream = nil
  }

  private func refresh() async {
    // update actor state
  }

  static func makeNotificationStream(
    name: Notification.Name
  ) -> (AsyncStream<Void>, () -> Void) {
    var continuation: AsyncStream<Void>.Continuation?
    let token = NotificationCenter.default.addObserver(
      forName: name, object: nil, queue: nil
    ) { _ in
      continuation?.yield(())
    }

    let stream = AsyncStream<Void> { cont in
      continuation = cont
      cont.onTermination = { @Sendable _ in
        NotificationCenter.default.removeObserver(token)
      }
    }

    return (stream, {
      NotificationCenter.default.removeObserver(token)
      continuation?.finish()
    })
  }
}
```

Choose `AsyncStream` when events repeat or termination must be explicit; choose a local `Task.sleep` loop when a simple periodic tick suffices and no external lifetime is needed. Test that `stop()` is idempotent because repeated teardown is common during rapid navigation and mode changes.

## 4. Bridging Legacy Closures And Structured Concurrency
### Use `withCheckedThrowingContinuation` Without Capturing The Actor
When wrapping callback‑style APIs, don’t retain the actor in the closure. Capture the continuation, resume exactly once, and return. Let the caller’s task own cancellation, and avoid `Task.detached` unless you must break actor inheritance.

```swift
actor ImageLoader {
  func fetch(_ url: URL) async throws -> Data {
    try await withCheckedThrowingContinuation { cont in
      legacyFetch(url) { data, error in
        if let error {
          cont.resume(throwing: error)
        } else if let data {
          cont.resume(returning: data)
        } else {
          cont.resume(throwing: URLError(.badServerResponse))
        }
      }
    }
  }

  // Legacy — bridged by the actor; implementation not shown
  private func legacyFetch(_ url: URL, completion: @Sendable (Data?, Error?) -> Void) {
    // call completion later
  }
}
```

Choose `withCheckedThrowingContinuation` for one‑shot results; choose `AsyncStream` for repeating events that require clean termination. In rollout, trace whether continuations complete by adding lightweight counters or logs to catch missing resumes before they pin tasks indefinitely.

## 5. Store Handles Intentionally, Not Habitually
### Keep Cancellation Close To Creation
Every stored `Task` or closure is a lifetime promise. If you keep it, you cancel it — across success, failure, and navigation. `URLSession.data(for:)` prefetches are a typical case where a stored handle lets you cancel when a view disappears.

```swift
actor FeedCoordinator {
  private var prefetch: Task<Void, Never>?

  func viewAppeared() {
    prefetch = Task { [weak self] in
      guard let self else { return }
      await self.fillCache()
    }
  }

  func viewDisappeared() {
    prefetch?.cancel()
    prefetch = nil
  }

  private func fillCache() async {
    // pre-warm via URLSession.data(for:) calls
  }
}
```

Choose a stored handle when you need explicit `cancel()` or observation across view transitions; choose a local `Task` when speculative work can be abandoned automatically. Assert in tests that `viewDisappeared()` followed by dropping the last strong reference leads to `deinit` after a brief sleep so cancellations can drain.

## Tradeoffs And Pitfalls
Weak captures break cycles but can hide logic bugs when `self` vanishes mid‑operation. If the work must complete, design for backpressure or explicit cancellation and report it upstream instead of returning early on `nil`.

`nonisolated` reduces capture risk, but it also forbids touching isolated state. Overuse spreads logic across isolation boundaries and can reintroduce concurrency bugs, so keep `nonisolated` narrow and well‑audited.

Stored `Task` references make lifetimes fragile. If you store, you own all teardown paths, including early returns on error. Failing to cancel can keep pipelines — networking, parsing, caching — alive longer than intended.

Cancellation is cooperative. Even with `async/await`, add periodic `Task.isCancelled` checks in long loops and CPU‑heavy phases to release references sooner.

## Validation And Observability
- Use `XCTest` async expectations to write lifetime tests: create an actor, run a happy‑path operation, call `shutdown()` or the relevant stop API, drop the strong reference, then await a short sleep and assert the weak ref is `nil`.
- Inspect with Instruments Allocations and Leaks: drive high‑load scenarios (rapid navigation, streaming, background work). Ensure actor `deinit` events align with feature exits and that there are no growing retained cycles.
- Add `OSSignposter` marks for actor init, task start/finish, and deinit so you can correlate timelines with user actions and network phases.
- Add structured logs that include task identifiers and actor roles around start/stop to debug mismatched lifetimes in CI and on‑device.
- Watch rollout using `MetricKit` memory‑pressure terminations and hang diagnostics to catch leaks that don’t crash.

```swift
import os
import XCTest

final class ActorLifetimeTests: XCTestCase {
  func testCoordinatorDeallocates() async {
    weak var weakRef: AnyObject?
    do {
      let signposter = OSSignposter(subsystem: "com.example.app", category: "lifecycle")
      let sid = signposter.makeSignpostID()
      var strong: DownloadCoordinator? = DownloadCoordinator()
      signposter.emitEvent("init", id: sid)
      await strong?.start(url: URL(string: "https://example.com")!)
      await strong?.shutdown()
      weakRef = strong
      strong = nil
      signposter.emitEvent("released", id: sid)
    }
    try? await Task.sleep(nanoseconds: 50_000_000)
    XCTAssertNil(weakRef)
  }
}
```

Gate promotion with leak tests under stress and verify signposted timelines match navigation and teardown.

## Practical Checklist
- [ ] Audit actor properties: remove or make weak any stored closures that reference the actor; avoid storing `Task`s whose bodies capture `self`.
- [ ] Add `deinit` to each actor that stores tasks or closures; call `cancel()` and nil out delegates and closures.
- [ ] Prefer `AsyncStream` for push sources and set `continuation.onTermination`; provide a stored “stop” closure and call it from `stop()` and `deinit`.
- [ ] Replace in‑actor timers with external producers or capture the actor weakly and cancel on teardown.
- [ ] Bridge callbacks with `withCheckedThrowingContinuation` and avoid capturing `self` inside legacy callbacks.
- [ ] Avoid `Task.detached` by default; if used, set an appropriate priority, check `Task.isCancelled`, and define a clear ownership boundary.
- [ ] Write `XCTest` lifetime tests that assert actors deallocate after `shutdown()` and scope exit.
- [ ] Add `OSSignposter` marks around actor init/teardown and task start/finish; validate in Instruments under load.

## Closing Takeaway
Actors give you data‑race safety, not lifetime safety. If an actor stores a `Task`, timer, or closure that captures it, you created a cycle you now must break. Keep tasks local unless you truly need cancellation, prefer `AsyncStream` with explicit termination for push sources, and centralize teardown. Ship with lifetime tests and signposted profiling so you can prove actors deallocate when features end. Continually review stored handles and `nonisolated` usage to prevent regressions as code evolves.

## Swift/SwiftUI Code Example

```swift
import Foundation
import OSLog

actor Heartbeat {
    private let logger = Logger(subsystem: "com.example.Heartbeat", category: "lifecycle")
    private let signposter = OSSignposter()
    private var heartbeatTask: Task<Void, Never>?
    private(set) var beats: Int = 0

    func start() {
        guard heartbeatTask == nil else { return }
        heartbeatTask = Task { [weak self] in
            let state = self?.signposter.beginInterval("heartbeat-loop")
            defer { if let state { self?.signposter.endInterval("heartbeat-loop", state) } }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                await self?.tick()
            }
        }
    }

    func stop() {
        heartbeatTask?.cancel()
        heartbeatTask = nil
    }

    private func tick() {
        beats += 1
        logger.log("beat=\(self.beats, privacy: .public)")
    }

    deinit {
        heartbeatTask?.cancel()
        logger.debug("Heartbeat deinit")
    }
}

// Example usage proving no retain cycle: the actor tears down after dropping the last strong ref.
func demoNoRetainCycle() async {
    var hb: Heartbeat? = Heartbeat()
    await hb?.start()
    try? await Task.sleep(for: .seconds(2))
    await hb?.stop()
    hb = nil
    try? await Task.sleep(for: .milliseconds(100))
}
```

## References

- [What's new in Swift: August 2026 Edition](https://swift.org/blog/whats-new-in-swift-august-2026/)
- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
