"""Job 2026-011 (Humbargar Residence addition, 441 Senter Drive, Castle Rock) run whole, against its sealed StruCalc Pro package of 4/21/2026
(31 pages; 2024 IBC, ASCE 7-22, 2024 NDS, ACI 318-19).  The project file tests/data/job_2026_011.strukit holds the 15 members with the same sizes, spans and
loads.  Every check agrees with StruCalc within 0.6 percent except the ones listed in DIFFERENT, each with its reason."""
import json
import os

import pytest

from strukit.gui import calc

SC = {
 "RoofJoist": {"moment": (13765.7, 16312.5), "shear": (1850.5, 3187.5), "end reaction": (1850.9, 2375.0), "deflection, total": (1.721, 1.984)},
 "Roof Beam A": {"bending": (2240.2, 2803.3), "shear": (197.1, 285.0), "bearing at support": (520.0, 750.0), "deflection, total": (0.341, 0.563)},
 "Deck Column": {"compression": (200.4, 559.0)},
 "Floor Joist": {"moment": (2088.8, 3025.0), "shear": (562.5, 1625.0), "end reaction": (562.5, 1306.3), "deflection, live": (0.225, 0.495)},
 "Floor Beam A": {"bending": (873.1, 2721.2), "shear": (143.9, 285.0), "bearing at interior support": (719.1, 843.8), "deflection, live": (0.044, 0.303)},
 "Floor Beam B": {"bending": (2010.5, 2803.3), "shear": (132.6, 285.0), "bearing at support": (350.0, 750.0), "deflection, total": (0.544, 0.750)},
 "Floor Beam C": {"bending": (2083.2, 2803.3), "shear": (78.4, 285.0), "bearing at support": (206.9, 750.0), "deflection, live": (0.413, 0.483)},
 "Deck Joist": {"bending": (118.1, 1138.5), "shear": (20.2, 180.0), "bearing at support": (41.6, 625.0), "deflection, live": (0.005, 0.150)},
 "Column A": {"compression": (111.3, 421.1)}, "Column B": {"compression": (228.4, 421.1)},
 "Header A LL": {"bending": (990.8, 1080.0), "shear": (149.6, 180.0), "bearing at support": (241.1, 625.0), "deflection, total": (0.041, 0.200)},
 "Header B LL": {"bending": (952.2, 990.0), "shear": (146.8, 180.0), "bearing at support": (301.8, 625.0), "deflection, total": (0.048, 0.250)},
 "Deck Stud Pack": {"compression": (183.9, 612.8)},
 "Footing A": {"soil bearing pressure": (1336.8, 1500.0), "one-way shear, x direction": (3711.3, 19718.0), "two-way shear": (10314.4, 61454.5), "flexure, x direction": (2638.9, 26198.6),
               "bearing on footing": (12160.0, 119340.0)},
 "Continuous Footing": {"soil bearing pressure": (1488.5, 1500.0), "one-way shear": (519.0, 15774.4), "flexure": (297.2, 8816.2)},
}

# (member, check) -> why StruKit's number is not StruCalc's
DIFFERENT = {
    ("RoofJoist", "deflection, total"): "shear deflection included (ESR-1336) and 1/cos^2 on the slope",
    ("Floor Joist", "deflection, live"): "shear deflection included (ESR-1336)",
    ("Roof Beam A", "deflection, total"): "shear deflection included (ESR-1040 note 11)",
    ("Floor Beam B", "deflection, total"): "shear deflection included",
    ("Floor Beam C", "deflection, live"): "shear deflection included",
    ("Floor Beam A", "bending"): "live load on the worst arrangement of spans (ASCE 7-22 Sect. 4.3.3) and the moment at the support centre line",
    ("Floor Beam A", "shear"): "live load arrangement",
    ("Floor Beam A", "bearing at interior support"): "live load arrangement; the strength, 750 x Cb 1.125, is the same",
    ("Floor Beam A", "deflection, live"): "live load on one span alone",
    ("Deck Joist", "deflection, live"): "StruCalc prints 0.005 in. to three places",
    ("Footing A", "one-way shear, x direction"): "ACI 318-19 Table 22.5.5.1(c) at d from the plate, ruling of 2026-11-20",
    ("Footing A", "two-way shear"): "ACI 318-19 22.6 with the average d, ruling of 2026-11-20",
    ("Footing A", "flexure, x direction"): "bar depth",
    ("Continuous Footing", "one-way shear"): "ACI 318-19 as written, ruling of 2026-11-20",
    ("Continuous Footing", "flexure"): "stem wall weight in the factored load, ruling of 2026-11-21",
}


def test_whole_job_against_the_sealed_strucalc_package():
    data = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_011.strukit")))
    assert len(data["members"]) == 15 and {m["values"]["mark"] for m in data["members"]} == set(SC)
    same = 0
    for m in data["members"]:
        r = calc.results(m["kind"], m["values"], data["project"])
        assert r["state"] == "done" and r["status"] == "OK", (m["values"]["mark"], r.get("messages"))      # the sealed design passes in StruKit
        rows = {x["check"]: x for x in r["rows"]}
        for chk, (d, c) in SC[m["values"]["mark"]].items():
            x = rows[chk]
            if (m["values"]["mark"], chk) in DIFFERENT:
                continue
            assert x["demand"] == pytest.approx(d, rel=0.006), (m["values"]["mark"], chk)
            assert x["capacity"] == pytest.approx(c, rel=0.006), (m["values"]["mark"], chk)
            same += 1
    assert same == 33
    # the differences are all on the safe side or by ruling: StruKit's deflections and continuous-beam demands are not below StruCalc's
    for (mark, chk) in (("Roof Beam A", "deflection, total"), ("Floor Beam A", "bending"), ("Floor Beam A", "bearing at interior support"), ("RoofJoist", "deflection, total")):
        m = next(x for x in data["members"] if x["values"]["mark"] == mark)
        x = {y["check"]: y for y in calc.results(m["kind"], m["values"], data["project"])["rows"]}[chk]
        assert x["demand"] > SC[mark][chk][0]
