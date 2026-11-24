"""2026-001 Rusler mezzanine: shear tab connections typed from sheets S2.0-S2.2 (sealed 07/24/2026).
Demand: the largest end reaction of any beam of that size in 2026-001-StruCalc.vtx (member named)."""
import json
from strukit.gui import calc
proj = json.load(open("/home/claude/strukit/tests/data/job_2026_001_mezzanine.strukit"))["project"]
MAT = dict(beam_Fu="65", beam_source="ASTM A992, sheet S0 Steel Notes", plate_Fy="36", plate_Fu="58", plate_source="ASTM A36, sheet S0 Steel Notes",
           group="A325", threads="N", holes="STD", FEXX="70")
HSS = dict(col_Fy="46", col_Fu="58", col_source="ASTM A500 Grade B, sheet S0 Steel Notes")
TW = {"W18X40": 0.315, "W21X50": 0.380, "W12X30": 0.260, "W16X31": 0.275, "W14X30": 0.270, "W8X15": 0.245}
R = {"W8X15": (0.50, 9.02, "FloorBeamB.3"), "W10X17": (3.48, 8.62, "FloorBeamD.2"), "W12X30": (0.87, 13.35, "FloorBeamY.2"),
     "W14X30": (3.14, 31.47, "FloorBeamD.3"), "W18X40": (1.84, 23.50, "FloorBeamY.4"), "W16X31": (1.34, 16.93, "FloorBeamG.2 (W16x40 in the file)"),
     "W21X50": (1.84, 38.80, "FloorBeamY.3 (W18x40 in the file)")}
def tab(mark, beam, n, d, s, lev, tp, weld, col=None, girder=None, a=3.0, leh=1.5, through=False):
    D, L, src = R[beam]
    v = dict(MAT, mark=mark, beam=beam, tp=str(tp), d=str(d), n=str(n), spacing=str(s), lev=str(lev), leh=str(leh), a=str(a), weld=str(weld),
             loads=[dict(case="D", P=str(D), label=src), dict(case="L", P=str(L), label=src)])
    if col and not through:
        v.update(HSS, column=col)
    elif col:
        v.update(support_name=f"through plate in {col}", support_t={"HSS5X5X3/8": "0.349", "HSS6X6X1/2": "0.465"}[col], support_Fu="58")
    else:
        v.update(support_name=f"{girder} web, full-depth stiffener plate", support_t=str(TW[girder]), support_Fu="65")
        # cope at the top flange: not dimensioned on the details. Taken as: depth = girder k rounded up to 1/4 in.; length = half the girder flange
        # + 1/2 in. rounded up to 1/4 in.; beam end 1/2 in. from the girder web; first bolt = girder flange thickness + plate edge distance below top of steel
        from strukit import shapes; import math
        g = shapes.get(girder); up = lambda x: math.ceil(x * 4 - 1e-9) / 4
        dc, c = up(g["kdes"]), up(g["bf"] / 2 + 0.5)
        dc = min(dc, math.floor((g["tf"] + lev - 1.0) * 8 + 1e-9) / 8)      # detail 23: a 1 in. cope would leave under 1 in. to the first bolt
        v.update(cope_dc=str(dc), cope_c=str(c), cope_setback="0.5", cope_lev=f"{g['tf'] + lev - dc:.3f}", cope_leh="2.25", beam_Fy="50")
    return ("single_plate", v)
M = [
 tab("Det 2, 3, 16, 17: W10x17 to HSS5x5x3/8", "W10X17", 3, 0.75, 2.5, 1.5, 0.375, 0.25, col="HSS5X5X3/8", leh=2),
 tab("Det 11: W8x15 to HSS5x5x3/8", "W8X15", 2, 0.75, 3, 1.5, 0.375, 0.25, col="HSS5X5X3/8", leh=2),
 tab("Det 2, 3, 17: W12x30 to HSS5x5x3/8", "W12X30", 3, 0.75, 3, 2, 0.375, 0.25, col="HSS5X5X3/8", leh=2, through=True),
 tab("Det 7, 19, 20: W14x30 to HSS6x6x1/2", "W14X30", 3, 0.75, 3, 2.5, 0.375, 0.25, col="HSS6X6X1/2", leh=2),
 tab("Det 16: W16x31 to HSS6x6x1/2", "W16X31", 4, 0.75, 3, 2, 0.4375, 0.25, col="HSS6X6X1/2", leh=2, through=True),
 tab("Det 7, 19, 20: W21x50 to HSS6x6x1/2", "W21X50", 5, 0.75, 3, 2.5, 0.4375, 0.25, col="HSS6X6X1/2", leh=2, through=True),
 tab("Det 4, 8, 10: W8x15 to W18x40", "W8X15", 3, 0.625, 2, 1.75, 0.375, 0.1875, girder="W18X40"),
 tab("Det 5: W8x15 to W21x50", "W8X15", 3, 0.5, 1.5, 1.75, 0.375, 0.1875, girder="W21X50"),
 tab("Det 24: W8x15 to W14x30", "W8X15", 2, 0.75, 3.5, 1.9375, 0.375, 0.1875, girder="W14X30"),
 tab("Det 6, 9: W10x17 to W18x40 or W12x30", "W10X17", 3, 0.75, 2.75, 1.75, 0.375, 0.1875, girder="W12X30"),
 tab("Det 23: W10x17 to W16x31", "W10X17", 3, 0.75, 3, 1.5, 0.375, 0.1875, girder="W16X31"),
 tab("Det 14, 37, 38: W14x30 to W16x31 or W21x50", "W14X30", 3, 0.75, 3, 3, 0.375, 0.1875, girder="W16X31"),
 tab("Det 31, 32: W18x40 to W18x40", "W18X40", 4, 0.75, 3.8125, 2.5, 0.375, 0.1875, girder="W18X40"),
]
def ep(mark, beam, n, width, length, gage, lev, s):
    D, L, src = R[beam]
    return ("end_plate", dict(mark=mark, beam=beam, beam_Fy="50", beam_Fu="65", beam_source="ASTM A992, sheet S0 Steel Notes", tp="0.5", width=str(width), length=str(length),
            plate_Fy="36", plate_Fu="58", plate_source="ASTM A36, sheet S0 Steel Notes", d="0.75", group="A325", threads="N", n=str(n), spacing=str(s), lev=str(lev), gage=str(gage),
            weld="0.1875", FEXX="70", loads=[dict(case="D", P=str(D), label=src), dict(case="L", P=str(L), label=src)]))
M += [
 ep("Det 29, 39: W8x15 end plate to PEMB column", "W8X15", 2, 6.5, 10, 3, 3.25, 3.5),
 ep("Det 13, 25: W10x17 end plate to PEMB column", "W10X17", 3, 6, 12, 3.5, 3, 3),
 ep("Det 25: W12x30 end plate to PEMB column", "W12X30", 3, 8, 14, 4, 3.5, 3.5),
 ep("Det 15, 35, 36: W14x30 end plate to PEMB column", "W14X30", 4, 8.5, 16, 5, 3.25, 3),
 ep("Det 12: W16x31 end plate to PEMB column", "W16X31", 4, 8.5, 18, 5, 3.75, 3.5),
 ep("Det 13, 29, 30, 33, 34: W18x40 end plate to PEMB column", "W18X40", 5, 8, 20, 5.5, 4, 3),
]
json.dump(dict(format="strukit-project", version=1, project=proj, members=[dict(kind=k, values=v) for k, v in M]), open("/home/claude/jobs/2026-001/2026-001-Connections.strukit", "w"), indent=1)
if __name__ == "__main__":
    for k, v in M:
        r = calc.results(k, v, proj)
        print(f"== {v['mark']} {r.get('state')} {r.get('status','')}")
        for m_ in r.get("messages", [])[:4]: print("   !", m_[:260])
        rows = r.get("rows", [])
        for row in rows:
            if row.get("status") != "OK" or (k == "end_plate" and row is max(rows, key=lambda x: x.get("dc") or 0)):
                print(f"   {row['check'][:50]:<50} {row['demand']:>8.2f} {row['capacity']:>8.2f} {row['unit']} dc {row.get('dc'):.2f} {row['status']}")
