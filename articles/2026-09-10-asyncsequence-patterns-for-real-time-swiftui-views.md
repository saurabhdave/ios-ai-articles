# AsyncSequence Patterns for Real-Time SwiftUI Views

Real-time SwiftUI often falters under bursty input: late updates, duplicated renders, or views that never fully recover after navigation. These failures usually trace back to unbounded buffers, work running on the main actor, or tasks that outlive their owners. Model each live feed as an `AsyncSequence` with explicit buffering, cancellation, and isolation you can validate in tests.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*
For practical deployment, the patterns shown work on iOS 15+ with Swift Concurrency; adjust APIs to your project’s minimum.

## Why This Matters For iOS Teams
Mixing `Combine`, `DispatchQueue`, and callbacks spreads state across lifecycles and abstractions. Consolidating on Swift Concurrency and `AsyncSequence` reduces the surface area and clarifies behavior: structured tasks define lifetime, cancellation is explicit, and isolation can be enforced. Real-time UI—scores ticking, chat scrolling, telemetry streaming—exposes missing bounds and bad actor hops. Treat each source as an `AsyncSequence`, consume with `task(id:)`, and mutate state on the main actor to get predictable teardown and fewer reconnection bugs.

> Streams often fail quietly. A small amount of jank or memory growth can indicate retained tasks or missing bounds.

## 1. Model Live Data Sources With `AsyncSequence`
### Prefer Sequences Over Callbacks
Expose each feed as an `AsyncSequence` rather than callbacks that obscure lifecycle. For server-sent events or chunked responses, adapt `URLSession.bytes(from:)` into an `AsyncThrowingStream` with an explicit `bufferingPolicy`.

```swift
import Foundation

actor LiveScores {
    func events(from url: URL) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream(bufferingPolicy: .bufferingOldest(256)) { continuation in
            let task = Task {
                do {
                    let (bytes, _) = try await URLSession.shared.bytes(from: url)
                    for try await line in bytes.lines {
                        if Task.isCancelled { break }
                        continuation.yield(line)
                    }
                    if !Task.isCancelled {
                        continuation.finish()
                    }
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }
}```

### Choose A Buffering Policy
- Choose `AsyncStream` when your code owns emission and failure is not expected.
- Choose `AsyncThrowingStream` when upstream can throw (network, file IO).
- Prefer `.bufferingOldest(N)` for user-facing feeds to cap memory; avoid `.unbounded` in production.

Call `finish()` on teardown paths. A producer that outlives its consumer retains memory and background work. Validate “no emit after cancel” with a unit test to catch sources that keep running during navigation changes.

## 2. Bridge Legacy Publishers And Delegates
### Bridge At Boundaries, Not In Views
During migration, convert delegates or publishers into `AsyncStream` at a repository boundary. Expose only `AsyncSequence` to the rest of the app so views don’t juggle two reactive models.

```swift
import Foundation
import CoreLocation

@MainActor
final class LocationStream: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var continuation: AsyncStream<CLLocation>.Continuation?

    func updates() -> AsyncStream<CLLocation> {
        AsyncStream(bufferingPolicy: .bufferingOldest(32)) { c in
            self.continuation = c
            c.onTermination = { [weak self] _ in
                self?.manager.stopUpdatingLocation()
                self?.manager.delegate = nil
                self?.continuation = nil
            }
            self.manager.delegate = self
            self.manager.startUpdatingLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let c = continuation else { return }
        for location in locations {
            _ = c.yield(location)
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        continuation?.finish()
    }
}```

### Decide What To Bridge
- Choose bridging when rewrite risk is high or the dependency is third-party.
- Avoid bridging inside views or models; hide them behind a service facade so UI code subscribes to a single abstraction.

Guard `Continuation` lifecycles carefully. Release references in `deinit`, call `finish()`, and stop producers so background emissions don’t persist after cancellation. Add an integration test that subscribes, cancels, and asserts no values arrive post-cancel to catch leaks where a delegate continues emitting.

## 3. Integrate Streams Into SwiftUI Rendering
### Use `task(id:)` And Mutate On The Main Actor
`task(id:)` cancels on disappearance and restarts on identity change. Keep UI state mutations on the main actor to avoid reentrancy and layout races.

```swift
import SwiftUI
import Observation

@Observable final class ChatState { var messages: [String] = [] }

struct ChatView: View {
    @State private var state = ChatState()
    let stream: AsyncStream<String>; let roomID: String
    var body: some View {
        List(state.messages, id: \.self) { Text($0) }
            .task(id: roomID) { for await m in stream { if !Task.isCancelled { await MainActor.run { state.messages.append(m) } } } }
    }
}
```

### Decide Where To Consume
- Consume once at the leaf that owns identity (for example, a `roomID`).
- Pass values down via state; avoid resubscribing in both parent and child for the same key.

If multiple independent consumers are required, scope each `task(id:)` with a distinct `id` to make restarts predictable. Detect duplicate work by logging a per-key render counter; two counters rising for one key usually indicates double-consumption.

## 4. Backpressure, Throttling, And Cancellation
### Bound, Coalesce Off-Main, And Check Cancellation
Use bounded buffers and coalescing in background contexts. Pull heavy parsing or diffing off the main actor, then hop back to update UI.

```swift
import Foundation
import os

struct Diff: Sendable { let ids: [String] }

let signposter = OSSignposter(subsystem: "com.example.app", category: "realtime")

func coalescedDiffs(from ids: AsyncStream<String>) -> AsyncStream<Diff> {
    AsyncStream(bufferingPolicy: .bufferingOldest(64)) { continuation in
        actor Pending {
            private var storage = Set<String>()
            func insert(_ id: String) { storage.insert(id) }
            func drain() -> [String] { defer { storage.removeAll() }; return Array(storage) }
            var isEmpty: Bool { storage.isEmpty }
        }

        let pending = Pending()
        var sleeper: Task<Void, Never>?
        var consumer: Task<Void, Never>?

        func scheduleFlush() {
            sleeper?.cancel()
            sleeper = Task.detached(priority: .utility) {
                let interval = signposter.beginInterval("coalesce")
                try? await Task.sleep(nanoseconds: 50_000_000)
                if Task.isCancelled {
                    signposter.endInterval("coalesce", interval)
                    return
                }
                let toEmit = await pending.drain()
                if !toEmit.isEmpty {
                    continuation.yield(Diff(ids: toEmit))
                }
                signposter.endInterval("coalesce", interval)
            }
        }

        continuation.onTermination = { _ in
            sleeper?.cancel()
            consumer?.cancel()
        }

        consumer = Task.detached(priority: .utility) {
            for await id in ids {
                await pending.insert(id)
                scheduleFlush()
            }
            let final = await pending.drain()
            if !final.isEmpty {
                continuation.yield(Diff(ids: final))
            }
            sleeper?.cancel()
            continuation.finish()
        }
    }
}```

### Choose `Task` Versus `Task.detached`
- Choose a child `Task` tied to view lifetime so cancellation is automatic.
- Choose `Task.detached` only when isolating from parent lifetime or adjusting priority; if used, set an explicit priority to avoid surprising scheduling.

Add cancellation checks in tight loops and `for await` bodies. Without them, updates can arrive after view teardown, and background tasks may linger and compete with rendering.

## Tradeoffs And Pitfalls
Async streams tighten the model but surface lifecycle bugs earlier. A mis-scoped `Continuation` or missing `finish()` leaks memory and work; the UI may “remember” old subscriptions if a producer never ends. Bridging can hide upstream timing issues; a flaky websocket that batches intermittently will still cause visible stutter unless you add explicit buffering and throttling in your layer. Backpressure choices trade fidelity for responsiveness: some feeds can keep only the newest `N` updates; others must avoid dropping recent items. Actor‑isolate mutable state touched by async code; races that look harmless in development often become failures under load.

## Validation & Observability
Codify invariants with tests and instrumentation. Write async tests for cancel-after-start: begin consumption, cancel, then assert no further values after a short grace window. Use Instruments Allocations with a scripted burst to confirm memory plateaus with your chosen `bufferingPolicy`. Add `OSSignposter` intervals around parse → diff → render to expose stalls. Emit structured `os_log` counters for queue depth, dropped items, and restart counts; include a stream key in log metadata. Track post-release with MetricKit for crashes and termination signals, and ramp behind a feature flag to watch trends before full rollout.

## Practical Checklist
- [ ] Model every live feed as an `AsyncSequence` with an explicit `bufferingPolicy`.
- [ ] Use `URLSession.bytes(from:)` for SSE or chunked streams and parse incrementally off-main.
- [ ] Consume with `task(id:)`; mutate view state on the `@MainActor`; break on `Task.isCancelled`.
- [ ] Bridge delegates and publishers at repository boundaries via `AsyncStream`; ensure `finish()` on teardown.
- [ ] Prefer a child `Task` tied to view lifetime; restrict `Task.detached` to priority or lifetime isolation scenarios.
- [ ] Add `OSSignposter` intervals and structured logs for buffer depth, dropped items, and restart counts.
- [ ] Validate with Instruments (Time Profiler, Allocations) under burst to confirm latency and memory behavior.
- [ ] Write XCTest for cancel-after-start and bounded-memory bursts; enforce them in CI.
- [ ] Roll out behind a flag and monitor MetricKit before expanding.

## Closing Takeaway
Treat real-time sources as `AsyncSequence`, not callbacks. Consume them with `task(id:)`, enforce buffer bounds, and check cancellation inside your loops. Isolate mutable state with actors and avoid heavy work on the main actor in hot paths. Prove cancellation and memory limits with tests, and annotate async boundaries with signposts so stalls are visible long before users feel them.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation

struct TickerEvent: Identifiable, Sendable { let id = UUID(); let value: Int; let time: Date }

actor TickerSource {
    private var continuation: AsyncStream<TickerEvent>.Continuation?
    private var pump: Task<Void, Never>?
    let id = UUID()
    func stream(buffer: Int = 64) -> AsyncStream<TickerEvent> {
        AsyncStream(bufferingPolicy: .bufferingOldest(buffer)) { cont in
            continuation = cont
            cont.onTermination = { [weak self] _ in Task { await self?.stop() } }
        }
    }
    func startDemo() {
        pump?.cancel()
        pump = Task {
            var n = 0
            while !Task.isCancelled {
                for _ in 0..<Int.random(in: 1...6) {
                    n += 1; continuation?.yield(.init(value: n, time: .now))
                }
                try? await Task.sleep(for: .milliseconds(Int.random(in: 60...220)))
            }
        }
    }
    func stop() { pump?.cancel(); pump = nil; continuation?.finish(); continuation = nil }
}

@MainActor @Observable final class ScoreModel {
    var recent: [TickerEvent] = []
    func connect(to source: TickerSource) async {
        for await e in source.stream(buffer: 128) {
            recent.append(e); if recent.count > 200 { recent.removeFirst(recent.count - 200) }
        }
    }
}

struct LiveTickerView: View {
    @State private var model = ScoreModel()
    private let source = TickerSource()
    var body: some View {
        List(model.recent.suffix(50)) { Text("#\($0.value) • \($0.time.formatted(date: .omitted, time: .standard))") }
            .task(id: source.id) { await model.connect(to: source) }
            .onAppear { Task { await source.startDemo() } }
            .onDisappear { Task { await source.stop() } }
    }
}
```

## References

- [Swift Concurrency](https://developer.apple.com/documentation/swift/concurrency)
- [AsyncSequence](https://developer.apple.com/documentation/swift/asyncsequence)
- [View.body](https://developer.apple.com/documentation/swiftui/view/body-swift.property)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
