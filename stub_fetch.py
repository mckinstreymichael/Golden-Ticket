#!/usr/bin/env python3
"""
stub_fetch.py  (v2)  —  giveaway listing collector for the Stub dashboard

Read-only aggregator. It collects PUBLIC giveaway listings from feeds you
choose, normalizes them, and writes a JSON file you load with the dashboard's
Import button. It never enters giveaways, submits forms, makes accounts, or
solves challenges — discovery only; you enter each one yourself.

By design it stays polite and identifiable: one descriptive User-Agent, a
delay between requests, a single pass, and feed/JSON endpoints over HTML
scraping. There is intentionally no proxy rotation, UA spoofing, or anti-bot
evasion — this tool is meant to be welcome traffic, not sneaky traffic.

QUICK START
  pip install feedparser requests
  python3 stub_fetch.py --init           # writes sources.json you can edit
  python3 stub_fetch.py                   # fetch -> stub-data.json
  # ...set some statuses in the dashboard, then Export, then later:
  python3 stub_fetch.py --merge stub-data.json --new-only

KEY FLAGS
  --config PATH     source list (default: sources.json)
  --out PATH        output file (default: stub-data.json)
  --merge PATH      merge into an existing export, preserving your statuses
  --new-only        only output giveaways not seen in previous runs
  --min-value N     drop giveaways whose detected prize value is below N
  --include a,b     keep only items whose text matches one of these words
  --exclude x,y     drop items whose text matches any of these words
"""

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import feedparser

from urllib.robotparser import RobotFileParser
from urllib.error import URLError, HTTPError

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

CACHE_FILE = ".stub_cache.json"
USER_AGENT = "StubGiveawayCollector/2.0 (personal giveaway tracker; read-only)"
REQUEST_DELAY_SECONDS = 2.0
MAX_ITEMS_PER_SOURCE = 50
GLOBAL_MAX = 400

DEFAULT_SOURCES = [
    {"type": "reddit", "sub": "giveaways", "name": "r/giveaways"},
    {"type": "reddit", "sub": "sweepstakes", "name": "r/sweepstakes"},
    {"type": "rss", "url": "https://example.com/giveaways/feed", "name": "Example Contests", "enabled": False},
    {"type": "csv", "path": "my_giveaways.csv", "name": "My sheet", "enabled": False},
    {"type": "html", "url": "https://example.com/giveaways", "name": "Example HTML page",
     "item_selector": ".giveaway-card", "title_selector": "h2",
     "link_selector": "a", "summary_selector": ".description", "enabled": False},
]

# ----------------------------- text helpers --------------------------------

def clean(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_MONTHS = ("january february march april may june july august september "
           "october november december").split()
_MON_RE = "(?:" + "|".join(m[:3] for m in _MONTHS) + ")[a-z]*"

_DATE_RULES = [
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "iso"),
    (re.compile(r"\bends?\s+(?:on\s+)?(\d{1,2}/\d{1,2}/\d{2,4})", re.I), "mdy"),
    (re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"), "mdy"),
    (re.compile(r"\b(" + _MON_RE + r"\.?\s+\d{1,2},?\s+\d{4})", re.I), "mon_d_y"),
    (re.compile(r"\b(\d{1,2}\s+" + _MON_RE + r"\.?\s+\d{4})", re.I), "d_mon_y"),
]
_RELATIVE_RE = re.compile(r"\b(?:ends?|closes?|expires?)\s+in\s+(\d{1,3})\s+day", re.I)


def guess_deadline(text):
    text = text or ""
    m = _RELATIVE_RE.search(text)
    if m:
        return (dt.date.today() + dt.timedelta(days=int(m.group(1)))).isoformat()
    for rx, kind in _DATE_RULES:
        m = rx.search(text)
        if not m:
            continue
        raw = m.group(1)
        try:
            if kind == "iso":
                return dt.datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
            if kind == "mdy":
                fmt = "%m/%d/%Y" if len(raw.split("/")[-1]) == 4 else "%m/%d/%y"
                return dt.datetime.strptime(raw, fmt).date().isoformat()
            if kind in ("mon_d_y", "d_mon_y"):
                norm = raw.replace(".", "").replace(",", "")
                for f in ("%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
                    try:
                        return dt.datetime.strptime(norm, f).date().isoformat()
                    except ValueError:
                        continue
        except ValueError:
            continue
    return ""


_PRIZE_RE = re.compile(r"(?:win(?:ning)?|prize|giveaway of|chance to win)\s*:?\s*(.{3,80})", re.I)
_VALUE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


def guess_prize(title, summary):
    for blob in (title, summary):
        m = _PRIZE_RE.search(blob or "")
        if m:
            return clean(m.group(1))
    return ""


def guess_value(text):
    vals = [float(v.replace(",", "")) for v in _VALUE_RE.findall(text or "")]
    return max(vals) if vals else 0.0


# ----------------------------- normalization -------------------------------

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref|ref_src|igshid)", re.I)


def normalize_url(url):
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        q = [(k, v) for k, v in parse_qsl(p.query) if not _TRACKING.match(k)]
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))
    except ValueError:
        return url.strip()


def title_key(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())[:60]


def make_id(url, title):
    basis = normalize_url(url) or title_key(title)
    return "f" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:11]


def build_item(title, url, summary, source_name):
    title = clean(title) or "(untitled giveaway)"
    summary = clean(summary)
    text = title + " " + summary
    return {
        "id": make_id(url, title),
        "title": title[:140],
        "prize": guess_prize(title, summary),
        "prize_value": guess_value(text),
        "url": normalize_url(url),
        "deadline": guess_deadline(text),
        "note": ("via " + source_name + (" — " + summary[:120] if summary else "")).strip(),
        "status": "todo",
    }


# ----------------------------- source fetchers -----------------------------

def fetch_rss(src):
    feed = feedparser.parse(src["url"], agent=USER_AGENT)
    return [build_item(e.get("title", ""), e.get("link", ""),
                       e.get("summary", e.get("description", "")),
                       src.get("name", src["url"]))
            for e in feed.entries[:MAX_ITEMS_PER_SOURCE]]


def fetch_reddit(src):
    if requests is None:
        print("  ! 'requests' not installed; skipping reddit source")
        return []
    url = "https://www.reddit.com/r/%s/new.json?limit=%d" % (src["sub"], MAX_ITEMS_PER_SOURCE)
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    out = []
    for child in r.json().get("data", {}).get("children", []):
        d = child.get("data", {})
        link = d.get("url_overridden_by_dest") or ("https://www.reddit.com" + d.get("permalink", ""))
        out.append(build_item(d.get("title", ""), link, d.get("selftext", ""), src.get("name", "reddit")))
    return out


def fetch_csv(src):
    """Read a local/exported sheet. Recognized columns (case-insensitive):
    title|name, prize, url|link, deadline|closes, note."""
    path = src["path"]
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            low = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
            title = low.get("title") or low.get("name") or ""
            url = low.get("url") or low.get("link") or ""
            note = low.get("note") or ""
            it = build_item(title, url, note, src.get("name", "csv"))
            if low.get("prize"):
                it["prize"] = clean(low["prize"])
                it["prize_value"] = guess_value(low["prize"]) or it["prize_value"]
            if low.get("deadline") or low.get("closes"):
                it["deadline"] = guess_deadline(low.get("deadline") or low.get("closes")) or it["deadline"]
            out.append(it)
    return out


FETCHERS = {"rss": fetch_rss, "reddit": fetch_reddit, "csv": fetch_csv}


# ----------------------------- robots.txt gate -----------------------------

# Per-host cache so we read each site's robots.txt at most once per run.
_ROBOTS_CACHE = {}


def robots_check(url, ua=USER_AGENT):
    """Return (allowed, crawl_delay_seconds). Honors the site's robots.txt.

    - No robots.txt (404): allowed, per the standard.
    - robots.txt forbids our path or the whole site: not allowed.
    - robots.txt unreachable (network error): not allowed, fail safe.
    """
    parts = urlparse(url)
    host = parts.scheme + "://" + parts.netloc
    if host not in _ROBOTS_CACHE:
        rp = RobotFileParser()
        rp.set_url(host + "/robots.txt")
        try:
            rp.read()
            _ROBOTS_CACHE[host] = rp
        except HTTPError as e:
            # 404 -> RobotFileParser already treats as allow-all; other codes are handled by it too.
            if e.code >= 500:
                _ROBOTS_CACHE[host] = None  # server trouble; don't assume permission
            else:
                _ROBOTS_CACHE[host] = rp
        except (URLError, Exception):       # noqa: BLE001 - any failure -> fail safe
            _ROBOTS_CACHE[host] = None
    rp = _ROBOTS_CACHE[host]
    if rp is None:
        return False, None
    try:
        return rp.can_fetch(ua, url), rp.crawl_delay(ua)
    except Exception:                        # noqa: BLE001
        return False, None


def fetch_html(src):
    """Scrape a single permitted listing page using CSS selectors you provide.

    Config keys:
      url, name, item_selector (required), and optional
      title_selector, link_selector, summary_selector.
    Only runs if robots.txt permits it; respects any crawl-delay.
    """
    if requests is None or BeautifulSoup is None:
        print("  ! needs 'requests' and 'beautifulsoup4'; skipping html source")
        return []
    url = src["url"]
    allowed, delay = robots_check(url)
    if not allowed:
        print("  ! robots.txt disallows fetching this page - skipping (this is by design)")
        return []
    if delay:
        print("  . robots.txt requests a %.0fs crawl-delay; honoring it" % delay)
        time.sleep(min(delay, 30))
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    item_sel = src.get("item_selector")
    if not item_sel:
        print("  ! html source needs an 'item_selector'; skipping")
        return []
    out = []
    base = urlparse(url)
    for node in soup.select(item_sel)[:MAX_ITEMS_PER_SOURCE]:
        def pick(sel):
            if not sel:
                return ""
            el = node.select_one(sel)
            return el.get_text(" ", strip=True) if el else ""
        title = pick(src.get("title_selector")) or node.get_text(" ", strip=True)
        link = ""
        link_sel = src.get("link_selector", "a")
        a = node.select_one(link_sel) if link_sel else None
        if a and a.get("href"):
            href = a["href"]
            if href.startswith("//"):
                href = base.scheme + ":" + href
            elif href.startswith("/"):
                href = base.scheme + "://" + base.netloc + href
            link = href
        summary = pick(src.get("summary_selector"))
        out.append(build_item(title, link, summary, src.get("name", base.netloc)))
    return out


FETCHERS["html"] = fetch_html


# ----------------------------- filtering -----------------------------------

def passes_filters(item, include, exclude, min_value):
    hay = (item["title"] + " " + item["note"] + " " + item["prize"]).lower()
    if include and not any(w in hay for w in include):
        return False
    if exclude and any(w in hay for w in exclude):
        return False
    if min_value and item.get("prize_value", 0) < min_value:
        return False
    return True


# ----------------------------- cache / merge -------------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"seen_ids": []}


def save_cache(cache):
    try:
        json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), indent=2)
    except OSError:
        pass


def merge_preserving_status(existing_path, fresh_items):
    """Keep everything in the existing export (manual entries + statuses),
    add only genuinely new giveaways. Refresh deadline if it was empty before."""
    try:
        data = json.load(open(existing_path, encoding="utf-8"))
    except (ValueError, OSError):
        print("  ! could not read %s; treating as empty" % existing_path)
        data = {"profile": {}, "giveaways": []}
    existing = data.get("giveaways", [])
    by_id = {g.get("id"): g for g in existing}
    by_title = {title_key(g.get("title", "")): g for g in existing}
    added = 0
    for it in fresh_items:
        match = by_id.get(it["id"]) or by_title.get(title_key(it["title"]))
        if match:
            # same giveaway already tracked - keep your status, only backfill a missing deadline
            if not match.get("deadline") and it.get("deadline"):
                match["deadline"] = it["deadline"]
        else:
            existing.append(it)
            by_id[it["id"]] = it
            by_title[title_key(it["title"])] = it
            added += 1
    data["giveaways"] = existing
    data.setdefault("profile", {})
    return data, added


# ----------------------------- main pipeline -------------------------------

def collect(sources, include, exclude, min_value, new_only, cache):
    seen_run, items = set(), []
    seen_prev = set(cache.get("seen_ids", []))
    for src in sources:
        if src.get("enabled") is False:
            continue
        label = src.get("name", src.get("url", src.get("sub", src.get("path", "?"))))
        print("Fetching: %s" % label)
        fetcher = FETCHERS.get(src.get("type"))
        if not fetcher:
            print("  ! unknown source type %r" % src.get("type"))
            continue
        try:
            got = fetcher(src)
        except Exception as ex:  # noqa: BLE001 - report and keep going
            print("  ! failed (%s)" % ex)
            got = []
        added = skipped = 0
        existing_titlekeys = {title_key(x["title"]) for x in items}
        for it in got:
            if it["id"] in seen_run or title_key(it["title"]) in existing_titlekeys:
                continue
            if not passes_filters(it, include, exclude, min_value):
                skipped += 1
                continue
            if new_only and it["id"] in seen_prev:
                skipped += 1
                continue
            seen_run.add(it["id"])
            existing_titlekeys.add(title_key(it["title"]))
            items.append(it)
            added += 1
            if len(items) >= GLOBAL_MAX:
                break
        print("  + %d new, %d skipped" % (added, skipped))
        if src.get("type") != "csv":
            time.sleep(REQUEST_DELAY_SECONDS)
        if len(items) >= GLOBAL_MAX:
            break

    cache["seen_ids"] = list(seen_prev | seen_run)[-5000:]
    cache["last_run"] = dt.datetime.now().isoformat(timespec="seconds")
    return items


def write_init(path):
    if os.path.exists(path):
        print("%s already exists - leaving it alone." % path)
        return
    json.dump({"sources": DEFAULT_SOURCES}, open(path, "w", encoding="utf-8"), indent=2)
    print("Wrote starter %s - edit it to list the feeds you want." % path)


def load_sources(path):
    if not os.path.exists(path):
        print("No %s found; using built-in defaults. Run --init to create one." % path)
        return DEFAULT_SOURCES
    data = json.load(open(path, encoding="utf-8"))
    return data.get("sources", data if isinstance(data, list) else [])


def run_once(args):
    include = [w.strip().lower() for w in args.include.split(",") if w.strip()]
    exclude = [w.strip().lower() for w in args.exclude.split(",") if w.strip()]

    cache = load_cache()
    sources = load_sources(args.config)
    items = collect(sources, include, exclude, args.min_value, args.new_only, cache)

    items.sort(key=lambda g: (g["deadline"] == "", g["deadline"]))

    if args.merge:
        payload, added = merge_preserving_status(args.merge, items)
        print("\nMerged: %d new added; statuses preserved." % added)
    else:
        payload = {"profile": {}, "giveaways": items}

    json.dump(payload, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    save_cache(cache)
    print("Wrote %d giveaways to %s" % (len(payload["giveaways"]), args.out))
    print("Open the Stub dashboard and use Import to load them.")


def main():
    ap = argparse.ArgumentParser(description="Collect public giveaway listings for the Stub dashboard.")
    ap.add_argument("--config", default="sources.json")
    ap.add_argument("--out", default="stub-data.json")
    ap.add_argument("--merge")
    ap.add_argument("--new-only", action="store_true")
    ap.add_argument("--min-value", type=float, default=0.0)
    ap.add_argument("--include", default="")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--every", type=float, default=0.0,
                    help="run repeatedly every N hours (e.g. 24 for daily). Ctrl-C to stop.")
    args = ap.parse_args()

    if args.init:
        write_init(args.config)
        return

    if args.every and args.every > 0:
        # When looping, default to merge+new-only so the output file accumulates
        # and your statuses survive each run.
        if not args.merge:
            args.merge = args.out
        args.new_only = True
        print("Scheduler on: every %.1f h, merging into %s. Ctrl-C to stop.\n" % (args.every, args.out))
        while True:
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            print("===== run @ %s =====" % stamp)
            try:
                run_once(args)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
            except Exception as ex:                  # noqa: BLE001 - keep the scheduler alive
                print("  ! run failed (%s); will retry next cycle" % ex)
            try:
                time.sleep(args.every * 3600)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
    else:
        run_once(args)


if __name__ == "__main__":
    main()
