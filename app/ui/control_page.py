"""제어 PC 문제 화면: 제목 검색 + 목록 + 큰 사진 + 펼쳐지는 해결 방법."""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSplitter, QTextBrowser, QVBoxLayout,
                               QWidget, QFrame)

from .. import config, storage
from .dialogs.common import ask_password, confirm
from .dialogs.entry_dialog import EntryDialog
from .widgets.image_widgets import ScaledImageLabel, ZoomView
from .widgets.page_header import PageHeader

CAT = config.CATEGORY_CONTROL


class ImageViewerDialog(QDialog):
    """사진을 크게 보는 창 (휠 확대, 드래그 이동)."""

    def __init__(self, parent, img, title=""):
        super().__init__(parent)
        self.setWindowTitle(title or "查看图片")
        w = parent.window() if parent else None
        self.resize(int(w.width() * 0.92) if w else 1100, int(w.height() * 0.92) if w else 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        self.view = ZoomView()
        self.view.set_image(img)
        lay.addWidget(self.view, 1)
        tip = QLabel("滚轮缩放 · 拖动平移 · 双击还原")
        tip.setAlignment(Qt.AlignCenter)
        lay.addWidget(tip)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.view.fit()


class ControlPage(QWidget):
    goHome = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("Page")
        self._current: Optional[dict] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        self.header = PageHeader("控制PC问题")
        self.header.back.clicked.connect(self.goHome)
        self.header.add.clicked.connect(self._add)
        root.addWidget(self.header)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("🔍  输入标题进行搜索（不区分大小写，支持部分匹配）")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        root.addWidget(self.search)

        body = QSplitter(Qt.Horizontal)
        body.setChildrenCollapsible(False)
        root.addWidget(body, 1)

        # 왼쪽: 목록
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        self.count = QLabel("")
        ll.addWidget(self.count)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.currentItemChanged.connect(self._on_select)
        ll.addWidget(self.list, 1)
        body.addWidget(left)

        # 오른쪽: 사진 + 해결 방법
        right = QFrame()
        right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 14)
        rl.setSpacing(10)
        self.photo = ScaledImageLabel(radius=10)
        self.photo.set_placeholder("")
        self.photo.setMinimumHeight(200)
        self.photo.doubleClicked.connect(self._zoom)
        self.photo.setToolTip("双击放大查看")
        rl.addWidget(self.photo, 1)

        self.toggle = QPushButton("▸  解决方法")
        self.toggle.setCheckable(True)
        self.toggle.setObjectName("Primary")
        self.toggle.toggled.connect(self._on_toggle)
        rl.addWidget(self.toggle)

        self.solution = QTextBrowser()
        self.solution.setObjectName("Solution")
        self.solution.setMinimumHeight(140)
        self.solution.setMaximumHeight(300)
        self.solution.hide()
        rl.addWidget(self.solution)

        row = QHBoxLayout()
        self.b_edit = QPushButton("编辑")
        self.b_edit.clicked.connect(self._edit)
        self.b_del = QPushButton("删除")
        self.b_del.setObjectName("Danger")
        self.b_del.clicked.connect(self._delete)
        row.addStretch(1)
        row.addWidget(self.b_edit)
        row.addWidget(self.b_del)
        rl.addLayout(row)
        body.addWidget(right)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 5)
        body.setSizes([320, 640])

        self.refresh()

    # ---------------- 데이터 ----------------
    def refresh(self, select_id: Optional[int] = None):
        if select_id is None and self._current:
            select_id = self._current["id"]
        entries = self.db.list_entries(CAT, self.search.text())
        total = len(self.db.list_entries(CAT))
        self.list.blockSignals(True)
        self.list.clear()
        target = None
        for e in entries:
            it = QListWidgetItem(e["title"])
            it.setData(Qt.UserRole, e["id"])
            it.setToolTip(e["title"])
            self.list.addItem(it)
            if e["id"] == select_id:
                target = it
        self.list.blockSignals(False)
        self.count.setText(f"共 {total} 条" + (f"，匹配 {len(entries)} 条" if self.search.text().strip() else ""))
        if target is not None:
            self.list.setCurrentItem(target)
            self._show(self.db.get_entry(select_id))
        else:
            self._show(None)

    def _on_select(self, cur, _prev):
        if cur is None:
            self._show(None)
        else:
            self.toggle.setChecked(False)
            self._show(self.db.get_entry(cur.data(Qt.UserRole)))

    def _show(self, entry: Optional[dict]):
        self._current = entry
        has = entry is not None
        for w in (self.toggle, self.b_edit, self.b_del):
            w.setEnabled(has)
        if not has:
            self.photo.set_image(None)
            empty = not self.db.list_entries(CAT)
            self.photo.set_placeholder("还没有数据。\n请点击右上角“添加”登记第一条故障。" if empty
                                       else "请从左侧列表选择一条故障")
            self.solution.hide()
            self.toggle.setChecked(False)
            return
        src = entry["original"] or entry["image"]
        self.photo.set_image(storage.load_qimage(src) if src else None)
        self.solution.setPlainText(entry["solution"] or "（尚未填写解决方法）")

    def _on_toggle(self, on):
        self.toggle.setText(("▾" if on else "▸") + "  解决方法")
        self.solution.setVisible(on and self._current is not None)

    def _zoom(self):
        if self._current and self.photo.has_image():
            src = self._current["original"] or self._current["image"]
            ImageViewerDialog(self, storage.load_qimage(src), self._current["title"]).exec()

    # ---------------- 추가/수정/삭제 ----------------
    def _add(self):
        dlg = EntryDialog(self, self.db, CAT)
        if dlg.exec() == QDialog.Accepted:
            self.search.clear()
            self._current = None
            self.refresh(dlg.saved_id)

    def _edit(self):
        if not self._current or not ask_password(self, self.db, "编辑需要输入密码"):
            return
        dlg = EntryDialog(self, self.db, CAT, self._current)
        if dlg.exec() == QDialog.Accepted:
            self.refresh(dlg.saved_id)

    def _delete(self):
        e = self._current
        if not e or not ask_password(self, self.db, "删除需要输入密码"):
            return
        if confirm(self, f"确定要删除“{e['title']}”吗？\n删除后无法恢复。", "删除确认", yes="删除", danger=True):
            storage.remove_files(e["original"], e["image"])
            self.db.delete_entry(e["id"])
            self._current = None
            self.refresh()
