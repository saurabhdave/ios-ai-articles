# Update Sign in with Apple Domains Without Breaking Login

Domain changes for Sign in with Apple look like DNS chores until they lock real users out. Miss a trailing slash on a redirect, swap a Service ID, or publish a bad AASA file and your logs fill with “canceled” errors while returning customers cannot get back in. The fix isn’t clever Swift; it’s a cautious migration plan that preserves identity and keeps both domains alive long enough to prove the switch is safe.

*All code in this article targets iOS 26+ and Swift 6.2 unless noted otherwise.*

## Why This Matters
Sign in with Apple is strict by design. Redirect URLs must match exactly; `ASAuthorizationController` (native) and `ASWebAuthenticationSession` (web) flows can yield different Apple user identifiers depending on whether you use an App ID or a Service ID; and Universal Links depend on correct `com.apple.developer.associated-domains` entitlements and a valid AASA file. Apple has announced that email domains for Sign in with Apple and Hide My Email will be unified under `private.icloud.com`, with new relay addresses using that domain and existing addresses on `privaterelay.appleid.com` and `icloud.com` continuing to forward. If your authentication or outbound email logic assumes only the legacy domains, passwordless and email-based flows can fail during a domain cutover.

> Treat domain updates like an authentication migration with rollback, not a website rename.

## 1. Map The Identity Surface Area Before You Cut Over
### Anchor: `ASAuthorizationAppleIDProvider` And Identifier Parity
The native flow via `ASAuthorizationController` yields a `user` identifier scoped to your App ID. The web flow via a Service ID yields a different `user` identifier. Assuming they’re the same is how duplicate accounts happen when users move between native and web paths during a domain change.

- Anti-pattern: keying accounts directly by `ASAuthorizationAppleIDCredential.user`.
- Preferred: persist a stable internal `accountId` and keep a 1:N table of Apple `user` strings mapped to it across App ID and Service ID.

Use the native API cleanly and keep the web flow for parity, but link identities server-side:

```swift
import AuthenticationServices

@MainActor
final class AppleSignInCoordinator: NSObject, ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {
    private let completion: (Result<ASAuthorizationAppleIDCredential, Error>) -> Void

    init(completion: @escaping (Result<ASAuthorizationAppleIDCredential, Error>) -> Void) {
        self.completion = completion
    }

    func start() {
        let provider = ASAuthorizationAppleIDProvider()
        let request = provider.createRequest()
        request.requestedScopes = [.email, .fullName]

        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.presentationContextProvider = self
        controller.performRequests()
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            completion(.failure(NSError(domain: "SignIn", code: -1)))
            return
        }
        completion(.success(credential))
    }

    func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        completion(.failure(error))
    }

    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { ($0 as? UIWindowScene)?.keyWindow }
            .first ?? UIWindow()
    }
}
```

- If you already have users signed in via the web flow, link explicitly.
- If you’re rebranding or moving to a new domain and cannot force a clean start, link explicitly.
- If you are launching Sign in with Apple for the first time and accept some edge cases from private relay addresses, link implicitly by email match.

Operationally, verify in a staging environment that both flows resolve to one `accountId` when a tester uses both native and web paths in sequence.

## 2. Run Dual Domains And Verify AASA On Real Devices
### Anchor: `com.apple.developer.associated-domains`, `applinks:`, `webcredentials:`, And AASA
Swapping the old domain for the new one in your entitlements and shipping immediately can break Universal Links and password autofill. Devices cache association files, CDNs can rewrite headers, and any redirect on `/.well-known/apple-app-site-association` can cause Safari opens instead of deep links.

- Anti-pattern: remove the old domain from `com.apple.developer.associated-domains` and publish the new AASA in the same release.
- Preferred: add the new domain alongside the old, publish a correct AASA, and ship an app update that includes both `applinks:` and `webcredentials:` before any traffic shift.

Minimum device-side checks:
- Verify `200 OK`, `application/json`, and no redirects for `/.well-known/apple-app-site-association`.
- Confirm the new domain is verified in the device’s Associated Domains developer tooling.

Keep a concrete test route behind the new domain and verify end-to-end deep link handling in a debug build. Staged adoption gives devices time to refresh associations and avoids flakiness during propagation.

## 3. Keep The Same Service ID And Register Both Redirects
### Anchor: Service ID, `ASWebAuthenticationSession`, And Exact Redirect Matching
Creating a brand-new Service ID for the new domain avoids touching existing config, but it also generates a fresh set of Apple `user` identifiers for the web flow. Keep the existing Service ID and register both old and new redirects during the transition.

- Anti-pattern: new Service ID, single redirect URL, and a hopeful QA pass.
- Preferred: existing Service ID, both exact redirect URLs registered, and production values used in tests.

`ASWebAuthenticationSession` cancels on redirect mismatches. The symptom is a generic canceled error shortly after starting the session. Test production URLs with exact scheme, host, and path.

```swift
import AuthenticationServices

@MainActor
final class WebAppleAuth {
    private var session: ASWebAuthenticationSession?

    func startAuth(authURL: URL, callbackScheme: String, completion: @escaping (Result<URL, Error>) -> Void) {
        let session = ASWebAuthenticationSession(url: authURL, callbackURLScheme: callbackScheme) { callbackURL, error in
            if let url = callbackURL {
                completion(.success(url))
            } else {
                completion(.failure(error ?? URLError(.cancelled)))
            }
        }
        session.prefersEphemeralWebBrowserSession = true
        session.presentationContextProvider = UIApplication.shared.delegate as? ASWebAuthenticationPresentationContextProviding
        self.session = session
        _ = session.start()
    }
}
```

- If you are cutting over live traffic gradually (canary rollout), keep two active redirects.
- If you cannot force an instant flip across all clients and caches, keep two active redirects.

Retire the old redirect only after logs confirm the new domain has stable throughput for at least one full app release cycle.

## 4. Validate Tokens And Protect Email Relay Continuity
### Anchor: `ASAuthorizationAppleIDCredential.identityToken`, JWKS, And Private Relay
Identity should not depend on email. Private relay addresses can change, and new relay addresses for Sign in with Apple and Hide My Email will be issued on `private.icloud.com` while legacy addresses on `privaterelay.appleid.com` and `icloud.com` continue to forward. Key your users by an internal `accountId` mapped to Apple `sub` values, not by `email`.

- Anti-pattern: treating `email` from `ASAuthorizationAppleIDCredential` as the account key.
- Preferred: verifying the `identityToken` on the backend, extracting `sub`, and mapping it to your internal `accountId`. Accept tokens for both your App ID and Service ID audiences during migration.

Client-side, log the presence (not contents) of the token to correlate issues without risking PII:

```swift
import AuthenticationServices
import os

actor AppleTokenLogger {
    private let log = Logger(subsystem: "com.example.auth", category: "siwa")

    func logCredential(_ cred: ASAuthorizationAppleIDCredential) {
        let user = cred.user
        let hasToken = cred.identityToken != nil
        log.info("SIWA credential received user=\(user, privacy: .private(mask: .hash)) token_present=\(hasToken, privacy: .public)")
    }
}```

For outbound email, update allowlists, filtering, and routing rules to include `private.icloud.com` in addition to `privaterelay.appleid.com` and `icloud.com`. Monitor undeliverables by domain, and pay attention to magic-link and receipt templates during the cutover window that rely on Universal Links.

## Tradeoffs And Pitfalls
- Dual domains add complexity across AASA, entitlements, redirects, and backend mapping, but they reduce outage risk. In production, the safety margin is often worth the overhead.
- Keeping one Service ID preserves user linkage. A new Service ID simplifies isolation but forces account relinking. If you must create a new one, build and ship a linking flow first.
- Removing the old domain quickly shortens the migration but increases risk from caches, CDN propagation, and staggered client adoption. Leave the old domain active through at least one full release cycle.
- Mixing native and web sign-in without explicit mapping tends to create duplicates. Merge work is slower, noisier, and more error-prone than doing the mapping upfront.
- AASA and entitlement mismatches can fail intermittently on poor networks, especially when TLS handshakes or redirects are unreliable.

## Validation & Observability
Silent auth failures look like user choices unless you instrument the boundaries. Add structure and timing to see what actually broke.

- Use `OSSignposter` to mark the login span from request start to token receipt. Add the domain, redirect host, and an error code to your fields, plus a correlation ID for server logs.
- Prefer `Logger` with privacy annotations over print statements; avoid logging raw tokens or emails.
- Gate the redirect switch behind a remote flag. A canary (a small percentage of traffic rolled to the new path) reveals mismatches without impacting the whole cohort.
- Write `XCTest` UI flows that drive `ASWebAuthenticationSession` against both registered redirects. Assert exact scheme, host, and path in the callback, and fail if any component differs.

```swift
import os

struct AuthSignposts {
    static let signposter = OSSignposter(subsystem: "com.example.auth", category: "siwa")
}

func signInTransaction<T>(_ name: StaticString, _ work: () async throws -> T) async rethrows -> T {
    let state = AuthSignposts.signposter.beginInterval(name)
    defer { AuthSignposts.signposter.endInterval(name, state) }
    return try await work()
}
```

Post-release, watch cancel rates, redirect error distributions, and email bounce metrics segmented by domain. Stable metrics for the new domain over a full traffic slice is your signal to retire the old paths safely.

## Practical Checklist
- [ ] Add the new domain to the existing Service ID and register both exact redirect URLs. Keep the old redirect active.
- [ ] Publish an AASA on the new domain with `application/json`, no redirects, and correct `applinks:`/`webcredentials:` content.
- [ ] Ship an app update with `com.apple.developer.associated-domains` listing both old and new domains; wait for adoption before shifting traffic.
- [ ] Update backend token verification to accept App ID and Service ID audiences during migration; map Apple `sub` to your internal `accountId`.
- [ ] Update outbound email policies and allowlists to include `private.icloud.com`, `privaterelay.appleid.com`, and `icloud.com`; monitor bounce and suppression lists.
- [ ] Instrument login spans with `OSSignposter` and structured `Logger` fields; canary the redirect switch behind a feature flag.
- [ ] Build `XCTest` UI flows that assert exact redirect URL matches and verify deep links on real devices with the new AASA.

## Closing Takeaway
Changing Sign in with Apple domains is an identity migration with production blast radius, not a DNS tweak. Keep your Service ID, register both redirects, and run dual domains until metrics show the new path is stable. Map Apple `user` identifiers to your own `accountId` and avoid equating identity with an email that may be a private relay. Stage entitlement and AASA updates before any traffic moves. With a canary, instrumentation, and a rollback path, you can ship the change without locking anyone out.

## Swift/SwiftUI Code Example

```swift
import Foundation
import AuthenticationServices
import Observation

@MainActor
@Observable
final class AppleSignInCoordinator: NSObject, ASWebAuthenticationPresentationContextProviding {
    private let serviceID = "com.example.web" // Service ID (web)
    private let primaryDomain = URL(string: "https://auth.new.example.com")!
    private let legacyDomains: Set<String> = ["auth.old.example.com", "auth.new.example.com"]
    private let callbackScheme = "myapp" // keep custom-scheme working during UL cutover
    private var state = UUID().uuidString
    private var webSession: ASWebAuthenticationSession?

    func beginWebSignIn() {
        state = UUID().uuidString
        var c = URLComponents(url: primaryDomain.appending(path: "/oauth/apple/start/"), resolvingAgainstBaseURL: false)!
        c.queryItems = [
            .init(name: "client_id", value: serviceID),
            .init(name: "state", value: state),
            .init(name: "redirect_uri", value: "https://auth.new.example.com/auth/callback/") // server will also allow old host
        ]
        let url = c.url!
        let s = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { [weak self] url, error in
            guard let self, let url else { return }
            self.consumeRedirect(url)
        }
        s.prefersEphemeralWebBrowserSession = true
        s.presentationContextProvider = self
        webSession = s
        s.start()
    }

    func consumeRedirect(_ url: URL) {
        guard validateRedirect(url) else { return }
        let q = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let code = q.first { $0.name == "code" }?.value
        let rcvdState = q.first { $0.name == "state" }?.value
        guard rcvdState == state, let code else { return }
        // Exchange code with backend (not shown). Keep both domains serving AASA until metrics confirm zero hits on legacy.
    }

    private func validateRedirect(_ url: URL) -> Bool {
        if url.scheme == callbackScheme { return true } // custom-scheme path during migration
        guard url.scheme == "https",
              let host = url.host,
              legacyDomains.contains(host),
              normalize(url.path) == "/auth/callback/" else { return false }
        return true
    }

    private func normalize(_ path: String) -> String { path.hasSuffix("/") ? path : path + "/" }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor { ASPresentationAnchor() }
}
```

## References

- [New domain for Sign in with Apple and iCloud+ Hide My Email](https://developer.apple.com/news/?id=sus6t6ab)
- [Swift at Apple: Migrating the TrueType Hinting Interpreter](https://swift.org/blog/migrating-truetype-hinting-to-swift/)
- [iOS 26.6 beta 2 (23G5043d)](https://developer.apple.com/news/releases/?id=06152026a)
- [iPadOS 26.6 beta 2 (23G5043d)](https://developer.apple.com/news/releases/?id=06152026b)
- [macOS 26.6 beta 2 (25G5043d)](https://developer.apple.com/news/releases/?id=06152026c)
- [WWDC26 survey](https://developer.apple.com/news/?id=15wishue)
- [Find out what's new for Apple developers](https://developer.apple.com/news/?id=8rgqj83s)
- [The Swift Programming Language](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift/)
