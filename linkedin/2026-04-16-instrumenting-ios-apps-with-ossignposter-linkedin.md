High-cardinality ad-hoc logs can bury real latency and causal boundaries — use `OSSignposter` to emit bounded, platform-visible intervals instead.

- Create one `OSSignposter` per subsystem and use stable signpost names; attach dynamic values with `os_log` format specifiers and privacy markers to keep signal usable.
- Generate an `OSSignpostID` at logical boundaries and pass it explicitly across `Task` hops or queues to help preserve correlation.
- Gate rollout behind a remote-config flag and sample a small fraction of users while you validate signal usefulness and resource impact; profile staging with `Instruments`.
- Test ordering (not absolute timestamps): use `XCTest` async expectations to assert signpost presence and sequence.

Choose sampling to limit telemetry volume during rollout; consider enabling broadly only after you’ve validated cost and the trace signal.

Callouts: `OSSignposter`, `MetricKit`, `Instruments`, `os_log`.

What tradeoff has surprised you most when adopting `OSSignposter` or sampling traces in production?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
