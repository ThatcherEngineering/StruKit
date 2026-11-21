"""Independent validation: AISC Design Examples v16.0 (bolts).

Example J.3 (Part I) and Example II.A-1A (Part II, all-bolted double-angle connection,
bolts at the beam web). Reference values are the numbers printed in the examples.
"""
import pytest

from strukit import bolts
from strukit.steel_beam import SteelInputError


def near(a, b, tol=5e-3):
    return a == pytest.approx(b, rel=tol)


def test_table_values_and_hole_sizes():
    assert near(bolts.area(0.75), 0.442)                          # Manual Table 7-2, per J.3
    assert bolts.standard_hole(0.75) == pytest.approx(13 / 16)    # Table J3.3
    assert bolts.standard_hole(0.875) == pytest.approx(15 / 16)
    assert bolts.standard_hole(1.0) == pytest.approx(1.125)
    assert bolts.TABLE_J3_2["GROUP 120"] == (90.0, 54.0, 68.0)    # Table J3.2
    assert bolts.TABLE_J3_2["GROUP 150"] == (113.0, 68.0, 84.0)
    assert bolts.TABLE_J3_2["A307"] == (45.0, 27.0, 27.0)


def test_example_J_3_combined_tension_and_shear():
    # 3/4 in Group 120-N. LRFD: Vu = 8.00, frv = 18.1 ksi, Fnt' = 76.8 ksi, phi Rn = 25.5 kips.
    # ASD: Va = 5.33, frv = 12.1 ksi, Fnt' = 76.7 ksi, Rn/Omega = 17.0 kips.
    l = bolts.tension_with_shear(0.75, "Group 120", 8.00, method="LRFD")
    a = bolts.tension_with_shear(0.75, "Group 120", 5.33, method="ASD")
    lv = {x.label: x.value for x in l.lines}
    av = {x.label: x.value for x in a.lines}
    assert near(lv["frv"], 18.1) and near(lv["Fnt'"], 76.8)
    assert near(av["frv"], 12.1) and near(av["Fnt'"], 76.7)
    assert near(l.R_avail, 25.5) and near(a.R_avail, 17.0)


def test_example_II_A_1A_single_bolt_values():
    # 3/4 in Group 120-N: phi rn = 17.9, rn/Omega = 11.9 kips (single shear).
    assert near(bolts.shear(0.75, "A325", method="LRFD").R_avail, 17.9)
    assert near(bolts.shear(0.75, "A325").R_avail, 11.9)
    # 5/16 in angle, Fu = 65: bearing 36.6; edge tearout lc = 0.844 -> 20.6; interior
    # lc = 2.19 -> 53.4. Web tw = 0.760: bearing 88.9, tearout 130.
    edge = bolts.hole(0.75, 5 / 16, 65, 1.25 - 0.5 * 13 / 16)
    inner = bolts.hole(0.75, 5 / 16, 65, 3 - 13 / 16)
    web = bolts.hole(0.75, 0.760, 65, 3 - 13 / 16)
    ev = {x.label: x.value for x in edge.lines}
    assert near(ev["Rn, bearing"], 36.6) and near(ev["Rn, tearout"], 20.6)
    assert "tearout" in edge.governs and near(edge.R_avail, 10.3)
    assert near({x.label: x.value for x in inner.lines}["Rn, tearout"], 53.4)
    wv = {x.label: x.value for x in web.lines}
    assert near(wv["Rn, bearing"], 88.9) and near(wv["Rn, tearout"], 130)


def test_example_II_A_1A_bolt_line_at_beam_web():
    # 8 bolts at 3 in, double shear, two 5/16 in angles (edge 1-1/4 in) on a 0.760 in web.
    # Printed: phi Rn = 282 kips, Rn/Omega = 187 kips; the edge bolt is limited by angle
    # tearout (31.0 / 20.6 kips), the others by bolt shear (35.8 / 23.8 kips).
    plies = [(5 / 16, 65, True, 2), (0.760, 65, False)]
    l = bolts.bolt_line(0.75, "Group 120", 8, 3.0, 1.25, plies, planes=2, method="LRFD")
    a = bolts.bolt_line(0.75, "Group 120", 8, 3.0, 1.25, plies, planes=2)
    assert near(l.R_avail, 282) and near(a.R_avail, 187)
    assert "tearout" in l.lines[0].note and "bolt shear" in l.lines[1].note
    assert near(0.75 * l.lines[0].value, 31.0, 1e-2) and near(0.75 * l.lines[1].value, 35.8)


def test_other_branches_and_bad_input():
    # deformation not a design consideration: Eq. J3-6b / J3-6d
    h = bolts.hole(0.75, 0.5, 65, 1.0, deformation=False)
    assert h.Rn == pytest.approx(min(3.0 * 0.75 * 0.5 * 65, 1.5 * 1.0 * 0.5 * 65))
    assert near(bolts.tension(0.75, "A490").Rn, 113 * 0.4418, 1e-3)
    assert near(bolts.shear(0.875, "A325", threads="X", planes=2).Rn, 68 * bolts.area(0.875) * 2, 1e-9)
    with pytest.raises(SteelInputError, match="not in Table J3.2"):
        bolts.shear(0.75, "A999")
    with pytest.raises(SteelInputError, match="exceeds the available"):
        bolts.tension_with_shear(0.75, "A325", 30.0, method="LRFD")
