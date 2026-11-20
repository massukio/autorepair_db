import os
import sqlite3

import pytest

from app import backup
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
                          f"auto_2000010{i}.db"), "w").close()
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
