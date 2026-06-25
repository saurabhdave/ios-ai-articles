# OSSignposter Custom Performance Markers for iOS

Cold starts regress, frames drop, and the trace looks “fine.” The bug only reproduces when a particular asset pack is present, the device is warm, and the user lands on a deep link. Without precise, low-overhead markers on the hot paths, you’re left correlating squishy timestamps and hunches. This is where `OSSignposter` helps replace guesswork with timelines you can reason about.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters For iOS Teams
Performance incidents often arrive as spikes. If your binary doesn’t already contain targeted signposts, you won’t reconstruct a startup hitch or a render stall that depends on data shape and device state. Platform tooling makes the signal actionable: `Instruments` overlays `Points of Interest` on other tracks, `XCTOSSignpostMetric` can turn intervals into measurable tests, and `MetricKit` can surface post-release trends. The constraint is not technology; it’s taxonomy and operational hygiene. Sloppy names, unbounded attributes, or mismatched intervals pollute traces and waste engineering time.

> Treat markers as API: stable names, bounded attributes, and a migration plan. Anything else is drift.

## 1. What `OSSignposter` Buys You
### Structured Intervals, Not Log Noise
Free-text `os_log` lines scatter context across threads and make correlation guesswork. `OSSignposter` brackets real work with `beginInterval(_:id:)` and `endInterval(_:id:)`, and tags milestones with `emitEvent(_:id:)`. You get scoped durations, correlation via `OSSignpostID`, and first-class visibility in `Instruments`.

```swift
import OSLog

struct StartupMarkers {
    private let log = OSLog(subsystem: "com.example.app", category: "Startup")
    private let sp: OSSignposter

    init() { sp = OSSignposter(logHandle: log) }

    func measureAppLaunch<T>(_ work: () throws -> T) rethrows -> T {
        let id = sp.makeSignpostID()
        let state = sp.beginInterval("AppLaunch", id: id)
        defer { sp.endInterval("AppLaunch", state) }

        sp.emitEvent("PrewarmCaches", id: id)
        return try work()
    }
}```

When you need intervals you can see on a timeline or assert in tests, use `OSSignposter`. For infrequent, human-readable breadcrumbs, keep `os_log`. A common failure mode is reusing a `OSSignpostID` across unrelated work or forgetting to end intervals on error paths—both corrupt your timeline. Use `defer` for symmetry and generate a fresh ID per logical unit of work.

### Operational Note
Validate intervals by overlaying `Points of Interest` on `Time Profiler`. Apparent “I/O” slowdowns can often correlate with main-thread activity once the overlay is visible.

## 2. Designing Marker Taxonomy And IDs
### Names Aggregate; IDs Correlate
The anti-pattern is “one-off labels per call-site” like “Fetch user A/B/C.” In `Instruments`, you’ll get fragmented lanes with no rollup. Instead, define a small, stable taxonomy with `OSLog(subsystem:category:)` and deterministic `OSSignpostID` derivations for entities you need to correlate across async boundaries.

Choose “one category per subsystem, one interval name per operation.” Use concise attributes that bucket cleanly (for example, `purpose=image`, `status=2xx/4xx/5xx`). Never include sensitive or high-cardinality values in names; unbounded variation makes aggregation unreadable.

### Operational Note
ID collisions conflate parallel intervals. If a simple derivation is too lossy for your domain, widen the space with a larger seed or combine a stable key with a local counter.

## 3. Wiring Signposts In Production Code
### A Thin Utility With A Toggle
Sprinkling `OSSignposter` calls everywhere couples hot paths to instrumentation and complicates rollout. Hide the API behind a tiny utility so you can tune density via configuration, disable in tests, and keep call-sites clean.

```swift
import Foundation
import OSLog
import CoreGraphics

struct PerfLog {
    static let rendering = OSLog(subsystem: "com.example.app", category: "rendering")
}

struct Signpost {
    private let sp: OSSignposter?
    private let enabled: Bool

    init(log: OSLog, enabled: Bool) {
        self.enabled = enabled
        self.sp = enabled ? OSSignposter(logHandle: log) : nil
    }

    func begin(_ name: StaticString) -> (OSSignpostID?, OSSignpostIntervalState?) {
        guard let sp = sp else { return (nil, nil) }
        let id = sp.makeSignpostID()
        let state = sp.beginInterval(name, id: id)
        return (id, state)
    }

    func event(_ name: StaticString, id: OSSignpostID?) {
        guard let sp = sp, let id = id else { return }
        sp.emitEvent(name, id: id)
    }

    func end(_ name: StaticString, id: OSSignpostID?, state: OSSignpostIntervalState?) {
        guard let sp = sp, let _ = id, let state = state else { return }
        sp.endInterval(name, state)
    }
}

actor ImageDecoder {
    private let sp = Signpost(log: PerfLog.rendering, enabled: true)

    func decode(_ data: Data) async throws -> CGImage {
        let (id, state) = sp.begin("DecodeImage")
        sp.event("StartParse", id: id)

        let image = try await decodeInternal(data)

        sp.event("CreatedCGImage", id: id)
        sp.end("DecodeImage", id: id, state: state)
        return image
    }

    private func decodeInternal(_ data: Data) async throws -> CGImage {
        throw NSError(domain: "Decode", code: -1)
    }
}```

Instrument leaf-heavy, high-impact paths and lifecycle stages (cold launch, navigation transitions, first frame). Do not blanket every function; in tight per-frame loops, per-call overhead can become visible. Keep density behind a configuration flag so you can dial it back without a client update.

### Operational Note
Always end intervals on all exits (success and error) with `defer` where possible. Mismatched names or missing `endInterval(_:id:state:)` calls reduce trace quality.

## 4. Failure Modes You Will Hit (And How To Avoid Them)
### Cross-Thread Contamination
Capturing a parent `OSSignpostID` into an escaping closure and emitting events from helper threads can extend or merge intervals unintentionally. Derive child IDs for sub-operations and keep parent IDs scoped to the primary task.

```swift
import OSLog

struct RenderMarkers {
    private let logger = Logger(subsystem: "com.example.app", category: "rendering")
    private var sp: OSSignposter { OSSignposter(logger: logger) }

    func measureFirstFrame(_ work: () async throws -> Void) async rethrows {
        let parentID = sp.makeSignpostID()
        let parentState = sp.beginInterval("FirstFrame", id: parentID)
        defer { sp.endInterval("FirstFrame", parentState) }

        sp.emitEvent("LayoutStart", id: parentID)

        let childID = sp.makeSignpostID()
        let childState = sp.beginInterval("Rasterize", id: childID)
        try await work()
        sp.endInterval("Rasterize", childState)

        sp.emitEvent("Commit", id: parentID)
    }
}```

When sub-operations matter independently, use a parent/child pattern. When you only care about end-to-end time, use a single bracketing interval.

### Operational Note
Foreground/background transitions can inflate intervals if you don’t close them. End or suspend critical intervals on lifecycle changes and resume with a new ID to prevent long, misleading tails.

## Tradeoffs And Pitfalls
- Precision vs. Overhead: Add intervals only where you need line-of-sight. If you feel tempted to instrument everything, you may not have a clear hypothesis yet.
- Taxonomy Discipline: Flexible labels invite creativity you cannot aggregate. Keep names short, stable, and documented alongside your `OSLog` definitions.
- Privacy And Stability: Do not embed sensitive or unstable tokens in names or attributes. Normalize values at the source and cap cardinality.
- ID Collisions: Weak ID derivations conflate parallel work. Combine a stable key with a wider seed or a namespaced counter when you need stronger uniqueness.
- Variance Across Conditions: Schedulers, thermal state, and background activity can introduce timing variance. Store thresholds with awareness of device class and OS context to keep tests useful.
- Tool Trust: A mismatched `beginInterval(_:id:)`/`endInterval(_:id:state:)` breaks the plot. Add lightweight tests that assert pairing on critical code paths.

## Validation And Observability
- XCTest Gates: Use `XCTOSSignpostMetric` to measure named intervals and fail the build when they exceed calibrated bounds. Start by gating one marker per feature area (startup, navigation, networking, rendering). Keep thresholds appropriate to the devices you run in CI, and quarantine noisy suites rather than deleting them.
- Instruments Workflow: Validate locally with `Points of Interest` overlaid on `Time Profiler` and `Allocations`. Confirm that interval boundaries align with the stacks and churn you expect. Be aware that capture conditions (like screen recording) can affect measurements.
- Structured Logging: Keep `os_log` for sparse, human-readable breadcrumbs that supplement signposts. Logs help reconstruct context around an interval without bloating `Instruments`.
- Post-Release Signals: `MetricKit` reports aggregated metrics (such as hang rate, animation hitches, and launch metrics). Use those signals to choose where to dig with a repro build, then read your existing signposts for root cause.
- Rollout Control: Ship a configuration-controlled density flag and category toggles. Start conservatively, enable for a small cohort, and verify no frame-rate regressions under realistic interaction before widening coverage. Keep a kill switch for incidents.

## Practical Checklist
- [ ] Define `OSLog` subsystem/categories and a tight marker taxonomy for Startup, Navigation, Networking, and Rendering.
- [ ] Introduce a thin wrapper for `OSSignposter`; control density via configuration.
- [ ] Instrument a handful of high-impact paths with `beginInterval(_:id:)`/`endInterval(_:id:state:)`, use stable `OSSignpostID` derivations, and normalize attributes.
- [ ] Add CI performance tests with `XCTOSSignpostMetric` for one interval per feature area; set thresholds appropriate to your CI hardware and OS context.
- [ ] Validate `Instruments` traces by overlaying `Points of Interest` with `Time Profiler` and `Allocations` on representative devices under realistic interaction.
- [ ] Add kill switches for marker density and category enablement; monitor trends with `MetricKit` and investigate spikes using repro builds.

## Closing Takeaway
Custom `OSSignposter` markers help convert performance from anecdote to assertion. The win is not the API—it’s the discipline: stable names, deterministic IDs, bounded attributes, and controlled rollout. A small set of precise intervals on startup, navigation, networking, and rendering carries most of the load. Gate them in CI, keep `Instruments` readable, and maintain trust by avoiding cardinality explosions and mismatched pairs. When the next regression spikes, you’ll have a timeline that moves the investigation forward.

## Swift/SwiftUI Code Example

```swift
import Foundation
import OSLog

struct DeepLinkPerformance {
    private static let sp = OSSignposter(subsystem: "com.acme.app", category: "Startup")
    
    enum Target: String { case product, settings, help }
    
    static func handleDeepLink(_ target: Target, assetPack: String, isWarmLaunch: Bool) async {
        sp.emitEvent("LaunchContext", "warm=\(isWarmLaunch, privacy: .public)")
        
        let state = sp.beginInterval("DeepLink", "target=\(target.rawValue, privacy: .public)")
        defer { sp.endInterval("DeepLink", state) }
        
        await preloadAssets(pack: assetPack)
        await renderFirstFrame()
    }
    
    private static func preloadAssets(pack: String) async {
        let boundedPack = String(pack.prefix(24))
        let state = sp.beginInterval("AssetLoad", "pack=\(boundedPack, privacy: .public)")
        try? await Task.sleep(nanoseconds: 60_000_000)
        sp.emitEvent("AssetCache", "hit=\(Int.random(in: 0...1), privacy: .public)")
        sp.endInterval("AssetLoad", state)
    }
    
    private static func renderFirstFrame() async {
        let state = sp.beginInterval("FirstFrame")
        try? await Task.sleep(nanoseconds: 16_000_000)
        sp.endInterval("FirstFrame", state)
    }
}
```

## References

- [Instruments Help](https://developer.apple.com/documentation/xcode/gathering-information-for-debugging)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
