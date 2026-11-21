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
