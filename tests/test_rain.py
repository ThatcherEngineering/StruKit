"""Rain loads, ASCE/SEI 7-22 Chapter 8 and AISC Design Guide 40.

References: AISC Design Guide 40 (Rain Loads and Ponding), Example 1 (existing dead flat roof, Tampa:
Q = 149 gal/min, Cp = 0.519, Cs = 0.161, Bp = 4.13, R = 122 psf) and Example 2 (24 in. channel scupper,
Q = 304 gal/min, dh = 2.68 in.); ASCE/SEI 7-22 Eq. 8.2-1 and Table 8.2-1 as printed."""
import pytest

from strukit import rain


def test_design_guide_40_example_1():
    assert rain.flow(50 * 38, 7.55) == pytest.approx(149, abs=0.5)
    Cp, Cs = rain.flexibility(50, 38, 6.25, 0.8 * 1830, 258.5)
    assert Cp == pytest.approx(0.519, abs=0.0006) and Cs == pytest.approx(0.161, abs=0.0006)
    r = rain.ponded(15, 2.0, 1.5, Cp, Cs)
    assert r["w0"] == pytest.approx(33.2) and r["Bp"] == pytest.approx(4.13, abs=0.02)
    assert r["total"] == pytest.approx(137, abs=1.0) and r["R"] == pytest.approx(122, abs=1.0)
    assert rain.rain_load(2.0, 1.5, r["dp"]) == pytest.approx(r["R"])


def test_design_guide_40_example_2_scupper():
    Q = rain.flow(4800, 6.09)
    assert Q == pytest.approx(304, abs=0.5) and rain.scupper_head(Q, 24) == pytest.approx(2.68, abs=0.005)


def test_general_stiffness_matches_the_steel_constants_and_instability_stops():
    a = rain.flexibility(50, 38, 6.25, 1464, 258.5)
    b = rain.flexibility(50, 38, 6.25, 1464, 258.5, Ep=29e6, Es=29e6)
    assert b[0] == pytest.approx(a[0], rel=0.01) and b[1] == pytest.approx(a[1], rel=0.01)
    assert rain.RETURN_PERIOD == {"I": 100, "II": 100, "III": 200, "IV": 500}
    with pytest.raises(rain.RainError):
        rain.amplification(0.6, 0.4)
    with pytest.raises(rain.RainError):
        rain.rain_load(-1, 0)


def test_rain_load_screen_and_sheet(tmp_path):
    """The screen on Design Guide 40 Example 1 (typed hydraulic head 1.5 in.) and with the Example 2 scupper."""
    from strukit import calcsheet
    from strukit.gui import calc
    v = dict(mark="RN1", risk="II", i="7.55", i_source="ASCE 7 Hazard Tool, Tampa, 100 year 15 minute", A="1900", ds="2", ds_source="secondary drain inlet 2 in. above the roof",
             head_type="typed in", dh="1.5", dh_source="ASCE 7-22 Table C8.2-1, 8 in. overflow dam", pond_type="from the bay stiffness", D="15", D_source="roof dead load",
             Lp="50", Ls="38", S="6.25", primary="structural steel member", Ip="1830", secondary="effective moment of inertia entered", Is="258.5")
    s, kind, _ = calc.build("rain_load", v, {})
    assert kind == "simple" and s.rain["R"] == pytest.approx(122, abs=1.0) and s.rain["Q"] == pytest.approx(149, abs=0.5)
    assert s.rows[0].demand == pytest.approx(1.15 * 0.519 + 0.161, abs=0.002) and s.rows[0].capacity == 1.0
    calcsheet.simple_pdf(s, str(tmp_path / "r.pdf"), "Job", "ASCE/SEI 7-22", "Nov 23, 2026")
    t, _, _ = calc.build("rain_load", dict(v, i="6.09", A="4800", head_type="channel scupper", scupper_w="24", pond_type="typed in", dp="0.5", dp_source="roof analysis"), {})
    assert t.rain["dh"] == pytest.approx(2.68, abs=0.005) and t.rain["R"] == pytest.approx(5.2 * (2 + t.rain["dh"] + 0.5))
    soft, _, _ = calc.build("rain_load", dict(v, Ip="900", Is="150"), {})
    assert soft.rain["R"] is None and soft.rows[0].demand > 1.0
    wood_bay, _, _ = calc.build("rain_load", dict(v, primary="other material", Ep="29000000", Ip="1464"), {})
    assert wood_bay.rain["R"] == pytest.approx(s.rain["R"], rel=0.03)
    assert calc.results("rain_load", dict(v, D=""), {})["state"] == "incomplete"
    assert calc.results("rain_load", dict(v, primary="other material"), {})["state"] == "incomplete"
