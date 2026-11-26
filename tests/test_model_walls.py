"""Bearing walls and continuous footing lines in the building model: a joist row covering part of a beam or wall, walls passing loads down
to walls and footings, several members summed on one footing, members end to end not carrying each other. Checked by statics."""
import json
import os

import pytest

from strukit.gui import calc

PROJ = dict(name="T", method="ASD", combos_asd=[dict(expr="D + L", source="t"), dict(expr="D + Lr", source="t")],
            combos_lrfd=[dict(expr="1.2D + 1.6L", source="t"), dict(expr="1.2D + 1.6Lr", source="t")],
            model=dict(levels=[dict(name="Foundation", elev="0"), dict(name="Main", elev="9"), dict(name="Roof", elev="18")], grids_x=[], grids_y=[]))
AR = lambda c, m: dict(case=c, kind="area", mag=str(m), mag2="", x1="", x2="", label="")
J = dict(name="BCI 4500S-1.8", depth="11.875", spacing="16", bearing="3.5", stiffeners="no", flange="yes", defl=[])
SW = dict(G="0.5", G_source="t", panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", blocking="blocked", h="9", load="wind",
          holddown="no", lengths="20", V="1000", v_source="t")
CF = dict(W="2", h="10", fc="3000", fy="60000", conc_pcf="145", wall="8", wall_kind="concrete", stem_h="36", stem_pcf="145", bar_t="5", spacing_t="12", bar_l="5",
          n_l="2", cover="3", P_service="1", service_combo="x", Pu="1", strength_combo="x", dead_factor="1.2", q_allow="1500", soil_source="t", soil_depth="3.5", soil_pcf="110")


def _by(out):
    return {m["values"]["mark"]: m["values"] for m in out["members"]}


def _sum(v, case):
    return sum(float(r.get("P") or 0) for r in v.get("loads", []) if isinstance(r, dict) and r.get("link") and r.get("case") == case)


def test_walls_footings_and_row_width():
    mem = [dict(kind="ijoist", values=dict(J, mark="RJ", span="20", loads=[AR("Lr", 20), AR("D", 15)], at_level="Roof", at_x1="2", at_y1="0", at_x2="2", at_y2="20", at_row="10")),
           dict(kind="ijoist", values=dict(J, mark="FJ", span="20", loads=[AR("L", 40)], at_level="Main", at_x1="0", at_y1="0", at_x2="0", at_y2="20", at_row="20")),
           dict(kind="shear_wall", values=dict(SW, mark="UW1", at_level="Roof", at_x1="0", at_y1="0", at_x2="20", at_y2="0")),
           dict(kind="shear_wall", values=dict(SW, mark="UW2", at_level="Roof", at_x1="0", at_y1="20", at_x2="20", at_y2="20")),
           dict(kind="shear_wall", values=dict(SW, mark="LW1", at_level="Main", at_x1="0", at_y1="0", at_x2="20", at_y2="0")),
           dict(kind="shear_wall", values=dict(SW, mark="LW2", at_level="Main", at_x1="0", at_y1="20", at_x2="20", at_y2="20")),
           dict(kind="footing_cont", values=dict(CF, mark="CF1", at_x1="0", at_y1="0", at_x2="20", at_y2="0")),
           dict(kind="footing_cont", values=dict(CF, mark="CF2", at_x1="0", at_y1="20", at_x2="20", at_y2="20"))]
    out = calc.model_links(PROJ, mem)
    v = _by(out)
    assert out["problems"] == []
    assert _sum(v["UW1"], "Lr") == pytest.approx(20 * 10 * 10, abs=2)        # 20 psf, 10 ft row, half of the 20 ft span
    assert _sum(v["LW1"], "L") == pytest.approx(40 * 20 * 10, abs=2) and _sum(v["LW1"], "Lr") == pytest.approx(2000, abs=2)   # floor row 20 ft + the wall above
    D = _sum(v["LW1"], "D")
    assert float(v["CF1"]["P_service"]) == pytest.approx((D + 8000) / 20, abs=1) and v["CF1"]["service_combo"] == "D + L"
    assert float(v["CF2"]["P_service"]) == pytest.approx(float(v["CF1"]["P_service"]), abs=1)


def test_several_on_one_footing_and_point_on_a_line():
    mem = [dict(kind="wood_post", values=dict(mark="P1", species="DOUGLAS FIR-LARCH", grade="No. 2", size="6x6", height="9", Ke1="1", Ke2="1", k_source="t",
                                               loads=[dict(case="L", P="3000", label=""), dict(case="D", P="1000", label="")], at_level="Main", at_base="Foundation", at_x1="5", at_y1="5")),
           dict(kind="wood_post", values=dict(mark="P2", species="DOUGLAS FIR-LARCH", grade="No. 2", size="6x6", height="9", Ke1="1", Ke2="1", k_source="t",
                                               loads=[dict(case="Lr", P="2000", label="")], at_level="Main", at_base="Foundation", at_x1="5", at_y1="5")),
           dict(kind="footing_iso", values=dict(mark="F1", at_x1="5", at_y1="5")),
           dict(kind="wood_post", values=dict(mark="P3", species="DOUGLAS FIR-LARCH", grade="No. 2", size="6x6", height="9", Ke1="1", Ke2="1", k_source="t",
                                               loads=[dict(case="L", P="3000", label="")], at_level="Main", at_base="Foundation", at_x1="0", at_y1="10")),
           dict(kind="footing_cont", values=dict(CF, mark="CF", at_x1="0", at_y1="0", at_x2="0", at_y2="20"))]
    out = calc.model_links(PROJ, mem)
    v = _by(out)
    assert any("P3" in p and "not spread" in p for p in out["problems"])
    assert float(v["F1"]["P_service"]) == pytest.approx(4000) and v["F1"]["service_combo"] == "D + L"     # 1000 + 3000 beats 1000 + 2000 (Lr of P2)


def test_joists_end_to_end_do_not_carry_each_other():
    mem = [dict(kind="ijoist", values=dict(J, mark="J1", span="10", loads=[AR("L", 40)], at_level="Main", at_x1="0", at_y1="0", at_x2="0", at_y2="10")),
           dict(kind="ijoist", values=dict(J, mark="J2", span="10", loads=[AR("L", 40)], at_level="Main", at_x1="0", at_y1="10", at_x2="0", at_y2="20")),
           dict(kind="lvl_beam", values=dict(mark="B", grade="2.1E 2800", thickness="1.75", depth="11.875", plies="2", span="12", bearing="3", bracing="supported throughout",
                                             repetitive="no", unit_weight="", loads=[], defl=[], at_level="Main", at_x1="-1", at_y1="10", at_x2="11", at_y2="10"))]
    out = calc.model_links(PROJ, mem)
    v = _by(out)
    rows = [r for r in v["B"]["loads"] if r.get("link")]
    assert {r["link"]["src"] for r in rows} == {"J1", "J2"}


def test_job_2026_011_model_runs():
    """Job 2026-011 placed as one building model (test material; the job is built): the load path links and the wind and seismic reach
    the wall lines. The problems StruKit reports are the parts of the house it cannot represent (the existing house, posts on footing lines)."""
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    out = calc.model_links(d["project"], d["members"])
    assert out["placed"] == 24 and out["made"] >= 18
    v = _by(out)
    assert float(v["Footing A"]["P_service"]) > 5000 and float(v["Footing Line 1"]["P_service"]) > 500
    g = calc.lateral_governing(d["project"], out["members"])
    walls = {m["values"]["mark"]: m["values"] for m in g["members"] if m["kind"] in ("shear_wall", "ftao_wall")}
    assert all(float(w["V"]) > 0 for w in walls.values())


def test_existing_walls_take_gravity_and_lateral():
    """2026-011 with the existing house wall (Line 2) as existing construction: the lower floor joists and the roof joists end on it, and it
    takes its share of the wind across the house. The loads per foot on it equal the floor and roof live loads the sealed calculations put on
    the Line 2 headers (297 and 598 plf, typed by hand there)."""
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    out = calc.model_links(d["project"], d["members"])
    ex = {e["source"]: e for e in out["existing"]}
    assert ex["FJ-lower"]["cases"]["L"] == pytest.approx(297, abs=2) and ex["Roof joists"]["cases"]["Lr"] == pytest.approx(598, abs=4)
    g = calc.lateral_governing(d["project"], out["members"])
    x_lines = {l["wall"]: l["V"] for l in g["lines"] if l.get("governs") and l["wind"] == "X"}
    assert x_lines["Line 1, lower level"] == pytest.approx(x_lines["Existing house wall, lower level (existing)"])
    assert not any("only one wall line" in p for p in g["problems"])


def test_wall_weight_reaches_the_footing_line():
    """A typed wall weight (psf x story height from the level elevations x wall length) goes down the wall stack as dead load: 10 psf on a
    9.5 ft story adds 95 lb/ft to the continuous footing under it for each wall so weighted. A weight with no source is refused."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))

    def foot(ms):
        out = calc.model_links(d["project"], ms)
        return float(next(m for m in out["members"] if m["values"].get("mark") == "Footing Line 1")["values"]["P_service"]), out

    ms = copy.deepcopy(d["members"])
    p0, _ = foot(ms)
    for mk in ("Line 1, lower level", "Line 1, main level"):
        next(m for m in ms if m["values"].get("mark") == mk)["values"].update(at_wall_psf="10", at_wall_psf_source="test value")
    p2, _ = foot(ms)
    assert p2 - p0 == pytest.approx(2 * 10 * 9.5, abs=1.0)
    w = next(m for m in ms if m["values"].get("mark") == "Line 1, lower level")["values"]
    w["at_wall_psf_source"] = ""
    assert "source" in calc._wall_weight(d["project"], w)


def test_post_on_footing_line_spread_over_typed_length():
    """A post on a continuous footing line is reported until the footing has a spread length with its source; then the post's load by case
    divided by that length is put on the footing per foot (statics: twice the length, half the load per foot)."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    ms = copy.deepcopy(d["members"])
    out = calc.model_links(d["project"], ms)
    assert any("Column A, base" in p and "not spread" in p for p in out["problems"])
    fv = next(m for m in ms if m["values"].get("mark") == "Footing Line A")["values"]
    got = []
    for L in ("4", "8"):
        fv.update(at_spread=L, at_spread_source="test value")
        out = calc.model_links(d["project"], ms)
        assert not any("Footing Line A" in p for p in out["problems"])
        f = next(m for m in out["members"] if m["values"].get("mark") == "Footing Line A")["values"]
        assert "spread over " + L + " ft of footing" in f["loads_from"]
        got.append(float(f["P_service"]))
    assert got[1] == pytest.approx(got[0] / 2, abs=1.0)
