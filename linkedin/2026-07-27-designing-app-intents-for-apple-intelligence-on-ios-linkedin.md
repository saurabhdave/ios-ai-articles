Siri or system search calls your app and nothing happens? That’s often not UI—it’s a fragile or missing `AppIntent` contract. Treat intents like a headless, public API that can run without scenes and on an unpredictable schedule.

- Model the domain with `AppEntity` + `EntityQuery`; return a small, ranked `suggestedEntities()` and freeze stable identifiers to avoid disrupting saved shortcuts.
- Scope one intent per job. Use explicit `@Parameter` types and write past‑tense dialogs; add a clear `DisplayRepresentation` so entry points are discoverable.
- Keep `perform()` deterministic and UI‑free; isolate mutable state in `actor`s and avoid `@MainActor` unless you’re bridging to UI.
- Make queries async and cancellable; cap results to reduce memory and disambiguation churn; don’t block the main actor with storage or network work.
- Ship behind flags, stage with cohorts, and instrument with `

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
