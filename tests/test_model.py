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


def _wall(mark, lengths, **place):
    return dict(kind="shear_wall", values=dict(mark=mark, panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", blocking="blocked", G="0.50", G_source="t",
                h="9", lengths=lengths, load="wind", V="1", v_source="typed", holddown="no", **place))


def test_wind_to_wall_lines():
    """A 30 x 40 ft two-story box: wall lines on the two 40 ft sides and the two 30 ft sides at each story, and one interior line at the lower story."""
    from strukit import wind
    proj = dict(COMBOS, name="t", number="t", date="2026-11-23", model=dict(levels=[dict(name="Foundation", elev="0"), dict(name="Floor", elev="10"), dict(name="Roof", elev="20")],
                                                                          grids_x=[], grids_y=[]))
    W = dict(kind="wind_mwfrs", values=dict(mark="W1", V="115", V_source="t", exposure="C", exposure_basis="t", enclosure="enclosed", enclosure_basis="t", across="30", along="40",
             roof="gable or flat", eave="20", h="20", theta="0", Kzt="1.0", Kzt_source="t"))
    ms = [W]
    for lv in ("Roof", "Floor"):
        ms += [_wall(f"S-{lv}", "12, 12", at_level=lv, at_x1="0", at_y1="0", at_x2="40", at_y2="0"), _wall(f"N-{lv}", "12, 12", at_level=lv, at_x1="0", at_y1="30", at_x2="40", at_y2="30"),
               _wall(f"W-{lv}", "10, 10", at_level=lv, at_x1="0", at_y1="0", at_x2="0", at_y2="30"), _wall(f"E-{lv}", "10, 10", at_level=lv, at_x1="40", at_y1="0", at_x2="40", at_y2="30")]
    ms.append(_wall("Mid-Floor", "10", at_level="Floor", at_x1="20", at_y1="0", at_x2="20", at_y2="30"))
    out = calc.lateral_wind(proj, ms)
    assert out["problems"] == [], out["problems"]
    L = {l["wall"]: l for l in out["lines"]}
    cases = calc.build("wind_mwfrs", W["values"], proj)[0].wind["cases"]
    w_roof = max(wind.line_load(r, 15, 20)["w"] for r in cases)
    w_floor = max(wind.line_load(r, 5, 15)["w"] for r in cases)
    # wind in X is taken by the lines running in X (S and N, 30 ft apart): half the 30 ft width each
    assert L["S-Roof"]["V"] == pytest.approx(0.6 * w_roof * 15, rel=1e-6) and L["S-Roof"]["trib"] == 15 and L["S-Roof"]["from_above"] == 0
    assert L["S-Floor"]["V"] == pytest.approx(0.6 * (w_roof + w_floor) * 15, rel=1e-6) and L["S-Floor"]["from_above"] == pytest.approx(L["S-Roof"]["V"])
    # wind in Y: W and E at the roof (20 ft each); at the floor the interior line takes the middle 20 ft and the outer lines 10 ft, plus what comes from above
    assert L["W-Roof"]["V"] == pytest.approx(0.6 * w_roof * 20, rel=1e-6)
    assert L["Mid-Floor"]["V"] == pytest.approx(0.6 * w_floor * 20, rel=1e-6) and L["Mid-Floor"]["from_above"] == 0
    assert L["W-Floor"]["V"] == pytest.approx(0.6 * w_floor * 10 + L["W-Roof"]["V"], rel=1e-6)
    tot_y = L["W-Floor"]["V"] + L["E-Floor"]["V"] + L["Mid-Floor"]["V"]
    assert tot_y == pytest.approx(0.6 * (w_roof + w_floor) * 40, rel=1e-6)                 # nothing lost: the base shear above mid-height of the first story
    v = {m["values"]["mark"]: m["values"] for m in out["members"]}
    assert float(v["S-Floor"]["above_T"]) == pytest.approx(L["S-Roof"]["T"], abs=1) and "from S-Roof above" in v["S-Floor"]["v_source"]
    assert v["S-Roof"]["v_source"].startswith("sheet W1, level Roof, walls from 15 to 20 ft")
    for m in out["members"]:
        assert calc.results(m["kind"], m["values"], proj)["state"] == "done", m["values"]["mark"]


def _box():
    proj = dict(COMBOS, name="t", number="t", date="2026-11-23", model=dict(levels=[dict(name="Foundation", elev="0"), dict(name="Floor", elev="10"), dict(name="Roof", elev="20")],
                                                                          grids_x=[], grids_y=[]))
    W = dict(kind="wind_mwfrs", values=dict(mark="W1", V="115", V_source="t", exposure="C", exposure_basis="t", enclosure="enclosed", enclosure_basis="t", across="30", along="40",
             roof="gable or flat", eave="20", h="20", theta="0", Kzt="1.0", Kzt_source="t"))
    E = dict(kind="seismic_elf", values=dict(mark="EQ1", SDS="1.0", SD1="0.6", S1="0.6", TL="8", ground_source="t", risk="II", system="Bearing wall: light-frame (wood) walls sheathed with wood structural panels",
             Ie="1.0", Ie_source="t", structure="all other structural systems", hn="20", rho="1.3", rho_source="t", levels=[dict(name="Roof", w="40", h="20"), dict(name="Floor", w="60", h="10")]))
    ms = [W, E]
    for lv in ("Roof", "Floor"):
        ms += [_wall(f"S-{lv}", "12, 12", at_level=lv, at_x1="0", at_y1="0", at_x2="40", at_y2="0"), _wall(f"N-{lv}", "12, 12", at_level=lv, at_x1="0", at_y1="30", at_x2="40", at_y2="30"),
               _wall(f"W-{lv}", "10, 10", at_level=lv, at_x1="0", at_y1="0", at_x2="0", at_y2="30"), _wall(f"E-{lv}", "10, 10", at_level=lv, at_x1="40", at_y1="0", at_x2="40", at_y2="30")]
    return proj, ms, E


def test_seismic_to_wall_lines_and_governing():
    proj, ms, E = _box()
    rows = {r["name"]: r["F"] * 1000 for r in calc.build("seismic_elf", E["values"], proj)[0].seismic["rows"]}
    out = calc.lateral_wind(proj, ms, load="seismic")
    assert out["problems"] == [], out["problems"]
    L = {l["wall"]: l for l in out["lines"]}
    assert L["S-Roof"]["V"] == pytest.approx(0.7 * 1.3 * rows["Roof"] / 2, rel=1e-6) and L["W-Roof"]["V"] == pytest.approx(L["S-Roof"]["V"])
    assert L["S-Floor"]["V"] == pytest.approx(0.7 * 1.3 * (rows["Roof"] + rows["Floor"]) / 2, rel=1e-6)
    v = {m["values"]["mark"]: m["values"] for m in out["members"]}
    assert v["S-Floor"]["load"] == "seismic" and "story force at Floor" in v["S-Floor"]["v_source"] and "x 1.3 x 0.7" in v["S-Floor"]["v_source"]
    gov = calc.lateral_governing(proj, ms)
    w = {l["wall"]: l["V"] for l in calc.lateral_wind(proj, ms)["lines"]}
    g = {m["values"]["mark"]: m["values"] for m in gov["members"] if m["kind"] == "shear_wall"}
    for mark, val in g.items():
        assert val["load"] == ("seismic" if 1.4 * L[mark]["V"] > w[mark] else "wind"), mark
    assert sum(1 for l in gov["lines"] if l["governs"]) == 8 and len(gov["lines"]) == 16
    bad = dict(proj, model=dict(proj["model"], levels=[dict(name="Foundation", elev="0"), dict(name="Second", elev="10"), dict(name="Roof", elev="20")]))
    assert any("names must match" in p for p in calc.lateral_wind(bad, ms, load="seismic")["problems"])


def _bay():
    """One 20 x 16 ft bay: four HSS columns, girders on grids A and B, three infill beams between them at 4 ft, on footings."""
    ms = [_beam("G1", "W16X31", 16, 0.05, 0.0, at_level="Floor", at_x1="A", at_y1="1", at_x2="A", at_y2="2"),
          _beam("G2", "W16X31", 16, 0.05, 0.0, at_level="Floor", at_x1="B", at_y1="1", at_x2="B", at_y2="2")]
    for i, y in enumerate((4, 8, 12), 1):
        ms.append(_beam(f"B{i}", "W12X26", 20, 0.3, 0.5, at_level="Floor", at_x1="A", at_y1=str(y), at_x2="B", at_y2=str(y)))
    for name, (x, y) in dict(C1=("A", "1"), C2=("A", "2"), C3=("B", "1"), C4=("B", "2")).items():
        ms.append(_col(name, at_level="Floor", at_base="Foundation", at_x1=x, at_y1=y))
    return ms


def test_space_frame_agrees_with_the_takedown():
    linked = calc.model_links(PROJ, _bay())
    assert len(linked["problems"]) == 4 and all("base: nothing in the model is under it" in p for p in linked["problems"])   # no footings in this test
    assert linked["made"] == 6 + 4                                                         # six infill beam ends on the girders, four girder ends on columns
    fr = calc.model_frame(PROJ, linked["members"])
    assert fr["problems"] == [] and fr["notes"] == [] and fr["cases"] == ["D", "L"] and len(fr["columns"]) == 4
    for col in fr["columns"]:
        for c, (frame, takedown) in col["cases"].items():
            assert frame == pytest.approx(takedown, rel=2e-3), (col["mark"], c)             # statically determinate framing: the two methods agree
        assert col["cases"]["L"][1] == pytest.approx(0.5 * 20 * 3 / 4 * 1000) and col["cases"]["D"][1] == pytest.approx((0.3 * 20 * 3 / 4 + 0.05 * 8) * 1000)


def test_space_frame_notes_and_problems():
    ms = _building()                                                                       # one column only: the other girder ends bear on supports
    linked = calc.model_links(PROJ, ms)
    fr = calc.model_frame(PROJ, linked["members"])
    assert fr["problems"] == [] and any("bearing on a support" in n for n in fr["notes"]) and len(fr["supports"]) == 3
    c1 = fr["columns"][0]["cases"]
    assert c1["L"][0] == pytest.approx(c1["L"][1], rel=2e-3) and c1["D"][0] == pytest.approx(c1["D"][1], rel=2e-3)
    assert "needs at least one" in calc.model_frame(PROJ, [m for m in ms if m["kind"] != "hss_column"])["problems"][0]
