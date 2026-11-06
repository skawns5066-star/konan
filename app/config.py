"""전역 설정값과 경로. 데이터는 항상 프로그램 폴더의 data/ 아래에 저장된다."""
import os
import sys
from pathlib import Path

APP_NAME = "设备故障解决指南"

FROZEN = getattr(sys, "frozen", False)
# exe 로 빌드되면 exe 옆, 개발 중에는 프로젝트 루트
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
# 번들 리소스(폰트 등) 위치
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))

DATA_DIR = Path(os.environ.get("GUIDE_DATA_DIR", APP_DIR / "data"))
DB_PATH = DATA_DIR / "guide.db"
IMG_DIR = DATA_DIR / "images"
ORIG_DIR = IMG_DIR / "original"
CROP_DIR = IMG_DIR / "cropped"
SOL_DIR = IMG_DIR / "solution"      # 해결 방법에 첨부한 사진
FONT_DIR = RES_DIR / "fonts"
BACKUP_DIR = APP_DIR / "backups"

# 카테고리: (key, 화면 제목, 홈 버튼 설명). 4개 모두 동일한 UI(사진 카드 3x2 + 크롭)를 쓴다.
CATEGORIES = [
    ("strip", "条状控制PC问题", "查看 / 登记条状控制PC的故障"),
    ("single", "单颗控制PC问题", "查看 / 登记单颗控制PC的故障"),
    ("sorter", "Sorter控制PC问题", "查看 / 登记Sorter控制PC的故障"),
    ("inspect", "检测程序PC问题", "查看 / 登记检测程序PC的故障"),
]
CATEGORY_TITLES = {k: t for k, t, _ in CATEGORIES}
LEGACY_CATEGORY_MAP = {"control": "strip"}   # 이전 버전의 '控制PC' 데이터는 '条状'으로 이전

DEFAULT_PASSWORD = "0812"

# 창 크기
HOME_SIZE = (1000, 700)           # 시작 화면
INSPECT_MAX_SIZE = (1500, 940)    # 검사 PC 화면(작은 모니터면 자동으로 줄어듦)

# 카드 비율 (설정에서 변경)
RATIOS = {"16:9": 16 / 9, "4:3": 4 / 3, "3:2": 3 / 2, "1:1": 1.0}
DEFAULT_RATIO = "16:9"
STATUS_OPEN = "open"        # 해결 방법을 아직 모름 → 답변 대기 (알람 표시)
STATUS_SOLVED = "solved"    # 해결 방법 등록됨
PAGE_SIZE = 6   # 3열 x 2행

DEFAULT_FONT_PT = 12
MIN_FONT_PT = 9
MAX_FONT_PT = 24

IMAGE_FILTER = "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;所有文件 (*.*)"


def ensure_dirs():
    for d in (DATA_DIR, ORIG_DIR, CROP_DIR, SOL_DIR):
        d.mkdir(parents=True, exist_ok=True)

# 동기화 기본값
SYNC_INTERVALS = [5, 10, 30, 60]   # 초
DEFAULT_SYNC_INTERVAL = 10
