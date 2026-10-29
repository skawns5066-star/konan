"""조명(GV) 파라미터 XML(LightSpec) 파싱 / 보정 계산 / 저장 (GUI 비의존 로직).

구조: <LightSet><Page Index=0..2 Enable=..><Channel Index Value Angle Color Enable/></Page></LightSet>
  - Page Index 0/1/2 = 1/2/3번 조명. Page 또는 Channel 의 Enable=0 이면 사용 안 함.
  - 같은 각도·색의 채널이 좌/우로 2개씩 있으므로(예: 30° 두 개) 한 항목으로 묶어 같이 바꾼다.
  - 저장은 Value="..." 숫자만 제자리 치환하므로 나머지 XML(주석, 탭, 줄바꿈, 인코딩)은 그대로 보존된다.
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
DEFAULT_TARGET = 100    # 목표 GV 기본값 (프리셋/각도/행별로 수정 가능)
MAX_STEP = 3.0          # 1회 보정에서 파라미터를 바꿀 수 있는 최대 배율(과보정 방지)
MAX_VALUE = 1024        # 샘플 XML에서 확인되는 Value 최대값
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
    set_index: int
    page: int
    value: float
    angle: int
    color: str
    enable: bool          # Page Enable 와 Channel Enable 가 모두 1일 때 True
    line_no: int
    span: tuple           # 원본 줄에서 Value 숫자의 (시작, 끝)
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


_LIGHTSET = re.compile(r"<LightSet\b[^>]*?\bIndex\s*=\s*\"(\d+)\"")
_PAGE = re.compile(r"<Page\b([^>]*)>")
_CHANNEL = re.compile(r"<Channel\b([^>]*)>")
_ATTR = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")


def _read_text(path):
    raw = Path(path).read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")      # BOM 유무까지 그대로 보존
    for enc in ("utf-8-sig" if bom else "utf-8", "cp949"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def parse_text(text, path="", encoding="utf-8"):
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    rows, set_idx, page, page_on = [], 0, 0, True
    for i, line in enumerate(lines):
        m = _LIGHTSET.search(line)
        if m:
            set_idx = int(m.group(1))
        m = _PAGE.search(line)
        if m:
            at = dict(_ATTR.findall(m.group(1)))
            page, page_on = int(at.get("Index", page)), at.get("Enable", "1") != "0"
        for m in _CHANNEL.finditer(line):
            body = m.group(1)
            at = dict(_ATTR.findall(body))
            color = at.get("Color", "")[:1].upper()
            try:
                value = float(at["Value"])
                angle = int(float(at["Angle"]))
            except (KeyError, ValueError):
                continue
            if color not in COLORS:
                continue
            vm = re.search(r"\bValue\s*=\s*\"([^\"]*)\"", body)
            start = m.start(1) + vm.start(1)
            rows.append(LightRow(set_idx, page, int(value) if value == int(value) else value, angle, color,
                                 page_on and at.get("Enable", "1") != "0", i, (start, start + len(vm.group(1)))))
    return ParsedFile(path, lines, rows, encoding, newline)


def parse_file(path):
    text, enc = _read_text(path)
    return parse_text(text, path, enc)


def find_item_file(model_dir, item, kind=None):
    """모델 폴더에서 항목에 해당하는 XML 탐색.

    1) 항목명과 같은 파일(확장자/대소문자 무시)  2) 항목명과 같은 하위 폴더 안의 LightSpec XML
    3) 항목명이 없거나 못 찾으면 LightSpec*{BT|ABF}*.xml 이 모델 폴더에 하나뿐일 때 그 파일
    """
    d = Path(model_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"모델 폴더가 없습니다: {d}")

    def xmls(folder):
        return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".xml")

    def of_kind(ps):
        return [p for p in ps if kind and kind.lower() in p.name.lower()]

    low = item.strip().lower()
    for p in sorted(d.iterdir()):
        if p.is_file() and not re.search(r"\.bak_\d", p.name) and low in (p.name.lower(), p.stem.lower()):
            return str(p)
    for sub in sorted(x for x in d.iterdir() if x.is_dir() and x.name.lower() == low):
        cands = xmls(sub)
        cands = of_kind(cands) or cands
        if len(cands) == 1:
            return str(cands[0])
    cands = of_kind(xmls(d))
    if len(cands) == 1:
        return str(cands[0])
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

    cands = {min(MAX_VALUE, max(0, math.floor(exact))), min(MAX_VALUE, max(0, math.ceil(exact)))}
    best = min(cands, key=lambda p: abs(predicted(p) - target))
    if best == cur_param and abs(cur_gv - target) > 0:
        best = cur_param + (1 if target > cur_gv else -1)
        best = min(max(best, 0), MAX_VALUE)
    return int(best)


@dataclass
class Entry:
    """화면 표의 한 줄 = 함께 보정되는 채널 묶음.

    BT : 같은 (조명, 각도, 색)의 좌/우 채널 묶음. ABF : 같은 (조명, 각도)의 모든 색 채널 묶음.
    ref(GV 기준 채널; ABF는 Green, 없으면 W)의 새 값을 구한 뒤 묶음 전체에 같은 비율을 적용한다.
    """
    kind: str
    set_index: int
    page: int
    angle: int
    rows: list
    ref: LightRow
    target: float = DEFAULT_TARGET
    cur_gv: float = None
    manual_ok: bool = False

    @property
    def key(self):
        return f"{self.set_index}|{self.page}|{self.angle}|{self.ref.color}"

    @property
    def ok(self):
        return self.manual_ok or (self.cur_gv is not None and is_ok(self.cur_gv, self.target))

    def param(self, color):
        """표시용 현재 파라미터. 좌/우 값이 다르면 '120/210' 처럼 모두 표시, 해당 색이 없으면 None."""
        vals = []
        for r in self.rows:
            if r.color == color and r.value not in vals:
                vals.append(r.value)
        return "/".join(str(v) for v in vals) if vals else None


def default_presets():
    """미리 만들어 두는 4개 프리셋. 이름·목표·각도별 목표는 화면에서 바꿀 수 있고 추가도 가능하다."""
    return [{"id": f"{k.lower()}_{pos.lower()}", "kind": k, "name": f"{k} {pos}", "target": DEFAULT_TARGET,
             "angle_targets": {}, "file": ""}
            for k in ("BT", "ABF") for pos in ("Top", "Bottom")]


def build_entries(kind, parsed, targets=None, default_target=DEFAULT_TARGET, angle_targets=None):
    """사용 중(Page·Channel Enable=1)인 채널만 화면 항목으로 만든다."""
    groups = {}
    for r in parsed.rows:
        if r.enable:
            k = (r.set_index, r.page, r.angle) + (() if kind == "ABF" else (COLORS.index(r.color),))
            groups.setdefault(k, []).append(r)
    entries = []
    for k, rows in sorted(groups.items()):
        ref = rows[0]
        if kind == "ABF":
            ref = next((r for r in rows if r.color == "G"), next((r for r in rows if r.color == "W"), rows[0]))
        entries.append(Entry(kind, k[0], k[1], k[2], rows, ref))
    for e in entries:
        # 우선순위: 행별 저장값 > 각도별 목표 > 프리셋 기본 목표
        e.target = (targets or {}).get(e.key, (angle_targets or {}).get(e.angle, default_target))
    return entries


def apply_corrections(entries, exponents=None):
    """OK가 아니고 현재 GV가 입력된 항목의 new_value를 채운다. 변경된 항목 수 반환."""
    changed = 0
    for e in entries:
        if e.ok or e.cur_gv is None or e.ref.value <= 0:
            continue
        exp = exponent_for(e.kind, e.page, e.ref.color, exponents)
        new_ref = calc_new_value(e.ref.value, e.cur_gv, e.target, exp)
        if new_ref == e.ref.value:
            continue
        ratio = new_ref / e.ref.value
        for r in e.rows:
            if r is e.ref or r.value == 0:
                continue
            r.new_value = min(MAX_VALUE, max(1, round(r.value * ratio)))
        e.ref.new_value = new_ref
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
