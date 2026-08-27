A minor rename in a `@Model` can silently drop data. A heavy migration at launch can stall cold start or trigger a crash loop. Treat SwiftData migrations as an operational deploy with observability, not a code refactor. ⚠️

- Version intentionally: define `VersionedSchema` and pin a stable path with `ModelConfiguration(url:)` so you can snapshot and restore under pressure.
- Plan deterministic bridges: use `MigrationPlan` with ordered stages; include every shipped hop so leapfrogging users still migrate safely.
- Control execution: gate `ModelContainer` open behind remote config; instrument with `OSSignposter` to keep migration work off first frame.
- Protect integrity: snapshot stores before first write; add a server kill switch and defer cleanup/compaction via `BackgroundTasks`.
- Prove it: ship `XCTest` fixtures that open old stores and assert invariants; emit structured `os_log` with stage names and counts.

Choose launch-time upgrades only when profiling shows they’re lightweight and bounded; defer or user-acknowledge when transforms are heavy or data volume is unknown.

How are you gating and observing SwiftData migrations today, and where have you drawn the line between “launch-time” and “deferred” in production?

#SwiftData #iOSDev #MobileArchitecture #Swift #SwiftUI
