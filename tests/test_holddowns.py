"""Simpson hold-down table: values as printed in catalog C-C-2026 (pp. 59, 61, 63, 67)."""
import pytest
from strukit import holddowns as H, ws_more


def test_table_values():
    assert H.check("HDUE5-SDS3", 4000, 0.50, "wind", "ASD")["capacity"] == 5375
    assert H.check("HDUE5-SDS3", 4000, 0.42, "wind", "ASD")["capacity"] == 4700          # SPF/HF
    assert H.check("HDUE5-SDS3", 4000, 0.50, "seismic", "LRFD")["capacity"] == pytest.approx(5375 * 1.4)
    k = dict(stem="8", position="end wall", cracked=True)
    assert H.check("STHD14", 1, 0.5, "wind", "ASD", **k)["capacity"] == 4410
    assert H.check("STHD14", 1, 0.5, "seismic", "ASD", sdc_high=True, **k)["capacity"] == 3500
    assert H.check("STHD10", 1, 0.5, "wind", "ASD", stem="6", position="corner", cracked=False)["capacity"] == 3535
    assert H.check("STHD10", 1, 0.5, "wind", "LRFD", stem="6", position="corner", cracked=False)["capacity"] == pytest.approx(3535 * 1.67)
    assert H.check("LSTHD8", 1, 0.5, "seismic", "ASD", stem="8", position="midwall", cracked=False, sdc_high=True)["capacity"] == 2615
    for (m, st), (_, _, lo, hi) in H.STRAP.items():                     # table pattern: SDC C-F never above wind; end wall never above midwall
        assert all(h <= l for h, l in zip(hi, lo)) and lo[2] <= lo[0] and lo[5] <= lo[3] and all(c <= u for u, c in zip(lo[:3], lo[3:]))
    with pytest.raises(H.HoldDownError):
        H.check("STHD14", 1, 0.5, "wind", "ASD")                        # stem wall, position, concrete not given


def test_pick():
    assert H.check("smallest HDUE or DTT that works", 4000, 0.5, "wind", "ASD")["model"] == "HDUE5-SDS3"
    assert H.check("smallest HDUE or DTT that works", 1500, 0.5, "wind", "ASD")["model"] == "DTT2Z"
    assert H.check("smallest LSTHD or STHD that works", 3000, 0.5, "wind", "ASD", stem="8", position="corner", cracked=True)["model"] == "STHD10"
    assert H.check("smallest HDUE or DTT that works", 99999, 0.5, "wind", "ASD")["model"] == "HDUE17-SDS4.5"


def test_on_the_shear_wall_sheet():
    kw = dict(mark="SW", panel="Sheathing, 7/16 in, 8d common", spacing=6, panel_type="OSB", G=0.5, G_source="x", h=9, lengths=[8.0], V=2000, load="wind",
              method="ASD", v_source="x")
    s = ws_more.shear_wall_sheet(**kw, holddown=dict(model="smallest HDUE or DTT that works"))
    r = [x for x in s.rows if x.check == "hold-down tension"][0]
    assert abs(r.demand - 2250) < 1e-6 and r.capacity == 3790 and s.wall.holddown["model"] == "HDUE3-SDS3"


def test_on_the_perforated_wall_sheet():
    """The perforated wall checks the chosen hold-down for the tension at each end of the wall (SDPWS 4.3.6.4.2.1, T = V h / (Co sum Li))."""
    from strukit.gui import calc
    kw = dict(mark="PW", panel="Sheathing, 7/16 in, 8d common", spacing=6, panel_type="OSB", G=0.5, G_source="x", h=8, length=20.0,
              openings=[dict(x=6.0, w=4.0, h=4.0, sill=3.0)], V=2000, load="wind", method="ASD", v_source="x")
    s = ws_more.perforated_wall_sheet(**kw, holddown=dict(model="smallest HDUE or DTT that works"))
    r = [x for x in s.rows if x.check == "hold-down tension"][0]
    assert r.demand == pytest.approx(s.wall.T) and r.capacity >= r.demand
    assert any(k == "Hold-Down" for k, _ in s.info) and not any(t.startswith("hold-downs and their connections") for t in s.not_checked)
    v = dict(mark="PW", panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", G="0.5", G_source="x", h="8", length="20",
             load="wind", V="2000", v_source="x", hd_model="smallest HDUE or DTT that works", openings=[dict(x="6", w="4", h="4", sill="3")])
    sc = calc.build("perforated_wall", v, dict(job="t", name="t", method="ASD"))[0]
    assert any(x.check == "hold-down tension" for x in sc.rows)
