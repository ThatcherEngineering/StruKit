"""A project like job 2026-030, Wayfarer Vans West Carport (test material only; built by jobs/2026_030_build_west.py): eight two-column bents
with rigid knees and fixed bases run as one 3D frame free to sway. The job's sealed report (his metal-building workbook) is NOT a reference: Zach, 2026-11-24 02:10, "don't use those wayfarer calcs as gospel...
it was done before I knew any better". The checks here are statics and equilibrium; the two ratios are pinned to StruKit's own values only so a
change in the frame shows up."""
import json, math, os
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
    assert col["C4A"]["ratio"] == pytest.approx(0.28, abs=0.02) and bm["R4"]["ratio"] == pytest.approx(0.35, abs=0.02)      # StruKit's own values (regression pin, not a reference)
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


def test_sloped_carport_from_the_quick_start():
    """The West carport at its real slope (1 in 12, 11.0 ft at the low column line): column heights follow the rafter, the 3D view shows the
    slope, and the frame still balances with the wind sheet."""
    from strukit import shapes
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj = dict(d["project"], model={})
    spec = dict(n="8", spacing="10, 20, 20, 20, 20, 20, 20", end_start="0.5", end_end="0.5", col_spacing="18.5", cant_low="1", cant_high="2.25", height="11", slope="1",
                col_shape="HSS8X8X1/2", col_Fy="46", raf_shape="HSS10X6X3/8", raf_Fy="46", base="fixed", D="6.1", S="36.12", Lr="")
    out = calc.bent_building(proj, [d["members"][0]], spec)
    assert out["problems"] == [] and "rising 1 in 12 from 11 ft at column line A to 12.542 ft at line B" in out["notes"][0]
    ms = out["members"]
    r4 = next(m for m in ms if m["values"]["mark"] == "R4")["values"]
    assert float(r4["at_dz1"]) == pytest.approx(-1 / 12, abs=1e-4) and float(r4["at_dz2"]) == pytest.approx(20.75 / 12, abs=1e-4)
    view = {i["mark"]: i for i in calc.model_view(out["project"], ms)["items"]}
    assert view["C4A"]["b"][2] == pytest.approx(11.0, abs=1e-3) and view["C4B"]["b"][2] == pytest.approx(11 + 18.5 / 12, abs=1e-3)
    assert view["R4"]["a"][2] == pytest.approx(11 - 1 / 12, abs=1e-3) and view["R4"]["b"][2] == pytest.approx(11 + 20.75 / 12, abs=1e-3)
    run = calc.model_frame_sway(out["project"], ms)
    assert run["problems"] == [] and any("modelled at their slope" in n for n in run["notes"])
    ws = calc.build("wind_free_roof", ms[0]["values"], proj)[0].free_roof
    Lr = 21.75 / math.cos(math.atan(1 / 12))
    dead = (6.1 * Lr * 131 + 8 * shapes.hss("HSS10X6X3/8")["W"] * Lr + 8 * shapes.hss("HSS8X8X1/2")["W"] * (11 + 11 + 18.5 / 12)) / 1000
    row = next(r for r in ws["totals"]["rows"] if r["gamma"] == 180 and r["case"] == "B")
    a = next(a for a in run["audit"] if a["run"] == "0.9D + 1.0W, wind across the roof from the low side, Case B")
    assert a["Rz"] == pytest.approx(0.9 * dead + row["V"] / 1000, abs=0.2)             # vertical: dead load less the sheet's uplift
    cols = {c["mark"]: c for c in run["columns"]}
    assert cols["C4A"]["ratio"] == pytest.approx(0.28, abs=0.05) and all(c["ratio"] < 1 for c in cols.values())


def test_wind_drift_limit_on_the_frame():
    d = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj, ms = d["project"], d["members"]
    base = calc.model_frame_sway(proj, ms)
    assert base["drift_checks"] == []
    proj2 = dict(proj, model=dict(proj["model"], drift_ratio="240", drift_factor="0.6", drift_source="Thatcher Engineering standard"))
    out = calc.model_frame_sway(proj2, ms)
    e = next(e for e in out["elastic"] if e["load"] == "wind" and e["dir"] == "Y")
    c = next(c for c in out["drift_checks"] if c["dir"] == "Y")
    assert c["drift"] == pytest.approx(0.6 * e["story"]) and c["limit"] == pytest.approx(11.77 * 12 / 240) and c["drift"] < c["limit"]
    fs = calc.frame_sheet(proj2, ms)
    r = next(r for r in fs.rows if r.check.startswith("wind drift") and "Y direction" in r.check)
    assert r.status == "OK" and r.source == "Thatcher Engineering standard" and "story height / 240" in r.note
    # the limit without its source is not used, and says so
    no = calc.model_frame_sway(dict(proj, model=dict(proj["model"], drift_ratio="240", drift_factor="0.6")), ms)
    assert no["drift_checks"] == [] and "needs its source" in " ".join(no["problems"])


def test_pitched_bents_from_the_quick_start():
    """Three pitched bents (ridge midway, 3 in 12): the two rafter halves are rigid at the ridge with no support there; the frame balances with
    the pitched open-roof wind sheet's totals."""
    from strukit import shapes, wind
    proj = dict(name="t", number="t", date="2026-11-24", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6S", source="t"), dict(expr="0.9D + 1.0W", source="t")],
                combos_asd=[dict(expr="D + S", source="t")])
    th = math.degrees(math.atan(3 / 12))
    W = dict(kind="wind_free_roof", values=dict(mark="WO1", V="115", V_source="t", exposure="C", exposure_basis="t", h="14", roof="pitched (gable)", theta=f"{th:.4f}", L="22", width="41",
             flow="clear", flow_basis="t", Kzt="1.0", Kzt_source="t", model_axis="Y"))
    spec = dict(n="3", spacing="20", end_start="0.5", end_end="0.5", col_spacing="18", cant_low="2", cant_high="2", height="12", slope="3", roof="pitched", ridge="",
                col_shape="HSS8X8X1/2", col_Fy="46", raf_shape="W12X26", raf_Fy="50", base="fixed", D="6", S="30", Lr="")
    out = calc.bent_building(proj, [W], spec)
    assert out["problems"] == [] and out["added"] == 3 * 4 and "ridge 9 ft from line A at 14.25 ft" in out["notes"][0]
    ms = out["members"]
    view = {i["mark"]: i for i in calc.model_view(out["project"], ms)["items"]}
    assert view["R2A"]["b"][2] == pytest.approx(14.25, abs=1e-3) and view["R2B"]["a"][2] == pytest.approx(14.25, abs=1e-3)
    assert view["C2A"]["b"][2] == pytest.approx(12.0, abs=1e-3) and view["C2B"]["b"][2] == pytest.approx(12.0, abs=1e-3) and view["R2B"]["b"][2] == pytest.approx(11.5, abs=1e-3)
    run = calc.model_frame_sway(out["project"], ms)
    assert run["problems"] == [] and not any("Taken as bearing" in n for n in run["notes"])
    ws = calc.build("wind_free_roof", W["values"], proj)[0].free_roof
    Ls = 22 / math.cos(math.atan(3 / 12))
    dead = (6 * Ls * 41 + 3 * shapes.get("W12X26")["W"] * Ls + 6 * shapes.hss("HSS8X8X1/2")["W"] * 12) / 1000
    drag = ws["factor"] * 6 * wind.other_cf("square", 12 / (8 / 12)) * (8 / 12) * 12 / 1000
    for row in ws["totals"]["rows"]:
        side = "in +Y" if row["gamma"] == 0 else "in -Y"
        a = next(a for a in run["audit"] if a["run"] == f"0.9D + 1.0W, wind across the roof {side}, Case {row['case']}")
        assert a["Rz"] == pytest.approx(0.9 * dead + row["V"] / 1000, abs=0.15)
        travel = 1 if row["gamma"] == 0 else -1
        net = travel * (row["H"] / 1000 + drag)                                  # the sheet's H is plus with the wind
        assert -a["Ry"] == pytest.approx(net + (1 if net > 0 else -1) * 0.003 * 0.9 * dead, abs=0.05)
    # the ridge moment is carried: the beam end at the ridge has moment in the gravity run
    ends = next(b for b in run["beams"] if b["mark"] == "R2A")["ends"]["right"]
    assert max(e["M"] for e in ends) > 12.0


def test_unbalanced_snow_on_pitched_bents():
    """Pitched bents with a gable roof snow sheet: every combination with S and no wind is also run with the Sect. 7.6.1 unbalanced load each way.
    Check: the total vertical reaction equals dead plus the unbalanced snow on the plan area, by hand from the snow sheet's own values."""
    from strukit import shapes
    proj = dict(name="t", number="t", date="2026-11-24", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6S", source="t")], combos_asd=[dict(expr="D + S", source="t")])
    SN = dict(kind="snow", values=dict(mark="SN1", pg="40", pg_source="t", risk="II", roughness="C", exposure="partially exposed", thermal="unheated, open-air, kept just above freezing, or cold ventilated roof",
              roof="gable or hip", rise="3", slippery="no", W="11", simple="no", W2="0.45", W2_source="t"))
    rs = calc.build("snow", SN["values"], proj)[0].snow
    assert rs.unbalanced and rs.unbalanced["surcharge"] > 0
    spec = dict(n="3", spacing="20", end_start="0", end_end="0", col_spacing="18", cant_low="2", cant_high="2", height="12", slope="3", roof="pitched", ridge="",
                col_shape="HSS8X8X1/2", col_Fy="46", raf_shape="W12X26", raf_Fy="50", base="fixed", D="6", S=f"{rs.balanced:.4f}", Lr="")
    out = calc.bent_building(proj, [SN], spec)
    run = calc.model_frame_sway(out["project"], out["members"])
    assert run["problems"] == [] and run["runs"] == 4 + 4 and any("Unbalanced snow" in n for n in run["notes"])
    u = rs.unbalanced
    cosr = math.cos(math.atan(3 / 12))
    Ls = 22 / cosr
    dead = (6 * Ls * 40 + 3 * shapes.get("W12X26")["W"] * Ls + 6 * shapes.hss("HSS8X8X1/2")["W"] * 12) / 1000
    # the generated S load is per foot of rafter length (psf x tributary on the sloped length), so the hand total uses the sloped lengths too
    half = 11 / cosr
    ext = min(u["extent"], 11) / cosr
    snow_unb = (u["windward"] * half + u["leeward"] * half + u["surcharge"] * ext) * 40 / 1000
    a = next(a for a in run["audit"] if "unbalanced snow, leeward side toward +Y, notional load in +Y" in a["run"])
    assert a["Rz"] == pytest.approx(1.2 * dead + 1.6 * snow_unb, rel=0.01)
    bal = next(a for a in run["audit"] if a["run"] == "1.2D + 1.6S, notional load in +Y")
    assert bal["Rz"] == pytest.approx(1.2 * dead + 1.6 * rs.balanced * Ls * 40 / 1000, rel=0.01)
    # a single-slope building has no ridge: no unbalanced runs
    mono = calc.bent_building(proj, [SN], dict(spec, roof="", slope="1"))
    assert calc.model_frame_sway(mono["project"], mono["members"])["runs"] == 4


def test_eave_portal_bays_carry_the_building_lengthwise():
    """Zach, 2026-11-24 02:39: wide-flange beams tie the bents together and make portal frames along the building. Quick start with W12X26 eave
    beams in bays 3 and 6, pinned struts in the other bays, and bases fixed for sway across the bents only (pinned along the building)."""
    src = json.load(open(os.path.join(HERE, "data", "job_2026_030_west.strukit")))
    proj = {k: v for k, v in src["project"].items() if k != "model"}
    spec = dict(n="8", spacing="10, 20, 20, 20, 20, 20, 20", end_start="0.5", end_end="0.5", col_spacing="18.5", cant_low="1", cant_high="2.25", height="11", slope="1",
                col_shape="HSS8X8X1/2", col_Fy="46", raf_shape="HSS10X6X3/8", raf_Fy="46", base="fixed for sway in Y only", D="6.1", S="36.12", Lr="",
                eave_shape="W12X26", eave_Fy="50", eave_bays="3, 6", strut_shape="C8X11.5", strut_Fy="36")
    out = calc.bent_building(proj, [src["members"][0]], spec)
    assert out["problems"] == [] and out["added"] == 24 + 14
    eb = {m["values"]["mark"]: m["values"] for m in out["members"] if m["values"].get("mark", "")[:1] == "E"}
    assert sorted(k for k in eb if not k.startswith("ES")) == ["E3A", "E3B", "E6A", "E6B"] and len(eb) == 14
    assert eb["E3A"]["at_fix_i"] == "moment" and "at_fix_i" not in eb["ES1A"]
    assert float(eb["E3B"]["at_dz1"]) == pytest.approx(18.5 / 12, abs=1e-3) and "at_dz1" not in eb["E3A"]      # line B column tops are higher
    assert calc._base_flags("fixed for sway in Y only") == (1, 1, 1, 1, 0, 1) and calc._base_flags("fixed for sway in X only") == (1, 1, 1, 0, 1, 1)
    assert calc._base_flags("") == (1, 1, 1, 0, 0, 1) and calc._base_flags("fixed") == (1, 1, 1, 1, 1, 1)
    r = calc.model_frame_sway(out["project"], out["members"])
    assert r["problems"] == []
    bm = {b["mark"]: b for b in r["beams"]}
    # the portal beams take the frame moment; a pinned strut has only its own weight in bending (w L^2 / 8 = 0.0115 x 20^2 / 8 x 1.2 = 0.69 kip-ft)
    assert all(float(bm[k]["M"]) / 12 > 5 for k in ("E3A", "E3B", "E6A", "E6B"))
    assert all(float(bm[k]["M"]) / 12 < 1.0 for k in bm if k.startswith("ES"))
    assert all(float(c["ratio"]) < 1 for c in r["columns"]) and all(float(b["ratio"]) < 1 for b in r["beams"])
    # with the bases pinned along the building and no portal bay, nothing holds the building lengthwise: the run says so
    bare = calc.bent_building(proj, [src["members"][0]], dict(spec, eave_shape="", eave_bays="", strut_shape=""))
    assert calc.model_frame_sway(bare["project"], bare["members"])["problems"]
    # input checks
    assert calc.bent_building(proj, [], dict(spec, eave_bays="9"))["problems"] and calc.bent_building(proj, [], dict(spec, eave_bays=""))["problems"]
