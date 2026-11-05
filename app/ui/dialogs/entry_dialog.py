"""등록/수정 창. 제어 PC: 사진 → OCR 자동 제목 / 검사 PC: 사진 → 크롭 편집 → 번체 제목 직접 입력."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
                               QVBoxLayout)

from ... import config, ocr, storage
from ..widgets.image_picker import ImagePicker
from ..widgets.image_widgets import PasteFilter
from .common import warn
from .crop_dialog import CropDialog


class EntryDialog(QDialog):
    def __init__(self, parent, db, category: str, entry: Optional[dict] = None):
        super().__init__(parent)
        self.db = db
        self.category = category
        self.entry = entry
        self.is_inspect = category == config.CATEGORY_INSPECT
        self.saved_id: Optional[int] = None

        # 사진 상태
        self._orig_img: Optional[QImage] = None     # 전체 원본
        self._new_src_path = ""                     # 새로 고른 파일 경로(없으면 클립보드 이미지)
        self._orig_is_new = False
        self._card_img: Optional[QImage] = None     # 검사PC: 크롭 결과
        self._meta: Optional[dict] = None
        self._crop_dirty = False
        # OCR 상태
        self._ocr_token = 0
        self._ocr_worker = None
        self._title_dirty = entry is not None       # 수정 모드에서는 기존 제목을 OCR 이 덮어쓰지 않음

        editing = entry is not None
        self.setWindowTitle(("编辑" if editing else "添加") + ("检测程序PC问题" if self.is_inspect else "控制PC问题"))
        self.resize(1060, 680)
        self._build()
        if editing:
            self._load_existing()

    # ---------------- UI ----------------
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        self.picker = ImagePicker("点击此处选择图片\n或按 Ctrl+V 粘贴截图\n（也可以直接拖入图片）")
        self.picker.imageChosen.connect(self._on_image)
        self.picker.error.connect(lambda m: warn(self, m))
        if self.is_inspect:
            self.btn_recrop = QPushButton("重新裁剪")
            self.btn_recrop.setEnabled(False)
            self.btn_recrop.clicked.connect(self._recrop)
            self.picker.btn_row.addWidget(self.btn_recrop)
        root.addWidget(self.picker, 5)

        form = QVBoxLayout()
        form.setSpacing(8)
        root.addLayout(form, 4)

        lbl = QLabel("标题")
        lbl.setObjectName("Section")
        form.addWidget(lbl)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("TcInput")
        if self.is_inspect:
            self.title_edit.setPlaceholderText("请输入标题（繁體中文）")
        else:
            self.title_edit.setPlaceholderText("添加图片后将自动识别文字，可手动修改")
        self.title_edit.textEdited.connect(self._on_title_edited)
        form.addWidget(self.title_edit)

        if not self.is_inspect:
            row = QHBoxLayout()
            self.ocr_status = QLabel("")
            self.ocr_status.setWordWrap(True)
            self.btn_ocr = QPushButton("重新识别文字")
            self.btn_ocr.setEnabled(False)
            self.btn_ocr.clicked.connect(self._run_ocr)
            row.addWidget(self.ocr_status, 1)
            row.addWidget(self.btn_ocr)
            form.addLayout(row)

        lbl2 = QLabel("解决方法")
        lbl2.setObjectName("Section")
        form.addSpacing(6)
        form.addWidget(lbl2)
        self.solution_edit = QTextEdit()
        self.solution_edit.setObjectName("Solution")
        self.solution_edit.setAcceptRichText(False)
        self.solution_edit.setPlaceholderText("请输入解决方法（可多行）")
        form.addWidget(self.solution_edit, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        form.addLayout(btns)

        # 입력칸에서 Ctrl+V 로 사진 붙여넣기(클립보드에 이미지만 있을 때)
        self._paste_filter = PasteFilter(self.picker.paste, self)
        for w in (self.title_edit, self.solution_edit):
            w.installEventFilter(self._paste_filter)

    def _load_existing(self):
        e = self.entry
        self.title_edit.setText(e["title"])
        self.solution_edit.setPlainText(e["solution"])
        src = e["original"] or e["image"]
        if src:
            self._orig_img = storage.load_qimage(src)
        shown = storage.load_qimage(e["image"]) if e["image"] else self._orig_img
        self.picker.show_image(shown)
        if self.is_inspect:
            self._meta = storage.loads_meta(e["crop_meta"])
            self.btn_recrop.setEnabled(self._orig_img is not None and not self._orig_img.isNull())
        elif self._orig_img is not None:
            self.btn_ocr.setEnabled(ocr.is_available())

    # ---------------- 사진 처리 ----------------
    def _on_image(self, img: QImage, path: str):
        if self.is_inspect:
            dlg = CropDialog(img, self.db.card_ratio_key, None, self)
            if dlg.exec() != QDialog.Accepted:
                return
            self._card_img = dlg.result_image()
            self._meta = dlg.meta()
            self._crop_dirty = True
            self.picker.show_image(self._card_img)
            self.btn_recrop.setEnabled(True)
        else:
            self.picker.show_image(img)
        self._orig_img = img
        self._new_src_path = path
        self._orig_is_new = True
        if not self.is_inspect:
            self.btn_ocr.setEnabled(ocr.is_available())
            if not self._title_dirty or not self.title_edit.text().strip():
                self._title_dirty = False
            self._run_ocr(auto=True)

    def _recrop(self):
        if self._orig_img is None or self._orig_img.isNull():
            return
        dlg = CropDialog(self._orig_img, self.db.card_ratio_key, self._meta, self)
        if dlg.exec() == QDialog.Accepted:
            self._card_img = dlg.result_image()
            self._meta = dlg.meta()
            self._crop_dirty = True
            self.picker.show_image(self._card_img)

    # ---------------- OCR ----------------
    def _on_title_edited(self, _text):
        self._title_dirty = True

    def _run_ocr(self, auto: bool = False):
        if self.is_inspect or self._orig_img is None:
            return
        if not ocr.is_available():
            self.ocr_status.setText("未安装 OCR 引擎，请手动输入标题。")
            return
        if auto is not True:        # 버튼으로 다시 실행하면 결과가 제목을 덮어쓴다
            self._title_dirty = False
        self._ocr_token += 1
        self.ocr_status.setText("正在识别图片中的文字…")
        worker = ocr.OcrWorker(self._ocr_token, self._orig_img, self)
        worker.done.connect(self._on_ocr_done)
        worker.failed.connect(self._on_ocr_failed)
        worker.finished.connect(worker.deleteLater)
        self._ocr_worker = worker
        worker.start()

    def _on_ocr_done(self, token, text):
        if token != self._ocr_token:
            return
        if not text:
            self.ocr_status.setText("未识别到文字，请手动输入标题。")
            return
        if self._title_dirty:
            self.ocr_status.setText(f"识别结果：{text}（已保留您输入的标题）")
        else:
            self.title_edit.setText(text)
            self.ocr_status.setText("已自动填入标题，识别可能有误，请确认后修改。")

    def _on_ocr_failed(self, token, msg):
        if token == self._ocr_token:
            self.ocr_status.setText("文字识别失败，请手动输入标题。")

    # ---------------- 저장 ----------------
    def _save(self):
        title = self.title_edit.text().strip()
        solution = self.solution_edit.toPlainText().strip()
        if self._orig_img is None or self._orig_img.isNull():
            warn(self, "请先添加图片。")
            return
        if not title:
            warn(self, "请输入标题。")
            self.title_edit.setFocus()
            return
        old = self.entry or {}
        orig_rel = old.get("original")
        image_rel = old.get("image")
        to_remove = []

        if self._orig_is_new:                      # 사진을 새로 첨부/교체
            to_remove += [old.get("original"), old.get("image")]
            orig_rel = (storage.import_image_file(self._new_src_path) if self._new_src_path
                        else storage.import_qimage(self._orig_img))
            image_rel = storage.save_cropped(self._card_img) if self.is_inspect else orig_rel
        elif self.is_inspect and self._crop_dirty:  # 사진은 그대로, 크롭만 다시 함
            to_remove.append(old.get("image"))
            image_rel = storage.save_cropped(self._card_img)

        meta = storage.dumps_meta(self._meta) if self.is_inspect else None
        if self.entry:
            self.db.update_entry(self.entry["id"], title=title, solution=solution,
                                 original=orig_rel, image=image_rel, crop_meta=meta)
            self.saved_id = self.entry["id"]
        else:
            self.saved_id = self.db.add_entry(self.category, title, solution, orig_rel, image_rel, meta)
        storage.remove_files(*[r for r in to_remove if r and r not in (orig_rel, image_rel)])
        self.accept()

    def done(self, result):
        if self._ocr_worker is not None and self._ocr_worker.isRunning():
            self._ocr_token += 1
            self._ocr_worker.wait(15000)
        super().done(result)
