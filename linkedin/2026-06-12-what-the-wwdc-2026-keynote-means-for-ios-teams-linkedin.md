Migrations to `SwiftUI` and structured concurrency often compile cleanly but can expose timing, cancellation, and partial-write bugs only at runtime — plan for an operational rollout phase.

- Treat framework migration as an operational rollout: add runtime availability guards, use server-side feature flags, and stage releases before wide distribution.
- Instrument hot async boundaries with `OSSignposter` and collect `MetricKit` diagnostics from staged users to help surface CPU, hang, and memory regressions.
- Replace fragile callback wrappers with actor-isolated async APIs and audit `withCheckedThrowingContinuation` sites for multi-resume risks.
- Include at least one end-to-end CI job on real devices that exercises `ScenePhase`/lifecycle transitions to surface background throttling and scheduling issues.

Choose a full rewrite when you need new ownership or UX; keep dual paths when retention-critical flows must remain stable.

How have you correlated signposts, `os_log`, and MetricKit traces during a staged rollout — which signal first alerted you to a migration regression?

#SwiftUI #iOSDev #MobileEngineering #SwiftConcurrency #iOS
