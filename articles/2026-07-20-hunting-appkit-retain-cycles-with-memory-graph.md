# Hunting AppKit Retain Cycles with Memory Graph

AppKit windows that visually close but stay alive can snowball into real incidents. A retained `NSViewController` tree keeps `NSTableCellView` instances and cached layouts around, turning into scrolling jank and rising memory. The Memory Graph exposes ownership paths fast; the work is turning those findings into durable fixes you can verify and keep from regressing.

*All code in this article targets macOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters

Long‑running desktop apps sit open for hours. A forgotten `NotificationCenter` token, a repeating `Timer`, or a strong delegate can hold an entire view hierarchy. Users feel this as “gets slow after a while” or “uses a lot of RAM,” especially after repeated open/close cycles. Swift closures plus AppKit delegates and notifications magnify the edges: a closure without `[weak self]` can retain a controller chain indefinitely. Normalize Debug Memory Graph and Instruments to reduce triage time and stop shipping “mystery bloat.”

## 1. Map The Territory With Memory Graph Debugger

### When To Use Memory Graph Versus Instruments

Choose Debug Memory Graph when you need concrete retain paths and strong‑reference dominators in a live process; choose Instruments > Allocations when you need growth trends across time and flows. Memory Graph can point from your leaked `NSViewController` to the `NotificationCenter` token or closure that’s holding `self`, while Allocations shows whether types expand with each open/close cycle.

> If the Memory Graph shows no path, the object may be legitimately alive — don’t “weakify” randomly. Prove lifetime with a second tool.

### Snapshot Discipline

Avoid guessing from heap size. Take structured snapshots: drive the flow multiple times, then let the runloop settle so transient references clear. Don’t capture while paused on breakpoints; suspended state and LLDB locals can masquerade as owners and waste time. Cross‑check with a longer Allocations run to catch leaks that burst and then quiesce.

```swift
import UIKit
import Foundation

@MainActor
func exerciseWindowOpenClose(iterations: Int) {
  guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else {
    return
  }
  for _ in 0..<iterations {
    var window: UIWindow? = UIWindow(windowScene: scene)
    let vc = UIViewController()
    vc.view.backgroundColor = .systemBackground
    window?.rootViewController = vc
    window?.makeKeyAndVisible()
    RunLoop.current.run(until: Date().addingTimeInterval(0.5))
    window?.isHidden = true
    window = nil
    RunLoop.current.run(until: Date().addingTimeInterval(0.5))
  }
}```

In CI or reproducibility harnesses, record the exact steps used for the snapshot, including any delays, so a failing build can be re‑examined with the same timing.

## 2. AppKit Hotspots: Where Cycles Hide

### Notifications, Timers, And Delegates

A high‑yield fix in production is cleaning up `NotificationCenter` observers and repeating timers. Utility windows and popovers opened and closed mid‑session are common culprits. Prefer timers you own and cancel over runloop‑owned repeating timers. Store notification tokens and remove them on a lifecycle event you control.

```swift
import AppKit

@MainActor
final class PreferencesViewController: NSViewController {
  private var token: Any?
  private var timer: DispatchSourceTimer?

  override func viewDidLoad() {
    super.viewDidLoad()

    token = NotificationCenter.default.addObserver(
      forName: NSApplication.didBecomeActiveNotification,
      object: nil,
      queue: .main
    ) { [weak self] _ in
      self?.refreshUI()
    }

    let t = DispatchSource.makeTimerSource(queue: .main)
    t.schedule(deadline: .now() + 30, repeating: .seconds(30))
    t.setEventHandler { [weak self] in self?.refreshBackgroundData() }
    t.resume()
    timer = t
  }

  override func viewWillDisappear() {
    super.viewWillDisappear()
    if let token { NotificationCenter.default.removeObserver(token) }
    timer?.cancel()
    timer = nil
  }

  private func refreshUI() {}
  private func refreshBackgroundData() {}
}
```

Choose `NSWindowDelegate.windowWillClose(_:)` or observe `NSWindow.willCloseNotification` for guaranteed teardown when windows churn; choose `deinit` cleanup only for objects that cannot participate in cycles by construction. When a window is minimized or hidden, `deinit` won’t fire, so rely on window lifecycle hooks for removing observers and cancelling timers.

### Decisions That Prevent Leaks

- Use weak delegates for `NSPopover`, `NSWindowController`, `NSCollectionView`, and `NSTableView` where appropriate.
- Centralize observer cleanup in `windowWillClose(_:)` or a custom `teardown()` you can call reliably.
- Avoid repeating `Timer` instances owned by the runloop when async work can outlive the owner; prefer explicit `DispatchSourceTimer` ownership you can cancel.

For testability, add logging around close events so you can correlate teardown calls with Memory Graph snapshots in failures.

## 3. Break Cycles With Explicit Ownership

### Weak Captures, Weak Delegates, And Weak Sets

Slapping `[weak self]` everywhere is not a strategy; neither is `unowned` by default. Use `weak` in closures that cross async boundaries or are owned by runloops (`DispatchSourceTimer`, `Task`, `NSOperation`). Use `unowned` only when the closure lifetime is provably shorter than `self`, and a crash is preferable to a leak. Custom observer registries backed by strong arrays can retain tokens; prefer `NSHashTable.weakObjects()` so the registry does not own its members.

```swift
import AppKit

protocol SidebarControllerDelegate: AnyObject {
  func sidebarDidSelectItem(id: String)
}

@MainActor
final class SidebarController: NSViewController {
  weak var delegate: SidebarControllerDelegate?

  private let observers = NSHashTable<AnyObject>.weakObjects()
  private var badgeTimer: DispatchSourceTimer?

  override func viewDidLoad() {
    super.viewDidLoad()

    let token = NotificationCenter.default.addObserver(
      forName: NSWindow.didBecomeKeyNotification,
      object: view.window,
      queue: .main
    ) { [weak self] _ in
      self?.reloadIfNeeded()
    }
    observers.add(token as AnyObject)

    let t = DispatchSource.makeTimerSource(queue: .main)
    t.schedule(deadline: .now() + 5, repeating: .seconds(60))
    t.setEventHandler { [weak self] in self?.refreshBadges() }
    t.resume()
    badgeTimer = t
  }

  override func viewWillDisappear() {
    super.viewWillDisappear()
    for token in observers.allObjects {
      NotificationCenter.default.removeObserver(token)
    }
    observers.removeAllObjects()
    badgeTimer?.cancel()
    badgeTimer = nil
  }

  private func reloadIfNeeded() {}
  private func refreshBadges() {}
}
```

Choose `weak` captures when tasks can outlive the controller or be scheduled by `DispatchQueue`; choose `unowned` captures only in strictly synchronous, tightly‑scoped callbacks where `self` is guaranteed to outlive the closure. In reviews, require a one‑line lifetime proof next to `unowned` so future refactors don’t silently introduce crashes.

## 4. Table And Collection Views: Data Flow Without Backreferences

### Anti‑Pattern To Preferred Pattern

Cells and diffing closures that call back into the controller are a classic leak. The data source holds the closure; the closure captures `self`; the controller holds the data source — cycle complete. If your `NSTableView` or `NSCollectionView` uses callback‑heavy adapters, ensure they do not store closures that retain `self` unless the adapter is guaranteed to outlive the controller.

```swift
// ❌ Before: closure captures controller strongly
dataSource.apply(snapshot, animatingDifferences: true) {
  self.didFinishReload()
}

// ✅ After: capture weak references and tolerate nil
dataSource.apply(snapshot, animatingDifferences: true) { [weak dataSource, weak self] in
  guard dataSource != nil else { return }
  self?.didFinishReload()
}
```

Choose adapters that accept delegates (`weak`) when you expect controllers to churn; choose closure‑based adapters only when they are owned by a longer‑lived coordinator and won’t retain `self`. These views may cache cells and layout state, so a retained data source can keep `NSTableCellView` instances alive after the window closes; after closing, verify in Debug Memory Graph that the data source is gone.

### Choose A Coordinator When Lifetimes Diverge

If timers, observers, and adapters extend beyond a view controller’s lifetime, introduce a window coordinator that owns them and performs teardown at `windowWillClose(_:)`. Keep controllers lean and ephemeral.

```swift
@MainActor
final class WindowCoordinator: NSObject, NSWindowDelegate {
  private weak var window: NSWindow?
  private var timers = [DispatchSourceTimer]()
  private let observers = NSHashTable<AnyObject>.weakObjects()

  init(window: NSWindow) {
    self.window = window
    super.init()
    window.delegate = self
  }

  func windowWillClose(_ notification: Notification) {
    for t in timers { t.cancel() }
    timers.removeAll()
    for token in observers.allObjects {
      NotificationCenter.default.removeObserver(token)
    }
    observers.removeAllObjects()
  }
}
```

Choose a per‑window coordinator when teardown ordering matters and shared state risks cross‑retention; choose a shared coordinator only for stateless services where windows are truly peers. For observability, emit signposts during open/close to line up lifecycle events with allocation deltas.

## 5. Migration And Rollout At Scale

### Canary First, Then Expand

Ownership refactors deserve a controlled rollout. Gate new teardown hooks and weak delegate changes behind a single flag exposed through a feature‑flag source of truth, and roll out to a small internal ring first.

```swift
struct FeatureFlags {
  var useWindowCoordinatorCleanup = false
}

@MainActor
final class AppBootstrap {
  private var flags: FeatureFlags

  init(flags: FeatureFlags) { self.flags = flags }

  func start(window: NSWindow) {
    if flags.useWindowCoordinatorCleanup {
      _ = WindowCoordinator(window: window)
    }
  }
}
```

Choose a feature‑flagged rollout when multiple ownership edges change and failure modes could be subtle; choose a single‑shot migration only for trivially provable, isolated fixes. Sanitizers such as `Address Sanitizer`, `Malloc Scribble`, and `Guard Edges` surface invalid frees during canary, but final validation should use unsanitized builds in Instruments > Allocations because sanitizers alter timing.

## Tradeoffs And Pitfalls

- Weakifying everything avoids cycles but can drop updates you meant to deliver. When work must outlive a controller, move ownership to a coordinator or model with the correct lifetime.
- Debug Memory Graph is point‑in‑time. Short spikes may never appear. Pair it with longer Allocations sessions and per‑flow memory tests to see deltas across interactions.
- Cleanup in `deinit` is ineffective when the cycle prevents `deinit`. Put `removeObserver` and `cancel()` calls in lifecycle hooks that always fire, such as `windowWillClose(_:)` or a coordinator’s `stop()`.
- Capturing `self` as `unowned` inside `Task` or `DispatchQueue.asyncAfter` can crash under close/reopen churn. If lifetimes are not identical, use `weak` and handle the optional.
- `NSTableView` and `NSCollectionView` adapters often hide closures deep inside. Audit them for captures, not just top‑level controllers.

## Validation And Observability

Bake memory into tests and make timelines legible in tools. Use `XCTMemoryMetric` to exercise open/close cycles and fail on sustained growth. In Instruments, run longer Allocations sessions on canary builds; confirm fixes with a Leaks pass so you don’t just hide a cycle behind timing. Annotate lifecycle with `OSSignposter` and `os_log` to reconcile counts against tool traces, and after release, monitor crash breadcrumbs for init/teardown mismatches and memory pressure terminations.

```swift
import XCTest
import OSLog

@MainActor
final class AppWindowController {
  func showWindow(_ sender: Any?) {}
  func close() {}
}

@MainActor
final class WindowLifecycleMemoryTests: XCTestCase {
  func testWindowOpenCloseMemory() {
    let metric = XCTMemoryMetric()
    let signposter = OSSignposter(subsystem: "com.example.MyMacApp", category: "Lifecycle")

    measure(metrics: [metric]) {
      let openState = signposter.beginInterval("OpenWindow")
      let wc = AppWindowController()
      wc.showWindow(nil)
      RunLoop.current.run(until: Date().addingTimeInterval(1.0))
      signposter.endInterval("OpenWindow", openState)

      let closeState = signposter.beginInterval("CloseWindow")
      wc.close()
      RunLoop.current.run(until: Date().addingTimeInterval(1.0))
      signposter.endInterval("CloseWindow", closeState)
    }
  }
}```

Stabilize CI by pinning datasets, delaying measurements until idle, and using threshold bands tight enough to catch regressions but loose enough to avoid flakes.

## Practical Checklist

- [ ] Capture a baseline Debug Memory Graph after realistic user flows; reproduce with repeated open/close and small idle gaps.
- [ ] Run a longer Instruments > Allocations session to confirm no slow creep; add a quick Leaks pass after fixes.
- [ ] Audit all `NotificationCenter` observers, timers, and delegates; make delegates `weak`, store tokens, and remove them in `windowWillClose(_:)`.
- [ ] Prefer timers you own and cancel; call `cancel()` in teardown.
- [ ] Introduce `NSHashTable.weakObjects()` for observer registries; avoid arrays that accidentally retain members.
- [ ] Add `XCTMemoryMetric` tests for key flows and tune thresholds to reduce noise.
- [ ] Gate high‑risk ownership changes behind a feature flag; canary with diagnostics on, then confirm on unsanitized builds.
- [ ] Re‑run Memory Graph after fixes and attach retain‑path screenshots to code review for shared understanding.

## Closing Takeaway

Treat retain cycles as an operational risk, not a one‑off bug hunt. Use Debug Memory Graph to see ownership, Allocations to see trends, and Leaks to confirm you actually broke the cycle. Default to `weak` on async closures and delegates, and perform teardown in lifecycle hooks you can guarantee. When leaks slip through, observability and staged rollout turn a mystery into a routine fix — and keep long‑running macOS apps stable over time.

## Swift/SwiftUI Code Example

```swift
import AppKit

final class ListViewController: NSViewController, NSTableViewDataSource, NSTableViewDelegate {
    private let tableView = NSTableView()
    private var notificationToken: NSObjectProtocol?
    private weak var refreshTimer: Timer?
    private var items: [String] = (0..<1_000).map { "Row \($0)" } // large data to make leaks obvious

    override func loadView() {
        let scroll = NSScrollView()
        scroll.documentView = tableView
        tableView.addTableColumn(NSTableColumn(identifier: .init("main")))
        tableView.headerView = nil
        tableView.delegate = self
        tableView.dataSource = self
        self.view = scroll
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        notificationToken = NotificationCenter.default.addObserver(
            forName: NSApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.tableView.reloadData()
        }

        let timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let self else { return }
            // simulate model update that would have leaked if self were strongly captured
            items.shuffle()
            tableView.reloadData()
        }
        refreshTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    deinit {
        if let token = notificationToken {
            NotificationCenter.default.removeObserver(token)
        }
        refreshTimer?.invalidate()
    }

    func numberOfRows(in tableView: NSTableView) -> Int { items.count }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let id = NSUserInterfaceItemIdentifier("cell")
        let cell = tableView.makeView(withIdentifier: id, owner: nil) as? NSTableCellView ?? {
            let v = NSTableCellView()
            v.identifier = id
            v.textField = NSTextField(labelWithString: "")
            v.addSubview(v.textField!)
            return v
        }()
        cell.textField?.stringValue = items[row]
        return cell
    }
}
```

## References

- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
