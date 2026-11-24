"""Sawn lumber beams, 2018 NDS.

Independent references:
  - Job 2026-011 (sealed StruCalc package, page 22), "Header A LL": (3) 2x8 Douglas
    Fir-Larch No. 2, 4 ft span, D + L, 1,627.44 plf total: Fb 900, CF 1.2, Fb' 1,080 psi;
    bending 990.8 psi, shear 149.6 psi, bearing 241.1 psi on 3 in, deflection 0.041 in.
  - 2018 NDS Supplement Table 1B section properties (A, Sxx, Ixx as printed).
  - Hand calculations of NDS Eq. 3.3-5 and 3.3-6, written out below.
"""
import csv
import math
import os

import pytest

from strukit import wood, ws_wood
from strukit.ws_steel_beam import Combo, DeflCheck, WorksheetError

DL = [Combo("D + L", {"D": 1, "L": 1}, "typed in")]
HEADER = [dict(case="L", kind="uniform", w=297), dict(case="D", kind="uniform", w=112), dict(case="D", kind="uniform", w=315),
          dict(case="L", kind="uniform", w=598), dict(case="D", kind="uniform", w=298), dict(case="D", kind="uniform", w=7.44)]


def _row(s, name):
    return next(r for r in s.rows if r.check.startswith(name))


def test_job_2026_011_header_a():
    s = ws_wood.beam("H-A", "DOUGLAS FIR-LARCH", "No. 2", "2x8", 3, 4.0, HEADER, DL, [DeflCheck("total", {"D": 1, "L": 1}, 240, "typed in")],
                     0.0, 3.0, False, False, False)
    assert _row(s, "bending").demand == pytest.approx(990.8, abs=0.1) and _row(s, "bending").capacity == pytest.approx(1080.0)
    assert _row(s, "shear").demand == pytest.approx(149.6, abs=0.1) and _row(s, "shear").capacity == pytest.approx(180.0)
    assert _row(s, "bearing").demand == pytest.approx(241.1, abs=0.1) and _row(s, "bearing").capacity == pytest.approx(625.0)
    assert _row(s, "deflection").demand == pytest.approx(0.041, abs=0.0006) and _row(s, "deflection").capacity == pytest.approx(0.2)


def test_table_1b_section_properties():
    path = os.path.join(os.path.dirname(wood.__file__), "data", "nds2018_table1b.csv")
    n = 0
    for r in csv.DictReader(open(path)):
        b, d = float(r["b"]), float(r["d"])
        assert b * d == pytest.approx(float(r["A"]), rel=0.002)
        assert b * d * d / 6 == pytest.approx(float(r["Sxx"]), rel=0.003)
        assert b * d ** 3 / 12 == pytest.approx(float(r["Ixx"]), rel=0.003)
        n += 1
    assert n > 80 and wood.SIZES["2x10"] == (1.5, 9.25) and wood.SIZES["4x12"] == (3.5, 11.25)


def test_table_4a_values_and_size_factors():
    v, CF, _ = wood.values("DOUGLAS FIR-LARCH", "No. 2", "2x10")
    assert (v["Fb"], v["Fv"], v["Fc_perp"], v["E"], v["Emin"], CF) == (900, 180, 625, 1600000, 580000, 1.1)
    assert wood.values("HEM-FIR", "No. 2", "2x12")[0]["Fb"] == 850 and wood.values("HEM-FIR", "No. 2", "2x12")[1] == 1.0
    assert wood.values("SPRUCE-PINE-FIR", "No. 1/ No. 2", "2x6")[0]["Fb"] == 875
    assert wood.values("DOUGLAS FIR-LARCH", "Select Structural", "4x10")[1] == 1.2      # 4 in. thick column of the table
    assert wood.values("DOUGLAS FIR-LARCH", "No. 2", "2x14")[1] == 0.9
    assert wood.values("DOUGLAS FIR-LARCH", "Stud", "2x4")[1] == 1.1 and wood.values("DOUGLAS FIR-LARCH", "Stud", "2x6")[1] == 1.0
    v, CF, note = wood.values("DOUGLAS FIR-LARCH", "Stud", "2x8")                       # uses No. 3
    assert v["Fb"] == 525 and CF == 1.2 and "No. 3" in note
    with pytest.raises(wood.WoodError):
        wood.values("DOUGLAS FIR-LARCH", "Construction", "2x6")
    with pytest.raises(wood.WoodError):
        wood.values("SPRUCE-PINE-FIR", "No. 2", "2x6")                                  # SPF lists No. 1/No. 2


def test_load_duration():
    assert wood.load_duration(["D"])[0] == 0.9
    assert wood.load_duration(["D", "L"])[:2] == (1.0, "L")
    assert wood.load_duration(["D", "L", "S"])[:2] == (1.15, "S")
    assert wood.load_duration(["D", "Lr"])[0] == 1.25 and wood.load_duration(["D", "W", "S"])[0] == 1.6
    with pytest.raises(wood.WoodError, match="H"):                      # a case with no duration in the table or by ruling
        wood.load_duration(["D", "H"])


def test_beam_stability_by_hand():
    # one 2x10 braced at 12 ft: lu/d = 144/9.25 = 15.6 > 14.3, le = 1.84 x 144 = 264.96
    # RB = sqrt(264.96 x 9.25 / 1.5^2) = 33.004; FbE = 1.2 x 580,000 / 33.004^2 = 638.95
    # Fb* = 1,000: a = 0.63895; (1 + a)/1.9 = 0.86261; CL = 0.86261 - sqrt(0.86261^2 - 0.63895/0.95) = 0.5952
    CL, st = wood.beam_stability(1000, 580000, 144, 1.5, 9.25)
    assert st["le"] == pytest.approx(264.96) and st["RB"] == pytest.approx(33.004, abs=0.001)
    assert st["FbE"] == pytest.approx(638.95, abs=0.01) and CL == pytest.approx(0.5952, abs=0.0002)
    assert wood.effective_length(48, 9.25) == pytest.approx(2.06 * 48)                   # lu/d < 7
    assert wood.effective_length(96, 9.25) == pytest.approx(1.63 * 96 + 3 * 9.25)        # 7 to 14.3
    assert wood.beam_stability(1000, 580000, 0, 1.5, 9.25)[0] == 1.0                     # supported throughout
    assert wood.beam_stability(1000, 580000, 144, 5.5, 5.5)[0] == 1.0                    # depth not more than breadth
    with pytest.raises(wood.WoodError, match="exceeds 50"):
        wood.beam_stability(1000, 580000, 400, 1.5, 11.25)


def test_wet_incised_repetitive_factors():
    f = wood.factors(900, 1.1, True, True, True)
    assert (f.CM_b, f.CM_v, f.CM_perp, f.CM_E, f.Ci_b, f.Ci_E, f.Cr) == (1.0, 0.97, 0.67, 0.9, 0.80, 0.95, 1.15)   # 900 x 1.1 <= 1,150
    assert wood.factors(900, 1.3, True, False, False).CM_b == 0.85


def test_snow_combination_uses_its_duration_factor_and_governs_by_ratio():
    loads = [dict(case="D", kind="uniform", w=100), dict(case="S", kind="uniform", w=200)]
    cb = [Combo("D", {"D": 1}, "x"), Combo("D + 0.7S", {"D": 1, "S": 0.7}, "x")]
    s = ws_wood.beam("R1", "HEM-FIR", "No. 2", "2x10", 2, 12, loads, cb, [], 0, 3.5, False, False, True)
    r = _row(s, "bending")
    # D + 0.7S: w = 240 plf, M = 240 x 144 / 8 = 4,320 lb-ft; S = 2 x 21.39 = 42.78; fb = 1,211.8
    # Fb' = 850 x 1.15 (CD) x 1.1 (CF) x 1.15 (Cr) = 1,236.5
    assert r.combo == "D + 0.7S" and r.demand == pytest.approx(4320 * 12 / (3 * 9.25 ** 2 / 6), rel=1e-4)
    assert r.capacity == pytest.approx(850 * 1.15 * 1.1 * 1.15, rel=1e-6)


def test_stops_on_bad_input():
    with pytest.raises(WorksheetError, match="Table 4A"):
        ws_wood.beam("X", "HEM-FIR", "No. 1/ No. 2", "2x10", 1, 12, HEADER, DL, [], 0, 3, False, False, False)
    with pytest.raises(WorksheetError, match="load duration"):
        ws_wood.beam("X", "HEM-FIR", "No. 2", "2x10", 1, 12, [dict(case="H", kind="uniform", w=50)], [Combo("H", {"H": 1}, "x")], [], 0, 3,
                     False, False, False)


def test_screen_builds_and_prints(tmp_path):
    from strukit import calcsheet
    from strukit.gui import calc
    proj = dict(method="LRFD", combos_asd=[dict(expr="D + L", source="typed in")], combos_lrfd=[dict(expr="1.2D + 1.6L", source="typed in")])
    v = dict(mark="WB1", species="DOUGLAS FIR-LARCH", grade="No. 2", size="2x8", plies="3", span="4", bracing="supported throughout",
             bearing="3", service="dry service", incised="no", repetitive="no", unit_weight="",
             loads=[dict(case=x["case"], kind="uniform", mag=str(x["w"]), x1="", x2="", label="") for x in HEADER],
             defl=[dict(label="total", expr="D + L", ratio="240", source="typed in")])
    r = calc.results("wood_beam", v, proj)                       # wood uses the ASD list whatever the steel method is
    assert r["state"] == "done" and r["status"] == "OK"
    assert next(x for x in r["rows"] if x["check"] == "bending")["demand"] == pytest.approx(990.8, abs=0.1)
    s, kind, _ = calc.build("wood_beam", v, proj)
    calcsheet.simple_pdf(s, str(tmp_path / "wb.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    assert (tmp_path / "wb.pdf").stat().st_size > 5000
    r = calc.results("wood_beam", dict(v, bracing="braced at a spacing", lu=""), proj)
    assert r["state"] == "incomplete" and any("Brace spacing" in m for m in r["messages"])


# ---------------------------------------------------------------- posts
def test_job_2026_011_deck_column():
    # sealed StruCalc package, page 7: 6x6 Douglas Fir-Larch No. 2, 9 ft, 6,062 lb, D + L:
    # Fc 700 psi, le/d 19.64, compressive stress 200.4 psi against 559.0 psi
    s = ws_wood.post("DC", "DOUGLAS FIR-LARCH", "No. 2", "6x6", 9, [dict(case="L", P=6000), dict(case="D", P=62)], DL, 1.0, 1.0,
                     "pinned top and bottom", False, False)
    r = s.rows[0]
    assert r.demand == pytest.approx(200.4, abs=0.05) and r.capacity == pytest.approx(559.0, abs=0.1)
    assert "le/d = 19.64" in r.note


def test_column_stability_by_hand():
    # FcE = 0.822 x 470,000 / 19.636^2 = 1,002.0; Fc* = 700: a = 1.4314; (1 + a)/1.6 = 1.5196
    # CP = 1.5196 - sqrt(1.5196^2 - 1.4314/0.8) = 0.7985
    CP, st = wood.column_stability(700, 470000, 108, 5.5, 108, 5.5)
    assert st["FcE"] == pytest.approx(1002.0, abs=0.1) and CP == pytest.approx(0.7985, abs=0.0002)
    # the larger slenderness ratio governs
    assert wood.column_stability(700, 470000, 108, 5.5, 60, 3.5)[1]["ratio"] == pytest.approx(108 / 5.5)
    with pytest.raises(wood.WoodError, match="exceeds 50"):
        wood.column_stability(700, 470000, 200, 3.5, 200, 3.5)


def test_post_values_from_both_tables():
    ref, CF, size, table, _ = wood.post_values("DOUGLAS FIR-LARCH", "No. 2", "4x4")
    assert ref["Fc"] == 1350 and CF == 1.15 and size == (3.5, 3.5) and table == "Table 4A"
    assert wood.post_values("DOUGLAS FIR-LARCH", "No. 2", "4x6")[1] == 1.1
    ref, CF, size, table, _ = wood.post_values("HEM-FIR", "No. 1", "8x8")
    assert ref["Fc"] == 850 and CF == 1.0 and size == (7.5, 7.5) and table == "Table 4D, Posts and Timbers"
    assert wood.post_values("DOUGLAS FIR-LARCH", "No. 1", "6x10")[3] == "Table 4D, Beams and Stringers"     # 10 is more than 2 over 6
    assert wood.post_values("DOUGLAS FIR-LARCH", "No. 1", "6x10")[0]["Fc"] == 925
    with pytest.raises(wood.WoodError, match="Table 4D file"):
        wood.post_values("REDWOOD", "No. 1", "6x6")


def test_post_wet_service_and_screen():
    from strukit.gui import calc
    # 4x4 DF-L No. 2 wet: Fc CF = 1,350 x 1.15 = 1,552 > 750, so CM = 0.8; E factor 0.9
    s = ws_wood.post("P", "DOUGLAS FIR-LARCH", "No. 2", "4x4", 8, [dict(case="D", P=2000)], [Combo("D", {"D": 1}, "x")], 1, 1, "pinned", True, False)
    assert next(l for l in s.steps if l.label == "CM").value == 0.8
    assert next(l for l in s.steps if l.label.startswith("Fc*")).value == pytest.approx(1350 * 0.9 * 0.8 * 1.15)
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")], combos_lrfd=[])
    v = dict(mark="WP1", species="DOUGLAS FIR-LARCH", grade="No. 2", size="6x6", height="9", lu1="", lu2="", Ke1="1", Ke2="1",
             k_source="pinned top and bottom", service="dry service", incised="no", unit_weight="",
             loads=[dict(case="L", P="6000", label=""), dict(case="D", P="62", label="")])
    r = calc.results("wood_post", v, proj)
    assert r["state"] == "done" and r["rows"][0]["demand"] == pytest.approx(200.4, abs=0.05)
    r = calc.results("wood_post", dict(v, k_source="", Ke1=""), proj)
    assert r["state"] == "incomplete" and any("Ke comes from" in m for m in r["messages"])


def test_table_4d_file():
    # values read against the table text for these species; every species has both classifications complete
    assert len(wood.TIMBER_SPECIES) == 29
    v = wood.TIMBER_VALUES
    assert v[("PONDEROSA PINE", "Posts and Timbers", "No. 2")]["Fc"] == 325 and v[("PONDEROSA PINE", "Beams and Stringers", "No. 1")]["Fb"] == 925
    assert v[("WESTERN CEDARS", "Posts and Timbers", "No. 1")]["Fc"] == 800 and v[("WESTERN CEDARS", "Posts and Timbers", "No. 1")]["Emin"] == 370000
    assert v[("DOUGLAS FIR-SOUTH", "Posts and Timbers", "Select Structural")]["Fc"] == 1050
    assert v[("DOUGLAS FIR-LARCH", "Posts and Timbers", "Dense No. 1")]["Fc"] == 1200
    for sp in wood.TIMBER_SPECIES:
        for cls in ("Beams and Stringers", "Posts and Timbers"):
            assert all((sp, cls, g) in v for g in ("Select Structural", "No. 1", "No. 2"))
    for sp in ("REDWOOD", "SITKA SPRUCE", "ALASKA CEDAR"):
        assert sp not in wood.TIMBER_SPECIES


def test_post_with_lateral_load_by_hand():
    # 4x6 DF-L No. 2 (3.5 x 5.5), 10 ft, braced at mid-height the weak way; D 1,500 lb, L 3,000 lb, wind 120 plf
    # D + 0.6W: fc = 1,500/19.25 = 77.92; M = 0.6 x 120 x 100/8 = 900 lb-ft; S1 = 3.5 x 5.5^2/6 = 17.646; fb = 612.0
    # le1/d1 = 120/5.5 = 21.82 governs (le2/d2 = 60/3.5 = 17.14); FcE1 = 0.822 x 580,000/21.82^2 = 1,001.6
    # Fc* = 1,350 x 1.6 x 1.1 = 2,376; CP = 0.3762; Fc' = 893.8
    # Fb* = 900 x 1.6 x 1.3 = 1,872; CL = 0.992; Eq. 3.9-3: (77.92/893.8)^2 + 612.0/(1,857 x (1 - 77.92/1,001.6)) = 0.365
    cb = [Combo("D + L", {"D": 1, "L": 1}, "x"), Combo("D + 0.6W", {"D": 1, "W": 0.6}, "x"),
          Combo("D + 0.75L + 0.45W", {"D": 1, "L": 0.75, "W": 0.45}, "x")]
    s = ws_wood.post("S1", "DOUGLAS FIR-LARCH", "No. 2", "4x6", 10, [dict(case="D", P=1500), dict(case="L", P=3000)], cb, 1, 1, "pinned",
                     False, False, lu2_ft=5, lateral=[dict(case="W", kind="uniform", w=120)])
    r = _row(s, "compression with bending")
    assert r.combo == "D + 0.6W" and r.demand == pytest.approx(0.365, abs=0.002) and r.capacity == 1.0
    assert "fb = 612.0 psi" in r.note and "CD = 1.6" in r.note
    assert _row(s, "shear").demand == pytest.approx(1.5 * 360 / 19.25, rel=1e-3) and _row(s, "shear").capacity == pytest.approx(180 * 1.6)
    c = _row(s, "compression")
    assert c.combo == "D + L" and c.demand == pytest.approx(4500 / 19.25, rel=1e-4)
    # Eq. 3.9-4 for the worst case: fc/FcE2 + (fb/FbE)^2, FcE2 = 0.822 x 580,000/17.14^2 = 1,622
    assert "FcE2 = 1,622 psi" in _row(s, "stability").note


def test_post_screen_with_lateral_table():
    from strukit.gui import calc
    proj = dict(method="ASD", combos_asd=[dict(expr="D + 0.6W", source="typed in")], combos_lrfd=[])
    v = dict(mark="S1", species="DOUGLAS FIR-LARCH", grade="No. 2", size="4x6", height="10", lu1="", lu2="5", Ke1="1", Ke2="1",
             k_source="pinned", service="dry service", incised="no", unit_weight="", loads=[dict(case="D", P="1500", label="")],
             lateral=[dict(case="W", kind="uniform", mag="120", x="", label="wind")])
    r = calc.results("wood_post", v, proj)
    assert r["state"] == "done" and next(x for x in r["rows"] if x["check"] == "compression with bending")["demand"] == pytest.approx(0.365, abs=0.002)


def test_timber_beam_by_hand():
    # 6x14 DF-L No. 1 (5.5 x 13.5), Beams and Stringers: Fb 1,350, Fv 170, E 1,600,000
    # CF = (12/13.5)^(1/9) = 0.98700; D + L, braced throughout: Fb' = 1,350 x 0.98700 = 1,332.4
    # w = 900 plf on 16 ft: M = 28,800 lb-ft; S = 5.5 x 13.5^2/6 = 167.06; fb = 2,068.7
    loads = [dict(case="D", kind="uniform", w=300), dict(case="L", kind="uniform", w=600)]
    s = ws_wood.beam("TB", "DOUGLAS FIR-LARCH", "No. 1", "6x14", 1, 16, loads, DL, [], 0, 5.5, False, False, False)
    r = _row(s, "bending")
    assert r.capacity == pytest.approx(1350 * (12 / 13.5) ** (1 / 9), rel=1e-6) and r.capacity == pytest.approx(1332.4, abs=0.1)
    assert r.demand == pytest.approx(28800 * 12 / (5.5 * 13.5 ** 2 / 6), rel=1e-4) and r.status == "FLAG"
    assert _row(s, "shear").capacity == 170 and _row(s, "shear").demand == pytest.approx(1.5 * 7200 / (5.5 * 13.5), rel=1e-4)
    assert "Table 4D, Beams and Stringers" in s.info[0][1]
    # a square timber takes the Posts and Timbers values; no size factor to 12 in. deep
    s = ws_wood.beam("TB", "DOUGLAS FIR-LARCH", "No. 1", "8x8", 1, 8, loads, DL, [], 0, 5.5, True, False, False)
    assert _row(s, "bending").capacity == 1200 and _row(s, "bearing").capacity == pytest.approx(625 * 0.67)
    with pytest.raises(WorksheetError, match="single piece"):
        ws_wood.beam("TB", "DOUGLAS FIR-LARCH", "No. 1", "6x12", 2, 16, loads, DL, [], 0, 5.5, False, False, False)


def test_job_2026_011_deck_joist_by_spacing():
    # sealed StruCalc package, page 16: 2x10 DF-L No. 2 at 16 in, 4.5 ft, 60 psf live, self-weight 3.16 plf:
    # Fb' 1,138.5 psi (CF 1.1, Cr 1.15); bending 118.1, shear 20.2, bearing 41.6 psi on 3 in; deflection 0.005 in
    loads = [dict(case="L", kind="area", q=60), dict(case="D", kind="uniform", w=3.16)]
    s = ws_wood.beam("DJ", "DOUGLAS FIR-LARCH", "No. 2", "2x10", 1, 4.5, loads, DL, [DeflCheck("total", {"D": 1, "L": 1}, 360, "x")], 0, 3.0,
                     False, False, True, spacing_in=16)
    assert _row(s, "bending").demand == pytest.approx(118.1, abs=0.1) and _row(s, "bending").capacity == pytest.approx(1138.5)
    assert _row(s, "shear").demand == pytest.approx(20.2, abs=0.05)
    assert _row(s, "bearing").demand == pytest.approx(41.6, abs=0.05)
    assert _row(s, "deflection").demand == pytest.approx(0.005, abs=0.0005) and _row(s, "deflection").capacity == pytest.approx(0.15)
    assert any("60.0 psf x 16 in = 80.0 plf" in t for t in s.load_lines)
    with pytest.raises(WorksheetError, match="spacing"):
        ws_wood.beam("DJ", "DOUGLAS FIR-LARCH", "No. 2", "2x10", 1, 4.5, loads, DL, [], 0, 3.0, False, False, True)


def test_joist_screen_area_load():
    from strukit.gui import calc
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")], combos_lrfd=[])
    v = dict(mark="DJ", species="DOUGLAS FIR-LARCH", grade="No. 2", size="2x10", plies="1", span="4.5", spacing="16",
             bracing="supported throughout", bearing="3", service="dry service", incised="no", repetitive="yes", unit_weight="",
             loads=[dict(case="L", kind="area", mag="60", x1="", x2="", label="deck live"), dict(case="D", kind="uniform", mag="3.16", x1="", x2="", label="")],
             defl=[])
    r = calc.results("wood_beam", v, proj)
    assert r["state"] == "done" and next(x for x in r["rows"] if x["check"] == "bending")["demand"] == pytest.approx(118.1, abs=0.1)
    r = calc.results("wood_beam", dict(v, spacing=""), proj)
    assert r["state"] == "incomplete" and "spacing" in r["messages"][0]


def test_built_up_column_by_hand():
    """(3) 2x6 Douglas Fir-Larch No. 2, nailed, 10 ft, pinned, unbraced both ways. NDS 15.3 by hand:
    Fc = 1,350, CF = 1.1, Emin = 580,000; D + L (CD = 1.0): Fc* = 1,485 psi.
    Across the face width: le/d = 120 / 5.5 = 21.82; FcE = 0.822 x 580,000 / 476.0 = 1,001.5; CP1 = 0.5443 (Kf = 1)
    Across the laminations: le/d = 120 / 4.5 = 26.67; FcE = 670.4; CP by Eq. 3.7-1 = 0.3986; x Kf 0.6 = 0.2392
    One lamination: le/t = 80 > 50, so no lower bound. CP = 0.2392; Fc' = 355.2 psi; A = 24.75 in2."""
    from strukit import ws_wood
    from tests.test_lvl import _combos
    import math
    def cp(r, Fcs=1485.0, Emin=580000.0):
        a = 0.822 * Emin / r ** 2 / Fcs
        return (1 + a) / 1.6 - math.sqrt(((1 + a) / 1.6) ** 2 - a / 0.8)
    loads = [dict(case="D", P=2000.0), dict(case="L", P=5000.0)]
    s = ws_wood.builtup_post("BC1", "DOUGLAS FIR-LARCH", "No. 2", "2x6", 3, "nailed", 10, loads, _combos(), 1.0, 1.0, "pinned", False, False)
    r = s.rows[0]
    assert r.demand == pytest.approx(7000 / 24.75) and r.capacity == pytest.approx(1485 * 0.6 * cp(120 / 4.5), rel=1e-6)
    assert cp(120 / 4.5) == pytest.approx(0.3986, abs=0.0005) and cp(120 / 5.5) == pytest.approx(0.5443, abs=0.0005)
    b = ws_wood.builtup_post("BC1", "DOUGLAS FIR-LARCH", "No. 2", "2x6", 3, "bolted", 10, loads, _combos(), 1.0, 1.0, "pinned", False, False)
    assert b.rows[0].capacity == pytest.approx(1485 * 0.75 * cp(120 / 4.5), rel=1e-6)
    # braced across the laminations at 4 ft (sheathing or blocking): le2/d2 = 10.67 -> Kf x CP2 = 0.6 x 0.867; the single
    # lamination (le/t = 32) gives CP = 0.293, less than that; CP1 = 0.544 against 0.6 x CP2
    c = ws_wood.builtup_post("BC1", "DOUGLAS FIR-LARCH", "No. 2", "2x6", 3, "nailed", 10, loads, _combos(), 1.0, 1.0, "pinned", False, False,
                             lu_stack_ft=4.0)
    assert c.rows[0].capacity == pytest.approx(1485 * min(cp(120 / 5.5), 0.6 * cp(48 / 4.5)), rel=1e-6)
    # lower bound: (2) 2x4... braced at 2 ft across the laminations, le/t = 16: single-lamination CP exceeds Kf x CP2
    e = ws_wood.builtup_post("BC2", "DOUGLAS FIR-LARCH", "No. 2", "2x6", 2, "nailed", 6, loads, _combos(), 1.0, 1.0, "pinned", False, False,
                             lu_stack_ft=2.0)
    single = min(cp(24 / 1.5), cp(72 / 5.5)); built = min(cp(72 / 5.5), 0.6 * cp(24 / 3.0))
    assert single > built and e.rows[0].capacity == pytest.approx(1485 * single, rel=1e-6)
    with pytest.raises(Exception, match="2 to 5"):
        ws_wood.builtup_post("BC1", "DOUGLAS FIR-LARCH", "No. 2", "2x6", 6, "nailed", 10, loads, _combos(), 1.0, 1.0, "pinned", False, False)


def test_post_with_eccentric_load_by_hand():
    """6x6 Douglas Fir-Larch No. 1 (Posts and Timbers: Fc 1,000, Fb 1,200, Emin 580,000), 10 ft, pinned, D 3,000 + L 5,000 lb at
    e = d/6 = 0.917 in. NDS Eq. 15.4-3: fc = 264.5 psi; le/d = 21.82; FcE = 1,001.5; CP = 0.6914; Fc' = 691.4;
    (fc/Fc')^2 = 0.1463; fc (6e/d)(1 + 0.234 fc/FcE) / (Fb' (1 - fc/FcE)) = 280.8 / 883.1 = 0.3180; total 0.464."""
    from strukit import ws_wood
    from tests.test_lvl import _combos
    s = ws_wood.post("P", "DOUGLAS FIR-LARCH", "No. 1", "6x6", 10, [dict(case="D", P=3000.0), dict(case="L", P=5000.0)], _combos(), 1.0, 1.0,
                     "pinned", False, False, e2_in=5.5 / 6)
    r = {x.check: x for x in s.rows}
    assert r["compression"].capacity == pytest.approx(691.4, abs=0.5)
    assert r["compression with eccentric load"].demand == pytest.approx(0.464, abs=0.003)
    assert "15.4-3" in r["compression with eccentric load"].source and "shear" not in r


def test_sloped_rafter_by_hand():
    """2x10 Douglas Fir-Larch No. 2 rafter at 24 in, 6 on 12, horizontal span 12 ft; D 15 psf along the slope, S 30 psf on the
    horizontal projection. cos = 0.8944. Per rafter: D 30 plf along the slope = 33.54 plf of horizontal; S 60 plf.
    D + 0.7S: w = 33.54 + 42 = 75.54 plf of horizontal; M = 75.54 x 144 / 8 = 1,359.7 lb-ft; fb = 1,359.7 x 12 / 21.39 = 762.8 psi
    shear normal to the rafter: 75.54 x 6 x 0.8944 = 405.4 lb; fv = 1.5 x 405.4 / 13.875 = 43.8 psi
    snow deflection (0.7S = 42 plf): horizontal 5 x 3.5 x 144^4 / (384 x 1.6e6 x 98.93) = 0.1238 in; normal = / cos^2 = 0.1547 in
    limit: sloped length 12 / 0.8944 = 13.416 ft = 161.0 in / 240 = 0.671 in"""
    from strukit import ws_wood
    from strukit.ws_steel_beam import DeflCheck
    from tests.test_lvl import _combos
    loads = [dict(case="D", kind="area", q=15.0), dict(case="S", kind="area", q=30.0)]
    s = ws_wood.beam("R1", "DOUGLAS FIR-LARCH", "No. 2", "2x10", 1, 12, loads, _combos(), [DeflCheck("snow", {"S": 0.7}, 240, "typed")],
                     0.0, 3.5, False, False, True, spacing_in=24, rise_on_12=6)
    r = {x.check: x for x in s.rows}
    assert r["bending"].demand == pytest.approx(762.8, abs=0.5) and r["shear"].demand == pytest.approx(43.8, abs=0.1)
    assert r["deflection, snow"].demand == pytest.approx(0.1547, abs=0.001) and r["deflection, snow"].capacity == pytest.approx(0.671, abs=0.001)
    assert r["bearing at support"].demand == pytest.approx(75.54 * 6 / (1.5 * 3.5), abs=0.3)
    assert any("6 on 12" in a for a in s.assumptions) and any("thrust" in n for n in s.not_checked)
    flat = ws_wood.beam("R1", "DOUGLAS FIR-LARCH", "No. 2", "2x10", 1, 12, loads, _combos(), [], 0.0, 3.5, False, False, True, spacing_in=24)
    assert {x.check: x for x in flat.rows}["bending"].demand < r["bending"].demand


def test_flat_use_plank_by_hand(tmp_path):
    """2x10 Douglas Fir-Larch No. 2 loaded on the wide face, 4 ft span, 100 plf live (D + L, CD 1.0), dry, not repetitive:
    b = 9.25 in., d = 1.5 in.; S = 9.25(1.5^2)/6 = 3.469 in3; M = 100(4^2)/8 = 200 lb-ft; fb = 2400/3.469 = 691.9 psi.
    Fb' = 900 (CF 1.1)(Cfu 1.2) = 1,188 psi; CL = 1.0 (depth does not exceed breadth). Cfu table: 2x4 1.1, 2x6 1.15, 2x12 1.2,
    4x6 1.05, 4x10 1.1, 4x4 1.0, 2x3 1.0."""
    from strukit import calcsheet, wood
    from strukit.gui import calc
    for size, v in (("2x4", 1.1), ("2x6", 1.15), ("2x8", 1.15), ("2x12", 1.2), ("4x6", 1.05), ("4x10", 1.1), ("4x4", 1.0), ("2x3", 1.0), ("3x5", 1.1)):
        assert wood.flat_use(size) == v
    with pytest.raises(wood.WoodError):
        wood.flat_use("6x6")
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")])
    v = dict(mark="WB9", species="DOUGLAS FIR-LARCH", grade="No. 2", size="2x10", plies="1", flat="yes", span="4", bracing="supported throughout",
             bearing="3", service="dry service", incised="no", repetitive="no", unit_weight="",
             loads=[dict(case="L", kind="uniform", mag="100", x1="", x2="", label="")], defl=[dict(label="live", expr="L", ratio="240", source="typed in")])
    s, _, _ = calc.build("wood_beam", v, proj)
    bend = next(x for x in s.rows if x.check == "bending")
    assert bend.demand == pytest.approx(691.9, abs=0.1) and bend.capacity == pytest.approx(1188.0, abs=0.1)
    assert "loaded on the wide face" in dict(s.info)["Size"] and any(getattr(x, "label", "") == "Cfu" for x in s.steps)
    calcsheet.simple_pdf(s, str(tmp_path / "f.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    edge, _, _ = calc.build("wood_beam", dict(v, flat="no"), proj)
    assert next(x for x in edge.rows if x.check == "bending").capacity == pytest.approx(990.0, abs=0.1)
    with pytest.raises(Exception):
        calc.build("wood_beam", dict(v, plies="2"), proj)


def test_southern_pine_table_4b(tmp_path):
    """2018 NDS Supplement Table 4B, values read from the Supplement: No. 2, 2 to 4 in. wide: Fb 1,100, Ft 675, Fv 175, Fc_perp 565, Fc 1,450,
    E 1,400,000, Emin 510,000; No. 2, 10 in. wide: Fb 800; No. 2, 12 in. wide: Fb 750; No. 1, 8 in. wide: Fb 1,250; Dense Select Structural,
    5 to 6 in. wide: Fb 2,400; No. 3 and Stud, 12 in. wide: Fb 450; Construction, 4 in. wide: Fb 875. CF: 1.1 for 4 in. thick 8 in. and wider;
    0.9 on the 12 in. values for wider members. Beam: 2x10 No. 2, repetitive, D + L: Fb' = 800(1.15) = 920 psi."""
    from strukit import calcsheet, wood
    from strukit.gui import calc
    v, CF, _ = wood.values("SOUTHERN PINE", "No. 2", "2x4")
    assert v == dict(Fb=1100, Ft=675, Fv=175, Fc_perp=565, Fc=1450, E=1400000, Emin=510000) and CF == 1.0
    for grade, size, Fb, cf in (("No. 2", "2x10", 800, 1.0), ("No. 2", "2x12", 750, 1.0), ("No. 1", "2x8", 1250, 1.0), ("Dense Select Structural", "2x6", 2400, 1.0),
                                ("Stud", "2x12", 450, 1.0), ("No. 3", "2x6", 575, 1.0), ("Construction", "2x4", 875, 1.0), ("No. 2", "4x10", 800, 1.1),
                                ("No. 2", "2x14", 750, 0.9), ("No. 1 Non-Dense", "4x4", 1300, 1.0)):
        r, c, _ = wood.values("SOUTHERN PINE", grade, size)
        assert r["Fb"] == Fb and c == pytest.approx(cf), (grade, size)
    assert wood.values("SOUTHERN PINE", "No. 2", "4x14")[1] == pytest.approx(0.99) and len(wood.SP_VALUES) == 76
    for grade, size in (("Construction", "2x6"), ("No. 1 & Btr", "2x8")):
        with pytest.raises(wood.WoodError):
            wood.values("SOUTHERN PINE", grade, size)
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")])
    f = dict(mark="WB8", species="SOUTHERN PINE", grade="No. 2", size="2x10", plies="1", span="12", spacing="16", bracing="supported throughout",
             bearing="1.5", service="dry service", incised="no", repetitive="yes", unit_weight="",
             loads=[dict(case="D", kind="area", mag="10", x1="", x2="", label=""), dict(case="L", kind="area", mag="40", x1="", x2="", label="")],
             defl=[dict(label="live", expr="L", ratio="360", source="typed in")])
    s, _, _ = calc.build("wood_beam", f, proj)
    bend = next(x for x in s.rows if x.check == "bending")
    assert bend.capacity == pytest.approx(920.0) and bend.demand == pytest.approx((50 * 16 / 12) * 144 / 8 * 12 / (1.5 * 9.25 ** 2 / 6), abs=0.5)
    assert "Table 4B" in " ".join(str(getattr(x, "source", "")) for x in s.steps) and "Table 4B values for 10 in. wide" in dict(s.info)["Member"]
    calcsheet.simple_pdf(s, str(tmp_path / "sp.pdf"), "Job", "2018 NDS", "Nov 23, 2026")


def test_southern_pine_post_by_hand(tmp_path):
    """4x4 Southern Pine No. 2, 8 ft, pinned, dead load only (CD 0.9): Table 4B, 2 to 4 in. wide: Fc 1,450 psi, Emin 510,000 psi; CF 1.0.
    le/d = 96/3.5 = 27.43; FcE = 0.822(510,000)/27.43^2 = 557.2 psi; Fc* = 1,450(0.9) = 1,305 psi; FcE/Fc* = 0.4270;
    CP = 0.8919 - sqrt(0.8919^2 - 0.4270/0.8) = 0.3803; Fc' = 496.3 psi. Wet: Fc over 750 psi, CM 0.8. 4x14: Fc CF 0.9."""
    from strukit import calcsheet, wood
    from strukit.gui import calc
    s = ws_wood.post("P", "SOUTHERN PINE", "No. 2", "4x4", 8, [dict(case="D", P=2000)], [Combo("D", {"D": 1}, "x")], 1, 1, "pinned", False, False)
    comp = next(x for x in s.rows if x.check == "compression")
    assert comp.capacity == pytest.approx(496.3, abs=0.5) and "Table 4B" in dict(s.info)["Member"]
    assert "Table 4B" in next(l for l in s.steps if l.label == "CF").source
    w = ws_wood.post("P", "SOUTHERN PINE", "No. 2", "4x4", 8, [dict(case="D", P=2000)], [Combo("D", {"D": 1}, "x")], 1, 1, "pinned", True, False)
    assert next(l for l in w.steps if l.label == "CM").value == 0.8
    assert wood.post_values("SOUTHERN PINE", "No. 2", "4x14")[1] == 0.9 and wood.post_values("SOUTHERN PINE", "No. 2", "4x6")[0]["Fc"] == 1400
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")], combos_lrfd=[])
    v = dict(mark="WP7", species="SOUTHERN PINE", grade="No. 1", size="4x6", height="9", lu1="", lu2="", Ke1="1", Ke2="1", k_source="pinned top and bottom",
             service="dry service", incised="no", unit_weight="", loads=[dict(case="L", P="3000", label=""), dict(case="D", P="1000", label="")])
    sh, _, _ = calc.build("wood_post", v, proj)
    calcsheet.simple_pdf(sh, str(tmp_path / "p.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    assert calc.results("wood_post", v, proj)["state"] == "done"


def test_southern_pine_builtup_column():
    """3 - 2x6 Southern Pine No. 2: Table 4B, 5 to 6 in. wide: Fc 1,400 psi, CF 1.0."""
    loads = [dict(case="D", P=2000), dict(case="L", P=4000)]
    s = ws_wood.builtup_post("BC2", "SOUTHERN PINE", "No. 2", "2x6", 3, "nailed", 10, loads, [Combo("D + L", {"D": 1, "L": 1}, "x")], 1.0, 1.0, "pinned", False, False)
    assert next(l for l in s.steps if l.label == "CF").value == 1.0 and "Table 4B" in next(l for l in s.steps if l.label == "CF").source
    assert any(getattr(l, "value", None) == 1400 for l in s.steps)


def test_posts_with_lateral_load_carry_shear_and_moment_diagrams(tmp_path):
    """A post with wind on its face prints the shear and moment diagram of the combination with the largest moment: 6x6, 10 ft, 120 plf wind,
    D + 0.6W: w = 72 plf; M = 72(10^2)/8 = 900 lb-ft; V = 360 lb. A post with axial load only has no diagram."""
    from strukit import calcsheet
    cs = [Combo("D + 0.6W", {"D": 1, "W": 0.6}, "x"), Combo("D", {"D": 1}, "x")]
    s = ws_wood.post("P", "DOUGLAS FIR-LARCH", "No. 2", "6x6", 10, [dict(case="D", P=2000)], cs, 1, 1, "pinned", False, False,
                     lateral=[dict(case="W", kind="uniform", w=120)])
    d = s.diagram
    assert d["combo"] == "D + 0.6W" and max(abs(m) for m in d["M"]) == pytest.approx(900, abs=1) and max(abs(v) for v in d["V"]) == pytest.approx(360, abs=1)
    assert d["x"][-1] == pytest.approx(10.0)
    calcsheet.simple_pdf(s, str(tmp_path / "p.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    plain = ws_wood.post("P", "DOUGLAS FIR-LARCH", "No. 2", "6x6", 10, [dict(case="D", P=2000)], cs, 1, 1, "pinned", False, False)
    assert getattr(plain, "diagram", None) is None


def test_lumber_decking_by_hand(tmp_path):
    """2018 NDS Supplement Table 4E, values read from the Supplement: Douglas Fir-Larch Select Dex: Fb 1,750, (Fb)(Cr) 2,000, Fc_perp 625,
    E 1,800,000; Hem-Fir Commercial: 1,150 / 1,350 / 405 / 1,400,000; Balsam Fir Select: repetitive 1,650 only. Size factors 1.10 (2 in.),
    1.04 (3 in.), 1.0 (4 in.). 3 in. Select Dex, 10 ft simple span, D 15 psf + 0.7(50) S: w = 50 plf on 12 in.; M = 625 lb-ft;
    S = 12(2.5^2)/6 = 12.5 in3; fb = 600 psi; Fb' = 2,000(1.15)(1.04) = 2,392 psi. Snow deflection, 35 plf: 5(2.917)(120^4)/(384(1.8e6)(15.625))
    = 0.280 in. Two equal spans: same moment; snow on one span 0.0092(2.917)(120^4)/(1.8e6 x 15.625) = 0.198 in."""
    from strukit import calcsheet, wood
    from strukit.gui import calc
    assert wood.DECKING[("DOUGLAS FIR-LARCH", "Select Dex")] == dict(Fb=1750, Fb_rep=2000, Fc_perp=625, E=1800000, Emin=660000)
    assert wood.DECKING[("HEM-FIR", "Commercial")]["Fb_rep"] == 1350 and wood.DECKING[("BALSAM FIR", "Select")]["Fb"] is None
    assert not any("REDWOOD" in k[0] for k in wood.DECKING) and wood.DECKING_CF == {2: 1.10, 3: 1.04, 4: 1.0}
    with pytest.raises(wood.WoodError):
        wood.decking_values("BALSAM FIR", "Select", 2, False)
    proj = dict(method="ASD", combos_asd=[dict(expr="D + 0.7S", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 3")])
    v = dict(mark="DK1", species="DOUGLAS FIR-LARCH", grade="Select Dex", thickness="3", span="10", layout="simple span", repetitive="yes", service="dry service",
             loads=[dict(case="D", q="15", label=""), dict(case="S", q="50", label="")], defl=[dict(label="snow", expr="0.7S", ratio="240", source="typed in")])
    s, kind, _ = calc.build("decking", v, proj)
    assert kind == "simple" and s.rows[0].demand == pytest.approx(600.0) and s.rows[0].capacity == pytest.approx(2392.0)
    assert s.rows[1].demand == pytest.approx(0.280, abs=0.001) and s.rows[1].capacity == pytest.approx(0.5)
    calcsheet.simple_pdf(s, str(tmp_path / "d.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    two, _, _ = calc.build("decking", dict(v, layout="two equal spans"), proj)
    assert two.rows[0].demand == pytest.approx(600.0) and two.rows[1].demand == pytest.approx(0.198, abs=0.001)
    assert s.picture[0] == "wood_beam" and s.picture[1]["supports"] == [0.0, 10.0] and two.picture[1]["supports"] == [0.0, 10.0, 20.0]
    assert two.picture[1]["d"] == 2.5 and [x["w"] for x in two.picture[1]["loads"]] == [15.0, 50.0]
    calcsheet.simple_pdf(two, str(tmp_path / "d2.pdf"), "Job", "2018 NDS", "Nov 23, 2026")
    single, _, _ = calc.build("decking", dict(v, repetitive="no", service="wet service"), proj)
    assert single.rows[0].capacity == pytest.approx(1750 * 1.15 * 0.85 * 1.04)
    assert calc.results("decking", dict(v, span=""), proj)["state"] == "incomplete"


def test_mixed_southern_pine_table_4b(tmp_path):
    """2018 NDS Supplement Table 4B, Mixed Southern Pine, values read from the Supplement: No. 2, 2 to 4 in. wide: Fb 1,100, Fc 1,450,
    E 1,400,000; No. 1, 8 in. wide: Fb 1,200, E 1,500,000; Select Structural, 12 in. wide: Fb 1,400; No. 3 and Stud, 10 in. wide: Fb 475;
    Utility, 4 in. wide: Fb 225, E 1,100,000. Joist: 2x8 No. 1, repetitive: Fb' = 1,200(1.15) = 1,380 psi."""
    from strukit import calcsheet, wood
    from strukit.gui import calc
    M = "MIXED SOUTHERN PINE"
    v, CF, _ = wood.values(M, "No. 2", "2x4")
    assert (v["Fb"], v["Fc"], v["E"], CF) == (1100, 1450, 1400000, 1.0)
    for grade, size, Fb in (("No. 1", "2x8", 1200), ("Select Structural", "2x12", 1400), ("Stud", "2x10", 475), ("Utility", "2x4", 225), ("No. 1", "4x6", 1300)):
        assert wood.values(M, grade, size)[0]["Fb"] == Fb
    assert wood.values(M, "No. 1", "2x8")[0]["E"] == 1500000 and wood.post_values(M, "No. 2", "4x4")[3] == "Table 4B"
    with pytest.raises(wood.WoodError):
        wood.values(M, "No. 1 Dense", "2x8")
    proj = dict(method="ASD", combos_asd=[dict(expr="D + L", source="typed in")])
    f = dict(mark="WB6", species=M, grade="No. 1", size="2x8", plies="1", span="10", spacing="16", bracing="supported throughout", bearing="1.5",
             service="dry service", incised="no", repetitive="yes", unit_weight="", loads=[dict(case="D", kind="area", mag="10", x1="", x2="", label=""),
             dict(case="L", kind="area", mag="40", x1="", x2="", label="")], defl=[dict(label="live", expr="L", ratio="360", source="typed in")])
    s, _, _ = calc.build("wood_beam", f, proj)
    assert next(x for x in s.rows if x.check == "bending").capacity == pytest.approx(1380.0) and "Mixed Southern Pine" in dict(s.info)["Member"]
    calcsheet.simple_pdf(s, str(tmp_path / "m.pdf"), "Job", "2018 NDS", "Nov 23, 2026")


def test_bearing_area_factor_at_interior_supports_and_loads_snapped_to_the_beam_end():
    """NDS 3.10.4, Eq. 3.10-2: Cb = (lb + 0.375) / lb for a bearing under 6 in. long that is not at a member end: 3 in. -> 1.125 (Table 3.10.4 lists 1.13),
    6 in. -> 1.0.  Job 2026-011 Floor Beam A: (2) 1.75 x 11.875 2.1E 2800 over three 9.0833 ft spans with loads typed to 27.25 ft (0.0012 in. past the end):
    StruCalc's interior bearing strength is 843.8 psi = 750 x 1.125, and with every span loaded its interior bearing stress is 719.1 psi."""
    from strukit.gui import calc
    u = lambda case, mag, x1="", x2="": dict(case=case, kind="uniform", mag=str(mag), mag2="", x1=str(x1), x2=str(x2), label="")
    v = dict(mark="FBA", grade="2.1E 2800", thickness="1.75", depth="11.875", plies="2", span="9.0833", more_spans="9.0833, 9.0833", lu_neg="9.0833", bearing="3", bearing_int="3",
             snow_partial="apply", bracing="supported throughout", repetitive="no", unit_weight="",
             loads=[u("D", 582.5, 0, 19.2917), u("D", 425, 19.2917, 27.25), u("D", 145.6, 0, 19.2917), u("D", 106.25, 19.2917, 27.25), u("D", 10.68)], defl=[])
    s, _, _ = calc.build("lvl_beam", v, dict(method="ASD", combos_asd=[dict(expr="D", source="test combination")]))
    r = {x.check: x for x in s.rows}
    assert r["bearing at interior support"].capacity == pytest.approx(843.75) and r["bearing at interior support"].demand == pytest.approx(719.1, abs=0.3)
    assert r["bearing at support"].capacity == 750.0
    s6, _, _ = calc.build("lvl_beam", dict(v, bearing_int="6"), dict(method="ASD", combos_asd=[dict(expr="D", source="test combination")]))
    assert {x.check: x for x in s6.rows}["bearing at interior support"].capacity == 750.0
