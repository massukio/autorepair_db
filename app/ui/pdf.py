"""Save simple HTML reports as A4 PDF files (Chinese fonts are embedded)."""
import datetime as _dt
import html
import os
from typing import Iterable, List, Optional, Sequence

from PyQt5 import QtCore, QtGui, QtPrintSupport, QtWidgets

from app.ui.widgets import ask, warn

FONT = "Microsoft JhengHei"


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def table_html(headers: Sequence[str], rows: Iterable[Sequence], right: Sequence[int] = ()) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for i, row in enumerate(rows):
        bg = ' bgcolor="#f3f3f3"' if i % 2 else ""
        cells = "".join(
            f'<td align="{"right" if c in right else "left"}">{esc(v)}</td>' for c, v in enumerate(row))
        body.append(f"<tr{bg}>{cells}</tr>")
    if not body:
        body.append(f'<tr><td colspan="{len(headers)}" align="center">（沒有資料）</td></tr>')
    return ('<table width="100%" border="1" cellspacing="0" cellpadding="5" '
            'style="border-collapse:collapse; border-color:#999;">'
            f'<thead><tr bgcolor="#dde6f3">{head}</tr></thead>{"".join(body)}</table>')


def document_html(title: str, lines: List[str], sections: List[str]) -> str:
    now = _dt.datetime.now().strftime("%Y/%m/%d %H:%M")
    info = "".join(f"<p style='margin:2px 0'>{esc(x)}</p>" for x in lines)
    return f"""<html><body style="font-family:'{FONT}'; font-size:10.5pt;">
    <h2 style="margin:0 0 4px 0; color:#0d47a1;">{esc(title)}</h2>
    <p style="color:#666; margin:0 0 8px 0;">列印時間：{now}</p>
    {info}
    {''.join(sections)}
    </body></html>"""


def render_pdf(html_text: str, path: str) -> None:
    printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
    printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    printer.setPageMargins(12, 12, 12, 12, QtPrintSupport.QPrinter.Millimeter)
    doc = QtGui.QTextDocument()
    doc.setDefaultFont(QtGui.QFont(FONT, 10))
    doc.setHtml(html_text)
    doc.setPageSize(printer.pageRect(QtPrintSupport.QPrinter.Point).size())
    doc.print_(printer)


def save_pdf(parent, default_name: str, html_text: str, start_dir: Optional[str] = None) -> None:
    """Ask where to save, write the PDF, then offer to open it."""
    start_dir = start_dir or QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "存成 PDF", os.path.join(start_dir, default_name), "PDF 檔 (*.pdf)")
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    tmp = path + ".tmp.pdf"
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
        render_pdf(html_text, tmp)  # QPrinter fails silently, so check the result
        if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            raise OSError("PDF 沒有寫出來")
        os.replace(tmp, path)
    except PermissionError:
        warn(parent, "存檔失敗：同名的 PDF 可能正開著。\n\n請先關閉那個 PDF，或換一個檔名再試一次。")
        return
    except Exception as e:  # noqa: BLE001 - show any failure to the user
        warn(parent, f"存檔失敗：{e}\n\n請換一個位置再試一次。")
        return
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
    if ask(parent, f"已存成 PDF：\n{path}\n\n要現在打開來看嗎？（可以從那裡列印）", "完成",
           yes="打開來看", no="不用"):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
