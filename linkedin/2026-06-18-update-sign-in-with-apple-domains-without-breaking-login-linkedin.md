Sign in with Apple outages during a domain change rarely come from Swift—they come from config. And with Apple unifying relay addresses under `private.icloud.com`, auth and email assumptions that only match legacy domains will quietly break returning users.

- Keep the existing Service ID and register both exact redirect URLs. `ASWebAuthenticationSession` treats mismatches as cancellations, so scheme/host/path must be identical.
- Run dual domains in `com.apple.developer.associated-domains` and publish a valid AASA (no redirects, `application/json`) before shifting any traffic.
- Map Apple identities to your own `accountId` using verified `sub` from the `ASAuthorizationAppleIDCredential.identityToken`; accept both App ID and Service ID audiences during the transition.
- Instrument with `OSSignposter` and `Logger`, and gate the redirect switch behind a remote flag to canary live traffic safely.
- Update outbound email rules to allow `private.icloud.com` alongside `privaterelay.appleid.com` and `icloud.com`.

Choose a new Service ID only if you can force relinking and ship an explicit account-link flow; otherwise preserve the current Service ID to avoid duped accounts.

Concrete tools: `ASAuthorizationController`, `ASWebAuthenticationSession`, `OSSignposter`, and associated domains entitlements.

How are you gating your redirect flip—feature flag, staged DNS, or both—and what signals tell you

#iOS #Swift #SwiftUI #iOSArchitecture #SoftwareArchitecture
