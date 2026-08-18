#!/usr/bin/env python3
"""Show what actually changed in the vault within a recent time window.

Classifies each changed item as:
  NEW ITEM           - creationDate == revisionDate (just created)
  PASSWORD CHANGED    - passwordHistory gained an entry in the window
                         (Bitwarden pushes the old value into history on
                         every real password overwrite)
  EDITED (other field) - revisionDate moved but neither of the above
                         (username, URI, notes, etc.)

Caveat: a bulk `bw sync` after migrating to a new server (or a large
import) stamps revisionDate — and often creationDate — on every item at
once. If you point --since past that timestamp, you'll get your entire
vault back as "changes", not real activity. Use --since with a timestamp
just after your last known bulk operation to cut through that noise, or
compare against a snapshot from before it (see diff_snapshots.py) instead.

Usage:
    python3 track_recent_changes.py [vault_export.json] [--hours 3] [--since 2026-08-16T18:45:00Z]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Show recent vault changes, classified by type")
    parser.add_argument("export_path", nargs="?", default="vault_export.json")
    parser.add_argument("--hours", type=float, default=3.0, help="lookback window in hours (default: 3)")
    parser.add_argument("--since", default=None, help="explicit ISO-8601 cutoff, overrides --hours")
    args = parser.parse_args()

    with open(args.export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cutoff = parse_dt(args.since) if args.since else datetime.now(timezone.utc) - timedelta(hours=args.hours)

    rows = []
    for it in data.get("items", []):
        rev = it.get("revisionDate", "")
        if not rev:
            continue
        rev_dt = parse_dt(rev)
        if rev_dt < cutoff:
            continue

        created = it.get("creationDate", "")
        is_new = bool(created) and abs((parse_dt(created) - rev_dt).total_seconds()) < 2

        has_pw_change = any(
            h.get("lastUsedDate") and parse_dt(h["lastUsedDate"]) >= cutoff
            for h in ((it.get("login") or {}).get("passwordHistory") or [])
        )

        name = it.get("name", "???")
        uris = (it.get("login") or {}).get("uris") or []
        uri = uris[0].get("uri", "") if uris else ""

        kind = "NEW ITEM" if is_new else ("PASSWORD CHANGED" if has_pw_change else "EDITED (other field)")
        rows.append((rev_dt, kind, name, uri))

    rows.sort(reverse=True)

    window_desc = f"since {args.since}" if args.since else f"last {args.hours}h"
    print(f"=== Changes {window_desc} ({len(rows)} items) ===\n")
    for dt, kind, name, uri in rows:
        print(f"{dt.strftime('%Y-%m-%d %H:%M:%S')}  |  {kind:20s}  |  {name}  |  {uri[:100]}")


if __name__ == "__main__":
    main()
