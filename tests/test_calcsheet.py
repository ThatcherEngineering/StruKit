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
