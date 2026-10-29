"""측정표(xlsx)에서 조명별 GV 반응 지수(e)를 구한다.  사용: python fit_exponents.py 측정표.xlsx          (지수 계산)
      python fit_exponents.py --check 측정표.xlsx   (정확도 검증: 종류별 BT/ABF 비교)

모델: GV ≈ k · Value^e  (로그-로그 기울기 e).  같은 (종류, 조명, 색)의 모든 장비/위치(탑1·탑2·바텀) 측정을
곡선별 기울기의 중앙값으로 합쳐 구한다. 측정 점이 3~4개뿐인 개별 곡선보다 새 파일에 대한 예측 오차가 작다.
결과를 light_spec_core.py 의 DEFAULT_EXPONENTS 에 붙여넣으면 된다. (엑셀 읽기에만 openpyxl 필요)

표 형식: 헤더 칸에 'N호기탑1/탑2/바텀' 또는 'ABF'가 들어 있고, 그 아래 '(탭1)' 행 다음부터
[N번, 색, 측정값들..., 'PARAMETER'(또는 'P')] 행 바로 아래 행이 GV 값 행('GV' 또는 'G').

입력 실수 걸러내기: 파라미터가 더 큰데 GV가 더 낮은(또는 같은) 점은 오입력으로 보고 버린다.
(단조 증가를 가장 많이 남기는 점들만 사용. 어느 점이 틀렸는지 애매하면 같은 조명·색의 다른 곡선 기울기와
가장 비슷해지는 쪽을 남긴다.) 버린 점은 출력에 표시된다.
"""
import itertools
import math
import re
import sys
from collections import defaultdict

BLOCK_COLS = (0, 11, 22)       # 한 줄에 놓인 표 블록의 시작 열
MAX_POINTS = 6


def series_exponent(pts):
    """한 곡선의 로그-로그 최소제곱 기울기."""
    pts = [(p, g) for p, g in pts if p and g and p > 0 and g > 0]
    if len(pts) < 2:
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


def _monotone(pts):
    pts = sorted(pts)
    return all(a[0] < b[0] and a[1] < b[1] for a, b in zip(pts, pts[1:]))


def clean_group(series):
    """같은 (종류, 조명, 색)의 곡선들에서 '파라미터↑ 인데 GV↓' 인 입력 실수 점을 버린다. (정리된 곡선들, 버린 점들) 반환."""
    def candidates(pts):
        pts = sorted(set(pts))
        for k in range(len(pts), 1, -1):
            subs = [list(c) for c in itertools.combinations(pts, k) if _monotone(c)]
            if subs:
                return subs
        return [pts]

    good = [sorted(p) for p in series if _monotone(p)]
    ref = [series_exponent(p) for p in good]
    ref = sorted(e for e in ref if e is not None)
    ref_e = ref[len(ref) // 2] if ref else None
    out, dropped = [], []
    for pts in series:
        if _monotone(pts):
            out.append(sorted(pts))
            continue
        subs = candidates(pts)
        if ref_e is not None and len(subs) > 1:
            subs.sort(key=lambda sub: abs((series_exponent(sub) if len(sub) >= 3 else _two_point(sub)) - ref_e))
        keep = subs[0]
        out.append(keep)
        dropped += [pt for pt in pts if pt not in keep]
    return out, dropped


def _two_point(pts):
    (p1, g1), (p2, g2) = pts[0], pts[-1]
    return math.log(g2 / g1) / math.log(p2 / p1)


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
                if rows[r + 1][c0 + 8] not in ("GV", "G") or not color:
                    break
                if label:
                    light = int(str(label)[0])
                pts = [(rows[r][c0 + 2 + k], rows[r + 1][c0 + 2 + k]) for k in range(MAX_POINTS)
                       if rows[r][c0 + 2 + k] is not None and rows[r + 1][c0 + 2 + k] is not None]
                if len(pts) >= 2:
                    data[(kind, light, str(color)[0].upper())].append(pts)
                r += 2
    return data


def _fit(pts):
    xs = [math.log(p) for p, _ in pts]
    ys = [math.log(g) for _, g in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return b, (lambda p: math.exp(my + b * (math.log(p) - mx)))


def check(path):
    """정확도 검증. 각 곡선의 한 점에서 다른 점의 GV로 맞추라고 할 때(모든 점 쌍),
    지수는 **같은 조명·색의 다른 곡선들**에서만 구한다(그 곡선은 계산에 쓰지 않음 = 공정 검증).
      · 예측 오차: 계산식이 예측한 GV 와 실제 측정 GV 의 차이
      · 1회 보정: calc_new_value 로 구한 새 파라미터의 (곡선 회귀 기준) GV 가 목표 ±10 이내인 비율
    """
    import light_spec_core as core
    data = read_sheet(path)
    stats = defaultdict(lambda: {"n": 0, "err": 0.0, "hit": 0, "shot": 0, "curves": 0})
    for (kind, light, color), series in data.items():
        series, dropped = clean_group(series)
        for i, pts in enumerate(series):
            others = [e for j, o in enumerate(series) if j != i and len(o) >= 2 for e in [series_exponent(o)] if e is not None]
            if len(pts) < 2 or not others:
                continue
            others.sort()
            e = max(others[len(others) // 2] if len(others) % 2 else (others[len(others) // 2 - 1] + others[len(others) // 2]) / 2,
                    core.MIN_EXPONENT)
            _, curve = _fit(pts)
            st = stats[kind]
            st["curves"] += 1
            for (pi, gi), (pj, gj) in itertools.permutations(pts, 2):
                d = abs(gi * (pj / pi) ** e - gj)
                new = core.calc_new_value(pi, curve(pi), gj, e)
                st["n"] += 1
                st["err"] += d
                st["hit"] += d <= 10
                st["shot"] += abs(curve(new) - gj) <= 10
    for kind, st in sorted(stats.items()):
        n = st["n"]
        print(f"{kind:4s} 곡선 {st['curves']:2d}개 / 시도 {n:3d}회 | 예측오차 평균 {st['err'] / n:4.1f} GV, ±10 이내 {100 * st['hit'] / n:3.0f}% "
              f"| 1회 보정 후 ±10 이내 {100 * st['shot'] / n:3.0f}%")


def main(path):
    data = read_sheet(path)
    print("# light_spec_core.py DEFAULT_EXPONENTS 에 붙여넣기: (종류, Page index = 조명번호-1, 색): 지수")
    for (kind, light, color), series in sorted(data.items()):
        series, dropped = clean_group(series)
        e = pooled_exponent(series)
        if e is not None:
            note = f", 입력 실수로 버린 점 {dropped}" if dropped else ""
            print(f'    ("{kind}", {light - 1}, "{color}"): {e:.2f},   # {light}번 {color}, 곡선 {len(series)}개 / 점 {sum(map(len, series))}개{note}')


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        check(sys.argv[2])
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        sys.exit(__doc__)
