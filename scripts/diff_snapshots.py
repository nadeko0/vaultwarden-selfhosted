#!/usr/bin/env python3
"""Compare two password-free vault snapshots by stable item id.

Why id and not name/URI: Bitwarden entries can carry multiple saved URIs,
and their order isn't guaranteed to stay stable across exports. Diffing on
the label text (e.g. "first URI in the list") produces false "new" entries
whenever the URI order simply gets reshuffled between exports — the id is
the only field guaranteed not to change for the life of the item.

Reports:
  - New items      (id in new, not in old)
  - Removed items   (id in old, not in new)
  - Changed items   (id in both, new revisionDate > old revisionDate)

Usage:
    python3 diff_snapshots.py vault_snapshot_OLD.json vault_snapshot_NEW.json
"""

from __future__ import annotations

import argparse
import json
import sys


def load_snapshot(path: str) -> dict[str, dict]:
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    return {it["id"]: it for it in items if it.get("id")}


def label(item: dict) -> str:
    uris = item.get("uris") or []
    uri = next((u for u in uris if u), "")
    name = item.get("name", "?")
    return f"{name}  ({uri})" if uri else name


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Diff two vault snapshots by stable id")
    parser.add_argument("old_snapshot")
    parser.add_argument("new_snapshot")
    args = parser.parse_args()

    old = load_snapshot(args.old_snapshot)
    new = load_snapshot(args.new_snapshot)

    old_ids, new_ids = set(old), set(new)
    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    common_ids = old_ids & new_ids

    changed = [
        new[i] for i in common_ids
        if new[i].get("revisionDate", "") > old[i].get("revisionDate", "")
    ]
    changed.sort(key=lambda it: it.get("revisionDate", ""), reverse=True)

    print(f"=== New items ({len(added_ids)}) ===\n")
    for i in sorted(added_ids, key=lambda i: new[i].get("name", "")):
        print(f"  + {label(new[i])}")

    print(f"\n=== Removed items ({len(removed_ids)}) ===\n")
    for i in sorted(removed_ids, key=lambda i: old[i].get("name", "")):
        print(f"  - {label(old[i])}")

    print(f"\n=== Changed items ({len(changed)}), newest first ===\n")
    for it in changed:
        old_rev = old[it["id"]].get("revisionDate", "?")
        new_rev = it.get("revisionDate", "?")
        print(f"  {new_rev}  (was {old_rev})  |  {label(it)}")


if __name__ == "__main__":
    main()
