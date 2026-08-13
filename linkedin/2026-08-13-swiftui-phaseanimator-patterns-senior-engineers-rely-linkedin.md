Animation bugs hide in plain sight: overlapping fades after a copy tweak, jitter when siblings animate independently, scroll hitches from redundant re-renders. When this shows up, adding more `withAnimation` often isn’t the fix—phase-driven motion can be.

`PhaseAnimator` helps you express explicit steps that map to your UI’s state changes, which can make behavior easier to reason about across refactors and feature flags.

- Name the phases and bind them to domain state; replace chains of `withAnimation` blocks with a compact `PhaseAnimator` over a few well-defined steps.
- Drive phases from model updates and respect `accessibilityReduceMotion`; skip or shorten transitional steps when motion should be reduced.
- Measure, don’t guess: use `OSSignposter` around transitions and validate on device with Instruments (Time Profiler, Core Animation) before merging.
- Keep one rendering core and swap only the motion driver behind a feature flag; avoid mixing implicit and phase-driven animations on the same property.
- Prefer state-driven phases; use `TimelineView` for truly time-based effects, and pause appropriately via `scenePhase` and system power conditions.

Tradeoff: reach for phase-driven

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
