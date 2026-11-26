"""Wood beams and posts in the 3D frame (gravity and sway runs): stiffness from the grade's E and the gross section, loads in lb converted,
rows of joists left out (their loads come through the load path). Checked by statics, against a hand beam formula and against the takedown."""
import json
import os

import pytest

from strukit.gui import calc
from strukit import wood

PROJ = dict(name="T", method="ASD", combos_asd=[dict(expr="D + L", source="t")], combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")],
            model=dict(levels=[dict(name="Foundation", elev="0"), dict(name="Main", elev="9")], grids_x=[], grids_y=[]))
POST = dict(species="DOUGLAS FIR-LARCH", grade="No. 2", size="6x6", height="9", lu1="", lu2="", Ke1="1", Ke2="1", k_source="t", service="dry service",
            incised="no", unit_weight="", loads=[], at_level="Main", at_base="Foundation")
BEAM = dict(species="DOUGLAS FIR-LARCH", grade="No. 2", size="4x10", plies="1", span="12", bracing="supported throughout", bearing="3", repetitive="no",
            service="dry service", incised="no", unit_weight="", defl=[])


def test_wood_beam_on_wood_posts_statics_and_stiffness():
    mem = [dict(kind="wood_post", values=dict(POST, mark="P1", at_x1="0", at_y1="0")),
           dict(kind="wood_post", values=dict(POST, mark="P2", at_x1="12", at_y1="0")),
           dict(kind="wood_beam", values=dict(BEAM, mark="B1", at_level="Main", at_x1="0", at_y1="0", at_x2="12", at_y2="0",
                                              loads=[dict(case="D", kind="point", mag="1000", mag2="", x1="3", x2="", label=""),
                                                     dict(case="L", kind="uniform", mag="200", mag2="", x1="", x2="", label="")]))]
    r = calc.model_frame(PROJ, mem)
    assert r["problems"] == []
    by = {c["mark"]: c["cases"] for c in r["columns"]}
    assert by["P1"]["D"][0] == pytest.approx(750, abs=1) and by["P2"]["D"][0] == pytest.approx(250, abs=1)     # 1000 lb at a quarter point
    assert by["P1"]["L"][0] == pytest.approx(1200, abs=1) and by["P2"]["L"][0] == pytest.approx(1200, abs=1)
    sec = calc._frame_section("wood_beam", mem[2]["values"])
    E = wood.values("DOUGLAS FIR-LARCH", "No. 2", "4x10")[0]["E"]
    assert sec["E"] == pytest.approx(E / 1000) and sec["Ix"] == pytest.approx(3.5 * 9.25 ** 3 / 12) and sec["G"] == pytest.approx(sec["E"] / 16)
    # the frame deflection at the 3 ft joint under the live load: w x (L^3 - 2 L x^2 + x^3) / 24 E I of the beam plus the shortening
    # P h / A E of the two posts (each 1,200 lb, 6x6: 5.5 x 5.5 in., E of the post grade)
    B = calc._model_frame_build(PROJ, mem, sway=False)
    res = B["fr"].solve({}, [(nm, "global", (0, 0, -w)) for nm, c, w in B["beam_loads"] if c == "L"])
    nd = next(n for n, (x, y, z) in B["fr"].nodes.items() if abs(x - 36.0) < 1e-6 and abs(z - 108.0) < 1e-6)
    w, L, x = 200 / 12000, 144.0, 36.0
    ps = calc._frame_section("wood_post", mem[0]["values"])
    short = 1.2 * 108.0 / (ps["A"] * ps["E"])
    assert -res.disp[nd][2] == pytest.approx(w * x * (L ** 3 - 2 * L * x ** 2 + x ** 3) / (24 * sec["E"] * sec["Ix"]) + short, rel=0.002)

def test_2026_011_wood_frame_agrees_with_takedown():
    """2026-011 model (test material): the LVL floor beams, built-up posts and pipe columns as one frame; each column's base load by case
    within 5 percent of the takedown (continuity of the three-span beam moves a little load between supports)."""
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_model.strukit")))
    lk = calc.model_links(d["project"], d["members"])
    r = calc.model_frame(d["project"], lk["members"])
    assert r["problems"] == [] and {c["mark"] for c in r["columns"]} == {"Column A", "Column B", "Post under Beam B", "Pipe Column 1", "Pipe Column 2"}
    for c in r["columns"]:
        for case, (fr_, td) in c["cases"].items():
            if td > 100:
                assert fr_ == pytest.approx(td, rel=0.05), (c["mark"], case)
    assert any("Rows of joists" in n for n in r["notes"]) and any("Wood members are in the frame" in n for n in r["notes"])
