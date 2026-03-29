Ad‑hoc frame math sprinkled through view bodies breeds flaky, non‑deterministic layout. Pull spatial rules into focused `Layout` types to get deterministic sizing and easier tests.

- Centralize placement math behind a small `Layout` so you can call `sizeThatFits` in `XCTest` and assert behavior across rotations or Dynamic Type changes.
- Use a minimal `Cache` inside the `Layout` to avoid repeated expensive measurements; document what invalidates it (for example: content changes, `\.sizeCategory`, or orientation).
- Combine custom `Layout` with `LazyVStack`/`LazyHStack` for large collections to avoid measuring every child eagerly.
- Instrument `sizeThatFits` and `placeSubviews` with Instruments or runtime timing (or `OSSignposter`) during rollout to spot hot paths.

When screens include large UIKit surfaces or third‑party `UIView`s, prefer incremental embedding with `UIHostingController` rather than rewriting everything at once.

What tradeoff surprised you most when adopting `Layout`, or how have you handled cache invalidation and flaky measurements migrating UIKit screens into SwiftUI? Share a concrete example.

#SwiftUI #iOSDev #MobileArchitecture #iOS #Swift
