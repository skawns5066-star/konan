"""조명(GV) 파라미터 파일 파싱 / 보정 계산 / 저장 (GUI 비의존 로직).

파일 한 행 = `Page index(0~2), Value, Angle, Color, Enable`
  - 구분자는 쉼표/탭/세미콜론/공백 모두 허용, `Value=12` 처럼 `키=값` 표기도 허용.
  - 5개 필드면 첫 필드가 Page index, 4개 필드면 직전의 `Page index N` 헤더 행을 따른다.
  - 파일 형식이 다르면 `parse_file` 한 곳만 고치면 된다. 저장은 Value 토큰만 제자리 치환하므로
    나머지 줄 내용/줄바꿈/인코딩은 그대로 보존된다.
"""
import json
import math
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BASE_DIR = r"D:\PxInventory\LIGHT_SPEC"
TOLERANCE = 10          # 목표 GV ± 10 이내면 OK
DEFAULT_TARGET = 150    # 목표 GV 기본값 (화면에서 행별로 수정/저장 가능)
MAX_STEP = 3.0          # 1회 보정에서 파라미터를 바꿀 수 있는 최대 배율(과보정 방지)
MIN_EXPONENT = 0.25     # 포화되는 조명에서 지수가 0에 가까워 폭주하는 것을 방지

ANGLES = {"BT": (0, 30, 60), "ABF": (0, 30, 60, 75)}
COLORS = ("W", "R", "G", "B")

# 조명 반응 모델: GV ≈ k * Value^e  (로그-로그 기울기 e).
# 첨부 측정표(측정 1~3회차)의 조명/색상별 기울기를 [MIN_EXPONENT, 1.0]로 제한한 초기값.
# 실측에 맞춰 설정 파일(light_gv_tool.json)의 "exponents"로 덮어쓸 수 있다.
DEFAULT_EXPONENT = 0.5
DEFAULT_EXPONENTS = {
    ("BT", 0, "R"): 0.58, ("BT", 0, "W"): 0.58,
    ("BT", 1, "R"): 0.25, ("BT", 1, "G"): 0.74, ("BT", 1, "B"): 0.25,
    ("BT", 2, "R"): 0.46, ("BT", 2, "G"): 0.48, ("BT", 2, "B"): 0.25,
    ("ABF", 0, "G"): 0.27, ("ABF", 1, "G"): 0.95, ("ABF", 2, "G"): 0.25,
}


@dataclass
class LightRow:
    page: int
    value: float
    angle: int
    color: str
    enable: bool
    line_no: int
    span: tuple          # 원본 줄에서 Value 토큰의 (시작, 끝)
    new_value: float = None

    @property
    def light(self):
        return self.page + 1   # Page index 0 = 1번 조명


@dataclass
class ParsedFile:
    path: str
    lines: list
    rows: list
    encoding: str
    newline: str


_TOKEN = re.compile(r"[^,\t;\s]+")
_PAGE_HEADER = re.compile(r"\[?\s*page\s*index\s*[=:]?\s*(\d+)\s*\]?", re.I)


def _val(tok):
    return tok.split("=")[-1].strip()


def _read_text(path):
    raw = Path(path).read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")      # BOM 유무까지 그대로 보존
    for enc in ("utf-8-sig" if bom else "utf-8", "cp949"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def parse_text(text, path="", encoding="utf-8-sig"):
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    rows, page = [], 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith(("#", "//", ";")):
            continue
        m = _PAGE_HEADER.fullmatch(s)
        if m:
            page = int(m.group(1))
            continue
        toks = list(_TOKEN.finditer(line))
        if len(toks) > 2 and toks[0].group().lower() == "page" and toks[1].group().lower().startswith("index"):
            toks = toks[2:]     # "Page index 0, 100, 30, R, 1" 형태
        if len(toks) not in (4, 5):
            continue
        vals = [_val(t.group()) for t in toks]
        try:
            if len(vals) == 5:
                pg, rest, rest_tok = int(float(vals[0])), vals[1:], toks[1:]
            else:
                pg, rest, rest_tok = page, vals, toks
            value = float(rest[0])
            angle = int(re.sub(r"\D", "", rest[1]) or "x")
            color = rest[2][:1].upper()
            enable = int(float(rest[3])) != 0
        except ValueError:
            continue
        if color not in COLORS:
            continue
        v_tok = rest_tok[0]
        key = v_tok.group().rfind("=")
        start = v_tok.start() + (key + 1 if key >= 0 else 0)
        rows.append(LightRow(pg, int(value) if value == int(value) else value,
                             angle, color, enable, i, (start, v_tok.end())))
    return ParsedFile(path, lines, rows, encoding, newline)


def parse_file(path):
    text, enc = _read_text(path)
    return parse_text(text, path, enc)


def find_item_file(model_dir, item):
    """모델 폴더에서 항목명에 해당하는 파일 탐색 (정확히 일치 -> 확장자 무시 -> 대소문자 무시)."""
    d = Path(model_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"모델 폴더가 없습니다: {d}")
    files = [p for p in d.iterdir() if p.is_file() and not re.search(r"\.bak_\d", p.name)]
    for match in (lambda p: p.name == item,
                  lambda p: p.stem == item,
                  lambda p: p.name.lower() == item.lower(),
                  lambda p: p.stem.lower() == item.lower()):
        for p in sorted(files):
            if match(p):
                return str(p)
    raise FileNotFoundError(f"'{item}' 파일을 찾을 수 없습니다: {d}")


def save_file(parsed, backup):
    """new_value가 지정된 행의 Value만 제자리 치환해 저장. 백업 파일 경로(없으면 None) 반환."""
    lines = list(parsed.lines)
    for r in sorted(parsed.rows, key=lambda r: r.line_no):
        if r.new_value is None:
            continue
        line, (a, b) = lines[r.line_no], r.span
        nv = int(r.new_value) if r.new_value == int(r.new_value) else r.new_value
        lines[r.line_no] = line[:a] + str(nv) + line[b:]
    bak = None
    if backup:
        bak = f"{parsed.path}.bak_{datetime.now():%Y%m%d_%H%M%S}"
        shutil.copy2(parsed.path, bak)
    text = parsed.newline.join(lines) + parsed.newline
    Path(parsed.path).write_bytes(text.encode(parsed.encoding))
    return bak


# ---------------------------------------------------------------- 보정 계산
def exponent_for(kind, page, color, overrides=None):
    key = (kind, page, color)
    if overrides and key in overrides:
        return max(overrides[key], MIN_EXPONENT)
    e = DEFAULT_EXPONENTS.get(key) or DEFAULT_EXPONENTS.get((kind, page, "G"), DEFAULT_EXPONENT)
    return max(e, MIN_EXPONENT)


def is_ok(cur_gv, target, tol=TOLERANCE):
    return abs(cur_gv - target) <= tol


def calc_new_value(cur_param, cur_gv, target, exponent):
    """GV = k*P^e 모델을 로그 공간에서 풀어 새 파라미터(정수)를 구한다.

    덧셈(+N)이 아니라 비율로 계산하므로 베이스가 작은 값(예: 4)과 큰 값(예: 300)에서
    같은 보정량이 극단적으로 다른 영향을 주는 문제가 생기지 않는다. 정수 반올림 시에는
    floor/ceil 중 예측 GV가 목표에 더 가까운 쪽을 고르고, 허용 오차를 벗어났다면 최소 ±1은 움직인다.
    """
    if cur_gv <= 0 or target <= 0:
        return cur_param
    if cur_param <= 0:   # 0이면 비율 계산 불가 -> 상승 시 1부터 시작
        return 1 if target > cur_gv else 0
    ratio = (target / cur_gv) ** (1.0 / exponent)
    ratio = min(max(ratio, 1.0 / MAX_STEP), MAX_STEP)
    exact = cur_param * ratio

    def predicted(p):
        return cur_gv * (max(p, 1e-9) / cur_param) ** exponent

    cands = {max(0, math.floor(exact)), max(0, math.ceil(exact))}
    best = min(cands, key=lambda p: abs(predicted(p) - target))
    if best == cur_param and abs(cur_gv - target) > 0:
        best = cur_param + (1 if target > cur_gv else -1)
        best = max(best, 0)
    return int(best)


@dataclass
class Entry:
    """화면 표의 한 줄. BT: 파일 한 행, ABF: (조명, 각도) 묶음(R/G/B/W 동시 보정)."""
    kind: str
    page: int
    angle: int
    rows: list
    ref: LightRow                 # GV 기준 행 (ABF는 Green)
    target: float = DEFAULT_TARGET
    cur_gv: float = None
    manual_ok: bool = False

    @property
    def key(self):
        return f"{self.page}|{self.angle}|{self.ref.color}"

    @property
    def ok(self):
        return self.manual_ok or (self.cur_gv is not None and is_ok(self.cur_gv, self.target))

    def param(self, color):
        for r in self.rows:
            if r.color == color:
                return r.value
        return None


def build_entries(kind, parsed, targets=None, default_target=DEFAULT_TARGET):
    """Enable=1 행만 화면 항목으로 만든다."""
    enabled = [r for r in parsed.rows if r.enable]
    entries = []
    if kind == "ABF":
        groups = {}
        for r in enabled:
            groups.setdefault((r.page, r.angle), []).append(r)
        for (page, angle), rows in sorted(groups.items()):
            ref = next((r for r in rows if r.color == "G"), rows[0])   # 기준은 Green
            entries.append(Entry(kind, page, angle, rows, ref))
    else:
        entries = [Entry(kind, r.page, r.angle, [r], r) for r in sorted(
            enabled, key=lambda r: (r.page, r.angle, COLORS.index(r.color)))]
    for e in entries:
        e.target = (targets or {}).get(e.key, default_target)
    return entries


def apply_corrections(entries, exponents=None):
    """OK가 아니고 현재 GV가 입력된 항목의 new_value를 채운다. 변경된 항목 수 반환."""
    changed = 0
    for e in entries:
        if e.ok or e.cur_gv is None:
            continue
        exp = exponent_for(e.kind, e.page, e.ref.color, exponents)
        new_ref = calc_new_value(e.ref.value, e.cur_gv, e.target, exp)
        if new_ref == e.ref.value:
            continue
        ratio = new_ref / e.ref.value if e.ref.value else None
        e.ref.new_value = new_ref
        for r in e.rows:          # ABF: R/G/B(/W) 동일 비율로 동시 변경 (색 균형 유지)
            if r is e.ref:
                continue
            if ratio is None or r.value == 0:
                continue
            r.new_value = max(1, round(r.value * ratio))
        changed += 1
    return changed


# ---------------------------------------------------------------- 설정 저장
def config_path():
    return Path(os.path.expanduser("~")) / "light_gv_tool.json"


def load_config():
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        config_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
