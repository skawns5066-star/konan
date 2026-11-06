"""검사 PC 카드 클릭 시 열리는 상세 창: 원본 사진(확대/이동) + 해결 방법."""
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTextBrowser, QVBoxLayout, QWidget)

from ... import config, storage
from ..widgets.image_widgets import ZoomView
from ..widgets.solution_photos import SolutionGallery
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

        # 왼쪽: 문제가 생긴 화면 (원본, 확대/이동)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        cap = QLabel("问题画面")
        cap.setObjectName("Section")
        ll.addWidget(cap)
        self.zoom = ZoomView()
        ll.addWidget(self.zoom, 1)
        tip = QLabel("滚轮缩放 · 拖动平移 · 双击还原")
        tip.setAlignment(Qt.AlignCenter)
        ll.addWidget(tip)
        split.addWidget(left)

        # 오른쪽: 제목 + 해결 방법(텍스트 + 사진 여러 장, 화살표로 넘김)
        right = QFrame()
        right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 18, 18, 16)
        rl.setSpacing(10)
        self.banner = QLabel()
        self.banner.setObjectName("AlertBanner")
        self.banner.setWordWrap(True)
        rl.addWidget(self.banner)
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("TcTitle")
        self.title_lbl.setWordWrap(True)
        rl.addWidget(self.title_lbl)
        self.meta_lbl = QLabel()
        rl.addWidget(self.meta_lbl)
        sec = QLabel("解决方法")
        sec.setObjectName("Section")
        rl.addWidget(sec)
        self.solution = QTextBrowser()
        self.solution.setObjectName("Solution")
        self.solution.setMaximumHeight(220)
        rl.addWidget(self.solution, 1)
        self.gallery_cap = QLabel("解决方法图片（用 ◀ ▶ 或键盘方向键切换）")
        self.gallery_cap.setObjectName("Section")
        rl.addWidget(self.gallery_cap)
        self.gallery = SolutionGallery()
        rl.addWidget(self.gallery, 3)
        row = QHBoxLayout()
        self.b_answer = QPushButton("填写解决方法")
        self.b_answer.setObjectName("Primary")
        self.b_answer.clicked.connect(self._answer)
        b_edit = QPushButton("编辑")
        b_edit.clicked.connect(self._edit)
        b_del = QPushButton("删除")
        b_del.setObjectName("Danger")
        b_del.clicked.connect(self._delete)
        b_close = QPushButton("关闭")
        b_close.setObjectName("Primary")
        b_close.clicked.connect(self.accept)
        row.addWidget(self.b_answer)
        row.addWidget(b_edit)
        row.addWidget(b_del)
        row.addStretch(1)
        row.addWidget(b_close)
        rl.addLayout(row)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        self._fill()

    def _fill(self):
        e = self.entry
        self.title_lbl.setText(e["title"])
        is_open = e.get("status") == config.STATUS_OPEN
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["created_at"]))
        if is_open:
            self.banner.setText("⏳ 等待解答中 —— 知道解决方法的人，请点击下方“填写解决方法”")
            self.meta_lbl.setText(f"提问PC：{e.get('asked_by') or '-'}　·　提问时间：{stamp}")
        else:
            self.meta_lbl.setText(f"解答PC：{e['answered_by']}" if e.get("answered_by") else "")
        self.banner.setVisible(is_open)
        self.meta_lbl.setVisible(bool(self.meta_lbl.text()))
        self.b_answer.setVisible(is_open)
        self.solution.setPlainText(e["solution"] or ("" if storage.sol_list(e) else (
            "（等待解答中，尚无解决方法）" if is_open else "（尚未填写解决方法）")))
        src = e["original"] or e["image"]
        self.zoom.set_image(storage.load_qimage(src) if src else None)
        sol = storage.sol_list(e)
        self.gallery.set_images(sol)
        self.gallery.setVisible(bool(sol))
        self.gallery_cap.setVisible(bool(sol))
        self.solution.setMaximumHeight(220 if sol else 16777215)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.zoom.fit()

    def _answer(self):
        if not ask_password(self, self.db, "填写解决方法需要输入密码"):
            return
        dlg = EntryDialog(self, self.db, self.entry["category"], self.entry, mode=EntryDialog.MODE_ANSWER)
        if dlg.exec() == QDialog.Accepted:
            self.entry = self.db.get_entry(self.entry["id"])
            self.was_changed = True
            self._fill()
            self.changed.emit()

    def _edit(self):
        if not ask_password(self, self.db, "编辑需要输入密码"):
            return
        dlg = EntryDialog(self, self.db, self.entry["category"], self.entry)
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
            storage.remove_files(*storage.entry_files(self.entry))
            self.db.delete_entry(self.entry["id"])
            self.was_changed = True
            self.changed.emit()
            self.accept()
