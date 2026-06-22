#!/usr/bin/env python3
"""
Fetches public GitHub profile + pinned repositories for the portfolio pages
and writes them to _data/github_profile.json (read in templates as
site.data.github_profile, exactly like _data/article_topics.yml).

Pinned repos are only available via the GraphQL API (REST cannot return them),
so a token is used when present; the default Actions secrets.GITHUB_TOKEN can
read this public data. If GraphQL is unavailable, it falls back to the user's
top repositories by stars over REST.

The script is FAIL-SOFT: any network/API error prints a warning and exits 0
without writing a partial file, so a transient outage never blocks the deploy.
The narrative/skills/contact prose lives in the hand-curated _data/profile.yml;
this file only carries structured facts.

Run locally:  GH_TOKEN=$(gh auth token) python scripts/fetch_github_profile.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

USERNAME = "saurabhdave"
PINNED_LIMIT = 6
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "_data", "github_profile.json")

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
UA = "ios-ai-articles-portfolio-sync"


def _token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _request(url, *, data=None, token=""):
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_profile(token):
    u = _request(f"{API}/users/{USERNAME}", token=token)
    return {
        "login": u.get("login"),
        "name": u.get("name"),
        "bio": u.get("bio"),
        "company": u.get("company"),
        "location": u.get("location"),
        "blog": u.get("blog"),
        "avatar_url": u.get("avatar_url"),
        "html_url": u.get("html_url"),
        "followers": u.get("followers"),
        "public_repos": u.get("public_repos"),
        "hireable": u.get("hireable"),
    }


def _map_topics(nodes):
    out = []
    for n in nodes or []:
        topic = (n or {}).get("topic") or {}
        if topic.get("name"):
            out.append(topic["name"])
    return out


def fetch_pinned_graphql(token):
    query = """
    query($login: String!, $first: Int!) {
      user(login: $login) {
        pinnedItems(first: $first, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              description
              url
              homepageUrl
              stargazerCount
              primaryLanguage { name color }
              repositoryTopics(first: 8) { nodes { topic { name } } }
            }
          }
        }
      }
    }
    """
    payload = {"query": query, "variables": {"login": USERNAME, "first": PINNED_LIMIT}}
    res = _request(GRAPHQL, data=payload, token=token)
    if res.get("errors"):
        raise RuntimeError(f"GraphQL errors: {res['errors']}")
    nodes = (((res.get("data") or {}).get("user") or {}).get("pinnedItems") or {}).get("nodes") or []
    repos = []
    for r in nodes:
        if not r:
            continue
        lang = r.get("primaryLanguage") or {}
        repos.append({
            "name": r.get("name"),
            "description": r.get("description"),
            "url": r.get("url"),
            "homepage": r.get("homepageUrl"),
            "stars": r.get("stargazerCount", 0),
            "language": lang.get("name"),
            "language_color": lang.get("color"),
            "topics": _map_topics((r.get("repositoryTopics") or {}).get("nodes")),
        })
    return repos


def fetch_top_repos_rest(token):
    """Fallback when GraphQL/pinned is unavailable: top owned repos by stars."""
    url = f"{API}/users/{USERNAME}/repos?type=owner&sort=updated&per_page=100"
    data = _request(url, token=token)
    owned = [r for r in data if not r.get("fork") and not r.get("archived")]
    owned.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    repos = []
    for r in owned[:PINNED_LIMIT]:
        repos.append({
            "name": r.get("name"),
            "description": r.get("description"),
            "url": r.get("html_url"),
            "homepage": r.get("homepage"),
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language"),
            "language_color": None,
            "topics": r.get("topics") or [],
        })
    return repos


def main():
    token = _token()
    try:
        profile = fetch_profile(token)

        pinned = []
        if token:
            try:
                pinned = fetch_pinned_graphql(token)
            except Exception as exc:  # noqa: BLE001 - GraphQL optional, fall back
                print(f"[fetch_github_profile] pinned via GraphQL failed ({exc}); "
                      "falling back to top repos", file=sys.stderr)
        if not pinned:
            pinned = fetch_top_repos_rest(token)

        out = dict(profile)
        out["pinned"] = pinned
        out["fetched_at"] = datetime.now(timezone.utc).isoformat()
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError,
            ValueError, KeyError) as exc:
        print(f"[fetch_github_profile] WARNING: could not sync GitHub data ({exc}); "
              "leaving existing _data/github_profile.json untouched.", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[fetch_github_profile] wrote {OUTPUT_PATH} "
          f"({len(out.get('pinned', []))} repos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
