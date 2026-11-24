"""Reading StruCalc project files (.vtx).  The fixture below is cut down from a real StruCalc Pro 2.8.5 file: three members with the tags the reader uses."""
import pytest

from strukit import strucalc
from strukit.gui import calc, server


def _mod(name, kind, species, grade, steel, spans, loads, reactions, extra=""):
    sp = "".join(f"<Span><unbracedTop>{t}</unbracedTop><unbracedBottom>{e}</unbracedBottom><unbracedX>{ux}</unbracedX><unbracedY>{uy}</unbracedY><spanStart>{s}</spanStart><spanEnd>{e}</spanEnd></Span>"
                 for s, e, t, ux, uy in spans)
    ld = "".join(f"<Load><loadName>{n}</loadName><loadType>{t}</loadType><leftMag>{a}</leftMag><rightMag>{a}</rightMag><loadStart>{x1}</loadStart><loadEnd>{x2}</loadEnd>"
                 f"<combinationType>{c}</combinationType><loadAxis>{ax}</loadAxis></Load>" for n, t, a, x1, x2, c, ax in loads)
    rx = "".join(f"<Reaction><Name>R</Name><Location>{x}</Location><verticalBoundaryCondition>{v}</verticalBoundaryCondition></Reaction>" for x, v in reactions)
    return (f"<DesignModule><Name>{name}</Name><designModuleType>{kind}</designModuleType><calculationType>ASD</calculationType><DesignModuleObjects><DesignModuleObject>"
            f"<Material>Steel</Material><Species>{species}</Species><Grade>{grade}</Grade><steelGrade>{steel}</steelGrade><liveLoadDeflection>360</liveLoadDeflection>"
            f"<totalLoadDeflection>240</totalLoadDeflection><includeSelfWeight>True</includeSelfWeight><Spans>{sp}</Spans></DesignModuleObject></DesignModuleObjects>"
            f"<Reactions>{rx}</Reactions><MyAdequacy><Adequacy><isControlling>true</isControlling><adequacyName>Moment Y</adequacyName><adequacyMagnitude>25286.625</adequacyMagnitude>"
            f"<adequacyMagnitudeLabel>lbf-ft</adequacyMagnitudeLabel><adequacyStrength>33932.1367</adequacyStrength><adequacyCombinationLabel>D+L</adequacyCombinationLabel></Adequacy></MyAdequacy>"
            f"<Loads>{ld}</Loads>{extra}</DesignModule>")


VTX = ("<VitruviusProject><Design><Name>Test Job</Name><DesignModules>"
       + _mod("FloorBeamA", "Floor Beam", "W Shapes", "W8x15", "A992-50", [(0, 13, 0, 0, 0)], [("Uniform", "Uniform", 750, 0, 13, "Live", "Y"), ("Uniform", "Uniform", 432, 0, 13, "Dead", "Y")], [(0, 1), (13, 1)])
       + _mod("Column-A.1", "Column", "HSS Square", "HSS6x6x.375", "A500 Gr.B-46", [(0, 13, 0, 10, 1)],
              [("Axial", "Axial", -80000, 13, 13, "Dead", "Z"), ("Moment", "Moment", 21000, 13, 13, "Live", "Y")], [(0, 1), (13, 1)])
       + _mod("Cantilever", "Floor Beam", "HSS Square", "HSS2-1/2x2-1/2x.250", "A500 Gr.B-46", [(0, 0.5, 0, 0, 0), (0.5, 2.8333, 0, 0, 0)],
              [("Uniform", "Uniform", 625, 0, 2.8333, "Live", "Y"), ("Uniform", "Uniform", 360, 0, 2.8333, "Dead", "Y")], [(0, 1), (0.5, 1), (2.8333, 0)])
       + _mod("Angle", "Floor Beam", "L Shapes (Equal Legs)", "L8x8x3/4", "A36-36", [(0, 5, 0, 0, 0)], [("Point", "Point", 25000, 2.5, 2.5, "Live", "Y")], [(0, 1), (5, 1)])
       + _mod("Twist", "Floor Beam", "W Shapes", "W14x30", "A992-50", [(0, 15.5, 0, 0, 0)], [("Uniform", "Uniform", 675, 0, 11, "Live", "Y"), ("Moment", "Moment", 9000, 1, 1, "Live", "X")], [(0, 1), (15.5, 1)])
       + "</DesignModules></Design></VitruviusProject>")


def test_reads_a_strucalc_file(tmp_path):
    """Values are those of job 2026-001's mezzanine file: W8x15 13 ft with 750 + 432 lb/ft: StruCalc 25,286.6 lb-ft against 33,932.1 (AISC F2), deflection 0.5526 in.;
    HSS6x6x3/8 column, 80 kips dead and 21 kip-ft live at the top: StruCalc H1-1a = 0.9784; HSS2-1/2 cantilever 2.3333 ft past its support: w a^2 / 2."""
    p = tmp_path / "job.vtx"
    p.write_text(VTX, encoding="utf-8")
    d, notes = strucalc.convert(str(p))
    by = {m["values"]["mark"]: m for m in d["members"]}
    assert set(by) == {"FloorBeamA", "Column-A.1", "Cantilever", "Twist"} and d["project"]["method"] == "ASD" and len(d["project"]["combos_asd"]) == 13
    assert any("Angle" in n and "L8x8x3/4" in n for n in notes) and any("Twist" in n and "Moment load 9000" in n for n in notes) and len(notes) == 2
    b = by["FloorBeamA"]["values"]
    assert (b["shape"], b["Fy"], b["span"], b["bracing"], b["self_weight"]) == ("W8X15", "50", "13", "continuous", "yes")
    assert b["loads"] == [dict(case="L", kind="uniform", mag="0.75", x1="", x2="", label=""), dict(case="D", kind="uniform", mag="0.432", x1="", x2="", label="")]
    r = {x["check"]: x for x in calc.results("steel_beam", b, d["project"])["rows"]}
    assert r["flexure"].get("demand") == pytest.approx(25.2866, abs=0.001) and r["flexure"]["capacity"] == pytest.approx(33.932, abs=0.005)
    assert r["deflection, total"]["demand"] == pytest.approx(0.5526, abs=0.0005)
    assert d["strucalc"]["FloorBeamA"][0] == dict(name="Moment Y", demand=25286.625, strength=33932.1367, unit="lbf-ft", combo="D+L", controls=True)
    c = by["Column-A.1"]["values"]
    assert (c["shape"], c["Fy"], c["height"], c["end_ratio"]) == ("HSS6X6X3/8", "46", "13", "0") and float(c["Kx"]) == pytest.approx(10 / 13) and c["loads"][0]["P"] == "80"
    rc = {x["check"]: x for x in calc.results("hss_column", c, d["project"])["rows"]}
    assert rc["Compression and bending"]["demand"] == pytest.approx(0.9784, abs=0.0005)
    assert {x["check"]: x for x in calc.results("hss_column", dict(c, end_ratio=""), d["project"])["rows"]}["Compression and bending"]["demand"] == pytest.approx(1.175, abs=0.002)   # Cm = 1.0
    k = by["Cantilever"]["values"]
    assert (k["shape"], k["span"], k["more_spans"], k["oh_right"]) == ("HSS2-1/2X2-1/2X1/4", "0.5", "", "2.3333")
    rk = {x["check"]: x for x in calc.results("steel_beam", k, d["project"])["rows"]}
    assert rk["flexure"]["demand"] == pytest.approx((0.625 + 0.360 + 0.00704) * 2.3333 ** 2 / 2, rel=0.002)
    opened = server.api("/api/open", dict(path=str(p)))
    assert opened["path"] is None and opened["imported"] == "job.vtx" and len(opened["data"]["members"]) == 4 and len(opened["notes"]) == 2
    (tmp_path / "bad.vtx").write_text("not xml")
    with pytest.raises(strucalc.StruCalcError):
        strucalc.convert(str(tmp_path / "bad.vtx"))
