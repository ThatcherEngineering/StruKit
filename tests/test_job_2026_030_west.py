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
    assert len(out["columns"]) == 16 and len(out["beams"]) == 8 and out["runs"] == 4 + 3 * 10
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
    from strukit import wind
    cf = wind.other_cf("square", 11.77 / (8 / 12))
    assert cf == pytest.approx(1.4 + 0.6 * (11.77 / (8 / 12) - 7) / 18) and wind.other_cf("square", 0.5) == 1.3 and wind.other_cf("square", 40) == 2.0 and wind.other_cf("round_smooth", 7) == 0.6
    drag = ws["factor"] * (2 * 2.0 * 1.25 * 131 + 16 * cf * (8 / 12) * 11.77) / 1000      # both eave fascias and sixteen columns, Eq. 29.4-1, kips
    for row in ws["totals"]["rows"]:
        side = "from the high side" if row["gamma"] == 0 else "from the low side"
        a = next(a for a in out["audit"] if a["run"] == f"0.9D + 1.0W, wind across the roof {side}, Case {row['case']}")
        assert a["Rz"] == pytest.approx(0.9 * dead + row["V"] / 1000, abs=0.15)
        travel = -1 if row["gamma"] == 0 else 1                               # the low eave is at the smaller Y; gamma = 0 blows from the high side
        net = (1 if row["V"] > 0 else -1) * abs(row["H"]) / 1000 + travel * drag   # the roof is pushed toward the high side by downward pressure
        assert -a["Ry"] == pytest.approx(net + (1 if net > 0 else -1) * 0.003 * 0.9 * dead, abs=0.03)      # plus the notional load (0.003 of the gravity load), the same way
    assert max(c["T"] for c in out["columns"]) > 1.0 and "Case B" in max(out["columns"], key=lambda c: c["T"])["T_combo"]


def test_west_carport_package_has_the_summary_and_the_frame_sheet(tmp_path):
    import subprocess
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    fs = calc.frame_sheet(proj, ms)
    assert fs is not None and len(fs.rows) == 16 + 2 * 8 and fs.ok and len(fs.blocks) == 5 and fs.blocks[0]["picture"][0] == "frame3d"
    sm = calc.summary_sheet(proj, [("FR", "3D Frame Analysis", fs)])
    assert dict(sm.info)["Status"] == "ALL CHECKS OK" and dict(sm.info)["Checks"] == "32" and "D/C" in dict(sm.info)["Governing"]
    n, skipped = calc.package_pdf(proj, ms, str(tmp_path / "p.pdf"))
    assert n >= 12
    # a project with no building model prints no frame sheet, and still gets the summary
    assert calc.frame_sheet(dict(proj, model={}), ms) is None


def test_bent_building_fills_the_model_like_the_west_carport():
    proj = dict(name="t", number="t", date="2026-11-23", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6S", source="t")], combos_asd=[dict(expr="D + S", source="t")])
    spec = dict(n="8", spacing="10, 20, 20, 20, 20, 20, 20", end_start="0.5", end_end="0.5", col_spacing="18.5", cant_low="1", cant_high="2.25", height="11.77",
                col_shape="HSS8X8X1/2", col_Fy="46", raf_shape="HSS10X6X3/8", raf_Fy="46", base="fixed", D="6.1", S="36.12", Lr="")
    out = calc.bent_building(proj, [], spec)
    assert out["problems"] == [] and out["added"] == 24
    by = {m["values"]["mark"]: m for m in out["members"]}
    assert by["R1"]["values"]["loads"][0]["mag"] == "0.03355" and by["R4"]["values"]["loads"][1]["mag"] == "0.72240"       # 6.1 psf x 5.5 ft; 36.12 psf x 20 ft
    assert by["C8B"]["values"]["at_x1"] == "130" and by["C8B"]["values"]["at_y1"] == "18.5" and by["R8"]["values"]["at_y2"] == "20.75"
    assert [l["name"] for l in out["project"]["model"]["levels"]] == ["Base", "Roof"] and len(out["project"]["model"]["grids_x"]) == 8
    run = calc.model_frame_sway(out["project"], out["members"])
    assert run["problems"] == [] and len(run["columns"]) == 16 and all(c["ratio"] < 1 for c in run["columns"])
    # the same marks again are refused, a prefix lets a second building in; bad input is listed and nothing is added
    again = calc.bent_building(out["project"], out["members"], spec)
    assert again["added"] == 0 and "already in the project" in again["problems"][0]
    assert calc.bent_building(out["project"], out["members"], dict(spec, prefix="N"))["added"] == 24
    bad = calc.bent_building(proj, [], dict(spec, n="1", col_shape="HSS99X1", spacing="x"))
    assert bad["added"] == 0 and len(bad["problems"]) >= 2
    # W-shape columns are steel columns
    w = calc.bent_building(proj, [], dict(spec, col_shape="W8X31", col_Fy="50", raf_shape="W12X26", raf_Fy="50", spacing="20", n="3"))
    assert w["added"] == 9 and w["members"][0]["kind"] == "steel_column" and calc.model_frame_sway(w["project"], w["members"])["levels"]


def test_west_carport_minimum_wind_case():
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    ws = calc.build("wind_free_roof", ms[0]["values"], proj)[0].free_roof
    out = calc.model_frame_sway(proj, ms)
    from strukit import shapes
    dead = (6.1 * 21.75 * 131 + 8 * shapes.hss("HSS10X6X3/8")["W"] * 21.75 + 16 * shapes.hss("HSS8X8X1/2")["W"] * 11.77) / 1000
    a = next(a for a in out["audit"] if a["run"] == "0.9D + 1.0W, minimum wind across the roof in +Y (Sect. 27.1.5)")
    assert -a["Ry"] == pytest.approx(ws["totals"]["F_min"] / 1000 + 0.003 * 0.9 * dead, abs=0.02) and a["Rz"] == pytest.approx(0.9 * dead, abs=0.05)


def test_frame_column_base_forces_reach_the_base_plate_and_footing_screens():
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    col = next(m for m in ms if m["values"]["mark"] == "C4A")
    got = calc.reactions("hss_column", col["values"], proj, ms)
    assert got["bases"] == ["strong-axis moment", "weak-axis moment"] and got["messages"] == []
    lr = calc.model_frame_sway(proj, ms)
    c = next(c for c in lr["columns"] if c["mark"] == "C4A")
    st = [r for r in got["strength"] if r["base"] == "weak-axis moment"]
    sv = [r for r in got["service"] if r["base"] == "weak-axis moment"]
    assert 1 <= len(st) <= 4 and 1 <= len(sv) <= 4
    assert max(r["M"] for r in st) == pytest.approx(max(b["Mw"] for b in c["base"]) * 1000 / 12, rel=1e-6)          # the largest base moment of the LRFD run
    assert max(r["P"] for r in st) == pytest.approx(max(b["P"] for b in c["base"]) * 1000, rel=1e-6)
    assert min(r["P"] for r in st) == pytest.approx(min(b["P"] for b in c["base"]) * 1000, rel=1e-6)
    assert max(r["M"] for r in sv) < max(r["M"] for r in st) and all(r["wt_factor"] for r in st) and all(r["wt_factor"] is None for r in sv)
    # a column that is not placed still goes the old way
    assert "error" in calc.reactions("hss_column", dict(col["values"], at_x1=""), proj, ms) or calc.reactions("hss_column", dict(col["values"], at_x1=""), proj, ms).get("bases") is not None
