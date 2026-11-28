"""Simpson Strong-Tie face-mount joist hangers (simpson.facemount): catalog C-C-2026 tables read into data/simpson_facemount.json.
The rows below were copied by hand from the catalog pages (pp. 114, 115, 119) and must match the data file; the adjustment factors
are the catalog's (p. 26 and p. 112: 2x carrying member 0.64 / 0.77; p. 110: end grain 0.67)."""
import pytest

from strukit import simpson
from strukit.gui import calc

HAND = [  # species, joist, model, nailing, uplift, floor, snow, roof, page
    ("DF/SP", "2x8", "LUS28", "", 1165, 1100, 1260, 1350, 114),
    ("DF/SP", "2x6", "HUS26", "", 1320, 2735, 3095, 3230, 114),
    ("DF/SP", "DBL 2x6", "HU26-2 / HUC26-2", "Max.", 1135, 1785, 2015, 2165, 114),
    ("DF/SP", "2x10", "HUS210", "", 2635, 5450, 5795, 5830, 115),
    ("DF/SP", "2x10", "HGUS210", "", 2090, 9100, 9100, 9100, 115),
    ("DF/SP", "DBL 2x10", "HU210-2 / HUC210-2", "Max.", 1895, 2680, 3020, 3250, 115),
    ("DF/SP", "DBL 2x10", "HUCQ210-2-SDS", "", 2345, 4315, 4315, 4315, 115),
    ("SPF/HF", "2x8", "LUS28", "", 1000, 945, 1085, 1160, 119),
    ("SPF/HF", "2x10", "LUS28", "", 1000, 945, 1085, 1160, 120),
    ("SPF/HF", "2x10", "HGUS210", "", 1545, 6340, None, None, 120),
]


@pytest.mark.parametrize("sp,joist,model,nail,up,fl,sn,rf,page", HAND)
def test_table_rows_match_the_catalog(sp, joist, model, nail, up, fl, sn, rf, page):
    rows = [r for r in simpson.facemount_rows() if r["species"] == sp and r["joist"] == joist and r["model"] == model and r["nailing"] == nail]
    assert rows, (sp, joist, model)
    r = rows[0]
    assert (r["uplift"], r["floor"], r["page"]) == (up, fl, page) and (sn is None or (r["snow"], r["roof"]) == (sn, rf))


def test_every_row_is_complete():
    rows = simpson.facemount_rows()
    assert len(rows) == 416 and all(r["joist"] and r["model"] and r["ga"] and r["W"] > 0 and r["H"] > 0 and r["B"] > 0 and r["header"] and r["joist_fast"]
                                   and r["uplift"] is not None and r["floor"] > 0 for r in rows)
    assert {"DF/SP", "SPF/HF"} == {r["species"] for r in rows}


def test_choice_and_adjustments():
    """2x8 DF/SP, 900 lb floor: LUS26 (865) and LU26 (835) fall short; LUS28 (1,100) is the first in the table that carries it.
    On a 2x header: LUS28 has 0.148 x 3 header nails, x 0.77 = 847 lb; HU210-2 (0.162 nails) x 0.64; end grain x 0.67."""
    h = simpson.facemount("2x8", "DF/SP", "lightest that works", 900, "floor (100)")
    assert h["row"]["model"] == "LUS28" and h["allow_down"] == 1100
    t = simpson.facemount("2x8", "DF/SP", "LUS28", 800, "floor (100)", two_by=True)
    assert t["factor"] == pytest.approx(0.77) and t["allow_down"] == pytest.approx(0.77 * 1100)
    u = simpson.facemount("DBL 2x10", "DF/SP", "HU210-2", 800, "roof (125)", uplift=500, two_by=True, nailing="Min.")
    assert u["row"]["nailing"] == "Min." and u["factor"] == pytest.approx(0.64) and u["allow_up"] == pytest.approx(0.64 * 1135)
    e = simpson.facemount("2x10", "DF/SP", "HUS210", 800, "snow (115)", end_grain=True)
    assert e["allow_down"] == pytest.approx(0.67 * 5795)
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("DBL 2x10", "DF/SP", "HUCQ210-2-SDS", 800, "floor (100)", two_by=True)
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x8", "DF/SP", "LUS210", 800, "floor (100)")
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x8", "DF/SP", "lightest that works", 50000, "floor (100)")


def test_on_the_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="JH1", joist="2x10", species="DF/SP", model="lightest that works", download="1200", duration="floor (100)", uplift="300",
             carrying="3x or larger, or a beam", load_source="joist J1")
    s = calc.build("joist_hanger", v, proj)[0]
    assert s.hanger["row"]["model"] == "LUS210" and all(r.status == "OK" for r in s.rows)
    with pytest.raises(calc.Missing):
        calc.build("joist_hanger", dict(v, load_source=""), proj)
    for vv in (v, dict(v, joist="DBL 2x10", model="HU210-2", nailing="Min.", carrying="2x (header nails shortened)"), dict(v, joist="6x12", model="lightest that works")):
        s = calc.build("joist_hanger", vv, proj)[0]
        calcsheet.simple_pdf(s, str(tmp_path / f"jh_{vv['joist'].replace(' ', '')}.pdf"), "Job", "Simpson C-C-2026", "Nov 26, 2026")


TF_HAND = [  # species, joist, model, uplift, floor, snow, roof, TF, page (catalog pp. 142, 146)
    ("DF/SP", "2x4", "PF24", 300, 1255, 1255, 1255, 1.0625, 142),
    ("DF/SP", "2x6", "JB26", 0, 995, 995, 995, 1.3125, 142),
    ("DF/SP", "DBL 2x10", "HUS210-2TF", 2315, 3735, 4065, 4275, 1.5, 142),
    ("DF/SP", "2x10", "BA210 (Max.)", 1275, 4720, 4720, 4720, 2.5, 142),
    ("SPF/HF", "4x14", "WP414", 0, 2230, 2230, 2230, 2.1875, 146),
]


@pytest.mark.parametrize("sp,joist,model,up,fl,sn,rf,tf,page", TF_HAND)
def test_top_flange_rows_match_the_catalog(sp, joist, model, up, fl, sn, rf, tf, page):
    rows = [r for r in simpson.rows_of("topflange") if r["species"] == sp and r["joist"] == joist and r["model"] == model]
    assert rows, (sp, joist, model)
    r = rows[0]
    assert (r["uplift"], r["floor"], r["snow"], r["roof"], r["TF"], r["page"]) == (up, fl, sn, rf, tf, page)


def test_top_flange_choice_and_limits(tmp_path):
    """2x10 DF/SP, 1,500 lb floor and 200 lb uplift: JB210A (260 / 1,685 lb, p. 142) is the first top-flange model that carries both;
    a hanger with "—" uplift is not chosen when there is uplift; a 2x nailer or end grain is not covered."""
    h = simpson.facemount("2x10", "DF/SP", "lightest that works", 1500, "floor (100)", 200, kind="topflange")
    assert h["row"]["model"] == "JB210A" and h["allow_up"] == 260
    j = simpson.facemount("2x6", "DF/SP", "lightest that works", 900, "floor (100)", 100, kind="topflange")
    assert j["row"]["model"] != "JB26" and j["allow_up"] >= 100
    assert simpson.facemount("2x10", "DF/SP", "BA210", 4000, "roof (125)", kind="topflange")["allow_down"] == 4720
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x10", "DF/SP", "JB210A", 1000, "floor (100)", two_by=True, kind="topflange")
    from strukit import calcsheet
    v = dict(mark="JH4", type="top flange", joist="2x10", species="DF/SP", model="lightest that works", download="1500", duration="floor (100)",
             uplift="200", carrying="3x or larger, or a beam", load_source="joist J2")
    s = calc.build("joist_hanger", v, dict(job="t", name="t", method="ASD"))[0]
    assert "top flange" in s.title and all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "tf.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_hurricane_tie_rows_against_the_catalog_page():
    """Every tie row (catalog p. 300, copied by hand into simpson.TIES) must appear in the page text: its DF/SP uplift, F1, F2 and
    SPF/HF uplift, F1, F2 in order on one line (the uplift-with-0.131 column between them)."""
    import re
    import subprocess
    from pathlib import Path
    pdf = Path("/mnt/user-data/uploads/StrucutralDesign/Simpson/C-C-2026.pdf")
    if not pdf.exists():
        pytest.skip("catalog not staged in this session")
    t = subprocess.run(["pdftotext", "-layout", "-f", "300", "-l", "300", str(pdf), "-"], capture_output=True, text=True).stdout
    f = lambda v: "—" if v is None else f"{v:,}"
    for tie in simpson.TIES:
        d_, s_ = tie[5], tie[6]
        pat = r"\s+".join([re.escape(f(v)) for v in d_] + [r"\S+"] + [re.escape(f(v)) for v in s_])
        assert re.search(pat, t), tie[0]


def test_hurricane_tie_choice_and_unity():
    """DF/SP, uplift 600, F1 150: H1A to H3 fail a direction; H7Z 600/830 + 150/410 = 1.09 and H10A field bent 600/780 + 150/565 = 1.03
    fail the unity equation (p. 289, Option 1); H10A (1,040 / 565) gives 0.577 + 0.265 = 0.842."""
    h = simpson.hurricane_tie("first that works", "DF/SP", 600, 150)
    assert h["tie"][0] == "H10A" and h["rows"][-1][1] == pytest.approx(600 / 1040 + 150 / 565)
    s = simpson.hurricane_tie("H2.5A", "SPF/HF", 400, 50, 50)
    assert s["rows"][-1][1] == pytest.approx(400 / 615 + 50 / 110 + 50 / 110)
    assert len(simpson.hurricane_tie("H2.5A", "DF/SP", 500)["rows"]) == 1          # one direction: no unity row
    with pytest.raises(simpson.SimpsonError):
        simpson.hurricane_tie("H6 (to plates)", "DF/SP", 500, 100)                # no F1 value in the table
    with pytest.raises(simpson.SimpsonError):
        simpson.hurricane_tie("first that works", "DF/SP", 5000)


def test_hurricane_tie_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="HT1", model="first that works", species="DF/SP", uplift="600", F1="150", F2="80", load_source="rafter R1")
    s = calc.build("hurricane_tie", v, proj)[0]
    assert all(r.status == "OK" for r in s.rows)
    with pytest.raises(calc.Missing):
        calc.build("hurricane_tie", dict(v, uplift="", F1="", F2=""), proj)
    calcsheet.simple_pdf(s, str(tmp_path / "ht.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def _page_text(page):
    import subprocess
    from pathlib import Path
    pdf = Path("/mnt/user-data/uploads/StrucutralDesign/Simpson/C-C-2026.pdf")
    if not pdf.exists():
        pytest.skip("catalog not staged in this session")
    return subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"], capture_output=True, text=True).stdout


def test_post_base_rows_against_the_catalog_page():
    """Every post base row (p. 77, copied by hand into simpson.POST_BASES) is found on one line of the page text: model, post, gauges,
    W, L, H, anchor, nails, then uplift (nails), uplift (bolts) and download."""
    import re
    t = _page_text(77)
    f = lambda v: "—" if v is None else f"{v:,}"
    for r in simpson.POST_BASES:
        j = lambda ps: r"\s+".join(re.escape(p).replace(r"\ ", r"\s+") for p in ps)
        tail = [r[7], r[8]] + ([str(r[11][0]), r[11][1]] if r[11] else ["—", "—"]) + [f(v) for v in (r[9], r[10], r[12])]
        hb = r"\s+(?:—|\d+\s+\d+/\d+)\s+"                           # the HB column (not used), a dash or a mixed number
        pat = j([r[0], r[1], str(r[2]), str(r[3]), r[4], r[5], r[6]]) + hb + j(tail)
        assert re.search(pat, t), r[0]


def test_column_cap_rows_against_the_catalog_pages():
    """CC rows (p. 101): the five loads in order on the model's line; BC rows (p. 93): dimensions, nails, uplift and lateral."""
    import re
    t = _page_text(101)
    for r in simpson.COLUMN_CAPS:
        pat = re.escape(r[0]).replace(r"\ ", r"\s+") + r"\s.*?" + r"\s+".join(re.escape(f"{v:,}") for v in r[9:14])
        assert re.search(pat, t), r[0]
    t = _page_text(93)
    for r in simpson.BC_CAPS:
        parts = list(r[:9])
        pat = r"\s+".join(re.escape(p).replace(r"\ ", r"\s+") for p in parts) + r"\s+—\s+" + r"\s+".join(re.escape(f"{v:,}") for v in r[9:11])
        assert re.search(pat, t), r[0]


def test_post_base_choice():
    """4x6, download 9,000, uplift 2,100, bolts: ABA46Z and ABW46Z have no bolted values; ABU46Z bolted 2,265 / 12,520 passes.
    With nails, uplift 2,100: ABA46Z 870 and ABW46Z 845 fail, ABU46Z 2,405 passes. ABU88Z has no bolted value."""
    h = simpson.post_base("4x6", "first that works", 9000, 2100, "bolts")
    assert h["base"][0] == "ABU46Z" and h["rows"] == [("download", 9000, 12520), ("uplift", 2100, 2265)]
    assert simpson.post_base("4x6", "first that works", 9000, 2100, "nails")["rows"][1][2] == 2405
    assert simpson.post_base("4x4", "first that works", 5000)["base"][0] == "ABA44Z"           # 5,000 <= 5,925
    with pytest.raises(simpson.SimpsonError):
        simpson.post_base("8x8", "ABU88Z", 1000, 500, "bolts")
    with pytest.raises(simpson.SimpsonError):
        simpson.post_base("4x4", "ABU46Z", 1000)                                              # wrong post
    with pytest.raises(simpson.SimpsonError):
        simpson.post_base("4x4", "first that works", 0, 3000)                                 # nothing carries 3,000 uplift


def test_column_cap_checks():
    """CC66 for a 5-1/2 in. beam on a 5-1/2 in. post (p. 101): CC64 is for a 3-5/8 in. post, so CC66 is the first that fits; download
    30,250, uplift 5,545; H1 6-1/2 against the beam depth. ECC: no uplift value. Splice (p. 73 note l): 12,032.5 each and 2 x the other.
    BC6 (p. 93): 600 / 1,185 + 700 / 1,825 = 0.890."""
    h = simpson.column_cap("CC", "first that works", 22000, 3000, beam_width=5.5, post_width=5.5, beam_depth=11.25)
    assert h["model"] == "CC66" and h["rows"][:2] == [("download", 22000, 30250), ("uplift", 3000, 5545)]
    assert h["rows"][2][1:] == (6.5, 11.25)
    assert simpson.column_cap("ECCU", "ECCU44", 5000, 1200, beam_depth=7.25)["rows"][1] == ("uplift", 1200, 1850)
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("ECC", "ECC44", 5000, 1200)
    s = simpson.column_cap("CC", "CC46", 9000, spliced=True, download2=7000)
    assert [r[2] for r in s["rows"]] == [24065 / 2, 14000, 24065 / 2, 18000]
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("CC", "CC46", 9000, 500, spliced=True, download2=7000)            # uplift does not apply at a splice
    b = simpson.column_cap("BC", "first that works", uplift=600, lateral=700, beam_width=5.5, post_width=5.5)
    assert b["model"] == "BC6" and b["rows"][-1][1] == pytest.approx(600 / 1185 + 700 / 1825)
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("BC", "BC6", 5000)                                                 # no download in the BC table
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("BC", "BC6", uplift=100, spliced=True)                             # note 4
    assert simpson.cap_models("ECCU")[2] == "ECCU44" and simpson.cap_models("ECC")[0] == "ECC3 1/4-4"


def test_post_base_and_cap_screens(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="PB1", post="4x6", model="first that works", fastening="bolts", download="9000", uplift="2100", load_source="post P1")
    s = calc.build("post_base", v, proj)[0]
    assert all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "pb.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")
    with pytest.raises(calc.Missing):
        calc.build("post_base", dict(v, download="", uplift=""), proj)
    for v in (dict(mark="CP1", series="CC", model="first that works", beam_width="5.5", post_width="5.5", beam_depth="11.25",
                   download="22000", uplift="3000", load_source="beam B1"),
              dict(mark="CP2", series="ECCU", model="ECCU44", beam_depth="7.25", download="5000", uplift="1200", load_source="beam B2"),
              dict(mark="CP3", series="BC", model="BC6", uplift="600", lateral="700", load_source="beam B3"),
              dict(mark="CP4", series="CC", model="CC46", beam_depth="9.25", download="9000", download2="7000", spliced="yes", load_source="B4")):
        s = calc.build("column_cap", v, proj)[0]
        assert all(r.status == "OK" for r in s.rows), v["mark"]
        calcsheet.simple_pdf(s, str(tmp_path / f"{v['mark']}.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_strap_rows_against_the_catalog_pages():
    """Strap ties p. 291, MST p. 292 (lower table) and coiled straps p. 296: every row copied into simpson found in the page text."""
    import re
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    t = _page_text(291)
    for r in simpson.STRAPS:
        assert re.search(re.escape(r[0]) + r"\s+(?:\d\d\s+)?" + j([r[2], r[3], r[4], f"{r[5]:,}", f"{r[6]:,}"]), t), r[0]
    t = _page_text(292)
    for r in simpson.MST:
        assert re.search(j([r[0]]) + r"\s+(?:\d\d\s+)?" + j([r[2], r[3], r[4], r[5][0], r[5][1]] + [f"{v:,}" for v in r[6:10]]), t), r[0]
    t = _page_text(296)
    for r in simpson.COILS:
        for o in r[3]:
            pat = j([o[0], o[1], o[2], o[3]]) + r"\s+" + re.escape(f"{r[4]:,}")
            assert re.search(pat, t), (r[0], o)


def test_strap_checks():
    """Catalog p. 296 note 2 worked example: CMSTC16, DF/SP, 40 nails total: 40 / 50 x 4,690 = 3,752 lb. Cut length (p. 288 note h):
    2 x 20 + 18 = 58 in. Strap ties (p. 291): 1,200 lb DF/SP: LSTA9 740, LSTA12 925, LSTA15 1,110 fail, LSTA18 1,235 passes. MST37 bolted
    SPF/HF 2,800 (p. 292). Bolts are refused on a strap tie; a coiled strap without the nail size is refused."""
    h = simpson.strap("coiled strap", "CMSTC16", "DF/SP", 3000, nail="0.148", nails_per_end=20, clear_span=18)
    assert h["allow"] == pytest.approx(3752.0) and h["cut"] == 58
    assert simpson.strap("strap tie", "first that works", "DF/SP", 1200)["model"] == "LSTA18"
    assert simpson.strap("MST", "MST37", "SPF/HF", 2500, "bolts")["allow"] == 2800
    assert simpson.strap("coiled strap", "first that works", "SPF/HF", 2000, nail="0.131")["model"] == "CS14"
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("strap tie", "LSTA18", "DF/SP", 1000, "bolts")
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("coiled strap", "CMSTC16", "DF/SP", 1000, nail="0.131")
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("strap tie", "first that works", "DF/SP", 9000)


def test_strap_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    for v in (dict(mark="ST1", kind="strap tie", model="first that works", species="DF/SP", tension="1200", load_source="plate splice"),
              dict(mark="ST2", kind="MST", model="MST37", species="SPF/HF", tension="2500", fastening="bolts", load_source="chord"),
              dict(mark="ST3", kind="coiled strap", model="CMSTC16", species="DF/SP", tension="3000", nail="0.148", nails_per_end="20",
                   clear_span="18", load_source="floor to floor")):
        s = calc.build("strap", v, proj)[0]
        assert all(r.status == "OK" for r in s.rows)
        calcsheet.simple_pdf(s, str(tmp_path / f"{v['mark']}.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")
    with pytest.raises(calc.Missing):
        calc.build("strap", dict(v, tension=""), proj)


def test_framing_angle_rows_against_the_catalog_page():
    """Every A34 / A35 / LTP4 / LTP5 row (p. 310): the direction and its six loads in order on one line of the page text, and the
    fasteners on the page. (The text prints the F2 footnote mark as a trailing digit, F26.)"""
    import re
    t = _page_text(310)
    for r in simpson.ANGLES:
        d_ = re.escape(r[3]) + (r"\d?" if r[3] == "F2" else "")
        assert re.search(r"\s" + d_ + r"\s+" + r"\s+".join(re.escape(f"{v:,}") for v in r[4] + r[5]), t), r
        assert r[2] in t, r[2]


def test_framing_angle_checks():
    """A35 type 4, DF/SP, (160): F1 300 / 650 + F2 200 / 670 = 0.760 (unity equation, p. 289). LTP4 type 7 with SD screws, SPF/HF floor
    (100): G 670; over 1/2 in. sheathing x 0.64 = 428.8 (note 3). Snow takes the floor column. Refusals: a direction not tabulated for the
    type, an unknown type for the model, the sheathing factor on an A35."""
    h = simpson.framing_angle("A35", 4, "", "DF/SP", "wind or earthquake (160)", {"F1": 300, "F2": 200})
    assert h["rows"][-1][1] == pytest.approx(300 / 650 + 200 / 670)
    l = simpson.framing_angle("LTP4", 7, "SD", "SPF/HF", "floor (100)", {"G": 400}, sheathing="1/2")
    assert l["rows"][0][2] == pytest.approx(670 * 0.64)
    assert simpson.framing_angle("A35", 2, "", "DF/SP", "snow (115)", {"E": 200})["rows"][0][2] == 295
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("A35", 2, "", "DF/SP", "floor (100)", {"F1": 100})
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("A34", 4, "", "DF/SP", "floor (100)", {"F1": 100})
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("A35", 4, "", "DF/SP", "floor (100)", {"F1": 100}, sheathing="1/2")


def test_framing_angle_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    for v in (dict(mark="FA1", model="A35", config="4: A35", fasteners="nails", species="DF/SP", duration="wind or earthquake (160)",
                   dir1="F1", load1="300", dir2="F2", load2="200", load_source="diaphragm boundary"),
              dict(mark="FA2", model="A35", config="3: A35", fasteners="nails", species="SPF/HF", duration="roof (125)", dir1="A2", load1="150",
                   load_source="stud"),
              dict(mark="FA3", model="LTP5", config="8: LTP5", fasteners="nails", species="DF/SP", duration="wind or earthquake (160)",
                   dir1="G", load1="300", sheathing="1/2", load_source="shear transfer")):
        s = calc.build("framing_angle", v, proj)[0]
        assert all(r.status == "OK" for r in s.rows)
        calcsheet.simple_pdf(s, str(tmp_path / f"{v['mark']}.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_l_ls_ga_angles_against_the_catalog_page():
    """L / LS / GA angles (p. 313): every row's eight loads found in order in the page text (the "F1, F2" rows print as "F1, F 2");
    L50 DF/SP snow (115): F1 300 / 415 + F2 50 / 415 = 0.843; LS90 with 0.148 x 3 nails at (160): 1,040; GA2 SD screws SPF/HF F2 (160): 540;
    an L angle must be entered as type 9."""
    import re
    t = _page_text(313)
    for r in simpson.ANGLES_L:
        d_ = r"F1,\s*F\s*2" if r[3] == "F1/F2" else re.escape(r[3])
        assert re.search(d_ + r"\s+" + r"\s+".join(re.escape(f"{v:,}") for v in r[4] + r[5]), t), r
    h = simpson.framing_angle("L50", 9, "nails", "DF/SP", "snow (115)", {"F1": 300, "F2": 50})
    assert h["rows"][-1][1] == pytest.approx(300 / 415 + 50 / 415)
    assert simpson.framing_angle("LS90", 9, "3 in. nails", "DF/SP", "wind or earthquake (160)", {"F1": 1000})["rows"][0][2] == 1040
    assert simpson.framing_angle("GA2", 9, "sd", "SPF/HF", "wind or earthquake (160)", {"F2": 450})["rows"][0][2] == 540
    assert simpson.framing_angle("L70", 9, "nails", "DF/SP", "floor (100)", {"F2": 400})["rows"][0] == ("F2", 400, 485)
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("L50", 4, "nails", "DF/SP", "floor (100)", {"F1": 100})
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("LS50", 9, "nails", "DF/SP", "floor (100)", {"F2": 100})        # LS: F1 only


def test_mpbz_rows_against_the_catalog_page():
    """MPBZ (p. 89): the four blocks (nonreinforced / reinforced x wind and SDC A&B / SDC C-F) in page order; each model's line carries its
    six concrete values, the wood assembly download (100), (160), moment and the rotational stiffness in order."""
    import re
    t = _page_text(89)
    lines = [l for l in t.splitlines() if re.search(r"MPB\d\dZ\s+\dx\d", l)]          # table rows (model, then the post size)
    order = [("nonreinforced", "A&B"), ("nonreinforced", "C-F"), ("reinforced", "A&B"), ("reinforced", "C-F")]
    assert len(lines) == 12
    for i, key in enumerate(order):
        for j, m in enumerate(("MPB44Z", "MPB66Z", "MPB88Z")):
            vals = simpson.MPBZ[key][m] + simpson._MPB_WOOD[m]
            pat = re.escape(m) + r".*?" + r"\s+".join(re.escape(f"{v:,}") for v in vals)
            assert re.search(pat, lines[3 * i + j]), (key, m)


def test_mpbz_checks():
    """MPB66Z, reinforced, cracked, wind and SDC A&B (p. 89): moment allowable the lesser of concrete 3,190 and wood 3,730 (note 8);
    download (160) 10,855; note 9: 3,000 / 10,855 + 1,600 / 3,190 + 500 / 2,405 = 0.986. MPB44Z nonreinforced uncracked SDC C-F: uplift
    4,785, moment min(1,180, 1,520) = 1,180, lateral 1,535. Download and uplift together are refused."""
    h = simpson.mpbz("first that works", "6x6", "reinforced", True, "A&B", download=3000, lateral=500, moment=1600, down_short=True)
    assert h["model"] == "MPB66Z" and h["allow"]["moment"] == 3190 and h["allow"]["download"] == 10855
    assert h["rows"][-1][1] == pytest.approx(3000 / 10855 + 1600 / 3190 + 500 / 2405)
    g = simpson.mpbz("MPB44Z", "4x4", "nonreinforced", False, "C-F", uplift=1200, lateral=300, moment=400)
    assert g["allow"]["uplift"] == 4785 and g["allow"]["moment"] == 1180 and g["allow"]["lateral"] == 1535
    assert simpson.mpbz("MPB88Z", "8x8", "nonreinforced", False, "A&B", moment=4000)["allow"]["moment"] == 4160    # concrete 4,160 < wood 4,560
    with pytest.raises(simpson.SimpsonError):
        simpson.mpbz("MPB44Z", "4x4", "reinforced", True, "A&B", download=100, uplift=100)
    with pytest.raises(simpson.SimpsonError):
        simpson.mpbz("MPB44Z", "6x6", "reinforced", True, "A&B", moment=100)


def test_mpbz_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="MB1", post="6x6", model="first that works", concrete="reinforced", cracked="yes", sdc="A&B", download="3000",
             down_short="yes", lateral="500", moment="1600", load_source="carport post")
    s = calc.build("mpbz", v, proj)[0]
    assert all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "mb.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")
    with pytest.raises(calc.Missing):
        calc.build("mpbz", dict(v, download="", lateral="", moment=""), proj)


def test_ccq_caps_against_the_catalog_page():
    """CCQ / ECCQ (p. 99): each row's beam width, W1, W2, L, H, screws and four loads found in the page text. CCQ66SDS2.5 is the first
    CCQ for a 5-1/2 in. beam on a 5-1/2 in. post; ECCQ46 down 12,030, uplift 3,785; a CCQ at a splice takes half the table download."""
    import re
    t = _page_text(99)
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    for r in simpson.CCQ_CAPS:
        pat = j([r[0], r[1], r[2], r[3], r[4][0], r[4][1], r[5], r[7][0], r[7][1], r[8], f"{r[9]:,}", f"{r[10]:,}", f"{r[12]:,}", f"{r[13]:,}"])
        assert re.search(pat, t), r[0]
    h = simpson.column_cap("CCQ", "first that works", 25000, 6000, beam_width=5.5, post_width=5.5, beam_depth=11.25)
    assert h["model"] == "CCQ66SDS2.5" and h["rows"][:2] == [("download", 25000, 30250), ("uplift", 6000, 6785)]
    e = simpson.column_cap("ECCQ", "ECCQ46SDS2.5", 9000, 2500, beam_depth=9.25)
    assert e["rows"][:2] == [("download", 9000, 12030), ("uplift", 2500, 3785)] and e["dims"]["beam_bolts"] == 14
    s = simpson.column_cap("CCQ", "CCQ46SDS2.5", 9000, spliced=True, download2=7000)
    assert s["rows"][0][2] == 24065 / 2
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("ECCQ", "ECCQ46SDS2.5", 9000, spliced=True, download2=7000)


def test_column_base_rows_and_checks():
    """CBSTQ / CBSQ (p. 85): both blocks of rows found in the page text (the A&B block prints the 6x6 model as CBSQT66Z-SDS2). CBSTQ44Z,
    cracked, A&B: uplift 4,650; with F1 100 and F2 300 (note 5: 485, 1,270): 2,000 / 4,650 + 100 / 485 + 300 / 1,270 = 0.873. CBSQ88 SDC C-F
    download 22,225; lateral on a CBSQ is refused."""
    import re
    t = _page_text(85)
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    for r in simpson.COLUMN_BASES:
        for blk in (r[9], r[10]):
            name = r"(?:CBSQT66Z|CBSTQ66Z)-SDS2" if r[0] == "CBSTQ66Z-SDS2" else re.escape(r[0])
            pat = name + r"\s+" + j([r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], f"{blk[0]:,}", f"{blk[1]:,}", f"{r[11]:,}"])
            assert re.search(pat, t), (r[0], blk)
    h = simpson.column_base("4x4", "first that works", True, "A&B", uplift=2000, F1=100, F2=300)
    assert h["row"][0] == "CBSTQ44Z-SDS2" and h["rows"][-1][1] == pytest.approx(2000 / 4650 + 100 / 485 + 300 / 1270)
    assert simpson.column_base("8x8", "CBSQ88-SDS2", True, "C-F", download=18000)["rows"] == [("download", 18000, 22225)]
    assert simpson.column_base("6x6", "first that works", False, "C-F", uplift=1000)["uplift_allow"] == 3830
    with pytest.raises(simpson.SimpsonError):
        simpson.column_base("8x8", "CBSQ88-SDS2", True, "A&B", F1=100)


def test_column_base_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    v = dict(mark="CB1", post="4x4", model="first that works", cracked="yes", sdc="A&B", uplift="2000", F1="100", F2="300", load_source="deck post")
    s = calc.build("column_base", v, proj)[0]
    assert all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "cb.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_ac_post_caps():
    """AC / ACHZ / LPCZ / LCE (p. 95): each row's fasteners and loads found in the page text. A 3-1/2 in. beam on a 3-1/2 in. post with
    uplift 2,000 and lateral 1,000: AC4 min / max and ACH4Z with nails fail the unity equation (1,745/1,610 ... 4,045/1,765: 2,000/4,045 +
    1,000/1,765 = 1.06), ACH4Z with SD screws passes (0.725); the end-of-beam rows are not picked. AC6 max nailing one side only: 2,815 x 0.4
    = 1,126 (note 2). No download in the table; one side refused for an LPCZ."""
    import re
    t = _page_text(95)
    for r in simpson.AC_CAPS:
        assert re.search(r"\s+".join(re.escape(x).replace(r"\ ", r"\s+") for x in (r[7], r[8], f"{r[9]:,}", f"{r[10]:,}")), t), r[0]
    h = simpson.column_cap("AC", "first that works", uplift=2000, lateral=1000, beam_width=3.5, post_width=3.5)
    assert h["label"] == "ACH4Z (SD screws)" and h["rows"][-1][1] == pytest.approx(2000 / 5895 + 1000 / 2595)
    assert simpson.column_cap("AC", "AC6 (max. nailing)", uplift=600, one_side=True)["rows"][0][2] == pytest.approx(1126)
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("AC", "AC6 (max. nailing)", download=600)
    with pytest.raises(simpson.SimpsonError):
        simpson.column_cap("AC", "LPC4Z", uplift=100, one_side=True)


def test_cast_bases_against_the_catalog_pages():
    """CB (p. 87), PB (p. 82), PBST (p. 83), EPB (p. 80): each row's dimensions and loads found in the page text; the choice, the
    lateral values by fastening (PBST note 9: F1 1,165 nails, 230 bolts) and the refusals by hand."""
    import re
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    texts = {p: _page_text(p) for p in (80, 82, 83, 87)}
    for r in simpson.CAST_BASES:
        if r["series"] == "CB":
            bolt = r["fast"].split(") ")[1].split('"')[0]
            pat = j([r["model"], r["post"], r["W1"], r["W2"], "2", bolt] + [f"{v:,}".replace(",", ",?") for v in ()])
            pat += r"\s+" + r"\s+".join(f"{v:,}".replace(",", ",?") for v in (r["AB"] + r["CF"] + (r["down"],)))
        elif r["series"] == "PB":
            pat = j([r["model"], r["W1"], r["W2"], "(12) 0.162 x 3 1/2"]) + r".*?" + j([f"{r['AB'][0]:,}", f"{r['AB'][1]:,}", f"{r['down']:,}"])
        elif r["series"] == "PBST":
            pat = j([r["model"], r["post"], "12"]) + r"\s+\d+\s+" + j([r["W1"], r["W2"], r["H"]]) + r".*?" + j([f"{v:,}" for v in r["AB"]] + [f"{r['down']:,}"])
        elif r["series"] == "EPB":
            pat = j([r["model"], r["W1"], r["W2"], r["H"], r["fast"].replace(" nails", "")] + [f"{v:,}" for v in r["AB"]] + [f"{r['down']:,}"] + [f"{v:,}" for v in r["lat"]["nails"]])
        else:
            continue
        assert re.search(pat, texts[r["page"]]), r["model"]
    for r in simpson.CAST_BASES:                                 # the SDC C-F blocks
        if r["series"] in ("PBST", "EPB"):
            assert re.search(j([r["model"]]) + r".*?" + j([f"{v:,}" for v in r["CF"]]), texts[r["page"]]), r["model"]
    h = simpson.cast_base("PBST", "4x4", "first that works", True, "A&B", uplift=500, F1=80, fastening="bolts")
    assert h["rows"][-1][1] == pytest.approx(500 / 865 + 80 / 230)
    assert simpson.cast_base("PBST", "4x4", "PBST44Z", True, "A&B", uplift=500, F1=300)["rows"][1][2] == 1165
    assert simpson.cast_base("CB", "6x6", "first that works", True, "C-F", uplift=3000, fastening="bolts")["base"]["model"] == "CB66"
    assert simpson.cast_base("EPB", "4x4", "first that works", True, "A&B", download=4000)["base"]["model"] == "EPB44"   # EPB44A 2,670
    assert simpson.cast_base("CB", "Glulam", "CB7-9", True, "A&B", download=60000, fastening="bolts")["rows"][0][2] == 91620
    with pytest.raises(simpson.SimpsonError):
        simpson.cast_base("CB", "6x6", "CB66", True, "A&B", uplift=100, F1=100, fastening="bolts")     # no lateral for CB
    with pytest.raises(simpson.SimpsonError):
        simpson.cast_base("PB", "4x4", "PB44", True, "A&B", uplift=100, fastening="bolts")             # PB44 not with bolts
    with pytest.raises(simpson.SimpsonError):
        simpson.cast_base("CB", "Glulam", "first that works", True, "A&B", uplift=100, fastening="bolts")


def test_cast_base_screen(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    for v in (dict(mark="CB3", series="CB", post="6x6", model="first that works", fastening="bolts", cracked="yes", sdc="C-F", uplift="3000", load_source="column"),
              dict(mark="CB5", series="PB", post="6x6", model="PB66", fastening="bolts", cracked="yes", sdc="A&B", uplift="500", F2="500", load_source="porch post"),
              dict(mark="CB7", series="EPB", post="4x4", model="first that works", cracked="yes", sdc="A&B", download="4000", load_source="deck post"),
              dict(mark="CB1", post="4x4", model="first that works", cracked="yes", sdc="A&B", uplift="2000", F1="100", F2="300", load_source="deck")):
        s = calc.build("column_base", v, proj)[0]
        assert all(r.status == "OK" for r in s.rows), v["mark"]
        calcsheet.simple_pdf(s, str(tmp_path / f"{v['mark']}.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_a_and_hl_angles():
    """A angles (p. 314) and HL heavy angles (p. 315): each rated row found in the page text. A44 SPF/HF (note 2, x 0.86): F1 775 x 0.86 =
    666.5, F2 290 x 0.86 = 249.4; HL55 DF/SP uplift 740 and F1 1,310 with the unity equation; only the (160) duration; A66 has no rating."""
    import re
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    t = _page_text(314)
    for r in simpson.ANGLES_A:
        assert re.search(j([r[0], r[1], r[2], r[3], "—", r[4], "—", r[5], f"{r[6]:,}", f"{r[7]:,}"]), t), r[0]
    t = _page_text(315)
    for r in simpson.ANGLES_HL:
        assert re.search(j([r[0], r[1], r[2], r[3]]) + r".*?" + j([r[4][0], r[4][1], f"{r[5]:,}", f"{r[6]:,}"]), t), r[0]
    a = simpson.framing_angle("A44", 10, "nails", "SPF/HF", "wind or earthquake (160)", {"F1": 400, "F2": 80})
    assert a["rows"][0][2] == pytest.approx(666.5) and a["rows"][1][2] == pytest.approx(249.4)
    h = simpson.framing_angle("HL55", 11, "", "DF/SP", "wind or earthquake (160)", {"Uplift": 500, "F1": 400})
    assert h["rows"][-1][1] == pytest.approx(500 / 740 + 400 / 1310) and h["bolts"] == (8, "1/2")
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("HL55", 11, "", "DF/SP", "floor (100)", {"F1": 100})
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("A66", 10, "", "DF/SP", "wind or earthquake (160)", {"F1": 100})
    with pytest.raises(simpson.SimpsonError):
        simpson.framing_angle("A44", 4, "", "DF/SP", "wind or earthquake (160)", {"F1": 100})


def test_corner_caps():
    """RTC44 / LCE4 (p. 95 lower table): rows found in the page text; RTC44 square cut SPF/HF: side 795, main 1,060, the two beams together
    against the post 1,515 (note 3)."""
    import re
    t = _page_text(95)
    for r in simpson.RTC_CAPS:
        vals = [f"{v:,}" for v in r[5] + r[6]]
        assert re.search(r"\s+".join(re.escape(x).replace(r"\ ", r"\s+") for x in (r[1], r[2], r[3], r[4], *vals)), t), r[0]
    h = simpson.corner_cap("RTC44 (square cut)", "SPF/HF", 900, 400)
    assert h["rows"] == [("uplift, side beam", 400, 795), ("uplift, main beam", 900, 1060), ("uplift, both beams, at the post (note 3)", 1300, 1515)]
    with pytest.raises(simpson.SimpsonError):
        simpson.corner_cap("RTC44", "DF/SP", 100, 0)


def test_corner_cap_and_a_hl_screens(tmp_path):
    from strukit import calcsheet
    proj = dict(job="t", name="t", method="ASD")
    s = calc.build("corner_cap", dict(mark="CC1", model="RTC44 (mitered corner)", species="DF/SP", uplift_main="600", uplift_side="500",
                                      load_source="porch corner"), proj)[0]
    assert all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, str(tmp_path / "cc.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")
    for v in (dict(mark="FA8", model="A44", config="10: A angle", fasteners="nails", species="SPF/HF", duration="wind or earthquake (160)",
                   dir1="F1", load1="400", dir2="F2", load2="80", load_source="blocking"),
              dict(mark="FA9", model="HL55", config="11: HL", fasteners="nails", species="DF/SP", duration="wind or earthquake (160)",
                   dir1="Uplift", load1="500", dir2="F1", load2="400", load_source="beam to post")):
        s = calc.build("framing_angle", v, proj)[0]
        assert all(r.status == "OK" for r in s.rows), v["mark"]
        calcsheet.simple_pdf(s, str(tmp_path / f"{v['mark']}.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_floor_to_floor_straps():
    """Floor-to-floor table (p. 292 upper): every row found in the page text. Between tabulated clear spans the load and the nails are
    interpolated (Zach 2026-11-27): 3,000 lb DF/SP over 17 in.: MSTC40 (16 in. 3,070, 18 in. 2,690) gives 2,880 and fails; MSTA49 2,020,
    MSTC28 1,342.5 fail; MSTC52 (4,610 / 4,225): 4,417.5 with (48 + 0.5 x (44 - 48)) = 46 nails. MST37 over 20 in.: 2,460 + 1/3 x (1,720 -
    2,460) = 2,213.3 (DF/SP), nails 20 - 2 = 18; over 31 in. refused; under 16 in. the shortest row."""
    import re
    t = _page_text(292)
    for r in simpson.FLOOR_TO_FLOOR:
        assert re.search(r"\s" + str(r[1]) + r"\s+" + re.escape(r[2]).replace(r"\ ", r"\s+") + r"\s+" + f"{r[3]:,}" + r"\s+" + f"{r[4]:,}", t), r
    h = simpson.strap("floor-to-floor", "first that works", "DF/SP", 3000, clear_span=17)
    assert h["model"] == "MSTC52" and h["allow"] == pytest.approx(4417.5) and h["n"] == 46 and h["table_span"] == (16, 18)
    m = simpson.strap("floor-to-floor", "MST37", "DF/SP", 1000, clear_span=20)
    assert m["allow"] == pytest.approx(2460 + (1720 - 2460) / 3) and m["n"] == 18
    assert simpson.strap("floor-to-floor", "MST37", "SPF/HF", 1000, clear_span=12)["allow"] == 2355
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("floor-to-floor", "MST37", "DF/SP", 1000, clear_span=31)


def test_heavy_straps():
    """HL / HT / HTQ (p. 293) and PS / PSQ / HST (p. 294): each row found in the page text. 1212HT DF/SP: 1,500 / 2,585 + 300 / 815 = 0.948;
    PSQ418 SPF/HF tension 2,620, F1 670 (note 3); 5,000 lb SPF/HF: HST2 4,835 fails, HST5 9,870 passes (the first in the table that works
    with an SPF/HF value); HL / HT have no species group and are refused for SPF/HF; the T and L straps are not load rated."""
    import re
    t = _page_text(293) + _page_text(294)
    j = lambda ps: r"\s+".join(re.escape(str(p)).replace(r"\ ", r"\s+") for p in ps)
    for r in simpson.HEAVY_STRAPS:
        vals = [f"{v:,}" for v in (r[7][0], r[7][1] if r[7][1] else r[8][0])]
        if r[1] == "HST":
            fast = [str(r[6][0]), r[6][1]]
        else:
            fast = [r[5]]
        assert re.search(j([r[0]]) + r".*?" + j([r[3]]) + r".*?" + j(fast + vals), t), r[0]
    h = simpson.strap("heavy strap", "1212HT", "DF/SP", 1500, F1=300)
    assert h["rows"][-1][1] == pytest.approx(1500 / 2585 + 300 / 815)
    p = simpson.strap("heavy strap", "PSQ418", "SPF/HF", 1500, F1=200)
    assert p["rows"][0][2] == 2620 and p["rows"][1][2] == 670
    assert simpson.strap("heavy strap", "first that works", "SPF/HF", 5000)["model"] == "HST5"
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("heavy strap", "1212HT", "SPF/HF", 1000)
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("heavy strap", "66T", "DF/SP", 100)
    with pytest.raises(simpson.SimpsonError):
        simpson.strap("strap tie", "LSTA18", "DF/SP", 100, F1=50)


def test_top_flange_on_a_nailer():
    """Nailer Table (p. 136): each BA / HB row found in the page text. A 2x10 on a 3x nailer, DF/SP, 2,500 lb down, 500 lb up, maximum joist
    nailing: BA210 at 3,230 / 970 (the (100) download for every duration, note 4); on steel with PDPAT the uplift has no value; HB on a 4x nailer
    in SPF/HF has no value."""
    import re
    t = _page_text(136)
    for x in simpson.NAILER_ROWS:
        f = lambda v: "—" if v is None else f"{v:,}"
        pat = r"\s+".join(re.escape(p).replace(r"\ ", r"\s+") for p in (x[2], x[3], f(x[4][0]), f(x[4][1]), f(x[5][0]), f(x[5][1])))
        assert re.search(pat, t), x
    h = simpson.facemount("2x10", "DF/SP", "lightest that works", 2500, "roof (125)", 500, nailing="Max.", kind="topflange", nailer="3x")
    assert h["row"]["model"].startswith("BA210") and h["rows"] == [("download", 2500, 3230), ("uplift", 500, 970)]
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("2x10", "DF/SP", "BA210", 1000, "floor (100)", 100, kind="topflange", nailer="steel (PDPAT)")
    with pytest.raises(simpson.SimpsonError):
        simpson.facemount("4x12", "SPF/HF", "HB412", 1000, "floor (100)", 0, kind="topflange", nailer="4x")


EWP_HAND = [  # kind, joist, model, nailing, uplift, (DF/SP floor, snow, roof, SPF/HF floor, snow, roof) or {header: load}, page — copied from the pages
    ("ewp_facemount", "1 1/2 x 9 1/2", "U210", "", 990, (1220, 1380, 1480, 1050, 1185, 1275), 158),
    ("ewp_facemount", "1 3/4 x 9 1/2", "HUS1.81/10", "", 2635, (5515, 5830, 5830, 4360, 4675, 4885), 158),
    ("ewp_facemount", "1 3/4 x 11 7/8", "HU11", "Max.", 1795, (4465, 4705, 4810, 3845, 4340, 4600), 158),
    ("ewp_facemount", "2 x 14", "IUS2.06/14", "Max.", 70, (1660, 1805, 1805, 1425, 1555, 1555), 158),
    ("ewp_topflange", "3 1/2 x 22", "HIT422", "", 305, {"LVL": 2550, "PSL": 2220, "LSL": 2500, "DF/SP": 2875, "SPF/HF": 1950, "DF/SCL I-joist": None}, 202),
    ("ewp_topflange", "3 1/2 x 22", "HB3.56/22", "", 2075, {"LVL": 5815, "PSL": 5640, "LSL": 6395, "DF/SP": 5395, "SPF/HF": 3820, "DF/SCL I-joist": None}, 202),
]


@pytest.mark.parametrize("kind,joist,model,nail,up,loads,page", EWP_HAND)
def test_ewp_rows_match_the_catalog(kind, joist, model, nail, up, loads, page):
    rows = [r for r in simpson.rows_of(kind) if r["joist"] == joist and r["model"] == model and r["nailing"] == nail]
    assert rows, (joist, model)
    r = rows[0]
    assert r["uplift"] == up and r["page"] == page
    if isinstance(loads, dict):
        assert all(r[k] == v for k, v in loads.items())
    else:
        assert (r["df_floor"], r["df_snow"], r["df_roof"], r["spf_floor"], r["spf_snow"], r["spf_roof"]) == loads


def test_ewp_rows_against_the_page_text():
    """Every row read by tools/simpson_extract_ewp.py: its loads found in order on one line of its page's text, and its width fits the
    member size of its group (W - b between 0 and 0.4 in.)."""
    import re
    texts = {}
    for kind in ("ewp_facemount", "ewp_topflange"):
        for r in simpson.rows_of(kind):
            if r["page"] not in texts:                     # thousands written 1,515 / 1515 / 2.985 on the pages: compared without the separator
                texts[r["page"]] = re.sub(r"(\d)[,.](\d{3})\b", r"\1\2", _page_text(r["page"]))
            t = texts[r["page"]]
            keys = ["uplift", "df_floor", "df_snow", "df_roof", "spf_floor", "spf_snow", "spf_roof"] if kind == "ewp_facemount" else \
                ["uplift"] + simpson.EWP_HEADERS
            vals = ["—" if r[k] is None else f"{r[k]:.0f}" for k in keys]
            assert re.search(r"\s" + r"\s+".join(re.escape(v) for v in vals), t), (r["page"], r["model"], r["joist"])
    assert len(simpson.rows_of("ewp_facemount")) == 268 and len(simpson.rows_of("ewp_topflange")) == 446


def test_ewp_hanger_choice():
    """2 1/16 x 11 7/8 I-joist, SPF/HF header, 1,200 lb floor, 300 lb up: IUS2.06/11.88 (uplift 70 x 0.86) and MIU2.06/11 (230 x 0.86) fail
    the uplift; HU2.1/11 915 x 0.86 = 786.9 passes (p. 164 note 2). Top flange 3 1/2 x 22 on PSL, 5,000 down: HB3.56/22 at 5,640."""
    h = simpson.ewp_hanger("face mount", "2 1/16 x 11 7/8", "SPF/HF", "lightest that works", 1200, "floor (100)", 300)
    assert h["row"]["model"] == "HU2.1/11" and h["allow_up"] == pytest.approx(915 * 0.86)
    t = simpson.ewp_hanger("top flange", "3 1/2 x 22", "PSL", "lightest that works", 5000, None, 1000)
    assert t["row"]["model"] == "HB3.56/22" and t["allow_down"] == 5640
    with pytest.raises(simpson.SimpsonError):
        simpson.ewp_hanger("top flange", "3 1/2 x 22", "DF/SCL I-joist", "HB3.56/22", 1000, None)
    from strukit import calcsheet
    import tempfile, os
    s = calc.build("ewp_hanger", dict(mark="JH7", type="face mount", member="I-joist", joist="2 1/16 x 11 7/8", header="SPF/HF",
                                      model="lightest that works", download="1200", duration="floor (100)", uplift="300", load_source="J3"),
                   dict(job="t", name="t", method="ASD"))[0]
    assert all(r.status == "OK" for r in s.rows)
    calcsheet.simple_pdf(s, os.path.join(tempfile.mkdtemp(), "ew.pdf"), "Job", "Simpson C-C-2026", "Nov 27, 2026")


def test_ewp_ijoist_header_factors():
    """Top-flange hanger on an I-joist header (catalog p. 206 note 4 and its table): ITS2.06/16 on a 2 x 16 joist, DF/SCL I-joist 1,085 lb
    (p. 198). By hand: 1-1/8 to 1-1/4 in. flange x 0.75 = 813.75 lb; 1-5/16 to 1-3/8 in. x 0.85 = 922.25 lb; SPF flange, ITS series x 0.86 =
    933.1 lb; both x 0.75 x 0.86 = 699.8 lb; uplift 120 lb takes the same factor. WP and BA series on an SPF flange: 1.00."""
    from strukit import simpson
    A = pytest.approx
    f = lambda t, m: simpson.ewp_hanger("top flange", "2 x 16", "DF/SCL I-joist", "ITS2.06/16", 500, None, 100, None, t, m)
    assert f("1 1/2 in. or more", "DF / LVL / LSL")["allow_down"] == A(1085)
    assert f("1 1/8 to 1 1/4 in.", "DF / LVL / LSL")["allow_down"] == A(813.75)
    assert f("1 5/16 to 1 3/8 in.", "DF / LVL / LSL")["allow_down"] == A(922.25)
    h = f("1 1/2 in. or more", "SPF")
    assert h["allow_down"] == A(933.1) and h["allow_up"] == A(103.2)
    assert f("1 1/8 to 1 1/4 in.", "SPF")["allow_down"] == A(1085 * 0.75 * 0.86)
    assert simpson.ij_header_factor("MIT9.5", "1 1/2 in. or more", "SPF")[0] == 0.72
    assert simpson.ij_header_factor("LBV1.56/9.5", "1 1/2 in. or more", "SPF")[0] == 0.90
    assert simpson.ij_header_factor("BA1.81/14", "1 1/2 in. or more", "SPF")[0] == 1.0
    assert simpson.ij_header_factor("WP1.81/14", "1 1/2 in. or more", "SPF")[0] == 1.0
    with pytest.raises(simpson.SimpsonError, match="no SPF"):
        simpson.ij_header_factor("HIT422", "1 1/2 in. or more", "SPF")
    # the factor carries to the choice: lightest that works on a thin flange needs a stronger hanger than on a full one
    full = simpson.ewp_hanger("top flange", "2 x 16", "DF/SCL I-joist", "lightest that works", 1000, None, 0, None)
    thin = simpson.ewp_hanger("top flange", "2 x 16", "DF/SCL I-joist", "lightest that works", 1000, None, 0, None, "1 1/8 to 1 1/4 in.", "DF / LVL / LSL")
    assert full["row"]["model"] == "ITS2.06/16" and thin["allow_down"] >= 1000 and thin["row"]["model"] != "ITS2.06/16"
    from strukit import ws_more
    s = ws_more.ewp_hanger_sheet("JH", "top flange", "I-joist", "2 x 16", "DF/SCL I-joist", "ITS2.06/16", 500, None, 0, None, "J3",
                                 "1 5/16 to 1 3/8 in.", "SPF")
    assert s.hanger["allow_down"] == A(1085 * 0.85 * 0.86) and any("p. 206 note 4" in str(x) for x in s.steps)
    assert dict(s.info)["Fasteners"].startswith("header (6) 0.148 x 1 1/2 (I-joist header")       # table (6) 0.148 x 3 -> 0.148 x 1-1/2


def test_skewed_and_sloped_ewp_rows_against_the_page_text():
    """Every SUR/SUL/HSUR/HSUL row (p. 175, tools/simpson_extract_skew.py) and every LSSR/LSU row (pp. 178-179,
    tools/simpson_extract_lssr.py): its model, gauge, fasteners and eight loads found in order on one line of the page text (the LSSR model
    is printed on the middle line of its three schedules, so for those the fasteners and loads are matched and the model checked nearby)."""
    import re
    norm = lambda t: re.sub(r"(\d),(\d{3})\b", r"\1\2", t.replace("⁄", "/"))
    t175 = norm(_page_text(175))
    keys = ["uplift", "df_floor", "df_snow", "df_roof", "uplift_spf", "spf_floor", "spf_snow", "spf_roof"]
    for r in simpson.rows_of("ewp_skew"):
        loads = r"\s+".join(f"{r[k]:.0f}" for k in keys)
        fast = re.escape(r["header"]) + r"\s+" + re.escape(r["joist_fast"])
        assert re.search(fast + r"\s+" + loads, t175) or (re.search(fast, t175) and re.search(re.escape(r["model"]) + r"\s+" + loads, t175)), r["model"]
        ls = t175.splitlines()                                       # gauge and W on the model's line, or one line away where the row wraps
        near = [ls[j] for i, l in enumerate(ls) if re.search(re.escape(r["model"]) + r"\b", l) for j in range(max(0, i - 6), i + 7)]
        assert any(re.search(r"(^|\s)" + r["ga"] + r"\s+" + re.escape(r["W_text"]) + r"\s", l) for l in near), r["model"]
    assert len(simpson.rows_of("ewp_skew")) == 44
    sl = simpson.rows_of("ewp_slope")
    for p in (178, 179):
        t = norm(_page_text(p))
        lines = t.splitlines()
        for r in [x for x in sl if x["page"] == p]:
            pat = re.escape(r["header"]).replace("SD\\ \\#9", r"SD ?# ?9") + r"\s+" + re.escape(r["joist_fast"]).replace("SD\\ \\#9", r"SD ?# ?9") \
                + r"\s+" + r"\s+".join(f"{r[k]:.0f}" for k in keys)
            hits = [i for i, l in enumerate(lines) if re.search(pat, l)]
            assert hits, (p, r["model"], r["header"])
            assert any(r["model"] in lines[j] for i in hits for j in range(max(0, i - 7), i + 8)), (p, r["model"])
        assert sum(1 for x in sl if x["page"] == p) == 22


@pytest.mark.parametrize("kind, joist, model, face, row", [
    # hand-copied from p. 175: uplift, floor, snow, roof (DF/SP), then the same for SPF/HF
    ("ewp_skew", "1 1/2 x 9 1/4-12", "SUR/L210", "(10) 0.162 x 3 1/2", (1445, 1440, 1630, 1760, 1075, 1240, 1400, 1515)),
    ("ewp_skew", "2 1/2-2 9/16 x 11 1/4-11 7/8", "SUR/L2.56/11", "(16) 0.162 x 3 1/2", (210, 2305, 2610, 2665, 180, 1980, 2245, 2290)),
    ("ewp_skew", "3 x 14-20", "HSUR/L214-2", "(26) 0.162 x 3 1/2", (1490, 3875, 4370, 4680, 1280, 3335, 3760, 4025)),
    ("ewp_skew", "5 x 16", "HSUR/L5.12/16", "(24) 0.162 x 3 1/2", (145, 3330, 3330, 3330, 140, 2865, 2865, 2865)),
    # hand-copied from pp. 178 (sloped only) and 179 (skewed, or sloped and skewed)
    ("ewp_slope", "2 to 2 1/16", "LSSR2.1Z", "(14) 0.148 x 2 1/2", (510, 1565, 1565, 1565, 440, 1345, 1345, 1345)),
    ("ewp_slope", "3", "LSSR210-2Z", "(22) 0.148 x 1 1/2", (535, 1085, 1085, 1085, 460, 935, 935, 935)),
    ("ewp_slope", "Dbl 2 1/2", "LSU5.12", "(24) 0.162 x 3 1/2", (885, 1790, 1790, 1790, 760, 1550, 1550, 1550)),
])
def test_skewed_and_sloped_rows_by_hand(kind, joist, model, face, row):
    keys = ["uplift", "df_floor", "df_snow", "df_roof", "uplift_spf", "spf_floor", "spf_snow", "spf_roof"]
    hits = [r for r in simpson.rows_of(kind) if r["joist"] == joist and r["model"] == model and r["header"] == face
            and tuple(r[k] for k in keys) == row]
    assert len(hits) == 1, (model, [tuple(r[k] for k in keys) for r in simpson.rows_of(kind) if r["model"] == model])


def test_skewed_and_sloped_hanger_choice():
    """By hand from pp. 174-179: SUR/SUL take 40 to 50 degrees of skew and no slope; LSSR/LSU 0 to 45 of each; the sloped-only table at no
    skew, the skewed table otherwise; SPF/HF uplift from its own column; 190 lb uplift cap for thin I-joist flanges without web stiffeners;
    LSU minimum joist heights; LSSR fasteners in the catalog's order unless chosen."""
    A = pytest.approx
    E = simpson.SimpsonError
    h = simpson.ewp_hanger("skewed 45 (SUR/SUL)", "2 x 11 7/8", "SPF/HF", "lightest that works", 2000, "snow (115)", 150, skew=45)
    assert h["row"]["model"] == "SUR/L2.06/11" and h["allow_down"] == 2170 and h["allow_up"] == 150
    with pytest.raises(E, match="40 to 50"):
        simpson.ewp_hanger("skewed 45 (SUR/SUL)", "2 x 11 7/8", "DF/SP", "lightest that works", 2000, "floor (100)", 0, skew=30)
    with pytest.raises(E, match="skewed only"):
        simpson.ewp_hanger("skewed 45 (SUR/SUL)", "2 x 11 7/8", "DF/SP", "lightest that works", 2000, "floor (100)", 0, skew=45, slope=10)
    h = simpson.ewp_hanger("skewed 45 (SUR/SUL)", "1 1/2 x 10-16", "DF/SP", "SUR/L214", 1000, "floor (100)", 500, skew=45, thin_flange=True)
    assert h["allow_up"] == 1890                                         # stiffeners required by the table: assumed installed
    with pytest.raises(E, match="requires web stiffeners"):
        simpson.ewp_hanger("skewed 45 (SUR/SUL)", "1 1/2 x 10-16", "DF/SP", "SUR/L214", 1000, "floor (100)", 100, skew=45, thin_flange=True,
                           no_stiffeners=True)
    h = simpson.ewp_hanger("skewed 45 (SUR/SUL)", "4 x 14", "DF/SP", "HSUR/L4.12/14", 1000, "floor (100)", 100, skew=45, thin_flange=True,
                           no_stiffeners=True)
    assert h["allow_up"] == 145                                          # already under 190
    up = lambda **kw: simpson.ewp_hanger("skewed 45 (SUR/SUL)", "2 x 11 7/8", "DF/SP", "SUR/L2.06/11", 1000, "floor (100)", 100, skew=45, **kw)["allow_up"]
    assert up() == 175 and up(thin_flange=True) == 175                   # 175 lb table value is under the 190 lb cap
    up2 = lambda **kw: simpson.ewp_hanger("skewed 45 (SUR/SUL)", "1 1/2 x 9 1/4-12", "DF/SP", "SUR/L210", 1000, "floor (100)", 100, skew=45, **kw)
    assert up2(thin_flange=True)["allow_up"] == 1445                     # this row requires web stiffeners: assumed installed, no cap
    up3 = lambda **kw: simpson.ewp_hanger("skewed 45 (SUR/SUL)", "2 1/2 x 9 1/2 (3 x 10,12)", "DF/SP", "SUR/L2.56/9", 1000, "floor (100)", 100,
                                          skew=45, **kw)
    assert up3()["allow_up"] == 210 and up3(thin_flange=True)["allow_up"] == 190 and up3(thin_flange=True)["uplift_190"]
    assert up3(thin_flange=True, stiff_installed=True)["allow_up"] == 210
    # LSSR: no skew -> p. 178; skew -> p. 179; first schedule that works
    h = simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "3", "DF/SP", "lightest that works", 2000, "floor (100)", 0, skew=0, slope=30, depth=11.25)
    assert h["row"]["page"] == 178 and h["row"]["header"] == "(22) 0.162 x 2 1/2" and h["allow_down"] == 2365
    h = simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "3", "DF/SP", "lightest that works", 2000, "floor (100)", 0, skew=20, slope=30, depth=11.25)
    assert h["row"]["page"] == 179 and h["row"]["header"] == "(22) SD #9 x 1 1/2" and h["allow_down"] == 2100
    h = simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "3", "SPF/HF", "LSSR210-2Z", 500, "floor (100)", 400, skew=20, slope=0, depth=11.25,
                           fasteners="nails, 1 1/2 in. in the face")
    assert h["allow_down"] == 935 and h["allow_up"] == 460
    with pytest.raises(E, match="11 in. deep"):
        simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "Dbl 2", "DF/SP", "LSU4.12", 1000, "floor (100)", 0, skew=0, slope=10, depth=9.5)
    assert simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "Dbl 2 1/16", "DF/SP", "LSU4.28", 1000, "floor (100)", 0, skew=0, slope=10,
                              depth=9.5)["allow_down"] == 3215
    with pytest.raises(E, match="0 to 45"):
        simpson.ewp_hanger("sloped / skewed (LSSR/LSU)", "3", "DF/SP", "LSSR210-2Z", 500, "floor (100)", 0, skew=50, depth=11.25)
    with pytest.raises(E, match="skewed or sloped joist"):
        simpson.ewp_hanger("face mount", "2 x 14", "DF/SP", "lightest that works", 500, "floor (100)", 0, skew=30)
    from strukit import ws_more
    s = ws_more.ewp_hanger_sheet("JH", "sloped / skewed (LSSR/LSU)", "I-joist", "2 to 2 1/16", "DF/SP", "lightest that works", 1300, "roof (125)",
                                 300, None, "R3", skew=30, slope=20, depth=11.875)
    assert s.hanger["allow_down"] == 1580 and any("web stiffeners" in a.lower() for a in s.assumptions)


def test_vpa_and_hip_ridge_rows_against_the_catalog_pages():
    """Every VPA row (p. 181) and HRC / HHRC row (p. 180), copied by hand into simpson.VPA and simpson.HIP_RIDGE, found on one line of its
    page's text: model, dimensions, fasteners and loads in order."""
    import re
    norm = lambda t: re.sub(r"(\d),(\d{3})\b", r"\1\2", t.replace("⁄", "/").replace('"', ""))
    t181, t180 = norm(_page_text(181)), norm(_page_text(180))
    for v in simpson.VPA:
        pat = r"\s+".join([re.escape(v[0]), re.escape(v[2]), re.escape(v[3]), re.escape(v[4]), re.escape(v[5])] + [str(x) for x in v[6:]])
        assert re.search(pat, t181), v[0]
    h = simpson.HIP_RIDGE[0]
    assert re.search(r"HRC1\.81\s+1 13/16\s+1 3/4\s+\(16\) 0\.148 x 1 1/2\s+\(2\) 0\.148 x 1 1/2\s+370\s+975\s+1105\s+1185\s+320\s+840\s+950\s+1020", t180)
    for h in simpson.HIP_RIDGE[1:]:
        pat = (re.escape(h[0]) + r".*?" + re.escape(h[4]) + r"\s+" + re.escape(h[5]) + r"\s+" + re.escape(h[6]).replace(r"\ SD", r" SD") + r"\s+"
               + re.escape(h[7]) + r"\s+" + r"\s+".join(str(x) for x in (h[9][0], h[9][1], h[10][0], h[10][1])))
        assert re.search(pat, t180), h[0]


def test_vpa_and_hip_ridge_by_hand():
    """VPA2 (p. 181), DF/SP: uplift 255, download 1,105, F1 345, F2 300 lb. Uplift 120 with F1 80 and F2 50: 120/255 + 80/345 + 50/300 =
    0.4706 + 0.2319 + 0.1667 = 0.869; download 600 with the same laterals: 0.5430 + 0.2319 + 0.1667 = 0.942. SPF/HF uses 220 / 950 / 295 / 260.
    Pitch outside 3:12 to 12:12 refused. HRC1.81 DF/SP per hip: snow 1,105 lb; HHRC: one download value; 1,500 lb per hip with 400 lb
    uplift: HRC1.81 (1,185 roof) is short, HHRC4/1.81 (3,110) is first."""
    A = pytest.approx
    h = simpson.vpa("1 1/2", "first that works", "DF/SP", uplift=120, download=600, F1=80, F2=50, pitch=6)
    rows = {n: (d, c) for n, d, c in h["rows"]}
    assert h["row"][0] == "VPA2" and rows["uplift with lateral, U/Ua + F1/F1a + F2/F2a"][0] == A(120 / 255 + 80 / 345 + 50 / 300)
    assert rows["download with lateral, D/Da + F1/F1a + F2/F2a"][0] == A(600 / 1105 + 80 / 345 + 50 / 300)
    s = simpson.vpa("3 1/2", "VPA4", "SPF/HF", uplift=100, pitch=12)
    assert s["allow"] == dict(uplift=220, download=1070, F1=295, F2=260) and len(s["rows"]) == 1
    with pytest.raises(simpson.SimpsonError, match="3:12 to 12:12"):
        simpson.vpa("3 1/2", "VPA4", "DF/SP", uplift=100, pitch=2)
    with pytest.raises(simpson.SimpsonError, match="not the VPA"):
        simpson.vpa("3 1/2", "VPA2", "DF/SP", uplift=100, pitch=6)
    assert simpson.hip_ridge("HRC1.81", "DF/SP", 1000, 0, "snow (115)", 30)["allow_down"] == 1105
    assert simpson.hip_ridge("HRC1.81", "SPF/HF", 0, 300, "floor (100)", 0)["allow_up"] == 320
    h = simpson.hip_ridge("first that works", "DF/SP", 1500, 400, "roof (125)", 20)
    assert h["row"][0] == "HHRC4/1.81" and h["allow_down"] == 3110 and h["allow_up"] == 1490
    assert simpson.hip_ridge("HHRC44", "SPF/HF", 2000, 0, "floor (100)")["allow_down"] == 2315
    with pytest.raises(simpson.SimpsonError, match="0 to 45"):
        simpson.hip_ridge("HRC1.81", "DF/SP", 500, 0, "floor (100)", 50)
    from strukit import ws_more
    sh = ws_more.rafter_connector_sheet("RC", "VPA rafter to top plate", "first that works", "DF/SP", "1 1/2", 6, 0, 600, None, 120, 80, 50, "R2")
    assert sh.ok
