If your AppKit window looks fine in Interface Builder but detonates when you drag a corner, it’s usually not a design issue—it’s a constraint system picking the wrong winner. The fix starts by seeing what the solver sees, not by guessing.

- Use `Debug View Hierarchy` to inspect active `NSLayoutConstraint`s, hugging/compression priorities, and `intrinsicContentSize`. Capture screenshots of the failing state.
- Order priorities; don’t tie them. Keep `.required` for truly non‑negotiable edges and ladder the rest with `.defaultHigh`/`.defaultLow`.
- Treat intrinsic sizes as signals. After changing text, symbols, or accessibility, call `invalidateIntrinsicContentSize()` and re-evaluate layout.
- Flatten hierarchies where you can. `NSGridView` helps with cross‑axis alignment; deep nested `NSStackView`s can create churn.
- Validate under runtime conditions: add layout XCTests, profile resize loops

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
