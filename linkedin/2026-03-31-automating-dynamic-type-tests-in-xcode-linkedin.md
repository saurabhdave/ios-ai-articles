Visual regressions at accessibility text sizes keep slipping into releases — clipped labels and truncated cells are often predictable and preventable. Run automated Dynamic Type checks in CI so typography issues surface earlier.

- Add fast component tests that construct views with `UITraitCollection(preferredContentSizeCategory: ...)` and assert intrinsic sizes or constraints to catch layout math errors early.
- Reserve snapshot diffs for a small set of high-risk screens at accessibility sizes; store baselines and run these in merge or nightly jobs to reduce PR flakiness.
- Use `XCUITest` launch arguments for a handful of critical end-to-end flows at large `UIContentSizeCategory` values to validate lifecycle and system interactions.
- Emit signposts and structured `os_log` on failures; attach screenshots and logs to failing CI jobs to speed triage.

Choose component `UITraitCollection` tests when PR feedback speed matters; choose snapshots or full-app flows when pixel fidelity or lifecycle behavior needs validation.

Example: `let traits = UITraitCollection(preferredContentSizeCategory: .accessibilityExtraExtraExtraLarge)`

Question: which screens would you include in a minimal accessibility snapshot matrix for your app? Share your shortlist and why.

#iOSDev #Swift #Accessibility #CI #iOS
