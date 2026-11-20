# 汽車保養紀錄 (autorepair_db)

給汽車保養廠使用的離線記帳小程式。專為不熟悉電腦的長輩設計：大字、大按鈕、全中文、步驟少。
A small offline Windows app for an auto-repair shop to record each customer visit.

- 不需要安裝、不需要網路、不需要伺服器 — 一個 `汽車保養紀錄.exe` 點兩下就能用
- 紀錄：**日期、車牌、金額、保養項目**（可另外填公里數、備註）
- 保養項目可隨時新增 / 改名 / 排序 / 刪除（刪除不影響舊紀錄）
- 輸入車牌時自動顯示「這台車上次來」的日期、金額、項目
- 查詢：用車牌（可只打一部分、不用打 `-`）或日期查詢，顯示筆數與合計；可修改、刪除、匯出 Excel (CSV)
- 備份：一鍵把全部資料存成一個檔案（可存到隨身碟或雲端硬碟）；換電腦時一鍵還原
- 每天開啟時自動備份一份到 `autorepair_data\auto_backup\`（保留 30 天）；還原前也會自動先備份目前資料

## 使用方式（給店家）

1. 把 `汽車保養紀錄.exe` 放到一個資料夾裡（例如桌面上的「保養紀錄」資料夾），點兩下開啟。
2. 第一次開啟會在 exe 旁邊建立 `autorepair_data` 資料夾，**所有資料都在這裡**。
   搬家時把整個資料夾（exe + `autorepair_data`）一起複製即可。
3. 換新電腦：把 exe 複製到新電腦 → 開啟 →「備份 / 還原」→「從備份檔還原」→ 選擇之前的備份檔。

> 若 exe 放在沒有寫入權限的位置（例如 `C:\Program Files`），資料會改存到 `%LOCALAPPDATA%\AutoRepairDB\autorepair_data`。
> 「備份 / 還原」頁面會顯示目前資料實際存放的位置。

## 開發 (Development)

Python 3.12 + PyQt5 + SQLite（Python 內建），PyInstaller 打包成單一 exe。

```bat
python -m pip install -r requirements.txt
python start.py               :: run from source
python -m pytest -q tests     :: data-layer tests
build_exe.bat                 :: tests + icon + build -> dist\汽車保養紀錄.exe
```

Set `AUTOREPAIR_DATA_DIR` to use a different data folder (handy for testing).
`tools/screenshot.py` renders every page to PNG (works with `QT_QPA_PLATFORM=offscreen`).

### Project layout

| Path | What |
| --- | --- |
| `start.py` | entry point: Qt setup, error log, open DB, daily auto backup |
| `app/config.py` | constants, default items, data-folder location logic |
| `app/db.py` | SQLite schema + all data operations, backup / restore |
| `app/backup.py` | daily auto backup and before-restore safety copies |
| `app/ui/main_window.py` | top navigation + page stack, font size |
| `app/ui/pages.py` | 新增紀錄 / 查詢紀錄 / 備份還原 / 設定 pages, edit dialog |
| `app/ui/record_form.py` | shared entry form (date / plate / amount / items ...) |
| `app/ui/widgets.py` | big buttons, Chinese message boxes, date picker, item grid |
| `app/ui/style.py` | one stylesheet scaled from the chosen font size |

### Data model

`records` (date, plate, amount, mileage, note) ↔ `record_items` ↔ `items` (name, order, active).
Items are soft-deleted (`active=0`) so old records keep their names. Plates are stored upper-case;
`plate_key` (plate without `-`) is used for matching so `ABC1234` finds `ABC-1234`.
A backup file is simply a consistent copy of the SQLite database made with SQLite's backup API.
