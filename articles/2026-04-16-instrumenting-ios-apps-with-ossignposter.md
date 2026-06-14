# Instrumenting iOS Apps with OSSignposter

In production timelines I often see ad-hoc logs and per-request identifiers create noisy, high-cardinality signals that hide real latency and causal boundaries. This note shows how to use `OSSignposter` to emit low-overhead, platform-visible intervals that map into `Instruments` and `MetricKit` while avoiding the common mistakes that create telemetry debt.

## Why This Matters For iOS Teams
Modern iOS apps need inexpensive, reliable signals for latency and lifecycle correlation that integrate with `Instruments` and `MetricKit`. Teams can add ad-hoc `os_log` strings and timers, but at scale those approaches produce free-form keys and can obscure interval boundaries in timeline views. Using `OSSignposter` yields explicit intervals and causal linkage while keeping emitted metadata bounded.

Instrumenting with `OSSignposter` does not replace distributed tracing for cross-process propagation; choose `OSSignposter` for local, platform-visible intervals and pair it with aggregate signals in `MetricKit` when you need post-release summaries. For environments where signposting is unsuitable, keep structured `os_log` output as a fallback.

> Use stable signpost names and pass `OSSignpostID` across async boundaries—dynamic names and implicit IDs are the main causes of noisy timelines.

## 1. Introduction To `OSSignposter`
### API And Pattern
`OSSignposter` is the API for marking intervals and events that appear in `Instruments` timelines. Create a shared `OSSignposter` per subsystem and a matching `OSLog` for human-readable logs and privacy markers.

Choose coarse-grained signposts when you want a small number of high-signal intervals (screen loads, long user interactions); choose fine-grained signposts when you need step-by-step breakdowns of multi-stage flows and are prepared to sample or gate the volume. Gate the first rollout behind a runtime feature flag and sample a small fraction of users so you can validate behavior before wider rollout.

```swift
import OSLog
import Foundation

@MainActor
final class NetworkSignposter {
    private let signposter = OSSignposter(subsystem: "com.example.app", category: "network")
    private let log = OSLog(subsystem: "com.example.app", category: "network")

    func makeID() -> OSSignpostID { signposter.makeSignpostID() }

    // beginInterval returns an interval state that endInterval requires; hand it
    // back to the caller so the matching end can pass it through.
    func beginRequest(id: OSSignpostID, endpoint: String) -> OSSignpostIntervalState {
        let state = signposter.beginInterval("Network.Fetch", id: id, "endpoint: \(endpoint, privacy: .public)")
        os_log("begin Network.Fetch for %{public}s", log: log, type: .info, endpoint)
        return state
    }

    func endRequest(_ state: OSSignpostIntervalState, status: Int) {
        signposter.endInterval("Network.Fetch", state)
        os_log("end Network.Fetch status=%{public}d", log: log, type: .info, status)
    }
}
```

Make signpost names stable and owned by a single team. Avoid embedding per-request identifiers in the name; bind dynamic values to `OSSignpostID` or pass them as bounded metadata via `OSLog` format specifiers.

## 2. Instrumentation Patterns And Naming
### Naming, Cardinality, And Metadata
Stable naming reduces query cost and keeps timelines readable. Use `OSLog` format specifiers to attach dynamic values and mark sensitive fields with privacy specifiers.

Choose stable names when you need predictable queries and low cardinality; choose dynamic, per-request names only when you have strict, short-lived debugging needs and can prune them promptly. Enforce naming and ownership in code review so inconsistent names do not proliferate.

When adding metadata, bound the payload size and avoid free-form text blobs. Document naming conventions in the repo and require them in PR checks so every signpost has a clear owner and lifecycle.

## 3. Concurrency, Safety, And Correct Correlation
### Passing `OSSignpostID` Across Tasks
Create an `OSSignpostID` at the logical boundary and pass it explicitly across `Task` hops or dispatch queues. Do not assume a signpost created on one thread will be correlated automatically if the ID is not propagated.

Choose explicit ID propagation when you need deterministic correlation across concurrency boundaries; choose per-task local signposts when intervals are strictly local to a task and correlation is unnecessary. If shared state mutates across concurrency boundaries, isolate it under an actor or `@MainActor` to avoid races.

If you observe unexpected ordering in `Instruments`, verify every hop carries the `OSSignpostID` and consider recording a compact timestamp in metadata to aid postmortem correlation. Emit signposts at explicit async boundaries (task creation, queue hops) rather than inside tight synchronous loops on the main thread.

## 4. Rollout, Backward Compatibility, And Governance
### Sampling, Feature Flags, And Fallbacks
Gate instrumentation behind a remote-config flag and increase sampling gradually; do not enable signposting everywhere in a single release. Provide a compile-time no-op path that builds on all deployment targets, and for environments where `OSSignposter` is unsuitable, emit structured `os_log` records instead.

Choose sampling when you need to reduce immediate telemetry volume; choose full enablement only after validating CPU, memory, and telemetry cost in staging. Keep runtime controls available for initial releases so you can adjust sampling or roll back quickly if issues arise.

Document the team naming convention and require a short instrumentation checklist in PR review to prevent unbounded signpost proliferation.

## Tradeoffs And Pitfalls
Instrumenting improves visibility but adds cost and potential noise. Instrument selectively: favor a small set of critical flows and expand only after validating the utility versus the telemetry cost. Inconsistent names and ad-hoc IDs create high-cardinality keys that slow queries and clutter `Instruments` timelines.

Testing time-sensitive signpost assertions can be fragile; prefer ordering checks and deterministic mocks rather than absolute-time assertions. Instrumented telemetry without governance becomes technical debt—name, own, and sample deliberately to avoid that trap.

## Validation & Observability
Use `XCTest` async expectations to assert signpost presence and ordering under deterministic inputs; replace absolute-time assertions with ordering or range checks to reduce flakiness. Run `Instruments` (Time Profiler and Allocations) on representative workloads to measure CPU and memory impact with signposting enabled.

Use `OSSignposter` intervals to mark async boundaries visible in timeline views and pair those with `MetricKit` for post-release aggregate signals and crash analysis. In CI, run integration tests that assert signpost ordering with mocked network responses; manual `Instruments` inspection remains valuable for exploratory diagnosis and performance characterization.

## Practical Checklist
- [ ] Identify 3–5 user-visible flows or hot paths to instrument first and document names and expected intervals.
- [ ] Add `OSSignposter` signposts with stable names and bounded metadata; use `OSLog` format specifiers for dynamic values.
- [ ] Gate instrumentation behind a runtime feature flag or sampling config with remote controls for rollout/rollback.
- [ ] Create `XCTest` integration tests that assert presence and order of signposts using deterministic inputs or mocks.
- [ ] Run `Instruments` (Time Profiler, Allocations) and `MetricKit` during staging to baseline CPU/memory and telemetry cost before a wider rollout.
- [ ] Publish naming and ownership conventions in the team repo and require them in PR reviews.

## Closing Takeaway
`OSSignposter` gives you platform-visible intervals that map into `Instruments` and `MetricKit` without building a custom tracing stack. Instrument deliberately: pick a small set of critical flows, use stable signpost names and `OSSignpostID` for correlation, gate rollout with sampling and feature flags, and validate using `XCTest`, `Instruments`, and `MetricKit`. With governance and incremental rollout, signposts produce signal rather than noise.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import OSLog

private let networkSignposter = OSSignposter(subsystem: "com.example.app", category: "network")

struct InstrumentedNetworkView: View {
    @State private var lastDuration: TimeInterval?
    var body: some View {
        VStack(spacing: 12) {
            Button("Fetch Resource") {
                Task { await fetchDemo() }
            }
            if let d = lastDuration {
                Text("Last request: \(String(format: "%.2f", d))s")
            }
        }
        .padding()
    }

    func fetchDemo() async {
        guard let url = URL(string: "https://api.example.com/resource") else { return }
        let id = networkSignposter.makeSignpostID()
        // Stable StaticString name + bounded metadata (host only). beginInterval
        // returns the state that endInterval requires.
        let state = networkSignposter.beginInterval("HTTP Request", id: id, "host: \(url.host ?? "unknown", privacy: .public)")
        let start = Date()
        defer {
            let duration = Date().timeIntervalSince(start)
            lastDuration = duration
            // End interval with a small, bounded payload (duration).
            networkSignposter.endInterval("HTTP Request", state, "duration: \(duration)")
        }

        do {
            let (data, resp) = try await URLSession.shared.data(from: url)
            _ = data // use data in real code
            if let http = resp as? HTTPURLResponse {
                networkSignposter.emitEvent("HTTP Response", id: id, "status: \(http.statusCode)")
            }
        } catch {
            networkSignposter.emitEvent("HTTP Error", id: id, "err: \(String(describing: error), privacy: .public)")
        }
    }
}
```

## References

- [Instruments Help](https://developer.apple.com/documentation/xcode/gathering-information-for-debugging)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
