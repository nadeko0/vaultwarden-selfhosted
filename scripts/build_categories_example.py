#!/usr/bin/env python3
"""Example categorization ruleset for priority_report.py's "report" phase.

This is a STARTER template, not a universal classifier — swap in domains
that actually appear in your own `extracted.json`. The rubric:

  CRITICAL - email providers, banks, payment systems, crypto exchanges,
             cloud infra with billing. Compromise here causes direct
             financial loss or cascades into everything else via
             password-reset flows.
  HIGH     - social media under your real identity, work/school systems,
             messengers, dev hosting, domain registrars.
  MEDIUM   - ordinary services holding personal data but no money
             (streaming, forums with a real profile, gaming platforms
             like Steam/Epic).
  LOW      - throwaway signups, small forums, non-monetized game accounts.

Usage:
    python3 build_categories_example.py extracted.json --output categories.json
"""

from __future__ import annotations

import argparse
import json
import sys

RULES = [
    # --- CRITICAL ---
    ("accounts.google", "CRITICAL"),
    ("gmail", "CRITICAL"),
    ("login.live.com", "CRITICAL"),
    ("outlook", "CRITICAL"),
    ("paypal", "CRITICAL"),
    ("stripe", "CRITICAL"),
    ("binance", "CRITICAL"),
    ("coinbase", "CRITICAL"),
    ("kraken.com", "CRITICAL"),
    ("aws.amazon.com", "CRITICAL"),
    ("cloud.google.com", "CRITICAL"),
    ("portal.azure.com", "CRITICAL"),
    ("digitalocean", "CRITICAL"),
    ("bank", "CRITICAL"),  # matches most "<something>bank.*" domains

    # --- HIGH ---
    ("facebook.com", "HIGH"),
    ("linkedin.com", "HIGH"),
    ("instagram.com", "HIGH"),
    ("twitter.com", "HIGH"),
    ("x.com", "HIGH"),
    ("discord", "HIGH"),
    ("telegram", "HIGH"),
    ("github.com", "HIGH"),
    ("gitlab.com", "HIGH"),
    ("namecheap", "HIGH"),
    ("godaddy", "HIGH"),
    ("workday", "HIGH"),
    ("myworkdayjobs", "HIGH"),

    # --- MEDIUM ---
    ("steamcommunity", "MEDIUM"),
    ("steampowered", "MEDIUM"),
    ("epicgames", "MEDIUM"),
    ("netflix", "MEDIUM"),
    ("spotify", "MEDIUM"),
    ("reddit.com", "MEDIUM"),
    ("twitch.tv", "MEDIUM"),

    # --- LOW ---
    ("forum", "LOW"),
]


def classify(label: str) -> str:
    low = label.lower()
    for pattern, category in RULES:
        if pattern in low:
            return category
    return "MEDIUM"  # safe default: review unmatched entries manually


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Build categories.json from an example ruleset")
    parser.add_argument("extracted_path")
    parser.add_argument("--output", default="categories.json")
    args = parser.parse_args()

    with open(args.extracted_path, "r", encoding="utf-8") as f:
        extracted = json.load(f)

    categories = {}
    unmatched = []
    for label in extracted["unique_labels"]:
        cat = classify(label)
        categories[label] = cat
        if cat == "MEDIUM" and not any(p in label.lower() for p in (r[0] for r in RULES)):
            unmatched.append(label)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    print(f"Classified {len(categories)} labels -> {args.output}")
    if unmatched:
        print(f"\n{len(unmatched)} labels fell through to the MEDIUM default. Add rules for these:")
        for u in unmatched:
            print(f"  - {u}")


if __name__ == "__main__":
    main()
