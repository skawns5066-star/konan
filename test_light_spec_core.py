import os
import shutil
import tempfile

import light_spec_core as core

HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.join(HERE, "samples", "LightSpec-bt.xml")
ABF = os.path.join(HERE, "samples", "LightSpec-ABF.xml")


def tmp_copy(src):
    d = tempfile.mkdtemp()
    return shutil.copy(src, d)


def test_bt_groups_left_right_and_enable():
    es = core.build_entries("BT", core.parse_file(BT))
    got = [(e.page, e.angle, e.ref.color, e.param(e.ref.color), len(e.rows)) for e in es]
    assert (0, 0, "W", "40", 1) in got and (0, 30, "W", "120", 2) in got     # 30° 좌/우 2채널 = 1항목
    assert (1, 0, "R", "1", 1) in got and (1, 60, "G", "175", 2) in got
    assert (2, 60, "R", "120/210", 2) in got                                  # 좌/우 값이 다르면 둘 다 표시
    assert not any(e.page == 1 and e.ref.color == "W" for e in es)            # Enable=0 제외
    assert len(es) == 15


def test_abf_page_disabled_and_rgb_group():
    es = core.build_entries("ABF", core.parse_file(ABF))
    assert not any(e.page == 2 for e in es)                                   # Page 2 Enable=0
    assert [(e.page, e.angle) for e in es] == [(0, 0), (0, 30), (0, 60), (1, 30), (1, 60), (1, 75)]
    assert es[1].param("W") == "105" and len(es[1].rows) == 2


def test_ratio_not_additive():
    small = core.calc_new_value(4, 180, 190, 0.5)
    large = core.calc_new_value(300, 180, 190, 0.5)
    assert 4 < small <= 5 and 300 < large < 340
    assert core.calc_new_value(100, 200, 150, 0.5) < 100
    assert core.calc_new_value(100, 150, 150, 0.5) == 100
    assert core.calc_new_value(100, 100, 400, 0.5) == 300
    assert core.calc_new_value(0, 50, 150, 0.5) == 1
    assert core.calc_new_value(900, 50, 255, 0.5) == core.MAX_VALUE


def test_ok_tolerance():
    assert core.is_ok(160, 150) and core.is_ok(140, 150) and not core.is_ok(161, 150)


def test_save_only_changes_values_and_both_channels():
    p = tmp_copy(BT)
    pf = core.parse_file(p)
    es = core.build_entries("BT", pf)
    e = next(x for x in es if (x.page, x.angle, x.ref.color) == (1, 30, "G"))
    e.cur_gv, e.target = 100, 150
    ok = next(x for x in es if (x.page, x.angle) == (0, 0))
    ok.manual_ok = True
    assert core.apply_corrections(es) == 1
    bak = core.save_file(pf, True)
    old, new = open(bak, newline="").read(), open(p, newline="").read()
    assert old == open(BT, newline="").read() and os.path.exists(bak)
    diff = [(a, b) for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
    assert len(diff) == 2                                                     # 좌/우 두 채널만 변경
    for a, b in diff:
        assert a.replace('Value="35"', "") == b.replace(b.split('Value="')[1].split('"')[0].join(['Value="', '"']), "")
    nv = {r.value for r in core.parse_file(p).rows if (r.page, r.angle, r.color) == (1, 30, "G")}
    assert nv == {e.ref.new_value} and e.ref.new_value > 35
    assert len(new.splitlines()) == len(old.splitlines())


def test_abf_scales_all_colors_together():
    pf = core.parse_file(ABF)
    es = core.build_entries("ABF", pf)
    e = next(x for x in es if (x.page, x.angle) == (1, 75))                   # R 채널만 있는 경우 R이 기준
    assert e.ref.color == "R"
    e.cur_gv, e.target = 100, 150
    core.apply_corrections(es)
    assert e.ref.new_value > 195 and all(r.new_value == e.ref.new_value for r in e.rows)


def test_find_item_file():
    d = tempfile.mkdtemp()
    shutil.copy(BT, d)
    shutil.copy(ABF, d)
    assert core.find_item_file(d, "LightSpec-bt").endswith("LightSpec-bt.xml")
    assert core.find_item_file(d, "탑1", "ABF").endswith("LightSpec-ABF.xml")   # 종류로 보조 탐색
    os.makedirs(os.path.join(d, "탑1"))
    shutil.copy(BT, os.path.join(d, "탑1"))
    assert os.sep + "탑1" + os.sep in core.find_item_file(d, "탑1", "BT")
