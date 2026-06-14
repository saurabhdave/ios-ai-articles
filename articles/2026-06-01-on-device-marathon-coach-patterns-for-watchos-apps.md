# On-device Marathon Coach Patterns for watchOS Apps

Consecutive guidance gaps of 10–30 seconds at crowded race starts revealed a common failure mode: critical pacing logic running off-watch and depending on a phone or network. These patterns document repeatable, on-device coaching choices for watchOS that reduce pairing and network dependencies, limit battery risk, and make rollouts safer. The recommendations are focused on engineering tradeoffs you will face when shifting live coaching onto the watch.

## Why This Matters For iOS Teams
Moving live coaching onto the watch reduces pairing and network dependence but shifts failure modes engineers must manage. `watchOS` constraints can surface battery regressions on older devices, workout sessions that persist after a crash, and schema migrations that stall on-device upgrades.

Early architecture choices influence how safely you can iterate and how likely you are to encounter customer-impacting failures during events. Make the watch the source of truth for in-run continuity: prefer system-managed workout sessions, local checkpoints, and energy-aware sampling so coaching degrades gracefully when resources are constrained.

## 1. Embedded Coaching Model
### Use `HKWorkoutSession` As The Source Of Truth
Anti-patterns include managing workout lifecycle with a `Timer` and manual bookkeeping, which decouples state from system policies and can lead to suspended timers, duplicate sensors, and workout state inconsistent with system-managed sessions. Preferred is to use `HKWorkoutSession` together with `HKLiveWorkoutBuilder` as the canonical lifecycle for live workouts; these types are the system-provided integration points for workout state and `HealthKit` sample collection.

Choose `HKWorkoutSession` when your coaching must persist across backgrounding and integrate with system metrics; choose lightweight background tasks or local timers when you only need ephemeral UI-only timers that do not require system continuity. Make start/stop idempotent and add crash-recovery checkpoints so a terminated process does not leave a workout session in an inconsistent state. Validate aborted starts and verify your app does not leave workout state that could confuse users or drain resources.

```swift
// Compact idempotent start example
actor WorkoutController {
    private var session: HKWorkoutSession?
    func startWorkout(configuration: HKWorkoutConfiguration) async throws {
        guard session == nil else { return }
        session = try HKWorkoutSession(healthStore: HKHealthStore(), configuration: configuration)
        session?.startActivity(with: Date())
    }
}
```

Test by simulating aborted starts, background-foreground transitions, and unexpected termination to ensure recovery paths clear `HKWorkoutSession` state.

## 2. Sensor Fusion And Pacing Algorithm
### Aggregate Samples, Keep Fusion Lightweight
Anti-patterns include streaming raw `CoreMotion` at full rate or running a heavy on-device ML model continuously; continuous high-rate sampling and heavy compute increase energy use and risk battery regressions. Preferred is to combine `CoreMotion` / `CMPedometer` cadence and `HealthKit` heart-rate samples with lightweight deterministic smoothing (thresholds plus a compact filter such as a small Kalman smoother).

Choose deterministic smoothing when your user base runs across a variety of device models; choose more aggressive ML or filters only on devices where you have measured sufficient CPU and energy headroom. Persist a device-model calibration factor and gate more aggressive smoothing by model identifier to avoid biased pace estimates on different hardware. Sample at higher rates only when relevant activity (for example, a detected stride) is present; otherwise fall back to a lower sampling rate.

```swift
// Burst sampling sketch
if strideDetected {
    motionManager.deviceMotionUpdateInterval = 1.0 / 50.0
} else {
    motionManager.deviceMotionUpdateInterval = 1.0
}
```

Profile live runs and validate the smoothing algorithm under jittered inputs to avoid oscillating guidance in noisy conditions. Measure power cost with Instruments during representative runs and reject outliers before fusion.

## 3. Data Sync, Persistence, And Rollout Gates
### Local-First Checkpoints, Post-Run Sync Only
Anti-patterns include relying on `WCSession` or `CloudKit` for live coaching state, which introduces pairing and network dependency during a run and increases the chance of guidance gaps. Preferred is to persist checkpoints locally (for example, in `CoreData`) and use `WCSession` / `CloudKit` only for post-run uploads or history sync. Design schema changes to be additive and migration-safe; feature-flag storage schema changes and stage them behind rollout gates.

Choose local-first persistence when in-run continuity is required; choose cloud sync only for non-critical history and analytics after the run. Test interrupted migrations by simulating upgrades that are killed mid-migration, and validate migrations on-device under constrained conditions such as low available storage to ensure no corrupt checkpoints block future runs.

```swift
// Save a lightweight checkpoint
func saveCheckpoint(context: NSManagedObjectContext, timestamp: Date, pace: Double) {
    let cp = Checkpoint(context: context)
    cp.timestamp = timestamp
    cp.pace = pace
    try? context.save()
}
```

Stage schema changes behind feature flags and validate rollback and interrupted upgrades during staged rollouts so users do not encounter blocking failures mid-event.

## 4. Sensor-to-Output Validation And Reliability
### Test The End-To-End Path With Synthetic Inputs
Anti-patterns include ad-hoc logs, unreproducible test runs, and relying solely on manual QA for pacing regressions. Preferred is automated `XCTest` suites that inject jittered `HKQuantitySample` and `CoreMotion` inputs, mark async boundaries with `OSSignposter`, and characterize energy with Instruments' Energy Log on-device. Note that `MetricKit` is not available on watchOS, so field energy aggregation has to come from your own sampled `os_log` records (optionally forwarded to a paired iOS app, which can use `MetricKit`).

Choose unit-level `XCTest` async expectations for invariant testing; choose integration profiling with Instruments for periodic spikes and energy characteristics. Add `OSSignposter` marks at high-level boundaries (ingestion → fusion → pacing output) rather than per-sample to keep traces interpretable. Correlate `OSSignposter` marks with your sampled `os_log` records during staged releases to make post-release diagnostics actionable.

Run Instruments `Time Profiler`, `Allocations`, and the Energy Log on representative multi-hour simulated runs to detect regressions before release. Add structured `os_log` messages for session start/stop and migration failures so postmortems point to meaningful traces.

> Make the watch the source of truth for in-run continuity and build recovery paths that assume the process can be killed at any time.

## Tradeoffs And Pitfalls
Battery vs. accuracy is the primary tradeoff: aggressive sampling improves guidance at the cost of battery. Default to conservative sampling on devices with smaller batteries and gate higher rates by device-model calibration. On-device ML increases CI and rollout complexity; deterministic filters and a compact smoother often provide a reasonable tradeoff between accuracy and maintainability.

Sync dependence introduces failure modes during events—phone or cloud dependence should be avoided for in-run continuity. A local-first design reduces that class of failures but increases the need for careful migration and checkpoint testing. Avoid shipping migrations that have not been validated under realistic failure modes and feature-flag storage changes to validate interrupted upgrades and rollbacks before wide rollout.

## Validation & Observability
### Signals You Need In Production
Instrument three primary signal classes: lifecycle events (`HKWorkoutSession` start/stop and `HKLiveWorkoutBuilder` events), ingestion/fusion boundaries marked with `OSSignposter`, and energy characterization captured with Instruments' Energy Log on-device (watchOS does not provide `MetricKit`). Emit structured `os_log` messages for session starts, stops, migration failures, and checkpoint errors to make postmortems actionable.

Combine unit-level `XCTest` expectations with staged release telemetry thresholds for battery regressions and increased session crash rates. Correlate signpost marks with your sampled energy logs and sampling-rate changes to identify regressions introduced by algorithm updates. Use Instruments on representative devices to surface periodic spikes and memory growth over long simulated runs.

- Use `OSSignposter` at coarse boundaries to keep traces readable.
- Capture energy characteristics with Instruments' Energy Log on-device before and during staged rollouts (`MetricKit` is unavailable on watchOS).
- Record `os_log` structured messages for session lifecycle and migration events.

## Practical Checklist
- [ ] Implement `HKWorkoutSession` lifecycle management with idempotent start/stop and crash-recovery tests.
- [ ] Build a sensor-fusion pipeline combining `CoreMotion`, `CMPedometer`, and `HealthKit` samples with energy-aware sampling policies.
- [ ] Add `OSSignposter` points around pacing decisions and measure energy with Instruments' Energy Log on-device during staged runs.
- [ ] Create `XCTest` suites that inject jittered sensor samples and assert pacing invariants.
- [ ] Persist checkpoints in `CoreData` with additive migrations and feature-flagged rollouts.
- [ ] Gate rollouts with telemetry thresholds (battery regressions, session crash rate, guidance error reports).

## Closing Takeaway
Make the watch the authoritative source for live coaching when you need in-run continuity: use `HKWorkoutSession` for lifecycle, fuse `CoreMotion` and `HealthKit` with energy-aware sampling, persist checkpoints locally, and instrument the pacing path with `OSSignposter` and structured `os_log`. Validate behavior with `XCTest` and Instruments (including the Energy Log), and phase rollouts behind telemetry gates so you can iterate with reduced risk.

## Swift/SwiftUI Code Example

```swift
import SwiftUI
import Observation
import HealthKit

@MainActor @Observable class RunCoach {
    let healthStore = HKHealthStore()
    var workoutSession: HKWorkoutSession?
    var isActive: Bool = false
    var targetPace: Double = 360.0 // seconds per km
    var lastCheckpoint: Date?

    // Start a system-managed workout so the watch is the source of truth
    func startWorkout() throws {
        let config = HKWorkoutConfiguration()
        config.activityType = .running
        config.locationType = .outdoor
        // Use the current initializer; init(configuration:) is deprecated.
        let session = try HKWorkoutSession(healthStore: healthStore, configuration: config)
        workoutSession = session
        // startActivity(with:) is synchronous and non-throwing.
        session.startActivity(with: Date())
        isActive = true
        lastCheckpoint = Date()
    }

    func endWorkout() {
        guard let session = workoutSession else { return }
        // end() is synchronous and non-throwing.
        session.end()
        workoutSession = nil
        isActive = false
    }

    func createCheckpoint() {
        lastCheckpoint = Date()
    }
}

struct RunCoachView: View {
    @State private var coach = RunCoach()

    var body: some View {
        VStack(spacing: 8) {
            Text(coach.isActive ? "Running — target pace \(Int(coach.targetPace))s/km" : "Ready")
            HStack {
                Button("Start") {
                    try? coach.startWorkout()
                }
                Button("Checkpoint") {
                    coach.createCheckpoint()
                }
                Button("End") {
                    coach.endWorkout()
                }
            }
        }
        .padding()
    }
}
```

## References

- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
