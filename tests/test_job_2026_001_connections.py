"""Job 2026-001 mezzanine shear tabs, typed from sheets S2.0 to S2.2 (sealed 07/24/2026)."""
import json, os
from strukit.gui import calc

D = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_001_connections.strukit")))


def test_shear_tabs():
    over = {}
    for m in D["members"]:
        r = calc.results(m["kind"], m["values"], D["project"])
        assert r["state"] == "done", (m["values"]["mark"], r["messages"])
        for x in r["rows"]:
            if x["unit"] == "kip" and x["status"] != "OK":
                over[m["values"]["mark"].split(":")[0]] = (x["check"], round(x["capacity"], 1))
    assert len(D["members"]) == 20
    # with reactions taken off the framing plan, the only strength row over is the three-bolt W14x30 tab under FloorBeamD.3's 34.6 kips
    assert over == {"W14x30 three-bolt tab under the FloorBeamD.3 reaction": ("Bolt shear with eccentricity", 29.6)}


def test_coped_beams_pass():
    n = 0
    for m in D["members"]:
        if m["values"].get("cope_dc"):
            r = calc.results(m["kind"], m["values"], D["project"])
            cop = [x for x in r["rows"] if x["check"].startswith("Coped")]
            assert len(cop) == 4 and all(x["status"] == "OK" for x in cop), m["values"]["mark"]
            n += 1
    assert n == 7


def test_end_plates_pass():
    eps = [m for m in D["members"] if m["kind"] == "end_plate"]
    assert len(eps) == 6
    for m in eps:
        r = calc.results(m["kind"], m["values"], D["project"])
        assert r["state"] == "done" and r["status"] == "OK", m["values"]["mark"]
