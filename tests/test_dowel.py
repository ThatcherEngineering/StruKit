"""Dowel-type fastener yield limit equations, 2018 NDS Sect. 12.3, checked against the standard's own
published tables: Table 12N (common wire nails, single shear, p = 10D) and Table 12A (bolts, single
shear, sawn lumber). Table values are rounded (nails to 1 lb, bolts to 10 lb)."""
import pytest
from strukit import dowel


@pytest.mark.parametrize("side_t, D, G, Z", [
    (1.5, 0.148, 0.50, 118), (1.5, 0.162, 0.50, 141), (1.5, 0.131, 0.50, 97), (0.75, 0.148, 0.50, 105), (1.5, 0.148, 0.42, 100),
    (1.5, 0.162, 0.42, 120), (0.75, 0.099, 0.67, 73), (1.5, 0.192, 0.55, 185), (1.0, 0.192, 0.50, 159), (0.75, 0.162, 0.36, 80),
    (1.25, 0.128, 0.46, 86), (1.0, 0.162, 0.43, 113)])
def test_nails_against_table_12n(side_t, D, G, Z):
    assert dowel.nail(D, side_t, G, G)["Z"] == pytest.approx(Z, abs=0.75)


@pytest.mark.parametrize("D, ts, tm, G, table", [
    (0.5, 1.5, 1.5, 0.50, (480, 300, 300, 220)), (0.75, 1.5, 2.5, 0.50, (1020, 590, 500, 380)), (1.0, 1.5, 1.5, 0.67, (1290, 740, 740, 470)),
    (0.625, 1.5, 2.5, 0.55, (930, 560, 490, 390)), (0.5, 1.5, 2.5, 0.46, (580, 340, 330, 270)), (0.875, 1.75, 1.75, 0.50, (990, 550, 550, 340))])
def test_bolts_against_table_12a(D, ts, tm, G, table):
    got = [dowel.bolt(D, ts, tm, G, G, a, b)["Z"] for a, b in ((0, 0), (90, 0), (0, 90), (90, 90))]     # Z parallel, Zs perp, Zm perp, Z perp
    for g, t in zip(got, table):
        assert g == pytest.approx(t, abs=7)


def test_dowel_pieces():
    assert dowel.fe(0.50, 0.148) == 4650 and dowel.fe(0.42, 0.131) == 3350 and dowel.fe(0.50, 0.5) == 5600 and dowel.fe(0.50, 0.5, 90) == 3150
    assert dowel.fe(0.67, 1.0, 90) == 3400 and dowel.fe(0.50, 0.75, 90) == 2600                    # Table 12.3.3 values
    assert dowel.rd(0.148, "IV") == 2.2 and dowel.rd(0.192, "Im") == pytest.approx(2.42) and dowel.rd(0.5, "II") == 3.6 and dowel.rd(0.5, "Im", 90) == 5.0
    assert dowel.nail_fyb(0.131) == 100000 and dowel.nail_fyb(0.148) == 90000 and dowel.nail_fyb(0.192) == 80000 and dowel.nail_fyb(0.244) == 70000
    d = dowel.bolt(0.5, 1.5, 3.5, 0.50, 0.50, double=True)
    assert set(d["modes"]) == {"Im", "Is", "IIIs", "IV"} and d["Z"] > dowel.bolt(0.5, 1.5, 3.5, 0.50, 0.50)["Z"]
    short = dowel.nail(0.148, 1.5, 0.5, 0.5, penetration=1.0)                                   # 6.8 D penetration
    assert short["Z"] < 118 and short["lm"] == pytest.approx(0.852)
    with pytest.raises(dowel.DowelError):
        dowel.nail(0.148, 1.5, 0.5, 0.5, penetration=0.8)
    with pytest.raises(dowel.DowelError):
        dowel.bolt(1.25, 1.5, 1.5, 0.5, 0.5)


def test_nailed_connection_sheet(tmp_path):
    """8 - 16d common (0.162 x 3.5 in.) through a 1-1/2 in. side member into a 3-1/2 in. main member, Douglas Fir-Larch, dry:
    penetration 2.0 in. (12.3 D), Z = 141 lb (Table 12N). Wind 1,500 lb, D + 0.6W: 900 lb; CD = 1.6: 8(141)(1.6) = 1,804 lb."""
    from strukit.gui import calc
    from strukit import calcsheet
    proj = dict(job="2026-000", name="Test", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5a"),
                                                                        dict(expr="D", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 1a")])
    v = dict(mark="NC1", nail="16d common", D="0.162", length="3.5", n="8", side_t="1.5", G_side="0.50", G_side_source="Douglas Fir-Larch, NDS Table 12.3.3A",
             main_t="3.5", G_main="0.50", G_main_source="Douglas Fir-Larch, NDS Table 12.3.3A", service="dry", loads=[dict(case="W", P="1500")])
    sheet, kind, _ = calc.build("nailed_connection", v, proj)
    c = sheet.connection
    assert kind == "simple" and c["Z"] == pytest.approx(141, abs=0.75) and sheet.rows[0].demand == pytest.approx(900) and sheet.rows[0].capacity == pytest.approx(8 * 141 * 1.6, abs=8)
    calcsheet._simple_pdf(sheet, str(tmp_path / "n.pdf"), "2026-000", "NDS 2018", "2026-11-23")
    wet, _, _ = calc.build("nailed_connection", dict(v, service="wet in service", end_grain="yes", diaphragm="yes", loads=[dict(case="D", P="400")]), proj)
    assert wet.rows[0].capacity == pytest.approx(8 * c["Z"] * 0.9 * 0.7 * 0.67 * 1.1, rel=1e-6) and wet.rows[0].combo in ("D", "D + 0.6W")
    from strukit.ws_steel_beam import WorksheetError
    with pytest.raises(WorksheetError):
        calc.build("nailed_connection", dict(v, length="2.25"), proj)                 # 0.75 in. penetration, under 6 D
    with pytest.raises(calc.Missing):
        calc.build("nailed_connection", dict(v, loads=[]), proj)
