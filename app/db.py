"""SQLite data layer.

Schema (version 2)
------------------
vehicles      : one row per car. plate_key = plate without dashes (match key,
                UNIQUE); plate = display form (prefers the dashed spelling).
records       : one row per visit -> vehicle_id, date 'YYYY-MM-DD', amount
                (integer NT$), optional mileage / note, unix timestamps.
record_items  : visit <-> item links (WITHOUT ROWID, clustered by record).
items         : selectable service items. Deleting only hides (active=0) so
                old records keep their names.
settings      : key/value (schema_version, font size, last backup ...).

Performance design
------------------
- idx_records_date    (date, vehicle_id, amount): date-range reports, totals,
  "newest first" listing - all answered from the index alone.
- idx_records_vehicle (vehicle_id, date, amount): one car's history, last
  visit and statistics - index only.
- Partial plate search scans the small vehicles table, then uses
  idx_records_vehicle, instead of scanning every visit.
- Rollback journal + synchronous=FULL (defaults): the database is always a
  single file and survives power loss; backups are compact VACUUM INTO copies.
"""
import datetime as _dt
import os
import re
import sqlite3
import time
from typing import Iterable, List, Optional

from app.config import DEFAULT_ITEMS

SCHEMA_VERSION = 2
SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_TABLES = {"items", "records", "record_items", "settings"}  # true for v1 and v2 files


class DataError(Exception):
    """User-facing error; message is shown to the user as-is (Chinese)."""


def normalize_plate(text: str) -> str:
    """Upper-case, keep only A-Z 0-9 and '-', collapse duplicate dashes."""
    text = (text or "").upper().strip()
    text = re.sub(r"[^A-Z0-9-]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def plate_key(text: str) -> str:
    """Plate without dashes, used for matching (ABC-1234 == ABC1234)."""
    return normalize_plate(text).replace("-", "")


def _now() -> int:
    return int(time.time())


def _columns(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS vehicles (
    id        INTEGER PRIMARY KEY,
    plate_key TEXT NOT NULL UNIQUE,
    plate     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    date       TEXT NOT NULL,
    amount     INTEGER NOT NULL DEFAULT 0,
    mileage    INTEGER,
    note       TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_date ON records(date, vehicle_id, amount);
CREATE INDEX IF NOT EXISTS idx_records_vehicle ON records(vehicle_id, date, amount);
CREATE TABLE IF NOT EXISTS record_items (
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    item_id   INTEGER NOT NULL REFERENCES items(id),
    PRIMARY KEY (record_id, item_id)
) WITHOUT ROWID;
"""


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """v1 stored plate/plate_key on every record. Move plates into vehicles.

    Runs with foreign keys OFF (so dropping the old tables cannot cascade) in
    one transaction, then verifies foreign keys before committing.
    """
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # executescript commits anything pending first, so BEGIN must be inside the script;
        # the transaction stays open until the COMMIT below
        conn.executescript("""
            BEGIN;
            CREATE TABLE vehicles (
                id        INTEGER PRIMARY KEY,
                plate_key TEXT NOT NULL UNIQUE,
                plate     TEXT NOT NULL
            );
            INSERT INTO vehicles (plate_key, plate)
                SELECT plate_key,
                       (SELECT r2.plate FROM records r2 WHERE r2.plate_key = r.plate_key
                        ORDER BY length(r2.plate) DESC, r2.id DESC LIMIT 1)
                FROM records r GROUP BY plate_key;
            CREATE TABLE records_v2 (
                id         INTEGER PRIMARY KEY,
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                date       TEXT NOT NULL,
                amount     INTEGER NOT NULL DEFAULT 0,
                mileage    INTEGER,
                note       TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            INSERT INTO records_v2
                SELECT r.id, v.id, r.date, r.amount, r.mileage, COALESCE(r.note, ''),
                       COALESCE(CAST(strftime('%s', r.created_at) AS INTEGER), 0),
                       COALESCE(CAST(strftime('%s', r.updated_at) AS INTEGER), 0)
                FROM records r JOIN vehicles v ON v.plate_key = r.plate_key;
            CREATE TABLE record_items_v2 (
                record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                item_id   INTEGER NOT NULL REFERENCES items(id),
                PRIMARY KEY (record_id, item_id)
            ) WITHOUT ROWID;
            INSERT OR IGNORE INTO record_items_v2 SELECT record_id, item_id FROM record_items;
            DROP TABLE record_items;
            DROP TABLE records;
            ALTER TABLE records_v2 RENAME TO records;
            ALTER TABLE record_items_v2 RENAME TO record_items;
        """)
        bad = conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise sqlite3.IntegrityError(f"migration foreign key check failed: {bad[:3]}")
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create or upgrade the schema. Runs on every open and after every restore."""
    tables = _tables(conn)
    if "records" in tables and "plate_key" in _columns(conn, "records"):
        _migrate_v1_to_v2(conn)
    conn.executescript(_SCHEMA_V2)
    for old in ("idx_records_plate_key", "idx_records_plate_date"):  # v1 leftovers
        conn.execute(f"DROP INDEX IF EXISTS {old}")
    conn.execute(
        "INSERT INTO settings(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
    seeded = conn.execute("SELECT value FROM settings WHERE key='items_seeded'").fetchone()
    if seeded is None:
        if not conn.execute("SELECT 1 FROM items LIMIT 1").fetchone():
            for i, name in enumerate(DEFAULT_ITEMS):
                conn.execute(
                    "INSERT OR IGNORE INTO items(name, sort_order, active) VALUES(?, ?, 1)", (name, i))
        conn.execute("INSERT INTO settings(key, value) VALUES('items_seeded', '1')")
    conn.commit()


_RECORD_SELECT = ("SELECT r.id, r.vehicle_id, r.date, r.amount, r.mileage, r.note, "
                  "r.created_at, r.updated_at, v.plate, v.plate_key "
                  "FROM records r JOIN vehicles v ON v.id = r.vehicle_id")


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA cache_size = -16000")  # 16 MB page cache
        self.conn.execute("PRAGMA temp_store = MEMORY")
        _create_schema(self.conn)

    def close(self) -> None:
        try:
            self.conn.execute("PRAGMA optimize")  # keeps query-planner statistics fresh
        except sqlite3.Error:
            pass
        self.conn.close()

    # ------------------------------------------------------------------ settings
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # --------------------------------------------------------------------- items
    def list_items(self, include_hidden: bool = False) -> List[dict]:
        sql = "SELECT id, name, sort_order, active FROM items"
        if not include_hidden:
            sql += " WHERE active=1"
        sql += " ORDER BY sort_order, id"
        return [dict(r) for r in self.conn.execute(sql)]

    def add_item(self, name: str) -> int:
        name = (name or "").strip()
        if not name:
            raise DataError("項目名稱不能空白。")
        row = self.conn.execute("SELECT id, active FROM items WHERE name=?", (name,)).fetchone()
        next_order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM items WHERE active=1"
        ).fetchone()[0]
        with self.conn:
            if row is not None:
                if row["active"]:
                    raise DataError(f"「{name}」已經存在了。")
                self.conn.execute(
                    "UPDATE items SET active=1, sort_order=? WHERE id=?", (next_order, row["id"]))
                return row["id"]
            cur = self.conn.execute(
                "INSERT INTO items(name, sort_order, active) VALUES(?, ?, 1)", (name, next_order))
            return cur.lastrowid

    def rename_item(self, item_id: int, new_name: str) -> None:
        new_name = (new_name or "").strip()
        if not new_name:
            raise DataError("項目名稱不能空白。")
        row = self.conn.execute(
            "SELECT id, active FROM items WHERE name=? AND id<>?", (new_name, item_id)).fetchone()
        with self.conn:
            if row is not None:
                if row["active"]:
                    raise DataError(f"「{new_name}」已經存在了。")
                # a deleted (hidden) item has this name: move it out of the way,
                # old records keep showing it under the suffixed name
                n = 1
                while self.conn.execute("SELECT 1 FROM items WHERE name=?",
                                        (f"{new_name}（舊{n}）",)).fetchone():
                    n += 1
                self.conn.execute("UPDATE items SET name=? WHERE id=?", (f"{new_name}（舊{n}）", row["id"]))
            self.conn.execute("UPDATE items SET name=? WHERE id=?", (new_name, item_id))

    def hide_item(self, item_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE items SET active=0 WHERE id=?", (item_id,))

    def move_item(self, item_id: int, delta: int) -> None:
        """Move an active item up (delta=-1) or down (delta=+1)."""
        ids = [it["id"] for it in self.list_items()]
        if item_id not in ids:
            return
        i = ids.index(item_id)
        j = i + delta
        if j < 0 or j >= len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        with self.conn:
            self.conn.executemany("UPDATE items SET sort_order=? WHERE id=?",
                                  [(order, iid) for order, iid in enumerate(ids)])

    # ------------------------------------------------------------------ vehicles
    def _vehicle_id(self, plate: str) -> int:
        """Find or create the vehicle for a (normalized) plate. Call inside a transaction."""
        key = plate_key(plate)
        row = self.conn.execute("SELECT id, plate FROM vehicles WHERE plate_key=?", (key,)).fetchone()
        if row is None:
            return self.conn.execute(
                "INSERT INTO vehicles(plate_key, plate) VALUES(?, ?)", (key, plate)).lastrowid
        if len(plate) > len(row["plate"]):  # prefer the spelling with the dash
            self.conn.execute("UPDATE vehicles SET plate=? WHERE id=?", (plate, row["id"]))
        return row["id"]

    def _drop_unused_vehicle(self, vehicle_id: int) -> None:
        self.conn.execute(
            "DELETE FROM vehicles WHERE id=? AND NOT EXISTS "
            "(SELECT 1 FROM records WHERE vehicle_id=?)", (vehicle_id, vehicle_id))

    # ------------------------------------------------------------------- records
    @staticmethod
    def _validate(date: str, plate: str, amount) -> tuple:
        try:
            _dt.date.fromisoformat(date)
        except (TypeError, ValueError):
            raise DataError("日期格式錯誤。")
        plate = normalize_plate(plate)
        if not plate:
            raise DataError("請輸入車牌。")
        try:
            amount = int(str(amount).replace(",", "").replace("，", "").strip())
        except (TypeError, ValueError):
            raise DataError("請輸入金額（只能是數字）。")
        if amount < 0:
            raise DataError("金額不能是負數。")
        return plate, amount

    def _set_record_items(self, record_id: int, item_ids: Iterable[int]) -> None:
        self.conn.execute("DELETE FROM record_items WHERE record_id=?", (record_id,))
        self.conn.executemany("INSERT INTO record_items(record_id, item_id) VALUES(?, ?)",
                              [(record_id, iid) for iid in set(item_ids)])

    def add_record(self, date: str, plate: str, amount, item_ids: Iterable[int] = (),
                   mileage: Optional[int] = None, note: str = "") -> int:
        plate, amount = self._validate(date, plate, amount)
        now = _now()
        with self.conn:
            vid = self._vehicle_id(plate)
            cur = self.conn.execute(
                "INSERT INTO records(vehicle_id, date, amount, mileage, note, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (vid, date, amount, mileage, (note or "").strip(), now, now))
            self._set_record_items(cur.lastrowid, item_ids)
        return cur.lastrowid

    def update_record(self, record_id: int, date: str, plate: str, amount,
                      item_ids: Iterable[int] = (), mileage: Optional[int] = None,
                      note: str = "") -> None:
        plate, amount = self._validate(date, plate, amount)
        with self.conn:
            old = self.conn.execute("SELECT vehicle_id FROM records WHERE id=?", (record_id,)).fetchone()
            if old is None:
                raise DataError("找不到這筆紀錄，可能已經被刪除了。")
            vid = self._vehicle_id(plate)
            self.conn.execute(
                "UPDATE records SET vehicle_id=?, date=?, amount=?, mileage=?, note=?, updated_at=? "
                "WHERE id=?",
                (vid, date, amount, mileage, (note or "").strip(), _now(), record_id))
            self._set_record_items(record_id, item_ids)
            if old["vehicle_id"] != vid:
                self._drop_unused_vehicle(old["vehicle_id"])

    def delete_record(self, record_id: int) -> None:
        with self.conn:
            row = self.conn.execute("SELECT vehicle_id FROM records WHERE id=?", (record_id,)).fetchone()
            self.conn.execute("DELETE FROM records WHERE id=?", (record_id,))
            if row:
                self._drop_unused_vehicle(row["vehicle_id"])

    def _attach_items(self, rows) -> List[dict]:
        records = [dict(r) for r in rows]
        if not records:
            return records
        by_id = {r["id"]: r for r in records}
        for r in records:
            r["item_ids"] = []
            r["item_names"] = []
        ids = list(by_id)
        # chunk to stay well below SQLite's variable limit
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for row in self.conn.execute(
                f"SELECT ri.record_id, i.id, i.name FROM record_items ri "
                f"JOIN items i ON i.id = ri.item_id WHERE ri.record_id IN ({marks}) "
                f"ORDER BY i.sort_order, i.id",
                chunk,
            ):
                rec = by_id[row["record_id"]]
                rec["item_ids"].append(row["id"])
                rec["item_names"].append(row["name"])
        return records

    def get_record(self, record_id: int) -> Optional[dict]:
        rows = self.conn.execute(_RECORD_SELECT + " WHERE r.id=?", (record_id,)).fetchall()
        recs = self._attach_items(rows)
        return recs[0] if recs else None

    @staticmethod
    def _search_where(plate: str, date_from: Optional[str], date_to: Optional[str]):
        sql = " WHERE 1=1"
        args: list = []
        key = plate_key(plate)
        if key:
            # scan the small vehicles table, then use idx_records_vehicle
            sql += " AND r.vehicle_id IN (SELECT id FROM vehicles WHERE plate_key LIKE ?)"
            args.append(f"%{key}%")
        if date_from:
            sql += " AND r.date >= ?"
            args.append(date_from)
        if date_to:
            sql += " AND r.date <= ?"
            args.append(date_to)
        return sql, args

    def search_records(self, plate: str = "", date_from: Optional[str] = None,
                       date_to: Optional[str] = None, limit: Optional[int] = None,
                       offset: int = 0) -> List[dict]:
        """Newest first. Use limit/offset to load a page at a time."""
        where, args = self._search_where(plate, date_from, date_to)
        sql = _RECORD_SELECT + where + " ORDER BY r.date DESC, r.id DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            args += [int(limit), int(offset)]
        return self._attach_items(self.conn.execute(sql, args).fetchall())

    def search_stats(self, plate: str = "", date_from: Optional[str] = None,
                     date_to: Optional[str] = None) -> dict:
        """Count / total / number of different cars for a search, without loading rows."""
        where, args = self._search_where(plate, date_from, date_to)
        row = self.conn.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(r.amount), 0) AS total, "
            "COUNT(DISTINCT r.vehicle_id) AS cars, MAX(r.vehicle_id) AS vehicle_id "
            "FROM records r" + where, args).fetchone()
        stats = dict(row)
        stats["plate"] = None
        if stats["cars"] == 1:
            v = self.conn.execute("SELECT plate FROM vehicles WHERE id=?", (stats["vehicle_id"],)).fetchone()
            stats["plate"] = v["plate"] if v else None
        return stats

    def plate_summary(self, plate: str) -> Optional[dict]:
        """Visit statistics for one car (exact plate match, dash-insensitive)."""
        key = plate_key(plate)
        if not key:
            return None
        v = self.conn.execute("SELECT id, plate FROM vehicles WHERE plate_key=?", (key,)).fetchone()
        if v is None:
            return None
        row = self.conn.execute(
            "SELECT COUNT(*) AS visits, COALESCE(SUM(amount), 0) AS total, "
            "MIN(date) AS first_date, MAX(date) AS last_date, COUNT(DISTINCT date) AS visit_days "
            "FROM records WHERE vehicle_id=?", (v["id"],)).fetchone()
        if not row["visits"]:
            return None
        summary = dict(row)
        summary["plate"] = v["plate"]
        first = _dt.date.fromisoformat(summary["first_date"])
        last = _dt.date.fromisoformat(summary["last_date"])
        summary["avg_interval_days"] = (round((last - first).days / (summary["visit_days"] - 1))
                                        if summary["visit_days"] >= 2 else None)
        summary["days_since_last"] = (_dt.date.today() - last).days
        return summary

    def last_record_for_plate(self, plate: str, exclude_id: Optional[int] = None) -> Optional[dict]:
        key = plate_key(plate)
        if not key:
            return None
        sql = _RECORD_SELECT + " WHERE v.plate_key=?"
        args: list = [key]
        if exclude_id is not None:
            sql += " AND r.id<>?"
            args.append(exclude_id)
        sql += " ORDER BY r.date DESC, r.id DESC LIMIT 1"
        recs = self._attach_items(self.conn.execute(sql, args).fetchall())
        return recs[0] if recs else None

    def report(self, date_from: str, date_to: str, bucket: str = "day") -> dict:
        """Totals for a period. bucket = 'day' or 'month' for the breakdown table.
        Everything except the item counts is answered from idx_records_date alone."""
        args = (date_from, date_to)
        where = "WHERE date >= ? AND date <= ?"
        t = self.conn.execute(
            f"SELECT COUNT(*) AS visits, COALESCE(SUM(amount), 0) AS total, "
            f"COUNT(DISTINCT vehicle_id) AS cars FROM records {where}", args).fetchone()
        key = "date" if bucket == "day" else "substr(date, 1, 7)"
        buckets = [dict(r) for r in self.conn.execute(
            f"SELECT {key} AS period, COUNT(*) AS visits, SUM(amount) AS total "
            f"FROM records {where} GROUP BY period ORDER BY period", args)]
        items = [dict(r) for r in self.conn.execute(
            "SELECT i.name AS name, c.times AS times FROM ("
            "  SELECT ri.item_id, COUNT(*) AS times FROM records r "
            "  JOIN record_items ri ON ri.record_id = r.id "
            "  WHERE r.date >= ? AND r.date <= ? GROUP BY ri.item_id"
            ") c JOIN items i ON i.id = c.item_id ORDER BY c.times DESC, i.sort_order", args)]
        customers = [dict(r) for r in self.conn.execute(
            "SELECT v.plate AS plate, c.visits, c.total, c.last_date FROM ("
            f"  SELECT vehicle_id, COUNT(*) AS visits, SUM(amount) AS total, MAX(date) AS last_date "
            f"  FROM records {where} GROUP BY vehicle_id ORDER BY visits DESC, total DESC LIMIT 50"
            ") c JOIN vehicles v ON v.id = c.vehicle_id ORDER BY c.visits DESC, c.total DESC", args)]
        return {"visits": t["visits"], "total": t["total"], "cars": t["cars"],
                "buckets": buckets, "items": items, "customers": customers}

    def count_records(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    # ------------------------------------------------------------ backup/restore
    def _same_file(self, path: str) -> bool:
        try:
            return os.path.exists(path) and os.path.samefile(path, self.path)
        except OSError:
            return False

    def backup_to(self, dest_path: str) -> None:
        """Write a compact, consistent copy of the whole database to dest_path."""
        if self._same_file(dest_path):
            raise DataError("不能把備份存在目前正在使用的資料檔上，請換一個位置或檔名。")
        tmp = dest_path + ".tmp"
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            self.conn.commit()
            self.conn.execute("VACUUM INTO ?", (tmp,))
            self.check_backup_file(tmp)  # never replace an older good backup with a bad copy
            os.replace(tmp, dest_path)
        except (OSError, sqlite3.Error, DataError) as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            raise DataError(f"無法寫入備份檔：{e}")

    @staticmethod
    def check_backup_file(path: str) -> int:
        """Validate a backup file; return its record count or raise DataError."""
        try:
            with open(path, "rb") as f:
                header = f.read(16)
        except OSError:
            raise DataError("無法讀取這個檔案。")
        if header != SQLITE_HEADER:
            raise DataError("這個檔案不是本程式的備份檔。")
        try:
            conn = sqlite3.connect(f"file:{_uri_path(path)}?mode=ro", uri=True)
            try:
                tables = _tables(conn)
                if not REQUIRED_TABLES.issubset(tables):
                    raise DataError("這個檔案不是本程式的備份檔。")
                cols = _columns(conn, "records")
                if not ({"date", "amount", "plate_key"} <= cols or {"date", "amount", "vehicle_id"} <= cols):
                    raise DataError("這個檔案不是本程式的備份檔。")
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DataError("備份檔已損壞，無法還原。")
                return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.Error:
            raise DataError("備份檔已損壞或無法讀取，無法還原。")

    def restore_from(self, src_path: str) -> None:
        """Replace all current data with the contents of a backup file."""
        if self._same_file(src_path):
            raise DataError("這是目前正在使用的資料檔，不需要還原。請選擇備份檔。")
        self.check_backup_file(src_path)
        try:
            src = sqlite3.connect(f"file:{_uri_path(src_path)}?mode=ro", uri=True)
            try:
                src.backup(self.conn)
            finally:
                src.close()
            self.conn.execute("PRAGMA foreign_keys = ON")
            _create_schema(self.conn)  # upgrades older backups
        except sqlite3.Error as e:
            raise DataError(f"還原失敗：{e}")


def _uri_path(path: str) -> str:
    """Absolute path usable in a sqlite file: URI (handles spaces, #, ? and Windows drives)."""
    from urllib.parse import quote
    p = os.path.abspath(path).replace("\\", "/")
    if p.startswith("//"):
        p = "//" + p  # network path //server/share/x -> file:////server/share/x
    elif not p.startswith("/"):
        p = "/" + p  # C:/x -> /C:/x
    return quote(p, safe="/:")
