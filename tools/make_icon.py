"""Generate assets/app.ico (run once before building)."""
import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.ico")


def main():
    app = QtWidgets.QApplication(sys.argv)  # noqa: F841 - needed for fonts
    size = 256
    img = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    img.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setBrush(QtGui.QColor("#1565c0"))
    p.setPen(QtCore.Qt.NoPen)
    p.drawRoundedRect(8, 8, size - 16, size - 16, 48, 48)
    font = QtGui.QFont("Microsoft JhengHei")
    font.setBold(True)
    font.setPixelSize(150)
    p.setFont(font)
    p.setPen(QtGui.QColor("white"))
    p.drawText(QtCore.QRect(0, 0, size, size), QtCore.Qt.AlignCenter, "保")
    p.end()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    w = QtGui.QImageWriter(OUT, b"ico")
    if not w.write(img):
        raise SystemExit("icon write failed: " + w.errorString())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
