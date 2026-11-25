"""Shear lug against AISC Design Guide 1 (3rd Ed.) Example 4.7-5: W14x90 on a 30 in. wall, f'c 4 ksi; PL 1 x 8 in. lug (A572 Gr. 50) 2 in. into
the concrete below 2 in. of grout; 15 x 15 x 1 in. plate; four 3/4 in. F1554 Gr. 36 rods at 8-1/2 in., 12 in. embedment; 5/16 in. E70 fillets;
Vu = 25.0, Va = 16.0 kips (wind).  Published: e 3.00 in.; fp 4.42 / 2.94 ksi; qmax 66.3 / 44.1 kip/in; Y 0.0967 / 0.0930 in.; T 6.41 / 4.10;
rod 3.21 / 2.05 kips; hef min 10.6 in.; bearing 70.9 kips; ca1 14.5, Avc 1,210, Avco 946 in2, Vb 31.4, Vcb 40.2, 26.1 kips; lug shear 240 / 160
and 234 / 156; flexure 90.0 / 59.9 and 97.5 / 65.0 kip-in.; Eq. 9-1 0.833 / 0.801; weld a 1.21 in., 7.91 / 5.06 against 10.4 / 6.95 kip/in;
plate 47.8 / 30.6 against 90.0 / 59.9 kip-in."""
import pytest

from strukit import calcsheet
from strukit.gui import calc
from strukit.ws_more import shear_lug_sheet
from strukit.ws_steel_beam import Combo, WorksheetError

GEOM = (8, 1, 2, 2, 50, 65, "A572 Gr. 50", 5 / 16, 70, 15, 15, 1.0, 50, 8.5, 0.75, 58, "F1554 Gr. 36", 12, 4, 4, 14.5, 99, 99, 1.0)


def _rows(s):
    return {r.check: r for r in s.rows}


def test_example_4_7_5(tmp_path):
    lr = [Combo("1.0W", {"W": 1.0}, "t")]
    s = shear_lug_sheet("SL", *GEOM, [dict(case="W", V=25.0, P=0.0)], lr, lr, "LRFD")
    r, d = _rows(s), s.shear_lug["steel"][0]
    assert s.shear_lug["e"] == 3.0 and s.shear_lug["fp"] == pytest.approx(4.42) and d["q"] == pytest.approx(66.3)
    assert d["Y"] == pytest.approx(0.0967, abs=0.0002) and d["T"] == pytest.approx(6.41, abs=0.01) and d["rod"] == pytest.approx(3.21, abs=0.01)
    assert r["Lug shear yielding"].capacity == pytest.approx(240) and r["Lug shear rupture"].capacity == pytest.approx(234)
    assert r["Lug flexural yielding"].capacity == pytest.approx(90.0) and r["Lug flexural rupture"].capacity == pytest.approx(97.5)
    assert r["Lug flexure and shear (Manual Eq. 9-1)"].demand == pytest.approx(0.833, abs=0.001)
    assert r["Lug welds to the plate"].demand == pytest.approx(7.91, abs=0.01) and r["Lug welds to the plate"].capacity == pytest.approx(10.4, abs=0.05)
    assert r["Base plate bending at the lug"].demand == pytest.approx(47.8, abs=0.1) and r["Base plate bending at the lug"].capacity == pytest.approx(90.0)
    assert r["Concrete bearing on the lug"].capacity == pytest.approx(70.9, rel=0.004)                  # the example rounds 108.8 to 109 kips first
    c = s.shear_lug["concrete"][0]["c"]
    assert c["Avc"] == pytest.approx(1210, rel=0.003) and c["Avco"] == pytest.approx(946, abs=0.5) and c["Vb"] == pytest.approx(31.4, abs=0.05)
    assert c["Vcb"] == pytest.approx(40.2, rel=0.004) and c["phiVcb"] == pytest.approx(26.1, abs=0.05)
    assert r["Anchor rod embedment"].demand == pytest.approx(10.625) and s.ok
    calcsheet.simple_pdf(s, str(tmp_path / "sl.pdf"), "Job", "AISC 360-22", "Nov 25, 2026")


def test_example_4_7_5_asd():
    asd, lr = [Combo("D + 0.6W", {"W": 0.64}, "t")], [Combo("1.0W", {"W": 1.0}, "t")]     # 0.64 x 25 = 16.0 kips
    s = shear_lug_sheet("SL", *GEOM, [dict(case="W", V=25.0, P=0.0)], asd, lr, "ASD")
    r, d = _rows(s), s.shear_lug["steel"][0]
    assert s.shear_lug["fp"] == pytest.approx(2.94, abs=0.005) and d["q"] == pytest.approx(44.1, abs=0.1) and d["Y"] == pytest.approx(0.0930, abs=0.0003)
    assert d["T"] == pytest.approx(4.10, abs=0.01) and d["rod"] == pytest.approx(2.05, abs=0.01)
    assert r["Lug shear yielding"].capacity == pytest.approx(160) and r["Lug shear rupture"].capacity == pytest.approx(156)
    assert r["Lug flexural yielding"].capacity == pytest.approx(59.9, abs=0.05) and r["Lug flexural rupture"].capacity == pytest.approx(65.0)
    assert r["Lug flexure and shear (Manual Eq. 9-1)"].demand == pytest.approx(0.801, abs=0.002)
    assert r["Lug welds to the plate"].demand == pytest.approx(5.06, abs=0.01) and r["Lug welds to the plate"].capacity == pytest.approx(6.95, abs=0.02)
    assert r["Base plate bending at the lug"].demand == pytest.approx(30.6, abs=0.1)


def test_axial_compression_and_refusals():
    lr = [Combo("1.2D + 1.0W", {"D": 1.2, "W": 1.0}, "t")]
    s = shear_lug_sheet("SL", *GEOM, [dict(case="W", V=25.0, P=0.0), dict(case="D", V=0.0, P=50.0)], lr, lr, "LRFD")
    c = s.shear_lug["concrete"][0]["c"]
    assert c["psi_brg"] == pytest.approx(min(1 + 4 * 60 / (225 * 4), 2.0))                            # Eq. 17.11.2.2.1c
    with pytest.raises(WorksheetError):
        shear_lug_sheet("SL", *GEOM, [dict(case="W", V=25.0, P=-10.0)], lr, lr, "LRFD")


def test_screen():
    v = dict(mark="SL1", bsl="8", tsl="1", hsl="2", t_grout="2", lug_Fy="50", lug_Fu="65", lug_source="ASTM A572 Gr. 50", weld="0.3125", FEXX="70", N="15", B="15", tbp="1",
             bp_Fy="50", s_rod="8.5", rod_d="0.75", rod_Fu="58", rod_source="ASTM F1554 Gr. 36", hef_rod="12", fc="4000", A2A1="4", ca1="14.5", ca2="99", ha="99",
             psi_c="cracked, no supplementary reinforcement (1.0)", loads=[dict(case="W", V="40", P="", label="")])
    proj = dict(name="T", number="1", address="", method="ASD", date="2026-11-25", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1")],
                combos_lrfd=[dict(expr="1.2D + 1.0W", source="ASCE/SEI 7-22 Sect. 2.3.1")])
    s, _, _ = calc.build("shear_lug", v, proj)
    assert s.title == "Shear Lug" and s.shear_lug["concrete"][0]["V"] == pytest.approx(40.0) and s.shear_lug["steel"][0]["V"] == pytest.approx(24.0)
