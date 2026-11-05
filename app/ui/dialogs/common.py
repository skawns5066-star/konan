"""공용 대화상자: 메시지, 확인, 비밀번호."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout)


def _box(parent, icon, title, text, buttons):
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    created = []
    for label, role, name in buttons:
        b = box.addButton(label, role)
        if name:
            b.setObjectName(name)
        created.append(b)
    return box, created


def info(parent, text, title="提示"):
    box, _ = _box(parent, QMessageBox.Information, title, text, [("确定", QMessageBox.AcceptRole, "Primary")])
    box.exec()


def warn(parent, text, title="提示"):
    box, _ = _box(parent, QMessageBox.Warning, title, text, [("确定", QMessageBox.AcceptRole, "Primary")])
    box.exec()


def confirm(parent, text, title="请确认", yes="确定", no="取消", danger=False) -> bool:
    box, (b_yes, b_no) = _box(parent, QMessageBox.Question, title, text,
                              [(yes, QMessageBox.AcceptRole, "Danger" if danger else "Primary"),
                               (no, QMessageBox.RejectRole, None)])
    box.setDefaultButton(b_no)
    box.exec()
    return box.clickedButton() is b_yes


class PasswordDialog(QDialog):
    def __init__(self, parent, db, prompt="请输入密码以继续"):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("需要密码")
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        title = QLabel(prompt)
        title.setObjectName("Section")
        lay.addWidget(title)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("密码")
        self.edit.setMinimumWidth(300)
        self.edit.returnPressed.connect(self._try)
        lay.addWidget(self.edit)
        self.msg = QLabel("")
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("确定")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._try)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _try(self):
        if self.db.verify_password(self.edit.text()):
            self.accept()
        else:
            self.msg.setText("密码错误，请重试。")
            self.edit.selectAll()
            self.edit.setFocus()


def ask_password(parent, db, prompt="修改/删除需要输入密码") -> bool:
    return PasswordDialog(parent, db, prompt).exec() == QDialog.Accepted


class ChangePasswordDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("修改密码")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        self.old = self._field(lay, "当前密码")
        self.new = self._field(lay, "新密码")
        self.new2 = self._field(lay, "再次输入新密码")
        self.msg = QLabel("")
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setObjectName("Primary")
        ok.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def _field(self, lay, label):
        lay.addWidget(QLabel(label))
        e = QLineEdit()
        e.setEchoMode(QLineEdit.Password)
        e.setMinimumWidth(320)
        lay.addWidget(e)
        return e

    def _save(self):
        if not self.db.verify_password(self.old.text()):
            self.msg.setText("当前密码不正确。")
        elif len(self.new.text()) < 1:
            self.msg.setText("新密码不能为空。")
        elif self.new.text() != self.new2.text():
            self.msg.setText("两次输入的新密码不一致。")
        else:
            self.db.set_password(self.new.text())
            self.accept()
