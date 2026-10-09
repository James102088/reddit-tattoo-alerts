#!/usr/bin/env python3
"""Watch subreddits for people asking for tattoo artist recommendations and
push matches to your phone via ntfy.sh.

Stdlib only. Config lives in config.json; already-seen post IDs in seen.json.

Env vars:
  NTFY_TOPIC            required to send alerts (otherwise matches are just printed)
  NTFY_SERVER           optional, default https://ntfy.sh
  REDDIT_CLIENT_ID      optional; if set (with secret) uses the Reddit API
  REDDIT_CLIENT_SECRET  instead of public RSS feeds
  DRY_RUN=1             print matches, don't notify, don't save state
"""
import base64
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
SEEN_PATH = ROOT / "seen.json"
USER_AGENT = "script:tattoo-rec-alerts:v1.0 (personal monitor)"
ATOM = "{http://www.w3.org/2005/Atom}"
MAX_SEEN = 2000  # cap state file size


def http(url, data=None, headers=None, retries=3):
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = int(e.headers.get("Retry-After") or 20 * (attempt + 1))
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            raise


# ---------- fetching ----------

def fetch_rss(sub):
    xml = http(f"https://www.reddit.com/r/{sub}/new/.rss?limit=50")
    posts = []
    for e in ET.fromstring(xml).findall(f"{ATOM}entry"):
        body_html = e.findtext(f"{ATOM}content") or ""
        body = html.unescape(re.sub(r"<[^>]+>", " ", body_html))
        posts.append({
            "id": e.findtext(f"{ATOM}id"),
            "title": e.findtext(f"{ATOM}title") or "",
            "body": re.sub(r"\s+", " ", body).strip(),
            "url": e.find(f"{ATOM}link").get("href"),
        })
    return posts


_token = None


def fetch_api(sub):
    global _token
    if _token is None:
        cid, secret = os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        resp = http("https://www.reddit.com/api/v1/access_token",
                    data=b"grant_type=client_credentials",
                    headers={"Authorization": f"Basic {auth}"})
        _token = json.loads(resp)["access_token"]
    data = json.loads(http(f"https://oauth.reddit.com/r/{sub}/new?limit=50&raw_json=1",
                           headers={"Authorization": f"Bearer {_token}"}))
    return [{
        "id": c["data"]["name"],
        "title": c["data"]["title"],
        "body": c["data"].get("selftext", ""),
        "url": "https://www.reddit.com" + c["data"]["permalink"],
    } for c in data["data"]["children"]]


def fetch(sub):
    if os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"):
        return fetch_api(sub)
    return fetch_rss(sub)


# ---------- matching ----------

def any_match(patterns, text):
    return next((p for p in patterns if re.search(p, text, re.I)), None)


def check(post, rules):
    """Return the matched request phrase, or None."""
    text = f"{post['title']}\n{post['body']}"
    if any_match(CONFIG["exclude_patterns"], text):
        return None
    hit = any_match(CONFIG["request_patterns"], text)
    if not hit:
        return None
    if rules.get("require_tattoo_mention") and not rany_match(CONFIG["tattoo_patterns"], text):
        return None
    if rules.get("require_nyc_mention") and not any_match(CONFIG["nyc_patterns"], text):
        return None
    return hit


# ---------- notifying ----------

def notify(sub, post):
    topic = os.environ.get("NTFY_TOPIC")
    snippet = post["body"][:240] + ("…" if len(post["body"]) > 240 else "")
    if not topic or os.environ.get("DRY_RUN"):
        print(f"  [MATCH] r/{sub}: {post['title']}\n          {post['url']}")
        return
    payload = {
        "topic": topic,
        "title": f"r/{sub}: {post['title']}"[:200],
        "message": snippet or "(no text — tap to open)",
        "click": post["url"],
        "tags": ["art"],
        "priority": 4,
    }
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    http(server, data=json.dumps(payload).encode(),
         headers={"Content-Type": "application/json"})
    print(f"  notified: {post['title']}")


# ---------- main ----------

def main():
    first_run = not SEEN_PATH.exists()
    seen = [] if first_run else json.loads(SEEN_PATH.read_text())
    seen_set = set(seen)
    dry = bool(os.environ.get("DRY_RUN"))
    errors = 0

    for i, (sub, rules) in enumerate(CONFIG["subreddits"].items()):
        if i:
            time.sleep(15)  # be gentle with unauthenticated limits
        print(f"r/{sub}")
        try:
            posts = fetch(sub)
        except Exception as e:  # keep going if one sub fails
            print(f"  fetch failed: {e}")
            errors += 1
            continue
        for post in reversed(posts):  # oldest first
            if post["id"] in seen_set and not dry:
                continue
            seen.append(post["id"])
            seen_set.add(post["id"])
            if first_run and not dry:
                continue  # seed state silently so the first run doesn't spam you
            if check(post, rules):
                notify(sub, post)

    if first_run and not dry:
        print("First run: recorded existing posts, no alerts sent.")
    if not dry:
        SEEN_PATH.write_text(json.dumps(seen[-MAX_SEEN:], indent=0) + "\n")
    # Fail the job only if every subreddit failed (e.g. Reddit blocked us)
    if errors == len(CONFIG["subreddits"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
