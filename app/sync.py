"""다중 PC 동기화 (공유 폴더 방식).

구조 (공유 폴더 = NAS / 공유 PC 폴더):
    <공유폴더>/entries/<uid>.json     항목 1개 = 파일 1개 (SQLite 를 네트워크에 두지 않아 손상 위험이 없다)
    <공유폴더>/images/original|cropped/…   사진 (파일명이 UUID 라 충돌하지 않는다)
    <공유폴더>/settings.json          모든 PC 가 공유하는 설정(비밀번호, 카드 비율)

각 PC 는 자기 data/ 에 전체 사본을 가지고 있어 공유 폴더가 끊겨도 계속 쓸 수 있고,
연결되면 변경분(dirty)을 올리고 다른 PC 의 변경분을 받아온다.
충돌(같은 항목을 동시에 수정)은 rev(수정 횟수) → 수정 시각 → PC id 순으로 더 새로운 쪽이 이긴다.
"""
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from . import config, storage


class SyncError(Exception):
    pass


# ---------------- 파일 유틸 ----------------

def _atomic_write(dest: Path, data: bytes):
    """임시 파일에 쓴 뒤 교체 → 다른 PC 가 반쯤 쓰인 파일을 읽는 일이 없다."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)


def _copy_atomic(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.name}.{os.getpid()}.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def _key(rec: dict):
    return (int(rec.get("rev") or 0), float(rec.get("updated_at") or 0), str(rec.get("device") or ""))


def _images(rec: dict):
    return storage.entry_files(rec)


# ---------------- 핵심 동기화 (Qt 비의존) ----------------

def check_folder(shared: str) -> Path:
    root = Path(shared)
    if not shared or not root.is_dir():
        raise SyncError(f"无法访问共享文件夹：{shared or '（未设置）'}")
    try:
        (root / "entries").mkdir(exist_ok=True)
        probe = root / f".probe_{os.getpid()}.tmp"
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise SyncError(f"共享文件夹没有写入权限：{exc}") from exc
    return root


def run_sync(db, shared: str, seen: dict) -> dict:
    """올리기(push) → 받기(pull) → 공유 설정. seen 은 파일 서명 캐시(변경 없는 파일은 다시 읽지 않음)."""
    root = check_folder(shared)
    entries_dir = root / "entries"
    pushed = pulled = 0

    # 1) PUSH: 이 PC 에서 바뀐 항목을 공유 폴더에 올림
    for e in db.dirty_entries():
        path = entries_dir / f"{e['uid']}.json"
        remote = _read_json(path)
        if remote and _key(remote) >= _key(e):
            if _key(remote) == _key(e):
                db.mark_clean(e["uid"], e["rev"])
            continue                      # 공유 쪽이 더 새로움 → 아래 pull 에서 덮어씀
        if e["deleted"]:
            for rel in _images(e):
                try:
                    (root / rel).unlink()
                except OSError:
                    pass
        else:
            for rel in _images(e):        # 사진을 먼저 올리고, 그 다음에 항목 파일(참조)을 올림
                src, dst = config.DATA_DIR / rel, root / rel
                if src.is_file() and not dst.exists():
                    _copy_atomic(src, dst)
        rec = {k: e[k] for k in ("category", "title", "solution", "original", "image", "crop_meta", "sol_images",
                                 "created_at", "updated_at", "rev", "deleted", "device")}
        rec["uid"] = e["uid"]
        _atomic_write(path, json.dumps(rec, ensure_ascii=False).encode("utf-8"))
        db.mark_clean(e["uid"], e["rev"])
        pushed += 1

    # 2) PULL: 다른 PC 가 바꾼 항목을 받아옴
    with os.scandir(entries_dir) as it:
        files = [d for d in it if d.name.endswith(".json")]
    for de in files:
        uid = de.name[:-5]
        try:
            st = de.stat()
        except OSError:
            continue
        sig = (st.st_mtime_ns, st.st_size)
        if seen.get(uid) == sig:
            continue
        rec = _read_json(Path(de.path))
        if not rec:
            continue
        local = db.get_by_uid(uid)
        if local and _key(local) >= _key(rec):
            seen[uid] = sig
            continue
        old_imgs = _images(local) if local else []
        if rec.get("deleted"):
            storage.remove_files(*old_imgs, *_images(rec))
        else:
            incomplete = False
            for rel in _images(rec):
                dst = config.DATA_DIR / rel
                if not dst.exists():
                    src = root / rel
                    if not src.is_file():
                        incomplete = True
                        break
                    _copy_atomic(src, dst)
            if incomplete:                # 사진이 아직 올라오는 중 → 다음 주기에 다시 시도
                continue
            storage.remove_files(*[r for r in old_imgs if r not in _images(rec)])
        db.upsert_remote(uid, rec)
        seen[uid] = sig
        pulled += 1

    # 3) 공유 설정 (비밀번호, 카드 비율)
    settings_changed = False
    sp = root / "settings.json"
    remote = _read_json(sp) or {}
    rrev = int(remote.get("rev", 0))
    mine = db.shared_state()
    if mine["dirty"] and mine["rev"] > rrev:
        data = {"password": mine["password"], "card_ratio": mine["card_ratio"], "rev": mine["rev"]}
        _atomic_write(sp, json.dumps(data).encode("utf-8"))
        db.clear_shared_dirty()
        pushed += 1
    elif rrev > mine["rev"] or (mine["dirty"] and rrev >= mine["rev"]):
        db.apply_shared(remote)
        settings_changed = True

    return {"pushed": pushed, "pulled": pulled, "settings_changed": settings_changed}


# ---------------- Qt 래퍼 ----------------

class _Worker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, db, path, seen, parent=None):
        super().__init__(parent)
        self.db, self.path, self.seen = db, path, seen

    def run(self):
        try:
            self.done.emit(run_sync(self.db, self.path, self.seen))
        except SyncError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - 네트워크 오류 등은 상태 표시만 하고 계속 동작
            self.failed.emit(f"同步失败：{exc}")


class SyncManager(QObject):
    """자동(주기적 + 변경 즉시) / 수동 동기화 관리."""
    status = Signal(str, str)      # state: off|ok|busy|pending|error , 표시 문구
    dataChanged = Signal(bool)     # 다른 PC 의 변경을 받았음 (공유 설정 변경 여부)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._seen: dict = {}
        self._worker: Optional[_Worker] = None
        self._again = False
        self._manual = False
        self.last_state, self.last_text = "off", ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.sync_now())
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(500)
        self.debounce.timeout.connect(lambda: self.sync_now())
        db.on_local_change = self.on_local_change

    # ---- 설정 ----
    @property
    def path(self) -> str:
        return self.db.get_setting("sync_path").strip()

    @property
    def auto(self) -> bool:
        return self.db.get_setting("sync_auto", "1") == "1"

    def configure(self):
        """설정이 바뀐 뒤 호출 (경로, 자동/수동, 주기)."""
        self._seen.clear()
        self.timer.stop()
        if not self.path:
            self._emit("off", "未设置共享文件夹")
            return
        if self.auto:
            try:
                sec = int(self.db.get_setting("sync_interval", str(config.DEFAULT_SYNC_INTERVAL)))
            except ValueError:
                sec = config.DEFAULT_SYNC_INTERVAL
            self.timer.start(max(3, sec) * 1000)
            self.sync_now()
        else:
            self._refresh_pending_text()

    def _emit(self, state, text):
        self.last_state, self.last_text = state, text
        self.status.emit(state, text)

    def _refresh_pending_text(self):
        n = self.db.dirty_count()
        if n:
            self._emit("pending", f"有 {n} 项修改待同步")
        else:
            self._emit("ok", "手动同步模式")

    # ---- 동작 ----
    def on_local_change(self):
        if not self.path:
            return
        if self.auto:
            self.debounce.start()
        else:
            self._refresh_pending_text()

    def sync_now(self, manual: bool = False):
        if not self.path:
            self._emit("off", "未设置共享文件夹")
            return
        if self._worker is not None:
            self._again = True
            self._manual = self._manual or manual
            return
        self._manual = manual
        self._emit("busy", "同步中…")
        self._worker = _Worker(self.db, self.path, self._seen, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._cleanup)
        self._worker.start()

    def _cleanup(self):
        w, self._worker = self._worker, None
        if w:
            w.deleteLater()
        if self._again:
            self._again = False
            self.sync_now(self._manual)

    def _on_done(self, res: dict):
        if res["pulled"] or res["settings_changed"]:
            self.dataChanged.emit(res["settings_changed"])
        stamp = time.strftime("%H:%M:%S")
        extra = f"（↑{res['pushed']} ↓{res['pulled']}）" if (res["pushed"] or res["pulled"]) else ""
        self._emit("ok", f"已同步 {stamp}{extra}")

    def _on_failed(self, msg: str):
        pend = self.db.dirty_count()
        self._emit("error", msg + (f"（{pend} 项修改待同步）" if pend else ""))

    def shutdown(self):
        self.timer.stop()
        self.debounce.stop()
        if self._worker is not None:
            self._worker.wait(20000)
