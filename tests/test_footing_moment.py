"""Footing with moment. References:
 (1) the centred footing module (validated against job 2026-011): with zero moment every
     demand must match it;
 (2) hand statics, worked here:
     Footing 8 ft x 6 ft carrying 100 kips total.
       M = 100 kip-ft: e = 1.00 ft < B/6 = 1.333 ft.
           q = P/A (1 +/- 6e/B) = 2.0833 (1 +/- 0.75) = 3.6458 and 0.5208 ksf.
       M = 150 kip-ft: e = 1.50 ft > B/6. Bearing length 3 (B/2 - e) = 7.50 ft;
           q max = 2 P / (L x 7.5) = 200 / 45 = 4.4444 ksf.
 No published worked example of a footing with moment is on file.
"""
import math

import numpy as np
import pytest

from strukit import footing
from strukit.footing import FootingInputError
from strukit.footing_moment import check_eccentric, pressure

GEO = dict(B_ft=2.5, L_ft=2.5, h_in=10, fc=3000, fy=60000, col_x_in=4, col_y_in=4, bar=5, n_x=3, n_y=3,
           cover_in=3, q_allow_psf=1500, conc_pcf=145, plate_x_in=6, plate_y_in=6)


def test_pressure_inside_and_outside_the_middle_third():
    q, e, a = pressure(100.0, 100.0, 8.0, 6.0)
    assert e == pytest.approx(1.0) and a == 8.0
    assert float(q(4.0)) == pytest.approx(3.6458, rel=1e-4) and float(q(-4.0)) == pytest.approx(0.5208, rel=1e-3)
    q, e, a = pressure(100.0, 150.0, 8.0, 6.0)
    assert a == pytest.approx(7.5) and float(q(4.0)) == pytest.approx(4.4444, rel=1e-4)
    assert float(q(-4.0)) == 0.0 and float(q(-3.5)) == 0.0                      # lifted off for the last 0.5 ft
    xs = np.linspace(-4, 4, 8001)                                                 # the pressure carries P at e
    tr = getattr(np, "trapezoid", None) or np.trapz
    assert 6.0 * tr(q(xs), xs) == pytest.approx(100.0, rel=1e-4)
    assert 6.0 * tr(q(xs) * xs, xs) == pytest.approx(150.0, rel=1e-4)
    with pytest.raises(FootingInputError):
        pressure(100.0, 400.0, 8.0, 6.0)                                          # e = B/2: overturns


def test_zero_moment_matches_the_centred_footing():
    base = footing.check(P_service=7600, service_combo="D+L", Pu=12160, strength_combo="1.2D+1.6L",
                         **{k: v for k, v in GEO.items()})
    r = check_eccentric(service=[dict(name="D+L", P=7600, M=0, V=0)],
                        strength=[dict(name="1.2D+1.6L", P=12160, M=0, V=0, wt_factor=1.2)], **GEO)
    assert r.get("soil bearing pressure, maximum").demand == pytest.approx(base.get("soil bearing pressure").demand, rel=1e-9)
    for nm in ("one-way shear, x direction", "one-way shear, y direction", "flexure, x direction", "flexure, y direction"):
        assert r.get(nm).demand == pytest.approx(base.get(nm).demand, rel=1e-4), nm
        assert r.get(nm).capacity == base.get(nm).capacity
    two, b2 = r.get("two-way shear with moment transfer"), base.get("two-way shear")
    bo_d = 2 * (5 + 6.375 + 5 + 6.375) * 6.375
    assert two.demand == pytest.approx(b2.demand / bo_d, rel=1e-4)              # same force, as a stress
    assert two.capacity == pytest.approx(b2.capacity / bo_d, rel=1e-9)


def test_moment_by_hand():
    # 6 ft square, 18 in thick, 16 in square column, #6 bars. Factored: Pu = 120 kips, Mu = 90 kip-ft,
    # weight factor 0 so the hand numbers stay simple (net pressure = pressure from Pu and Mu).
    g = dict(B_ft=6, L_ft=6, h_in=18, fc=4000, fy=60000, col_x_in=16, col_y_in=16, bar=6, n_x=8, n_y=8, cover_in=3,
             q_allow_psf=4000, conc_pcf=150)
    r = check_eccentric(service=[dict(name="S", P=90000, M=60000, V=0)],
                        strength=[dict(name="U", P=120000, M=90000, V=0, wt_factor=0.0)], **g)
    # factored pressure: e = 0.75 ft < 1.0 ft: q = 120/36 (1 +/- 0.75) = 5.8333 and 0.8333 ksf, slope 0.8333 ksf/ft
    d_x = 18 - 3 - 0.375                                                         # 14.625 in, lower layer
    xs = (8 + d_x) / 12                                                          # 1.8854 ft from the centre
    q = lambda x: 3.3333 + 0.83333 * x
    v_hand = 6 * (q(3) + q(xs)) / 2 * (3 - xs) * 1000                             # trapezoid, lb
    assert r.get("one-way shear, x direction").demand == pytest.approx(v_hand, rel=2e-3)
    xc = 8 / 12
    a = 3 - xc                                                                   # cantilever 2.333 ft
    m_hand = 6 * (q(xc) * a ** 2 / 2 + (q(3) - q(xc)) * a ** 2 / 3) * 1000        # lb-ft
    assert r.get("flexure, x direction").demand == pytest.approx(m_hand, rel=2e-3)
    assert r.get("flexure, y direction").demand == pytest.approx(120000 / 6 * a ** 2 / 2, rel=2e-3)
    # two-way: d = 18 - 3 - 0.75 = 14.25 in; b1 = b2 = 30.25 in; bo = 121 in
    d = 14.25
    b = 16 + d
    Vu = 120000 - (120000 / 5184) * b * b                                        # mean pressure over the perimeter area
    gv = 1 - 1 / (1 + 2 / 3)
    Jc = d * b ** 3 / 6 + b * d ** 3 / 6 + d * b * b ** 2 / 2
    vu = Vu / (4 * b * d) + gv * 90000 * 12 * (b / 2) / Jc
    two = r.get("two-way shear with moment transfer")
    assert gv == pytest.approx(0.4) and two.demand == pytest.approx(vu, rel=2e-3)
    assert two.capacity == pytest.approx(0.75 * 4 * math.sqrt(4000), rel=1e-9)
    # service: P total = 90 + 36 x 1.5 x 0.150 = 98.1 kips; e = 60 / 98.1 = 0.6116 ft; q max = 98.1/36 (1 + 6 x 0.6116 / 6)
    assert r.get("soil bearing pressure, maximum").demand == pytest.approx(98100 / 36 * (1 + 0.6116), rel=1e-3)


def test_overturning_sliding_and_uplift_notes():
    g = dict(B_ft=6, L_ft=6, h_in=18, fc=4000, fy=60000, col_x_in=16, col_y_in=16, bar=6, n_x=8, n_y=8, cover_in=3,
             q_allow_psf=4000, conc_pcf=150)
    sv = [dict(name="0.6D+0.6W", P=20000, M=40000, V=3000)]
    st = [dict(name="0.9D+W", P=30000, M=66000, V=5000, wt_factor=0.9)]
    r = check_eccentric(service=sv, strength=st, ot_required=1.5, slide_mu=0.35, slide_required=1.5, **g)
    Pt = 20000 + 8100
    assert r.get("overturning").capacity == pytest.approx(Pt * 3 / (40000 + 3000 * 1.5), rel=1e-6)
    assert r.get("sliding").capacity == pytest.approx(0.35 * Pt / 3000, rel=1e-6)
    assert any("lifts off" in n for n in r.notes) and any("top reinforcement" in n for n in r.not_checked)
    r2 = check_eccentric(service=sv, strength=st, **g)
    assert any("overturning" in n for n in r2.not_checked) and any("sliding" in n for n in r2.not_checked)
    with pytest.raises(FootingInputError):
        check_eccentric(service=sv, strength=[dict(name="U", P=1, M=1, V=0)], **g)      # weight factor missing
