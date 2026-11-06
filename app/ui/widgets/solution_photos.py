"""해결 방법 사진 편집(여러 장): 추가 / 붙여넣기 / 순서 변경 / 삭제 + 열람용 갤러리(화살표로 넘김)."""
from typing import List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QListView, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from ... import config, storage
from .image_widgets import ZoomView, clipboard_image, read_image

THUMB = QSize(120, 84)


def _thumb(img: QImage) -> QIcon:
    return QIcon(QPixmap.fromImage(img.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)))


class SolutionPhotoEditor(QFrame):
    """등록/수정 창에서 해결 방법 사진을 여러 장 관리."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        head = QLabel("解决方法图片（可添加多张）")
        head.setObjectName("Section")
        lay.addWidget(head)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(False)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(THUMB)
        self.list.setSpacing(6)
        self.list.setFixedHeight(THUMB.height() + 58)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.keyPressEvent = self._list_key
        lay.addWidget(self.list)

        row = QHBoxLayout()
        b_add = QPushButton("添加图片…")
        b_add.clicked.connect(self.add_files)
        b_paste = QPushButton("粘贴图片")
        b_paste.clicked.connect(self.paste)
        b_left = QPushButton("◀")
        b_left.setToolTip("前移")
        b_left.clicked.connect(lambda: self._move(-1))
        b_right = QPushButton("▶")
        b_right.setToolTip("后移")
        b_right.clicked.connect(lambda: self._move(1))
        b_del = QPushButton("移除所选")
        b_del.clicked.connect(self._remove)
        for b in (b_add, b_paste, b_left, b_right):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_del)
        lay.addLayout(row)

    # ---- 데이터 ----
    def set_existing(self, rels: List[str]):
        self.list.clear()
        for rel in rels:
            img = storage.load_qimage(rel)
            if not img.isNull():
                self._append({"rel": rel, "img": None, "src": ""}, img)

    def items(self) -> List[dict]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def _append(self, data: dict, thumb_src: QImage):
        it = QListWidgetItem(_thumb(thumb_src), "")
        it.setData(Qt.UserRole, data)
        it.setSizeHint(QSize(THUMB.width() + 14, THUMB.height() + 38))
        self.list.addItem(it)
        self._renumber()
        self.list.setCurrentItem(it)
        self.list.scrollToItem(it)

    def _renumber(self):
        n = self.list.count()
        for i in range(n):
            self.list.item(i).setText(f"{i + 1} / {n}")

    def add_image(self, img: QImage, src: str = ""):
        self._append({"rel": None, "img": img, "src": src}, img)

    # ---- 동작 ----
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片（可多选）", "", config.IMAGE_FILTER)
        for p in paths:
            img = read_image(p)
            if not img.isNull():
                self.add_image(img, p)

    def paste(self):
        img, path = clipboard_image()
        if img is not None:
            self.add_image(img, path or "")

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)
            self._renumber()

    def _move(self, d):
        row = self.list.currentRow()
        new = row + d
        if row < 0 or not (0 <= new < self.list.count()):
            return
        it = self.list.takeItem(row)
        self.list.insertItem(new, it)
        self.list.setCurrentRow(new)
        self._renumber()

    def _list_key(self, ev):
        if ev.matches(QKeySequence.Paste):
            self.paste()
        elif ev.key() == Qt.Key_Delete:
            self._remove()
        else:
            QListWidget.keyPressEvent(self.list, ev)


class SolutionGallery(QWidget):
    """열람용: 큰 사진 1장 + ◀ ▶ 화살표 + '2 / 5'. 휠 확대, 키보드 ←/→ 지원."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rels: List[str] = []
        self._idx = 0
        self.setFocusPolicy(Qt.StrongFocus)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.view = ZoomView()
        self.view.setMinimumHeight(160)
        lay.addWidget(self.view, 1)
        nav = QHBoxLayout()
        nav.addStretch(1)
        self.prev = QPushButton("◀")
        self.next = QPushButton("▶")
        for b in (self.prev, self.next):
            b.setMinimumWidth(64)
        self.counter = QLabel("")
        self.counter.setObjectName("Section")
        self.counter.setAlignment(Qt.AlignCenter)
        self.counter.setMinimumWidth(80)
        self.prev.clicked.connect(lambda: self.go(self._idx - 1))
        self.next.clicked.connect(lambda: self.go(self._idx + 1))
        nav.addWidget(self.prev)
        nav.addWidget(self.counter)
        nav.addWidget(self.next)
        nav.addStretch(1)
        lay.addLayout(nav)

    def set_images(self, rels: List[str]):
        self._rels = list(rels)
        self.go(0)

    def go(self, idx: int):
        n = len(self._rels)
        if n == 0:
            self.view.set_image(None)
            self.counter.setText("")
            return
        self._idx = max(0, min(idx, n - 1))
        self.view.set_image(storage.load_qimage(self._rels[self._idx]))
        self.counter.setText(f"{self._idx + 1} / {n}")
        self.prev.setEnabled(self._idx > 0)
        self.next.setEnabled(self._idx < n - 1)
        self.prev.setVisible(n > 1)
        self.next.setVisible(n > 1)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.go(self._idx - 1)
        elif ev.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.go(self._idx + 1)
        else:
            super().keyPressEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.view.fit()
