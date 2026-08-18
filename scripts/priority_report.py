#!/usr/bin/env python3
"""Prioritize which reused Bitwarden passwords to rotate first.

Two-phase workflow — no cloud API key required. Site-importance categorization
is done by a human (or by pasting the extracted label list into any LLM chat)
reading a plain list of domains, never by an automated API call that would
need credentials or send data off-machine:

  Phase "extract":
    Reads a `bw export --format json` file, filters out local/dev entries,
    groups external items by identical password, and writes ONLY the unique
    site names/domains (never passwords) to an intermediate JSON file.

  Phase "report":
    Reads the intermediate extraction file plus a categorization mapping
    ({site_label: CRITICAL|HIGH|MEDIUM|LOW}, produced externally — see
    build_categories_example.py for a starter ruleset) and writes the final
    markdown priority report.

Passwords never leave the extract phase: they are used solely as an
in-memory grouping key (immediately hashed) and are never printed, logged,
or written to any file at any stage.

Usage:
    python3 priority_report.py extract [vault_export.json] [--output extracted.json]
    python3 priority_report.py report --extracted extracted.json --categories categories.json [--output priority_report.md]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from urllib.parse import urlparse

LOCAL_HOST_RE = re.compile(
    r"""
    ^(
        localhost |
        127\.\d+\.\d+\.\d+ |
        10\.\d+\.\d+\.\d+ |
        192\.168\.\d+\.\d+ |
        172\.(1[6-9]|2\d|3[01])\.\d+\.\d+ |
        .*\.local$ |
        .*\.lan$ |
        .*\.home$
    )$
    """,
    re.IGNORECASE | re.VERBOSE,
)

CATEGORY_WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def uri_is_local(uri: str) -> bool:
    parsed = urlparse(uri if "://" in uri else f"http://{uri}")
    host = (parsed.hostname or parsed.path or uri).strip().lower()
    return bool(LOCAL_HOST_RE.match(host))


def item_is_local(item: dict) -> bool:
    login = item.get("login") or {}
    uris = login.get("uris") or []
    if not uris:
        return False
    return all(uri_is_local(u.get("uri", "")) for u in uris if u.get("uri"))


def item_label(item: dict) -> str:
    login = item.get("login") or {}
    uris = login.get("uris") or []
    if uris:
        return uris[0].get("uri", item.get("name", "?"))
    return item.get("name", "?")


def load_items(path: str) -> tuple[list[dict], list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = [
        it for it in data.get("items", [])
        if it.get("type") == 1 and (it.get("login") or {}).get("password")
    ]
    local_items = [it for it in items if item_is_local(it)]
    external_items = [it for it in items if it not in local_items]
    return local_items, external_items


def group_by_password(external_items: list[dict]) -> dict[str, list[dict]]:
    """Group items by password. Returns {password_hash: [items]}.

    The password itself is only ever used as a dict key in memory here — it
    is hashed immediately so nothing derived from the plaintext password is
    retained beyond this function's local scope in a reversible form.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for it in external_items:
        pw = it["login"]["password"]
        key = hashlib.sha256(pw.encode("utf-8")).hexdigest()
        groups[key].append(it)
    return {k: v for k, v in groups.items() if len(v) >= 2}


def cmd_extract(args: argparse.Namespace) -> None:
    local_items, external_items = load_items(args.export_path)
    groups = group_by_password(external_items)

    print(f"Local items (skipped from prioritization): {len(local_items)}", file=sys.stderr)
    print(f"External items: {len(external_items)}", file=sys.stderr)
    print(f"Reused-password groups (2+ sites): {len(groups)}", file=sys.stderr)

    out_groups = {
        f"group_{idx}": [item_label(it) for it in entries]
        for idx, (_, entries) in enumerate(groups.items(), 1)
    }
    out_local = sorted(item_label(it) for it in local_items)
    unique_labels = sorted({label for labels in out_groups.values() for label in labels})
    print(f"Unique site labels to categorize: {len(unique_labels)}", file=sys.stderr)

    payload = {"groups": out_groups, "local_items": out_local, "unique_labels": unique_labels}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Extracted (no passwords) -> {args.output}", file=sys.stderr)


def build_report(extracted: dict, categories: dict[str, str]) -> str:
    group_summaries = []
    for group_id, labels in extracted["groups"].items():
        idx = int(group_id.split("_")[1])
        labeled = [(label, categories.get(label, "MEDIUM")) for label in labels]
        labeled.sort(key=lambda t: -CATEGORY_WEIGHT[t[1]])
        max_severity = max(CATEGORY_WEIGHT[c] for _, c in labeled)
        group_summaries.append({
            "group_num": idx, "size": len(labels), "max_severity": max_severity, "labeled": labeled,
        })

    group_summaries.sort(key=lambda g: (g["max_severity"], g["size"]), reverse=True)

    p1 = [g for g in group_summaries if g["max_severity"] == CATEGORY_WEIGHT["CRITICAL"]]
    p2 = [g for g in group_summaries if g["max_severity"] == CATEGORY_WEIGHT["HIGH"]]
    p3 = [g for g in group_summaries if g["max_severity"] in (CATEGORY_WEIGHT["MEDIUM"], CATEGORY_WEIGHT["LOW"])]

    lines: list[str] = ["# Password Rotation Priority Report\n"]

    def render_group(g: dict) -> str:
        names = ", ".join(name for name, _ in g["labeled"])
        return f"- **Group {g['group_num']}** ({g['size']} sites): {names}"

    lines.append(f"## Priority 1 - rotate today (CRITICAL, {len(p1)} groups)\n")
    lines.extend(render_group(g) for g in p1) if p1 else lines.append("_(none)_")
    lines.append("")

    lines.append(f"## Priority 2 - rotate this week (HIGH, {len(p2)} groups)\n")
    lines.extend(render_group(g) for g in p2) if p2 else lines.append("_(none)_")
    lines.append("")

    lines.append(f"## Priority 3 - low urgency (MEDIUM/LOW, {len(p3)} groups)\n")
    lines.extend(render_group(g) for g in p3) if p3 else lines.append("_(none)_")
    lines.append("")

    local_items = extracted.get("local_items", [])
    lines.append(f"## Local/dev (no rotation needed, {len(local_items)} entries)\n")
    for label in sorted(local_items):
        lines.append(f"- {label}")
    lines.append("")

    return "\n".join(lines)


def cmd_report(args: argparse.Namespace) -> None:
    with open(args.extracted, "r", encoding="utf-8") as f:
        extracted = json.load(f)
    with open(args.categories, "r", encoding="utf-8") as f:
        categories = json.load(f)

    for label in extracted["unique_labels"]:
        cat = str(categories.get(label, "MEDIUM")).upper()
        categories[label] = cat if cat in CATEGORY_WEIGHT else "MEDIUM"

    report = build_report(extracted, categories)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to {args.output}", file=sys.stderr)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Prioritize password rotation by site importance")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Read vault export, group by password, dump site labels (no passwords)")
    p_extract.add_argument("export_path", nargs="?", default="vault_export.json")
    p_extract.add_argument("--output", default="extracted.json")
    p_extract.set_defaults(func=cmd_extract)

    p_report = sub.add_parser("report", help="Build the final markdown report from extracted labels + categorization")
    p_report.add_argument("--extracted", default="extracted.json")
    p_report.add_argument("--categories", required=True)
    p_report.add_argument("--output", default="priority_report.md")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
