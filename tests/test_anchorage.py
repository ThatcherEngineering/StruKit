"""Anchor rods in concrete, ACI 318-19 Chapter 17.

Independent references:
  - AISC Design Examples v16.0, Example I.8 (pages I-95, I-96): shear breakout parallel to
    an edge by ACI 318 Chapter 17: AVco = 450 in2 and Vb = 21.2 kips (welded studs,
    coefficient 8). Its AVc is for studs inside an encased column and is not comparable.
  - Tensile stress areas of coarse-thread rods (3/4-10: 0.334 in2; 1-8: 0.606 in2).
  - Hand calculations of the Code equations, written out below. No published worked
    example of a cast-in rod group in tension is on file.
"""
import math

import pytest

from strukit import anchorage as A
from strukit import calcsheet, ws_more
from strukit.ws_steel_beam import WorksheetError


def test_thread_area_matches_published_stress_areas():
    assert A.ase(0.75, 10) == pytest.approx(0.334, abs=0.001)
    assert A.ase(1.0, 8) == pytest.approx(0.606, abs=0.001)


def test_hex_bearing_area_is_hexagon_less_rod():
    assert A.hex_bearing_area(1.25, 0.75) == pytest.approx(0.8660 * 1.25 ** 2 - 0.4418, abs=0.001)


def test_single_rod_breakout_far_from_edges():
    # Nb = 24 sqrt(4000) 6^1.5 = 24 x 63.246 x 14.697 = 22,308 lb; ANc = ANco
    N, d = A.tension_breakout(6, 4000, 1, 0, 1, 0, 50, 50, 50, 50, 1.0)
    assert N == pytest.approx(22308, rel=1e-3)
    assert d["ANc"] == pytest.approx(9 * 36)
    # uncracked: psi_c,N = 1.25
    assert A.tension_breakout(6, 4000, 1, 0, 1, 0, 50, 50, 50, 50, 1.25)[0] == pytest.approx(1.25 * 22308, rel=1e-3)


def test_single_deep_rod_uses_eq_17_6_2_2_3():
    # 16 sqrt(4000) 12^(5/3) = 16 x 63.246 x 62.898 = 63,648 lb
    N, d = A.tension_breakout(12, 4000, 1, 0, 1, 0, 50, 50, 50, 50, 1.0)
    assert N == pytest.approx(63648, rel=1e-3)
    assert "17.6.2.2.3" in d["eq"]
    # a group keeps Eq. 17.6.2.2.1
    assert "17.6.2.2.1" in A.tension_breakout(12, 4000, 1, 0, 2, 6, 50, 50, 50, 50, 1.0)[1]["eq"]


def test_row_near_three_edges_uses_reduced_hef():
    # two rods 9 in apart, 7 in from the end, 10.5 in from each side, 23 in from the far end, hef 12:
    # three edges closer than 18 in -> hef = max(10.5/1.5, 9/3) = 7 (17.6.2.1.2)
    # ANc = (7 + 10.5)(10.5 + 9 + 10.5) = 525; ANco = 441; psi_ed = 0.7 + 0.3 x 7/10.5 = 0.9
    # Nb = 24 sqrt(3000) 7^1.5 = 24,346; Ncbg = 525/441 x 0.9 x 24,346 = 26,084 lb
    N, d = A.tension_breakout(12, 3000, 1, 0, 2, 9, 7, 23, 10.5, 10.5, 1.0)
    assert d["hef"] == pytest.approx(7.0)
    assert d["ANc"] == pytest.approx(525.0)
    assert d["psi_ed"] == pytest.approx(0.9)
    assert N == pytest.approx(26084, rel=1e-3)


def test_shear_breakout_parallel_to_edge_aisc_example_i8():
    # Example I.8: ca1 = 10 in, 3/4 in anchors, le = 3.63 in, f'c = 5,000 psi, uncracked (1.4):
    # AVco = 450 in2 and Vb = 21.2 kips with coefficient 8 (welded studs). This module uses 7
    # (Eq. 17.7.2.2.1a, rods not welded), so its Vb is 7/8 of the example's. The example's AVc is
    # for studs inside an encased column (the breakout face is the full 24 in column width), a
    # different geometry from rods at the top of a footing, so only the 15 + 40 + 15 length, the
    # doubling for shear parallel to the edge and the factor chain are compared.
    V, d = A.shear_breakout(10, 5, 10, 15, 15, 24, 0.75, 3.63, 5000, 1.4, parallel=True)
    assert d["AVco"] == pytest.approx(450)
    assert d["Vb"] * 8 / 7 / 1000 == pytest.approx(21.2, abs=0.05)
    assert d["AVc"] == pytest.approx((15 + 40 + 15) * 15)        # depth 1.5 ca1 for rods at the surface
    assert V == pytest.approx(2 * d["AVc"] / 450 * 1.4 * d["Vb"])


def test_shear_breakout_toward_edge_thin_narrow_member():
    # far row of the pattern above: ca1 = 23, sides 10.5, ha = 24: both less than 1.5 x 23, so
    # ca1 = max(10.5/1.5, 24/1.5, 9/3) = 16 (17.7.2.1.2); AVc = 30 x 24 = 720; AVco = 1,152
    # psi_ed = 0.7 + 0.3 x 10.5/24 = 0.831; Vb = 9 sqrt(3000) 16^1.5 = 31,549 (less than Eq. a)
    V, d = A.shear_breakout(23, 2, 9, 10.5, 10.5, 24, 0.75, 12, 3000, 1.0)
    assert d["ca1"] == pytest.approx(16)
    assert d["AVc"] == pytest.approx(720)
    assert d["Vb"] == pytest.approx(31549, rel=1e-3)
    assert V == pytest.approx(720 / 1152 * 0.83125 * 31549, rel=1e-4)


def test_thickness_factor():
    # ca1 = 10, ha = 9 < 15: psi_h = sqrt(15/9) = 1.291; AVc = 30 x 9
    V, d = A.shear_breakout(10, 1, 0, 40, 40, 9, 0.75, 6, 4000, 1.0)
    assert d["psi_h"] == pytest.approx(math.sqrt(15 / 9))
    assert d["AVc"] == pytest.approx(270)


def _pattern(**kw):
    a = dict(da=0.75, nt=10, futa=58, fya=36, ductile=True, hef=12, Abrg=0.911, fc=3000, ha=24, n=2, s_row=9,
             s_rows=16, c_end=7, c_side=10.5, cracked=True, supplementary=False, edge_reinf=0, grout=True,
             rows_in_shear=2)
    a.update(kw)
    return A.check(**a)


def _mode(r, key):
    return next(m for m in r.modes if m.key == key)


def test_pattern_strengths_and_factors():
    r = _pattern()
    assert _mode(r, "Nsa").Rn == pytest.approx(0.3345 * 58, rel=1e-3) and _mode(r, "Nsa").phi == 0.75
    assert _mode(r, "Ncb").Rn == pytest.approx(26.084, rel=1e-3) and _mode(r, "Ncb").phi == 0.70
    assert _mode(r, "Npn").Rn == pytest.approx(8 * 0.911 * 3.0, rel=1e-6) and _mode(r, "Npn").phi == 0.70
    # steel in shear: 0.6 Ase futa x 0.8 for the grout pad; phi 0.65
    assert _mode(r, "Vsa").Rn == pytest.approx(0.6 * 0.3345 * 58 * 0.8, rel=1e-3) and _mode(r, "Vsa").phi == 0.65
    # rows 16 in apart, 7 in from the edge: Case 1 (half on the near row) and Case 2 (all on the far row)
    assert _mode(r, "Vcb_case1").share == 0.5 and _mode(r, "Vcb_case2").share == 1.0
    assert _mode(r, "Vcb_case2").Rn == pytest.approx(16.391, rel=1e-3)
    # Case 2 puts the steel shear on the far row alone
    assert _mode(r, "Vsa").share == pytest.approx(0.5)
    # pryout: 2 x Ncbg of the four rods = 2 x (900/441 x 0.9 x 24.346) = 89.43
    assert _mode(r, "Vcp").Rn == pytest.approx(89.43, rel=1e-3)
    # no side-face blowout: hef 12 is not more than 2.5 x 7
    assert not [m for m in r.modes if m.key.startswith("Nsb")]


def test_factors_change_with_inputs():
    r = _pattern(ductile=False, supplementary=True, cracked=False, grout=False)
    assert _mode(r, "Nsa").phi == 0.65 and _mode(r, "Vsa").phi == 0.60
    assert _mode(r, "Ncb").phi == 0.75
    assert _mode(r, "Npn").Rn == pytest.approx(1.4 * 8 * 0.911 * 3.0)
    assert _mode(r, "Vsa").Rn == pytest.approx(0.6 * 0.3345 * 58, rel=1e-3)
    # futa is held to 1.9 fya and 125 ksi
    assert _mode(_pattern(futa=150, fya=105), "Nsa").Rn == pytest.approx(0.3345 * 125, rel=1e-3)
    assert _mode(_pattern(futa=75, fya=36), "Nsa").Rn == pytest.approx(0.3345 * 68.4, rel=1e-3)


def test_rows_closer_than_edge_distance_is_case_3():
    r = _pattern(c_end=20, s_rows=16)
    assert _mode(r, "Vcb_case3").share == 1.0
    assert _mode(r, "Vsa").share == pytest.approx(0.25)


def test_side_face_blowout_deep_rods_near_the_end():
    # c_end = 4, hef = 12 > 10: Nsb = 160 x 4 x sqrt(0.911) x sqrt(3000) = 33,458 lb
    # row of two at 9 in < 24: Nsbg = (1 + 9/24) x 33.458 = 46.00
    r = _pattern(c_end=4)
    assert _mode(r, "Nsb_end").Rn == pytest.approx((1 + 9 / 24) * 33.458, rel=1e-3)
    assert _mode(r, "Nsb_end").share == 1.0


def test_interaction_rule():
    r = _pattern()
    _, inter, rt, rv = A.demands(r, 2.0, 0.5)
    assert inter is None                                   # both ratios small: neglected (17.8.2)
    _, inter, rt, rv = A.demands(r, 15.0, 6.0)
    assert rt > 0.2 and rv > 0.2 and inter == pytest.approx(rt + rv)


def test_input_limits():
    with pytest.raises(A.AnchorageError):
        _pattern(hef=30)                                    # deeper than the concrete
    with pytest.raises(A.AnchorageError):
        _pattern(fc=12000)
    with pytest.raises(A.AnchorageError):
        _pattern(rows_in_shear=3)


# ---------------------------------------------------------------- on the base plate sheet
CASES = [dict(name="D + S", P=13.43, M=0.41, V=0.03), dict(name="D + 0.6W", P=4.43, M=34.51, V=2.40)]
FACT = [dict(name="1.2D + 1.6S + 0.5W", P=19.72, M=30.23, V=2.0), dict(name="0.9D + 1.0W", P=3.99, M=56.84, V=4.0)]


def _an(**kw):
    a = dict(hef=12, ha=24, nt=8, fya=36, ductile=True, Abrg=A.hex_bearing_area(1.625, 1.0), head="hex nut",
             cracked=True, supplementary=False, edge_reinf=0, grout=True, sdc="A or B")
    a.update(kw)
    return a


def _sheet(method="ASD", cases=CASES, fact=FACT, n_shear=4, an=None, support=(108, 72)):
    return ws_more.base_plate_moment_sheet("BP2", "W8X31", 20, 12, 1.75, 36, 3000, support, 1.0, 58, "typed in", 2, 2, 1.5,
                                           n_shear, cases, method, anchorage=_an() if an is None else an, cases_factored=fact)


def test_sheet_adds_anchorage_rows_at_factored_loads():
    s = _sheet()
    names = [r.check for r in s.rows]
    assert "ACI breakout, tension" in names and "ACI pullout" in names and "ACI pryout" in names
    r = next(r for r in s.rows if r.check == "ACI rod steel, tension")
    assert r.combo == "0.9D + 1.0W"                         # a factored case, not an ASD one
    # row tension by hand for 0.9D + 1.0W: fp = 0.65 x 0.85 x 3 x 2 = 3.315 ksi, q = 39.78 k/in,
    # drive = 56.84 x 12 + 3.99 x 8 = 714.0, arm = 18: Y = 18 - sqrt(324 - 2 x 714.0/39.78) = 1.0258
    # T = 39.78 x 1.0258 - 3.99 = 36.82; per rod 18.41
    assert r.demand == pytest.approx(18.41, abs=0.03)
    assert s.blocks and s.blocks[0]["picture"][0] == "anchorage"
    assert not any("Chapter 17" in t for t in s.not_checked)


def test_sheet_without_anchorage_lists_it_as_not_checked():
    s = ws_more.base_plate_moment_sheet("BP2", "W8X31", 20, 12, 1.75, 36, 3000, (108, 72), 1.0, 58, "typed in", 2, 2, 1.5,
                                        4, CASES, "ASD")
    assert any("Chapter 17" in t for t in s.not_checked) and not s.blocks


def test_sheet_stops_without_factored_cases_or_outside_scope():
    with pytest.raises(WorksheetError, match="LRFD"):
        _sheet(fact=None)
    with pytest.raises(WorksheetError, match="17.10"):
        _sheet(an=_an(sdc="C to F"))
    with pytest.raises(WorksheetError, match="counted on for shear"):
        _sheet(n_shear=3)
    with pytest.raises(WorksheetError, match="missing"):
        _sheet(an={k: v for k, v in _an().items() if k != "nt"})


def test_lrfd_project_uses_its_own_cases():
    s = _sheet(method="LRFD", cases=FACT, fact=None)
    assert any(r.check == "ACI breakout, tension" for r in s.rows)


def test_small_pier_flags_breakout(tmp_path):
    s = _sheet(support=(30, 30))
    r = next(r for r in s.rows if r.check == "ACI breakout, tension")
    assert r.status == "FLAG"
    out = calcsheet.simple_pdf(s, str(tmp_path / "bp.pdf"), "Job", "AISC 360-22, ACI 318-19", "Nov 21, 2026")
    assert (tmp_path / "bp.pdf").stat().st_size > 5000


# ---------------------------------------------------------------- on the screen
def _typed(**kw):
    v = dict(mark="BP2", shape="W8X31", N="20", B="12", t="1.75", Fy="36", fc="3000", full="no", sup_N="108", sup_B="72",
             rod_d="1", rod_Fu="58", rod_source="typed in", n_rods="2", rod_edge="2", rod_side="1.5", n_shear="4",
             anc_hef="12", anc_h="24", anc_F="1.625", anc_tpi="8", anc_fy="36", anc_ductile="yes", anc_cracked="cracked",
             anc_supp="no", anc_edge="none or smaller than No. 4", anc_grout="yes", anc_sdc="A or B",
             cases=[dict(name=c["name"], P=str(c["P"]), M=str(c["M"]), V=str(c["V"])) for c in CASES],
             cases_lrfd=[dict(name=c["name"], P=str(c["P"]), M=str(c["M"]), V=str(c["V"])) for c in FACT])
    v.update(kw)
    return v


PROJECT = dict(name="Job", number="1", address="", date="Nov 21, 2026", method="ASD",
               combos_asd=[dict(expr="D + S", source="typed in")], combos_lrfd=[dict(expr="1.2D + 1.6S", source="typed in")])


def test_screen_builds_anchorage_and_names_blank_boxes():
    from strukit.gui import calc
    s, kind, _ = calc.build("base_plate_moment", _typed(), PROJECT)
    assert kind == "simple" and any(r.check == "ACI pullout" for r in s.rows)
    assert "1.625 in across flats" in s.blocks[0]["info"][0][1]
    with pytest.raises(calc.Missing) as e:
        calc.build("base_plate_moment", _typed(anc_fy="", anc_sdc="", anc_cracked="", cases_lrfd=[]), PROJECT)
    msg = str(e.value)
    assert "Fy" in msg and "Seismic Design Category is blank" in msg
    assert "service load is blank" in msg and "factored (LRFD) load cases" in msg
    with pytest.raises(calc.Missing, match="not both"):
        calc.build("base_plate_moment", _typed(anc_abrg="1.5"), PROJECT)


def test_screen_takes_rod_data_from_design_guide_1_tables():
    from strukit.gui import calc
    v = _typed(rod_grade="F1554 Gr. 36", rod_Fu="", rod_source="", anc_F="", anc_tpi="", anc_fy="", anc_ductile="")
    s, _, _ = calc.build("base_plate_moment", v, PROJECT)
    info = s.blocks[0]["info"][0][1]
    assert "Abrg = 1.500 in2" in info and "Design Guide 1 Table 4-2" in info and "8 threads per inch" in info
    assert "Fy = 36 ksi" in info and "ductile" in info
    assert any("Design Guide 1" in t and "Table 2-2" in t for _, t in s.info)
    # a diameter outside the table needs the thread and head data typed
    with pytest.raises(calc.Missing, match="not in the Design Guide 1 table"):
        calc.build("base_plate_moment", dict(v, rod_d="1.1"), PROJECT)


def test_screen_leaves_anchorage_out_when_embedment_is_blank():
    from strukit.gui import calc
    s, _, _ = calc.build("base_plate_moment", _typed(anc_hef="", cases_lrfd=[]), PROJECT)
    assert not s.blocks and any("Chapter 17" in t for t in s.not_checked)


def test_sheet_notes_are_factual_not_a_design_log():
    # Zach, 2026-11-23: report sheets read professional and factual; rulings and the reasons for
    # choosing one reading over another stay in the rulings file, never on the sheet
    s = _sheet(an=_an(hef=14))
    text = " ".join(s.assumptions + s.not_checked + [r.note for r in s.rows]).lower()
    for phrase in ("would give", "thatcher engineering standard", "ruled", "on file", "lower value", "is not used for"):
        assert phrase not in text
