# Experience log (append new entries at the bottom)

Entry format:
```
## YYYY-MM-DD — short title
- What happened:
- Cause:
- Rule / fix: (and "promoted to <file>" if it became a rule elsewhere)
```

## 2026-11-20 — Table fill was O(n²): history page took 10.6 s on 90k rows
- What happened: opening 查詢紀錄 with ~10 years of data froze for seconds.
- Cause: loading every record, and `setItem` per cell with `ResizeToContents`
  columns makes Qt re-measure the whole column after each cell.
- Rule / fix: page results (200 at a time), SQL aggregates for totals,
  `fill_table()` pauses column auto-size. Promoted to `workflows/performance.md`.

## 2026-11-20 — Offscreen screenshot run "hung"
- What happened: `tools/screenshot.py` never finished; CPU near idle.
- Cause: a modal `QMessageBox` (「沒有資料可以存成 PDF」) opened offscreen, because
  the script searched a plate that did not exist in the dataset.
- Rule / fix: low CPU + no progress = modal dialog; use faulthandler to find it.
  The script now picks the most frequent plate. Promoted to `workflows/develop.md`.

## 2026-11-20 — Dialog taller than the screen hid its save button
- What happened: the edit dialog on a small VM screen extended below the
  taskbar; content looked "cut even after scrolling".
- Cause: dialog resized to a fixed size, buttons inside the scroll area.
- Rule / fix: `fit_to_screen()` for every dialog; pin action buttons outside the
  scroll area. Promoted to `reference/design-system.md`.

## 2026-11-20 — Word-wrapped labels overlapped or got clipped
- What happened: the customer summary label was cut off / overlapped other widgets.
- Cause: QLabel with word wrap does not reserve height-for-width in nested
  layouts; when the page is too short, layouts compress below minimum.
- Rule / fix: `WrapLabel` (sets its own minimum height); put pages in scroll
  areas so they scroll instead of overlapping; prefer structured widgets
  (tiles, key/value rows) over long wrapped text.

## 2026-11-20 — Stylesheet `min-height` on buttons caused overlapping rows
- Cause: QSS min-height is not reflected in the layout size hint.
- Rule / fix: size buttons with padding, not `min-height`.

## 2026-11-20 — Mac renders look bigger than Windows
- What happened: fonts that looked right in macOS offscreen renders were too
  small on Windows (Microsoft JhengHei draws smaller).
- Rule / fix: calibrate sizes on the Windows exe (reference 19 pt @ 1280×760).

## 2026-11-20 — Emoji in labels
- Rule: avoid emoji (📅 etc.) — Qt5 on Windows renders them as boxes or mono
  glyphs. Use ◀ ▶ ✓ ‹ › which exist in Windows fonts.

## 2026-11-20 — `.bat` file broke cmd.exe
- Cause: LF line endings + UTF-8 Chinese text in `build_exe.bat`.
- Rule / fix: CRLF + ASCII only; `.gitattributes` enforces CRLF. Promoted to
  `workflows/build-release.md`.

## 2026-11-20 — Windows VM automation quirks
- GUI apps started over SSH are invisible (session 0) → use `schtasks /IT`.
- `CopyFromScreen` returns a stale frame on the VM → use `PrintWindow`.
- Paths with Chinese in `schtasks /TR` get mangled → launch via a UTF-16LE
  PowerShell script.
- A dropped `scp` silently leaves old source; always check timestamps.
- Explorer caches the exe icon per path; rebuilt exe may show the old icon.
- All promoted to `workflows/build-release.md`.

## 2026-11-20 — Unparented QLabel popped up as its own window
- Cause: a label created by a form but only added to a layout on one page;
  `show()` on an unparented widget makes it a top-level window.
- Rule: every widget that can be shown must be placed in a layout by its owner.

## 2026-11-20 — Owner feedback patterns
- The owner tests on a small VM window: always check small sizes (≈1000×560).
- The owner values: zero clipping, elegant visuals, discoverable editing
  (they could not find item editing when it lived only in 設定), PDF over Excel.

## 2026-11-20 — Schema redesign before first release (v1 → v2)
- What happened: owner asked for a deep look at SQL performance/storage.
- Cause: v1 stored plate text on every visit; plate search scanned all visits.
- Rule / fix: `vehicles` table + covering indexes + WITHOUT ROWID links +
  integer timestamps + VACUUM INTO backups. 19 → 11 MB, plate search 110 → 23 ms.
  Do structural schema changes BEFORE a release when possible. Promoted to
  `reference/architecture.md`, `workflows/data-changes.md`.

## 2026-11-20 — `executescript` silently commits
- Cause: Python's `sqlite3` `executescript()` COMMITs any pending transaction
  before running, so `conn.execute("BEGIN")` + `executescript(...)` is NOT atomic.
- Rule / fix: put `BEGIN;` inside the script and COMMIT after checks. Promoted
  to `workflows/data-changes.md`.

## 2026-11-20 — Independent code review found real bugs
- Found by a reviewer agent (all fixed, tests added):
  editing a record dropped items that had been deleted from the item list;
  sqlite errors during backup/restore (USB pulled, disk full) were not caught
  (they are `sqlite3.Error`, not `OSError`); backup onto / restore from the live
  DB file was not refused; zh_TW `QIntValidator` accepts "1,500" then `int()`
  crashed; PDF overwrite of a file open in a viewer failed silently and showed
  the stale PDF; entry date/report period went stale overnight; two app copies
  could run at once; renaming onto a hidden item's name gave a confusing error;
  `Segmented.set_current("")` could not clear an exclusive group; font size not
  re-applied after restore; updating a deleted record raised IntegrityError.
- Rule: after any sizeable change, run an independent review focused on data
  safety and crash paths (not style); verify each finding before fixing.

## 2026-11-20 — Renaming user data files safely
- Rule: when a data file is renamed (e.g. to Chinese names), rename in place —
  never copy+delete; move a SQLite database together with its `-journal`; if the
  rename fails, keep using the old name instead of creating a new empty
  database; cover it with a test that builds the old layout. Promoted to
  `reference/architecture.md`.

## 2026-11-20 — State the user cannot see (owner: "I click the table but see nothing selected")
- Cause: the stylesheet styled `QTableWidget::item` (padding, border) but had no
  `::item:selected` rule, so Qt drew only a faint tint. Related, found by review:
  styled buttons draw no focus ring; QDialog buttons are `autoDefault`, so Enter
  "clicked" whatever had focus (a brand chip, the VIP toggle, 取消); confirmation
  boxes defaulted to the destructive button (確定刪除 / 確定還原).
- Rules (promoted to design-system.md): every interactive state needs an explicit,
  strong style — `::item:selected` (solid accent + white bold), `:hover`,
  `QPushButton:focus` amber ring (placed last in the stylesheet so it wins);
  `button()` sets `setAutoDefault(False)`; message boxes default to the SAFE
  choice; dialogs set an explicit default/focus (e.g. 客戶資訊 → 關閉).

## 2026-11-20 — PyQt5 aborts on exceptions inside Qt callbacks
- What happened: test run ended with "Fatal Python error: Aborted".
- Cause: an exception in a slot/event handler with no `sys.excepthook` → PyQt5 calls
  qFatal. (The app's `start.py` installs a hook that logs to 錯誤紀錄.log.)
- Rule: tests install a hook that records such exceptions and fails the test
  (`tests/conftest.py`); stop timers before closing the database in fixtures.
