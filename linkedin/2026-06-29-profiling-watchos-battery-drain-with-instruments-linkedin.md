Tiny inefficiencies sink Apple Watch battery: extra SwiftUI invalidations, stray timers, and too many radio wakeups. The simulator hides this; only an on‑device `Instruments` Energy Log exposes the real cost.

- Start with a 15–20 min Energy Log on physical hardware, covering idle → glance → scroll → tap → background. Save two baseline traces for diffs.
- Correlate spikes with `OSSignposter` intervals like “tap → fetch → render”, then validate causes with `Time Profiler` instead of guessing.
- Shrink SwiftUI work by scoping `@Observable` state locally and stabilizing list identity; confirm wins with back‑to‑back traces.
- Replace repeating timers with debounced, event‑driven tasks; batch network requests using `URLSessionConfiguration.background` and `waitsForConnectivity`. 🔋
- Keep background honest: handle `WKRefreshBackgroundTask`; use `WKExtendedRuntimeSession` only for active, time‑boxed experiences and end it deterministically.

Tradeoff: choose offline test scenarios to attribute UI/CPU cost; choose connected runs to attribute radio/setup overhead. Keep both reproducible.

Tooling to standardize: `Instruments` Energy Log, `Time Profiler`, `NWPathMonitor`, `MetricKit`, `os_log`.

How are you structuring deterministic watchOS scenarios so a spike always maps to a signpost and a code path?

#watchOS #Instruments #SwiftUI #MobilePerformance #AppleWatchDev
