"""Live load reduction, ASCE/SEI 7-22 Sect. 4.7 and 4.8. Hand calculations."""
import pytest
from strukit import liveload as ll


def test_floor_reduction_by_hand():
    """Interior column, AT = 900 ft2, 50 psf: KLL AT = 3,600; 0.25 + 15/60 = 0.50 -> 25.0 psf.
    Interior beam, AT = 400 ft2: KLL AT = 800; 0.25 + 15/28.28 = 0.780 -> 39.0 psf (of 50).
    Interior column, AT = 2,500 ft2, three floors: KLL AT = 10,000; 0.25 + 0.15 = 0.40 -> 0.40 Lo; one floor: 0.50 minimum.
    All other members, AT = 300 ft2: KLL AT = 300, under 400: not reduced."""
    r = ll.floor(50, "interior column", 900, 1)
    assert r["L"] == pytest.approx(25.0) and r["KLL_AT"] == 3600 and r["by"] == "Eq. 4.7-1"
    assert ll.floor(50, "interior beam", 400, 1)["L"] == pytest.approx(50 * (0.25 + 15 / 800 ** 0.5)) == pytest.approx(39.02, abs=0.01)
    assert ll.floor(50, "interior column", 2500, 3)["factor"] == pytest.approx(0.40)
    one = ll.floor(50, "interior column", 2500, 1)
    assert one["factor"] == 0.5 and "minimum 0.50" in one["by"]
    assert ll.floor(50, "interior column", 40000, 3)["factor"] == 0.4
    assert ll.floor(50, "all other members", 300, 1)["factor"] == 1.0
    assert ll.floor(40, "interior beam", 200, 1)["factor"] == pytest.approx(1.0)        # 0.25 + 15/20 = 1.0 at exactly 400
    # heavy loads, garages, assembly
    assert ll.floor(125, "interior column", 900, 1)["factor"] == 1.0 and ll.floor(125, "interior column", 900, 2)["factor"] == 0.8
    assert ll.floor(125, "interior beam", 250, 2)["factor"] == pytest.approx(0.25 + 15 / 500 ** 0.5)      # 0.921: above 0.8, so Eq. 4.7-1 holds
    assert ll.floor(40, "interior column", 900, 1, "passenger vehicle garage")["factor"] == 1.0
    assert ll.floor(40, "interior column", 900, 2, "passenger vehicle garage")["factor"] == 0.8
    assert ll.floor(100, "interior column", 900, 3, "assembly area")["factor"] == 1.0
    with pytest.raises(ll.LiveLoadError):
        ll.floor(50, "girder", 900, 1)


def test_roof_reduction_by_hand():
    """AT = 400 ft2, 6 on 12: R1 = 0.8, R2 = 0.9 -> 20(0.72) = 14.4 psf. AT = 700 ft2, 12 on 12: 20(0.36) = 7.2 -> 12 psf.
    AT = 150 ft2, 3 on 12: 20 psf."""
    r = ll.roof(20, 400, 6)
    assert (r["R1"], r["R2"]) == pytest.approx((0.8, 0.9)) and r["Lr"] == pytest.approx(14.4) and r["by"] == "Eq. 4.8-1"
    assert ll.roof(20, 700, 12)["Lr"] == 12.0 and ll.roof(20, 700, 12)["by"] == "minimum 12 psf"
    assert ll.roof(20, 150, 3)["Lr"] == 20.0 and ll.roof(20, 600, 4)["Lr"] == pytest.approx(12.0)


def test_live_load_sheet(tmp_path):
    from strukit.gui import calc
    from strukit import calcsheet
    v = dict(mark="LL1", floors=[dict(name="C1", element="interior column", Lo="50", source="offices, Table 4.3-1", AT="900", floors="1"),
                                 dict(name="C2", element="interior column", Lo="40", source="garage, Table 4.3-1", AT="900", floors="2", occupancy="passenger vehicle garage")],
             roofs=[dict(name="RB1", Lo="20", source="ordinary roof, Table 4.3-1", AT="400", F="6")])
    sheet, kind, _ = calc.build("live_load", v, dict(job="2026-000", name="Test", method="ASD"))
    assert kind == "simple" and sheet.live["floors"][0]["L"] == pytest.approx(25.0) and sheet.live["floors"][1]["factor"] == 0.8
    assert sheet.live["roofs"][0]["Lr"] == pytest.approx(14.4) and len(sheet.blocks) == 2
    calcsheet._simple_pdf(sheet, str(tmp_path / "ll.pdf"), "2026-000", "ASCE/SEI 7-22", "2026-11-23")
    with pytest.raises(calc.Missing):
        calc.build("live_load", dict(mark="LL1"), dict(job="2026-000", name="Test", method="ASD"))
    with pytest.raises(calc.Missing):
        calc.build("live_load", dict(mark="LL1", floors=[dict(name="C1", element="interior column", Lo="50", AT="900", floors="1")]), dict(job="2026-000", name="Test", method="ASD"))
