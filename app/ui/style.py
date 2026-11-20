"""Global stylesheet + UI scaling.

Everything is sized from one base font size (pt). The main window recomputes
that size whenever it is resized, so the UI fits any screen / window size.
Fixed pixel sizes set in code go through ``sized()`` so they scale too.
"""
import weakref

from app import config

GREEN = "#2e7d32"
GREEN_DARK = "#1b5e20"
BLUE = "#1565c0"
BLUE_DARK = "#0d47a1"
RED = "#c62828"
BG = "#f4f1ea"


_scale = 1.0
_registry = []  # (weakref to widget, method name, reference values)


def scale() -> float:
    return _scale


def px(n: float) -> int:
    return max(1, round(n * _scale))


def sized(widget, method: str, *values):
    """Call e.g. widget.setMinimumWidth(px(280)) now and again whenever the scale changes."""
    _registry.append((weakref.ref(widget), method, values))
    getattr(widget, method)(*(px(v) for v in values))
    return widget


def set_scale(new_scale: float) -> None:
    global _scale
    _scale = new_scale
    alive = []
    for ref, method, values in _registry:
        w = ref()
        if w is None:
            continue
        try:
            getattr(w, method)(*(px(v) for v in values))
        except RuntimeError:  # C++ object already deleted
            continue
        alive.append((ref, method, values))
    _registry[:] = alive


def base_font_for(width: int, height: int, factor: float) -> int:
    fit = min(width / config.REF_WIDTH, height / config.REF_HEIGHT) ** config.SCALE_EXPONENT
    base = round(config.REF_FONT_PT * fit * factor)
    return max(config.MIN_FONT_PT, min(config.MAX_FONT_PT, base))


def build_stylesheet(base: int) -> str:
    k = base / config.REF_FONT_PT

    def p(n):  # scale a pixel value with the font
        return max(1, round(n * k))

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
        background: #fff8e1; border: {p(2)}px solid #f9a825; border-radius: {p(10)}px;
        padding: {p(8)}px {p(12)}px; font-size: {base}pt;
    }}
    QLabel[role="total"] {{ font-size: {base + 2}pt; font-weight: bold; color: {GREEN_DARK}; }}

    QPushButton {{
        background: white; border: {p(2)}px solid #8a8a8a; border-radius: {p(10)}px;
        padding: {p(10)}px {p(18)}px;
    }}
    QPushButton:hover {{ background: #e8f0fe; border-color: {BLUE}; }}
    QPushButton:pressed {{ background: #c5d8f8; }}
    QPushButton:disabled {{ color: #aaa; border-color: #ccc; background: #f0f0f0; }}

    QPushButton[role="primary"] {{
        background: {GREEN}; color: white; border-color: {GREEN_DARK};
        font-weight: bold; font-size: {base + 4}pt; padding: {p(14)}px {p(30)}px;
    }}
    QPushButton[role="primary"]:hover {{ background: #388e3c; }}
    QPushButton[role="danger"] {{ background: {RED}; color: white; border-color: #8e0000; font-weight: bold; }}
    QPushButton[role="danger"]:hover {{ background: #d32f2f; }}

    QPushButton[role="nav"] {{
        background: #e0e0e0; border: {p(2)}px solid #9e9e9e; border-radius: {p(12)}px;
        font-size: {base + 4}pt; font-weight: bold; padding: {p(12)}px {p(22)}px;
    }}
    QPushButton[role="nav"]:checked {{ background: {BLUE}; color: white; border-color: {BLUE_DARK}; }}

    QPushButton[role="item"] {{
        font-size: {base + 2}pt; padding: {p(18)}px {p(8)}px; border-radius: {p(12)}px;
    }}
    QPushButton[role="item"]:checked {{
        background: {GREEN}; color: white; border: {p(2)}px solid {GREEN_DARK}; font-weight: bold;
    }}
    QPushButton[role="additem"] {{
        font-size: {base + 2}pt; border: {p(2)}px dashed {BLUE}; color: {BLUE}; background: #f5f9ff;
        border-radius: {p(12)}px; padding: {p(18)}px {p(8)}px;
    }}
    QPushButton[role="date"] {{ font-size: {big}pt; font-weight: bold; background: white; }}

    QLineEdit {{
        background: white; border: {p(2)}px solid #8a8a8a; border-radius: {p(8)}px;
        padding: {p(8)}px {p(10)}px; font-size: {big}pt;
    }}
    QLineEdit:focus {{ border: {p(3)}px solid {BLUE}; }}
    QLineEdit[role="small"] {{ font-size: {base + 2}pt; }}

    QTableWidget {{
        background: white; gridline-color: #d0d0d0; font-size: {base}pt;
        selection-background-color: #bbdefb; selection-color: black;
        alternate-background-color: #f7f7f7;
    }}
    QHeaderView::section {{
        background: #e3e3e3; padding: {p(6)}px; border: {p(1)}px solid #c8c8c8;
        font-weight: bold; font-size: {base}pt;
    }}
    QListWidget {{ background: white; font-size: {base + 2}pt; border: {p(2)}px solid #8a8a8a; border-radius: {p(8)}px; }}
    QListWidget::item {{ padding: {p(10)}px; }}
    QListWidget::item:selected {{ background: #bbdefb; color: black; }}

    QCalendarWidget QWidget {{ font-size: {base + 2}pt; }}
    QCalendarWidget QToolButton {{ font-size: {base + 2}pt; color: black; padding: {p(6)}px; }}
    QCalendarWidget QAbstractItemView {{ selection-background-color: {BLUE}; selection-color: white; }}

    QFrame[role="card"] {{
        background: white; border: {p(2)}px solid #c8c8c8; border-radius: {p(12)}px;
    }}
    QLabel[role="cardvalue"] {{ font-size: {base + 8}pt; font-weight: bold; color: {GREEN_DARK}; border: none; }}
    QFrame[role="card"] QLabel {{ border: none; }}
    QMenu {{ font-size: {base + 2}pt; background: white; border: {p(1)}px solid #888; }}
    QMenu::item {{ padding: {p(10)}px {p(24)}px; }}
    QMenu::item:selected {{ background: #bbdefb; color: black; }}
    QMessageBox QLabel {{ font-size: {base + 2}pt; }}
    QMessageBox QPushButton {{ min-width: {p(120)}px; }}
    QScrollBar:vertical {{ width: {p(22)}px; }}
    """
