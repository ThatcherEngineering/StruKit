"""The calc sheet PDFs are produced with the firm header and footer (matching HydroKit's
sheets) and carry the checks."""
import subprocess

from strukit.calcsheet import steel_beam_pdf
from strukit.ws_steel_beam import Combo, DeflCheck, run


def test_steel_beam_calc_sheet(tmp_path):
    loads = [dict(case="D", kind="uniform", w=0.45), dict(case="L", kind="uniform", w=0.75)]
    asd = [Combo("D + L", {"D": 1, "L": 1}, "ASCE/SEI 7 Ch. 2")]
    defl = [DeflCheck("live", {"L": 1}, 360, "given")]
    sheet = run("B1", "W18x50", 50, 35, loads, asd, defl, [], "ASD", True)
    out = steel_beam_pdf(sheet, str(tmp_path / "b1.pdf"), "0000-000 TEST", "AISC 360-22",
                         "2026-11-21", combos=asd)
    data = open(out, "rb").read()
    assert data[:5] == b"%PDF-" and len(data) > 2000
    try:
        text = subprocess.run(["pdftotext", "-layout", out, "-"], capture_output=True,
                              text=True, timeout=30).stdout
    except FileNotFoundError:
        return                                   # pdftotext not installed: skip the text checks
    assert "Thatcher Engineering, LLC" in text and "Beam B1" in text
    assert "FLAG - Flexure" in text and "Eq. F2-4" in text and "Sheet 1 of 1" in text
    assert "Prepared with StruKit" in text and "office@thatcherengineering.org" in text
    assert "Nov 21, 2026" in text and "run " not in text and "Trail Stone" not in text


def _text(path):
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True,
                              text=True, timeout=30).stdout
    except FileNotFoundError:
        return None


def test_steel_column_calc_sheet(tmp_path):
    from strukit.calcsheet import steel_column_pdf
    from strukit.ws_steel_column import run as col
    cb = [Combo("1.2D + 1.6L", {"D": 1.2, "L": 1.6}, "given")]
    s = col("C1", "W14x90", 50, 30, [dict(case="D", P=140.0), dict(case="L", P=420.0)], cb,
            1.0, 1.0, "pinned top and bottom", "LRFD", False, Ly_ft=15)
    out = steel_column_pdf(s, str(tmp_path / "c1.pdf"), "0000-000 TEST", "AISC 360-22",
                           "2026-11-21", combos=cb)
    t = _text(out)
    if t is None:
        return
    assert "Column C1" in t and "Eq. E3-1" in t and "840.0 kip" in t and "Sheet 1 of 1" in t
    assert "Not Checked" in t.title()


def test_footing_calc_sheets(tmp_path):
    import pytest
    from strukit import ws_footing
    from strukit.calcsheet import footing_pdf
    from strukit.ws_steel_beam import WorksheetError
    iso = dict(B_ft=2.5, L_ft=2.5, h_in=10, fc=3000, fy=60000, col_x_in=4, col_y_in=4, bar=5,
               n_x=3, n_y=3, cover_in=3, P_service=7600, service_combo="D + L", Pu=12160,
               strength_combo="1.2D + 1.6L", q_allow_psf=1500, conc_pcf=145, plate_x_in=6,
               plate_y_in=6)
    with pytest.raises(WorksheetError):                  # no soil source: stop
        ws_footing.isolated("A", "", "wood", **iso)
    f = ws_footing.isolated("A", "test soils report", "wood", **iso)
    t = _text(footing_pdf(f, str(tmp_path / "f.pdf"), "0000-000 TEST", "ACI 318-19", "2026-11-21"))
    con = dict(W_ft=2, h_in=10, fc=3000, fy=60000, wall_in=8, bar_t=5, spacing_t_in=12, bar_l=5,
               n_l=2, cover_in=3, P_service_plf=1932, service_combo="D + L", Pu_plf=2675.2,
               strength_combo="1.2D + 1.6L", dead_factor=1.2, q_allow_psf=1500, conc_pcf=145,
               stem_h_in=36, stem_pcf=145, soil_depth_ft=3.5, soil_pcf=110)
    g = ws_footing.continuous("CF1", "test soils report", **con)
    t2 = _text(footing_pdf(g, str(tmp_path / "g.pdf"), "0000-000 TEST", "ACI 318-19", "2026-11-21"))
    if t is None:
        return
    assert "Footing A" in t and "1,337 psf" in t and "Table 22.6.5.2" in t and "test soils report" in t
    assert "Footing CF1" in t2 and "1,488 psf" in t2 and "stem wall weight = 290.0" in t2
    assert "ACI 318-19" in t


def test_column_with_lateral_load_sheet_runs_to_two_pages(tmp_path):
    from strukit import calcsheet
    from strukit.ws_steel_column import run as col
    cb = [Combo("D + L", {"D": 1, "L": 1}, "given"), Combo("D + 0.6W", {"D": 1, "W": 0.6}, "given")]
    s = col("C2", "W10x33", 50, 16, [dict(case="D", P=12.0), dict(case="L", P=30.0)], cb, 1.0, 1.0,
            "pinned top and bottom", "ASD", True,
            lateral=[dict(case="W", bending="x", kind="uniform", w=1.5)])
    out = calcsheet.steel_column_pdf(s, str(tmp_path / "c2.pdf"), "0000-000 TEST", "AISC 360-22",
                                     "2026-11-21", combos=cb)
    t = _text(out)
    if t is None:
        return
    assert calcsheet._paged.last_pages == 2 and "Sheet 1 of 2" in t and "Sheet 2 of 2" in t
    assert "Eq. A-8-3" in t and "H1-1" in t and "Shear, strong direction" in t


def test_header_takes_project_name_job_and_site(tmp_path):
    loads = [dict(case="D", kind="uniform", w=0.45)]
    asd = [Combo("D", {"D": 1}, "given")]
    sheet = run("B1", "W18x50", 50, 20, loads, asd, [], "continuous", "ASD", True)
    out = steel_beam_pdf(sheet, str(tmp_path / "b.pdf"),
                         dict(name="Test Building", number="2026-000", address="1 Main St, Pueblo, CO"),
                         "AISC 360-22", "2026-11-21", combos=asd)
    t = _text(out)
    if t is None:
        return
    assert "Test Building" in t and "Job 2026-000" in t and "1 Main St, Pueblo, CO" in t


def test_frame_calc_sheet(tmp_path):
    from strukit import calcsheet, ws_frame
    lay = ws_frame.layout([24, 30], [14, 12], "fixed", "W10x49", "W16x40", roof="gable", rise_ft=6,
                          rafter_shape="W14x30")
    loads = [dict(case="D", on="level:1", w=0.9), dict(case="S", on="rafters", w=0.75, kind="projected"),
             dict(case="W", level=2, Fx=3.5)]
    cb = [Combo("D + S", {"D": 1, "S": 1}, "given"), Combo("D + 0.6W", {"D": 1, "W": 0.6}, "given")]
    s = ws_frame.run("F2", lay, 50, loads, cb, "ASD", True, {"columns": 12, "beams": 6, "rafters": 5})
    t = _text(calcsheet.frame_pdf(s, str(tmp_path / "f.pdf"), "0000-000 TEST", "AISC 360-22", "2026-11-21"))
    if t is None:
        return
    assert "Frame F2" in t and "Member Summary" in t.title() and "Drift amplification, story 2" in t
    assert "B2-1" in t and "R3" in t and "Base Reactions" in t.title()


def test_frame_sheet_draws_every_load_type(tmp_path):
    """The frame elevation carries its loads: member gravity loads, a sideways member load, joint loads and level loads all print."""
    from strukit import calcsheet, ws_frame
    lay = ws_frame.layout([24], [14], "pin", "W10x49", "W16x40")
    col = next(m.name for m in lay.members if m.role == "column")
    top = lay.levels[1][0]
    loads = [dict(case="D", on="beams", w=0.9), dict(case="W", on=col, w=0.2, dir="x"), dict(case="W", level=1, Fx=3.5),
             dict(case="D", node=top, Fy=-5.0), dict(case="W", node=top, Fx=-1.0, Fy=2.0)]
    cb = [Combo("D + 0.6W", {"D": 1, "W": 0.6}, "given"), Combo("D", {"D": 1}, "given")]
    s = ws_frame.run("F3", lay, 50, loads, cb, "ASD", True, {"columns": 14, "beams": 6})
    path = calcsheet.frame_pdf(s, str(tmp_path / "f.pdf"), "0000-000 TEST", "AISC 360-22", "2026-11-23")
    t = _text(path)
    if t is not None:
        z = t.replace(" ", "")
        assert "D0.9k/ft" in z and "W0.2k/ft" in z and "W3.5k" in z and "D5k" in z and "W1k" in z and "W2k" in z
