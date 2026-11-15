"""Reusable widgets and dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..localization.i18n import tr


def label(text: str = "", obj: str | None = None, wrap: bool = True, rich: bool = False) -> QLabel:
    lb = QLabel(text)
    # Untrusted data must never be interpreted as HTML: plain text by default.
    lb.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    lb.setWordWrap(wrap)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if obj:
        lb.setObjectName(obj)
    return lb


def button(text: str, primary: bool = False, obj: str | None = None) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if primary:
        b.setObjectName("Primary")
    if obj:
        b.setObjectName(obj)
    return b


class Card(QFrame):
    def __init__(self, title: str | None = None, obj: str = "Card", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(obj)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 14)
        self.lay.setSpacing(8)
        if title:
            self.lay.addWidget(label(title, "CardTitle"))

    def add(self, w) -> QWidget:
        if isinstance(w, QWidget):
            self.lay.addWidget(w)
        else:
            self.lay.addLayout(w)
        return w


def stat_card(title: str, value: str) -> Card:
    c = Card()
    c.add(label(title, "Muted"))
    c.add(label(value, "BigNumber"))
    c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return c


class Page(QWidget):
    """Scrollable page with title, intro and a body layout."""
    step_index: int | None = None

    def __init__(self, title: str, intro: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("Content")
        scroll.setWidget(inner)
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(32, 24, 32, 24)
        self.body.setSpacing(14)
        if self.step_index is not None:
            self.body.addWidget(label(tr("nav.step_of", n=self.step_index, total=6), "StepLabel"))
        self.body.addWidget(label(title, "PageTitle"))
        if intro:
            self.body.addWidget(label(intro, "PageIntro"))

    def add(self, w) -> QWidget:
        if isinstance(w, QWidget):
            self.body.addWidget(w)
        else:
            self.body.addLayout(w)
        return w

    def finish(self) -> None:
        self.body.addStretch(1)

    def refresh(self) -> None:  # overridden
        pass


def clear_layout(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def row(*widgets, stretch: bool = True) -> QHBoxLayout:
    h = QHBoxLayout()
    for w in widgets:
        if isinstance(w, QWidget):
            h.addWidget(w)
        else:
            h.addLayout(w)
    if stretch:
        h.addStretch(1)
    return h


def confirm(parent: QWidget, title: str, text: str, danger: bool = False) -> bool:
    box = QMessageBox(QMessageBox.Warning if danger else QMessageBox.Question, title, text, parent=parent)
    box.setTextFormat(Qt.PlainText)
    yes = box.addButton(tr("common.confirm"), QMessageBox.AcceptRole)
    box.addButton(tr("common.cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(box.buttons()[-1])  # safe default: cancel
    box.exec()
    return box.clickedButton() is yes


def error(parent: QWidget, text: str, detail: str = "") -> None:
    box = QMessageBox(QMessageBox.Critical, tr("common.error"), text, parent=parent)
    box.setTextFormat(Qt.PlainText)
    if detail:
        box.setInformativeText(detail)
    box.exec()


def info(parent: QWidget, text: str) -> None:
    box = QMessageBox(QMessageBox.Information, "SERAFIS", text, parent=parent)
    box.setTextFormat(Qt.PlainText)
    box.exec()


def open_url_confirmed(parent: QWidget, url: str) -> bool:
    if not url or not url.startswith("https://"):
        return False
    if confirm(parent, tr("link.title"), tr("link.confirm", url=url)):
        return QDesktopServices.openUrl(QUrl(url))
    return False
