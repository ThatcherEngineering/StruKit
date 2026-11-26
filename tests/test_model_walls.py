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
    pad = next(p for p in out["pads"] if p["src"] == "P3")             # P3 on the footing line: a pad check of that line
    assert pad["foot"] == "CF" and pad["q"] <= pad["q_allow"]
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
    assert out["placed"] == 25 and out["made"] >= 18
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
    # openings deducted when picked: a 3 x 4 ft window and a 3 x 6.8 ft door take 10 psf x 32.4 sq ft off the wall
    w["at_wall_psf_source"] = "test value"
    W0, _ = calc._wall_weight(d["project"], w)
    w.update(at_openings="2 3 3 4; 8 3 0 6.8", at_wall_deduct="yes")
    W1, note = calc._wall_weight(d["project"], w)
    assert W0 - W1 == pytest.approx(10 * (12 + 20.4)) and "less 32.4 sq ft of 2 openings" in note
    w["at_wall_deduct"] = "no"
    assert calc._wall_weight(d["project"], w)[0] == pytest.approx(W0)
    w.update(at_wall_deduct="yes", at_openings="2 3 x 4")
    assert "cannot be read" in calc._wall_weight(d["project"], w)


def test_point_loads_on_footing_lines_get_pads():
    """Posts on continuous footing lines are checked as pads: the continuous footing over its width (or the typed length) with the point load,
    its own line load and stem wall; where the soil bearing is exceeded a larger pad is sized in 3 in. steps (square, or lengthened along the
    line when a width across is typed). Each pad is an Isolated Footing member whose own sheet checks bearing, shear and flexure."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    ms = copy.deepcopy(d["members"])
    out = calc.model_links(d["project"], ms)
    pads = {p["src"]: p for p in out["pads"]}
    assert set(pads) == {"Column A", "Column B", "Post under Beam B"}
    assert not pads["Column A"]["enlarged"] and (pads["Column A"]["B"], pads["Column A"]["L"]) == (2.0, 2.0)
    pb = pads["Post under Beam B"]
    assert pb["enlarged"] and pb["B"] == pb["L"] == 2.25 and pb["q"] <= pb["q_allow"]
    # by hand: a 2 ft square fails, 2.25 ft passes (no line load on Footing Line A; stem wall, footing and soil weights as typed on it)
    fv = next(m for m in ms if m["values"]["mark"] == "Footing Line A")["values"]
    W, h, conc = float(fv["W"]), float(fv["h"]), float(fv["conc_pcf"])
    stem = float(fv["wall"]) / 12 * float(fv.get("stem_h") or 0) / 12 * float(fv.get("stem_pcf") or 0)
    sd, sp = float(fv.get("soil_depth") or 0), float(fv.get("soil_pcf") or 0)
    pad = next(m for m in out["members"] if m["values"].get("mark") == "Footing Line A at Post under Beam B")["values"]
    P = float(pad["P_service"])
    qh = lambda B: (P - stem * 2.25 + stem * B + B * B * h / 12 * conc + (B * B - (float(fv["wall"]) / 12) ** 2) * sd * sp) / (B * B)
    assert qh(2.25) == pytest.approx(pb["q"], rel=1e-3) and qh(2.0) > pb["q_allow"]
    sheet, _, _ = calc.build("footing_iso", pad, d["project"])
    assert all(r.status == "OK" for r in sheet.rows)
    # a pad width across typed: the pad is lengthened along the line instead
    fv.update(at_pad_width="2")
    pb2 = next(p for p in calc.model_links(d["project"], ms)["pads"] if p["src"] == "Post under Beam B")
    assert pb2["B"] == 2.0 and pb2["L"] > 2.25 and pb2["q"] <= pb2["q_allow"]
    # a longer length of footing typed for point loads: the continuous footing carries it
    fv.update(at_pad_width="", at_spread="4", at_spread_source="test value")
    pb3 = next(p for p in calc.model_links(d["project"], ms)["pads"] if p["src"] == "Post under Beam B")
    assert not pb3["enlarged"] and pb3["L"] == 4.0
    # running again replaces the pads (no duplicates)
    out2 = calc.model_links(d["project"], out["members"])
    assert sum(1 for m in out2["members"] if m["values"].get("pad_of")) == 3

def test_header_in_a_wall_line():
    """A beam placed in a wall line at the wall's top level is a header: the joist row over its length goes onto it, the wall keeps the rest
    of the row, and the header's end reactions come down the jack studs onto what is under the wall (here the lower-story wall). Statics:
    the roof live load reaching the lower wall is the same with and without the header; with Roof Beam A over 0.5 to 11.25 ft of the row as
    well, the main wall keeps 26.75 - 10.75 - 4 = 12 ft of row."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))

    def run(ms):
        out = calc.model_links(d["project"], ms)
        by = {m["values"]["mark"]: m["values"] for m in out["members"]}
        return by, sum(float(r["P"]) for r in by["Line 1, lower level"]["loads"] if r.get("case") == "Lr")

    ms = copy.deepcopy(d["members"])
    _, lr0 = run(ms)
    h = next(m for m in ms if m["values"]["mark"] == "Header A LL")["values"]
    h.update(at_level="Roof", at_x1="14", at_y1="0", at_x2="18", at_y2="0", loads=[])
    by, lr1 = run(ms)
    assert lr1 == pytest.approx(lr0, abs=2)
    row = [r for r in by["Header A LL"]["loads"] if r.get("case") == "Lr"]
    assert len(row) == 1 and row[0]["x1"] == "0" and row[0]["x2"] == "4"
    main = sum(float(r["P"]) for r in by["Line 1, main level"]["loads"] if r.get("case") == "Lr")
    assert main == pytest.approx(float(row[0]["mag"]) * 12.0, rel=0.002)
    jacks = [r for r in by["Line 1, lower level"]["loads"] if "Header A LL" in (r.get("label") or "") and r.get("case") == "Lr"]
    assert len(jacks) == 2 and sum(float(r["P"]) for r in jacks) == pytest.approx(float(row[0]["mag"]) * 4, abs=2)


def test_header_in_the_lower_wall_takes_the_wall_above():
    """A header in the lower-story wall takes the part of the upper wall over it (uniform over its length) and the joist rows over it; the
    lower wall keeps the rest; the jack studs bring the header ends to the footing line. Statics: the floor live load is the same in total."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    ms = copy.deepcopy(d["members"])
    next(m for m in ms if m["values"]["mark"] == "Footing Line 1")["values"].update(at_spread="2", at_spread_source="test value")
    L = lambda rows: sum(float(r["P"]) for r in rows if r.get("case") == "L")
    out = calc.model_links(d["project"], ms)
    l0 = L(next(m for m in out["members"] if m["values"]["mark"] == "Line 1, lower level")["values"]["loads"])
    next(m for m in ms if m["values"]["mark"] == "Header B LL")["values"].update(at_level="Main floor", at_x1="5.0", at_y1="0", at_x2="10", at_y2="0", loads=[])
    out = calc.model_links(d["project"], ms)
    by = {m["values"]["mark"]: m["values"] for m in out["members"]}
    hl = sum(float(r["mag"]) * (float(r["x2"]) - float(r["x1"])) for r in by["Header B LL"]["loads"] if r.get("case") == "L")
    assert L(by["Line 1, lower level"]["loads"]) + hl == pytest.approx(l0, abs=2)
    up = [r for r in by["Header B LL"]["loads"] if "Line 1, main level" in r.get("label", "") and r["case"] == "Lr"]
    assert len(up) == 1 and (up[0]["x1"], up[0]["x2"]) == ("0", "5")
    assert {p["support"] if "support" in p else p["src"] for p in out["pads"] if p["src"] == "Header B LL"} == {"Header B LL"}
    assert sum(1 for p in out["pads"] if p["src"] == "Header B LL") == 2                  # a pad check under each end


def test_header_at_a_wall_corner():
    """Roof Beam A is a header in the Line 1 wall starting at the Line A corner: its left jack studs stand on the Line 1 lower wall (the
    wall line the header is in), not reported as two walls under it; it takes the roof joist row from 0.5 to 11.25 ft."""
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    out = calc.model_links(d["project"], d["members"])
    assert not any("Roof Beam A" in p for p in out["problems"])
    by = {m["values"]["mark"]: m["values"] for m in out["members"]}
    row = [r for r in by["Roof Beam A"]["loads"] if r.get("case") == "Lr"]
    assert len(row) == 1 and (row[0]["x1"], row[0]["x2"]) == ("0.5", "11.25")
    assert any("Roof Beam A, left support" in r.get("label", "") for r in by["Line 1, lower level"]["loads"])


def test_seismic_weights_from_the_model():
    """Effective seismic weight by level from the placed members (Sect. 12.7.2): each member's own dead load (links not counted twice), a
    joist row times the members over the length it covers, walls half up and half down by their typed weight. Statics on the 2026-011 model:
    the roof joist row covers 26.75 ft (16 ft on the wall, 10.75 ft on Roof Beam A) at 24 in.; a 10 psf wall weight adds half of
    10 x 9.5 x 27.25 lb to each of the two levels it spans, except the half that goes to the foundation."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    ms = copy.deepcopy(d["members"])
    w = calc.model_seismic_weights(d["project"], ms)
    rj = next(m for m in ms if m["values"]["mark"] == "Roof joists")
    own = dict(rj["values"], loads=[r for r in rj["values"]["loads"] if not isinstance(r.get("link"), dict)])
    per = sum(s_["cases"].get("D", 0) for s_ in calc.case_reactions("ijoist", own, d["project"])["supports"])
    rba = next(m for m in ms if m["values"]["mark"] == "Roof Beam A")
    rb = sum(s_["cases"].get("D", 0) for s_ in calc.case_reactions("lvl_beam", rba["values"], d["project"])["supports"])
    assert w["levels"]["Roof"] == pytest.approx(per * 26.75 * 12 / 24 + rb, rel=1e-4)
    assert w["levels"]["Foundation"] == 0 and any("No wall weight" in p for p in w["problems"])
    for mk in ("Line 1, main level", "Line 1, lower level"):
        next(m for m in ms if m["values"]["mark"] == mk)["values"].update(at_wall_psf="10", at_wall_psf_source="test value")
    w2 = calc.model_seismic_weights(d["project"], ms)
    half = 10 * 9.5 * 27.25 / 2
    assert w2["levels"]["Roof"] - w["levels"]["Roof"] == pytest.approx(half, abs=1)
    assert w2["levels"]["Main floor"] - w["levels"]["Main floor"] == pytest.approx(2 * half, abs=1)
    # the takeoff prints on the seismic sheet
    eq = next(m for m in ms if m["kind"] == "seismic_elf")["values"]
    sheet, _, _ = calc.build("seismic_elf", dict(eq, w_source="building model weight takeoff", w_parts=["Roof: 1 lb"]), d["project"])
    assert any(b.get("title") == "Seismic Weight Takeoff" for b in sheet.blocks) and ("Seismic Weights", "building model weight takeoff") in sheet.info


def test_diaphragms_filled_from_the_model():
    """Placed Wood Diaphragms (level, load direction) take the span between neighbouring wall lines parallel to the load, the depth of the
    plan along the load, and the load per foot of the lateral distribution; wind or seismic by the larger of w and 1.4 w (SDPWS 4.1.4)."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    ms = copy.deepcopy(d["members"])
    r = calc.model_diaphragms(d["project"], ms)
    f = {x["mark"]: x for x in r["filled"]}
    roofY = f["Roof diaphragm, wind on Line 1"]
    assert (roofY["dir"], roofY["L"], roofY["W"], roofY["load"]) == ("Y", 27.25, 29.75, "wind")
    spans = calc.lateral_wind(d["project"], ms)["spans"]
    sp = next(s_ for s_ in spans if s_["level"] == "Roof" and s_["dir"] == "Y")
    assert roofY["w"] == pytest.approx(sp["w"])
    fx = f["Main floor diaphragm, wind on Line A or B"]
    assert fx["L"] == 29.75 and "Existing house wall" in fx["lines"][1]
    # seismic governs once 1.4 x its load per foot is over the wind's
    eq = next(m for m in ms if m["kind"] == "seismic_elf")["values"]
    for row in eq["levels"]:
        row["w"] = str(float(row["w"]) * 20)
    r2 = calc.model_diaphragms(d["project"], ms)
    assert {x["load"] for x in r2["filled"]} == {"seismic"}
    v = next(m for m in r2["members"] if m["values"]["mark"] == "Roof diaphragm, wind on Line 1")["values"]
    assert v["load"] == "seismic" and "story force at Roof" in v["w_source"]


def test_existing_beam_and_post_carry_and_list():
    """Existing construction may be a beam, a post or a footing: what lands on it stops there and is listed; only existing walls are wall
    lines for wind and seismic. 2026-011 with the lower existing wall entered as an existing beam instead, and Column B removed with an
    existing post in its place: FJ-lower ends on the beam (297 plf live, as on the wall) and Floor Beam A's right end on the post."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    proj = copy.deepcopy(d["project"])
    ex = proj["model"]["existing"]
    ex[1].update(kind="beam")
    ex.append(dict(name="Existing post", kind="post", level="Main floor", x1="27.25", y1="14.896"))
    ms = [m for m in copy.deepcopy(d["members"]) if m["values"]["mark"] != "Column B"]
    out = calc.model_links(proj, ms)
    on = {(e["wall"], e["source"]): e for e in out["existing"]}
    assert on[("Existing house wall, lower level", "FJ-lower")]["cases"]["L"] == pytest.approx(297, abs=2)
    fa = on[("Existing post", "Floor Beam A")]
    assert fa["unit"] == "lb" and fa["support"] == "right support" and fa["cases"]["L"] > 0
    g = calc.lateral_governing(proj, out["members"])
    walls = {l["wall"] for l in g["lines"]}
    assert "Existing house wall, main level (existing)" in walls and not any("lower level (existing)" in w for w in walls)
    sh = calc.existing_sheet(proj, out["members"])
    assert ("Existing", "Existing house wall, main level (wall), Existing house wall, lower level (beam), Existing post (post)") in sh.info


def test_header_jack_and_king_studs():
    """Jack studs under each end of a header carry that end's reaction by load case (2 or more as a Built-Up Wood Column, 1 as a Wood
    Post); king studs take the wind on the wall over half the opening plus half a stud space, shared among them. Made again on every run."""
    import copy
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    proj = copy.deepcopy(d["project"])
    proj["combos_asd"] = list(proj.get("combos_asd") or []) + [dict(expr="D + 0.6W", source="ASCE/SEI 7-22 Sect. 2.4.1, combination 5")]
    ms = copy.deepcopy(d["members"])
    next(m for m in ms if m["values"]["mark"] == "Roof Beam A")["values"].update(
        at_jacks="2", at_jack_size="2x6", at_jack_species="DOUGLAS FIR-LARCH", at_jack_grade="No. 2", at_jack_h="8", at_jack_brace="1.33",
        at_kings="2", at_king_h="9", at_king_p="25", at_king_p_source="test value", at_stud_sp="16")
    out = calc.model_links(proj, ms)
    by = {m["values"]["mark"]: m for m in out["members"]}
    hdr = by["Roof Beam A"]
    reac = {s_["name"]: s_["cases"] for s_ in calc.case_reactions(hdr["kind"], hdr["values"], proj)["supports"]}
    for side in ("left support", "right support"):
        j = by[f"Roof Beam A jacks, {side}"]
        assert j["kind"] == "builtup_post" and j["values"]["plies"] == "2"
        got = {r["case"]: float(r["P"]) for r in j["values"]["loads"]}
        assert all(got[c] == pytest.approx(P, abs=1) for c, P in reac[side].items() if abs(P) >= 0.5)
        sheet, _, _ = calc.build("builtup_post", j["values"], proj)
        assert sheet.rows
    k = by["Roof Beam A king studs"]["values"]
    assert float(k["lateral"][0]["mag"]) == pytest.approx(25 * (11.25 / 2 + 16 / 24) / 2, abs=0.1)
    sheet, _, _ = calc.build("wood_post", k, proj)
    assert any(r.combo == "D + 0.6W" for r in sheet.rows)
    out2 = calc.model_links(proj, out["members"])
    assert sum(1 for m in out2["members"] if m["values"].get("stud_of")) == 3
