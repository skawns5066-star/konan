"""설비 오류 해결 가이드 - 진입점"""
import sys

from PySide6.QtWidgets import QApplication

from app import config, theme
from app.db import Database
from app.ui.main_window import MainWindow


def main():
    config.ensure_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    theme.load_fonts()
    db = Database()
    theme.apply(app, db.font_pt)
    win = MainWindow(db)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
