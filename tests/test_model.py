"""Building model: members placed on levels and grids are linked by position, then the load path is recalculated."""
import pytest
from strukit.gui import calc

COMBOS = dict(method="ASD", combos_asd=[dict(expr="D + L", source="t")], combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")])
MODEL = dict(levels=[dict(name="Foundation", elev="0"), dict(name="Floor", elev="10")],
             grids_x=[dict(name="A", at="0"), dict(name="B", at="20")], grids_y=[dict(name="1", at="0"), dict(name="2", at="16")])
PROJ = dict(COMBOS, name="t", number="t", date="2026-11-23", model=MODEL)
DEFL = [dict(label="live", expr="L", ratio="360", source="t")]


def _beam(mark, shape, span, w_D, w_L, **place):
    return dict(kind="steel_beam", values=dict(mark=mark, shape=shape, Fy="50", span=str(span), more_spans="", oh_left="", oh_right="", bracing="continuous", brace_pts="",
                self_weight="no", loads=[dict(case="D", kind="uniform", mag=str(w_D), x1="", x2="", label=""), dict(case="L", kind="uniform", mag=str(w_L), x1="", x2="", label="")],
                defl=DEFL, **place))


def _col(mark, **place):
    return dict(kind="hss_column", values=dict(mark=mark, shape="HSS6X6X3/8", Fy="46", Fy_source="t", height="10", Kx="1", Ky="1", k_source="t", self_weight="no", loads=[], moments=[], **place))


def _ftg(mark, **place):
    return dict(kind="footing_iso", values=dict(mark=mark, B="5", L="5", h="14", fc="3000", fy="60000", conc_pcf="145", col_x="8", col_y="8", supported="steel", plate_x="12", plate_y="12",
                bar="5", n_x="6", n_y="6", cover="3", bottom="x", q_allow="3000", soil_source="t", **place))


def _building():
    # two girders on grids A and B (16 ft, lines 1 to 2), one infill beam at mid-span between them (20 ft), a column and a footing under girder A at line 1
    return [_beam("B1", "W12X26", 20, 0.3, 0.5, at_level="Floor", at_x1="A", at_y1="8", at_x2="B", at_y2="8"),
            _beam("G1", "W16X31", 16, 0.05, 0.0, at_level="Floor", at_x1="A", at_y1="1", at_x2="A", at_y2="2"),
            _beam("G2", "W16X31", 16, 0.05, 0.0, at_level="Floor", at_x1="B", at_y1="1", at_x2="B", at_y2="2"),
            _col("C1", at_level="Floor", at_base="Foundation", at_x1="A", at_y1="1"),
            _ftg("F1", at_x1="A", at_y1="1")]


def test_coordinates():
    gx = MODEL["grids_x"]
    assert calc._coord("B", gx) == 20 and calc._coord("b+2.5", gx) == 22.5 and calc._coord("B-1", gx) == 19 and calc._coord("7.25", gx) == 7.25 and calc._coord("Z", gx) is None


def test_links_by_position_and_takedown():
    out = calc.model_links(PROJ, _building())
    v = {m["values"]["mark"]: m["values"] for m in out["members"]}
    # B1's two ends land on G1 and G2 at 8 ft; G1's left end lands on C1; C1 lands on F1. G1's right end and G2 have nothing under them: reported.
    assert out["placed"] == 5 and out["made"] == 4
    pt = [r for r in v["G1"]["loads"] if r.get("link")]
    assert {r["case"]: float(r["mag"]) for r in pt} == {"D": 3.0, "L": 5.0} and all(r["x1"] == "8" and r["kind"] == "point" for r in pt)
    col = {r["case"]: float(r["P"]) for r in v["C1"]["loads"]}
    assert col == pytest.approx({"D": 3.0 * 0.5 + 0.05 * 8, "L": 2.5})                      # half of B1's reaction (mid-span of G1) plus G1's own load
    assert float(v["F1"]["P_service"]) == pytest.approx(1900 + 2500, abs=1) and float(v["F1"]["Pu"]) == pytest.approx(1.2 * 1900 + 1.6 * 2500, abs=1)
    assert v["F1"]["loads_from"] == "reaction of C1, base"
    assert sum("nothing in the model is under it" in p for p in out["problems"]) == 3    # G1 right, G2 left, G2 right
    again = calc.model_links(PROJ, out["members"])                                         # run again: the same links, nothing doubled
    assert again["members"] == out["members"]
    for m in out["members"]:
        assert calc.results(m["kind"], m["values"], PROJ)["state"] == "done", m["values"]["mark"]


def test_length_mismatch_and_plan():
    ms = _building()
    ms[0]["values"]["span"] = "18"
    out = calc.model_links(PROJ, ms)
    assert any("placed 20.00 ft long in the model, but its spans add up to 18.00 ft" in p for p in out["problems"])
    plan = calc.model_plan(PROJ, _building())
    assert plan["levels"] == ["Foundation", "Floor"] and len(plan["items"]["Floor"]) == 4 and {i["mark"] for i in plan["items"]["Foundation"]} == {"F1", "C1"}
