"""측정표(xlsx)에서 조명별 GV 반응 지수(e)를 구한다.  사용: python fit_exponents.py 측정표.xlsx

모델: GV ≈ k · Value^e  (로그-로그 기울기 e).  같은 (종류, 조명, 색)의 모든 장비/위치(탑1·탑2·바텀) 측정을
곡선별 기울기의 중앙값으로 합쳐 구한다. 측정 점이 3~4개뿐인 개별 곡선보다 새 파일에 대한 예측 오차가 작다.
결과를 light_spec_core.py 의 DEFAULT_EXPONENTS 에 붙여넣으면 된다. (엑셀 읽기에만 openpyxl 필요)

표 형식: 헤더 칸에 'N호기탑1/탑2/바텀' 또는 'ABF'가 들어 있고, 그 아래 '(탭1)' 행 다음부터
[N번, 색, 측정값들..., 'PARAMETER'] 행 바로 아래 행이 GV 값 행('GV').
"""
import math
import re
import sys
from collections import defaultdict

BLOCK_COLS = (0, 11, 22)       # 한 줄에 놓인 표 블록의 시작 열
MAX_POINTS = 6


def series_exponent(pts):
    """한 곡선의 로그-로그 최소제곱 기울기."""
    pts = [(p, g) for p, g in pts if p and g and p > 0 and g > 0]
    if len(pts) < 3:
        return None
    xs = [math.log(p) for p, _ in pts]
    ys = [math.log(g) for _, g in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


def pooled_exponent(series):
    """같은 (종류, 조명, 색)의 곡선들(탑1·탑2·바텀 등)을 하나의 지수로 합친다: 곡선별 기울기의 **중앙값**.

    점이 3~4개뿐인 곡선은 측정 오차(GV ±5)에 기울기가 크게 흔들리고, 값 범위가 넓은 곡선 하나가
    전체를 끌고 가기 쉽다. 중앙값은 그런 이상치에 강해서 새 데이터에 대한 1회 보정 적중률이 가장 높았다.
    """
    es = sorted(e for e in (series_exponent(pts) for pts in series) if e is not None)
    if not es:
        return None
    n = len(es)
    return es[n // 2] if n % 2 else (es[n // 2 - 1] + es[n // 2]) / 2


def read_sheet(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).active
    rows = [[c.value for c in r] for r in ws.iter_rows()]
    data = defaultdict(list)           # (kind, light, color) -> [[(Value, GV), ...], ...]
    for r0, row in enumerate(rows):
        for c0 in BLOCK_COLS:
            head = str(row[c0] or "") if c0 < len(row) else ""
            kind = "ABF" if "ABF" in head.upper() else ("BT" if re.search(r"\d호기(탑|바텀)", head) else None)
            if not kind:
                continue
            light, r = None, r0 + 2
            while r + 1 < len(rows) and c0 + 8 < len(rows[r]):
                label, color = rows[r][c0], rows[r][c0 + 1]
                if rows[r + 1][c0 + 8] != "GV" or not color:
                    break
                if label:
                    light = int(str(label)[0])
                pts = [(rows[r][c0 + 2 + k], rows[r + 1][c0 + 2 + k]) for k in range(MAX_POINTS)
                       if rows[r][c0 + 2 + k] is not None and rows[r + 1][c0 + 2 + k] is not None]
                if len(pts) >= 2:
                    data[(kind, light, str(color)[0].upper())].append(pts)
                r += 2
    return data


def main(path):
    data = read_sheet(path)
    print("# light_spec_core.py DEFAULT_EXPONENTS 에 붙여넣기: (종류, Page index = 조명번호-1, 색): 지수")
    for (kind, light, color), series in sorted(data.items()):
        e = pooled_exponent(series)
        if e is not None:
            print(f'    ("{kind}", {light - 1}, "{color}"): {e:.2f},   # {light}번 {color}, 곡선 {len(series)}개 / 점 {sum(map(len, series))}개')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
