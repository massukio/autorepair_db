# Fix a bug

1. Reproduce first. Data bugs: write a failing test in `tests/test_db.py`.
   UI bugs: reproduce with `tools/screenshot.py` or a small offscreen script that
   drives the widget (see how `tools/bench.py` types into fields).
2. Check `錯誤紀錄.log` in the user's `汽車保養資料` folder if they sent it —
   `start.py` logs every unhandled exception there with a timestamp.
3. Fix the root cause, not the symptom. Search for the same pattern elsewhere
   (e.g. a missing `sized()`, a cell-by-cell table fill, an unparented label
   that shows as a stray window).
4. If the bug could have touched user data, think about existing databases in
   the field: does the fix need a migration or a repair step at startup?
5. Verify (tests, screenshots, Windows exe), then retro — every bug is a lesson
   for `knowledge/lessons.md`.
