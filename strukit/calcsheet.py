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
        avail = RM - (tx + max(c.stringWidth(FIRM, FB, 10.5), c.stringWidth(SEP.join(x for x in CONTACT if x), FR, 8.25)) + 14)
        line2 = [_date(date), f"Sheet {self.page + self.used - 1} of {self.pages}"]
        rest = [x for x in rest if x]
        fit = lambda nm, rs: c.stringWidth(nm, FB, 8.25) + c.stringWidth((SEP if nm and rs else "") + SEP.join(rs), FR, 8.25) <= avail
        while rest and not fit(name, rest):                  # a long heading: the site, then the job number, move to the second line
            line2.insert(0, rest.pop())
        while line2 and c.stringWidth(SEP.join(line2), FR, 8.25) > avail and len(line2) > 2:
            line2.pop(0)
        while name and not fit(name, rest):
            name = name[:-2].rstrip(" ,") + "\u2026" if len(name) > 4 else ""
            name = name.replace("\u2026\u2026", "\u2026")
        tail = SEP.join(rest)
        if name and tail:
            tail = SEP + tail
        w_tail = c.stringWidth(tail, FR, 8.25)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25); c.drawRightString(RM, TOP - 12.5, tail)
        if name:
            c.setFillColorRGB(*INK); c.setFont(FB, 8.25); c.drawRightString(RM - w_tail, TOP - 12.5, name)
        c.setFillColorRGB(*GREY); c.setFont(FR, 8.25)
        c.drawRightString(RM, TOP - 24.9, SEP.join(line2))
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
        rows = list(rows)
        kw = max([kw] + [c.stringWidth(str(k), FR, 8.5) + 6 for k, _ in rows])      # the value column starts clear of the longest label
        for k, v in rows:
            c.setFont(FR, 8.5); c.setFillColorRGB(*GREY); c.drawString(x, yy, k)
            c.setFillColorRGB(*INK)
            v = str(v)
            for t in ([v] if c.stringWidth(v, FR, 8.5) <= RM - x - kw else _wrapw(v, FR, 8.5, RM - x - kw)):     # a value never passes the right margin
                c.drawString(x + kw, yy, t)
                yy -= 11.5
        if y is None:
            self.y = yy
        return yy

    def text(self, s, font=FR, size=8.5, color=INK, x=LM, dy=11.5):
        """One line of text; a line too wide for the sheet continues on the next line(s) inside the right margin."""
        s = str(s)
        if self.c.stringWidth(s, font, size) > RM - x + 0.5:
            parts = _table_line(s, RM - x, font, size) if font == FM else _wrapw(s, font, size, RM - x)
        else:
            parts = [s]
        for t in parts:
            self.c.setFont(font, size); self.c.setFillColorRGB(*color)
            self.c.drawString(x, self.y, t)
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
        notes = _wrapw(ln.note, FR, 7.5, RM - LM - 26) if ln.note else []
        need = 10.0 + 8.5 * len(notes)
        if p.y - need < 64:
            close()
            p.room(1000)
            p.head(title + ", Continued")
            box_top = p.y + 9
        val = ln.value if isinstance(ln.value, str) else f"{ln.value:.2f}" if not ln.unit else _fmt(ln.value, ln.unit)
        c.setFont(FM, 8); c.setFillColorRGB(*INK)
        left = f"{ln.label} = {val}"
        room = RM - LM - 12
        if c.stringWidth(left, FM, 8) > room:                      # a long line continues below, inside the box
            for t in _table_line(left, room, FM, 8)[:-1]:
                c.drawString(LM + 6, p.y, t); p.y -= 9.5
            left = _table_line(left, room, FM, 8)[-1]
        c.drawString(LM + 6, p.y, left)
        c.setFont(FR, 7.5); c.setFillColorRGB(*GREY)
        if c.stringWidth(left, FM, 8) + c.stringWidth(ln.source or "", FR, 7.5) + 10 > room:     # the reference goes on its own line when the two would meet
            p.y -= 8.5
        c.drawRightString(RM - 6, p.y, ln.source)
        for t in notes:
            p.y -= 8.5
            c.drawString(LM + 18, p.y, t)
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


def _wrapw(text, font, size, width):
    """Break text into lines no wider than width (points) in the given font, at spaces; a single word wider than the column is cut."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    out, line = [], ""
    for word in str(text or "").split(" "):
        while stringWidth(word, font, size) > width:
            n = len(word)
            while n > 1 and stringWidth(word[:n], font, size) > width:
                n -= 1
            if line:
                out.append(line); line = ""
            out.append(word[:n]); word = word[n:]
        trial = (line + " " + word) if line else word
        if stringWidth(trial, font, size) <= width:
            line = trial
        else:
            out.append(line); line = word
    return out + ([line] if line else []) or [""]


def _table_line(t, width, font=None, size=7.5):
    """A row of a monospace table that is wider than the sheet is continued on the next line(s), indented to where its last column
    starts, so nothing runs past the margin and nothing is cut off."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    font = font or FM
    n = int(width / stringWidth("0", font, size))
    if len(t) <= n:
        return [t]
    k = t.rfind("  ", 0, n - 12)
    ind = k + 2 if k > 0 else 4
    while ind < len(t) and t[ind] == " ":
        ind += 1
    ind = min(ind, n - 24)
    out, rest, first = [], t, True
    while rest:
        room = n if first else n - ind
        if len(rest) <= room:
            cut = len(rest)
        else:
            cut = rest.rfind(" ", 0, room + 1)
            cut = cut if cut > (ind if first else 0) else room
        out.append(rest[:cut].rstrip() if first else " " * ind + rest[:cut].strip())
        rest, first = rest[cut:].strip(), False
    return out


def _summary(p, rows):
    """Check summary table: demand, capacity, D/C and result for every check, the code
    reference under each, and a boxed FLAG line for every check that fails. The check name and the combination wrap inside their own
    columns, so a long combination name never runs under the numbers."""
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
    from reportlab.pdfbase.pdfmetrics import stringWidth
    for r in rows:
        flag = r.status == "FLAG"
        sub = _split(r.source, 132) + (_split(r.note, 132) if r.note else [])
        dem = _fmt(r.demand, r.unit)
        names = _wrapw(r.check[0].upper() + r.check[1:], FR, 8.5, 142)
        combos = _wrapw(r.combo, FM, 8, 318 - stringWidth(dem, FM, 8) - 8 - 150) if r.combo else []
        top = 9.5 * (max(len(names), len(combos), 1) - 1)
        hgt = 16 + top + 8.5 * len(sub)
        p.room(hgt - 8)
        if flag:
            c.setFillColorRGB(0.99, 0.95, 0.91); c.rect(LM, p.y - hgt + 11, RM - LM, hgt, fill=1, stroke=0)
            flags.append(r)
        c.setFillColorRGB(*INK); c.setFont(FR, 8.5)
        for i, t in enumerate(names):
            c.drawString(LM, p.y - 9.5 * i, t)
        c.setFont(FM, 8)
        for i, t in enumerate(combos):
            c.drawString(LM + 150, p.y - 9.5 * i, t)
        c.drawRightString(LM + 318, p.y, dem)
        c.drawRightString(LM + 392, p.y, _fmt(r.capacity, r.unit))
        c.drawRightString(LM + 430, p.y, f"{r.dc:.2f}")
        c.setFont(FB, 8.5); c.setFillColorRGB(*(FLAGC if flag else OKC))
        c.drawString(LM + 446, p.y, r.status)
        c.setFont(FR, 7.5); c.setFillColorRGB(*GREY)
        for i, t in enumerate(sub):
            c.drawString(LM + 8, p.y - top - 9.5 - 8.5 * i, t)
        c.setStrokeColorRGB(*RULE); c.setLineWidth(0.4)
        c.line(LM, p.y - hgt + 11, RM, p.y - hgt + 11)
        p.y -= hgt
    if flags:
        p.y -= 5
    for r in flags:
        text = (f"FLAG - {r.check[0].upper() + r.check[1:]}: {_fmt(r.demand, r.unit)} exceeds {_fmt(r.capacity, r.unit)}"
                + (f" ({r.combo})" if r.combo else ""))
        lines = _wrapw(text, FB, 8.5, RM - LM - 12)
        bh = 8 + 10.5 * len(lines)
        p.room(bh - 6)
        c.setStrokeColorRGB(*FLAGC); c.setLineWidth(1); c.rect(LM, p.y - bh + 12, RM - LM, bh, fill=0, stroke=1)
        c.setFillColorRGB(*FLAGC); c.setFont(FB, 8.5)
        for i, t in enumerate(lines):
            c.drawString(LM + 6, p.y - 10.5 * i, t)
        p.y -= bh + 3
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


def _bu_view(pr):
    """A built-up section's properties rounded for printing (4 significant figures) and its plate rows."""
    q = {k: (float(f"{v:.4g}") if isinstance(v, float) else v) for k, v in pr.items()}
    f = lambda x: (str(int(x)) if abs(x - round(x)) < 1e-9 else
                   (f"{int(x)}-{_frac(x - int(x))}" if x > 1 else _frac(x)))
    plates = [("Plates", f"top flange PL {f(pr['bft'])} x {f(pr['tft'])}, web PL {f(pr['h'])} x {f(pr['tw'])}"),
              ("", f"bottom flange PL {f(pr['bfb'])} x {f(pr['tfb'])}, welded")]
    return q, plates


def _frac(x):
    from fractions import Fraction
    fr = Fraction(x).limit_denominator(16)
    return f"{fr.numerator}/{fr.denominator}"


def _steel_beam_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
    """Write the calc sheet for a ws_steel_beam.SteelBeamSheet. `combos` are the Combo
    objects that were run, printed with their sources."""
    p = _Page(path, getattr(sheet, "heading", None) or f"Beam {sheet.mark} - Steel Bending Member", job, code, sheet.method,
              page, pages, date)
    c, pr = p.c, sheet.props

    # member data (left) and loading sketch (right)
    top = p.y
    hss_kind = {"HSS-RECT": "rect", "HSS-ROUND": "round", "PIPE": "round"}.get(pr.get("type"))
    depth_in = pr["d"] if hss_kind is None else (pr["OD"] if hss_kind == "round" else pr["Ht"])
    p.head("Member")
    bu = pr.get("type") == "BU"
    if bu:
        pr, plates = _bu_view(pr)
    p.kv([("Section", f"{pr['label'] if bu else sheet.shape}  (Fy = {sheet.Fy:g} ksi)"),
          ("Span", getattr(sheet, "span_text", None) or f"{sheet.span_ft:g} ft, simply supported"),
          ("Bracing", sheet.bracing_text),
          ] + (plates if bu else []) + ([("Dimensions", f"d = {pr['d']:g} in, bf = {pr['bf']:g} in"),
                ("", f"tf = {pr['tf']:g} in, tw = {pr['tw']:g} in"),
                ("Properties", f"Zx = {pr['Zx']:g} in3, Sx = {pr['Sx']:g} in3"),
                ("", f"Ix = {pr['Ix']:g} in4, ry = {pr['ry']:g} in"),
                ("", (f"rts = {pr['rts']:g} in, " if pr.get("rts") else "") + f"J = {pr['J']:g} in4, ho = {pr['ho']:g} in")] if hss_kind is None else
               [("Dimensions", (f"OD = {pr['OD']:g} in" if hss_kind == "round" else f"H = {pr['Ht']:g} in, B = {pr['B']:g} in") + f", design t = {pr['tdes']:g} in"),
                ("Properties", f"Zx = {pr['Zx']:g} in3, Sx = {pr['Sx']:g} in3"),
                ("", f"Ix = {pr['Ix']:g} in4, ry = {pr['ry']:g} in, J = {pr['J']:g} in4")]) + [
          ("Source", pr.get("source") or "AISC Shapes Database v16.0")])
    bottom_left = p.y
    x0, w = 338, 166
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8); c.drawString(x0, top - 4, "LOADING SKETCH")
    by = top - 64                                    # underside of the beam
    stair = getattr(sheet, "stair", None)
    if stair:
        by = _stair_sketch(c, x0, top, w, sheet, stair)
    else:
        hb, true_scale = memberart.elev_depth(sheet.span_ft * 12, depth_in, w)
        memberart.steel_elevation(c, x0, by, w, hb, depth_in, pr["tf"] if hss_kind is None else max(pr["tdes"], depth_in * 0.06))
        sp_ = sheet.props
        if bu and (sp_.get("stiff") or sp_.get("brg")):               # transverse and bearing stiffeners seen from the side, between the flanges
            tfp = max(hb * pr["tf"] / depth_in, 1.5)
            L_in = sheet.span_ft * 12.0
            px = lambda xin: x0 + w * xin / L_in
            st_ = sp_.get("stiff")
            from .ws_steel_beam import _faces
            sups_ = list(getattr(sheet, "supports", None) or (0.0, sheet.span_ft))
            fcs = _faces(sups_, sheet.span_ft)
            xs_ = []
            if st_:
                for s0, dr, lim, _ in fcs:
                    acc = 0.0
                    for a_ in (st_["panels"] or []) if st_.get("panels") else [st_["a"]] * 400:
                        acc += a_
                        if acc >= lim * 12.0 - 1e-6:
                            break
                        xs_.append(s0 * 12.0 + dr * acc)
            c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.35); c.setFillColorRGB(0.62, 0.67, 0.73)
            for xin in xs_:
                c.rect(px(xin) - 0.5, by + tfp, 1.0, hb - 2 * tfp, fill=1, stroke=1)
            if sp_.get("brg") and sp_["brg"].get("ts"):
                for s0 in sups_:
                    xin = s0 * 12.0
                    xx = px(xin)
                    off = 0.3 if xin <= 1e-6 else (-2.1 if abs(xin - L_in) <= 1e-6 else -0.9)
                    c.rect(xx + off, by + tfp, 1.8, hb - 2 * tfp, fill=1, stroke=1)
                if sp_["brg"].get("at_loads"):
                    for ld in sheet.loads:
                        if ld.get("kind") == "point" and not str(ld.get("dir") or "").startswith("side"):
                            c.rect(px(ld["x_ft"] * 12.0) - 0.9, by + tfp, 1.8, hb - 2 * tfp, fill=1, stroke=1)
        c.setStrokeColorRGB(*BLUE); c.setFillColorRGB(0.91, 0.93, 0.96); c.setLineWidth(0.6)
        down = [ld for ld in sheet.loads if not str(ld.get("dir") or "").startswith("side")]
        side = [ld for ld in sheet.loads if str(ld.get("dir") or "").startswith("side")]
        if any(ld["kind"] == "uniform" for ld in down):
            c.rect(x0, by + hb + 4, w, 10, fill=1, stroke=1)
        c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.9)
        sup_x = [x0 + 3 + (w - 6) * v / sheet.span_ft for v in getattr(sheet, "supports", None) or (0.0, sheet.span_ft)]
        for xx in sup_x:
            t = c.beginPath(); t.moveTo(xx, by - 1); t.lineTo(xx - 6, by - 12); t.lineTo(xx + 6, by - 12); t.close()
            c.drawPath(t, fill=0, stroke=1)
        for ld in down:
            if ld["kind"] == "point":
                xx = x0 + w * ld["x_ft"] / sheet.span_ft
                c.line(xx, by + hb + 30, xx, by + hb + 7)
                t = c.beginPath(); t.moveTo(xx, by + hb + 1); t.lineTo(xx - 3, by + hb + 8); t.lineTo(xx + 3, by + hb + 8); t.close()
                c.drawPath(t, fill=1, stroke=0)
        c.setFillColorRGB(*GREY); c.setFont(FM, 7.5)
        if getattr(sheet, "supports", None):
            c.setFont(FM, 6.5)
            marks = [x0 + 3] + sup_x + [x0 + w - 3]
            vals = [0.0] + list(sheet.supports) + [sheet.span_ft]
            for (xa_, xb_), (va_, vb_) in zip(zip(marks[:-1], marks[1:]), zip(vals[:-1], vals[1:])):
                if vb_ - va_ > 1e-6:
                    c.drawCentredString((xa_ + xb_) / 2, by - 22, f"{vb_ - va_:g} ft")
        else:
            c.drawCentredString(x0 + w / 2, by - 22, f"L = {sheet.span_ft:g} ft")
        if not true_scale:
            c.setFont(FR, 6); c.drawCentredString(x0 + w / 2, by - 30, "side view: depth enlarged for clarity")
        uni = [f"{ld['case']} {ld['w']:.3f}" for ld in down if ld["kind"] == "uniform"]
        if side:                                         # sideways loads act in the plane of the flanges: listed under the beam, not drawn down
            stxt = [f"{ld['case']} {ld['w']:.3f} kip/ft" if ld["kind"] == "uniform" else f"{ld['case']} {ld['P']:.2f} kip at {ld['x_ft']:g} ft" for ld in side]
            c.setFillColorRGB(*BLUE); c.setFont(FM, 6.5)
            c.drawCentredString(x0 + w / 2, by - 40, "sideways, y axis: " + " + ".join(stxt))
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
    if hss_kind is None:
        if pr.get("type") == "BU":
            memberart.steel_section(c, sx, top - 38, 40, 46, pr["d"], pr["bft"], pr["tft"], pr["tw"], None, pr["bfb"], pr["tfb"])
            wd_ = (sheet.props or {}).get("weld")
            if wd_:                                              # the flange-to-web fillets, both sides at each flange
                k_ = min(40.0 / max(pr["bft"], pr["bfb"]), 46.0 / pr["d"])
                ws_ = max(2.2, wd_["w"] * k_)
                tw2 = pr["tw"] * k_ / 2
                yt_, yb_ = top - 38 + pr["d"] * k_ / 2 - pr["tft"] * k_, top - 38 - pr["d"] * k_ / 2 + pr["tfb"] * k_
                c.setFillColorRGB(0.20, 0.22, 0.25)
                for yy, sg in ((yt_, -1), (yb_, 1)):
                    for sx_ in (-1, 1):
                        t_ = c.beginPath(); t_.moveTo(sx + sx_ * tw2, yy); t_.lineTo(sx + sx_ * (tw2 + ws_), yy); t_.lineTo(sx + sx_ * tw2, yy + sg * ws_); t_.close()
                        c.drawPath(t_, fill=1, stroke=0)
        else:
            (memberart.channel_section if pr.get("type") in ("C", "MC") else memberart.steel_section)(
                c, sx, top - 38, 40, 46, pr["d"], pr["bf"], pr["tf"], pr["tw"], pr.get("kdes"))
        c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString(sx, top - 72, "to scale")
    else:
        _hss_section(c, sx - 6, top - 36, 40.0, dict(kind=hss_kind, OD=pr.get("OD"), H=pr.get("Ht"), B=pr.get("B"), t=pr["tdes"]))
    c.setStrokeColorRGB(*INK)
    p.y = min(bottom_left, by - (46 if any(str(ld.get("dir") or "").startswith("side") for ld in sheet.loads) else 34)) - 2

    p.head("Loads")
    for ld in sheet.loads:
        if ld["kind"] == "uniform":
            s = f"{ld['case']:<3} uniform  {ld['w']:.3f} kip/ft"
            if "x1_ft" in ld:
                s += f"  from {ld['x1_ft']:g} to {ld['x2_ft']:g} ft"
        else:
            s = f"{ld['case']:<3} point    {ld['P']:.2f} kip at {ld['x_ft']:g} ft"
        if ld.get("e_in"):
            s += f", {ld['e_in']:g} in. off the shear center"
        if ld.get("label"):
            s += f"   ({ld['label']})"
        p.text(s, font=FM, size=8)
    p.y -= 2
    p.head("Load Combinations")
    for cb in combos:
        p.text(f"{cb.name:<18} reactions " + " / ".join(f"{v:.2f}" for v in sheet.reactions[cb.name]) + " kip" + (f"; moment at the support {sheet.support_moment[cb.name]:.2f} kip-ft" if getattr(sheet, "support_moment", {}).get(cb.name) is not None else ""), font=FM, size=8, dy=10)
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

    _steps(p, "Flexural, Shear and Torsional Strength (AISC 360-22)" if getattr(sheet, "torsion_lines", None) else "Flexural and Shear Strength (AISC 360-22)",
           list(sheet.steps) + list(getattr(sheet, "torsion_lines", None) or []))
    _summary(p, sheet.rows)
    return _closing(p, sheet.assumptions)


def _sketch_title(c, x, top, text, centred=False):
    c.setFillColorRGB(*BLUE); c.setFont(FB, 8)
    (c.drawCentredString if centred else c.drawString)(x, top - 4, text)


def _small(c, x, y, text, size=6):
    """A caption centred on x. One too wide to stay inside the margins at that centre is broken into lines that do."""
    c.setFillColorRGB(*GREY); c.setFont(FR, size)
    room = 2 * min(x - LM, RM - x)
    lines = [text] if c.stringWidth(text, FR, size) <= room else _wrapw(text, FR, size, room)
    for i, t in enumerate(lines):
        c.drawCentredString(x, y - (size + 1.5) * i, t)


def _steel_column_pdf(sheet, path, job, code, date, page=1, pages=1, combos=()):
    """Write the calc sheet for a ws_steel_column.SteelColumnSheet."""
    kind = ("Cantilevered Steel Column" if sheet.sway else
            "Steel Column with Lateral Load" if sheet.lateral else "Steel Compression Member")
    p = _Page(path, f"Column {sheet.mark} - {kind}", job, code, sheet.method,
              page, pages, date)
    c, pr = p.c, sheet.props
    top = p.y
    hss_kind = {"HSS-RECT": "rect", "HSS-ROUND": "round", "PIPE": "round"}.get(pr.get("type"))
    depth_in = pr["d"] if hss_kind is None else (pr["OD"] if hss_kind == "round" else pr["Ht"])
    p.head("Member")
    bu = pr.get("type") == "BU"
    if bu:
        pr, plates = _bu_view(pr)
    p.kv([("Section", f"{pr['label'] if bu else sheet.shape}  (Fy = {sheet.Fy:g} ksi)"),
          *(plates if bu else []),
          ("Height", f"{sheet.height_ft:g} ft"),
          ("Unbraced Length", f"x axis {sheet.Lx_ft:g} ft, y axis {sheet.Ly_ft:g} ft"),
          ("Effective Length", f"Kx = {sheet.Kx:g}, Ky = {sheet.Ky:g}  ({sheet.k_source})"),
          ("Ends", ("fixed base; top free to move for bending about " + " and ".join(sheet.sway))
           if sheet.sway else "held against sideways movement top and bottom"),
          *([("Dimensions", f"d = {pr['d']:g} in, bf = {pr['bf']:g} in"), ("", f"tf = {pr['tf']:g} in, tw = {pr['tw']:g} in")] if hss_kind is None else
            [("Dimensions", (f"OD = {pr['OD']:g} in" if hss_kind == "round" else f"H = {pr['Ht']:g} in, B = {pr['B']:g} in") + f", design t = {pr['tdes']:g} in")]),
          ("Properties", f"A = {pr['A']:g} in2, rx = {pr['rx']:g} in, ry = {pr['ry']:g} in"),
          ("", f"Ix = {pr['Ix']:g} in4, Iy = {pr['Iy']:g} in4, Zx = {pr['Zx']:g} in3, Zy = {pr['Zy']:g} in3"),
          ("Source", pr.get("source") or "AISC Shapes Database v16.0")])
    bottom_left = p.y
    # column standing up, with its load and supports
    ex, eh = 440, 62
    ey = top - 88
    _sketch_title(c, ex, top, "LOADING", centred=True)
    braces = [sheet.Ly_ft * 12 * k for k in range(1, 50) if sheet.Ly_ft * k < sheet.height_ft - 1e-6]
    w = memberart.steel_column_elevation(c, ex, ey, eh, depth_in, pr["tf"] if hss_kind is None else max(pr["tdes"], depth_in * 0.06), sheet.height_ft * 12, braces)
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
    if hss_kind is None:
        if pr.get("type") == "BU":
            memberart.steel_section(c, sx, top - 44, 46, 50, pr["d"], pr["bft"], pr["tft"], pr["tw"], None, pr["bfb"], pr["tfb"])
        else:
            memberart.steel_section(c, sx, top - 44, 46, 50, pr["d"], pr["bf"], pr["tf"], pr["tw"], pr.get("kdes"))
    else:
        _hss_section(c, sx - 4, top - 40, 40.0, dict(kind=hss_kind, OD=pr.get("OD"), H=pr.get("Ht"), B=pr.get("B"), t=pr["tdes"]))
    if hss_kind is None:
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


def _footing_shape(name):
    """The drawing data of a steel column named on the footing screen (HSS, pipe or W), or None."""
    from . import shapes
    if not (name or "").strip():
        return None
    try:
        h = shapes.hss(name)
        return dict(kind="hss", t=h["tdes"], round=h.get("type") != "HSS-RECT", label=shapes.normalize(name))
    except Exception:
        pass
    try:
        w = shapes.get(name)
        return dict(kind="w", d=w["d"], bf=w["bf"], tf=w["tf"], tw=w["tw"], k=w.get("kdes"), label=shapes.normalize(name))
    except Exception:
        return None


def _callout(c, x_tip, y_tip, x_txt, y_txt, text):
    """A note with a leader to the part it names (text left-aligned at x_txt)."""
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.35)
    c.line(x_tip, y_tip, x_txt - 2, y_txt + 2); c.circle(x_tip, y_tip, 0.7, fill=1, stroke=0)
    c.setFillColorRGB(*INK); c.setFont(FR, 6); c.drawString(x_txt, y_txt, text)


def _footing_picture(p, sheet):
    """Footing section (and plan, isolated), to scale and dimensioned, as built: soil, concrete, bars and the member it carries."""
    i = sheet.inp
    iso = sheet.kind == "isolated"
    c = p.c
    D = footing.BAR_DIA
    shp = _footing_shape(getattr(sheet, "col_shape", "")) if iso and sheet.supported == "steel" else None
    p.room(178)
    p.head("Section" + (" and Plan" if iso else ""))
    top = p.y
    ytop = top - 24                                                     # room for the load label above the member
    if iso:
        cx, bw = LM + 140, 196
        low = i.get("bottom_layer", "x")
        n_dots = i["n_y"] if low == "x" else i["n_x"]
        alng = "y" if low == "y" else "x"                                     # cut along the lowest bars: they show full length
        W_in = (i["L_ft"] if alng == "y" else i["B_ft"]) * 12
        sw, kind = (i["col_y_in"] if alng == "y" else i["col_x_in"]), sheet.supported
        if shp and shp["kind"] == "w":                                       # depth along x in the plan: cut along y, the flange is seen
            shp = dict(shp, flange_face=alng == "y")
        sc_, g = memberart.footing_detail(c, cx, None, bw, 112, W_in, i["h_in"], sw, kind, i["cover_in"], D[i["bar"]], n_dots, D[i["bar"]],
                                          plate_w_in=(i.get("plate_y_in") if alng == "y" else i.get("plate_x_in")), soil_depth_in=i.get("soil_depth_ft", 0) * 12, shape=shp, top_y=ytop)
        lab = f"{i['P_service']:,.0f} lb service"
        Wtxt = f"{W_in / 12:g} ft ({alng})"
        oth = "x" if alng == "y" else "y"
        cl = [(g["x1"] - g["cov"] - 6, g["yb"], f"({i['n_' + alng]}) #{i['bar']} in {alng}, lowest; {i['cover_in']:g} in clear cover"),
              (g["dots"][-1] if g["dots"] else g["x1"] - 8, g["yd"] + 2, f"({i['n_' + oth]}) #{i['bar']} in {oth}")]
        what = (shp["label"] if shp else ("wood post" if kind == "wood" else "concrete pier" if kind == "concrete" else "steel column"))
        cl.append(((g["sup_l"] + g["sup_r"]) / 2 + 1, g["sup_top"] - 8, what + (f" on {i['plate_x_in']:g} x {i['plate_y_in']:g} in plate" if i.get("plate_x_in") else "")))
    else:
        cx, bw = LM + 160, 240
        stem = i.get("stem_h_in", 0) or 0.0
        sc_, g = memberart.footing_detail(c, cx, None, bw, 112, i["W_ft"] * 12, i["h_in"], i["wall_in"], i.get("wall_kind", "concrete"), i["cover_in"],
                                          D[i["bar_t"]], i["n_l"], D[i["bar_l"]], stem_h_in=stem, soil_depth_in=i.get("soil_depth_ft", 0) * 12, top_y=ytop)
        lab = f"{i['P_service_plf']:,.0f} lb/ft service"
        Wtxt = f"{i['W_ft']:g} ft"
        cl = [(g["x1"] - g["cov"] - 6, g["yb"], f"#{i['bar_t']} at {i['spacing_t_in']:g} in across, lowest"),
              (g["dots"][-1] if g["dots"] else g["x1"] - 8, g["yd"] + 2, f"({i['n_l']}) #{i['bar_l']} lengthwise; {i['cover_in']:g} in clear cover"),
              ((g["sup_l"] + g["sup_r"]) / 2 + 1, g["sup_top"] - 8, f"{i['wall_in']:g} in {i.get('wall_kind', 'concrete')} wall" + (f", {stem:g} in high" if stem else ""))]
    base = g["y0"]
    # load down the member and soil pressure under the footing (not to a force scale)
    xm = (g["sup_l"] + g["sup_r"]) / 2
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow_down(c, xm, g["sup_top"] + 14, g["sup_top"] + 2)
    c.setFont(FR, 6); c.drawCentredString(xm, g["sup_top"] + 16.5, lab)
    c.setLineWidth(0.5)
    for k in range(7):
        xx = g["x0"] + (k + 0.5) * (g["x1"] - g["x0"]) / 7
        _arrow(c, xx, g["ylo"] + 1, xx, base - 1.2, head=2.2)
    # dimensions
    xl = g["soil_l"] - 8                                                # thickness and soil depth on the left, notes on the right
    memberart._dim_h(c, g["x0"], g["x1"], g["ylo"] - 7, Wtxt, FR, ext_from=base)
    memberart._dim_v(c, base, g["top"], xl, f"{i['h_in']:g} in", FR, ext_from=g["x0"])
    if i.get("soil_depth_ft"):
        memberart._dim_v(c, g["top"], g["gy"], xl, f"{i['soil_depth_ft']:g} ft soil", FR, ext_from=g["soil_l"])
    xr = g["soil_r"]
    # notes with leaders, to the right of the dimensions
    xt = xr + 16
    ys = [base + 4, base + 16, g["sup_top"] - 6]
    for (xt_, yt_, txt), yy in zip(cl, ys):
        _callout(c, xt_, yt_, xt, yy, txt)
    _small(c, cx, g["ylo"] - 22, "section, to scale; load and soil pressure arrows are not to a force scale")
    low_y = g["ylo"] - 24
    if iso:
        pcx, pcy, box = RM - 70, top - 62, 104
        s2, px0, py0, px1, py1 = memberart.footing_detail_plan(c, pcx, pcy, box, i["B_ft"] * 12, i["L_ft"] * 12, i["col_x_in"], i["col_y_in"],
                                                               i["n_x"], i["n_y"], i["cover_in"], sheet.supported, i.get("plate_x_in"), i.get("plate_y_in"), shp)
        memberart._dim_h(c, px0, px1, py0 - 8, f"{i['B_ft']:g} ft (x)", FR, ext_from=py0)
        memberart._dim_v(c, py0, py1, px0 - 8, f"{i['L_ft']:g} ft (y)", FR, ext_from=px0)
        _small(c, pcx, py0 - 26, "plan, to scale; bars dashed below the top")
        low_y = min(low_y, py0 - 28)
    p.y = low_y - 10



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

    p.y = bottom_left
    _footing_picture(p, sheet)

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


def _frame_member_shape(name):
    """Drawing data for a frame member's section: kind, depth, flange or wall thickness."""
    from . import shapes
    try:
        h = shapes.hss(name)
        return dict(kind="hss", d=h.get("OD") or h["Ht"], t=h["tdes"], round=h.get("type") != "HSS-RECT")
    except Exception:
        pass
    try:
        w = shapes.get(name)
        return dict(kind="w", d=w["d"], tf=w["tf"])
    except Exception:
        return None


def _knockout(c, x, y, text, size, left=False, color=None, font=None):
    """Text on a white ground so it reads where it crosses a drawn line (left: text starts at x; else centred)."""
    f_ = font or FR
    wd = c.stringWidth(text, f_, size)
    xl = x if left else x - wd / 2
    c.setFillColorRGB(1, 1, 1); c.rect(xl - 1, y - 1.5, wd + 2, size + 1.5, fill=1, stroke=0)
    c.setFillColorRGB(*(color or GREY)); c.setFont(f_, size); c.drawString(xl, y, text)


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
            sh_ = _frame_member_shape(m.shape)                 # drawn as what it is: a W with its flanges, an HSS with its corner lines
            if sh_ and sh_["kind"] == "hss":
                memberart.hss_elevation(c, 0, -band / 2, L, band, max(band * sh_["t"] / sh_["d"], 0.5), rnd=sh_["round"], vertical=False)
            else:
                memberart.w_side(c, 0, -band / 2, L, band, max(band * (sh_["tf"] / sh_["d"] if sh_ else 0.08), 0.8), vertical=False)
        c.restoreState()
        if labels:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if m.role == "column":
                _knockout(c, mx + band / 2 + 2, my - 2.5, m.name, 5.5, left=True)
            elif L < 34:                                    # a short member (a ridge piece): its name above, clear of the columns
                _knockout(c, mx, max(y1, y2) + band / 2 + 3, m.name, 5.5)
            else:
                _knockout(c, mx, my - band / 2 - 7.5, m.name, 5.5)
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
    merged, order = {}, []                                 # loads on the same members the same way share one row of arrows
    for ld in loads:
        if ld.get("auto"):
            continue
        if "on" in ld:
            key = (tuple(lay.names(ld["on"])), ld.get("dir", "gravity"), ld.get("kind"))
            if key not in merged:
                merged[key] = dict(ld, parts=[]); order.append(merged[key])
            merged[key]["parts"].append(f"{ld['case']} {ld['w']:g}")
        else:
            order.append(ld)
    for ld in order:
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
                txt = " + ".join(ld["parts"]) + " k/ft"
                c.setFont(FR, 5.5); c.drawRightString(lx, ly, txt); c.setFillColorRGB(*LOADC)
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
    placed, texts = [], []
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
        texts.append((lx, ly, f"{abs(M[i]):.0f}"))
    for lx, ly, t_ in texts:                               # values last, on a white ground, so no diagram line runs through them
        _knockout(c, lx, ly, t_, 6, color=col, font=FM)
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
    p.room(215)
    p.y -= 4
    p.head("Elevation and Loads")
    ytop = p.y
    hh = 128
    xs_ = [q[0] for q in lay.nodes.values()]; ys_ = [q[1] for q in lay.nodes.values()]
    sc_ = min(270 / (max(xs_) - min(xs_) or 1.0), hh / (max(ys_) - min(ys_) or 1.0))
    hh = sc_ * (max(ys_) - min(ys_))                       # top of the frame just under the load rows
    xy_, _s = _draw_frame(c, lay, LM + 120, ytop - 30 - hh, 270, hh + 0.01, band=5.0)
    _frame_loads(c, lay, xy_, sheet.loads)
    ylow = min(xy_(n)[1] for n in lay.supports) - 12
    _small(c, (LM + RM) / 2, ylow - 4, "frame to scale; member depth and load arrows not to scale; loads in kips and kip/ft, "
           "cases on the same members added on one row of arrows")
    p.y = ylow - 18

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

    p.room(146)
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
    """Cover sheet of a calc package: the job, the basis of design,
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
    p.y -= 4                                         # no seal box: the engineer's own cover sheet carries the seal (Zach, 2026-11-25 16:06)
    p.head("Basis of Design")
    for t in cover["basis"]:
        for k, ln in enumerate(_split(t, 118)):
            p.room(12); p.text(("- " if k == 0 else "  ") + ln, size=8, dy=10.5)
    for title, rows_ in (("ASD Load Combinations", cover["asd"]), ("LRFD Load Combinations", cover["lrfd"])):
        if not rows_:
            continue
        p.y -= 2; p.room(40); p.head(title)
        for expr, src in rows_:
            words, lines_, cur_ = src.split(), [], ""                 # the source wraps inside the right margin
            for w_ in words:
                t_ = (cur_ + " " + w_).strip()
                if cur_ and c.stringWidth(t_, FR, 7.5) > RM - LM - 200:
                    lines_.append(cur_); cur_ = w_
                else:
                    cur_ = t_
            lines_.append(cur_)
            p.room(12 + 9 * (len(lines_) - 1))
            c.setFont(FM, 8); c.setFillColorRGB(*INK); c.drawString(LM, p.y, expr)
            c.setFont(FR, 7.5); c.setFillColorRGB(*GREY)
            for k_, ln_ in enumerate(lines_):
                c.drawString(LM + 200, p.y - 9 * k_, ln_)
            p.y -= 10.5 + 9 * (len(lines_) - 1)
    p.y -= 2; p.room(50); p.head("Contents")
    def header():
        c.setFont(FB, 7.5); c.setFillColorRGB(*GREY)
        for x, t in ((LM, "Mark"), (LM + 110, "Member"), (LM + 268, "Code"), (LM + 430, "Sheet"), (LM + 466, "Result")):
            c.drawString(x, p.y, t)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.line(LM, p.y - 3, RM, p.y - 3)
        p.y -= 13
    header()
    for it in cover["contents"]:
        if p.y - 12 < 64:
            p.room(1000); p.head("Contents, Continued"); header()
        ok = it["flags"] == 0
        c.setFont(FR, 8.5); c.setFillColorRGB(*INK)
        fit = lambda t_, w_: t_ if c.stringWidth(t_, FR, 8.5) <= w_ else next(t_[:k] + "..." for k in range(len(t_), 0, -1) if c.stringWidth(t_[:k] + "...", FR, 8.5) <= w_)
        c.drawString(LM, p.y, fit(it["mark"], 104)); c.drawString(LM + 110, p.y, fit(it["title"], 152)); c.drawString(LM + 268, p.y, fit(it["code"], 156))
        c.setFont(FM, 8); c.drawString(LM + 430, p.y, str(it["sheet"]))
        c.setFont(FB, 8.5); c.setFillColorRGB(*(OKC if ok else FLAGC))
        c.drawString(LM + 466, p.y, "OK" if ok else f"{it['flags']} FLAG" + ("S" if it["flags"] > 1 else ""))
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
        _sketch_title(c, 495, top, "SECTION")
        s_ = memberart.wood_section(c, 518, top - 50, 46, 46, d["b"], d["d"], d.get("plies", 1), kind=d.get("kind", "sawn"))
        memberart._dim_h(c, 518 - d["b"] * s_ / 2, 518 + d["b"] * s_ / 2, top - 50 - d["d"] * s_ / 2 - 8, f"{d['b']:g}", FR,
                         ext_from=top - 50 - d["d"] * s_ / 2)
        memberart._dim_v(c, top - 50 - d["d"] * s_ / 2, top - 50 + d["d"] * s_ / 2, 518 + d["b"] * s_ / 2 + 7, f"{d['d']:g}", FR,
                         ext_from=518 + d["b"] * s_ / 2)
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
        cx, cy = 530, top - 46
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
        s_ = memberart.wood_section(c, 527, top - 46, 44, 60, d["b"], d["d"], d["plies"], kind=d.get("kind", "sawn"))
        memberart._dim_h(c, 527 - d["b"] * s_ / 2, 527 + d["b"] * s_ / 2, top - 46 - d["d"] * s_ / 2 - 8, f"{d['b']:g}", FR,
                         ext_from=top - 46 - d["d"] * s_ / 2)
        memberart._dim_v(c, top - 46 - d["d"] * s_ / 2, top - 46 + d["d"] * s_ / 2, 527 + d["b"] * s_ / 2 + 7, f"{d['d']:g}", FR,
                         ext_from=527 + d["b"] * s_ / 2)
        _small(c, 476, min(top - 98, y - 34), d.get("caption") or ("section to scale, dimensions in inches" + ("; loads in plf and lb" if lh else "")))
        return min(top - 102, y - 38)
    if name == "base_plate":
        _sketch_title(c, 470, top, "PLAN", centred=True)
        memberart.base_plate_plan(c, 470, top - 52, 170, 82, d["d"], d["bf"], d["tf"], d["tw"], d["N"], d["B"],
                                  d["support"], font=FR, kind=d.get("kind", "I"))
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
        if d.get("kind", "I") == "I":
            c.saveState(); c.translate(cx, cy); c.rotate(90)
            memberart.steel_section(c, 0, 0, d["bf"] * s, d["d"] * s, d["d"], d["bf"], d["tf"], d["tw"])
            c.restoreState()
        else:                                             # HSS cut above the plate, depth along the moment (page width)
            memberart.hss_plan(c, cx, cy, d["d"] * s, d["bf"] * s, max(d["tf"] * s, 1.2), rnd=d.get("kind") == "round", inside=(0.87, 0.90, 0.93))
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
        x0 = 474
        _sketch_title(c, x0, top, "SECTION")
        s2 = 70 / N
        px, py, tp = x0 + 4, top - 52, max(d["t"] * s2, 2.0)
        memberart._concrete(c, px - 4, py - 22, N * s2 + 8, 22)
        c.setLineWidth(0.6); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(*memberart.STEEL_FILL)
        c.rect(px, py, N * s2, tp, fill=1, stroke=1)
        cw = d["d"] * s2
        if d.get("kind", "I") == "I":                       # W column cut through the web: the flanges at each side
            memberart.w_side(c, px + N * s2 / 2 - cw / 2, py + tp, cw, 22, d["tf"] * s2)
        else:                                               # HSS cut through its middle: the two walls
            memberart.hss_cut_side(c, px + N * s2 / 2 - cw / 2, py + tp, cw, 22, d["tf"] * s2)
        _break_h(c, px + N * s2 / 2 - cw / 2, px + N * s2 / 2 + cw / 2, py + tp + 22, amp=2.0)
        for sx in (0, 1):                                   # rods, with a nut and washer on the plate
            rx = px + (d["edge"] if sx == 0 else N - d["edge"]) * s2
            c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(1.1); c.line(rx, py - 16, rx, py + tp + 5)
            c.setFillColorRGB(0.20, 0.22, 0.25); c.rect(rx - 2.6, py + tp, 5.2, 2.2, fill=1, stroke=0)
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
            c.setFont(FM, 6); c.drawString(px - 2, py + tp + 26, f"T = {d['T']:.1f} k")
        _small(c, 476, top - 104, f"dimensions in inches; section shows the bearing block and rod tension for {d['case']}")
        return top - 124
    if name == "footing_moment":
        _sketch_title(c, 470, top, "SECTION AND SOIL PRESSURE", centred=True)
        base = top - 74
        shp_ = _footing_shape(d.get("shape")) if d["supported"] == "steel" else None
        s, _g = memberart.footing_detail(c, 470, base, 150, 52, d["B"], d["h"], d["col"], d["supported"], d["cover"],
                                         d["db"], d["n"], d["db"], plate_w_in=d["plate"], soil_depth_in=d["soil"], shape=shp_)
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
            y_top = _g["sup_top"]
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
                c.drawRightString(xs_ - 2, y_ftg + 8, f"V {sc['V']:,.0f} lb")
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
            n_info = sum(len(_split(v, 104)) for _, v in b.get("info", ())) + len(b.get("text", ()))
            p.room(min(_picture_height(b["picture"]) + 22 + 10 * n_info, 700))
            if b["picture"][0] in ("wind_mwfrs", "wind_zones", "seismic_forces", "diaphragm", "collector", "nailed", "toe_nail", "lag", "bolted", "bolted_perp", "model3d"):
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
                for u in _table_line(t, RM - LM):
                    p.room(11); p.text(u, font=FM, size=7.5, dy=10)
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
        boxes, top_lvl = [], 0
        for xf, parts in sorted(at.items()):
            xx = x0 + (x1 - x0) * xf / span
            c.setFont(FR, 5.5)
            txt = " + ".join(parts) + " lb"
            w = c.stringWidth(txt, FR, 5.5)
            xa, xb = (xx - 2.5 - w, xx - 2.5) if (x1 - xx < 20 and xx - x0 >= 20) else (xx + 2.5, xx + 2.5 + w)
            lvl = 0                                          # labels of loads close together step up, each clear of the others
            while any(l == lvl and xa < b_ + 3 and a_ < xb + 3 for a_, b_, l in boxes):
                lvl += 1
            boxes.append((xa, xb, lvl)); top_lvl = max(top_lvl, lvl)
            _arrow_down(c, xx, yy + 13 + 7 * lvl, yy, head=2.8)
            c.drawString(xa, yy + 8.5 + 7 * lvl, txt)
        yy += 16 + 7 * top_lvl
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


def _picture_height(pic):
    """Height a block picture takes, found by drawing it on a scratch canvas, so the page breaks before it rather than through it."""
    import io
    from reportlab.pdfgen import canvas as _cv
    try:
        c = _cv.Canvas(io.BytesIO(), pagesize=(612, 792))
        return 760.0 - _block_picture(c, 760.0, pic)
    except Exception:
        return 230.0


def _block_picture(c, top, pic):
    """Full-width pictures for the further blocks of a SimpleSheet. Returns the y below."""
    name, d = pic
    if name == "snow":
        return _snow_picture(c, top, d)
    if name == "frame3d":
        return _frame3d_picture(c, top, d)
    if name == "model3d":
        return _model3d_picture(c, top, d)
    if name == "shear_wall":
        return _shear_wall_picture(c, top, d)
    if name == "sill_anchor":
        return _sill_anchor_picture(c, top, d)
    if name == "joist_hanger":
        return _joist_hanger_picture(c, top, d)
    if name == "hurricane_tie":
        return _hurricane_tie_picture(c, top, d)
    if name == "post_base":
        return _post_base_picture(c, top, d)
    if name == "column_cap":
        return _column_cap_picture(c, top, d)
    if name == "strap":
        return _strap_picture(c, top, d)
    if name == "framing_angle":
        return _framing_angle_picture(c, top, d)
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
    if name == "free_roof":
        return _free_roof_picture(c, top - 6, d)
    if name == "snow_corner":
        return _snow_corner_picture(c, top - 6, d)
    if name == "hss_column":
        return _hss_column_picture(c, top - 6, d)
    if name == "guard":
        return _guard_picture(c, top - 6, d)
    if name == "tread":
        return _tread_picture(c, top - 6, d)
    if name == "tension":
        return _tension_picture(c, top - 6, d)
    if name == "shear_lug":
        return _shear_lug_picture(c, top - 6, d)
    if name == "crane_runway":
        return _crane_runway_picture(c, top - 6, d)
    if name == "angle_beam":
        return _angle_beam_picture(c, top - 6, d)
    if name == "base_plate_uplift":
        return _base_plate_uplift_picture(c, top - 6, d)
    if name == "single_plate":
        return _single_plate_picture(c, top - 6, d)
    if name == "coped_end":
        return _coped_end_picture(c, top - 6, d)
    if name == "end_plate":
        return _end_plate_picture(c, top - 6, d)
    if name == "seat":
        return _seat_picture(c, top - 6, d)
    if name == "cap_plate":
        return _cap_plate_picture(c, top - 6, d)
    if name == "through_plate":
        return _through_plate_picture(c, top - 6, d)
    if name == "wt_flange":
        return _wt_flange_picture(c, top - 6, d)
    if name == "stiffened_seat":
        return _stiffened_seat_picture(c, top - 6, d)
    if name == "angle_ecc":
        return _angle_ecc_picture(c, top - 6, d)
    if name == "beam_hss_moment":
        return _beam_hss_moment_picture(c, top - 6, d)
    if name == "flush_end_plate":
        return _flush_end_plate_picture(c, top - 6, d)
    if name == "base_biaxial":
        return _base_biaxial_picture(c, top - 6, d)
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
    col = d.get("col")
    g = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    # ---- plan: the moment and the shear act along the page width
    _sketch_title(c, LM + 6, top - 4, "PLAN")
    s = min(150 / SN, 92 / SB)
    x0, y0 = LM + 30, top - 22 - SB * s
    memberart._concrete(c, x0, y0, SN * s, SB * s, seed=5)
    px, py = x0 + (SN - N) * s / 2, y0 + (SB - B) * s / 2
    c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(0.87, 0.90, 0.93)
    c.rect(px, py, N * s, B * s, fill=1, stroke=1)
    if col:
        if col.get("kind", "I") == "I":
            c.saveState(); c.translate(px + N * s / 2, py + B * s / 2); c.rotate(90)
            memberart.steel_section(c, 0, 0, col["bf"] * s, col["d"] * s, col["d"], col["bf"], col["tf"], col["tw"])
            c.restoreState()
        else:
            memberart.hss_plan(c, px + N * s / 2, py + B * s / 2, col["d"] * s, col["bf"] * s, col["tf"] * s, inside=(0.87, 0.90, 0.93))
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
    col = d.get("col")
    if col:                                                 # the column on the plate, cut through its middle and broken off
        cw, xm = col["d"] * s2, cx0 + SN * s2 / 2
        if col.get("kind", "I") == "I":
            memberart.w_side(c, xm - cw / 2, ctop + tp, cw, 16, col["tf"] * s2)
        else:
            memberart.hss_cut_side(c, xm - cw / 2, ctop + tp, cw, 16, col["tf"] * s2)
        _break_h(c, xm - cw / 2, xm + cw / 2, ctop + tp + 16, amp=2.0)
    for k in (0, 1):
        rx = cx0 + (d["c_end"] + k * d["s_rows"]) * s2
        c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(1.1)
        c.line(rx, ctop - d["hef"] * s2, rx, ctop + tp + 5)
        c.setFillColorRGB(0.20, 0.22, 0.25)
        c.rect(rx - 3, ctop - d["hef"] * s2 - 2.2, 6, 2.2, fill=1, stroke=0)
        c.rect(rx - 2.4, ctop + tp, 4.8, 2, fill=1, stroke=0)
    xr = cx0 + SN * s2 + 8
    memberart._dim_v(c, ctop - d["hef"] * s2, ctop, xr, "hef = " + g(d["hef"]), FR, ext_from=cx0 + SN * s2)
    memberart._dim_v(c, ctop - d["ha"] * s2, ctop, xr + 34, "ha = " + g(d["ha"]), FR, ext_from=cx0 + SN * s2)
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


def _hex(c, x, y, F):
    """A hex nut or head seen along its axis: across flats F (points), the flats horizontal."""
    import math
    r = F / math.sqrt(3)
    p_ = c.beginPath()
    for k in range(6):
        a = math.radians(60 * k)
        (p_.moveTo if k == 0 else p_.lineTo)(x + r * math.cos(a), y + r * math.sin(a))
    p_.close(); c.drawPath(p_, fill=1, stroke=1)


def _bolted_picture(c, top, d):
    """Face of the connection at the member end, to scale: the member with its grain, broken off beyond the bolts, each bolt with its washer
    and nut (a lag screw head); end distance, spacing in a row, spacing between rows and edge distance dimensioned; the load arrow. Below it a
    section through one row of bolts: the members cut (end grain), the bolt with its head, washers and nut through them."""
    D, R, n, sp, g, end, edge, w = d["D"], d["rows"], d["n"], d["s"], d["g"], d["end"], d["edge"], d["w"]
    Lshow = end + (n - 1) * (sp or 0) + max(3 * D, 3.0)
    sc = min(230.0 / Lshow, 70.0 / w)
    x_end = (LM + RM) / 2 - Lshow * sc / 2                 # the member end at the left
    y0 = top - 26 - w * sc
    y1 = y0 + w * sc
    x_far = x_end + Lshow * sc
    memberart.wood_elevation(c, x_end, y0, x_far - x_end, y1 - y0, seed=3)
    _break_v(c, x_far, y0 - 2, y1 + 2)
    yb = [y1 - (edge + k * g) * sc for k in range(R)]       # the first row at the entered edge distance from the top edge
    Fw = max(2.2 * D * sc, 5.0)                             # washer about 2.2 D across (NDS 12.1.3 calls for washers; size not checked here)
    for y in yb:
        for k in range(n):
            xb = x_end + (end + k * (sp or 0)) * sc
            c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
            if not d.get("steel"):
                c.setFillColorRGB(0.80, 0.83, 0.87); c.circle(xb, y, Fw / 2, fill=1, stroke=1)
            c.setFillColorRGB(0.55, 0.60, 0.66); _hex(c, xb, y, max(1.5 * D * sc, 3.6))
            if not d.get("lag"):
                c.setFillColorRGB(0.30, 0.33, 0.37); c.circle(xb, y, max(D * sc / 2, 1.2), fill=1, stroke=0)     # the bolt end through the nut
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
    _small(c, (LM + RM) / 2, y0 - 28, "face at the connection, to scale; washers and nuts shown" if not d.get("lag") else "face at the connection, to scale")
    low = y0 - 34
    if d.get("side_t") and d.get("main_t") and not d.get("lag") and not d.get("perp"):
        # section through one row of bolts: the members cut across their length (end grain), stacked along the bolt
        ts, tm, dbl = d["side_t"], d["main_t"], d.get("double")
        layers = ([("side", ts)] + [("main", tm)] + ([("side", ts)] if dbl else [])) if not d.get("lag") else [("side", ts), ("main", tm)]
        tot = sum(t_ for _, t_ in layers)
        s2 = min(sc, 150.0 / tot, 60.0 / w)
        ytop = low - 14
        h2 = w * s2
        xc0 = (LM + RM) / 2 - tot * s2 / 2
        x_ = xc0
        for nm, t_ in layers:
            if nm == "side" and d.get("steel"):
                c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
                c.rect(x_, ytop - h2, t_ * s2, h2, fill=1, stroke=1); memberart._hatch_rect(c, x_, ytop - h2, t_ * s2, h2)
            else:
                memberart.wood_section(c, x_ + t_ * s2 / 2, ytop - h2 / 2, t_ * s2, h2, t_, w)
            x_ += t_ * s2
        for k in range(R):
            yy = ytop - (edge + k * g) * s2
            if d.get("lag"):
                L_ = ts + tm * 0.85
                memberart.bolt_side(c, xc0, yy, xc0 + L_ * s2, yy, max(D * s2, 2.0), head_end=1)
            else:
                memberart.bolt_side(c, xc0, yy, xc0 + tot * s2, yy, max(D * s2, 2.0), head_end=1)
        memberart._dim_h(c, xc0, xc0 + ts * s2, ytop - h2 - 9, f"{ts:g} in", FR, ext_from=ytop - h2)
        memberart._dim_h(c, xc0 + ts * s2, xc0 + (ts + tm) * s2, ytop - h2 - 9, f"{tm:g} in", FR, ext_from=ytop - h2)
        memberart._dim_v(c, ytop - h2, ytop, xc0 + tot * s2 + 22, f"{w:g} in", FR, ext_from=xc0 + tot * s2 + 8)
        _small(c, (LM + RM) / 2, ytop - h2 - 26, "section through a row of fasteners, members cut across their length, to scale")
        low = ytop - h2 - 32
    return low


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
    memberart.wood_elevation(c, x_end, y0, x_far - x_end, y1 - y0, seed=6)          # grain left to right
    _break_v(c, x_far, y0 - 2, y1 + 2)
    xs = [x_end + (end_show + k * g) * sc for k in range(R)]
    ys = [y0 + (le + k * sp) * sc for k in range(n)]
    for x in xs:
        for y in ys:
            c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
            c.setFillColorRGB(0.80, 0.83, 0.87); c.circle(x, y, max(2.2 * D * sc, 5.0) / 2, fill=1, stroke=1)
            c.setFillColorRGB(0.55, 0.60, 0.66); _hex(c, x, y, max(1.5 * D * sc, 3.6))
            c.setFillColorRGB(0.30, 0.33, 0.37); c.circle(x, y, max(D * sc / 2, 1.2), fill=1, stroke=0)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
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
    for (xa, ya, w_, h_, kind, sd) in ((x0 - 22, y_mid, wd, ts * sc, "side", 5), (x0 + 22, y_bot, wd, tm * sc, "main", 9)):
        memberart.wood_elevation(c, xa, ya, w_, h_, seed=sd)
        _break_v(c, xa if kind == "side" else xa + w_, ya - 2, ya + h_ + 2)               # each member continues beyond the joint
    xn = (LM + RM) / 2
    c.setStrokeColorRGB(0.25, 0.27, 0.3); c.setLineWidth(max(1.0, D * sc)); c.line(xn, y_top, xn, y_top - Lg * sc + D * sc)
    hd = max(2.6 * D * sc, 5.0)                                                            # the nail head, about 2.6 D across
    c.setFillColorRGB(0.35, 0.38, 0.42); c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(0.4)
    c.rect(xn - hd / 2, y_top, hd, max(0.12 * D * sc * 2, 1.4), fill=1, stroke=1)
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
    if d.get("steel_side"):                                  # steel side plate, cut
        c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE)
        c.rect(x0, y_mid, wd, max(ts * sc, 1.2), fill=1, stroke=1); memberart._hatch_rect(c, x0, y_mid, wd, max(ts * sc, 1.2))
    else:
        memberart.wood_elevation(c, x0, y_mid, wd, max(ts * sc, 1.2), seed=4)
    memberart.wood_elevation(c, x0, y_bot, wd, tmd * sc, seed=8)
    _break_v(c, x0, y_bot - 2, y_mid + max(ts * sc, 1.2) + 2); _break_v(c, x0 + wd, y_bot - 2, y_mid + max(ts * sc, 1.2) + 2)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    if tmd < tm:
        _break_h(c, x0, x0 + wd, y_bot)
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
    memberart.wood_elevation(c, xm0, y_bot, xm1 - xm0, tmd * sc, seed=8)                   # the main member, grain along it, broken off each end
    _break_v(c, xm0, y_bot - 2, y_mid + 2); _break_v(c, xm1, y_bot - 2, y_mid + 2)
    if tmd < tm:                                          # main member deeper than shown
        _break_h(c, xm0, xm1, y_bot)
    c.saveState(); c.translate(xs0 + ts * sc, y_mid); c.rotate(90)                            # the side member standing on it, grain vertical
    memberart.wood_elevation(c, 0, 0, hs * sc, ts * sc, seed=5)
    c.restoreState()
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
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


def _tread_picture(c, top, d):
    """Cross section of the bent plate tread, to scale with the thickness drawn not less than a visible line: width, leg depth and thickness."""
    b, t, dd = d["b"], d["t"], d["d"]
    sc = min(170.0 / b, 30.0 / dd)
    tt = max(t * sc, 1.6)
    x0 = (LM + RM) / 2 - b * sc / 2
    y1 = top - 26
    y0 = y1 - dd * sc
    c.setFillColorRGB(0.74, 0.79, 0.86); c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
    p = c.beginPath()
    for i, (x, y) in enumerate(((x0, y0), (x0, y1), (x0 + b * sc, y1), (x0 + b * sc, y0), (x0 + b * sc - tt, y0), (x0 + b * sc - tt, y1 - tt), (x0 + tt, y1 - tt), (x0 + tt, y0))):
        (p.moveTo if i == 0 else p.lineTo)(x, y)
    p.close(); c.drawPath(p, fill=1, stroke=1)
    memberart._dim_h(c, x0, x0 + b * sc, y0 - 10, f"{b:g} in", FR, ext_from=y0)
    memberart._dim_v(c, y0, y1, x0 + b * sc + 12, f"{dd:g} in", FR, ext_from=x0 + b * sc)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawRightString(x0 - 8, y1 - 4, f"PL {t:g} in.")
    c.drawRightString(x0 - 8, y1 - 13, f"span {d['span']:g} ft")
    _small(c, (LM + RM) / 2, y0 - 30, "tread cross section; spans between the stringers")
    return y0 - 38


def _angle_beam_picture(c, top, d):
    """Loading diagram over the span (down loads; sideways loads listed) with the span dimensioned, and the cut section of the angle to
    scale in its orientation, legs and thickness dimensioned, with the directions of the down and sideways loads."""
    L, loads = d["L"], d["loads"]
    x0, x1 = LM + 40, LM + 300
    hl = _beam_loads_height(loads)
    yb = top - 18 - hl - 8
    c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    c.rect(x0, yb - 6, x1 - x0, 6, fill=1, stroke=1)                                   # the vertical leg, seen on its face
    band = 1.6                                                                          # the horizontal leg seen edge-on at the heel
    c.setFillColorRGB(*memberart.STEEL_LINE)
    c.rect(x0, (yb - 6) if d.get("toe", "up") == "up" else (yb - band), x1 - x0, band, fill=1, stroke=0)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setLineWidth(0.6)
    sups = d.get("supports")
    for xx in ([x0 + (x1 - x0) * s_ / L for s_ in sups] if sups else (x0, x1)):
        p_ = c.beginPath(); p_.moveTo(xx, yb - 6); p_.lineTo(xx - 5, yb - 14); p_.lineTo(xx + 5, yb - 14); p_.close()
        c.drawPath(p_, fill=0, stroke=1)
    _beam_loads(c, x0, x1, yb, L, loads)
    if sups:
        marks = sorted(set([0.0, L] + list(sups)))
        for a_, b_ in zip(marks[:-1], marks[1:]):
            memberart._dim_h(c, x0 + (x1 - x0) * a_ / L, x0 + (x1 - x0) * b_ / L, yb - 24, f"{b_ - a_:g} ft", FR, ext_from=yb - 14)
    else:
        memberart._dim_h(c, x0, x1, yb - 24, f"span {L:g} ft", FR, ext_from=yb - 14)
    yl = yb - 44
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(x0, yl, d["shape"] + " (down loads drawn; plf and lb)")
    for k, t_ in enumerate(d["side"]):
        c.drawString(x0, yl - 9 * (k + 1), "sideways: " + t_)
    yl -= 9 * len(d["side"])
    axl = d.get("axial") or []
    for k, (t_, cmp_) in enumerate(axl):
        c.drawString(x0, yl - 9 * (k + 1), "axial: " + t_)
    yl -= 9 * len(axl)
    if axl:                                                  # axial arrows at both ends: toward the member in compression, away in tension
        cmp_ = any(q[1] for q in axl)
        c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
        yy = yb - 3
        if cmp_:
            _arrow(c, x0 - 30, yy, x0 - 2, yy, head=3); _arrow(c, x1 + 30, yy, x1 + 2, yy, head=3)
        else:
            _arrow(c, x0 - 2, yy, x0 - 30, yy, head=3); _arrow(c, x1 + 2, yy, x1 + 30, yy, head=3)
        c.setFont(FR, 6); c.drawCentredString(x1 + 16, yy + 4, "P")
        c.drawCentredString(x0 - 16, yy + 4, "P")
    Lv, Lh, t = d["Lv"], d["Lh"], d["t"]
    sc = min(90.0 / max(Lv, Lh), 20.0)
    hx = RM - 150                                            # heel, outside corner
    sgn = 1 if d["toe"] == "up" else -1
    hy = (top - 30 - Lv * sc) if sgn > 0 else (top - 30)
    c.setFillColorRGB(0.55, 0.62, 0.72); c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
    c.rect(hx, hy if sgn > 0 else hy - Lv * sc, t * sc, Lv * sc, fill=1, stroke=1)
    c.rect(hx + t * sc, hy if sgn > 0 else hy - t * sc, (Lh - t) * sc, t * sc, fill=1, stroke=1)
    yv0, yv1 = (hy, hy + Lv * sc) if sgn > 0 else (hy - Lv * sc, hy)
    memberart._dim_v(c, yv0, yv1, hx - 12, f"{Lv:g} in", FR, ext_from=hx)
    yh = (hy - 12) if sgn > 0 else (hy - Lv * sc - 12)
    memberart._dim_h(c, hx, hx + Lh * sc, yh, f"{Lh:g} in", FR, ext_from=hy if sgn > 0 else hy)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    c.drawString(hx + Lh * sc + 4, (hy + t * sc / 2 - 2) if sgn > 0 else (hy - t * sc / 2 - 2), f"t {t:g} in")
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    ax = hx + Lh * sc + 46
    _arrow_down(c, ax, yv1 + 6, yv1 - 16, head=3)
    c.setFont(FR, 6); c.drawString(ax + 4, yv1 - 4, "down")
    if d["side"]:
        ay = (yv0 + yv1) / 2
        _arrow(c, hx + Lh * sc + 40, ay - 14, hx + Lh * sc + 14, ay - 14, head=3)
        c.drawString(hx + Lh * sc + 18, ay - 24, "sideways +")
    c.setFillColorRGB(*INK)
    ys = min(yv0, yh) - 18
    _small(c, hx + Lh * sc / 2, ys, "section, to scale")
    return min(yl, ys) - 12


def _angle_ecc_picture(c, top, d):
    """Cut section of a single angle loaded through one leg, to scale: the angle with its thickness, the gusset plate against the back of
    the attached leg (cut short with break lines), the centroid, the principal axes w and z (centre lines), the load point at mid-width of the
    attached leg, points A, B, C named; the leg lengths, the load's offset and its height on the leg dimensioned."""
    Lv, Lh, t, e, xc, yc = d["Lv"], d["Lh"], d["t"], d["e"], d["xc"], d["yc"]
    wx, wy = d["w_hat"]
    sc = min(150.0 / (Lv + 2), 170.0 / (Lh + e + 4), 26.0)
    hx, hy = LM + 190, top - 36 - Lv * sc                  # heel, outside corner
    X = lambda x: hx + x * sc
    Y = lambda y: hy + y * sc
    tg = max(2 * e, 0.375)                                 # gusset drawn at twice the load's offset (the load on its centre line)
    c.setFillColorRGB(0.86, 0.89, 0.92); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    c.rect(X(-tg), Y(-1.0), tg * sc, (Lv + 2.0) * sc, fill=1, stroke=1)            # gusset plate, cut
    _break_h(c, X(-tg) - 2, X(0) + 2, Y(-1.0)); _break_h(c, X(-tg) - 2, X(0) + 2, Y(Lv + 1.0))
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.7)
    pth = c.beginPath(); pth.moveTo(X(0), Y(0)); pth.lineTo(X(Lh), Y(0)); pth.lineTo(X(Lh), Y(t)); pth.lineTo(X(t), Y(t)); pth.lineTo(X(t), Y(Lv))
    pth.lineTo(X(0), Y(Lv)); pth.close(); c.drawPath(pth, fill=1, stroke=1)
    # principal axes through the centroid, as centre lines
    c.setStrokeColorRGB(0.35, 0.40, 0.48); c.setLineWidth(0.4); c.setDash([6, 2, 1, 2])
    R = 0.42 * max(Lv, Lh)
    for (ux, uy), nm in (((-wy, wx), "w"), ((wx, wy), "z")):              # the w axis runs across w_hat; the z axis across z_hat (= along w_hat)
        if ux < 0 or (abs(ux) < 1e-9 and uy < 0):
            ux, uy = -ux, -uy                                               # name each axis at its right-hand (or upper) end
        if nm == "z" and uy < 0:
            ux, uy = -ux, -uy
        c.line(X(xc - ux * R), Y(yc - uy * R), X(xc + ux * R), Y(yc + uy * R))
        c.setDash(); c.setFont(FR, 6.5); c.setFillColorRGB(0.35, 0.40, 0.48)
        c.drawString(X(xc + ux * R) + 3, Y(yc + uy * R) + 1, nm); c.setDash([6, 2, 1, 2])
    c.setDash()
    c.setFillColorRGB(*INK); c.circle(X(xc), Y(yc), 1.4, fill=1, stroke=0)
    # load point
    lx, ly = X(-e), Y(Lv / 2)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(1, 1, 1); c.setLineWidth(0.9)
    c.circle(lx, ly, 3.2, fill=1, stroke=1); c.line(lx - 2.2, ly - 2.2, lx + 2.2, ly + 2.2); c.line(lx - 2.2, ly + 2.2, lx + 2.2, ly - 2.2)
    c.setFillColorRGB(*LOADC); c.setFont(FR, 6); c.drawRightString(lx - 6, ly + 4, f"P, {d['P']}")
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    for nm, (px, py) in d["pts_xy"].items():
        c.drawString(X(px) + 3, Y(py) + 2, nm)
    memberart._dim_v(c, Y(0), Y(Lv), X(Lh) + 26, f"{Lv:g} in", FR, ext_from=X(t))
    yb_ = min(Y(0), Y(yc - R * 1.0)) - 14
    memberart._dim_h(c, X(0), X(Lh), yb_, f"{Lh:g} in, t = {t:g} in", FR, ext_from=Y(0))
    memberart._dim_v(c, Y(0), ly, X(-tg) - 40, f"{Lv / 2:g} in", FR, ext_from=X(-tg))
    yt_ = Y(Lv + 1.0) + 14
    memberart._dim_h(c, lx, X(0), yt_, "", FR, ext_from=Y(Lv + 1.0) + 4)
    c.setFont(FR, 6); c.setFillColorRGB(*INK); c.drawRightString(lx - 6, yt_ - 2, f"load {e:g} in outside the leg")
    _small(c, X(Lh / 2), yb_ - 22, f"{d['shape']} section, to scale; load at mid-width of the attached leg; principal axes w and z")
    return yb_ - 30


def _crane_runway_picture(c, top, d):
    """Loading diagram of the runway beam with the wheels at the position of the largest moment, the span dimensioned, and the beam section
    with the rail and the lateral wheel load at the top of the rail."""
    L, loads = d["L"], d["loads"]
    x0, x1 = LM + 40, LM + 300
    hl = _beam_loads_height(loads)
    yb = top - 18 - hl - 8
    memberart.steel_elevation(c, x0, yb - 10, x1 - x0, 10, d["d"], d["tf"])
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
    sx = [x0 + (x1 - x0) * s_ / L for s_ in d["supports"]] if d.get("supports") else (x0, x1)
    for xx in sx:
        p_ = c.beginPath(); p_.moveTo(xx, yb - 10); p_.lineTo(xx - 5, yb - 18); p_.lineTo(xx + 5, yb - 18); p_.close()
        c.drawPath(p_, fill=0, stroke=1)
    _beam_loads(c, x0, x1, yb, L, loads)
    if d.get("supports") and len(d["supports"]) > 2:
        for a_, b_ in zip(sx[:-1], sx[1:]):
            memberart._dim_h(c, a_, b_, yb - 28, f"{(b_ - a_) / (x1 - x0) * L:g} ft", FR, ext_from=yb - 18)
    else:
        memberart._dim_h(c, x0, x1, yb - 28, f"span {L:g} ft", FR, ext_from=yb - 18)
    _small(c, (x0 + x1) / 2, yb - 46, "wheels with impact at the position of the largest moment; not to scale")
    cx, cy = RM - 100, top - 70
    s_ = memberart.steel_section(c, cx, cy, 70, 80, d["d"], d["bf"], d["tf"], d["tw"])
    yt = cy + d["d"] * s_ / 2
    c.setFillColorRGB(0.40, 0.42, 0.46); c.setStrokeColorRGB(*INK)
    c.rect(cx - 4, yt, 8, 8, fill=1, stroke=1)                                       # rail
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow(c, cx - 40, yt + 8, cx - 5, yt + 8, head=3)
    c.setFont(FR, 6); c.drawRightString(cx - 42, yt + 6, f"H {d['H']:.2f} kip")
    _arrow_down(c, cx, yt + 26, yt + 9, head=3)
    c.drawString(cx + 4, yt + 20, "wheel")
    c.setFillColorRGB(*INK)
    _small(c, cx, cy - d["d"] * s_ / 2 - 10, f"{d['beam']} with rail; not to scale")
    return min(yb - 54, cy - d["d"] * s_ / 2 - 18)


def _shear_lug_picture(c, top, d):
    """Section along the shear, to scale: base plate, grout, the lug down into the concrete, the concrete edge at ca1, with tbp, grout,
    embedment, lug thickness and ca1 dimensioned; plan of the plate with the lug width and the rod square dimensioned."""
    bsl, tsl, hsl, tg, tbp, N, ca1, s_ = d["bsl"], d["tsl"], d["hsl"], d["tg"], d["tbp"], d["N"], d["ca1"], d["s"]
    col, cru = d.get("col"), d.get("cruci")
    span = N / 2 + max(ca1 + tsl / 2, N / 2) + 4
    sc = min(230.0 / span, 110.0 / (tbp + tg + hsl + 6), 12.0)
    xc = LM + 50 + (N / 2 + 2) * sc                                  # lug centre
    hcol = 22.0 if col else 0.0                                      # the column drawn above the plate, broken off
    yt = top - 26 - hcol                                             # top of the plate
    yg = yt - tbp * sc                                               # underside of the plate = top of grout
    yc = yg - tg * sc                                                # top of concrete
    yb = yc - (hsl + 5) * sc
    xe = xc + (tsl / 2 + ca1) * sc                                   # concrete edge toward the shear
    memberart._concrete(c, xc - (N / 2 + 2) * sc, yb, xe - (xc - (N / 2 + 2) * sc), yc - yb, seed=4)                    # concrete
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
    c.setFillColorRGB(0.93, 0.92, 0.88); c.rect(xc - N / 2 * sc, yc, N * sc, tg * sc, fill=1, stroke=1)               # grout
    c.saveState(); gp = c.beginPath(); gp.rect(xc - N / 2 * sc, yc, N * sc, tg * sc); c.clipPath(gp, stroke=0, fill=0)
    c.setFillColorRGB(0.62, 0.60, 0.55)
    for k in range(int(N * tg * 1.5)):
        c.circle(xc - N / 2 * sc + ((k * 37) % 100) / 100 * N * sc, yc + ((k * 61) % 100) / 100 * tg * sc, 0.25, fill=1, stroke=0)
    c.restoreState()
    if cru:                                                          # the plate of the cross lying in this section, cut
        c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE)
        c.rect(xc - bsl / 2 * sc, yc - hsl * sc, bsl * sc, (hsl + tg) * sc, fill=1, stroke=1)
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE)
    c.rect(xc - N / 2 * sc, yg, N * sc, tbp * sc, fill=1, stroke=1)                                                      # plate, cut
    memberart._hatch_rect(c, xc - N / 2 * sc, yg, N * sc, tbp * sc)
    c.rect(xc - tsl / 2 * sc, yc - hsl * sc, tsl * sc, (hsl + tg) * sc, fill=1, stroke=1)                              # lug, cut
    memberart._hatch_rect(c, xc - tsl / 2 * sc, yc - hsl * sc, tsl * sc, (hsl + tg) * sc)
    if col:                                                          # the column on the plate, cut through its middle
        cw = col["d"] * sc
        if col["kind"] == "I":
            memberart.w_side(c, xc - cw / 2, yt, cw, hcol, col["tf"] * sc)
        else:
            memberart.hss_cut_side(c, xc - cw / 2, yt, cw, hcol, col["tf"] * sc)
        _break_h(c, xc - cw / 2, xc + cw / 2, yt + hcol, amp=2.0)
    rd = d.get("rod_d") or 0.75                                      # the rods each side, nut and washer on the plate
    for sg in (-1, 1):
        rx = xc + sg * s_ / 2 * sc
        hb_ = min((d.get("hef") or hsl + 4) * sc, yc - yb - 4)
        c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(max(rd * sc * 0.5, 1.0)); c.line(rx, yc - hb_, rx, yt + 4)
        c.setFillColorRGB(0.20, 0.22, 0.25)
        c.rect(rx - rd * sc * 0.9, yt, rd * sc * 1.8, max(rd * sc * 0.6, 2.0), fill=1, stroke=0)
        c.rect(rx - rd * sc * 0.9, yc - hb_ - 2, rd * sc * 1.8, 2, fill=1, stroke=0)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow(c, xc - N / 2 * sc - 20, yt + 9, xc - N / 2 * sc + 18, yt + 9, head=3)
    c.setFont(FR, 6); c.drawRightString(xc - N / 2 * sc - 23, yt + 7, "V")
    xr = xc - N / 2 * sc - 14
    memberart._dim_v(c, yg, yt, xr, f"{tbp:g} in", FR, ext_from=xc - N / 2 * sc)
    memberart._dim_v(c, yc, yg, xr - 30 if tg * sc < 8 else xr, f"grout {tg:g} in", FR, ext_from=xc - N / 2 * sc)
    memberart._dim_v(c, yc - hsl * sc, yc, xc - tsl / 2 * sc - 10, f"{hsl:g} in", FR, ext_from=xc - tsl / 2 * sc)
    memberart._dim_h(c, xc - tsl / 2 * sc, xc + tsl / 2 * sc, yc - hsl * sc - 10, f"{tsl:g} in", FR, ext_from=yc - hsl * sc)
    memberart._dim_h(c, xc + tsl / 2 * sc, xe, yb - 8, f"ca1 {ca1:g} in", FR, ext_from=yb)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    c.drawString(xc + N / 2 * sc + 4, yt - 6, f"PL {tbp:g} in.")
    if col:
        c.drawString(xc + col["d"] * sc / 2 + 4, yt + hcol - 6, col.get("name", ""))
    c.drawString(xc + N / 2 * sc + 4, yt - 14, f"lug {tsl:g} in., {d['weld']:g} in. fillets both faces")
    _small(c, (xc - N / 2 * sc + xe) / 2, yb - 26, "section along the shear, to scale")
    # plan
    ps = min(90.0 / N, 6.0)
    px, py = RM - 70, top - 22 - N * ps / 2
    c.setFillColorRGB(0.86, 0.89, 0.93); c.setStrokeColorRGB(*INK); c.setLineWidth(0.7)
    c.rect(px - N * ps / 2, py - N * ps / 2, N * ps, N * ps, fill=1, stroke=1)
    if col:                                                          # the column on the plate, cut above it
        if col["kind"] == "I":
            c.saveState(); c.translate(px, py); c.rotate(90)
            memberart.steel_section(c, 0, 0, col["bf"] * ps, col["d"] * ps, col["d"], col["bf"], col["tf"], col["tw"])
            c.restoreState()
        else:
            memberart.hss_plan(c, px, py, col["d"] * ps, col["bf"] * ps, col["tf"] * ps, rnd=col["kind"] == "round", inside=(0.86, 0.89, 0.93))
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.7)
    c.setDash(2, 2); c.rect(px - tsl * ps / 2, py - bsl * ps / 2, tsl * ps, bsl * ps, fill=0, stroke=1)
    if cru:
        c.rect(px - bsl * ps / 2, py - tsl * ps / 2, bsl * ps, tsl * ps, fill=0, stroke=1)
    c.setDash()
    c.setFillColorRGB(1, 1, 1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.circle(px + sx * s_ / 2 * ps, py + sy * s_ / 2 * ps, 1.8, fill=1, stroke=1)
    memberart._dim_v(c, py - bsl * ps / 2, py + bsl * ps / 2, px - N * ps / 2 - 10, f"lug {bsl:g} in", FR, ext_from=px - tsl * ps / 2)
    memberart._dim_h(c, px - s_ / 2 * ps, px + s_ / 2 * ps, py - N * ps / 2 - 10, f"{s_:g} in", FR, ext_from=py - s_ / 2 * ps)
    _small(c, px, py - N * ps / 2 - 28, "plan; lug below the plate dashed" if not cru else "plan; cruciform lug below the plate dashed")
    return min(yb - 34, py - N * ps / 2 - 36)


def _tension_picture(c, top, d):
    """The member in elevation with the tension pulling at each end, its length dimensioned and the section named."""
    x0, x1 = (LM + RM) / 2 - 110, (LM + RM) / 2 + 110
    y = top - 30
    c.setFillColorRGB(0.74, 0.79, 0.86); c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.rect(x0, y - 5, x1 - x0, 10, fill=1, stroke=1)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    if d.get("compression"):
        _arrow(c, x1 + 34, y, x1 + 4, y, head=4)
        _arrow(c, x0 - 34, y, x0 - 4, y, head=4)
    else:
        _arrow(c, x1 + 4, y, x1 + 34, y, head=4)
        _arrow(c, x0 - 4, y, x0 - 34, y, head=4)
    c.setFont(FR, 6.5)
    c.drawString(x1 + 38, y - 2, d["T"]); c.drawRightString(x0 - 38, y - 2, d["T"])
    c.setFillColorRGB(*INK); c.drawCentredString((x0 + x1) / 2, y + 9, d["shape"])
    memberart._dim_h(c, x0, x1, y - 16, f"{d['L']:g} ft", FR, ext_from=y - 5)
    _small(c, (LM + RM) / 2, y - 36, "member in compression; not to scale" if d.get("compression") else "member in tension; not to scale")
    return y - 44


def _base_plate_uplift_picture(c, top, d):
    """Plan of the plate, to scale: the column section, the four rods inside its profile, the rod spacings and the plate size dimensioned."""
    N, B, dd, bf, tf, tw, g, s_ = d["N"], d["B"], d["d"], d["bf"], d["tf"], d["tw"], d["g"], d["s"]
    sc = min(110.0 / N, 110.0 / B)
    cx, cy = (LM + RM) / 2, top - 22 - N * sc / 2
    c.setFillColorRGB(0.90, 0.92, 0.95); c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.rect(cx - B * sc / 2, cy - N * sc / 2, B * sc, N * sc, fill=1, stroke=1)
    memberart.steel_section(c, cx, cy, bf * sc, dd * sc, dd, bf, tf, tw, k=d.get("k"))       # the column cut above the plate
    c.setFillColorRGB(1, 1, 1); c.setLineWidth(0.8)
    for sx in (1, -1):
        for sy in (1, -1):
            c.circle(cx + sx * g / 2 * sc, cy + sy * s_ / 2 * sc, max(d["rod_d"] * sc / 2, 1.8), fill=1, stroke=1)
    yb = cy - N * sc / 2
    xr = cx + B * sc / 2
    memberart._dim_h(c, cx - g / 2 * sc, cx + g / 2 * sc, yb - 10, f"g {g:g} in", FR, ext_from=cy - s_ / 2 * sc)
    memberart._dim_h(c, cx - B * sc / 2, cx + B * sc / 2, yb - 26, f"B {B:g} in", FR, ext_from=yb)
    memberart._dim_v(c, cy - s_ / 2 * sc, cy + s_ / 2 * sc, xr + 10, f"{s_:g} in", FR, ext_from=cx + g / 2 * sc)
    memberart._dim_v(c, yb, yb + N * sc, xr + 48, f"N {N:g} in", FR, ext_from=xr)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5); c.drawRightString(cx - B * sc / 2 - 8, cy, d["shape"])
    _small(c, cx, yb - 46, "plan, to scale; rods inside the column profile")
    return yb - 54


def _single_plate_picture(c, top, d):
    """Elevation of the shear tab and a plan section through the beam web, to scale: the column (HSS drawn as a tube, or the support
    plate), the plate welded to it, the bolts and the beam with its flanges; a, the horizontal edge distance, the vertical edge distances,
    the bolt spacing and the plate length dimensioned; plate and weld called out on the plan."""
    n, s_, lev, leh, a, L = d["n"], d["s"], d["lev"], d["leh"], d["a"], d["L"]
    bd, btf, btw, bbf = d.get("bd") or L + 4, d.get("btf") or 0.5, d.get("btw") or 0.35, d.get("bbf") or 6.0
    hss, t, sup = d.get("hss"), d.get("t") or 0.5, d.get("sup")
    sc = min(130.0 / max(L, bd, sup["d"] if sup and sup["web"] else 0), 15.0)
    xw = LM + 130                                             # face of the column wall
    yc = top - 26 - max(L, bd) * sc / 2
    y0, y1 = yc - L * sc / 2, yc + L * sc / 2
    yb0, yb1 = yc - bd * sc / 2, yc + bd * sc / 2
    ylo, yhi = min(y0, yb0) - 10, max(y1, yb1) + 10
    if hss:
        colw = min(d["H"] * sc, 70.0)
        memberart.hss_elevation(c, xw - colw, ylo, colw, yhi - ylo, t * sc, rnd=d.get("rnd"))
    elif sup and sup["web"]:                                  # girder web: the girder cut, web at the face
        ylo, yhi = min(ylo, yc - sup["d"] * sc / 2 - 6), max(yhi, yc + sup["d"] * sc / 2 + 6)
        colw = sup["bf"] * sc / 2
        memberart.steel_section(c, xw - sup["tw"] * sc / 2, yc, sup["bf"] * sc, sup["d"] * sc, sup["d"], sup["bf"], sup["tf"], sup["tw"])
    elif sup:                                                 # column flange: the column seen from the side, flange at the face
        colw = min(sup["d"] * sc, 80.0)
        memberart.w_side(c, xw - colw, ylo, colw, yhi - ylo, sup["tf"] * sc)
    else:
        colw = max(t * sc, 3.0)
        c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6); c.setFillColorRGB(*memberart.STEEL_CUT)
        c.rect(xw - colw, ylo, colw, yhi - ylo, fill=1, stroke=1)
    if not (sup and sup["web"]):
        _break_h(c, xw - colw, xw, ylo); _break_h(c, xw - colw, xw, yhi)
    xb = xw + 0.5 * sc                                        # beam end, 1/2 in. clear of the column
    xe = xb + (a + leh) * sc + 46
    cp = d.get("cope")
    if cp:                                                    # the coped beam end, cut to its outline
        xc_ = xb + cp["c"] * sc
        yt, ybm = yb1 - cp["dc"] * sc, yb0 + cp["dcb"] * sc
        c.saveState()
        pth = c.beginPath(); pth.moveTo(xb, ybm); pth.lineTo(xc_, ybm); pth.lineTo(xc_, yb0); pth.lineTo(xe, yb0); pth.lineTo(xe, yb1)
        pth.lineTo(xc_, yb1); pth.lineTo(xc_, yt); pth.lineTo(xb, yt); pth.close()
        c.clipPath(pth, stroke=0, fill=0)
        memberart.w_side(c, xb, yb0, xe - xb, bd * sc, btf * sc, vertical=False)
        c.restoreState()
        c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6); c.drawPath(pth, fill=0, stroke=1)
    else:
        memberart.w_side(c, xb, yb0, xe - xb, bd * sc, btf * sc, vertical=False)
    _break_v(c, xe, yb0, yb1)
    c.setFillColorRGB(0.66, 0.72, 0.80); c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.rect(xw, y0, (a + leh) * sc, L * sc, fill=1, stroke=1)
    c.setFillColorRGB(1, 1, 1)
    ys = [y1 - (lev + k * s_) * sc for k in range(n)]
    for y in ys:
        c.circle(xw + a * sc, y, max(1.8, d["d"] * sc / 2), fill=1, stroke=1)
    yd = ylo - 6
    memberart._dim_h(c, xw, xw + a * sc, yd, f"a {a:g} in", FR, ext_from=y0)
    memberart._dim_h(c, xw + a * sc, xw + (a + leh) * sc, yd - 16, f"{leh:g} in", FR, ext_from=y0)
    xr = xe + 10
    memberart._dim_v(c, ys[0], y1, xr, f"{lev:g} in", FR, ext_from=xw + (a + leh) * sc)
    if n > 1:
        memberart._dim_v(c, ys[1], ys[0], xr, f"{s_:g} in" + (" typ." if n > 2 else ""), FR, ext_from=xw + (a + leh) * sc)
    memberart._dim_v(c, y0, ys[-1], xr, f"{lev:g} in", FR, ext_from=xw + (a + leh) * sc)
    memberart._dim_v(c, y0, y1, xr + 40, f"l {L:g} in", FR)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawRightString(xw - colw - 6, yc - 2, d["column"])
    c.drawString(xb + 4, yhi + 4, d["beam"])
    _small(c, xw + 40, yd - 34, "elevation, to scale")
    # ---- plan section through the beam web, looking down
    H_ = d["H"] if hss else (sup["d"] if sup and not sup["web"] else max(t, 0.5))
    B_ = d["B"] if hss else (sup["bf"] if sup else 10.0)
    s2 = min(11.0, 185.0 / (H_ + a + leh + 5), 96.0 / max(B_, bbf + 2))
    xq = RM - 20 - (a + leh + 5) * s2                         # face of the column in plan
    cq = (top - 30 + ylo) / 2 + 6
    tpp = max(d["tp"] * s2, 1.6)
    yw = cq + tpp                                             # the beam web beside the plate
    tww = max(btw * s2, 1.4)
    xbe = xq + 0.5 * s2
    xpe = RM - 20
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4); c.setFillColorRGB(0.95, 0.96, 0.97)
    c.rect(xbe, yw + tww / 2 - bbf * s2 / 2, xpe - xbe, bbf * s2, fill=1, stroke=1)          # bottom flange below the cut
    _break_v(c, xpe, yw + tww / 2 - bbf * s2 / 2, yw + tww / 2 + bbf * s2 / 2)
    if hss:
        memberart.hss_plan(c, xq - H_ * s2 / 2, cq, H_ * s2, B_ * s2, t * s2, rnd=d.get("rnd"))
        if d.get("rnd"):
            xq = xq - (H_ / 2 - math.sqrt(max((H_ / 2) ** 2 - (tpp / s2) ** 2, 0))) * s2 * 0
    elif sup and not sup["web"]:                              # the column cut, its flange at the face
        c.saveState(); c.translate(xq - sup["d"] * s2 / 2, cq); c.rotate(90)
        memberart.steel_section(c, 0, 0, sup["bf"] * s2, sup["d"] * s2, sup["d"], sup["bf"], sup["tf"], sup["tw"])
        c.restoreState()
    else:                                                     # a girder web (its bottom flange seen below the cut) or a plain support
        tw_ = max(t * s2, 2.5)
        if sup:
            c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4); c.setFillColorRGB(0.95, 0.96, 0.97)
            c.rect(xq - tw_ / 2 - sup["bf"] * s2 / 2, cq - 40, sup["bf"] * s2, 80, fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
        c.rect(xq - tw_, cq - 40, tw_, 80, fill=1, stroke=1)
        memberart._hatch_rect(c, xq - tw_, cq - 40, tw_, 80)
        _break_h(c, xq - tw_ - (sup["bf"] * s2 / 2 if sup else 0), xq + (sup["bf"] * s2 / 2 - tw_ / 2 if sup else 0), cq - 40)
        _break_h(c, xq - tw_ - (sup["bf"] * s2 / 2 if sup else 0), xq + (sup["bf"] * s2 / 2 - tw_ / 2 if sup else 0), cq + 40)
    xp0 = xq - ((H_ - t) * s2 if d.get("through") else 0.0)  # a through plate runs to the far wall
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    c.rect(xp0, cq, xq + (a + leh) * s2 - xp0, tpp, fill=1, stroke=1)                       # the plate, cut
    c.rect(xbe, yw, xpe - xbe, tww, fill=1, stroke=1)                                       # the beam web, cut
    w = max(d["weld"] * s2, 2.0)
    c.setFillColorRGB(*INK)
    for xx in ([xq, xp0 + t * s2] if d.get("through") else [xq]):
        sgn = 1 if xx == xq else -1
        for yy, up in ((cq + tpp, 1), (cq, -1)):
            pth = c.beginPath(); pth.moveTo(xx, yy); pth.lineTo(xx + sgn * w, yy); pth.lineTo(xx, yy + up * w); pth.close(); c.drawPath(pth, fill=1, stroke=0)
    xbolt = xq + a * s2
    c.setFillColorRGB(*INK); c.setStrokeColorRGB(*INK); c.setLineWidth(max(d["d"] * s2 * 0.6, 1.0))
    c.line(xbolt, cq - 3, xbolt, yw + tww + 3)
    c.setLineWidth(0.5)
    hw = max(d["d"] * s2 * 0.85, 2.0)
    c.rect(xbolt - hw, cq - 3 - 2, 2 * hw, 2, fill=1, stroke=0); c.rect(xbolt - hw, yw + tww + 3, 2 * hw, 2, fill=1, stroke=0)
    ypl = cq - (B_ * s2 / 2 if (hss or (sup and not sup["web"])) else 40) - 12
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    xt = xq + 6
    c.drawString(xt, ypl, f"PL {d['tp']:g} in.")
    c.drawString(xt, ypl - 8, f"{d['weld']:g} in. fillet each side")
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4)
    c.line(xt - 1, ypl + 2, xq + 1.5, cq - 0.5)
    _small(c, xq + 10, ypl - 22, "plan section through the beam web, to scale")
    return min(yd - 42, ypl - 30)


def _coped_end_picture(c, top, d):
    """Side elevation of a coped beam end, to scale: the support face, the setback, the beam with its cope(s), the bolts in the web; cope
    length and depth, setback, e, bolt line to the beam end, cut edge to the nearest bolt, bolt spacing and beam depth dimensioned."""
    bd, tf, dct, dcb, cl, sb = d["bd"], d["tf"], d.get("dct") or 0.0, d.get("dcb") or 0.0, d["c"], d["setback"]
    n, s_, lev, leh = d["n"], d["s"], d["lev"], d["leh"]
    Lshow = cl + 0.9 * bd
    sup0 = d.get("sup")
    deep = max(bd, sup0["d"] if (sup0 and sup0["web"]) else 0.0)
    sc = min(140.0 / deep, 290.0 / (sb + Lshow), 15.0)
    xs = LM + 90
    xb, xc, xe = xs + sb * sc, xs + (sb + cl) * sc, xs + (sb + Lshow) * sc
    yt = top - 44
    yb = yt - bd * sc
    sup, ylo, yhi = d.get("sup"), yb - 12, yt + 12                                                  # the support as the real member
    if d.get("hss"):
        colw = min((d.get("H") or 8) * sc, 70.0)
        memberart.hss_elevation(c, xs - colw, ylo, colw, yhi - ylo, (d.get("t") or 0.5) * sc, rnd=d.get("rnd"))
        _break_h(c, xs - colw, xs, ylo); _break_h(c, xs - colw, xs, yhi)
    elif sup and sup["web"]:                                                                          # girder web: the girder cut
        colw = sup["bf"] * sc / 2
        memberart.steel_section(c, xs - sup["tw"] * sc / 2, yt - sup["d"] * sc / 2, sup["bf"] * sc, sup["d"] * sc, sup["d"], sup["bf"], sup["tf"], sup["tw"])   # tops flush
        ylo = min(ylo, yt - sup["d"] * sc)
    elif sup:                                                                                         # column flange at the face, the column seen from the side
        colw = min(sup["d"] * sc, 80.0)
        memberart.w_side(c, xs - colw, ylo, colw, yhi - ylo, sup["tf"] * sc)
        _break_h(c, xs - colw, xs, ylo); _break_h(c, xs - colw, xs, yhi)
    else:
        colw = 14
        c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
        c.rect(xs - 14, ylo, 14, yhi - ylo, fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    pts = [(xb, yt - dct * sc)]
    if dct:
        pts += [(xc, yt - dct * sc), (xc, yt)]
    else:
        pts += [(xb, yt)]
    pts += [(xe, yt), (xe, yb)]
    if dcb:
        pts += [(xc, yb), (xc, yb + dcb * sc)]
    else:
        pts += [(xb, yb)]
    pts += [(xb, yb + dcb * sc)]
    pth = c.beginPath(); pth.moveTo(*pts[0])
    for q in pts[1:]:
        pth.lineTo(*q)
    pth.close()
    c.saveState(); c.clipPath(pth, stroke=0, fill=0)                                                   # the beam with its flanges, cut to the cope outline
    memberart.w_side(c, xb, yb, xe - xb, bd * sc, tf * sc, vertical=False)
    c.restoreState()
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.7); c.drawPath(pth, fill=0, stroke=1)
    _break_v(c, xe, yb, yt)
    pl = d.get("plate")
    if pl:                                                                                            # the shear plate on the far side of the web, hidden
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.5); c.setDash(2.5, 1.8)
        ypt = (yt - (dct + lev - pl["lev"]) * sc) if (dct or not dcb) else (yb + (dcb + lev - pl["lev"]) * sc + pl["L"] * sc)
        c.rect(xs, ypt - pl["L"] * sc, (pl["a"] + pl["leh"]) * sc, pl["L"] * sc, fill=0, stroke=1)
        c.setDash()
    xbolt = xb + leh * sc
    if dct or not dcb:
        ys = [yt - (dct + lev + k * s_) * sc for k in range(n)]
        ycut = yt - dct * sc
    else:
        ys = [yb + (dcb + lev + k * s_) * sc for k in range(n)]
        ycut = yb + dcb * sc
    for y in ys:                                                                                      # nuts on the beam side: hexagons with the bolt end
        r_ = max(2.6, d["d"] * 0.8 * sc)
        hp = c.beginPath()
        for k_ in range(6):
            a_ = math.pi / 6 + k_ * math.pi / 3
            (hp.moveTo if k_ == 0 else hp.lineTo)(xbolt + r_ * math.cos(a_), y + r_ * math.sin(a_))
        hp.close()
        c.setFillColorRGB(0.42, 0.47, 0.54); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4); c.drawPath(hp, fill=1, stroke=1)
        c.setFillColorRGB(0.70, 0.74, 0.79); c.circle(xbolt, y, max(1.2, d["d"] * sc / 2), fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    memberart._dim_h(c, xs, xb, yt + 16, "", FR, ext_from=yt)
    c.setFont(FR, 6); c.drawRightString(xs - 4, yt + 24, f"setback {sb:g} in")
    memberart._dim_h(c, xb, xc, yt + 16, f"c {cl:g} in", FR, ext_from=yt)
    memberart._dim_h(c, xs, xc, yt + 34, f"e {sb + cl:g} in", FR)
    memberart._dim_h(c, xb, xbolt, yb - 16, f"{leh:g} in", FR, ext_from=yb)
    if dct:
        memberart._dim_v(c, yt - dct * sc, yt, xc - 5, f"{dct:g} in", FR, ext_from=xc)
    if dcb:
        memberart._dim_v(c, yb, yb + dcb * sc, xc - 5, f"{dcb:g} in", FR, ext_from=xc)
    xr = xe + 14
    memberart._dim_v(c, min(ycut, ys[0]), max(ycut, ys[0]), xr, f"{lev:g} in", FR, ext_from=xbolt)
    if n > 1:
        memberart._dim_v(c, min(ys[0], ys[1]), max(ys[0], ys[1]), xr, f"{s_:g} in" + (" typ." if n > 2 else ""), FR, ext_from=xbolt)
    memberart._dim_v(c, yb, yt, xr + 46, f"d {bd:g} in", FR, ext_from=xe)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    lab = d.get("column") or "support"
    if xs - colw - 6 - c.stringWidth(lab, FR, 6.5) < LM:
        c.drawString(xs - colw, yt + 40, lab)                         # no room beside the support: above it, over the dimensions
    else:
        c.drawRightString(xs - colw - 6, (yt + yb) / 2 + 2, lab)
    c.drawRightString(xe - 4, yt + 4, d["beam"])
    ybot = min(yb - 40, ylo - 14)
    _small(c, (LM + RM) / 2, ybot, "side elevation of the beam end, to scale; the plate on the far side of the web dashed")
    return ybot - 8


def _end_plate_picture(c, top, d):
    """Face view of the end plate, to scale: the plate, the beam section behind it, two vertical rows of bolts; gage, edge distances,
    bolt spacing, plate width and length dimensioned; weld and plate called out."""
    n, s_, lev, leh, g, L, W = d["n"], d["s"], d["lev"], d["leh"], d["gage"], d["L"], d["W"]
    bd, bf, tf, tw = d["bd"], d["bf"], d["tf"], d["tw"]             # the beam section behind the plate
    sc = min(150.0 / max(L, bd), 110.0 / max(W, bf), 15.0)
    xc = (LM + RM) / 2 - 20
    yc = top - 26 - max(L, bd) * sc / 2
    x0, x1, y0, y1 = xc - W * sc / 2, xc + W * sc / 2, yc - L * sc / 2, yc + L * sc / 2
    yb0, yb1 = yc - bd * sc / 2, yc + bd * sc / 2
    memberart.steel_section(c, xc, yc, bf * sc, bd * sc, bd, bf, tf, tw)
    c.setFillColorRGB(0.86, 0.89, 0.93); c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.rect(x0, y0, W * sc, L * sc, fill=1, stroke=1)
    c.saveState()                                                                                    # the beam behind the plate, hidden
    clp = c.beginPath(); clp.rect(x0, y0, W * sc, L * sc); c.clipPath(clp, stroke=0, fill=0)
    c.setDash(2.5, 1.8); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    for yy in (yb0, yb0 + tf * sc, yb1 - tf * sc, yb1):
        c.line(xc - bf * sc / 2, yy, xc + bf * sc / 2, yy)
    for xx in (xc - bf * sc / 2, xc + bf * sc / 2):
        c.line(xx, yb0, xx, yb0 + tf * sc); c.line(xx, yb1 - tf * sc, xx, yb1)
    for xx in (xc - tw * sc / 2, xc + tw * sc / 2):
        c.line(xx, yb0 + tf * sc, xx, yb1 - tf * sc)
    c.restoreState()
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(1, 1, 1); c.setLineWidth(0.9)
    ys = [y1 - (lev + k * s_) * sc for k in range(n)]
    for y in ys:
        for x in (xc - g * sc / 2, xc + g * sc / 2):
            c.circle(x, y, max(1.8, d["d"] * sc / 2), fill=1, stroke=1)
    yd = min(y0, yb0) - 14
    memberart._dim_h(c, x0, xc - g * sc / 2, yd, f"{leh:g} in", FR, ext_from=y0)
    memberart._dim_h(c, xc - g * sc / 2, xc + g * sc / 2, yd - 14, f"gage {g:g} in", FR, ext_from=y0)
    memberart._dim_h(c, xc + g * sc / 2, x1, yd, f"{leh:g} in", FR, ext_from=y0)
    memberart._dim_h(c, x0, x1, yd - 30, f"{W:g} in", FR)
    xr = max(x1, xc + bf * sc / 2) + 14
    memberart._dim_v(c, ys[0], y1, xr, f"{lev:g} in", FR, ext_from=x1)
    if n > 1:
        memberart._dim_v(c, ys[1], ys[0], xr, f"{s_:g} in" + (" typ." if n > 2 else ""), FR, ext_from=x1)
    memberart._dim_v(c, y0, ys[-1], xr, f"{(L - lev - (n - 1) * s_):g} in", FR, ext_from=x1)
    memberart._dim_v(c, y0, y1, xr + 44, f"l {L:g} in", FR)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    xl = min(x0, xc - bf * sc / 2) - 8
    c.drawRightString(xl, yb1 - 6, d["beam"])
    c.drawRightString(x0 - 8, yc + 4, f"PL {d['tp']:g} in.")
    c.drawRightString(x0 - 8, yc - 5, f"{d['weld']:g} in. fillet, both sides of the web")
    _small(c, (LM + RM) / 2, yd - 46, "face of the end plate, to scale; the beam behind the plate dashed")
    return yd - 54


def _frame3d_picture(c, top, d):
    """Parallel projection of the placed frame (columns, beams, braces) with member marks; not to a stated scale. d: items of calc.model_view."""
    import math
    items = [i for i in d["items"] if i.get("b") is not None and i.get("type") not in ("wall", "joist", "deck")]
    if not items:
        return top
    yaw, tilt = math.radians(d.get("yaw", 30.0)), math.radians(d.get("tilt", 24.0))

    def pr(p):
        x, y, z = p
        u = x * math.cos(yaw) + y * math.sin(yaw)
        w = -x * math.sin(yaw) + y * math.cos(yaw)
        return u, z * math.cos(tilt) + w * math.sin(tilt)
    pts = [pr(i[k]) for i in items for k in ("a", "b")]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    Wd, Hd = RM - LM - 40, 190.0
    sc = min(Wd / max(x1 - x0, 1e-6), Hd / max(y1 - y0, 1e-6))
    ox = (LM + RM) / 2 - sc * (x0 + x1) / 2
    oy = top - 14 - sc * y1
    X = lambda p: ox + sc * p[0]
    Y = lambda p: oy + sc * p[1]
    many = len(items) > 40
    for typ, wdt, col in (("column", 1.6, INK), ("brace", 0.7, (0.55, 0.2, 0.1)), ("beam", 1.1, (0.13, 0.21, 0.32)), ("joist", 0.5, (0.4, 0.45, 0.5))):
        c.setLineWidth(wdt); c.setStrokeColorRGB(*col)
        for i in items:
            if i.get("type") == typ or (typ == "beam" and i.get("type") not in ("column", "brace", "joist")):
                a, b = pr(i["a"]), pr(i["b"])
                c.line(X(a), Y(a), X(b), Y(b))
    c.setFillColorRGB(*GREY); c.setFont(FR, 5.5 if many else 6.5)
    placed = []
    for i in items:
        a, b = pr(i["a"]), pr(i["b"])
        if many and i.get("type") == "brace":
            continue
        # the mark sits beside the member, clear of its line: offset square to the member, toward the upper side
        dx, dy = X(b) - X(a), Y(b) - Y(a)
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        if ny < -1e-9 or (abs(ny) <= 1e-9 and nx < 0):
            nx, ny = -nx, -ny
        mark = str(i.get("mark") or "")
        fs = 5.5 if many else 6.5
        tw = c.stringWidth(mark, FR, fs)
        off = 3.5 + 0.5 * tw * abs(nx) + 0.5 * fs * abs(ny)
        # try the middle of the member first, then other points along it and the other side, until the mark is clear of the marks already placed
        for frac, side in ((0.5, 1), (0.5, -1), (0.3, 1), (0.7, 1), (0.3, -1), (0.7, -1), (0.15, 1), (0.85, 1), (0.5, 1)):
            mx = X(a) + dx * frac + side * nx * off
            my = Y(a) + dy * frac + side * ny * off
            box = (mx - tw / 2 - 1, my - fs / 2 - 1, mx + tw / 2 + 1, my + fs / 2 + 1)
            if not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in placed):
                break
        placed.append(box)
        # a white patch under the mark, so a member line passing behind it in a crowded view never runs through the letters
        c.setFillColorRGB(1, 1, 1); c.rect(box[0], box[1], box[2] - box[0], box[3] - box[1], fill=1, stroke=0)
        c.setFillColorRGB(*GREY)
        c.drawCentredString(mx, my - 0.35 * fs, mark)
    c.setFillColorRGB(*INK); c.setStrokeColorRGB(*INK)
    yb = oy + sc * y0 - 12
    c.setFillColorRGB(*GREY); c.setFont(FR, 7); c.drawCentredString((LM + RM) / 2, yb, "View of the frame as analysed (not to scale)."); c.setFillColorRGB(*INK)
    return yb - 10


def _model3d_picture(c, top, d):
    """The building model in four parallel projections (2 x 2), walls as panels, footings as pads and strips, beams, columns and joist
    rows as lines; existing construction grey; a legend below. d: items and levels of calc.model_view. Not to scale."""
    import math
    items = d["items"]
    if not items:
        return top
    views = [(35.0, "+X, -Y"), (125.0, "+X, +Y"), (215.0, "-X, +Y"), (305.0, "-X, -Y")]
    tilt = math.radians(26.0)
    gap, capH = 14.0, 12.0
    cw, ch = (RM - LM - gap) / 2, 205.0
    WALL, WALL_E, FOOT = ((0.79, 0.64, 0.48), (0.54, 0.35, 0.17)), ((0.80, 0.82, 0.85), (0.48, 0.52, 0.58)), ((0.86, 0.87, 0.89), (0.42, 0.47, 0.54))

    def polys(it):
        tp = it.get("type")
        if tp == "wall":
            a, b = it["a"], it["b"]
            L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            at = lambda t, z: (a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L, z)
            ops = [("opening", [at(s1, lo), at(s2, lo), at(s2, hi), at(s1, hi)]) for (s1, s2), (lo, hi) in it.get("openings") or []]
            return [("wall", [a, b, (b[0], b[1], it["zb"]), (a[0], a[1], it["zb"])])] + ops
        if tp == "deck":
            return [("deck", list(it["poly"]))]
        if tp == "footing":
            a, b = it["a"], it.get("b")
            z = a[2]
            if b is not None:
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / L, dx / L
                return [("foot", [(a[0] + nx, a[1] + ny, z), (b[0] + nx, b[1] + ny, z), (b[0] - nx, b[1] - ny, z), (a[0] - nx, a[1] - ny, z)])]
            s_ = 1.5
            return [("foot", [(a[0] - s_, a[1] - s_, z), (a[0] + s_, a[1] - s_, z), (a[0] + s_, a[1] + s_, z), (a[0] - s_, a[1] + s_, z)])]
        if it.get("b") is not None:
            return [(tp, [it["a"], it["b"]])]
        return []

    shapes_ = [(it, kind_, pts) for it in items for kind_, pts in polys(it)]
    OPEN, DECK = ((0.88, 0.93, 0.98), (0.30, 0.38, 0.48)), ((0.90, 0.84, 0.74), (0.72, 0.62, 0.48))
    for vi, (yaw_deg, side) in enumerate(views):
        yaw = math.radians(yaw_deg)
        pr = lambda p: (p[0] * math.cos(yaw) + p[1] * math.sin(yaw),
                        p[2] * math.cos(tilt) + (-p[0] * math.sin(yaw) + p[1] * math.cos(yaw)) * math.sin(tilt))
        dep = lambda p: (-p[0] * math.sin(yaw) + p[1] * math.cos(yaw)) * math.cos(tilt) - p[2] * math.sin(tilt)
        allp = [pr(q) for _, _, pts in shapes_ for q in pts]
        x0, x1 = min(q[0] for q in allp), max(q[0] for q in allp)
        y0, y1 = min(q[1] for q in allp), max(q[1] for q in allp)
        col, row = vi % 2, vi // 2
        cx0 = LM + col * (cw + gap)
        cy1 = top - 6 - row * (ch + capH + 10)
        sc = min((cw - 16) / max(x1 - x0, 1e-6), (ch - 12) / max(y1 - y0, 1e-6))
        ox = cx0 + cw / 2 - sc * (x0 + x1) / 2
        oy = cy1 - ch / 2 - sc * (y0 + y1) / 2
        X = lambda q: ox + sc * q[0]
        Y = lambda q: oy + sc * q[1]
        c.setStrokeColorRGB(0.85, 0.87, 0.9); c.setLineWidth(0.4)
        c.rect(cx0, cy1 - ch, cw, ch, fill=0, stroke=1)
        # farthest first; an opening is drawn right after its wall (same depth, a hair nearer)
        key_ = lambda t: -(sum(dep(q) for q in t[2]) / len(t[2])) + (0.01 if t[1] == "opening" else 0.0)
        for it, kind_, pts in sorted(shapes_, key=key_):
            sp = [pr(q) for q in pts]
            if kind_ in ("wall", "foot", "opening", "deck"):
                fill, stroke = ((WALL_E if it.get("existing") else WALL) if kind_ == "wall" else FOOT if kind_ == "foot" else OPEN if kind_ == "opening" else DECK)
                path = c.beginPath(); path.moveTo(X(sp[0]), Y(sp[0]))
                for q in sp[1:]:
                    path.lineTo(X(q), Y(q))
                path.close()
                c.setFillColorRGB(*fill); c.setFillAlpha({"wall": 0.55, "opening": 0.95, "deck": 0.30}.get(kind_, 0.9))
                c.setStrokeColorRGB(*stroke); c.setLineWidth(0.3 if kind_ == "deck" else 0.6)
                c.drawPath(path, fill=1, stroke=1)
                c.setFillAlpha(1.0)
            else:
                wdt, colr = {"column": (1.6, INK), "joist": (0.5, (0.45, 0.5, 0.56)), "brace": (0.8, (0.55, 0.2, 0.1))}.get(kind_, (1.2, NAVY))
                c.setStrokeColorRGB(*colr); c.setLineWidth(wdt)
                c.line(X(sp[0]), Y(sp[0]), X(sp[1]), Y(sp[1]))
        c.setFillColorRGB(*GREY); c.setFont(FR, 7)
        c.drawCentredString(cx0 + cw / 2, cy1 - ch - 9, f"View from the {side} side")
    yb = top - 6 - 2 * (ch + capH + 10) - 4
    leg = [("wall", "new shear and bearing walls"), ("wall_e", "existing walls"), ("foot", "footings"),
           ("beam", "beams"), ("column", "columns and posts"), ("joist", "joists and rafters"),
           ("opening", "windows and doors"), ("deck", "floor and roof decks")]
    c.setFont(FR, 7)
    for k_, (kind_, text) in enumerate(leg):
        x = LM + (k_ % 3) * ((RM - LM) / 3)
        y = yb - (k_ // 3) * 11
        if kind_ in ("wall", "wall_e", "foot", "opening", "deck"):
            fill, stroke = {"wall": WALL, "wall_e": WALL_E, "foot": FOOT, "opening": OPEN, "deck": DECK}[kind_]
            c.setFillColorRGB(*fill); c.setStrokeColorRGB(*stroke); c.setLineWidth(0.6); c.rect(x, y - 1, 12, 6, fill=1, stroke=1)
        else:
            wdt, colr = {"column": (1.6, INK), "joist": (0.5, (0.45, 0.5, 0.56))}.get(kind_, (1.2, NAVY))
            c.setStrokeColorRGB(*colr); c.setLineWidth(wdt); c.line(x, y + 2, x + 12, y + 2)
        c.setFillColorRGB(*GREY); c.drawString(x + 17, y, text)
    c.setFillColorRGB(*INK); c.setStrokeColorRGB(*INK)
    return yb - 35


def _seat_picture(c, top, d):
    """Side view of the seat, to scale: the support face, the seat angle, the beam end on it; outstanding leg, vertical leg, angle
    thickness, setback and bearing length dimensioned."""
    osl, vl, t, sb, N = d["osl"], d["vleg"], d["t"], d["setback"], d["N"]
    sc = min(110.0 / max(vl + 4, 8), 16.0)
    xs = (LM + RM) / 2 - 40                       # face of the support
    ys = top - 30 - min(d.get("bd", 6.0), 5.0) * sc  # top of the seat
    hb = min(d.get("bd", 6.0), 5.0) * sc                    # the beam drawn to this height, then broken
    ysup0, ysup1 = ys - vl * sc - 12, ys + hb + 12
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6); c.setFillColorRGB(*memberart.STEEL_FILL)
    c.rect(xs - 14, ysup0, 14, ysup1 - ysup0, fill=1, stroke=1)                  # the support
    _break_h(c, xs - 14, xs, ysup0); _break_h(c, xs - 14, xs, ysup1)
    T, r = t * sc, min(t * sc, 0.4 * (osl - t) * sc)
    pth = c.beginPath()                                                          # the seat angle, cut: heel at the support, fillet inside the heel
    pth.moveTo(xs, ys - vl * sc); pth.lineTo(xs + T, ys - vl * sc); pth.lineTo(xs + T, ys - T - r)
    pth.curveTo(xs + T, ys - T - r / 2, xs + T + r / 2, ys - T, xs + T + r, ys - T)
    pth.lineTo(xs + osl * sc, ys - T); pth.lineTo(xs + osl * sc, ys); pth.lineTo(xs, ys); pth.close()
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.7)
    c.drawPath(pth, fill=1, stroke=1)
    c.saveState(); c.clipPath(pth, stroke=0, fill=0); memberart._hatch_rect(c, xs, ys - vl * sc, osl * sc, vl * sc); c.restoreState()
    if d.get("kind") == "bolted" and d.get("db"):                                # a bolt through the vertical leg and the support
        yb_ = ys - T - max(1.5, (vl - t) * 0.55) * sc
        c.setFillColorRGB(*INK); c.setStrokeColorRGB(*INK); c.setLineWidth(max(d["db"] * sc * 0.7, 1.0))
        c.line(xs - 14 - 3, yb_, xs + T + 3, yb_)
        hh = d["db"] * sc * 0.85
        c.rect(xs + T + 1, yb_ - hh, 2.5, 2 * hh, fill=1, stroke=0); c.rect(xs - 14 - 3.5, yb_ - hh, 2.5, 2 * hh, fill=1, stroke=0)
    elif d.get("weld"):                                                          # fillet at the angle ends, seen against the leg
        w_ = max(d["weld"] * sc, 1.5)
        c.setFillColorRGB(*INK); c.rect(xs + T, ys - vl * sc, min(w_, 4.0) * 0 + 0, 0, fill=0, stroke=0)
        pw = c.beginPath(); pw.moveTo(xs, ys - vl * sc); pw.lineTo(xs - w_ * 0, ys - vl * sc - w_); pw.lineTo(xs + w_, ys - vl * sc); pw.close()
        c.drawPath(pw, fill=1, stroke=0)
    xb = xs + sb * sc
    xbe = xs + osl * sc + 40
    memberart.w_side(c, xb, ys, xbe - xb, hb, d.get("tf", 0.5) * sc, vertical=False)
    c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_FILL)
    c.rect(xb + 0.3, ys + hb - d.get("tf", 0.5) * sc - 0.3, xbe - xb - 0.6, d.get("tf", 0.5) * sc + 1, fill=1, stroke=0)   # only the bottom flange is in view
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6); c.line(xb, ys, xb, ys + hb); c.line(xbe, ys, xbe, ys + hb)
    _break_h(c, xb, xbe, ys + hb)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    _arrow_down(c, xb + N * sc / 2, ys + hb + 20, ys + hb + 2, head=3)
    c.setFont(FR, 6.5); c.drawString(xb + N * sc + 6, ys + hb + 9, d["R"])     # beside the arrow, clear of the dimension lines
    # two short dimensions side by side: each text sits outside its own end, so the texts and the load label stay clear of each other
    memberart._dim_h(c, xs, xb, ys + hb + 34, "", FR, ext_from=ys + hb)
    memberart._dim_h(c, xb, xb + N * sc, ys + hb + 34, "", FR, ext_from=ys + hb)
    c.setFont(FR, 6)
    c.drawRightString(xs - 5, ys + hb + 32, f"setback {sb:g} in")
    c.drawString(xb + N * sc + 5, ys + hb + 32, f"bearing {N:.2f} in")
    memberart._dim_h(c, xs, xs + osl * sc, ys - vl * sc - 16, f"leg {osl:g} in", FR, ext_from=ys - t * sc)
    memberart._dim_v(c, ys - vl * sc, ys, xs - 26, f"leg {vl:g} in", FR, ext_from=xs)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(xs + osl * sc + 8, ys - t * sc - 2, f"seat angle, t = {t:g} in., {d['length']:g} in. long")
    c.drawString(xb + osl * sc + 46, ys + hb / 2 - 2, d["beam"])
    c.drawString(xs + osl * sc + 8, ys - t * sc - 11, d["attach"])
    _small(c, (LM + RM) / 2, ys - vl * sc - 34, "side view, to scale; the seat angle cut; top angle not shown")
    return ys - vl * sc - 42


def _base_biaxial_picture(c, top, d):
    """Plan of the base plate, to scale: plate, column outline, the four rods; plate size and rod edge distances dimensioned; the two moment axes named."""
    N, B, dc, bc, eN, eB, rd = d["N"], d["B"], d["d"], d["b"], d["edge_N"], d["edge_B"], d["rod_d"]
    sc = min(150.0 / max(N, B), 11.0)
    xc, yc = (LM + RM) / 2, top - 30 - B * sc / 2
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.setFillColorRGB(0.82, 0.85, 0.89); c.rect(xc - N / 2 * sc, yc - B / 2 * sc, N * sc, B * sc, fill=1, stroke=1)
    c.setFillColorRGB(0.62, 0.68, 0.76)
    if d["kind"] == "I":                                  # the column cut above the plate: W with its fillets, depth along N
        c.saveState(); c.translate(xc, yc); c.rotate(90)
        memberart.steel_section(c, 0, 0, bc * sc, dc * sc, dc, bc, d["tf"], d["tw"], k=d.get("k"))
        c.restoreState()
    else:                                                 # HSS cut above the plate: wall at its thickness, rounded corners
        memberart.hss_plan(c, xc, yc, dc * sc, bc * sc, d["tf"] * sc, rnd=d["kind"] == "round", inside=(0.82, 0.85, 0.89))
    c.setFillColorRGB(*INK)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.circle(xc + sx * (N / 2 - eN) * sc, yc + sy * (B / 2 - eB) * sc, max(rd / 2 * sc, 1.8), fill=1, stroke=0)
    memberart._dim_h(c, xc - N / 2 * sc, xc + N / 2 * sc, yc + B / 2 * sc + 16, f"N = {N:g} in", FR, ext_from=yc + B / 2 * sc)
    memberart._dim_v(c, yc - B / 2 * sc, yc + B / 2 * sc, xc - N / 2 * sc - 16, f"B = {B:g} in", FR, ext_from=xc - N / 2 * sc)
    memberart._dim_h(c, xc + (N / 2 - eN) * sc, xc + N / 2 * sc, yc - B / 2 * sc - 14, f"{eN:g} in", FR, ext_from=yc - B / 2 * sc)
    memberart._dim_v(c, yc + (B / 2 - eB) * sc, yc + B / 2 * sc, xc + N / 2 * sc + 16, f"{eB:g} in", FR, ext_from=xc + N / 2 * sc)
    _small(c, xc, yc - B / 2 * sc - 30, "plan, to scale. Mx bends the column about its strong axis (tension on a rod pair at one end of N); My about its weak axis.")
    return yc - B / 2 * sc - 38


def _flush_end_plate_picture(c, top, d):
    """Face of the end plate, to scale: plate, beam section behind it, the two tension bolts and the two compression-side bolts; plate width,
    gage, pfi and beam depth dimensioned. Beside it a side view of the beam on the column flange with the cap plate, to the same scale."""
    D, bf, tf, bp, tp, g, pfi, db = d["d"], d["bf"], d["tf"], d["bp"], d["tp"], d["g"], d["pfi"], d["db"]
    dc, tcf, tcap = d["dc"], d["tcf"], d["tcap"]
    ext = (d["pfo"] + 1.5) if d.get("pfo") else 0.5   # plate above the top of the beam
    Hp = D + 0.5 + ext
    sc = min(170.0 / Hp, 9.0)
    xc, yt = LM + 150, top - 26                       # plate centre line, top of plate
    yb = yt - Hp * sc
    y_top = yt - ext * sc                             # top of the beam
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.setFillColorRGB(0.82, 0.85, 0.89); c.rect(xc - bp / 2 * sc, yb, bp * sc, Hp * sc, fill=1, stroke=1)
    # the beam cut just in front of the plate (cut surfaces darker), with its flanges and web at thickness and the fillet welds to the plate
    tw_ = d.get("tw") or 0.4
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    c.rect(xc - bf / 2 * sc, y_top - tf * sc, bf * sc, tf * sc, fill=1, stroke=1); c.rect(xc - bf / 2 * sc, y_top - D * sc, bf * sc, tf * sc, fill=1, stroke=1)
    c.rect(xc - tw_ / 2 * sc, y_top - (D - tf) * sc, max(tw_ * sc, 1.2), (D - 2 * tf) * sc, fill=1, stroke=1)
    wf = (d.get("wf") or 0.25) * sc
    c.setFillColorRGB(0.30, 0.33, 0.38)
    for yf in (y_top, y_top - tf * sc, y_top - (D - tf) * sc, y_top - D * sc):              # fillets along both faces of each flange
        sgn = 1 if yf in (y_top, y_top - (D - tf) * sc) else -1
        c.rect(xc - bf / 2 * sc, yf if sgn > 0 else yf - max(wf, 1.0), bf * sc, max(wf, 1.0), fill=1, stroke=0)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    c.setFillColorRGB(*INK)
    y1, y2 = y_top - (tf + pfi) * sc, y_top - (D - tf - pfi) * sc
    rows_y = [y1, y2] + ([y1 - d["pb"] * sc] if d.get("pb") else []) + ([y_top + d["pfo"] * sc] if d.get("pfo") else [])
    if d.get("pfo"):
        memberart._dim_v(c, y_top, y_top + d["pfo"] * sc, xc - bp / 2 * sc - 16, f"pfo = {d['pfo']:g} in", FR, ext_from=xc - g / 2 * sc)
    for yy in rows_y:                                  # bolt heads seen on the plate face: hexagons with the shank
        for sx in (-1, 1):
            cx_, r_ = xc + sx * g / 2 * sc, max(db * 0.8 * sc, 2.6)
            pth = c.beginPath()
            for k_ in range(6):
                a_ = math.pi / 6 + k_ * math.pi / 3
                (pth.moveTo if k_ == 0 else pth.lineTo)(cx_ + r_ * math.cos(a_), yy + r_ * math.sin(a_))
            pth.close()
            c.setFillColorRGB(0.42, 0.47, 0.54); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4); c.drawPath(pth, fill=1, stroke=1)
            c.setFillColorRGB(0.70, 0.74, 0.79); c.circle(cx_, yy, max(db / 2 * sc, 1.2), fill=1, stroke=1)
    c.setFillColorRGB(*INK); c.setStrokeColorRGB(*INK)
    if d.get("pb"):
        memberart._dim_v(c, y1 - d["pb"] * sc, y1, xc + bp / 2 * sc + 14, f"pb = {d['pb']:g} in", FR, ext_from=xc + g / 2 * sc)
    memberart._dim_h(c, xc - bp / 2 * sc, xc + bp / 2 * sc, yt + 14, f"bp = {bp:g} in", FR, ext_from=yt)
    memberart._dim_h(c, xc - g / 2 * sc, xc + g / 2 * sc, yb - 14, f"g = {g:g} in", FR, ext_from=y2)
    memberart._dim_v(c, y1, y_top - tf * sc, xc + bp / 2 * sc + 14, f"pfi = {pfi:g} in", FR, ext_from=xc + g / 2 * sc)
    memberart._dim_v(c, y_top - D * sc, y_top, xc - bp / 2 * sc - 16, f"d = {D:g} in", FR, ext_from=xc - bp / 2 * sc)
    _small(c, xc, yb - 30, "face of the end plate, to scale; tension flange at the top")
    if not d.get("column"):
        return yb - 38
    # side view
    xs = RM - 170                                      # outside face of the column flange
    up = 14 if d.get("cont") else 0                    # a continuous column runs on above the plate
    memberart.w_side(c, xs, yb - 14, dc * sc, Hp * sc + 14 + up, tcf * sc)                              # the column seen at its web, flanges at the sides
    _break_h(c, xs, xs + dc * sc, yb - 14)
    if up:
        _break_h(c, xs, xs + dc * sc, yb + Hp * sc + up)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.9)
    if not d.get("cont") and not d.get("nocap"):
        c.rect(xs, yt, dc * sc, max(tcap * sc, 2), fill=1, stroke=1)                                     # cap plate
    st = d.get("stiff")
    if st:                                                                                              # stiffeners in line with both beam flanges
        c.setFillColorRGB(0.45, 0.5, 0.58)
        for yc_ in (y_top - tf / 2 * sc, y_top - (D - tf / 2) * sc):
            c.rect(xs + tcf * sc, yc_ - st["ts"] / 2 * sc, st["ls"] * sc, max(st["ts"] * sc, 1.2), fill=1, stroke=1)
        memberart._dim_h(c, xs + tcf * sc, xs + (tcf + st["ls"]) * sc, y_top - tf * sc - 12, f"{st['ls']:g} in", FR, ext_from=y_top - tf * sc)
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    c.rect(xs - tp * sc, yb, tp * sc, Hp * sc, fill=1, stroke=1)                                     # end plate, cut
    memberart.w_side(c, xs - tp * sc - 70, y_top - D * sc, 70, D * sc, tf * sc, vertical=False)       # the beam with its flanges, broken off
    _break_v(c, xs - tp * sc - 70, y_top - D * sc, y_top)
    wf = max((d.get("wf") or 0.25) * sc, 1.4)
    c.setFillColorRGB(0.30, 0.33, 0.38)
    for yf, sg in ((y_top, 1), (y_top - tf * sc, -1), (y_top - (D - tf) * sc, 1), (y_top - D * sc, -1)):   # flange fillets to the plate, in profile
        p_ = c.beginPath(); p_.moveTo(xs - tp * sc, yf); p_.lineTo(xs - tp * sc - wf, yf); p_.lineTo(xs - tp * sc, yf + sg * wf); p_.close()
        c.drawPath(p_, fill=1, stroke=0)
    for yy in rows_y:                                                                                   # bolts: head on the plate, washer and nut inside the column flange
        memberart.bolt_side(c, xs - tp * sc, yy, xs + tcf * sc, yy, max(db * sc, 2.0), head_end=1)
    c.setLineWidth(0.9); c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(xs - tp * sc - 58, y_top - D * sc / 2, d["beam"]); c.drawString(xs + tcf * sc + 8, yb + Hp * sc / 2, d["column"])
    if not d.get("cont") and not d.get("nocap"):
        c.drawString(xs + 4, yt + max(tcap * sc, 2) + 4, f"cap plate {tcap:g} in")
    elif st:
        c.drawString(xs + dc * sc + 6, y_top - tf / 2 * sc - 2, f"stiffeners {st['ts']:g} x {st['bs']:g} in")
    c.drawRightString(xs - tp * sc - 2, yb - 9, f"end plate {tp:g} in")
    _small(c, xs + dc * sc / 2 - 30, yb - 30, "side view, same scale")
    return yb - 38


def _wt_flange_picture(c, top, d):
    """Plan of the welded WT flange connection, to scale: the HSS, the WT flange across its face welded at the corners, the WT stem bolted to the
    beam flange; WT length, gage, spacing and edge distances dimensioned."""
    Bw, Hc, L, tf, dt, n, s_, g, leh, leb, db_, bf = d["Bw"], d["Hc"], d["L"], d["tf_t"], d["d_t"], d["n"], d["s"], d["g"], d["leh"], d["le_b"], d["db"], d["bf"]
    span = Hc + dt + 14
    sc = min(5.0, (RM - LM - 120) / span, 90.0 / max(L, Bw))
    x0 = LM + 60
    yc = top - 26 - max(L, Bw) / 2 * sc
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    memberart.hss_plan(c, x0 + Hc * sc / 2, yc, Hc * sc, Bw * sc, d["t"] * sc)                                                     # HSS, cut
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    xf = x0 + Hc * sc
    c.setFillColorRGB(0.62, 0.68, 0.76)
    c.rect(xf, yc - L / 2 * sc, tf * sc, L * sc, fill=1, stroke=1)                                                                  # WT flange
    c.rect(xf + tf * sc, yc - L / 2 * sc, (dt - tf) * sc, L * sc, fill=1, stroke=1)                                                 # WT stem (plan)
    xb0 = xf + dt * sc - (leh + (n - 1) * s_ + leb) * sc
    c.setFillColorRGB(0.90, 0.92, 0.95); c.rect(xb0, yc - bf / 2 * sc, (RM - 20) - xb0, bf * sc, fill=1, stroke=1)                  # beam flange
    c.setFillColorRGB(*INK)
    for i in range(n):
        xb = xf + dt * sc - (leh + i * s_) * sc
        for gy in (-1, 1):
            c.circle(xb, yc + gy * g / 2 * sc, max(db_ / 2 * sc, 1.5), fill=1, stroke=0)
    for gy in (-1, 1):                                                                                                               # flare-bevel welds
        c.circle(xf, yc + gy * Bw / 2 * sc, 2.2, fill=1, stroke=0)
    memberart._dim_v(c, yc - L / 2 * sc, yc + L / 2 * sc, x0 - 14, f"L = {L:g} in", FR, ext_from=xf)
    memberart._dim_v(c, yc - g / 2 * sc, yc + g / 2 * sc, RM - 50, f"g = {g:g} in", FR, ext_from=xf + dt * sc - leh * sc)
    xl = xf + dt * sc - (leh + (n - 1) * s_) * sc
    ylow = yc - max(L, bf) / 2 * sc - 14
    memberart._dim_h(c, xl, xf + dt * sc - leh * sc, ylow, f"{n - 1} @ {s_:g}" if n > 1 else "", FR, ext_from=yc - g / 2 * sc)
    memberart._dim_h(c, xf + dt * sc - leh * sc, xf + dt * sc, ylow - 16, f"{leh:g}", FR, ext_from=yc - L / 2 * sc)
    memberart._dim_h(c, xb0, xl, yc + max(L, bf) / 2 * sc + 14, f"{leb:g}", FR, ext_from=yc + bf / 2 * sc)
    c.setFont(FR, 6.5); c.setFillColorRGB(*INK)
    c.drawCentredString(x0 + Hc * sc / 2, yc - 3, d["column"])
    yb = ylow - 34
    _small(c, (LM + RM) / 2, yb, f"plan of the {d['wt']} at a beam flange: the HSS cut above the WT, the WT flange flare-bevel welded at the HSS corners (dots), the stem bolted to the beam flange; to scale; dimensions in inches")
    return yb - 10


def _through_plate_picture(c, top, d):
    """Plan of a through plate on the HSS column with the beam flanges bolted to it each side, to scale, and an elevation of the joint: plate
    width, HSS size, distance to the first bolt, spacing, edge distances and gage dimensioned."""
    H, B, bp, n, s_, g, L1, lep, lef, db_, bf = d["H"], d["B"], d["bp"], d["n"], d["s"], d["g"], d["L1"], d["le_p"], d["le_f"], d["d"], d["bf"]
    half = L1 + (n - 1) * s_ + lep                     # plate past each HSS face
    Lp = H + 2 * half
    sc = min(4.6, (RM - LM - 40) / Lp, 70.0 / max(bp, B))
    xc, yc = (LM + RM) / 2, top - 22 - max(bp, B) / 2 * sc
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setFillColorRGB(0.62, 0.68, 0.76); c.rect(xc - Lp / 2 * sc, yc - bp / 2 * sc, Lp * sc, bp * sc, fill=1, stroke=1)                       # plate
    c.setFillColorRGB(0.90, 0.92, 0.95)
    for sg in (-1, 1):                                                                                                                   # beam flanges, held back
        x0 = xc + sg * (H / 2 + L1 - lef) * sc
        x1 = xc + sg * (Lp / 2 + 18 / sc) * sc
        c.rect(min(x0, x1), yc - bf / 2 * sc, abs(x1 - x0), bf * sc, fill=1, stroke=1)
    if d.get("cut"):                                                                                                                     # HSS runs through the cut-out
        memberart.hss_plan(c, xc, yc, H * sc, B * sc, d["t"] * sc)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
        memberart._dim_v(c, yc + B / 2 * sc, yc + bp / 2 * sc, xc + H / 2 * sc - 10, f"ws = {d['ws']:g}", FR, ext_from=xc + H / 2 * sc)
    else:
        memberart.hss_plan(c, xc, yc, H * sc, B * sc, d["t"] * sc, inside=(0.62, 0.68, 0.76))                                          # HSS cut above the plate
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setFillColorRGB(*INK)
    for sg in (-1, 1):
        for i in range(n):
            xb = xc + sg * (H / 2 + L1 + i * s_) * sc
            for gy in (-1, 1):
                c.circle(xb, yc + gy * g / 2 * sc, max(db_ / 2 * sc, 1.5), fill=1, stroke=0)
    xr0 = xc + (H / 2) * sc
    memberart._dim_h(c, xc - H / 2 * sc, xc + H / 2 * sc, yc + max(bp, B) / 2 * sc + 14, f"H = {H:g} in", FR, ext_from=yc + B / 2 * sc)
    memberart._dim_h(c, xr0, xr0 + L1 * sc, yc - max(bp, bf) / 2 * sc - 14, f"{L1:g}", FR, ext_from=yc - g / 2 * sc)
    memberart._dim_h(c, xr0 + L1 * sc, xr0 + (L1 + (n - 1) * s_) * sc, yc - max(bp, bf) / 2 * sc - 14, f"{n - 1} @ {s_:g} in", FR, ext_from=yc - g / 2 * sc)
    memberart._dim_h(c, xr0 + (L1 + (n - 1) * s_) * sc, xr0 + half * sc, yc - max(bp, bf) / 2 * sc - 30, f"{lep:g}", FR, ext_from=yc - bp / 2 * sc)
    xl = xc - (H / 2 + L1) * sc
    memberart._dim_h(c, xc - (H / 2 + L1 - lef) * sc, xl, yc + max(bp, bf) / 2 * sc + 14, f"{lef:g}", FR, ext_from=yc + bf / 2 * sc)
    memberart._dim_v(c, yc - bp / 2 * sc, yc + bp / 2 * sc, xc - Lp / 2 * sc - 30, f"bp = {bp:g} in", FR, ext_from=xc - Lp / 2 * sc)
    memberart._dim_v(c, yc - g / 2 * sc, yc + g / 2 * sc, xc + Lp / 2 * sc + 30, f"g = {g:g} in", FR, ext_from=xc + (H / 2 + L1 + (n - 1) * s_) * sc)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    if c.stringWidth(d["column"], FR, 6.5) < H * sc - 6:
        c.drawCentredString(xc, yc - 3, d["column"])
    else:                                                                # too wide for the HSS: below it, clear of the flanges
        c.drawCentredString(xc, yc - B / 2 * sc - 9, d["column"])
    yb = yc - max(bp, B, bf) / 2 * sc - 44
    _small(c, xc, yb, (f"plan of a cut-out plate {d['tp']:g} x {bp:g} in. wrapping the HSS (cut above the plate), {d['beam']} flanges bolted each side; to scale; dimensions in inches" if d.get("cut") else
                       f"plan of a through plate {d['tp']:g} x {bp:g} in. passing through the HSS (cut above the plate), {d['beam']} flanges bolted each side; to scale; dimensions in inches"))
    return yb - 10


def _cap_plate_picture(c, top, d):
    """Elevation along the beam and plan of the cap plate, to scale: HSS column, cap plate, bottom of the beam, the four bolts; bolt spacing,
    column width, plate thickness, gage and plate width dimensioned."""
    B, s_, g, bp, tp, db, tf = d["B"], d["s"], d["g"], d["bp"], d["tp"], d["d"], d["tf"]
    Lp = s_ + 3.0                                  # plate length drawn: 1-1/2 in. past each bolt line
    sc = min(9.0, 150.0 / Lp)
    # elevation, left
    xc = LM + 150
    yp = top - 70                                  # underside of the cap plate
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    memberart.hss_elevation(c, xc - B / 2 * sc, yp - 60, B * sc, 60, d.get("t", 0.25) * sc)                                      # HSS column
    _break_h(c, xc - B / 2 * sc, xc + B / 2 * sc, yp - 60)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setFillColorRGB(0.62, 0.68, 0.76); c.rect(xc - Lp / 2 * sc, yp, Lp * sc, tp * sc, fill=1, stroke=1)                   # cap plate
    xb0, wb = xc - Lp / 2 * sc - 30, Lp * sc + 60                                                                            # the beam: bottom flange and web, broken
    c.setFillColorRGB(*memberart.STEEL_FILL); c.rect(xb0, yp + (tp + tf) * sc, wb, 26, fill=1, stroke=0)
    c.setFillColorRGB(*memberart.STEEL_CUT); c.rect(xb0, yp + tp * sc, wb, tf * sc, fill=1, stroke=1)
    c.line(xb0, yp + (tp + tf) * sc, xb0, yp + (tp + tf) * sc + 26); c.line(xb0 + wb, yp + (tp + tf) * sc, xb0 + wb, yp + (tp + tf) * sc + 26)
    _break_h(c, xb0, xb0 + wb, yp + (tp + tf) * sc + 26)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.setFillColorRGB(0.90, 0.92, 0.95)
    c.setLineWidth(1.4)
    for sx in (-1, 1):
        xb = xc + sx * s_ / 2 * sc
        c.line(xb, yp - 5, xb, yp + (tp + tf) * sc + 5)
        c.rect(xb - db * 0.8 * sc, yp - 5 - 3, db * 1.6 * sc, 3, fill=1, stroke=1); c.rect(xb - db * 0.8 * sc, yp + (tp + tf) * sc + 5, db * 1.6 * sc, 3, fill=1, stroke=1)
    c.setLineWidth(0.8)
    memberart._dim_h(c, xc - s_ / 2 * sc, xc + s_ / 2 * sc, yp + (tp + tf) * sc + 44, f"s = {s_:g} in", FR, ext_from=yp + (tp + tf) * sc + 10)
    memberart._dim_h(c, xc - B / 2 * sc, xc + B / 2 * sc, yp - 74, f"B = {B:g} in", FR, ext_from=yp - 60)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(xc + max(Lp / 2, s_ / 2 + db * 0.8) * sc + 8, yp + tp * sc / 2 - 2, f"cap plate {tp:g} in")
    c.drawString(xc + B / 2 * sc + 5, yp - 34, d["column"])
    c.drawString(xc + Lp / 2 * sc + 36, yp + (tp + tf) * sc + 10, d["beam"])
    _small(c, xc, yp - 90, "elevation along the beam, to scale")
    # plan, right
    xq, yq = RM - 135, top - 70 - 12
    c.setFillColorRGB(0.62, 0.68, 0.76); c.rect(xq - Lp / 2 * sc, yq - bp / 2 * sc, Lp * sc, bp * sc, fill=1, stroke=1)
    memberart.hss_plan(c, xq, yq, B * sc, B * sc, d.get("t", 0.25) * sc, dashed=True)                                             # the column below, hidden
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setFillColorRGB(*INK)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.circle(xq + sx * s_ / 2 * sc, yq + sy * g / 2 * sc, max(db / 2 * sc, 1.6), fill=1, stroke=0)
    memberart._dim_v(c, yq - g / 2 * sc, yq + g / 2 * sc, xq + Lp / 2 * sc + 14, f"g = {g:g} in", FR, ext_from=xq + s_ / 2 * sc)
    memberart._dim_v(c, yq - bp / 2 * sc, yq + bp / 2 * sc, xq - Lp / 2 * sc - 14, f"{bp:g} in", FR, ext_from=xq - Lp / 2 * sc)
    memberart._dim_h(c, xq - s_ / 2 * sc, xq + s_ / 2 * sc, yq + max(bp, B) / 2 * sc + 16, f"s = {s_:g} in", FR, ext_from=yq + g / 2 * sc)
    _small(c, xq, yq - max(bp, B) / 2 * sc - 16, "plan of the cap plate, to scale; the HSS below is dashed")
    return min(yp - 98, yq - max(bp, B) / 2 * sc - 24)


def _break_h(c, x1, x2, y, amp=3.0):
    """A break line across a member cut short (horizontal, from x1 to x2 at y): a straight line with one zigzag at the middle."""
    xm = (x1 + x2) / 2
    c.saveState(); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    p = c.beginPath(); p.moveTo(x1 - 1, y); p.lineTo(xm - amp, y); p.lineTo(xm - amp / 2, y + amp); p.lineTo(xm + amp / 2, y - amp)
    p.lineTo(xm + amp, y); p.lineTo(x2 + 1, y); c.drawPath(p, fill=0, stroke=1); c.restoreState()


def _break_v(c, x, y1, y2, amp=3.0):
    """A break line across a member cut short (vertical, at x from y1 to y2)."""
    ym = (y1 + y2) / 2
    c.saveState(); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    p = c.beginPath(); p.moveTo(x, y1 - 1); p.lineTo(x, ym - amp); p.lineTo(x + amp, ym - amp / 2); p.lineTo(x - amp, ym + amp / 2)
    p.lineTo(x, ym + amp); p.lineTo(x, y2 + 1); c.drawPath(p, fill=0, stroke=1); c.restoreState()


def _beam_hss_moment_picture(c, top, d):
    """Elevation of the beam framing into the HSS face and a plan of the face with the flange or flange plate on it, to scale: beam depth,
    column side wall, face width, flange or plate width and the distance from its edge to the HSS wall dimensioned."""
    B, H, Bb, tb, dd, tf, a_ = d["B"], d["H"], d["Bb"], d["tb"], d["d"], d["tf"], d["a"]
    sc = min(6.5, 120.0 / (dd + 12), 110.0 / (H + 14))
    # elevation, left
    xc, ym = LM + 120, top - 100                    # centre of the column, mid-depth of the beam
    hc = (dd + 14) * sc
    bot = d.get("bot")
    if d.get("plan_only"):
        return _beam_hss_moment_plan(c, top, d, B, H, Bb, tb, a_, ym, hc, xq=(LM + RM) / 2 + 30)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    memberart.hss_elevation(c, xc - H / 2 * sc, ym - hc / 2, H * sc, hc, d["t"] * sc)                                 # HSS column
    _break_h(c, xc - H / 2 * sc, xc + H / 2 * sc, ym - hc / 2); _break_h(c, xc - H / 2 * sc, xc + H / 2 * sc, ym + hc / 2)
    xf, Lb = xc + H / 2 * sc, 12 * sc                # face of the column, beam length drawn
    g_ = 0.5 * sc if d["plate"] else 0.0             # beam held back from the face where flange plates are used
    memberart.w_side(c, xf + g_, ym - dd / 2 * sc, Lb - g_, dd * sc, tf * sc, vertical=False)
    _break_v(c, xf + Lb, ym - dd / 2 * sc, ym + dd / 2 * sc)
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    blv, wlv = d.get("bolts"), d.get("welds")
    Lpl = (blv["a1"] + (blv["n"] - 1) * blv["s"] + blv["lev_p"]) if blv else ((wlv["a1"] + wlv["Lw"]) if wlv else 8.0)
    if d["plate"]:
        c.setFillColorRGB(0.62, 0.68, 0.76)
        tbb = bot["tb"] if bot else tb
        for sg in (1, -1):
            y0 = ym + sg * dd / 2 * sc if sg > 0 else ym - dd / 2 * sc - tbb * sc
            c.rect(xf, y0, Lpl * sc, (tb if sg > 0 else tbb) * sc, fill=1, stroke=1)
        if wlv:                                      # the fillets to the beam flange, seen along the plate edges
            c.setFillColorRGB(0.35, 0.38, 0.42)
            wb = max(1.2, wlv["w"] * sc)
            for yy in (ym + dd / 2 * sc - wb * 0.5, ym - dd / 2 * sc - wb * 0.5):
                c.rect(xf + wlv["a1"] * sc, yy, wlv["Lw"] * sc, wb, fill=1, stroke=0)
            c.setFillColorRGB(0.62, 0.68, 0.76)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(xf + Lb + 16, ym + 6, d["beam"])
    c.drawRightString(xc - H / 2 * sc - 5, ym - hc / 2 + 4, d["column"])
    memberart._dim_v(c, ym - dd / 2 * sc, ym + dd / 2 * sc, xf + Lb + 8, f"d = {dd:g} in", FR, ext_from=xf + Lb)
    memberart._dim_h(c, xc - H / 2 * sc, xc + H / 2 * sc, ym - hc / 2 - 12, f"{H:g} in", FR, ext_from=ym - hc / 2)
    if d["plate"]:
        c.setFont(FR, 6)
        if bot:
            c.drawString(xf + 2, ym + dd / 2 * sc + tb * sc + 4, f"top plate {Bb:g} x {tb:g} in")
            c.drawString(xf + 2, ym - dd / 2 * sc - bot["tb"] * sc - 9, f"bottom plate {bot['Bb']:g} x {bot['tb']:g} in")
        else:
            c.drawString(xf + 2, ym - dd / 2 * sc - tb * sc - 9, f"flange plate {Bb:g} x {tb:g} in, top and bottom")
    _small(c, xc + 20, ym - hc / 2 - 28, "elevation, to scale")
    return _beam_hss_moment_plan(c, top, d, B, H, Bb, tb, a_, ym, hc, xq=RM - 150)


def _beam_hss_moment_plan(c, top, d, B, H, Bb, tb, a_, ym, hc, xq):
    """Plan of the HSS face with the flange or flange plate on it (see _beam_hss_moment_picture)."""
    yq = top - 100
    s2 = min(7.5, 95.0 / B, 95.0 / H)
    c.setLineWidth(0.8); c.setStrokeColorRGB(*INK)
    memberart.hss_plan(c, xq - H * s2 / 2, yq, H * s2, B * s2, d["t"] * s2)                                         # HSS cut at the flange
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    bl, wl_ = d.get("bolts"), d.get("welds")
    Lp = (bl["a1"] + (bl["n"] - 1) * bl["s"] + bl["lev_p"]) * s2 if bl else ((wl_["a1"] + wl_["Lw"]) * s2 if wl_ else 46)
    bf_ = d.get("bf") or Bb
    flange_rect = lambda: None
    if wl_:                                                  # the beam flange, held 1/2 in. off the face, broken beyond the plate
        xb0, xb1 = xq + 0.5 * s2, xq + Lp + 16
        def flange_rect():
            c.setFillColorRGB(0.90, 0.92, 0.95); c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
            c.rect(xb0, yq - bf_ / 2 * s2, xb1 - xb0, bf_ * s2, fill=1, stroke=1)
            c.setLineWidth(0.4); c.setDash(2.5, 1.8)
            c.line(xb0, yq - bm_tw / 2 * s2, xb1, yq - bm_tw / 2 * s2); c.line(xb0, yq + bm_tw / 2 * s2, xb1, yq + bm_tw / 2 * s2)   # web beyond, hidden
            c.setDash()
            _break_v(c, xb1, yq - bf_ / 2 * s2 - 2, yq + bf_ / 2 * s2 + 2)
        bm_tw = d.get("tw") or 0.3
        if bf_ > Bb:
            flange_rect()                                    # looking down: the flange under a narrower plate
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    c.setFillColorRGB(0.62, 0.68, 0.76) if d["plate"] else c.setFillColorRGB(0.90, 0.92, 0.95)
    c.rect(xq, yq - Bb / 2 * s2, Lp, Bb * s2, fill=1, stroke=1)
    if wl_:
        if bf_ <= Bb:
            flange_rect()                                    # looking up at a wider plate: the flange is nearer the viewer
        wlw = min(bf_, Bb)                                   # the weld lines lie along the edges of the narrower part
        band = max(2.0, min(3.4, wl_["w"] * s2 * 0.9))
        xw0, xw1 = xq + wl_["a1"] * s2, xq + (wl_["a1"] + wl_["Lw"]) * s2
        c.setFillColorRGB(0.35, 0.38, 0.42); c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(0.3)
        strips = [(xw0, yq + wlw / 2 * s2, xw1 - xw0, band), (xw0, yq - wlw / 2 * s2 - band, xw1 - xw0, band)]
        if wl_["end"]:
            strips.append((xw1, yq - wlw / 2 * s2 - band, band, wlw * s2 + 2 * band))
        for (sx, sy, sw, sh) in strips:
            c.rect(sx, sy, sw, sh, fill=1, stroke=0)
            if sw > sh:
                k = sx
                while k < sx + sw - 1:
                    c.line(k, sy, min(k + sh * 0.7, sx + sw), sy + sh); k += 3.0
            else:
                k = sy
                while k < sy + sh - 1:
                    c.line(sx, k, sx + sw, min(k + sw * 0.7, sy + sh)); k += 3.0
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    memberart._dim_v(c, yq - B / 2 * s2, yq + B / 2 * s2, xq - H * s2 - 10, f"B = {B:g} in", FR, ext_from=xq - H * s2)
    memberart._dim_v(c, yq - Bb / 2 * s2, yq + Bb / 2 * s2, xq + Lp + (46 if bl else 26 if wl_ else 10), f"{Bb:g} in", FR, ext_from=xq + Lp)
    if bl:                                                   # bolts in plan, with the gage, the distance from the face and the spacing dimensioned
        c.setFillColorRGB(*INK)
        xs_ = [xq + (bl["a1"] + i * bl["s"]) * s2 for i in range(bl["n"])]
        for xb_ in xs_:
            for sg in (1, -1):
                c.circle(xb_, yq + sg * bl["g"] / 2 * s2, max(1.6, 0.4 * s2), fill=1, stroke=0)
        ybot = yq - Bb / 2 * s2 - 10
        memberart._dim_h(c, xq, xs_[0], ybot, "", FR, ext_from=yq - Bb / 2 * s2)
        c.setFont(FR, 6); c.setFillColorRGB(*INK)
        c.drawRightString(xq - 2, ybot - 8, f"{bl['a1']:g} in")
        if bl["n"] > 1:
            memberart._dim_h(c, xs_[0], xs_[-1], ybot, "", FR, ext_from=yq - Bb / 2 * s2)
            c.drawString(xs_[0] + 2, ybot - 8, f"{bl['n'] - 1} @ {bl['s']:g} in")
        memberart._dim_v(c, yq - bl["g"] / 2 * s2, yq + bl["g"] / 2 * s2, xq + Lp + 8, "", FR, ext_from=xs_[-1])
        c.setFont(FR, 6); c.setFillColorRGB(*INK)
        c.drawString(xq + Lp + 11, yq - 2, f"g = {bl['g']:g} in")
    if wl_:                                                  # weld start from the face and weld length dimensioned
        ybot = yq - max(Bb, bf_) / 2 * s2 - 10
        memberart._dim_h(c, xq, xw0, ybot, "", FR, ext_from=yq - wlw / 2 * s2 - band)
        memberart._dim_h(c, xw0, xw1, ybot, "", FR, ext_from=yq - wlw / 2 * s2 - band)
        c.setFont(FR, 6); c.setFillColorRGB(*INK)
        c.drawRightString(xq - 2, ybot - 8, f"{wl_['a1']:g} in")
        c.drawCentredString((xw0 + xw1) / 2, ybot - 8, f"{wl_['Lw']:g} in")
        c.drawString(xq, ybot - 17, f"fillet {wl_['w']:g} in, both edges" + (" and across the end" if wl_["end"] else ""))
    memberart._dim_v(c, yq + Bb / 2 * s2, yq + B / 2 * s2, xq + 22, "", FR, ext_from=xq)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    if wl_:
        c.drawString(xq + 26, yq + B / 2 * s2 + 3, f"a = {a_:.3g} in")
    else:
        c.drawString(xq + 26, yq + (Bb / 2 + a_ / 2) * s2 - 2 + max(0, 6 - a_ * s2), f"a = {a_:.3g} in")
    lo = yq - max(B, Bb, bf_ if wl_ else 0) / 2 * s2
    _small(c, xq - H * s2 / 2 + 20, lo - (34 if wl_ else 26 if bl else 14),
           ("plan looking up at the bottom flange plate, to scale" if (d.get("plan_only") or (wl_ and bf_ <= Bb)) else
            "plan at the top flange plate, to scale" if d.get("bot") else "plan at a " + ("flange plate" if d["plate"] else "flange") + ", to scale"))
    return min(ym - hc / 2 - 36, lo - (42 if wl_ else 34 if bl else 22)) if not d.get("plan_only") else lo - (42 if wl_ else 34 if bl else 22)


def _stiffened_seat_picture(c, top, d):
    """Stiffened seat, to scale: an elevation as a section at the beam centreline (the support as the real member: a W column with its flange
    at the face, or the column web cut with the far flange seen beyond; the seat plate, the stiffener plate with its fillets or the two angles
    with their bolts, the beam with its flanges broken off, the seat bolts and the top angle with their heads and nuts) and, where the support
    is a W shape, a plan section cut above the seat. W, L, lb, B and the plates dimensioned."""
    W, L, ts, tp, dd, tf = d["W"], d["L"], d["ts"], d["tseat"], d["d"], d["tf"]
    sup = d.get("sup")
    bo, top_a = d.get("bolted"), d.get("top")
    sc = min(7.0, 190.0 / (dd + L + tp + 4), 150.0 / (W + 12))
    xf = LM + 150                                    # face of the support
    ys = top - 16 - dd * sc                          # top of the seat plate (underside of the beam)
    ylo, yhi = ys - tp * sc - L * sc - 14, ys + dd * sc + 14
    tsup = d.get("t_sup") or 0.5
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
    hssc = sup if (sup and sup.get("kind") == "hss") else None
    if hssc:                                         # HSS column cut lengthwise through the seat: both walls hatched (the far one broken off if wide)
        full = hssc["H"] * sc
        colw = min(full, 90.0)
        if colw >= full - 1e-6:
            memberart.hss_cut_side(c, xf - colw, ylo, colw, yhi - ylo, hssc["t"] * sc)
        else:
            tw_ = max(hssc["t"] * sc, 1.2)
            c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6); c.setFillColorRGB(0.93, 0.94, 0.96)
            c.rect(xf - colw, ylo, colw, yhi - ylo, fill=1, stroke=0)
            c.setFillColorRGB(*memberart.STEEL_CUT); c.rect(xf - tw_, ylo, tw_, yhi - ylo, fill=1, stroke=1); memberart._hatch_rect(c, xf - tw_, ylo, tw_, yhi - ylo)
            _break_v(c, xf - colw, ylo, yhi)
        _break_h(c, xf - colw, xf, ylo); _break_h(c, xf - colw, xf, yhi)
        sup = None
    elif sup and not sup["web"]:                       # W column seen from the side, its flange at the face
        colw = min(sup["d"] * sc, 90.0)
        memberart.w_side(c, xf - colw, ylo, colw, yhi - ylo, sup["tf"] * sc)
        _break_h(c, xf - colw, xf, ylo); _break_h(c, xf - colw, xf, yhi)
    elif sup:                                        # section at the beam centreline: the column web cut, the far flange seen beyond
        colw = sup["bf"] * sc / 2
        c.setFillColorRGB(0.90, 0.92, 0.95); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
        c.rect(xf - sup["tw"] * sc - colw + sup["tw"] * sc / 2, ylo, sup["bf"] * sc, yhi - ylo, fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_CUT)
        c.rect(xf - sup["tw"] * sc, ylo, max(sup["tw"] * sc, 1.5), yhi - ylo, fill=1, stroke=1)
        _break_h(c, xf - colw - sup["tw"] * sc / 2, xf + colw - sup["tw"] * sc / 2, ylo); _break_h(c, xf - colw - sup["tw"] * sc / 2, xf + colw - sup["tw"] * sc / 2, yhi)
    else:
        colw = max(tsup * sc, 4.0)
        c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
        c.rect(xf - colw, ylo, colw, yhi - ylo, fill=1, stroke=1)
        _break_h(c, xf - colw, xf, ylo); _break_h(c, xf - colw, xf, yhi)
    # seat plate and stiffener
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    ystf = ys - tp * sc - L * sc
    if bo:                                           # the far angle: outstanding leg seen, vertical leg cut against the face
        c.setFillColorRGB(*memberart.STEEL_FILL)
        c.rect(xf, ystf, W * sc, L * sc, fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_CUT)
        c.rect(xf, ystf, max(ts * sc, 1.4), L * sc, fill=1, stroke=1)
        yb_ = [ystf + (bo["lev"] + k * bo["s"]) * sc for k in range(bo["n"])]
        for yb in yb_:
            memberart.bolt_side(c, xf - (tsup if not (sup and not sup["web"]) else sup["tf"]) * sc, yb, xf + max(ts * sc, 1.4), yb, max(bo["d"] * sc, 2.0), head_end=2)
    else:
        c.setFillColorRGB(*memberart.STEEL_FILL)
        c.rect(xf, ystf, W * sc, L * sc, fill=1, stroke=1)                                   # stiffener plate, side view
        band = max(1.8, d["weld"] * sc)
        c.setFillColorRGB(0.35, 0.38, 0.42); c.setLineWidth(0.3)
        c.rect(xf, ystf, band, L * sc, fill=1, stroke=0)                                     # fillet along the face, both sides of the stiffener
        k = ystf
        while k < ys - tp * sc - 1:
            c.line(xf, k, xf + band, min(k + band * 0.7, ys - tp * sc)); k += 3.0
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    c.rect(xf, ys - tp * sc, W * sc + 0.5 * sc, tp * sc, fill=1, stroke=1)                     # seat plate, cut
    # beam with its flanges, 1/2 in. setback, broken off
    xb = xf + 0.5 * sc
    xe = xb + (W + 9) * sc
    memberart.w_side(c, xb, ys, xe - xb, dd * sc, tf * sc, vertical=False)
    _break_v(c, xe, ys, ys + dd * sc)
    # seat bolts through the seat plate and the bottom flange
    xB = xf + (d.get("B") or max(W / 2, 2.625 if W / 2 < 2.625 else W / 2)) * sc
    memberart.bolt_side(c, xB, ys - tp * sc, xB, ys + tf * sc, max(0.75 * sc, 2.0), head_end=1)
    # top angle
    if top_a:
        tt, lg = top_a["t"], top_a["leg"]
        yt = ys + dd * sc
        c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
        pth = c.beginPath(); pth.moveTo(xf, yt); pth.lineTo(xf + 4 * sc, yt); pth.lineTo(xf + 4 * sc, yt + tt * sc); pth.lineTo(xf + tt * sc, yt + tt * sc)
        pth.lineTo(xf + tt * sc, yt + lg * sc); pth.lineTo(xf, yt + lg * sc); pth.close(); c.drawPath(pth, fill=1, stroke=1)
        if top_a["attach"].startswith("two bolts"):
            memberart.bolt_side(c, xf + 2.5 * sc, yt - tf * sc, xf + 2.5 * sc, yt + tt * sc, max(0.75 * sc, 2.0), head_end=2)
        else:
            c.setFillColorRGB(0.35, 0.38, 0.42)
            p2 = c.beginPath(); p2.moveTo(xf + 4 * sc, yt); p2.lineTo(xf + 4 * sc + 2.2, yt); p2.lineTo(xf + 4 * sc, yt + 2.2); p2.close(); c.drawPath(p2, fill=1, stroke=0)
        c.setFont(FR, 6); c.setFillColorRGB(*INK)
        c.drawString(xf + 4 * sc + 6, yt + lg * sc - 4, f"top angle, {tt:g} in, {lg:g} in leg, " + ("bolted" if top_a["attach"].startswith("two bolts") else "welded at the toes"))
    # reaction at 0.8 W
    xr = xf + 0.8 * W * sc
    c.setStrokeColorRGB(*FLAGC); c.setLineWidth(1.0)
    c.line(xr, ys + tf * sc + 22, xr, ys + tf * sc + 7)
    t_ = c.beginPath(); t_.moveTo(xr, ys + tf * sc + 1); t_.lineTo(xr - 3, ys + tf * sc + 8); t_.lineTo(xr + 3, ys + tf * sc + 8); t_.close()
    c.setFillColorRGB(*FLAGC); c.drawPath(t_, fill=1, stroke=0)
    c.setFont(FR, 6); c.drawString(xr + 4, ys + tf * sc + 14, "R at 0.8 W")
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(xe + 6, ys + dd * sc / 2, d["beam"])
    c.drawRightString(xf - colw - 6, ys - L * sc / 2, d["support"])
    memberart._dim_h(c, xf, xf + W * sc, ystf - 12, f"W = {W:g} in", FR, ext_from=ystf)
    memberart._dim_v(c, ystf, ys - tp * sc, xf + W * sc + 12, f"L = {L:g} in", FR, ext_from=xf + W * sc)
    if d.get("B"):                                   # seat bolts from the web face, dimensioned inside the beam above the bottom flange
        memberart._dim_h(c, xf, xB, ys + tf * sc + 30, f"B = {d['B']:g} in", FR, ext_from=ys + tf * sc + 2)
    c.setFont(FR, 6); c.setFillColorRGB(*INK)
    c.drawString(xf + W * sc + 46, ystf + L * sc * 0.62, f"seat PL {tp:g} in, lb = {d['lb']:.3g} in")
    c.drawString(xf + W * sc + 46, ystf + L * sc * 0.62 - 8, (f"two angles {ts:g} in, {2 * bo['n']} bolts" if bo else (f"two stiffeners PL {ts:g} in" if (d.get("n_stiff") or 1) == 2 else f"stiffener PL {ts:g} in")))
    if not bo:
        c.drawString(xf + W * sc + 46, ystf + L * sc * 0.62 - 16, f"{d['weld']:g} in fillets to the support")
    yl = ystf - 30
    _small(c, xf - 20, yl, "section at the beam centreline, to scale; beam set back 1/2 in.")
    low = yl - 6
    # plan section, cut above the seat plate, where the support is a W shape or an HSS
    if hssc:
        s2 = min(6.0, 150.0 / (max(hssc["H"], hssc["B"]) + W + 6))
        xq = RM - 30 - (W + 6) * s2 - (40 if (d.get("n_stiff") or 1) == 2 else 0)     # room for the spacing dimension
        cq = ys - tp * sc - 30
        memberart.hss_plan(c, xq - hssc["H"] * s2 / 2, cq, hssc["H"] * s2, hssc["B"] * s2, hssc["t"] * s2)
        g2 = d.get("g") or 0.0
        two = (d.get("n_stiff") or 1) == 2
        bw_ = min(max(d.get("bbf") or 7.0, (g2 + ts + 1.0) if two else 0.0), hssc["B"] - 1.0)
        c.setFillColorRGB(0.90, 0.92, 0.95); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
        c.rect(xq, cq - bw_ / 2 * s2, (W + 0.5) * s2, bw_ * s2, fill=1, stroke=1)
        c.setDash(2, 1.5)
        for yo_ in ((-g2 / 2, g2 / 2) if two else (0.0,)):                  # stiffener(s) below the seat plate, hidden
            c.rect(xq, cq + yo_ * s2 - ts * s2 / 2, W * s2, ts * s2, fill=0, stroke=1)
        c.setDash()
        xb2 = xq + 0.5 * s2
        c.setFillColorRGB(*memberart.STEEL_CUT)
        c.rect(xb2, cq - max(d.get("tw", 0.4) * s2, 1.2) / 2, (W + 5) * s2, max(d.get("tw", 0.4) * s2, 1.2), fill=1, stroke=1)
        _break_v(c, xb2 + (W + 5) * s2, cq - bw_ / 2 * s2 - 2, cq + bw_ / 2 * s2 + 2)
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*INK)
        xBp = xq + max(W / 2, 2.625) * s2
        gb_ = min(max(1.75, (g2 + ts) / 2 + 0.75) if two else 1.75, bw_ / 2 - 0.75)   # seat bolts clear of the stiffeners
        for sg in (1, -1):
            c.circle(xBp, cq + sg * gb_ * s2, max(1.6, 0.4 * s2), fill=1, stroke=1)
        hb = hssc["B"] * s2 / 2
        if two:
            xg_ = xq + (W + 5.5) * s2 + 14                                  # past the broken-off beam
            memberart._dim_v(c, cq - g2 / 2 * s2, cq + g2 / 2 * s2, xg_, f"{g2:g} in c/c", FR, ext_from=xq + W * s2 + 2)
        memberart._dim_v(c, cq - hb, cq + hb, xq - hssc["H"] * s2 - 10, f"{hssc['B']:g} in face", FR, ext_from=xq - hssc["H"] * s2)
        _small(c, xq - hssc["H"] * s2 * 0.5 + 10, cq - hb - 14, "plan, cut above the seat, to scale")
        low = min(low, cq - hb - 20)
    if sup:
        s2 = min(6.0, 150.0 / (max(sup["d"], sup["bf"]) + W + 6))
        xq = RM - 30 - (W + 6) * s2                   # face of the support in plan
        cq = ys - tp * sc - 30
        c.saveState()
        if sup["web"]:
            c.translate(xq - sup["tw"] * s2 / 2, cq)
            memberart.steel_section(c, 0, 0, sup["bf"] * s2, sup["d"] * s2, sup["d"], sup["bf"], sup["tf"], sup["tw"])
            c.restoreState()
            hb = sup["d"] * s2 / 2
        else:
            c.translate(xq - sup["d"] * s2 / 2, cq); c.rotate(90)
            memberart.steel_section(c, 0, 0, sup["bf"] * s2, sup["d"] * s2, sup["d"], sup["bf"], sup["tf"], sup["tw"])
            c.restoreState()
            hb = sup["bf"] * s2 / 2
        bw_ = d.get("bbf") or 7.0                     # seat plate as wide as the beam flange
        c.setFillColorRGB(0.90, 0.92, 0.95); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
        c.rect(xq, cq - bw_ / 2 * s2, (W + 0.5) * s2, bw_ * s2, fill=1, stroke=1)                # seat plate seen below the cut
        c.setDash(2, 1.5)
        if bo:
            c.rect(xq, cq - ts * s2 - 0.5, W * s2, ts * s2, fill=0, stroke=1); c.rect(xq, cq + 0.5, W * s2, ts * s2, fill=0, stroke=1)
        else:
            c.rect(xq, cq - ts * s2 / 2, W * s2, ts * s2, fill=0, stroke=1)                    # stiffener below the seat, hidden
        c.setDash()
        xb2 = xq + 0.5 * s2
        c.setFillColorRGB(*memberart.STEEL_CUT)
        c.rect(xb2, cq - max(d.get("tw", 0.4) * s2, 1.2) / 2, (W + 5) * s2, max(d.get("tw", 0.4) * s2, 1.2), fill=1, stroke=1)   # beam web, cut
        c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
        c.line(xb2, cq - bw_ / 2 * s2, xb2 + (W + 5) * s2, cq - bw_ / 2 * s2); c.line(xb2, cq + bw_ / 2 * s2, xb2 + (W + 5) * s2, cq + bw_ / 2 * s2)
        _break_v(c, xb2 + (W + 5) * s2, cq - bw_ / 2 * s2 - 2, cq + bw_ / 2 * s2 + 2)
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*INK)
        xBp = xq + (d.get("B") or max(W / 2, 2.625)) * s2
        for sg in (1, -1):
            c.circle(xBp, cq + sg * min(1.75, bw_ / 2 - 1.0) * s2, max(1.6, 0.4 * s2), fill=1, stroke=1)
        if d.get("B"):
            memberart._dim_h(c, xq, xBp, cq - max(hb, bw_ / 2 * s2) - 8, f"B = {d['B']:g} in", FR, ext_from=cq - bw_ / 2 * s2)
        _small(c, xq - hb * 0.5 - 10, cq - max(hb, bw_ / 2 * s2) - 26, "plan, cut above the seat, to scale")
        low = min(low, cq - max(hb, bw_ / 2 * s2) - 32)
    return low


def _guard_picture(c, top, d):
    """Guard elevation, to scale: three posts and the top rail drawn as tubes (corner lines on HSS, shading on pipe), the rail running over
    the post tops and broken off past the end posts, each post on a base plate (or welded to the top flange of the channel stringer, drawn
    with its flanges), the 200 lb load at mid-span and at a post top, the uniform load where it applies, spacing and height dimensioned;
    beside it the rail and the post cut to scale."""
    S, h = d["S"], d["h"]
    rd, pd = d.get("rail_d"), d.get("post_d")
    sc = min(80.0 / S, 70.0 / h)
    x0 = LM + 70
    ch = d.get("channel")
    yb = top - 38 - h * sc
    yt = yb + h * sc
    dim = lambda q: ((q["OD"] if q["kind"] == "round" else q["H"]) if q else 1.5)
    rw = max(dim(rd) * sc / 12, 3.0)                     # rail depth, to scale (not less than a visible tube)
    pw = max((pd["OD"] if pd and pd["kind"] == "round" else (pd["B"] if pd else 1.5)) * sc / 12, 3.0)
    xe = x0 + 2 * S * sc
    # what the posts stand on
    if ch:
        cd_ = ch["d"] * sc / 12
        memberart.w_side(c, x0 - 22, yb - cd_, xe - x0 + 44, cd_, max(ch["tf"] * sc / 12, 1.2), vertical=False)
        _break_v(c, x0 - 22, yb - cd_ - 2, yb + 2); _break_v(c, xe + 22, yb - cd_ - 2, yb + 2)
        ybase = yb
        c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawString(xe + 28, yb - cd_ / 2 - 2, f"{ch['name']} stringer")
    else:
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.6); c.line(x0 - 22, yb - 3, xe + 22, yb - 3)
        c.setLineWidth(0.35)
        xx = x0 - 21
        while xx + 3 <= xe + 22:
            c.line(xx, yb - 6, xx + 3, yb - 3); xx += 4
        ybase = yb
    for k in range(3):                                   # posts, each on its plate or welded to the flange
        xp = x0 + k * S * sc
        if not ch:
            c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
            c.rect(xp - pw / 2 - 3, yb - 3, pw + 6, 3, fill=1, stroke=1)
        memberart.hss_elevation(c, xp - pw / 2, ybase, pw, yt - rw / 2 - ybase, max((pd or {}).get("t", 0.12) * sc / 12, 0.6),
                                rnd=bool(pd and pd["kind"] == "round"))
        _weld_marks(c, xp, ybase, pw)
    memberart.hss_elevation(c, x0 - 18, yt - rw / 2, xe - x0 + 36, rw, max((rd or {}).get("t", 0.12) * sc / 12, 0.6),
                            rnd=bool(rd and rd["kind"] == "round"), vertical=False)
    _break_v(c, x0 - 18, yt - rw / 2 - 2, yt + rw / 2 + 2); _break_v(c, xe + 18, yt - rw / 2 - 2, yt + rw / 2 + 2)
    # loads, one at a time
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.8)
    _arrow_down(c, x0 + S * sc / 2, yt + rw / 2 + 16, yt + rw / 2 + 2, head=3)
    c.setFont(FR, 6.5); c.drawCentredString(x0 + S * sc / 2, yt + rw / 2 + 19, "200 lb, any direction")
    _arrow(c, x0 + S * sc - 24, yt - rw / 2 - 8, x0 + S * sc - pw / 2 - 2, yt - rw / 2 - 8, head=3)
    c.drawRightString(x0 + S * sc - 26, yt - rw / 2 - 10, "200 lb")
    if d.get("uniform"):
        xa, xb = x0 + S * sc + 6, xe - 6
        c.setLineWidth(0.45); c.line(xa, yt + rw / 2 + 11, xb, yt + rw / 2 + 11)
        n = max(int((xb - xa) / 10), 3)
        for j in range(n + 1):
            _arrow_down(c, xa + (xb - xa) * j / n, yt + rw / 2 + 11, yt + rw / 2 + 2, head=1.6)
        c.drawCentredString((xa + xb) / 2, yt + rw / 2 + 14, "or 50 lb/ft")
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawString(xe + 28, yt - 2, f"top rail {d['rail']}")
    c.drawString(xe + 28, (yb + yt) / 2 - 2, f"posts {d['post']}")
    ylo = yb - (ch["d"] * sc / 12 if ch else 6)
    memberart._dim_h(c, x0, x0 + S * sc, ylo - 10, f"{S:g} ft", FR, ext_from=ylo - 2)
    memberart._dim_h(c, x0 + S * sc, xe, ylo - 10, f"{S:g} ft", FR, ext_from=ylo - 2)
    memberart._dim_v(c, yb, yt, x0 - 30, f"{h:g} ft", FR, ext_from=x0 - pw / 2)
    _small(c, (x0 + xe) / 2, ylo - 28, "elevation, to scale; loads one at a time, in the direction that governs")
    # the rail and a post, cut to scale
    xs = RM - 100
    for j, (q, nm) in enumerate(((rd, f"top rail {d['rail']}"), (pd, f"post {d['post']}"))):
        if q:
            _hss_section(c, xs + j * 62, yt - 20, 34.0, q)
            c.setFillColorRGB(*INK); c.setFont(FR, 6.5); c.drawCentredString(xs + j * 62, yt + 4, "top rail" if j == 0 else "post")
    _small(c, xs + 31, yt - 70, "sections, to scale (in.)")
    return min(ylo - 34, yt - 78)


def _weld_marks(c, xp, y, w):
    """A small fillet at each side of a post at its base (the post is welded to what it stands on)."""
    c.setFillColorRGB(*memberart.STEEL_LINE)
    for sg in (-1, 1):
        x_ = xp + sg * w / 2
        t = c.beginPath(); t.moveTo(x_, y); t.lineTo(x_ + sg * 2.2, y); t.lineTo(x_, y + 2.2); t.close(); c.drawPath(t, fill=1, stroke=0)


def _hss_section(c, cx, cy, box, d):
    """Cut section of a round or rectangular HSS to scale in a box, wall drawn at its design
    thickness (not less than a visible line), dimensioned. Returns the scale."""
    rnd = d["kind"] == "round"
    W, H = (d["OD"], d["OD"]) if rnd else (d["B"], d["H"])
    s_ = box / max(W, H)
    tw = max(d["t"] * s_, 1.6)
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    if rnd:
        c.setFillColorRGB(*memberart.STEEL_FILL); c.circle(cx, cy, W * s_ / 2, fill=1, stroke=1)
        c.setFillColorRGB(1, 1, 1); c.circle(cx, cy, W * s_ / 2 - tw, fill=1, stroke=1)
        memberart._dim_h(c, cx - W * s_ / 2, cx + W * s_ / 2, cy - H * s_ / 2 - 8, f"OD {W:g}", FR, ext_from=cy)
    else:
        r_o = min(1.5 * d["t"] * s_ + 0.6, W * s_ / 3)
        c.setFillColorRGB(*memberart.STEEL_FILL); c.roundRect(cx - W * s_ / 2, cy - H * s_ / 2, W * s_, H * s_, r_o, fill=1, stroke=1)
        c.setFillColorRGB(1, 1, 1); c.roundRect(cx - W * s_ / 2 + tw, cy - H * s_ / 2 + tw, W * s_ - 2 * tw, H * s_ - 2 * tw, max(r_o - tw, 0.5), fill=1, stroke=1)
        memberart._dim_h(c, cx - W * s_ / 2, cx + W * s_ / 2, cy - H * s_ / 2 - 8, f"{W:g}", FR, ext_from=cy - H * s_ / 2)
        memberart._dim_v(c, cy - H * s_ / 2, cy + H * s_ / 2, cx + W * s_ / 2 + 7, f"{H:g}", FR, ext_from=cx + W * s_ / 2)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString(cx, cy - H * s_ / 2 - 26, f"t = {d['t']:g} (design)")
    return s_


def _hss_column_picture(c, top, d):
    """Elevation of the column as a tube (corner lines, or shading for a round section; width exaggerated), pinned at its base and held
    sideways at both ends, with the axial loads, the moments entered and the height dimensioned, beside the cut section to scale."""
    hh = 104.0
    cx = (LM + RM) / 2 - 90
    yb = top - 44 - hh
    wdt = 14.0
    rnd = d.get("kind") == "round"
    memberart.hss_elevation(c, cx - wdt / 2, yb, wdt, hh, 1.4, rnd=rnd)
    # base: a hinge on its support, the ground hatched
    c.setStrokeColorRGB(*INK); c.setLineWidth(0.8); c.setFillColorRGB(1, 1, 1)
    p_ = c.beginPath(); p_.moveTo(cx, yb); p_.lineTo(cx - 7, yb - 10); p_.lineTo(cx + 7, yb - 10); p_.close(); c.drawPath(p_, fill=1, stroke=1)
    c.circle(cx, yb, 1.6, fill=1, stroke=1)
    c.line(cx - 12, yb - 10, cx + 12, yb - 10)
    c.setLineWidth(0.4)
    for k in range(7):
        x_ = cx - 12 + k * 4
        c.line(x_, yb - 10, x_ - 3, yb - 14)
    # top: held sideways (a roller against a wall line) with the hinge
    c.setLineWidth(0.8); c.circle(cx, yb + hh, 1.6, fill=1, stroke=1)
    c.line(cx - wdt / 2 - 10, yb + hh - 8, cx - wdt / 2 - 10, yb + hh + 8)
    c.setLineWidth(0.4)
    for k in range(5):
        y_ = yb + hh - 8 + k * 4
        c.line(cx - wdt / 2 - 10, y_, cx - wdt / 2 - 14, y_ - 3)
    c.setLineWidth(0.8)
    for yy in (yb + hh - 3, yb + hh + 3):
        c.circle(cx - wdt / 2 - 7.5, yy, 1.4, fill=0, stroke=1)
    # loads
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9)
    ax_ = d.get("axial") or []
    y0_ = yb + hh + 8                                     # lowest label line, clear of the hinge
    _arrow_down(c, cx, y0_ + 7.5 * max(len(ax_) - 1, 0) + 8, yb + hh + 3, head=3.2)
    c.setFont(FR, 6.5)
    for k, txt in enumerate(ax_):
        c.drawString(cx + 6, y0_ + 7.5 * (len(ax_) - 1 - k), txt)
    if d.get("moment"):
        c.setLineWidth(0.7); c.arc(cx + 12, yb + hh - 36, cx + 28, yb + hh - 20, startAng=-70, extent=250)
        mt = d.get("moments") or ["M"]
        for k, txt in enumerate(mt):
            c.drawString(cx + 32, yb + hh - 26 - 7.5 * k, txt)
    memberart._dim_v(c, yb, yb + hh, cx - 36, f"{d['height']:g} ft", FR)
    if d.get("Kx") is not None:
        c.setFillColorRGB(*GREY); c.setFont(FR, 6)
        c.drawString(cx + 12, yb + 6, f"Kx = {d['Kx']:g}, Ky = {d['Ky']:g}")
    _sketch_title(c, cx + 150, top - 4, "SECTION")
    _hss_section(c, cx + 180, yb + hh / 2 + 4, 62.0, d)
    _small(c, (LM + RM) / 2, yb - 26, f"{d['shape']}; elevation with the width exaggerated, ends held against sidesway; section to scale, dimensions in inches")
    return yb - 32


def _stair_sketch(c, x0, top, w, sheet, st):
    """Stair stringer in place of the level beam sketch: the sloped stringer with its treads to
    scale, supports at each end, the uniform loads on the horizontal projection, the run and
    the rise dimensioned. Returns the y used as the underside for the layout below."""
    run, rise = sheet.span_ft * 12.0, st["rise_total_in"]
    s_ = min((w - 44) / run, 50.0 / rise)
    xa, ya = x0 + 8, top - 100
    xb, yb = xa + run * s_, ya + rise * s_
    n = max(int(round(rise / st["riser_in"])), 1)
    pr_ = sheet.props
    d_in, tf_in = pr_.get("d") or 12.0, pr_.get("tf") or 0.5
    L_ = math.hypot(run, rise)
    ux, uy = run / L_, rise / L_                          # along the stringer; nx, ny square to it, upward
    nx, ny = -uy, ux
    D, TF = max(d_in * s_, 4.0), max(tf_in * s_, 0.9)
    def band(o1, o2, fill):                               # a strip parallel to the slope, o1 to o2 from the work line, ends cut plumb
        e1, e2 = o1 / ny, o2 / ny                         # plumb offsets at the ends
        pth = c.beginPath()
        pth.moveTo(xa, ya + e1); pth.lineTo(xb, yb + e1); pth.lineTo(xb, yb + e2); pth.lineTo(xa, ya + e2); pth.close()
        c.setFillColorRGB(*fill); c.drawPath(pth, fill=1, stroke=1)
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    band(-D / 2, D / 2, memberart.STEEL_FILL)             # the channel seen from the stair side: web, flanges along both edges
    band(D / 2 - TF, D / 2, (0.64, 0.69, 0.75)); band(-D / 2, -D / 2 + TF, (0.64, 0.69, 0.75))   # flanges seen edge-on
    top_e = (D / 2) / ny                                  # plumb height of the stringer top edge above the work line
    tt = max(1.25 * s_, 1.2)                              # treads: plates on clips at each riser, nosing on the line of nosings
    c.setFillColorRGB(0.90, 0.92, 0.94); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
    for k in range(1, n + 1):
        xn, yn = xa + run * s_ * k / n, ya + rise * s_ * k / n + top_e * 0.35
        c.rect(xn - st["tread_in"] * s_, yn - tt, st["tread_in"] * s_ + 1.0, tt, fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.9)
    for xx, yy in ((xa, ya), (xb, yb)):
        t = c.beginPath(); t.moveTo(xx, yy - 2); t.lineTo(xx - 5, yy - 11); t.lineTo(xx + 5, yy - 11); t.close()
        c.drawPath(t, fill=0, stroke=1)
    yl = yb + 12
    c.setStrokeColorRGB(*BLUE); c.setFillColorRGB(*BLUE); c.setLineWidth(0.5)
    c.line(xa, yl + 9, xb, yl + 9)
    m = max(int((xb - xa) / 12), 4)
    for k in range(m + 1):
        _arrow_down(c, xa + (xb - xa) * k / m, yl + 9, yl, head=1.8)
    uni = [f"{ld['case']} {ld['w']:.3f}" for ld in sheet.loads if ld["kind"] == "uniform"]
    wt_ = "w = " + " + ".join(uni) + " kip/ft of run"
    c.setFont(FM, 6.5)
    if c.stringWidth(wt_, FM, 6.5) > w + 20:                # too long beside the section: two lines
        half = len(uni) // 2 + len(uni) % 2
        c.drawString(x0, top - 13, "w = " + " + ".join(uni[:half]) + " +")
        c.drawString(x0 + 8, top - 21, " + ".join(uni[half:]) + " kip/ft of run")
    else:
        c.drawString(x0, top - 15, wt_)
    memberart._dim_h(c, xa, xb, ya - 16, f"run {sheet.span_ft:g} ft", FR, ext_from=ya - 11)
    memberart._dim_v(c, ya, yb, xb + 10, f"{rise:.1f} in", FR, ext_from=xb)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawCentredString((xa + xb) / 2, ya - 36, f"to scale; risers {st['riser_in']:g} in, treads {st['tread_in']:g} in")
    return ya - 6


def _snow_corner_picture(c, top, d):
    """Plan of a reentrant corner, to scale: the two walls of the upper roof drawn heavy, the
    drift strip beside each with its width dimensioned and its surcharge at the wall, and the
    line across the overlap on which the two drift heights are equal."""
    a, b = d["a"], d["b"]
    wa, wb = max(a["w"], 1e-6), max(b["w"], 1e-6)
    ext_x, ext_y = 1.45 * max(wa, 0.4 * wb), 1.45 * max(wb, 0.4 * wa)
    s_ = min(200.0 / ext_x, 96.0 / ext_y)
    x0 = (LM + RM) / 2 - ext_x * s_ / 2
    y1 = top - 26                                        # wall B runs along the top; wall A down the left side
    X, Y = ext_x * s_, ext_y * s_
    c.setFillColorRGB(0.97, 0.98, 0.99); c.setStrokeColorRGB(*GREY); c.setLineWidth(0.3); c.rect(x0, y1 - Y, X, Y, fill=1, stroke=0)
    c.setFillColorRGB(0.86, 0.92, 0.98)
    if a["w"]:
        c.rect(x0, y1 - Y, wa * s_, Y, fill=1, stroke=0)
    if b["w"]:
        c.rect(x0, y1 - wb * s_, X, wb * s_, fill=1, stroke=0)
    if a["w"] and b["w"]:                                # overlap: the line of equal drift height
        c.setFillColorRGB(0.76, 0.85, 0.95); c.rect(x0, y1 - wb * s_, wa * s_, wb * s_, fill=1, stroke=0)
        Ha, Hb = a["h"], b["h"]
        if Ha <= Hb:                                     # at the wall A face (x = 0) the drifts are equal at y = wb (1 - Ha / Hb)
            px, py = 0.0, wb * (1 - Ha / Hb)
        else:
            px, py = wa * (1 - Hb / Ha), 0.0
        c.setStrokeColorRGB(*LOADC); c.setLineWidth(0.8); c.setDash(4, 2)
        c.line(x0 + px * s_, y1 - py * s_, x0 + wa * s_, y1 - wb * s_); c.setDash()
    c.setStrokeColorRGB(*INK); c.setLineWidth(2.6)
    c.line(x0, y1, x0, y1 - Y); c.line(x0, y1, x0 + X, y1)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawString(x0 + 3, y1 + 5, f"{b['name']}: surcharge {b['pd']:.1f} psf at the wall" if b["w"] else f"{b['name']}: no drift")
    c.saveState(); c.translate(x0 - 5, y1 - Y / 2); c.rotate(90)
    c.drawCentredString(0, 0, f"{a['name']}: {a['pd']:.1f} psf at the wall" if a["w"] else f"{a['name']}: no drift"); c.restoreState()
    if a["w"]:
        memberart._dim_h(c, x0, x0 + wa * s_, y1 - Y - 8, f"{a['w']:.1f} ft", FR, ext_from=y1 - Y)
    if b["w"]:
        memberart._dim_v(c, y1 - wb * s_, y1, x0 + X + 8, f"{b['w']:.1f} ft", FR, ext_from=x0 + X)
    c.setFillColorRGB(*GREY); c.setFont(FR, 6)
    c.drawString(x0 + max(wa * s_, 0) + 8, y1 - Y + 6, "lower roof")
    _small(c, (LM + RM) / 2, y1 - Y - 26, "plan to scale; upper roof beyond the heavy lines; dashed line: the two drift heights are equal")
    return y1 - Y - 32


def _free_roof_picture(c, top, d):
    """Two sections of the monoslope free roof to scale, one for each wind direction across the
    slope, with the windward and leeward halves marked, h and L dimensioned."""
    L, h, th = d["L"], d["h"], math.radians(d["theta"])
    if d.get("roof") in ("pitched", "troughed"):          # one section: the two slopes, wind from the left
        rise = L / 2 * math.tan(th) * (1 if d["roof"] == "pitched" else -1)
        s_ = min(170.0 / L, 70.0 / (h + abs(rise) / 2 + 1e-9))
        x0 = (LM + RM) / 2 - L * s_ / 2
        yb = top - 34 - (h + abs(rise) / 2) * s_
        ye, yr = yb + (h - rise / 2) * s_, yb + (h + rise / 2) * s_
        xm, xb = x0 + L * s_ / 2, x0 + L * s_
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.line(x0 - 14, yb, xb + 14, yb)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
        for f in (0.08, 0.92):
            c.line(x0 + L * s_ * f, yb, x0 + L * s_ * f, ye + (yr - ye) * 0.16)
        c.setLineWidth(2.2); c.line(x0, ye, xm, yr); c.line(xm, yr, xb, ye)
        c.setFillColorRGB(*LOADC); c.setStrokeColorRGB(*LOADC); c.setFont(FR, 6.5)
        c.drawRightString(xm - 8, max(yr, ye) + 6, "windward half, CNW"); c.drawString(xm + 8, max(yr, ye) + 6, "leeward half, CNL")
        c.setLineWidth(0.8); _arrow(c, x0 - 38, ye + 4, x0 - 10, ye + 4, head=3.2)
        memberart._dim_h(c, x0, xb, yb - 6, f"L {L:g} ft", FR, ext_from=yb)
        memberart._dim_v(c, yb, (ye + yr) / 2, xb + 16, f"h {h:g} ft", FR)
        _small(c, (LM + RM) / 2, yb - 24, "section to scale; h is the mean roof height")
        return yb - 30
    rise = L * math.tan(th)
    s_ = min(150.0 / L, 70.0 / (h + rise / 2 + 1e-9))
    yb = top - 34 - (h + rise / 2) * s_
    out = yb
    for k, (g, word) in enumerate(((0, "wind against the high edge (0 degrees)"), (180, "wind against the low edge (180 degrees)"))):
        x0 = LM + 40 + k * 250
        xa, xb = x0, x0 + L * s_                              # high edge at the left in both sections
        ya, yb2 = yb + (h + rise / 2) * s_, yb + (h - rise / 2) * s_
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.line(x0 - 14, yb, xb + 14, yb)
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.8)
        for f in (0.12, 0.88):
            xx = xa + (xb - xa) * f
            c.line(xx, yb, xx, ya + (yb2 - ya) * f)
        c.setLineWidth(2.2); c.line(xa, ya, xb, yb2)
        xm, ym = (xa + xb) / 2, (ya + yb2) / 2
        c.setLineWidth(0.5); c.line(xm, ym - 4, xm, ym + 10)
        c.setFillColorRGB(*LOADC); c.setStrokeColorRGB(*LOADC); c.setFont(FR, 6.5)
        left, right = ("windward half, CNW", "leeward half, CNL") if g == 0 else ("leeward half, CNL", "windward half, CNW")
        c.drawCentredString((xa + xm) / 2, max(ya, ym) + 14, left); c.drawCentredString((xm + xb) / 2, ym + 14, right)
        c.setLineWidth(0.8)
        if g == 0:
            _arrow(c, xa - 34, ya + 2, xa - 8, ya + 2, head=3.2)
        else:
            _arrow(c, xb + 34, yb2 + 8, xb + 8, yb2 + 8, head=3.2)
        c.setFillColorRGB(*GREY); c.setFont(FR, 6); c.drawCentredString(xm, yb - 22, word)
        memberart._dim_h(c, xa, xb, yb - 6, f"L {L:g} ft", FR, ext_from=yb)
        if k == 0:
            memberart._dim_v(c, yb, ym, xa - 16, f"h {h:g} ft", FR)
        out = yb - 30
    return out


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
    cant = d.get("cant")
    c.setStrokeColorRGB(*GREY); c.setLineWidth(2.4); c.line(x0, y0 - 3, x0, y1 + 3)
    if not cant:
        c.line(x1, y0 - 3, x1, y1 + 3)                                                         # lines of resistance
    else:                                                                                       # the free (open) edge
        c.setStrokeColorRGB(*INK); c.setLineWidth(0.6); c.setDash(3, 2); c.line(x1, y0, x1, y1); c.setDash()
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.6)
    n = max(6, int(w_ / 16))
    for k in range(n + 1):
        _arrow_down(c, x0 + w_ * k / n, y1 + 16, y1 + 3)
    c.line(x0, y1 + 16, x1, y1 + 16)
    c.setFont(FR, 6.5); c.drawCentredString((x0 + x1) / 2, y1 + 19, f"w = {d['w']:,.0f} plf")
    for x, al in (((x0, "right"),) if cant else ((x0, "right"), (x1, "left"))):
        _arrow(c, x + (-7 if al == "right" else 7), y0 + h_ * 0.35, x + (-7 if al == "right" else 7), y0 + h_ * 0.65, head=3.5)
        t = [f"R = {d['R']:,.0f} lb", f"v = {d['v']:,.0f} plf"]
        for j, tt in enumerate(t):
            (c.drawRightString if al == "right" else c.drawString)(x + (-12 if al == "right" else 12), y0 + h_ * 0.55 - j * 8, tt)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    at = " at the line" if cant else ""
    tC, tT = f"chord, C = {d['T']:,.0f} lb{at}", f"chord, T = {d['T']:,.0f} lb{at}"
    fits = c.stringWidth(tC, FR, 6) <= w_ - 8
    if fits and d.get("opening"):                                               # a clear stretch of chord between the openings' framing
        cuts = sorted([(r_["xs"], r_["xe"]) for r_ in (d.get("regions") or [d["opening"]])])
        edges = [0.0] + [v_ for ab_ in cuts for v_ in ab_] + [L]
        fits = max(edges[k + 1] - edges[k] for k in range(0, len(edges), 2)) * s > c.stringWidth(tC, FR, 6) + 6
    if not fits:                                                                # the chord forces beside the line of resistance
        c.drawRightString(x0 - 8, y1 - 3, tC); c.drawRightString(x0 - 8, y0 - 1, tT)
    else:
        xm = (x0 + x1) / 2
        op = d.get("opening")
        if op:                                                                  # clear of the openings and their framing
            cuts = sorted([(r_["xs"], r_["xe"]) for r_ in (d.get("regions") or [op])])
            edges = [0.0] + [v_ for ab_ in cuts for v_ in ab_] + [L]
            segs = [(edges[k], edges[k + 1]) for k in range(0, len(edges), 2)]
            a_, b_ = max(segs, key=lambda q: q[1] - q[0])
            xm = x0 + (a_ + b_) / 2 * s
            half = c.stringWidth(tC, FR, 6) / 2 + 3
            xm = min(max(xm, x0 + a_ * s + half), x0 + b_ * s - half) if (b_ - a_) * s > 2 * half else xm
        c.drawCentredString(xm, y1 - 9, tC)
        c.drawCentredString(xm, y0 + 4, tT)
    memberart._dim_h(c, x0, x1, y0 - 10, f"L' = {L:g} ft" if cant else f"L = {L:g} ft", FR, ext_from=y0)
    memberart._dim_v(c, y0, y1, x1 + 62, f"W' = {W:g} ft" if cant else f"W = {W:g} ft", FR, ext_from=x1 + 4)
    if cant:
        c.setFont(FR, 6); c.drawString(x1 + 4, y0 + h_ / 2 - 2, "open edge")
    op = d.get("opening")
    regs = d.get("regions") or ([op] if op else [])
    for rg in regs:
        _opening_in_plan(c, rg, x0, y0, s, small=True)
    _small(c, (LM + RM) / 2, y0 - 28, "plan, to scale; the heavy line at the left is the line of resistance, the dashed edge is open" if cant else
           "plan, to scale; heavy lines at the ends are the lines of resistance")
    if not regs:
        return y0 - 34
    y_ = y0 - 46
    for k, rg in enumerate(regs, 1):
        y_ = _opening_enlarged(c, y_, rg, d, title=("REGION AROUND THE OPENING" + ("S" if rg.get("multi") else "") + ", ENLARGED"
                                                     + (f" ({k} OF {len(regs)})" if len(regs) > 1 else ""))) - 12
    return y_ + 12


def _opening_in_plan(c, op, x0, y0, s, small=False, sy=None, holes=None, yt=None):
    """The opening(s) of one region, their framing (members across the depth at the ends, along each opening side) extended into the
    diaphragm, and the region of the force-transfer analysis dashed. (x0, y0): the plan's corner at the support / line of resistance and the
    chord the openings are measured from. holes: [(y0, b)] in the same units as op (default: the region's openings)."""
    sy = sy or s
    holes = holes or [(o["y0"], o["b"]) for o in (op.get("openings") or [dict(y0=op["y0"], b=op["b"])])]
    ox, ow = x0 + op["x0"] * s, op["a"] * s
    rx0, rx1 = x0 + op["xs"] * s, x0 + op["xe"] * s
    yt = yt if yt is not None else y0 + (sum(op["piers"]) + sum(b_ for _, b_ in holes) if op.get("piers") else op["d1"] + op["b"] + op["d2"]) * sy
    tw = 1.6 if small else 3.2                                          # drawn width of the framing members
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.5); c.setDash(2.5, 2); c.rect(rx0, y0, rx1 - rx0, yt - y0, fill=0, stroke=1); c.setDash()
    for hy, hb in holes:                                                # along the opening sides, over the region
        for yy in (y0 + hy * sy, y0 + (hy + hb) * sy):
            memberart.wood_elevation(c, rx0, yy - tw / 2, rx1 - rx0, tw, seed=int(yy) % 9)
    for xx in (ox, ox + ow):                                            # across the depth at the opening ends, chord to chord
        c.saveState(); c.translate(xx + tw / 2, y0); c.rotate(90)
        memberart.wood_elevation(c, 0, 0, yt - y0, tw, seed=int(xx) % 7)
        c.restoreState()
    for hy, hb in holes:
        oy, oh = y0 + hy * sy, hb * sy
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*INK); c.setLineWidth(0.6)
        c.rect(ox + tw / 2, oy + tw / 2, ow - tw, oh - tw, fill=1, stroke=1)          # the hole, with the usual cross
        c.setLineWidth(0.35); c.line(ox + tw / 2, oy + tw / 2, ox + ow - tw / 2, oy + oh - tw / 2); c.line(ox + tw / 2, oy + oh - tw / 2, ox + ow - tw / 2, oy + tw / 2)


def _opening_enlarged(c, top, op, d, title="REGION AROUND THE OPENING, ENLARGED"):
    """Enlarged plan of the region around the opening(s), depth W by Lr: the zones of the force-transfer analysis with their unit shears (the
    strips beside and between openings, their corner zones, the full depth each side of the openings), the framing at the openings drawn as
    wood members with their forces, and every length dimensioned."""
    holes = op.get("openings") or [dict(y0=op["y0"], b=op["b"])]
    piers = op.get("piers") or [op["d1"], op["d2"]]
    rows_ = []                                                          # (kind, size, index) from the first chord up
    for i, dpr in enumerate(piers):
        rows_.append(("strip", dpr, i))
        if i < len(holes):
            rows_.append(("hole", holes[i]["b"], i))
    W = sum(r_[1] for r_ in rows_)
    Lr = op["Lr"]
    _sketch_title(c, LM + 6, top, title)
    s = sy = min(300.0 / Lr, 140.0 / W)
    to_scale = True
    if min(op["e1"], op["a"], op["e2"]) * s < 30 or min(r_[1] for r_ in rows_) * sy < 14:     # too small to label: lengths not to scale
        to_scale = False
        xs_ = [max(44.0, min(110.0, v_ * 300.0 / Lr)) for v_ in (op["e1"], op["a"], op["e2"])]
        ys_ = [max(16.0, min(50.0, r_[1] * 140.0 / W)) for r_ in rows_]
    else:
        xs_ = [v_ * s for v_ in (op["e1"], op["a"], op["e2"])]
        ys_ = [r_[1] * sy for r_ in rows_]
    wr, hr = sum(xs_), sum(ys_)
    x0 = (LM + RM) / 2 - wr / 2 + 10
    y1 = top - 30
    y0 = y1 - hr
    xs = [x0, x0 + xs_[0], x0 + xs_[0] + xs_[1], x0 + wr]
    ys = [y0]
    for h_ in ys_:
        ys.append(ys[-1] + h_)
    sts = op["strips"]
    zone = {}
    for j, (kind, _, i) in enumerate(rows_):
        if kind == "strip":
            zone[(0, j)] = zone[(2, j)] = sts[i]["vc"]; zone[(1, j)] = sts[i]["v"]
        else:
            zone[(0, j)] = zone[(2, j)] = op["va"]
    for (i, j), v in zone.items():                                      # sheathing zones, shaded by unit shear
        f = 0.97 - 0.16 * min(1.0, abs(v) / max(op["v_max"], 1.0))
        c.setFillColorRGB(f, f + 0.01, f + 0.03); c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4)
        c.rect(xs[i], ys[j], xs[i + 1] - xs[i], ys[j + 1] - ys[j], fill=1, stroke=1)
    c.setStrokeColorRGB(*INK); c.setLineWidth(1.8); c.line(x0, y0, x0 + wr, y0); c.line(x0, y1, x0 + wr, y1)        # the chords
    hole_px = [(ys[j] - y0, ys[j + 1] - ys[j]) for j, r_ in enumerate(rows_) if r_[0] == "hole"]
    _opening_in_plan(c, dict(op, x0=xs_[0], xs=0.0, xe=wr, a=xs_[1]), x0, y0, 1.0, holes=hole_px, yt=y1)
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    for (i, j), v in zone.items():
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        t = f"{v:,.0f} plf"
        if c.stringWidth(t, FR, 6) < xs[i + 1] - xs[i] - 4 and ys[j + 1] - ys[j] > 9:
            c.drawCentredString(cx, cy - 2, t)
    # member forces: along the opening sides at the right of each opening, across the depth at the top
    c.setFillColorRGB(*INK); c.setFont(FR, 6)
    for j, r_ in enumerate(rows_):
        if r_[0] == "hole":
            c.drawString(x0 + wr + 6, (ys[j] + ys[j + 1]) / 2 - 2, f"{op['N_side']:,.0f} lb each side")
    if xs[2] - xs[1] >= 34:
        c.drawCentredString(xs[1], y1 + 5, f"{op['F_end']:,.0f} lb"); c.drawCentredString(xs[2], y1 + 5, f"{op['F_end']:,.0f} lb")
    else:
        c.drawCentredString((xs[1] + xs[2]) / 2, y1 + 5, f"{op['F_end']:,.0f} lb each")
    c.setFont(FR, 5.5); c.setFillColorRGB(*GREY)
    c.drawCentredString((xs[1] + xs[2]) / 2, y1 + 13, "members across the depth")
    # shear V at each end of the region (arrows); dimensions across the depth on the left
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.6)
    za, zb = ys[0] + (ys[1] - ys[0]) * 0.25, ys[0] + (ys[1] - ys[0]) * 0.75
    _arrow(c, x0 - 5, zb, x0 - 5, za, head=3.0)
    za, zb = ys[-2] + (ys[-1] - ys[-2]) * 0.25, ys[-2] + (ys[-1] - ys[-2]) * 0.75
    _arrow(c, x0 + wr + 5, za, x0 + wr + 5, zb, head=3.0)
    c.setFont(FR, 6)
    c.drawString(x0 + wr + 6, y1 + 5, f"V = {op['V']:,.0f} lb")
    g = lambda v: f"{v:g}"
    yb = y0 - 9
    memberart._dim_h(c, xs[0], xs[1], yb, f"e1 = {g(op['e1'])}", FR, ext_from=y0)
    memberart._dim_h(c, xs[1], xs[2], yb, f"a = {g(op['a'])}", FR, ext_from=y0)
    memberart._dim_h(c, xs[2], xs[3], yb, f"e2 = {g(op['e2'])}", FR, ext_from=y0)
    memberart._dim_h(c, xs[0], xs[3], yb - 14, f"Lr = {g(Lr)} ft", FR)
    xl = x0 - 14
    for j, r_ in enumerate(rows_):
        lab = (f"d = {g(r_[1])}" if r_[0] == "strip" else f"b = {g(r_[1])}")
        memberart._dim_v(c, ys[j], ys[j + 1], xl, lab, FR, ext_from=x0)
    _small(c, (LM + RM) / 2, yb - 30, ("enlarged plan to scale" if to_scale else "enlarged plan, not to scale") + ", lengths in ft; unit shear in each zone of sheathing; framing at the openings drawn as wood with the largest "
           "axial force of the members along the opening sides (right) and across the depth (top), tension or compression as the load reverses; chords at top and bottom")
    return yb - 44


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


def _hurricane_tie_picture(c, top, d):
    """Hurricane tie, to scale: a section across the wall at a rafter: the double top plate cut in end grain on the stud below (broken
    off), the rafter or truss chord in elevation bearing on the plate, cut short with break lines, and the tie on its face, nailed to the
    rafter, the plates and (where the model calls for it) the stud; the uplift and lateral loads as arrows (F1 along the plate, into the page)."""
    import math as _m
    sc = 11.0
    cx, yp = LM + 170, top - 120                             # plate top at the wall centre
    pw, pt = 3.5, 1.5
    memberart.wood_section(c, cx, yp - pt * sc / 2, pw * sc, pt * sc, pw, pt)                     # upper top plate
    memberart.wood_section(c, cx, yp - 1.5 * pt * sc, pw * sc, pt * sc, pw, pt)                   # lower top plate
    c.saveState(); c.translate(cx - pw * sc / 2, yp - 2 * pt * sc - 6.0 * sc); c.rotate(90)
    memberart.wood_elevation(c, 0, -pw * sc, 6.0 * sc, pw * sc); c.restoreState()                # stud below, grain vertical
    memberart._break_h(c, cx - pw * sc / 2, cx + pw * sc / 2, yp - 2 * pt * sc - 6.0 * sc)
    ang = _m.atan2(5, 12)                                     # rafter at 5:12, bearing on the plate (depiction)
    rd, rlen = 5.5, 16.0
    c.saveState(); c.translate(cx - 6.5 * sc * _m.cos(ang), yp - 6.5 * sc * _m.sin(ang)); c.rotate(_m.degrees(ang))
    memberart.wood_elevation(c, 0, 0, rlen * sc, rd * sc)
    c.restoreState()
    # the rafter's seat (bird's mouth) on the plate: the plates drawn again in front of the rafter
    memberart.wood_section(c, cx, yp - pt * sc / 2, pw * sc, pt * sc, pw, pt)
    memberart.wood_section(c, cx, yp - 1.5 * pt * sc, pw * sc, pt * sc, pw, pt)
    # the tie: a steel strip on the near face, over the rafter and down the plates (and the stud)
    c.setFillColorRGB(0.72, 0.76, 0.81); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
    w_ = 1.6 * sc
    yb_ = yp - 2 * pt * sc - (4.0 * sc if d.get("studs") else 0.0)
    c.rect(cx + 0.3 * sc, yb_, w_, yp - yb_ + 3.2 * sc, fill=1, stroke=1)
    c.setFillColorRGB(1, 1, 1); c.setLineWidth(0.4)
    ys = [yp + 1.6 * sc, yp + 2.6 * sc] if d.get("rafter") else []
    ys += [yp - 0.75 * sc, yp - 2.25 * sc] if d.get("plates") else []
    ys += [yp - 2 * pt * sc - 1.5 * sc, yp - 2 * pt * sc - 3.0 * sc] if d.get("studs") else []
    for y_ in ys:
        c.circle(cx + 0.3 * sc + w_ / 2, y_, 1.1, fill=1, stroke=1)
    _knockout(c, cx + 0.3 * sc + w_ + 4, yp + 3.0 * sc, d["model"], 6.5, left=True, color=INK)
    # loads
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9); c.setFont(FR, 6.5)
    if d.get("uplift"):
        _arrow(c, cx - 1.0 * sc, yp + 4.5 * sc, cx - 1.0 * sc, yp + 8.5 * sc, head=3)
        c.drawRightString(cx - 1.0 * sc - 3, yp + 7.0 * sc, f"uplift {d['uplift']:,.0f} lb")
    if d.get("F2"):                                         # across the plate, on the inside face below the rafter
        xr_ = cx + 0.3 * sc + w_
        _arrow(c, xr_ + 6.0 * sc, yp - 2.4 * sc, xr_ + 1.0, yp - 2.4 * sc, head=3)
        c.drawString(xr_ + 6.3 * sc, yp - 2.4 * sc - 2, f"F2 {d['F2']:,.0f} lb, across the plate")
    if d.get("F1"):
        xo, yo = cx + pw * sc / 2 + 7.5 * sc, yp - 5.0 * sc
        c.circle(xo, yo, 3.2, fill=0, stroke=1); c.line(xo - 2.2, yo - 2.2, xo + 2.2, yo + 2.2); c.line(xo - 2.2, yo + 2.2, xo + 2.2, yo - 2.2)
        c.drawString(xo + 6, yo - 2, f"F1 {d['F1']:,.0f} lb, along the plate")
    _small(c, cx + 40, yp - 2 * pt * sc - 6.0 * sc - 14, "section across the wall at a rafter, to scale (rafter slope shown 5:12); loads at the ASD level")
    return yp - 2 * pt * sc - 6.0 * sc - 22


def _mixed(x):
    """5.5 -> '5 1/2', 0.625 -> '5/8', 7.0 -> '7' (to 1/16 in.)."""
    from fractions import Fraction
    fr = Fraction(round(x * 16), 16)
    w, r = divmod(fr, 1)
    return (f"{w}" if w else "") + (" " if w and r else "") + (f"{r.numerator}/{r.denominator}" if r else "") or "0"


def _post_dims(label):
    """Actual size (b, d) in inches of a post label of the post base table ('4x6', 'Rough 6x6', '5 1/8 x 6', 'Double 2x4')."""
    import re as _re
    from . import simpson as _s
    lab = label.strip()
    if lab.lower().startswith("rough"):
        a, b = _re.findall(r"\d+", lab)[:2]
        return float(a), float(b)
    if lab.lower().startswith("double 2x"):
        return 3.0, _lumber_dims("2x" + lab.split("2x")[1])[1]
    if " x " in lab:
        a, b = lab.split(" x ")
        return _s._in(a), _s._in(b)
    a, b = lab.lower().split("x")
    act = {2: 1.5, 3: 2.5, 4: 3.5, 5: 4.5, 6: 5.5, 8: 7.25, 10: 9.25, 12: 11.25}
    if int(a) >= 6 and int(b) >= 6:                         # timbers 5 in. and over: nominal less 1/2 in. (NDS Supplement Table 1B)
        return int(a) - 0.5, int(b) - 0.5
    return act[int(a)], act.get(int(b), int(b) - 0.5)


def _steel_strip(c, x, y, w, h, cut=False):
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    c.setFillColorRGB(*(memberart.STEEL_CUT if cut else memberart.STEEL_FILL))
    c.rect(x, y, w, h, fill=1, stroke=1)


def _nail_heads(c, x, y, w, h, n, r=0.9):
    """n nail heads in two staggered columns on a strip seen face on."""
    if n <= 0:
        return
    rows = (n + 1) // 2
    c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
    for k in range(n):
        col, rw = k % 2, k // 2
        c.circle(x + w * (0.3 + 0.4 * col), y + h * (0.12 + 0.76 * (rw + 0.5 * col) / max(rows, 1)), r, fill=1, stroke=1)


def _bolt_heads(c, pts, d):
    """Bolt heads seen end on: a hexagon around the bolt end."""
    import math as _m
    c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
    for (x, y) in pts:
        c.setFillColorRGB(0.42, 0.47, 0.54)
        p = c.beginPath()
        for k in range(6):
            a = _m.radians(30 + 60 * k)
            (p.moveTo if k == 0 else p.lineTo)(x + 0.85 * d * _m.cos(a), y + 0.85 * d * _m.sin(a))
        p.close(); c.drawPath(p, fill=1, stroke=1)
        c.setFillColorRGB(0.70, 0.74, 0.79); c.circle(x, y, 0.45 * d, fill=1, stroke=1)


def _leader_notes(c, notes, tx):
    last = None
    c.setFont(FR, 6.2)
    for (y_, xt_, t_) in sorted(notes, key=lambda q: -q[0]):
        yy = y_ if last is None or last - y_ >= 9 else last - 9
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.35); c.line(xt_, y_, tx - 3, yy + 1.5)
        c.setFillColorRGB(*GREY); c.circle(xt_, y_, 0.7, fill=1, stroke=0)
        c.setFillColorRGB(*INK); c.drawString(tx, yy - 0.5, t_); last = yy
    return last


def _post_base_picture(c, top, d):
    """Adjustable standoff post base (ABA / ABU / ABW), to scale, two views. Left: elevation looking at a strap face: the concrete cut
    short below, the U base on the concrete, the 1 in. standoff, the post on it with its grain (broken off above), the strap up the post
    face with its nails or bolt heads; W and H dimensioned. Right: section through the post centre square to the straps: the straps cut
    (darker) on both faces, the base plate, the nut and washer on the anchor, the standoff plate over them, the anchor dashed in the
    concrete, the through bolts with heads and nuts where used; L and the 1 in. standoff dimensioned."""
    W, Ls, H = d["W"], d["L"], d["H"]
    pb, pd = _post_dims(d["post"])                          # post across the straps (b) and along them (d)
    t = {10: 0.134, 12: 0.105, 14: 0.075, 16: 0.06}.get(d["strap_ga"], 0.075)
    tb = {10: 0.134, 12: 0.105, 14: 0.075, 16: 0.06}.get(d["ga"], 0.075)
    hp = H + 6.0                                            # post shown above the base
    hc = 5.0                                                # concrete shown
    sc = min(7.0, 140.0 / (hp + 1.0 + hc + 2), 120.0 / (max(pb, pd) + 4))
    so = 1.0                                                # standoff, catalog p. 76
    ytop = top - 14
    yc = ytop - (hp + so + 0.4) * sc                        # top of the concrete
    T, TB = max(t * sc, 1.1), max(tb * sc, 1.1)
    from . import simpson as _sp
    for vx, wpost, view in ((LM + 95, pd, 1), (LM + 300, pb, 2)):
        cwid = wpost + 7.0
        memberart._concrete(c, vx - cwid * sc / 2, yc - hc * sc, cwid * sc, hc * sc, seed=11 + view)
        memberart._break_h(c, vx - cwid * sc / 2, vx + cwid * sc / 2, yc - hc * sc - 1)
        ya = yc + TB                                         # top of the U base
        yp = yc + so * sc                                    # post bottom on the standoff
        # anchor rod: nut and washer on the base, the rod dashed in the concrete
        Da = 0.625
        if view == 2:
            c.setDash(2, 1.4); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)
            c.line(vx - Da * sc / 2, ya, vx - Da * sc / 2, yc - (hc - 0.8) * sc); c.line(vx + Da * sc / 2, ya, vx + Da * sc / 2, yc - (hc - 0.8) * sc)
            c.setDash()
            c.setFillColorRGB(0.62, 0.66, 0.72); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
            c.rect(vx - 1.0 * sc, ya, 2.0 * sc, 0.12 * sc + 0.6, fill=1, stroke=1)
            c.setFillColorRGB(0.42, 0.47, 0.54); c.rect(vx - 0.5 * sc, ya + 0.12 * sc + 0.6, 1.0 * sc, 0.55 * sc, fill=1, stroke=1)
            c.setFillColorRGB(0.70, 0.74, 0.79); c.rect(vx - Da * sc / 2, ya + 0.67 * sc + 0.6, Da * sc, 0.2 * sc, fill=1, stroke=1)
        # the U base on the concrete and the standoff plate over the nut
        bw = (W if view == 2 else Ls) + 2 * t
        _steel_strip(c, vx - bw * sc / 2, yc, bw * sc, TB, cut=(view == 2))
        _steel_strip(c, vx - wpost * sc / 2, yp - TB, wpost * sc, TB, cut=(view == 2))
        if view == 2:
            for sg in (-1, 1):                               # standoff legs
                _steel_strip(c, vx + sg * (wpost / 2 - 0.4) * sc - (0.4 * sc if sg < 0 else 0) + (0 if sg < 0 else 0), ya, 0.4 * sc, yp - TB - ya, cut=True)
        # the post
        c.saveState(); c.translate(vx - wpost * sc / 2, yp); c.rotate(90)
        memberart.wood_elevation(c, 0, -wpost * sc, hp * sc, wpost * sc, seed=3 + view); c.restoreState()
        memberart._break_h(c, vx - wpost * sc / 2, vx + wpost * sc / 2, yp + hp * sc - 1)
        if view == 1:                                        # strap face on
            sw = min(Ls, wpost)
            _steel_strip(c, vx - sw * sc / 2, yc, sw * sc, H * sc)
            n_ = int(d["nails"].split(")")[0].strip("(")) // 2
            if d.get("bolts") and d.get("bolt"):
                nb = d["bolt"][0]
                _bolt_heads(c, [(vx, yp + H * sc * (0.35 + 0.4 * k / max(nb - 1, 1))) for k in range(nb)], 0.5 * sc)
            else:
                _nail_heads(c, vx - sw * sc / 2, yp, sw * sc, H * sc - so * sc, n_)
            memberart._dim_h(c, vx - sw * sc / 2, vx + sw * sc / 2, yc - hc * sc - 12, f"L {d['L_txt']}", FR, ext_from=yc - hc * sc)
            memberart._dim_v(c, yc, yc + H * sc, vx - max(wpost, sw) * sc / 2 - 14, f"H {d['H_txt']}", FR, ext_from=vx - sw * sc / 2)
            _small(c, vx, yc - hc * sc - 30, "elevation, strap face on, to scale (in.)")
        else:                                                # straps cut on both faces
            for sg in (-1, 1):
                xs_ = vx + sg * wpost * sc / 2 + (0 if sg > 0 else -T)
                _steel_strip(c, xs_, yc, T, H * sc, cut=True)
            if d.get("bolts") and d.get("bolt"):
                nb = d["bolt"][0]
                for k in range(nb):
                    yb_ = yp + H * sc * (0.35 + 0.4 * k / max(nb - 1, 1))
                    memberart.bolt_side(c, vx - wpost * sc / 2 - T, yb_, vx + wpost * sc / 2 + T, yb_, 0.5 * sc)
            else:                                            # nails driven through the straps into the post
                c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
                for sg in (-1, 1):
                    for k in range(3):
                        yn_ = yp + (H - so) * sc * (0.25 + 0.25 * k)
                        c.line(vx + sg * (wpost / 2) * sc, yn_, vx + sg * (wpost / 2 - 2.5) * sc, yn_)
                c.setDash()
            memberart._dim_h(c, vx - W * sc / 2, vx + W * sc / 2, yc - hc * sc - 12, f"W {d['W_txt']}", FR, ext_from=yc - hc * sc)
            memberart._dim_v(c, yc, yp, vx - cwid * sc / 2 - 6, "1 standoff", FR, ext_from=vx - wpost * sc / 2 - T)
            _small(c, vx, yc - hc * sc - 30, "section through the post centre, to scale (in.); anchor dashed")
            tx = vx + cwid * sc / 2 + 50
            _leader_notes(c, [(yp + hp * sc * 0.7, vx + wpost * sc * 0.3, f"{d['post']} post, broken off"),
                              (yc + H * sc * 0.8, vx + wpost * sc / 2 + T, f"{d['model']} strap, {d['strap_ga']} ga"),
                              (yp - TB / 2, vx - wpost * sc * 0.35, "standoff plate"),
                              (ya + 0.5 * sc, vx + 0.5 * sc, "nut and washer on the anchor"),
                              (yc - hc * sc * 0.5, vx + Da * sc / 2, f"anchor, {d['anchor']} in. dia., by the designer"),
                              (yc - hc * sc + 6, vx + cwid * sc / 2 - 3, "concrete")], tx)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawCentredString(LM + 200, ytop + 6, f"{d['model']} on a {d['post']} post" + (", bolted" if d.get("bolts") else ", nailed"))
    return yc - hc * sc - 38


def _column_cap_picture(c, top, d):
    """Column or post cap, to scale, two views. Left: elevation along the beam: the post below with its grain (broken off), the beam over
    it (broken off at each end, or ending on an end cap, or two beams meeting at a splice), the cap plate between, the beam straps and the
    post straps face on with their bolt heads (CC series) or nails (BC). Right: section across the beam: the beam cut in end grain inside
    the U, the straps and the cap plate cut (darker), the post below with its straps cut, the through bolts with heads and nuts. W1, W2,
    H1 and L dimensioned."""
    dm, ser = d["dims"], d["series"]
    bc = ser == "BC"
    bw, pw, bd = d["beam_width"], d["post_width"], d["beam_depth"]
    t = {3: 0.239, 7: 0.179, 18: 0.048}.get(d["ga"], 0.1)
    Lc = dm["L"]
    H1 = dm["H1"]
    H2 = dm.get("H2") or (H1 if bc else 8.5)                # CC post straps 1-1/2 + 3 + 4 in. long (p. 100 figure)
    hp = H2 + 6.0
    sc = min(6.5, 150.0 / (bd + hp + 2), 110.0 / (Lc + 12))
    T = max(t * sc, 1.0)
    ytop = top - 16
    yb = ytop - bd * sc                                     # beam bottom = cap plate top
    # ---------------- elevation along the beam
    vx = LM + 120
    beam_len = Lc + 10.0
    end = ser in ("ECC", "ECCU")
    if end:
        beam_len = Lc + 6.0
    x0 = vx - beam_len * sc / 2
    x1 = vx + beam_len * sc / 2
    pxc = (x1 - pw * sc / 2) if end else vx                 # post centre: under the beam end for an end cap
    if d.get("spliced"):
        memberart.wood_elevation(c, x0, yb, (x1 - x0) / 2, bd * sc, seed=4)
        memberart.wood_elevation(c, vx, yb, (x1 - x0) / 2, bd * sc, seed=9)
        c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.8); c.line(vx, yb, vx, yb + bd * sc)
    else:
        memberart.wood_elevation(c, x0, yb, x1 - x0, bd * sc, seed=4)
    _break_v(c, x0, yb - 2, yb + bd * sc + 2)
    if not end:
        _break_v(c, x1, yb - 2, yb + bd * sc + 2)
    # post below (its width along the beam drawn as the post width; the cap is square to it)
    pl = pw
    c.saveState(); c.translate(pxc - pl * sc / 2, yb - T - hp * sc); c.rotate(90)
    memberart.wood_elevation(c, 0, -pl * sc, hp * sc, pl * sc, seed=6); c.restoreState()
    memberart._break_h(c, pxc - pl * sc / 2, pxc + pl * sc / 2, yb - T - hp * sc - 1)
    # cap plate seen edge on, the straps face on
    xc0 = (x1 - Lc * sc) if end else (vx - Lc * sc / 2)
    _steel_strip(c, xc0, yb - T, Lc * sc, T)
    sw_b = Lc if bc else Lc
    _steel_strip(c, xc0, yb, sw_b * sc, H1 * sc)
    psw = min(pl, (2.75 if dm.get("bolt", 0) < 0.7 else 3.0) if not bc else pl * 0.7)   # post strap 2-3/4 in. (5/8 in. bolts), 3 in. (3/4), p. 100
    _steel_strip(c, pxc - psw * sc / 2, yb - T - H2 * sc, psw * sc, H2 * sc)
    if bc:
        _nail_heads(c, xc0, yb, sw_b * sc, H1 * sc, 6)
        _nail_heads(c, pxc - psw * sc / 2, yb - T - H2 * sc, psw * sc, H2 * sc, 4)
    else:
        nb = dm["beam_bolts"]
        cols = 1 if nb <= 2 else 2
        rows_ = 1 if nb == 1 else 2 if nb in (2, 4) else nb // cols
        db = dm["bolt"] * sc
        pts = []                                            # bolts 1-1/4 in. from the plate ends (p. 100), two rows in H1
        xs_ = [xc0 + 1.25 * sc, xc0 + (Lc - 1.25) * sc] if cols == 2 else [xc0 + (Lc - 1.25) * sc if end else xc0 + Lc * sc / 2]
        for xq in xs_:
            for j in range(rows_):
                if len(pts) < nb:
                    pts.append((xq, yb + H1 * sc * (0.3 + 0.4 * j) if rows_ > 1 else yb + H1 * sc * 0.5))
        _bolt_heads(c, pts, db)
        _bolt_heads(c, [(pxc, yb - T - k_ * sc) for k_ in (4.0, 7.0)][:dm["post_bolts"]], db)   # 4 and 7 in. below the cap, p. 100
    memberart._dim_h(c, xc0, xc0 + Lc * sc, ytop + 10, f"L {_mixed(Lc)}", FR, ext_from=ytop)
    memberart._dim_v(c, yb, yb + H1 * sc, x0 - 12, f"H1 {_mixed(H1)}", FR, ext_from=xc0)
    _small(c, vx, yb - T - hp * sc - 18, "elevation along the beam, to scale (in.)")
    # ---------------- section across the beam
    sx = LM + 330
    memberart.wood_section(c, sx, yb + bd * sc / 2, bw * sc, bd * sc, bw, bd)
    c.saveState(); c.translate(sx - pw * sc / 2, yb - T - hp * sc); c.rotate(90)
    memberart.wood_elevation(c, 0, -pw * sc, hp * sc, pw * sc, seed=8); c.restoreState()
    memberart._break_h(c, sx - pw * sc / 2, sx + pw * sc / 2, yb - T - hp * sc - 1)
    W1, W2 = dm["W1"], dm["W2"]
    _steel_strip(c, sx - max(W1, W2) * sc / 2 - T, yb - T, (max(W1, W2) + 0) * sc + 2 * T, T, cut=True)
    for sg in (-1, 1):
        _steel_strip(c, sx + sg * W1 * sc / 2 + (0 if sg > 0 else -T), yb, T, H1 * sc, cut=True)
        _steel_strip(c, sx + sg * W2 * sc / 2 + (0 if sg > 0 else -T), yb - T - H2 * sc, T, H2 * sc, cut=True)
    if bc:
        c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
        for sg in (-1, 1):
            for k in range(2):
                yn_ = yb + H1 * sc * (0.35 + 0.3 * k); c.line(sx + sg * W1 * sc / 2, yn_, sx + sg * (W1 / 2 - 2.0) * sc, yn_)
                yn_ = yb - T - H2 * sc * (0.35 + 0.3 * k); c.line(sx + sg * W2 * sc / 2, yn_, sx + sg * (W2 / 2 - 2.0) * sc, yn_)
        c.setDash()
    else:
        db = dm["bolt"] * sc
        memberart.bolt_side(c, sx - W1 * sc / 2 - T, yb + H1 * sc * 0.5, sx + W1 * sc / 2 + T, yb + H1 * sc * 0.5, db)
        memberart.bolt_side(c, sx - W2 * sc / 2 - T, yb - T - H2 * sc * 0.5, sx + W2 * sc / 2 + T, yb - T - H2 * sc * 0.5, db)
    if c.stringWidth(f"W1 {_mixed(W1)}", FR, 6) > W1 * sc - 4:       # narrow: the figure beside the dimension
        memberart._dim_h(c, sx - W1 * sc / 2, sx + W1 * sc / 2, ytop + 10, "", FR, ext_from=ytop)
        c.setFont(FR, 6); c.setFillColorRGB(0.23, 0.28, 0.34); c.drawString(sx + W1 * sc / 2 + 4, ytop + 8, f"W1 {_mixed(W1)}")
    else:
        memberart._dim_h(c, sx - W1 * sc / 2, sx + W1 * sc / 2, ytop + 10, f"W1 {_mixed(W1)}", FR, ext_from=ytop)
    memberart._dim_h(c, sx - W2 * sc / 2, sx + W2 * sc / 2, yb - T - hp * sc - 10, f"W2 {_mixed(W2)}", FR, ext_from=yb - T - hp * sc)
    _small(c, sx, yb - T - hp * sc - 28, "section across the beam, to scale (in.)")
    tx = sx + max(W1, W2) * sc / 2 + 55
    _leader_notes(c, [(yb + bd * sc * 0.85, sx + bw * sc * 0.25, f"beam {_mixed(bw)} x {_mixed(bd)}"),
                      (yb + H1 * sc * 0.8, sx + W1 * sc / 2 + T, f"{d['model']}, {d['ga']} ga"),
                      (yb - T / 2, sx + max(W1, W2) * sc / 2 - 2, "cap plate"),
                      (yb - T - H2 * sc * 0.5, sx + W2 * sc / 2 + T + 3, d["bolt_txt"] or "nails, as the catalog lists"),
                      (yb - T - hp * sc * 0.75, sx - pw * sc * 0.2, f"post {_mixed(pw)} across the beam, broken off")], tx)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawCentredString(LM + 225, ytop + 22, d["model"] + (", beams spliced over the post" if d.get("spliced") else ""))
    return yb - T - hp * sc - 36


def _strap_picture(c, top, d):
    """Strap tie in tension, to scale. Left: elevation looking at the strap face on two wood members end to end (with the clear span
    between them for a coiled strap), each broken off at its far end, the strap over both with its nails (or bolts) in each member, the
    tension arrows; the strap length, or the end lengths and clear span, dimensioned. Right: section across the strap on the member: the
    member in end grain, the strap at its thickness, a nail driven into the member (dashed in the wood)."""
    W, ga = d["W"], d["ga"]
    t = {10: 0.134, 12: 0.105, 14: 0.075, 16: 0.06, 18: 0.048, 20: 0.036, 22: 0.030}.get(ga, 0.06)
    if d["coil"]:
        e, cl = float(d["end"] or 12), float(d["clear"] or 0.0)
        Ls = 2 * e + cl
    else:
        Ls, cl = d["L"], 0.0
        e = Ls / 2
    mem_d = max(5.5, W + 2.5)                                # member face shown (depth), depiction
    extra = 6.0
    total = Ls + 2 * extra
    sc = min(8.0, (RM - LM - 210) / total)
    x0 = LM + 30
    ym = top - 30 - mem_d * sc / 2
    yb = ym - mem_d * sc / 2
    xa = x0 + extra * sc                                     # strap start
    xm1 = xa + e * sc                                        # end of member 1 (the joint, or the start of the clear span)
    xm2 = xm1 + cl * sc
    memberart.wood_elevation(c, x0, yb, xm1 - x0, mem_d * sc, seed=5)
    memberart.wood_elevation(c, xm2, yb, x0 + total * sc - xm2, mem_d * sc, seed=12)
    _break_v(c, x0, yb - 2, yb + mem_d * sc + 2)
    _break_v(c, x0 + total * sc, yb - 2, yb + mem_d * sc + 2)
    c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.8)
    c.line(xm1, yb, xm1, yb + mem_d * sc); c.line(xm2, yb, xm2, yb + mem_d * sc)
    sw = W * sc
    _steel_strip(c, xa, ym - sw / 2, Ls * sc, sw)
    nh = d["n"] // 2
    if d.get("bolts"):
        _bolt_heads(c, [(xa + e * sc * (k + 0.5) / nh, ym) for k in range(nh)] + [(xm2 + e * sc * (k + 0.5) / nh, ym) for k in range(nh)], 0.5 * sc)
    else:
        c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.35)
        rr = max(0.075 * sc, 0.7)
        for xs_ in (xa, xm2):
            for k in range(nh):                              # two staggered rows along the strap in each member
                xq = xs_ + (k + 0.5) * (e - 1.0) * sc / nh + 0.5 * sc
                yq = ym + (sw * 0.22 if k % 2 == 0 else -sw * 0.22) if W >= 1.2 else ym
                c.circle(xq, yq, rr, fill=1, stroke=1)
    c.setStrokeColorRGB(*LOADC); c.setFillColorRGB(*LOADC); c.setLineWidth(0.9); c.setFont(FR, 6.5)
    _arrow(c, x0 + 2 * sc, ym + mem_d * sc / 2 + 8, x0 - 8, ym + mem_d * sc / 2 + 8, head=3)
    _arrow(c, x0 + total * sc - 2 * sc, ym + mem_d * sc / 2 + 8, x0 + total * sc + 8, ym + mem_d * sc / 2 + 8, head=3)
    c.drawCentredString(x0 + total * sc / 2, ym + mem_d * sc / 2 + 6, f"T = {d['tension']:,.0f} lb")
    if d["coil"]:
        memberart._dim_h(c, xa, xm1, yb - 12, f"end {e:g}", FR, ext_from=yb)
        if cl > 0:
            memberart._dim_h(c, xm1, xm2, yb - 12, f"clear {cl:g}", FR, ext_from=yb)
        memberart._dim_h(c, xm2, xm2 + e * sc, yb - 12, f"end {e:g}", FR, ext_from=yb)
        memberart._dim_h(c, xa, xa + Ls * sc, yb - 28, f"cut length {Ls:g}", FR, ext_from=yb - 12)
    else:
        memberart._dim_h(c, xa, xa + Ls * sc, yb - 12, f"L {_mixed(Ls)}", FR, ext_from=ym - sw / 2)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawCentredString(x0 + total * sc / 2, ym + mem_d * sc / 2 + 18, f"{d['model']}, {ga} ga, {_mixed(W)} in. wide; {d['fast']}")
    _small(c, x0 + total * sc / 2, yb - 44, "elevation, strap face on, to scale (in.); half the fasteners in each member")
    # section across the strap
    sx = RM - 70
    bsec, dsec = 1.5 * 2, mem_d                               # member shown 3 in. thick (depiction)
    s2 = min(9.0, 70.0 / dsec)
    memberart.wood_section(c, sx, ym, bsec * s2, dsec * s2, bsec, dsec)
    T = max(t * s2, 1.0)
    _steel_strip(c, sx - bsec * s2 / 2 - T, ym - W * s2 / 2, T, W * s2, cut=True)
    c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6)
    if d.get("bolts"):
        memberart.bolt_side(c, sx - bsec * s2 / 2 - T, ym, sx + bsec * s2 / 2, ym, 0.5 * s2)
    else:
        c.line(sx - bsec * s2 / 2 - T - 1.2, ym, sx - bsec * s2 / 2 - T, ym)     # nail head
        c.setDash(1.4, 1.0); c.line(sx - bsec * s2 / 2 - T, ym, sx - bsec * s2 / 2 + 2.5 * s2 * 0.6, ym); c.setDash()
    memberart._dim_v(c, ym - W * s2 / 2, ym + W * s2 / 2, sx - bsec * s2 / 2 - T - 10, f"W {_mixed(W)}", FR, ext_from=sx - bsec * s2 / 2 - T)
    _small(c, sx, yb - 44, "section across the strap")
    return yb - 52


def _framing_angle_picture(c, top, d):
    """Framing angle or lateral tie plate, to scale, two views, with the members of the connection type drawn and broken off.
    A34 / A35: left, elevation looking along the supporting plate: the plate cut in end grain, the joist (or the stud, type 3) on it in
    elevation with its grain, the angle's leg on the member face with its nails and the other leg on the plate edge on; right, section
    looking along the joist: the joist cut in end grain on the plate in elevation, the angle cut (darker) wrapping the corner, nails dashed
    into both members. LTP4 / LTP5: left, elevation of the wall face: the double top plate (with the subfloor edge for LTP5) and the rim
    board above, the plate across the joint with its fasteners in each member; right, section: the members in end grain, the plate
    edge on. The loads are listed with the directions of the catalog figure."""
    mdl, cfg = d["model"], d["config"]
    sc = 7.0
    ytop = top - 16
    ltp = mdl.startswith("LTP")
    t = 0.036 if ltp else 0.048                            # 20 ga, 18 ga (catalog p. 309)
    T = max(t * sc, 1.0)
    vx, sx = LM + 110, LM + 300
    if not ltp:
        pw, ph = 3.5, 1.5                                   # 2x plate laid flat
        jb, jd = 1.5, 7.25                                  # 2x joist or stud
        stud = cfg == 3
        yp = ytop - (jd + ph + 1.0) * sc                    # plate bottom
        # ---- view 1: plate in end grain, member on it in elevation
        memberart.wood_section(c, vx, yp + ph * sc / 2, pw * sc, ph * sc, pw, ph)
        if stud:                                            # the stud's side face, 3-1/2 in. across the wall, grain vertical
            c.saveState(); c.translate(vx - pw * sc / 2, yp + ph * sc); c.rotate(90)
            memberart.wood_elevation(c, 0, -pw * sc, jd * sc, pw * sc, seed=4); c.restoreState()
            memberart._break_h(c, vx - pw * sc / 2, vx + pw * sc / 2, yp + (ph + jd) * sc - 1)
            mw = pw
        else:
            memberart.wood_elevation(c, vx - 9.0 * sc, yp + ph * sc, 18.0 * sc, jd * sc, seed=4)
            _break_v(c, vx - 9.0 * sc, yp + ph * sc - 2, yp + (ph + jd) * sc + 2)
            _break_v(c, vx + 9.0 * sc, yp + ph * sc - 2, yp + (ph + jd) * sc + 2)
            mw = 18.0
        lw, lh = (2.875, 2.5) if mdl == "A34" else (2.875, 3.0)   # leg widths 1 7/16 + 1 7/16; heights p. 309
        if d.get("L"):                                      # L, LS, GA (p. 313): length L along the member, legs about 1-3/8 in.
            lw, lh = (2.0, d["L"]) if mdl.startswith("GA") else (1.375, d["L"])
        lw = min(lw, mw)
        _steel_strip(c, vx - lw * sc / 2, yp + ph * sc, lw * sc, lh * sc)                   # leg on the member face, face on
        _steel_strip(c, vx - lw * sc / 2, yp + ph * sc, lw * sc, T, cut=True)                 # leg on the plate, edge on
        n_ = int(d["fast"].split(")")[0].strip("("))
        _nail_heads(c, vx - lw * sc / 2, yp + ph * sc + T, lw * sc, lh * sc - T, max(n_ // 2, 2))
        _small(c, vx, yp - 16, "elevation along the plate, to scale (in.)" if not stud else "elevation along the wall, plate cut, to scale (in.)")
        # ---- view 2: member in end grain on the plate in elevation
        memberart.wood_elevation(c, sx - 9.0 * sc, yp, 18.0 * sc, ph * sc, seed=9)
        _break_v(c, sx - 9.0 * sc, yp - 2, yp + ph * sc + 2); _break_v(c, sx + 9.0 * sc, yp - 2, yp + ph * sc + 2)
        if stud:                                            # the stud in elevation on the wall face, 1-1/2 in. wide, broken off
            c.saveState(); c.translate(sx - jb * sc / 2, yp + ph * sc); c.rotate(90)
            memberart.wood_elevation(c, 0, -jb * sc, jd * sc, jb * sc, seed=6); c.restoreState()
            memberart._break_h(c, sx - jb * sc / 2, sx + jb * sc / 2, yp + (ph + jd) * sc - 1)
            mb_, mh_ = jb, jd
        else:
            memberart.wood_section(c, sx, yp + (ph + jd / 2) * sc, jb * sc, jd * sc, jb, jd)
            mb_, mh_ = jb, jd
        xf = sx + mb_ * sc / 2                              # the member face the angle is on
        c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setFillColorRGB(*memberart.STEEL_CUT); c.setLineWidth(0.4)
        c.rect(xf, yp + ph * sc, T, lh * sc, fill=1, stroke=1)                              # vertical leg, cut
        c.rect(xf, yp + ph * sc, (1.375 if d.get("L") else 1.44) * sc, T, fill=1, stroke=1)   # leg on the plate, cut
        c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
        for k in range(2):
            yn_ = yp + ph * sc + lh * sc * (0.35 + 0.35 * k)
            c.line(xf + T, yn_, xf - 1.3 * sc, yn_)                                         # nails into the member
        c.line(xf + 0.8 * sc, yp + ph * sc + T, xf + 0.8 * sc, yp + 0.2 * sc)              # nail into the plate
        c.setDash()
        _small(c, sx, yp - 16, "section along the joist, to scale (in.)" if not stud else "elevation of the wall face, angle cut, to scale (in.)")
        ybot = yp - 22
        lab = [(yp + ph * sc / 2, sx - 6.0 * sc, "plate, 2x flat, broken off"),
               (yp + (ph + mh_ * 0.75) * sc, sx - mb_ * sc * 0.2, ("stud" if stud else "joist or blocking") + ", 2x"),
               (yp + (ph + lh * 0.6) * sc, xf + T, f"{mdl}, {d.get('ga', 18)} ga")]
    else:
        tp, rim = 1.5, 9.25
        sub = 0.75 if mdl == "LTP5" else 0.0
        pwid, phgt = (3.0, 4.25) if mdl == "LTP4" else (4.5, 5.125)
        yp = ytop - (2 * tp + sub + 4.0 + 1.0) * sc         # bottom of the lower top plate (rim shown 4 in. then broken)
        yj = yp + 2 * tp * sc                               # top of the top plates
        for k in range(2):
            memberart.wood_elevation(c, vx - 10 * sc, yp + k * tp * sc, 20 * sc, tp * sc, seed=3 + k)
        if sub:
            c.setFillColorRGB(0.93, 0.86, 0.70); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.5)
            c.rect(vx - 10 * sc, yj, 20 * sc, sub * sc, fill=1, stroke=1)
        memberart.wood_elevation(c, vx - 10 * sc, yj + sub * sc, 20 * sc, 4.0 * sc, seed=8)
        memberart._break_h(c, vx - 10 * sc, vx + 10 * sc, yj + (sub + 4.0) * sc - 1)
        for x_ in (vx - 10 * sc, vx + 10 * sc):
            _break_v(c, x_, yp - 2, yj + (sub + 4.0) * sc - 2)
        y0 = yj - phgt * sc / 2 - (0 if not sub else -sub * sc / 2)
        _steel_strip(c, vx - pwid * sc / 2, y0, pwid * sc, phgt * sc)
        n_ = int(d["fast"].split(")")[0].strip("(")) // 2
        _nail_heads(c, vx - pwid * sc / 2, yj + sub * sc, pwid * sc, y0 + phgt * sc - yj - sub * sc, n_)
        _nail_heads(c, vx - pwid * sc / 2, y0, pwid * sc, yj - y0, n_)
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.4); c.setDash(3, 2)
        c.line(vx - pwid * sc / 2 - 6, yj, vx + pwid * sc / 2 + 6, yj); c.setDash()
        memberart._dim_h(c, vx - pwid * sc / 2, vx + pwid * sc / 2, yp - 10, f"{_mixed(pwid)}", FR, ext_from=y0)
        memberart._dim_v(c, y0, y0 + phgt * sc, vx + 10 * sc + 10, f"{_mixed(phgt)}", FR, ext_from=vx + pwid * sc / 2)   # clear of the members
        _small(c, vx, yp - 26, "elevation of the wall face, to scale (in.)")
        # section
        for k in range(2):
            memberart.wood_section(c, sx, yp + (k + 0.5) * tp * sc, 3.5 * sc, tp * sc, 3.5, tp)
        if sub:
            c.setFillColorRGB(0.93, 0.86, 0.70); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.5)
            c.rect(sx - 1.75 * sc, yj, 8.0 * sc, sub * sc, fill=1, stroke=1)
        memberart.wood_section(c, sx - 1.75 * sc + 0.75 * sc, yj + (sub + 2.0) * sc, 1.5 * sc, 4.0 * sc, 1.5, 4.0)
        memberart._break_h(c, sx - 1.75 * sc, sx - 0.25 * sc, yj + (sub + 4.0) * sc - 1)
        _steel_strip(c, sx - 1.75 * sc - T, y0, T, phgt * sc, cut=True)
        c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
        for yn_ in (y0 + phgt * sc * 0.15, y0 + phgt * sc * 0.85):
            c.line(sx - 1.75 * sc - T, yn_, sx - 0.25 * sc, yn_)
        c.setDash()
        _small(c, sx, yp - 26, "section across the wall, to scale (in.)")
        ybot = yp - 32
        lab = [(yp + tp * sc * 0.5, sx + 1.0 * sc, "double top plate"),
               (yj + (sub + 3.0) * sc, sx - 0.5 * sc, "rim board or blocking, broken off"),
               (y0 + phgt * sc * 0.5, sx - 1.75 * sc - T, f"{mdl}, 20 ga")]
        if sub:
            lab.append((yj + sub * sc / 2, sx + 5.5 * sc, "subfloor sheathing"))
    tx = sx + 70
    last = _leader_notes(c, lab, tx)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    lds = ", ".join(f"{k} {v:,.0f} lb" for k, v in d["loads"].items())
    yl = min(last - 14, ybot + 30)
    c.drawString(tx, yl, f"loads: {lds}")
    c.drawString(tx, yl - 9, "directions as catalog p. 313, typical installations" if d.get("L") else f"directions as catalog p. 309, figure {cfg}")
    ybot = min(ybot, yl - 16)
    c.drawCentredString(LM + 200, ytop + 6, (f"{mdl} angle, L {_mixed(d['L'])} in." if d.get("L") else f"{mdl}, connection type {cfg}") + f"; {d['fast']}")
    return ybot - 8


def _lumber_dims(label):
    """Dressed size (b, d) in inches of a joist label such as '2x10', 'DBL 2x8' or '6x12' (NDS Supplement Table 1B)."""
    import re as _re
    plies = {"DBL": 2, "TPL": 3, "QUAD": 4}.get(label.split()[0], 1) if " " in label else 1
    b, d = [int(x) for x in _re.findall(r"\d+", label)[-2:]]
    tb = {2: 1.5, 3: 2.5, 4: 3.5}.get(b, b - 0.5)
    td = (d - 0.5 if b >= 5 else {2: 1.5, 3: 2.5, 4: 3.5, 6: 5.5, 8: 7.25}.get(d, d - 0.75))
    return tb * plies, td, plies


def _joist_hanger_picture(c, top, d):
    """Face-mount joist hanger, to scale: a side elevation (the carrying member cut, in end grain; the joist in elevation with its grain,
    seated in the hanger; the hanger's side plate with its nails and its flange on the header face) and a section looking along the joist
    (the joist cut in end grain inside the U of the hanger, the flanges nailed to the header face behind). W, H and B dimensioned."""
    W, H, B = d["W"], d["H"], d["B"]
    jb, jd, plies = _lumber_dims(d["joist"])
    t = max(d["ga"] and {12: 0.105, 14: 0.075, 16: 0.06, 18: 0.048, 20: 0.036}.get(d["ga"], 0.06), 0.03)
    TF = d.get("TF")
    hb, hd = (5.25, H + 1.0) if TF else (3.5, jd + 3.0)     # the carrying member drawn: depiction only, not dimensioned
    sc = min(7.0, 120.0 / (hd + 3), 150.0 / (hb + B + 10))
    # side elevation
    x0, ytop = LM + 40, top - 20
    yb = ytop - hd * sc
    memberart.wood_section(c, x0 + hb * sc / 2, yb + hd * sc / 2, hb * sc, hd * sc, hb, hd, plies=2 if d.get("two_by") else 1)
    jx0 = x0 + hb * sc + 0.0
    jy0 = yb + 1.0 * sc                                     # joist seated 1 in. above the header bottom (depiction)
    memberart.wood_elevation(c, jx0, jy0, (B + 9.0) * sc, jd * sc)
    _break_v(c, jx0 + (B + 9.0) * sc, jy0 - 2, jy0 + jd * sc + 2)
    c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    T = max(t * sc, 0.9)
    c.rect(jx0, jy0 - T, B * sc, T, fill=1, stroke=1)                       # seat under the joist
    p_ = c.beginPath(); p_.moveTo(jx0, jy0 - T); p_.lineTo(jx0 + B * sc, jy0 - T); p_.lineTo(jx0 + B * sc, jy0 + H * sc * 0.55)
    p_.lineTo(jx0 + B * sc * 0.35, jy0 + H * sc); p_.lineTo(jx0, jy0 + H * sc); p_.close()
    c.setFillColorRGB(0.80, 0.84, 0.88); c.drawPath(p_, fill=1, stroke=1)   # side plate seen face on
    c.setFillColorRGB(*memberart.STEEL_CUT); c.rect(jx0 - T, jy0 - T, T, H * sc + T, fill=1, stroke=1)   # flange on the header face, edge on
    if TF:                                                 # the top flange over the carrying member, with its nails
        c.rect(jx0 - TF * sc, jy0 + H * sc, TF * sc, max(T, 1.2), fill=1, stroke=1)
        c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
        for k in range(2):
            xn_ = jx0 - TF * sc * (0.35 + 0.35 * k)
            c.line(xn_, jy0 + H * sc + T, xn_, jy0 + H * sc - 2.2 * sc)
        c.setDash(); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
        memberart._dim_h(c, jx0 - TF * sc, jx0, jy0 + H * sc + 9, "", FR, ext_from=jy0 + H * sc + T)
        c.setFont(FR, 6); c.setFillColorRGB(0.23, 0.28, 0.34); c.drawRightString(jx0 - TF * sc - 4, jy0 + H * sc + 7, f"TF {TF:g}")
    c.setFillColorRGB(1, 1, 1)
    for k in range(3):                                     # joist nails through the side plate
        c.circle(jx0 + B * sc * 0.55, jy0 + H * sc * (0.2 + 0.18 * k), max(0.12 * sc, 0.9), fill=1, stroke=1)
    if d.get("double"):                                    # double-shear nails driven at an angle through the joist into the header
        c.setStrokeColorRGB(0.25, 0.27, 0.30); c.setLineWidth(0.6); c.setDash(1.4, 1.0)
        for k in range(2):
            yy = jy0 + H * sc * (0.3 + 0.3 * k)
            c.line(jx0 + B * sc * 0.55, yy, jx0 - 1.2 * sc, yy - 1.0 * sc)
        c.setDash()
    memberart._dim_h(c, jx0, jx0 + B * sc, jy0 - T - 10, f"B {B:g}", FR, ext_from=jy0 - T)
    memberart._dim_v(c, jy0 - T, jy0 + H * sc, jx0 + (B + 9.0) * sc + 10, f"H {H:g}", FR, ext_from=jx0 + (B + 9.0) * sc + 3)
    _small(c, x0 + (hb + B + 9) * sc / 2, yb - 22, "side view, to scale (in.)")
    # section looking along the joist
    sx = RM - 120
    fl = 1.1                                                # flange width each side (depiction)
    c.saveState()
    memberart.wood_elevation(c, sx - (W / 2 + fl + 2.0) * sc, yb, (W + 2 * fl + 4.0) * sc, hd * sc)   # header face behind
    c.restoreState()
    memberart.wood_section(c, sx, jy0 + jd * sc / 2, jb * sc, jd * sc, jb, jd, plies=plies)
    c.setFillColorRGB(*memberart.STEEL_CUT); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
    c.rect(sx - W * sc / 2 - T, jy0 - T, W * sc + 2 * T, T, fill=1, stroke=1)                 # seat, cut
    if TF:                                                 # top flanges lying on the carrying member behind
        c.setFillColorRGB(*memberart.STEEL_FILL)
        c.rect(sx - W * sc / 2 - T - 0.6 * sc, jy0 + H * sc, W * sc + 2 * T + 1.2 * sc, max(T, 1.2), fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_CUT)
    for sg in (-1, 1):
        xw = sx + sg * W * sc / 2 + (0 if sg > 0 else -T)
        c.rect(xw, jy0 - T, T, H * sc + T, fill=1, stroke=1)                                 # sides, cut
        if TF:
            continue
        c.setFillColorRGB(*memberart.STEEL_FILL)
        xf = sx + sg * (W * sc / 2 + T) + (0 if sg > 0 else -fl * sc)
        c.rect(xf, jy0 + 0.2 * sc, fl * sc, H * sc - 0.2 * sc, fill=1, stroke=1)              # flanges on the header face
        c.setFillColorRGB(1, 1, 1)
        for k in range(3):
            c.circle(xf + fl * sc / 2, jy0 + H * sc * (0.25 + 0.25 * k), max(0.12 * sc, 0.8), fill=1, stroke=1)
        c.setFillColorRGB(*memberart.STEEL_CUT)
    memberart._dim_h(c, sx - W * sc / 2, sx + W * sc / 2, jy0 - T - 10, f"W {W:g}", FR, ext_from=jy0 - T)
    _small(c, sx, yb - 22, "section looking along the joist, to scale (in.)")
    c.setFillColorRGB(*INK); c.setFont(FR, 6.5)
    c.drawCentredString((x0 + RM - 120) / 2 + 30, ytop + 6, f"{d['model']}, {d['ga']} ga, on a {d['joist']} joist")
    return yb - 30


def _sill_anchor_picture(c, top, d):
    """Section across the wall at an anchor bolt, to scale: the concrete stem wall cut short below the bolt, the bottom plate in end
    grain with the stud above it broken off and the sheathing on its face, the plate washer and nut, the bolt dashed in the concrete to
    its headed nut or hook; embedment, edge distance, foundation width and plate dimensioned."""
    fw, pt, pw, D, hef = d["fwidth"], d["sill_t"], d["sill_w"], d["D"], d["hef"]
    off = d.get("offset") if d.get("offset") is not None else pw / 2.0
    ce = d["edge"]
    hshow = hef + 4.0
    sc = min(170.0 / max(fw + 10.0, pw + 10.0), 150.0 / (hshow + pt + 9.0))
    cx0 = LM + 130                                             # outer (sheathed) face of the stem wall
    yt = top - 10 - (pt + 7.5) * sc                            # top of the concrete
    memberart._concrete(c, cx0, yt - hshow * sc, fw * sc, hshow * sc, seed=17)
    memberart._break_h(c, cx0, cx0 + fw * sc, yt - hshow * sc - 1)
    xb = cx0 + ce * sc                                         # the bolt
    px = xb - off * sc                                         # the plate's sheathed edge
    c.saveState()                                              # bottom plate, end grain
    memberart.wood_section(c, px + pw * sc / 2, yt + pt * sc / 2, pw * sc, pt * sc, pw, pt)
    c.restoreState()
    st_h = 7.0 * sc                                            # the stud above, broken off
    c.saveState(); c.translate(px, yt + pt * sc); c.rotate(90)
    memberart.wood_elevation(c, 0, -pw * sc, st_h, pw * sc); c.restoreState()
    memberart._break_h(c, px, px + pw * sc, yt + pt * sc + st_h - 1)
    c.setFillColorRGB(0.93, 0.86, 0.70); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.5)   # sheathing on the outer face
    c.rect(px - 0.5 * sc, yt + 0.5 * sc, 0.5 * sc, pt * sc + st_h - 1.5 * sc, fill=1, stroke=1)
    ww, wt = d.get("washer_w") or 3.0, d.get("washer_t") or 0.229
    c.setFillColorRGB(0.62, 0.66, 0.72); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
    c.rect(xb - ww * sc / 2, yt + pt * sc, ww * sc, max(wt * sc, 1.0), fill=1, stroke=1)         # plate washer
    nh = max(0.55 * D * sc, 2.0)
    c.setFillColorRGB(0.42, 0.47, 0.54); c.rect(xb - 0.8 * D * sc, yt + pt * sc + max(wt * sc, 1.0), 1.6 * D * sc, nh, fill=1, stroke=1)
    c.setFillColorRGB(0.70, 0.74, 0.79); c.rect(xb - D * sc / 2, yt + pt * sc + max(wt * sc, 1.0) + nh, D * sc, max(0.4 * D * sc, 1.2), fill=1, stroke=1)
    c.setDash(2, 1.4); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.6)          # bolt hidden in the plate and the concrete
    yb_ = yt - hef * sc
    c.line(xb - D * sc / 2, yt + pt * sc, xb - D * sc / 2, yb_); c.line(xb + D * sc / 2, yt + pt * sc, xb + D * sc / 2, yb_)
    if d.get("hooked"):
        eh = d.get("eh") or 3 * D
        c.line(xb - D * sc / 2, yb_, xb + (eh + D / 2) * sc, yb_); c.line(xb + D * sc / 2, yb_ + D * sc, xb + (eh + D / 2) * sc, yb_ + D * sc)
        c.line(xb + (eh + D / 2) * sc, yb_, xb + (eh + D / 2) * sc, yb_ + D * sc)
    else:
        c.line(xb - 0.8 * D * sc, yb_, xb + 0.8 * D * sc, yb_); c.line(xb - 0.8 * D * sc, yb_ - 0.55 * D * sc, xb + 0.8 * D * sc, yb_ - 0.55 * D * sc)
        c.line(xb - 0.8 * D * sc, yb_, xb - 0.8 * D * sc, yb_ - 0.55 * D * sc); c.line(xb + 0.8 * D * sc, yb_, xb + 0.8 * D * sc, yb_ - 0.55 * D * sc)
    c.setDash()
    memberart._dim_v(c, yb_, yt, cx0 - 12, f"hef {hef:g} in", FR, ext_from=xb - D * sc)
    if c.stringWidth(f"{ce:g} in", FR, 6) > (xb - cx0) - 4:   # a short edge distance: its figure beside the dimension
        memberart._dim_h(c, cx0, xb, yt - hshow * sc - 12, "", FR, ext_from=yt - hshow * sc)
        c.setFont(FR, 6); c.setFillColorRGB(0.23, 0.28, 0.34); c.drawRightString(cx0 - 4, yt - hshow * sc - 14, f"{ce:g} in")
    else:
        memberart._dim_h(c, cx0, xb, yt - hshow * sc - 12, f"{ce:g} in", FR, ext_from=yt - hshow * sc)
    memberart._dim_h(c, cx0, cx0 + fw * sc, yt - hshow * sc - 24, f"{fw:g} in", FR, ext_from=yt - hshow * sc - 12)
    c.setFillColorRGB(*INK); c.setFont(FR, 6.2)
    tx = cx0 + fw * sc + 60
    notes = [(yt + pt * sc + st_h * 0.6, px + pw * sc * 0.6, "stud, broken off; sheathing on the outer face"),
             (yt + pt * sc + 1.5, xb + ww * sc / 2 - 1, f"plate washer {ww:g} x {d.get('washer_l') or 3.0:g} x {wt:g} in, nut"),
             (yt + pt * sc / 2, px + pw * sc - 2, f"bottom plate {pt:g} x {pw:g} in"),
             (yt - hef * sc / 2, xb + D * sc / 2, f"{D:g} in {d['grade']}, " + ("hooked" if d.get("hooked") else "headed")),
             (yt - hshow * sc + 6, cx0 + fw * sc - 4, f"concrete, f'c {d['fc']:,.0f} psi")]
    last = None
    for (y_, xt_, t_) in sorted(notes, key=lambda q: -q[0]):  # notes with leaders, clear of each other
        yy = y_ if last is None or last - y_ >= 9 else last - 9
        c.setStrokeColorRGB(*GREY); c.setLineWidth(0.35); c.line(xt_, y_, tx - 3, yy + 1.5)
        c.setFillColorRGB(*GREY); c.circle(xt_, y_, 0.7, fill=1, stroke=0)
        c.setFillColorRGB(*INK); c.drawString(tx, yy - 0.5, t_); last = yy
    _small(c, cx0 + fw * sc / 2 + 40, yt - hshow * sc - 40, "section across the wall at an anchor bolt, to scale; bolt hidden lines dashed")
    return yt - hshow * sc - 46


def _anchor_bolt_marks(c, xa, xb, y0, sc, ab):
    """Foundation anchor bolts along a bottom plate, to scale (sc points per ft): the first 12 in. from each end, then at the spacing;
    each bolt seen through the sheathing, dashed below the plate into the concrete, with its plate washer."""
    s_ft = ab["s"] / 12.0
    L = (xb - xa) / sc
    xs, x = [], 1.0
    while x < L - 1.0 + 1e-6:
        xs.append(x); x += s_ft
    if L > 2.0 and (not xs or L - 1.0 - xs[-1] > 0.25):
        xs.append(L - 1.0)
    for xf in xs:
        px = xa + xf * sc
        c.setStrokeColorRGB(0.20, 0.22, 0.25); c.setLineWidth(0.8); c.setDash(1.6, 1.0)
        c.line(px, y0 - 6.0, px, y0 + 3.2); c.setDash()
        c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.4)
        c.rect(px - 1.6, y0 + 1.2, 3.2, 1.0, fill=1, stroke=1)
    return len(xs)


def _perforated_wall_picture(c, top, d):
    """Elevation of a sheathed shear wall with openings, to scale, drawn as built: the sheathing face with its 4 x 8 ft panel joints, the
    framing behind it dashed (studs at 16 in., the bottom plate and the double top plate, king and jack studs at each opening, the end
    posts heavier), the openings, a hold-down at each end of the wall, and for force transfer the strap and blocking along the top and
    bottom of each opening; the full-height segment lengths, opening widths and height dimensioned, the shear and the chord forces."""
    Lw, h = d["L"], d["h"]
    sc = min((RM - LM - 130) / Lw, 118.0 / h)
    _sketch_title(c, LM + 6, top - 4, "ELEVATION")
    x0, y0 = LM + 50, top - 36 - h * sc
    W, H = Lw * sc, h * sc
    ops = sorted(d["openings"], key=lambda o: o["x"])
    inside = lambda x, y: any(o["x"] - 1e-6 < x < o["x"] + o["w"] + 1e-6 and o["sill"] - 1e-6 < y < o["sill"] + o["h"] + 1e-6 for o in ops)
    # sheathing face
    c.setLineWidth(0.7); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setFillColorRGB(0.94, 0.88, 0.76)
    c.rect(x0, y0, W, H, fill=1, stroke=1)
    c.saveState()                                            # strand texture of the panels, clipped off the openings
    pth = c.beginPath(); pth.rect(x0, y0, W, H)
    for o in ops:
        pth.rect(x0 + o["x"] * sc, y0 + o["sill"] * sc, o["w"] * sc, o["h"] * sc)
    c.clipPath(pth, stroke=0, fill=0, fillMode=1)
    import random as _r
    rnd = _r.Random(int(Lw * 13 + h * 7))
    c.setStrokeColorRGB(0.80, 0.70, 0.52); c.setLineWidth(0.35)
    for _ in range(int(W * H / 22)):
        px, py, ln = x0 + rnd.uniform(0, W), y0 + rnd.uniform(0, H), rnd.uniform(1.5, 3.5)
        a = rnd.uniform(-0.6, 0.6)
        c.line(px, py, px + ln, py + ln * a)
    c.restoreState()
    c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.5)       # panel joints: 4 ft sheets, 8 ft long
    xx = 4.0
    while xx < Lw - 1e-6:
        c.line(x0 + xx * sc, y0, x0 + xx * sc, y0 + H)
        xx += 4.0
    if h > 8.0 + 1e-6:
        c.line(x0, y0 + 8.0 * sc, x0 + W, y0 + 8.0 * sc)
    # framing behind, dashed
    c.setStrokeColorRGB(0.45, 0.32, 0.18); c.setLineWidth(0.35); c.setDash(2.2, 1.6)
    c.line(x0, y0 + 0.125 * sc, x0 + W, y0 + 0.125 * sc)                            # bottom plate
    c.line(x0, y0 + H - 0.25 * sc, x0 + W, y0 + H - 0.25 * sc)                      # double top plate
    c.line(x0, y0 + H - 0.125 * sc, x0 + W, y0 + H - 0.125 * sc)
    k = 1
    while k * 16.0 / 12.0 < Lw - 0.2:                                              # studs at 16 in.
        xs = k * 16.0 / 12.0
        segs, yy, ys_ = [], 0.0, [0.0]
        for o in ops:
            if o["x"] < xs < o["x"] + o["w"]:
                segs += [(0.0, o["sill"]), (o["sill"] + o["h"], h)]
        for a, b in (segs or [(0.0, h)]):
            if b - a > 1e-6:
                c.line(x0 + xs * sc, y0 + a * sc, x0 + xs * sc, y0 + b * sc)
        k += 1
    for o in ops:                                                                   # king and jack studs, header and sill lines
        for xq in (o["x"] - 0.0625, o["x"] - 0.1875, o["x"] + o["w"] + 0.0625, o["x"] + o["w"] + 0.1875):   # jack, then king, each side
            c.line(x0 + xq * sc, y0, x0 + xq * sc, y0 + H)
        c.line(x0 + o["x"] * sc, y0 + (o["sill"] + o["h"]) * sc + 1.2, x0 + (o["x"] + o["w"]) * sc, y0 + (o["sill"] + o["h"]) * sc + 1.2)
        if o["sill"] > 0:
            c.line(x0 + o["x"] * sc, y0 + o["sill"] * sc - 1.2, x0 + (o["x"] + o["w"]) * sc, y0 + o["sill"] * sc - 1.2)
    c.setDash()
    c.setLineWidth(0.8)                                                             # end posts (chords), dashed heavier
    c.setDash(3, 1.6)
    for xe in (x0 + 2.0, x0 + W - 2.0):
        c.line(xe, y0, xe, y0 + H)
    c.setDash()
    # openings
    c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(*memberart.WOOD_LINE); c.setLineWidth(0.7)
    for o in ops:
        c.rect(x0 + o["x"] * sc, y0 + o["sill"] * sc, o["w"] * sc, o["h"] * sc, fill=1, stroke=1)
    # force transfer: strap and blocking along the top and bottom of each opening, across the piers beside it
    if d.get("ftao"):
        segs_ = d.get("segs") or []
        c.setFillColorRGB(0.55, 0.58, 0.62); c.setStrokeColorRGB(0.30, 0.33, 0.37); c.setLineWidth(0.3)
        for o in ops:
            xl = max([s_["x"] for s_ in segs_ if s_["x"] + s_["b"] <= o["x"] + 1e-6] or [o["x"]])
            xr = min([s_["x"] + s_["b"] for s_ in segs_ if s_["x"] >= o["x"] + o["w"] - 1e-6] or [o["x"] + o["w"]])
            for yl in ([o["sill"]] if o["sill"] > 0 else []) + [o["sill"] + o["h"]]:
                c.rect(x0 + xl * sc + 1, y0 + yl * sc - 0.9, (xr - xl) * sc - 2, 1.8, fill=1, stroke=1)
    # hold-downs at the ends: bracket on the end post, anchor rod into the foundation
    c.setFillColorRGB(*memberart.STEEL_FILL); c.setStrokeColorRGB(*memberart.STEEL_LINE); c.setLineWidth(0.5)
    for xe, sg in ((x0, 1), (x0 + W, -1)):
        bx = xe + sg * 2.5 - (4.0 if sg < 0 else 0.0)
        c.rect(bx, y0 + 1.0, 4.0, 11.0, fill=1, stroke=1)
        c.setLineWidth(0.9); c.line(bx + 2.0, y0 - 5.0, bx + 2.0, y0 + 4.0); c.setLineWidth(0.5)
    c.setStrokeColorRGB(*GREY); c.setLineWidth(0.6); c.line(x0 - 14, y0, x0 + W + 14, y0)
    if d.get("ab"):                                       # anchor bolts along each length of bottom plate (none across a door)
        cuts = [0.0] + [v_ for o in ops if o["sill"] <= 1e-6 for v_ in (o["x"], o["x"] + o["w"])] + [Lw]
        for a_, b_ in zip(cuts[0::2], cuts[1::2]):
            if b_ - a_ > 1e-6:
                _anchor_bolt_marks(c, x0 + a_ * sc, x0 + b_ * sc, y0, sc, d["ab"])
    # loads and dimensions
    c.setStrokeColorRGB(*INK); c.setFillColorRGB(*INK); c.setLineWidth(0.8)
    c.line(x0 + 2, y0 + H + 6, x0 + W - 2, y0 + H + 6); c.line(x0 + W - 2, y0 + H + 6, x0 + W - 6, y0 + H + 8)
    c.line(x0 + W - 2, y0 + H + 6, x0 + W - 6, y0 + H + 4)
    c.setFont(FR, 6.5); c.drawCentredString(x0 + W / 2, y0 + H + 10, f"V = {d['V']:,.0f} lb")
    marks = [0.0]
    for o in ops:
        marks += [o["x"], o["x"] + o["w"]]
    marks.append(Lw)
    for a, b in zip(marks[:-1], marks[1:]):
        if b - a > 1e-6:
            memberart._dim_h(c, x0 + a * sc, x0 + b * sc, y0 - 11, f"{b - a:g}" if (b - a) * sc < 24 else f"{b - a:g} ft", FR, ext_from=y0 - 6)
    memberart._dim_h(c, x0, x0 + W, y0 - 23, f"{Lw:g} ft", FR, ext_from=y0 - 11)
    memberart._dim_v(c, y0, y0 + H, x0 + W + 10, f"{h:g} ft", FR, ext_from=x0 + W)
    c.setFont(FR, 6); c.setFillColorRGB(*GREY)
    c.drawRightString(x0 - 4, y0 + 4, f"T {d['T']:,.0f}"); c.drawString(x0 + W + 4, y0 - 7, f"C {d['T']:,.0f}")
    _small(c, (LM + RM) / 2, y0 - 43, "to scale; sheathing face with 4 x 8 ft panel joints, framing behind dashed, hold-down at each end"
           + ("; strap and blocking along the top and bottom of each opening" if d.get("ftao") else "")
           + (f"; anchor bolts {d['ab']['D']:g} in. at {d['ab']['s']:g} in." + ("" if d["ab"]["given"] else " (the spacing found)") + ", 12 in. from the plate ends"
              if d.get("ab") else "") + "; chord forces in lb")
    return y0 - 55


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
        if d.get("ab"):
            _anchor_bolt_marks(c, x, x + w, y0, sc, d["ab"])
        x += w + gap
    memberart._dim_v(c, y0, y0 + d["h"] * sc, x - gap + 8, f"{d['h']:g} ft", FR, ext_from=x - gap)
    _small(c, (LM + RM) / 2, y0 - 32, "segments drawn to scale, side by side; chord forces in lb; framing lines are schematic"
           + (f"; anchor bolts {d['ab']['D']:g} in. at {d['ab']['s']:g} in." + ("" if d["ab"]["given"] else " (the spacing found)") + ", 12 in. from the plate ends"
              if d.get("ab") else ""))
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
