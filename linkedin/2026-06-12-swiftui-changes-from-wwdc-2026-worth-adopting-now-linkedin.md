Converting to modern SwiftUI often changes runtime behavior more than code size — cancellation, invalidation, and state restoration can surface in production if you treat this as a purely syntactic swap.

Prefer `Layout` for reusable, cacheable measurement; keep `GeometryReader` for one-off probes to avoid repeated layout work.
Use a single-owner observable pattern (one clear owner for mutable state) to reduce unexpected multiplied renders instead of passing the same observable through many view layers.
Tie concurrent work to explicit cancellation boundaries with `Task`, `TaskGroup`, or view-scoped tasks, and add async XCTest assertions that tasks cancel on lifecycle transitions.
Prototype risky screens with `UIViewControllerRepresentable` when you need to validate scheduling and platform interop on device before a full rewrite.
Instrument render-critical paths and async boundaries with signposts and profile on device (Time Profiler, Allocations, Instruments).

Choose `NavigationStack` with a value-typed router when deterministic restoration and deep-linking matter.

Which screen in your app would you gate behind a feature flag to validate renders, cancellation, and restoration first?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
