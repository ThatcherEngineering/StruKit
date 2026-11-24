"""Roof snow loads against ASCE/SEI 7-22 Commentary C7 worked examples.

  Example 1: gable roof, 6 on 12, pg = 30 psf, W2 = 0.55, R = 30 unventilated, composition
     shingles, Roughness B partially exposed, W = 30 ft: Ce = 1.0, Ct = 1.14, pf = 23.9,
     Cs = 1.0, ps = 23.9; density 17.9 pcf, hd = 2.46 ft, surcharge 31.1 psf over 9.3 ft;
     no minimum (slope over 15 deg), no rain-on-snow.
  Example 3: high roof pg = 40, Ce = 0.9, R = 30: Ct = 1.13, pf = 28.5; minimum 30 psf (Risk
     Category II). Low roof pg = 32, unheated, partially exposed: pf = 27 (26.9).
"""
import pytest

from strukit import snow

B_PART = dict(roughness="B", exposure="partially exposed")


def test_commentary_example_1_gable():
    r = snow.roof(30, "II", thermal=snow.HEATED, r_roof=30, roof_type="gable", rise_on_12=6, slippery=False, W_ft=30,
                  W2=0.55, simple_members=False, **B_PART)
    assert r.Ce == 1.0 and r.Ct == pytest.approx(1.14)
    assert r.pf == pytest.approx(23.9, abs=0.05)
    assert r.Cs == 1.0 and r.ps == pytest.approx(23.9, abs=0.05)
    assert r.pm == 0 and r.rain_on_snow == 0
    u = r.unbalanced
    assert u["gamma"] == pytest.approx(17.9) and u["hd"] == pytest.approx(2.46, abs=0.01)
    assert u["surcharge"] == pytest.approx(31.1, abs=0.2) and u["extent"] == pytest.approx(9.3, abs=0.05)
    assert u["windward"] == pytest.approx(0.3 * r.ps) and u["leeward"] == pytest.approx(r.ps)


def test_commentary_example_3_flat_roofs():
    hi = snow.roof(40, "II", "C", "fully exposed", snow.HEATED, "monoslope", 0.25, False, 100, r_roof=30)
    assert hi.Ce == 0.9 and hi.Ct == pytest.approx(1.13)
    assert hi.pf == pytest.approx(28.5, abs=0.05)
    assert hi.pm == 30.0                                    # pg above the Risk Category II limit
    lo = snow.roof(32, "I", "C", "partially exposed", snow.THERMAL[1], "monoslope", 0.25, False, 240)
    assert lo.Ct == 1.2 and lo.pf == pytest.approx(26.9, abs=0.05)
    assert lo.pm == 25.0


def test_thermal_factor_table():
    assert snow.ct(snow.HEATED, 10, 20)[0] == 1.20
    assert snow.ct(snow.HEATED, 25, 20)[0] == pytest.approx(1.08)          # between 1.11 and 1.05
    assert snow.ct(snow.HEATED, 40, 35)[0] == pytest.approx(1.145)         # between rows 30 and 40
    assert snow.ct(snow.HEATED, 90, 15)[0] == 1.00                         # beyond both ends
    assert snow.ct(snow.HEATED, 30, 60)[0] == 1.2                          # note b
    assert snow.ct("freezer building", 30)[0] == 1.3
    assert snow.ct("continuously heated greenhouse", 30)[0] == 0.85


def test_slope_factor_graphs():
    assert snow.cs(1.0, 30, True)[0] == 1.0                                 # graph (a): one line for all surfaces
    assert snow.cs(1.1, 50, False)[0] == pytest.approx(0.5)                 # (a) applies at Ct = 1.1
    assert snow.cs(1.14, 40, True)[0] == pytest.approx(0.5)                 # (b) slippery: 1 - (40 - 10)/60
    assert snow.cs(1.14, 40, False)[0] == pytest.approx(1 - 2.5 / 32.5)
    assert snow.cs(1.2, 45, False)[0] == 1.0 and snow.cs(1.2, 42.5, True)[0] == pytest.approx(0.5)
    assert snow.cs(1.3, 70, False)[0] == 0.0


def test_exposure_table():
    assert snow.ce("B", "sheltered") == 1.2 and snow.ce("C", "sheltered") == 1.1 and snow.ce("D", "fully exposed") == 0.8
    with pytest.raises(snow.SnowError):
        snow.ce("above the tree line", "sheltered")


def test_minimum_and_rain_on_snow():
    # pg = 20 (below the limit): pm = pg; slope 0.25 on 12 = 1.19 deg < W/50 = 2.0 deg: 8 psf on the balanced case
    r = snow.roof(20, "II", "C", "partially exposed", snow.THERMAL[1], "monoslope", 0.25, False, 100)
    assert r.pm == 20 and r.rain_on_snow == 8
    assert r.balanced == pytest.approx(0.7 * 1.0 * 1.2 * 20 + 8)
    assert r.uniform_design == pytest.approx(24.8)
    # a steeper roof: no surcharge
    assert snow.roof(20, "II", "C", "partially exposed", snow.THERMAL[1], "monoslope", 1, False, 100).rain_on_snow == 0


def test_short_gable_with_simple_rafters():
    r = snow.roof(30, "II", thermal=snow.THERMAL[1], roof_type="gable", rise_on_12=4, slippery=False, W_ft=16,
                  simple_members=True, **B_PART)
    assert r.unbalanced == dict(windward=0.0, leeward=30, surcharge=0.0, extent=0.0)


def test_no_unbalanced_outside_the_slope_range_and_inputs_stop():
    steep = snow.roof(30, "II", thermal=snow.THERMAL[1], roof_type="gable", rise_on_12=9, slippery=False, W_ft=30, **B_PART)
    assert steep.unbalanced == {}
    with pytest.raises(snow.SnowError, match="W2"):
        snow.roof(30, "II", thermal=snow.THERMAL[1], roof_type="gable", rise_on_12=6, slippery=False, W_ft=30,
                  simple_members=False, **B_PART)
    with pytest.raises(snow.SnowError, match="R-value"):
        snow.roof(30, "II", thermal=snow.HEATED, roof_type="monoslope", rise_on_12=1, slippery=False, W_ft=30, **B_PART)


# ---------------------------------------------------------------- sheet and screen
def _typed(**kw):
    v = dict(mark="SN1", pg="30", pg_source="ASCE 7 Hazard Tool, sample value", risk="II", roughness="B",
             exposure="partially exposed", thermal=snow.HEATED, r_roof="30", roof="gable or hip", rise="6", slippery="no",
             W="30", simple="no", W2="0.55", W2_source="ASCE 7 Hazard Tool, sample value")
    v.update(kw)
    return v


def test_screen_builds_the_snow_sheet_and_prints_it(tmp_path):
    from strukit import calcsheet
    from strukit.gui import calc
    s, kind, _ = calc.build("snow", _typed(), {})
    assert kind == "simple" and s.snow.ps == pytest.approx(23.9, abs=0.05)
    assert any("31.2 psf" in t and "9.3 ft" in t for t in s.blocks[0]["text"])
    r = calc.results("snow", _typed(), {})
    assert r["state"] == "done" and r["status"] == "OK" and any(x["label"].startswith("pf") for x in r["steps"])
    calcsheet.simple_pdf(s, str(tmp_path / "sn.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    assert (tmp_path / "sn.pdf").stat().st_size > 4000


def test_screen_names_what_is_missing():
    from strukit.gui import calc
    r = calc.results("snow", _typed(pg_source="", r_roof="", risk=""), {})
    assert r["state"] == "incomplete"
    msg = " ".join(r["messages"])
    assert "Where pg comes from is blank" in msg and "Roof R-value" in msg and "Risk Category is blank" in msg
    r = calc.results("snow", _typed(W2=""), {})
    assert r["state"] == "stopped" and "W2" in r["messages"][0]
    r = calc.results("snow", _typed(W2_source=""), {})
    assert r["state"] == "stopped" and "source of the winter wind parameter" in r["messages"][0]


def test_monoslope_sheet_has_minimum_and_no_unbalanced():
    from strukit.gui import calc
    s, _, _ = calc.build("snow", _typed(roof="monoslope", rise="0.25", thermal=snow.THERMAL[1], r_roof="", pg="20", W="100",
                                         simple="", W2="", W2_source=""), {})
    assert s.snow.pm == 20 and s.snow.rain_on_snow == 8 and not s.snow.unbalanced
    assert any("Minimum snow load" in t for t in s.blocks[0]["text"])


# ---- drifts and sliding snow --------------------------------------------------------------
def test_commentary_example_3_drifts():
    """ASCE/SEI 7-22 Commentary C7, Example 3: lower roof ps = 27 psf, step 10 ft, upper roof 100 ft, lower roof 240 ft,
    W2 = 0.5, pg = 32 psf in Eq. 7.6-1 with gamma = 19 pcf: hb = 1.4 ft, hc = 8.6 ft, leeward hd = 3.4 ft, windward
    0.75 hd = 3.41 ft (the example prints hd = 4.55 ft; Eq. 7.6-1 gives 4.69 ft), width 8 x 3.41 = 27.3 ft, surcharge 64.8 psf.
    The example takes gamma from a 40 psf ground load and hd from a 32 psf one; StruKit uses one pg, so the comparison is
    within 5 to 6 percent, not exact."""
    from strukit import snow
    r = snow.lower_roof(32, 0.5, 27, 100, 240, 10)
    assert r.required and r.hb == pytest.approx(1.4, abs=0.1) and r.hc == pytest.approx(8.6, abs=0.1)
    assert r.leeward.height == pytest.approx(3.4, rel=0.05) and r.leeward.width == pytest.approx(4 * r.leeward.height)
    assert r.windward.height == pytest.approx(3.41, rel=0.06) and r.windward.width == pytest.approx(8 * r.windward.height)
    assert r.windward.pd == pytest.approx(64.8, rel=0.06)
    assert 0.75 * 1.5 * (32 ** 0.74 * 240 ** 0.70 * 0.5 ** 1.7 / 19) ** 0.5 == pytest.approx(3.52, abs=0.01)   # against the printed 3.41
    # Eq. 7.6-1 itself with the example's own numbers: 1.5 sqrt(32^0.74 x 100^0.70 x 0.5^1.7 / 19) = 3.45 ft
    assert 1.5 * (32 ** 0.74 * 100 ** 0.70 * 0.5 ** 1.7 / 19) ** 0.5 == pytest.approx(3.4, abs=0.06)


def test_drift_rules_by_hand():
    from strukit import snow
    # a low step: pg 30 (gamma 17.9), ps 21, step 3 ft: hb = 1.173, hc = 1.827; leeward from a 200 ft roof, W2 0.45:
    hd = 1.5 * (30 ** 0.74 * 200 ** 0.70 * 0.45 ** 1.7 / 17.9) ** 0.5
    r = snow.lower_roof(30, 0.45, 21, 200, 50, 3)
    assert hd > r.hc and r.leeward.height == pytest.approx(r.hc) and r.leeward.width == pytest.approx(min(4 * hd ** 2 / r.hc, 8 * r.hc))
    assert r.leeward.pd == pytest.approx(r.hc * 17.9)
    # the 0.6 x lower roof length limit, and the taper on a narrow lower roof
    n = snow.lower_roof(30, 0.45, 21, 200, 4, 12)
    assert n.leeward.hd_eq == pytest.approx(2.4) and n.leeward.extent == 4 and n.leeward.at_far_end == pytest.approx(n.leeward.pd * (1 - 4 / 9.6))
    # hc / hb under 0.2: no drift
    assert not snow.lower_roof(30, 0.45, 21, 200, 50, 1.3).required
    with pytest.raises(snow.SnowError):
        snow.lower_roof(30, None, 21, 200, 50, 3)


def test_sliding_snow_by_hand():
    from strukit import snow
    # upper roof pf = 30 psf, W = 20 ft, 4 on 12, not slippery: 0.4 x 30 x 20 = 240 plf over 15 ft = 16 psf
    r = snow.lower_roof(30, 0.45, 21, 40, 30, 8, sliding=dict(pf=30, W=20, rise_on_12=4, slippery=False))
    assert r.sliding_psf == pytest.approx(16) and r.sliding_extent == 15 and r.sliding_total == pytest.approx(240)
    # lower roof 10 ft wide: the same 16 psf on 10 ft
    r = snow.lower_roof(30, 0.45, 21, 40, 10, 8, sliding=dict(pf=30, W=20, rise_on_12=4, slippery=False))
    assert r.sliding_psf == pytest.approx(16) and r.sliding_extent == 10 and r.sliding_total == pytest.approx(160)
    # 2 on 12 and not slippery: none; 1 on 12 and slippery: applies
    assert snow.lower_roof(30, 0.45, 21, 40, 30, 8, sliding=dict(pf=30, W=20, rise_on_12=2, slippery=False)).sliding_psf == 0
    assert snow.lower_roof(30, 0.45, 21, 40, 30, 8, sliding=dict(pf=30, W=20, rise_on_12=1, slippery=True)).sliding_psf == pytest.approx(16)


def test_parapet_drift_by_hand():
    from strukit import snow
    # pg 30 (gamma 17.9), W2 0.45, ps 21 psf, 120 ft of roof upwind, 3 ft parapet: hb = 1.173, hc = 1.827
    # 0.75 hd = 0.75 x 1.5 sqrt(30^0.74 x 120^0.70 x 0.45^1.7 / 17.9); the height is capped at hc; width 8 x 0.75 hd
    h = 0.75 * 1.5 * (30 ** 0.74 * 120 ** 0.70 * 0.45 ** 1.7 / 17.9) ** 0.5
    r = snow.lower_roof(30, 0.45, 21, None, 120, 3, parapet=True)
    assert r.leeward is None and r.governing is r.windward
    assert r.windward.hd_eq == pytest.approx(h) and r.windward.height == pytest.approx(min(h, r.hc)) and r.windward.width == pytest.approx(8 * h)
    assert r.windward.pd == pytest.approx(min(h, r.hc) * 17.9)


def test_drift_on_an_adjacent_lower_structure(tmp_path):
    """ASCE/SEI 7-22 Sect. 7.7.2 (page text, pdf p. 126). pg = 40 psf, W2 = 0.45, upper roof 60 ft, lower roof 40 ft with ps = 30 psf, height
    difference h = 8 ft, gap s = 6 ft (under 20 ft and under 6h = 48 ft). gamma = 0.13(40) + 14 = 19.2 pcf. Leeward: hd by Eq. 7.6-1 for 60 ft;
    height = the smaller of hd and (48 - 6)/6 = 7 ft, so hd; extent = the smaller of 6 hd and 42 ft; pd = hd gamma. With h = 3 ft and s = 12 ft:
    (18 - 12)/6 = 1.0 ft governs the height and 6 ft the extent. No drift where s is 20 ft or more, or not under 6h."""
    from strukit import snow, calcsheet
    from strukit.gui import calc
    hd = snow.drift_height(40, 60, 0.45)
    r = snow.lower_roof(40, 0.45, 30, 60, 40, 8, separation=6)
    assert r.leeward.height == pytest.approx(hd) and r.leeward.width == pytest.approx(6 * hd) and r.leeward.pd == pytest.approx(hd * 19.2) and hd < 7
    assert r.windward.width == pytest.approx(8 * r.windward.hd_eq) and r.governing.kind == "leeward"
    r = snow.lower_roof(40, 0.45, 30, 60, 40, 3, separation=12)
    assert r.leeward.height == pytest.approx(1.0) and r.leeward.width == pytest.approx(6.0)
    for h, s_ in ((8, 20), (3, 18.5), (8, 60)):
        n = snow.lower_roof(40, 0.45, 30, 60, 40, h, separation=s_)
        assert not n.required and "7.7.2" in n.why
    same = snow.lower_roof(40, 0.45, 30, 60, 40, 8)
    assert snow.lower_roof(40, 0.45, 30, 60, 40, 8, separation=0).leeward.width == same.leeward.width
    with pytest.raises(snow.SnowError):
        snow.lower_roof(40, 0.45, 30, 60, 40, 8, parapet=True, separation=6)
    proj = dict(job="2026-000", name="Test", method="ASD")
    v = dict(mark="SD4", pg="40", pg_source="ASCE 7 Hazard Tool", W2="0.45", W2_source="ASCE 7 Hazard Tool", ps="30", ps_source="sheet SN1", at="a roof step (lower roof beside a higher roof)",
             lu_upper="60", lu_lower="40", step="8", separation="6", slide="no")
    sheet, _, _ = calc.build("snow_drift", v, proj)
    assert dict(sheet.info)["Separation"].startswith("6 ft") and any("7.7.2" in str(getattr(l, "source", "")) for l in sheet.steps)
    assert "sliding snow (Sect. 7.9)" in sheet.not_checked and sheet.blocks[0]["picture"][1]["gap"] == 6
    calcsheet._simple_pdf(sheet, str(tmp_path / "g.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")


def test_sliding_snow_across_a_gap():
    """ASCE/SEI 7-22 Sect. 7.9, separated structures (page text, pdf pp. 128-129): considered when h/s > 1 and s < 15 ft; extent 15 - s;
    load per foot of eave 0.4 pf W (15 - s)/15. pf = 28 psf, W = 20 ft, h = 8 ft, s = 6 ft: 0.4(28)(20) = 224 plf; over 15 ft: 14.93 psf;
    on the lower roof over 9 ft: 134.4 plf = 224(9/15). s = 10 ft with h = 8 ft: h/s under 1, none. s = 15 ft: none."""
    from strukit import snow
    sl = dict(pf=28, W=20, rise_on_12=4, slippery=False)
    r = snow.lower_roof(40, 0.45, 30, 60, 40, 8, sliding=sl, separation=6)
    assert r.sliding_psf == pytest.approx(224 / 15) and r.sliding_extent == 9 and r.sliding_total == pytest.approx(224 * 9 / 15)
    assert snow.lower_roof(40, 0.45, 30, 60, 40, 8, sliding=sl).sliding_extent == 15
    for h, s_ in ((8, 10), (20, 15), (20, 16)):
        n = snow.lower_roof(40, 0.45, 30, 60, 40, h, sliding=sl, separation=s_)
        assert n.sliding_psf == 0 and "7.9" in n.sliding_why
    from strukit.gui import calc
    v = dict(mark="SD5", pg="40", pg_source="Hazard Tool", W2="0.45", W2_source="Hazard Tool", ps="30", ps_source="SN1", at="a roof step (lower roof beside a higher roof)",
             lu_upper="60", lu_lower="40", step="8", separation="6", slide="yes", s_pf="28", s_pf_source="SN1", s_W="20", s_rise="4", s_slippery="no")
    sheet, _, _ = calc.build("snow_drift", v, dict(job="2026-000", name="Test", method="ASD"))
    assert sheet.drift.sliding_extent == 9 and not any("sliding" in t for t in sheet.not_checked)


def test_snow_loads_api_for_member_screens():
    """Beam and joist screens take the uniform design snow load from a roof snow sheet: the larger of the balanced case and the minimum."""
    from strukit.gui import server, calc
    v = _typed()
    sheet, _, _ = calc.build("snow", v, {})
    got = server.api("/api/snow_loads", dict(values=v, project={}))
    r = sheet.snow
    assert got["uniform_design"] == pytest.approx(r.uniform_design) and got["ps"] == pytest.approx(r.ps) and got["unbalanced"] == bool(r.unbalanced)
    assert got["governs"].startswith("minimum" if r.pm > r.balanced else "balanced")
    assert "not complete" in server.api("/api/snow_loads", dict(values=dict(v, pg=""), project={}))["error"]


def test_intersecting_drifts_at_a_reentrant_corner(tmp_path):
    """ASCE/SEI 7-22 Sect. 7.7.3 as printed (pdf p. 126): each drift by Sect. 7.7.1 with the roof lengths perpendicular to its wall; where the
    two overlap the larger drift depth governs and the two are not added.  Each drift equals the Snow Drift sheet's result for the same wall;
    by hand at a point 25 percent of the way across drift A and at wall B: the larger of 0.75 hA gamma and hB gamma."""
    from strukit import calcsheet, snow as sn
    from strukit.gui import calc
    v = dict(mark="SC1", pg="40", pg_source="jurisdiction", W2="0.45", W2_source="Hazard Tool", ps="30", ps_source="sheet SN1",
             a_name="Wall A", a_step="8", a_lu_upper="60", a_lu_lower="30", b_name="Wall B", b_step="8", b_lu_upper="30", b_lu_lower="40")
    s, kind, _ = calc.build("snow_corner", v, {})
    ga, gb = sn.lower_roof(40, 0.45, 30, 60, 30, 8).governing, sn.lower_roof(40, 0.45, 30, 30, 40, 8).governing
    a, b, at = s.corner["a"], s.corner["b"], s.corner["at"]
    assert kind == "simple" and (a["pd"], a["w"], b["pd"], b["w"]) == pytest.approx((ga.pd, ga.width, gb.pd, gb.width))
    assert at(0, 0) == pytest.approx(max(ga.pd, gb.pd)) and at(0.25 * ga.width, 0) == pytest.approx(max(0.75 * ga.pd, gb.pd))
    assert at(0.5 * ga.width, 0.5 * gb.width) == pytest.approx(max(0.5 * ga.pd, 0.5 * gb.pd)) and at(ga.width, gb.width) == pytest.approx(0.0)
    assert at(ga.width + 1, 0.25 * gb.width) == pytest.approx(0.75 * gb.pd) and at(0, gb.width + 5) == pytest.approx(ga.pd)
    calcsheet.simple_pdf(s, str(tmp_path / "c.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    low, _, _ = calc.build("snow_corner", dict(v, b_step="1.7"), {})                     # hc/hb under 0.2 at wall B: no drift there
    assert low.corner["b"]["pd"] == 0.0 and low.corner["at"](0, 0) == pytest.approx(ga.pd)
    calcsheet.simple_pdf(low, str(tmp_path / "c2.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    assert calc.results("snow_corner", dict(v, b_lu_upper=""), {})["state"] == "incomplete"
