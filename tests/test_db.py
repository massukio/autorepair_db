import os
import sqlite3

import pytest

from app import backup, config
from app.config import DEFAULT_ITEMS
from app.db import Database, DataError, normalize_plate, plate_key


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "t.db"))
    yield d
    d.close()


def ids_by_name(db):
    return {it["name"]: it["id"] for it in db.list_items()}


def test_default_items_seeded_once(tmp_path):
    p = str(tmp_path / "a.db")
    d = Database(p)
    assert [i["name"] for i in d.list_items()] == DEFAULT_ITEMS
    d.hide_item(d.list_items()[0]["id"])
    d.close()
    d = Database(p)  # reopening must not re-add the hidden default item
    assert len(d.list_items()) == len(DEFAULT_ITEMS) - 1
    d.close()


def test_plate_normalization():
    assert normalize_plate(" abc-1234 ") == "ABC-1234"
    assert normalize_plate("ab c--12") == "ABC-12"
    assert normalize_plate("車abc") == "ABC"
    assert plate_key("ABC-1234") == "ABC1234"


def test_add_search_record(db):
    ids = ids_by_name(db)
    rid = db.add_record("2026-11-20", "abc-1234", "1500", [ids["機油"], ids["機油濾芯"]],
                        mileage=52000, note="下次 5000 公里")
    rec = db.get_record(rid)
    assert rec["plate"] == "ABC-1234"
    assert rec["amount"] == 1500
    assert rec["item_names"] == ["機油", "機油濾芯"]
    # searching without dash / partial / lowercase works
    assert [r["id"] for r in db.search_records("abc1234")] == [rid]
    assert [r["id"] for r in db.search_records("1234")] == [rid]
    assert db.search_records("XYZ") == []
    assert db.search_records(date_from="2026-11-21") == []
    assert len(db.search_records(date_from="2026-11-01", date_to="2026-11-30")) == 1


def test_validation(db):
    with pytest.raises(DataError):
        db.add_record("2026-11-20", "", 100)
    with pytest.raises(DataError):
        db.add_record("2026-11-20", "ABC", "")
    with pytest.raises(DataError):
        db.add_record("bad", "ABC", 100)
    with pytest.raises(DataError):
        db.add_record("2026-11-20", "ABC", -5)


def test_update_delete(db):
    ids = ids_by_name(db)
    rid = db.add_record("2026-11-20", "ABC-1234", 1000, [ids["機油"]])
    db.update_record(rid, "2026-11-19", "XYZ-9", 2000, [ids["電瓶"]])
    rec = db.get_record(rid)
    assert (rec["date"], rec["plate"], rec["amount"], rec["item_names"]) == (
        "2026-11-19", "XYZ-9", 2000, ["電瓶"])
    db.delete_record(rid)
    assert db.get_record(rid) is None
    assert db.conn.execute("SELECT COUNT(*) FROM record_items").fetchone()[0] == 0


def test_last_record_for_plate(db):
    a = db.add_record("2026-01-01", "ABC-1234", 100)
    b = db.add_record("2026-06-01", "ABC1234", 200)
    assert db.last_record_for_plate("abc-1234")["id"] == b
    assert db.last_record_for_plate("ABC1234", exclude_id=b)["id"] == a
    assert db.last_record_for_plate("") is None


def test_items_crud(db):
    nid = db.add_item("雨刷")
    assert db.list_items()[-1]["name"] == "雨刷"
    with pytest.raises(DataError):
        db.add_item("雨刷")
    with pytest.raises(DataError):
        db.add_item("  ")
    db.rename_item(nid, "雨刷片")
    with pytest.raises(DataError):
        db.rename_item(nid, "機油")
    db.move_item(nid, -1)
    assert db.list_items()[-2]["name"] == "雨刷片"
    # hidden item still shows on old records
    rid = db.add_record("2026-11-20", "A1", 1, [nid])
    db.hide_item(nid)
    assert "雨刷片" not in [i["name"] for i in db.list_items()]
    assert db.get_record(rid)["item_names"] == ["雨刷片"]
    # re-adding a hidden item un-hides it
    assert db.add_item("雨刷片") == nid


def test_backup_and_restore(db, tmp_path):
    ids = ids_by_name(db)
    db.add_record("2026-11-20", "ABC-1234", 1500, [ids["機油"]])
    bpath = str(tmp_path / "備份 檔案.db")  # Chinese + space in path
    db.backup_to(bpath)
    assert Database.check_backup_file(bpath) == 1

    db.add_record("2026-11-21", "NEW-1", 10)
    db.add_item("新項目")
    db.restore_from(bpath)
    assert db.count_records() == 1
    assert "新項目" not in [i["name"] for i in db.list_items()]
    assert db.search_records()[0]["item_names"] == ["機油"]
    # still writable after restore
    db.add_record("2026-11-22", "AFTER-1", 5)
    assert db.count_records() == 2


def test_restore_rejects_bad_files(db, tmp_path):
    txt = tmp_path / "x.db"
    txt.write_text("hello")
    with pytest.raises(DataError):
        db.restore_from(str(txt))
    other = tmp_path / "other.db"
    c = sqlite3.connect(str(other))
    c.execute("CREATE TABLE foo(x)")
    c.commit()
    c.close()
    with pytest.raises(DataError):
        db.restore_from(str(other))
    with pytest.raises(DataError):
        db.restore_from(str(tmp_path / "missing.db"))


def test_auto_backup(db, tmp_path):
    folder = str(tmp_path / "auto")
    for i in range(5):
        open(os.path.join(folder if os.path.isdir(folder) else (os.makedirs(folder) or folder),
                          f"自動備份_2000010{i}.db"), "w").close()
    p = backup.daily_auto_backup(db, folder, keep=3)
    assert os.path.exists(p)
    files = sorted(os.listdir(folder))
    assert len(files) == 3 and files[-1] == os.path.basename(p)
    # second call same day does not duplicate
    backup.daily_auto_backup(db, folder, keep=3)
    assert len(os.listdir(folder)) == 3
    s = backup.safety_backup_before_restore(db, folder)
    assert Database.check_backup_file(s) == 0


def test_plate_summary(db):
    assert db.plate_summary("ABC-1234") is None
    db.add_record("2026-01-01", "ABC-1234", 1000)
    db.add_record("2026-03-02", "abc1234", 2000)
    db.add_record("2026-05-01", "ABC-1234", 500)
    db.add_record("2026-05-01", "OTHER-1", 999)
    s = db.plate_summary("abc1234")
    assert (s["visits"], s["total"], s["first_date"], s["last_date"]) == (3, 3500, "2026-01-01", "2026-05-01")
    assert s["avg_interval_days"] == 60  # 120 days / 2 gaps
    single = db.plate_summary("OTHER-1")
    assert single["visits"] == 1 and single["avg_interval_days"] is None


def test_report(db):
    ids = ids_by_name(db)
    db.add_record("2026-11-02", "A-1", 1000, [ids["機油"], ids["機油濾芯"]])
    db.add_record("2026-11-02", "B-2", 500, [ids["機油"]])
    db.add_record("2026-11-20", "A1", 300, [ids["電瓶"]])
    db.add_record("2026-12-01", "C-3", 9999, [ids["機油"]])
    r = db.report("2026-11-01", "2026-11-30", "day")
    assert (r["visits"], r["total"], r["cars"]) == (3, 1800, 2)
    assert [(b["period"], b["visits"], b["total"]) for b in r["buckets"]] == [
        ("2026-11-02", 2, 1500), ("2026-11-20", 1, 300)]
    assert r["items"][0] == {"name": "機油", "times": 2}
    assert r["customers"][0]["visits"] == 2 and r["customers"][0]["total"] == 1300
    y = db.report("2026-01-01", "2026-12-31", "month")
    assert [(b["period"], b["visits"]) for b in y["buckets"]] == [("2026-11", 3), ("2026-12", 1)]
    empty = db.report("2025-01-01", "2025-12-31")
    assert (empty["visits"], empty["total"], empty["buckets"]) == (0, 0, [])


def test_search_paging_and_stats(db):
    for i in range(25):
        db.add_record(f"2026-01-{i + 1:02d}", "ABC-1234" if i % 2 else "XYZ-9", 100 + i)
    page1 = db.search_records(limit=10)
    page2 = db.search_records(limit=10, offset=10)
    assert len(page1) == 10 and len(page2) == 10
    assert page1[0]["date"] == "2026-01-25" and page2[0]["date"] == "2026-01-15"
    assert not {r["id"] for r in page1} & {r["id"] for r in page2}
    st = db.search_stats()
    assert (st["count"], st["total"], st["cars"]) == (25, sum(100 + i for i in range(25)), 2)
    one = db.search_stats("abc1234")
    assert (one["count"], one["cars"], one["plate"]) == (12, 1, "ABC-1234")
    assert db.search_stats("nothing")["count"] == 0


V1_SCHEMA = """
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, plate TEXT NOT NULL,
                      plate_key TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, mileage INTEGER,
                      note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX idx_records_date ON records(date);
CREATE INDEX idx_records_plate_key ON records(plate_key);
CREATE TABLE record_items (record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                           item_id INTEGER NOT NULL REFERENCES items(id), PRIMARY KEY (record_id, item_id));
INSERT INTO settings VALUES ('schema_version', '1'), ('items_seeded', '1'), ('font_size', '大');
INSERT INTO items VALUES (1, '機油', 0, 1), (2, '電瓶', 1, 1), (3, '舊項目', 2, 0);
INSERT INTO records VALUES
  (1, '2026-01-05', 'ABC1234', 'ABC1234', 1500, 40000, '', '2026-01-05 10:00:00', '2026-01-05 10:00:00'),
  (2, '2026-03-05', 'ABC-1234', 'ABC1234', 1800, 45000, '下次換電瓶', '2026-03-05 10:00:00', '2026-03-05 10:00:00'),
  (3, '2026-03-06', 'XYZ-9', 'XYZ9', 3000, NULL, '', '2026-03-06 10:00:00', '2026-03-06 10:00:00');
INSERT INTO record_items VALUES (1, 1), (2, 1), (2, 3), (3, 2);
"""


def make_v1(path):
    c = sqlite3.connect(path)
    c.executescript(V1_SCHEMA)
    c.commit()
    c.close()


def test_migrates_v1_database(tmp_path):
    p = str(tmp_path / "v1.db")
    make_v1(p)
    db = Database(p)
    assert db.get_setting("schema_version") == "2"
    assert db.get_setting("font_size") == "大"
    assert db.count_records() == 3
    cols = {r[1] for r in db.conn.execute("PRAGMA table_info(records)")}
    assert "vehicle_id" in cols and "plate_key" not in cols
    # both spellings became one car, displayed with the dash
    assert db.conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 2
    s = db.plate_summary("abc1234")
    assert (s["plate"], s["visits"], s["total"]) == ("ABC-1234", 2, 3300)
    rec = db.get_record(2)
    assert rec["item_names"] == ["機油", "舊項目"] and rec["note"] == "下次換電瓶"
    assert rec["created_at"] > 1700000000
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # the migrated database keeps working
    db.add_record("2026-04-01", "XYZ9", 100, [2])
    assert db.plate_summary("XYZ-9")["visits"] == 2
    db.close()
    Database(p).close()  # reopening is a no-op


def test_restore_old_v1_backup(db, tmp_path):
    old = str(tmp_path / "old_backup.db")
    make_v1(old)
    assert Database.check_backup_file(old) == 3
    db.add_record("2026-11-01", "NEW-1", 1)
    db.restore_from(old)
    assert db.count_records() == 3
    assert db.plate_summary("ABC-1234")["visits"] == 2


def test_vehicle_cleanup_and_plate_change(db):
    rid = db.add_record("2026-01-01", "AAA-111", 100)
    db.update_record(rid, "2026-01-01", "BBB-222", 100)
    plates = [r[0] for r in db.conn.execute("SELECT plate FROM vehicles")]
    assert plates == ["BBB-222"]
    db.delete_record(rid)
    assert db.conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 0


def test_review_fixes(db, tmp_path):
    # amount with thousands separator
    rid = db.add_record("2026-01-01", "AAA-1", "1,500")
    assert db.get_record(rid)["amount"] == 1500
    with pytest.raises(DataError):
        db.add_record("2026-01-01", "AAA-1", "12a")
    # updating a deleted record gives a friendly error
    db.delete_record(rid)
    with pytest.raises(DataError):
        db.update_record(rid, "2026-01-01", "AAA-1", 1)
    # backup onto / restore from the live file is refused
    with pytest.raises(DataError):
        db.backup_to(db.path)
    with pytest.raises(DataError):
        db.restore_from(db.path)
    # renaming onto a deleted item's name moves the hidden one aside
    ids = ids_by_name(db)
    db.hide_item(ids["燈泡"])
    db.rename_item(ids["電瓶"], "燈泡")
    names = {i["name"]: i["active"] for i in db.list_items(include_hidden=True)}
    assert names["燈泡"] == 1 and names["燈泡（舊1）"] == 0
    # backup into an unwritable location -> DataError, no .tmp left behind
    bad = str(tmp_path / "missing_dir" / "x.db")
    with pytest.raises(DataError):
        db.backup_to(bad)


def test_backup_is_compact_and_valid(db, tmp_path):
    for i in range(300):
        db.add_record("2026-01-01", f"CAR-{i}", i, [1], None, "x" * 200)
    for r in db.search_records()[:250]:
        db.delete_record(r["id"])
    out = str(tmp_path / "b.db")
    db.backup_to(out)
    assert Database.check_backup_file(out) == 50
    assert os.path.getsize(out) < os.path.getsize(db.path)


def test_chinese_names_and_legacy_rename(tmp_path, monkeypatch):
    # an install that still has the early English names
    old = tmp_path / "autorepair_data"
    (old / "auto_backup").mkdir(parents=True)
    make_v1(str(old / "autorepair.db"))
    (old / "autorepair.db-journal").write_bytes(b"")  # journal must travel with the db
    (old / "error.log").write_text("old log")
    (old / "app.lock").write_text("x")
    (old / "auto_backup" / "auto_20261101.db").write_bytes(b"x")
    (old / "auto_backup" / "before_restore_20261101_101010.db").write_bytes(b"x")
    monkeypatch.delenv("AUTOREPAIR_DATA_DIR", raising=False)
    monkeypatch.setattr(config, "app_dir", lambda: str(tmp_path))

    assert config.data_dir() == str(tmp_path / "汽車保養資料")
    new = tmp_path / "汽車保養資料"
    assert not old.exists()
    assert config.db_path() == str(new / "保養資料.db")
    assert (new / "保養資料.db").exists() and (new / "保養資料.db-journal").exists()
    assert (new / "錯誤紀錄.log").read_text() == "old log"
    assert not (new / "app.lock").exists()
    assert sorted(os.listdir(new / "自動備份")) == ["自動備份_20261101.db", "還原前備份_20261101_101010.db"]
    os.remove(new / "保養資料.db-journal")  # empty test journal; let sqlite open normally
    d = Database(config.db_path())
    assert d.count_records() == 3
    p = backup.daily_auto_backup(d, config.auto_backup_dir())
    assert os.path.basename(p).startswith("自動備份_")
    d.close()


def test_fresh_install_uses_chinese_names(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOREPAIR_DATA_DIR", raising=False)
    monkeypatch.setattr(config, "app_dir", lambda: str(tmp_path))
    assert config.db_path() == str(tmp_path / "汽車保養資料" / "保養資料.db")
    assert config.auto_backup_dir() == str(tmp_path / "汽車保養資料" / "自動備份")


def test_uri_path_handles_network_paths():
    from app.db import _uri_path
    assert _uri_path("//NAS/share/x.db").startswith("////NAS/share/")  # file:////NAS/... (no URI authority)
    assert not _uri_path("/tmp/a b.db").startswith("//")


def test_rotation_with_glob_chars_in_folder(db, tmp_path):
    folder = tmp_path / "[修車] 資料"  # [ ] are glob patterns and valid on Windows
    folder.mkdir()
    for i in range(5):
        (folder / f"{config.AUTO_BACKUP_PREFIX}2025010{i}.db").write_bytes(b"")
    backup.daily_auto_backup(db, str(folder), keep=3)
    assert len(os.listdir(folder)) == 3
