Cold starts regress, frames drop, and the trace looks “fine.” Without precise, low-overhead markers on hot paths, you’re debugging timestamps and gut feel instead of timelines you can reason about.

- Treat markers as API: stable names, bounded attributes, and a migration plan. Sloppy labels and high-cardinality values can poison aggregation.
- Use `OSSignposter` intervals for startup, navigation, networking, and rendering. Create a fresh `OSSignpostID` per unit of work and end with `defer`.
- Hide instrumentation behind a small wrapper and config flag to tune density at runtime; keep call sites clean and reversible.
- Validate in `Instruments` by correlating `Points of Interest` with `Time Profiler`, and consider gating key intervals in CI with `XCTOSSignpostMetric`.
- Watch for cross-thread issues: prefer separate IDs for sub-operations and avoid stretching a single interval across async boundaries.

Choose intervals when you need timelines you can assert; keep `os_log` for sparse, human-readable breadcrumbs.

`MetricKit` can hint where to dig; targeted signposts can make the repro actionable.

How are you naming intervals and bounding attributes so traces stay readable six months later? Share your taxonomy and what you gate in CI.

#iOSDev #Swift #PerformanceEngineering #Instruments #MobileArchitecture
