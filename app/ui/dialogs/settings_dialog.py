"""설정: 글자 크기, 카드 비율, 비밀번호, 백업/복원."""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QLineEdit, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout)

import time

from ... import backup, config, storage
from .common import ChangePasswordDialog, ask_password, confirm, info, warn


class SettingsDialog(QDialog):
    fontChanged = Signal(int)
    dataReplaced = Signal()
    ratioChanged = Signal()

    def __init__(self, parent, db, sync):
        super().__init__(parent)
        self.db = db
        self.sync = sync
        self.setWindowTitle("设置")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        # 글자 크기
        lay.addWidget(self._section("文字大小"))
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(config.MIN_FONT_PT, config.MAX_FONT_PT)
        self.slider.setValue(db.font_pt)
        self.size_lbl = QLabel(f"{db.font_pt} pt")
        self.size_lbl.setMinimumWidth(56)
        self.slider.valueChanged.connect(self._on_font)
        reset = QPushButton("恢复默认")
        reset.clicked.connect(lambda: self.slider.setValue(config.DEFAULT_FONT_PT))
        row.addWidget(QLabel("小"))
        row.addWidget(self.slider, 1)
        row.addWidget(QLabel("大"))
        row.addWidget(self.size_lbl)
        row.addWidget(reset)
        lay.addLayout(row)

        # 카드 비율
        lay.addWidget(self._section("图片卡片比例（所有PC共用）"))
        row = QHBoxLayout()
        self.ratio = QComboBox()
        for k in config.RATIOS:
            self.ratio.addItem(k)
        self.ratio.setCurrentText(db.card_ratio_key)
        self.ratio.setMinimumWidth(120)
        self.ratio.activated.connect(self._on_ratio)
        row.addWidget(self.ratio)
        row.addWidget(QLabel("更改后，已保存的图片会根据原图自动重新生成。"), 1)
        lay.addLayout(row)

        # 비밀번호
        lay.addWidget(self._section("密码（编辑/删除时使用）"))
        b_pw = QPushButton("修改密码…")
        b_pw.clicked.connect(lambda: ChangePasswordDialog(self, self.db).exec())
        lay.addWidget(b_pw, 0, Qt.AlignLeft)

        # 동기화
        lay.addWidget(self._section("多台PC数据同步（共享文件夹）"))
        row = QHBoxLayout()
        self.path_edit = QLineEdit(db.get_setting("sync_path"))
        self.path_edit.setPlaceholderText(r"例如 \\NAS\guide  或  Z:\guide  （所有PC填写相同路径）")
        b_browse = QPushButton("浏览…")
        b_browse.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(b_browse)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.auto_chk = QCheckBox("自动同步")
        self.auto_chk.setChecked(db.get_setting("sync_auto", "1") == "1")
        self.interval = QComboBox()
        for sec in config.SYNC_INTERVALS:
            self.interval.addItem(f"每 {sec} 秒检查", sec)
        cur = int(db.get_setting("sync_interval", str(config.DEFAULT_SYNC_INTERVAL)) or 10)
        idx = self.interval.findData(cur)
        self.interval.setCurrentIndex(idx if idx >= 0 else 1)
        b_apply = QPushButton("应用并立即同步")
        b_apply.setObjectName("Primary")
        b_apply.clicked.connect(self._apply_sync)
        row.addWidget(self.auto_chk)
        row.addWidget(self.interval)
        row.addStretch(1)
        row.addWidget(b_apply)
        lay.addLayout(row)
        self.sync_status = QLabel(sync.last_text)
        self.sync_status.setWordWrap(True)
        sync.status.connect(self._on_status)
        lay.addWidget(self.sync_status)

        # 백업
        lay.addWidget(self._section("数据备份"))
        row = QHBoxLayout()
        b_exp = QPushButton("导出备份 (zip)…")
        b_exp.clicked.connect(self._export)
        b_imp = QPushButton("导入备份…")
        b_imp.clicked.connect(self._import)
        b_open = QPushButton("打开数据文件夹")
        b_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.DATA_DIR))))
        row.addWidget(b_exp)
        row.addWidget(b_imp)
        row.addWidget(b_open)
        row.addStretch(1)
        lay.addLayout(row)
        note = QLabel(f"数据保存位置：{config.DATA_DIR}\n也可以直接把整个程序文件夹复制到其他电脑，无需额外设置。")
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(note)

        close = QPushButton("关闭")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)

    def _section(self, text):
        l = QLabel(text)
        l.setObjectName("Section")
        return l

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择共享文件夹", self.path_edit.text())
        if path:
            self.path_edit.setText(path)

    def _on_status(self, _state, text):
        self.sync_status.setText(text)

    def _apply_sync(self):
        self.db.set_setting("sync_path", self.path_edit.text().strip())
        self.db.set_setting("sync_auto", "1" if self.auto_chk.isChecked() else "0")
        self.db.set_setting("sync_interval", str(self.interval.currentData()))
        self.sync.configure()
        if not self.auto_chk.isChecked():
            self.sync.sync_now(manual=True)

    def done(self, r):
        try:
            self.sync.status.disconnect(self._on_status)
        except (RuntimeError, TypeError):
            pass
        super().done(r)

    def _on_font(self, v):
        self.size_lbl.setText(f"{v} pt")
        self.db.set_setting("font_pt", str(v))
        self.fontChanged.emit(v)

    def _on_ratio(self, _idx):
        new_key = self.ratio.currentText()
        old_key = self.db.card_ratio_key
        if new_key == old_key:
            return
        self.db.set_card_ratio(new_key)
        n = storage.regenerate_cards(self.db, config.RATIOS[old_key], config.RATIOS[new_key])
        self.ratioChanged.emit()
        info(self, f"卡片比例已改为 {new_key}。\n已重新生成 {n} 张图片。")

    def _export(self):
        name = f"设备故障指南备份_{time.strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "导出备份", name, "ZIP (*.zip)")
        if not path:
            return
        try:
            backup.export_zip(path, self.db)
            info(self, f"备份已保存：\n{path}")
        except Exception as exc:  # noqa: BLE001
            warn(self, f"导出失败：{exc}")

    def _import(self):
        if not ask_password(self, self.db, "导入备份会覆盖现有数据，请输入密码"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入备份", "", "ZIP (*.zip)")
        if not path:
            return
        if not confirm(self, "导入后将用备份内容替换当前所有数据。\n（替换前会自动在 backups 文件夹保留一份当前数据）\n\n是否继续？",
                       "导入确认", yes="导入", danger=True):
            return
        try:
            backup.import_zip(path, self.db)
        except Exception as exc:  # noqa: BLE001
            warn(self, f"导入失败：{exc}")
            return
        self.slider.blockSignals(True)
        self.slider.setValue(self.db.font_pt)
        self.slider.blockSignals(False)
        self.ratio.setCurrentText(self.db.card_ratio_key)
        self.fontChanged.emit(self.db.font_pt)
        self.dataReplaced.emit()
        self.sync.configure()
        info(self, "导入完成。")
