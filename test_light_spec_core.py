import os
import tempfile

import light_spec_core as core

BT = """Page index 0
100,0,W,1
60,30,R,0
Page index 1
4,0,R,1
300,0,B,1
"""
ABF = """0,100,0,R,1
0,120,0,G,1
0,80,0,B,1
0,90,75,G,1
1,50,0,G,0
"""


def write(text, name="a.txt"):
    d = tempfile.mkdtemp()
    p = os.path.join(d, name)
    with open(p, "w", newline="") as f:
        f.write(text)
    return p


def test_parse_bt_and_enable():
    pf = core.parse_text(BT)
    assert [(r.page, r.value, r.angle, r.color, r.enable) for r in pf.rows] == [
        (0, 100, 0, "W", True), (0, 60, 30, "R", False), (1, 4, 0, "R", True), (1, 300, 0, "B", True)]
    assert [e.ref.value for e in core.build_entries("BT", pf)] == [100, 4, 300]


def test_ratio_not_additive():
    # 같은 GV 부족분이라도 베이스가 작으면 변화량이 작고, 크면 크다(비율 계산)
    small = core.calc_new_value(4, 180, 190, 0.5)
    large = core.calc_new_value(300, 180, 190, 0.5)
    assert 4 < small <= 5 and 300 < large < 340
    assert core.calc_new_value(100, 200, 150, 0.5) < 100        # 내림
    assert core.calc_new_value(100, 150, 150, 0.5) == 100
    assert core.calc_new_value(100, 100, 400, 0.5) == 300       # MAX_STEP 제한
    assert core.calc_new_value(0, 50, 150, 0.5) == 1


def test_ok_tolerance():
    assert core.is_ok(160, 150) and core.is_ok(140, 150) and not core.is_ok(161, 150)


def test_abf_green_only_and_rgb_together():
    pf = core.parse_text(ABF)
    es = core.build_entries("ABF", pf)
    assert [(e.angle, e.ref.color) for e in es] == [(0, "G"), (75, "G")]   # 75도, Enable=0 제외
    e0 = es[0]
    assert [e0.param(c) for c in "RGB"] == [100, 120, 80]
    e0.cur_gv, e0.target = 100, 150
    core.apply_corrections(es)
    g, r, b = (next(x for x in e0.rows if x.color == c) for c in "GRB")
    assert g.new_value > 120
    assert abs(r.new_value / 100 - g.new_value / 120) < 0.02 and abs(b.new_value / 80 - g.new_value / 120) < 0.03
    assert es[1].ref.new_value is None


def test_save_preserves_format_and_backup():
    p = write(BT.replace("\n", "\r\n"))
    pf = core.parse_file(p)
    es = core.build_entries("BT", pf)
    es[1].cur_gv, es[1].target = 100, 150
    es[0].manual_ok = True
    core.apply_corrections(es)
    bak = core.save_file(pf, True)
    assert os.path.exists(bak)
    new = open(p, newline="").read()
    old = open(bak, newline="").read()
    assert old == BT.replace("\n", "\r\n")
    assert new.count("\r\n") == old.count("\r\n")
    diff = [(a, b) for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
    assert len(diff) == 1 and diff[0][0] == "4,0,R,1" and diff[0][1].endswith(",0,R,1")
    assert core.parse_file(p).rows[2].value == es[1].ref.new_value
    assert core.find_item_file(os.path.dirname(p), "a") == p      # 확장자 없이 항목명 매칭, .bak 제외


def test_key_value_style():
    pf = core.parse_text("Page index 2\nValue=77\tAngle=60\tColor=G\tEnable=1\n")
    assert pf.rows[0].page == 2 and pf.rows[0].value == 77 and pf.rows[0].angle == 60
    assert pf.lines[0] and pf.rows[0].span == (6, 8)
