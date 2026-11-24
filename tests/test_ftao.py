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
