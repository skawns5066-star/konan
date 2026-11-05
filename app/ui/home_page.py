from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class HomeCard(QPushButton):
    def __init__(self, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("HomeCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(240)
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
        lay.addWidget(t)
        lay.addWidget(d)


class HomePage(QWidget):
    openControl = Signal()
    openInspect = Signal()
    openSettings = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 36, 48, 28)
        root.setSpacing(8)

        title = QLabel("设备故障解决指南")
        title.setObjectName("HomeTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("记录故障截图与解决方法，遇到相同问题时快速查找")
        sub.setObjectName("Subtitle")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(18)

        row = QHBoxLayout()
        row.setSpacing(28)
        self.btn_control = HomeCard("控制PC问题", "查看 / 登记控制PC的故障")
        self.btn_inspect = HomeCard("检测程序PC问题", "查看 / 登记检测程序PC的故障")
        self.btn_control.clicked.connect(self.openControl)
        self.btn_inspect.clicked.connect(self.openInspect)
        row.addWidget(self.btn_control, 1)
        row.addWidget(self.btn_inspect, 1)
        root.addLayout(row, 1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        b = QPushButton("设置")
        b.clicked.connect(self.openSettings)
        foot.addWidget(b)
        root.addLayout(foot)
