"""Builds a StruKit project like job 2026-030, Wayfarer Vans West Carport (sealed 08/19/2026): eight two-column bents, HSS8x8x1/2 columns,
HSS10x6x3/8 rafters with rigid knees, 18.5 ft between columns, rafters cantilevering 1.0 ft (low side) and 2.25 ft (high side). Test material only.
Inputs are the sealed report's: D 6.1 psf, ps 36.12 psf, free-roof wind 130 mph Exposure C. The roof is modelled level at the mean column height."""
import json, sys
W = dict(mark="WO1", V="130", V_source="sealed report 2026-030, Risk Category II", exposure="C", exposure_basis="sealed report 2026-030", h="13.27", roof="monoslope", theta="4.76",
         L="21.75", width="131", flow="clear", flow_basis="open carport, vehicles under less than 50 percent blockage (sealed report)", Kzt="1.0", Kzt_source="sealed report 2026-030", model_axis="Y", model_low="smaller coordinate", fascia="1.25")
frames = [0, 10, 30, 50, 70, 90, 110, 130]
trib = [5.5, 15, 20, 20, 20, 20, 20, 10.5]
D, S, WD = 6.1, 36.12, 28.18
proj = dict(name="Wayfarer Vans, West Carport (StruKit test run)", number="2026-030", date="2026-11-23", method="LRFD",
            combos_lrfd=[dict(expr="1.4D", source="ASCE/SEI 7-16 Sect. 2.3.1"), dict(expr="1.2D + 1.6S + 0.5W", source="ASCE/SEI 7-16 Sect. 2.3.1"),
                         dict(expr="1.2D + 1.0W + 0.5S", source="ASCE/SEI 7-16 Sect. 2.3.1"), dict(expr="0.9D + 1.0W", source="ASCE/SEI 7-16 Sect. 2.3.1")],
            combos_asd=[dict(expr="D + S", source="ASCE/SEI 7-16 Sect. 2.4.1"), dict(expr="D + 0.6W", source="ASCE/SEI 7-16 Sect. 2.4.1"), dict(expr="D + 0.75S + 0.45W", source="ASCE/SEI 7-16 Sect. 2.4.1")],
            model=dict(levels=[dict(name="Base", elev="0"), dict(name="Roof", elev="11.77")], grids_x=[dict(name=str(i + 1), at=str(x)) for i, x in enumerate(frames)],
                       grids_y=[dict(name="A", at="0"), dict(name="B", at="18.5")]))
ms = [dict(kind="wind_free_roof", values=W)]
for i, (x, t) in enumerate(zip(frames, trib), 1):
    for g, y in (("A", 0), ("B", 18.5)):
        ms.append(dict(kind="hss_column", values=dict(mark=f"C{i}{g}", shape="HSS8X8X1/2", Fy="46", Fy_source="ASTM A500 Grade B (sealed report: 46 ksi)", height="11.77", Kx="1.0", Ky="1.0",
                  k_source="direct analysis method", self_weight="yes", loads=[], moments=[], at_level="Roof", at_base="Base", at_x1=str(x), at_y1=str(y), at_base_fix="fixed")))
    ld = lambda c, q, note: dict(case=c, kind="uniform", mag=f"{q * t / 1000:.4f}", x1="", x2="", label=f"{note} {q:g} psf x {t:g} ft")
    ms.append(dict(kind="steel_beam", values=dict(mark=f"R{i}", shape="HSS10X6X3/8", Fy="46", support_type="", span="18.5", more_spans="", oh_left="1.0", oh_right="2.25", bracing="continuous",
              brace_pts="", self_weight="yes", loads=[ld("D", D, "roof dead load"), ld("S", S, "roof snow load"), ld("W", WD, "wind, downward case")],
              defl=[dict(label="snow", expr="S", ratio="180", source="sealed report 2026-030")], at_level="Roof", at_x1=str(x), at_y1="-1", at_x2=str(x), at_y2="20.75")))
json.dump(dict(format="strukit-project", version=1, project=proj, members=ms), open(sys.argv[1] if len(sys.argv) > 1 else "tests/data/job_2026_030_west.strukit", "w"), indent=1)
