A hang is the ugliest failure: no crash, just a frozen UI. The fastest path from “feels stuck” to “this line is blocking the main thread” is a clean Instruments Time Profiler trace and a careful read of the main-thread stack.

- Record on a physical device with Time Profiler and enable “Record Waiting Threads.” Capture long enough to include the stall, then stop and save the trace.
- Verify symbolication before drawing conclusions. Unsymbolicated stacks turn attribution into guesswork.
- Start at the main thread, expand system frames until you hit your code, and look for synchronous I/O, decoding, image work, or cross-queue waits.
- Move heavy work off the main thread and reenter via `@MainActor`. Align `DispatchQoS.QoSClass.userInitiated` for UI-visible tasks; use lower QoS for prefetching or background work.
- Add signposts with `OSSignposter` to bracket decode, image processing, and layout, then re-profile to confirm time moved off the main thread.

If you’ve chased a nasty UI stall recently: what was the actual blocker on your main thread, and what signpost or stack clue cracked it?

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
