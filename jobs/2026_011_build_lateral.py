"""2026-011 Humbargar addition: lateral run in StruKit, typed from sheets S0-S3 (sealed 06/30/2026)
and the architect's plans A2.1/A2.2 (04-01-2026). Wall lines named from sheet S1:
Line 1 = the 27'-3" wall opposite the existing house; Line 2 = the existing-house side;
Line A = the 29'-9 1/2" side wall; Line B = the 22'-7" side wall."""
import json, sys
from strukit import wind
from strukit.gui import calc
proj = json.load(open("/home/claude/jobs/2026-011/2026-011.strukit"))["project"]
S0 = "sheet S0, Design Criteria"
HT = "9 ft walls each level (sealed calculation package, wall dead 315 plf at 35 psf), 11-7/8 in. floor joists, 16 in. roof joists"
W = lambda mark, across, along: dict(mark=mark, V="115", V_source=S0, exposure="C", exposure_basis=S0, enclosure="enclosed",
        enclosure_basis=S0 + ", internal pressure coefficient +/-0.18", across=str(across), along=str(along), roof="gable or flat",
        eave="20.5", h="20.5", theta="1.2", Kzt="1.0", Kzt_source="no hill, ridge or escarpment noted on the drawings", overhang="2")
M = []
M.append(("wind_mwfrs", W("Wind", 27.25, 29.6)))
ws, _, _ = calc.build("wind_mwfrs", M[0][1], proj)
loads = {}
for title, r in zip(ws.wind["titles"], ws.wind["cases"]):
    top = max(r["top_w"], r["top_l"])
    loads[r["B"]] = dict(title=title, roof=wind.line_load(r, 14.5, top), floor=wind.line_load(r, 4.5, 14.5), top=top)
    print(title, "B", r["B"], "roof", round(loads[r["B"]]["roof"]["w"], 1), loads[r["B"]]["roof"]["governs"], "| floor", round(loads[r["B"]]["floor"]["w"], 1), loads[r["B"]]["floor"]["governs"])
# seismic, for the record (weights: roof 20 psf and wall 35 psf from S0; floor 15 psf from the sealed package (112 plf on 7.5 ft))
roofA, flrA, perim = 27.25 * 29.6 + 2 * (2 * 27.25 + 29.6) , 27.25 * 29.6, 2 * 27.25 + 2 * 29.6
w_roof = (roofA * 20 + perim * 4.5 * 35) / 1000
w_flr = (flrA * 15 + perim * 9 * 35) / 1000
M.append(("seismic_elf", dict(mark="Seismic", SDS="0.225", SD1="0.093", S1="0.058", TL="4", ground_source=S0 + " (Site Class D, Risk Category II); TL: ASCE 7-22 Figure 22-14, to be confirmed on the Hazard Tool",
    risk="II", system="Bearing wall: light-frame (wood) walls sheathed with wood structural panels", Ie="1.0", Ie_source="Risk Category II, Table 1.5-2",
    structure="all other structural systems", hn="20", rho="1.0", rho_source="Seismic Design Category B, Sect. 12.3.4.1",
    levels=[dict(name="Roof", w=f"{w_roof:.1f}", h="20"), dict(name="Main floor", w=f"{w_flr:.1f}", h="10")])))
es, _, _ = calc.build("seismic_elf", M[1][1], proj)
print("seismic", {k: v for k, v in es.seismic.items() if k in ("V", "Cs", "W")}, [{a: (round(b, 2) if isinstance(b, float) else b) for a, b in x.items() if not isinstance(b, (list, dict))} for x in es.seismic["rows"]])
G = dict(G="0.50", G_source="No. 2 Douglas Fir-Larch studs and plates, sheet S0 Timber Notes; NDS Table 12.3.3A")
DI = dict(G, panel="Sheathing and Single-Floor, 15/32 in, 8d common", edges="unblocked", face="2", case="Case 1", panel_type="OSB", load="wind")
SW = dict(G, panel="Sheathing, 7/16 in, 8d common", spacing="6", panel_type="OSB", sides="one side", blocking="blocked", h="9", load="wind", holddown="no")
R = {}
for B, L, Wd, tag, lines in ((27.25, 27.25, 29.6, "wind on Line 1", ("A", "B")), (29.6, 29.6, 27.25, "wind on Line A or B", ("1", "2"))):
    d = loads[B]
    for lev, key, z in (("Roof", "roof", f"14.5 to {d['top']:g}"), ("Main floor", "floor", "4.5 to 14.5")):
        w = 0.6 * d[key]["w"]
        M.append(("diaphragm", dict(DI, mark=f"{lev} diaphragm, {tag}", L=str(L), W=str(Wd), w=f"{w:.1f}",
                 w_source=f"sheet Wind, {d['title'].lower()}, walls from {z} ft: {d[key]['w']:.1f} plf x 0.6")))
        for ln in lines:
            R[(lev, ln)] = w * L / 2
SEG = {("Roof", "1"): "2.67", ("Roof", "A"): "7.58, 5.33, 4.67", ("Roof", "B"): "5.33, 7.08, 4.17",
       ("Main floor", "1"): "16.75", ("Main floor", "A"): "22.58, 4.67", ("Main floor", "B"): "5.33, 14.75"}
for (lev, ln), seg in SEG.items():
    V = R[("Roof", ln)] + (R[("Main floor", ln)] if lev == "Main floor" else 0)
    story = "main level" if lev == "Roof" else "lower level"
    src = (f"roof diaphragm {R[('Roof', ln)]:.0f} lb" + (f" + main floor diaphragm {R[('Main floor', ln)]:.0f} lb" if lev == "Main floor" else "")) + ", half the diaphragm load to each line"
    M.append(("shear_wall", dict(SW, mark=f"Line {ln}, {story}", lengths=seg, V=f"{V:.0f}", v_source=src)))
json.dump(dict(format="strukit-project", version=1, project=proj, members=[dict(kind=k, values=v) for k, v in M]), open("/home/claude/jobs/2026-011/2026-011-Lateral.strukit", "w"), indent=1)
print({k: round(v) for k, v in R.items()})
for k, v in M:
    r = calc.results(k, v, proj)
    print(f"== {v['mark']} [{k}] {r.get('state')} {r.get('status','')}")
    for m_ in r.get("messages", [])[:4]: print("   !", m_[:300])
    for row in r.get("rows", []):
        print(f"   {row.get('check','')[:44]:<44} {str(row.get('demand'))[:10]:>10} {str(row.get('capacity'))[:10]:>10} {row.get('unit','')} {row.get('status','')} | {row.get('note','')[:110]}")
