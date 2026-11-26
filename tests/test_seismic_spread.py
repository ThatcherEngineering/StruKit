"""Seismic story force to the wall lines by the weight in the building model (option on the Seismic Base Shear screen) instead of evenly over
the building width. The story force is shared in proportion to the placed seismic weight between the half-way lines of neighbouring wall
lines; the total at each level is unchanged."""
import copy
import json
import pathlib

import pytest

from strukit.gui import calc


def test_weight_in_strip_by_hand():
    seg = [dict(W=100.0, p1=(0.0, 0.0), p2=(0.0, 10.0), off=None)]              # a 10 ft wall along y
    assert calc._weight_in_strip(seg, 1, 0.0, 2.5) == pytest.approx(25.0, abs=2.5)
    assert calc._weight_in_strip(seg, 1, -5.0, 20.0) == pytest.approx(100.0)
    assert calc._weight_in_strip(seg, 0, 1.0, 5.0) == 0.0
    row = [dict(W=400.0, p1=(0.0, 0.0), p2=(10.0, 0.0), off=(0.0, -20.0))]       # joists 10 ft long over a 20 ft wide row
    assert calc._weight_in_strip(row, 1, -5.0, 0.0) == pytest.approx(100.0, rel=0.05)
    assert calc._weight_in_strip(row, 0, 0.0, 10.0) == pytest.approx(400.0)


def test_2026_011_by_weight_keeps_the_total_and_follows_the_weight():
    d = json.loads(pathlib.Path(__file__).with_name("data").joinpath("job_2026_011_model.strukit").read_text())
    P, ms = d["project"], d["members"]
    even = calc.lateral_wind(P, ms, load="seismic")
    ms2 = copy.deepcopy(ms)
    next(m for m in ms2 if m["kind"] == "seismic_elf")["values"]["spread"] = "by the weight in the building model"
    mass = calc.lateral_wind(P, ms2, load="seismic")
    assert not mass["problems"]
    for lvl in {l["level"] for l in even["lines"]}:
        for ax in ("X", "Y"):
            e = sum(l["V"] - l["from_above"] for l in even["lines"] if l["level"] == lvl and l["wind"] == ax)
            m = sum(l["V"] - l["from_above"] for l in mass["lines"] if l["level"] == lvl and l["wind"] == ax)
            assert m == pytest.approx(e, rel=1e-6)                      # same story force at each level, shared differently
    assert any(abs(a["V"] - b["V"]) > 50 for a, b in zip(even["lines"], mass["lines"]))
    w = next(m for m in mass["members"] if (m.get("values") or {}).get("mark") == "Line 1, lower level")
    assert "the model's seismic weight between the half-way lines" in w["values"]["v_source"]
