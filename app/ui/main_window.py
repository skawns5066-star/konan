"""메인 창: 시작 화면 ↔ 카테고리 화면 전환, 창 크기 자동 조절, 동기화 상태 표시."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

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

        self.resize(self._home_size)
        self.setMinimumSize(*HOME_MIN)
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
        self._reload_all()

    def _reload_all(self):
        for p in self.pages.values():
            p.refresh()

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
