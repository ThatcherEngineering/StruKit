"""Gravity takedown: reactions by load case from one member, ready to be loads on the member below."""
import json, os
import pytest
from strukit.gui import calc

D11 = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011.strukit")))
D01 = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_001_mezzanine.strukit")))


def test_steel_beam_by_case():
    m = [x for x in D01["members"] if x["values"]["mark"] == "FloorBeamD.1"][0]          # W10x17, 15.5 ft, D 0.432 + 0.017, L 0.75 kip/ft
    r = calc.case_reactions(m["kind"], m["values"], D01["project"])
    assert [s["name"] for s in r["supports"]] == ["left support", "right support"] and r["supports"][1]["x_ft"] == 15.5
    c = r["supports"][0]["cases"]
    assert c["L"] == pytest.approx(0.75 * 15.5 / 2 * 1000, rel=1e-4) and c["D"] == pytest.approx((0.432 + 0.017) * 15.5 / 2 * 1000, rel=2e-3)
    full = calc.build(m["kind"], m["values"], D01["project"])[0].reactions["D + L"][0] * 1000
    assert c["D"] + c["L"] == pytest.approx(full, rel=1e-6)


def test_overhang_and_wood():
    m = [x for x in D01["members"] if x["values"]["mark"] == "Cantilever"][0]
    r = calc.case_reactions(m["kind"], m["values"], D01["project"])
    assert r["supports"][0]["cases"]["L"] < 0 < r["supports"][1]["cases"]["L"]                 # uplift at the back support of the cantilever
    for m in D11["members"]:
        if m["kind"] in calc.TAKEDOWN_BEAMS:
            r = calc.case_reactions(m["kind"], m["values"], D11["project"])
            assert "supports" in r, (m["values"]["mark"], r)
            tot = calc.build(m["kind"], m["values"], D11["project"])[0].reactions
            name = next(n for n in tot if n in ("D + L", "D + Lr"))
            want = tot[name]
            want = [want[k] for k in sorted(want)] if isinstance(want, dict) else [want] * len(r["supports"])
            for s, w in zip(r["supports"], want):
                got = s["cases"].get("D", 0) + s["cases"].get("L" if name == "D + L" else "Lr", 0)
                assert got == pytest.approx(w, rel=1e-6, abs=0.5), m["values"]["mark"]


def test_post_base():
    m = [x for x in D11["members"] if x["kind"] == "builtup_post"][0]
    r = calc.case_reactions(m["kind"], m["values"], D11["project"])
    assert r["supports"][0]["name"] == "base" and sum(r["supports"][0]["cases"].values()) == pytest.approx(sum(float(x["P"]) for x in m["values"]["loads"]))
    assert "error" in calc.case_reactions("footing_iso", {}, {})


def test_governing_for_a_footing():
    m = [x for x in D11["members"] if x["kind"] == "builtup_post"][0]
    r = calc.case_reactions(m["kind"], m["values"], D11["project"])["supports"][0]
    c = r["cases"]
    assert r["service"]["P"] == pytest.approx(max(c.get("D", 0) + c.get("L", 0), c.get("D", 0) + c.get("Lr", 0), c.get("D", 0) + 0.75 * c.get("L", 0) + 0.75 * c.get("Lr", 0)))
    assert r["strength"]["name"].startswith("1.2D") and r["strength"]["P"] > r["service"]["P"]
