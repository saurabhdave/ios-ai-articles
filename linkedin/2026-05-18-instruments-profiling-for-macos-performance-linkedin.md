A single shared `@Observable` model caused a feed view to render multiple times during scrolling on device — the kind of runtime regression that often only appears under real-device load.

- Prefer device-first profiling for UI and scheduling issues: run `Time Profiler` and `Allocations` against real scroll traces to find call-stack hotspots and allocation churn.
- Add sparse `OSSignposter` spans around top user journeys, validate matching end calls, then narrow your investigation to the fault domains those spans reveal.
- Instrument async lifecycles: mark `Task` creation and cancellation, and prefer supervised scopes (`TaskGroup`) when work should follow a parent lifecycle.
- Gate verbose telemetry behind rollout flags and run `XCTest` performance checks on representative hardware before broad rollout.

Choose unstructured `Task` only when work truly needs to outlive the caller; otherwise prefer structured scopes to reduce the risk of runaway child tasks.

How do you validate cancellation and render isolation on device as part of your release checklist?

#SwiftUI #iOSDev #Performance #MobileEngineering #iOS
