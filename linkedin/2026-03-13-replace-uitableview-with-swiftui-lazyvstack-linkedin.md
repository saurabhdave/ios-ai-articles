Swapping UITableView for SwiftUI LazyVStack? Treat it as a behavioral change, not a drop-in swap — it changes lifecycle, identity semantics, and performance tradeoffs. Teams have moved parts of screens to SwiftUI successfully, but expect different reuse and update behavior.

Practical takeaways:
- Inventory screens as Simple / Moderate / Advanced before you start.
- Prefer LazyVStack for self-contained vertical lists driven by a single source of truth.
- Use UIHostingConfiguration to embed SwiftUI rows incrementally in existing cells; keep diffable data sources (NSDiffableDataSourceSnapshot) where you need deterministic, snapshot-driven updates.
- Gate rollouts with per-screen feature flags, Instruments traces (Allocations/Time Profiler), and focused UI tests for fast-scroll and gesture scenarios.

Decision point: if a screen depends on coordinated, snapshot-driven multi-item animations and strict ordering guarantees, consider keeping UICollectionView + diffable data source — migrating can change animation and update semantics.

Optional snippet — host a SwiftUI row inside a cell:
cell.contentConfiguration = config

Who else is running mixed UIKit/SwiftUI fleets? What pitfalls did you catch in production? 👇

#iOS #SwiftUI #Architecture #EngineeringLeadership #MobileDev
