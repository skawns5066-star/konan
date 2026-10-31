"""튜닝 시도 로그(logs/tuning_log.csv)로 알고리즘 상태를 점검한다.  사용: python analyze_log.py [로그.csv ...]

· 1차 보정 적중률: 첫 보정(correct) 다음 측정이 목표 ±10 이내(OK)였던 비율 (조명별)
· 실측 지수: 연속된 두 시도에서 ln(GV 비) / ln(앵커 파라미터 비) — 프로그램이 쓴 지수와 비교해 DEFAULT_EXPONENTS 를 고칠 근거로 쓴다
여러 PC 의 로그 파일을 같이 넘기면 합쳐서 분석한다.
"""
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load(paths):
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rows += list(csv.DictReader(f))
    return rows


def cycles(rows):
    """같은 (PC, 모델, 항목, 조명 키)의 시도들을 시간순으로 묶는다."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["pc"], r["model"], r["item"], r["key"])].append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["time"])
        yield g


def analyze(rows):
    hit = defaultdict(lambda: [0, 0])            # (kind, light) -> [다음 측정이 OK 였던 횟수, 보정 횟수]
    obs = defaultdict(list)                       # (kind, light) -> [실측 지수]
    used = defaultdict(list)
    for g in cycles(rows):
        for prev, cur in zip(g, g[1:]):
            if prev["action"] != "correct" or int(cur["attempt"]) != int(prev["attempt"]) + 1:
                continue
            k = (prev["kind"], prev["light"])
            hit[k][1] += 1
            hit[k][0] += cur["gv_ok"] == "1"
            try:
                e = math.log(float(cur["cur_gv"]) / float(prev["cur_gv"])) / math.log(float(prev["anchor_after"]) / float(prev["anchor_before"]))
                if 0 < e < 3:
                    obs[k].append(e)
                    used[k].append(float(prev["exponent"]))
            except (ValueError, ZeroDivisionError):
                pass
    print(f"{'종류':4s} {'조명':4s} {'보정→재측정':>12s} {'1회 보정 적중':>14s} {'실측 지수(중앙값)':>18s} {'사용한 지수':>10s}")
    for k in sorted(hit):
        ok, n = hit[k]
        e = f"{statistics.median(obs[k]):.2f} (n={len(obs[k])})" if obs[k] else "-"
        u = f"{statistics.median(used[k]):.2f}" if used[k] else "-"
        print(f"{k[0]:4s} {k[1]:4s} {n:12d} {100 * ok / n:13.0f}% {e:>18s} {u:>10s}")
    if not hit:
        print("아직 '보정 → 재측정'이 이어진 기록이 없습니다.")


if __name__ == "__main__":
    paths = sys.argv[1:] or [str(Path(__file__).resolve().parent / "logs" / "tuning_log.csv")]
    analyze(load(paths))
