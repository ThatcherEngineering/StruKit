"""HSS and pipe section properties, AISC Shapes Database v16.0.

Reference: AISC Design Guide 34, Example 10.1.7, which lists (from Manual Table 1-13) HSS1.900x0.145: A 0.749 in2, t 0.135 in., D/t 14.1,
I 0.293 in4, S 0.309 in3, r 0.626 in., Z 0.421 in3, 2.72 lb/ft; HSS1.660x0.140: A 0.625, t 0.130, D/t 12.8, I 0.184, S 0.222, r 0.543, Z 0.305, 2.27 lb/ft."""
import pytest

from strukit import shapes


def test_round_hss_properties_match_design_guide_34():
    a = shapes.hss("HSS1.900x0.145")
    assert (a["type"], a["A"], a["tdes"], a["D_t"], a["Ix"], a["Sx"], a["rx"], a["Zx"], a["W"]) == ("HSS-ROUND", 0.749, 0.135, 14.1, 0.293, 0.309, 0.626, 0.421, 2.72)
    b = shapes.hss("HSS1.660X0.140")
    assert (b["A"], b["tdes"], b["D_t"], b["Ix"], b["Sx"], b["rx"], b["Zx"], b["W"]) == (0.625, 0.130, 12.8, 0.184, 0.222, 0.543, 0.305, 2.27)


def test_rectangular_hss_and_pipe_load():
    r = shapes.hss("HSS6x4x1/4")
    assert r["type"] == "HSS-RECT" and (r["Ht"], r["B"], r["tdes"], r["A"]) == (6, 4, 0.233, 4.3) and r["Ix"] > r["Iy"]
    p = shapes.hss("Pipe 3 STD")
    assert p["type"] == "PIPE" and p["OD"] == 3.5 and p["tdes"] == 0.201
    assert len(shapes.hss_labels("HSS-RECT")) == 525 and len(shapes.hss_labels("HSS-ROUND")) == 189 and len(shapes.hss_labels("PIPE")) == 51
    with pytest.raises(shapes.ShapeError):
        shapes.hss("HSS99x99x1")
