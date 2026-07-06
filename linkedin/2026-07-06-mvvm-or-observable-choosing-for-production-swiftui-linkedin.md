A feed that jitters on device but “looks fine” in Simulator is often observation, not layout. I traced a scroll hitch to a single `@Observable` retained by two ancestors—body executions fanned out and taxed frames.

- Give each `@Observable` exactly one owner and pass references downward. Don’t cache or re-wrap the same instance in multiple ancestors.
- Treat every `View.body` read as a subscription; narrow reads and move derived work into mutators so invalidations stay local.
- Instrument mutations with `OSSignposter`, profile on device with Time Profiler, and correlate mutate → render waves. 🔬
- Gate migrations behind a provider façade so you can swap implementations and roll back without touching call sites.
- Add render-count tests for hot paths (scroll, type-ahead); assert idempotence so no-op state sets don’t re-render.

Choose `@Observable` when your ownership graph is single-writer and explicit; keep MVVM façades where UIKit or cross-platform surfaces remain, and flip via a feature flag.

What guard

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
