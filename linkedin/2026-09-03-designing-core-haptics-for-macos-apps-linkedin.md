Your Mac build can feel perfect on a Force Touch trackpad and completely silent behind a KVM. On macOS, haptics are a capability, not a constant—assume hardware can change at runtime and design for it.

- Query `CHHapticEngine.capabilitiesForHardware().supportsHaptics` before every play; route to `CoreHaptics`, fall back to `NSHapticFeedbackManager`, or no‑op.
- Keep a single warmed `CHHapticEngine` per UI domain with `isAutoShutdownEnabled`; rebuild on `resetHandler`/`stoppedHandler`.
- Externalize cues as `.ahap`, add `-mac` overrides, and tune separately from iPhone patterns.
- Respect focus and intent: throttle cues, offer a user toggle, and suppress when the app is inactive.
- Instrument with `OSSignposter` to measure cold start vs warm play; coalesce error logs by signature.

Tradeoff: Prefer one long‑lived engine over per‑tap creation—unless you have truly isolated latency domains that justify separate graphs.

APIs that matter: `CHHapticEngine`, `CHHapticPattern`, `CHHapticAdvancedPatternPlayer`, `NSHapticFeedbackManager`, `OSSignposter`.

Also: with Rosetta support concluding in macOS 27 and prompts appearing on recent macOS when translation is required, ship Apple silicon native to keep haptics and startup predictable.

How are you gating fallbacks and measuring first‑tap latency across varied desktop setups?

#macOSDev #Swift #CoreHaptics #AppArchitecture #iOS
