# Performance (must not lag on old PCs with years of data)

## Budgets (measured with `tools/bench.py --records 90000`, ~10 years of a busy shop)

Target on a modern dev machine — leave ~5× headroom for old shop PCs:

| Action | Budget | Last measured |
| --- | --- | --- |
| Open any page | < 100 ms | 查詢紀錄 53 ms, others < 40 ms |
| Typing a plate (history, debounced) | < 100 ms | 24 ms |
| Customer card while typing (entry) | < 30 ms | 9 ms |
| Save a record incl. UI update | < 20 ms | 3 ms |
| Year report (UI) | < 100 ms | ~33 ms |
| App startup | < 1 s | ~0.36 s |
| DB size for 90k visits | — | 11 MB |

History: v1 schema + per-cell table fill = 10.6 s to open 查詢紀錄 (2026-11-20).

Update "Last measured" in the retro whenever you re-run the bench.

## Rules

1. **Never load an unbounded result set into a widget.** Tables page with
   `limit/offset` (`HistoryPage.PAGE_SIZE = 200`, 「顯示更多」 button). Totals and
   counts come from SQL aggregates (`db.search_stats`), not from Python sums
   over loaded rows.
2. **Fill tables with `fill_table()`.** It pauses `ResizeToContents` columns;
   filling cell by cell made Qt re-measure whole columns per cell (O(n²)) —
   that was the 10.6 s history page.
3. **Debounce typing** (`QTimer` single-shot, 250–300 ms) before querying.
4. **Lazy refresh.** Pages refresh in `show_page`; do not re-query hidden pages
   on `data_changed`.
5. Heavy one-off work (PDF of thousands of rows) asks first
   (`PDF_WARN_ROWS`) and shows a wait cursor.
6. Indexes are covering by design: `records(date, vehicle_id, amount)` and
   `records(vehicle_id, date, amount)`. Partial plate search
   (`plate_key LIKE '%x%'`) scans only the small `vehicles` table, then seeks
   `idx_records_vehicle`. Check new queries with `EXPLAIN QUERY PLAN`.
7. `_attach_items` batches item lookups in chunks of 500 ids — keep it that way;
   never query items per record in a loop.
