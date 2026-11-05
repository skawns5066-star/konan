"""이미지 표시용 위젯: 비율 유지 라벨, 확대/이동 뷰, 클립보드 헬퍼."""
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QImageReader, QKeySequence, QPainter, QPainterPath,
                           QPixmap)
from PySide6.QtWidgets import (QApplication, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
                               QSizePolicy, QWidget)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


# ---------------- 클립보드 ----------------

def clipboard_has_image() -> bool:
    md = QApplication.clipboard().mimeData()
    if md is None:
        return False
    if md.hasImage():
        return True
    return any(Path(u.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES
               for u in md.urls() if u.isLocalFile())


def clipboard_image():
    """(QImage, 파일경로|None) — 없으면 (None, None)."""
    cb = QApplication.clipboard()
    md = cb.mimeData()
    if md is None:
        return None, None
    if md.hasImage():
        img = cb.image()
        if not img.isNull():
            return img, None
    for u in md.urls():
        if u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES:
            img = read_image(u.toLocalFile())
            if not img.isNull():
                return img, u.toLocalFile()
    return None, None


def read_image(path: str) -> QImage:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    return reader.read()


class PasteFilter(QObject):
    """텍스트 입력칸에서도 클립보드에 '이미지만' 있을 때는 Ctrl+V 를 사진 붙여넣기로 처리."""

    def __init__(self, callback: Callable[[], None], parent=None):
        super().__init__(parent)
        self._cb = callback

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and ev.matches(QKeySequence.Paste):
            md = QApplication.clipboard().mimeData()
            if clipboard_has_image() and not (md and md.hasText() and not md.hasUrls()):
                self._cb()
                return True
        return False


# ---------------- 비율 유지 이미지 라벨 ----------------

class ScaledImageLabel(QWidget):
    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, parent=None, radius: int = 10, bg: str = "#E9EDF4"):
        super().__init__(parent)
        self._pix: Optional[QPixmap] = None
        self._cache = None
        self._cache_key = None
        self._radius = radius
        self._bg = QColor(bg) if bg else None
        self._text = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(40, 30)

    def set_pixmap(self, pix: Optional[QPixmap]):
        self._pix = pix if pix is not None and not pix.isNull() else None
        self._cache = None
        self.update()

    def set_image(self, img: Optional[QImage]):
        self.set_pixmap(QPixmap.fromImage(img) if img is not None and not img.isNull() else None)

    def set_placeholder(self, text: str):
        self._text = text
        self.update()

    def has_image(self) -> bool:
        return self._pix is not None

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)
        p.setClipPath(path)
        if self._bg:
            p.fillRect(r, self._bg)
        if self._pix is None:
            if self._text:
                p.setPen(QColor("#000000"))
                p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, self._text)
            return
        dpr = self.devicePixelRatioF()
        target = self.size() * dpr
        key = (target.width(), target.height())
        if self._cache is None or self._cache_key != key:
            self._cache = self._pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._cache.setDevicePixelRatio(dpr)
            self._cache_key = key
        cw, ch = self._cache.width() / dpr, self._cache.height() / dpr
        p.drawPixmap(QPointF((r.width() - cw) / 2, (r.height() - ch) / 2), self._cache)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.clicked.emit()

    def mouseDoubleClickEvent(self, ev):
        self.doubleClicked.emit()


# ---------------- 확대/이동 뷰 ----------------

class ZoomView(QGraphicsView):
    """휠로 확대·축소, 드래그로 이동, 더블클릭으로 화면에 맞춤."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item: Optional[QGraphicsPixmapItem] = None
        self._user_zoomed = False
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QColor("#E9EDF4"))

    def set_image(self, img: Optional[QImage]):
        self._scene.clear()
        self._item = None
        if img is None or img.isNull():
            return
        self._item = self._scene.addPixmap(QPixmap.fromImage(img))
        self._item.setTransformationMode(Qt.SmoothTransformation)
        self._scene.setSceneRect(self._item.boundingRect())
        self.fit()

    def fit(self):
        self._user_zoomed = False
        if self._item:
            self.resetTransform()
            self.fitInView(self._item, Qt.KeepAspectRatio)

    def wheelEvent(self, ev):
        if not self._item:
            return
        factor = 1.2 if ev.angleDelta().y() > 0 else 1 / 1.2
        cur = self.transform().m11()
        if not (0.05 < cur * factor < 40):
            return
        self._user_zoomed = True
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, ev):
        self.fit()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if not self._user_zoomed:
            self.fit()
