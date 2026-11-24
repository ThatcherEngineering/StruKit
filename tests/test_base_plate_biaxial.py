"""Base plate with biaxial bending: AISC Design Guide 1 (3rd Ed.) Example 4.7-14 (W8x48, Pu 90 kips, Mux 700, Muy 450 kip-in., 14 x 14 x 1-3/4 plate,
Grade 50, f'c 4 ksi, A2/A1 = 4, four 5/8 in. F1554 Grade 55 rods 1.5 in. from the edges)."""
import pytest
from strukit import ws_more
from strukit.gui import calc

V = dict(mark="BPX1", shape="W8X48", N="14", B="14", t="1.75", Fy="50", fc="4000", area_ratio="4", rod_d="0.625", rod_grade="F1554 Gr. 55", rod_edge="1.5", rod_side="1.5",
         cases=[dict(name="1.2D + 1.6L", P="90", Mx=str(700 / 12), My=str(450 / 12))])
PROJ = dict(job="t", name="t", method="LRFD", combos_lrfd=[dict(expr="1.2D + 1.6L", source="t")], combos_asd=[dict(expr="D + L", source="t")])


def test_example_4_7_14_strength_with_the_guides_rod_value():
    # the Guide takes 12.7 kips per rod (its Table 4-1): 2 x 12.7 = 25.4 kips on the tension side
    s = ws_more.biaxial_base_strength(90.0, 14.0, 14.0, 5.5, 3.76, 1.59, 4.42, 1.75, 50.0, 25.4)
    assert s["q"] == pytest.approx(61.9, abs=0.05) and s["Y"] == pytest.approx(1.86, abs=0.005) and s["M"] == pytest.approx(837, rel=0.005) and s["governs"] == "anchor rods"
    assert s["M_bearing"] == pytest.approx(437, rel=0.003) and s["M_plate"] == pytest.approx(482, rel=0.003) and s["T_plate"] == pytest.approx(303, rel=0.005)
    y = ws_more.biaxial_base_strength(90.0, 14.0, 14.0, 5.5, 3.76, 3.76 - 1.5, 4.42, 1.75, 50.0, 25.4)
    assert y["T_plate"] == pytest.approx(213, rel=0.005) and y["M"] == pytest.approx(837, rel=0.005)
    assert (700 / s["M"]) ** 2 + (450 / y["M"]) ** 2 == pytest.approx(0.988, abs=0.008)


def test_example_4_7_14_on_the_screen():
    s, kind, _ = calc.build("base_plate_biaxial", V, PROJ)
    b = s.biax
    assert b["fp"] == pytest.approx(4.42, abs=0.005) and b["m"] == pytest.approx(2.96, abs=0.005) and b["n"] == pytest.approx(3.76, abs=0.005)
    assert b["t_bear"] == pytest.approx(1.67, abs=0.01)                                  # 1.49 n (fp / Fy)^0.5
    # StruKit's rod strength is 0.75 x 0.75 Fu Ab (AISC 360-22 Table J3.2) = 12.9 kips against the Guide's 12.7: strengths 1 percent higher
    assert b["rt"] == pytest.approx(12.9, abs=0.06) and b["worst"]["sx"]["M"] == pytest.approx(837, rel=0.015) and b["worst"]["val"] == pytest.approx(0.988, abs=0.03)
    assert s.ok and [r.check for r in s.rows] == ["Plate thickness, bearing side", "Biaxial interaction"]
    thin = calc.build("base_plate_biaxial", dict(V, t="1.5"), PROJ)[0]
    assert thin.rows[0].status == "FLAG"
    over = calc.build("base_plate_biaxial", dict(V, cases=[dict(name="x", P="90", Mx="65", My="45")]), PROJ)[0]
    assert over.rows[1].status == "FLAG"
    with pytest.raises(Exception, match="axial tension"):
        calc.build("base_plate_biaxial", dict(V, cases=[dict(name="x", P="-5", Mx="10", My="10")]), PROJ)
    asd = calc.build("base_plate_biaxial", dict(V, cases=[dict(name="D + L", P="60", Mx="38", My="25")]), dict(PROJ, method="ASD"))[0]
    assert asd.biax["fp"] == pytest.approx(0.85 * 4 * 2 / 2.31) and asd.biax["worst"]["sx"]["M"] < s.biax["worst"]["sx"]["M"]


def test_frame_column_fills_the_biaxial_base_plate(tmp_path):
    import json, os
    d = json.load(open(os.path.join(os.path.dirname(__file__), "data", "job_2026_030_west.strukit")))
    got = calc.frame_base_biaxial(d["project"], d["members"], "C4B")
    assert got["method"] == "LRFD" and 2 <= len(got["rows"]) <= 4 and all({"name", "P", "Mx", "My"} <= set(r) for r in got["rows"])
    comp = [r for r in got["rows"] if r["P"] > 0]
    v = dict(mark="BPX2", shape="HSS8X8X1/2", N="16", B="16", t="1.25", Fy="50", fc="4000", area_ratio="1", rod_d="0.875", rod_grade="F1554 Gr. 36", rod_edge="1.5", rod_side="1.5",
             cases=[dict(name=r["name"], P=str(r["P"]), Mx=str(r["Mx"]), My=str(r["My"])) for r in comp])
    s = calc.build("base_plate_biaxial", v, d["project"])[0]
    assert len(s.rows) == 1 + len(comp) and s.blocks[-1]["picture"][0] == "base_biaxial"
    calc.package_pdf(dict(d["project"]), [dict(kind="base_plate_biaxial", values=v)], str(tmp_path / "b.pdf"), cover=False)
