# Add or change a feature

1. Restate the request in terms of the elderly user's workflow (who clicks what,
   in which page). If the request conflicts with `knowledge/decisions.md`, ask.
2. Find the code via `reference/architecture.md`. Reuse existing widgets
   (`Card`, `Tile`, `Segmented`, `RecordForm`, `CustomerCard`, flows in
   `items.py`) before writing new ones.
3. Data first: add queries/columns in `app/db.py` following
   `workflows/data-changes.md`, with pytest coverage in `tests/test_db.py`.
4. UI: follow `reference/design-system.md`. Text in Traditional Chinese.
   Lists/tables follow `workflows/performance.md` (paging, `fill_table`,
   debounced typing).
5. Wire cross-page navigation through `MainWindow` signals (pattern:
   `open_history(plate)`), not by pages reaching into each other.
6. Verify: tests → screenshots at several sizes → `tools/bench.py` if data or
   tables were touched → build and run on Windows.
7. Update README.md (features list) when user-visible behaviour changes.
8. Retro (`workflows/retro.md`).
