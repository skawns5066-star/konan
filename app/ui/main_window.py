"""메인 창: 시작 화면 ↔ 카테고리 화면 전환, 창 크기 자동 조절, 동기화 상태 표시."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget

from .. import config, theme
from ..sync import SyncManager
from .card_page import CardPage
from .dialogs.common import ask_password
from .dialogs.settings_dialog import SettingsDialog
from .home_page import HomePage

HOME_MIN = (820, 560)
CARD_MIN = (1000, 680)


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle(config.APP_NAME)
        self._home_size = QSize(*config.HOME_SIZE)
        self._anim = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.home = HomePage()
        self.stack.addWidget(self.home)
        self.pages = {}
        for key, title, _ in config.CATEGORIES:
            page = CardPage(db, key, title)
            page.goHome.connect(self.go_home)
            page.changed.connect(self._on_local_change)
            self.pages[key] = page
            self.stack.addWidget(page)

        self.home.openCategory.connect(self.go_category)
        self.home.openSettings.connect(self.open_settings)

        # 동기화
        self.sync = SyncManager(db, self)
        self.sync.status.connect(self._on_sync_status)
        self.sync.dataChanged.connect(self._on_remote_data)
        buttons = [self.home.sync] + [p.header.sync for p in self.pages.values()]
        for b in buttons:
            b.clicked.connect(lambda: self.sync.sync_now(manual=True))

        # 새 '답변 대기' 알림(토스트)
        self._known_open = db.open_uids()
        self._toast_target = None
        self.toast = QLabel(self)
        self.toast.setObjectName("Toast")
        self.toast.setCursor(Qt.PointingHandCursor)
        self.toast.hide()
        self.toast.mousePressEvent = self._toast_clicked
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast.hide)

        self.resize(self._home_size)
        self.setMinimumSize(*HOME_MIN)
        self._update_alarms()
        self.sync.configure()

    # ---- 화면 전환 ----
    def go_category(self, key: str):
        page = self.pages[key]
        if self.stack.currentWidget() is self.home:
            if not self.isMaximized():
                self._home_size = self.size()
        self.stack.setCurrentWidget(page)
        self.setMinimumSize(*CARD_MIN)
        self._resize_to(self._card_size())
        page.refresh()

    def go_home(self):
        was_card = self.stack.currentWidget() is not self.home
        self.stack.setCurrentWidget(self.home)
        self.setMinimumSize(*HOME_MIN)
        self._update_alarms()
        if was_card:
            self._resize_to(self._home_size)

    def _card_size(self) -> QSize:
        """홈 화면보다 크게, 사진 6장이 화면을 거의 채우도록. 모니터를 넘지 않게 제한."""
        screen = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        w = min(config.INSPECT_MAX_SIZE[0], int(screen.width() * 0.97))
        h = min(config.INSPECT_MAX_SIZE[1], int(screen.height() * 0.95))
        return QSize(w, h)

    def _resize_to(self, size: QSize):
        if self.isMaximized() or self.isFullScreen():
            return
        screen = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        size = QSize(min(size.width(), screen.width()), min(size.height(), screen.height()))
        center = self.geometry().center()
        x = min(max(screen.left(), center.x() - size.width() // 2), screen.right() - size.width() + 1)
        y = min(max(screen.top(), center.y() - size.height() // 2), screen.bottom() - size.height() + 1)
        target = QRect(x, y, size.width(), size.height())
        if not self.isVisible():
            self.setGeometry(target)
            return
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(target)
        self._anim.start()

    # ---- 동기화 ----
    def _on_sync_status(self, state: str, text: str):
        labels = [self.home.sync_lbl] + [p.header.sync_lbl for p in self.pages.values()]
        for lbl in labels:
            lbl.setText(("● " if state in ("ok", "busy", "pending", "error") else "○ ") + text)
            lbl.setToolTip(text)
        buttons = [self.home.sync] + [p.header.sync for p in self.pages.values()]
        for b in buttons:
            b.setEnabled(state != "busy")

    def _on_remote_data(self, _settings_changed: bool):
        self._notify_new_questions()
        self._reload_all()

    def _reload_all(self):
        for p in self.pages.values():
            p.refresh()
        self._update_alarms()

    # ---- 답변 대기 알람 ----
    def _update_alarms(self):
        counts = {key: self.db.count_open(key) for key in self.pages}
        self.home.set_alarms(counts)
        total = sum(counts.values())
        base = config.APP_NAME
        self.setWindowTitle(f"({total}) {base}" if total else base)   # 작업표시줄에서도 보이게

    def _on_local_change(self):
        self._known_open = self.db.open_uids()     # 이 PC 에서 올린 질문은 알림 대상이 아님
        self._update_alarms()

    def _notify_new_questions(self):
        """다른 PC 에서 새 질문이 올라오면 소리 + 작업표시줄 깜박임 + 화면 알림."""
        now_open = self.db.open_uids()
        new = now_open - self._known_open
        self._known_open = now_open
        if not new:
            return
        entries = []
        for key in self.pages:
            entries += [e for e in self.db.list_entries(key) if e["uid"] in new]
        if not entries:
            return
        first = entries[0]
        cat = config.CATEGORY_TITLES.get(first["category"], "")
        if len(entries) == 1:
            text = f"⏳ 新的待解答问题\n[{cat}] {first['title']}"
        else:
            text = f"⏳ 有 {len(entries)} 个新的待解答问题\n最新：[{cat}] {first['title']}"
        self._toast_target = first["category"]
        self.toast.setText(text + "\n（点击查看）")
        self.toast.adjustSize()
        self._place_toast()
        self.toast.show()
        self.toast.raise_()
        self._toast_timer.start(12000)
        QApplication.beep()
        QApplication.alert(self, 0)

    def _place_toast(self):
        self.toast.move(self.width() - self.toast.width() - 24, 24)

    def _toast_clicked(self, _ev):
        self.toast.hide()
        if self._toast_target in self.pages:
            self.go_category(self._toast_target)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "toast") and self.toast.isVisible():
            self._place_toast()

    # ---- 설정 ----
    def open_settings(self):
        if not ask_password(self, self.db, "进入设置需要输入密码"):
            return
        dlg = SettingsDialog(self, self.db, self.sync)
        dlg.fontChanged.connect(lambda pt: theme.apply(QApplication.instance(), pt))
        dlg.dataReplaced.connect(self._reload_all)
        dlg.ratioChanged.connect(self._reload_all)
        dlg.exec()

    def closeEvent(self, ev):
        self.sync.shutdown()
        super().closeEvent(ev)
