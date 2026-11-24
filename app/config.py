"""Application constants and data-location logic.

Data lives in a 「汽車保養資料」 folder next to the exe so the whole folder
(exe + data) can be copied anywhere. If that folder is not writable (e.g. the
exe was put under Program Files) we fall back to %LOCALAPPDATA%.

Every folder / file the program creates by itself has a Chinese name (owner
decision). Installs that still use the early English names are renamed in
place on start-up (see ``_migrate_legacy_names``); nothing is copied or deleted.
"""
import os
import sys

APP_NAME = "汽車保養資料庫"
APP_VERSION = "1.0.2"
APP_AUTHOR = "Sukio Lin"
APP_CREATED_YEAR = 2026
APP_RELEASE_DATE = "2026-11-24"
APP_LICENSE = "MIT License"
APP_LICENSE_URL = "https://opensource.org/licenses/MIT"

DATA_DIRNAME = "汽車保養資料"            # next to the exe
DB_FILENAME = "保養資料.db"
AUTO_BACKUP_DIRNAME = "自動備份"
AUTO_BACKUP_PREFIX = "自動備份_"          # 自動備份_20261120.db
BEFORE_RESTORE_PREFIX = "還原前備份_"     # 還原前備份_20261120_235959.db
LOG_FILENAME = "錯誤紀錄.log"
LOCK_FILENAME = "使用中.lock"
FALLBACK_DIRNAME = "汽車保養資料庫"       # under %LOCALAPPDATA%
AUTO_BACKUP_KEEP = 30

# English names used before the Chinese naming; migrated automatically.
LEGACY_DATA_DIRNAME = "autorepair_data"
LEGACY_DB_FILENAME = "autorepair.db"
LEGACY_AUTO_BACKUP_DIRNAME = "auto_backup"
LEGACY_LOG_FILENAME = "error.log"
LEGACY_LOCK_FILENAME = "app.lock"
LEGACY_FALLBACK_DIRNAME = "AutoRepairDB"
LEGACY_BACKUP_PREFIXES = {"auto_": AUTO_BACKUP_PREFIX, "before_restore_": BEFORE_RESTORE_PREFIX}

DEFAULT_ITEMS = [
    "機油", "機油濾芯", "空氣濾芯", "冷氣濾芯", "變速箱油",
    "煞車油", "電瓶", "水箱精", "燈泡",
]

# The UI scales with the window size: at REF_WIDTH x REF_HEIGHT the base font
# is REF_FONT_PT. The user's 小/中/大/特大 choice multiplies that.
# Calibrated on Windows (Microsoft JhengHei). Shrinking is softened by
# SCALE_EXPONENT because every page can scroll when space runs out.
REF_WIDTH, REF_HEIGHT, REF_FONT_PT = 1280, 760, 19
SCALE_EXPONENT = 0.7
MIN_FONT_PT, MAX_FONT_PT = 12, 34
FONT_SCALES = {"小": 0.85, "中": 1.0, "大": 1.15, "特大": 1.3}
DEFAULT_FONT_SIZE = "中"


def resource_path(*parts: str) -> str:
    """Path of a bundled file (works from source and from the PyInstaller exe)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _rename(old: str, new: str) -> bool:
    """Rename old -> new if old exists and new does not. True if new is now in place."""
    if not os.path.exists(old):
        return os.path.exists(new)
    if os.path.exists(new):
        return True
    try:
        os.rename(old, new)
        return True
    except OSError:
        return False


def _data_dir_in(parent: str) -> str:
    """The data folder under parent, renaming the old English folder if needed."""
    new = os.path.join(parent, DATA_DIRNAME)
    old = os.path.join(parent, LEGACY_DATA_DIRNAME)
    if os.path.isdir(old) and not os.path.exists(new) and not _rename(old, new):
        return old  # could not rename (in use?) - keep using the old folder, never lose data
    return new


def _migrate_legacy_names(folder: str) -> None:
    """Rename English-named files inside the data folder to their Chinese names."""
    # the database and its rollback journal must move together (a leftover
    # journal after a crash is needed to recover the database)
    old_db = os.path.join(folder, LEGACY_DB_FILENAME)
    new_db = os.path.join(folder, DB_FILENAME)
    if os.path.exists(old_db) and not os.path.exists(new_db):
        old_j, new_j = old_db + "-journal", new_db + "-journal"
        if _rename(old_db, new_db) and os.path.exists(old_j):
            if not _rename(old_j, new_j):
                _rename(new_db, old_db)  # keep the pair together
    _rename(os.path.join(folder, LEGACY_LOG_FILENAME), os.path.join(folder, LOG_FILENAME))
    try:
        os.remove(os.path.join(folder, LEGACY_LOCK_FILENAME))
    except OSError:
        pass
    old_bk = os.path.join(folder, LEGACY_AUTO_BACKUP_DIRNAME)
    new_bk = os.path.join(folder, AUTO_BACKUP_DIRNAME)
    if os.path.isdir(old_bk) and not os.path.exists(new_bk):
        _rename(old_bk, new_bk)
    if os.path.isdir(new_bk):
        for name in os.listdir(new_bk):
            for old_prefix, new_prefix in LEGACY_BACKUP_PREFIXES.items():
                if name.startswith(old_prefix) and name.endswith(".db"):
                    _rename(os.path.join(new_bk, name),
                            os.path.join(new_bk, new_prefix + name[len(old_prefix):]))


def data_dir() -> str:
    override = os.environ.get("AUTOREPAIR_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        _migrate_legacy_names(override)
        return override
    preferred = _data_dir_in(app_dir())
    if _is_writable(preferred):
        _migrate_legacy_names(preferred)
        return preferred
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    new_base = os.path.join(base, FALLBACK_DIRNAME)
    old_base = os.path.join(base, LEGACY_FALLBACK_DIRNAME)
    if os.path.isdir(old_base) and not os.path.exists(new_base) and not _rename(old_base, new_base):
        new_base = old_base
    fallback = _data_dir_in(new_base)
    os.makedirs(fallback, exist_ok=True)
    _migrate_legacy_names(fallback)
    return fallback


def db_path() -> str:
    folder = data_dir()
    new = os.path.join(folder, DB_FILENAME)
    old = os.path.join(folder, LEGACY_DB_FILENAME)
    if not os.path.exists(new) and os.path.exists(old):
        return old  # rename failed (file in use); keep using the existing data
    return new


def auto_backup_dir() -> str:
    path = os.path.join(data_dir(), AUTO_BACKUP_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path
