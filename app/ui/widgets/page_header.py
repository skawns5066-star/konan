from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class PageHeader(QWidget):
    """[← 首页]  제목  ......  [＋ 添加]"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.back = QPushButton("←  返回首页")
        self.back.setObjectName("Flat")
        self.title = QLabel(title)
        self.title.setObjectName("Title")
        self.add = QPushButton("＋  添加")
        self.add.setObjectName("Primary")
        lay.addWidget(self.back)
        lay.addSpacing(8)
        lay.addWidget(self.title)
        lay.addStretch(1)
        lay.addWidget(self.add)
