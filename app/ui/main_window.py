"""메인 창: 시작/제어/검사 화면 전환과 창 크기 자동 조절."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from .. import config, theme
from .control_page import ControlPage
from .dialogs.settings_dialog import SettingsDialog
from .home_page import HomePage
from .inspect_page import InspectPage

HOME, CONTROL, INSPECT = 0, 1, 2


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
        self.control = ControlPage(db)
        self.inspect = InspectPage(db)
        for p in (self.home, self.control, self.inspect):
            self.stack.addWidget(p)

        self.home.openControl.connect(lambda: self.go(CONTROL))
        self.home.openInspect.connect(lambda: self.go(INSPECT))
        self.home.openSettings.connect(self.open_settings)
        self.control.goHome.connect(lambda: self.go(HOME))
        self.inspect.goHome.connect(lambda: self.go(HOME))

        self.resize(self._home_size)
        self.setMinimumSize(820, 560)

    # ---- 화면 전환 ----
    def go(self, page: int):
        was_inspect = self.stack.currentIndex() == INSPECT
        self.stack.setCurrentIndex(page)
        if page == INSPECT:
            if not was_inspect:
                self._home_size = self.size() if not self.isMaximized() else self._home_size
            self.setMinimumSize(1000, 680)
            self._resize_to(self._inspect_size())
            self.inspect.refresh()
        else:
            self.setMinimumSize(820, 560)
            if was_inspect:
                self._resize_to(self._home_size)
            if page == CONTROL:
                self.control.refresh()

    def _inspect_size(self) -> QSize:
        """제어 화면보다 크게(약 +30% 이상), 단 모니터를 넘지 않게."""
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

    # ---- 설정 ----
    def open_settings(self):
        dlg = SettingsDialog(self, self.db)
        dlg.fontChanged.connect(lambda pt: theme.apply(QApplication.instance(), pt))
        dlg.dataReplaced.connect(self._reload_all)
        dlg.ratioChanged.connect(self._reload_all)
        dlg.exec()

    def _reload_all(self):
        self.control.refresh()
        self.inspect.refresh()
