"""폰트 로드와 전체 스타일(QSS). 글자색은 전부 검은색, 글자 크기는 설정에서 조절."""
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

from . import config

UI_FAMILIES = ["Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
               "WenQuanYi Zen Hei", "Noto Sans CJK SC", "Segoe UI", "sans-serif"]
TC_FAMILIES = ["Noto Sans TC", "Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC",
               "Noto Sans CJK TC", "WenQuanYi Zen Hei", "sans-serif"]

BG = "#F4F6FA"
BORDER = "#D5DDEA"
ACCENT = "#CFE3FF"        # 연한 파랑 (검은 글자가 잘 보이도록 진한 색은 쓰지 않음)
ACCENT_HOVER = "#B9D6FF"
ACCENT_LINE = "#8DB8F2"


def load_fonts() -> list:
    """fonts/ 폴더의 글꼴을 앱에 등록 (번체/간체 모두 깨지지 않게 프로그램에 포함)."""
    loaded = []
    if config.FONT_DIR.exists():
        for f in sorted(config.FONT_DIR.iterdir()):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                fid = QFontDatabase.addApplicationFont(str(f))
                if fid >= 0:
                    loaded += QFontDatabase.applicationFontFamilies(fid)
    return loaded


def _fam(families) -> str:
    return ", ".join(f'"{f}"' if " " in f else f for f in families)


def build_qss(pt: int) -> str:
    k = pt / 12.0

    def px(n):
        return max(1, round(n * k))

    def sz(f):
        return f"{pt * f:.1f}pt"

    return f"""
* {{ color: #000000; }}
QWidget {{ font-family: {_fam(UI_FAMILIES)}; font-size: {pt}pt; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Page {{ background: {BG}; }}
QLabel {{ background: transparent; }}
QLabel#Title {{ font-size: {sz(1.9)}; font-weight: 700; }}
QLabel#HomeTitle {{ font-size: {sz(2.6)}; font-weight: 700; }}
QLabel#Subtitle {{ font-size: {sz(1.05)}; }}
QLabel#Section {{ font-size: {sz(1.1)}; font-weight: 700; }}
QLabel#Empty {{ font-size: {sz(1.15)}; }}
QLabel#TcTitle {{ font-family: {_fam(TC_FAMILIES)}; font-size: {sz(1.5)}; font-weight: 700; }}
QLabel#CardTitle {{ font-family: {_fam(TC_FAMILIES)}; font-size: {sz(1.0)}; font-weight: 600; }}
QLabel#HomeCardTitle {{ font-size: {sz(2.0)}; font-weight: 700; }}
QLabel#HomeCardDesc {{ font-size: {sz(1.0)}; }}

QPushButton {{
    background: #FFFFFF; border: 1px solid #C3CCDA; border-radius: {px(9)}px;
    padding: {px(7)}px {px(18)}px; min-height: {px(20)}px;
}}
QPushButton:hover {{ background: #EEF3FB; }}
QPushButton:pressed {{ background: #E1EAF7; }}
QPushButton:disabled {{ color: #8A8F98; background: #F0F2F6; }}
QPushButton:checked {{ background: {ACCENT}; border: 1px solid {ACCENT_LINE}; }}
QPushButton#Primary {{ background: {ACCENT}; border: 1px solid {ACCENT_LINE}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Danger {{ background: #FFDADA; border: 1px solid #EFA3A3; }}
QPushButton#Danger:hover {{ background: #FFC6C6; }}
QPushButton#Flat {{ background: transparent; border: 1px solid transparent; }}
QPushButton#Flat:hover {{ background: #E4EBF6; }}
QPushButton#HomeCard {{
    background: #FFFFFF; border: 2px solid {BORDER}; border-radius: {px(26)}px;
}}
QPushButton#HomeCard:hover {{ background: #F1F7FF; border: 2px solid {ACCENT_LINE}; }}
QPushButton#HomeCard:pressed {{ background: #E3EEFF; }}

QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox {{
    background: #FFFFFF; border: 1px solid #C3CCDA; border-radius: {px(9)}px;
    padding: {px(7)}px {px(10)}px; selection-background-color: #BBD7FF; selection-color: #000000;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 1px solid #5B9BFF; }}
QLineEdit#Search {{ border-radius: {px(20)}px; padding: {px(9)}px {px(16)}px; font-size: {sz(1.1)}; }}
QLineEdit#TcInput {{ font-family: {_fam(TC_FAMILIES)}; }}
QTextEdit#Solution, QTextBrowser#Solution {{ font-size: {sz(1.05)}; }}

QListWidget {{
    background: #FFFFFF; border: 1px solid {BORDER}; border-radius: {px(14)}px;
    padding: {px(6)}px; outline: 0;
}}
QListWidget::item {{ padding: {px(10)}px {px(12)}px; border-radius: {px(8)}px; margin: {px(1)}px 0; }}
QListWidget::item:hover {{ background: #EEF4FF; color: #000000; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #000000; }}

QFrame#Panel {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: {px(14)}px; }}
QFrame#PhotoCard {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: {px(14)}px; }}
QFrame#PhotoCard:hover {{ border: 2px solid #7FB0F5; }}

QScrollBar:vertical {{ background: transparent; width: {px(12)}px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C5CEDC; border-radius: {px(5)}px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #A9B6CA; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {px(12)}px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C5CEDC; border-radius: {px(5)}px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{ color: #000000; background: #FFFBE6; border: 1px solid #999999; padding: 4px; }}
QMessageBox QLabel {{ min-width: {px(260)}px; }}
"""


def apply(app, pt: int):
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPointSize(pt)
    app.setFont(font)
    pal = QPalette(app.palette())
    black = QColor("#000000")
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText, QPalette.ToolTipText,
                 QPalette.HighlightedText):
        pal.setColor(role, black)
    pal.setColor(QPalette.PlaceholderText, QColor("#5A5F68"))
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.Base, QColor("#FFFFFF"))
    app.setPalette(pal)
    app.setStyleSheet(build_qss(pt))
