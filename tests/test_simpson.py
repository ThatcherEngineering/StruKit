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
