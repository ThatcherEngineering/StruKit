"""The calc sheet PDF is produced, is one page, and carries the firm name, the checks
and no program name."""
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
    assert "THATCHER ENGINEERING, LLC" in text and "Beam B1" in text
    assert "FLAG - Flexure" in text and "Eq. F2-4" in text and "Page 1 of 1" in text
    assert "strukit" not in text.lower()


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
    assert "Column C1" in t and "Eq. E3-1" in t and "840.0 kip" in t and "Page 1 of 1" in t
    assert "Not Checked" in t.title() and "strukit" not in t.lower()


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
    assert "strukit" not in (t + t2).lower()


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
    assert calcsheet._paged.last_pages == 2 and "Page 1 of 2" in t and "Page 2 of 2" in t
    assert "Eq. A-8-3" in t and "H1-1" in t and "Shear, strong direction" in t
