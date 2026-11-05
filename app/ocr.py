"""오프라인 OCR (RapidOCR + onnxruntime). 설치되지 않았거나 실패해도 앱은 계속 동작한다."""
import importlib.util

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

_engine = None
MAX_SIDE = 2000
MIN_SCORE = 0.4


def is_available() -> bool:
    return importlib.util.find_spec("rapidocr_onnxruntime") is not None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _to_bgr(img: QImage) -> np.ndarray:
    if max(img.width(), img.height()) > MAX_SIDE:
        from PySide6.QtCore import Qt
        img = img.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=bpl * h).reshape(h, bpl)
    rgb = buf[:, : w * 3].reshape(h, w, 3)
    return np.ascontiguousarray(rgb[:, :, ::-1])  # RGB -> BGR


def recognize(img: QImage) -> str:
    result, _ = _get_engine()(_to_bgr(img))
    if not result:
        return ""
    lines = []
    for box, text, score in result:
        try:
            if float(score) < MIN_SCORE:
                continue
        except (TypeError, ValueError):
            pass
        lines.append((box[0][1], box[0][0], text.strip()))
    lines.sort(key=lambda t: (round(t[0] / 12), t[1]))  # 위→아래, 왼→오른쪽
    return " ".join(t[2] for t in lines if t[2])


class OcrWorker(QThread):
    done = Signal(int, str)     # token, text
    failed = Signal(int, str)   # token, message

    def __init__(self, token: int, img: QImage, parent=None):
        super().__init__(parent)
        self.token = token
        self._img = img.copy()

    def run(self):
        try:
            self.done.emit(self.token, recognize(self._img))
        except Exception as exc:  # noqa: BLE001 - OCR 실패는 사용자에게 메시지만 보여줌
            self.failed.emit(self.token, str(exc))
