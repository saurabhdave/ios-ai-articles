# Xcode Time Profiler for macOS hang detection

A frozen macOS window during a customer demo erodes trust the moment it happens. Hangs frequently appear only on physical devices where GPU, scheduler, and driver interactions differ from the simulator. This guide gives a conservative, repeatable workflow to make hangs actionable: capture appropriate samples on device, map them to code with `OSSignposter` and `os_log`, validate in CI with `XCTest` and `Allocations`, and gate rollouts with telemetry and feature flags.

## Why This Matters For iOS Teams
A single production hang increases incident load and damages user confidence. Profiling on the simulator can mask device-specific stalls caused by driver and scheduler behavior; reproducing and analyzing hangs requires device captures and reliable symbolication. When tooling or instrumentation is inconsistent, triage becomes guesswork: capture hangs on device, map samples to named operations, validate fixes in CI and on hardware, and roll out conservatively.

> Make a hang measurable before you try to fix it: capture on device, correlate with signposts and logs, then validate under CI and production gates.

## 1. Collecting Reproducible Samples
### Use `Time Profiler` And Sampling Strategy
Collect system-wide and process-only samples on the affected hardware using `Time Profiler`. Choose time-based sampling when the stall is CPU-bound and nondeterministic; choose tracing templates when you need detailed GPU or short-lived I/O traces and accept higher overhead. Choose system-wide captures when the hang could originate from drivers or other processes; choose process-only captures when you need focused application stack detail.

Avoid attaching `lldb` and setting breakpoints during nondeterministic hangs because a debugger changes timing and can hide races. Record a low-overhead `Time Profiler` capture on device first, then repeat with a narrower process-only capture for focused analysis. For lab validation, run multiple captures with varying sample rates and verify the hang persists before declaring a fix effective. Do not run continuous high-frequency sampling on production builds since higher sample rates can perturb timing.

Testing: run captures on representative devices and multiple OS versions where the app ships. Limit high-overhead captures to lab windows to avoid perturbing production timing.

## 2. Correlating OS Activity And App Events
### Mark Boundaries With `OSSignposter` And `os_log`
Instrument top-level operations with `OSSignposter` and emit contextual `os_log` entries for state changes. Use signposts to correlate a `Time Profiler` sample timestamp to a named operation such as `render` or `layout`. Choose signposts when you need coarse-to-medium latency boundaries; choose full tracing when you need sub-millisecond GPU or driver internals and can accept extra overhead.

Anti-pattern: scattering ad-hoc `os_log` messages with inconsistent formats. Preferred: implement a small `LatencyTracker` that emits begin/end signposts and structured logs. Gate verbose signposts behind runtime flags or debug builds to reduce the chance of changing production timing. Validate cancellation and cleanup paths before rollout; a task that cannot be cancelled leaks CPU and battery.

```swift
import os

actor LatencyTracker {
    private let log = OSLog(subsystem: "com.example.app", category: "latency")
    // OSSignposter(logger:) takes a Logger; pass subsystem/category directly here.
    private let signposter = OSSignposter(subsystem: "com.example.app", category: "signpost")

    // beginInterval returns the OSSignpostIntervalState that endInterval requires.
    func beginRender(id: String) -> OSSignpostIntervalState {
        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval("render", id: signpostID, "id: \(id, privacy: .public)")
        os_log("Begin render %{public}s", log: log, type: .debug, id)
        return state
    }

    func endRender(_ state: OSSignpostIntervalState) {
        signposter.endInterval("render", state)
    }
}
```

When you need to map samples to user-visible work, emit structured `os_log` messages alongside `OSSignposter` intervals and ensure timestamps are synchronized across your logging and sampling systems.

## 3. Validation In CI And Device Labs
### Assert Performance With `XCTest` And Capture `Allocations`
Add `XCTest` performance tests that measure baseline CPU wall time for the problematic UI flow and fail in CI when regressions occur. Choose short, representative scenarios for CI and longer, device-only tests for lab validation. Choose local device jobs when you need exact hardware behavior; choose simulator jobs only for fast smoke checks that cannot detect device-specific driver stalls.

Capture `Allocations` to rule out memory pressure as a cause of stalls and run `Time Profiler` captures on lab devices as part of regression checks. Include a CI job that runs representative performance checks on lab devices after merging high-risk changes. Also add a verification step that confirms symbolication for the test build before accepting fixes.

Use async expectations in `XCTest` performance assertions and fail CI when baseline CPU time increases beyond a tolerated delta.

## 4. Symbolication And Postmortem Analysis
### Archive `dSYM` And Verify Mapping
Automate `dSYM` archiving and verify symbolication before relying on a sample for root-cause analysis. Choose automated verification when you expect frequent postmortems; choose manual symbolication only for ad-hoc triage. Triaging based on unsymbolicated addresses forces guessing by address and increases triage time.

Mismatched `dSYM` and build IDs commonly occur when build or strip settings change; ensure archive retention covers the expected analysis window. Automate `dSYM` upload and include a CI check that runs a symbolication mapping on a representative address to confirm function names are resolved. Operationally, confirm symbolication early in your validation pipeline so developers do not chase ambiguous stack traces.

## 5. Rollout, Gatekeeping, And Mitigation
### Phase Deployments And Use Feature Flags
Gate high-risk fixes behind short-lived feature flags and phased rollouts. Release to a small percentage of users, validate telemetry trends and signpost-correlated logs, and then increase rollout. Choose a straight phased rollout when changes are low-risk and reversible; choose feature flags when you need granular control and immediate rollback paths.

Feature-flag complexity introduces paths that must be covered by tests; add smoke tests for each flag state to CI and include a quick rollback path. A hang fixed locally but not validated on device remains a production risk, so ensure lab verification precedes wide rollout.

Configure telemetry thresholds and quick rollback automation to limit blast radius when a rollout increases hang rates.

## Tradeoffs And Pitfalls
Sampling granularity trades signal for perturbation: higher sample rates reveal more detail but can change scheduler behavior and increase CPU usage. More signposting and `os_log` improves correlation at the cost of additional I/O and possible timing impact—gate detailed telemetry for short windows. Aggregated telemetry ingestion systems provide trends rather than per-user immediacy; do not rely on them as the sole incident source.

Be cautious with the debugger and breakpoints: `lldb` alters timing and can suppress races. Also validate cancellation and cleanup paths before rollout because work that cannot be cancelled can leak CPU and battery. Missing or mismatched `dSYM` will derail postmortems; invest in automation to avoid this predictable failure mode.

## Validation & Observability
### Combine Automated Tests, Device Captures, And Fleet Signals
Run these checks together:
- `XCTest` performance assertions with async expectations that run on CI devices and fail when baseline CPU time increases.
- `Time Profiler` and `Allocations` templates for in-lab captures on device; repeat captures with both system-wide and process-only modes.
- `OSSignposter` signposts plus structured `os_log` to map samples to user-visible operations.
- Aggregated telemetry ingestion and in-app metrics to monitor hang-rate deltas during phased rollouts.

Operationally, include a CI job that runs representative performance checks on lab devices after merging high-risk changes, and a verification step that confirms symbolication for the test build before accepting fixes. Use telemetry for trend confirmation, and rely on device captures for immediate triage.

## Practical Checklist
- [ ] Record reproducible hangs with `Time Profiler` using system-wide and process-only captures on device.
- [ ] Add `OSSignposter` signposts around the top two latency-sensitive paths and correlate with structured `os_log` entries.
- [ ] Create `XCTest` performance tests asserting baseline CPU time for critical UI flows and run them on CI devices.
- [ ] Ensure automatic `dSYM` archiving and verify symbolication before accepting fixes.
- [ ] Configure phased rollouts or feature flags and monitor aggregated telemetry for hang-rate deltas during rollout.
- [ ] Add runtime gates to disable verbose tracing in production builds to avoid perturbing timing-sensitive behavior.

## Closing Takeaway
Treat hangs as diagnosable engineering problems by making them measurable and repeatable. Capture appropriate `Time Profiler` samples on device, correlate samples with `OSSignposter` and `os_log`, verify fixes with `XCTest` and `Allocations`, and gate rollouts with phased deployments and telemetry. Focus instrumentation on the top latency-sensitive paths, automate `dSYM` verification, and enforce CI checks so future production hangs are easier to reproduce and resolve.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation
import OSLog

@MainActor @Observable final class Renderer {
    private let signposter = OSSignposter()
    private let logger = Logger(subsystem: "com.example.app", category: "Renderer")
    var busy: Bool = false

    func simulateRenderFrame(durationMillis: UInt64 = 700) async {
        let signpostState = signposter.beginInterval("RenderFrame")
        logger.log("RenderFrame begin")
        busy = true
        // Simulate device-only stall: perform a CPU-bound short busy-wait to surface scheduling/driver interactions
        let end = Task.detached { Date().addingTimeInterval(Double(durationMillis)/1000.0) }
        while Date() < (try! await end.value) {
            // tight loop simulating work; keep body minimal to ensure measurable samples in Time Profiler
            _ = (1...1000).reduce(0, +)
            await Task.yield() // keep cooperative with the scheduler
        }
        busy = false
        signposter.endInterval("RenderFrame", signpostState)
        logger.log("RenderFrame end")
    }
}

struct HangDemoView: View {
    @State private var renderer = Renderer()
    var body: some View {
        VStack(spacing: 12) {
            Text(renderer.busy ? "Rendering…" : "Idle")
            Button("Simulate Hang") {
                Task {
                    await renderer.simulateRenderFrame()
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
```

## References

- [Xcode 26.5 (17F42)](https://developer.apple.com/news/releases/?id=05112026n)
- [Instruments Help](https://developer.apple.com/documentation/xcode/gathering-information-for-debugging)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
