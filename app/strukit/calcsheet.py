"""Calc sheets (PDF), one member per sheet (running onto more sheets when needed).

Layout rules (Thatcher Engineering): header and footer as on HydroKit's sheets, sheet
titles in title case, every check with demand, capacity, D/C, result and code reference,
the governing equations with intermediate values, assumptions stated. No revision logs
on the page. The PE stamp goes on the package cover only.
"""
import datetime
import math
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
        self.owns = not isinstance(path, canvas.Canvas)      # a package passes its own canvas
        self.c = canvas.Canvas(path, pagesize=letter) if self.owns else path
        if self.owns:
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
        val = ln.value if isinstance(ln.value, str) else f"{ln.value:.2f}" if not ln.unit else _fmt(ln.value, ln.unit)
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
    p.c.showPage()
    if p.owns:
        p.c.save()
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
    _sketch_title(c, ex, top, "LOADING", centred=True)
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
    ax_txt = [f"{ld['case']} {ld['P']:.1f} kip" for ld in sheet.loads]
    c.setFillColorRGB(*LOADC); c.setFont(FR, 5.5)
    if len(ax_txt) <= 2:
        for i, t_ in enumerate(ax_txt):
            c.drawRightString(ex - 6, ey + eh + 8 + 6.5 * (len(ax_txt) - 1 - i), t_)
    else:
        c.drawRightString(ex - 6, ey + eh + 9, " + ".join(f"{ld['case']} {ld['P']:.1f}" for ld in sheet.loads) + " kip")
    c.setFillColorRGB(*GREY); c.setFont(FM, 7.5)
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
            c.setFont(FR, 5.5)
            for i, ld in enumerate([x for x in sheet.lateral if x["kind"] == "uniform"]):
                c.drawRightString(xl - 19, ey + eh * 0.5 - 2 - 6.5 * i, f"{ld['case']} {ld['w']:.3g} kip/ft")
        for ld in sheet.lateral:
            if ld["kind"] == "point":
                yy_ = ey + eh * ld["x_ft"] / sheet.height_ft
                arrow(yy_, 24)
                c.setFont(FR, 5.5); c.drawRightString(xl - 28, yy_ - 2, f"{ld['case']} {ld['P']:.3g} kip")
        c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK)
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


def _footing_load(c, cx, base, s, W_in, h_in, sup_h_in, label):
    """Loading on the footing section: the service load down the supported member and the soil
    pressure it bears on, drawn as arrows (not to a force scale)."""
    y_top = base + (h_in + sup_h_in) * s
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow_down(c, cx, y_top + 13, y_top + 1.5)
    c.setFont(FR, 6); c.drawCentredString(cx, y_top + 15.5, label)
    c.setLineWidth(0.5)
    n = 7
    for k in range(n):
        x = cx - W_in * s / 2 + (k + 0.5) * W_in * s / n
        _arrow(c, x, base - 8, x, base - 1.5, head=2.5)
    c.line(cx - W_in * s / 2, base - 8, cx + W_in * s / 2, base - 8)


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
        sc_ = memberart.footing_section(c, sec_cx, base, 110, 60, i["B_ft"] * 12, i["h_in"], i["col_x_in"],
                                        sheet.supported, i["cover_in"], D[i["bar"]], n_dots, D[i["bar"]],
                                        plate_w_in=i.get("plate_x_in"),
                                        soil_depth_in=i.get("soil_depth_ft", 0) * 12)
        _footing_load(c, sec_cx, base, sc_, i["B_ft"] * 12, i["h_in"], max(1.6 * i["h_in"], 12.0) + (0.25 if i.get("plate_x_in") else 0.0),
                      f"{i['P_service']:,.0f} lb service")
        _sketch_title(c, 516, top, "PLAN", centred=True)
        memberart.footing_plan(c, 516, top - 52, 72, i["B_ft"] * 12, i["L_ft"] * 12, i["col_x_in"],
                               i["col_y_in"], i["n_x"], i["n_y"], i["cover_in"],
                               i.get("plate_x_in"), i.get("plate_y_in"))
        _small(c, 516, base - 16, "to scale")
    else:
        sc_ = memberart.footing_section(c, sec_cx, base, 150, 76, i["W_ft"] * 12, i["h_in"], i["wall_in"],
                                        "concrete", i["cover_in"], D[i["bar_t"]], i["n_l"], D[i["bar_l"]],
                                        stem_h_in=i.get("stem_h_in", 0),
                                        soil_depth_in=i.get("soil_depth_ft", 0) * 12)
        _footing_load(c, sec_cx, base, sc_, i["W_ft"] * 12, i["h_in"], i.get("stem_h_in", 0) or max(1.6 * i["h_in"], 12.0),
                      f"{i['P_service_plf']:,.0f} lb/ft service")
    _small(c, sec_cx, base - 16, "to scale; load and soil pressure arrows are not to a force scale")
    p.y = min(bottom_left, base - 21) - 2

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


def _frame_loads(c, lay, xy, loads):
    """The loads on the frame elevation, by load case: distributed member loads as rows of
    arrows with their value in kip/ft, joint and level loads as single arrows in kips.
    Arrows are not to a force scale; cases on the same member stack outward."""
    import math as _m
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC)
    stack, jstack = {}, {}
    for ld in loads:
        if ld.get("auto"):
            continue
        if "on" in ld:
            names = list(lay.names(ld["on"]))
            side = ld.get("dir", "gravity") == "x"
            ends = []
            for name in names:
                m = next(x for x in lay.members if x.name == name)
                (x1, y1), (x2, y2) = xy(m.i), xy(m.j)
                k = stack.get(name, 0); stack[name] = k + 1
                Lp = _m.hypot(x2 - x1, y2 - y1)
                n = max(2, int(Lp / 16))
                c.setLineWidth(0.5)
                if side:                                   # sideways load on a member: arrows from the left
                    off = 9 + 11 * k
                    for q in range(n + 1):
                        f = q / n
                        px, py = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
                        _arrow(c, px - off - 7, py, px - off, py, head=2.2)
                    ends.append((min(x1, x2) - off - 9, (y1 + y2) / 2 - 2))
                else:                                      # gravity: arrows down onto the member
                    off = 8 + 11 * k
                    if Lp >= 14:
                        for q in range(n + 1):
                            f = q / n
                            px, py = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
                            _arrow_down(c, px, py + off + 7, py + off)
                    c.line(x1, y1 + off + 7, x2, y2 + off + 7)
                    xl, yl = (x1, y1) if x1 <= x2 else (x2, y2)
                    ends.append((xl - 3, yl + off + 5))
            if ends:                                       # one label for the load, at its left end
                lx, ly = min(ends)
                c.setFont(FR, 5.5); c.drawRightString(lx, ly, f"{ld['case']} {ld['w']:g} k/ft")
        else:
            node = ld["node"] if "node" in ld else lay.levels[ld["level"]][0]
            if node not in lay.nodes:
                continue
            x, y = xy(node)
            k = jstack.get(node, 0); jstack[node] = k + 1
            fx, fy = ld.get("Fx", 0.0), ld.get("Fy", 0.0)
            c.setLineWidth(0.9); c.setFont(FR, 5.5)
            xs_all = [xy(n_)[0] for n_ in lay.nodes]
            left = x <= (min(xs_all) + max(xs_all)) / 2      # loads are drawn on the outer side of the joint
            sgn = -1 if left else 1
            if fx:
                yk = y + 3 - 8 * jstack.setdefault((node, "x"), 0); jstack[(node, "x")] += 1
                if (fx > 0) == left:                         # pushing toward the frame
                    _arrow(c, x + sgn * 26, yk, x + sgn * 6, yk, head=3)
                else:                                        # pulling away from it
                    _arrow(c, x + sgn * 6, yk, x + sgn * 26, yk, head=3)
                (c.drawRightString if left else c.drawString)(x + sgn * 28, yk - 2, f"{ld['case']} {abs(fx):g} k")
            if fy:
                xa = x + sgn * (9 + 11 * jstack.setdefault((node, "y"), 0)); jstack[(node, "y")] += 1
                y0_, y1_ = y + 22, y + 33
                if fy < 0:
                    _arrow_down(c, xa, y1_, y0_)
                else:
                    _arrow(c, xa, y0_, xa, y1_, head=3)
                c.drawCentredString(xa + sgn * 4 * (jstack[(node, "y")] - 1), y1_ + 2 + 7 * (jstack[(node, "y")] - 1), f"{ld['case']} {abs(fy):g} k")
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK)


def _moment_on_frame(c, sheet, x0, y0, w, h):
    """Bending moment diagram of the governing combination, drawn on the frame on the
    tension side of each member."""
    import math as _m
    lay = sheet.lay
    xy, s = _draw_frame(c, lay, x0, y0, w, h, labels=False, light=True)
    mmax = max(float(max(abs(v) for v in M)) for _, M in sheet.diagram.values()) or 1.0
    k = 18.0 / mmax
    col = (0.54, 0.35, 0.0)
    placed = []
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
        lx = x1 + ux * L * f + nx * (k * M[i] + (6 if M[i] >= 0 else -6))
        ly = y1 + uy * L * f + ny * (k * M[i] + (6 if M[i] >= 0 else -6)) - 2
        for _ in range(6):                                 # step along the member until the label is clear
            if all(abs(lx - a) > 13 or abs(ly - b) > 7 for a, b in placed):
                break
            step = -1 if f > 0.5 else 1
            lx += ux * 9 * step; ly += uy * 9 * step
        placed.append((lx, ly))
        c.setFillColorRGB(*col); c.setFont(FM, 6)
        c.drawCentredString(lx, ly, f"{abs(M[i]):.0f}")
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
    xy_, _s = _draw_frame(c, lay, 368, top - 104, 150, 50)
    _frame_loads(c, lay, xy_, sheet.loads)
    _small(c, 448, top - 118, "frame to scale; member depth and load arrows not to scale; loads in kips and kip/ft")
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


def _cover_pdf(cover, path, job, code, date, page=1, pages=1):
    """Cover sheet of a calc package: the job, the engineer's seal box, the basis of design,
    the load combinations with their sources, the contents with each member's result, the
    flagged checks and anything left out."""
    p = _Page(path, "Structural Calculations", job, "Cover sheet", "", page, pages, date)
    c = p.c
    top = p.y
    name = job.get("name") if isinstance(job, dict) else ""
    p.head("Project")
    rows = [("Project", name or "-"), ("Job Number", (job.get("number") if isinstance(job, dict) else str(job)) or "-"),
            ("Site", (job.get("address") if isinstance(job, dict) else "") or "-"), ("Date", _date(date)),
            ("Prepared By", FIRM), ("Sheets", f"{pages}, including this cover")]
    p.kv(rows, kw=86)
    # seal box
    c.setStrokeColorRGB(*RULE); c.setLineWidth(0.8); c.rect(RM - 150, top - 96, 150, 96, fill=0, stroke=1)
    c.setFillColorRGB(*GREY); c.setFont(FR, 7); c.drawCentredString(RM - 75, top - 104, "Engineer's seal and signature")
    p.y = min(p.y, top - 110) - 2
    p.head("Basis of Design")
    for t in cover["basis"]:
        for k, ln in enumerate(_split(t, 118)):
            p.room(12); p.text(("- " if k == 0 else "  ") + ln, size=8, dy=10.5)
    for title, rows_ in (("ASD Load Combinations", cover["asd"]), ("LRFD Load Combinations", cover["lrfd"])):
        if not rows_:
            continue
        p.y -= 2; p.room(40); p.head(title)
        for expr, src in rows_:
            p.room(12)
            c.setFont(FM, 8); c.setFillColorRGB(*INK); c.drawString(LM, p.y, expr)
            c.setFont(FR, 7.5); c.setFillColorRGB(*GREY); c.drawString(LM + 200, p.y, src)
            p.y -= 10.5
    p.y -= 2; p.room(50); p.head("Contents")
    def header():
        c.setFont(FB, 7.5); c.setFillColorRGB(*GREY)
        for x, t in ((LM, "Mark"), (LM + 70, "Member"), (LM + 290, "Code"), (LM + 400, "Sheet"), (LM + 446, "Result")):
            c.drawString(x, p.y, t)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(LM, p.y - 3, RM, p.y - 3)
        p.y -= 13
    header()
    for it in cover["contents"]:
        if p.y - 12 < 64:
            p.room(1000); p.head("Contents, Continued"); header()
        ok = it["flags"] == 0
        c.setFont(FR, 8.5); c.setFillColorRGB(*INK)
        c.drawString(LM, p.y, it["mark"]); c.drawString(LM + 70, p.y, it["title"]); c.drawString(LM + 290, p.y, it["code"])
        c.setFont(FM, 8); c.drawString(LM + 400, p.y, str(it["sheet"]))
        c.setFont(FB, 8.5); c.setFillColorRGB(*(OKC if ok else FLAGC))
        c.drawString(LM + 446, p.y, "OK" if ok else f"{it['flags']} FLAG" + ("S" if it["flags"] > 1 else ""))
        p.y -= 11.5
    if cover["flag_lines"]:
        p.y -= 4; p.room(40); p.head("Flagged Checks")
        for t in cover["flag_lines"]:
            p.room(12); p.text(t, size=8, color=FLAGC, dy=10.5)
    else:
        p.y -= 4; p.room(24); p.text("No check in this package is flagged.", size=8.5, color=OKC)
    if cover["skipped"]:
        p.y -= 4; p.room(40); p.head("Members Not Included")
        p.wrap("These members are in the project but are not complete, so they are not in this package: "
               + ", ".join(cover["skipped"]) + ".", width=118, size=8, dy=10.5)
    c.showPage()
    if p.owns:
        c.save()
    return p.used


def package_pdf(items, path, job, date, title="Structural Calculations", cover=None):
    """One PDF of several members, sheets numbered through the whole package.
    items: (kind, sheet, code, extra) with kind one of steel_beam, steel_column, footing,
    frame, conn, simple; extra is a dict of that sheet's keyword arguments.
    cover: None for no cover, or dict(basis, asd, lrfd, contents=[dict(mark, title, code,
    flags)], flag_lines, skipped); the contents get their sheet numbers here."""
    import io
    build = {"steel_beam": _steel_beam_pdf, "steel_column": _steel_column_pdf, "footing": _footing_pdf,
             "frame": _frame_pdf, "conn": _conn_pdf, "simple": _simple_pdf}
    counts = []
    for kind, sheet, code, extra in items:                # first pass: how many sheets each member takes
        counts.append(build[kind](sheet, io.BytesIO(), job, code, date, page=1, pages=1, **extra))
    n_cover = 0
    if cover is not None:
        for it in cover["contents"]:
            it["sheet"] = 0
        n_cover = _cover_pdf(cover, io.BytesIO(), job, "", date, 1, 1)
        first = n_cover + 1
        for it, n in zip(cover["contents"], counts):
            it["sheet"] = first
            first += n
    total = sum(counts) + n_cover
    c = canvas.Canvas(path, pagesize=letter)
    c.setTitle(title); c.setAuthor(FIRM)
    if cover is not None:
        _cover_pdf(cover, c, job, "", date, 1, total)
    page = n_cover + 1
    for (kind, sheet, code, extra), n in zip(items, counts):
        build[kind](sheet, c, job, code, date, page=page, pages=total, **extra)
        page += n
    c.save()
    return total


# ------------------------------------------------------------------ connections
def _yn(v):
    return "yes" if v else "no"


def _conn_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
    """Calc sheet for a ws_conn.ConnSheet (fillet weld group or line of bolts)."""
    i = sheet.inp
    weld = sheet.kind == "weld"
    p = _Page(path, f"Connection {sheet.mark} - " + ("Fillet Weld" if weld else "Bolt Line"), job, code,
              sheet.method, page, pages, date)
    c = p.c
    top = p.y
    p.head("Connection")
    if weld:
        rows = [("Welds", f"({i['n_lines']:g}) fillet welds, {i['size']:g} in leg, {i['length']:g} in long each"),
                ("Electrode", f"FEXX = {i['FEXX']:g} ksi"),
                ("Load Direction", f"{i['theta_deg']:g} degrees to the weld axis"),
                ("Directional Increase", _yn(i["directional"]) + " (Eq. J2-5)"),
                ("End Loaded", _yn(i["end_loaded"]) + " (J2.2b(d))"),
                ("Thinner Part", f"{i['t_thinner']:g} in" if i["t_thinner"] is not None else "not entered"),
                ("Edge Thickness", f"{i['t_edge']:g} in" if i["t_edge"] is not None else "not entered"),
                ("Base Metal", f"{i['base_t']:g} in thick, Fu = {i['base_Fu']:g} ksi" if i["base_t"] is not None
                 else "not entered")]
    else:
        rows = [("Bolts", f"({i['n']}) {i['d']:g} in diameter, {i['group']}"),
                ("Threads", "in the shear plane (N)" if i["threads"] == "N" else "excluded from the shear plane (X)"),
                ("Shear Planes", f"{i['planes']}"),
                ("Spacing", f"{i['spacing']:g} in centre to centre"),
                ("Edge Distance", f"{i['edge']:g} in, bolt centre to the edge the load pushes toward"),
                ("Holes", "standard (Table J3.3)"),
                ("Hole Deformation", "a design consideration" if i["deformation"] else "not a design consideration")]
        for k, ply in enumerate(i["plies"], 1):
            t, Fu, has_edge = ply[:3]
            cnt = ply[3] if len(ply) > 3 else 1
            rows.append((f"Part {k}", f"{'(%d) ' % cnt if cnt > 1 else ''}{t:g} in thick, Fu = {Fu:g} ksi, "
                                      + ("with an edge in the load direction" if has_edge else "no edge in the load direction")))
    p.kv(rows, kw=104)
    bottom_left = p.y
    if weld:
        _sketch_title(c, 388, top, "PLAN")
        cut = memberart.weld_plan(c, 388, top - 84, 96, 66, i["n_lines"], i["length"], i["size"], font=FR)
        _sketch_title(c, 500, top, "SECTION")
        memberart.weld_section(c, 500, top - 84, 56, 66, i["n_lines"], i["size"], i["t_edge"] or i["t_thinner"], font=FR)
        _small(c, 478, top - 93, "dimensions in inches; welds shown dark; section across the welds, not to scale")
    else:
        _sketch_title(c, 404, top, "SKETCH")
        memberart.bolt_picture(c, 404, top - 84, 160, 66, i["n"], i["spacing"], i["edge"], i["d"], font=FR)
        _small(c, 484, top - 93, "dimensions in inches; load toward the right edge")
    p.y = min(bottom_left, top - 100) - 2

    p.head("Loads")
    for ld in sheet.loads:
        s = f"{ld['case']:<3} {ld['P']:.2f} kip"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font=FM, size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in combos:
        mark = "   governs" if cb.name == sheet.governing else ""
        p.room(24)
        p.text(f"{cb.name:<18} force = {sheet.totals[cb.name]:.2f} kip{mark}", font=FM, size=8, dy=10)
        p.text(cb.source, size=7.5, color=GREY, x=LM + 12)
    p.y -= 4
    _steps(p, "Strength Calculation (AISC 360-22)", sheet.steps)
    _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions, sheet.not_checked)


def conn_pdf(sheet, path, job, code, date, page=1, pages=None, combos=()):
    return _paged(_conn_pdf, sheet, path, job, code, date, page, pages, combos=combos)


# ------------------------------------------------------------------ simple sheets
def _picture(c, top, pic):
    """Pictures for SimpleSheet members (base plate, footing with moment)."""
    name, d = pic
    if name == "wood_post":
        ax, lat = d.get("axial") or [], d.get("lateral") or []
        _sketch_title(c, 400, top, "LOADING" if (ax or lat) else "ELEVATION")
        wpt = max(min(d["d"] * 1.8, 16), 7)
        drop = (14 + 6.5 * len(ax)) if ax else 0                     # room above the post for the axial load and its labels
        ytop, ybot = top - 18 - drop, top - 96 - drop
        c.saveState(); c.translate(430 + wpt / 2, ybot); c.rotate(90)
        memberart.wood_elevation(c, 0, 0, 78, wpt, 1, kind=d.get("kind", "sawn"))
        c.restoreState()
        memberart._dim_v(c, ybot, ytop, 430 + wpt / 2 + 8, f"{d['height']:g} ft", FR, ext_from=430 + wpt / 2)
        c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC)
        if ax:
            c.setLineWidth(0.9)
            _arrow_down(c, 430, ytop + 12, ytop + 1, head=3)
            c.setFont(FR, 5.5)
            for i, t_ in enumerate(ax):
                c.drawCentredString(430, ytop + 14 + 6.5 * (len(ax) - 1 - i), t_)
        if lat:
            xl = 430 - wpt / 2
            for k, ld in enumerate(lat):
                c.setLineWidth(0.45)
                if ld["kind"] == "uniform":
                    xo = xl - 9 - 0 * k
                    c.line(xo, ybot, xo, ytop)
                    for i in range(8):
                        yy = ybot + (ytop - ybot) * i / 7
                        c.line(xo, yy, xl - 2.2, yy)
                        t = c.beginPath(); t.moveTo(xl - 0.5, yy); t.lineTo(xl - 3, yy + 1.1); t.lineTo(xl - 3, yy - 1.1); t.close()
                        c.drawPath(t, fill=1, stroke=0)
                    c.setFont(FR, 5.5); c.drawRightString(xo - 2, (ytop + ybot) / 2 - 2 + 7 * k, f"{ld['case']} {ld['w']:,.0f} plf")
                else:
                    yy = ybot + (ytop - ybot) * ld["x_ft"] / d["height"]
                    c.setLineWidth(0.8); c.line(xl - 16, yy, xl - 3, yy)
                    t = c.beginPath(); t.moveTo(xl - 0.5, yy); t.lineTo(xl - 3.6, yy + 1.6); t.lineTo(xl - 3.6, yy - 1.6); t.close()
                    c.drawPath(t, fill=1, stroke=0)
                    c.setFont(FR, 5.5); c.drawRightString(xl - 18, yy - 2, f"{ld['case']} {ld['P']:,.0f} lb")
        c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK)
        _sketch_title(c, 505, top, "SECTION")
        s_ = memberart.wood_section(c, 528, top - 50, 46, 46, d["b"], d["d"], d.get("plies", 1), kind=d.get("kind", "sawn"))
        memberart._dim_h(c, 528 - d["b"] * s_ / 2, 528 + d["b"] * s_ / 2, top - 50 - d["d"] * s_ / 2 - 8, f"{d['b']:g}", FR,
                         ext_from=top - 50 - d["d"] * s_ / 2)
        memberart._dim_v(c, top - 50 - d["d"] * s_ / 2, top - 50 + d["d"] * s_ / 2, 528 + d["b"] * s_ / 2 + 7, f"{d['d']:g}", FR,
                         ext_from=528 + d["b"] * s_ / 2)
        _small(c, 476, top - 106 - drop, "section to scale, dimensions in inches" + ("; loads in lb and plf" if (ax or lat) else ""))
        return top - 110 - drop
    if name == "ijoist":
        lh = _beam_loads_height(d.get("loads"))
        _sketch_title(c, 384, top, "LOADING" if lh else "ELEVATION")
        h = max(min(d["d"] * 1.2, 18), 9)
        x0, x1, y = 384, 384 + 118, top - 26 - h - max(lh - 8, 0)
        if lh:
            _beam_loads(c, x0 + 3, x1 - 3, y + h, d["span"], d["loads"])
        fl = max(h * 0.16, 1.8)
        c.setLineWidth(0.5); c.setStrokeColorRGB(*memberart.LVL_LINE)
        c.setFillColorRGB(0.93, 0.87, 0.74); c.rect(x0, y, x1 - x0, h, fill=1, stroke=1)                 # web
        c.setFillColorRGB(*memberart.LVL_FILL)
        c.rect(x0, y, x1 - x0, fl, fill=1, stroke=1); c.rect(x0, y + h - fl, x1 - x0, fl, fill=1, stroke=1)
        c.setFillColorRGB(0.20, 0.22, 0.25)
        sup = d.get("supports") or [0.0, d["span"]]
        sx = [x0 + 3 + (x1 - x0 - 6) * v / d["span"] for v in sup]
        for xx in sx:
            p_ = c.beginPath(); p_.moveTo(xx, y); p_.lineTo(xx - 4, y - 6); p_.lineTo(xx + 4, y - 6); p_.close()
            c.drawPath(p_, fill=1, stroke=0)
        marks = [x0 + 3] + sx + [x1 - 3]
        vals = [0.0] + list(sup) + [d["span"]]
        for (xa, xb), (va, vb) in zip(zip(marks[:-1], marks[1:]), zip(vals[:-1], vals[1:])):
            if vb - va > 1e-6:
                memberart._dim_h(c, xa, xb, y - 15, f"{vb - va:g} ft" if xb - xa > 22 else f"{vb - va:g}", FR, ext_from=y - 6)
        _sketch_title(c, 520, top, "SECTION")
        D = max(min(d["d"] * 2.6, 58), 26); fw, fd, wt = D * 0.22 + 4, max(D * 0.11, 3.5), 1.6
        cx, cy = 540, top - 46
        c.setLineWidth(0.6); c.setStrokeColorRGB(*memberart.LVL_LINE)
        c.setFillColorRGB(0.93, 0.87, 0.74); c.rect(cx - wt / 2, cy - D / 2 + fd * 0.6, wt, D - fd * 1.2, fill=1, stroke=1)
        c.setFillColorRGB(*memberart.LVL_FILL)
        c.rect(cx - fw / 2, cy - D / 2, fw, fd, fill=1, stroke=1); c.rect(cx - fw / 2, cy + D / 2 - fd, fw, fd, fill=1, stroke=1)
        memberart._dim_v(c, cy - D / 2, cy + D / 2, cx + fw / 2 + 7, f"{d['d']:g}", FR, ext_from=cx + fw / 2)
        _small(c, 476, min(top - 98, y - 34), "schematic; depth in inches" + ("; loads in plf and lb" if lh else ""))
        return min(top - 102, y - 38)
    if name == "wood_beam":
        lh = _beam_loads_height(d.get("loads"))
        _sketch_title(c, 384, top, "LOADING" if lh else "ELEVATION")
        h = max(min(d["d"] * 1.6, 18), 7)
        x0, x1, y = 384, 384 + 118, top - 26 - h - max(lh - 8, 0)
        if lh:
            _beam_loads(c, x0 + 3, x1 - 3, y + h, d["span"], d["loads"])
        memberart.wood_elevation(c, x0, y, x1 - x0, h, d["plies"], kind=d.get("kind", "sawn"), lams=d.get("lams"))
        c.setFillColorRGB(0.20, 0.22, 0.25)
        sup = d.get("supports") or [0.0, d["span"]]
        sx = [x0 + 3 + (x1 - x0 - 6) * v / d["span"] for v in sup]
        for xx in sx:
            p_ = c.beginPath(); p_.moveTo(xx, y); p_.lineTo(xx - 4, y - 6); p_.lineTo(xx + 4, y - 6); p_.close()
            c.drawPath(p_, fill=1, stroke=0)
        marks = [x0 + 3] + sx + [x1 - 3]
        vals = [0.0] + list(sup) + [d["span"]]
        for (xa, xb), (va, vb) in zip(zip(marks[:-1], marks[1:]), zip(vals[:-1], vals[1:])):
            if vb - va > 1e-6:
                memberart._dim_h(c, xa, xb, y - 15, f"{vb - va:g} ft" if xb - xa > 22 else f"{vb - va:g}", FR, ext_from=y - 6)
        _sketch_title(c, 520, top, "SECTION")
        s_ = memberart.wood_section(c, 540, top - 46, 44, 60, d["b"], d["d"], d["plies"], kind=d.get("kind", "sawn"))
        memberart._dim_h(c, 540 - d["b"] * s_ / 2, 540 + d["b"] * s_ / 2, top - 46 - d["d"] * s_ / 2 - 8, f"{d['b']:g}", FR,
                         ext_from=top - 46 - d["d"] * s_ / 2)
        memberart._dim_v(c, top - 46 - d["d"] * s_ / 2, top - 46 + d["d"] * s_ / 2, 540 + d["b"] * s_ / 2 + 7, f"{d['d']:g}", FR,
                         ext_from=540 + d["b"] * s_ / 2)
        _small(c, 476, min(top - 98, y - 34), d.get("caption") or ("section to scale, dimensions in inches" + ("; loads in plf and lb" if lh else "")))
        return min(top - 102, y - 38)
    if name == "base_plate":
        _sketch_title(c, 470, top, "PLAN", centred=True)
        memberart.base_plate_plan(c, 470, top - 52, 170, 82, d["d"], d["bf"], d["tf"], d["tw"], d["N"], d["B"],
                                  d["support"], font=FR)
        _small(c, 470, top - 102, "dimensions in inches; to scale" + ("; concrete support dashed" if d["support"] else ""))
        return top - 106
    if name == "base_plate_moment":
        N, B = d["N"], d["B"]
        # plan: the moment acts along the page width
        _sketch_title(c, 384, top, "PLAN")
        s = min(74 / N, 50 / B)
        cx, cy = 384 + 37, top - 44
        c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(0.87, 0.90, 0.93)
        c.rect(cx - N * s / 2, cy - B * s / 2, N * s, B * s, fill=1, stroke=1)
        c.saveState(); c.translate(cx, cy); c.rotate(90)
        memberart.steel_section(c, 0, 0, d["bf"] * s, d["d"] * s, d["d"], d["bf"], d["tf"], d["tw"])
        c.restoreState()
        r = max(d["rod_d"] * s / 2, 1.3)
        for sx in (-1, 1):
            for k in range(d["n"]):
                yy = cy - B * s / 2 + (d["side"] + (B - 2 * d["side"]) * (k / (d["n"] - 1) if d["n"] > 1 else 0.5 * 0 + 0.5)) * s \
                    if d["n"] > 1 else cy
                c.setFillColorRGB(0.30, 0.34, 0.39); c.circle(cx + sx * (N / 2 - d["edge"]) * s, yy, r, fill=1, stroke=0)
        memberart._dim_h(c, cx - N * s / 2, cx + N * s / 2, cy - B * s / 2 - 15, f"{N:g}", FR, ext_from=cy - B * s / 2)
        memberart._dim_h(c, cx - N * s / 2, cx - (N / 2 - d["edge"]) * s, cy - B * s / 2 - 5, f"{d['edge']:g}", FR,
                         ext_from=cy - B * s / 2)
        memberart._dim_v(c, cy - B * s / 2, cy + B * s / 2, cx + N * s / 2 + 6, f"{B:g}", FR, ext_from=cx + N * s / 2)
        # section along the moment: bearing block and rod tension for the governing case
        x0 = 486
        _sketch_title(c, x0, top, "SECTION")
        s2 = 70 / N
        px, py, tp = x0 + 4, top - 52, max(d["t"] * s2, 2.0)
        memberart._concrete(c, px - 4, py - 22, N * s2 + 8, 22)
        c.setLineWidth(0.6); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(*memberart.STEEL_FILL)
        c.rect(px, py, N * s2, tp, fill=1, stroke=1)
        cw = d["d"] * s2
        c.rect(px + N * s2 / 2 - cw / 2, py + tp, cw, 22, fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_LINE)
        tfp = max(d["tf"] * s2, 1.2)
        c.rect(px + N * s2 / 2 - cw / 2, py + tp, tfp, 22, fill=1, stroke=0)
        c.rect(px + N * s2 / 2 + cw / 2 - tfp, py + tp, tfp, 22, fill=1, stroke=0)
        for sx in (0, 1):                                   # rods
            rx = px + (d["edge"] if sx == 0 else N - d["edge"]) * s2
            c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(1.1); c.line(rx, py - 16, rx, py + tp + 5)
        Y = d["Y"] * s2                                     # bearing block at the right (compression) edge
        c.setFillColorRGB(0.86, 0.90, 0.95); c.setStrokeColorRGB(*BLUE); c.setLineWidth(0.6)
        c.rect(px + N * s2 - Y, py - 9, Y, 9, fill=1, stroke=1)
        memberart._dim_h(c, px + N * s2 - Y, px + N * s2, py - 27, f"Y = {d['Y']:.2f}", FR, ext_from=py - 9)
        if d["T"] > 0:
            rx = px + d["edge"] * s2
            c.setStrokeColorRGB(*FLAGC); c.setFillColorRGB(*FLAGC); c.setLineWidth(0.9)
            c.line(rx, py + tp + 6, rx, py + tp + 18)
            t = c.beginPath(); t.moveTo(rx, py + tp + 21); t.lineTo(rx - 2.5, py + tp + 16); t.lineTo(rx + 2.5, py + tp + 16); t.close()
            c.drawPath(t, fill=1, stroke=0)
            c.setFont(FM, 6); c.drawString(px - 2, py + tp + 24, f"T = {d['T']:.1f} k")
        _small(c, 476, top - 104, "dimensions in inches; section shows the bearing block and rod tension")
        _small(c, 476, top - 111, f"for {d['case']}")
        return top - 115
    if name == "footing_moment":
        _sketch_title(c, 470, top, "SECTION AND SOIL PRESSURE", centred=True)
        base = top - 74
        s = memberart.footing_section(c, 470, base, 150, 52, d["B"], d["h"], d["col"], d["supported"], d["cover"],
                                      d["db"], d["n"], d["db"], plate_w_in=d["plate"], soil_depth_in=d["soil"])
        x0, W = 470 - d["B"] * s / 2, d["B"] * s
        k = 20.0 / (d["qmax"] or 1.0)
        a = d["bearing"] * s
        p = c.beginPath()                                    # pressure pushes up on the underside; drawn below it
        p.moveTo(x0 + W, base - 2); p.lineTo(x0 + W, base - 2 - k * d["qmax"])
        p.lineTo(x0 + W - a, base - 2 - k * d["qmin"]); p.lineTo(x0 + W - a, base - 2); p.close()
        c.setFillColorRGB(0.86, 0.90, 0.95); c.setStrokeColorRGB(*BLUE); c.setLineWidth(0.6)
        c.drawPath(p, fill=1, stroke=1)
        c.setFillColorRGB(*BLUE); c.setFont(FM, 6.5)
        c.drawString(x0 + W + 3, base - 2 - k * d["qmax"], f"{d['qmax']:,.0f} psf")
        c.drawRightString(x0 + W - a - 3, base - 9, f"{d['qmin']:,.0f} psf")
        sc = d.get("case")
        if sc:                                               # loading of the governing service case on the section (not to a force scale)
            import math as _m
            y_ftg = base + d["h"] * s
            y_top = y_ftg + (max(1.6 * d["h"], 12.0) + (0.25 if d.get("plate") else 0.0)) * s
            c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
            _arrow_down(c, 470, y_top + 12, y_top + 1.5)
            c.setFont(FR, 6); c.drawRightString(470 - 4, y_top + 6, f"P {sc['P']:,.0f} lb")
            if sc["M"]:
                r_ = 7.0                                     # moment toward the edge with the larger pressure (the right)
                c.setLineWidth(0.8); c.arc(470 + 6 - r_, y_top + 4 - r_, 470 + 6 + r_, y_top + 4 + r_, 135, -180)
                ex, ey = 470 + 6 + r_ * _m.cos(_m.radians(-45)), y_top + 4 + r_ * _m.sin(_m.radians(-45))
                t_ = c.beginPath(); t_.moveTo(ex - 1.2, ey - 3.6); t_.lineTo(ex - 3.4, ey + 1.0); t_.lineTo(ex + 1.6, ey + 0.2); t_.close()
                c.drawPath(t_, fill=1, stroke=0)
                c.drawString(470 + 16, y_top + 6, f"M {sc['M']:,.0f} lb-ft")
            if sc["V"]:
                xs_ = 470 - d["col"] * s / 2
                _arrow(c, xs_ - 22, y_ftg + 4, xs_ - 2, y_ftg + 4, head=3)
                c.drawRightString(xs_ - 24, y_ftg + 2, f"V {sc['V']:,.0f} lb")
        _small(c, 470, base - 32, "section to scale; loads and soil pressure for the governing service case" + (f", {sc['name']}" if sc else ""))
        return base - 36
    return top


def _simple_pdf(sheet, path, job, code, date, page=1, pages=1):
    p = _Page(path, f"{sheet.mark} - {sheet.title}", job, code, sheet.method, page, pages, date)
    top = p.y
    p.head(sheet.section)
    for k, v in sheet.info:
        lines = _split(v, 62)
        p.kv([(k, lines[0])] + [("", t) for t in lines[1:]], kw=86)
    bottom_left = p.y
    low = _picture(p.c, top, sheet.picture) if sheet.picture else top
    p.y = min(bottom_left, low) - 2
    if sheet.load_lines:
        p.head("Loads")
        for s in sheet.load_lines:
            p.room(12); p.text(s, font=FM, size=7.5 if len(s) > 105 else 8)
        p.y -= 2
    if sheet.combo_lines:
        p.head("Load Combinations")
        for t, src in sheet.combo_lines:
            p.room(24)
            p.text(t, font=FM, size=8, dy=10)
            p.text(src, size=7.5, color=GREY, x=LM + 12)
    dg = getattr(sheet, "diagram", None)
    if dg:
        p.y -= 4
        p.room(70)
        p.head(f"Shear and Moment, {dg['combo']}" + (f" ({dg['note']})" if dg.get("note") else ""))
        dy0 = p.y - 40
        V, M = dg["V"], dg["M"]
        _diagram(p.c, LM, dy0, 245, 32, dg["x"], V, BLUE, f"V max = {max(abs(v) for v in V):,.0f} lb")
        _diagram(p.c, LM + 280, dy0, 245, 32, dg["x"], [-m for m in M], (0.54, 0.35, 0.0), f"M max = {max(abs(m) for m in M):,.0f} lb-ft")
        p.y = dy0 - 12
    p.y -= 4
    if sheet.steps:
        _steps(p, sheet.steps_title, sheet.steps)
    for b in sheet.blocks:
        if b.get("picture"):
            p.room(316 if b["picture"][0] == "wind_mwfrs" and len(b["picture"][1]["panels"]) > 2 else
                   230 if b["picture"][0] in ("anchorage", "perforated_wall") else 215 if b["picture"][0] == "lag" else 175)
            if b["picture"][0] in ("wind_mwfrs", "wind_zones", "seismic_forces", "diaphragm", "collector", "nailed", "toe_nail", "lag", "bolted", "bolted_perp"):
                p.head(b["title"]); p.y = _block_picture(p.c, p.y + 4, b["picture"]) - 6
                continue
            p.head(b.get("head") or b["title"] + ": Inputs and Layout")
            for k, v in b.get("info", ()):
                lines = _split(v, 104)
                p.kv([(k, lines[0])] + [("", t) for t in lines[1:]], kw=86)
            for t in b.get("text", ()):
                p.text(t, font=FM, size=8)
            p.y = _block_picture(p.c, p.y + 4, b["picture"]) - 6
        if b.get("steps"):
            _steps(p, b["title"], b["steps"])
        if b.get("lines"):
            p.room(min(14 + 10 * (len(b["lines"]) + sum(len(_split(t, 116)) for t in b.get("after", ())) + 1), 260))
            p.head(b["title"])
            for t in b["lines"]:
                p.room(11); p.text(t, font=FM, size=7.5, dy=10)
            for t in b.get("after", ()):
                for u in _split(t, 116):
                    p.room(11); p.text(u, size=7.5, color=GREY, dy=10)
            p.y -= 3
    if sheet.rows:
        _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions, sheet.not_checked)


LOADC = (0.16, 0.33, 0.58)


def _arrow_down(c, x, y_top, y_tip, head=2.2):
    c.line(x, y_top, x, y_tip + head)
    t = c.beginPath(); t.moveTo(x, y_tip); t.lineTo(x - head * 0.7, y_tip + head * 1.6); t.lineTo(x + head * 0.7, y_tip + head * 1.6); t.close()
    c.drawPath(t, fill=1, stroke=0)


def _beam_load_rows(loads):
    """Rows of the loading diagram, bottom row first: each uniform load is its own band;
    all point loads share the lowest row."""
    uni = [ld for ld in loads if ld["kind"] == "uniform"]
    pts = [ld for ld in loads if ld["kind"] != "uniform"]
    return pts, uni


def _beam_loads_height(loads):
    pts, uni = _beam_load_rows(loads or [])
    return (16 if pts else 0) + sum(12 if ld.get("w2") is None else 14 for ld in uni) + (3 if (pts or uni) else 0)


def _beam_loads(c, x0, x1, y, span, loads):
    """Loading diagram over a beam whose top is at y, drawn between x0 and x1 (the span):
    point loads as single arrows with their value, uniform loads as bands of arrows, each
    labelled with its load case and value. Loads are in plf and lb."""
    pts, uni = _beam_load_rows(loads or [])
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC)
    yy = y + 1.5
    if pts:
        c.setLineWidth(0.8)
        at = {}
        for ld in pts:
            at.setdefault(round(ld["x_ft"], 3), []).append(f"{ld['case']} {ld['P']:,.0f}")
        for xf, parts in at.items():
            xx = x0 + (x1 - x0) * xf / span
            _arrow_down(c, xx, yy + 13, yy, head=2.8)
            c.setFont(FR, 5.5)
            txt = " + ".join(parts) + " lb"
            if xx - x0 < 20:
                c.drawString(xx + 2.5, yy + 8.5, txt)
            elif x1 - xx < 20:
                c.drawRightString(xx - 2.5, yy + 8.5, txt)
            else:
                c.drawString(xx + 2.5, yy + 8.5, txt)
        yy += 16
    for ld in uni:
        xa = x0 + (x1 - x0) * ld.get("x1_ft", 0.0) / span
        xb = x0 + (x1 - x0) * ld.get("x2_ft", span) / span
        c.setLineWidth(0.45)
        w2 = ld.get("w2")
        if w2 is None:
            ha = hb_ = 5.0
        else:
            m_ = max(abs(ld["w"]), abs(w2)) or 1.0
            ha, hb_ = 1.2 + 6.3 * abs(ld["w"]) / m_, 1.2 + 6.3 * abs(w2) / m_
        c.line(xa, yy + ha, xb, yy + hb_)
        n = max(int((xb - xa) / 9), 2)
        for i in range(n + 1):
            hh = ha + (hb_ - ha) * i / n
            if hh > 2.6:
                _arrow_down(c, xa + (xb - xa) * i / n, yy + hh, yy, head=1.5)
        c.setFont(FR, 5.5)
        fmt = lambda v: f"{v:,.0f}" if abs(v) >= 20 else f"{v:.1f}"
        if w2 is None:
            c.drawCentredString((xa + xb) / 2, yy + 6.5, f"{ld['case']} {fmt(ld['w'])} plf")
        else:                                              # label over the low half of the taper, clear of the sloping line
            xl_ = xa + (xb - xa) * (0.75 if ha >= hb_ else 0.25)
            c.drawCentredString(xl_, yy + (ha + hb_) / 2 + 2.5, f"{ld['case']} {fmt(ld['w'])} to {fmt(w2)} plf")
        yy += 12 if w2 is None else 14
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK)


def _block_picture(c, top, pic):
    """Full-width pictures for the further blocks of a SimpleSheet. Returns the y below."""
    name, d = pic
    if name == "snow":
        return _snow_picture(c, top, d)
    if name == "shear_wall":
        return _shear_wall_picture(c, top, d)
    if name == "perforated_wall":
        return _perforated_wall_picture(c, top, d)
    if name == "snow_drift":
        return _snow_drift_picture(c, top, d)
    if name == "wind_mwfrs":
        return _wind_mwfrs_picture(c, top, d)
    if name == "wind_zones":
        return _wind_zones_picture(c, top, d)
    if name == "seismic_forces":
        return _seismic_forces_picture(c, top, d)
    if name == "diaphragm":
        return _diaphragm_picture(c, top, d)
    if name == "collector":
        return _collector_picture(c, top - 6, d)
    if name == "rain":
        return _rain_picture(c, top - 6, d)
    if name == "guard":
        return _guard_picture(c, top - 6, d)
    if name == "topo":
        return _topo_picture(c, top - 6, d)
    if name == "nailed":
        return _nailed_picture(c, top, d)
    if name == "lag":
        return _lag_picture(c, top - 8, d)
    if name == "toe_nail":
        return _toe_nail_picture(c, top - 8, d)
    if name == "bolted":
        return _bolted_picture(c, top, d)
    if name == "bolted_perp":
        return _bolted_perp_picture(c, top, d)
    if name != "anchorage":
        return top
    SN, SB, N, B = d["sup_N"], d["sup_B"], d["N"], d["B"]
    g = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    # ---- plan: the moment and the shear act along the page width
    _sketch_title(c, LM + 6, top - 4, "PLAN")
    s = min(150 / SN, 92 / SB)
    x0, y0 = LM + 30, top - 22 - SB * s
    memberart._concrete(c, x0, y0, SN * s, SB * s, seed=5)
    px, py = x0 + (SN - N) * s / 2, y0 + (SB - B) * s / 2
    c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(0.87, 0.90, 0.93)
    c.rect(px, py, N * s, B * s, fill=1, stroke=1)
    r = max(d["rod_d"] * s / 2, 1.4)
    ys = [y0 + (d["c_side"] + k * d["s_row"]) * s for k in range(d["n"])] if d["n"] > 1 else [y0 + SB * s / 2]
    xs = [x0 + d["c_end"] * s, x0 + (d["c_end"] + d["s_rows"]) * s]
    c.setFillColorRGB(0.30, 0.34, 0.39)
    for xx in xs:
        for yy in ys:
            c.circle(xx, yy, r, fill=1, stroke=0)
    yb = y0 - 8
    memberart._dim_h(c, x0, xs[0], yb, g(d["c_end"]), FR, ext_from=y0)
    memberart._dim_h(c, xs[0], xs[1], yb, g(d["s_rows"]), FR, ext_from=y0)
    memberart._dim_h(c, xs[1], x0 + SN * s, yb, g(d["c_end"]), FR, ext_from=y0)
    memberart._dim_h(c, x0, x0 + SN * s, yb - 14, g(SN) + " concrete", FR)
    xr = x0 + SN * s + 8
    memberart._dim_v(c, y0, ys[0], xr, g(d["c_side"]), FR, ext_from=x0 + SN * s)
    if d["n"] > 1:
        memberart._dim_v(c, ys[0], ys[-1], xr, (f"{d['n'] - 1} @ " if d["n"] > 2 else "") + g(d["s_row"]), FR, ext_from=x0 + SN * s)
        memberart._dim_v(c, ys[-1], y0 + SB * s, xr, g(d["c_side"]), FR, ext_from=x0 + SN * s)
    else:
        memberart._dim_v(c, ys[0], y0 + SB * s, xr, g(d["c_side"]), FR, ext_from=x0 + SN * s)
    memberart._dim_v(c, y0, y0 + SB * s, xr + 38, g(SB) + " concrete", FR)
    low1 = yb - 26
    # ---- section along the moment
    sx0 = LM + 300
    _sketch_title(c, sx0, top - 4, "SECTION")
    s2 = min(150 / SN, 84 / d["ha"])
    tp = 3.0
    cx0, ctop = sx0 + 6, top - 34
    memberart._concrete(c, cx0, ctop - d["ha"] * s2, SN * s2, d["ha"] * s2, seed=9)
    c.setLineWidth(0.6); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(*memberart.STEEL_FILL)
    c.rect(cx0 + (SN - N) * s2 / 2, ctop, N * s2, tp, fill=1, stroke=1)
    for k in (0, 1):
        rx = cx0 + (d["c_end"] + k * d["s_rows"]) * s2
        c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(1.1)
        c.line(rx, ctop - d["hef"] * s2, rx, ctop + tp + 5)
        c.setFillColorRGB(0.20, 0.22, 0.25)
        c.rect(rx - 3, ctop - d["hef"] * s2 - 2.2, 6, 2.2, fill=1, stroke=0)
        c.rect(rx - 2.4, ctop + tp, 4.8, 2, fill=1, stroke=0)
    xr = cx0 + SN * s2 + 8
    memberart._dim_v(c, ctop - d["hef"] * s2, ctop, xr, "hef = " + g(d["hef"]), FR, ext_from=cx0 + SN * s2)
    memberart._dim_v(c, ctop - d["ha"] * s2, ctop, xr + 44, "ha = " + g(d["ha"]), FR, ext_from=cx0 + SN * s2)
    yb2 = ctop - d["ha"] * s2 - 8
    memberart._dim_h(c, cx0, cx0 + d["c_end"] * s2, yb2, g(d["c_end"]), FR, ext_from=ctop - d["ha"] * s2)
    memberart._dim_h(c, cx0 + d["c_end"] * s2, cx0 + (d["c_end"] + d["s_rows"]) * s2, yb2, g(d["s_rows"]), FR,
                     ext_from=ctop - d["ha"] * s2)
    low2 = yb2 - 12
    low = min(low1, low2)
    _small(c, (LM + RM) / 2, low - 4, "dimensions in inches; to scale; edge distances are measured from the rod centres")
    return low - 8


def _arrow(c, x1, y1, x2, y2, head=3.2):
    """A line from (x1, y1) to (x2, y2) with a filled head at the second point."""
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    c.line(x1, y1, x2 - head * 0.8 * math.cos(a), y2 - head * 0.8 * math.sin(a))
    t = c.beginPath(); t.moveTo(x2, y2)
    for da in (2.7, -2.7):
        t.lineTo(x2 + head * math.cos(a + da), y2 + head * math.sin(a + da))
    t.close(); c.drawPath(t, fill=1, stroke=0)


def _wind_mwfrs_picture(c, top, d):
    """One section through the building for each wind direction, to scale, wind from the
    left: an arrow on each surface toward it (pressure) or away from it (suction) with the
    external pressure q Kd G Cp in psf. The internal pressure is not drawn. Two panels to a row."""
    import math
    pw = (RM - LM) / 2
    hmax = max(max(pn["hl"], pn["hr"]) + (pn["rise"] if pn["shape"] == "gable" else 0.0) for pn in d["panels"])
    lmax = max(pn["L"] for pn in d["panels"])
    s = min((pw - 150) / lmax, 62.0 / hmax)
    y = top
    for i, pn in enumerate(d["panels"]):
        if i and i % 2 == 0:
            y -= 140
        x0 = LM + (i % 2) * pw
        ybase = y - 112
        _sketch_title(c, x0 + 6, y - 4, pn["title"])
        L, shape = pn["L"], pn["shape"]
        xl = x0 + 76 + ((pw - 150) - L * s) / 2
        xr, yl, yrt = xl + L * s, ybase + pn["hl"] * s, ybase + pn["hr"] * s
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.line(x0 + 30, ybase, x0 + pw - 30, ybase)
        c.setStrokeColorRGB(*INK); c.setLineWidth(1.0)
        c.line(xl, ybase, xl, yl); c.line(xr, ybase, xr, yrt)
        if shape == "gable":
            yp = yl + pn["rise"] * s
            xp1, xp2 = (xl + xr) / 2 - pn.get("top", 0.0) * s / 2, (xl + xr) / 2 + pn.get("top", 0.0) * s / 2
            c.line(xl, yl, xp1, yp); c.line(xp1, yp, xp2, yp); c.line(xp2, yp, xr, yrt)
        else:
            c.line(xl, yl, xr, yrt)
        c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.7); c.setFont(FR, 6)

        def wall(x, ht, p, side, label):
            out = -1 if side == "left" else 1
            for f in (0.3, 0.7):
                yy = ybase + ht * s * f
                a, b = (x + out * 16, x + out * 1) if p >= 0 else (x + out * 1, x + out * 16)
                _arrow(c, a, yy, b, yy)
            t = f"{label} {p:+.1f}"
            (c.drawRightString if side == "left" else c.drawString)(x + out * 19, ybase + ht * s * 0.5 - 2, t)

        def slope(xa, ya, xb, yb, vals, nm, align):
            ang = math.atan2(yb - ya, xb - xa)
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            nx, ny = -math.sin(ang), math.cos(ang)
            a, b = ((mx + nx * 16, my + ny * 16), (mx + nx, my + ny)) if vals[0] >= 0 else ((mx + nx, my + ny), (mx + nx * 16, my + ny * 16))
            _arrow(c, a[0], a[1], b[0], b[1])
            t = nm + " " + " and ".join(f"{v:+.1f}" for v in vals)
            {"right": c.drawRightString, "left": c.drawString, "centre": c.drawCentredString}[align](
                mx + nx * 19 + (-2 if align == "right" else 2 if align == "left" else 0), my + ny * 19 + 1, t)

        wall(xl, pn["hl"], pn["windward"], "left", "windward")
        wall(xr, pn["hr"], pn["leeward"], "right", "leeward")
        ytop = max(yl, yrt)
        if shape == "gable":
            slope(xl, yl, xp1, yp, pn["roof_windward"], "windward roof", "right")
            slope(xp2, yp, xr, yrt, pn["roof_leeward"], "leeward roof", "left")
        elif shape == "mono":
            slope(xl, yl, xr, yrt, pn["roof_values"], "roof", "centre")
        else:
            zs = pn["zones"]
            for k, (x1, x2, p) in enumerate(zs):
                xa, xb = xl + x1 * s, xl + x2 * s
                ya = yl + (yrt - yl) * ((xa + xb) / 2 - xl) / (xr - xl)
                if k:
                    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.line(xa, ya - 3, xa, ya + 20)
                    c.setStrokeColorRGB(*LOADC); c.setLineWidth(0.7)
                xm = (xa + xb) / 2
                a, b = (ya + 16, ya + 1) if p >= 0 else (ya + 1, ya + 16)
                _arrow(c, xm, a, xm, b)
                c.drawCentredString(xm, ya + 19 + (7 if (xb - xa) < 26 and k % 2 else 0), f"{p:+.1f}")
            c.drawString(xr + 4, yrt + 12, f"each zone also {pn['other']:+.1f}")
            c.setFillColorRGB(*GREY)
            c.drawCentredString((xl + xr) / 2, min(yl, yrt) - 8, "roof zones at " + ", ".join(f"{x2:g}" for x1, x2, p in zs) + " ft")
        c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.9)
        _arrow(c, x0 + 6, y - 26, x0 + 34, y - 26, head=4)
        c.setFont(FR, 6); c.drawString(x0 + 6, y - 22, "WIND")
        memberart._dim_h(c, xl, xr, ybase - 9, f"L = {L:g} ft", FR, ext_from=ybase)
    ybase = y - 112
    _small(c, (LM + RM) / 2, ybase - 30, "sections to scale; external pressure q Kd G Cp in psf, + toward the surface, - away from it; windward wall value at its top")
    return ybase - 36


def _bolted_picture(c, top, d):
    """Face of the main member at its end, to scale: the bolts, the end distance, the spacing
    in a row, the spacing between rows and the edge distance dimensioned; the load arrow."""
    D, R, n, sp, g, end, edge, w = d["D"], d["rows"], d["n"], d["s"], d["g"], d["end"], d["edge"], d["w"]
    Lshow = end + (n - 1) * (sp or 0) + max(3 * D, 3.0)
    sc = min(230.0 / Lshow, 70.0 / w)
    x_end = (LM + RM) / 2 - Lshow * sc / 2                 # the member end at the left
    y0 = top - 26 - w * sc
    y1 = y0 + w * sc
    x_far = x_end + Lshow * sc
    c.setFillColorRGB(0.93, 0.87, 0.74); c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    pth = c.beginPath(); pth.moveTo(x_far, y1); pth.lineTo(x_end, y1); pth.lineTo(x_end, y0); pth.lineTo(x_far, y0); c.drawPath(pth, fill=1, stroke=1)
    c.setDash(2, 2); c.line(x_far, y0, x_far, y1); c.setDash()
    group = (R - 1) * g
    yb = [y1 - (edge + k * g) * sc for k in range(R)]       # the first row at the entered edge distance from the top edge
    c.setFillColorRGB(1, 1, 1)
    for y in yb:
        for k in range(n):
            c.circle(x_end + (end + k * (sp or 0)) * sc, y, max(1.6, D * sc / 2), fill=1, stroke=1)
    memberart._dim_h(c, x_end, x_end + end * sc, y0 - 9, f"{end:g} in", FR, ext_from=y0)
    if n > 1:
        memberart._dim_h(c, x_end + end * sc, x_end + (end + sp) * sc, y0 - 9, f"{sp:g} in", FR, ext_from=y0)
    xr = x_far + 10
    memberart._dim_v(c, yb[0], y1, xr, f"{edge:g} in", FR, ext_from=x_far)
    if R > 1:
        memberart._dim_v(c, yb[1], yb[0], xr + 34, f"{g:g} in", FR, ext_from=x_far)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    xa = x_far + 84
    if d["sense"] == "tension":
        _arrow(c, xa, (y0 + y1) / 2, xa + 26, (y0 + y1) / 2, head=4)
    else:
        _arrow(c, xa + 26, (y0 + y1) / 2, xa, (y0 + y1) / 2, head=4)
    c.setFont(FR, 6.5); c.drawString(xa, (y0 + y1) / 2 + 5, d["sense"])
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawRightString(x_end - 4, (y0 + y1) / 2 - 2, "member end")
    _small(c, (LM + RM) / 2, y0 - 28, "face of the main member at the connection, to scale")
    return y0 - 34


def _bolted_perp_picture(c, top, d):
    """Face of the member loaded perpendicular to grain, to scale, grain running left to right
    and the load acting downward: the bolts, the loaded and unloaded edge distances, the
    spacing along the load, the spacing between rows and the end distance dimensioned."""
    D, R, n, sp, g, w = d["D"], d["rows"], d["n"], d["s"] or 0.0, d["g"] or 0.0, d["w"]
    le, ue, end = d["loaded_edge"], d["unloaded_edge"], d["end"]
    end_show = min(end, max(6 * D, 6.0))
    Lshow = end_show + (R - 1) * g + max(4 * D, 4.0)
    sc = min(230.0 / Lshow, 76.0 / w)
    x_end = (LM + RM) / 2 - Lshow * sc / 2
    y0 = top - 26 - w * sc
    y1 = y0 + w * sc
    x_far = x_end + Lshow * sc
    c.setFillColorRGB(0.93, 0.87, 0.74); c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    pth = c.beginPath(); pth.moveTo(x_far, y1); pth.lineTo(x_end, y1); pth.lineTo(x_end, y0); pth.lineTo(x_far, y0); c.drawPath(pth, fill=1, stroke=1)
    c.setDash(2, 2); c.line(x_far, y0, x_far, y1); c.setDash()
    xs = [x_end + (end_show + k * g) * sc for k in range(R)]
    ys = [y0 + (le + k * sp) * sc for k in range(n)]
    c.setFillColorRGB(1, 1, 1)
    for x in xs:
        for y in ys:
            c.circle(x, y, max(1.6, D * sc / 2), fill=1, stroke=1)
    xr = x_far + 10
    memberart._dim_v(c, y0, ys[0], xr, f"{le:g} in loaded edge", FR, ext_from=x_far)
    if n > 1:
        memberart._dim_v(c, ys[0], ys[1], xr + 0, f"{sp:g} in", FR, ext_from=x_far)
    memberart._dim_v(c, ys[-1], y1, xr, f"{ue:g} in unloaded edge", FR, ext_from=x_far)
    memberart._dim_h(c, x_end, xs[0], y0 - 9, f"{end:g} in" + (" (cut short)" if end_show < end else ""), FR, ext_from=y0)
    if R > 1:
        memberart._dim_h(c, xs[0], xs[1], y0 - 9, f"{g:g} in", FR, ext_from=y0)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    xa = x_end - 26
    _arrow(c, xa, y1 - 4, xa, y0 + 4, head=4)
    c.setFont(FR, 6.5); c.drawRightString(xa - 4, (y0 + y1) / 2 - 2, "load on the bolts")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString((x_end + x_far) / 2, y1 + 4, "grain")
    _small(c, (LM + RM) / 2, y0 - 28, "face of the member loaded perpendicular to grain, to scale")
    return y0 - 34


def _nailed_picture(c, top, d):
    """Section through the connection, to scale: the side member over the main member, one
    nail through both, the load on each member, and the thicknesses, nail length and
    penetration dimensioned."""
    ts, tm, Lg, p, D = d["side_t"], d["main_t"], d["length"], d["p"], d["D"]
    sc = min(26.0, 86.0 / (ts + tm))                      # points per inch
    wd = 150.0
    x0 = (LM + RM) / 2 - wd / 2
    y_top = top - 26
    y_mid = y_top - ts * sc
    y_bot = y_mid - tm * sc
    for (xa, ya, w_, h_, kind) in ((x0 - 22, y_mid, wd, ts * sc, "side"), (x0 + 22, y_bot, wd, tm * sc, "main")):
        c.setFillColorRGB(0.93, 0.87, 0.74); c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.rect(xa, ya, w_, h_, fill=1, stroke=1)
    xn = (LM + RM) / 2
    c.setStrokeColorRGB(0.25, 0.27, 0.3); c.setLineWidth(max(1.0, D * sc)); c.line(xn, y_top, xn, y_top - Lg * sc + D * sc)
    c.setLineWidth(0.8); c.line(xn - 3.5, y_top + 0.8, xn + 3.5, y_top + 0.8)
    t = c.beginPath(); t.moveTo(xn - D * sc / 2, y_top - Lg * sc + D * sc); t.lineTo(xn + D * sc / 2, y_top - Lg * sc + D * sc); t.lineTo(xn, y_top - Lg * sc); t.close()
    c.setFillColorRGB(0.25, 0.27, 0.3); c.drawPath(t, fill=1, stroke=0)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    if d.get("withdrawal"):
        xl = x0 + 8
        _arrow(c, xl, y_top, xl, y_top + 22, head=4); _arrow(c, xl + 44, y_bot, xl + 44, y_bot - 22, head=4)
        c.setFont(FR, 6.5); c.drawString(xl + 5, y_top + 14, "load"); c.drawString(xl + 49, y_bot - 18, "load")
    else:
        _arrow(c, x0 - 22, (y_top + y_mid) / 2, x0 - 50, (y_top + y_mid) / 2, head=4)
        _arrow(c, x0 + 22 + wd, (y_mid + y_bot) / 2, x0 + 50 + wd, (y_mid + y_bot) / 2, head=4)
        c.setFont(FR, 6.5); c.drawRightString(x0 - 54, (y_top + y_mid) / 2 - 2, "load"); c.drawString(x0 + 54 + wd, (y_mid + y_bot) / 2 - 2, "load")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawString(x0 - 18, (y_top + y_mid) / 2 - 2, "side member"); c.drawString(x0 + 26, y_bot + 3, "main member")
    xr = x0 + 22 + wd + 14
    memberart._dim_v(c, y_mid, y_top, xr + 66, f"{ts:g} in", FR, ext_from=x0 + wd - 22)
    memberart._dim_v(c, y_bot, y_mid, xr + 66, f"{tm:g} in", FR, ext_from=xr - 14)
    memberart._dim_v(c, y_top - Lg * sc, y_mid, xn + 24, f"p = {p:.2f} in", FR, ext_from=xn + 2)
    c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawCentredString(xn, y_top + 6, d["label"])
    off = 24 if d.get("withdrawal") else 0
    _small(c, (LM + RM) / 2, y_bot - 12 - off, "section through one wood screw, to scale" if d.get("screw") else "section through one nail, to scale")
    return y_bot - 18 - off


def _lag_picture(c, top, d):
    """Section through one lag screw, to scale: the side member (or plate) over the main member,
    the screw with its head, washer, unthreaded shank, threads and tapered tip; the side member
    thickness, the thread penetration and the tip dimensioned; the load along the screw."""
    D, L, ts, tm, T, E, pt, wash = d["D"], d["L"], d["side_t"], d["main_t"], d["T"], d["E"], d["pt"], d.get("washer") or 0.0
    tmd = min(tm, (L - wash - ts) + max(0.75, D))          # depth of the main member shown, in
    sc = min(26.0, 104.0 / (ts + tmd + wash + 0.5 * D))
    wd = 150.0
    xc = (LM + RM) / 2
    y_top = top - 34 - (wash + 0.5 * D) * sc              # top of the side member
    y_mid = y_top - ts * sc
    y_bot = y_mid - tmd * sc
    x0 = xc - wd / 2
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    if d.get("steel_side"):
        c.setFillColorRGB(0.72, 0.75, 0.80)
    else:
        c.setFillColorRGB(0.93, 0.87, 0.74)
    c.rect(x0, y_mid, wd, max(ts * sc, 1.2), fill=1, stroke=1)
    c.setFillColorRGB(0.93, 0.87, 0.74)
    c.rect(x0, y_bot, wd, tmd * sc, fill=1, stroke=(0 if tmd < tm else 1))
    if tmd < tm:
        c.line(x0, y_mid, x0 + wd, y_mid); c.line(x0, y_mid, x0, y_bot); c.line(x0 + wd, y_mid, x0 + wd, y_bot)
    steel = (0.25, 0.27, 0.3)
    y_head = y_top + wash * sc
    y_tip = y_head - L * sc
    y_thr = y_tip + T * sc                                 # top of the threads
    c.setStrokeColorRGB(*steel); c.setFillColorRGB(*steel)
    if wash:
        c.rect(xc - 1.3 * D * sc, y_top, 2.6 * D * sc, wash * sc, fill=1, stroke=0)
    c.rect(xc - 0.8 * D * sc, y_head, 1.6 * D * sc, 0.5 * D * sc, fill=1, stroke=0)        # head
    c.rect(xc - D * sc / 2, y_thr, D * sc, y_head - y_thr, fill=1, stroke=0)               # shank
    c.setFillColorRGB(0.55, 0.58, 0.62)
    c.rect(xc - D * sc / 2, y_tip + E * sc, D * sc, (T - E) * sc, fill=1, stroke=0)        # threads
    tp = c.beginPath(); tp.moveTo(xc - D * sc / 2, y_tip + E * sc); tp.lineTo(xc + D * sc / 2, y_tip + E * sc); tp.lineTo(xc, y_tip); tp.close()
    c.drawPath(tp, fill=1, stroke=0)
    c.setStrokeColorRGB(*steel); c.setLineWidth(0.4)
    k, pitch = y_tip + E * sc, max(2.0, 0.18 * D * sc * 2)
    while k < y_thr - 0.5:
        c.line(xc - D * sc / 2, k, xc + D * sc / 2, min(k + pitch * 0.6, y_thr)); k += pitch
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    lat = d.get("lateral")
    if lat:
        ys = (y_top + y_mid) / 2
        _arrow(c, x0, ys, x0 - 28, ys, head=4); _arrow(c, x0 + wd, (y_mid + y_bot) / 2, x0 + wd + 28, (y_mid + y_bot) / 2, head=4)
        c.setFont(FR, 6.5); c.drawRightString(x0 - 32, ys - 2, "load"); c.drawString(x0 + wd + 32, (y_mid + y_bot) / 2 - 2, "load")
    else:
        _arrow(c, x0 + 14, y_top, x0 + 14, y_top + 22, head=4); _arrow(c, x0 + wd - 14, y_bot, x0 + wd - 14, y_bot - 20, head=4)
        c.setFont(FR, 6.5); c.drawString(x0 + 19, y_top + 14, "load"); c.drawRightString(x0 + wd - 19, y_bot - 16, "load")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawString(x0 + 4, y_top + 3, "side plate" if d.get("steel_side") else "side member") if lat else \
        c.drawRightString(x0 - 4, (y_top + y_mid) / 2 - 2, "side plate" if d.get("steel_side") else "side member")
    c.drawRightString(x0 + wd - 4, y_bot + 3, "main member")
    y_pt_top = y_tip + E * sc + pt * sc
    memberart._dim_v(c, y_mid, y_top, x0 + wd + (44 if lat else 16), f"{ts:g} in", FR, ext_from=x0 + wd)
    if lat:
        memberart._dim_v(c, y_tip + E * sc, y_mid, xc + D * sc / 2 + 18, f"p = {pt:.2f} in", FR, ext_from=xc + D * sc / 2 + 1)
    else:
        memberart._dim_v(c, y_tip + E * sc, y_pt_top, xc + D * sc / 2 + 18, f"pt = {pt:.2f} in", FR, ext_from=xc + D * sc / 2 + 1)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawRightString(xc - D * sc / 2 - 6, y_tip + E * sc / 2 - 2, f"tapered tip E = {E:.2f} in")
    c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawCentredString(xc, y_head + 0.5 * D * sc + 26, d["label"])
    _small(c, xc, y_bot - (14 if lat else 34), f"section through one lag screw, to scale; threads shaded; main member {tm:g} in thick" + (", not shown full depth" if tmd < tm else ""))
    return y_bot - (20 if lat else 40)


def _toe_nail_picture(c, top, d):
    """Toe-nail (NDS Figure 12A), to scale: the side member standing on the main member, one
    nail at 30 degrees to the side member started L/3 from its end, with L/3, the penetration
    and the member thicknesses dimensioned."""
    ts, tm, Lg, p, D = d["side_t"], d["main_t"], d["length"], d["p"], d["D"]
    hs = max(Lg * 0.75, Lg / 3.0 + 0.6)                   # height of the side member shown, in
    tmd = min(tm, max(p + 0.5, 1.5))                      # depth of the main member shown, in
    sc = min(30.0, 96.0 / (hs + tmd), 120.0 / max(ts, 1.0))
    xc = (LM + RM) / 2
    y_top = top - 24
    y_mid = y_top - hs * sc                               # top of the main member
    y_bot = y_mid - tmd * sc
    xs0, xs1 = xc - ts * sc / 2, xc + ts * sc / 2
    xm0, xm1 = xs0 - 60, xs1 + 60
    c.setFillColorRGB(0.93, 0.87, 0.74); c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.rect(xm0, y_bot, xm1 - xm0, tmd * sc, fill=1, stroke=(0 if tmd < tm else 1))
    if tmd < tm:                                          # main member deeper than shown: open at the bottom
        c.line(xm0, y_mid, xm1, y_mid); c.line(xm0, y_mid, xm0, y_bot); c.line(xm1, y_mid, xm1, y_bot)
    c.rect(xs0, y_mid, ts * sc, hs * sc, fill=1, stroke=0)
    c.line(xs0, y_mid, xs0, y_top); c.line(xs1, y_mid, xs1, y_top); c.line(xs0, y_mid, xs1, y_mid)
    yh = y_mid + Lg / 3.0 * sc                            # nail head, on the face of the side member
    xt, yt = xs1 - Lg * 0.5 * sc, yh - Lg * 0.8660254 * sc
    c.setStrokeColorRGB(0.25, 0.27, 0.3); c.setLineWidth(max(1.0, D * sc)); c.line(xs1, yh, xt, yt)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    if d.get("withdrawal"):
        _arrow(c, xs0 - 10, y_top - 30, xs0 - 10, y_top - 6, head=4); _arrow(c, xm0 + 20, y_bot, xm0 + 20, y_bot - 20, head=4)
        c.setFont(FR, 6.5); c.drawRightString(xs0 - 14, y_top - 14, "load"); c.drawString(xm0 + 25, y_bot - 16, "load")
    else:
        _arrow(c, xs0, y_top - 8, xs0 - 28, y_top - 8, head=4)
        _arrow(c, xm1, (y_mid + y_bot) / 2, xm1 + 28, (y_mid + y_bot) / 2, head=4)
        c.setFont(FR, 6.5); c.drawRightString(xs0 - 32, y_top - 10, "load"); c.drawString(xm1 + 32, (y_mid + y_bot) / 2 - 2, "load")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawRightString(xs0 - 4, y_mid + 12, "side member"); c.drawString(xm0 + 4, y_bot + 3, "main member")
    c.drawString(xs1 + 4, yh + 3, "30 degrees to the side member")
    memberart._dim_v(c, y_mid, yh, xs1 + 22, f"L/3 = {Lg / 3.0:.2f} in", FR, ext_from=xs1 + 2)
    memberart._dim_v(c, yt, y_mid, xs1 + 22, f"p = {p:.2f} in", FR, ext_from=xt + 2)
    memberart._dim_h(c, xs0, xs1, y_top + 8, f"{ts:g} in", FR, ext_from=y_top)
    c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawCentredString(xc, y_top + 22, d["label"])
    off = 24 if d.get("withdrawal") else 0
    _small(c, xc, y_bot - 12 - off, f"section through one toe-nail, to scale; main member {tm:g} in thick" + (", not shown full depth" if tmd < tm else ""))
    return y_bot - 18 - off


def _topo_picture(c, top, d):
    """Section through the hill, ridge or escarpment, schematic (not to scale): the wind from the
    left, the crest, H, Lh (crest back to half height), the site at x from the crest."""
    esc = d["shape"] == "2D escarpment"
    hgt, half = 44.0, 62.0                                # drawn height of the feature; drawn Lh
    xc = (LM + RM) / 2 - (30 if esc else 0)               # crest
    y0 = top - 30 - hgt                                   # upwind ground
    def prof(xx):
        u = (xx - xc) / half
        if esc:
            return y0 + hgt * (0.5 + 0.5 * math.cos(math.pi * min(max(-u / 2.0, 0.0), 1.0)))
        return y0 + hgt / (1.0 + u * u)
    xa, xb = xc - 175, xc + 175
    pth = c.beginPath(); pth.moveTo(xa, y0 - 10)
    n = 140
    pts = [(xa + (xb - xa) * j / n, prof(xa + (xb - xa) * j / n)) for j in range(n + 1)]
    for px, py in pts:
        pth.lineTo(px, py)
    pth.lineTo(xb, y0 - 10); pth.close()
    c.setFillColorRGB(0.93, 0.91, 0.86); c.setStrokeColorRGB(*INK); c.setLineWidth(0.3); c.drawPath(pth, fill=1, stroke=0)
    c.setLineWidth(1.0)
    pth = c.beginPath(); pth.moveTo(*pts[0])
    for px, py in pts[1:]:
        pth.lineTo(px, py)
    c.drawPath(pth, fill=0, stroke=1)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.7)
    _arrow(c, xa + 4, y0 + hgt + 8, xa + 44, y0 + hgt + 8, head=3.5)
    c.setFont(FR, 6.5); c.drawString(xa + 4, y0 + hgt + 12, "wind")
    # site: x from the crest, drawn at a fixed offset on its side
    off = 0.0 if d["x"] == 0 else (48.0 if d["downwind"] else -34.0)
    xs = xc + off
    ys = prof(xs)
    c.setFillColorRGB(0.35, 0.38, 0.42); c.setStrokeColorRGB(*INK); c.setLineWidth(0.5)
    c.rect(xs - 5, ys, 10, 12, fill=1, stroke=1)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString(xs, ys + 15, "site")
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.setDash(2, 2)
    c.line(xc, y0 - 4, xc, y0 + hgt + 20); c.line(xa, y0, xc + (0 if esc else half * 2), y0); c.setDash()
    if off > 0:
        c.drawRightString(xc - 3, y0 + hgt + 22, "crest")
    elif off < 0:
        c.drawString(xc + 3, y0 + hgt + 22, "crest")
    else:
        c.drawCentredString(xc, y0 + hgt + 30, "crest")
    memberart._dim_v(c, y0, y0 + hgt, xb - 26 if esc else xc + half * 2 + 12, f"H {d['H']:g} ft", FR)
    memberart._dim_h(c, xc - half, xc, y0 - 12, f"Lh {d['Lh']:g} ft", FR, ext_from=y0 + hgt / 2)
    if off:
        memberart._dim_h(c, min(xc, xs), max(xc, xs), y0 + hgt + 32, f"x {d['x']:g} ft", FR)
    _small(c, (LM + RM) / 2, y0 - 34, "schematic section, not to scale; Lh is measured upwind from the crest to half the height H")
    return y0 - 40


def _guard_picture(c, top, d):
    """Elevation of three posts and the top rail, schematic: the 200 lb load at mid-span and
    at the top of a post, the uniform load along the rail where it applies, post spacing and
    guard height dimensioned."""
    S, h = d["S"], d["h"]
    sc = min(100.0 / S, 62.0 / h)
    x0 = (LM + RM) / 2 - S * sc
    yb = top - 40 - h * sc
    yt = yb + h * sc
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.6); c.line(x0 - 26, yb, x0 + 2 * S * sc + 26, yb)
    c.setStrokeColorRGB(*INK); c.setLineWidth(2.2)
    for k in range(3):
        c.line(x0 + k * S * sc, yb, x0 + k * S * sc, yt)
    c.setLineWidth(2.6); c.line(x0 - 6, yt, x0 + 2 * S * sc + 6, yt)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.8)
    _arrow_down(c, x0 + S * sc / 2, yt + 17, yt + 3, head=3)
    c.setFont(FR, 6.5); c.drawCentredString(x0 + S * sc / 2, yt + 20, "200 lb, any direction")
    _arrow(c, x0 + S * sc - 22, yt - 6, x0 + S * sc - 3, yt - 6, head=3)
    c.drawRightString(x0 + S * sc - 24, yt - 8, "200 lb")
    if d.get("uniform"):
        xa, xb = x0 + S * sc + 6, x0 + 2 * S * sc - 6
        c.setLineWidth(0.45); c.line(xa, yt + 11, xb, yt + 11)
        n = max(int((xb - xa) / 10), 3)
        for j in range(n + 1):
            _arrow_down(c, xa + (xb - xa) * j / n, yt + 11, yt + 3, head=1.6)
        c.drawCentredString((xa + xb) / 2, yt + 14, "or 50 lb/ft")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawString(x0 + 2 * S * sc + 10, yt - 2, f"top rail {d['rail']}")
    c.drawString(x0 + 2 * S * sc + 10, yb + h * sc / 2, f"posts {d['post']}")
    memberart._dim_h(c, x0, x0 + S * sc, yb - 10, f"S {S:g} ft", FR, ext_from=yb)
    memberart._dim_h(c, x0 + S * sc, x0 + 2 * S * sc, yb - 10, f"{S:g} ft", FR, ext_from=yb)
    memberart._dim_v(c, yb, yt, x0 - 46, f"h {h:g} ft", FR)
    _small(c, (LM + RM) / 2, yb - 28, "elevation, to scale; loads are applied one at a time, in the direction that governs")
    return yb - 34


def _rain_picture(c, top, d):
    """Section through the bay, not to scale: the undeflected roof (dashed), the deflected roof,
    the inlet of the secondary drainage at the edge, and the water over it, with the static,
    hydraulic and ponding heads dimensioned."""
    ds, dh, dp = d["ds"], d["dh"], d.get("dp") or 0.0
    tot = max(ds + dh + dp, 1e-6)
    k = 46.0 / tot                                         # points per inch of water
    x0, x1 = LM + 150, LM + 390
    y_roof = top - 20 - (ds + dh) * k                      # undeflected roof surface
    y_inlet, y_water = y_roof + ds * k, y_roof + (ds + dh) * k
    sag = dp * k
    n = 40
    pts = [(x0 + (x1 - x0) * j / n, y_roof - sag * math.sin(math.pi * j / n)) for j in range(n + 1)]
    pth = c.beginPath(); pth.moveTo(x0, y_water); pth.lineTo(x0, y_roof)
    for x, y in pts:
        pth.lineTo(x, y)
    pth.lineTo(x1, y_water); pth.close()
    c.setFillColorRGB(0.84, 0.91, 0.98); c.drawPath(pth, fill=1, stroke=0)
    c.setStrokeColorRGB(*LOADC); c.setLineWidth(0.7); c.line(x0, y_water, x1, y_water)
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.setDash(3, 2); c.line(x0, y_roof, x1, y_roof); c.setDash()
    c.setStrokeColorRGB(*INK); c.setLineWidth(1.4)
    pth = c.beginPath(); pth.moveTo(*pts[0])
    for x, y in pts[1:]:
        pth.lineTo(x, y)
    c.drawPath(pth, fill=0, stroke=1)
    c.setLineWidth(1.0)                                    # parapet each side; inlet of the secondary drainage on the left
    c.line(x1, y_roof, x1, y_water + 10)
    c.line(x0, y_roof, x0, y_inlet); c.line(x0, y_water + 3, x0, y_water + 10)
    c.line(x0 - 9, y_inlet, x0, y_inlet)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawRightString(x0 - 12, y_inlet - 2, "inlet of the secondary drainage")
    c.drawString(x1 + 6, y_roof - 2, "undeflected roof")
    c.drawString(x1 + 6, y_water - 2, "water surface")
    xm = (x0 + x1) / 2
    if ds * k > 5:
        memberart._dim_v(c, y_roof, y_inlet, x0 + 28, f"ds {ds:.2f}", FR)
    if dh * k > 5:
        memberart._dim_v(c, y_inlet, y_water, x0 + 28, f"dh {dh:.2f}", FR)
    if sag > 5:
        memberart._dim_v(c, y_roof - sag, y_roof, xm, f"dp {dp:.2f}", FR)
    y_b = y_roof - sag - 12
    _small(c, (LM + RM) / 2, y_b, "section through the bay, not to scale; heads in inches"
           + (f"; R = {d['R']:,.1f} psf" if d.get("R") is not None else ""))
    return y_b - 6


def _collector_picture(c, top, d):
    """The line of resistance to scale with its walls drawn heavy, the diaphragm shear along
    it, and the collector force diagram above with the value at each peak; the line length
    and each wall dimensioned."""
    W, segs, pts, Fmax = d["W"], d["segments"], d["points"], d["Fmax"]
    s_ = 320.0 / W
    x0 = (LM + RM) / 2 - 160.0
    h = 34.0                                              # half height of the force diagram
    y_axis = top - 22 - h
    y_line = y_axis - h - 30
    k = (h / Fmax) if Fmax > 0 else 0.0
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.line(x0, y_axis, x0 + W * s_, y_axis)
    pth = c.beginPath(); pth.moveTo(x0, y_axis)
    for x, F in pts:
        pth.lineTo(x0 + x * s_, y_axis + F * k)
    pth.lineTo(x0 + W * s_, y_axis); pth.close()
    c.setFillColorRGB(0.87, 0.91, 0.97); c.setStrokeColorRGB(*LOADC); c.setLineWidth(0.9); c.drawPath(pth, fill=1, stroke=1)
    c.setFillColorRGB(*LOADC); c.setFont(FR, 6.5)
    for x, F in pts:
        if abs(F) > 0.02 * Fmax:
            c.drawCentredString(x0 + x * s_, y_axis + F * k + (4 if F > 0 else -9), f"{abs(F):,.0f} lb")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawRightString(x0 - 6, y_axis - 2, "collector force")
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(x0, y_line, x0 + W * s_, y_line)
    c.setLineWidth(4.0)
    for a, b in segs:
        c.line(x0 + a * s_, y_line, x0 + (a + b) * s_, y_line)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.6)
    n = max(6, int(W * s_ / 26))
    for i in range(n):
        xa = x0 + (i + 0.15) * W * s_ / n
        _arrow(c, xa, y_line + 9, xa + 0.6 * W * s_ / n, y_line + 9, head=3)
    c.setFont(FR, 6.5); c.drawString(x0 + W * s_ + 6, y_line + 7, f"vd = {d['vd']:,.0f} plf")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawRightString(x0 - 6, y_line - 2, "line, walls heavy")
    yd = y_line - 10
    edges = sorted({0.0, W} | {a for a, b in segs} | {a + b for a, b in segs})
    for a, b in zip(edges[:-1], edges[1:]):
        if (b - a) * s_ > 16:
            memberart._dim_h(c, x0 + a * s_, x0 + b * s_, yd, f"{b - a:g} ft", FR, ext_from=y_line)
    memberart._dim_h(c, x0, x0 + W * s_, yd - 14, f"{W:g} ft", FR, ext_from=yd)
    _small(c, (LM + RM) / 2, yd - 30, f"line of resistance to scale; walls take vw = {d['vw']:,.0f} plf; forces above and below the axis are of opposite sense")
    return yd - 36


def _diaphragm_picture(c, top, d):
    """Plan of the diaphragm to scale: the uniform load along one long edge, the reaction and
    unit shear at each line of resistance, the chords with their force, L and W dimensioned."""
    L, W = d["L"], d["W"]
    s = min(300.0 / L, 80.0 / W)
    w_, h_ = L * s, W * s
    x0 = (LM + RM) / 2 - w_ / 2
    y1 = top - 34
    y0 = y1 - h_
    x1 = x0 + w_
    c.setFillColorRGB(0.96, 0.97, 0.99); c.setStrokeColorRGB(*INK); c.setLineWidth(0.6); c.rect(x0, y0, w_, h_, fill=1, stroke=1)
    c.setLineWidth(1.8); c.line(x0, y0, x1, y0); c.line(x0, y1, x1, y1)                     # chords
    c.setStrokeColorRGB(*GREY); c.setLineWidth(2.4); c.line(x0, y0 - 3, x0, y1 + 3); c.line(x1, y0 - 3, x1, y1 + 3)   # lines of resistance
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.6)
    n = max(6, int(w_ / 16))
    for k in range(n + 1):
        _arrow_down(c, x0 + w_ * k / n, y1 + 16, y1 + 3)
    c.line(x0, y1 + 16, x1, y1 + 16)
    c.setFont(FR, 6.5); c.drawCentredString((x0 + x1) / 2, y1 + 19, f"w = {d['w']:,.0f} plf")
    for x, al in ((x0, "right"), (x1, "left")):
        _arrow(c, x + (-7 if al == "right" else 7), y0 + h_ * 0.35, x + (-7 if al == "right" else 7), y0 + h_ * 0.65, head=3.5)
        t = [f"R = {d['R']:,.0f} lb", f"v = {d['v']:,.0f} plf"]
        for j, tt in enumerate(t):
            (c.drawRightString if al == "right" else c.drawString)(x + (-12 if al == "right" else 12), y0 + h_ * 0.55 - j * 8, tt)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    c.drawCentredString((x0 + x1) / 2, y1 - 9, f"chord, C = {d['T']:,.0f} lb")
    c.drawCentredString((x0 + x1) / 2, y0 + 4, f"chord, T = {d['T']:,.0f} lb")
    memberart._dim_h(c, x0, x1, y0 - 10, f"L = {L:g} ft", FR, ext_from=y0)
    memberart._dim_v(c, y0, y1, x1 + 62, f"W = {W:g} ft", FR, ext_from=x1 + 4)
    _small(c, (LM + RM) / 2, y0 - 28, "plan, to scale; heavy lines at the ends are the lines of resistance")
    return y0 - 34


def _seismic_forces_picture(c, top, d):
    """Elevation of the building as a stack of levels, heights to scale: the force at each
    level as an arrow with its value, the story shear beside each story, the base shear."""
    rows = d["rows"]
    H = 104.0
    sc = H / d["hn"]
    xl = (LM + RM) / 2 - 60
    xr = xl + 120
    yb = top - 20 - H
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.line(xl - 90, yb, xr + 110, yb)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    ytop = yb + rows[0]["h"] * sc
    c.line(xl, yb, xl, ytop); c.line(xr, yb, xr, ytop)
    fmax = max(r["F"] for r in rows) or 1.0
    prev = None
    for r in rows:
        y = yb + r["h"] * sc
        c.setStrokeColorRGB(*INK); c.setLineWidth(1.4); c.line(xl, y, xr, y)
        c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
        ln = 18 + 44 * r["F"] / fmax
        _arrow(c, xl - 4 - ln, y, xl - 4, y, head=4)
        c.setFont(FR, 6.5); c.drawRightString(xl - 8 - ln, y - 2, f"{r['name']}: {r['F']:.2f} {d['unit']}")
        c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawString(xr + 6, y - 2, f"{r['h']:g} ft")
        prev = y
    ys = [yb + r["h"] * sc for r in rows] + [yb]
    for r, ya, yb_ in zip(rows, ys[:-1], ys[1:]):
        if ya - yb_ >= 8:
            c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawCentredString((xl + xr) / 2, (ya + yb_) / 2 - 2, f"V = {r['V']:.2f} {d['unit']}")
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow(c, xr + 60, yb - 7, xr + 20, yb - 7, head=4)
    c.setFont(FR, 6.5); c.drawString(xr + 64, yb - 9, f"base shear {d['V']:.2f} {d['unit']}")
    _small(c, (LM + RM) / 2, yb - 22, "elevation; heights to scale")
    return yb - 28


def _wind_zones_picture(c, top, d):
    """Key plan of the component and cladding zones, not to scale, with the zone widths
    dimensioned. d["kind"]: "wall" (elevation), "flat" (Figure 30.3-2A), "ridge" (2B, 2C) or
    "corner" (2D)."""
    kind = d["kind"]
    W, H = (230.0, 70.0) if kind == "wall" else (170.0, 116.0)
    x0 = (LM + RM) / 2 - W / 2
    y1 = top - 22
    y0 = y1 - H
    x1 = x0 + W

    def tag(x, y, t):
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*INK); c.setLineWidth(0.5); c.circle(x, y, 5.2, fill=1, stroke=1)
        c.setFillColorRGB(*INK); c.setFont(FB, 6.5); c.drawCentredString(x, y - 2.2, t)

    def dash(xa, ya, xb, yb):
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.setDash(3, 2); c.line(xa, ya, xb, yb); c.setDash()

    c.setStrokeColorRGB(*INK); c.setLineWidth(1.0); c.setFillColorRGB(0.96, 0.97, 0.99)
    c.rect(x0, y0, W, H, fill=1, stroke=1)
    if kind == "wall":
        a = 30.0
        dash(x0 + a, y0, x0 + a, y1); dash(x1 - a, y0, x1 - a, y1)
        tag(x0 + a / 2, (y0 + y1) / 2, "5"); tag(x1 - a / 2, (y0 + y1) / 2, "5"); tag((x0 + x1) / 2, (y0 + y1) / 2, "4")
        memberart._dim_h(c, x0, x0 + a, y0 - 9, f"a = {d['a']:.1f} ft", FR, ext_from=y0)
        memberart._dim_h(c, x1 - a, x1, y0 - 9, f"a = {d['a']:.1f} ft", FR, ext_from=y0)
        note = "wall elevation; zone 5 at each corner of the building, zone 4 between; not to scale"
    elif kind == "flat":
        e, k = 20.0, 8.0
        for n in (1, 2):
            c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.setDash(3, 2)
            c.rect(x0 + n * e, y0 + n * e, W - 2 * n * e, H - 2 * n * e, fill=0, stroke=1); c.setDash()
        for cx, sx in ((x0, 1), (x1, -1)):
            for cy, sy in ((y0, 1), (y1, -1)):
                dash(cx + sx * e, cy + sy * k, cx + sx * k, cy + sy * k); dash(cx + sx * k, cy + sy * k, cx + sx * k, cy + sy * e)
                tag(cx + sx * 4, cy + sy * 4, "3")
        tag((x0 + x1) / 2, (y0 + y1) / 2, "1'"); tag((x0 + x1) / 2, y1 - 1.5 * e, "1"); tag((x0 + x1) / 2, y1 - 0.5 * e, "2")
        tag(x0 + 0.5 * e, (y0 + y1) / 2, "2"); tag(x0 + 1.5 * e, (y0 + y1) / 2, "1")
        memberart._dim_h(c, x0, x0 + e, y0 - 9, "", FR, ext_from=y0)
        memberart._dim_h(c, x0 + e, x0 + 2 * e, y0 - 9, "", FR, ext_from=y0)
        c.setFillColorRGB(*INK); c.setFont(FR, 6)
        c.drawString(x0 + 2 * e + 4, y0 - 11, f"0.6h = {d['edge']:.1f} ft each")
        memberart._dim_v(c, y1 - k, y1, x1 + 9, f"0.2h = {d['corner']:.1f} ft", FR, ext_from=x1)
        memberart._dim_v(c, y0, y0 + e, x1 + 9, f"0.6h = {d['edge']:.1f} ft", FR, ext_from=x1)
        note = "roof plan; not to scale"
    elif kind == "hip":
        a = 12.0
        run = H / 2.0                                         # hips drawn at 45 degrees in plan
        xa, xb, ym = x0 + run, x1 - run, (y0 + y1) / 2
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
        c.line(xa, ym, xb, ym)
        for (cx, cy, rx) in ((x0, y0, xa), (x0, y1, xa), (x1, y0, xb), (x1, y1, xb)):
            c.line(cx, cy, rx, ym)
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.setDash(3, 2); c.rect(x0 + a, y0 + a, W - 2 * a, H - 2 * a, fill=0, stroke=1); c.setDash()
        tag((x0 + x1) / 2, y0 + a / 2, "3"); tag((x0 + x1) / 2, y1 - a / 2, "3"); tag(x0 + a / 2, ym, "3"); tag(x1 - a / 2, ym, "3")
        tag((xa + xb) / 2 - 16, ym, "2"); tag((x0 + a + xa) / 2 + 4, (y0 + a + ym) / 2 + 4, "2"); tag((x1 - a + xb) / 2 - 4, (y1 - a + ym) / 2 - 4, "2")
        tag((x0 + x1) / 2, (y0 + a + ym) / 2 - 2, "1"); tag((x0 + x1) / 2, (y1 - a + ym) / 2 + 2, "1"); tag(x0 + a + (run - a) / 2 - 2, ym, "1"); tag(x1 - a - (run - a) / 2 + 2, ym, "1")
        memberart._dim_h(c, x0, x0 + a, y0 - 9, f"a = {d['a']:.1f} ft", FR, ext_from=y0)
        memberart._dim_v(c, y1 - a, y1, x1 + 9, f"a = {d['a']:.1f} ft", FR, ext_from=x1)
        note = "roof plan; not to scale; zone 2 also runs the width a each side of the ridge and of each hip"
    elif kind in ("mono_a", "mono_b"):
        a = 13.0
        A5 = kind == "mono_a"
        t = 2 * a if A5 else a                               # depth of the strips along the sloping edges
        dash(x0 + 2 * a, y0, x0 + 2 * a, y1)                  # high eave strip, 2a wide
        dash(x0, y0 + 4 * a, x0 + 2 * a, y0 + 4 * a); dash(x0, y1 - 4 * a, x0 + 2 * a, y1 - 4 * a)
        dash(x0 + 2 * a, y0 + t, x1 - a, y0 + t); dash(x0 + 2 * a, y1 - t, x1 - a, y1 - t)
        dash(x1 - a, y0 + t, x1 - a, y1 - t)
        hi3, hi2 = ("3'", "2'") if A5 else ("3", "2")
        tag(x0 + a, y0 + 2 * a, hi3); tag(x0 + a, y1 - 2 * a, hi3); tag(x0 + a, (y0 + y1) / 2, hi2)
        tag(x1 - a / 2, (y0 + y1) / 2, "2"); tag((x0 + 2 * a + x1 - a) / 2, (y0 + y1) / 2, "1")
        if A5:
            dash(x1 - 2 * a, y0, x1 - 2 * a, y0 + t); dash(x1 - 2 * a, y1 - t, x1 - 2 * a, y1)
            tag(x1 - a, y0 + a, "3"); tag(x1 - a, y1 - a, "3")
            tag((x0 + 2 * a + x1 - 2 * a) / 2, y0 + a, "2'"); tag((x0 + 2 * a + x1 - 2 * a) / 2, y1 - a, "2'")
            memberart._dim_h(c, x1 - 2 * a, x1, y1 + 8, "", FR, ext_from=y1)
            c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawString(x1 + 4, y1 + 6, f"2a = {2 * d['a']:.1f} ft")
        else:
            tag((x0 + 2 * a + x1) / 2, y0 + a / 2, "2"); tag((x0 + 2 * a + x1) / 2, y1 - a / 2, "2")
        memberart._dim_h(c, x0, x0 + 2 * a, y1 + 8, "", FR, ext_from=y1)
        c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawRightString(x0 - 4, y1 + 6, f"2a = {2 * d['a']:.1f} ft")
        memberart._dim_v(c, y0, y0 + t, x1 + 9, f"{'2a' if A5 else 'a'} = {(2 if A5 else 1) * d['a']:.1f} ft", FR, ext_from=x1)
        memberart._dim_h(c, x1 - a, x1, y0 - 9, f"a = {d['a']:.1f} ft", FR, ext_from=y0)
        c.setFillColorRGB(*GREY); c.setFont(FR, 6)
        c.drawRightString(x0 - 5, (y0 + y1) / 2 - 2, "high eave"); c.drawString(x1 + 5, (y0 + y1) / 2 - 2, "low eave")
        c.saveState(); c.translate(x0 - 5, y0 + 2 * a); c.rotate(90); c.drawCentredString(0, 0, f"4a = {4 * d['a']:.1f} ft"); c.restoreState()
        note = "roof plan; not to scale"
    else:
        a = 18.0
        xm = (x0 + x1) / 2
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.9); c.line(xm, y0, xm, y1)
        dash(x0, y0 + a, x1, y0 + a); dash(x0, y1 - a, x1, y1 - a)
        if kind == "ridge":
            dash(xm - a, y0, xm - a, y1); dash(xm + a, y0, xm + a, y1)
            for yy in (y0 + a / 2, y1 - a / 2):
                tag(xm - a / 2, yy, "3"); tag(xm + a / 2, yy, "3"); tag(x0 + (W / 2 - a) / 2, yy, "2"); tag(x1 - (W / 2 - a) / 2, yy, "2")
            tag(xm - a / 2, (y0 + y1) / 2, "2"); tag(xm + a / 2, (y0 + y1) / 2, "2")
            tag(x0 + (W / 2 - a) / 2, (y0 + y1) / 2, "1"); tag(x1 - (W / 2 - a) / 2, (y0 + y1) / 2, "1")
            memberart._dim_h(c, xm - a, xm, y1 + 8, "", FR, ext_from=y1); memberart._dim_h(c, xm, xm + a, y1 + 8, "", FR, ext_from=y1)
            c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawString(xm + a + 4, y1 + 6, f"a = {d['a']:.1f} ft each side of the ridge")
        else:
            for cx, sx in ((x0, 1), (x1, -1)):
                for cy, sy in ((y0, 1), (y1, -1)):
                    dash(cx + sx * a, cy, cx + sx * a, cy + sy * a); tag(cx + sx * a / 2, cy + sy * a / 2, "3")
            for yy in (y0 + a / 2, y1 - a / 2):
                tag(x0 + W / 4 + a / 2, yy, "2"); tag(x1 - W / 4 - a / 2, yy, "2")
            tag(x0 + W / 4, (y0 + y1) / 2, "1"); tag(x1 - W / 4, (y0 + y1) / 2, "1")
            memberart._dim_h(c, x0, x0 + a, y1 + 8, "", FR, ext_from=y1)
            c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawString(x0 + a + 4, y1 + 6, f"a = {d['a']:.1f} ft")
        memberart._dim_v(c, y0, y0 + a, x1 + 9, f"a = {d['a']:.1f} ft", FR, ext_from=x1)
        c.setFillColorRGB(*GREY); c.setFont(FR, 6)
        c.drawCentredString(xm, y0 - 8, "ridge"); c.drawRightString(x0 - 5, (y0 + y1) / 2 - 2, "eave"); c.drawString(x1 + 5, (y0 + y1) / 2 - 2, "eave")
        c.drawCentredString(x0 + W / 4, y0 - 8, "gable end")
        note = "roof plan; not to scale"
    _small(c, (LM + RM) / 2, y0 - 26, note)
    return y0 - 32


def _snow_drift_picture(c, top, d):
    """Section through the roof step: the wall of the upper roof, the lower roof, the
    balanced snow, and one panel for each drift (and one for sliding snow), with the
    surcharge and its width dimensioned. Vertical and horizontal scales differ."""
    panels = [("drift", x) for x in d["drifts"]] + ([("sliding", d["sliding"])] if d["sliding"] else [])
    if not panels:
        panels = [("none", None)]
    pw = (RM - LM - 20) / max(len(panels), 2)
    shown = min(d["lu"], max([x["w"] for k, x in panels if k == "drift"] + [x["ext"] for k, x in panels if k == "sliding"] + [10.0]) * 1.25)
    sx = (pw - 84) / shown                                  # points per ft, horizontal
    sy = 58.0 / max(d["step"], d["hb"] * 2, 1.0)            # points per ft, vertical
    ybase = top - 96
    for i, (kind, x) in enumerate(panels):
        x0 = LM + 10 + i * pw
        title = {"drift": ((x or {}).get("kind", "").upper() + " DRIFT").strip(), "sliding": "SLIDING SNOW", "none": "BALANCED"}[kind]
        _sketch_title(c, x0, top - 4, title)
        wx = x0 + 34                                        # face of the upper wall
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
        gx = 14 if d.get("gap") else 0                      # adjacent structures: the higher wall stands back by the gap (not to scale)
        c.line(wx - gx, ybase - (10 if gx else 0), wx - gx, ybase + d["step"] * sy); c.line(wx - gx - 18, ybase + d["step"] * sy, wx - gx, ybase + d["step"] * sy)
        c.line(wx, ybase, wx + shown * sx, ybase)
        if gx:
            c.line(wx, ybase, wx, ybase - 10)
            c.setFillColorRGB(*GREY); c.setFont(FR, 5.5); c.drawCentredString(wx - gx / 2, ybase - 17, f"gap {d['gap']:g} ft")
        c.setFillColorRGB(0.90, 0.93, 0.97); c.setStrokeColorRGB(*LOADC); c.setLineWidth(0.5)
        hb = d["hb"] * sy
        c.rect(wx, ybase, shown * sx, hb, fill=1, stroke=1)
        c.setFillColorRGB(0.78, 0.85, 0.94)
        if kind == "drift":
            w_, h_ = min(x["w"], shown) * sx, x["h"] * sy
            far = h_ * (x["far"] / x["pd"]) if x["pd"] else 0.0
            p_ = c.beginPath(); p_.moveTo(wx, ybase + hb); p_.lineTo(wx, ybase + hb + h_); p_.lineTo(wx + w_, ybase + hb + far)
            p_.lineTo(wx + w_, ybase + hb); p_.close(); c.drawPath(p_, fill=1, stroke=1)
            c.setFillColorRGB(*LOADC); c.setFont(FR, 6)
            c.drawString(wx + 4, ybase + hb + h_ + 3, f"{x['pd']:.1f} psf surcharge, {x['h']:.2f} ft")
            memberart._dim_h(c, wx, wx + w_, ybase - 9, f"{x['w']:.1f} ft", FR, ext_from=ybase)
        elif kind == "sliding":
            w_ = min(x["ext"], shown) * sx
            c.rect(wx, ybase + hb, w_, 9, fill=1, stroke=1)
            c.setFillColorRGB(*LOADC); c.setFont(FR, 6); c.drawString(wx + 4, ybase + hb + 12, f"{x['psf']:.1f} psf surcharge")
            memberart._dim_h(c, wx, wx + w_, ybase - 9, f"{x['ext']:g} ft", FR, ext_from=ybase)
        c.setFillColorRGB(*GREY); c.setFont(FR, 6)
        c.drawString(wx + shown * sx - 46, ybase + 2, f"balanced {d['ps']:g} psf")
        memberart._dim_v(c, ybase, ybase + d["step"] * sy, wx - 24 - (10 if d.get("gap") else 0), f"{d['step']:g} ft", FR, ext_from=wx - 18 - (14 if d.get("gap") else 0))
    _small(c, (LM + RM) / 2, ybase - 32, "sections through the roof step; not to scale")
    return ybase - 38


def _perforated_wall_picture(c, top, d):
    """Elevation of a perforated shear wall to scale: sheathing, openings, the full-height
    segment lengths, opening widths, the height, the shear and the chord forces."""
    Lw, h = d["L"], d["h"]
    sc = min((RM - LM - 130) / Lw, 84.0 / h)
    _sketch_title(c, LM + 6, top - 4, "ELEVATION")
    x0, y0 = LM + 50, top - 36 - h * sc
    W, H = Lw * sc, h * sc
    c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setFillColorRGB(*memberart.WOOD_FILL)
    c.rect(x0, y0, W, H, fill=1, stroke=1)
    c.setFillColorRGB(1, 1, 1); c.setLineWidth(0.6)
    for o in d["openings"]:
        c.rect(x0 + o["x"] * sc, y0 + o["sill"] * sc, o["w"] * sc, o["h"] * sc, fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.8)
    c.line(x0 + 2, y0 + H + 6, x0 + W - 2, y0 + H + 6); c.line(x0 + W - 2, y0 + H + 6, x0 + W - 6, y0 + H + 8)
    c.line(x0 + W - 2, y0 + H + 6, x0 + W - 6, y0 + H + 4)
    c.setFont(FR, 6.5); c.drawCentredString(x0 + W / 2, y0 + H + 10, f"V = {d['V']:,.0f} lb")
    marks = [0.0]
    for o in sorted(d["openings"], key=lambda o: o["x"]):
        marks += [o["x"], o["x"] + o["w"]]
    marks.append(Lw)
    for a, b in zip(marks[:-1], marks[1:]):
        if b - a > 1e-6:
            memberart._dim_h(c, x0 + a * sc, x0 + b * sc, y0 - 9, f"{b - a:g}" if (b - a) * sc < 24 else f"{b - a:g} ft", FR, ext_from=y0)
    memberart._dim_h(c, x0, x0 + W, y0 - 21, f"{Lw:g} ft", FR, ext_from=y0 - 9)
    memberart._dim_v(c, y0, y0 + H, x0 + W + 8, f"{h:g} ft", FR, ext_from=x0 + W)
    c.setFont(FR, 6); c.setFillColorRGB(*GREY)
    c.drawRightString(x0 - 4, y0 + 2, f"T {d['T']:,.0f}"); c.drawString(x0 + W + 4, y0 - 6, f"C {d['T']:,.0f}")
    _small(c, (LM + RM) / 2, y0 - 41, "to scale; openings shown white; chord forces in lb")
    return y0 - 47


def _shear_wall_picture(c, top, d):
    """Elevation of the wall line: each full-height segment as a sheathed panel with its
    length, shear and chord forces. Segments are drawn side by side with a gap; lengths and
    height are to one scale."""
    segs = d["segs"]
    total = sum(s["b"] for s in segs)
    gap = 26.0
    sc = min((RM - LM - 120 - gap * (len(segs) - 1)) / total, 78.0 / d["h"])
    _sketch_title(c, LM + 6, top - 4, "ELEVATION")
    y0 = top - 34 - d["h"] * sc
    x = LM + 46
    for i, s in enumerate(segs, 1):
        w, hh = s["b"] * sc, d["h"] * sc
        c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setFillColorRGB(*memberart.WOOD_FILL)
        c.rect(x, y0, w, hh, fill=1, stroke=1)
        c.setLineWidth(0.3)
        n = max(int(s["b"] / 1.3333 + 0.5), 1)                # studs at 16 in. for the look of framing
        for k in range(1, n):
            c.line(x + w * k / n, y0, x + w * k / n, y0 + hh)
        c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
        c.drawCentredString(x + w / 2, y0 + hh + 9, f"{s['V']:,.0f} lb  ({s['v']:.0f} plf)")
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
        c.line(x + 2, y0 + hh + 5, x + w - 2, y0 + hh + 5); c.line(x + w - 2, y0 + hh + 5, x + w - 6, y0 + hh + 7)
        c.line(x + w - 2, y0 + hh + 5, x + w - 6, y0 + hh + 3)
        c.setFont(FR, 6); c.setFillColorRGB(*GREY)
        c.drawCentredString(x, y0 - 22, f"T {s['T']:,.0f}"); c.drawCentredString(x + w, y0 - 22, f"C {s.get('C', s['T']):,.0f}")
        memberart._dim_h(c, x, x + w, y0 - 9, f"{s['b']:g} ft", FR, ext_from=y0)
        x += w + gap
    memberart._dim_v(c, y0, y0 + d["h"] * sc, x - gap + 8, f"{d['h']:g} ft", FR, ext_from=x - gap)
    _small(c, (LM + RM) / 2, y0 - 32, "segments drawn to scale, side by side; chord forces in lb; framing lines are schematic")
    return y0 - 38


def _snow_picture(c, top, d):
    """Balanced and unbalanced snow on the roof profile, loads drawn to one scale."""
    gable = d["roof"] == "gable"
    u = d["unb"]
    panels = [("BALANCED", None)] + ([("UNBALANCED", u)] if u else [])
    peak_load = max([d["balanced"]] + ([u["leeward"] + u.get("surcharge", 0)] if u else [])) or 1.0
    k = 34.0 / peak_load                                   # points per psf
    wpan = 200.0
    span = 2 * d["W"] if gable else d["W"]
    sx = 170.0 / span
    rise_pt = min(d["rise"] / 12.0 * d["W"] * sx, 30.0)
    low = top
    for n, (title, ub) in enumerate(panels):
        x0 = LM + 14 + n * (wpan + 62)
        _sketch_title(c, x0, top - 4, title)
        base = top - 22 - 40 - 8 - rise_pt                 # eave line
        x1 = x0 + span * sx
        xr = x0 + d["W"] * sx if gable else x1             # ridge or upper edge
        c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(1.4)
        if gable:
            c.line(x0, base, xr, base + rise_pt); c.line(xr, base + rise_pt, x1, base)
        else:
            c.line(x0, base, x1, base + rise_pt)
        datum = base + rise_pt + 8                         # loads are drawn on the horizontal projection
        c.setLineWidth(0.5); c.setStrokeColorRGB(0.45, 0.50, 0.56); c.line(x0, datum, x1, datum)

        def block(xa, xb, y0, psf, label, above=True):
            if psf <= 0:
                return
            c.setFillColorRGB(0.82, 0.88, 0.95); c.setStrokeColorRGB(0.13, 0.21, 0.32); c.setLineWidth(0.6)
            c.rect(xa, y0, xb - xa, psf * k, fill=1, stroke=1)
            c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
            c.drawCentredString((xa + xb) / 2, y0 + psf * k + 2.5 if above else y0 + psf * k / 2 - 2, label)

        if ub is None:
            block(x0, x1, datum, d["balanced"], f"{d['balanced']:.1f} psf")
        else:
            block(x0, xr, datum, ub["windward"], f"{ub['windward']:.1f} psf")
            block(xr, x1, datum, ub["leeward"], f"{ub['leeward']:.1f} psf", above=not ub.get("surcharge"))
            if ub.get("surcharge"):
                xe = xr + ub["extent"] * sx
                block(xr, xe, datum + ub["leeward"] * k, ub["surcharge"], f"+ {ub['surcharge']:.1f} psf")
                memberart._dim_h(c, xr, xe, base - 9, f"{ub['extent']:.1f} ft", FR, ext_from=datum)
            c.setFillColorRGB(*GREY); c.setFont(FR, 6)
            c.drawString(x0, datum + 38, "wind")
            c.setStrokeColorRGB(*GREY); c.setLineWidth(0.6); c.line(x0 + 16, datum + 40, x0 + 34, datum + 40)
            c.line(x0 + 34, datum + 40, x0 + 30, datum + 42); c.line(x0 + 34, datum + 40, x0 + 30, datum + 38)
        yb = base - (22 if (ub and ub.get("surcharge")) else 9)
        if gable:
            memberart._dim_h(c, x0, xr, yb, f"W = {d['W']:g} ft", FR, ext_from=base)
            memberart._dim_h(c, xr, x1, yb, f"{d['W']:g} ft", FR, ext_from=base)
        else:
            memberart._dim_h(c, x0, x1, yb, f"W = {d['W']:g} ft", FR, ext_from=base)
        low = min(low, yb - 12)
    _small(c, (LM + RM) / 2, low - 2, "loads in psf on the horizontal projection, drawn to one scale")
    return low - 8


def simple_pdf(sheet, path, job, code, date, page=1, pages=None):
    return _paged(_simple_pdf, sheet, path, job, code, date, page, pages)
