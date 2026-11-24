"""A project like job 2026-030, Wayfarer Vans West Carport (test material only; built by jobs/2026_030_build_west.py): eight two-column bents
with rigid knees and fixed bases run as one 3D frame free to sway. Reference numbers are the sealed report's (his metal-building workbook):
portal column H1-1 0.29, portal rafter H1-1 0.30 to 0.35."""
import json, os
import pytest
from strukit.gui import calc

HERE = os.path.dirname(__file__)


def test_west_carport_as_a_3d_frame():
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    out = calc.model_frame_sway(proj, ms)
    assert len(out["columns"]) == 16 and len(out["beams"]) == 8 and out["runs"] == 16
    assert [p for p in out["problems"] if "Main System sheet" not in p] == []
    col = {c["mark"]: c for c in out["columns"]}
    bm = {b["mark"]: b for b in out["beams"]}
    # gravity on an interior bent: (1.2 x 6.1 + 1.6 x 36.12 + 0.5 x 28.18) psf x 20 ft x 21.75 ft, plus member weight, on two columns
    w = (1.2 * 6.1 + 1.6 * 36.12 + 0.5 * 28.18) * 20 * 21.75 / 1000
    assert col["C4A"]["P"] + col["C4B"]["P"] == pytest.approx(w + 1.2 * (35.3 * 21.75 + 2 * 45.8 * 11.77) / 1000, rel=0.03)
    assert col["C4A"]["ratio"] == pytest.approx(0.29, abs=0.04) and bm["R4"]["ratio"] == pytest.approx(0.33, abs=0.05)      # the sealed report's portal checks
    assert all(c["ratio"] < 1 for c in col.values()) and all(b["ratio"] < 1 for b in bm.values())
