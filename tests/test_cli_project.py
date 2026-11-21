"""strukit preflight / run --from <project.strukit>: the run contract on a project file."""
import json
import os

from strukit.cli import main

PROJ = dict(name="Test", number="2026-000", address="", method="ASD", date="2026-11-21",
            combos=[dict(expr="D + L", source="typed")])
BEAM = dict(mark="B1", shape="W18x50", Fy="50", span="35", bracing="continuous", self_weight="yes",
            loads=[dict(case="D", kind="uniform", mag="0.45"), dict(case="L", kind="uniform", mag="0.75")], defl=[])
FTG = dict(mark="F-A", B="2.5", L="2.5", h="10", fc="3000", fy="60000", conc_pcf="145", col_x="4", col_y="4", supported="wood",
           plate_x="6", plate_y="6", bar="5", n_x="3", n_y="3", cover="3", bottom="x", P_service="7600", service_combo="D + L",
           Pu="12160", strength_combo="1.2D + 1.6L", q_allow="1500", soil_source="test report")


def write(tmp_path, members):
    p = tmp_path / "job.strukit"
    p.write_text(json.dumps(dict(format="strukit-project", version=1, project=PROJ, members=members)))
    return str(p)


def first_line(tmp_path):
    return (tmp_path / "strukit.log").read_text().splitlines()[0]


def test_run_writes_results_package_log_and_status(tmp_path):
    p = write(tmp_path, [dict(kind="steel_beam", values=BEAM), dict(kind="footing_iso", values=FTG)])
    assert main(["run", "--from", p, "--quiet"]) == 0
    assert first_line(tmp_path) == "OK job.strukit"
    res = (tmp_path / "job-stresults.csv").read_bytes().decode("ascii")
    lines = res.split("\r\n")
    assert lines[0] == "STRUKIT-RESULTS,1,2026-000" and lines[1].startswith("KIND,ID,HANDLE,CHECK,COMBO,DEMAND,CAPACITY,UNIT,DC,STATUS,SOURCE,NOTE")
    assert any(ln.startswith("MEMBER,B1,,flexure,D + L,") for ln in lines) and any(ln.startswith("FTG,F-A,,soil bearing pressure") for ln in lines)
    assert '"' not in res and (tmp_path / "job-stresults.csv.done").exists()
    assert (tmp_path / "job-calcs.pdf").read_bytes()[:5] == b"%PDF-"
    st = json.loads((tmp_path / "strukit-status.json").read_text())
    assert st["status"] == "OK" and st["exit"] == 0 and st["members"] == 2 and st["results"].endswith("job-stresults.csv")
    assert not (tmp_path / "strukit.lock").exists()


def test_flags_give_exit_1(tmp_path):
    p = write(tmp_path, [dict(kind="steel_beam", values=dict(BEAM, bracing="at points", brace_pts="17.5"))])
    assert main(["run", "--from", p, "--quiet"]) == 1
    assert first_line(tmp_path) == "SOLVED WITH FLAGS job.strukit"
    assert "FLAG B1: flexure" in (tmp_path / "strukit.log").read_text()


def test_preflight_lists_every_problem_and_a_failed_run_keeps_old_results(tmp_path):
    good = write(tmp_path, [dict(kind="steel_beam", values=BEAM)])
    assert main(["run", "--from", good, "--quiet"]) == 0
    before = (tmp_path / "job-stresults.csv").read_bytes()
    bad = write(tmp_path, [dict(kind="steel_beam", values=dict(BEAM, shape="", span="")),
                           dict(kind="footing_iso", values=dict(FTG, soil_source=""))])
    assert main(["preflight", "--from", bad, "--quiet"]) == 2
    log = (tmp_path / "strukit.log").read_text()
    assert log.startswith("FAILED job.strukit") and "PREFLIGHT: 3 input problem(s)" in log
    assert "B1: Section is blank" in log and "B1: Span is blank" in log and "F-A: Soil bearing source is blank" in log
    assert main(["run", "--from", bad, "--quiet"]) == 2
    assert (tmp_path / "job-stresults.csv").read_bytes() == before         # untouched


def test_preflight_ok_and_other_inputs(tmp_path):
    p = write(tmp_path, [dict(kind="steel_beam", values=BEAM)])
    assert main(["preflight", "--from", p, "--quiet"]) == 0 and first_line(tmp_path) == "OK job.strukit"
    assert not (tmp_path / "job-stresults.csv").exists()                   # preflight solves nothing
    (tmp_path / "x-struct.csv").write_text("# STRUKIT-INPUT,1,test\n")
    assert main(["run", "--from", str(tmp_path / "x-struct.csv"), "--quiet"]) == 2
    assert "not read yet" in (tmp_path / "strukit.log").read_text()
