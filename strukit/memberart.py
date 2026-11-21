"""Member pictures for calc sheets: the side view and the cut section of a member, drawn
so a steel beam reads as steel and a wood member reads as wood.

Sections are drawn to scale from the member's real dimensions. Side views show the true
span; the depth is enlarged where a true-scale depth would be too thin to read, and the
sheet says so.
"""
import math
import random

STEEL_FILL, STEEL_LINE = (0.80, 0.84, 0.88), (0.17, 0.22, 0.28)
WOOD_FILL, WOOD_LINE, WOOD_GRAIN = (0.90, 0.80, 0.62), (0.42, 0.28, 0.13), (0.66, 0.49, 0.30)


def elev_depth(span_in, d_in, width_pt, min_pt=9.0, max_pt=16.0):
    """Depth of the side view in points, and whether it is true to scale."""
    true = width_pt * d_in / span_in
    used = min(max(true, min_pt), max_pt)
    return used, abs(used - true) < 0.05


def steel_elevation(c, x, y, w, h, d_in, tf_in):
    """Side view of an I-shape: both flanges as solid bands, the web between them.
    (x, y) is the bottom left corner; h is the drawn depth."""
    tf = max(h * tf_in / d_in, 1.5)
    c.setLineWidth(0.5); c.setStrokeColorRGB(*STEEL_LINE)
    c.setFillColorRGB(*STEEL_FILL); c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColorRGB(*STEEL_LINE)
    c.rect(x, y, w, tf, fill=1, stroke=0); c.rect(x, y + h - tf, w, tf, fill=1, stroke=0)


def steel_section(c, cx, cy, box_w, box_h, d, bf, tf, tw, k=None):
    """Cut section of an I-shape, to scale, centred on (cx, cy) inside box_w x box_h.
    Returns the scale used (points per inch)."""
    s = min(box_w / bf, box_h / d)
    D, B, TF, TW = d * s, bf * s, tf * s, tw * s
    r = max(0.0, min(((k - tf) if k else 0.0) * s, (B - TW) / 2 - 0.5, (D - 2 * TF) / 2 - 0.5))
    x0, y0, xw = cx - B / 2, cy - D / 2, cx - TW / 2
    p = c.beginPath()
    p.moveTo(x0, y0); p.lineTo(x0 + B, y0); p.lineTo(x0 + B, y0 + TF)
    p.lineTo(xw + TW + r, y0 + TF)
    p.curveTo(xw + TW + r / 2, y0 + TF, xw + TW, y0 + TF + r / 2, xw + TW, y0 + TF + r)
    p.lineTo(xw + TW, y0 + D - TF - r)
    p.curveTo(xw + TW, y0 + D - TF - r / 2, xw + TW + r / 2, y0 + D - TF, xw + TW + r, y0 + D - TF)
    p.lineTo(x0 + B, y0 + D - TF); p.lineTo(x0 + B, y0 + D); p.lineTo(x0, y0 + D)
    p.lineTo(x0, y0 + D - TF); p.lineTo(xw - r, y0 + D - TF)
    p.curveTo(xw - r / 2, y0 + D - TF, xw, y0 + D - TF - r / 2, xw, y0 + D - TF - r)
    p.lineTo(xw, y0 + TF + r)
    p.curveTo(xw, y0 + TF + r / 2, xw - r / 2, y0 + TF, xw - r, y0 + TF)
    p.lineTo(x0, y0 + TF); p.close()
    c.setLineWidth(0.7); c.setStrokeColorRGB(*STEEL_LINE); c.setFillColorRGB(*STEEL_FILL)
    c.drawPath(p, fill=1, stroke=1)
    return s


def wood_elevation(c, x, y, w, h, plies=1, seed=7):
    """Side view of a sawn or built-up wood member: tan face with grain lines running
    along the length. Ply lines are not visible from the side, so plies only seeds the
    grain so that different members do not look identical."""
    rnd = random.Random(seed + plies)
    c.setLineWidth(0.5); c.setStrokeColorRGB(*WOOD_LINE)
    c.setFillColorRGB(*WOOD_FILL); c.rect(x, y, w, h, fill=1, stroke=1)
    c.saveState()
    clip = c.beginPath(); clip.rect(x, y, w, h); c.clipPath(clip, stroke=0, fill=0)
    c.setStrokeColorRGB(*WOOD_GRAIN); c.setLineWidth(0.35)
    n = max(3, int(h / 2.2))
    for i in range(n):
        yy = y + h * (i + 0.5) / n
        amp, ph, wl = rnd.uniform(0.2, 0.7), rnd.uniform(0, 6.28), rnd.uniform(60, 140)
        p = c.beginPath(); p.moveTo(x, yy + amp * math.sin(ph))
        for j in range(1, 41):
            xx = x + w * j / 40
            p.lineTo(xx, yy + amp * math.sin(ph + 6.28 * (xx - x) / wl))
        c.drawPath(p, fill=0, stroke=1)
    c.restoreState()


def wood_section(c, cx, cy, box_w, box_h, b, d, plies=1):
    """Cut section of a wood member, to scale: end grain shown as growth rings, one set
    per ply, with the ply joints drawn. b is the total width. Returns points per inch."""
    s = min(box_w / b, box_h / d)
    B, D = b * s, d * s
    x0, y0 = cx - B / 2, cy - D / 2
    c.setLineWidth(0.7); c.setStrokeColorRGB(*WOOD_LINE); c.setFillColorRGB(*WOOD_FILL)
    c.rect(x0, y0, B, D, fill=1, stroke=1)
    pw = B / plies
    for i in range(plies):
        px = x0 + i * pw
        c.saveState()
        clip = c.beginPath(); clip.rect(px, y0, pw, D); c.clipPath(clip, stroke=0, fill=0)
        c.setStrokeColorRGB(*WOOD_GRAIN); c.setLineWidth(0.35)
        ox = px + pw * (0.5 + (0.9 if i % 2 else -0.9))      # pith off to one side
        oy = y0 - D * 0.25
        rr = 3.0
        while rr < 2.2 * max(pw, D):
            c.circle(ox, oy, rr, fill=0, stroke=1); rr += 2.4
        c.restoreState()
        if i:
            c.setStrokeColorRGB(*WOOD_LINE); c.setLineWidth(0.5); c.line(px, y0, px, y0 + D)
    return s


CONC_FILL, CONC_LINE, CONC_DOT = (0.88, 0.88, 0.86), (0.25, 0.25, 0.25), (0.48, 0.48, 0.46)
SOIL_LINE, BAR = (0.40, 0.33, 0.22), (0.05, 0.05, 0.05)


def _concrete(c, x, y, w, h, seed=3):
    """Concrete in section: light grey with the drafting stipple (dots and small
    triangles for aggregate)."""
    c.setLineWidth(0.7); c.setStrokeColorRGB(*CONC_LINE); c.setFillColorRGB(*CONC_FILL)
    c.rect(x, y, w, h, fill=1, stroke=1)
    rnd = random.Random(seed + int(w * 7 + h * 13))
    c.saveState()
    clip = c.beginPath(); clip.rect(x + 0.5, y + 0.5, w - 1, h - 1); c.clipPath(clip, stroke=0, fill=0)
    c.setFillColorRGB(*CONC_DOT); c.setStrokeColorRGB(*CONC_DOT); c.setLineWidth(0.3)
    for _ in range(int(w * h / 14)):
        c.circle(x + rnd.uniform(1, w - 1), y + rnd.uniform(1, h - 1), 0.25, fill=1, stroke=0)
    for _ in range(int(w * h / 90)):
        px, py, a = x + rnd.uniform(2, w - 2), y + rnd.uniform(2, h - 2), rnd.uniform(0, 6.28)
        t = c.beginPath()
        for k in range(3):
            xx, yy = px + 1.3 * math.cos(a + k * 2.094), py + 1.3 * math.sin(a + k * 2.094)
            (t.moveTo if k == 0 else t.lineTo)(xx, yy)
        t.close(); c.drawPath(t, fill=0, stroke=1)
    c.restoreState()


def _grade(c, x1, x2, y):
    """Finished grade line with earth ticks under it."""
    c.setStrokeColorRGB(*SOIL_LINE); c.setLineWidth(0.7); c.line(x1, y, x2, y)
    c.setLineWidth(0.35)
    xx = x1 + 1
    while xx + 3 <= x2:
        c.line(xx, y - 3, xx + 3, y); xx += 4


def footing_section(c, cx, y0, box_w, box_h, W_in, h_in, sup_w_in, sup_kind, cover_in,
                    db_low_in, n_dots, db_dot_in, plate_w_in=None, stem_h_in=0.0,
                    soil_depth_in=0.0):
    """Section through a footing, to scale, bottom of footing at y0, centred on cx.
    sup_kind: "concrete" (stem wall or pier), "wood" or "steel" (post). The lower bar
    layer is drawn as a line (bars running across the page); n_dots bars of the other
    direction are drawn end-on above it. Returns points per inch."""
    sup_h = stem_h_in if stem_h_in else max(1.6 * h_in, 12.0)
    s = min(box_w / W_in, box_h / (h_in + max(sup_h, soil_depth_in) + 2))
    W, H, SW, SH = W_in * s, h_in * s, sup_w_in * s, sup_h * s
    x0 = cx - W / 2
    if soil_depth_in:
        gy = y0 + H + soil_depth_in * s
        _grade(c, x0 - 6, cx - SW / 2, gy); _grade(c, cx + SW / 2, x0 + W + 6, gy)
    _concrete(c, x0, y0, W, H)
    top = y0 + H
    if plate_w_in:
        PW = plate_w_in * s
        c.setFillColorRGB(*STEEL_LINE); c.rect(cx - PW / 2, top, PW, max(0.25 * s, 1.0), fill=1, stroke=0)
        top += max(0.25 * s, 1.0)
    if sup_kind == "concrete":
        _concrete(c, cx - SW / 2, top, SW, SH, seed=11)
    elif sup_kind == "wood":
        c.saveState(); c.translate(cx - SW / 2, top); c.rotate(90)
        wood_elevation(c, 0, -SW, SH, SW); c.restoreState()
    else:
        c.setLineWidth(0.5); c.setStrokeColorRGB(*STEEL_LINE); c.setFillColorRGB(*STEEL_FILL)
        c.rect(cx - SW / 2, top, SW, SH, fill=1, stroke=1)
    if not stem_h_in:                                    # break line: the member continues
        c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1.6); c.line(cx - SW / 2 - 2, top + SH, cx + SW / 2 + 2, top + SH)
        c.setStrokeColorRGB(*CONC_LINE); c.setLineWidth(0.4)
        c.line(cx - SW / 2 - 2, top + SH - 1.5, cx + SW / 2 + 2, top + SH + 1.5)
    # bars
    cov, dbl, dbd = cover_in * s, max(db_low_in * s, 1.0), max(db_dot_in * s, 1.6)
    c.setStrokeColorRGB(*BAR); c.setFillColorRGB(*BAR); c.setLineWidth(dbl)
    yb = y0 + cov + dbl / 2
    c.line(x0 + cov, yb, x0 + W - cov, yb)
    yd = y0 + cov + dbl + dbd / 2
    for i in range(n_dots):
        xx = x0 + cov + dbd / 2 + (W - 2 * cov - dbd) * (i / (n_dots - 1) if n_dots > 1 else 0.5)
        c.circle(xx, yd, dbd / 2, fill=1, stroke=0)
    return s


def footing_plan(c, cx, cy, box, B_in, L_in, col_x_in, col_y_in, n_x, n_y, cover_in,
                 plate_x_in=None, plate_y_in=None):
    """Plan of an isolated footing, to scale: outline, the bars each way, the column and
    its base plate. Returns points per inch."""
    s = min(box / B_in, box / L_in)
    B, L = B_in * s, L_in * s
    x0, y0 = cx - B / 2, cy - L / 2
    c.setLineWidth(0.7); c.setStrokeColorRGB(*CONC_LINE); c.setFillColorRGB(*CONC_FILL)
    c.rect(x0, y0, B, L, fill=1, stroke=1)
    cov = cover_in * s
    c.setStrokeColorRGB(*BAR); c.setLineWidth(0.6)
    for i in range(n_x):                                   # bars running in x
        yy = y0 + cov + (L - 2 * cov) * (i / (n_x - 1) if n_x > 1 else 0.5)
        c.line(x0 + cov, yy, x0 + B - cov, yy)
    for i in range(n_y):
        xx = x0 + cov + (B - 2 * cov) * (i / (n_y - 1) if n_y > 1 else 0.5)
        c.line(xx, y0 + cov, xx, y0 + L - cov)
    if plate_x_in:
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*STEEL_LINE); c.setLineWidth(0.6)
        c.rect(cx - plate_x_in * s / 2, cy - plate_y_in * s / 2, plate_x_in * s, plate_y_in * s, fill=1, stroke=1)
    c.setFillColorRGB(*STEEL_LINE); c.setStrokeColorRGB(*STEEL_LINE)
    c.rect(cx - col_x_in * s / 2, cy - col_y_in * s / 2, col_x_in * s, col_y_in * s, fill=1, stroke=1)
    return s


def steel_column_elevation(c, cx, y, h, d_in, tf_in, height_in, braces=()):
    """Side view of a steel column standing up, seen with the web toward the reader:
    two flange lines and the web between. braces are heights (in) of intermediate brace
    points, marked on the column. Width is enlarged enough to read."""
    w = min(max(h * d_in / height_in, 7.0), 12.0)
    tf = max(w * tf_in / d_in, 1.3)
    c.setLineWidth(0.5); c.setStrokeColorRGB(*STEEL_LINE); c.setFillColorRGB(*STEEL_FILL)
    c.rect(cx - w / 2, y, w, h, fill=1, stroke=1)
    c.setFillColorRGB(*STEEL_LINE)
    c.rect(cx - w / 2, y, tf, h, fill=1, stroke=0); c.rect(cx + w / 2 - tf, y, tf, h, fill=1, stroke=0)
    c.setStrokeColorRGB(0.60, 0.24, 0.0); c.setLineWidth(0.9)
    for b in braces:
        m = y + h * b / height_in
        c.line(cx - 2.5, m - 2.5, cx + 2.5, m + 2.5); c.line(cx - 2.5, m + 2.5, cx + 2.5, m - 2.5)
    return w


def _dim_h(c, x1, x2, y, text, font, ext_from=None):
    """Horizontal dimension line from x1 to x2 at height y, with ticks and centred text
    below it. ext_from: y of the object, for extension lines."""
    c.setStrokeColorRGB(0.23, 0.28, 0.34); c.setFillColorRGB(0.23, 0.28, 0.34); c.setLineWidth(0.4)
    c.line(x1, y, x2, y)
    for q in (x1, x2):
        if ext_from is not None:
            c.line(q, ext_from, q, y - 2.5 if y < ext_from else y + 2.5)
        c.line(q - 1.6, y - 1.6, q + 1.6, y + 1.6)
    c.setFont(font, 6)
    c.drawCentredString((x1 + x2) / 2, y - 7.5, text)


def weld_plan(c, x, y, w, h, n_lines, length_in, size_in, font="Helvetica"):
    """Plan of a plate lapped on a wider plate, the fillet welds along its long edges shown
    hatched, with the weld length dimensioned. One weld is drawn on one edge; two or more on
    both edges (the count is on the sheet)."""
    dim_h = 13.0
    bx, by, bw, bh = x, y + dim_h, w, h - dim_h                                   # back plate
    c.setLineWidth(0.6); c.setStrokeColorRGB(*STEEL_LINE)
    c.setFillColorRGB(0.87, 0.90, 0.93); c.rect(bx, by, bw, bh, fill=1, stroke=1)
    px, pw, ph = bx + bw * 0.30, bw * 0.58, bh * 0.42
    py = by + (bh - ph) / 2
    c.setFillColorRGB(*STEEL_FILL)
    c.rect(bx - 8, py, px + pw - bx + 8, ph, fill=1, stroke=1)                    # lapped plate, running off to the left
    c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(1.4); c.line(bx - 8, py - 1, bx - 8, py + ph + 1)   # break
    band = max(2.2, min(3.6, size_in * 10))
    c.setFillColorRGB(0.35, 0.38, 0.42); c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(0.3)
    for ey in [py + ph] + ([py - band] if n_lines >= 2 else []):
        c.rect(px, ey, pw, band, fill=1, stroke=0)
        k = px
        while k < px + pw - 1:
            c.line(k, ey, k + band * 0.7, ey + band); k += 3.0
    _dim_h(c, px, px + pw, by - 6.0, f"{length_in:g}", font, ext_from=py - (band if n_lines >= 2 else 0) - 1)
    return py + ph / 2                                                              # height of the cut line


def weld_section(c, x, y, w, h, n_lines, size_in, t_top_in=None, font="Helvetica"):
    """Section across the welds: the lapped plate on the wider plate with a fillet weld at
    one or both edges, the weld leg dimensioned. Not to scale unless the plate thickness is
    given; the leg is drawn in proportion to it when it is."""
    tb = h * 0.22                                                                  # back plate
    tt = h * 0.26                                                                  # lapped plate
    leg = tt * min(1.0, (size_in / t_top_in) if t_top_in else 0.75)
    by = y + 14.0
    c.setLineWidth(0.6); c.setStrokeColorRGB(*STEEL_LINE)
    c.setFillColorRGB(0.87, 0.90, 0.93); c.rect(x, by, w, tb, fill=1, stroke=1)
    px, pw = x + w * 0.24, w * 0.52
    c.setFillColorRGB(*STEEL_FILL); c.rect(px, by + tb, pw, tt, fill=1, stroke=1)
    c.setFillColorRGB(0.35, 0.38, 0.42)
    sides = [(px + pw, 1)] + ([(px, -1)] if n_lines >= 2 else [])
    for ex, sgn in sides:
        p = c.beginPath(); p.moveTo(ex, by + tb); p.lineTo(ex + sgn * leg, by + tb); p.lineTo(ex, by + tb + leg); p.close()
        c.drawPath(p, fill=1, stroke=1)
    ex = px + pw                                                                   # dimension the right-hand weld leg
    _dim_h(c, ex, ex + leg, by - 4.0, f"{size_in:g}", font, ext_from=by + tb)
    c.setStrokeColorRGB(0.23, 0.28, 0.34); c.setLineWidth(0.4)                     # vertical leg
    xd = ex + leg + 6
    c.line(xd, by + tb, xd, by + tb + leg)
    for q in (by + tb, by + tb + leg):
        c.line(ex + 1, q, xd + 2.5, q); c.line(xd - 1.6, q - 1.6, xd + 1.6, q + 1.6)
    c.setFont(font, 6); c.drawString(xd + 3, by + tb + leg / 2 - 2, f"{size_in:g}")


def bolt_picture(c, x, y, w, h, n, spacing_in, edge_in, d_in, font="Helvetica"):
    """A plate with its line of bolts, to scale along the line: holes, bolt heads, the
    edge the load pushes toward at the right, and a dimension line under the plate giving
    the edge distance and the bolt spacing."""
    dim_h = 13.0                                         # room under the plate for the dimensions
    total = edge_in + (n - 1) * spacing_in + max(edge_in, 1.5 * d_in)
    s = min(w / total, (h - dim_h) / (6 * d_in))
    pw, ph = total * s, min(h - dim_h, max(6 * d_in * s, 14))
    px, py = x + (w - pw) / 2, y + dim_h + (h - dim_h - ph) / 2
    c.setLineWidth(0.6); c.setStrokeColorRGB(*STEEL_LINE); c.setFillColorRGB(*STEEL_FILL)
    c.rect(px, py, pw, ph, fill=1, stroke=1)
    r = max(d_in * s / 2, 1.6)
    xs = [px + pw - (edge_in + i * spacing_in) * s for i in range(n)]
    for cx in xs:
        c.setFillColorRGB(1, 1, 1); c.circle(cx, py + ph / 2, r * 1.12, fill=1, stroke=1)
        c.setFillColorRGB(0.30, 0.34, 0.39); c.circle(cx, py + ph / 2, r * 0.82, fill=1, stroke=0)
    # dimension line: plate edge, then each bolt
    yd = py - 6.0
    pts = [px + pw] + xs
    c.setStrokeColorRGB(0.23, 0.28, 0.34); c.setFillColorRGB(0.23, 0.28, 0.34); c.setLineWidth(0.4)
    c.line(pts[-1], yd, pts[0], yd)
    for q in pts:
        c.line(q, py - 1.5, q, yd - 2.5)                  # extension line
        c.line(q - 1.6, yd - 1.6, q + 1.6, yd + 1.6)      # tick
    c.setFont(font, 6)
    gaps = [(pts[0], pts[1], f"{edge_in:g}")] + [(pts[k], pts[k + 1], f"{spacing_in:g}") for k in range(1, len(pts) - 1)]
    room = min(abs(a - b) for a, b, _ in gaps) >= c.stringWidth("0.00", font, 6) + 2
    for k, (a, b, t) in enumerate(gaps):
        if room or k < 2:
            label = t if room or k == 0 else t + " typ."
            c.drawCentredString((a + b) / 2, yd - 7.5, label)
    return px, py, pw, ph, s
