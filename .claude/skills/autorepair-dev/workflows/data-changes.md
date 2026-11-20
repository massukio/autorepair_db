# Database changes

Shops keep using old databases and old backup files for years. Every change
must open, migrate and restore them safely.

## Rules

1. **Never lose data in a migration.** Prefer additive changes
   (`ALTER TABLE ... ADD COLUMN` guarded by `PRAGMA table_info`). A table
   rebuild (like `_migrate_v1_to_v2`) must: turn `foreign_keys` OFF *outside*
   the transaction (otherwise dropping `records` cascades and empties
   `record_items`), do everything in ONE transaction, run
   `PRAGMA foreign_key_check` before COMMIT, and be covered by a test that
   builds the old schema by hand (see `V1_SCHEMA` in `tests/test_db.py`).
2. Migrations live in `_create_schema()` in `app/db.py`, detected from the
   actual table shape (not only `settings.schema_version`); bump
   `SCHEMA_VERSION`. `_create_schema` runs on every open **and after every
   restore**, so old backup files upgrade automatically.
   Python gotcha: `executescript()` COMMITs any open transaction first — put
   `BEGIN;` inside the script.
3. `check_backup_file()` defines what a valid backup is (`REQUIRED_TABLES`).
   Do not add newly created tables to `REQUIRED_TABLES`, or older backups will
   be rejected.
4. Writes that touch several rows use `with self.conn:` (one transaction).
5. Items are soft-deleted (`active=0`); queries for the item buttons use
   `list_items()`; history/report queries must still show hidden items' names.
6. Plates live in `vehicles`; records reference `vehicle_id`. Match via
   `vehicles.plate_key` (dash-insensitive); create cars only through
   `Database._vehicle_id()`.
7. Dates are ISO `YYYY-MM-DD` strings; compare as strings.
8. New query on `records` → check it with `EXPLAIN QUERY PLAN` (want
   `COVERING INDEX idx_records_date` / `idx_records_vehicle`, no full `SCAN
   records` on common paths) and run `tools/bench.py`. Prefer extending a
   covering index over adding a new one; every index costs disk and write time.
9. Backups must stay a single self-contained file: keep the rollback journal
   (no WAL), keep `VACUUM INTO` in `backup_to`, and keep
   `check_backup_file` accepting every older schema (`REQUIRED_TABLES` plus the
   column check).

## Test checklist

- New test in `tests/test_db.py` for the query/migration.
- Open a database created by the previous release (e.g. `git stash` the
  change, create one with `tools/make_fake_data.py`, unstash, open it).
- Restore an old backup file into the new version.
