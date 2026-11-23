"""ASCE/SEI 7-22 Chapter 2 combinations, checked against the standard's text
(Sect. 2.3.1: 1.4D; 1.2D + 1.6L + (0.5Lr or 0.3S or 0.5R); 1.2D + (1.6Lr or 1.0S or 1.6R) + (L or 0.5W);
1.2D + 1.0W + L + (0.5Lr or 0.3S or 0.5R); 0.9D + 1.0W.  Sect. 2.4.1: D; D + L; D + (Lr or 0.7S or R);
D + 0.75L + 0.75(Lr or 0.7S or R); D + 0.6W; D + 0.75L + 0.75(0.6W) + 0.75(Lr or 0.7S or R); 0.6D + 0.6W)."""
import pytest

from strukit import loadcombos as lc
from strukit.gui.calc import parse_expr


def _f(rows):
    return [parse_expr(r["expr"]) for r in rows]


def test_strength_combinations():
    f = _f(lc.LRFD)
    assert len(f) == 14
    assert {"D": 1.4} in f and {"D": 0.9, "W": 1.0} in f
    assert {"D": 1.2, "L": 1.6, "S": 0.3} in f                 # snow as companion: 0.3 in 7-22
    assert {"D": 1.2, "S": 1.0, "W": 0.5} in f                 # snow as principal: 1.0 in 7-22
    assert {"D": 1.2, "Lr": 1.6, "L": 1.0} in f
    assert {"D": 1.2, "W": 1.0, "L": 1.0, "R": 0.5} in f
    assert all("7-22 Sect. 2.3.1" in r["source"] for r in lc.LRFD)


def test_allowable_stress_combinations():
    f = _f(lc.ASD)
    assert len(f) == 13
    assert {"D": 1.0} in f and {"D": 1.0, "L": 1.0} in f and {"D": 0.6, "W": 0.6} in f
    assert {"D": 1.0, "S": 0.7} in f
    assert {"D": 1.0, "L": 0.75, "S": pytest.approx(0.75 * 0.7)} in f
    assert {"D": 1.0, "L": 0.75, "W": pytest.approx(0.75 * 0.6), "Lr": 0.75} in f
    assert all("7-22 Sect. 2.4.1" in r["source"] for r in lc.ASD)


def test_window_offers_the_set():
    from strukit.gui import server
    info = server.api("/api/info", {}) if hasattr(server, "api") else None
    if info:
        assert info["combo_sets"]["ASCE/SEI 7-22"]["ASD"][0]["expr"] == "D"
