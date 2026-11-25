# 汽車保養資料庫 (autorepair_db)

給汽車保養廠使用的離線紀錄程式，專為不熟悉電腦的長輩設計：大字、大按鈕、全中文、步驟少，畫面乾淨好讀。
An offline Windows app for a small auto repair shop to record every customer visit.

- 不需要安裝、不需要網路、不需要伺服器 — 一個 `汽車保養資料庫.exe` 點兩下就能用
- 紀錄：**日期、車牌、金額、保養項目**（可另外填公里數、備註）
- 保養項目永久保存，可隨時新增 / 改名 / 排序 / 刪除（輸入畫面的「＋ 新增項目」「管理項目」、在項目上按右鍵，或到「設定」）；刪除不影響舊紀錄
- 輸入車牌時立即顯示「車輛資訊」：來過幾次、累計消費、平均多久來一次、上次保養的日期 / 金額 / 公里數 / 項目
- 查詢紀錄：用車牌（可只打一部分、不用打 `-`）或日期查詢，顯示筆數與合計；可修改、刪除、存成 PDF
- 報表統計：每週 / 每月 / 每年的營業額、台次、車輛數、每日（每月）明細、各項目次數、常來的客人，可存成 PDF
- 畫面與字體會依視窗大小自動縮放，「設定」中可再調整大小
- 備份：一鍵把全部資料存成一個檔案（可存到隨身碟或雲端硬碟）；換電腦時一鍵還原
- 每天開啟時自動備份到 `汽車保養資料\自動備份\`（保留 30 天）；還原前也會自動先備份目前資料
- 資料量大也不卡：十年、九萬筆紀錄的資料庫，每個畫面都在 0.1 秒內開好

## 使用方式（給店家）

程式右上角的「**？ 使用說明**」（或按 F1）有完整的圖文使用說明書，也可以存成 PDF 印出來。

1. 把 `汽車保養資料庫.exe` 放到一個資料夾裡（例如桌面上的「保養紀錄」資料夾），點兩下開啟。
2. 第一次開啟會在 exe 旁邊建立 `汽車保養資料` 資料夾，**所有資料都在這裡**。
   搬家時把整個資料夾（exe + `汽車保養資料`）一起複製即可。
3. 換新電腦：把 exe 複製到新電腦 → 開啟 →「備份 / 還原」→「選擇備份檔並還原」→ 選擇之前的備份檔。
4. 更新程式：只要用新的 exe 取代舊的 exe，資料會自動沿用（舊格式的資料與備份檔會自動升級）。

> 若 exe 放在沒有寫入權限的位置（例如 `C:\Program Files`），資料會改存到 `%LOCALAPPDATA%\汽車保養資料庫\汽車保養資料`。
> 「備份 / 還原」頁面會顯示目前資料實際存放的位置。程式同時只能開一個。

## 開發 (Development)

Python 3.12 + PyQt5 + SQLite（Python 內建），PyInstaller 打包成單一 exe。

```bat
python -m pip install -r requirements.txt
python start.py                            :: run from source (set AUTOREPAIR_DATA_DIR to use test data)
python -m pytest -q tests                  :: data-layer tests
build_exe.bat                              :: tests + icon + build -> dist\汽車保養資料庫.exe
```

Tools: `tools/screenshot.py` (render every page offscreen), `tools/make_fake_data.py`
(one year of realistic test data), `tools/bench.py` (large-database benchmark),
`tools/make_icon.py` (builds `app.ico` from `assets/icon_source.jpg`).

### For maintainers (human or AI)

The full maintainer guide — architecture, data model, design system, workflows
for features / bug fixes / schema changes / performance / Windows builds, owner
decisions and the experience log — lives in the project skill
[`.claude/skills/autorepair-dev/SKILL.md`](.claude/skills/autorepair-dev/SKILL.md).
Start there; it routes to everything else and ends every task with a
retrospective that keeps the guide current.

### Data model (schema v2)

`vehicles(plate_key UNIQUE, plate)` ← `records(vehicle_id, date, amount, mileage, note, …)`
↔ `record_items` (WITHOUT ROWID) ↔ `items(name, sort_order, active)`; `settings(key, value)`.
Covering indexes `records(date, vehicle_id, amount)` and `records(vehicle_id, date, amount)`
serve listings, reports and per-car statistics from the index alone. Older databases and
backup files are migrated automatically on open / restore.

## License

MIT License — Copyright (c) 2026 Sukio Lin. See [LICENSE](LICENSE).
