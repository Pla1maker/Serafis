#!/usr/bin/env python3
"""Draw the Serafis shield icon (PNG + ICO) with Qt. Run once; outputs are committed."""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

app = QGuiApplication(sys.argv)
out = Path(__file__).resolve().parent.parent / "serafis" / "resources"
out.mkdir(parents=True, exist_ok=True)


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    path = QPainterPath()
    path.moveTo(128 * s, 12 * s)
    path.lineTo(228 * s, 50 * s)
    path.cubicTo(228 * s, 150 * s, 190 * s, 210 * s, 128 * s, 244 * s)
    path.cubicTo(66 * s, 210 * s, 28 * s, 150 * s, 28 * s, 50 * s)
    path.closeSubpath()
    g = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    g.setColorAt(0, QColor("#2f7de1"))
    g.setColorAt(1, QColor("#0f2747"))
    p.setBrush(QBrush(g))
    p.setPen(QPen(QColor("#ffffff"), max(1.0, 6 * s)))
    p.drawPath(path)
    f = QFont("DejaVu Sans", int(120 * s))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(QRectF(0, 20 * s, size, 200 * s), Qt.AlignCenter, "S")
    p.end()
    return img


draw(256).save(str(out / "serafis.png"))
ok = draw(256).save(str(out / "serafis.ico"))
print("ico written:", ok)
