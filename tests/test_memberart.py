"""Member pictures: sections are to scale, side views say when the depth is enlarged."""
from reportlab.pdfgen import canvas

from strukit import memberart, shapes


def test_section_scale_fits_box(tmp_path):
    c = canvas.Canvas(str(tmp_path / "a.pdf"))
    p = shapes.get("W18X50")
    s = memberart.steel_section(c, 100, 100, 40, 46, p["d"], p["bf"], p["tf"], p["tw"], p["kdes"])
    assert abs(s - 46 / 18.0) < 1e-9                     # depth governs: 46 pt for 18 in
    s = memberart.wood_section(c, 200, 100, 44, 60, 3.0, 9.25, plies=2)
    assert abs(s - 60 / 9.25) < 1e-9
    memberart.steel_elevation(c, 50, 300, 200, 10, p["d"], p["tf"])
    memberart.wood_elevation(c, 50, 400, 200, 12, plies=2)
    c.save()


def test_elevation_depth_flag():
    h, true = memberart.elev_depth(35 * 12, 18.0, 166)   # true depth 7.1 pt: enlarged to 9
    assert h == 9.0 and not true
    h, true = memberart.elev_depth(10 * 12, 12.0, 166)   # true depth 16.6 pt: capped
    assert h == 16.0 and not true
    h, true = memberart.elev_depth(20 * 12, 16.0, 166)   # 11.07 pt: drawn true
    assert abs(h - 11.0667) < 1e-3 and true
