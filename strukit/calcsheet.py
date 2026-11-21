"""Calc sheets (PDF), one member per sheet (running onto more sheets when needed).

Layout rules (Thatcher Engineering): header and footer as on HydroKit's sheets, sheet
titles in title case, every check with demand, capacity, D/C, result and code reference,
the governing equations with intermediate values, assumptions stated. No revision logs
on the page. The PE stamp goes on the package cover only.
"""
import datetime
import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import __version__, footing, memberart

# Sheet header and footer match HydroKit's (Thatcher Engineering ruling, 2026-11-21):
# logo, firm name and contact line at left; project, job, site, date and sheet number at
# right; navy rule under the header; basis of the sheet and "Prepared with" in the footer.
# CSS pixels in that specification are 0.75 pt here.
FIRM = "Thatcher Engineering, LLC"
CONTACT = ["office@thatcherengineering.org", "719-225-0150"]     # no street address (ruling)
SEP = " \u00b7 "
NAVY = (0x21 / 255, 0x36 / 255, 0x51 / 255)
INK = (0x1B / 255, 0x24 / 255, 0x30 / 255)
GREY = (0x3A / 255, 0x47 / 255, 0x56 / 255)
RULE = (0xD5 / 255, 0xDB / 255, 0xE3 / 255)
BLUE = NAVY
FLAGC, OKC = (0.60, 0.24, 0.0), (0.11, 0.42, 0.23)
LM, RM = 43.2, 612 - 43.2                            # 0.6 in side margins
TOP, BOT = 792 - 39.6, 32.4                          # 0.55 in top, 0.45 in bottom


def _fonts():
    """IBM Plex Sans / Mono (SIL Open Font License), bundled in data/fonts. Falls back
    to the PDF base fonts if the files are missing."""
    d = os.path.join(os.path.dirname(__file__), "data", "fonts")
    try:
        for name, fn in (("PlexSans", "IBMPlexSans-Regular.ttf"), ("PlexSans-Bold", "IBMPlexSans-Bold.ttf"),
                         ("PlexMono", "IBMPlexMono-Regular.ttf")):
            pdfmetrics.registerFont(TTFont(name, os.path.join(d, fn)))
        return "PlexSans", "PlexSans-Bold", "PlexMono"
    except Exception:
        return FR, FB, FM


FR, FB, FM = _fonts()


def _date(d):
    """Nov 21, 2026 from an ISO date; anything else is printed as given."""
    try:
        t = datetime.date.fromisoformat(d)
        return f"{t.strftime('%b')} {t.day}, {t.year}"
    except (TypeError, ValueError):
        return str(d)


def _fmt(v, unit=""):
    a = abs(v)
    s = f"{v:,.0f}" if a >= 1000 else f"{v:.1f}" if a >= 100 else f"{v:.2f}" if a >= 1 else f"{v:.3f}"
    return f"{s} {unit}".strip()


class _Page:
    """job: a text job number, or dict(name=, number=, address=) for the project name,
    job number and site address in the header."""

    def __init__(self, path, title, job, code, method, page, pages, date):
        self.c = canvas.Canvas(path, pagesize=letter)
        self.c.setTitle(title)
        self.c.setAuthor(FIRM)
        self.args = (title, job, code, method, date)
        self.page, self.pages, self.used = page, pages, 1
        self._frame(title)

    def _frame(self, title):
        c = self.c
        _, job, code, method, date = self.args
        # logo: Thatcher Engineering mark, 30 pt square (viewBox 1200)
        k = 30.0 / 1200.0
        lx, ly = LM, TOP
        c.setFillColorRGB(*NAVY)
        t = c.beginPath()
        for i, (x, y) in enumerate(((60, 1140), (1140, 60), (1140, 1140))):
            (t.moveTo if i == 0 else t.lineTo)(lx + x * k, ly - y * k)
        t.close(); c.drawPath(t, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.rect(lx + 600 * k, ly - (492 + 108) * k, 396 * k, 108 * k, fill=1, stroke=0)
        c.rect(lx + 708 * k, ly - (600 + 444) * k, 108 * k, 444 * k, fill=1, stroke=0)
        tx = LM + 30 + 7.5
        c.setFillColorRGB(*NAVY); c.setFont(FB, 10.5); c.drawString(tx, TOP - 13.5, FIRM)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25); c.drawString(tx, TOP - 25.5, SEP.join(x for x in CONTACT if x))
        # right block: project, job, site / date, sheet
        if isinstance(job, dict):
            name = job.get("name", "")
            rest = [("Job " + job["number"]) if job.get("number") else "", job.get("address", "")]
        else:
            name, rest = "", ["Job " + str(job)]
        tail = SEP.join(x for x in rest if x)
        if name and tail:
            tail = SEP + tail
        w_tail = c.stringWidth(tail, FR, 8.25)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25); c.drawRightString(RM, TOP - 12.5, tail)
        if name:
            c.setFillColorRGB(*INK); c.setFont(FB, 8.25); c.drawRightString(RM - w_tail, TOP - 12.5, name)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25)
        c.drawRightString(RM, TOP - 24.9, SEP.join([_date(date), f"Sheet {self.page + self.used - 1} of {self.pages}"]))
        c.setStrokeColorRGB(*NAVY); c.setLineWidth(2.25); c.line(LM, TOP - 38.6, RM, TOP - 38.6)
        # footer, pinned to the bottom
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.75); c.line(LM, BOT + 14.6, RM, BOT + 14.6)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25)
        c.drawString(LM, BOT + 2, SEP.join(x for x in (code, method) if x))
        c.drawRightString(RM, BOT + 2, f"Prepared with StruKit {__version__}{SEP}{FIRM}")
        # sheet title, first thing in the content
        size = 15.0
        while c.stringWidth(title, FB, size) > RM - LM and size > 9:
            size -= 0.5
        c.setFillColorRGB(*INK); c.setFont(FB, size); c.drawString(LM, TOP - 58, title)
        c.setStrokeColorRGB(*INK)
        self.y = TOP - 75

    def room(self, h):
        """Start a new page (same header, title marked Continued) if h points do not fit."""
        if self.y - h < 55:
            self.c.showPage()
            self.used += 1
            self._frame(self.args[0] + " (Continued)")

    def head(self, text):
        c = self.c
        self.y -= 4
        c.setFillColorRGB(*BLUE); c.setFont(FB, 8)
        c.drawString(LM, self.y, text.upper())
        self.y -= 12

    def kv(self, rows, x=LM, kw=92, y=None):
        c = self.c
        yy = self.y if y is None else y
        for k, v in rows:
            c.setFont(FR, 8.5); c.setFillColorRGB(*GREY); c.drawString(x, yy, k)
            c.setFillColorRGB(*INK); c.drawString(x + kw, yy, v)
            yy -= 11.5
        if y is None:
            self.y = yy
        return yy

    def text(self, s, font=FR, size=8.5, color=INK, x=LM, dy=11.5):
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
    c.setFillColorRGB(*color); c.setFont(FM, 7.5); c.drawString(x0, y0 + h + 3, label)
    c.setStrokeColorRGB(*INK)


def _steps(p, title, lines):
    """The governing calculation, one line per value with its equation reference. The
    box carries on to the next page when it does not fit."""
    c = p.c
    p.room(60)
    p.head(title)
    box_top = p.y + 9

    def close():
        c.setStrokeColorRGB(*RULE); c.setLineWidth(0.5)
        c.rect(LM, p.y + 6, RM - LM, box_top - p.y - 6, fill=0, stroke=1)

    for ln in lines:
        need = 10.0 + (8.5 if ln.note else 0)
        if p.y - need < 64:
            close()
            p.room(1000)
            p.head(title + ", Continued")
            box_top = p.y + 9
        val = f"{ln.value:.2f}" if not ln.unit else _fmt(ln.value, ln.unit)
        c.setFont(FM, 8); c.setFillColorRGB(*INK)
        c.drawString(LM + 6, p.y, f"{ln.label} = {val}")
        c.setFont(FR, 7.5); c.setFillColorRGB(*GREY)
        c.drawRightString(RM - 6, p.y, ln.source)
        if ln.note:
            p.y -= 8.5
            c.drawString(LM + 18, p.y, ln.note)
        p.y -= 10.0
    close()
    p.y -= 6


def _split(s, width):
    out, line = [], ""
    for w in s.split():
        if len(line) + len(w) + 1 > width:
            out.append(line); line = w
        else:
            line = (line + " " + w).strip()
    return out + ([line] if line else [])


def _summary(p, rows):
    """Check summary table: demand, capacity, D/C and result for every check, the code
    reference under each, and a boxed FLAG line for every check that fails."""
    c = p.c
    p.room(70)
    p.head("Check Summary")
    c.setFont(FB, 8); c.setFillColorRGB(*GREY)
    for x, t, right in ((LM, "Check", 0), (LM + 150, "Combination", 0), (LM + 318, "Demand", 1),
                        (LM + 392, "Capacity", 1), (LM + 430, "D/C", 1), (LM + 446, "Result", 0)):
        (c.drawRightString if right else c.drawString)(x, p.y, t)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(LM, p.y - 3, RM, p.y - 3)
    p.y -= 14
    flags = []
    for r in rows:
        flag = r.status == "FLAG"
        sub = _split(r.source, 132) + (_split(r.note, 132) if r.note else [])
        hgt = 14 + 8.5 * len(sub)
        p.room(hgt - 8)
        if flag:
            c.setFillColorRGB(0.99, 0.95, 0.91); c.rect(LM, p.y - hgt + 11, RM - LM, hgt, fill=1, stroke=0)
            flags.append(r)
        c.setFillColorRGB(*INK); c.setFont(FR, 8.5)
        c.drawString(LM, p.y, r.check[0].upper() + r.check[1:])
        c.setFont(FM, 8); c.drawString(LM + 150, p.y, r.combo)
        c.drawRightString(LM + 318, p.y, _fmt(r.demand, r.unit))
        c.drawRightString(LM + 392, p.y, _fmt(r.capacity, r.unit))
        c.drawRightString(LM + 430, p.y, f"{r.dc:.2f}")
        c.setFont(FB, 8.5); c.setFillColorRGB(*(FLAGC if flag else OKC))
        c.drawString(LM + 446, p.y, r.status)
        c.setFont(FR, 7.5); c.setFillColorRGB(*GREY)
        for i, t in enumerate(sub):
            c.drawString(LM + 8, p.y - 9.5 - 8.5 * i, t)
        c.setStrokeColorRGB(*RULE); c.setLineWidth(0.4)
        c.line(LM, p.y - hgt + 11, RM, p.y - hgt + 11)
        p.y -= hgt
    for r in flags:
        p.room(8)
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(1); c.rect(LM, p.y - 6, RM - LM, 18, fill=0, stroke=1)
        c.setFillColorRGB(*FLAGC); c.setFont(FB, 8.5)
        c.drawString(LM + 6, p.y, f"FLAG - {r.check[0].upper() + r.check[1:]}: {_fmt(r.demand, r.unit)} "
                                  f"exceeds {_fmt(r.capacity, r.unit)} ({r.combo})")
        p.y -= 21
    c.setStrokeColorRGB(*INK)


def _closing(p, assumptions, not_checked=()):
    need = 16 + 10 * sum(len(_split("- " + a, 118)) for a in assumptions)
    if not_checked:
        need += 18 + 10 * len(_split("; ".join(not_checked) + ".", 118))
    p.room(need - 8)
    p.head("Assumptions")
    for s in assumptions:
        p.wrap("- " + s, width=118, size=8, dy=10)
    if not_checked:
        p.y -= 2
        p.head("Not Checked on This Sheet")
        p.wrap("; ".join(not_checked) + ".", width=118, size=8, dy=10)
    p.c.setStrokeColorRGB(*INK)
    p.c.showPage(); p.c.save()
    return p.used


def _steel_beam_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
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
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8); c.drawString(x0, top - 4, "LOADING SKETCH")
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
    c.setFillColorRGB(*GREY); c.setFont(FM, 7.5)
    c.drawCentredString(x0 + w / 2, by - 22, f"L = {sheet.span_ft:g} ft")
    if not true_scale:
        c.setFont(FR, 6); c.drawCentredString(x0 + w / 2, by - 30, "side view: depth enlarged for clarity")
    uni = [f"{ld['case']} {ld['w']:.3f}" for ld in sheet.loads if ld["kind"] == "uniform"]
    if uni:
        c.setFillColorRGB(*BLUE); c.setFont(FM, 7.5)
        c.drawCentredString(x0 + w / 2, by + hb + 34, "w = " + " + ".join(uni) + " kip/ft")
    for bx in getattr(sheet, "brace_points", []):
        xx = x0 + w * bx / sheet.span_ft
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(0.9)
        xx = min(max(xx, x0 + 4), x0 + w - 4); m = by + hb / 2
        c.line(xx - 2.5, m - 2.5, xx + 2.5, m + 2.5); c.line(xx - 2.5, m + 2.5, xx + 2.5, m - 2.5)
    # cut section, to scale
    sx = 536
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8); c.drawCentredString(sx, top - 4, "SECTION")
    memberart.steel_section(c, sx, top - 38, 40, 46, pr["d"], pr["bf"], pr["tf"], pr["tw"], pr.get("kdes"))
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString(sx, top - 72, "to scale")
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
        p.text(s, font=FM, size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in combos:
        ra, rb = sheet.reactions[cb.name]
        p.text(f"{cb.name:<18} reactions {ra:.2f} / {rb:.2f} kip", font=FM, size=8, dy=10)
        p.text(cb.source, size=7.5, color=GREY, x=LM + 12)

    # diagrams for the governing combination
    p.y -= 4
    p.head(f"Shear and Moment, {sheet.governing['flexure']}")
    xs, V, M = sheet.diagram["x"], sheet.diagram["V"], sheet.diagram["M"]
    dy0 = p.y - 40
    _diagram(c, LM, dy0, 245, 32, xs, V, BLUE, f"V max = {max(abs(v) for v in V):.2f} kip")
    _diagram(c, LM + 280, dy0, 245, 32, xs, [-m for m in M], (0.54, 0.35, 0.0),
             f"M max = {max(abs(m) for m in M):.1f} kip-ft")
    p.y = dy0 - 12

    _steps(p, "Flexural and Shear Strength (AISC 360-22)", sheet.steps)
    _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions)


def _sketch_title(c, x, top, text, centred=False):
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8)
    (c.drawCentredString if centred else c.drawString)(x, top - 4, text)


def _small(c, x, y, text, size=6):
    c.setFillColorRGB(*GREY); c.setFont(FR, size); c.drawCentredString(x, y, text)


def _steel_column_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
    """Write the calc sheet for a ws_steel_column.SteelColumnSheet."""
    kind = ("Cantilevered Steel Column" if sheet.sway else
            "Steel Column with Lateral Load" if sheet.lateral else "Steel Compression Member")
    p = _Page(path, f"Column {sheet.mark} - {kind}", job, code, sheet.method,
              page, pages, date)
    c, pr = p.c, sheet.props
    top = p.y
    p.head("Member")
    p.kv([("Section", f"{sheet.shape}  (Fy = {sheet.Fy:g} ksi)"),
          ("Height", f"{sheet.height_ft:g} ft"),
          ("Unbraced Length", f"x axis {sheet.Lx_ft:g} ft, y axis {sheet.Ly_ft:g} ft"),
          ("Effective Length", f"Kx = {sheet.Kx:g}, Ky = {sheet.Ky:g}  ({sheet.k_source})"),
          ("Ends", ("fixed base; top free to move for bending about " + " and ".join(sheet.sway))
           if sheet.sway else "held against sideways movement top and bottom"),
          ("Dimensions", f"d = {pr['d']:g} in, bf = {pr['bf']:g} in"),
          ("", f"tf = {pr['tf']:g} in, tw = {pr['tw']:g} in"),
          ("Properties", f"A = {pr['A']:g} in2, rx = {pr['rx']:g} in, ry = {pr['ry']:g} in"),
          ("", f"Ix = {pr['Ix']:g} in4, Iy = {pr['Iy']:g} in4, Zx = {pr['Zx']:g} in3, Zy = {pr['Zy']:g} in3"),
          ("Source", "AISC Shapes Database v16.0")])
    bottom_left = p.y
    # column standing up, with its load and supports
    ex, eh = 440, 62
    ey = top - 88
    _sketch_title(c, ex, top, "ELEVATION", centred=True)
    braces = [sheet.Ly_ft * 12 * k for k in range(1, 50) if sheet.Ly_ft * k < sheet.height_ft - 1e-6]
    w = memberart.steel_column_elevation(c, ex, ey, eh, pr["d"], pr["tf"], sheet.height_ft * 12, braces)
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.9)
    c.line(ex, ey + eh + 16, ex, ey + eh + 6)
    t = c.beginPath(); t.moveTo(ex, ey + eh + 1); t.lineTo(ex - 3, ey + eh + 7); t.lineTo(ex + 3, ey + eh + 7); t.close()
    c.drawPath(t, fill=1, stroke=0)
    c.setLineWidth(1.2); c.line(ex - 12, ey - 0.6, ex + 12, ey - 0.6)
    if sheet.sway:                                        # fixed base: ground hatch under the line
        c.setLineWidth(0.4)
        for k in range(7):
            c.line(ex - 12 + 4 * k, ey - 0.6, ex - 15 + 4 * k, ey - 4.5)
    c.setFillColorRGB(*GREY); c.setFont(FM, 7.5)
    c.drawString(ex + w / 2 + 6, ey + eh / 2 - 3, f"{sheet.height_ft:g} ft")
    c.drawRightString(ex - 6, ey + eh + 9, "P")
    if braces:
        _small(c, ex, ey - 11, "x = braced against weak-axis buckling")
    _small(c, ex, ey - (19 if braces else 11), ("fixed base, free top; " if sheet.sway else "")
           + "width enlarged for clarity")
    sx = 530
    _sketch_title(c, sx, top, "SECTION", centred=True)
    memberart.steel_section(c, sx, top - 44, 46, 50, pr["d"], pr["bf"], pr["tf"], pr["tw"], pr.get("kdes"))
    _small(c, sx, top - 80, "to scale")
    p.y = min(bottom_left, ey - 24) - 2

    if sheet.lateral:                                     # sideways load arrows on the picture
        c.setStrokeColorRGB(*BLUE); c.setFillColorRGB(*BLUE); c.setLineWidth(0.7)
        xl = ex - w / 2
        def arrow(yy, length=14):
            c.line(xl - length - 2, yy, xl - 5, yy)
            t = c.beginPath(); t.moveTo(xl - 1, yy); t.lineTo(xl - 6, yy + 2); t.lineTo(xl - 6, yy - 2); t.close()
            c.drawPath(t, fill=1, stroke=0)
        if any(ld["kind"] == "uniform" for ld in sheet.lateral):
            for k in range(6):
                arrow(ey + eh * (0.05 + 0.18 * k))
            c.line(xl - 16, ey + eh * 0.05, xl - 16, ey + eh * 0.95)
        for ld in sheet.lateral:
            if ld["kind"] == "point":
                arrow(ey + eh * ld["x_ft"] / sheet.height_ft, 24)
        c.setStrokeColorRGB(*INK)
    p.head("Loads")
    for ld in sheet.loads:
        s = f"{ld['case']:<3} axial    {ld['P']:.2f} kip"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font=FM, size=8)
    for ld in sheet.lateral:
        ax = "bending about x (strong axis)" if ld["bending"] == "x" else "bending about y (weak axis)"
        if ld["kind"] == "uniform":
            s = f"{ld['case']:<3} sideways {ld['w']:.3f} kip/ft over the height, {ax}"
        else:
            s = f"{ld['case']:<3} sideways {ld['P']:.2f} kip at {ld['x_ft']:g} ft above the base, {ax}"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font=FM, size=8)
    for ld in sheet.leaning:
        s = f"{ld['case']:<3} leaning  {ld['P']:.2f} kip on other columns that this column holds up sideways"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font=FM, size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in combos:
        mark = "   governs" if cb.name == sheet.governing else ""
        comb = f"   combined ratio {sheet.combined[cb.name]:.2f}" if cb.name in sheet.combined else ""
        p.text(f"{cb.name:<18} P = {sheet.totals[cb.name]:.2f} kip{comb}{mark}", font=FM, size=8, dy=10)
        p.text(cb.source, size=7.5, color=GREY, x=LM + 12)
    p.y -= 4
    if sheet.diagram:
        p.head(f"Bending Moment Along the Column (Base at Left), {sheet.governing}")
        d = sheet.diagram
        dy0, k = p.y - 40, 0
        for key, lab in (("Mx", "Mx"), ("My", "My")):
            if any(abs(v) > 1e-9 for v in d[key]):
                _diagram(c, LM + 269 * k, dy0, 235, 32, d["x"], [-m for m in d[key]], (0.54, 0.35, 0.0),
                         f"{lab} max = {max(abs(m) for m in d[key]):.2f} kip-ft "
                         + ("(second-order)" if sheet.sway else "(before B1)"))
                k += 1
        p.y = dy0 - 12
    _steps(p, "Strength Calculation (AISC 360-22)" if sheet.lateral or sheet.sway
           else "Compressive Strength (AISC 360-22)", sheet.steps)
    _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions, sheet.not_checked)


def _footing_pdf(sheet, path, job, code, date, method="Strength design (LRFD)", page=1, pages=1):
    """Write the calc sheet for a ws_footing.FootingSheet (isolated or continuous)."""
    i, res = sheet.inp, sheet.result
    iso = sheet.kind == "isolated"
    p = _Page(path, f"Footing {sheet.mark} - " + ("Isolated Spread Footing" if iso else
                                                  "Continuous Footing"), job, code, method,
              page, pages, date)
    c = p.c
    top = p.y
    p.head("Footing")
    if iso:
        sup = f"{i['col_x_in']:g} x {i['col_y_in']:g} in {sheet.supported} column"
        if i.get("plate_x_in"):
            sup += f" on {i['plate_x_in']:g} x {i['plate_y_in']:g} in base plate"
        low = i.get("bottom_layer", "x")
        rows = [("Size", f"{i['B_ft']:g} ft x {i['L_ft']:g} ft x {i['h_in']:g} in thick"),
                ("Supports", sup),
                ("Reinforcing", f"({i['n_x']}) #{i['bar']} in x, ({i['n_y']}) #{i['bar']} in y"),
                ("", f"{i['cover_in']:g} in clear cover, {low}-direction bars lowest")]
    else:
        stem = f", {i['stem_h_in']:g} in high" if i.get("stem_h_in") else ""
        rows = [("Size", f"{i['W_ft']:g} ft wide x {i['h_in']:g} in thick, per foot of length"),
                ("Supports", f"{i['wall_in']:g} in {i.get('wall_kind', 'concrete')} wall{stem}"),
                ("Reinforcing", f"#{i['bar_t']} at {i['spacing_t_in']:g} in across, "
                                f"({i['n_l']}) #{i['bar_l']} lengthwise"),
                ("", f"{i['cover_in']:g} in clear cover, bars across are lowest")]
    rows += [("Concrete", f"f'c = {i['fc']:,.0f} psi, {i['conc_pcf']:g} pcf"
                          + ("" if i.get("lam", 1.0) == 1.0 else f", lambda = {i['lam']:g}")),
             ("Bars", f"fy = {i['fy']:,.0f} psi"),
             ("Soil", f"allowable bearing {i['q_allow_psf']:,.0f} psf")]
    if i.get("soil_depth_ft"):
        rows.append(("", f"{i['soil_depth_ft']:g} ft of soil over the footing at {i['soil_pcf']:g} pcf"))
    p.kv(rows, kw=70)
    p.text("Soil source: " + sheet.soil_source, size=7.5, color=GREY)
    bottom_left = p.y

    # pictures: section (always) and plan (isolated)
    sec_cx = 400 if iso else 450
    _sketch_title(c, sec_cx, top, "SECTION", centred=True)
    base = top - (92 if iso else 106)
    D = footing.BAR_DIA
    if iso:
        low = i.get("bottom_layer", "x")
        n_dots = i["n_y"] if low == "x" else i["n_x"]
        memberart.footing_section(c, sec_cx, base, 110, 76, i["B_ft"] * 12, i["h_in"], i["col_x_in"],
                                  sheet.supported, i["cover_in"], D[i["bar"]], n_dots, D[i["bar"]],
                                  plate_w_in=i.get("plate_x_in"),
                                  soil_depth_in=i.get("soil_depth_ft", 0) * 12)
        _sketch_title(c, 516, top, "PLAN", centred=True)
        memberart.footing_plan(c, 516, top - 52, 72, i["B_ft"] * 12, i["L_ft"] * 12, i["col_x_in"],
                               i["col_y_in"], i["n_x"], i["n_y"], i["cover_in"],
                               i.get("plate_x_in"), i.get("plate_y_in"))
        _small(c, 516, base - 9, "to scale")
    else:
        memberart.footing_section(c, sec_cx, base, 150, 92, i["W_ft"] * 12, i["h_in"], i["wall_in"],
                                  "concrete", i["cover_in"], D[i["bar_t"]], i["n_l"], D[i["bar_l"]],
                                  stem_h_in=i.get("stem_h_in", 0),
                                  soil_depth_in=i.get("soil_depth_ft", 0) * 12)
    _small(c, sec_cx, base - 9, "to scale")
    p.y = min(bottom_left, base - 14) - 2

    p.head("Loads")
    u = "lb" if iso else "lb/ft"
    ps, pu = (i["P_service"], i["Pu"]) if iso else (i["P_service_plf"], i["Pu_plf"])
    what = "column load" if iso else "wall load at the top of the stem wall"
    p.text(f"Service   {ps:>10,.0f} {u}   {i['service_combo']}   ({what})", font=FM, size=8)
    p.text(f"Factored  {pu:>10,.0f} {u}   {i['strength_combo']}", font=FM, size=8)
    v = res.values
    p.y -= 2
    p.head("Weights and Design Values")
    lines = [f"footing weight = {v['W_ftg']:,.1f} {u}"]
    if v.get("W_stem"):
        lines.append(f"stem wall weight = {v['W_stem']:,.1f} {u} (full weight for soil bearing; "
                     f"x {i['dead_factor']:g} for strength)")
    if v.get("W_soil"):
        lines.append(f"soil over footing = {v['W_soil']:,.1f} {u}")
    if not iso:
        lines += [f"factored load with stem wall, Pu = {v['Pu_plf']:,.1f} lb/ft",
                  f"factored soil pressure, qu = {v['qu_psf']:,.1f} psf",
                  f"d = {v['d']:.3f} in;  As = {v['As']:.3f} in2/ft"]
    for s in lines:
        p.text(s, font=FM, size=8, dy=10.5)
    p.y -= 4
    _summary(p, sheet.rows)
    notes = ["Load is centred on the footing; soil pressure is uniform.",
             "Footing weight and soil over the footing count toward soil bearing only. Strength "
             "checks use the soil pressure caused by the factored loads (ACI 318-19 13.2.6.3)."]
    return _closing(p, notes + list(res.notes), res.not_checked)


def _paged(build, sheet, path, job, code, date, page=1, pages=None, **kw):
    """Write a member's sheet. When the member runs past one page and the caller did
    not give the package's page count, the sheet is written again so every page reads
    "Page n of N" correctly. Returns the path; the page count is on the function as
    .last_pages."""
    used = build(sheet, path, job, code, date, page=page, pages=pages or 1, **kw)
    if pages is None and used != 1:
        used = build(sheet, path, job, code, date, page=page, pages=used, **kw)
    _paged.last_pages = used
    return path


def steel_beam_pdf(sheet, path, job, code, date, page=1, pages=None, combos=()):
    return _paged(_steel_beam_pdf, sheet, path, job, code, date, page, pages, combos=combos)


def steel_column_pdf(sheet, path, job, code, date, page=1, pages=None, combos=()):
    return _paged(_steel_column_pdf, sheet, path, job, code, date, page, pages, combos=combos)


def footing_pdf(sheet, path, job, code, date, method="Strength design (LRFD)", page=1, pages=None):
    return _paged(_footing_pdf, sheet, path, job, code, date, page, pages, method=method)


# ----------------------------------------------------------------------- frames
def _frame_xy(lay, x0, y0, w, h):
    xs = [p[0] for p in lay.nodes.values()]; ys = [p[1] for p in lay.nodes.values()]
    s = min(w / (max(xs) - min(xs) or 1.0), h / (max(ys) - min(ys) or 1.0))
    ox = x0 + (w - s * (max(xs) - min(xs))) / 2
    return (lambda n: (ox + s * (lay.nodes[n][0] - min(xs)), y0 + s * (lay.nodes[n][1] - min(ys)))), s


def _draw_frame(c, lay, x0, y0, w, h, band=3.2, labels=True, light=False):
    """The frame to scale: members as steel bands, pinned or fixed bases."""
    import math as _m
    xy, s = _frame_xy(lay, x0, y0, w, h)
    for m in lay.members:
        (x1, y1), (x2, y2) = xy(m.i), xy(m.j)
        L, ang = _m.hypot(x2 - x1, y2 - y1), _m.degrees(_m.atan2(y2 - y1, x2 - x1))
        c.saveState(); c.translate(x1, y1); c.rotate(ang)
        if light:
            c.setStrokeColorRGB(0.55, 0.58, 0.62); c.setLineWidth(0.8); c.line(0, 0, L, 0)
        else:
            memberart.steel_elevation(c, 0, -band / 2, L, band, 10.0, 0.9)
        c.restoreState()
        if labels:
            c.setFillColorRGB(*GREY); c.setFont(FR, 5.5)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if m.role == "column":
                c.drawString(mx + band, my - 2, m.name)
            else:
                c.drawCentredString(mx, my + band + 1.5, m.name)
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK)
    for n, kind in lay.supports.items():
        x, y = xy(n)
        if kind == "pin":
            c.setLineWidth(0.7)
            t = c.beginPath(); t.moveTo(x, y); t.lineTo(x - 4, y - 7); t.lineTo(x + 4, y - 7); t.close()
            c.drawPath(t, fill=0, stroke=1)
        else:
            c.setLineWidth(1.2); c.line(x - 7, y, x + 7, y)
            c.setLineWidth(0.4)
            for k in range(5):
                c.line(x - 7 + 3.5 * k, y, x - 9.5 + 3.5 * k, y - 4)
    return xy, s


def _moment_on_frame(c, sheet, x0, y0, w, h):
    """Bending moment diagram of the governing combination, drawn on the frame on the
    tension side of each member."""
    import math as _m
    lay = sheet.lay
    xy, s = _draw_frame(c, lay, x0, y0, w, h, labels=False, light=True)
    mmax = max(float(max(abs(v) for v in M)) for _, M in sheet.diagram.values()) or 1.0
    k = 18.0 / mmax
    col = (0.54, 0.35, 0.0)
    for m in lay.members:
        st, M = sheet.diagram[m.name]
        (x1, y1), (x2, y2) = xy(m.i), xy(m.j)
        L = _m.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = uy, -ux                                   # right-hand side looking from i to j
        p = c.beginPath(); p.moveTo(x1, y1)
        for a, mv in zip(st, M):
            f = a / (st[-1] or 1.0)
            p.lineTo(x1 + ux * L * f + nx * k * mv, y1 + uy * L * f + ny * k * mv)
        p.lineTo(x2, y2); p.close()
        c.setFillColorRGB(*[min(1, 0.80 + 0.2 * v) for v in col]); c.setStrokeColorRGB(*col); c.setLineWidth(0.6)
        c.drawPath(p, fill=1, stroke=1)
        i = int(max(range(len(M)), key=lambda q: abs(M[q])))
        f = st[i] / (st[-1] or 1.0)
        c.setFillColorRGB(*col); c.setFont(FM, 6)
        c.drawCentredString(x1 + ux * L * f + nx * (k * M[i] + (6 if M[i] >= 0 else -6)),
                            y1 + uy * L * f + ny * (k * M[i] + (6 if M[i] >= 0 else -6)) - 2, f"{abs(M[i]):.0f}")
    c.setStrokeColorRGB(*INK)


def _frame_pdf(sheet, path, job, code, date, page=1, pages=1):
    lay = sheet.lay
    p = _Page(path, f"Frame {sheet.mark} - Steel Moment Frame", job, code, sheet.method, page, pages, date)
    c = p.c
    top = p.y
    p.head("Frame")
    for t in _split(lay.description[0].upper() + lay.description[1:], 62):
        p.text(t)
    groups = {}
    for m in lay.members:
        groups.setdefault((m.role, shapes_normalize(m.shape), sheet.brace[m.name]), []).append(m.name)
    for (role, shp, lb), names in groups.items():
        nm = ", ".join(names) if len(names) <= 6 else f"{names[0]} to {names[-1]} ({len(names)})"
        for k, t in enumerate(_split(f"{role.title()}s {nm}: {shp}, braced out of plane at {lb:.3g} ft", 62)):
            p.text(t, x=LM + (8 if k else 0))
    p.text(f"Fy = {sheet.Fy:g} ksi; section properties from the AISC Shapes Database v16.0")
    bottom_left = p.y
    _sketch_title(c, 338, top, "ELEVATION")
    _draw_frame(c, lay, 338, top - 104, 220, 88)
    _small(c, 448, top - 118, "to scale; member depth not to scale")
    p.y = min(bottom_left, top - 122) - 2

    p.head("Loads")
    for ld in sheet.loads:
        if ld.get("auto"):
            continue
        if "on" in ld:
            tgt = ld["on"] if isinstance(ld["on"], str) else ", ".join(ld["on"])
            kind = "per ft of horizontal run" if ld.get("kind") == "projected" else "per ft of member"
            s = (f"{ld['case']:<3} {ld['w']:.3f} kip/ft on {tgt}, " +
                 ("sideways" if ld.get("dir") == "x" else f"gravity, {kind}"))
        elif "node" in ld:
            s = f"{ld['case']:<3} at joint {ld['node']}: Fx = {ld.get('Fx', 0):.2f}, Fy = {ld.get('Fy', 0):.2f} kip"
        else:
            s = f"{ld['case']:<3} lateral {ld['Fx']:.2f} kip at level {ld['level']}"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.room(12); p.text(s, font=FM, size=8)
    if any(ld.get("auto") for ld in sheet.loads):
        p.text("D   member self-weight on every member", font=FM, size=8)
    for ld in sheet.leaning:
        p.room(12)
        p.text(f"{ld['case']:<3} leaning {ld['P']:.2f} kip at level {ld['level']} on columns outside the frame",
               font=FM, size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in sheet.combos:
        p.room(24)
        mark = "   governs" if cb.name == sheet.governing["combo"] else ""
        p.text(f"{cb.name}{mark}", font=FM, size=8, dy=10)
        p.text(cb.source, size=7.5, color=GREY, x=LM + 12)

    p.room(150)
    p.y -= 4
    g = sheet.governing
    p.head(f"Bending Moment (kip-ft), {g['combo']}" + (f", {g['label']}" if g["label"] else ""))
    _moment_on_frame(c, sheet, LM + 40, p.y - 112, 250, 92)
    # base reactions, largest over all combinations
    x = LM + 318
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8); c.drawString(x, p.y, "BASE REACTIONS, LARGEST OF ALL")
    c.setFillColorRGB(*GREY); c.setFont(FB, 7.5)
    yy = p.y - 13
    for dx, t in ((0, "Base"), (64, "Down, kip"), (128, "Sideways, kip"), (196, "Moment, kip-ft")):
        (c.drawRightString if dx else c.drawString)(x + dx, yy, t)
    c.setFont(FM, 7.5); c.setFillColorRGB(*INK)
    for n in lay.supports:
        yy -= 10
        v = [max(abs(r[n][k]) for r in sheet.reactions.values()) for k in range(3)]
        c.drawString(x, yy, n); c.drawRightString(x + 64, yy, f"{v[1]:.1f}")
        c.drawRightString(x + 128, yy, f"{v[0]:.2f}"); c.drawRightString(x + 196, yy, f"{v[2] / 12:.1f}")
    p.y -= 126

    _steps(p, f"Governing Member {g['member']} (AISC 360-22)", sheet.steps)

    p.room(60)
    p.head("Member Summary (Worst Combination for Each Member)")
    cols = ((LM, "Member", 0), (LM + 46, "Section", 0), (LM + 108, "Combination", 0), (LM + 268, "Axial, kip", 1),
            (LM + 326, "Moment, kip-ft", 1), (LM + 376, "Shear, kip", 1), (LM + 414, "Ratio", 1), (LM + 430, "Result", 0))
    def header():
        c.setFont(FB, 7.5); c.setFillColorRGB(*GREY)
        for xx, t, right in cols:
            (c.drawRightString if right else c.drawString)(xx, p.y, t)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(LM, p.y - 3, RM, p.y - 3)
        p.y -= 13
    header()
    flags = []
    for r in sheet.member_rows:
        if p.y - 12 < 64:
            p.room(1000); p.head("Member Summary, Continued"); header()
        flag = r["status"] == "FLAG"
        if flag:
            c.setFillColorRGB(0.99, 0.95, 0.91); c.rect(LM, p.y - 3, RM - LM, 11, fill=1, stroke=0); flags.append(r)
        c.setFillColorRGB(*INK); c.setFont(FM, 7.5)
        c.drawString(LM, p.y, r["member"]); c.drawString(LM + 46, p.y, r["shape"])
        c.drawString(LM + 108, p.y, (r["combo"] + (" *" if r["label"] else ""))[:30])
        c.drawRightString(LM + 268, p.y, f"{r['Pr']:.1f} " + ("C" if r["axial"] == "compression" else "T"))
        c.drawRightString(LM + 326, p.y, f"{r['Mr']:.1f}"); c.drawRightString(LM + 376, p.y, f"{r['Vr']:.1f}")
        c.drawRightString(LM + 414, p.y, f"{r['ratio']:.2f}")
        c.setFont(FB, 8); c.setFillColorRGB(*(FLAGC if flag else OKC)); c.drawString(LM + 430, p.y, r["status"])
        p.y -= 11
    c.setFillColorRGB(*GREY); c.setFont(FR, 7)
    c.drawString(LM, p.y, "Ratio = the larger of the combined axial and bending check (Eq. H1-1a / H1-1b) and shear (G2.1). "
                          "C = compression, T = tension. * = with notional load.")
    p.y -= 14
    for r in flags:
        p.room(8)
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(1); c.rect(LM, p.y - 6, RM - LM, 18, fill=0, stroke=1)
        c.setFillColorRGB(*FLAGC); c.setFont(FB, 8.5)
        c.drawString(LM + 6, p.y, f"FLAG - Member {r['member']} ({r['shape']}): ratio {r['ratio']:.2f} exceeds 1.00 ({r['combo']})")
        p.y -= 24
    _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions, sheet.not_checked)


def shapes_normalize(name):
    from . import shapes
    return shapes.normalize(name)


def frame_pdf(sheet, path, job, code, date, page=1, pages=None):
    return _paged(_frame_pdf, sheet, path, job, code, date, page, pages)
