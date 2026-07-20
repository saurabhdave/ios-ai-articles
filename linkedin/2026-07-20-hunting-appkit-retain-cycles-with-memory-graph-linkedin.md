AppKit windows that “close” but keep their `NSViewController` trees alive can turn into scrolling jank and quiet memory creep. The fix starts with seeing the actual owners, not guessing from heap size.

- Use `Debug Memory Graph` to trace strong-reference paths from an `NSViewController` to the `NotificationCenter` token, timer, or closure that’s holding it.
- Pair it with `Instruments > Allocations` for time-based growth; short spikes won’t always appear in a snapshot.
- Teardown where it reliably runs during close: `NSWindowDelegate.windowWillClose(_:)` (remove observers, cancel timers), not only in `deinit`.
- Prefer owned, cancelable timers like `DispatchSourceTimer` over repeating `Timer` tied to the runloop.
- Audit `NSTableView`/`NSCollectionView` adapters: closure callbacks that capture `self` can

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
