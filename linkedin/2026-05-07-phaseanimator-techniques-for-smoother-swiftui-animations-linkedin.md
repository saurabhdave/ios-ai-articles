Flicker, multi-render storms, and orphaned mid-animation views often trace back to scattered `withAnimation` calls and shared observable state. Centralize phase ownership to make motion more predictable.

- Use a single coordinator `ObservableObject` to own named phases and expose read-only state to children so ordering is easier to reason about.
- Assign intent per phase: pick distinct `Animation` or a `Transaction(disablesAnimations:)` path for entrance vs emphasis vs cancellation so behaviors don't collide.
- Map phases to a `UIViewPropertyAnimator` adapter when you need finer interruptibility; keep SwiftUI as the source of truth so rollbacks remain simpler.
- Add UI tests that assert final visual states and simulate cancellations; profile on device with Instruments to spot layer or CPU spikes.

Tradeoff: adopt a coordinator when choreography and ordering matter; for isolated single-property fades, `withAnimation` may be simpler and lower overhead.

Instrument phase boundaries with `OSSignposter` and gate rollout behind a feature flag for safer launches. Who on your team owns phase boundaries and interruption semantics today — would a coordinator reduce or increase test surface for your flows?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
