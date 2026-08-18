#!/usr/bin/env python3
"""Group a Bitwarden JSON export into local/external buckets and by reused password.

Usage:
    python3 group_reused_passwords.py [vault_export.json]

Reads a `bw export --format json` file (plaintext, contains real passwords)
and prints:
  - count of local vs external login items
  - external items grouped by identical password, largest group first

Does not modify or write the export file. Delete the export yourself after
reviewing the output — see the reminder printed at the end.
"""

from __future__ import annotations

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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        # Windows consoles default to cp1252; export data is UTF-8 and often
        # contains non-ASCII site/account names. Without this, printing a
        # non-Latin1 character crashes with UnicodeEncodeError mid-report.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    path = sys.argv[1] if len(sys.argv) > 1 else "vault_export.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = [
        it for it in data.get("items", [])
        if it.get("type") == 1 and (it.get("login") or {}).get("password")
    ]

    local_items = [it for it in items if item_is_local(it)]
    external_items = [it for it in items if it not in local_items]

    print(f"Total login items:    {len(items)}")
    print(f"Local (skip for now): {len(local_items)}")
    print(f"External (real work): {len(external_items)}")
    print()

    groups: dict[str, list[dict]] = defaultdict(list)
    for it in external_items:
        pw = it["login"]["password"]
        groups[pw].append(it)

    reused = {pw: entries for pw, entries in groups.items() if len(entries) > 1}
    unique_count = sum(1 for entries in groups.values() if len(entries) == 1)

    print(f"Unique passwords (1 site each): {unique_count}")
    print(f"Reused passwords (2+ sites):    {len(reused)}")
    print()

    ranked = sorted(reused.items(), key=lambda kv: len(kv[1]), reverse=True)
    for i, (pw, entries) in enumerate(ranked, 1):
        masked = pw[:2] + "*" * max(len(pw) - 4, 0) + pw[-2:] if len(pw) > 4 else "*" * len(pw)
        print(f"[{i}] password {masked!r} used on {len(entries)} sites:")
        for it in sorted(entries, key=item_label):
            print(f"      - {item_label(it)}  ({it.get('name', '')})")
        print()

    print("Reminder: this script never writes vault_export.json.")
    print("Delete it yourself now that you've reviewed the output:")
    print("  shred -u vault_export.json          # Linux/macOS")
    print("  Remove-Item vault_export.json -Force # Windows PowerShell")


if __name__ == "__main__":
    main()
