# Owner decisions (do not re-litigate; ask before changing)

Format: `YYYY-MM-DD — decision — why / context`

- 2026-11-20 — Offline, single portable Windows exe; no server, no network, no
  installer required. — Shop has no IT support; the exe must run anywhere.
- 2026-11-20 — Main inputs are 日期 / 車牌 / 金額 + selectable 項目; 公里數 and 備註
  are optional extras. — Owner's spec; mileage helps oil-change follow-up.
- 2026-11-20 — Default items: 機油, 機油濾芯, 空氣濾芯, 冷氣濾芯, 變速箱油, 煞車油,
  電瓶, 水箱精, 燈泡 (濾芯 spelling normalized). Items are permanent and fully
  editable (add / rename / delete / reorder) from the entry page and 設定.
- 2026-11-20 — All UI in Traditional Chinese, designed for elderly users, but it
  must also look clean and elegant ("plain/ugly" was rejected).
- 2026-11-20 — Font and layout auto-scale with the window size; 小/中/大/特大
  only adjust on top.
- 2026-11-20 — Export is **PDF**, not Excel/CSV ("Excel is useless for elders").
- 2026-11-20 — Backup = one file the user saves anywhere (USB / cloud folder);
  restore replaces all data after confirmation and a safety copy.
- 2026-11-20 — Reports: weekly / monthly / yearly; customer frequency (visits,
  average interval, last visit details) when a plate is entered.
- 2026-11-20 — Report page shows 回到本週/本月/今年 only when viewing another period.
- 2026-11-20 — App name 汽車保養資料庫 (window title, header, exe name).
- 2026-11-20 — Version 1.0.0 for the first release; author Sukio Lin; created
  2026; MIT License; shown in 設定 → 關於本程式 (mirrors the earlier carwash app
  massukio/new_again_db).
- 2026-11-20 — Icon: white wrench + clipboard on a steel-blue rounded square
  (owner generated it; source in `assets/icon_source.jpg`).
- 2026-11-20 — Must not lag on old PCs even with many years of data.
- 2026-11-20 — Code lives at github.com/massukio/autorepair_db (public).
- 2026-11-20 — Every folder/file the program creates uses a Chinese name
  (汽車保養資料/保養資料.db/自動備份/錯誤紀錄.log/使用中.lock; backup and PDF
  names too). Old English-named installs are renamed automatically. — Users
  are elderly Chinese readers browsing these folders in Explorer.
