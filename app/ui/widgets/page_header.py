from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class PageHeader(QWidget):
    """[← 首页]  제목  ......  동기화 상태 [⟳ 同步] [＋ 添加]"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.back = QPushButton("←  返回首页")
        self.back.setObjectName("Flat")
        self.title = QLabel(title)
        self.title.setObjectName("Title")
        self.sync_lbl = QLabel("")
        self.sync_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # 좁은 창에서는 제목보다 먼저 줄어듦
        self.sync_lbl.setMinimumWidth(0)
        self.sync = QPushButton("⟳  同步")
        self.ask = QPushButton("❓  提问（求助）")
        self.ask.setObjectName("Alert")
        self.ask.setToolTip("不知道解决方法？上传出问题的画面，向其他人求助")
        self.add = QPushButton("＋  添加")
        self.add.setObjectName("Primary")
        lay.addWidget(self.back)
        lay.addSpacing(8)
        lay.addWidget(self.title)
        lay.addStretch(1)
        lay.addWidget(self.sync_lbl)
        lay.addWidget(self.sync)
        lay.addWidget(self.ask)
        lay.addWidget(self.add)
