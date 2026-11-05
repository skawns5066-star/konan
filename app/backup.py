"""백업 내보내기 / 가져오기. 폴더 통째로 복사해도 동일하게 동작한다."""
import shutil
import sqlite3
import tempfile
import time
import zipfile
from contextlib import closing
from pathlib import Path

from . import config


def export_zip(dest: str, db):
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "guide.db"
        with closing(sqlite3.connect(str(db.path))) as src, closing(sqlite3.connect(str(snap))) as dst:
            src.backup(dst)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "guide.db")
            if config.IMG_DIR.exists():
                for f in config.IMG_DIR.rglob("*"):
                    if f.is_file():
                        z.write(f, "images/" + f.relative_to(config.IMG_DIR).as_posix())


def _safe_members(z: zipfile.ZipFile):
    for name in z.namelist():
        p = Path(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("备份文件包含不安全的路径")
    return z.namelist()


def import_zip(src: str, db):
    """zip 의 내용으로 현재 데이터를 교체한다. 교체 전 자동 백업을 backups/ 에 남긴다."""
    with zipfile.ZipFile(src) as z:
        names = _safe_members(z)
        if "guide.db" not in names:
            raise ValueError("不是有效的备份文件（缺少 guide.db）")
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        export_zip(str(config.BACKUP_DIR / f"before_import_{time.strftime('%Y%m%d_%H%M%S')}.zip"), db)
        with tempfile.TemporaryDirectory() as tmp:
            z.extractall(tmp)
            tmp = Path(tmp)
            if config.IMG_DIR.exists():
                shutil.rmtree(config.IMG_DIR)
            if (tmp / "images").exists():
                shutil.copytree(tmp / "images", config.IMG_DIR)
            shutil.copy2(tmp / "guide.db", config.DB_PATH)
    config.ensure_dirs()
    db.init()
