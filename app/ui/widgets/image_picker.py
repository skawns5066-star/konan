"""사진 선택 위젯: 파일 선택 / Ctrl+V 붙여넣기 / 드래그&드롭."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QPushButton, QVBoxLayout

from ... import config
from .image_widgets import (IMAGE_SUFFIXES, ScaledImageLabel, clipboard_image, read_image)


class ImagePicker(QFrame):
    # 새 사진이 선택되었을 때: (QImage, 파일경로 또는 "")
    imageChosen = Signal(object, str)
    error = Signal(str)

    def __init__(self, hint: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        self.preview = ScaledImageLabel(radius=10)
        self.preview.set_placeholder(hint)
        self.preview.setMinimumSize(320, 220)
        self.preview.clicked.connect(self.choose_file)
        lay.addWidget(self.preview, 1)

        self.btn_row = QHBoxLayout()
        self.btn_choose = QPushButton("选择图片…")
        self.btn_choose.clicked.connect(self.choose_file)
        self.btn_paste = QPushButton("粘贴图片 (Ctrl+V)")
        self.btn_paste.clicked.connect(self.paste)
        self.btn_row.addWidget(self.btn_choose)
        self.btn_row.addWidget(self.btn_paste)
        lay.addLayout(self.btn_row)

    # 외부에서 미리보기 갱신
    def show_image(self, img):
        self.preview.set_image(img)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", config.IMAGE_FILTER)
        if path:
            self._load_path(path)

    def paste(self):
        img, path = clipboard_image()
        if img is None:
            self.error.emit("剪贴板中没有图片。\n请先截图或复制图片后再粘贴。")
            return
        self.imageChosen.emit(img, path or "")

    def _load_path(self, path: str):
        img = read_image(path)
        if img.isNull():
            self.error.emit("无法读取该图片文件。")
            return
        self.imageChosen.emit(img, path)

    def keyPressEvent(self, ev):
        if ev.matches(QKeySequence.Paste):
            self.paste()
            return
        super().keyPressEvent(ev)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls() or ev.mimeData().hasImage():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        md = ev.mimeData()
        for u in md.urls():
            if u.isLocalFile() and u.toLocalFile().lower().endswith(tuple(IMAGE_SUFFIXES)):
                self._load_path(u.toLocalFile())
                return
        if md.hasImage():
            img = md.imageData()
            if img is not None:
                self.imageChosen.emit(img, "")
