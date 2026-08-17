# Swift 6 Concurrency Migration for Deprecated iOS APIs

Swift’s concurrency model turns “good enough” callbacks into potential runtime risk. The symptoms often show up after rollout: tasks that don’t cancel underlying work, UI jank during fast list scrolling, and races that are hard to reproduce. If your networking, caching, and UI lifecycles aren’t encoded in types, the compiler or your crash reports will force the issue.

> If you can’t name where work runs, when it cancels, and who owns the state, you don’t have concurrency—you have a raffle.

## Why This Matters For iOS Teams
Stricter compiler checks and deprecated patterns surface quickly during migration. Teams can get stuck between silencing warnings and not breaking production, and partial migrations are risky: two concurrency models stitched together with shared mutable state and “temporary” shims that outlive their intent.

In practice, drift is the hidden cost. One codepath for modern APIs, another for older devices, and ad‑hoc `DispatchQueue` hops that obscure thread affinity until latency spikes appear under interaction-heavy workloads. The fix is not a mass rewrite; it’s targeted boundaries: structured concurrency where you own lifecycle, actors for shared state, and a small bridge for legacy edges.

## 1. Bridge Legacy Callbacks And Delegates To Async/Await
### Use Continuations For One-Shot Work, Streams For Multi-Event
When a legacy callback fires exactly once with a result, use `withCheckedThrowingContinuation`. When the legacy API emits a sequence (for example, progress or events), use `AsyncStream` or `AsyncThrowingStream`. Avoid mixing both; a one-shot continuation wrapped around a multi-event delegate can hang or double-resume.

```swift
import Foundation

enum ImageError: Error { case cancelled, badData }

actor ImageLoader {
    private let session = URLSession.shared

    // Preferred: Native async with URLSession
    func fetch(_ url: URL) async throws -> Data {
        let (data, _) = try await session.data(from: url)
        return data
    }

    // Legacy — wrapped once behind a stable async API
    // Assume a third-party `LegacyImageService` with a single-shot completion.
    func fetchFromLegacy(_ url: URL, using service: LegacyImageService) async throws -> Data {
        try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                var token: Cancellable?
                token = service.load(url: url) { result in
                    switch result {
                    case .success(let data):
                        continuation.resume(returning: data)
                    case .failure(let err):
                        continuation.resume(throwing: err)
                    }
                    // Allow token to be released after completion
                    _ = token
                }
            }
        } onCancel: {
            // Translate cooperative cancellation
            service.cancel(url: url)
        }
    }
}

// Example legacy surface you don't control
protocol LegacyImageService {
    @discardableResult
    func load(url: URL, completion: @escaping (Result<Data, Error>) -> Void) -> Cancellable
    func cancel(url: URL)
}

protocol Cancellable { func cancel() }
```

When a callback might never fire (for example, due to a deallocated delegate), a continuation won’t resume. Centralize the bridge in one type and own the delegate lifecycle there. Validate cancellation so that canceling a task also stops underlying work.

For multi-event delegates:

```swift
final class LegacyEventSource {
    weak var delegate: LegacyEventSourceDelegate?
    func start() { /* ... */ }
    func stop() { /* ... */ }
}

protocol LegacyEventSourceDelegate: AnyObject {
    func eventSource(_ source: LegacyEventSource, didEmit value: Int)
    func eventSourceDidFinish(_ source: LegacyEventSource, error: Error?)
}

struct EventStream {
    static func stream(from source: LegacyEventSource) -> AsyncThrowingStream<Int, Error> {
        AsyncThrowingStream { continuation in
            final class Bridge: LegacyEventSourceDelegate {
                let continuation: AsyncThrowingStream<Int, Error>.Continuation
                init(_ continuation: AsyncThrowingStream<Int, Error>.Continuation) {
                    self.continuation = continuation
                }
                func eventSource(_ source: LegacyEventSource, didEmit value: Int) {
                    continuation.yield(value)
                }
                func eventSourceDidFinish(_ source: LegacyEventSource, error: Error?) {
                    if let error { continuation.finish(throwing: error) }
                    else { continuation.finish() }
                }
            }

            let bridge = Bridge(continuation)
            source.delegate = bridge
            source.start()

            continuation.onTermination = { @Sendable _ in
                source.stop()
            }
        }
    }
}
```

## 2. Replace GCD With Structured Concurrency
### Bind Work To Ownership And Carry Priority
`Task`, `withTaskGroup`, and `MainActor` make ownership explicit. Use them for work scoped to a view, controller, or model. Reserve `DetachedTask` for cases where no parent is appropriate and cross-actor work is required, and pass an explicit `TaskPriority` if you do.

```swift
import UIKit

@MainActor
final class FeedController: UIViewController {
    private var loadTask: Task<Void, Never>?
    private let loader = ImageLoader()

    func loadFeed(thumbnails: [URL]) {
        loadTask?.cancel()
        loadTask = Task(priority: .userInitiated) { [loader] in
            await withTaskGroup(of: (Int, UIImage?).self) { group in
                for (idx, url) in thumbnails.enumerated() {
                    group.addTask(priority: .userInitiated) {
                        do {
                            let data = try await loader.fetch(url)
                            return (idx, UIImage(data: data))
                        } catch {
                            return (idx, nil)
                        }
                    }
                }

                for await (idx, image) in group {
                    guard let image else { continue }
                    // Already on MainActor due to @MainActor on the class
                    // update the cell at idx with image
                }
            }
        }
    }

    deinit { loadTask?.cancel() }
}
```

Prefer child tasks within a `TaskGroup`; they inherit cancellation and priority, and they tear down as a unit. If you truly need detached execution, never touch UIKit there; hop back via `await MainActor.run`.

## 3. Sendability, Isolation, And Swift Checks
### Encode Invariants In Types, Not Comments
Adopt `Sendable` where types are value-like or internally synchronized. Use `@MainActor` to guard UI-bound state, and use `actor` for shared mutable state. Avoid `@unchecked Sendable` unless you can document and uphold invariants.

```swift
import Foundation

actor ImageCache {
    private var store: [URL: Data] = [:]

    func get(_ url: URL) -> Data? { store[url] }
    func set(_ url: URL, data: Data) { store[url] = data }
}

@MainActor
final class FeedViewModel {
    private let cache = ImageCache()
    private let loader = ImageLoader()

    func image(for url: URL) async -> Data? {
        if let cached = await cache.get(url) { return cached }
        do {
            let data = try await loader.fetch(url)
            await cache.set(url, data: data)
            return data
        } catch {
            return nil
        }
    }
}
```

Actor reentrancy can surprise teams. A “check-then-calculate-then-store” spread across multiple `await`s is not atomic; other calls can interleave between steps. If you need atomicity, confine the sequence inside a single actor method or maintain a local snapshot for consistency. For imported modules that lack sendability annotations, `@preconcurrency` can defer warnings, but treat it as a temporary shim and tighten types when you update those modules.

## 4. Availability, Back Deployment, And Rollout Gates
### Keep One Entry Point, Hide The Conditional
You can often avoid duplicating codepaths when back deploying. Centralize availability checks at the edge and provide a single async entry point. Call modern async APIs like `URLSession.data(for:)` when available; route to a single legacy bridge otherwise. Call sites stay uniform and testable.

```swift
import Foundation

struct NetworkClient {
    private let session = URLSession.shared

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try await session.data(for: request)
    }
}
```

Roll out the new path with a feature flag placed above the shim so both variants share business logic and observability. The failure mode to avoid is divergence over time—“temporary” paths that keep accumulating fixes. Gate OS availability in CI with a device/version matrix and assert the minimum deployment target you are shipping.

## Tradeoffs And Pitfalls
Structured concurrency surfaces hidden UI-thread assumptions that GCD may have masked. Annotate UI owners with `@MainActor` and make hops explicit; it reads like ceremony but prevents reentrancy issues. Overusing `DetachedTask` might “work” in local tests yet behave unpredictably when the system schedules unparented background work. Prefer parented tasks and carry `TaskPriority` so the scheduler can make informed decisions.

Treat cancellation as a first-class signal. Legacy code often never canceled anything; `Task` does. If you don’t translate cancellation to the underlying operation—network request, file I/O, long decode—you risk wasting resources with no user-visible benefit. Be disciplined with `@unchecked Sendable`; it’s a promise to the compiler that you must uphold indefinitely. Prefer actors and values to comments and hope.

## Validation And Observability
Mark async boundaries so you can compare before/after behavior with data instead of anecdotes. Use Instruments (Time Profiler and Allocations) to verify that replacing callbacks with `async/await` didn’t regress hot-path latency or object lifetime under representative workloads. For logs, prefer `os_log` with categories and subsystems; prints from multiple tasks can reorder and make device logs noisy.

`OSSignposter` gives you intervals and counters you can view in Instruments and Console. Wrap expensive or latency-sensitive calls so you can track distribution shifts during rollout.

```swift
import os

enum NetSignposts {
    static let log = OSLog(subsystem: "com.acme.app.network", category: "requests")
    static let signposter = OSSignposter(logHandle: log)
}

func signposted<T>(_ name: StaticString, _ op: @escaping () async throws -> T) async throws -> T {
    let state = NetSignposts.signposter.beginInterval(name)
    do {
        let result = try await op()
        NetSignposts.signposter.endInterval(name, state)
        return result
    } catch {
        NetSignposts.signposter.endInterval(name, state)
        throw error
    }
}
```

Write async tests that await conditions instead of sleeping. Use expectations with timeouts tied to realistic conditions. For post-release signals, add crash diagnostics and capture signpost summaries per feature flag path; a regression in tail latency should trigger an alert, not a chat thread. Test cancellation: start an operation, cancel the parent task, and assert that underlying work stops within a bounded window.

## Practical Checklist
- [ ] Inventory every callback and delegate; classify as one-shot or streaming.
- [ ] Bridge one-shots with `withCheckedThrowingContinuation`; model multi-event delegates with `AsyncStream` or `AsyncThrowingStream`.
- [ ] Replace UI-adjacent `DispatchQueue.async` with `Task` and `withTaskGroup`; return to `MainActor` for UI.
- [ ] Pass `TaskPriority` to child tasks; avoid `DetachedTask` unless isolation demands it.
- [ ] Actor-isolate shared mutable state; annotate UI owners with `@MainActor`.
- [ ] Add `Sendable` where correct; avoid `@unchecked Sendable` without documented invariants.
- [ ] Translate `Task` cancellation to the underlying operation (network, file, decode).
- [ ] Instrument with `OSSignposter` and structured `os_log`; retire print debugging across tasks.
- [ ] Write async tests with expectations and explicit timeouts; remove sleeps.
- [ ] Centralize availability shims; enforce target OS in a CI device/version matrix.
- [ ] Roll out behind a feature flag above the shim; track signpost deltas per path.

## Closing Takeaway
Concurrency migration isn’t a stylistic pass; it’s encoding ownership, cancellation, and isolation so the compiler can help you. Bridge legacy edges with a single continuation-based shim, move UI-scoped work into `Task` and `TaskGroup`, and protect shared state with actors. Measure with Instruments and signposts rather than guessing. Done this way, you reduce risk, keep one codepath, and trade heisenbugs for intent the toolchain can enforce.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation
import Foundation

// ❌ Before — networking used legacy callbacks, a global mutable cache on a background queue,
// and rows didn’t cancel in‑flight work during fast scrolling, causing jank and data races.

// ✅ After — structured concurrency with an actor cache; cooperative cancellation via Task APIs.
actor ImageCache {
    private var store: [URL: Data] = [:]
    func data(for url: URL) -> Data? { store[url] }
    func insert(_ data: Data, for url: URL) { store[url] = data }
}

@MainActor
@Observable
class FeedModel {
    var images: [URL: Image] = [:]
    private let cache = ImageCache()
    func image(for url: URL) async -> Image? {
        if let img = images[url] { return img }
        if let cached = await cache.data(for: url), let ui = UIImage(data: cached) {
            let image = Image(uiImage: ui); images[url] = image; return image
        }
        do {
            try Task.checkCancellation()
            let (data, _) = try await URLSession.shared.data(from: url)
            try Task.checkCancellation()
            await cache.insert(data, for: url)
            guard let ui = UIImage(data: data) else { return nil }
            let image = Image(uiImage: ui); images[url] = image; return image
        } catch is CancellationError { return nil } catch { return nil }
    }
}

struct FeedList: View {
    @State private var model = FeedModel()
    let urls: [URL]
    var body: some View {
        List(urls, id: \.self) { url in
            HStack {
                if let img = model.images[url] {
                    img.resizable().frame(width: 44, height: 44).clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    Rectangle().fill(.gray.opacity(0.2)).frame(width: 44, height: 44)
                        .task(id: url) { _ = await model.image(for: url) } // cancels on reuse/scroll
                }
                Text(url.lastPathComponent).lineLimit(1)
            }
        }
    }
}
```

## References

- [What's new in Swift: July 2026 Edition](https://swift.org/blog/whats-new-in-swift-july-2026/)
- [Swift Testing explained with code examples](https://www.avanderlee.com/swift-testing/modern-unit-test/)
- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
