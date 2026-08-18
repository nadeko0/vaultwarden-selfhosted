#!/usr/bin/env python3
"""Extract a password-free snapshot of a Bitwarden/Vaultwarden export.

Snapshot contains ONLY: id (stable UUID), name, uris (full list), revisionDate.
No passwords, no other fields — safe to keep around for change-tracking history
and to commit to a repo if you want a record of when you rotated what.

Usage:
    python3 build_snapshot.py [vault_export.json] [--output vault_snapshot_YYYYMMDD.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


def build_snapshot(export_path: str) -> list[dict]:
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    snapshot = []
    for item in data.get("items", []):
        if item.get("type") != 1:  # login items only
            continue
        login = item.get("login") or {}
        if not login.get("password"):
            continue
        snapshot.append({
            "id": item.get("id"),
            "name": item.get("name", ""),
            "uris": [u.get("uri", "") for u in (login.get("uris") or [])],
            "revisionDate": item.get("revisionDate", ""),
        })
    return snapshot


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Build a password-free snapshot from a vault export")
    parser.add_argument("export_path", nargs="?", default="vault_export.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    output = args.output or f"vault_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"

    snapshot = build_snapshot(args.export_path)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"Snapshot written: {output} ({len(snapshot)} login items, no passwords)")
    print(
        "\nReminder: the source export still contains plaintext passwords.\n"
        "Delete it now:\n"
        "  shred -u vault_export.json           # Linux/macOS\n"
        "  Remove-Item vault_export.json -Force # Windows PowerShell"
    )


if __name__ == "__main__":
    main()
