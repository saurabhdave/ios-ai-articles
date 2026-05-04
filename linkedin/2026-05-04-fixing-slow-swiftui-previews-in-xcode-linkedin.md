Shared state high in the view tree can silently slow down SwiftUI previews — you notice it once `View.body` starts re-evaluating constantly during interaction.

- Prefer focused `PreviewProvider` fixtures for rapid visual feedback and keep a single small integration preview per screen to catch environment-driven interactions.
- Set `BUILD_ACTIVE_ARCH_ONLY = YES` for your debug/dev scheme so local builds target the current architecture and compile faster.
- Consider a slim preview build in CI that runs frequently and produces lightweight artifacts (XCResult or similar) for regression checks.
- Instrument on a device with signposts and capture a short Instruments Time Profiler trace when you change ownership or state patterns to validate impact.

Choose focused previews for speed; use integration previews sparingly to validate cross-cutting state.

When you change ownership patterns, do you run a quick device trace first or rely on automated CI checks? Share the tradeoffs you’ve found.

#SwiftUI #iOSDev #Performance #Xcode #iOS
