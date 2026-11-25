"""Single angles in bending, AISC 360-22 Sect. F10, against AISC Design Examples v16.0 Examples F.11A, F.11B and F.11C (L4x4x1/4, A572 Gr. 50,
6 ft simple span, D = 0.05 and L = 0.15 kip/ft; F.11C adds W = 0.12 kip/ft horizontal)."""
import pytest

from strukit import anglebeam as ab, calcsheet, shapes
from strukit.gui import calc
from strukit.ws_more import angle_beam_sheet
from strukit.ws_steel_beam import Combo, WorksheetError

DL = [dict(case="D", kind="uniform", w=0.05, dir="down"), dict(case="L", kind="uniform", w=0.15, dir="down")]
LR, AS = Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "t"), Combo("D + L", {"D": 1.0, "L": 1.0}, "t")


def test_F11A_geometric_axis_no_restraint():
    """Published: yielding 77.3 kip-in.; My = 0.80 Fy Sx = 41.2; Cb 1.14; Mcr 107; Mn 49.2 kip-in. (LTB governs); leg 53.0 kip-in. with
    Sc = 0.80 Sx; 3.69 / 2.46 kip-ft against 1.35 / 0.900 kip-ft."""
    a = shapes.angle("L4X4X1/4")
    g = ab.geometry(a, "long", "up")
    r = ab.geometric_strength(a, g, 50, "none", 72, ab.cb_f1((1, 0.75, 1, 0.75)))
    lim = {n: v for n, v, _ in r["limits"]}
    assert lim["yielding"] == pytest.approx(77.3, abs=0.1) and r["My"] == pytest.approx(41.2, abs=0.05) and r["Mcr"] == pytest.approx(107, abs=0.5)
    assert lim["lateral-torsional buckling"] == pytest.approx(49.2, abs=0.1) and lim["leg local buckling"] == pytest.approx(53.0, abs=0.1)
    for m, cb, M, cap in (("LRFD", LR, 1.35, 3.69), ("ASD", AS, 0.900, 2.46)):
        s = angle_beam_sheet("LB", "L4X4X1/4", 50, "A572 Gr. 50", 6, "long", "up", "none", False, DL, [cb], m)
        row = s.rows[0]
        assert row.demand == pytest.approx(M, abs=0.001) and row.capacity == pytest.approx(cap, abs=0.01)


def test_F11B_restraint_at_midspan():
    """Published: Cb 1.30; My = Fy Sx = 51.5; Mcr = 1.25 x Eq. F10-5a = 176; LTB 66.3 kip-in.; leg local buckling 53.0 (0.80 Sx, governs):
    3.98 / 2.65 kip-ft."""
    a = shapes.angle("L4X4X1/4")
    cb = ab.cb_f1((1, 0.4375, 0.75, 0.9375))
    r = ab.geometric_strength(a, ab.geometry(a, "long", "up"), 50, "max", 36, cb)
    assert cb == pytest.approx(1.30, abs=0.005) and r["Mcr"] == pytest.approx(176, abs=0.5) and r["My"] == pytest.approx(51.5, abs=0.1)
    assert dict((n, v) for n, v, _ in r["limits"])["lateral-torsional buckling"] == pytest.approx(66.3, abs=0.2) and r["Mn"] == pytest.approx(53.0, abs=0.1)
    for m, cbo, cap in (("LRFD", LR, 3.98), ("ASD", AS, 2.65)):
        s = angle_beam_sheet("LB", "L4X4X1/4", 50, "A572 Gr. 50", 6, "long", "up", "midspan", False, DL, [cbo], m)
        assert s.rows[0].capacity == pytest.approx(cap, abs=0.01)


def test_F11C_principal_axes():
    """Published: Mw 0.286 / 0.347, Mz 1.05 / 0.691 kip-ft; Mnz 4.59 (leg, SzC 0.856), Mnw 8.32 (Mcr 195, LTB); 4.13 / 2.75 and 7.49 / 4.98 kip-ft;
    Eq. H2-1 at A (both compress) 0.292 / 0.321, at C 0.216 / 0.182, at B 0.254 / 0.251."""
    loads = DL + [dict(case="W", kind="uniform", w=0.12, dir="sideways")]
    for m, cb, Mw, Mz, cw, cz, top, other, heel in (("LRFD", Combo("1.2D + L + W", {"D": 1.2, "L": 1.0, "W": 1.0}, "t"), 0.286, 1.05, 7.49, 4.13, 0.292, 0.216, 0.254),
                                                    ("ASD", Combo("D + 0.75L + 0.45W", {"D": 1.0, "L": 0.75, "W": 0.45}, "t"), 0.347, 0.691, 4.98, 2.75, 0.321, 0.182, 0.251)):
        s = angle_beam_sheet("LB", "L4X4X1/4", 50, "A572 Gr. 50", 6, "long", "up", "none", False, loads, [cb], m)
        d = s.angle_beam["detail"]
        assert not s.angle_beam["geometric"]
        assert abs(d["Bw"]) == pytest.approx(Mw, abs=0.003) and abs(d["Bz"]) == pytest.approx(Mz, abs=0.005)
        assert d["st"]["Mnw"] / 12 == pytest.approx(8.32, abs=0.02) and d["st"]["Mnz"] / 12 == pytest.approx(4.59, abs=0.01) and d["st"]["Mcr"] == pytest.approx(195, abs=0.6)
        assert d["cw"] == pytest.approx(cw, abs=0.02) and d["cz"] == pytest.approx(cz, abs=0.01)
        it = sorted(d["it"].values())
        assert it[2] == pytest.approx(top, abs=0.002) and it[1] == pytest.approx(other, abs=0.002) and it[0] == pytest.approx(-heel, abs=0.002)


def test_principal_points_against_the_shapes_table():
    """Signs come from the geometry; the magnitudes are the table's. The table's section moduli follow from them (L6x4x1/2: SwA 7.14, SwC 5.04,
    SzB 2.08, SzC 3.71 in3)."""
    a = shapes.angle("L6X4X1/2")
    w, z, pts = ab.principal_points(a, ab.geometry(a, "long", "up"))
    assert a["Iw"] / abs(pts["A"][1]) == pytest.approx(7.14, rel=0.01) and a["Iw"] / abs(pts["C"][1]) == pytest.approx(5.04, rel=0.01)
    assert a["Iz"] / abs(pts["B"][0]) == pytest.approx(2.08, rel=0.01) and a["Iz"] / abs(pts["C"][0]) == pytest.approx(3.71, rel=0.01)
    assert pts["C"][1] > 0 and pts["A"][1] < 0                     # long leg up: its toe on the + side of the w axis
    assert ab.beta_w(ab.geometry(a, "long", "up")) == 3.14         # Commentary Table C-F10.1


def test_screen_and_refusals(tmp_path):
    v = dict(mark="LB1", shape="L4X4X1/4", Fy="50", steel_source="A572 Gr. 50", span="6", vertical="", toe="up", restraint="none between the ends", self_weight="yes",
             loads=[dict(case="D", kind="uniform, full span", value="0.05", x="", dir="down", label=""), dict(case="L", kind="point", value="0.5", x="2", dir="down", label="")])
    proj = dict(name="T", number="1", address="", method="LRFD", date="2026-11-25", combos=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1")])
    s, _, _ = calc.build("angle_beam", v, proj)
    assert s.title == "Single-Angle Beam" and s.ok and any("self-weight" in x for x in s.load_lines)
    calcsheet.simple_pdf(s, str(tmp_path / "lb.pdf"), "Job", "AISC 360-22", "Nov 25, 2026")
    with pytest.raises(WorksheetError):                              # largest moment is not at midspan
        calc.build("angle_beam", dict(v, restraint="at midspan only", self_weight="no", loads=[dict(case="L", kind="point", value="0.5", x="1", dir="down", label="")]), proj)
    with pytest.raises(WorksheetError):
        angle_beam_sheet("LB", "L4X4X1/4", 50, "A36", 6, "long", "up", "continuous", False, DL + [dict(case="L", kind="uniform", w=0.1, dir="sideways")], [LR], "LRFD")
    s2 = angle_beam_sheet("LB", "L6X4X1/2", 36, "A36", 8, "long", "up", "none", True, DL, [LR], "LRFD")
    assert not s2.angle_beam["geometric"]                           # unequal legs without continuous restraint: principal axes
