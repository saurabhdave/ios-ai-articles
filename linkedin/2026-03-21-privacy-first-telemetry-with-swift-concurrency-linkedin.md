Converting completion-handler telemetry to async/await can change cancellation and lifecycle semantics — and that can increase the risk of leaking data or leaving on-disk batches after consent changes.

Practical guardrails I use:

- Validate consent at enqueue time: cancel in-flight `Task`s and remove pending files when consent is revoked, aiming for atomicity where possible.
- Use background delivery (`URLSession` background configuration or `BackgroundTasks`) for resilient uploads, but test revocation semantics end-to-end since batching can increase the window between revocation and delivery.
- Protect identifiers with irreversible hashes or `CryptoKit` HMACs and rotate salts; emit versioned pseudonyms so joins tolerate rotation.
- Add an adapter layer to normalize schemas, run CI contract tests, and validate changes via a shadow or staging path before rolling a schema change to production.

Operational notes:

- Prefer background uploads when network resilience and retry semantics matter; prefer immediate `URLSession.data(for:)` when minimizing revocation latency is the priority.
- Instrument async boundaries with `os_signpost`, collect post-release signals (for example via `MetricKit`), and assert `Task` cancellation behavior with XCTest async expectations.

How are you treating consent boundaries and task lifetimes in your telemetry pipelines? What tradeoff surprised you most when moving to async/await for telemetry delivery?

#iOSDev #Swift #MobilePlatform #iOS #SwiftUI
