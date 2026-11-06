"""사진 카드 화면(4개 카테고리 공통): 3x2 카드가 창을 가득 채움 + 페이지 넘김."""
from typing import List, Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from .. import config, storage
from .dialogs.detail_dialog import DetailDialog
from .dialogs.entry_dialog import EntryDialog
from .widgets.image_widgets import ScaledImageLabel
from .widgets.page_header import PageHeader

COLS, ROWS = 3, 2
PAD = 8


class PhotoCard(QFrame):
    clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PhotoCard")
        self.setCursor(Qt.PointingHandCursor)
        self.entry_id = 0
        self.image = ScaledImageLabel(self, radius=8)
        self.image.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.title = QLabel(self)
        self.title.setObjectName("CardTitle")
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_entry(self, e: dict):
        self.entry_id = e["id"]
        src = e["image"] or e["original"]
        self.image.set_image(storage.load_qimage(src) if src else None)
        self.title.setText(e["title"])
        self.setToolTip(e["title"])

    def layout_children(self, ratio: float, title_h: int):
        w = self.width()
        iw = w - 2 * PAD
        ih = int(round(iw / ratio))
        self.image.setGeometry(PAD, PAD, iw, ih)
        self.title.setGeometry(PAD, PAD + ih + 4, iw, title_h)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clicked.emit(self.entry_id)


class CardGrid(QWidget):
    """창 크기에 맞춰 카드 6장이 영역을 최대한 채우도록 직접 배치한다."""
    cardClicked = Signal(int)
    GAP = 16

    def __init__(self, ratio: float, parent=None):
        super().__init__(parent)
        self.ratio = ratio
        self.cards: List[PhotoCard] = []
        for _ in range(COLS * ROWS):
            c = PhotoCard(self)
            c.clicked.connect(self.cardClicked)
            c.hide()
            self.cards.append(c)
        self.empty = QLabel("", self)
        self.empty.setObjectName("Empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.hide()

    def set_ratio(self, ratio: float):
        self.ratio = ratio
        self._relayout()

    def set_entries(self, entries: list, empty_text: str):
        for i, card in enumerate(self.cards):
            if i < len(entries):
                card.set_entry(entries[i])
                card.show()
            else:
                card.hide()
        self.empty.setText(empty_text)
        self.empty.setVisible(not entries)
        self._relayout()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._relayout()

    def _relayout(self):
        W, H, g = self.width(), self.height(), self.GAP
        self.empty.setGeometry(0, 0, W, H)
        if W < 100 or H < 100:
            return
        fm = self.cards[0].title.fontMetrics()
        lh = fm.lineSpacing()
        texts = [c.title.text() for c in self.cards if c.isVisibleTo(self)]
        lines = 1

        def solve(nlines):
            title_h = lh * nlines + 6
            extra = 2 * PAD + 4 + title_h
            cw_by_w = (W - (COLS - 1) * g) / COLS
            ch_max = (H - (ROWS - 1) * g) / ROWS
            cw_by_h = (ch_max - extra) * self.ratio + 2 * PAD
            cw = int(max(120, min(cw_by_w, cw_by_h)))
            return cw, title_h, extra

        cw, title_h, extra = solve(1)
        if any(fm.horizontalAdvance(t) > cw - 2 * PAD - 6 for t in texts):
            cw, title_h, extra = solve(2)      # 제목이 길면 2줄 확보
        ch = int(round((cw - 2 * PAD) / self.ratio)) + extra
        gy = g + min(max(0, H - (ROWS * ch + (ROWS - 1) * g)), 40)   # 남는 세로 공간은 행 간격에 일부 배분
        total_w = COLS * cw + (COLS - 1) * g
        total_h = ROWS * ch + (ROWS - 1) * gy
        x0 = (W - total_w) // 2
        y0 = max(0, (H - total_h) // 2)
        for i, card in enumerate(self.cards):
            r, c = divmod(i, COLS)
            card.setGeometry(QRect(x0 + c * (cw + g), y0 + r * (ch + gy), cw, ch))
            card.layout_children(self.ratio, title_h)


class CardPage(QWidget):
    goHome = Signal()

    def __init__(self, db, category: str, title: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.category = category
        self.setObjectName("Page")
        self._page = 0
        self._entries: List[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(10)

        self.header = PageHeader(title)
        self.header.back.clicked.connect(self.goHome)
        self.header.add.clicked.connect(self._add)
        root.addWidget(self.header)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("🔍  输入标题进行搜索（不区分大小写，支持部分匹配）")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)
        root.addWidget(self.search)

        self.grid = CardGrid(db.card_ratio)
        self.grid.cardClicked.connect(self._open)
        root.addWidget(self.grid, 1)

        pager = QHBoxLayout()
        pager.addStretch(1)
        self.prev = QPushButton("◀  上一页")
        self.next = QPushButton("下一页  ▶")
        self.page_lbl = QLabel("0 / 0")
        self.page_lbl.setObjectName("Section")
        self.page_lbl.setMinimumWidth(80)
        self.page_lbl.setAlignment(Qt.AlignCenter)
        self.count_lbl = QLabel("")
        self.prev.clicked.connect(lambda: self._goto(self._page - 1))
        self.next.clicked.connect(lambda: self._goto(self._page + 1))
        pager.addWidget(self.prev)
        pager.addWidget(self.page_lbl)
        pager.addWidget(self.next)
        pager.addStretch(1)
        pager.addWidget(self.count_lbl)
        root.addLayout(pager)

        self.refresh()

    # ---------------- 데이터 ----------------
    def pages(self) -> int:
        return max(1, -(-len(self._entries) // config.PAGE_SIZE))

    def refresh(self):
        self.grid.set_ratio(self.db.card_ratio)
        self._entries = self.db.list_entries(self.category, self.search.text())
        self._page = min(self._page, self.pages() - 1)
        self._render()

    def _on_search(self, _t):
        self._page = 0
        self.refresh()

    def _goto(self, p):
        self._page = max(0, min(p, self.pages() - 1))
        self._render()

    def _render(self):
        start = self._page * config.PAGE_SIZE
        chunk = self._entries[start:start + config.PAGE_SIZE]
        if self._entries:
            empty = ""
        elif self.search.text().strip():
            empty = "没有找到匹配的标题"
        else:
            empty = "还没有数据。\n请点击右上角“添加”登记第一条故障。"
        self.grid.set_entries(chunk, empty)
        total = len(self._entries) and self.pages()
        self.page_lbl.setText(f"{self._page + 1 if self._entries else 0} / {total}")
        self.prev.setEnabled(self._page > 0)
        self.next.setEnabled(self._page < self.pages() - 1)
        all_n = len(self.db.list_entries(self.category))
        self.count_lbl.setText(f"共 {all_n} 条")

    # ---------------- 동작 ----------------
    def _open(self, entry_id: int):
        e = self.db.get_entry(entry_id)
        if not e:
            return
        dlg = DetailDialog(self, self.db, e)
        dlg.exec()
        if dlg.was_changed:
            self.refresh()

    def _add(self):
        dlg = EntryDialog(self, self.db, self.category)
        if dlg.exec() == QDialog.Accepted:
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self._page = 0
            self.refresh()
