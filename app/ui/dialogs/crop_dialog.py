"""크롭 편집 창: 비율 고정 박스 이동/크기조절, 프리셋, '자르지 않고 맞추기', 실시간 미리보기."""
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ... import storage
from ...config import RATIOS

HANDLE = 9          # 핸들 그리기 반지름(px)
HIT = 14            # 핸들 판정 반경(px)
MIN_SIZE = 24       # 이미지 좌표 기준 최소 크기


class CropCanvas(QWidget):
    changed = Signal()

    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.image = image
        self.pix = QPixmap.fromImage(image)
        self.rect_img = QRectF(0, 0, image.width(), image.height())  # 이미지 좌표계의 크롭 박스
        self.ratio: Optional[float] = None
        self.fit_mode = False
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._drag = None

    # ---- 좌표 변환 ----
    def _view(self):
        m = 12
        s = min((self.width() - 2 * m) / self.image.width(), (self.height() - 2 * m) / self.image.height())
        w, h = self.image.width() * s, self.image.height() * s
        return s, (self.width() - w) / 2, (self.height() - h) / 2

    def _to_widget(self, r: QRectF) -> QRectF:
        s, ox, oy = self._view()
        return QRectF(ox + r.x() * s, oy + r.y() * s, r.width() * s, r.height() * s)

    def _to_image(self, p: QPointF) -> QPointF:
        s, ox, oy = self._view()
        return QPointF((p.x() - ox) / s, (p.y() - oy) / s)

    # ---- 외부 API ----
    def set_box(self, rect: QRectF):
        self.rect_img = rect
        self.update()
        self.changed.emit()

    def set_ratio(self, ratio: Optional[float]):
        """비율이 바뀌면 박스 중심은 유지하고 이미지 안에서 가능한 가장 큰 크기로 조정."""
        self.ratio = ratio
        iw, ih = self.image.width(), self.image.height()
        c = self.rect_img.center()
        if ratio is None:
            w, h = self.rect_img.width(), self.rect_img.height()
        else:
            w = min(iw, ih * ratio) * 0.9
            h = w / ratio
        x = min(max(0, c.x() - w / 2), iw - w)
        y = min(max(0, c.y() - h / 2), ih - h)
        self.set_box(QRectF(x, y, w, h))

    def set_fit_mode(self, on: bool):
        self.fit_mode = on
        self.update()
        self.changed.emit()

    # ---- 그리기 ----
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#E9EDF4"))
        s, ox, oy = self._view()
        img_rect = QRectF(ox, oy, self.image.width() * s, self.image.height() * s)
        p.drawPixmap(img_rect, self.pix, QRectF(self.pix.rect()))
        if self.fit_mode:
            return
        box = self._to_widget(self.rect_img)
        dim = QColor(0, 0, 0, 130)
        # 박스 바깥을 어둡게
        p.fillRect(QRectF(img_rect.left(), img_rect.top(), img_rect.width(), box.top() - img_rect.top()), dim)
        p.fillRect(QRectF(img_rect.left(), box.bottom(), img_rect.width(), img_rect.bottom() - box.bottom()), dim)
        p.fillRect(QRectF(img_rect.left(), box.top(), box.left() - img_rect.left(), box.height()), dim)
        p.fillRect(QRectF(box.right(), box.top(), img_rect.right() - box.right(), box.height()), dim)
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(box)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        for i in (1, 2):  # 3분할 가이드선
            p.drawLine(QPointF(box.left() + box.width() * i / 3, box.top()),
                       QPointF(box.left() + box.width() * i / 3, box.bottom()))
            p.drawLine(QPointF(box.left(), box.top() + box.height() * i / 3),
                       QPointF(box.right(), box.top() + box.height() * i / 3))
        p.setPen(QPen(QColor("#2F7DE1"), 2))
        p.setBrush(QColor("#FFFFFF"))
        for pt in self._handles(box).values():
            p.drawEllipse(pt, HANDLE / 1.5, HANDLE / 1.5)

    def _handles(self, box: QRectF) -> dict:
        h = {"tl": box.topLeft(), "tr": box.topRight(), "bl": box.bottomLeft(), "br": box.bottomRight()}
        if self.ratio is None:
            h.update({"t": QPointF(box.center().x(), box.top()), "b": QPointF(box.center().x(), box.bottom()),
                      "l": QPointF(box.left(), box.center().y()), "r": QPointF(box.right(), box.center().y())})
        return h

    def _hit(self, pos: QPointF):
        box = self._to_widget(self.rect_img)
        for name, pt in self._handles(box).items():
            if (pt - pos).manhattanLength() <= HIT * 1.4:
                return name
        if box.contains(pos):
            return "move"
        return None

    # ---- 마우스 ----
    def mousePressEvent(self, ev):
        if self.fit_mode or ev.button() != Qt.LeftButton:
            return
        hit = self._hit(ev.position())
        if hit:
            self._drag = (hit, self._to_image(ev.position()), QRectF(self.rect_img))

    def mouseMoveEvent(self, ev):
        if self.fit_mode:
            self.setCursor(Qt.ArrowCursor)
            return
        if not self._drag:
            hit = self._hit(ev.position())
            cur = {"move": Qt.SizeAllCursor, "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
                   "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor, "t": Qt.SizeVerCursor,
                   "b": Qt.SizeVerCursor, "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor}.get(hit, Qt.ArrowCursor)
            self.setCursor(cur)
            return
        kind, start, orig = self._drag
        now = self._to_image(ev.position())
        iw, ih = self.image.width(), self.image.height()
        if kind == "move":
            dx, dy = now.x() - start.x(), now.y() - start.y()
            x = min(max(0, orig.x() + dx), iw - orig.width())
            y = min(max(0, orig.y() + dy), ih - orig.height())
            self.set_box(QRectF(x, y, orig.width(), orig.height()))
        elif self.ratio is None:
            self.set_box(self._resize_free(kind, now, orig, iw, ih))
        else:
            self.set_box(self._resize_locked(kind, now, orig, iw, ih))

    def mouseReleaseEvent(self, _):
        self._drag = None

    def _resize_free(self, kind, now, o: QRectF, iw, ih) -> QRectF:
        l, t, r, b = o.left(), o.top(), o.right(), o.bottom()
        nx = min(max(0, now.x()), iw)
        ny = min(max(0, now.y()), ih)
        if "l" in kind:
            l = min(nx, r - MIN_SIZE)
        if "r" in kind:
            r = max(nx, l + MIN_SIZE)
        if "t" in kind:
            t = min(ny, b - MIN_SIZE)
        if "b" in kind:
            b = max(ny, t + MIN_SIZE)
        return QRectF(QPointF(l, t), QPointF(r, b))

    def _resize_locked(self, kind, now, o: QRectF, iw, ih) -> QRectF:
        if len(kind) != 2:
            return o
        sx = 1 if "r" in kind else -1
        sy = 1 if "b" in kind else -1
        ax = o.left() if sx > 0 else o.right()      # 반대편 고정 모서리
        ay = o.top() if sy > 0 else o.bottom()
        r = self.ratio
        w = max(abs(now.x() - ax), abs(now.y() - ay) * r)
        max_w = min((iw - ax) if sx > 0 else ax, ((ih - ay) if sy > 0 else ay) * r)
        w = max(MIN_SIZE * r if r > 1 else MIN_SIZE, min(w, max_w))
        h = w / r
        x = ax if sx > 0 else ax - w
        y = ay if sy > 0 else ay - h
        return QRectF(x, y, w, h)


class CropDialog(QDialog):
    def __init__(self, image: QImage, card_ratio_key: str, meta: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("裁剪图片")
        self.image = image
        self.card_ratio = RATIOS[card_ratio_key]
        self.resize(1080, 700)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self.canvas = CropCanvas(image)
        self.canvas.changed.connect(self._update_preview)
        root.addWidget(self.canvas, 1)

        side = QVBoxLayout()
        side.setSpacing(10)
        root.addLayout(side)
        side.addWidget(self._section("裁剪比例"))

        # 프리셋: 카드 비율 + 16:9, 4:3, 1:1, 자유
        keys = []
        for k in [card_ratio_key, "16:9", "4:3", "1:1"]:
            if k not in keys:
                keys.append(k)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        row = QHBoxLayout()
        self._preset_ratio = {}
        for k in keys + ["自由"]:
            b = QPushButton(k)
            b.setCheckable(True)
            self.group.addButton(b)
            self._preset_ratio[b] = RATIOS.get(k)
            row.addWidget(b)
            b.clicked.connect(lambda _=False, btn=b: self._on_preset(btn))
        side.addLayout(row)
        tip = QLabel(f"当前卡片比例：{card_ratio_key}（建议使用此比例，以便整齐显示）")
        tip.setWordWrap(True)
        side.addWidget(tip)

        self.fit_check = QCheckBox("不裁剪，完整放入卡片框内（多余部分留白）")
        self.fit_check.toggled.connect(self._on_fit)
        side.addWidget(self.fit_check)

        side.addWidget(self._section("预览（卡片效果）"))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(300, 190)
        self.preview.setStyleSheet("background:#E9EDF4;border-radius:10px;")
        side.addWidget(self.preview)
        hint = QLabel("拖动框内可移动，拖动角点可调整大小。")
        hint.setWordWrap(True)
        side.addWidget(hint)
        side.addStretch(1)

        row2 = QHBoxLayout()
        row2.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.clicked.connect(self.accept)
        row2.addWidget(cancel)
        row2.addWidget(ok)
        side.addLayout(row2)

        self._init_state(meta, keys)

    def _section(self, text):
        l = QLabel(text)
        l.setObjectName("Section")
        return l

    def _init_state(self, meta, keys):
        ratio = self.card_ratio
        if meta and meta.get("mode") == "crop":
            ratio = meta.get("ratio")
        btn = self._button_for(ratio)
        btn.setChecked(True)
        self.canvas.ratio = ratio
        if meta and meta.get("mode") == "crop":
            x, y, w, h = meta["rect"]
            self.canvas.rect_img = QRectF(x, y, w, h)
            self.canvas.update()
        else:
            self.canvas.set_ratio(ratio)
        if meta and meta.get("mode") == "fit":
            self.fit_check.setChecked(True)
        self._update_preview()

    def _button_for(self, ratio):
        for b, r in self._preset_ratio.items():
            if (r is None and ratio is None) or (r and ratio and abs(r - ratio) < 1e-3):
                return b
        return next(iter(self._preset_ratio))

    def _on_preset(self, btn):
        self.canvas.set_ratio(self._preset_ratio[btn])
        if self.fit_check.isChecked():
            self.fit_check.setChecked(False)

    def _on_fit(self, on):
        self.canvas.set_fit_mode(on)
        for b in self.group.buttons():
            b.setEnabled(not on)

    # ---- 결과 ----
    def meta(self) -> dict:
        if self.fit_check.isChecked():
            return {"mode": "fit"}
        r = self.canvas.rect_img
        return {"mode": "crop", "rect": [r.x(), r.y(), r.width(), r.height()], "ratio": self.canvas.ratio}

    def result_image(self) -> QImage:
        return storage.render_card_image(self.image, self.meta(), self.card_ratio)

    def _update_preview(self):
        img = self.result_image()
        box_w = 300
        box_h = int(box_w / self.card_ratio)
        self.preview.setFixedSize(box_w, max(120, box_h))
        pix = QPixmap.fromImage(img).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)
