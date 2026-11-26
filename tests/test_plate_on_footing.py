"""A base plate linked to the footing it sits on (Zach 2026-11-25 21:24: "The anchor rod calcs need to be able to link to a foundation
system or be independent"). Linked, the footing's plan, thickness and f'c fill the plate's concrete; the plate's size fills the footing's
base plate boxes. Unlinked, nothing changes."""
import pytest

from strukit.gui import calc
from strukit import loadcombos as lc

P = dict(name="t", job="t", date="Nov 25, 2026", method="LRFD", combos_asd=[dict(c) for c in lc.ASD], combos_lrfd=[dict(c) for c in lc.LRFD])
FOOT = dict(kind="footing_iso", values=dict(mark="F1", B="5", L="6", h="18", fc="3500", fy="60000", conc_pcf="150", col_x="10", col_y="10",
                                             supported="steel", bar="5", n_x="7", n_y="7", cover="3", bottom="x", P_service="40000",
                                             service_combo="D + L", Pu="55000", strength_combo="1.2D + 1.6L", q_allow="2500",
                                             soil_source="soils report"))
UP = dict(kind="base_plate_uplift", values=dict(mark="BPU1", shape="W10X45", col_Fy="50", N="14", B="12", t="1", Fy="50", rod_d="0.875",
                                                 rod_Fu="58", rod_source="ASTM F1554 Grade 36", gauge="4", pitch="4", weld="0.1875", FEXX="70",
                                                 anc_grade="F1554 Gr. 36", anc_hef="12", anc_cracked="cracked", anc_supp="no", anc_sdc="A or B",
                                                 cases=[dict(name="0.9D + 1.0W", T="40")]))


def test_uplift_plate_takes_the_footing():
    up = dict(UP, values=dict(UP["values"], on_footing="F1", on_footing_N="y"))
    linked = {m["values"]["mark"]: m["values"] for m in calc.link_foundations([FOOT, up])}
    v = linked["BPU1"]
    assert (v["anc_fc"], v["anc_h"], v["anc_supN"], v["anc_supB"]) == ("3500", "18", "72", "60")    # N along L = 6 ft
    f = linked["F1"]
    assert (f["plate_x"], f["plate_y"], f["supported"]) == ("12", "14", "steel")
    sh, _, _ = calc.build("base_plate_uplift", v, P)
    assert any(a.startswith("Concrete under the plate: footing F1, 5 ft x 6 ft, 18 in. thick, f'c 3500 psi") for a in sh.assumptions)
    # the window path: results with the project's members shows what the link filled
    r = calc.results("base_plate_uplift", up["values"], P, [FOOT, up])
    assert r["state"] == "done" and r["linked"]["anc_supN"] == "72"
    # a bigger footing gives more breakout than a 5 x 6 ft one with the rods near the middle? Same here (edges > 1.5 hef); a small pier gives less
    small = dict(FOOT, values=dict(FOOT["values"], B="2", L="2"))
    s2, _, _ = calc.build("base_plate_uplift", calc.link_foundations([small, up])[1]["values"], P)
    br = lambda s: next(x for x in s.rows if x.check == "ACI breakout, tension").capacity
    assert br(s2) < br(sh)


def test_independent_plate_unchanged_and_link_problems():
    assert calc.link_foundations([FOOT, UP])[1] is UP
    assert calc.results("base_plate_uplift", UP["values"], P, [FOOT, UP]).get("linked") is None
    gone = dict(UP, values=dict(UP["values"], on_footing="F9"))
    assert "not in the project" in calc.results("base_plate_uplift", gone["values"], P, [FOOT, gone])["messages"][0]
    no_dir = dict(UP, values=dict(UP["values"], on_footing="F1"))
    assert "not square" in calc.results("base_plate_uplift", no_dir["values"], P, [FOOT, no_dir])["messages"][0]
    sq = dict(FOOT, values=dict(FOOT["values"], L="5"))
    assert calc.results("base_plate_uplift", no_dir["values"], P, [sq, no_dir])["state"] == "done"      # square: no direction needed
    two = dict(UP, values=dict(no_dir["values"], mark="BPU2"))
    r = calc.results("footing_iso", sq["values"], P, [sq, no_dir, two])
    assert r["state"] == "incomplete" and "one plate per isolated footing" in r["messages"][0]


def test_biaxial_area_ratio_from_the_footing():
    bx = dict(kind="base_plate_biaxial", values=dict(mark="BPX1", shape="W8X48", N="14", B="14", t="1.75", Fy="50", fc="3000", area_ratio="1",
                                                     rod_d="0.75", rod_grade="F1554 Gr. 36", rod_edge="1.5", rod_side="1.5", on_footing="F1",
                                                     on_footing_N="x", cases=[dict(name="1.2D + 1.6L", P="60", Mx="10", My="5")]))
    v = calc.link_foundations([FOOT, bx])[1]["values"]
    assert v["fc"] == "3500" and float(v["area_ratio"]) == pytest.approx(min(4.0, min(60 / 14, 72 / 14) ** 2))


def test_moment_plate_on_footing_with_moment():
    fm = dict(kind="footing_moment", values=dict(mark="FM1", B="8", L="5", h="24", fc="4000"))
    bp = dict(kind="base_plate_moment", values=dict(mark="BPM1", N="20", B="12", fc="3000", full="yes", on_footing="FM1"))
    v = calc.link_foundations([fm, bp])[1]["values"]
    assert (v["fc"], v["full"], v["sup_N"], v["sup_B"], v["anc_h"]) == ("4000", "no", "96", "60", "24")   # moment along B both screens
    f = calc.link_foundations([fm, bp])[0]["values"]
    assert (f["plate_x"], f["plate_y"]) == ("20", "12")
