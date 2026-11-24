"""Coped beam end against AISC Design Examples v16.0, Example II.A-6 (W21x62, 8 in. deep by 9 in. long top cope)."""
import pytest
from strukit import cope, shapes


def test_example_IIA6():
    b = shapes.get("W21X62")
    r = cope.top_cope(b["d"], b["tw"], b["bf"], b["tf"], 50, 65, 8.0, 9.0, 9.5)
    assert r["hc"] == pytest.approx(13.0) and r["f"] == pytest.approx(0.858, abs=0.002) and r["k"] == pytest.approx(4.04, abs=0.01)
    assert r["Sc"] == pytest.approx(17.8, rel=0.01) and r["Zc"] == pytest.approx(32.2, rel=0.01)       # Manual Tables 9-2a, 9-2b
    assert r["lam"] == pytest.approx(32.5) and r["lam_p"] == pytest.approx(21.3, abs=0.1)
    assert r["Mn"] == pytest.approx(1230, rel=0.01) and r["R_flex"] == pytest.approx(129, rel=0.01)
    assert 0.9 * r["R_flex"] == pytest.approx(116, rel=0.01) and r["R_flex"] / 1.67 == pytest.approx(77.2, rel=0.01)
    assert r["R_vy"] == pytest.approx(156, rel=0.005) and r["R_vr"] == pytest.approx(203, rel=0.005)


def test_branches_and_limits():
    b = shapes.get("W21X62")
    a = (b["d"], b["tw"], b["bf"], b["tf"], 50, 65)
    short = cope.top_cope(*a, 2.0, 1.5, 2.0)
    assert short["Mn"] == pytest.approx(short["Mp"])                    # stocky: plastic moment
    long_ = cope.top_cope(*a, 8.0, 30.0, 30.5)
    assert long_["f"] == pytest.approx(1 + 30 / b["d"]) and long_["k"] == pytest.approx(2.2 * 13 / 30) and long_["k1"] >= 1.61
    with pytest.raises(cope.CopeError):
        cope.top_cope(*a, 11.0, 9.0, 9.5)
    bs = cope.web_block_shear(0.4, 50, 65, 3, 3, 1.5, 1.75, 0.875)
    assert bs["Agv"] == pytest.approx(3.0) and bs["Anv"] == pytest.approx(3.0 - 2.5 * 0.875 * 0.4) and bs["Ant"] == pytest.approx((1.75 - 0.4375) * 0.4)
