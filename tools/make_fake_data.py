"""Fill a database with about one year of realistic fake records (for testing).

Usage:
    python tools/make_fake_data.py <path-to-autorepair.db> [--days 365] [--seed 1]

A safety copy of the database is written next to it first
(<name>.before_fake_<timestamp>.db), so the fake data can be undone by
restoring that file from 「備份 / 還原」.
"""
import argparse
import datetime as dt
import os
import random
import shutil
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import Database  # noqa: E402

# item -> (min price, max price), rounded to 50
PRICES = {
    "機油": (800, 1600), "機油濾芯": (150, 350), "空氣濾芯": (300, 600),
    "冷氣濾芯": (300, 700), "變速箱油": (1500, 3000), "煞車油": (600, 1200),
    "電瓶": (2200, 4500), "水箱精": (400, 900), "燈泡": (150, 500),
}
EXTRA_ITEMS = {"雨刷": (300, 800), "輪胎": (2500, 4000)}  # added as new items
NOTES = ["下次 5000 公里換機油", "客人自備機油", "建議下次換煞車皮", "輪胎快磨平了",
         "冷氣不冷，下次檢查", "老客人打折", "電瓶有點弱", "", "", "", "", "", "", ""]
SURNAMES = list("陳林黃張李王吳劉蔡楊")


def fake_plate(rng):
    letters = "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
    digits = f"{rng.randint(0, 9999):04d}"
    style = rng.random()
    if style < 0.6:
        return f"{letters}-{digits}"
    if style < 0.85:
        return f"{digits}-{letters[:2]}"
    return f"{letters[:2]}-{digits}"


def pick_items(rng, km_since_oil):
    """A typical service: usually oil, sometimes extras."""
    chosen = []
    if rng.random() < 0.85:
        chosen += ["機油"]
        if rng.random() < 0.7:
            chosen.append("機油濾芯")
    for name, p in [("空氣濾芯", 0.25), ("冷氣濾芯", 0.2), ("變速箱油", 0.08),
                    ("煞車油", 0.08), ("電瓶", 0.06), ("水箱精", 0.1), ("燈泡", 0.08),
                    ("雨刷", 0.06), ("輪胎", 0.04)]:
        if rng.random() < p:
            chosen.append(name)
    return chosen or [rng.choice(["燈泡", "電瓶", "水箱精"])]


def price_of(rng, names):
    total = 0
    for n in names:
        lo, hi = PRICES.get(n) or EXTRA_ITEMS[n]
        total += rng.randint(lo // 50, hi // 50) * 50
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    if os.path.exists(args.db):
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = f"{os.path.splitext(args.db)[0]}.before_fake_{stamp}.db"
        shutil.copy2(args.db, safety)
        print("safety copy:", safety)

    db = Database(args.db)
    for name in EXTRA_ITEMS:
        if name not in {i["name"] for i in db.list_items(include_hidden=True)}:
            db.add_item(name)
    ids = {i["name"]: i["id"] for i in db.list_items(include_hidden=True)}

    today = dt.date.today()
    start = today - dt.timedelta(days=args.days)

    # regular customers come back every 60-150 days; occasional ones once or twice
    cars = []
    for _ in range(40):
        cars.append({"plate": fake_plate(rng), "every": rng.randint(60, 150),
                     "km": rng.randint(20, 150) * 1000, "per_day_km": rng.randint(25, 70)})
    for _ in range(160):
        cars.append({"plate": fake_plate(rng), "every": None,
                     "km": rng.randint(10, 200) * 1000, "per_day_km": rng.randint(20, 60)})

    visits = []
    for car in cars:
        if car["every"]:
            d = start + dt.timedelta(days=rng.randint(0, car["every"]))
            while d <= today:
                visits.append((d, car))
                d += dt.timedelta(days=car["every"] + rng.randint(-15, 20))
        else:
            for _ in range(rng.choice([1, 1, 1, 2])):
                visits.append((start + dt.timedelta(days=rng.randint(0, args.days)), car))

    visits.sort(key=lambda v: v[0])
    count = 0
    last_seen = {}
    for d, car in visits:
        if d.weekday() == 6:  # closed on Sundays
            d -= dt.timedelta(days=1)
        if d > today:
            continue
        prev = last_seen.get(car["plate"])
        if prev:
            car["km"] += (d - prev).days * car["per_day_km"]
        last_seen[car["plate"]] = d
        names = pick_items(rng, 0)
        note = rng.choice(NOTES)
        if rng.random() < 0.03:
            note = f"{rng.choice(SURNAMES)}先生的車"
        mileage = car["km"] if rng.random() < 0.8 else None
        db.add_record(d.isoformat(), car["plate"], price_of(rng, names),
                      [ids[n] for n in names], mileage, note)
        count += 1

    total = sum(r["amount"] for r in db.search_records(date_from=start.isoformat()))
    print(f"added {count} records from {start} to {today}; total ${total:,}")
    print("regular customer plates to try:", ", ".join(c["plate"] for c in cars[:5]))
    db.close()


if __name__ == "__main__":
    main()
