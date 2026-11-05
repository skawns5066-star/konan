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
FONT_DIR = RES_DIR / "fonts"
BACKUP_DIR = APP_DIR / "backups"

CATEGORY_CONTROL = "control"
CATEGORY_INSPECT = "inspect"

DEFAULT_PASSWORD = "0812"

# 창 크기
HOME_SIZE = (1000, 700)           # 시작 / 제어 PC 화면
INSPECT_MAX_SIZE = (1500, 940)    # 검사 PC 화면(작은 모니터면 자동으로 줄어듦)

# 카드 비율 (설정에서 변경)
RATIOS = {"16:9": 16 / 9, "4:3": 4 / 3, "3:2": 3 / 2, "1:1": 1.0}
DEFAULT_RATIO = "16:9"
PAGE_SIZE = 6   # 3열 x 2행

DEFAULT_FONT_PT = 12
MIN_FONT_PT = 9
MAX_FONT_PT = 24

IMAGE_FILTER = "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;所有文件 (*.*)"


def ensure_dirs():
    for d in (DATA_DIR, ORIG_DIR, CROP_DIR):
        d.mkdir(parents=True, exist_ok=True)
