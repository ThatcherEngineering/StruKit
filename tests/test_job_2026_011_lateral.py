"""Job 2026-011 lateral run (wind governs): typed from sheets S0-S3 and the architect's plans."""
import json, os
from strukit.gui import calc

D = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011_lateral.strukit")))


def test_lateral_lines():
    got = {}
    for m in D["members"]:
        r = calc.results(m["kind"], m["values"], D["project"])
        assert r["state"] == "done", (m["values"]["mark"], r["messages"])
        got[m["values"]["mark"]] = r["status"]
    assert len(got) == 12
    flagged = [k for k, v in got.items() if v != "OK"]
    assert flagged == []          # Line 1 main level by force transfer around the middle awning window


def test_holddown_forces():
    """Lower-level chord tension includes the wall above (stacked walls)."""
    T, own = {}, {}
    for m in D["members"]:
        s, _, _ = calc.build(m["kind"], m["values"], D["project"])
        if m["kind"] == "shear_wall":
            T[m["values"]["mark"]] = max(g.T for g in s.wall.segments)
            own[m["values"]["mark"]] = max(t for t, _ in s.wall.own)
        elif m["kind"] == "ftao_wall":
            T[m["values"]["mark"]] = s.wall_T
    assert abs(T["Line 1, main level"] - 1523 * 9 / 7.84) < 2          # V h / L
    assert abs(T["Line A, lower level"] - (1205.5 + 725)) < 5 and abs(T["Line B, lower level"] - (1636 + 784)) < 5
    assert abs(T["Line 1, lower level"] - (2139.6 + 1748)) < 5 and T["Line 1, lower level"] < 4410


def test_stack_needs_source():
    import pytest
    from strukit import ws_more
    kw = dict(mark="SW", panel="Sheathing, 7/16 in, 8d common", spacing=6, panel_type="OSB", G=0.5, G_source="x", h=9, lengths=[8.0], V=1000, load="wind",
              method="ASD", v_source="x")
    a = ws_more.shear_wall_sheet(**kw)
    b = ws_more.shear_wall_sheet(**kw, above_T=500, above_source="SW above")
    assert abs(a.wall.segments[0].T - 1125) < 1e-6 and abs(b.wall.segments[0].T - 1625) < 1e-6 and abs(b.wall.segments[0].C - 1625) < 1e-6
    assert b.wall.capacity == a.wall.capacity
    with pytest.raises(Exception):
        ws_more.shear_wall_sheet(**kw, above_T=500)
