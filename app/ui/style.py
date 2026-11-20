"""Global stylesheet. Everything is sized from one base font size so the
user can switch 小/中/大/特大 in 設定 and the whole app follows."""

GREEN = "#2e7d32"
GREEN_DARK = "#1b5e20"
BLUE = "#1565c0"
BLUE_DARK = "#0d47a1"
RED = "#c62828"
BG = "#f4f1ea"


def build_stylesheet(base: int) -> str:
    big = base + 6
    title = base + 8
    small = max(base - 3, 11)
    return f"""
    QWidget {{
        font-family: "Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC", sans-serif;
        font-size: {base}pt;
        color: #1f1f1f;
    }}
    QMainWindow, QDialog, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
    QToolTip {{ font-size: {base}pt; }}

    QLabel[role="title"] {{ font-size: {title}pt; font-weight: bold; color: {BLUE_DARK}; }}
    QLabel[role="field"] {{ font-weight: bold; font-size: {base + 2}pt; }}
    QLabel[role="hint"] {{ color: #555; font-size: {small}pt; }}
    QLabel[role="info"] {{
        background: #fff8e1; border: 2px solid #f9a825; border-radius: 10px;
        padding: 8px 12px; font-size: {base}pt;
    }}
    QLabel[role="total"] {{ font-size: {base + 2}pt; font-weight: bold; color: {GREEN_DARK}; }}

    QPushButton {{
        background: white; border: 2px solid #8a8a8a; border-radius: 10px;
        padding: 10px 18px;
    }}
    QPushButton:hover {{ background: #e8f0fe; border-color: {BLUE}; }}
    QPushButton:pressed {{ background: #c5d8f8; }}
    QPushButton:disabled {{ color: #aaa; border-color: #ccc; background: #f0f0f0; }}

    QPushButton[role="primary"] {{
        background: {GREEN}; color: white; border-color: {GREEN_DARK};
        font-weight: bold; font-size: {base + 4}pt; padding: 14px 30px;
    }}
    QPushButton[role="primary"]:hover {{ background: #388e3c; }}
    QPushButton[role="danger"] {{ background: {RED}; color: white; border-color: #8e0000; font-weight: bold; }}
    QPushButton[role="danger"]:hover {{ background: #d32f2f; }}

    QPushButton[role="nav"] {{
        background: #e0e0e0; border: 2px solid #9e9e9e; border-radius: 12px;
        font-size: {base + 4}pt; font-weight: bold; padding: 12px 22px;
    }}
    QPushButton[role="nav"]:checked {{ background: {BLUE}; color: white; border-color: {BLUE_DARK}; }}

    QPushButton[role="item"] {{
        font-size: {base + 2}pt; padding: 18px 8px; border-radius: 12px;
    }}
    QPushButton[role="item"]:checked {{
        background: {GREEN}; color: white; border: 2px solid {GREEN_DARK}; font-weight: bold;
    }}
    QPushButton[role="additem"] {{
        font-size: {base + 2}pt; border: 2px dashed {BLUE}; color: {BLUE}; background: #f5f9ff;
        border-radius: 12px; padding: 18px 8px;
    }}
    QPushButton[role="date"] {{ font-size: {big}pt; font-weight: bold; background: white; }}

    QLineEdit {{
        background: white; border: 2px solid #8a8a8a; border-radius: 8px;
        padding: 8px 10px; font-size: {big}pt;
    }}
    QLineEdit:focus {{ border: 3px solid {BLUE}; }}
    QLineEdit[role="small"] {{ font-size: {base + 2}pt; }}

    QTableWidget {{
        background: white; gridline-color: #d0d0d0; font-size: {base}pt;
        selection-background-color: #bbdefb; selection-color: black;
        alternate-background-color: #f7f7f7;
    }}
    QHeaderView::section {{
        background: #e3e3e3; padding: 6px; border: 1px solid #c8c8c8;
        font-weight: bold; font-size: {base}pt;
    }}
    QListWidget {{ background: white; font-size: {base + 2}pt; border: 2px solid #8a8a8a; border-radius: 8px; }}
    QListWidget::item {{ padding: 10px; }}
    QListWidget::item:selected {{ background: #bbdefb; color: black; }}

    QCalendarWidget QWidget {{ font-size: {base + 2}pt; }}
    QCalendarWidget QToolButton {{ font-size: {base + 2}pt; color: black; padding: 6px; }}
    QCalendarWidget QAbstractItemView {{ selection-background-color: {BLUE}; selection-color: white; }}

    QMessageBox QLabel {{ font-size: {base + 2}pt; }}
    QMessageBox QPushButton {{ min-width: 120px; }}
    QScrollBar:vertical {{ width: 22px; }}
    """
