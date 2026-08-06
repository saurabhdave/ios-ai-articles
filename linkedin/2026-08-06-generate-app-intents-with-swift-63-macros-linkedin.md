Your build is green, but your intents extension can still miss release if a macro target fails on CI. Worse, a generated member may mask an entitlement or lifecycle issue and your `perform()` can crash without a clear trail. That can break discovery in Siri/Shortcuts/Spotlight.

- Use Swift macros to generate the boring 80% of `AppIntent`/`AppEntity`: titles, descriptions, `parameterSummary`, and `DisplayRepresentation`. Keep `perform()` and identity hand-written.
- Prefer attached macros with clear opt-outs. Synthesize when shapes are uniform; skip when an intent needs bespoke wording, availability,

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
