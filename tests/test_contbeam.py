"""Beams of more than one span and with overhangs: statics against textbook values, and
the worksheet against hand calculations.

Textbook values (uniform load w, equal spans L):
  two spans, both loaded: support moment w L^2 / 8, centre reaction 1.25 w L, end 0.375 w L,
    span moment 9 w L^2 / 128; one span loaded: span moment 49 w L^2 / 512 (0.0957 w L^2)
  three spans, all loaded: support moment 0.100 w L^2, end-span moment 0.080 w L^2;
    live on the two end spans: end-span moment 0.101 w L^2; live on two adjacent spans:
    support moment 0.1167 w L^2
  overhang a with load w: support moment w a^2 / 2
"""
import pytest

from strukit import contbeam as cb, ws_wood
from strukit.ws_steel_beam import DeflCheck
from tests.test_lvl import _combos


def test_two_span_statics():
    lay = cb.layout(None, [10, 10])
    e = cb.envelope(lay, 1e9, {"D": [dict(kind="uniform", w=100.0)]}, {"D": 1.0})
    assert e.Mneg / 12 == pytest.approx(1250, rel=1e-5) and e.Mpos / 12 == pytest.approx(703.125, rel=1e-5)
    assert e.R_int == pytest.approx(1250, rel=1e-5) and e.R_end == pytest.approx(375, rel=1e-5) and e.n == 1
    p = cb.envelope(lay, 1e9, {"L": [dict(kind="uniform", w=100.0)]}, {"L": 1.0})
    assert p.Mpos / 12 == pytest.approx(49 / 512 * 1e4, rel=1e-4) and p.Mneg / 12 == pytest.approx(1250, rel=1e-5) and p.R_min < 0


def test_three_span_live_load_patterns():
    lay = cb.layout(None, [10, 10, 10])
    d = cb.envelope(lay, 1e9, {"D": [dict(kind="uniform", w=100.0)]}, {"D": 1.0})
    assert d.Mneg / 12 == pytest.approx(0.100 * 1e4, rel=1e-4) and d.Mpos / 12 == pytest.approx(0.080 * 1e4, rel=1e-4)
    p = cb.envelope(lay, 1e9, {"L": [dict(kind="uniform", w=100.0)]}, {"L": 1.0})
    assert p.Mpos / 12 == pytest.approx(0.1013 * 1e4, rel=2e-3) and p.Mneg / 12 == pytest.approx(0.11667 * 1e4, rel=1e-3)


def test_overhang_statics_and_deflection_limit():
    lay = cb.layout(10, None, 0, 4)
    e = cb.envelope(lay, 1e9, {"D": [dict(kind="uniform", w=100.0)]}, {"D": 1.0})
    assert e.Mneg / 12 == pytest.approx(800, rel=1e-5)
    segs = lay.segments
    assert segs[1][2] == "right overhang" and segs[1][3] == 8.0             # limit on twice the overhang
    assert "overhang at the right" in lay.describe()


def test_two_span_glulam_beam_by_hand():
    # 5.5 x 18 24F-V4, two 20 ft spans, D 300 + L 500 plf, top braced, bottom braced at the support, bearing 4 in / 6 in
    # negative: (300 + 500) x 400 / 8 = 40,000 lb-ft; S = 297; fb = 1,616.2 psi against Fbx- 1,850 x CV
    # positive: D 9/128 x 300 x 400 + L 49/512 x 500 x 400 = 8,437.5 + 19,140.6 = 27,578 lb-ft; fb = 1,114.3 against 2,400 x CV
    # CV = (21/20 x 12/18 x 5.125/5.5)^0.1 = 0.9583; negative governs: 1,616.2 / 1,772.8
    # centre reaction 1.25 x 800 x 20 = 20,000 lb on 5.5 x 6 = 606.1 psi against 650; end: 0.375 x 300 x 20 + 0.4375 x 500 x 20 = 6,625 lb
    loads = [dict(case="D", kind="uniform", w=300.0), dict(case="L", kind="uniform", w=500.0)]
    s = ws_wood.glulam_beam("GB3", "24F-V4 DF/DF", False, 5.5, 18, 20, loads, _combos(), [DeflCheck("live", {"L": 1}, 360, "typed")],
                            0.0, 4.0, False, spans=[20, 20], lu_neg_ft=0.0, bearing_int_in=6.0)
    r = {x.check: x for x in s.rows}
    cv = (21 / 20 * 12 / 18 * 5.125 / 5.5) ** 0.1
    assert r["bending"].demand == pytest.approx(1616.2, abs=0.3) and r["bending"].capacity == pytest.approx(1850 * cv, abs=0.5)
    assert "negative" in r["bending"].note
    assert r["bearing at interior support"].demand == pytest.approx(606.1, abs=0.2)
    assert r["bearing at support"].demand == pytest.approx(6625 / 22, abs=0.2)
    assert r["shear"].demand == pytest.approx(1.5 * 10000 / 99, abs=0.2)                    # 0.625 w L at the centre support
    # live deflection, one span loaded: 0.0092 w L^4 / EI (textbook 0.00915) = 0.0092 x 500/12 x 240^4 / (1.8e6 x 2673)
    assert r["deflection, live"].demand == pytest.approx(0.00915 * (500 / 12) * 240 ** 4 / (1.8e6 * 2673), rel=0.01)
    assert any("4.3.3" in a for a in s.assumptions) and any("snow" in n for n in s.not_checked)
    with pytest.raises(Exception, match="bottom edge"):
        ws_wood.glulam_beam("GB3", "24F-V4 DF/DF", False, 5.5, 18, 20, loads, _combos(), [], 0.0, 4.0, False, spans=[20, 20])


def test_sawn_beam_with_overhang_by_hand():
    # (2) 2x10 DF-L No. 2, 10 ft span with a 3 ft overhang, D 100 + L 300 plf everywhere, bottom edge unbraced 3 ft
    # overhang moment 400 x 9 / 2 = 1,800 lb-ft; span moment with live off the overhang:
    #   R1 = 400 x 5 - 100 x 4.5 / 10 = 1,955 lb; M = R1^2 / (2 x 400) = 4,777.5 lb-ft -> governs
    loads = [dict(case="D", kind="uniform", w=100.0), dict(case="L", kind="uniform", w=300.0)]
    s = ws_wood.beam("B", "DOUGLAS FIR-LARCH", "No. 2", "2x10", 2, 10, loads, _combos(), [DeflCheck("live", {"L": 1}, 360, "typed")],
                     0.0, 3.0, False, False, False, overhang_right=3.0, lu_neg_ft=3.0)
    r = {x.check: x for x in s.rows}
    S = 3.0 * 9.25 ** 2 / 6
    assert r["bending"].demand == pytest.approx(4777.5 * 12 / S, rel=1e-3)
    assert "overhang" in dict(s.info)["Span"] and r["deflection, live"].note.startswith(("span", "right overhang"))
