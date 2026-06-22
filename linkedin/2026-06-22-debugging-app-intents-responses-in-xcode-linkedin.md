Shortcuts shows one dialog, your logs insist another? You may be attached to the wrong process—or hitting `@Parameter`/`EntityQuery` timing differences. Trust what the Shortcuts card shows first; then make your instrumentation reflect what the user actually sees.

- Attach the debugger to the host: set the scheme to “Wait for the executable to be launched,” run, then trigger from Shortcuts so you catch the extension host at startup.
- Keep logs focused with `Logger` and confirm the host via `ProcessInfo.processName`; keep `.debug` for suspicious paths to reduce log noise and potential I/O slowdown.
- Stabilize UI text and icons with `displayRepresentation` on every `AppEntity`, not ad hoc strings in `perform()`.
- Make `EntityQuery` resolution cache-friendly; avoid network work during parameter/entity resolution, especially for background paths.
- Prefer returning dialog-style responses when possible; only open the app when a foreground step is truly required.

Tradeoff: consider optional parameters with safe defaults when required fields would trigger slow or unreliable resolution during background runs.

What’s the most reliable step you use to ensure you’re attached to the correct host when debugging App Intents? Share your setup.

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
