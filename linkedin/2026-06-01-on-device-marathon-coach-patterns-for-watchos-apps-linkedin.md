Short guidance gaps at crowded race starts can come from coaching logic running off-watch—phone or network dependencies can break continuity. Make the watch the source of truth for live coaching where possible.

- Use the system-managed workout lifecycle: drive in-run continuity with `HKWorkoutSession`/`HKLiveWorkoutBuilder`, make start/stop idempotent, and add crash-recovery checkpoints.
- Keep sensor fusion lightweight: combine `CoreMotion`/`CMPedometer` cadence with `HealthKit` HR samples and a compact deterministic smoother; consider burst-sampling only when a stride is detected to limit work.
- Persist local-first checkpoints (Core Data) and defer `WCSession`/cloud sync to post-run to reduce the impact of pairing or network interruptions during events.
- Instrument coarse boundaries with `OSSignpost` and collect energy/quality signals via `MetricKit`; correlate signposts with MetricKit payloads for actionable postmortems.

Prefer deterministic smoothing unless device profiling shows safe CPU/energy headroom for continuous on-device ML.

What tradeoff has surprised you most when moving coaching logic onto the watch? Want to walk through sampling-rate tradeoffs or migration strategies for specific older watch models—tell me the target device and constraints.

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
