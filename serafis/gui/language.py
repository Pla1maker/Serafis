from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..localization.i18n import FLAGS, LANGUAGES
from .widgets import label


class LanguageScreen(QWidget):
    """First screen: bilingual, so it is readable before a choice is made."""
    chosen = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Content")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(18)
        t = label("SERAFIS", "PageTitle", wrap=False)
        t.setStyleSheet("font-size:34pt; letter-spacing:6px;")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        s = label("Ransomware Recovery Companion", "PageIntro", wrap=False)
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(s)
        q = label("Scegli la lingua  ·  Choose your language", "CardTitle", wrap=False)
        q.setAlignment(Qt.AlignCenter)
        lay.addWidget(q)
        h = QHBoxLayout()
        h.setSpacing(24)
        h.addStretch(1)
        self.buttons = {}
        for code in ("it", "en"):
            b = QPushButton(f"{FLAGS[code]}  {LANGUAGES[code]}")
            b.setObjectName("LangCard")
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumSize(240, 110)
            b.setAccessibleName(LANGUAGES[code])
            b.clicked.connect(lambda _=False, c=code: self.chosen.emit(c))
            self.buttons[code] = b
            h.addWidget(b)
        h.addStretch(1)
        lay.addLayout(h)
        n = label("Serafis non invia dati a nessuno · Serafis never sends your data anywhere", "Muted", wrap=False)
        n.setAlignment(Qt.AlignCenter)
        lay.addWidget(n)
