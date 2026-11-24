"""Job 2026-001 (Rusler Implements, Pueblo), the mezzanine: the 27 steel members StruKit can take from the job's StruCalc Pro working file
(2026-001-StruCalc.vtx; AISC 360-16 there, 360-22 here), brought across by strukit.strucalc.  The project file tests/data/job_2026_001_mezzanine.strukit
carries StruCalc's own results under "strucalc".  Shear, flexure, compression, interaction and deflection agree within 0.8 percent on every member except
the cantilever, where StruCalc takes the moment short of the support centre line and reports the back-span deflection."""
import json
import os

import pytest

from strukit.gui import calc

MAP = {"Shear Force Y": ("shear", 1000.0), "Moment Y": ("flexure", 1000.0), "Compressive Force": ("Axial compression", 1000.0), "Bending-Compression": ("Compression and bending", 1.0)}


def test_mezzanine_against_the_strucalc_file():
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_001_mezzanine.strukit")))
    assert len(d["members"]) == 27
    n = 0
    for m in d["members"]:
        mk = m["values"]["mark"]
        r = calc.results(m["kind"], m["values"], d["project"])
        assert r["state"] == "done", (mk, r.get("messages"))
        rows = {x["check"]: x for x in r["rows"]}
        theirs = d["strucalc"][mk]
        if mk == "FloorBeamY.3":                                   # a trial size StruCalc also marks inadequate (263.7 kip-ft against 195.6)
            assert r["status"] == "FLAG" and rows["flexure"]["demand"] > rows["flexure"]["capacity"]
        elif mk not in ("FloorBeamY.5",):                          # Y.5 fails in StruCalc on a weak-axis moment StruKit's beam screen does not take
            assert r["status"] == "OK", mk
        for t in theirs:
            if mk == "Cantilever" and t["name"] in ("Moment Y", "Deflection Y"):
                continue
            if t["name"] in MAP and MAP[t["name"]][0] in rows:
                chk, div = MAP[t["name"]]
                assert rows[chk]["demand"] == pytest.approx(t["demand"] / div, rel=0.008), (mk, chk)
                assert rows[chk]["capacity"] == pytest.approx(t["strength"] / div, rel=0.008), (mk, chk)
                n += 1
            elif t["name"] == "Deflection Y" and m["kind"] == "steel_beam":
                key = "deflection, live" if t["combo"] == "L" else "deflection, total"
                assert rows[key]["demand"] == pytest.approx(t["demand"], rel=0.008, abs=0.0002), (mk, key)
                n += 1
    assert n == 78
