"""검사 PC 카드 클릭 시 열리는 상세 창: 원본 사진(확대/이동) + 해결 방법."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTextBrowser, QVBoxLayout, QWidget)

from ... import config, storage
from ..widgets.image_widgets import ZoomView
from .common import ask_password, confirm
from .entry_dialog import EntryDialog


class DetailDialog(QDialog):
    changed = Signal()

    def __init__(self, parent, db, entry: dict):
        super().__init__(parent)
        self.db = db
        self.entry = entry
        self.was_changed = False
        self.setWindowTitle("解决方法")
        if parent is not None:
            w = parent.window()
            self.resize(int(w.width() * 0.88), int(w.height() * 0.88))
        else:
            self.resize(1200, 760)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split)

        # 왼쪽: 확대 가능한 원본
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.zoom = ZoomView()
        ll.addWidget(self.zoom, 1)
        tip = QLabel("滚轮缩放 · 拖动平移 · 双击还原")
        tip.setAlignment(Qt.AlignCenter)
        ll.addWidget(tip)
        split.addWidget(left)

        # 오른쪽: 제목 + 해결 방법
        right = QFrame()
        right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 16)
        rl.setSpacing(10)
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("TcTitle")
        self.title_lbl.setWordWrap(True)
        rl.addWidget(self.title_lbl)
        sec = QLabel("解决方法")
        sec.setObjectName("Section")
        rl.addWidget(sec)
        self.solution = QTextBrowser()
        self.solution.setObjectName("Solution")
        rl.addWidget(self.solution, 1)
        row = QHBoxLayout()
        b_edit = QPushButton("编辑")
        b_edit.clicked.connect(self._edit)
        b_del = QPushButton("删除")
        b_del.setObjectName("Danger")
        b_del.clicked.connect(self._delete)
        b_close = QPushButton("关闭")
        b_close.setObjectName("Primary")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_edit)
        row.addWidget(b_del)
        row.addStretch(1)
        row.addWidget(b_close)
        rl.addLayout(row)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self._fill()

    def _fill(self):
        e = self.entry
        self.title_lbl.setText(e["title"])
        self.solution.setPlainText(e["solution"] or "（尚未填写解决方法）")
        src = e["original"] or e["image"]
        self.zoom.set_image(storage.load_qimage(src) if src else None)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.zoom.fit()

    def _edit(self):
        if not ask_password(self, self.db, "编辑需要输入密码"):
            return
        dlg = EntryDialog(self, self.db, config.CATEGORY_INSPECT, self.entry)
        if dlg.exec() == QDialog.Accepted:
            self.entry = self.db.get_entry(self.entry["id"])
            self.was_changed = True
            self._fill()
            self.changed.emit()

    def _delete(self):
        if not ask_password(self, self.db, "删除需要输入密码"):
            return
        if confirm(self, f"确定要删除“{self.entry['title']}”吗？\n删除后无法恢复。", "删除确认",
                   yes="删除", danger=True):
            storage.remove_files(self.entry["original"], self.entry["image"])
            self.db.delete_entry(self.entry["id"])
            self.was_changed = True
            self.changed.emit()
            self.accept()
