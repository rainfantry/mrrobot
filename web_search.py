"""
SERVITOR — websearch tool
=========================
DuckDuckGo HTML search wrapper. Returns clean (title, url, snippet) dicts.
Used by mrrobot.py to fulfil [WEBSEARCH]: sentinels emitted by SERVITOR.

Standalone test:
    python web_search.py "current openssh version"

Module use:
    from web_search import search
    results = search("query here", max_results=5)
    # -> [{"title": ..., "url": ..., "snippet": ...}, ...]
    # -> [] on failure (reason is logged via logging module)
"""

import sys
import json
import logging
from typing import List, Dict

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
except ImportError:
    DDGS = None
    DDGSException = Exception

log = logging.getLogger("servitor.search")

# Quiet the ddgs library's noisy INFO chatter (logs every HTTP response).
# Caller's bot.log stays clean — only warnings/errors from search bubble up.
logging.getLogger("ddgs").setLevel(logging.WARNING)
logging.getLogger("primp").setLevel(logging.WARNING)

DEFAULT_MAX = 5
SEARCH_TIMEOUT = 15  # seconds (passed to underlying primp client)
OVERSAMPLE = 4       # request N extra so ad-filtering still leaves max_results

# URL/title patterns identifying sponsored/ad results to drop.
AD_URL_FRAGMENTS = (
    "bing.com/aclick",
    "googleadservices.com",
    "doubleclick.net",
    "googlesyndication.com",
    "/aclk?",
    "syndicatedsearch.goog",
)
AD_TITLE_PREFIXES = ("Ad", "Sponsored")


def _is_ad(title: str, url: str) -> bool:
    if any(frag in url for frag in AD_URL_FRAGMENTS):
        return True
    t = title.lstrip()
    for prefix in AD_TITLE_PREFIXES:
        if t.startswith(prefix) and (len(t) <= len(prefix) or not t[len(prefix)].isalpha()):
            return True
    return False


def search(query: str, max_results: int = DEFAULT_MAX) -> List[Dict[str, str]]:
    """Run a DuckDuckGo text search. Returns up to max_results normalized dicts.

    On any failure (no module, no network, no results, rate limit) returns []
    and logs the reason at WARNING level — caller decides how to surface it.
    """
    query = (query or "").strip()
    if not query:
        log.warning("[SEARCH] empty query — skipping")
        return []

    if DDGS is None:
        log.error("[SEARCH] ddgs package not installed (pip install ddgs)")
        return []

    # Oversample so ad-filtering doesn't undershoot caller's requested count.
    fetch_n = max_results + OVERSAMPLE
    try:
        with DDGS(timeout=SEARCH_TIMEOUT) as ddgs:
            raw = list(ddgs.text(query, max_results=fetch_n))
    except DDGSException as exc:
        log.warning("[SEARCH] DDG error for %r: %s", query, exc)
        return []
    except Exception as exc:
        log.warning("[SEARCH] unexpected error for %r: %s", query, exc)
        return []

    if not raw:
        log.info("[SEARCH] zero results for %r", query)
        return []

    out = []
    dropped_ads = 0
    for r in raw:
        title = (r.get("title") or "").strip()
        url   = (r.get("href")  or "").strip()
        if _is_ad(title, url):
            dropped_ads += 1
            continue
        out.append({
            "title": title,
            "url":   url,
            "snippet": (r.get("body") or "").strip(),
        })
        if len(out) >= max_results:
            break

    log.info("[SEARCH] %d results for %r (ads dropped: %d, raw fetched: %d)",
             len(out), query, dropped_ads, len(raw))
    return out


def format_for_prompt(query: str, results: List[Dict[str, str]]) -> str:
    """Render results as a prompt-injectable block.

    Format:
        <<<SEARCH_RESULTS query="...">>>
        1. <title>
           <snippet>
           URL: <url>
        2. ...
        <<<END>>>

    If results is empty, returns a clear "no results" block so the model
    knows the search ran but found nothing — distinct from "search disabled".
    """
    head = f'<<<SEARCH_RESULTS query="{query}">>>'
    tail = "<<<END>>>"
    if not results:
        return f"{head}\n(no results — search returned empty)\n{tail}"
    body_lines = []
    for i, r in enumerate(results, 1):
        body_lines.append(f"{i}. {r['title']}")
        if r["snippet"]:
            body_lines.append(f"   {r['snippet']}")
        body_lines.append(f"   URL: {r['url']}")
    return "\n".join([head, *body_lines, tail])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if len(sys.argv) < 2:
        print("usage: python web_search.py \"<query>\" [max_results]")
        raise SystemExit(2)
    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX
    results = search(q, max_results=n)
    print(f"\n=== RAW RESULTS ({len(results)}) ===\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['title']}")
        print(f"    {r['url']}")
        print(f"    {r['snippet'][:200]}{'...' if len(r['snippet'])>200 else ''}")
        print()
    print("=== PROMPT FORMAT ===")
    sys.stdout.buffer.write(format_for_prompt(q, results).encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
