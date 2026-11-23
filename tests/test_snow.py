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
