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
    with pytest.raises(wood.WoodError, match="R"):
        wood.load_duration(["D", "R"])


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
        ws_wood.beam("X", "HEM-FIR", "No. 2", "2x10", 1, 12, [dict(case="R", kind="uniform", w=50)], [Combo("R", {"R": 1}, "x")], [], 0, 3,
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
