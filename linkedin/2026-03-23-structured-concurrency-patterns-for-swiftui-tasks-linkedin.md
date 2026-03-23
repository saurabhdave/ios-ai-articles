Orphaned async work and UI updates after navigation are a frequent source of bugs and wasted resources—make task lifetimes explicit instead of sprinkling ad-hoc `Task` spawns.

- Move view-tied async into `ObservableObject` view models and own a cancellable `Task` so teardown cancels background work and avoids UI updates after the view unmounts.
- Use `withTaskGroup` (or `TaskGroup`) to aggregate parallel work and cap concurrency to protect device and backend resources.
- Wrap legacy completion handlers with `withCheckedThrowingContinuation` and keep UI work on the main actor to avoid leaking continuations or updating UI from background contexts.
- Add cooperative cancellation checks with `Task.isCancelled` / `Task.checkCancellation()` and assert cancellation in async unit tests; emit signposts or structured logs for lifecycle tracing.

Choose a view-model-owned `Task` when work should die with a screen; choose a service-owned long-lived `Task` when work must survive navigation.

Example: `private var loadingTask: Task<Void, Never>? // cancel in deinit`

What painful symptom did you hit when migrating to structured concurrency or improving observability? Share one concrete example your team ran into.

#SwiftUI #iOSDev #Concurrency #iOS #Swift
