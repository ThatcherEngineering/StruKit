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
    assert len(out["columns"]) == 16 and len(out["beams"]) == 8 and out["runs"] == 4 + 3 * 8
    assert out["problems"] == []
    col = {c["mark"]: c for c in out["columns"]}
    bm = {b["mark"]: b for b in out["beams"]}
    # gravity on an interior bent: (1.2 x 6.1 + 1.6 x 36.12 + 0.5 x 28.18) psf x 20 ft x 21.75 ft, plus member weight, on two columns
    # (Case A downward pressures at this roof angle: +31.88 psf on the windward half, +7.97 psf on the leeward half)
    w = (1.2 * 6.1 + 1.6 * 36.12 + 0.5 * (31.883 + 7.971) / 2) * 20 * 21.75 / 1000
    assert col["C4A"]["P"] + col["C4B"]["P"] == pytest.approx(w + 1.2 * (35.3 * 21.75 + 2 * 45.8 * 11.77) / 1000, rel=0.04)
    assert col["C4A"]["ratio"] == pytest.approx(0.29, abs=0.04) and bm["R4"]["ratio"] == pytest.approx(0.32, abs=0.05)      # the sealed report's portal checks
    assert all(c["ratio"] < 1 for c in col.values()) and all(b["ratio"] < 1 for b in bm.values())


def test_west_carport_wind_cases_balance_with_the_wind_sheet():
    """Equilibrium audit: in 0.9D + 1.0W the base reactions equal 0.9 x dead load less the open-roof sheet's total uplift, and the horizontal
    reaction equals the sheet's horizontal total plus the notional load."""
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    ws = calc.build("wind_free_roof", ms[0]["values"], proj)[0].free_roof
    out = calc.model_frame_sway(proj, ms)
    from strukit import shapes
    dead = (6.1 * 21.75 * 131 + 8 * shapes.hss("HSS10X6X3/8")["W"] * 21.75 + 16 * shapes.hss("HSS8X8X1/2")["W"] * 11.77) / 1000
    for row in ws["totals"]["rows"]:
        side = "from the high side" if row["gamma"] == 0 else "from the low side"
        a = next(a for a in out["audit"] if a["run"] == f"0.9D + 1.0W, wind across the roof {side}, Case {row['case']}")
        assert a["Rz"] == pytest.approx(0.9 * dead + row["V"] / 1000, abs=0.15)
        assert abs(a["Ry"]) == pytest.approx(abs(row["H"]) / 1000 + 0.003 * 0.9 * dead, abs=0.02)      # roof push plus the notional load (0.003 of the gravity load), the same way
    assert max(c["T"] for c in out["columns"]) > 1.0 and "Case B" in max(out["columns"], key=lambda c: c["T"])["T_combo"]
