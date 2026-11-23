"""Round HSS members, AISC 360-22 Sect. E3, F8, G5.

Reference: AISC Design Guide 34, Example 10.1.7, guard top rail HSS1.900x0.145, ASTM A500 Grade C (Fy 46 ksi), 4 ft long:
D/t 14.1 nonslender (limit 69.3), Lc/r = 76.7, Fcr = 31.0 ksi, Pn = 23.2 kips; shear Fcr = 27.6 ksi, Vn = 10.3 kips, Vn/1.67 = 6.17 kips;
flexure (Manual Table 3-14) phi Mn = 1.45 kip-ft, Mn/1.67 = 0.966 kip-ft.  Limits as printed in AISC 360-22 Table B4.1a Case 9 and B4.1b Case 20."""
import pytest

from strukit import hss, shapes


def test_guard_rail_of_design_guide_34():
    p = shapes.hss("HSS1.900x0.145")
    c = hss.compression(p, 46.0, 48.0)
    assert c["lam_r"] == pytest.approx(69.3, abs=0.05) and c["Lc_r"] == pytest.approx(76.7, abs=0.05) and c["limit"] == pytest.approx(118, abs=0.5)
    assert c["Fcr"] == pytest.approx(31.0, abs=0.05) and c["Pn"] == pytest.approx(23.2, abs=0.05) and c["eq"] == "E3-2"
    v = hss.shear(p, 46.0, Lv=24.0)
    assert v["Fcr"] == pytest.approx(27.6) and v["yield_governs"] and v["Vn"] == pytest.approx(10.3, abs=0.05)
    assert hss.available(v["Vn"], "shear", "ASD") == pytest.approx(6.17, abs=0.03)
    f = hss.flexure(p, 46.0)
    assert f["cls"] == "compact" and hss.available(f["Mn"], "flexure", "LRFD") / 12 == pytest.approx(1.45, abs=0.005)
    assert hss.available(f["Mn"], "flexure", "ASD") / 12 == pytest.approx(0.966, abs=0.001)


def test_round_hss_limit_states_by_hand():
    """Hand checks: a D/t 60 pipe at Fy 35: lambda_p = 0.07(29000)/35 = 58.0, so noncompact: Mn = (0.021(29000)/60 + 35) S = 45.15 S.
    Long column, Lc/r = 200 > 4.71 (29000/46)^0.5 = 118.3: Fcr = 0.877 pi^2 (29000)/200^2 = 6.275 ksi."""
    fake = dict(type="PIPE", OD=12.0, tdes=0.2, D_t=60.0, Zx=30.0, Sx=22.0, rx=4.0, A=7.4)
    f = hss.flexure(fake, 35.0)
    assert f["cls"] == "noncompact" and f["Mn"] == pytest.approx(45.15 * 22.0)
    assert hss.flexure(dict(fake, D_t=300.0), 35.0)["cls"] == "slender"
    with pytest.raises(hss.HSSError):
        hss.flexure(dict(fake, D_t=400.0), 35.0)
    with pytest.raises(hss.HSSError):
        hss.compression(dict(fake, D_t=100.0), 35.0, 100.0)
    p = shapes.hss("HSS1.900x0.145")
    c = hss.compression(p, 46.0, 200 * p["rx"])
    assert c["eq"] == "E3-3" and c["Fcr"] == pytest.approx(6.275, abs=0.002)
    with pytest.raises(hss.HSSError):
        hss.flexure(shapes.hss("HSS6x4x1/4"), 46.0)
    assert hss.shear(p, 46.0)["Fcr"] == pytest.approx(27.6)


def test_guard_screen_against_design_guide_34(tmp_path):
    """Design Guide 34 Example 10.1.7 (ASD): rail HSS1.900x0.145 at 4 ft: Ma = 0.205 kip-ft and Va = 0.205 kip under the 200 lb load,
    0.105 kip-ft and 0.105 kip under 50 lb/ft; Mn/1.67 = 0.966 kip-ft. LRFD: Mu = 0.327 kip-ft, phi Mn = 1.45 kip-ft.
    Post, by hand: 200 lb x 3.5 ft = 700 lb-ft; 50 lb/ft x 4 ft x 3.5 ft = 700 lb-ft. Loads as printed in ASCE/SEI 7-22 Sect. 4.5.1."""
    from strukit import calcsheet, ws_more
    from strukit.gui import calc
    assert (ws_more.GUARD_P, ws_more.GUARD_W, ws_more.GUARD_INFILL) == (200.0, 50.0, 50.0)
    v = dict(mark="GD1", rail="HSS1.900x0.145", rail_Fy="46", rail_Fy_source="ASTM A500 Grade C", post="HSS1.900x0.145", post_Fy="46", post_Fy_source="ASTM A500 Grade C",
             spacing="4", height="3.5", uniform="applies")
    s, kind, _ = calc.build("guard", v, dict(method="ASD"))
    r = {x.check: x for x in s.rows}
    assert kind == "simple" and r["Top rail bending"].demand == pytest.approx(205.4, abs=0.1) and r["Top rail bending"].capacity == pytest.approx(966, abs=1)
    assert r["Top rail shear"].demand == pytest.approx(205.4, abs=0.1) and r["Post bending"].demand == pytest.approx(700.0)
    uni = [c for c in s.guard["cases"] if c[0] == "50 lb/ft"][0]
    assert uni[1] == pytest.approx(105.4, abs=0.1) and uni[2] == pytest.approx(105.4, abs=0.1)
    calcsheet.simple_pdf(s, str(tmp_path / "g.pdf"), "Job", "AISC 360-22", "Nov 23, 2026")
    l, _, _ = calc.build("guard", v, dict(method="LRFD"))
    rl = {x.check: x for x in l.rows}
    assert rl["Top rail bending"].demand == pytest.approx(327, abs=1) and rl["Top rail bending"].capacity == pytest.approx(1450, abs=5)
    e, _, _ = calc.build("guard", dict(v, uniform="exception", uniform_basis="one- and two-family dwelling", spacing="6"), dict(method="ASD"))
    assert len(e.guard["cases"]) == 1 and {x.check: x for x in e.rows}["Post bending"].demand == pytest.approx(700.0)
    assert calc.results("guard", dict(v, uniform="exception"), dict(method="ASD"))["state"] == "incomplete"
    assert calc.results("guard", v, {})["state"] == "incomplete"
    bad = calc.results("guard", dict(v, post="HSS6x4x1/4"), dict(method="ASD"))
    assert bad["state"] != "ok" if "state" in bad else True
