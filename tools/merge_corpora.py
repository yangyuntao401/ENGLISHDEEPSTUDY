#!/usr/bin/env python3
"""Merge collector backup JSON files into one import and first-run seed bundle."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/deepstudy-import.json"))
    parser.add_argument("--js-output", type=Path, default=Path("app/seed-data.js"))
    args = parser.parse_args()
    result = {
        "version": 1, "articles": [], "words": {}, "grammar": {}, "reads": {},
        "queue": [], "phase": "", "idx": 0, "wrong": [], "today": date.today().isoformat(),
        "collection": {"adapter": "merged", "sources": []},
    }
    seen_articles = set()
    for path in args.inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        for article in data.get("articles", []):
            if article.get("id") in seen_articles:
                continue
            seen_articles.add(article.get("id"))
            result["articles"].append(article)
        for token, incoming in data.get("words", {}).items():
            current = result["words"].setdefault(token, incoming)
            if current is not incoming:
                for article_id in incoming.get("sourceIds", []):
                    if article_id not in current.setdefault("sourceIds", []):
                        current["sourceIds"].append(article_id)
                current["mastered"] = current.get("mastered", False) or incoming.get("mastered", False)
                if not current.get("meaning") and incoming.get("meaning"):
                    current["meaning"] = incoming["meaning"]
        for group, value in data.get("grammar", {}).items():
            result["grammar"][group] = result["grammar"].get(group, False) or value
        result["reads"].update(data.get("reads", {}))
        collection = data.get("collection", {})
        sources = collection.get("sources")
        result["collection"]["sources"].extend(sources if isinstance(sources, list) else [collection])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.js_output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.write_text(serialized, encoding="utf-8")
    args.js_output.write_text("window.DEEPSTUDY_SEED = " + json.dumps(result, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Wrote {len(result['articles'])} materials, {len(result['words'])} unique word forms")
    print(f"JSON: {args.output}; app seed: {args.js_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
