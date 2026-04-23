Converting free-text intent slots to `AppIntent` often pushes parsing errors from QA into production — misrouted intents, misclassifications, and new support cases can appear quickly.

- Replace catch-all `String` slots with typed `@Parameter` fields (`UUID`, `Date`, enums) to reduce ambiguous routing and make follow-up dialogs clearer.
- Add deterministic `XCTest` coercion tests and synthetic prompt scenarios to catch misclassification before rollout.
- Instrument parsing and execution with `OSSignposter` and structured `os_log`; collect aggregated signals (respecting privacy) for post‑deploy analysis.
- Gate exposure with server-side feature flags or percentage rollouts and keep `INIntent` fallbacks during migration.

Choose strict parameter schemas when misclassification risk or sensitive inputs exist; use permissive `String` only when true free-form prose is required.

How are you validating system-driven prompts in production, and which runtime signals (error rate, misrouting, user complaints, metric anomalies) typically trigger a rollback in your org?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
