"""Force transfer around an opening, Diekmann technique, against APA's published design example (Force Transfer Around Openings design
examples, Ex. 3): 8 ft wall, 2.3 ft pier, 4 ft x 4 ft opening with 2 ft below, 4 ft pier, V = 2,000 lb."""
import pytest
from strukit import shearwall, ws_more

A = ("Sheathing, 7/16 in, 8d common", 6, "OSB", 0.5, 8.0, 2.3, 4.0, 4.0, 4.0, 2.0, 2000.0, "wind", "ASD")


def test_apa_example_3():
    w = shearwall.ftao(*A)
    assert w["H"] == pytest.approx(1553, abs=1) and w["vh"] == pytest.approx(317, abs=1) and w["vv"] == pytest.approx(388, abs=1)
    assert w["F"] == pytest.approx(1553, abs=2) and w["F1"] == pytest.approx(567, abs=2) and w["F2"] == pytest.approx(986, abs=2) and w["vc"] == pytest.approx(246, abs=1)


def test_limits_and_sheet():
    with pytest.raises(shearwall.ShearWallError, match="2 ft"):
        shearwall.ftao(*A[:5], 1.5, *A[6:])
    with pytest.raises(shearwall.ShearWallError, match="3.5"):
        shearwall.ftao(*A[:5], 2.0, 4.0, 2.0, 7.5, 0.0, 2000.0, "wind", "ASD")
    s = ws_more.ftao_wall_sheet("FT", A[0], A[1], A[2], A[3], "x", *A[4:], "x", above_T=500, above_source="wall above", holddown=dict(model="smallest HDUE or DTT that works"))
    r = {x.check: x for x in s.rows}
    assert r["hold-down tension"].demand == pytest.approx(2053, abs=1) and s.wall_T == pytest.approx(2053, abs=1)
    assert r["unit shear in the piers beside the opening"].capacity == pytest.approx(335.0)        # 670 / 2, piers under 2:1 against the 4 ft opening


def test_two_openings_published_example_20ft():
    """APA method for several openings (Technical Note T555) as worked in the published example (IIBEC Interface, Oct. 2018, and STRUCTURE):
    20 ft x 10 ft wall, V = 4,000 lb; piers 2, 4.5, 3.5 ft; openings 4 ft and 6 ft wide, 2 ft above and 3 ft below each.
    Published: H 2,000 lb; va 400 plf; O 1,600 / 2,400 lb; F 492, 1,108, 1,350, 1,050 lb; T 1.23, 2.77, 3.38, 2.63 ft; V 323, 473, 350 plf;
    R 646, 2,129, 1,225 lb; corner zones 77, -73, 50 plf; shear lines 2,000, 0, 0, 0, 0, 2,000 lb."""
    w = shearwall.ftao_multi("Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, 10.0, [2.0, 4.5, 3.5],
                             [dict(w=4.0, ho=5.0, sill=3.0), dict(w=6.0, ho=5.0, sill=3.0)], 4000.0, "wind", "ASD")
    assert w["H"] == pytest.approx(2000) and [o["va"] for o in w["openings"]] == pytest.approx([400, 400]) and [o["O"] for o in w["openings"]] == pytest.approx([1600, 2400])
    o1, o2 = w["openings"]
    assert [o1["F_left"], o1["F_right"], o2["F_left"], o2["F_right"]] == pytest.approx([492, 1108, 1350, 1050], abs=0.6)
    assert [o1["T_left"], o1["T_right"], o2["T_left"], o2["T_right"]] == pytest.approx([1.23, 2.77, 3.38, 2.63], abs=0.006)
    p = w["piers"]
    assert [x["v"] for x in p] == pytest.approx([323, 473, 350], abs=0.6) and [x["R"] for x in p] == pytest.approx([646, 2129, 1225], abs=1)
    assert [x["vc"] for x in p] == pytest.approx([77, -73, 50], abs=0.6)
    assert w["checks"] == pytest.approx([2000, 0, 0, 0, 0, 2000], abs=1e-6)
    assert sum(x["v"] * x["L"] for x in p) == pytest.approx(4000) and p[0]["reduction"] == pytest.approx(0.8)     # 2 ft pier beside a 5 ft opening


def test_two_openings_seaoc_2015():
    """Beebe and Skaggs, SEAOC 2015 Convention Proceedings, Figures 7 and 8: V = 3,750 lb, h = 8 ft, two windows. The dimensions are in the
    figures only; they follow from the printed values (piers 4, 4, 3.5 ft; openings 6 ft and 2 ft; ha + hb = 5-1/3 ft): H 1,538 lb, va 288 plf,
    O 1,731 / 577 lb, F 865, 865, 308, 269 lb, T 3, 3, 1.1, 0.9 ft, V 337, 388, 244 plf, R 1,346, 1,551, 853 lb, corner zones 120, 95, 167 plf."""
    w = shearwall.ftao_multi("Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, 8.0, [4.0, 4.0, 3.5],
                             [dict(w=6.0, ho=8 / 3, sill=4.0), dict(w=2.0, ho=8 / 3, sill=4.0)], 3750.0, "wind", "ASD")
    o1, o2 = w["openings"]
    assert w["H"] == pytest.approx(1538, abs=0.6) and o1["va"] == pytest.approx(288, abs=0.6) and [o1["O"], o2["O"]] == pytest.approx([1731, 577], abs=1)
    assert [o1["F_left"], o1["F_right"], o2["F_left"], o2["F_right"]] == pytest.approx([865, 865, 308, 269], abs=1)
    assert [o2["T_left"], o2["T_right"]] == pytest.approx([1.1, 0.9], abs=0.05)
    p = w["piers"]
    assert [x["v"] for x in p] == pytest.approx([337, 388, 244], abs=0.6) and [x["R"] for x in p] == pytest.approx([1346, 1551, 853], abs=1.5)
    assert [x["vc"] for x in p] == pytest.approx([120, 95, 167], abs=0.6)


def test_one_opening_agrees_with_the_one_opening_function():
    one = shearwall.ftao(*A)
    m = shearwall.ftao_multi(A[0], A[1], A[2], A[3], A[4], [2.3, 4.0], [dict(w=4.0, ho=4.0, sill=2.0)], 2000.0, "wind", "ASD")
    assert m["H"] == pytest.approx(one["H"]) and m["openings"][0]["va"] == pytest.approx(one["vv"])
    assert [x["v"] for x in m["piers"]] == pytest.approx([one["vh"]] * 2) and m["piers"][0]["vF"] == pytest.approx(one["vc"])
    assert m["piers"][0]["vc"] == pytest.approx(71, abs=0.6)                    # APA Ex. 3: 317 - 246 = 71 plf


def test_several_openings_on_the_sheet(tmp_path):
    from strukit import calcsheet
    s = ws_more.ftao_wall_sheet("FT", "Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, "DF-L", 10.0, 2.0, 4.0, 4.5, 5.0, 3.0, 4000.0, "wind", "ASD", "test",
                                more=[dict(w=6.0, ho=5.0, sill=3.0, pier=3.5)])
    names = [r.check for r in s.rows]
    assert "unit shear in pier 3 (3.5 ft)" in names and "corner zones of pier 2" in names and "unit shear above and below opening 2" in names
    cz = {r.check: r for r in s.rows}["corner zones of pier 2"]
    assert cz.demand == pytest.approx((1108 + 1350) / 4.5, abs=1)            # the larger of |R - F| / L and F / L
    assert s.wall_T == pytest.approx(2000) and s.title == "Wood Shear Wall, Force Transfer Around Openings"
    calcsheet.simple_pdf(s, str(tmp_path / "ft.pdf"), "Job", "SDPWS-2021", "Nov 25, 2026")
    with pytest.raises(Exception):
        ws_more.ftao_wall_sheet("FT", "Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, "DF-L", 10.0, 2.0, 4.0, 4.5, 5.0, 3.0, 4000.0, "wind", "ASD", "test",
                                more=[dict(w=6.0, ho=5.0, sill=3.0, pier=1.5)])


def test_deflection_one_and_two_openings(tmp_path):
    """Deflection by the APA pier method (SEAOC 2015; T555): each pier by SDPWS Eq. 4.3-1 at its own v and b, once each way, the average; every
    pier over the full wall height (Zach's ruling 2026-11-26, the more conservative reading). By hand for APA Example 3 and the 20 ft wall."""
    from strukit import calcsheet
    defl = dict(E=1.6e6, A=10.5, Da=0.1)
    s = ws_more.ftao_wall_sheet("FT", A[0], A[1], A[2], A[3], "x", *A[4:], "x", defl=defl)
    w = s.wall
    Ga = w["Ga"]
    EA = 1.6e6 * 10.5
    f = lambda v, h, b: 8 * v * h ** 3 / (EA * b) + v * h / (1000 * Ga) + h * 0.1 / b
    v = w["vh"]
    hand = [f(v, 8.0, 2.3), f(v, 8.0, 2.3), f(v, 8.0, 4.0), f(v, 8.0, 4.0)]       # every pier over the full wall height (Zach 2026-11-26)
    assert s.wall_defl["delta"] == pytest.approx(sum(hand) / 4, rel=1e-9) and Ga == pytest.approx(shearwall.TABLE_4_3A[shearwall.panel_key(A[0])][0][1])
    assert "deflection" not in s.not_checked and any(b["title"] == "Deflection" for b in s.blocks)
    assert "deflection" in ws_more.ftao_wall_sheet("FT", A[0], A[1], A[2], A[3], "x", *A[4:], "x").not_checked
    m = ws_more.ftao_wall_sheet("FT", "Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, "DF-L", 10.0, 2.0, 4.0, 4.5, 5.0, 3.0, 4000.0, "wind", "ASD", "test",
                                more=[dict(w=6.0, ho=5.0, sill=2.0, pier=3.5)], defl=defl)
    c = m.wall_defl["cases"]
    assert [x["h"] for x in c] == [10.0] * 6
    apa = shearwall.ftao_deflection(10.0, [dict(L=2.0, v=1, hb_right=3.0), dict(L=4.5, v=1, hb_left=3.0, hb_right=2.0), dict(L=3.5, v=1, hb_left=2.0)], 10.0, EA, 0.1)
    assert [x["h"] for x in apa["cases"]] == [7.0, 10.0, 8.0, 7.0, 10.0, 8.0]      # APA's heights, kept in the function, not used on the sheet
    assert m.wall_defl["delta"] == pytest.approx(sum(x["d"] for x in c) / 6)
    calcsheet.simple_pdf(m, str(tmp_path / "ftd.pdf"), "Job", "SDPWS-2021", "Nov 26, 2026")


def test_openings_of_different_heights_are_flagged(tmp_path):
    """APA T555 closes equilibrium for openings of one clear height (sills may differ: ha + hb is then the same). With different clear
    heights the shear lines beside the openings do not net zero, so the sheet flags the wall (no published method for openings of
    different heights is on file; see docs/REFERENCES.md)."""
    args = ("FT", "Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, "DF-L", 10.0, 2.0, 4.0, 4.5, 5.0, 3.0, 4000.0, "wind", "ASD", "test")
    m = ws_more.ftao_wall_sheet(*args, more=[dict(w=6.0, ho=6.5, sill=0.5, pier=3.5)])
    r = [x for x in m.rows if x.check.startswith("openings of one clear height")]
    assert len(r) == 1 and r[0].status == "FLAG" and r[0].demand == pytest.approx(1.5)
    w = shearwall.ftao_multi("Sheathing, 15/32 in, 8d common", 4, "OSB", 0.5, 10.0, [2.0, 4.5, 3.5],
                             [dict(w=4.0, ho=5.0, sill=3.0), dict(w=6.0, ho=6.5, sill=0.5)], 4000.0, "wind", "ASD")
    assert max(abs(c) for c in w["checks"][1:-1]) > 1.0                  # the lines beside the openings do not balance
    for sill in (3.0, 2.0):                                              # one clear height, sills equal or not: balanced, no flag
        same = ws_more.ftao_wall_sheet(*args, more=[dict(w=6.0, ho=5.0, sill=sill, pier=3.5)])
        assert not any(x.check.startswith("openings of one clear height") for x in same.rows)
