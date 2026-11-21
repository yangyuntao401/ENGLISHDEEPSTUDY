#!/usr/bin/env python3
"""Collect short, attributed articles from a specified MediaWiki API.

The default profile targets Simple English Wikipedia. It uses the Action API,
serial requests, maxlag, a descriptive User-Agent, and writes a DeepStudy JSON
backup that can be imported from the app's Data & Sources page.

This is a source adapter, not blanket permission to reuse every page. Review
each page's notices and the target jurisdiction before importing the output.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_API = "https://simple.wikipedia.org/w/api.php"
DEFAULT_LICENSE = "CC BY-SA 4.0 (verify page-specific notices)"
WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def request_json(api: str, params: dict[str, str], user_agent: str) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json", "maxlag": "5"})
    req = urllib.request.Request(
        f"{api}?{query}",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry = int(exc.headers.get("Retry-After", "10"))
            time.sleep(max(10, retry))
            return request_json(api, params, user_agent)
        raise


def clean_extract(raw: str) -> str:
    # Action API plaintext extracts may still contain section labels and
    # whitespace artifacts; retain paragraph breaks and normalize spacing.
    lines = []
    for line in html.unescape(raw).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line.startswith("=="):
            continue
        if line.lower().startswith(("see the main article:", "main articles:")):
            continue
        if line.lower() in {"see also", "references", "external links", "further reading"}:
            break
        lines.append(line)
    return "\n".join(lines)


def split_sentences(text: str) -> list[str]:
    result = []
    for paragraph in text.splitlines():
        for sentence in SENTENCE_RE.split(paragraph):
            sentence = sentence.strip()
            if len(WORD_RE.findall(sentence)) >= 3 and sentence[-1:] in ".!?":
                result.append(sentence)
    return result


def cap_sentences(sentences: list[str], max_words: int) -> list[str]:
    selected = []
    count = 0
    for sentence in sentences:
        size = len(WORD_RE.findall(sentence))
        if selected and count + size > max_words:
            break
        selected.append(sentence)
        count += size
    return selected


def collect(args: argparse.Namespace) -> dict:
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    articles = []
    words: dict[str, dict] = {}
    seen_ids = set()
    for query_index, query in enumerate(args.query):
        if query_index:
            time.sleep(1)
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "0",
            "gsrlimit": str(args.count),
            "prop": "extracts|info|revisions|pageprops",
            "explaintext": "1",
            "exsectionformat": "plain",
            "inprop": "url",
            "rvprop": "ids|timestamp",
        }
        data = request_json(args.api, params, args.user_agent)
        if "error" in data:
            raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))
        pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p["pageid"])
        for page in pages:
            props = page.get("pageprops", {})
            if "disambiguation" in props or "extract" not in page:
                continue
            body = clean_extract(page["extract"])
            sentences = cap_sentences(split_sentences(body), args.max_words)
            if len(WORD_RE.findall(body)) < args.min_words or not sentences:
                continue
            rev = (page.get("revisions") or [{}])[0]
            page_url = page.get("fullurl", f"https://simple.wikipedia.org/wiki/{urllib.parse.quote(page['title'].replace(' ', '_'))}")
            revision_id = rev.get("revid")
            stable_url = f"https://simple.wikipedia.org/w/index.php?oldid={revision_id}" if revision_id else page_url
            article_id = f"mw_{page['pageid']}_{revision_id or 'latest'}"
            if article_id in seen_ids:
                continue
            seen_ids.add(article_id)
            articles.append({
                "id": article_id,
                "title": page["title"],
                "source": "Simple English Wikipedia",
                "author": "Wikipedia contributors (see page history)",
                "url": stable_url,
                "license": args.license,
                "kind": args.kind,
                "excerpt": len(WORD_RE.findall(body)) > sum(len(WORD_RE.findall(s)) for s in sentences),
                "excerptNote": "Opening excerpt; see linked source for full text.",
                "added": collected_at,
                "collectedAt": collected_at,
                "revisionId": revision_id,
                "revisionTimestamp": rev.get("timestamp"),
                "sentences": sentences,
            })
            for sentence in sentences:
                for match in WORD_RE.finditer(sentence):
                    token = match.group(0).lower().replace("’", "'")
                    entry = words.setdefault(token, {
                        "token": token, "meaning": "", "mastered": False,
                        "sourceIds": [], "needsReview": True,
                    })
                    if article_id not in entry["sourceIds"]:
                        entry["sourceIds"].append(article_id)

    return {
        "version": 1,
        "articles": articles,
        "words": words,
        "grammar": {},
        "reads": {},
        "queue": [],
        "phase": "",
        "idx": 0,
        "wrong": [],
        "today": datetime.now().date().isoformat(),
        "collection": {
            "adapter": "mediawiki-action-api",
            "api": args.api,
            "queries": args.query,
            "collectedAt": collected_at,
            "licenseNotice": "Check each page and applicable jurisdiction before redistribution.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", required=True, help="Search query; repeat to collect several topics")
    parser.add_argument("--output", type=Path, default=Path("deepstudy-import.json"))
    parser.add_argument("--js-output", type=Path, help="Also write a browser seed bundle that loads on first app launch")
    parser.add_argument("--count", type=int, default=10, help="Maximum search results (1–50)")
    parser.add_argument("--min-words", type=int, default=90, help="Discard very short search pages")
    parser.add_argument("--max-words", type=int, default=260, help="Keep an opening excerpt of at most this many words")
    parser.add_argument("--kind", default="article", choices=["article", "dialogue", "literature", "technology", "blog"])
    parser.add_argument("--api", default=DEFAULT_API, help="Only use an API whose reuse terms you have checked")
    parser.add_argument("--license", default=DEFAULT_LICENSE, help="Recorded license string; does not replace page-level review")
    parser.add_argument("--user-agent", required=True, help="Identify the client and provide a contact URL or email")
    args = parser.parse_args()
    if not 1 <= args.count <= 50:
        parser.error("--count must be between 1 and 50")
    if "(" not in args.user_agent or ")" not in args.user_agent:
        parser.error("--user-agent must identify the client and include contact details in parentheses")
    try:
        result = collect(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.js_output:
            args.js_output.parent.mkdir(parents=True, exist_ok=True)
            args.js_output.write_text("window.DEEPSTUDY_SEED = " + json.dumps(result, ensure_ascii=False) + ";\n", encoding="utf-8")
    except Exception as exc:  # keep a readable CLI error without a traceback
        print(f"Collection failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {len(result['articles'])} articles and {len(result['words'])} unique word forms to {args.output}")
    print("Review page notices, source attribution, and jurisdiction before importing or redistributing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
