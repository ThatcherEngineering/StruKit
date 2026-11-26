"""Crane runway beam: ASCE/SEI 7-22 Sect. 4.9 crane loads and moving wheels on a simple span. No published crane runway example is on file
(AISC Design Guide 7 is not on hand); the loads are checked against the standard's text, the moving-load analysis against the closed-form
two-wheel moment and a brute-force sweep, and the member strengths come from the steel beam functions validated elsewhere."""
import pytest

from strukit import calcsheet, crane, shapes, steel_beam, steel_beamcol
from strukit.gui import calc
from strukit.ws_more import crane_runway_sheet
from strukit.ws_steel_beam import Combo, WorksheetError

LR = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t")]


def test_asce7_crane_loads():
    c = crane.loads("bridge crane, service class A, B or C", 10, 2.2, 8.5, 2, True, 0.5)
    assert c["impact"] == 0.10 and c["P_imp"] == pytest.approx(9.35) and c["H_total"] == pytest.approx(2.44) and c["H"] == pytest.approx(0.61)
    assert c["LF"] == pytest.approx(1.7)                                       # 10% of the two maximum wheel loads (4.9.5)
    d = crane.loads("bridge crane, service class D, E or F", 10, 2.2, 8.5, 2, False, 0.5)
    assert d["impact"] == 0.25 and d["H"] == 0.0                              # no powered trolley, no lateral force (4.9.4)
    h = crane.loads("hand-geared bridge, trolley and hoist", 10, 2.2, 8.5, 2, False, 0.5)
    assert h["impact"] == 0.0 and h["LF"] == 0.0
    assert crane.loads("monorail crane (powered)", 4, 0.5, 2.5, 1, True, 1.0)["impact"] == 0.25


@pytest.mark.parametrize("L, a", [(20, 10), (20, 4), (30, 25), (12, 9)])
def test_moving_two_wheels_against_the_closed_form(L, a):
    m = crane.moving(L, 10.0, a, 2, step=L / 4000)
    assert m["M"] == pytest.approx(crane.two_wheel_closed_form(L, 10.0, a), rel=2e-4)
    assert m["R"] == pytest.approx(10 + (10 * (L - a) / L if a < L else 0))


def test_sheet(tmp_path):
    s = crane_runway_sheet("CR1", "W18X50", 50, "A992", 20, 40, "ASCE 40 lb rail", "bridge crane, service class A, B or C", "light shop", 10, 2.2, 8.5, "maker", 2, 10,
                           True, 0.5, "two equal runways", LR, "LRFD", defl=dict(v_ratio=600, h_ratio=400, source="typed for the test"))
    p = shapes.get("W18X50")
    Mcx = steel_beam.check(p, 50, 240, 1.0, "LRFD").M_avail / 12
    Mcy = steel_beamcol.weak_axis_flexure(p, 50, "LRFD").available / 24
    mv = crane.two_wheel_closed_form(20, 9.35, 10)
    wD = (50 + 40) / 1000
    Mx = 1.2 * wD * 12.5 * 7.5 / 2 + 1.6 * mv                                # dead moment at the wheel under the largest moment (12.5 ft)
    My = 1.6 * mv * 0.61 / 9.35
    assert s.crane["Mx"] == pytest.approx(Mx, rel=1e-3) and s.crane["ratio"] == pytest.approx(Mx / Mcx + My / Mcy, rel=1e-3)
    assert s.crane["V"] == pytest.approx(1.2 * wD * 10 + 1.6 * (9.35 + 9.35 * 10 / 20), rel=1e-6) and s.ok
    assert s.crane["dv"] == pytest.approx(crane.deflection_mid(20, 29000 * p["Ix"], [(8.5, 5), (8.5, 15)]), rel=1e-9)
    calcsheet.simple_pdf(s, str(tmp_path / "cr.pdf"), "Job", "AISC 360-22", "Nov 25, 2026")
    with pytest.raises(WorksheetError):
        crane_runway_sheet("CR1", "HSS8X8X1/2", 50, "A500", 20, 0, "", "bridge crane, service class A, B or C", "x", 10, 2, 8.5, "maker", 2, 10, True, 0.5, "x", LR, "LRFD")


def test_screen():
    v = dict(mark="CR1", beam="W18X50", Fy="50", beam_source="ASTM A992", span="20", rail="40", rail_note="ASCE 40 lb", crane_type="bridge crane, service class A, B or C",
             class_basis="light repair shop", capacity="10", trolley="2.2", wheel="8.5", wheel_source="maker's data", n="2", spacing="10", powered="yes", share="0.5",
             share_source="two equal runway beams", defl_v="", defl_h="", defl_source="")
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-25", combos=[dict(expr="D + L", source="ASCE/SEI 7-22 Sect. 2.4.1")])
    s, _, _ = calc.build("crane_runway", v, proj)
    assert s.ok and "deflection limits" in s.not_checked


def test_web_local_yielding_and_crippling_under_the_wheels():
    """AISC Design Examples v16.0 Example J.7 (W24x55, Fy 50, lb 7.50 in., load away from the end): Eq. J10-2 248 kips and Eq. J10-4 282 kips;
    at the member end, Eq. J10-3 and J10-5a / J10-5b by hand. On the runway sheet the wheel is taken at the beam end."""
    import math
    p = shapes.get("W24X55")
    a = crane.web_under_wheel(p, 50, 7.5, at_end=False)
    assert a["Ry"] == pytest.approx(248, rel=0.003) and a["Rc"] == pytest.approx(282, rel=0.003)
    e = crane.web_under_wheel(p, 50, 3.0, at_end=True)
    root = math.sqrt(29000 * 50 * p["tf"] / p["tw"])
    assert e["Ry"] == pytest.approx(50 * p["tw"] * (2.5 * p["kdes"] + 3.0)) and e["eq_c"] == "Eq. J10-5a"
    assert e["Rc"] == pytest.approx(0.40 * p["tw"] ** 2 * (1 + 3 * (3.0 / p["d"]) * (p["tw"] / p["tf"]) ** 1.5) * root)
    e2 = crane.web_under_wheel(p, 50, 6.0, at_end=True)
    assert e2["eq_c"] == "Eq. J10-5b" and e2["Rc"] == pytest.approx(0.40 * p["tw"] ** 2 * (1 + (4 * 6.0 / p["d"] - 0.2) * (p["tw"] / p["tf"]) ** 1.5) * root)
    s = crane_runway_sheet("CR1", "W18X50", 50, "A992", 20, 40, "ASCE 40 lb rail", "bridge crane, service class A, B or C", "light shop", 10, 2.2, 8.5, "maker", 2, 10,
                           True, 0.5, "two equal runways", LR, "LRFD", lb_wheel=2.0, lb_source="rail base")
    r = {x.check: x for x in s.rows}
    w = crane.web_under_wheel(shapes.get("W18X50"), 50, 2.0)
    assert r["Web local yielding under a wheel"].capacity == pytest.approx(w["Ry"]) and r["Web local crippling under a wheel"].capacity == pytest.approx(0.75 * w["Rc"])
    assert r["Web local yielding under a wheel"].demand == pytest.approx(1.6 * 8.5 * 1.1)


def test_continuous_runway(tmp_path):
    """Moving load on two equal spans: one wheel P gives the largest positive moment 0.2074 P L (at 0.432 L) and the largest negative moment
    0.0962 P L over the middle support (load at L / 3^0.5 from the end: P a (L^2 - a^2) / (4 L^2)); a single span matches the simple-span
    moving-load result. On the sheet: positive and negative moments, Eq. H1-1b and shear over the spans."""
    r = crane.moving_continuous([30.0, 30.0], 20.0, 10.0, 1, 29000 * 800.0)
    assert r["Mpos"] == pytest.approx(0.2074 * 20 * 30, rel=0.002) and r["Mneg"] == pytest.approx(-20 * 30 / 3 ** 0.5 * (2 / 3) / 4, rel=0.002)
    assert r["R"] == pytest.approx(20.0, rel=1e-6)
    one = crane.moving_continuous([20.0], 9.35, 10.0, 2, 29000 * 800.0)
    assert one["Mpos"] == pytest.approx(crane.two_wheel_closed_form(20, 9.35, 10), rel=0.002)
    s = crane_runway_sheet("CR1", "W18X50", 50, "A992", 20, 40, "ASCE 40 lb rail", "bridge crane, service class A, B or C", "light shop", 10, 2.2, 8.5, "maker", 2, 10,
                           True, 0.5, "two equal runways", LR, "LRFD", defl=dict(v_ratio=600, h_ratio=400, source="typed"), spans=[20.0, 20.0, 20.0])
    names = [x.check for x in s.rows]
    assert "Flexure, negative moment over a support" in names and "continuous runway beams" not in s.not_checked
    calcsheet.simple_pdf(s, str(tmp_path / "crc.pdf"), "Job", "AISC 360-22", "Nov 26, 2026")
