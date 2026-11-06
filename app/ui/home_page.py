from PySide6.QtCore import Qt, Signal

from .. import config
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class HomeCard(QPushButton):
    def __init__(self, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("HomeCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(120)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("HomeCardTitle")
        t.setAlignment(Qt.AlignCenter)
        d = QLabel(desc)
        d.setObjectName("HomeCardDesc")
        d.setAlignment(Qt.AlignCenter)
        for w in (t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.badge = QLabel("")
        self.badge.setObjectName("HomeBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.badge.hide()
        lay.addWidget(t)
        lay.addWidget(d)
        lay.addWidget(self.badge, 0, Qt.AlignHCenter)

    def set_pending(self, n: int):
        self.badge.setText(f"⏳ {n} 个问题等待解答")
        self.badge.setVisible(n > 0)
        self.setProperty("pending", n > 0)
        self.style().unpolish(self)
        self.style().polish(self)


class HomePage(QWidget):
    openCategory = Signal(str)
    openSettings = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 30, 48, 24)
        root.setSpacing(8)

        title = QLabel("设备故障解决指南")
        title.setObjectName("HomeTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("记录故障截图与解决方法，遇到相同问题时快速查找")
        sub.setObjectName("Subtitle")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addWidget(sub)
        self.alarm = QLabel("")
        self.alarm.setObjectName("AlertBanner")
        self.alarm.setAlignment(Qt.AlignCenter)
        self.alarm.hide()
        root.addWidget(self.alarm)
        root.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(24)
        self.cards = {}
        for i, (key, name, desc) in enumerate(config.CATEGORIES):
            card = HomeCard(name, desc)
            card.clicked.connect(lambda _=False, k=key: self.openCategory.emit(k))
            grid.addWidget(card, i // 2, i % 2)
            self.cards[key] = card
        for r in range(2):
            grid.setRowStretch(r, 1)
        for c in range(2):
            grid.setColumnStretch(c, 1)
        root.addLayout(grid, 1)

        foot = QHBoxLayout()
        self.sync_lbl = QLabel("")
        self.sync = QPushButton("⟳  同步")
        foot.addWidget(self.sync_lbl)
        foot.addStretch(1)
        foot.addWidget(self.sync)
        b = QPushButton("设置")
        b.clicked.connect(self.openSettings)
        foot.addWidget(b)
        root.addLayout(foot)

    def set_alarms(self, counts: dict):
        """카테고리별 답변 대기 개수 → 버튼 배지 + 상단 경고 배너."""
        for key, card in self.cards.items():
            card.set_pending(counts.get(key, 0))
        total = sum(counts.values())
        self.alarm.setVisible(total > 0)
        if total:
            self.alarm.setText(f"⚠ 共有 {total} 个问题正在等待解答，知道解决方法的人请进入对应分类查看")
