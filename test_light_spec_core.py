import os
import shutil
import tempfile

import light_spec_core as core

HERE = os.path.dirname(os.path.abspath(__file__))
BT = os.path.join(HERE, "samples", "LightSpec-bt.xml")
ABF = os.path.join(HERE, "samples", "LightSpec-ABF.xml")
P = core.load_presets()


def tmp_copy(src):
    return shutil.copy(src, tempfile.mkdtemp())


def bt_entries(preset="BT_TOP"):
    return core.build_entries("BT", core.parse_file(BT), P[preset])


def test_presets_cover_four_areas():
    assert set(P) >= {"BT_TOP", "BT_BOTTOM", "ABF_TOP", "ABF_BOTTOM"}
    assert P["BT_TOP"]["lights"]["2"]["groups"][0]["targets"] == {"AU": 195}      # '190~195' -> 큰 값
    assert P["BT_BOTTOM"]["lights"]["2"]["groups"][0]["targets"]["AU"] == 255     # '255+'
    assert P["ABF_TOP"]["lights"]["2"]["groups"][0]["targets"] == {"SR": 105}     # Green 기준


def test_bt_entries_follow_preset_and_file_ratio():
    es = {(e.page, e.gid): e for e in bt_entries()}
    assert len(es) == 7                      # 1번 W / 2번 R,G,B / 3번 R,G,B
    e = es[(1, "G")]
    assert e.keys() == ["G30", "G60"] and e.ratio_text() == "1:5" and e.param_text() == "G30°=35 · G60°=175"
    assert e.target == 185 and e.ratio_matches()
    assert es[(2, "R")].param_text() == "R0°=480 · R60°=120/210" and not es[(2, "R")].ratio_matches()
    assert es[(0, "R")].keys() == ["W0", "W30", "W60"] and es[(0, "R")].ratio_matches()   # BT 1번 = W, 1:3:3


def test_material_changes_target():
    e = bt_entries("BT_BOTTOM")[1]
    assert e.targets == {"AU": 255, "OSP": 195} and e.target == 255
    e.set_material("OSP")
    assert e.target == 195


def test_abf_all_three_lights_shown_and_page_off_light_still_correctable():
    es = core.build_entries("ABF", core.parse_file(ABF), P["ABF_TOP"])
    assert [(e.light_no, e.disabled) for e in es] == [(1, False), (2, False), (3, True)]   # 3호: 파일에서 Page Enable=0 (안내만)
    assert es[1].param_text() == "R75°=195 · W30°=390 · W60°=325"
    assert {r.color for r in es[1].rows} == {"W", "R"}
    e = es[2]
    e.set_channel_gv("G", 100)                                                               # 꺼진 페이지여도 G 입력 -> 보정 가능
    assert core.apply_corrections(es) == 1 and all(r.new_value and r.new_value > r.value for r in e.rows)


def test_abf_channels_targets_from_spec_and_only_g_is_input_by_default():
    es = core.build_entries("ABF", core.parse_file(ABF), P["ABF_TOP"])
    t1 = {c: (v["target"], v["input"]) for c, v in es[0].channels.items()}
    assert t1 == {"R": (255, False), "G": (200, True), "B": (130, False)}            # 규격표 OSP: R 255 / G 200 / B 130
    es[0].set_material("SOP")
    assert [es[0].channels[c]["target"] for c in "RGB"] == [145, 150, 130]
    assert [v["target"] for v in es[1].channels.values()] == [95, 105, 120]          # 2호 SR: 90~95 / 100~105 / 110~120 -> 큰 값
    bot = core.build_entries("ABF", core.parse_file(ABF), P["ABF_BOTTOM"])
    assert [bot[0].channels[c]["target"] for c in "RGB"] == [250, 225, 135]


def test_abf_correction_is_driven_by_g_only():
    e = core.build_entries("ABF", core.parse_file(ABF), P["ABF_TOP"])[0]
    assert not e.ok
    e.set_channel_gv("R", 120)                     # R 은 목표(255)와 한참 달라도 (참고용 입력) 판정/보정에 영향 없음
    assert not e.ok and e.cur_gv is None
    e.set_channel_gv("G", 195)
    assert e.ok and e.target == 200
    e.set_channel_gv("G", 150)
    assert not e.ok and e.cur_gv == 150
    assert core.apply_corrections([e]) == 1
    g_new = {r.new_value for r in e.rows if r.color == "W" and r.angle == 30}
    assert g_new and next(iter(g_new)) > 105       # G 만 보고 올림 (R=120 은 무시)


def test_names_have_no_dmg():
    assert all("DMG" not in l["name"] for v in P.values() for l in v["lights"].values())


def test_ratio_not_additive():
    small = core.calc_new_value(4, 180, 190, 0.5)
    large = core.calc_new_value(300, 180, 190, 0.5)
    assert 4 < small <= 5 and 300 < large < 340
    assert core.calc_new_value(100, 200, 150, 0.5) < 100
    assert core.calc_new_value(100, 150, 150, 0.5) == 100
    assert core.calc_new_value(100, 100, 400, 0.5) == 1024      # 배율 제한 없음(필요하면 크게), 상한은 Value 최대 1024
    assert core.calc_new_value(100, 100, 200, 0.5) == 400       # 3배를 넘는 보정도 그대로 계산
    assert core.calc_new_value(0, 50, 150, 0.5) == 1
    assert core.calc_new_value(900, 50, 255, 0.5) == core.MAX_VALUE


def test_ok_tolerance():
    assert core.is_ok(160, 150) and core.is_ok(140, 150) and not core.is_ok(161, 150)


def test_correction_keeps_preset_ratio_and_saves_only_values():
    p = tmp_copy(BT)
    pf = core.parse_file(p)
    es = core.build_entries("BT", pf, P["BT_TOP"])
    g = next(e for e in es if (e.page, e.gid) == (1, "G"))
    g.cur_gv = 120                                           # 목표 185 -> 올려야 함
    next(e for e in es if e.page == 0).manual_ok = True
    assert core.apply_corrections(es) == 1
    bak = core.save_file(pf, True)
    old, new = open(bak, newline="").read(), open(p, newline="").read()
    assert old == open(BT, newline="").read()
    diff = [(a, b) for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
    assert len(diff) == 4                                    # 30°·60° 좌/우 4채널만 변경
    vals = {(r.angle): r.value for r in core.parse_file(p).rows if (r.page, r.color) == (1, "G") and r.enable}
    assert vals[30] > 35 and vals[60] == vals[30] * 5       # 1:5 정확히 유지
    assert len(new.splitlines()) == len(old.splitlines())


def test_unaligned_ratio_proportional_when_option_off():
    pf = core.parse_file(BT)
    es = core.build_entries("BT", pf, P["BT_TOP"])
    r = next(e for e in es if (e.page, e.gid) == (2, "R"))
    r.cur_gv = 40
    assert core.apply_corrections([r], align_ratio=False) == 0   # 좌/우 불일치(120/210) 항목은 보정하지 않는다
    assert all(x.new_value is None for x in r.rows)
    g = next(e for e in es if (e.page, e.gid) == (2, "G"))
    g.cur_gv = 80
    core.apply_corrections([g], align_ratio=False)
    assert abs(g.rows_of("G60")[0].new_value / g.rows_of("G30")[0].new_value - 2.0) < 0.05   # 현재 비율 유지


def test_abf_scales_all_channels_by_g_target():
    pf = core.parse_file(ABF)
    es = core.build_entries("ABF", pf, P["ABF_TOP"])
    e = es[1]
    e.cur_gv = 60
    assert core.apply_corrections(es) == 1
    assert all(r.new_value > r.value for r in e.rows)


def test_find_item_file():
    d = tempfile.mkdtemp()
    shutil.copy(BT, d)
    assert core.find_item_file(d, ["nope", "LightSpec-bt"]).endswith("LightSpec-bt.xml")
    os.makedirs(os.path.join(d, "Top"))
    shutil.copy(BT, os.path.join(d, "Top"))
    assert os.sep + "Top" + os.sep in core.find_item_file(d, ["Top"])
    try:
        core.find_item_file(d, ["Bottom"])
        assert False
    except FileNotFoundError:
        pass


def test_left_right_mismatch_detected_and_fixed():
    p = tmp_copy(BT)
    pf = core.parse_file(p)
    es = core.build_entries("BT", pf, P["BT_TOP"])
    bad = [(e, e.mismatches()) for e in es if e.mismatches()]
    assert len(bad) == 1 and list(bad[0][1].values()) == [[120, 210]]       # 3번 조명 R 60°: 120/210
    e = bad[0][0]
    (k,) = e.mismatches()
    e.cur_gv = 50
    assert core.apply_corrections(es) == 0 or all(r.new_value is None for r in e.rows)   # 통일 전에는 GV 보정 제외
    assert core.apply_fixes(e, {k: 120}) == 1 and e.fixed
    core.save_file(pf, False)
    again = core.build_entries("BT", core.parse_file(p), P["BT_TOP"])
    assert not any(x.mismatches() for x in again)
    assert core.apply_fixes(e, {k: 5000}) == 0                               # 범위 밖 값 거부


def test_password_default_and_change():
    cfg = {}
    assert core.verify_password(cfg, "1234") and not core.verify_password(cfg, "0000")
    core.set_password(cfg, "abcd")
    assert core.verify_password(cfg, "abcd") and not core.verify_password(cfg, "1234")


def test_find_kind_file_without_item_name():
    d = tempfile.mkdtemp()
    shutil.copy(BT, d)
    shutil.copy(ABF, d)
    assert core.find_kind_file(d, "BT").endswith("LightSpec-bt.xml")
    assert core.find_kind_file(d, "ABF").endswith("LightSpec-ABF.xml")


def test_translations_complete_and_consistent():
    import re
    import i18n
    for key, vals in i18n.TEXT.items():
        assert len(vals) == len(i18n.LANGS) and all(vals), key
        holders = [sorted(re.findall(r"\{(\w+)", v)) for v in vals]
        assert holders[0] == holders[1] == holders[2], key        # 언어마다 {자리표시자}가 같아야 한다
    i18n.set_lang("zh")
    assert i18n.t("light_n", n=2) == "2號光源"
    i18n.set_lang("vi")
    assert i18n.t("light_n", n=2) == "Đèn 2"
    i18n.set_lang("ko")


def test_spec_file_error_is_translatable():
    try:
        core.find_kind_file(os.path.join(tempfile.mkdtemp(), "none"), "BT")
        assert False
    except core.SpecFileError as ex:
        assert ex.key == "err_model_dir" and "d" in ex.params and isinstance(ex, FileNotFoundError)


def _bt_with_bad_ratio():
    """샘플의 2호 R(R0=1, R30=4 → 규격 1:4)을 R0=4, R30=12(1:3)로 바꾼 복사본."""
    p = tmp_copy(BT)
    pf = core.parse_file(p)
    e = next(x for x in core.build_entries("BT", pf, P["BT_TOP"]) if (x.page, x.gid) == (1, "R"))
    for r in e.rows:
        r.new_value = 4 if r.angle == 0 else 12
    core.save_file(pf, False)
    return p


def test_ratio_suggestion_and_fix():
    p = _bt_with_bad_ratio()
    pf = core.parse_file(p)
    es = core.build_entries("BT", pf, P["BT_TOP"])
    e = next(x for x in es if (x.page, x.gid) == (1, "R"))
    assert e.ratio_matches() is False and e.ratio_suggestions() == {"R30": 16}      # 12 -> 16 유도
    assert core.apply_fixes(e, {"R30": 16}) == 1 and e.fixed
    assert core.apply_fixes(e, {"R0": 99}) == 0                                       # 기준(1) 채널은 권장 대상이 아님
    core.save_file(pf, False)
    again = next(x for x in core.build_entries("BT", core.parse_file(p), P["BT_TOP"]) if (x.page, x.gid) == (1, "R"))
    assert again.ratio_matches() and again.ratio_suggestions() == {}
    assert [r.value for r in again.rows_of("R30")] == [16, 16]                        # 좌/우 둘 다 수정


def test_ratio_suggestion_waits_for_left_right_fix():
    es = core.build_entries("BT", core.parse_file(BT), P["BT_TOP"])
    e = next(x for x in es if (x.page, x.gid) == (2, "R"))        # 120/210 불일치
    assert e.mismatches() and e.ratio_suggestions() == {}


# 2호기 BT 실측(탑1·탑2·바텀) 중 일부: (Value, GV) 점들 — fit_exponents 가 같은 값을 재현하는지 확인
MEASURED_2R = [[(1, 197), (2, 205), (4, 216), (6, 224)], [(6, 180), (8, 193), (10, 204)], [(5, 181), (7, 192), (9, 205)]]
MEASURED_3R = [[(700, 77), (740, 80), (760, 82), (780, 84)], [(780, 77), (800, 83), (820, 84)], [(512, 82), (532, 84), (552, 88)]]


def test_fitted_exponents_match_defaults_and_hit_tolerance():
    import fit_exponents as fe
    assert abs(fe.pooled_exponent(MEASURED_2R) - core.DEFAULT_EXPONENTS[("BT", 1, "R")]) < 0.01
    assert abs(fe.pooled_exponent(MEASURED_3R) - core.DEFAULT_EXPONENTS[("BT", 2, "R")]) < 0.01
    # 2번 조명 R(Value 1~10, 한 단계가 GV 약 10~14): 5->7 처럼 정수 한 칸 단위로 목표(탑2 측정점 192)에 도달해야 한다
    assert core.calc_new_value(5, 181, 192, core.exponent_for("BT", 1, "R")) in (6, 7, 8)
    # 켜져 있던 조명은 보정 때문에 0(꺼짐)이 되지 않는다
    assert core.calc_new_value(1, 224, 100, core.exponent_for("BT", 1, "R")) == 1


def test_measurement_sheet_reader():
    import fit_exponents as fe
    data = fe.read_sheet(os.path.join(HERE, "samples", "measure_BT_2호기.xlsx"))
    assert len(data) == 7 and all(len(v) == 3 for v in data.values())       # 7개 (조명,색) x 3개 위치
    assert fe.pooled_exponent(data[("BT", 2, "R")]) and abs(fe.pooled_exponent(data[("BT", 2, "R")]) - 0.21) < 0.01


def test_abf_measurement_drops_input_mistake_and_matches_defaults():
    import fit_exponents as fe
    data = fe.read_sheet(os.path.join(HERE, "samples", "measure_ABF_1.xlsx"))
    assert sorted(data) == [("ABF", 1, "G"), ("ABF", 2, "G"), ("ABF", 3, "G")] and all(len(v) == 2 for v in data.values())
    series, dropped = fe.clean_group(data[("ABF", 3, "G")])
    assert dropped == [(6, 162)]                           # 파라미터 6 > 5 인데 GV 162 < 170 : 입력 실수
    for light in (1, 2, 3):
        s, d = fe.clean_group(data[("ABF", light, "G")])
        assert abs(fe.pooled_exponent(s) - core.DEFAULT_EXPONENTS[("ABF", light - 1, "G")]) < 0.01


def test_clean_group_keeps_clean_series_untouched():
    import fit_exponents as fe
    s, d = fe.clean_group(MEASURED_2R)
    assert d == [] and [sorted(x) for x in MEASURED_2R] == s


ABF_2HO_XML = """<pixel><Light_Setting><LightSet Index="1">
<Page Index="1" ChannelCount="4" Enable="1">
<Channel Index="0" Value="100" Angle="0" Color="W" Enable="1"></Channel>
<Channel Index="1" Value="200" Angle="30" Color="W" Enable="1"></Channel>
<Channel Index="2" Value="200" Angle="60" Color="W" Enable="1"></Channel>
<Channel Index="3" Value="195" Angle="75" Color="R" Enable="0"></Channel>
</Page></LightSet></Light_Setting></pixel>"""


def test_abf_ratio_checked_even_when_file_has_channel_not_in_spec():
    """ABF 2호 규격은 W30:W60:R75 = 6:5:3. 파일에는 W0°(규격에 없음)가 켜져 있고 R75°는 꺼져 있다."""
    pf = core.parse_text(ABF_2HO_XML)
    e = core.build_entries("ABF", pf, P["ABF_TOP"])[0]
    assert e.spec_keys() == ["W30", "W60"] and e.ratio_usable()
    assert e.ratio_matches() is False                                  # 200:200 은 6:5 가 아니다
    assert e.ratio_suggestions() == {"W30": 240}                       # 기준(비율 5)=W60 은 그대로, W30 을 240 으로 유도
    core.apply_fixes(e, {"W30": 240})
    assert [(r.angle, r.new_value) for r in e.rows if r.new_value] == [(30, 240)]
    # GV 보정 시: 규격에 없는 W0° 는 현재 비율대로 같이 움직이고, 규격 키는 6:5 로 맞춰진다
    e2 = core.build_entries("ABF", pf, P["ABF_TOP"])[0]
    e2.set_channel_gv("G", 70)
    assert core.apply_corrections([e2]) == 1
    nv = {(r.angle): r.new_value for r in e2.rows if r.new_value}
    assert abs(nv[30] / nv[60] - 6 / 5) < 0.02 and nv[0] / nv[60] - 0.5 < 0.02
