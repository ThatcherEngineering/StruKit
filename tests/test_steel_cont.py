"""Steel beams over more than one span or with overhangs.

References (statics, textbook continuous-beam values): two equal spans L under uniform w: M over the middle support = w L^2 / 8, largest shear 0.625 w L,
reactions 0.375 w L, 1.25 w L, 0.375 w L; largest sagging moment with live load on one span only = 0.0957 w L^2 (0.070 with both loaded); live deflection with
one span loaded 0.0092 w L^4 / (E I).  Overhang a beyond a simple span: M at the support = w a^2 / 2.  Strength of each unbraced segment as on a simple span."""
import pytest

from strukit import calcsheet, shapes, steel_beam
from strukit.gui import calc

LRFD = dict(method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 2")])
V = dict(mark="B2", shape="W16X26", Fy="50", span="20", more_spans="20", oh_left="", oh_right="", bracing="continuous", brace_pts="", self_weight="no",
         loads=[dict(case="D", kind="uniform", mag="0.5", x1="", x2="", label=""), dict(case="L", kind="uniform", mag="1.0", x1="", x2="", label="")],
         defl=[dict(label="live", expr="L", ratio="360", source="typed in")])


def test_two_equal_spans(tmp_path):
    s, kind, kw = calc.build("steel_beam", V, LRFD)
    r = {x.check: x for x in s.rows}
    assert r["flexure"].demand == pytest.approx(2.2 * 400 / 8, rel=1e-3) and r["shear"].demand == pytest.approx(0.625 * 2.2 * 20, rel=1e-3)
    assert s.reactions["1.2D + 1.6L"] == pytest.approx((16.5, 55.0, 16.5), rel=1e-3)
    assert r["deflection, live"].demand == pytest.approx(0.0092 * (1.0 / 12) * 240 ** 4 / (29000 * 301), rel=0.01) and r["deflection, live"].capacity == pytest.approx(240 / 360)
    assert s.supports == [0.0, 20.0, 40.0] and "continuous over 3 supports" in s.span_text
    calcsheet.steel_beam_pdf(s, str(tmp_path / "b.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)


def test_pattern_live_load_governs_the_sagging_segment():
    """Dead load small: with brace points at the supports only, the segment check for span 1 sees the sagging moment with live load on span 1 alone."""
    v = dict(V, bracing="at points", brace_pts="20", loads=[dict(case="L", kind="uniform", mag="1.0", x1="", x2="", label="")], defl=[])
    s, _, _ = calc.build("steel_beam", v, LRFD)
    # the sagging moment with one span loaded, 0.0957(1.6)(400) = 61.2 kip-ft at its lower Cb, governs over the hogging 80 kip-ft at its higher Cb
    r = {x.check: x for x in s.rows}["flexure"]
    assert r.demand == pytest.approx(0.0957 * 1.6 * 400, rel=0.005) and "Lb = 20 ft" in r.note and s.brace_points == [0.0, 20.0, 40.0]
    p = shapes.get("W16X26")
    cb = float(r.note.split("Cb = ")[1].split(",")[0])
    assert r.capacity == pytest.approx(steel_beam.check(p, 50.0, 240.0, cb, "LRFD").M_avail / 12, rel=0.005)
    from strukit import contbeam
    lay = contbeam.layout(20.0, [20.0, 20.0])
    env = contbeam.envelope(lay, 29000 * 301, {"L": [dict(case="L", kind="uniform", w=1.0)]}, {"L": 1.6})
    assert env.Mpos / 12 == pytest.approx(0.0957 * 1.6 * 400, rel=0.005) and env.n == 3


def test_overhang_and_other_sections(tmp_path):
    v = dict(V, more_spans="", oh_right="6", loads=[dict(case="D", kind="uniform", mag="1.0", x1="20", x2="", label="")], defl=[dict(label="dead", expr="D", ratio="240", source="typed in")])
    s, _, kw = calc.build("steel_beam", v, dict(method="LRFD", combos_lrfd=[dict(expr="1.4D", source="ASCE/SEI 7-22 Sect. 2.3.1, combination 1")]))
    r = {x.check: x for x in s.rows}
    assert r["flexure"].demand == pytest.approx(1.4 * 1.0 * 36 / 2, rel=2e-3) and "right overhang" in r["deflection, dead"].note and "2 x 6 ft / 240" in r["deflection, dead"].note
    calcsheet.steel_beam_pdf(s, str(tmp_path / "o.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    h, _, kw = calc.build("steel_beam", dict(V, shape="HSS10x6x3/16"), LRFD)
    assert {x.check: x for x in h.rows}["shear"].source == "AISC 360-22 Sect. G4"
    calcsheet.steel_beam_pdf(h, str(tmp_path / "h.pdf"), "Job", "AISC 360-22", "Nov 23, 2026", **kw)
    assert calc.results("steel_beam", dict(V, bracing="at points", brace_pts="55"), LRFD)["state"] == "stopped"
    one, _, _ = calc.build("steel_beam", dict(V, more_spans=""), LRFD)                     # one span: the earlier path, unchanged
    assert not hasattr(one, "supports") and {x.check: x for x in one.rows}["flexure"].demand == pytest.approx(2.2 * 400 / 8)
