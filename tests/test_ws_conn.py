"""Connection worksheets against AISC Design Examples v16.0 (the same references the
weld and bolt modules are checked against in test_welds_* and test_bolts_*)."""
import pytest

from strukit import ws_conn
from strukit.ws_steel_beam import Combo, WorksheetError

LRFD = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "given")]
ASD = [Combo("D + L", {"D": 1, "L": 1}, "given")]


def test_bolt_line_example_II_A_1A():
    # (8) 3/4 in Group 120 (A325-N) bolts in double shear through two 5/16 in angles and a
    # W36 web: printed 282 kips (LRFD), 187 kips (ASD).  Loads chosen to give D/C near 1.
    plies = [(0.3125, 65.0, True, 2), (0.625, 65.0, False)]
    s = ws_conn.bolt_line("BG1", [dict(case="D", P=50.0), dict(case="L", P=130.0)], LRFD, "LRFD",
                          0.75, "A325", 8, 3.0, 1.25, plies, "N", 2, True)
    r = s.rows[0]
    assert r.demand == pytest.approx(268.0) and r.status == "OK"
    assert 250 < r.capacity < 300                       # exact value is asserted in test_bolts_aisc_examples
    from strukit import bolts
    assert r.capacity == pytest.approx(bolts.bolt_line(0.75, "A325", 8, 3.0, 1.25, plies, "N", 2, True, "LRFD").R_avail)


def test_fillet_weld_size_rows_and_demand():
    s = ws_conn.fillet_weld("W1", [dict(case="D", P=10.0), dict(case="L", P=30.0)], ASD, "ASD",
                            0.25, 16.0, 2, 70.0, 0.0, False, False, t_thinner=0.375, t_edge=0.375)
    from strukit import welds
    assert s.rows[0].demand == pytest.approx(40.0)
    assert s.rows[0].capacity == pytest.approx(welds.fillet(0.25, 16.0, 2, 70.0, 0.0, False, False, method="ASD").R_avail)
    mn = next(r for r in s.rows if r.check == "minimum weld size")
    assert mn.demand == pytest.approx(3 / 16) and mn.status == "OK"
    mx = next(r for r in s.rows if r.check.startswith("maximum weld size"))
    assert mx.capacity == pytest.approx(0.375 - 1 / 16) and mx.status == "OK"
    small = ws_conn.fillet_weld("W2", [dict(case="D", P=1.0)], ASD, "ASD", 0.125, 6.0, 1, 70.0, 0.0, False, False,
                                t_thinner=0.75)
    assert next(r for r in small.rows if r.check == "minimum weld size").status == "FLAG"
    assert any("Table J2.4" in n for n in ws_conn.fillet_weld("W3", [dict(case="D", P=1.0)], ASD, "ASD", 0.25, 6.0, 1,
                                                               70.0, 0.0, False, False).not_checked)


def test_missing_inputs_stop():
    with pytest.raises(WorksheetError):
        ws_conn.fillet_weld("W", [], ASD, "ASD", 0.25, 6, 1, 70, 0, False, False)
    with pytest.raises(WorksheetError):
        ws_conn.fillet_weld("W", [dict(case="D", P=1.0)], ASD, "ASD", 0.25, 6, 1, 70, 0, None, False)
    with pytest.raises(WorksheetError):
        ws_conn.bolt_line("B", [dict(case="D", P=1.0)], ASD, "ASD", 0.75, "A325", 2, 3, 1.5, [], "N", 1, True)
