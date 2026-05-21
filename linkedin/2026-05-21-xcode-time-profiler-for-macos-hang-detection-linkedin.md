A frozen macOS window during a customer demo erodes trust instantly — many stubborn hangs only reproduce on device because the simulator’s environment differs.

- Start with `Time Profiler` captures on the affected hardware; follow with focused process-only captures to narrow stacks. 
- Correlate samples with `OSSignposter` intervals and structured `os_log` so timestamps map to named operations. 
- Gate verbose tracing behind runtime flags and run targeted `Allocations` captures to help rule out memory-pressure stalls. 
- Add `XCTest` performance assertions that run on device in CI to detect CPU-time regressions.

Choose system-wide sampling when you suspect driver or kernel activity; choose process-only when you need clearer app stacks.

Callout: use `OSSignposter`, `os_log`, `Time Profiler`, and `Allocations` together, and automate `dSYM` verification before postmortem analysis.

Snippet:
signposter.endInterval(id)

How do you validate device-only hangs in your CI/device lab runs?

#Swift #iOSDev #Performance #Xcode #macOS
