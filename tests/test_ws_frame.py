"""Frame worksheet against AISC Design Examples v16.0, Example C.1A.

The example frame: one bay of 30 ft, 20 ft high, W12x65 columns with pinned bases,
W18x40 beam, wD = 0.400 and wL = 1.20 kip/ft, beam reactions from the adjacent bays on
each column (D 6, L 18 kips), and three leaning columns carrying D 24 + L 72 kips.
Printed required strengths for both columns (direct analysis method):
    LRFD: Pr = 72.6 kips, Mr = 127 kip-ft;   ASD: Pr = 48.4 kips, Mr = 84.8 kip-ft
Printed drift ratios: 1.60 (LRFD), 1.66 (ASD); tau_b = 1.0.
"""
import pytest

from strukit import ws_frame
from strukit.ws_steel_beam import Combo, DeflCheck, WorksheetError


def c1a(method):
    lay = ws_frame.layout([30], [20], "pin", "W12x65", "W18x40")
    loads = [dict(case="D", on="beams", w=0.400), dict(case="L", on="beams", w=1.20)]
    for n in ("N1-1", "N2-1"):
        loads += [dict(case="D", node=n, Fy=-6.0), dict(case="L", node=n, Fy=-18.0)]
    lean = [dict(case="D", level=1, P=24.0), dict(case="L", level=1, P=72.0)]
    cb = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "given")] if method == "LRFD" else \
        [Combo("D + L", {"D": 1, "L": 1}, "given")]
    return ws_frame.run("F1", lay, 50, loads, cb, method, False, {"columns": 20, "beams": 5}, leaning=lean)


def row(s, name):
    return next(r for r in s.member_rows if r["member"] == name)


def test_C1A_lrfd_required_strengths():
    s = c1a("LRFD")
    for col in ("C1-1", "C2-1"):                           # notional load each way: both columns alike
        r = row(s, col)
        assert r["Pr"] == pytest.approx(72.6, rel=0.01) and r["Mr"] == pytest.approx(127, rel=0.015)
        assert r["tau"] == 1.0
    d = next(r for r in s.rows if r.check.startswith("drift amplification"))
    assert d.demand == pytest.approx(1.60, rel=0.03)


def test_C1A_asd_required_strengths():
    s = c1a("ASD")
    r = row(s, "C2-1")
    assert r["Pr"] == pytest.approx(48.4, rel=0.01) and r["Mr"] == pytest.approx(84.8, rel=0.015)
    d = next(r for r in s.rows if r.check.startswith("drift amplification"))
    assert d.demand == pytest.approx(1.66, rel=0.03)


def test_layouts():
    two = ws_frame.layout([24, 24, 30], [14, 12], "fixed", "W10x49", "W16x31")
    assert len([m for m in two.members if m.role == "column"]) == 8
    assert len([m for m in two.members if m.role == "beam"]) == 6 and two.names("level:1") == ["B1-1", "B2-1", "B3-1"]
    g = ws_frame.layout([40], [16], "pin", "W10x49", "W16x31", roof="gable", rise_ft=5)
    assert g.nodes["RIDGE"] == (20.0, 21.0) and [m.name for m in g.members if m.role == "rafter"] == ["R1", "R2"]
    m = ws_frame.layout([20, 20], [12], "pin", "W10x49", "W16x31", roof="mono", rise_ft=4)
    assert m.nodes["N3-1"][1] == 16.0 and m.nodes["N2-1"][1] == 14.0


def test_multi_story_frame_statics_and_drift_check():
    lay = ws_frame.layout([24, 24], [14, 12], "fixed", "W10x49", "W16x31")
    loads = [dict(case="D", on="beams", w=1.0), dict(case="W", level=1, Fx=6.0), dict(case="W", level=2, Fx=4.0)]
    cb = [Combo("D", {"D": 1}, "given"), Combo("D + 0.6W", {"D": 1, "W": 0.6}, "given")]
    s = ws_frame.run("F2", lay, 50, loads, cb, "ASD", False, {"columns": 12, "beams": 6},
                     drift_checks=[DeflCheck("wind", {"W": 0.6}, 400, "given")])
    rx = s.reactions["D + 0.6W"]
    assert sum(v[0] for v in rx.values()) == pytest.approx(-0.6 * 10.0, rel=1e-6)          # base shear
    assert sum(v[1] for v in rx.values()) == pytest.approx(1.0 * 48 * 2, rel=1e-6)         # gravity
    assert len(s.member_rows) == 10 and any(r.check.startswith("story drift, wind, story 2") for r in s.rows)
    assert "D (notional load to the right)" in s.reactions


def test_gable_frame_with_projected_snow():
    lay = ws_frame.layout([40], [16], "pin", "W12x53", "W16x40", roof="gable", rise_ft=5)
    loads = [dict(case="S", on="rafters", w=0.8, kind="projected")]
    s = ws_frame.run("F3", lay, 50, loads, [Combo("S", {"S": 1}, "given")], "ASD", False,
                     {"columns": 16, "rafters": 5})
    r = next(iter(s.reactions.values()))
    assert sum(v[1] for v in r.values()) == pytest.approx(0.8 * 40, rel=1e-6)
    assert row(s, "R1")["axial"] == "compression"          # rafters of a gable frame thrust


def test_missing_inputs_stop():
    lay = ws_frame.layout([30], [20], "pin", "W12x65", "W18x40")
    with pytest.raises(WorksheetError):                    # beams have no unbraced length
        ws_frame.run("F", lay, 50, [dict(case="D", on="beams", w=1.0)], [Combo("D", {"D": 1}, "g")], "ASD",
                     False, {"columns": 20})
    with pytest.raises(WorksheetError):
        ws_frame.layout([30], [20], "pin", "W12x65", "W18x40", roof="gable")
