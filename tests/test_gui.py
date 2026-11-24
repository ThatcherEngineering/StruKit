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
    r = calc.results("steel_beam", BEAM, dict(PROJ, method=""))
    assert any("Design method" in m for m in r["messages"])
    r = calc.results("steel_beam", BEAM, dict(PROJ, combos=[]))
    assert any("No ASD load combinations" in m for m in r["messages"])
    new = dict(name="T", number="1", method="LRFD", date="2026-11-21", combos_asd=PROJ["combos"], combos_lrfd=[])
    r = calc.results("steel_beam", BEAM, new)                                    # ASD list only, LRFD asked for
    assert any("No LRFD load combinations" in m for m in r["messages"])


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
    assert set(info["forms"]) == {"steel_beam", "steel_column", "footing_iso", "footing_cont", "frame", "weld", "bolts", "stair_tread", "single_plate", "base_plate", "base_plate_moment", "footing_moment", "snow", "wood_beam", "decking", "wood_post", "shear_wall", "lvl_beam", "lvl_post", "glulam_beam", "wey_beam", "ijoist", "wey_post", "builtup_post", "perforated_wall", "snow_drift", "snow_corner", "rain_load", "guard", "hss_column", "stair_stringer", "glulam_post", "wind_pressure", "wind_free_roof", "wind_kzt", "wind_mwfrs", "wind_cc_walls", "wind_cc_roof", "wind_cc_parapet", "seismic_elf", "live_load", "diaphragm", "collector", "nailed_connection", "nail_withdrawal", "lag_connection", "lag_withdrawal", "screw_connection", "screw_withdrawal", "bolted_connection"} and "W18X50" in info["shapes"]
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


def test_base_plate_and_footing_with_moment_on_the_screen(tmp_path):
    bp = dict(mark="BP1", shape="W12X96", N="22", B="22", t="1.75", Fy="50", fc="3000", full="no", sup_N="24", sup_B="24",
              loads=[dict(case="D", P="115"), dict(case="L", P="345")])
    r = calc.results("base_plate", bp, PROJ)                    # AISC Example J.6, ASD: 583 kips, t min 1.54 in
    assert r["state"] == "done" and r["status"] == "OK"
    assert r["rows"][0]["capacity"] == pytest.approx(583, rel=5e-3) and r["rows"][1]["demand"] == pytest.approx(1.54, abs=0.006)
    assert calc.results("base_plate", dict(bp, t="1.5"), PROJ)["status"] == "FLAG"
    assert any("Support length" in m for m in calc.results("base_plate", dict(bp, sup_N=""), PROJ)["messages"])
    fm = dict(mark="FM1", B="9", L="6", h="24", fc="3000", fy="60000", conc_pcf="150", col_x="14", col_y="12", supported="steel",
              bar="6", n_x="8", n_y="11", cover="3", bottom="x", q_allow="2000", soil_source="test report",
              ot_required="1.5", limits_source="test",
              service=[dict(name="D + 0.6W", P="4400", M="33600", V="2400")],
              strength=[dict(name="0.9D + 1.0W", P="3600", M="56000", V="4000", wt_factor="0.9")])
    r = calc.results("footing_moment", fm, PROJ)
    assert r["state"] == "done" and any(x["check"] == "overturning" for x in r["rows"])
    assert any("sliding" in n for n in r["not_checked"])
    assert any("Source of those limits" in m for m in calc.results("footing_moment", dict(fm, limits_source=""), PROJ)["messages"])
    assert any("No factored load case" in m for m in calc.results("footing_moment", dict(fm, strength=[]), PROJ)["messages"])
    n, skipped = calc.package_pdf(PROJ, [dict(kind="base_plate", values=bp), dict(kind="footing_moment", values=fm)],
                                  str(tmp_path / "p.pdf"))
    assert n >= 2 and not skipped


def test_base_reactions_for_footings():
    P = dict(name="T", number="1", method="ASD", date="2026-11-21",
             combos_asd=[dict(expr="D + S", source="t"), dict(expr="D + 0.6W", source="t")],
             combos_lrfd=[dict(expr="1.2D + 1.6S", source="t"), dict(expr="0.9D + 1.0W", source="t")])
    col = dict(mark="C2", shape="W8X31", Fy="50", height="14", ends="free about x (cantilever, strong axis)", Kx="1", Ky="1",
               k_source="direct analysis", self_weight="no", loads=[dict(case="D", P="4"), dict(case="S", P="9")],
               lateral=[dict(case="W", bending="x", kind="point", mag="4", x="14")], leaning=[], drift=[])
    r = calc.reactions("steel_column", col, P)
    sv = {x["name"]: x for x in r["service"]}
    st = {x["name"]: x for x in r["strength"]}
    assert sv["D + S"]["P"] == pytest.approx(13000) and sv["D + 0.6W"]["V"] == pytest.approx(2400)
    assert sv["D + 0.6W"]["M"] > 2400 * 14                    # second-order: more than V x height
    assert sv["D + 0.6W"]["M"] < 2400 * 14 * 1.1
    assert sv["D + S"]["M"] > 0                               # the notional load of a gravity-only combination
    assert st["0.9D + 1.0W"]["wt_factor"] == 0.9 and st["1.2D + 1.6S"]["P"] == pytest.approx(1.2 * 4000 + 1.6 * 9000)
    assert "Loads can be taken" in calc.reactions("steel_beam", {}, P)["error"]
    only_asd = dict(P, combos_lrfd=[])
    r = calc.reactions("steel_column", col, only_asd)
    assert r["service"] and not r["strength"] and any("LRFD" in m for m in r["messages"])


def test_package_has_a_cover_with_contents(tmp_path):
    import subprocess
    members = [dict(kind="steel_beam", values=BEAM), dict(kind="steel_beam", values=dict(mark="B9"))]
    p = str(tmp_path / "pkg.pdf")
    n, skipped = calc.package_pdf(PROJ, members, p)
    assert n >= 2 and skipped == ["B9"]
    try:
        t = subprocess.run(["pdftotext", "-layout", "-l", "1", p, "-"], capture_output=True, text=True, timeout=30).stdout
    except FileNotFoundError:
        return
    assert "Structural Calculations" in t and "Engineer's seal" in t and "Sheet 1 of" in t
    assert "Members Not Included" in t.title() and "B9" in t and "D + L" in t
    assert "Flagged Checks" in t.title() or "No check in this package is flagged" in t


def test_base_plate_with_moment_on_the_screen():
    v = dict(mark="BP2", shape="W8X31", N="20", B="12", t="1.5", Fy="36", fc="3000", full="no", sup_N="30", sup_B="30",
             rod_d="1", rod_Fu="58", rod_source="ASTM F1554 Grade 36 (typed)", n_rods="2", rod_edge="2", rod_side="1.5",
             n_shear="2", cases=[dict(name="D + S", P="13.43", M="0.41", V="0.03"), dict(name="D + 0.6W", P="4.43", M="34.51", V="2.40")])
    r = calc.results("base_plate_moment", v, PROJ)
    assert r["state"] == "done" and r["status"] == "OK"
    assert {x["check"] for x in r["rows"]} >= {"plate thickness", "anchor rod tension", "anchor rod shear", "bearing block length"}
    assert any("Chapter 17" in n for n in r["not_checked"])
    assert calc.results("base_plate_moment", dict(v, t="1.25"), PROJ)["status"] == "FLAG"
    assert any("Anchor rod grade" in m for m in calc.results("base_plate_moment", dict(v, rod_source=""), PROJ)["messages"])
    stop = calc.results("base_plate_moment", dict(v, cases=[dict(name="U", P="-50", M="1", V="0")]), PROJ)
    assert stop["state"] == "stopped" and "uplift" in stop["messages"][0]
