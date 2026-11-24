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
    assert flagged == ["Line 1, main level", "Line 1, lower level"]     # one 2 ft 8 in. pier between the awning windows, and the hold-down below it


def test_holddown_forces():
    """Lower-level chord tension includes the wall above (stacked walls)."""
    T, own = {}, {}
    for m in D["members"]:
        if m["kind"] == "shear_wall":
            s, _, _ = calc.build("shear_wall", m["values"], D["project"])
            T[m["values"]["mark"]] = max(g.T for g in s.wall.segments)
            own[m["values"]["mark"]] = max(t for t, _ in s.wall.own)
    assert abs(T["Line A, main level"] - 725) < 5 and abs(own["Line B, lower level"] - 1636) < 5
    assert abs(T["Line A, lower level"] - (1205.5 + 725)) < 5          # 3,650 x 9 / 27.25 + the wall above
    assert abs(T["Line B, lower level"] - (1636 + 784)) < 5
    assert abs(T["Line 1, lower level"] - (2139.6 + 5134)) < 5


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
