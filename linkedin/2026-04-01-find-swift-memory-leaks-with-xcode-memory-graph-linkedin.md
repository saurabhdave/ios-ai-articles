Memory growth during long sessions often points to an ownership leak, not a rendering bug — catch it with repeatable `Xcode Memory Graph` snapshots and diffs before assuming layout is the culprit.

- Capture a baseline snapshot, run a reproducible user flow, capture again and diff; consider archiving snapshots as CI artifacts for postmortems.
- Audit closure captures and delegates: prefer `weak` captures when the referent can become nil; reserve `unowned` for relationships you can prove are hierarchical.
- Scope `AnyCancellable` to owner lifetimes and cancel explicitly in lifecycle hooks to avoid view controllers retaining subscriptions.
- Use `Instruments` Allocations/Leaks and correlate intervals with `OSSignpost` events — this can help map production traces back to the observed leak window.

When memory cost is unacceptable, prefer eager cleanup; when timing-sensitive crashes are a risk, prefer conservative cleanup.

Are you capturing Memory Graph snapshots in CI or running deterministic XCTest flows to validate ownership fixes? Share one challenge you’ve seen and how you traced it.

#iOSDev #Swift #MobileEngineering #Instruments #Observability
