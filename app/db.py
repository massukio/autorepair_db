"""SQLite data layer.

Schema
------
items         : the selectable service items (機油, 電瓶 ...). Deleting an item
                only hides it (active=0) so old records keep their item names.
records       : one row per customer visit (date, plate, amount, ...).
record_items  : many-to-many link between records and items.
settings      : simple key/value store (font size, last backup time ...).
"""
import datetime as _dt
import os
import re
import sqlite3
from typing import Iterable, List, Optional

from app.config import DEFAULT_ITEMS

SCHEMA_VERSION = 1
SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_TABLES = {"items", "records", "record_items", "settings"}


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


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active     INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS records (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            plate      TEXT NOT NULL,
            plate_key  TEXT NOT NULL,
            amount     INTEGER NOT NULL DEFAULT 0,
            mileage    INTEGER,
            note       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_records_date ON records(date);
        CREATE INDEX IF NOT EXISTS idx_records_plate_key ON records(plate_key);
        CREATE TABLE IF NOT EXISTS record_items (
            record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            item_id   INTEGER NOT NULL REFERENCES items(id),
            PRIMARY KEY (record_id, item_id)
        );
        """
    )
    row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),)
        )
    seeded = conn.execute("SELECT value FROM settings WHERE key='items_seeded'").fetchone()
    if seeded is None:
        for i, name in enumerate(DEFAULT_ITEMS):
            conn.execute(
                "INSERT OR IGNORE INTO items(name, sort_order, active) VALUES(?, ?, 1)", (name, i)
            )
        conn.execute("INSERT INTO settings(key, value) VALUES('items_seeded', '1')")
    conn.commit()


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        _create_schema(self.conn)

    def close(self) -> None:
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
        if row is not None:
            if row["active"]:
                raise DataError(f"「{name}」已經存在了。")
            self.conn.execute(
                "UPDATE items SET active=1, sort_order=? WHERE id=?", (next_order, row["id"])
            )
            self.conn.commit()
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO items(name, sort_order, active) VALUES(?, ?, 1)", (name, next_order)
        )
        self.conn.commit()
        return cur.lastrowid

    def rename_item(self, item_id: int, new_name: str) -> None:
        new_name = (new_name or "").strip()
        if not new_name:
            raise DataError("項目名稱不能空白。")
        row = self.conn.execute(
            "SELECT id FROM items WHERE name=? AND id<>?", (new_name, item_id)
        ).fetchone()
        if row is not None:
            raise DataError(f"「{new_name}」已經存在了。")
        self.conn.execute("UPDATE items SET name=? WHERE id=?", (new_name, item_id))
        self.conn.commit()

    def hide_item(self, item_id: int) -> None:
        self.conn.execute("UPDATE items SET active=0 WHERE id=?", (item_id,))
        self.conn.commit()

    def move_item(self, item_id: int, delta: int) -> None:
        """Move an active item up (delta=-1) or down (delta=+1)."""
        items = self.list_items()
        ids = [it["id"] for it in items]
        if item_id not in ids:
            return
        i = ids.index(item_id)
        j = i + delta
        if j < 0 or j >= len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        for order, iid in enumerate(ids):
            self.conn.execute("UPDATE items SET sort_order=? WHERE id=?", (order, iid))
        self.conn.commit()

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
            amount = int(amount)
        except (TypeError, ValueError):
            raise DataError("請輸入金額。")
        if amount < 0:
            raise DataError("金額不能是負數。")
        return plate, amount

    def _set_record_items(self, record_id: int, item_ids: Iterable[int]) -> None:
        self.conn.execute("DELETE FROM record_items WHERE record_id=?", (record_id,))
        for iid in set(item_ids):
            self.conn.execute(
                "INSERT INTO record_items(record_id, item_id) VALUES(?, ?)", (record_id, iid)
            )

    def add_record(self, date: str, plate: str, amount, item_ids: Iterable[int] = (),
                   mileage: Optional[int] = None, note: str = "") -> int:
        plate, amount = self._validate(date, plate, amount)
        now = _now()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO records(date, plate, plate_key, amount, mileage, note, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (date, plate, plate_key(plate), amount, mileage, (note or "").strip(), now, now),
            )
            self._set_record_items(cur.lastrowid, item_ids)
        return cur.lastrowid

    def update_record(self, record_id: int, date: str, plate: str, amount,
                      item_ids: Iterable[int] = (), mileage: Optional[int] = None,
                      note: str = "") -> None:
        plate, amount = self._validate(date, plate, amount)
        with self.conn:
            self.conn.execute(
                "UPDATE records SET date=?, plate=?, plate_key=?, amount=?, mileage=?, note=?, "
                "updated_at=? WHERE id=?",
                (date, plate, plate_key(plate), amount, mileage, (note or "").strip(), _now(),
                 record_id),
            )
            self._set_record_items(record_id, item_ids)

    def delete_record(self, record_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM records WHERE id=?", (record_id,))

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
        rows = self.conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchall()
        recs = self._attach_items(rows)
        return recs[0] if recs else None

    def search_records(self, plate: str = "", date_from: Optional[str] = None,
                       date_to: Optional[str] = None) -> List[dict]:
        sql = "SELECT * FROM records WHERE 1=1"
        args: list = []
        key = plate_key(plate)
        if key:
            sql += " AND plate_key LIKE ?"
            args.append(f"%{key}%")
        if date_from:
            sql += " AND date >= ?"
            args.append(date_from)
        if date_to:
            sql += " AND date <= ?"
            args.append(date_to)
        sql += " ORDER BY date DESC, id DESC"
        return self._attach_items(self.conn.execute(sql, args).fetchall())

    def last_record_for_plate(self, plate: str, exclude_id: Optional[int] = None) -> Optional[dict]:
        key = plate_key(plate)
        if not key:
            return None
        sql = "SELECT * FROM records WHERE plate_key=?"
        args: list = [key]
        if exclude_id is not None:
            sql += " AND id<>?"
            args.append(exclude_id)
        sql += " ORDER BY date DESC, id DESC LIMIT 1"
        recs = self._attach_items(self.conn.execute(sql, args).fetchall())
        return recs[0] if recs else None

    def count_records(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    # ------------------------------------------------------------ backup/restore
    def backup_to(self, dest_path: str) -> None:
        """Write a consistent copy of the whole database to dest_path."""
        tmp = dest_path + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        dest = sqlite3.connect(tmp)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        os.replace(tmp, dest_path)

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
            conn = sqlite3.connect(path)
            try:
                tables = {
                    r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if not REQUIRED_TABLES.issubset(tables):
                    raise DataError("這個檔案不是本程式的備份檔。")
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DataError("備份檔已損壞，無法還原。")
                return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            raise DataError("備份檔已損壞，無法還原。")

    def restore_from(self, src_path: str) -> None:
        """Replace all current data with the contents of a backup file."""
        self.check_backup_file(src_path)
        src = sqlite3.connect(src_path)
        try:
            src.backup(self.conn)
        finally:
            src.close()
        self.conn.execute("PRAGMA foreign_keys = ON")
        _create_schema(self.conn)
