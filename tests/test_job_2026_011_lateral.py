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
    assert flagged == ["Line 1, main level"]          # one 2'-8" pier between the awning windows


def test_holddown_forces():
    T = {}
    for m in D["members"]:
        if m["kind"] == "shear_wall":
            s, _, _ = calc.build("shear_wall", m["values"], D["project"])
            w = getattr(s, "shearwall", None) or s.wall
            T[m["values"]["mark"]] = max((g["T"] if isinstance(g, dict) else g.T) for g in w.segments)
    assert abs(T["Line 1, lower level"] - 2140) < 5 and abs(T["Line B, lower level"] - 1636) < 5 and abs(T["Line A, main level"] - 725) < 5
