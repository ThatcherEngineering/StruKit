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
# Plan takedown, sheet S1.0 with the S0 loads (dead 15 + 52 + 5 = 72 psf, live 125 psf):
#  W14x30 infill at 4'-11 1/2" o.c., longest span 24'-8" (K to M): wD = 0.072 x 4.96 + 0.030 = 0.387, wL = 0.125 x 4.96 = 0.620 kip/ft -> 4.77 D, 7.65 L
#  W21x50 girder on line K, 19'-10" span, three pairs of W14x30 (24'-0" and 24'-8" spans): 1.5 x (4.64 + 4.77) + 0.5 = 14.6 D, 1.5 x (7.44 + 7.65) = 22.6 L
#  W8x15 header at detail 5, 3'-0" span beside the floor opening: bound 0.55 D, 0.95 L
PLAN = "plan takedown, sheet S1.0, 72 psf dead and 125 psf live"
R.update({"W14X30": (4.77, 7.65, PLAN + ": 24 ft 8 in. span at 4 ft 11-1/2 in. o.c."), "W14X30-D3": (3.14, 31.47, "FloorBeamD.3 of the StruCalc file; not located on the plan"),
          "W21X50": (14.6, 22.6, PLAN + ": line K girder, 19 ft 10 in. span, three pairs of W14x30"), "W8X15-5": (0.55, 0.95, PLAN + ": 3 ft header beside the floor opening (upper bound)"),
          "W16X31": (1.34, 16.93, "upper bound; plan takedown gives about 17.3 kips on line M")})
def tab(mark, beam, n, d, s, lev, tp, weld, col=None, girder=None, a=3.0, leh=1.5, through=False, rkey=None):
    D, L, src = R[rkey or beam]
    v = dict(MAT, mark=mark, beam=beam, tp=str(tp), d=str(d), n=str(n), spacing=str(s), lev=str(lev), leh=str(leh), a=str(a), weld=str(weld),
             loads=[dict(case="D", P=str(D), label=src), dict(case="L", P=str(L), label=src)])
    if col and not through:
        v.update(HSS, column=col)
    elif col:
        v.update(HSS, column=col, through={"HSS5X5X3/8": "5", "HSS6X6X1/2": "6"}[col])
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
 tab("Det 5: W8x15 to W21x50", "W8X15", 3, 0.5, 1.5, 1.75, 0.375, 0.1875, girder="W21X50", rkey="W8X15-5"),
 tab("Det 24: W8x15 to W14x30", "W8X15", 2, 0.75, 3.5, 1.9375, 0.375, 0.1875, girder="W14X30"),
 tab("Det 6, 9: W10x17 to W18x40 or W12x30", "W10X17", 3, 0.75, 2.75, 1.75, 0.375, 0.1875, girder="W12X30"),
 tab("Det 23: W10x17 to W16x31", "W10X17", 3, 0.75, 3, 1.5, 0.375, 0.1875, girder="W16X31"),
 tab("Det 14, 37, 38: W14x30 to W16x31 or W21x50", "W14X30", 3, 0.75, 3, 3, 0.375, 0.1875, girder="W16X31"),
 tab("W14x30 three-bolt tab under the FloorBeamD.3 reaction", "W14X30", 3, 0.75, 3, 2.5, 0.375, 0.25, col="HSS6X6X1/2", leh=2, rkey="W14X30-D3"),
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
# Columns and base plates. Column loads from the plan takedown:
#  HSS6x6x1/2 on line K (interior): W21x50 girder 37.2 (south span) + 12.7 (north span, 9 ft 4 in., one pair of W14x30) + two W14x30 at the column = 29.0 D, 45.5 L
#  HSS5x5x3/8: upper bound, two W12x30 and two W10x17 at their largest StruCalc reactions = 8.7 D, 43.9 L
COLS = [("HSS6X6X1/2", "1", "Det 1.1", 29.0, 45.5, PLAN + ": interior column on line K"),
        ("HSS5X5X3/8", "0.625", "Det 1.0", 8.7, 43.9, "upper bound: two W12x30 and two W10x17 at their largest StruCalc reactions")]
for shp, t, det, D_, L_, src in COLS:
    ld = [dict(case="D", P=str(D_), label=src), dict(case="L", P=str(L_), label=src)]
    M.append(("hss_column", dict(mark=f"Column {shp.replace('X', 'x')}", shape=shp, Fy="46", Fy_source="ASTM A500 Grade B, sheet S0 Steel Notes", height="13.33", Kx="1", Ky="1",
              k_source="pinned at the base plate and at the beams; height taken to the top of slab, 113 ft 4 in.", self_weight="yes", loads=ld, moments=[])))
    M.append(("base_plate", dict(mark=f"{det}: base plate under {shp.replace('X', 'x')}", shape=shp, N="12", B="12", t=t, Fy="36", fc="4500", full="yes", loads=ld)))
# Stairs, sheet S2.3: MC12x10.6 stringers, 3 ft 8 in. clear, 11 in. treads, 6-7/8 in. risers; lower flight of the west stair 15 treads (13 ft 9 in. run, counted on the plan).
M.append(("stair_stringer", dict(mark="West stair stringer, lower flight", shape="MC12X10.6", Fy="36", run="13.75", riser="6.875", tread="11", trib="1.92", dead="12",
          dead_note="grating treads on 2 x 2 x 1/4 angles (weight taken as 12 psf; tread by the manufacturer)", extra="10", extra_note="guard", occupancy="stairs and exit ways",
          braced="yes", defl=[dict(label="live", expr="L", ratio="360", source="IBC Table 1604.3, floor members")])))
# Guard, detail 47 and S0 (50 plf or 200 lb): post spacing is not on the drawings; run at 4 ft.
M.append(("guard", dict(mark="Det 47: guard, posts at 4 ft", rail="PIPE1-1/4STD", rail_Fy="35", rail_Fy_source="ASTM A53 Grade B, sheet S0 Steel Notes", post="HSS1-1/2X1-1/2X1/4",
          post_Fy="46", post_Fy_source="ASTM A500 Grade B, sheet S0 Steel Notes", spacing="4", height="3.5", uniform="applies")))
# Deck brace, details 21 and 22: L3x3x1/4 at 5 ft o.c. under the cantilevered deck edge (1 ft 10 in. overhang, 3 ft backspan).
# Vertical load at the brace = 0.197 ksf x (1.83 + 1.5) ft x 5 ft, split 72 / 125; brace at about 45 degrees: x 1.414; length about 2.5 ft.
M.append(("angle_strut", dict(mark="Det 21, 22: deck brace L3x3x1/4", shape="L3X3X1/4", Fy="36", steel_source="ASTM A36, sheet S0 Steel Notes", length="2.5", attached="",
          loads=[dict(case="D", P="1.70", label="72 psf x 3.33 ft x 5 ft x 1.414"), dict(case="L", P="2.94", label="125 psf x 3.33 ft x 5 ft x 1.414")])))
# Detail 35: W21x50 on an L8x8x3/4 bearing angle, 8 in. long, four 3/4 in. bolts to the PEMB column; the 5/8 in. stiffener plate under it is not counted.
D_, L_, src_ = R["W21X50"]
M.append(("seat", dict(mark="Det 35: W21x50 on the L8x8x3/4 bearing angle", beam="W21X50", beam_Fy="50", beam_source="ASTM A992, sheet S0 Steel Notes", t="0.75", length="8", osl="8",
          vleg="8", angle_Fy="36", angle_source="ASTM A36, sheet S0 Steel Notes", attach="bolted", n_bolts="4", d="0.75", group="A325", threads="N",
          loads=[dict(case="D", P=str(D_), label=src_), dict(case="L", P=str(L_), label=src_)])))
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
