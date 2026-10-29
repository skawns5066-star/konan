"""조명(GV) 파라미터 XML(LightSpec) 파싱 / 보정 계산 / 저장 (GUI 비의존 로직).

구조: <LightSet><Page Index=0..2 Enable=..><Channel Index Value Angle Color Enable/></Page></LightSet>
  - Page Index 0/1/2 = 1/2/3번 조명. Page 또는 Channel 의 Enable=0 이면 사용 안 함.
  - 같은 각도·색의 채널이 좌/우로 2개씩 있으므로(예: 30° 두 개) 한 항목으로 묶어 같이 바꾼다.
  - 저장은 Value="..." 숫자만 제자리 치환하므로 나머지 XML(주석, 탭, 줄바꿈, 인코딩)은 그대로 보존된다.
"""
import hashlib
import hmac
import json
import math
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VERSION = "2026.10.29-5"   # 프로그램 파일(5개)이 모두 같은 버전인지 확인용. 수정할 때마다 세 파일을 같이 올린다.
BASE_DIR = r"D:\PxInventory\LIGHT_SPEC"
TOLERANCE = 10          # 목표 GV ± 10 이내면 OK
DEFAULT_TARGET = 100    # 목표 GV 기본값 (프리셋/각도/행별로 수정 가능)
MAX_VALUE = 1024        # 샘플 XML에서 확인되는 Value 최대값
MIN_EXPONENT = 0.08     # 지수가 0에 가까운(포화) 조명에서 계산이 폭주하는 것을 방지하는 하한

ANGLES = {"BT": (0, 30, 60), "ABF": (0, 30, 60, 75)}
COLORS = ("W", "R", "G", "B")

# 조명 반응 모델: GV ≈ k * Value^e  (로그-로그 기울기 e).
# BT: 2호기 탑1·탑2·바텀 실측(fit_exponents.py, 조명·색별 3개 곡선의 중앙값)에서 구한 값.
#     (1번 조명은 프리셋의 GV 기준 id 가 'R' 이라 W 와 R 키를 같이 둔다)
# ABF: 아직 실측 전이라 이전 임시값. ABF 측정표를 받으면 fit_exponents.py 로 교체한다.
# 실측에 맞춰 설정 파일(light_gv_tool.json)의 "exponents"로 덮어쓸 수도 있다.
DEFAULT_EXPONENT = 0.5
DEFAULT_EXPONENTS = {
    ("BT", 0, "W"): 0.51, ("BT", 0, "R"): 0.51,
    ("BT", 1, "R"): 0.21, ("BT", 1, "G"): 0.37, ("BT", 1, "B"): 0.35,
    ("BT", 2, "R"): 0.94, ("BT", 2, "G"): 0.59, ("BT", 2, "B"): 0.72,
    ("ABF", 0, "G"): 0.27, ("ABF", 1, "G"): 0.95, ("ABF", 2, "G"): 0.25,
}


class SpecFileError(FileNotFoundError):
    """파일/폴더를 못 찾았을 때. 화면 언어에 맞춰 번역할 수 있도록 key/params 를 함께 가진다."""

    def __init__(self, key, ko_message, **params):
        super().__init__(ko_message)
        self.key, self.params = key, params


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


def find_item_file(model_dir, names):
    """모델 폴더에서 이름 후보(names)에 해당하는 XML 탐색.

    후보 순서대로 1) 같은 이름의 파일(확장자/대소문자 무시) 2) 같은 이름 하위 폴더 안의 XML(하나뿐일 때).
    찾지 못하면 FileNotFoundError (GUI가 파일 선택창을 띄운다).
    """
    d = Path(model_dir)
    if not d.is_dir():
        raise SpecFileError("err_model_dir", f"모델 폴더가 없습니다: {d}", d=d)
    entries = sorted(d.iterdir())
    for name in ([names] if isinstance(names, str) else names):
        low = name.strip().lower()
        if not low:
            continue
        for p in entries:
            if p.is_file() and not re.search(r"\.bak_\d", p.name) and low in (p.name.lower(), p.stem.lower()):
                return str(p)
        for sub in (x for x in entries if x.is_dir() and x.name.lower() == low):
            xs = [x for x in sorted(sub.iterdir()) if x.is_file() and x.suffix.lower() == ".xml"]
            if len(xs) == 1:
                return str(xs[0])
    raise SpecFileError("err_spec_none", f"규격 파일을 찾을 수 없습니다: {d}", d=d)


def find_kind_file(model_dir, kind):
    """항목명 없이 모델 폴더에 바로 있는 파일: 이름에 BT/ABF가 들어간 XML이 하나뿐이면 그 파일."""
    d = Path(model_dir)
    if not d.is_dir():
        raise SpecFileError("err_model_dir", f"모델 폴더가 없습니다: {d}", d=d)
    xs = [p for p in sorted(d.iterdir()) if p.is_file() and p.suffix.lower() == ".xml" and kind.lower() in p.name.lower()]
    if len(xs) == 1:
        return str(xs[0])
    raise SpecFileError("err_kind_ambig", f"{kind} 규격 파일을 특정할 수 없습니다 (후보 {len(xs)}개): {d}", kind=kind, n=len(xs), d=d)


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
    exact = cur_param * ratio

    def predicted(p):
        return cur_gv * (max(p, 1e-9) / cur_param) ** exponent

    # 켜져 있던 조명(cur_param>0)을 보정 때문에 0(꺼짐)으로 만들지는 않는다: 최소 1
    lo = 1 if cur_param > 0 else 0
    cands = {min(MAX_VALUE, max(lo, math.floor(exact))), min(MAX_VALUE, max(lo, math.ceil(exact)))}
    best = min(cands, key=lambda p: abs(predicted(p) - target))
    if best == cur_param and abs(cur_gv - target) > 0:
        best = cur_param + (1 if target > cur_gv else -1)
        best = min(max(best, lo), MAX_VALUE)
    return int(best)


# ---------------------------------------------------------------- 프리셋 (presets.json)
def load_presets():
    """프로그램 폴더의 presets.json 을 읽고, 사용자 폴더의 light_gv_presets.json 이 있으면 키 단위로 덮어쓴다.
    새 모델/규격은 코드 수정 없이 JSON 에 프리셋을 추가하면 된다."""
    presets = {}
    for path in (Path(__file__).with_name("presets.json"), Path(os.path.expanduser("~")) / "light_gv_presets.json"):
        try:
            presets.update(json.loads(path.read_text(encoding="utf-8")).get("presets", {}))
        except (OSError, ValueError):
            pass
    return presets


def rkey(color, angle):
    return f"{color}{angle}"


@dataclass
class Entry:
    """화면 표의 한 줄 = 함께 보정되는 채널 묶음(한 조명의 한 GV 채널).

    BT : 한 색의 각도들(예: R0:R30 = 1:4). ABF : 한 조명의 모든 색/각도(예: W30:W60:R75 = 6:5:3).
    목표 GV 에 맞는 배율을 구해 묶음 전체에 적용하되, 프리셋 비율이 있으면 그 비율대로 값을 재구성한다.
    """
    kind: str
    set_index: int
    page: int
    gid: str                 # 묶음 id (BT: 색, ABF: 'G' = GV 기준 채널)
    label: str
    rows: list
    ratio: dict = field(default_factory=dict)     # 프리셋 비율 {"R0":1,"R30":4}
    targets: dict = field(default_factory=dict)   # 소재별 목표 GV {"AU":195}
    material: str = ""
    target: float = DEFAULT_TARGET
    cur_gv: float = None
    manual_ok: bool = False
    fixed: bool = False      # 좌/우 불일치를 사용자가 입력한 값으로 통일했는지
    light_no: int = 0        # 조명 번호 (화면에서 언어별 라벨을 만들 때 사용)
    preset_name: str = ""    # 프리셋에 정의된 조명 이름 (예: "DMG 1호"), 없으면 ""
    ch: str = ""             # GV 기준 채널 (R/G/B/W)

    @property
    def key(self):
        return f"{self.set_index}|{self.page}|{self.gid}"

    def mismatches(self):
        """같은 색·각도의 좌/우 채널 값이 서로 다른 경우 {키: [값들]}. 정상 파일이면 빈 dict."""
        bad = {}
        for k in self.keys():
            vals = []
            for r in self.rows_of(k):
                if r.value not in vals:
                    vals.append(r.value)
            if len(vals) > 1:
                bad[k] = vals
        return bad

    @property
    def ok(self):
        return self.manual_ok or (self.cur_gv is not None and is_ok(self.cur_gv, self.target))

    def keys(self):
        """사용 중인 (색+각도) 키, 각도 오름차순 (BT 는 색이 하나뿐)."""
        return sorted({rkey(r.color, r.angle) for r in self.rows}, key=lambda k: (k[0], int(k[1:])))

    def rows_of(self, key):
        return [r for r in self.rows if rkey(r.color, r.angle) == key]

    def param_text(self):
        """표시용 현재 파라미터. 좌/우 값이 다르면 '120/210'. 예: R0°=1 · R30°=4"""
        out = []
        for k in self.keys():
            vals = []
            for r in self.rows_of(k):
                if r.value not in vals:
                    vals.append(r.value)
            out.append(f"{k[0]}{k[1:]}°={'/'.join(str(v) for v in vals)}")
        return " · ".join(out)

    def ratio_text(self):
        if not self.ratio:
            return "-"
        return ":".join(str(self.ratio[k]) for k in self.keys() if k in self.ratio)

    def ratio_usable(self):
        """사용 중인 모든 키에 프리셋 비율이 있으면 프리셋 비율로 재구성 가능."""
        return bool(self.ratio) and all(self.ratio.get(k, 0) > 0 for k in self.keys())

    def ratio_matches(self, tol=0.08):
        """현재 파일 값이 프리셋 비율과 맞는지 (앵커 대비 ±8%)."""
        if not self.ratio_usable():
            return None
        anchor = self.anchor_key()
        a = self.rows_of(anchor)[0].value
        if a <= 0:
            return False
        for k in self.keys():
            want = a * self.ratio[k] / self.ratio[anchor]
            for r in self.rows_of(k):
                if abs(r.value - want) > max(1.0, want * tol):
                    return False
        return True

    def ratio_suggestions(self, tol=0.08):
        """비율이 규격과 다를 때 맞추기 위한 권장값 {키: 값}. 기준(비율 1) 채널은 그대로 두고 나머지를 맞춘다.

        좌/우 값이 다르면(먼저 통일해야 하므로) 규격 비율이 없거나 이미 맞으면 빈 dict.
        """
        if self.mismatches() or not self.ratio_usable() or self.ratio_matches():
            return {}
        anchor = self.anchor_key()
        a = self.rows_of(anchor)[0].value
        if a <= 0:
            return {}
        out = {}
        for k in self.keys():
            if k == anchor:
                continue
            want = a * self.ratio[k] / self.ratio[anchor]
            if abs(self.rows_of(k)[0].value - want) > max(1.0, want * tol):
                out[k] = min(MAX_VALUE, max(0, round(want)))
        return out

    def anchor_key(self):
        """비율이 가장 작은 키 = 기준(1) 채널."""
        ks = self.keys()
        return min(ks, key=lambda k: (self.ratio.get(k, 1e9), ks.index(k)))

    def set_material(self, material):
        if material in self.targets:
            self.material, self.target = material, self.targets[material]


def build_entries(kind, parsed, preset=None, saved_targets=None, default_target=DEFAULT_TARGET):
    """사용 중(Page·Channel Enable=1)인 채널을 프리셋 규칙에 따라 화면 항목으로 묶는다.

    프리셋에 없는 조명(페이지)은 BT: 색별, ABF: 조명별로 묶고 비율/목표는 비워 둔다(현재 비율 유지).
    """
    lights = (preset or {}).get("lights", {})
    entries = []
    for page in sorted({(r.set_index, r.page) for r in parsed.rows if r.enable}):
        set_idx, pg = page
        rows = [r for r in parsed.rows if r.enable and (r.set_index, r.page) == page]
        light = lights.get(str(pg + 1))
        lname = light["name"] if light else f"{pg + 1}호"
        if light:
            groups = light["groups"]
        elif kind == "ABF":
            groups = [{"id": "G", "colors": None, "gv_channel": "G", "ratio": {}, "targets": {}}]
        else:
            groups = [{"id": c, "colors": [c], "gv_channel": c, "ratio": {}, "targets": {}}
                      for c in COLORS if any(r.color == c for r in rows)]
        for grp in groups:
            members = [r for r in rows if grp.get("colors") is None or r.color in grp["colors"]]
            if not members:
                continue
            ch = grp.get("gv_channel", grp["id"])
            label = f"{lname} · {ch}" if kind == "BT" else f"{lname} · {ch} 기준"
            e = Entry(kind, set_idx, pg, grp["id"], label, members, dict(grp.get("ratio", {})), dict(grp.get("targets", {})))
            e.light_no, e.preset_name, e.ch = pg + 1, (light["name"] if light else ""), ch
            if e.targets:
                e.set_material(next(iter(e.targets)))
            else:
                e.target = default_target
            if saved_targets and e.key in saved_targets:
                e.target = saved_targets[e.key]
            entries.append(e)
    return entries


def apply_fixes(entry, fixes):
    """값 직접 수정: 좌/우 불일치 통일 + 규격 비율 맞춤. fixes = {키(예 'R30'): 새 값}. 적용한 키 수를 반환.

    값이 바뀌는 채널만 new_value 를 채운다. 파일 값이 바뀌므로 이 항목의 GV 보정은 재측정 후로 미룬다.
    """
    n = 0
    valid = set(entry.mismatches()) | set(entry.ratio_suggestions())
    for k, v in fixes.items():
        if not 0 <= v <= MAX_VALUE or k not in valid:
            continue
        for r in entry.rows_of(k):
            r.new_value = int(v) if r.value != v else None
        n += 1
    entry.fixed = n > 0
    return n


def apply_corrections(entries, exponents=None, align_ratio=True):
    """OK가 아니고 현재 GV가 입력된 항목의 new_value를 채운다. 변경된 항목 수 반환.

    배율은 앵커 채널(비율 1) 기준으로 비선형 모델로 구하고, 프리셋 비율이 있으면
    다른 각도/색 채널은 `앵커 새 값 × 비율`로 계산해 비율을 정확히 유지한다(없으면 같은 배율로 비례).
    """
    changed = 0
    for e in entries:
        if e.ok or e.cur_gv is None or not e.rows or e.mismatches():
            continue    # 좌/우 값이 다른 항목은 먼저 값을 통일(apply_fixes)한 뒤 재측정해야 한다
        use_ratio = align_ratio and e.ratio_usable()
        anchor = e.anchor_key() if e.ratio else e.keys()[0]
        arow = e.rows_of(anchor)[0]
        if arow.value <= 0:
            continue
        exp = exponent_for(e.kind, e.page, next((g for g in [e.gid] if g in COLORS), "G"), exponents)
        new_a = calc_new_value(arow.value, e.cur_gv, e.target, exp)
        # 가장 큰 채널이 MAX_VALUE 를 넘지 않도록 앵커를 제한 (넘으면 비율이 깨지므로 클램프 대신 전체를 축소)
        top = max(e.ratio[k] for k in e.keys()) / e.ratio[anchor] if use_ratio else max(r.value for r in e.rows) / arow.value
        new_a = min(new_a, int(MAX_VALUE / top))
        if new_a == arow.value and not use_ratio:
            continue
        scale = new_a / arow.value
        any_change = False
        for r in e.rows:
            if r.value == 0:
                continue
            k = rkey(r.color, r.angle)
            nv = new_a * e.ratio[k] / e.ratio[anchor] if use_ratio else r.value * scale
            r.new_value = min(MAX_VALUE, max(1, round(nv)))
            any_change |= r.new_value != r.value
        if not any_change:
            for r in e.rows:
                r.new_value = None
            continue
        changed += 1
    return changed


# ---------------------------------------------------------------- 목표 GV 수정 비밀번호
DEFAULT_PASSWORD = "1234"


def _pw_hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 100_000).hex()


def verify_password(cfg, pw):
    """저장된 비밀번호가 없으면 초기 비밀번호(1234)와 비교한다."""
    rec = cfg.get("password")
    if not rec:
        return hmac.compare_digest(pw.encode("utf-8"), DEFAULT_PASSWORD.encode("utf-8"))
    return hmac.compare_digest(_pw_hash(pw, bytes.fromhex(rec["salt"])), rec["hash"])


def set_password(cfg, pw):
    salt = os.urandom(16)
    cfg["password"] = {"salt": salt.hex(), "hash": _pw_hash(pw, salt)}


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
