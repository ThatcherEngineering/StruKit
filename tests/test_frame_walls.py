"""Shear walls as members of the 3D frame (sway runs): each placed wall is an X-braced panel whose lateral stiffness equals the design
shear over the SDPWS Eq. 4.3-1 deflection of its own sheet; a stiff diaphragm ties each level. Checked against the wall sheets and statics."""
import pytest

from strukit.gui import calc

PROJ = dict(name="T", method="ASD", combos_asd=[dict(expr="D + 0.6W", source="t")], combos_lrfd=[dict(expr="1.2D + 1.0W", source="t")],
            model=dict(levels=[dict(name="Foundation", elev="0"), dict(name="Roof", elev="9")], grids_x=[], grids_y=[]))
SW = dict(G="0.5", G_source="t", panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", blocking="blocked", h="9", load="wind",
          holddown="no", V="2000", v_source="t", chord_A="16.5", chord_E="1600000", slip="0.1")


def _box(L1="20", L2="20"):
    return [dict(kind="shear_wall", values=dict(SW, mark="S", lengths=L1, at_level="Roof", at_x1="0", at_y1="0", at_x2=L1, at_y2="0")),
            dict(kind="shear_wall", values=dict(SW, mark="N", lengths=L2, at_level="Roof", at_x1="0", at_y1="20", at_x2=L2, at_y2="20")),
            dict(kind="shear_wall", values=dict(SW, mark="W", lengths="20", at_level="Roof", at_x1="0", at_y1="0", at_x2="0", at_y2="20")),
            dict(kind="shear_wall", values=dict(SW, mark="E", lengths="20", at_level="Roof", at_x1="20", at_y1="0", at_x2="20", at_y2="20"))]


def test_wall_stiffness_is_its_sheet_v_over_delta():
    m = _box()[0]
    k, how = calc._wall_stiffness(PROJ, m)
    sheet, _, _ = calc.build("shear_wall", m["values"], PROJ)
    seg = sheet.wall.segments[0]
    assert k == pytest.approx(seg.V / seg.defl) and "Eq. 4.3-1" in how


def test_two_walls_share_by_stiffness_and_drift_is_p_over_k():
    """A 20 x 20 ft box; 2 kips along X at the roof. Walls S and N (in X) take it in proportion to their stiffness (stiff diaphragm) and the
    roof moves 2 / (kS + kN) in X; the walls in Y take nothing (load through the centre of stiffness when S and N are equal)."""
    mem = _box()
    B = calc._model_frame_build(PROJ, mem, sway=True)
    assert B["problems"] == [] and len(B["walls"]) == 4
    fr = B["fr"]
    tops = [nd for nd, (x, y, z) in fr.nodes.items() if abs(z - 108.0) < 1e-6]
    res = fr.solve({nd: (2.0 / len(tops), 0, 0, 0, 0, 0) for nd in tops}, [])
    kS = calc._wall_stiffness(PROJ, mem[0])[0] / 1000.0
    for nd in tops:
        assert res.disp[nd][0] == pytest.approx(2.0 / (2 * kS), rel=1e-3)
    base = {nd: r_ for nd, r_ in res.reactions.items() if abs(fr.nodes[nd][2]) < 1e-6}
    assert sum(r_[0] for r_ in base.values()) == pytest.approx(-2.0, abs=1e-6)
    # a longer, stiffer wall S (30 ft, so its own sheet is stiffer) takes the larger share; shares in proportion to the two stiffnesses
    mem2 = _box(L1="30")
    mem2[0]["values"]["at_x2"] = "30"
    B2 = calc._model_frame_build(PROJ, mem2, sway=True)
    fr2 = B2["fr"]
    k1, k2 = calc._wall_stiffness(PROJ, mem2[0])[0], calc._wall_stiffness(PROJ, mem2[1])[0]
    tops2 = [nd for nd, (x, y, z) in fr2.nodes.items() if abs(z - 108.0) < 1e-6]
    res2 = fr2.solve({nd: (2.0 / len(tops2), 0, 0, 0, 0, 0) for nd in tops2}, [])
    shear = lambda mk: sum(res2.reactions[nd][0] for nd in res2.reactions if abs(fr2.nodes[nd][2]) < 1e-6 and abs(fr2.nodes[nd][1] - (0 if mk == "S" else 240)) < 1e-6
                           and 0 < fr2.nodes[nd][0] / 12 <= (30 if mk == "S" else 20) + 1e-6)
    assert abs(shear("S")) > abs(shear("N"))


def test_force_transfer_wall_stiffness_from_its_piers():
    v = dict(G="0.5", G_source="t", mark="FT", panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", h="9", L1="4",
             Lo="4", L2="4", ho="4", sill="3", load="wind", V="2000", v_source="t", chord_A="16.5", chord_E="1600000", slip="0.1")
    k, how = calc._wall_stiffness(PROJ, dict(kind="ftao_wall", values=v))
    seg_v = dict(SW, mark="x", lengths="12")
    Ga = calc.build("shear_wall", seg_v, PROJ)[0].wall.Ga
    vv = 2000 / 8
    d = 8 * vv * 9 ** 3 / (1600000 * 16.5 * 4) + vv * 9 / (1000 * Ga) + 9 * 0.1 / 4
    assert k == pytest.approx(2 * vv * 4 / d, rel=1e-6) and "pier" in how
    v.pop("chord_A")
    assert "end post area" in calc._wall_stiffness(PROJ, dict(kind="ftao_wall", values=v))
