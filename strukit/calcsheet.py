"""Calc sheets (PDF), one page per member.

Layout rules (Thatcher Engineering): firm title block top and bottom, sheet titles in
title case, every check with demand, capacity, D/C, result and code reference, the
governing equations with intermediate values, assumptions stated. No program names,
run IDs or revision logs on the page. The PE stamp goes on the package cover only.
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from . import memberart

FIRM = "THATCHER ENGINEERING, LLC"
FIRM_LINE = "4050 Trail Stone Cir., Castle Rock, CO 80108  |  719.225.0150"
INK, GREY, BLUE, FLAGC, OKC = (0.10, 0.11, 0.13), (0.29, 0.31, 0.35), (0.12, 0.31, 0.47), \
    (0.60, 0.24, 0.0), (0.11, 0.42, 0.23)
LM, RM = 54, 558                                     # left / right margins, points


def _fmt(v, unit=""):
    a = abs(v)
    s = f"{v:,.0f}" if a >= 1000 else f"{v:.1f}" if a >= 100 else f"{v:.2f}" if a >= 1 else f"{v:.3f}"
    return f"{s} {unit}".strip()


class _Page:
    def __init__(self, path, title, job, code, method, page, pages, date):
        self.c = canvas.Canvas(path, pagesize=letter)
        self.c.setTitle(title)
        self.c.setAuthor("Thatcher Engineering, LLC")
        c = self.c
        c.setFillColorRGB(*GREY); c.setFont("Helvetica-Bold", 8)
        c.drawString(LM, 742, FIRM)
        c.setFillColorRGB(*INK); c.setFont("Helvetica-Bold", 16)
        c.drawString(LM, 722, title)
        c.setFont("Helvetica", 8)
        for i, (k, v) in enumerate((("Job", job), ("Code", code), ("Method", method))):
            c.setFillColorRGB(*GREY); c.drawRightString(410, 744 - 11 * i, k)
            c.setFillColorRGB(*INK); c.drawString(416, 744 - 11 * i, v)
        c.setLineWidth(1.5); c.line(LM, 714, RM, 714)
        c.setLineWidth(0.6); c.line(LM, 50, RM, 50)
        c.setFillColorRGB(*GREY); c.setFont("Helvetica", 7.5)
        c.drawString(LM, 40, FIRM_LINE)
        c.drawCentredString(306, 40, date)
        c.drawRightString(RM, 40, f"Page {page} of {pages}")
        self.y = 698

    def head(self, text):
        c = self.c
        self.y -= 4
        c.setFillColorRGB(*BLUE); c.setFont("Helvetica-Bold", 8)
        c.drawString(LM, self.y, text.upper())
        self.y -= 12

    def kv(self, rows, x=LM, kw=92, y=None):
        c = self.c
        yy = self.y if y is None else y
        for k, v in rows:
            c.setFont("Helvetica", 8.5); c.setFillColorRGB(*GREY); c.drawString(x, yy, k)
            c.setFillColorRGB(*INK); c.drawString(x + kw, yy, v)
            yy -= 11.5
        if y is None:
            self.y = yy
        return yy

    def text(self, s, font="Helvetica", size=8.5, color=INK, x=LM, dy=11.5):
        self.c.setFont(font, size); self.c.setFillColorRGB(*color)
        self.c.drawString(x, self.y, s)
        self.y -= dy

    def wrap(self, s, width=96, **kw):
        words, line = s.split(), ""
        for w in words:
            if len(line) + len(w) + 1 > width:
                self.text(line, **kw); line = w
            else:
                line = (line + " " + w).strip()
        if line:
            self.text(line, **kw)


def _diagram(c, x0, y0, w, h, xs, vals, color, label):
    """Filled diagram of vals over xs inside the box (x0, y0, w, h); baseline at zero."""
    vmax = max(max(vals), 0.0); vmin = min(min(vals), 0.0)
    rng = (vmax - vmin) or 1.0
    L = xs[-1] - xs[0] or 1.0
    zero = y0 + h * (0 - vmin) / rng
    p = c.beginPath(); p.moveTo(x0, zero)
    step = max(1, len(xs) // 160)
    for i in range(0, len(xs), step):
        p.lineTo(x0 + w * (xs[i] - xs[0]) / L, y0 + h * (vals[i] - vmin) / rng)
    p.lineTo(x0 + w, y0 + h * (vals[-1] - vmin) / rng); p.lineTo(x0 + w, zero); p.close()
    c.setFillColorRGB(*[min(1, 0.80 + 0.2 * v) for v in color]); c.setStrokeColorRGB(*color)
    c.setLineWidth(0.8); c.drawPath(p, fill=1, stroke=1)
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.line(x0, zero, x0 + w, zero)
    c.setFillColorRGB(*color); c.setFont("Courier", 7.5); c.drawString(x0, y0 + h + 3, label)
    c.setStrokeColorRGB(*INK)


def steel_beam_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
    """Write the calc sheet for a ws_steel_beam.SteelBeamSheet. `combos` are the Combo
    objects that were run, printed with their sources."""
    p = _Page(path, f"Beam {sheet.mark} - Steel Bending Member", job, code, sheet.method,
              page, pages, date)
    c, pr = p.c, sheet.props

    # member data (left) and loading sketch (right)
    top = p.y
    p.head("Member")
    p.kv([("Section", f"{sheet.shape}  (Fy = {sheet.Fy:g} ksi)"),
          ("Span", f"{sheet.span_ft:g} ft, simply supported"),
          ("Bracing", sheet.bracing_text),
          ("Dimensions", f"d = {pr['d']:g} in, bf = {pr['bf']:g} in"),
          ("", f"tf = {pr['tf']:g} in, tw = {pr['tw']:g} in"),
          ("Properties", f"Zx = {pr['Zx']:g} in3, Sx = {pr['Sx']:g} in3"),
          ("", f"Ix = {pr['Ix']:g} in4, ry = {pr['ry']:g} in"),
          ("", f"rts = {pr['rts']:g} in, J = {pr['J']:g} in4, ho = {pr['ho']:g} in"),
          ("Source", "AISC Shapes Database v16.0")])
    bottom_left = p.y
    x0, w = 338, 166
    c.setFillColorRGB(*BLUE); c.setFont("Helvetica-Bold", 8); c.drawString(x0, top - 4, "LOADING SKETCH")
    by = top - 64                                    # underside of the beam
    hb, true_scale = memberart.elev_depth(sheet.span_ft * 12, pr["d"], w)
    memberart.steel_elevation(c, x0, by, w, hb, pr["d"], pr["tf"])
    c.setStrokeColorRGB(*BLUE); c.setFillColorRGB(0.91, 0.93, 0.96); c.setLineWidth(0.6)
    if any(ld["kind"] == "uniform" for ld in sheet.loads):
        c.rect(x0, by + hb + 4, w, 10, fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.9)
    for xx in (x0 + 3, x0 + w - 3):
        t = c.beginPath(); t.moveTo(xx, by - 1); t.lineTo(xx - 6, by - 12); t.lineTo(xx + 6, by - 12); t.close()
        c.drawPath(t, fill=0, stroke=1)
    for ld in sheet.loads:
        if ld["kind"] == "point":
            xx = x0 + w * ld["x_ft"] / sheet.span_ft
            c.line(xx, by + hb + 30, xx, by + hb + 7)
            t = c.beginPath(); t.moveTo(xx, by + hb + 1); t.lineTo(xx - 3, by + hb + 8); t.lineTo(xx + 3, by + hb + 8); t.close()
            c.drawPath(t, fill=1, stroke=0)
    c.setFillColorRGB(*GREY); c.setFont("Courier", 7.5)
    c.drawCentredString(x0 + w / 2, by - 22, f"L = {sheet.span_ft:g} ft")
    if not true_scale:
        c.setFont("Helvetica", 6); c.drawCentredString(x0 + w / 2, by - 30, "side view: depth enlarged for clarity")
    uni = [f"{ld['case']} {ld['w']:.3f}" for ld in sheet.loads if ld["kind"] == "uniform"]
    if uni:
        c.setFillColorRGB(*BLUE); c.setFont("Courier", 7.5)
        c.drawCentredString(x0 + w / 2, by + hb + 34, "w = " + " + ".join(uni) + " kip/ft")
    for bx in getattr(sheet, "brace_points", []):
        xx = x0 + w * bx / sheet.span_ft
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(0.9)
        xx = min(max(xx, x0 + 4), x0 + w - 4); m = by + hb / 2
        c.line(xx - 2.5, m - 2.5, xx + 2.5, m + 2.5); c.line(xx - 2.5, m + 2.5, xx + 2.5, m - 2.5)
    # cut section, to scale
    sx = 536
    c.setFillColorRGB(*BLUE); c.setFont("Helvetica-Bold", 8); c.drawCentredString(sx, top - 4, "SECTION")
    memberart.steel_section(c, sx, top - 38, 40, 46, pr["d"], pr["bf"], pr["tf"], pr["tw"], pr.get("kdes"))
    c.setFillColorRGB(*GREY); c.setFont("Helvetica", 6); c.drawCentredString(sx, top - 72, "to scale")
    c.setStrokeColorRGB(*INK)
    p.y = min(bottom_left, by - 34) - 2

    p.head("Loads")
    for ld in sheet.loads:
        if ld["kind"] == "uniform":
            s = f"{ld['case']:<3} uniform  {ld['w']:.3f} kip/ft"
            if "x1_ft" in ld:
                s += f"  from {ld['x1_ft']:g} to {ld['x2_ft']:g} ft"
        else:
            s = f"{ld['case']:<3} point    {ld['P']:.2f} kip at {ld['x_ft']:g} ft"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font="Courier", size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in combos:
        ra, rb = sheet.reactions[cb.name]
        p.text(f"{cb.name:<18} reactions {ra:.2f} / {rb:.2f} kip", font="Courier", size=8, dy=10)
        p.text(cb.source, size=7.5, color=GREY, x=LM + 12)

    # diagrams for the governing combination
    p.y -= 4
    p.head(f"Shear and Moment, {sheet.governing['flexure']}")
    xs, V, M = sheet.diagram["x"], sheet.diagram["V"], sheet.diagram["M"]
    dy0 = p.y - 46
    _diagram(c, LM, dy0, 235, 38, xs, V, BLUE, f"V max = {max(abs(v) for v in V):.2f} kip")
    _diagram(c, LM + 269, dy0, 235, 38, xs, [-m for m in M], (0.54, 0.35, 0.0),
             f"M max = {max(abs(m) for m in M):.1f} kip-ft")
    p.y = dy0 - 12

    # governing strength calculation, line by line
    p.head("Flexural and Shear Strength (AISC 360-22)")
    c.setStrokeColorRGB(0.79, 0.81, 0.83); c.setLineWidth(0.5)
    box_top = p.y + 9
    for ln in sheet.steps:
        val = f"{ln.value:.2f}" if not ln.unit else _fmt(ln.value, ln.unit)
        c.setFont("Courier", 8); c.setFillColorRGB(*INK)
        c.drawString(LM + 6, p.y, f"{ln.label} = {val}")
        c.setFont("Helvetica", 7.5); c.setFillColorRGB(*GREY)
        c.drawRightString(RM - 6, p.y, ln.source)
        if ln.note:
            p.y -= 9
            c.drawString(LM + 18, p.y, ln.note)
        p.y -= 10.5
    c.rect(LM, p.y + 6, RM - LM, box_top - p.y - 6, fill=0, stroke=1)
    p.y -= 6

    # check summary
    p.head("Check Summary")
    cols = [(LM, "Check"), (LM + 110, "Combination"), (LM + 268, "Demand"), (LM + 340, "Capacity"),
            (LM + 392, "D/C"), (LM + 424, "Result")]
    c.setFont("Helvetica-Bold", 8); c.setFillColorRGB(*GREY)
    for x, t in cols:
        (c.drawRightString if t in ("Demand", "Capacity", "D/C") else c.drawString)(
            x + (0 if t not in ("Demand", "Capacity", "D/C") else 0), p.y, t)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(LM, p.y - 3, RM, p.y - 3)
    p.y -= 14
    flags = []
    for r in sheet.rows:
        flag = r.status == "FLAG"
        if flag:
            c.setFillColorRGB(0.99, 0.95, 0.91); c.rect(LM, p.y - 13, RM - LM, 24, fill=1, stroke=0)
            flags.append(r)
        c.setFillColorRGB(*INK); c.setFont("Helvetica", 8.5); c.drawString(LM, p.y, r.check.title())
        c.setFont("Courier", 8); c.drawString(LM + 110, p.y, r.combo)
        c.drawRightString(LM + 268, p.y, _fmt(r.demand, r.unit))
        c.drawRightString(LM + 340, p.y, _fmt(r.capacity, r.unit))
        c.drawRightString(LM + 392, p.y, f"{r.dc:.2f}")
        c.setFont("Helvetica-Bold", 8.5); c.setFillColorRGB(*(FLAGC if flag else OKC))
        c.drawString(LM + 424, p.y, r.status)
        c.setFont("Helvetica", 7.5); c.setFillColorRGB(*GREY)
        c.drawString(LM + 8, p.y - 9.5, (r.source + ("   " + r.note if r.note else ""))[:128])
        c.setStrokeColorRGB(0.88, 0.89, 0.91); c.setLineWidth(0.4); c.line(LM, p.y - 13, RM, p.y - 13)
        p.y -= 25
    for r in flags:
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(1); c.rect(LM, p.y - 6, RM - LM, 18, fill=0, stroke=1)
        c.setFillColorRGB(*FLAGC); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(LM + 6, p.y, f"FLAG - {r.check.title()}: {_fmt(r.demand, r.unit)} exceeds "
                                  f"{_fmt(r.capacity, r.unit)} ({r.combo})")
        p.y -= 24

    p.head("Assumptions")
    for s in sheet.assumptions:
        p.wrap("- " + s, width=118, size=8, dy=10)
    c.setStrokeColorRGB(*INK)
    c.showPage(); c.save()
    return path
