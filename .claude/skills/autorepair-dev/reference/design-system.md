# Design system (elder-first, calm, clean)

Goal set by the owner: easy for elderly users who are not familiar with
computers, **and** visually high quality — "clear, nice and elegant". Plain or
cramped UI was explicitly rejected once; do not regress.

## Principles

1. One obvious main action per screen (green `primary` button, e.g. 儲存紀錄).
2. Big text and big click targets; nothing important smaller than the base size.
3. Say what to do next in plain Traditional Chinese (「先點一下表格中的一行，再按『修改』」).
4. Confirm destructive actions with explicit verbs on buttons (確定刪除 / 不要刪除),
   never just 是/否 for deletes.
5. Never clip content. If space runs out, the area scrolls; buttons that finish
   a task (save/cancel) are pinned outside the scroll area.
6. Dialogs use `fit_to_screen()` so they never exceed the screen.
7. Prefer structure over text blobs: tiles, key/value rows, cards — not long
   wrapped sentences (the old wrapped customer summary was called "ugly").

## Palette (`app/ui/style.py`)

| Token | Use |
| --- | --- |
| `BG #F3F1EC` | window background (warm paper) |
| `SURFACE #FFFFFF` | cards |
| `SURFACE_ALT #F8F6F2` | tiles, table header |
| `BORDER #E3DED5` / `BORDER_STRONG #BDB6AA` | card borders / inputs, buttons |
| `TEXT #1F2328` / `MUTED #6A6F78` | text / secondary text |
| `PRIMARY #1F5F8B` (+ `_DARK`, `_SOFT`) | navigation, links, focus, selection |
| `SUCCESS #2F7D50` | selected item chips and the save button only |
| `DANGER #B3261E` | delete (outlined, not filled) |
| `AMBER #9A6412` / `AMBER_SOFT` | badges (常客), info boxes |

Do not introduce new colors casually; add a token if truly needed.

## Components (`app/ui/widgets.py`) and roles

- `Card(title)` — white rounded panel; `add()`, `add_header_widget()` for
  header-right actions (e.g. 存成 PDF, 清除條件). Use for every page section.
- `Tile(caption)` — stat tile (caption + big value).
- `Segmented([(key, text)])` — pill switch for modes/ranges (每週/每月/每年,
  font size, quick date ranges).
- `button(text, role)` roles: default (secondary), `primary`, `danger`, `link`
  (quiet text action), `item` (checkable chip), `nav` (header tab), `seg`, `date`.
- `label(text, role)` roles: `cardtitle`, `field`, `muted`/`hint`, `tilecap`,
  `tileval`, `plate`, `total`, `badge`, `badgenew`, `rowkey`, `rowval`, `info`,
  `empty`. Wrapping roles use `WrapLabel` (reserves its full height).
- `ItemGrid` — responsive chip grid (column count from width); right-click menu.
- `DatePicker` (◀ date ▶ 今天), `OptionalDateButton` (不限 allowed).
- Messages: `info`, `warn`, `ask(yes=..., no=...)`, `ask_text`.
- Tables: `make_table` + `fill_table` (never fill cell-by-cell in a loop
  without it — see performance).

## Sizing

- Never hard-code pixel sizes; use `sized(widget, method, *px_at_reference)`.
- Base font is automatic from window size; 小/中/大/特大 multiply it.
- Text sizes are relative to `base` in the stylesheet (`base + 3` titles, etc.).
- Windows renders Microsoft JhengHei smaller than macOS PingFang: judge sizes
  on Windows, not on Mac offscreen renders.

## Checklist for any UI change

- Render `tools/screenshot.py` at 1070×540, 1280×760, 1920×1040 (and 800×480
  for robustness) and look at every changed screen.
- No horizontal clipping, no overlap, primary action visible without scrolling.
- Empty states have a friendly sentence (e.g. 「輸入車牌後，這裡會顯示…」).
- Then verify on the real Windows exe (`workflows/build-release.md`).

## Visible state (mandatory)

- Selected table row: solid accent background, white bold text (`::item:selected`);
  hover tint on rows. Anything the user must click first (a row) needs a visible
  confirmation of what is selected (carwash: 「目前選擇」 box).
- Keyboard focus: amber ring on every focusable button; inputs show an accent border.
- No hidden Enter behaviour: `button()` turns off autoDefault; dialogs that want
  Enter to save handle it in `keyPressEvent`; message boxes default to the safe button.
- Test it: `tests/test_ui.py` style tests click, press Enter/ESC and assert the
  visible state, not only the data.

## 使用說明 (in-app manual) — keep it true

- Header right: 「？ 使用說明」 (`role="help"`, amber pill) and F1 open `app/ui/manual.py`
  at the chapter of the current page (`MainWindow.MANUAL_ANCHORS` ↔ `<a name>` in
  `assets/manual/manual.html`). The header hides the program name (icon stays)
  when it has no room (`_fit_header`), so no tab or the help button is ever cut off.
- Any change to a screen, a button text or a flow: update the chapter in
  `manual.html` and regenerate the pictures with `tools/make_manual.py` ON WINDOWS
  (`workflows/build-release.md`), then look at every picture. `test_manual_is_complete`
  checks pictures/links/anchors, not wording — re-read the text yourself.
- Writing style (owner request): spoken Taiwanese Mandarin for an elderly shop
  owner, 「您」, short sentences, steps ①②③ matching the orange numbers in the
  pictures, 小提醒 / 注意 boxes, a 常見問題 chapter, 「回到目錄」 after every chapter.
  No machine-translation tone, no English, no emoji (Qt on Windows shows boxes).
