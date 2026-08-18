# Bitwarden Vault Hygiene Toolkit

A set of small, local-only Python scripts for auditing a Bitwarden/Vaultwarden
vault that's grown for years: finding reused passwords, prioritizing which
ones to rotate first, and tracking real changes over time without getting
fooled by sync noise.

Built after migrating a ~500-entry personal vault to a self-hosted
[Vaultwarden](https://github.com/dani-garcia/vaultwarden) instance. Reviewing
every entry by hand wasn't realistic, and every tool in this repo exists
because a naive first attempt at something broke in a specific, instructive
way — see [Devlog](#devlog) below.

## Why local-only

Every script here operates on `bw export --format json` output on your own
machine. Nothing is sent anywhere:

- **No API key, no network calls.** Site-importance categorization
  (`build_categories_example.py`) is a plain rule table you edit — swap in
  your own domains. There is nothing to authenticate against.
- **Passwords never get written or printed.** `group_reused_passwords.py`
  and `priority_report.py` group entries by password using a SHA-256 hash
  of the password as an in-memory dict key — the plaintext value itself
  never leaves the variable it's read into, and grouping output shows only
  a masked preview (`Ol****3!`), not the real value.
- **Snapshots are intentionally safe to keep.** `build_snapshot.py` writes
  only `id` / `name` / `uris` / `revisionDate` — no password field exists
  in that file's schema at all. Fine to commit for a rotation history.
- **The one file with real secrets, `vault_export.json`, is never touched
  after use.** Every script that reads it prints a reminder to shred it
  when you're done.

## What's here

| Script | Purpose |
|---|---|
| `group_reused_passwords.py` | Quick pass: how many entries reuse the same password, grouped and ranked by size. |
| `priority_report.py` | Two-phase pipeline — `extract` pulls password-reuse groups down to a list of bare site names (no passwords), `report` turns a categorized version of that list into a markdown priority report. A group is bumped to top priority the moment *any* site in it is CRITICAL, regardless of group size. |
| `build_categories_example.py` | Starter rule table for the categorization step — CRITICAL / HIGH / MEDIUM / LOW by domain keyword. Meant to be edited, not used as-is. |
| `build_snapshot.py` | Strips a full export down to a password-free `{id, name, uris, revisionDate}` snapshot. |
| `diff_snapshots.py` | Compares two snapshots by stable `id` to find genuinely new / removed / edited entries. |
| `track_recent_changes.py` | Real-time check: what changed in the last N hours, classified as a new item, an actual password rotation, or an unrelated field edit. |

## Usage

```bash
# 1. Export your vault (bw CLI, already logged in and unlocked)
bw sync
bw export --format json --output vault_export.json

# 2. See which passwords are reused
python3 scripts/group_reused_passwords.py vault_export.json

# 3. Build a prioritized rotation plan
python3 scripts/priority_report.py extract vault_export.json --output extracted.json
python3 scripts/build_categories_example.py extracted.json --output categories.json
# edit categories.json / the rule table above for your actual domains, then:
python3 scripts/priority_report.py report --extracted extracted.json --categories categories.json

# 4. Take a snapshot now, another one later, see what really changed
python3 scripts/build_snapshot.py vault_export.json --output vault_snapshot_$(date +%Y%m%d).json
# ...time passes, you rotate some passwords, run bw export again...
python3 scripts/diff_snapshots.py vault_snapshot_20260101.json vault_snapshot_20260201.json

# 5. Or check activity in the last few hours directly
python3 scripts/track_recent_changes.py vault_export.json --hours 3

# 6. Always, immediately after:
shred -u vault_export.json          # Linux/macOS
Remove-Item vault_export.json -Force # Windows PowerShell
```

A synthetic demo export lives at `examples/sample_vault_export.json` — every
command above runs against it with no real vault required:

```bash
python3 scripts/group_reused_passwords.py examples/sample_vault_export.json
```

## Devlog

Four things broke while building this, each one changing the design:

### 1. Windows console couldn't print the data it was exporting

`print()` on a script iterating a Bitwarden export crashed partway through
with `UnicodeEncodeError: 'charmap' codec can't encode character`. Windows
terminals default `stdout` to `cp1252`; vault entries routinely contain
non-Latin1 names and URIs. Fix, added to every script here:

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

### 2. "What changed today" via `revisionDate` was 100% noise after a migration

First attempt at change tracking: filter items where
`revisionDate` falls on today's date. Result on a freshly-migrated vault:
**every single entry** came back as "changed today" — the bulk `bw sync`
after moving to the new Vaultwarden instance stamped `revisionDate` (and,
for some entries, `creationDate`) identically across the whole vault in a
two-minute window. A same-day filter can't distinguish "you edited this"
from "the server touched this during an unrelated bulk operation."

Fix: two different approaches depending on what you're actually asking:
- **"What's different since a known point in time?"** → `diff_snapshots.py`,
  comparing two snapshots by stable id instead of trusting a single
  timestamp field.
- **"Did I really just rotate a password?"** → `track_recent_changes.py`,
  which checks `passwordHistory` instead of `revisionDate`. Bitwarden only
  appends to password history when a password is *actually overwritten*
  with a new value — a bulk sync that re-stamps metadata doesn't touch it,
  so it isn't fooled by the same noise.

### 3. Diffing by "first URI in the list" invented phantom new entries

Before switching to id-based diffing, a first pass compared two exports by
label (`name` + first saved URI). Result: dozens of entries that hadn't
changed at all showed up as "new," because an item with multiple saved
URIs doesn't guarantee the same URI stays first across two exports —
Bitwarden doesn't promise ordering stability there. Comparing on the
item's `id` (a stable UUID that never changes for the life of the entry)
instead of any derived text field fixed it outright.

### 4. Grouping by password without ever holding onto the password

The naive version of "group entries with the same password" builds
`{password: [entries]}` directly — which means the plaintext password sits
in a variable, and by extension in scrollback, in `pdb` if you ever drop a
breakpoint, in a `print(groups)` while debugging. Grouping by
`hashlib.sha256(password).hexdigest()` instead gives the same grouping
correctness (identical passwords still collide identically) without ever
needing the plaintext itself as a persistent value.

## Requirements

Python 3.10+, standard library only. No dependencies to install for the
scripts in this repo. You'll separately need the
[Bitwarden CLI](https://bitwarden.com/help/cli/) (`bw`) to produce the
`vault_export.json` these scripts read.

## License

MIT — see [LICENSE](LICENSE).
