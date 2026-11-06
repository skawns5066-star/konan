"""사진 파일 관리. 모든 사진은 data/images 로 복사되고 DB 에는 상대경로만 저장된다."""
import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter

from . import config

MAX_SIDE = 2000          # 크롭본 최대 변

FIT_BG = QColor("#EEF1F6")


def abs_path(rel: Optional[str]) -> Optional[Path]:
    return (config.DATA_DIR / rel) if rel else None


def _rel(path: Path) -> str:
    return path.relative_to(config.DATA_DIR).as_posix()


def load_qimage(source) -> QImage:
    """파일 경로(절대 또는 data 기준 상대)를 읽는다. EXIF 회전 반영."""
    p = Path(source)
    if not p.is_absolute():
        p = config.DATA_DIR / p
    reader = QImageReader(str(p))
    reader.setAutoTransform(True)
    return reader.read()


def import_image_file(src: str) -> str:
    """사용자가 고른 파일을 원본 그대로 data/images/original 로 복사."""
    config.ORIG_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(src).suffix.lower() or ".png"
    dest = config.ORIG_DIR / f"{uuid.uuid4().hex}{ext}"
    shutil.copy2(src, dest)
    return _rel(dest)


def import_qimage(img: QImage) -> str:
    """클립보드 등 메모리 상의 이미지를 PNG 원본으로 저장."""
    config.ORIG_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.ORIG_DIR / f"{uuid.uuid4().hex}.png"
    img.save(str(dest), "PNG")
    return _rel(dest)


def save_cropped(img: QImage) -> str:
    config.CROP_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.CROP_DIR / f"{uuid.uuid4().hex}.png"
    img.save(str(dest), "PNG")
    return _rel(dest)


def remove_files(*rels):
    for rel in {r for r in rels if r}:
        try:
            p = abs_path(rel)
            if p and p.is_file() and config.DATA_DIR in p.resolve().parents:
                p.unlink()
        except OSError:
            pass


# ---------------- 크롭 / 맞추기 렌더링 ----------------

def render_card_image(src: QImage, meta: dict, card_ratio: float) -> QImage:
    """meta: {"mode": "crop", "rect": [x,y,w,h], "ratio": float|None}  또는  {"mode": "fit"}"""
    if meta.get("mode") == "fit":
        base = 1280
        if card_ratio >= 1:
            w, h = base, max(1, round(base / card_ratio))
        else:
            h, w = base, max(1, round(base * card_ratio))
        out = QImage(w, h, QImage.Format_RGB32)
        out.fill(FIT_BG)
        scaled = src.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p = QPainter(out)
        p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        p.end()
        return out

    x, y, w, h = [int(round(v)) for v in meta["rect"]]
    rect = QRect(x, y, w, h).intersected(src.rect())
    out = src.copy(rect)
    if max(out.width(), out.height()) > MAX_SIDE:
        out = out.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return out


def default_meta(img: QImage, ratio: Optional[float]) -> dict:
    """이미지 안에 들어가는 가장 큰 크롭 박스(중앙)를 기본값으로."""
    iw, ih = img.width(), img.height()
    if ratio is None:
        w, h = iw * 0.9, ih * 0.9
    else:
        w = min(iw, ih * ratio) * 0.9
        h = w / ratio
    return {"mode": "crop", "rect": [(iw - w) / 2, (ih - h) / 2, w, h], "ratio": ratio}


def adapt_meta_to_ratio(meta: dict, img: QImage, new_ratio: float) -> dict:
    """카드 비율이 바뀌었을 때 기존 크롭의 중심을 유지하며 새 비율로 변환."""
    if meta.get("mode") == "fit":
        return meta
    x, y, w, h = meta["rect"]
    cx, cy = x + w / 2, y + h / 2
    nw = min(w, h * new_ratio)
    nh = nw / new_ratio
    nx = min(max(0, cx - nw / 2), img.width() - nw)
    ny = min(max(0, cy - nh / 2), img.height() - nh)
    return {"mode": "crop", "rect": [nx, ny, nw, nh], "ratio": new_ratio}


def dumps_meta(meta: Optional[dict]) -> Optional[str]:
    return json.dumps(meta) if meta else None


def loads_meta(text: Optional[str]) -> Optional[dict]:
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def regenerate_cards(db, old_ratio: float, new_ratio: float) -> int:
    """카드 비율 설정이 바뀌면 보관된 원본에서 카드용 사진을 다시 만든다."""
    count = 0
    for e in db.all_entries():
        if not e["original"]:
            continue
        meta = loads_meta(e["crop_meta"])
        if not meta:
            continue
        follows_card = meta.get("mode") == "fit" or (
            meta.get("ratio") and abs(meta["ratio"] - old_ratio) < 1e-3)
        if not follows_card:
            continue
        src = load_qimage(e["original"])
        if src.isNull():
            continue
        meta = adapt_meta_to_ratio(meta, src, new_ratio)
        new_rel = save_cropped(render_card_image(src, meta, new_ratio))
        db.update_entry(e["id"], image=new_rel, crop_meta=dumps_meta(meta))
        remove_files(e["image"])
        count += 1
    return count
