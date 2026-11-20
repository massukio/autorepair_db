"""Entry point: python start.py  (or double-click the built exe)."""
import datetime
import os
import sys
import traceback

from PyQt5 import QtCore, QtGui, QtWidgets

from app import backup, config
from app.db import Database


def _log_path() -> str:
    try:
        return os.path.join(config.data_dir(), config.LOG_FILENAME)
    except OSError:
        return os.path.join(os.path.expanduser("~"), "autorepair_error.log")


def _excepthook(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
    except OSError:
        pass
    app = QtWidgets.QApplication.instance()
    if app is not None:
        QtWidgets.QMessageBox.critical(
            None, "發生錯誤",
            f"程式發生錯誤，請把以下檔案給維護人員：\n{_log_path()}\n\n{exc}")


def main() -> int:
    sys.excepthook = _excepthook
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    icon_path = config.resource_path("assets", "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))

    # Chinese labels on the built-in Qt dialogs (file dialog / calendar)
    QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Chinese, QtCore.QLocale.Taiwan))
    translator = QtCore.QTranslator(app)
    if translator.load("qtbase_zh_TW", QtCore.QLibraryInfo.location(
            QtCore.QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)

    try:
        db = Database(config.db_path())
    except Exception as e:  # noqa: BLE001 - show any startup problem to the user
        QtWidgets.QMessageBox.critical(None, "無法開啟資料", f"無法開啟資料檔：\n{config.db_path()}\n\n{e}")
        return 1
    try:
        backup.daily_auto_backup(db, config.auto_backup_dir())
    except Exception as e:  # noqa: BLE001 - auto backup must never block startup
        _excepthook(type(e), e, e.__traceback__)

    from app.ui.main_window import MainWindow
    win = MainWindow(db)
    win.showMaximized()
    rc = app.exec_()
    db.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
