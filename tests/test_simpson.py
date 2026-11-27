"""Simpson Strong-Tie face-mount joist hangers (simpson.facemount): catalog C-C-2026 tables read into data/simpson_facemount.json.
The rows below were copied by hand from the catalog pages (pp. 114, 115, 119) and must match the data file; the adjustment factors
are the catalog's (p. 26 and p. 112: 2x carrying member 0.64 / 0.77; p. 110: end grain 0.67)."""
import pytest

from strukit import simpson
from strukit.gui import calc

HAND = [  # species, joist, model, nailing, uplift, floor, snow, roof, page
    ("DF/SP", "2x8", "LUS28", "", 1165, 1100, 1260, 1350, 114),
    ("DF/SP", "2x6", "HUS26", "", 1320, 2735, 3095, 3230, 114),
    ("DF/SP", "DBL 2x6", "HU26-2 / HUC26-2", "Max.", 1135, 1785, 2015, 2165, 114),
    ("DF/SP", "2x10", "HUS210", "", 2635, 5450, 5795, 5830, 115),
    ("DF/SP", "2x10", "HGUS210", "", 2090, 9100, 9100, 9100, 115),
    ("DF/SP", "DBL 2x10", "HU210-2 / HUC210-2", "Max.", 1895, 2680, 3020, 3250, 115),
    ("DF/SP", "DBL 2x10", "HUCQ210-2-SDS", "", 2345, 4315, 4315, 4315, 115),
    ("SPF/HF", "2x8", "LUS28", "", 1000, 945, 1085, 1160, 119),
    ("SPF/HF", "2x10", "LUS28", "", 1000, 945, 1085, 1160, 120),
    ("SPF/HF", "2x10", "HGUS210", "", 1545, 6340, None, None, 120),
]


@pytest.mark.parametrize("sp,joist,model,nail,up,fl,sn,rf,page", HAND)
def test_table_rows_match_the_catalog(sp, joist, model, nail, up, fl, sn, rf, page):
    rows = [r for r in simpson.facemount_rows() if r["species"] == sp and r["joist"] == joist and r["model"] == model and r["nailing"] == nail]
    assert rows, (sp, joist, model)
    r = rows[0]
    assert (r["uplift"], r["floor"], r["page"]) == (up, fl, page) and (sn is None or (r["snow"], r["roof"]) == (sn, rf))


def test_every_row_is_complete():
    rows = simpson.facemount_rows()
    assert len(rows) == 416 and all(r["joist"] and r["model"] and r["ga"] and r["W"] > 0 and r["H"] > 0 and r["B"] > 0 and r["header"] and r["joist_fast"]
                                   and r["uplift"] is not None and r["floor"] > 0 for r in rows)
    assert {"DF/SP", "SPF/HF"} == {r["species"] for r in rows}


def test_choice_and_adjustments():
    """2x8 DF/SP, 900 lb floor: LUS26 (865) and LU26 (835) fall short; LUS28 (1,100) is the first in the table that carries it.
    On a 2x header: LUS28 has 0.148 x 3 header nails, x 0.77 = 847 lb; HU210-2 (0.162 nails) x 0.64; end grain x 0.67."""
    h = simpson.facemount("2x8", "DF/SP", "lightest that works", 900, "floor (100)")
    assert h["row"]["model"] == "LUS28" and h["allow_down"] == 1100
    t = simpson.facemount("2x8", "DF/SP", "LUS28", 800, "floor (100)", two_by=True)
    assert t["factor"] == pytest.approx(0.77) and t["allow_down"] == pytest.approx(0.77 * 1100)
    u = simpson.facemount("DBL 2x10", "DF/SP", "HU210-2", 800, "roof (125)", uplift=500, two_by=True, nailing="Min.")
    assert u["row"]["nailing"] == "Min." and u["factor"] == pytest.approx(0.64) and u["allow_up"] == pytest.approx(0.64 * 1135)
    e = simpson.facemount("2x10", "DF/SP", "HUS210", 800, "snow (115)", end_grain=True)
    assert e["allow_down"] == pytest.approx(0.67 * 5795)
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("DBL 2x10", "DF/SP", "HUCQ210-2-SDS", 800, "floor (100)", two_by=True)
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x8", "DF/SP", "LUS210", 800, "floor (100)")
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x8", "DF/SP", "lightest that works", 50000, "floor (100)")


def test_on_the_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="JH1", joist="2x10", species="DF/SP", model="lightest that works", download="1200", duration="floor (100)", uplift="300",
             carrying="3x or larger, or a beam", load_source="joist J1")
    s = calc.build("joist_hanger", v, proj)[0]
    assert s.hanger["row"]["model"] == "LUS210" and all(r.status == "OK" for r in s.rows)
    with pytest.raises(calc.Missing):
        calc.build("joist_hanger", dict(v, load_source=""), proj)
    for vv in (v, dict(v, joist="DBL 2x10", model="HU210-2", nailing="Min.", carrying="2x (header nails shortened)"), dict(v, joist="6x12", model="lightest that works")):
        s = calc.build("joist_hanger", vv, proj)[0]
        calcsheet.simple_pdf(s, str(tmp_path / f"jh_{vv['joist'].replace(' ', '')}.pdf"), "Job", "Simpson C-C-2026", "Nov 26, 2026")


TF_HAND = [  # species, joist, model, uplift, floor, snow, roof, TF, page (catalog pp. 142, 146)
    ("DF/SP", "2x4", "PF24", 300, 1255, 1255, 1255, 1.0625, 142),
    ("DF/SP", "2x6", "JB26", 0, 995, 995, 995, 1.3125, 142),
    ("DF/SP", "DBL 2x10", "HUS210-2TF", 2315, 3735, 4065, 4275, 1.5, 142),
    ("DF/SP", "2x10", "BA210 (Max.)", 1275, 4720, 4720, 4720, 2.5, 142),
    ("SPF/HF", "4x14", "WP414", 0, 2230, 2230, 2230, 2.1875, 146),
]


@pytest.mark.parametrize("sp,joist,model,up,fl,sn,rf,tf,page", TF_HAND)
def test_top_flange_rows_match_the_catalog(sp, joist, model, up, fl, sn, rf, tf, page):
    rows = [r for r in simpson.rows_of("topflange") if r["species"] == sp and r["joist"] == joist and r["model"] == model]
    assert rows, (sp, joist, model)
    r = rows[0]
    assert (r["uplift"], r["floor"], r["snow"], r["roof"], r["TF"], r["page"]) == (up, fl, sn, rf, tf, page)


def test_top_flange_choice_and_limits(tmp_path):
    """2x10 DF/SP, 1,500 lb floor and 200 lb uplift: JB210A (260 / 1,685 lb, p. 142) is the first top-flange model that carries both;
    a hanger with "—" uplift is not chosen when there is uplift; a 2x nailer or end grain is not covered."""
    h = simpson.facemount("2x10", "DF/SP", "lightest that works", 1500, "floor (100)", 200, kind="topflange")
    assert h["row"]["model"] == "JB210A" and h["allow_up"] == 260
    j = simpson.facemount("2x6", "DF/SP", "lightest that works", 900, "floor (100)", 100, kind="topflange")
    assert j["row"]["model"] != "JB26" and j["allow_up"] >= 100
    assert simpson.facemount("2x10", "DF/SP", "BA210", 4000, "roof (125)", kind="topflange")["allow_down"] == 4720
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x10", "DF/SP", "JB210A", 1000, "floor (100)", two_by=True, kind="topflange")
    from strukit import calcsheet
    v = dict(mark="JH4", type="top flange", joist="2x10", species="DF/SP", model="lightest that works", download="1500", duration="floor (100)",
             uplift="200", carrying="3x or larger, or a beam", load_source="joist J2")
    s = calc.build("joist_hanger", v, dict(job="t", name="t", method="ASD"))[0]
    assert "top flange" in s.title and all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "tf.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")
