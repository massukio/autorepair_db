"""Application constants and data-location logic.

Data lives in an ``autorepair_data`` folder next to the exe so the whole
folder (exe + data) can be copied anywhere. If that folder is not writable
(e.g. the exe was put under Program Files) we fall back to %LOCALAPPDATA%.
"""
import os
import sys

APP_NAME = "汽車保養紀錄"
APP_VERSION = "1.0.0"

DB_FILENAME = "autorepair.db"
DATA_DIRNAME = "autorepair_data"
AUTO_BACKUP_DIRNAME = "auto_backup"
AUTO_BACKUP_KEEP = 30
LOG_FILENAME = "error.log"

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


def data_dir() -> str:
    override = os.environ.get("AUTOREPAIR_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    preferred = os.path.join(app_dir(), DATA_DIRNAME)
    if _is_writable(preferred):
        return preferred
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    fallback = os.path.join(base, "AutoRepairDB", DATA_DIRNAME)
    os.makedirs(fallback, exist_ok=True)
    return fallback


def db_path() -> str:
    return os.path.join(data_dir(), DB_FILENAME)


def auto_backup_dir() -> str:
    path = os.path.join(data_dir(), AUTO_BACKUP_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path
