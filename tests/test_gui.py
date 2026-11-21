"""The screen's bridge to the calculations, and the server's requests."""
import json
import os

import pytest

from strukit.gui import calc, server

PROJ = dict(name="Test", number="1", address="", method="ASD", date="2026-11-21",
            combos=[dict(expr="D + L", source="typed"), dict(expr="D + 0.6W", source="typed")])
BEAM = dict(mark="B1", shape="W18x50", Fy="50", span="35", bracing="at points", brace_pts="17.5", self_weight="yes",
            loads=[dict(case="D", kind="uniform", mag="0.45"), dict(case="L", kind="uniform", mag="0.75")],
            defl=[dict(label="live", expr="L", ratio="360", source="typed")])


def test_combination_text():
    assert calc.parse_expr("1.2D + 1.6L") == {"D": 1.2, "L": 1.6}
    assert calc.parse_expr("D+0.75L+0.45W") == {"D": 1.0, "L": 0.75, "W": 0.45}
    assert calc.parse_expr("0.6D - 0.6W") == {"D": 0.6, "W": -0.6}
    with pytest.raises(ValueError):
        calc.parse_expr("")
    with pytest.raises(ValueError):
        calc.parse_expr("1.2 & D")


def test_beam_matches_the_worksheet():
    r = calc.results("steel_beam", BEAM, PROJ)                 # AISC Example F.1-3 loads
    assert r["state"] == "done" and r["status"] == "FLAG"
    fl = next(x for x in r["rows"] if x["check"] == "flexure")
    assert fl["demand"] == pytest.approx(191.4, rel=1e-3) and fl["capacity"] == pytest.approx(191.3, rel=2e-3)


def test_blank_boxes_are_all_listed_and_nothing_is_assumed():
    r = calc.results("steel_beam", dict(mark="B2"), PROJ)
    assert r["state"] == "incomplete"
    for need in ("Section is blank", "Fy is blank", "Span is blank", "Add self-weight is blank"):
        assert need in r["messages"]
    r = calc.results("steel_beam", BEAM, dict(PROJ, method="", combos=[]))
    assert any("Design method" in m for m in r["messages"]) and any("No load combinations" in m for m in r["messages"])


def test_a_load_case_missing_from_every_combination_is_reported():
    v = dict(BEAM, loads=BEAM["loads"] + [dict(case="S", kind="uniform", mag="0.3")])
    r = calc.results("steel_beam", v, PROJ)
    assert r["state"] == "incomplete" and any("Load case S" in m for m in r["messages"])


def test_bad_section_stops_with_a_reason():
    r = calc.results("steel_beam", dict(BEAM, shape="W99x1"), PROJ)
    assert r["state"] == "stopped" and "W99x1" in r["messages"][0]


def test_column_frame_and_footings_run():
    col = dict(mark="C2", shape="W8X31", Fy="50", height="14", ends="free about x (cantilever, strong axis)", Kx="1", Ky="1",
               k_source="direct analysis", self_weight="yes", loads=[dict(case="D", P="4")],
               lateral=[dict(case="W", bending="x", kind="point", mag="4", x="14")], leaning=[], drift=[])
    r = calc.results("steel_column", col, PROJ)
    assert r["state"] == "done" and any(x["check"].startswith("drift amplification") for x in r["rows"])
    fr = dict(mark="F1", bays="30", stories="20", base="pin", roof="flat", col_shape="W12X65", beam_shape="W18X40", Fy="50",
              lb_col="20", lb_beam="5", self_weight="no", shape_of=[],
              loads=[dict(case="D", where="beams", kind="gravity per ft of member", mag="0.4"),
                     dict(case="L", where="beams", kind="gravity per ft of member", mag="1.2"),
                     dict(case="W", where="level:1", kind="lateral at level", mag="3")], leaning=[], drift=[])
    r = calc.results("frame", fr, PROJ)
    assert r["state"] == "done" and len(r["members"]) == 3 and r["frame"]["supports"] == {"N1-0": "pin", "N2-0": "pin"}
    ft = dict(mark="F-A", B="2.5", L="2.5", h="10", fc="3000", fy="60000", conc_pcf="145", col_x="4", col_y="4", supported="wood",
              plate_x="6", plate_y="6", bar="5", n_x="3", n_y="3", cover="3", bottom="x", P_service="7600", service_combo="D + L",
              Pu="12160", strength_combo="1.2D + 1.6L", q_allow="1500", soil_source="test report")
    r = calc.results("footing_iso", ft, PROJ)
    assert r["state"] == "done" and r["rows"][0]["demand"] == pytest.approx(1336.8, rel=1e-4)      # 2026-011 Footing A
    assert calc.results("footing_iso", dict(ft, soil_source=""), PROJ)["state"] == "incomplete"


def test_server_requests_save_open_and_print(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "APP_DIR", tmp_path / "app")
    monkeypatch.setattr(server, "SETTINGS", tmp_path / "app" / "settings.json")
    info = server.api("/api/info", {})
    assert set(info["forms"]) == {"steel_beam", "steel_column", "footing_iso", "footing_cont", "frame", "weld", "bolts"} and "W18X50" in info["shapes"]
    data = dict(format="strukit-project", version=1, project=PROJ, members=[dict(kind="steel_beam", values=BEAM)])
    p = str(tmp_path / "job.strukit")
    assert server.api("/api/save", dict(path=p, data=data))["path"] == p
    assert server.api("/api/open", dict(path=p))["data"]["members"][0]["values"]["mark"] == "B1"
    assert not os.path.exists(p + ".tmp") and server.load_settings()["recent"] == [p]
    (tmp_path / "x.strukit").write_text(json.dumps({"hello": 1}))
    with pytest.raises(ValueError):
        server.api("/api/open", dict(path=str(tmp_path / "x.strukit")))
    r = server.api("/api/pdf", dict(kind="steel_beam", values=BEAM, project=PROJ))
    f = server._pdfs[r["url"][5:-4]]
    assert open(f, "rb").read(5) == b"%PDF-"
    r = server.api("/api/package", dict(project=PROJ, members=data["members"] + [dict(kind="steel_beam", values=dict(mark="B9"))]))
    assert r["sheets"] >= 1 and r["skipped"] == ["B9"]
