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


def _chain():
    import copy
    ms = copy.deepcopy(D11["members"])
    g = lambda mark: next(m for m in ms if m["values"]["mark"] == mark)
    g("Column B")["values"]["loads"] = [dict(case="D", P="0", label="x", link=dict(src="Floor Beam C", support="left support", count=1))]
    g("Footing A")["values"]["link"] = dict(src="Column B", support="base", count=1)
    g("Floor Beam C")["values"]["loads"].append(dict(case="D", kind="point", mag="0", mag2="", x1="3", x2="", label="x", link=dict(src="Deck Joist", support="left support", count=2, x="3")))
    return ms, g


def test_takedown_runs_top_down():
    ms, g = _chain()
    out = calc.takedown(D11["project"], ms)
    assert out["problems"] == [] and [l["target"] for l in out["links"]] == ["Floor Beam C", "Column B", "Footing A"]
    new = {m["values"]["mark"]: m["values"] for m in out["members"]}
    joist = calc.case_reactions("wood_beam", g("Deck Joist")["values"], D11["project"])["supports"][0]["cases"]
    pts = [r for r in new["Floor Beam C"]["loads"] if r.get("link")]
    assert {r["case"]: float(r["mag"]) for r in pts} == {c: round(v * 2) for c, v in joist.items() if abs(v) >= 0.5} and pts[0]["label"].endswith("x 2")
    beam = calc.case_reactions("lvl_beam", new["Floor Beam C"], D11["project"])["supports"][0]
    post = {r["case"]: float(r["P"]) for r in new["Column B"]["loads"]}
    assert post == {c: round(v) for c, v in beam["cases"].items()}                       # the post sees the beam WITH the joists just added
    base = calc.case_reactions("builtup_post", new["Column B"], D11["project"])["supports"][0]
    assert float(new["Footing A"]["P_service"]) == round(base["service"]["P"]) and new["Footing A"]["loads_from"] == "reaction of Column B, base"
    again = calc.takedown(D11["project"], out["members"])                                # running it twice changes nothing
    assert again["members"] == out["members"]
    for m in out["members"]:
        assert calc.results(m["kind"], m["values"], D11["project"])["state"] == "done", m["values"]["mark"]


def test_takedown_problems():
    ms, g = _chain()
    g("Deck Joist")["values"]["loads"].append(dict(case="D", kind="point", mag="0", mag2="", x1="1", x2="", label="x", link=dict(src="Floor Beam C", support="left support", count=1, x="1")))
    out = calc.takedown(D11["project"], ms)
    assert out["problems"] and "circle" in out["problems"][0] and out["members"] is ms
    ms, g = _chain()
    g("Column B")["values"]["loads"][0]["link"]["src"] = "Gone"
    out = calc.takedown(D11["project"], ms)
    assert any("no longer in the project" in p_ for p_ in out["problems"])


def test_row_of_joists_as_a_line_load():
    import copy
    ms = copy.deepcopy(D11["members"])
    g = lambda mark: next(m for m in ms if m["values"]["mark"] == mark)
    j = g("Floor Joist")["values"]
    g("Floor Beam B")["values"]["loads"].append(dict(case="D", kind="uniform", mag="0", mag2="", x1="", x2="", label="",
                                                    link=dict(src="Floor Joist", support="left support", count=1, mode="line", spacing_in=float(j["spacing"]))))
    out = calc.takedown(D11["project"], ms)
    assert out["problems"] == []
    rows = [r for r in next(m for m in out["members"] if m["values"]["mark"] == "Floor Beam B")["values"]["loads"] if r.get("link")]
    R = calc.case_reactions("ijoist", j, D11["project"])["supports"][0]["cases"]
    assert rows and all(r["kind"] == "uniform" for r in rows)
    assert {r["case"]: float(r["mag"]) for r in rows} == {c: round(v * 12 / float(j["spacing"]), 1) for c, v in R.items() if abs(v) >= 0.5}
    assert "as a line at 16 in. o.c." in rows[0]["label"]
