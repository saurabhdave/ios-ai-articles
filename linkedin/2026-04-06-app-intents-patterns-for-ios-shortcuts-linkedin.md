Shortcuts that “do nothing” usually hide preventable failures: intent resolution misses, missing prompts, or long work killed silently — make them diagnosable, not mysterious.

- Define `AppIntent` inputs with `@Parameter` and concrete types (Date, enum) and add `XCTest` round-trip checks for archived shortcut metadata where feasible.
- Keep `perform()` short: return a quick acknowledgement and hand off heavy work to background workers with idempotency keys and retry policies.
- Surface localized, actionable error messages and gate permission-flow changes behind feature flags so support can anticipate new prompts.
- Consider instrumenting entry/exit and I/O boundaries with `OSSignposter` and structured logging, and include correlation IDs so traces can be stitched across services.

Choose typed parameters when the input shape is stable; choose freeform `String` when user intent is genuinely ambiguous.

How have you handled migration of legacy shortcut identifiers in production, and which debugging signals (logs, signposts, telemetry) proved most useful?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
