"""등록/수정 창 (모든 카테고리 공통).
왼쪽: 문제가 생긴 화면 사진 1장(크롭) / 오른쪽: 제목 + 해결 방법(텍스트 + 사진 여러 장)."""
import json
from typing import Optional

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout
from PySide6.QtGui import QImage

from ... import config, storage
from ..widgets.image_picker import ImagePicker
from ..widgets.image_widgets import PasteFilter
from ..widgets.solution_photos import SolutionPhotoEditor
from .common import warn
from .crop_dialog import CropDialog


class EntryDialog(QDialog):
    def __init__(self, parent, db, category: str, entry: Optional[dict] = None):
        super().__init__(parent)
        self.db = db
        self.category = category
        self.entry = entry
        self.saved_id: Optional[int] = None

        # 사진 상태
        self._orig_img: Optional[QImage] = None     # 전체 원본
        self._new_src_path = ""                     # 새로 고른 파일 경로(없으면 클립보드 이미지)
        self._orig_is_new = False
        self._card_img: Optional[QImage] = None     # 크롭 결과(카드용)
        self._meta: Optional[dict] = None
        self._crop_dirty = False

        self.setWindowTitle(("编辑 · " if entry else "添加 · ") + config.CATEGORY_TITLES.get(category, ""))
        self.resize(1200, 760)
        self._build()
        if entry:
            self._load_existing()

    # ---------------- UI ----------------
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        self.picker = ImagePicker("问题画面（1张）\n点击此处选择图片\n或按 Ctrl+V 粘贴截图\n（也可以直接拖入图片）")
        self.picker.imageChosen.connect(self._on_image)
        self.picker.error.connect(lambda m: warn(self, m))
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
        self.title_edit.setPlaceholderText("请输入标题（繁體中文）")
        form.addWidget(self.title_edit)

        lbl2 = QLabel("解决方法")
        lbl2.setObjectName("Section")
        form.addSpacing(6)
        form.addWidget(lbl2)
        self.solution_edit = QTextEdit()
        self.solution_edit.setObjectName("Solution")
        self.solution_edit.setAcceptRichText(False)
        self.solution_edit.setPlaceholderText("请输入解决方法（可多行）")
        form.addWidget(self.solution_edit, 1)
        self.sol_editor = SolutionPhotoEditor()
        form.addWidget(self.sol_editor)

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
        # 제목 칸 Ctrl+V → 문제 화면 사진, 해결 방법 칸 Ctrl+V → 해결 방법 사진
        self._pf_problem = PasteFilter(self.picker.paste, self)
        self._pf_solution = PasteFilter(self.sol_editor.paste, self)
        self.title_edit.installEventFilter(self._pf_problem)
        self.solution_edit.installEventFilter(self._pf_solution)

    def _load_existing(self):
        e = self.entry
        self.title_edit.setText(e["title"])
        self.solution_edit.setPlainText(e["solution"])
        src = e["original"] or e["image"]
        if src:
            self._orig_img = storage.load_qimage(src)
        shown = storage.load_qimage(e["image"]) if e["image"] else self._orig_img
        self.picker.show_image(shown)
        self._meta = storage.loads_meta(e["crop_meta"])
        self.btn_recrop.setEnabled(self._orig_img is not None and not self._orig_img.isNull())
        self.sol_editor.set_existing(storage.sol_list(e))

    # ---------------- 사진 처리 ----------------
    def _on_image(self, img: QImage, path: str):
        dlg = CropDialog(img, self.db.card_ratio_key, None, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self._card_img = dlg.result_image()
        self._meta = dlg.meta()
        self._crop_dirty = True
        self.picker.show_image(self._card_img)
        self.btn_recrop.setEnabled(True)
        self._orig_img = img
        self._new_src_path = path
        self._orig_is_new = True

    def _recrop(self):
        if self._orig_img is None or self._orig_img.isNull():
            return
        dlg = CropDialog(self._orig_img, self.db.card_ratio_key, self._meta, self)
        if dlg.exec() == QDialog.Accepted:
            self._card_img = dlg.result_image()
            self._meta = dlg.meta()
            self._crop_dirty = True
            self.picker.show_image(self._card_img)

    # ---------------- 저장 ----------------
    def _save(self):
        title = self.title_edit.text().strip()
        solution = self.solution_edit.toPlainText().strip()
        if self._orig_img is None or self._orig_img.isNull():
            warn(self, "请先添加问题画面图片。")
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
            image_rel = storage.save_cropped(self._card_img)
        elif self._crop_dirty:                      # 사진은 그대로, 크롭만 다시 함
            to_remove.append(old.get("image"))
            image_rel = storage.save_cropped(self._card_img)

        # 해결 방법 사진: 기존 것은 유지, 새로 추가한 것은 복사, 목록에서 빠진 것은 삭제
        new_sol = []
        for it in self.sol_editor.items():
            if it["rel"]:
                new_sol.append(it["rel"])
            elif it["src"]:
                new_sol.append(storage.import_solution_file(it["src"]))
            else:
                new_sol.append(storage.import_solution_qimage(it["img"]))
        to_remove += [r for r in storage.sol_list(old) if r not in new_sol]
        sol_json = json.dumps(new_sol) if new_sol else None

        meta = storage.dumps_meta(self._meta)
        if self.entry:
            self.db.update_entry(self.entry["id"], title=title, solution=solution,
                                 original=orig_rel, image=image_rel, crop_meta=meta, sol_images=sol_json)
            self.saved_id = self.entry["id"]
        else:
            self.saved_id = self.db.add_entry(self.category, title, solution, orig_rel, image_rel, meta, sol_json)
        storage.remove_files(*[r for r in to_remove if r and r not in (orig_rel, image_rel, *new_sol)])
        self.accept()
