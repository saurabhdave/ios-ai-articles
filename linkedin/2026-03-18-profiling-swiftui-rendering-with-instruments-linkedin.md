Frame drops after a staged rollout often trace back to hidden per-frame rendering costs: repeated `body` evaluation, allocation churn, or large compositor uploads — and those costs can be invisible until production load.

Record short, reproducible on-device sessions with `Time Profiler` and `Core Animation` to separate CPU-side `SwiftUI` work from compositor/GPU uploads.

- If profiles show repeated samples in `body` and allocation spikes, focus on tightening state boundaries and moving heavy work off the render path.
- If `Core Animation` shows large backing-store uploads or long layer times, reduce paint cost (less dynamic offscreen content, smaller layers, fewer expensive compositing operations).
- Add `os_signpost` around async work and frame boundaries so traces correlate user actions to expensive work; archive `dSYM` so traces can be symbolicated.

When `Time Profiler` points to allocation churn, favor state-model refactoring; when `Core Animation` dominates, prioritize painting reductions.

Have a trace you want a second pair of eyes on, or a trace-driven tradeoff you debated? Post a summary or DM me a anonymized trace and we’ll compare notes.

#SwiftUI #iOSDev #Performance #Instruments #CoreAnimation
