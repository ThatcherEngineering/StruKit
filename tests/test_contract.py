import json
import os

import pytest

from strukit import XDATA_APP, juris
from strukit.cli import main
from strukit.dxfin import read_entities
from strukit.outputs import write_results
from strukit.preflight import check
from strukit.sidecar import read_sidecar

PROJECT = """[project]
JURIS,PUEBLO
ADDRESS,8121 Suzie Dr; Rye CO
ELEV_FT,6800
RISK_CAT,I
ENCLOSURE,PARTIAL
EXPOSURE,C
SOIL_SOURCE,PRESUMPTIVE
DATUM_EL,100.0
METHOD,ASD
"""


def ent(kind, handle, keys, pts=((0, 0), (0, 12))):
    out = ["0", kind, "5", handle, "8", "S-FRAME"]
    for i, (x, y) in enumerate(pts[:2]):
        out += [str(10 + i), str(x), str(20 + i), str(y)]
    out += ["1001", XDATA_APP]
    for k, v in keys.items():
        out += ["1000", f"{k}={v}"]
    return out


def make_job(tmp_path, entities, project=PROJECT):
    dxf = tmp_path / "job-struct.dxf"
    lines = ["0", "SECTION", "2", "HEADER", "9", "$HANDLING", "70", "1", "0", "ENDSEC",
             "0", "SECTION", "2", "ENTITIES"]
    for e in entities:
        lines += e
    lines += ["0", "ENDSEC", "0", "EOF"]
    dxf.write_text("\r\n".join(lines) + "\r\n")
    (tmp_path / "job-struct.csv").write_text(project)
    return str(dxf)


GOOD_POST = dict(MARK="P1", TYPE="POST", SIZE="6x6", SPECIES="DF-L", GRADE="No.2")
GOOD_FTG = dict(FTG="F1", KIND="EMBEDDED", DIA_IN="24", EMBED_FT="4.5", CONSTRAINED="0",
                BACKFILL="CONCRETE", POST="P1")


def test_reader_gets_handles_keys_and_points(tmp_path):
    dxf = make_job(tmp_path, [ent("LINE", "2A", GOOD_POST)])
    (e,) = read_entities(dxf, XDATA_APP)
    assert e.handle == "2A" and e.keys["SIZE"] == "6x6" and len(e.points) == 2
    assert e.name == "P1 (handle 2A)"


def test_other_xdata_apps_are_ignored(tmp_path):
    raw = ["0", "CIRCLE", "5", "3B", "8", "X", "10", "0", "20", "0",
           "1001", "GDSTRUCT", "1000", "MARK=MH-1"]
    dxf = make_job(tmp_path, [raw])
    (e,) = read_entities(dxf, XDATA_APP)
    assert e.keys == {}


def test_preflight_lists_every_problem_with_its_object(tmp_path):
    bad = dict(MARK="R1", TYPE="RAFTER", SIZE="2x10", SUPPORT="B9")      # no species/grade/spacing
    ftg = dict(FTG="F2", KIND="SPREAD", W_FT="x", POST="P7")
    dxf = make_job(tmp_path, [ent("LINE", "10", bad), ent("CIRCLE", "11", ftg)],
                   project=PROJECT.replace("JURIS,PUEBLO\n", ""))
    project, _ = read_sidecar(dxf[:-4] + ".csv")
    problems, _ = check(project, read_entities(dxf, XDATA_APP))
    text = "\n".join(problems)
    for want in ["job record: missing key JURIS", "R1 (handle 10): missing key SPECIES",
                 "R1 (handle 10): missing key GRADE", "R1 (handle 10): missing key SPACING_IN",
                 "SUPPORT=B9 is not a mark", "F2 (handle 11): missing key L_FT",
                 "F2 (handle 11): missing key THICK_IN", "W_FT='x' is not a number",
                 "POST=P7 is not a mark"]:
        assert want in text


def test_preflight_clean_job_is_ok(tmp_path):
    dxf = make_job(tmp_path, [ent("LINE", "1", GOOD_POST), ent("CIRCLE", "2", GOOD_FTG)])
    assert main(["preflight", "--from-dxf", dxf, "--quiet"]) == 0
    log = (tmp_path / "strukit.log").read_text()
    assert log.splitlines()[0].startswith("OK ")
    assert json.loads((tmp_path / "strukit-status.json").read_text())["members"] == 1


def test_failed_run_keeps_previous_results_and_ignores_unknown_flags(tmp_path):
    dxf = make_job(tmp_path, [ent("LINE", "1", dict(MARK="P1"))])
    res = tmp_path / "job-stresults.csv"
    res.write_text("previous good results")
    code = main(["run", "--from-dxf", dxf, "--results", str(res), "--quiet", "--future-flag"])
    assert code == 2
    assert res.read_text() == "previous good results"
    assert (tmp_path / "strukit.log").read_text().startswith("FAILED ")
    assert not (tmp_path / "strukit.lock").exists()


def test_missing_sidecar_fails_with_a_plain_message(tmp_path):
    dxf = make_job(tmp_path, [ent("LINE", "1", GOOD_POST)])
    os.remove(dxf[:-4] + ".csv")
    assert main(["preflight", "--from-dxf", dxf, "--quiet"]) == 2
    assert "file not found" in (tmp_path / "strukit.log").read_text()


def test_results_file_format(tmp_path):
    path = str(tmp_path / "r.csv")
    write_results(path, "2026-046 Shed, Rye", [
        dict(KIND="MEMBER", ID="R1", HANDLE="2A", CHECK="bending", DEMAND=812.0, CAPACITY=1035.0,
             UNIT="psi", DC=0.7845, STATUS="OK", SOURCE="NDS 3.3", NOTE="a, b", EXTRA="x")])
    raw = open(path, "rb").read()
    lines = raw.decode("ascii").split("\r\n")
    assert lines[0] == "STRUKIT-RESULTS,1,2026-046 Shed; Rye"
    assert lines[1].startswith("KIND,ID,HANDLE,CHECK,COMBO") and lines[1].endswith(",EXTRA")
    assert lines[2] == "MEMBER,R1,2A,bending,,812,1035,psi,0.7845,OK,NDS 3.3,a; b,x"
    assert os.path.exists(path + ".done") and not os.path.exists(path + ".tmp")


def _juris_file(tmp_path, body, good_hash=True):
    h = juris.data_hash(body) if good_hash else "0" * 64
    p = tmp_path / "STRUKIT-JURIS.csv"
    head = "juris,key,risk_cat,elev_min_ft,elev_max_ft,value,unit,source,source_date,note"
    p.write_bytes(("\r\n".join([f"STRUKIT-JURIS,1,test,{h}", head] + body) + "\r\n").encode())
    return str(p)


BODY = ["DOUGLAS COUNTY,v_ult,II,,,115,mph,Pre-Submittal Handout,2026-06-01,",
        "DOUGLAS COUNTY,v_ult,III/IV,,,120,mph,Pre-Submittal Handout,2026-06-01,",
        "DOUGLAS COUNTY,snow,,6000,6499,35,psf,Pre-Submittal Handout,2026-06-01,",
        "DOUGLAS COUNTY,snow,,6500,6999,40,psf,Pre-Submittal Handout,2026-06-01,"]


def test_juris_lookup_by_risk_category_and_elevation(tmp_path):
    t = juris.load(_juris_file(tmp_path, BODY))
    assert juris.lookup(t, "Douglas County", "v_ult", risk_cat="IV")["value"] == "120"
    assert juris.lookup(t, "Douglas County", "snow", elev_ft=6185)["value"] == "35"
    assert juris.lookup(t, "Douglas County", "snow") is None           # no elevation: no guess
    assert juris.lookup(t, "PUEBLO", "snow", elev_ft=6185) is None     # never another agency's


def test_juris_refuses_an_edited_file_and_rows_without_a_source(tmp_path):
    with pytest.raises(juris.JurisError, match="hash"):
        juris.load(_juris_file(tmp_path, BODY, good_hash=False))
    with pytest.raises(juris.JurisError, match="source"):
        juris.load(_juris_file(tmp_path, ["X,frost,,,,36,in,,2026-01-01,"]))
