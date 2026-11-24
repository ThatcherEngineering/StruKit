"""Worksheet screens: the forms, and the bridge from what is typed to the calculations.

Each worksheet kind has a form description (fields and tables) that the screen draws,
and a function that turns the typed values into the same worksheet objects the tests
exercise. Nothing typed is defaulted here: a blank required box comes back as a message
naming the box, and all such messages come back together.
"""
import re

from .. import calcsheet, glulam, ijoist, scl, shapes, shearwall, snow, wood, ws_conn, ws_footing, ws_frame, ws_more, ws_steel_beam, ws_steel_column, ws_wood
from ..footing import FootingInputError
from ..steel_beam import SteelInputError
from ..ws_steel_beam import Combo, DeflCheck, WorksheetError


class Missing(Exception):
    def __init__(self, items):
        super().__init__("; ".join(items))
        self.items = items


def F(key, label, kind="number", unit="", options=None, required=True, help=""):
    return dict(key=key, label=label, type=kind, unit=unit, options=options, required=required, help=help)


def T(key, label, columns, help=""):
    return dict(key=key, label=label, columns=columns, help=help)


CASE = F("case", "Case", "text", help="D, L, Lr, S, W, E, Em (seismic with overstrength) ...")
FORMS = {
    "steel_beam": dict(
        title="Steel Beam", code="AISC 360-22", mark="B",
        fields=[F("shape", "Section", "shape_any", help="W, M, S or HP shape, C or MC channel, square, rectangular or round HSS, or pipe"), F("Fy", "Fy", unit="ksi"), F("span", "Span", unit="ft"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False, help="separated by commas, left to right after the first span; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load and brace positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("bracing", "Compression flange braced", "select", options=["continuous", "at points"]),
                F("brace_pts", "Brace points", "text", "ft", required=False,
                  help="distances from the left end, separated by commas; the ends are always braced"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point"]),
                                     F("mag", "Load", unit="k/ft or k"),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "steel_column": dict(
        title="Steel Column", code="AISC 360-22", mark="C",
        fields=[F("shape", "Section", "shape_col", help="W, M, S or HP shape, HSS or pipe"), F("Fy", "Fy", unit="ksi"), F("height", "Height", unit="ft"),
                F("ends", "Top of column", "select",
                  options=["held sideways (braced)", "free about x (cantilever, strong axis)",
                           "free about y (cantilever, weak axis)", "free both ways (cantilever)"]),
                F("Lx", "Unbraced length, x axis", unit="ft", required=False, help="blank = full height"),
                F("Ly", "Unbraced length, y axis", unit="ft", required=False, help="blank = full height"),
                F("Kx", "Kx"), F("Ky", "Ky"), F("k_source", "K comes from", "text"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("loads", "Axial loads", [CASE, F("P", "P", unit="kip"), F("label", "Note", "text", required=False)]),
                T("lateral", "Sideways loads", [CASE, F("bending", "Bends about", "select", options=["x", "y"]),
                                                F("kind", "Type", "select", options=["uniform", "point"]),
                                                F("mag", "Load", unit="k/ft or k"),
                                                F("x", "Height", unit="ft", required=False, help="point loads: height above the base"),
                                                F("label", "Note", "text", required=False)]),
                T("leaning", "Loads leaning on this column (cantilever only)", [CASE, F("P", "P", unit="kip")]),
                T("drift", "Drift limits at the top (cantilever only)",
                  [F("label", "Name", "text"), F("expr", "Loads", "text"), F("ratio", "Height /"), F("source", "Source", "text")])]),
    "stair_stringer": dict(
        title="Steel Stair Stringer", code="AISC 360-22", mark="ST",
        fields=[F("shape", "Stringer section", "shape_any", help="C or MC channel, W shape, HSS or pipe"), F("Fy", "Fy", unit="ksi"),
                F("run", "Horizontal run between supports", unit="ft"),
                F("riser", "Riser height", unit="in"), F("tread", "Tread length", unit="in"),
                F("trib", "Tread width carried by this stringer", unit="ft", help="half the stair width for a stair on two stringers"),
                F("dead", "Dead load of treads, risers and finishes", unit="psf", help="on the horizontal projection"),
                F("dead_note", "What that dead load is", "text", help="for example: 12 ga pans with 2 in. concrete fill"),
                F("extra", "Other dead load on the stringer", unit="lb/ft", required=False, help="per foot of run, for example a guard"),
                F("extra_note", "What the other dead load is", "text", required=False),
                F("occupancy", "Live load", "select", options=["stairs and exit ways", "one- and two-family dwellings"], help="100 psf or 40 psf, ASCE 7-22 Table 4.3-1"),
                F("braced", "Treads and risers brace the stringer", "select", options=["yes", "no"])],
        tables=[T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text"), F("ratio", "Run /"), F("source", "Source", "text")])]),
    "stair_tread": dict(
        title="Stair Tread (bent plate)", code="AISC 360-22", mark="TR",
        fields=[F("t", "Plate thickness", unit="in"), F("b", "Tread width", unit="in"), F("d", "Leg depth, overall", unit="in", help="legs turned down at both edges"),
                F("span", "Span between stringers", unit="ft"), F("Fy", "Plate yield stress, Fy", unit="ksi"),
                F("Fy_source", "Where that Fy comes from", "text", help="for example: ASTM A36; raised pattern floor plate (A786) has no specified yield, verify"),
                F("live_psf", "Uniform live load", unit="psf"), F("live_P", "Concentrated live load", unit="lb"),
                F("live_source", "Where the live loads come from", "text", help="for example: ASCE/SEI 7-22 Table 4.3-1, stairs: 100 psf or 300 lb")],
        tables=[]),
    "tension_member": dict(
        title="Steel Tension Member", code="AISC 360-22", mark="TM",
        fields=[F("shape", "Section", "shape_tension", help="W, M, S, HP, C, MC, HSS, pipe or single angle (for example L3x3x3/16)"), F("Fy", "Fy", unit="ksi"), F("Fu", "Fu", unit="ksi"),
                F("steel_source", "Where Fy and Fu come from", "text", help="for example: ASTM A992"), F("length", "Length", unit="ft"),
                F("n_holes", "Bolt holes across the critical section", required=False, help="blank or 0 for a welded end"),
                F("bolt_d", "Bolt diameter", unit="in", required=False), F("hole_t", "Thickness of the part the holes are in", unit="in", required=False),
                F("U", "Shear lag factor, U", help="AISC 360-22 Table D3.1"), F("U_source", "Which case of Table D3.1", "text", help="for example: Case 2, 1 - x/l, x = 0.831 in., l = 9 in.")],
        tables=[T("loads", "Axial tension", [CASE, F("P", "Tension", unit="kip"), F("label", "Note", "text", required=False)])]),
    "hss_column": dict(
        title="HSS or Pipe Column", code="AISC 360-22", mark="HC",
        fields=[F("shape", "Section", "hss_shape", help="square, rectangular or round HSS, or pipe, by its Manual label: HSS6x6x1/4, HSS8x4x3/16, HSS5.563x0.258, Pipe 4 STD"),
                F("Fy", "Fy", unit="ksi"), F("Fy_source", "Where Fy comes from", "text", help="for example: ASTM A500 Grade C"),
                F("height", "Height", unit="ft"), F("Kx", "Kx"), F("Ky", "Ky"), F("k_source", "K comes from", "text"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("loads", "Axial loads", [CASE, F("P", "P", unit="kip"), F("label", "Note", "text", required=False)]),
                T("moments", "Moments (first-order)", [CASE, F("Mx", "Mx", unit="kip-ft", required=False), F("My", "My", unit="kip-ft", required=False),
                                                       F("label", "Note", "text", required=False)],
                  help="Optional. The largest moment along the height for each load case, for example an eccentric beam reaction.")]),
    "footing_iso": dict(
        title="Isolated Footing", code="ACI 318-19", mark="F",
        fields=[F("B", "Width, x", unit="ft"), F("L", "Length, y", unit="ft"), F("h", "Thickness", unit="in"),
                F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"), F("conc_pcf", "Concrete weight", unit="pcf"),
                F("col_x", "Column, x", unit="in"), F("col_y", "Column, y", unit="in"),
                F("supported", "Column is", "select", options=["steel", "wood", "concrete"]),
                F("plate_x", "Base plate, x", unit="in", required=False), F("plate_y", "Base plate, y", unit="in", required=False),
                F("bar", "Bar size #"), F("n_x", "Bars in x"), F("n_y", "Bars in y"), F("cover", "Clear cover", unit="in"),
                F("bottom", "Lowest bars run in", "select", options=["x", "y"]),
                F("P_service", "Service load", unit="lb"), F("service_combo", "Service combination", "text"),
                F("Pu", "Factored load", unit="lb"), F("strength_combo", "Strength combination", "text"),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False),
                F("loads_from", "Loads come from", "text", required=False, help="printed on the sheet")],
        tables=[]),
    "footing_cont": dict(
        title="Continuous Footing", code="ACI 318-19", mark="CF",
        fields=[F("W", "Width", unit="ft"), F("h", "Thickness", unit="in"), F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"),
                F("conc_pcf", "Concrete weight", unit="pcf"), F("wall", "Wall thickness", unit="in"),
                F("wall_kind", "Wall is", "select", options=["concrete", "masonry"]),
                F("stem_h", "Stem wall height", unit="in", required=False), F("stem_pcf", "Stem wall weight", unit="pcf", required=False),
                F("bar_t", "Bars across, size #"), F("spacing_t", "Bars across, spacing", unit="in"),
                F("bar_l", "Bars lengthwise, size #"), F("n_l", "Bars lengthwise, number"), F("cover", "Clear cover", unit="in"),
                F("P_service", "Service wall load", unit="lb/ft"), F("service_combo", "Service combination", "text"),
                F("Pu", "Factored wall load", unit="lb/ft"), F("strength_combo", "Strength combination", "text"),
                F("dead_factor", "Dead-load factor of that combination", help="applied to the stem wall weight"),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False)],
        tables=[]),
    "frame": dict(
        title="Moment Frame", code="AISC 360-22", mark="FR",
        fields=[F("bays", "Bay widths", "text", "ft", help="left to right, separated by commas"),
                F("stories", "Story heights", "text", "ft", help="bottom to top (to the eave for a sloped roof)"),
                F("base", "Column bases", "select", options=["pin", "fixed"]),
                F("roof", "Roof", "select", options=["flat", "gable", "mono"]),
                F("rise", "Roof rise", unit="ft", required=False),
                F("col_shape", "Columns", "shape_col"), F("beam_shape", "Beams", "shape_col"),
                F("rafter_shape", "Rafters", "shape_col", required=False), F("Fy", "Fy", unit="ksi"),
                F("lb_col", "Columns braced out of plane at", unit="ft"), F("lb_beam", "Beams braced at", unit="ft"),
                F("lb_rafter", "Rafters braced at", unit="ft", required=False),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"])],
        tables=[T("shape_of", "Section for one member (optional)", [F("member", "Member", "text"), F("shape", "Section", "shape_col")]),
                T("loads", "Loads", [CASE, F("where", "On", "text", help="beams, rafters, columns, level:1, a member name; "
                                                                             "joint N1-1; or lateral level:1"),
                                     F("kind", "Type", "select", options=["gravity per ft of member", "gravity per ft horizontal",
                                                                          "sideways per ft of member", "joint load", "lateral at level"]),
                                     F("mag", "Load", unit="k/ft or k"), F("Fx", "Joint Fx", unit="kip", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("leaning", "Loads on columns outside the frame", [CASE, F("level", "Level"), F("P", "P", unit="kip")]),
                T("drift", "Story drift limits", [F("label", "Name", "text"), F("expr", "Loads", "text"),
                                                  F("ratio", "Story height /"), F("source", "Source", "text")])]),
    "weld": dict(
        title="Fillet Weld", code="AISC 360-22", mark="W",
        fields=[F("size", "Weld size (leg)", unit="in"), F("length", "Length of each weld", unit="in"),
                F("n_lines", "Number of welds"), F("FEXX", "Electrode FEXX", unit="ksi"),
                F("theta", "Angle of load to weld axis", unit="deg", help="0 = load along the weld, 90 = across it"),
                F("directional", "Use the directional increase", "select", options=["yes", "no"], help="Eq. J2-5"),
                F("end_loaded", "End loaded", "select", options=["yes", "no"], help="J2.2b(d): long welds loaded from one end"),
                F("t_thinner", "Thinner part joined", unit="in", required=False, help="turns on the minimum size check"),
                F("t_edge", "Thickness at the welded edge", unit="in", required=False, help="turns on the maximum size check"),
                F("base_t", "Base metal thickness", unit="in", required=False),
                F("base_Fu", "Base metal Fu", unit="ksi", required=False)],
        tables=[T("loads", "Force on the weld group", [CASE, F("P", "Force", unit="kip"), F("label", "Note", "text", required=False)])]),
    "bolts": dict(
        title="Bolt Line", code="AISC 360-22", mark="BG",
        fields=[F("d", "Bolt diameter", unit="in"), F("group", "Bolt type", "select", options=["A325", "A490", "A307", "F3148"]),
                F("n", "Number of bolts"), F("spacing", "Spacing", unit="in"),
                F("edge", "Edge distance", unit="in", help="bolt centre to the edge the load pushes toward"),
                F("threads", "Threads", "select", options=["N", "X"], help="N = in the shear plane, X = excluded"),
                F("planes", "Shear planes"),
                F("deformation", "Hole deformation is a design consideration", "select", options=["yes", "no"])],
        tables=[T("plies", "Connected parts", [F("t", "Thickness", unit="in"), F("Fu", "Fu", unit="ksi"),
                                               F("has_edge", "Edge in load direction", "select", options=["yes", "no"]),
                                               F("count", "How many", required=False, help="2 for a pair of angles")]),
                T("loads", "Force along the bolt line", [CASE, F("P", "Force", unit="kip"), F("label", "Note", "text", required=False)])]),
    "single_plate": dict(
        title="Single-Plate Shear Connection (shear tab)", code="AISC 360-22", mark="SP",
        fields=[F("column", "HSS column", "hss_shape", required=False, help="leave blank for a column flange or girder web and fill the three support boxes"),
                F("col_Fy", "HSS column Fy", unit="ksi", required=False), F("col_Fu", "HSS column Fu", unit="ksi", required=False), F("col_source", "Source of the column Fy and Fu", "text", required=False),
                F("support_name", "Other support: what the plate is welded to", "text", required=False, help="for example: W14x90 column flange, or W24x55 girder web"),
                F("support_t", "Other support: thickness at the weld", unit="in", required=False), F("support_Fu", "Other support: Fu", unit="ksi", required=False),
                F("beam", "Beam", "shape"), F("beam_Fu", "Beam Fu", unit="ksi"), F("beam_source", "Source of the beam Fu", "text"),
                F("tp", "Plate thickness", unit="in"), F("plate_Fy", "Plate Fy", unit="ksi"), F("plate_Fu", "Plate Fu", unit="ksi"), F("plate_source", "Source of the plate Fy and Fu", "text"),
                F("d", "Bolt diameter", unit="in"), F("group", "Bolt type", "select", options=["A325", "A490", "F3148"]),
                F("threads", "Threads", "select", options=["N", "X"], help="N = in the shear plane, X = excluded"),
                F("n", "Number of bolts", help="one vertical row, 2 to 5"), F("spacing", "Bolt spacing", unit="in"),
                F("lev", "Vertical edge distance", unit="in", help="bolt centre to the top and bottom of the plate"),
                F("leh", "Horizontal edge distance", unit="in", help="bolt centre to the free end of the plate"),
                F("a", "Weld line to bolt line, a", unit="in", help="3-1/2 in. or less"),
                F("holes", "Holes in the plate", "select", options=["STD", "SSLT"], help="SSLT = horizontal short slots"),
                F("weld", "Fillet weld size, each side", unit="in"), F("FEXX", "Electrode strength", unit="ksi")],
        tables=[T("loads", "Beam end reaction", [CASE, F("P", "Reaction", unit="kip"), F("label", "Note", "text", required=False)])]),
    "wood_beam": dict(
        title="Wood Beam", code="2018 NDS", mark="WB",
        fields=[F("species", "Species", "select",
                  options=["DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR"]
                  + [x for x in sorted(set(wood.SPECIES) | set(wood.TIMBER_SPECIES) | set(wood.SP_SPECIES)) if x not in ("DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR")],
                  help="2018 NDS Supplement Table 4A (2 to 4 in. thick), Table 4B (Southern Pine, 2 to 4 in. thick) or Table 4D (5x5 and larger)"),
                F("grade", "Grade", "select", options=["Select Structural", "No. 1 & Btr", "No. 1", "No. 2", "No. 1/ No. 2", "No. 3",
                                                        "Stud", "Construction", "Standard", "Utility", "Dense Select Structural",
                                                        "Dense No. 1", "No. 2 Dense", "No. 1 Dense", "No. 1 Non-Dense", "No. 2 Non-Dense",
                                                        "Non-Dense Select Structural"]),
                F("size", "Size (nominal)", "select", options=list(wood.SIZES) + list(wood.TIMBER_SIZES)),
                F("plies", "Number of plies", "select", options=["1", "2", "3", "4", "5", "6"]),
                F("flat", "Loaded on the wide face (flat use, plank)", "select", options=["no", "yes"], required=False, help="one piece 2 to 4 in. thick; blank = no"),
                F("span", "Span", unit="ft"),
                F("spacing", "Member spacing (joists and rafters)", unit="in", required=False, help="needed for area loads in psf"),
                F("rise", "Roof rise in 12 (sloped rafter; spans are horizontal)", required=False, help="blank = level member; dead load is entered along the slope"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False,
                  help="lengths of the second and later spans, separated by commas; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("snow_partial", "Partial snow loading (more spans or an overhang)", "select", required=False,
                  options=["apply", "not required: member perpendicular to the ridge, gable roof 1/2 to 7 on 12"],
                  help="ASCE/SEI 7-22 Sect. 7.5.1; blank = apply"),
                F("lu_neg", "Bottom edge unbraced length where it is in compression", unit="ft", required=False,
                  help="needed with more spans or an overhang; 0 = braced"),
                F("bearing_int", "Bearing length at interior supports", unit="in", required=False, help="blank = same as the ends"),
                F("bracing", "Compression edge", "select", options=["supported throughout", "braced at a spacing"]),
                F("lu", "Brace spacing (unbraced length)", unit="ft", required=False),
                F("bearing", "Bearing length at each support", unit="in"),
                F("service", "Moisture", "select", options=["dry service", "wet service"], help="wet: moisture content above 19 percent for an extended time"),
                F("incised", "Incised", "select", options=["yes", "no"]),
                F("repetitive", "Repetitive member", "select", options=["yes", "no"],
                  help="joists, rafters or similar at 24 in. or less, three or more, joined by sheathing (NDS 4.3.9)"),
                F("unit_weight", "Wood unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point", "area"]),
                                     F("mag", "Load", unit="plf, lb or psf"),
                                     F("mag2", "Load at the To end (tapered load)", unit="plf or psf", required=False),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "decking": dict(
        title="Lumber Decking", code="2018 NDS", mark="DK",
        fields=[F("species", "Species", "select", options=["DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR"]
                  + [x for x in wood.DECKING_SPECIES if x not in ("DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR")], help="2018 NDS Supplement Table 4E"),
                F("grade", "Grade", "select", options=["Select Dex", "Commercial Dex", "Selected", "Select", "Commercial"]),
                F("thickness", "Nominal thickness", "select", options=["2", "3", "4"], unit="in"),
                F("span", "Span", unit="ft"),
                F("layout", "Layout", "select", options=["simple span", "two equal spans"]),
                F("repetitive", "Repetitive member use", "select", options=["yes", "no"], help="Table 4E lists (Fb)(Cr) for repetitive use and Fb for single member use"),
                F("service", "Moisture", "select", options=["dry service", "wet service"])],
        tables=[T("loads", "Loads", [CASE, F("q", "Load", unit="psf"), F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "lvl_beam": dict(
        title="LVL Beam", code="2018 NDS, ICC-ES ESR-1040", mark="LB",
        fields=[F("grade", "Versa-Lam grade", "select", options=["2.1E 2800", "2.1E 3100", "1.8E 2650", "1.7E 2650"]
                  + [g for g in scl.GRADES if g not in ("2.1E 2800", "2.1E 3100", "1.8E 2650", "1.7E 2650")],
                  help="ICC-ES ESR-1040 Table 1; use the grade stamped on the product"),
                F("thickness", "Thickness of one ply", unit="in", help="1.75, 3.5, 5.25 or 7"),
                F("depth", "Depth", unit="in", help="for example 9.5, 11.875, 14, 16, 18"),
                F("plies", "Number of plies", "select", options=["1", "2", "3", "4"]),
                F("span", "Span", unit="ft"),
                F("spacing", "Member spacing (joists and rafters)", unit="in", required=False, help="needed for area loads in psf"),
                F("rise", "Roof rise in 12 (sloped rafter; spans are horizontal)", required=False, help="blank = level member; dead load is entered along the slope"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False,
                  help="lengths of the second and later spans, separated by commas; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("snow_partial", "Partial snow loading (more spans or an overhang)", "select", required=False,
                  options=["apply", "not required: member perpendicular to the ridge, gable roof 1/2 to 7 on 12"],
                  help="ASCE/SEI 7-22 Sect. 7.5.1; blank = apply"),
                F("lu_neg", "Bottom edge unbraced length where it is in compression", unit="ft", required=False,
                  help="needed with more spans or an overhang; 0 = braced"),
                F("bearing_int", "Bearing length at interior supports", unit="in", required=False, help="blank = same as the ends"),
                F("bracing", "Compression edge", "select", options=["supported throughout", "braced at a spacing"]),
                F("lu", "Brace spacing (unbraced length)", unit="ft", required=False),
                F("bearing", "Bearing length at each support", unit="in"),
                F("repetitive", "Repetitive member", "select", options=["yes", "no"],
                  help="joists, studs or similar at 24 in. or less, three or more, joined by sheathing (NDS 8.3.7)"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point", "area"]),
                                     F("mag", "Load", unit="plf, lb or psf"),
                                     F("mag2", "Load at the To end (tapered load)", unit="plf or psf", required=False),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "wey_beam": dict(
        title="Microllam, Parallam or TimberStrand Beam", code="2018 NDS, ICC-ES ESR-1387", mark="LB",
        fields=[F("grade", "Product and grade", "select", options=['Microllam LVL 2.0E-2900Fb WS', 'Parallam PSL 2.2E WS', 'Parallam PSL 2.0E WS', 'TimberStrand LSL 1.55E', 'TimberStrand LSL 1.3E']
                  + [f"{p} {g}" for p in scl.WEY for g in scl.WEY[p] if f"{p} {g}" not in ['Microllam LVL 2.0E-2900Fb WS', 'Parallam PSL 2.2E WS', 'Parallam PSL 2.0E WS', 'TimberStrand LSL 1.55E', 'TimberStrand LSL 1.3E']],
                  help="Weyerhaeuser, ICC-ES ESR-1387 Table 1; use the grade stamped on the product"),
                F("thickness", "Thickness of one ply", unit="in", help="Microllam 1.75; Parallam 3.5, 5.25 or 7; TimberStrand 1.75 or 3.5"),
                F("depth", "Depth", unit="in", help="for example 9.5, 11.875, 14, 16, 18"),
                F("plies", "Number of plies", "select", options=["1", "2", "3", "4"]),
                F("span", "Span", unit="ft"),
                F("spacing", "Member spacing (joists and rafters)", unit="in", required=False, help="needed for area loads in psf"),
                F("rise", "Roof rise in 12 (sloped rafter; spans are horizontal)", required=False, help="blank = level member; dead load is entered along the slope"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False,
                  help="lengths of the second and later spans, separated by commas; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("snow_partial", "Partial snow loading (more spans or an overhang)", "select", required=False,
                  options=["apply", "not required: member perpendicular to the ridge, gable roof 1/2 to 7 on 12"],
                  help="ASCE/SEI 7-22 Sect. 7.5.1; blank = apply"),
                F("lu_neg", "Bottom edge unbraced length where it is in compression", unit="ft", required=False,
                  help="needed with more spans or an overhang; 0 = braced"),
                F("bearing_int", "Bearing length at interior supports", unit="in", required=False, help="blank = same as the ends"),
                F("bracing", "Compression edge", "select", options=["supported throughout", "braced at a spacing"]),
                F("lu", "Brace spacing (unbraced length)", unit="ft", required=False),
                F("bearing", "Bearing length at each support", unit="in"),
                F("repetitive", "Repetitive member", "select", options=["yes", "no"],
                  help="joists, studs or similar at 24 in. or less, three or more, joined by sheathing (NDS 8.3.7)"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point", "area"]),
                                     F("mag", "Load", unit="plf, lb or psf"),
                                     F("mag2", "Load at the To end (tapered load)", unit="plf or psf", required=False),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "wood_post": dict(
        title="Wood Post", code="2018 NDS", mark="WP",
        fields=[F("species", "Species", "select",
                  options=["DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR"]
                  + [x for x in sorted(set(wood.SPECIES) | set(wood.TIMBER_SPECIES) | set(wood.SP_SPECIES)) if x not in ("DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR")],
                  help="2018 NDS Supplement Table 4A or 4B (Southern Pine), 3 and 4 in. thick, or Table 4D (5x5 and larger)"),
                F("grade", "Grade", "select", options=["Select Structural", "No. 1 & Btr", "No. 1", "No. 2", "No. 1/ No. 2", "No. 3",
                                                        "Stud", "Construction", "Standard", "Utility", "Dense Select Structural",
                                                        "Dense No. 1", "No. 2 Dense", "No. 1 Dense", "No. 1 Non-Dense", "No. 2 Non-Dense", "Non-Dense Select Structural"]),
                F("size", "Size (nominal)", "select", options=[x for x in wood.SIZES if x.split("x")[0] in ("3", "4")] + list(wood.TIMBER_SIZES)),
                F("height", "Height", unit="ft"),
                F("lu1", "Unbraced length, larger dimension", unit="ft", required=False, help="blank = full height"),
                F("lu2", "Unbraced length, smaller dimension", unit="ft", required=False, help="blank = full height"),
                F("Ke1", "Ke, larger dimension"), F("Ke2", "Ke, smaller dimension"),
                F("k_source", "Ke comes from", "text", help="for example: pinned top and bottom, NDS Appendix G"),
                F("service", "Moisture", "select", options=["dry service", "wet service"]),
                F("incised", "Incised", "select", options=["yes", "no"]),
                F("e1", "Load eccentricity, parallel to the larger dimension", unit="in", required=False, help="blank = 0"),
                F("e2", "Load eccentricity, parallel to the smaller dimension", unit="in", required=False, help="blank = 0"),
                F("unit_weight", "Wood unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="lb"), F("label", "Note", "text", required=False)]),
                T("lateral", "Lateral load on the narrow face (bending about the strong axis)",
                  [CASE, F("kind", "Type", "select", options=["uniform", "point"]), F("mag", "Load", unit="plf or lb"),
                   F("x", "At (point load)", unit="ft", required=False), F("label", "Note", "text", required=False)],
                  help="leave empty for an axially loaded post")]),
    "glulam_beam": dict(
        title="Glulam Beam", code="2018 NDS", mark="GB",
        fields=[F("stress_class", "Stress class", "select", options=["24F-V4 DF/DF", "24F-1.8E"] + [k for k in glulam.CLASSES if k not in ("24F-V4 DF/DF", "24F-1.8E")],
                  help="2018 NDS Supplement Table 5A"),
                F("species", "Species", "select", options=["Douglas Fir or other", "Southern Pine"], help="sets the volume factor exponent"),
                F("b", "Width", unit="in", help="for example 3.125, 5.125, 5.5, 6.75, 8.75"),
                F("d", "Depth", unit="in"),
                F("span", "Span", unit="ft"),
                F("spacing", "Member spacing", unit="in", required=False, help="needed for area loads in psf"),
                F("rise", "Roof rise in 12 (sloped rafter; spans are horizontal)", required=False, help="blank = level member; dead load is entered along the slope"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False,
                  help="lengths of the second and later spans, separated by commas; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("snow_partial", "Partial snow loading (more spans or an overhang)", "select", required=False,
                  options=["apply", "not required: member perpendicular to the ridge, gable roof 1/2 to 7 on 12"],
                  help="ASCE/SEI 7-22 Sect. 7.5.1; blank = apply"),
                F("lu_neg", "Bottom edge unbraced length where it is in compression", unit="ft", required=False,
                  help="needed with more spans or an overhang; 0 = braced"),
                F("bearing_int", "Bearing length at interior supports", unit="in", required=False, help="blank = same as the ends"),
                F("bracing", "Compression edge", "select", options=["supported throughout", "braced at a spacing"]),
                F("lu", "Brace spacing (unbraced length)", unit="ft", required=False),
                F("bearing", "Bearing length at each support", unit="in"),
                F("service", "Moisture", "select", options=["dry service", "wet service"], help="wet: moisture content 16 percent or more"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["uniform", "point", "area"]),
                                     F("mag", "Load", unit="plf, lb or psf"),
                                     F("mag2", "Load at the To end (tapered load)", unit="plf or psf", required=False),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "glulam_post": dict(
        title="Glulam Column", code="2018 NDS", mark="GC",
        fields=[F("combination", "Combination (Table 5B)", "select", options=["3 (DF L2D)"] + [k for k in glulam.COLUMNS if k != "3 (DF L2D)"],
                  help="2018 NDS Supplement Table 5B; Combination 3 is Boise's stock column grade"),
                F("b", "Width (lamination width)", unit="in", help="for example 3.125, 3.5, 5.125, 5.5, 6.75, 8.75"),
                F("d", "Depth (stack of laminations)", unit="in", help="15 in. maximum"),
                F("lams", "Number of laminations", help="depth divided by the lamination thickness"),
                F("height", "Height", unit="ft"),
                F("lu_d", "Unbraced length, along the depth", unit="ft", required=False, help="blank = full height"),
                F("lu_b", "Unbraced length, along the width", unit="ft", required=False, help="blank = full height"),
                F("Ke_d", "Ke, along the depth"), F("Ke_b", "Ke, along the width"),
                F("k_source", "Ke comes from", "text", help="for example: pinned top and bottom, NDS Appendix G"),
                F("e_d", "Load eccentricity, along the depth", unit="in", required=False, help="blank = 0"),
                F("e_b", "Load eccentricity, along the width", unit="in", required=False, help="blank = 0"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="lb"), F("label", "Note", "text", required=False)])]),
    "builtup_post": dict(
        title="Built-Up Wood Column", code="2018 NDS", mark="BC",
        fields=[F("species", "Species", "select",
                  options=["DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR"] + [x for x in sorted(set(wood.SPECIES) | set(wood.SP_SPECIES)) if x not in ("DOUGLAS FIR-LARCH", "HEM-FIR", "SPRUCE-PINE-FIR")],
                  help="2018 NDS Supplement Table 4A, or Table 4B for Southern Pine"),
                F("grade", "Grade", "select", options=["No. 2", "Select Structural", "No. 1 & Btr", "No. 1", "No. 1/ No. 2", "No. 3", "Stud",
                                                        "Construction", "Standard", "Utility", "Dense Select Structural", "No. 1 Dense", "No. 1 Non-Dense",
                                                        "No. 2 Dense", "No. 2 Non-Dense", "Non-Dense Select Structural"]),
                F("size", "Lamination size (nominal)", "select", options=[x for x in wood.SIZES if x.split("x")[0] == "2"]),
                F("plies", "Number of laminations", "select", options=["2", "3", "4", "5"]),
                F("fastening", "Fastened together by", "select", options=["nailed", "bolted"], help="NDS 15.3.3 or 15.3.4"),
                F("height", "Height", unit="ft"),
                F("lu_d", "Unbraced length, across the lamination face width", unit="ft", required=False, help="blank = full height"),
                F("lu_stack", "Unbraced length, across the laminations", unit="ft", required=False, help="blank = full height"),
                F("Ke_d", "Ke, across the face width"), F("Ke_stack", "Ke, across the laminations"),
                F("k_source", "Ke comes from", "text", help="for example: pinned top and bottom, NDS Appendix G"),
                F("service", "Moisture", "select", options=["dry service", "wet service"]),
                F("incised", "Incised", "select", options=["no", "yes"]),
                F("unit_weight", "Wood unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="lb"), F("label", "Note", "text", required=False)])]),
    "ijoist": dict(
        title="I-Joist", code="2018 NDS, ICC-ES ESR-1336, ESR-1153", mark="J",
        fields=[F("name", "Joist series", "select", options=list(ijoist.NAMES), help="Boise BCI (ESR-1336) or Weyerhaeuser TJI (ESR-1153)"),
                F("depth", "Depth", "select", options=[f"{d:g}" for d in ijoist.DEPTHS], unit="in"),
                F("span", "Span", unit="ft"),
                F("spacing", "Joist spacing", unit="in", required=False, help="needed for area loads in psf"),
                F("bearing", "Bearing length at each end", unit="in", help="1.5 in. minimum for BCI, 1.75 in. for TJI"),
                F("stiffeners", "Web stiffeners at the end bearing", "select", options=["no", "yes"]),
                F("rise", "Roof rise in 12 (sloped rafter; spans are horizontal)", required=False, help="blank = level member; dead load is entered along the slope"),
                F("more_spans", "More spans (continuous over supports)", "text", "ft", required=False,
                  help="lengths of the second and later spans, separated by commas; blank = one span"),
                F("oh_left", "Overhang past the left support", unit="ft", required=False, help="load positions are measured from the left end of the member"),
                F("oh_right", "Overhang past the right support", unit="ft", required=False),
                F("snow_partial", "Partial snow loading (more spans or an overhang)", "select", required=False,
                  options=["apply", "not required: member perpendicular to the ridge, gable roof 1/2 to 7 on 12"],
                  help="ASCE/SEI 7-22 Sect. 7.5.1; blank = apply"),
                F("bearing_int", "Bearing length at intermediate supports", unit="in", required=False, help="3.5 in. minimum; needed with more spans"),
                F("stiffeners_int", "Web stiffeners at intermediate supports", "select", options=["no", "yes"], required=False),
                F("flange", "Compression flange supported throughout (sheathing)", "select", options=["yes", "no"], help="NDS 7.3.5")],
        tables=[T("loads", "Loads", [CASE, F("kind", "Type", "select", options=["area", "uniform", "point"]),
                                     F("mag", "Load", unit="psf, plf or lb"),
                                     F("mag2", "Load at the To end (tapered load)", unit="psf or plf", required=False),
                                     F("x1", "From / at", unit="ft", required=False),
                                     F("x2", "To", unit="ft", required=False),
                                     F("label", "Note", "text", required=False)]),
                T("defl", "Deflection limits", [F("label", "Name", "text"), F("expr", "Loads", "text", help="for example L, or D + L"),
                                                F("ratio", "Span /"), F("source", "Source", "text")])]),
    "lvl_post": dict(
        title="LVL Column", code="2018 NDS, ICC-ES ESR-1040", mark="LC",
        fields=[F("grade", "Versa-Lam grade", "select", options=["1.8E 2650", "2.1E 3100", "2.1E 2800", "1.8E 2400"]
                  + [g for g in scl.GRADES if g not in ("1.8E 2650", "2.1E 3100", "2.1E 2800", "1.8E 2400")],
                  help="ICC-ES ESR-1040 Table 1; use the grade stamped on the product"),
                F("b", "Section, one side (the thickness of one ply when built up)", unit="in", help="3.5, 5.25 or 7; or 1.75 per ply"),
                F("plies", "Number of plies", "select", options=["1", "2", "3", "4", "5"], required=False, help="blank = one piece"),
                F("fastening", "Plies fastened by", "select", options=["nailed", "bolted"], required=False, help="NDS 15.3.3 or 15.3.4"),
                F("d", "Section, other side", unit="in"),
                F("height", "Height", unit="ft"),
                F("lu1", "Unbraced length, larger dimension", unit="ft", required=False, help="blank = full height"),
                F("lu2", "Unbraced length, smaller dimension", unit="ft", required=False, help="blank = full height"),
                F("Ke1", "Ke, larger dimension"), F("Ke2", "Ke, smaller dimension"),
                F("k_source", "Ke comes from", "text", help="for example: pinned top and bottom, NDS Appendix G"),
                F("e1", "Load eccentricity, parallel to the larger dimension", unit="in", required=False, help="blank = 0"),
                F("e2", "Load eccentricity, parallel to the smaller dimension", unit="in", required=False,
                  help="blank = 0; the manufacturer's column tables use 1/6 of the dimension"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="lb"), F("label", "Note", "text", required=False)]),
                T("lateral", "Lateral load on the narrow face (bending about the strong axis)",
                  [CASE, F("kind", "Type", "select", options=["uniform", "point"]), F("mag", "Load", unit="plf or lb"),
                   F("x", "At (point load)", unit="ft", required=False), F("label", "Note", "text", required=False)],
                  help="leave empty for a column with no lateral load")]),
    "wey_post": dict(
        title="Microllam, Parallam or TimberStrand Column", code="2018 NDS, ICC-ES ESR-1387", mark="LC",
        fields=[F("grade", "Product and grade", "select", options=['Parallam PSL 1.8E WS', 'Parallam PSL 2.2E WS', 'TimberStrand LSL 1.3E', 'TimberStrand LSL 1.55E', 'Microllam LVL 2.0E-2900Fb WS']
                  + [f"{p} {g}" for p in scl.WEY for g in scl.WEY[p] if f"{p} {g}" not in ['Parallam PSL 1.8E WS', 'Parallam PSL 2.2E WS', 'TimberStrand LSL 1.3E', 'TimberStrand LSL 1.55E', 'Microllam LVL 2.0E-2900Fb WS']],
                  help="Weyerhaeuser, ICC-ES ESR-1387 Table 1; use the grade stamped on the product"),
                F("b", "Section, one side (the thickness of one ply when built up)", unit="in"),
                F("plies", "Number of plies", "select", options=["1", "2", "3", "4", "5"], required=False, help="blank = one piece"),
                F("fastening", "Plies fastened by", "select", options=["nailed", "bolted"], required=False, help="NDS 15.3.3 or 15.3.4"),
                F("d", "Section, other side", unit="in"),
                F("height", "Height", unit="ft"),
                F("lu1", "Unbraced length, larger dimension", unit="ft", required=False, help="blank = full height"),
                F("lu2", "Unbraced length, smaller dimension", unit="ft", required=False, help="blank = full height"),
                F("Ke1", "Ke, larger dimension"), F("Ke2", "Ke, smaller dimension"),
                F("k_source", "Ke comes from", "text", help="for example: pinned top and bottom, NDS Appendix G"),
                F("e1", "Load eccentricity, parallel to the larger dimension", unit="in", required=False, help="blank = 0"),
                F("e2", "Load eccentricity, parallel to the smaller dimension", unit="in", required=False,
                  help="blank = 0; Parallam 1.9E and higher take at least t/6 + 5 L^2 / 4608 (ESR-1387)"),
                F("unit_weight", "Unit weight, to add self-weight", unit="pcf", required=False, help="blank = self-weight not added")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="lb"), F("label", "Note", "text", required=False)]),
                T("lateral", "Lateral load on the narrow face (bending about the strong axis)",
                  [CASE, F("kind", "Type", "select", options=["uniform", "point"]), F("mag", "Load", unit="plf or lb"),
                   F("x", "At (point load)", unit="ft", required=False), F("label", "Note", "text", required=False)],
                  help="leave empty for a column with no lateral load")]),
    "shear_wall": dict(
        title="Wood Shear Wall", code="SDPWS-2021", mark="SW",
        fields=[F("panel", "Sheathing and nails", "select", options=list(shearwall.PANELS), help="SDPWS Table 4.3A; blocked, one side"),
                F("spacing", "Edge nail spacing", "select", options=["6", "4", "3", "2"], unit="in"),
                F("panel_type", "Panel", "select", options=["OSB", "plywood"], help="for the shear stiffness Ga"),
                F("sides", "Panels on", "select", options=["one side", "both sides (same panels and nailing)", "both sides (different panels or nailing)"]),
                F("panel2", "Other side: sheathing and nails", "select", options=list(shearwall.PANELS), required=False, help="different panels or nailing on the two sides; SDPWS 4.3.5.4.2"),
                F("spacing2", "Other side: edge nail spacing", "select", options=["6", "4", "3", "2"], unit="in", required=False),
                F("panel_type2", "Other side: panel", "select", options=["OSB", "plywood"], required=False),
                F("blocking", "Panel edges", "select", options=["blocked", "unblocked"], help="unblocked: edge nails at 6 in., wall to 16 ft, h/b to 2"),
                F("stud_spacing", "Unblocked: stud spacing", "select", options=["12", "16", "20", "24"], unit="in", required=False),
                F("field_nails", "Unblocked: nail spacing at intermediate framing", "select", options=["6", "12"], unit="in", required=False),
                F("G", "Framing specific gravity, G", help="0.50 for Douglas Fir-Larch; NDS Table 12.3.3A"),
                F("G_source", "Where G comes from", "text", help="species and the table"),
                F("h", "Wall height", unit="ft"),
                F("lengths", "Full-height segment lengths", "text", "ft", help="separated by commas, for example 8, 3, 6"),
                F("load", "Load", "select", options=["wind", "seismic"]),
                F("V", "Design shear on the wall line", unit="lb", help="at the project's design method (ASD or LRFD)"),
                F("v_source", "Where the shear comes from", "text"),
                F("holddown", "10d nails: hold-down on the inside face of the end post", "select", options=["yes", "no"], required=False,
                  help="Table 4.3A note 10"),
                F("arm_offset", "Overturning arm: reduce the segment length by", unit="in", required=False,
                  help="distance from the segment ends to the hold-down and to the centre of bearing, added together; blank = 0"),
                F("dead", "Uplift: dead load on the wall", unit="plf", required=False, help="blank = dead load not counted against uplift"),
                F("dead_factor", "Uplift: dead load factor", required=False, help="0.6 for ASD (0.6D + 0.6W); 0.9 for LRFD"),
                F("dead_source", "Uplift: source of the dead load and factor", "text", required=False),
                F("chord_A", "Deflection: end post area", unit="in2", required=False),
                F("chord_E", "Deflection: end post E", unit="psi", required=False),
                F("slip", "Deflection: anchorage slip at the design load", unit="in", required=False)],
        tables=[]),
    "perforated_wall": dict(
        title="Perforated Wood Shear Wall", code="SDPWS-2021", mark="PSW",
        fields=[F("panel", "Sheathing and nails", "select", options=list(shearwall.PANELS), help="SDPWS Table 4.3A; blocked"),
                F("spacing", "Edge nail spacing", "select", options=["6", "4", "3", "2"], unit="in"),
                F("panel_type", "Panel", "select", options=["OSB", "plywood"], help="for the shear stiffness Ga"),
                F("sides", "Panels on", "select", options=["one side", "both sides (same panels and nailing)"]),
                F("G", "Framing specific gravity, G", help="0.50 for Douglas Fir-Larch; NDS Table 12.3.3A"),
                F("G_source", "Where G comes from", "text", help="species and the table"),
                F("h", "Wall height", unit="ft", help="20 ft maximum"),
                F("length", "Wall length, hold-down to hold-down", unit="ft"),
                F("load", "Load", "select", options=["wind", "seismic"]),
                F("V", "Design shear on the wall", unit="lb", help="at the project's design method (ASD or LRFD)"),
                F("v_source", "Where the shear comes from", "text"),
                F("holddown", "10d nails: hold-down on the inside face of the end post", "select", options=["yes", "no"], required=False,
                  help="Table 4.3A note 10"),
                F("chord_A", "Deflection: end post area", unit="in2", required=False),
                F("chord_E", "Deflection: end post E", unit="psi", required=False),
                F("slip", "Deflection: anchorage slip at the design load", unit="in", required=False)],
        tables=[T("openings", "Openings", [F("x", "From the left end", unit="ft"), F("w", "Width", unit="ft"),
                                           F("h", "Clear height", unit="ft"), F("sill", "Sill height (0 for a door)", unit="ft", required=False)],
                  help="a full-height segment is needed at each end of the wall")]),
    "snow": dict(
        title="Roof Snow Load", code="ASCE/SEI 7-22", mark="SN",
        fields=[F("pg", "Ground snow load, pg", unit="psf", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("pg_source", "Where pg comes from", "text", help="for example: ASCE 7 Hazard Tool, the address, the date looked up"),
                F("risk", "Risk Category", "select", options=["I", "II", "III", "IV"]),
                F("roughness", "Surface roughness", "select", options=list(snow.CE), help="ASCE 7-22 Sect. 26.7; Table 7.3-1"),
                F("exposure", "Exposure of the roof", "select", options=list(snow.EXPOSURES), help="Table 7.3-1"),
                F("thermal", "Thermal condition", "select", options=list(snow.THERMAL), help="Tables 7.3-2 and 7.3-3"),
                F("r_roof", "Roof R-value (heated, unventilated roof)", unit="h ft2 F/Btu", required=False),
                F("roof", "Roof", "select", options=["gable or hip", "monoslope"]),
                F("rise", "Roof rise in 12", help="for example 6 for a 6 on 12 roof"),
                F("slippery", "Unobstructed slippery surface", "select", options=["yes", "no"],
                  help="metal, slate, glass or smooth membrane, with nothing to hold the snow and room below the eaves"),
                F("W", "Eave to ridge distance, W (horizontal)", unit="ft", help="for a monoslope roof, eave to upper edge"),
                F("simple", "Gable: simply supported rafters, ridge to eave", "select", options=["yes", "no"], required=False,
                  help="Sect. 7.6.1; matters for the unbalanced load"),
                F("W2", "Winter wind parameter, W2 (gable)", required=False, help="from the ASCE 7 Hazard Tool; Fig. 7.6-1"),
                F("W2_source", "Where W2 comes from (gable)", "text", required=False)],
        tables=[]),
    "wind_enclosure": dict(
        title="Wind Enclosure Classification", code="ASCE/SEI 7-22", mark="WE",
        fields=[F("roof_gross", "Roof gross area", unit="ft2"), F("roof_open", "Roof openings", unit="ft2", required=False),
                F("openings_basis", "What is counted as an opening", "text", help="for example: overhead doors taken as open; windows rated for the design pressure taken as closed")],
        tables=[T("walls", "Walls", [F("name", "Wall", "text"), F("gross", "Gross area", unit="ft2"), F("open", "Openings", unit="ft2")])]),
    "wind_kzt": dict(
        title="Wind Topographic Factor (Kzt)", code="ASCE/SEI 7-22", mark="WT",
        fields=[F("shape", "Topographic feature", "select", options=["2D ridge", "2D escarpment", "3D axisymmetrical hill"], help="ASCE 7-22 Figure 26.8-1"),
                F("exposure", "Exposure category upwind of the feature", "select", options=["B", "C", "D"]),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("H", "Height of the feature above the upwind terrain, H", unit="ft"),
                F("Lh", "Distance upwind of the crest to half the height, Lh", unit="ft"),
                F("geometry_source", "Where H and Lh come from", "text", help="for example: USGS topographic map, section through the site"),
                F("x", "Distance from the crest to the site, x", unit="ft", help="0 at the crest"),
                F("side", "Site is", "select", options=["downwind of the crest", "upwind of the crest"]),
                F("located", "Site is in the upper half of the hill or ridge, or near the crest of the escarpment", "select", options=["yes", "no"], help="Sect. 26.8.1, condition 1"),
                F("heights", "Heights above ground for Kzt", "text", "ft", help="separated by commas, for example 0, 15, 30; Kzt is largest at the ground")],
        tables=[]),
    "wind_free_roof": dict(
        title="Wind Pressures, Open Building (free roof)", code="ASCE/SEI 7-22", mark="WO",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("h", "Mean roof height, h", unit="ft"),
                F("roof", "Roof", "select", options=["monoslope", "pitched (gable)", "troughed", "hip"]),
                F("theta_hip", "Hip roof: angle of the hip ends", unit="deg", required=False),
                F("theta", "Roof angle", unit="deg", help="0 to 45 degrees"),
                F("L", "Roof dimension L", unit="ft", help="horizontal: in the direction of the slope for a monoslope roof, edge to edge for a pitched or troughed roof, the shorter plan dimension for a hip roof"),
                F("width", "Roof dimension perpendicular to L", unit="ft", required=False, help="gives the total horizontal and vertical force on the roof and the minimum of Sect. 27.1.5; needed for a hip roof (the longer plan dimension)"),
                F("flow", "Wind flow under the roof", "select", options=["clear", "obstructed"], help="obstructed: more than 50 percent blockage below the roof (Figure 27.3-4 note 2)"),
                F("flow_basis", "Basis of clear or obstructed flow", "text", help="for example: open below, picnic tables only"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text", help="for example: no hill, ridge or escarpment, Sect. 26.8.1"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "wind_pressure": dict(
        title="Wind Velocity Pressure", code="ASCE/SEI 7-22", mark="WV",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text", help="for example: open terrain with scattered obstructions, Sect. 26.7.3"),
                F("h", "Mean roof height, h", unit="ft"),
                F("heights", "Other heights for qz", "text", "ft", required=False, help="separated by commas, for example 15, 20, 25"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text", help="for example: no hill, ridge or escarpment, Sect. 26.8.1"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "wind_mwfrs": dict(
        title="Wind Pressures, Main System (gable, hip, monoslope or flat roof)", code="ASCE/SEI 7-22", mark="WM",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("enclosure", "Enclosure classification", "select", options=["enclosed", "partially enclosed", "partially open"], help="ASCE 7-22 Sect. 26.12"),
                F("enclosure_basis", "Basis of the enclosure classification", "text"),
                F("across", "Plan dimension across the ridge", unit="ft", help="flat roof: one plan dimension"),
                F("along", "Plan dimension along the ridge", unit="ft", help="flat roof: the other plan dimension"),
                F("roof", "Roof", "select", options=["gable or flat", "hip", "monoslope"], required=False),
                F("theta_hip", "Hip roof: hip end roof angle", unit="degrees", required=False),
                F("eave", "Eave height (monoslope: the low eave)", unit="ft"),
                F("h", "Mean roof height, h", unit="ft", help="the eave height where the roof angle is 10 degrees or less"),
                F("theta", "Roof angle", unit="degrees", help="0 for a flat roof"),
                F("parapet", "Parapet height above the wall top", unit="ft", required=False, help="blank = no parapets"),
                F("overhang", "Roof overhang, horizontal projection", unit="ft", required=False, help="blank = no overhang"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "wind_cc_walls": dict(
        title="Wind Pressures, Wall Components and Cladding (h 60 ft or less)", code="ASCE/SEI 7-22", mark="WC",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("enclosure", "Enclosure classification", "select", options=["enclosed", "partially enclosed", "partially open"], help="ASCE 7-22 Sect. 26.12"),
                F("enclosure_basis", "Basis of the enclosure classification", "text"),
                F("h", "Mean roof height, h", unit="ft", help="the eave height where the roof angle is 10 degrees or less"),
                F("least", "Least horizontal dimension of the building", unit="ft"),
                F("theta", "Roof angle", unit="degrees", help="0 for a flat roof"),
                F("areas", "Effective wind areas", "text", "ft2", help="separated by commas, for example 10, 20, 50, 100, 200, 500"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "wind_cc_roof": dict(
        title="Wind Pressures, Roof Components and Cladding (flat, gable, hip or monoslope roof)", code="ASCE/SEI 7-22", mark="WR",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("enclosure", "Enclosure classification", "select", options=["enclosed", "partially enclosed", "partially open"], help="ASCE 7-22 Sect. 26.12"),
                F("enclosure_basis", "Basis of the enclosure classification", "text"),
                F("h", "Mean roof height, h", unit="ft", help="the eave height where the roof angle is 10 degrees or less; 60 ft or less"),
                F("roof", "Roof", "select", options=["gable or flat", "hip", "monoslope"], required=False),
                F("theta", "Roof angle", unit="degrees", help="0 for a flat roof; gable roofs up to 45 degrees, monoslope roofs up to 30"),
                F("least", "Least horizontal dimension of the building", unit="ft", required=False, help="needed for a gable roof over 7 degrees or a monoslope roof over 3"),
                F("overhang", "Roof overhangs", "select", options=["no", "yes"], required=False),
                F("parapet", "Parapet 3 ft or higher around the whole roof", "select", options=["no", "yes"], required=False, help="roofs at 7 degrees or less"),
                F("areas", "Effective wind areas", "text", "ft2", help="separated by commas, for example 10, 20, 50, 100, 200, 500, 1000"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "wind_cc_parapet": dict(
        title="Wind Pressures, Parapets (flat or up to 7 degrees)", code="ASCE/SEI 7-22", mark="WP",
        fields=[F("V", "Basic wind speed, V", unit="mi/h", help="for the project's Risk Category, from the ASCE 7 Hazard Tool or the jurisdiction"),
                F("V_source", "Where V comes from", "text"),
                F("exposure", "Exposure category", "select", options=["B", "C", "D"], help="ASCE 7-22 Sect. 26.7"),
                F("exposure_basis", "Basis of the exposure category", "text"),
                F("hp", "Height of the top of the parapet above ground", unit="ft"),
                F("h", "Eave (roof) height, h", unit="ft", help="60 ft or less"),
                F("least", "Least horizontal dimension of the building", unit="ft"),
                F("theta", "Roof angle", unit="degrees", help="0 for a flat roof; 7 degrees or less"),
                F("areas", "Effective wind areas", "text", "ft2", help="separated by commas, for example 10, 20, 50, 100, 200, 500"),
                F("Kzt", "Topographic factor, Kzt", help="1.0 where Sect. 26.8.1 does not apply"),
                F("Kzt_source", "Where Kzt comes from", "text"),
                F("elevation", "Ground elevation above sea level", unit="ft", required=False, help="blank = Ke taken as 1.0"),
                F("elevation_source", "Where the elevation comes from", "text", required=False)],
        tables=[]),
    "seismic_elf": dict(
        title="Seismic Base Shear and Story Forces", code="ASCE/SEI 7-22", mark="EQ",
        fields=[F("SDS", "SDS", unit="g", help="from the ASCE 7 Hazard Tool for the site, Risk Category and Site Class"),
                F("SD1", "SD1", unit="g"), F("S1", "S1", unit="g"), F("TL", "Long-period transition period, TL", unit="s"),
                F("ground_source", "Where these values come from", "text", help="for example: ASCE 7 Hazard Tool, Site Class D, Risk Category II, with the date"),
                F("risk", "Risk Category", "select", options=["I", "II", "III", "IV"], help="ASCE 7-22 Table 1.5-1"),
                F("system", "Seismic force-resisting system", "select", required=False, options=['Bearing wall: light-frame (wood) walls sheathed with wood structural panels', 'Bearing wall: light-frame walls with shear panels of all other materials', 'Bearing wall: special reinforced masonry shear walls', 'Bearing wall: intermediate reinforced masonry shear walls', 'Bearing wall: ordinary reinforced masonry shear walls', 'Building frame: light-frame (wood) walls sheathed with wood structural panels', 'Building frame: steel special concentrically braced frames', 'Building frame: steel ordinary concentrically braced frames', 'Building frame: special reinforced masonry shear walls', 'Moment frame: steel special moment frames', 'Moment frame: steel intermediate moment frames', 'Moment frame: steel ordinary moment frames', 'Cantilevered column: steel ordinary cantilever column systems', 'Cantilevered column: timber frames', 'Steel systems not specifically detailed for seismic resistance', 'other (type R and Cd)'],
                  help="ASCE 7-22 Table 12.2-1: fills R and Cd and checks the height limit; blank or other = type R below"),
                F("R", "Other system: R", required=False, help="ASCE 7-22 Table 12.2-1"),
                F("R_source", "Other system: the system and its line in Table 12.2-1", "text", required=False),
                F("Ie", "Importance factor, Ie", help="ASCE 7-22 Table 1.5-2"),
                F("Ie_source", "Where Ie comes from", "text", help="for example: Risk Category II, Table 1.5-2"),
                F("structure", "Structure type for the period", "select", options=["all other structural systems", "steel moment-resisting frame",
                  "concrete moment-resisting frame", "steel eccentrically braced frame", "steel buckling-restrained braced frame"], help="Table 12.8-2"),
                F("hn", "Structural height, hn", unit="ft", help="base to the highest level (to the average roof height of a sloped roof)"),
                F("T", "Period from analysis", unit="s", required=False, help="blank = the approximate period Ta"),
                F("T_source", "Where that period comes from", "text", required=False),
                F("Cd", "Drift: deflection amplification factor, Cd", required=False, help="ASCE 7-22 Table 12.2-1; fill the drift boxes and the displacement column to check story drift"),
                F("Cd_source", "Drift: where Cd comes from", "text", required=False),
                F("drift_type", "Drift: structure type for the limit", "select", required=False, options=["four stories or less, finishes designed for the drift",
                  "all other structures", "masonry cantilever shear walls", "other masonry shear walls"], help="Table 12.12-1"),
                F("de_source", "Drift: where the elastic displacements come from", "text", required=False, help="for example: shear wall sheets SW1 to SW4, or the frame analysis"),
                F("rho", "Wall lines: redundancy factor", "select", options=["1.0", "1.3"], required=False, help="ASCE 7-22 Sect. 12.3.4; needed when wall lines are listed"),
                F("rho_source", "Wall lines: basis of the redundancy factor", "text", required=False)],
        tables=[T("levels", "Levels", [F("name", "Level", "text"), F("w", "Effective seismic weight", unit="kips"),
                                       F("h", "Height above the base", unit="ft"),
                                       F("wp", "Diaphragm weight, wpx", unit="kips", required=False, help="blank = the level weight"),
                                       F("de", "Elastic displacement", unit="in", required=False, help="under the design seismic forces; for the drift check")]),
                T("lines", "Wall or frame lines", [F("name", "Line", "text"), F("level", "Story below level", "text", help="a level name from the Levels table"),
                                                  F("share", "Share of the story shear", unit="%")],
                  help="Optional. Each line's share of the story shear, for the shear wall or frame sheets.")]),
    "live_load": dict(
        title="Live Load Reduction", code="ASCE/SEI 7-22", mark="LL",
        fields=[],
        tables=[T("floors", "Floor members", [F("name", "Member", "text"),
                    F("element", "Element", "select", options=["interior column", "exterior column without cantilever slabs", "edge column with cantilever slabs",
                      "corner column with cantilever slabs", "edge beam without cantilever slabs", "interior beam", "all other members"]),
                    F("Lo", "Unreduced live load, Lo", unit="psf"), F("source", "Source of Lo", "text"), F("AT", "Tributary area", unit="ft2"),
                    F("floors", "Floors supported"),
                    F("occupancy", "Occupancy", "select", options=["ordinary", "passenger vehicle garage", "assembly area"], required=False)],
                  help="ASCE 7-22 Sect. 4.7, Table 4.7-1. Occupancy blank = ordinary."),
                T("roofs", "Roof members (ordinary roofs)", [F("name", "Member", "text"), F("Lo", "Unreduced roof live load, Lo", unit="psf"),
                    F("source", "Source of Lo", "text"), F("AT", "Tributary area", unit="ft2"), F("F", "Roof rise", unit="in/ft")],
                  help="ASCE 7-22 Sect. 4.8.2.")]),
    "collector": dict(
        title="Collector Force (drag strut)", code="ASCE/SEI 7-22", mark="CL",
        fields=[F("line_name", "Line", "text", required=False, help="for example: grid A, roof"),
                F("W", "Length of the line", unit="ft", help="the diaphragm dimension along this line of resistance"),
                F("R", "Force the diaphragm delivers to the line", unit="lb", help="the reaction at this line from the diaphragm sheet"),
                F("level", "Load and load level", "text", help="for example: seismic, strength level"),
                F("R_source", "Where that force comes from", "text", help="for example: diaphragm sheet DI1")],
        tables=[T("walls", "Walls on the line", [F("start", "Starts at", unit="ft"), F("length", "Length", unit="ft")],
                  help="Each wall length on the line, measured from one end of the line. The walls take the force in proportion to their lengths.")]),
    "diaphragm": dict(
        title="Wood Diaphragm", code="SDPWS-2021", mark="DI",
        fields=[F("panel", "Sheathing and nails", "select", options=["Structural I, 5/16 in, 6d common", "Structural I, 3/8 in, 8d common", "Structural I, 15/32 in, 10d common",
                  "Sheathing and Single-Floor, 5/16 in, 6d common", "Sheathing and Single-Floor, 3/8 in, 6d common", "Sheathing and Single-Floor, 3/8 in, 8d common",
                  "Sheathing and Single-Floor, 7/16 in, 8d common", "Sheathing and Single-Floor, 15/32 in, 8d common",
                  "Sheathing and Single-Floor, 15/32 in, 10d common", "Sheathing and Single-Floor, 19/32 in, 10d common"],
                  help="SDPWS Tables 4.2A (blocked) and 4.2C (unblocked)"),
                F("edges", "Panel edges", "select", options=["unblocked", "blocked"]),
                F("spacing", "Blocked: nail spacing at the boundaries", "select", options=["6", "4", "2-1/2", "2"], unit="in", required=False,
                  help="Table 4.2A; other panel edges at 6, 6, 4 and 3 in."),
                F("face", "Nominal width of the nailed face", "select", options=["2", "3"], unit="in", help="framing at adjoining panel edges and boundaries"),
                F("case", "Unblocked: panel layout", "select", options=["Case 1", "Cases 2 to 6"], required=False,
                  help="SDPWS Table 4.2C figure; Case 1: continuous panel joints perpendicular to the framing, load perpendicular to them"),
                F("panel_type", "Panel", "select", options=["OSB", "plywood"], help="for the shear stiffness Ga"),
                F("G", "Framing specific gravity, G", help="0.50 for Douglas Fir-Larch; NDS Table 12.3.3A"),
                F("G_source", "Where G comes from", "text"),
                F("L", "Span between the lines of resistance, L", unit="ft"),
                F("W", "Diaphragm width parallel to the load, W", unit="ft"),
                F("load", "Load", "select", options=["wind", "seismic"]),
                F("w", "Uniform load on the diaphragm", unit="plf", help="at the project's design method (ASD or LRFD)"),
                F("w_source", "Where the load comes from", "text"),
                F("trib_low", "Wind fill: tributary wall from height", unit="ft", required=False, help="above ground; used only by Take the wind load from"),
                F("trib_high", "Wind fill: tributary wall to height", unit="ft", required=False, help="the eave height for a roof diaphragm (the fill then runs to the top of the walls for each wind direction)"),
                F("chord_A", "Deflection: chord area", unit="in2", required=False),
                F("chord_E", "Deflection: chord E", unit="psi", required=False),
                F("defl_limit", "Deflection: limit", unit="in", required=False),
                F("defl_limit_source", "Deflection: where the limit comes from", "text", required=False)],
        tables=[T("splices", "Chord splices (for deflection)", [F("x", "Distance to the nearest support", unit="ft"), F("slip", "Slip at the design load", unit="in")],
                  help="Optional.")]),
    "nailed_connection": dict(
        title="Nailed Connection (lateral)", code="NDS 2018", mark="NC",
        fields=[F("nail", "Nail", "select", options=["6d common", "7d common", "8d common", "10d common", "12d common", "16d common", "20d common", "30d common",
                  "40d common", "50d common", "60d common", "6d box", "7d box", "8d box", "10d box", "12d box", "16d box", "20d box", "30d box", "40d box",
                  "6d sinker", "7d sinker", "8d sinker", "10d sinker", "12d sinker", "16d sinker", "20d sinker", "30d sinker", "40d sinker", "60d sinker",
                  "other (type the size)"], help="NDS Appendix Table L4"),
                F("nail_name", "Other nail: description", "text", required=False),
                F("D", "Other nail: diameter", unit="in", required=False),
                F("length", "Other nail: length", unit="in", required=False),
                F("n", "Number of nails"),
                F("side_t", "Side member thickness", unit="in", help="the piece the nail head is in"),
                F("G_side", "Side member specific gravity, G", help="NDS Table 12.3.3A"), F("G_side_source", "Where that G comes from", "text"),
                F("main_t", "Main member thickness", unit="in", help="the piece the nail point is in"),
                F("G_main", "Main member specific gravity, G"), F("G_main_source", "Where that G comes from", "text"),
                F("service", "Moisture", "select", options=["dry", "wet in service", "wet at fabrication, dry in service"], help="NDS Table 11.3.3"),
                F("end_grain", "Nails in the end grain of the main member", "select", options=["no", "yes"], required=False),
                F("diaphragm", "Diaphragm construction", "select", options=["no", "yes"], required=False, help="NDS 12.5.3"),
                F("toe_nail", "Toe-nailed", "select", options=["no", "yes"], required=False, help="driven at 30 degrees through the end of the side member; NDS 12.1.6.3")],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Lateral force on the group of nails, by load case; the project's ASD combinations are applied.")]),
    "nail_withdrawal": dict(
        title="Nails in Withdrawal", code="NDS 2018", mark="NW",
        fields=[F("nail", "Nail", "select", options=["6d common", "7d common", "8d common", "10d common", "12d common", "16d common", "20d common", "30d common",
                  "40d common", "50d common", "60d common", "6d box", "7d box", "8d box", "10d box", "12d box", "16d box", "20d box", "30d box", "40d box",
                  "6d sinker", "7d sinker", "8d sinker", "10d sinker", "12d sinker", "16d sinker", "20d sinker", "30d sinker", "40d sinker", "60d sinker",
                  "other (type the size)"], help="NDS Appendix Table L4"),
                F("nail_name", "Other nail: description", "text", required=False),
                F("D", "Other nail: diameter", unit="in", required=False),
                F("length", "Other nail: length", unit="in", required=False),
                F("head", "Other nail: head diameter", unit="in", required=False),
                F("n", "Number of nails"),
                F("side_t", "Side member thickness", unit="in", help="the piece the nail head is in"),
                F("G_side", "Side member specific gravity, G", help="NDS Table 12.3.3A"), F("G_side_source", "Where that G comes from", "text"),
                F("main_t", "Main member thickness", unit="in", help="the piece the nail point is in"),
                F("G_main", "Main member specific gravity, G"), F("G_main_source", "Where that G comes from", "text"),
                F("service", "Moisture", "select", options=["dry", "wet in service", "wet at fabrication, dry in service", "wet at fabrication and in service"], help="NDS Table 11.3.3"),
                F("toe_nail", "Toe-nailed", "select", options=["no", "yes"], required=False, help="driven at 30 degrees through the end of the side member; NDS 12.1.6.3")],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Force pulling the side member off the main member, on the group of nails, by load case; the project's ASD combinations are applied.")]),
    "screw_connection": dict(
        title="Wood Screw Connection (lateral)", code="NDS 2018", mark="WS",
        fields=[F("screw", "Wood screw number", "select", options=["#6", "#7", "#8", "#9", "#10", "#12", "#14"], help="NDS Appendix Table L3"),
                F("length", "Screw length", unit="in"),
                F("n", "Number of screws"),
                F("side_t", "Side member thickness", unit="in", help="the piece the screw head is in"),
                F("G_side", "Side member specific gravity, G", help="NDS Table 12.3.3A"), F("G_side_source", "Where that G comes from", "text"),
                F("main_t", "Main member thickness", unit="in", help="the piece the screw point is in"),
                F("G_main", "Main member specific gravity, G"), F("G_main_source", "Where that G comes from", "text"),
                F("service", "Moisture", "select", options=["dry", "wet in service", "wet at fabrication, dry in service"], help="NDS Table 11.3.3"),
                F("end_grain", "Screws in the end grain of the main member", "select", options=["no", "yes"], required=False)],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Lateral force on the group of screws, by load case; the project's ASD combinations are applied.")]),
    "screw_withdrawal": dict(
        title="Wood Screws in Withdrawal", code="NDS 2018", mark="SW",
        fields=[F("screw", "Wood screw number", "select", options=["#6", "#7", "#8", "#9", "#10", "#12", "#14"], help="NDS Appendix Table L3"),
                F("length", "Screw length", unit="in"),
                F("n", "Number of screws"),
                F("side_kind", "Side member material", "select", options=["wood", "steel"], required=False, help="blank = wood; steel: no head pull-through check"),
                F("side_t", "Side member thickness", unit="in", help="the piece the screw head is in"),
                F("G_side", "Side member specific gravity, G", required=False, help="wood side member; NDS Tables 12.3.3A, 12.3.3B"),
                F("G_side_source", "Where that G comes from", "text", required=False),
                F("main_t", "Main member thickness", unit="in", help="the piece the threads are in, measured along the screw"),
                F("G_main", "Main member specific gravity, G"), F("G_main_source", "Where that G comes from", "text"),
                F("service", "Moisture in service", "select", options=["dry", "wet in service"], help="NDS Table 11.3.3"),
                F("steel", "Allowable tension of one screw", unit="lb", required=False, help="the steel at the root diameter; NDS 12.2.2.5"),
                F("steel_source", "Where that allowable tension comes from", "text", required=False)],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Force pulling the side member off the main member, on the group of screws, by load case; the project's ASD combinations are applied.")]),
    "bolted_connection": dict(
        title="Bolted Connection", code="NDS 2018", mark="BC",
        fields=[F("D", "Bolt diameter", "select", options=["1/2", "5/8", "3/4", "7/8", "1"], unit="in"),
                F("shear", "Shear", "select", options=["single", "double"], help="double: a main member between two side members"),
                F("rows", "Rows of bolts"), F("n_row", "Bolts in a row"),
                F("spacing", "Spacing in a row", unit="in", required=False, help="along the grain; 4 D for the full value"),
                F("row_spacing", "Spacing between rows", unit="in", required=False),
                F("end", "End distance", unit="in", required=False, help="bolt to the end of the member loaded parallel to grain; not used with a steel plate on a main member loaded perpendicular"),
                F("edge", "Edge distance", unit="in", required=False, help="outer row to the edge of the member loaded parallel to grain"),
                F("grain", "Load direction to the grain", "select", required=False, options=["parallel in every member", "perpendicular in the side member(s)", "perpendicular in the main member"],
                  help="blank = parallel in every member"),
                F("p_loaded", "Perpendicular member: loaded edge distance", unit="in", required=False, help="bolt to the edge the load pushes toward; 4 D minimum"),
                F("p_unloaded", "Perpendicular member: unloaded edge distance", unit="in", required=False),
                F("p_end", "Perpendicular member: end distance", unit="in", required=False, help="bolts to the end of that member, along its grain"),
                F("p_Fv", "Perpendicular member: Fv", unit="psi", required=False, help="with every adjustment factor except CD; fill to check shear at the connection (NDS 3.4.3.3)"),
                F("p_Fv_source", "Perpendicular member: where Fv comes from", "text", required=False),
                F("sense", "Load in the member loaded parallel to grain", "select", options=["tension", "compression"], required=False, help="tension: the bolts bear toward the member end"),
                F("wood_type", "Wood", "select", options=["softwood", "hardwood"], required=False),
                F("side_steel", "Side member material", "select", required=False, options=["wood", "ASTM A36 steel plate", "ASTM A653 Grade 33 steel sheet"], help="blank = wood"),
                F("side_t", "Side member thickness", unit="in"), F("side_w", "Side member width", unit="in"),
                F("G_side", "Side member specific gravity, G", required=False, help="wood side members"), F("E_side", "Side member E", unit="psi", required=False, help="wood side members"),
                F("side_source", "Where the side member values come from", "text", required=False, help="wood side members"),
                F("main_t", "Main member thickness", unit="in"), F("main_w", "Main member width", unit="in"),
                F("G_main", "Main member specific gravity, G"), F("E_main", "Main member E", unit="psi"), F("main_source", "Where the main member values come from", "text"),
                F("service", "Moisture", "select", options=["dry", "wet in service", "wet at fabrication, dry in service"], help="NDS Table 11.3.3"),
                F("Ft_main", "Tear-out: main member Ft", unit="psi", required=False, help="with every adjustment factor except CD; fill these six to check net section and tear-out (tension)"),
                F("Fv_main", "Tear-out: main member Fv", unit="psi", required=False),
                F("Ft_side", "Tear-out: side member Ft", unit="psi", required=False), F("Fv_side", "Tear-out: side member Fv", unit="psi", required=False),
                F("local_source", "Tear-out: where Ft and Fv come from", "text", required=False),
                F("hole", "Tear-out: bolt hole diameter", unit="in", required=False, help="blank = bolt diameter + 1/16 in.")],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Force along the members, by load case; the project's ASD combinations are applied.")]),
    "lag_connection": dict(
        title="Lag Screw Connection (lateral)", code="NDS 2018", mark="LC",
        fields=[F("D", "Lag screw diameter", "select", options=["1/4", "5/16", "3/8", "7/16", "1/2", "5/8", "3/4", "7/8", "1"], unit="in"),
                F("L", "Lag screw length", "select", options=["1", "1-1/2", "2", "2-1/2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], unit="in", help="NDS Appendix Table L2"),
                F("washer", "Washer thickness under the head", unit="in", required=False, help="blank = none deducted from the penetration"),
                F("alpha", "Angle of the load to the wood surface", unit="deg", required=False, help="blank or 0 = lateral load only; over 0: combined lateral and withdrawal, NDS 12.4.1"),
                F("rows", "Rows of lag screws"), F("n_row", "Lag screws in a row"),
                F("spacing", "Spacing in a row", unit="in", required=False, help="along the grain; 4 D for the full value"),
                F("row_spacing", "Spacing between rows", unit="in", required=False),
                F("end", "End distance", unit="in", required=False, help="lag screw to the end of the member loaded parallel to grain; not used with a steel plate on a main member loaded perpendicular"),
                F("edge", "Edge distance", unit="in", required=False, help="outer row to the edge of the member loaded parallel to grain"),
                F("grain", "Load direction to the grain", "select", required=False, options=["parallel in every member", "perpendicular in the side member(s)", "perpendicular in the main member"],
                  help="blank = parallel in every member"),
                F("p_loaded", "Perpendicular member: loaded edge distance", unit="in", required=False, help="lag screw to the edge the load pushes toward; 4 D minimum"),
                F("p_unloaded", "Perpendicular member: unloaded edge distance", unit="in", required=False),
                F("p_end", "Perpendicular member: end distance", unit="in", required=False, help="lag screws to the end of that member, along its grain"),
                F("p_Fv", "Perpendicular member: Fv", unit="psi", required=False, help="with every adjustment factor except CD; fill to check shear at the connection (NDS 3.4.3.3)"),
                F("p_Fv_source", "Perpendicular member: where Fv comes from", "text", required=False),
                F("sense", "Load in the member loaded parallel to grain", "select", options=["tension", "compression"], required=False, help="tension: the lag screws bear toward the member end"),
                F("wood_type", "Wood", "select", options=["softwood", "hardwood"], required=False),
                F("side_steel", "Side member material", "select", required=False, options=["wood", "ASTM A36 steel plate", "ASTM A653 Grade 33 steel sheet"], help="blank = wood"),
                F("side_t", "Side member thickness", unit="in"), F("side_w", "Side member width", unit="in"),
                F("G_side", "Side member specific gravity, G", required=False, help="wood side members"), F("E_side", "Side member E", unit="psi", required=False, help="wood side members"),
                F("side_source", "Where the side member values come from", "text", required=False, help="wood side members"),
                F("main_t", "Main member thickness", unit="in"), F("main_w", "Main member width", unit="in"),
                F("G_main", "Main member specific gravity, G"), F("E_main", "Main member E", unit="psi"), F("main_source", "Where the main member values come from", "text"),
                F("service", "Moisture", "select", options=["dry", "wet in service", "wet at fabrication, dry in service"], help="NDS Table 11.3.3")],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Force along the members, by load case; the project's ASD combinations are applied.")]),
    "lag_withdrawal": dict(
        title="Lag Screws in Withdrawal", code="NDS 2018", mark="LW",
        fields=[F("D", "Lag screw diameter", "select", options=["1/4", "5/16", "3/8", "7/16", "1/2", "5/8", "3/4", "7/8", "1"], unit="in"),
                F("L", "Lag screw length", "select", options=["1", "1-1/2", "2", "2-1/2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], unit="in", help="NDS Appendix Table L2"),
                F("washer", "Washer thickness under the head", unit="in", required=False, help="blank = none"),
                F("n", "Number of lag screws"),
                F("side_t", "Side member thickness", unit="in", help="the part the screw passes through, wood or steel"),
                F("side_kind", "Side member material", "select", options=["wood", "steel"], required=False, help="for the sketch only"),
                F("main_t", "Main member thickness", unit="in", help="the piece the threads are in, measured along the screw"),
                F("G_main", "Main member specific gravity, G", help="NDS Table 12.3.3A"), F("G_main_source", "Where that G comes from", "text"),
                F("service", "Moisture in service", "select", options=["dry", "wet in service"], help="NDS Table 11.3.3"),
                F("end_grain", "Screws in the end grain of the main member", "select", options=["no", "yes"], required=False),
                F("edge", "Edge distance", unit="in", required=False, help="1.5 D minimum; NDS Table 12.5.1E"),
                F("end", "End distance", unit="in", required=False, help="4 D minimum"),
                F("spacing", "Spacing", unit="in", required=False, help="4 D minimum"),
                F("steel", "Allowable tension of one screw", unit="lb", required=False, help="the steel at the root diameter; NDS 12.2.1.4"),
                F("steel_source", "Where that allowable tension comes from", "text", required=False),
                F("washer_od", "Washer bearing: washer outside diameter", unit="in", required=False, help="round washer on a wood side member; fill these to check bearing under the washer"),
                F("washer_hole", "Washer bearing: hole in the side member", unit="in", required=False, help="blank = screw diameter + 1/16 in."),
                F("Fc_perp", "Washer bearing: side member Fc_perp", unit="psi", required=False, help="with the wet service and other factors that apply"),
                F("Fc_perp_source", "Washer bearing: where Fc_perp comes from", "text", required=False),
                F("washer_away", "Washer bearing: 3 in. or more from the member end", "select", options=["no", "yes"], required=False, help="yes: the bearing area factor Cb is taken; NDS 3.10.4")],
        tables=[T("loads", "Load on the connection", [CASE, F("P", "Force", unit="lb"), F("label", "Note", "text", required=False)],
                  help="Force pulling the lag screws out, on the group, by load case; the project's ASD combinations are applied.")]),
    "guard": dict(
        title="Guard (HSS or pipe)", code="ASCE/SEI 7-22, AISC 360-22", mark="GD",
        fields=[F("rail", "Top rail", "hss_shape", help="HSS or pipe by its Manual label, for example HSS1.900x0.145, HSS2x2x1/8 or Pipe 1-1/2 STD"),
                F("rail_Fy", "Top rail yield stress, Fy", unit="ksi"), F("rail_Fy_source", "Where that Fy comes from", "text", help="for example: ASTM A500 Grade C"),
                F("post", "Post", "hss_shape", help="HSS or pipe by its Manual label"),
                F("post_Fy", "Post yield stress, Fy", unit="ksi"), F("post_Fy_source", "Where that Fy comes from", "text"),
                F("spacing", "Post spacing", unit="ft"),
                F("height", "Height from the post base to the top rail", unit="ft"),
                F("uniform", "50 lb/ft uniform load", "select", options=["applies", "exception"], help="ASCE 7-22 Sect. 4.5.1.1: not required for one- and two-family dwellings, "
                  "factory, industrial and storage areas not open to the public serving 50 occupants or fewer, and roofs not intended for occupancy"),
                F("uniform_basis", "Exception: which one applies", "text", required=False),
                F("stringer", "Posts on the top flange of a channel: the channel", "text", required=False, help="optional, for example C12x20.7; checks the channel web for the post moment (Design Guide 34)"),
                F("stringer_Fy", "Channel yield stress, Fy", unit="ksi", required=False), F("stringer_Fy_source", "Where that Fy comes from", "text", required=False)],
        tables=[]),
    "rain_load": dict(
        title="Rain Load", code="ASCE/SEI 7-22", mark="RN",
        fields=[F("risk", "Risk category", "select", options=["I", "II", "III", "IV"], help="sets the design storm, ASCE 7-22 Table 8.2-1"),
                F("i", "Rainfall intensity, 15 minute storm", unit="in/hr", help="for the return period of the risk category; ASCE 7 Hazard Tool or NOAA Atlas 14"),
                F("i_source", "Where the intensity comes from", "text"),
                F("A", "Roof area draining to each secondary drain or scupper", unit="ft2"),
                F("ds", "Static head, ds", unit="in", help="depth of water on the undeflected roof up to the inlet of the secondary drain or scupper"),
                F("ds_source", "Where the static head comes from", "text", help="for example: scupper invert 2 in. above the low point"),
                F("head_type", "Hydraulic head", "select", options=["channel scupper", "typed in"], help="typed in: from drain test data or ASCE 7-22 Tables C8.2-1 to C8.2-3"),
                F("scupper_w", "Channel scupper: width", unit="in", required=False),
                F("dh", "Typed in: hydraulic head, dh", unit="in", required=False),
                F("dh_source", "Typed in: where dh comes from", "text", required=False),
                F("pond_type", "Ponding head", "select", options=["from the bay stiffness", "typed in"], help="bay stiffness: AISC Design Guide 40 amplified first-order analysis"),
                F("D", "Bay: dead load", unit="psf", required=False),
                F("D_source", "Bay: where the dead load comes from", "text", required=False),
                F("Lp", "Bay: span of the primary members (girders)", unit="ft", required=False),
                F("Ls", "Bay: span of the secondary members (joists or beams)", unit="ft", required=False),
                F("S", "Bay: spacing of the secondary members", unit="ft", required=False),
                F("primary", "Bay: primary member", "select", required=False, options=["structural steel member", "open web steel joist or joist girder", "effective moment of inertia entered", "other material"]),
                F("Ip", "Bay: primary member moment of inertia", unit="in4", required=False),
                F("Ep", "Bay: primary member E (other material)", unit="psi", required=False),
                F("secondary", "Bay: secondary member", "select", required=False, options=["structural steel member", "open web steel joist or joist girder", "effective moment of inertia entered", "other material"]),
                F("Is", "Bay: secondary member moment of inertia", unit="in4", required=False),
                F("Es", "Bay: secondary member E (other material)", unit="psi", required=False),
                F("dp", "Typed in: ponding head, dp", unit="in", required=False),
                F("dp_source", "Typed in: where dp comes from", "text", required=False),
                F("slope", "Low slope check: roof slope", unit="in/ft", required=False, help="blank = no check; ASCE 7-22 Sect. 8.3, bays without accumulated rain"),
                F("parallel_edge", "Low slope check: bay beside a free-draining edge with secondary members parallel to it", "select", options=["no", "yes"], required=False),
                F("ls_Ls", "Low slope check: span of the secondary members", unit="ft", required=False, help="blank = the bay value above"),
                F("ls_S", "Low slope check: spacing of the secondary members", unit="ft", required=False, help="blank = the bay value above")],
        tables=[]),
    "snow_corner": dict(
        title="Intersecting Snow Drifts (reentrant corner)", code="ASCE/SEI 7-22", mark="SC",
        fields=[F("pg", "Ground snow load, pg", unit="psf"), F("pg_source", "Where pg comes from", "text"),
                F("W2", "Winter wind parameter, W2", help="from the ASCE 7 Hazard Tool; Fig. 7.6-1"), F("W2_source", "Where W2 comes from", "text"),
                F("ps", "Balanced snow load on the lower roof", unit="psf", help="from its Roof Snow Load sheet"),
                F("ps_source", "Where that load comes from", "text", help="for example: sheet SN1"),
                F("a_name", "Wall A: name", "text", help="for example: north wall of the addition"),
                F("a_step", "Wall A: height of the upper roof above the lower roof", unit="ft"),
                F("a_lu_upper", "Wall A: upper roof length, perpendicular to wall A", unit="ft"),
                F("a_lu_lower", "Wall A: lower roof length, perpendicular to wall A", unit="ft"),
                F("b_name", "Wall B: name", "text"),
                F("b_step", "Wall B: height of the upper roof above the lower roof", unit="ft"),
                F("b_lu_upper", "Wall B: upper roof length, perpendicular to wall B", unit="ft"),
                F("b_lu_lower", "Wall B: lower roof length, perpendicular to wall B", unit="ft")],
        tables=[]),
    "snow_drift": dict(
        title="Snow Drift on a Lower Roof", code="ASCE/SEI 7-22", mark="SD",
        fields=[F("pg", "Ground snow load, pg", unit="psf"), F("pg_source", "Where pg comes from", "text"),
                F("W2", "Winter wind parameter, W2", help="from the ASCE 7 Hazard Tool; Fig. 7.6-1"), F("W2_source", "Where W2 comes from", "text"),
                F("ps", "Balanced snow load on the lower roof", unit="psf", help="from its Roof Snow Load sheet"),
                F("ps_source", "Where that load comes from", "text", help="for example: sheet SN1"),
                F("at", "Drift at", "select", options=["a roof step (lower roof beside a higher roof)", "a parapet or roof projection"]),
                F("lu_upper", "Upper roof length, perpendicular to the step", unit="ft", required=False, help="roof step only"),
                F("lu_lower", "Lower roof length, perpendicular to the step (parapet: roof length upwind)", unit="ft"),
                F("step", "Height of the upper roof, or of the parapet, above the roof", unit="ft"),
                F("separation", "Gap between the two structures", unit="ft", required=False, help="blank = one structure; adjacent structures: ASCE 7-22 Sect. 7.7.2"),
                F("slide", "Sliding snow from the upper roof", "select", options=["no", "yes"], help="the upper roof slopes toward the lower roof"),
                F("s_pf", "Sliding: upper roof flat roof snow load, pf", unit="psf", required=False),
                F("s_pf_source", "Sliding: where pf comes from", "text", required=False),
                F("s_W", "Sliding: upper roof eave to ridge, W (horizontal)", unit="ft", required=False),
                F("s_rise", "Sliding: upper roof rise in 12", required=False),
                F("s_slippery", "Sliding: slippery upper roof surface", "select", options=["yes", "no"], required=False)],
        tables=[]),
    "base_plate": dict(
        title="Base Plate", code="AISC 360-22", mark="BP",
        fields=[F("shape", "Column", "shape_col", help="W, M, S or HP shape, HSS or pipe"), F("N", "Plate length (along column depth)", unit="in"),
                F("B", "Plate width", unit="in"), F("t", "Plate thickness", unit="in"), F("Fy", "Plate Fy", unit="ksi"),
                F("fc", "Concrete f'c", unit="psi"),
                F("full", "Plate covers the whole support", "select", options=["yes", "no"]),
                F("sup_N", "Support length (parallel to plate length)", unit="in", required=False),
                F("sup_B", "Support width", unit="in", required=False)],
        tables=[T("loads", "Axial compression", [CASE, F("P", "P", unit="kip"), F("label", "Note", "text", required=False)])]),
    "base_plate_uplift": dict(
        title="Base Plate in Uplift", code="AISC 360-22, AISC Design Guide 1", mark="BPU",
        fields=[F("shape", "Column", "shape", help="W, M, S or HP shape"), F("col_Fy", "Column Fy", unit="ksi"),
                F("N", "Plate length (along the column depth)", unit="in"), F("B", "Plate width", unit="in"), F("t", "Plate thickness", unit="in"), F("Fy", "Plate Fy", unit="ksi"),
                F("rod_d", "Anchor rod diameter", unit="in"), F("rod_Fu", "Anchor rod Fu", unit="ksi"), F("rod_source", "Anchor rod material", "text", help="for example: ASTM F1554 Grade 36"),
                F("gauge", "Rod spacing across the web", unit="in", help="four rods inside the column profile, two each side of the web"),
                F("pitch", "Rod spacing along the web", unit="in"),
                F("weld", "Web fillet weld size, each side", unit="in"), F("FEXX", "Electrode strength", unit="ksi")],
        tables=[T("cases", "Net uplift by load combination", [F("name", "Combination", "text"), F("T", "Net uplift", unit="kip")])]),
    "base_plate_moment": dict(
        title="Base Plate with Moment", code="AISC 360-22, AISC Design Guide 1, ACI 318-19", mark="BPM",
        fields=[F("shape", "Column", "shape_col", help="W, M, S or HP shape, or square or rectangular HSS"), F("N", "Plate length (direction of the moment)", unit="in"),
                F("B", "Plate width", unit="in"), F("t", "Plate thickness", unit="in"), F("Fy", "Plate Fy", unit="ksi"),
                F("fc", "Concrete f'c", unit="psi"),
                F("full", "Plate covers the whole support", "select", options=["yes", "no"]),
                F("sup_N", "Support length (direction of the moment)", unit="in", required=False),
                F("sup_B", "Support width", unit="in", required=False),
                F("rod_d", "Anchor rod diameter", unit="in"),
                F("rod_grade", "Anchor rod grade", "select", options=["F1554 Gr. 36", "F1554 Gr. 55", "F1554 Gr. 105", "other"],
                  required=False, help="strengths from AISC Design Guide 1 Table 2-2; pick other to type them"),
                F("rod_Fu", "Anchor rod Fu (grade: other)", unit="ksi", required=False),
                F("rod_source", "Anchor rod material (grade: other)", "text", required=False,
                  help="where Fu comes from"),
                F("n_rods", "Rods on each side"), F("rod_edge", "Rods from the plate end", unit="in"),
                F("rod_side", "Rods from the plate sides", unit="in"),
                F("n_shear", "Rods counted on for shear", help="0 = the rods do not carry the base shear"),
                F("fw_size", "Column flange fillet weld size", unit="in", required=False, help="optional: checks the weld along the outside of the tension flange for the moment"),
                F("fw_FEXX", "Flange weld electrode strength", unit="ksi", required=False),
                F("loads_from", "Loads come from", "text", required=False, help="printed on the sheet"),
                F("anc_hef", "Anchorage: rod embedment to the head, hef", unit="in", required=False,
                  help="ACI 318-19 Chapter 17; leave blank to leave the anchorage in the concrete unchecked"),
                F("anc_h", "Anchorage: concrete thickness at the rods", unit="in", required=False),
                F("anc_F", "Anchorage: hex head or nut, width across flats", unit="in", required=False,
                  help="leave blank for a heavy hex nut (AISC Design Guide 1 Table 4-2)"),
                F("anc_abrg", "Anchorage: head bearing area, if not a hex", unit="in2", required=False),
                F("anc_tpi", "Anchorage: rod threads per inch", required=False,
                  help="leave blank for coarse thread (AISC Design Guide 1 Table 4-1)"),
                F("anc_fy", "Anchorage: anchor rod Fy (grade: other)", unit="ksi", required=False),
                F("anc_ductile", "Anchorage: rod steel is ductile (grade: other)", "select", options=["yes", "no"], required=False,
                  help="elongation at least 14 percent and reduction in area at least 30 percent"),
                F("anc_cracked", "Anchorage: concrete at the rods at service load", "select", options=["cracked", "uncracked"],
                  required=False),
                F("anc_supp", "Anchorage: supplementary reinforcement at the rods", "select", options=["yes", "no"], required=False,
                  help="ACI 318-19 Table 17.5.3(b)"),
                F("anc_edge", "Anchorage: bars between the rods and the edge", "select",
                  options=["none or smaller than No. 4", "No. 4 or larger", "No. 4 or larger in stirrups at 4 in."],
                  required=False, help="ACI 318-19 Table 17.7.2.5.1"),
                F("anc_grout", "Anchorage: grout pad under the plate", "select", options=["yes", "no"], required=False),
                F("anc_sdc", "Anchorage: Seismic Design Category", "select", options=["A or B", "C to F"], required=False)],
        tables=[T("cases", "Load cases at the base (at the project's design method)",
                  [F("name", "Combination", "text"), F("P", "P", unit="kip"), F("M", "M", unit="kip-ft"), F("V", "V", unit="kip")]),
                T("cases_lrfd", "Factored (LRFD) load cases for the rod anchorage",
                  [F("name", "Combination", "text"), F("P", "Pu", unit="kip"), F("M", "Mu", unit="kip-ft"), F("V", "Vu", unit="kip")],
                  help="needed only when the anchorage is checked and the project's design method is ASD")]),
    "footing_moment": dict(
        title="Footing with Moment", code="ACI 318-19", mark="FM",
        fields=[F("B", "Width, in the direction of the moment", unit="ft"), F("L", "Length", unit="ft"), F("h", "Thickness", unit="in"),
                F("fc", "f'c", unit="psi"), F("fy", "fy", unit="psi"), F("conc_pcf", "Concrete weight", unit="pcf"),
                F("col_x", "Column, in the direction of the moment", unit="in"), F("col_y", "Column, other way", unit="in"),
                F("supported", "Column is", "select", options=["steel", "wood", "concrete"]),
                F("plate_x", "Base plate, x", unit="in", required=False), F("plate_y", "Base plate, y", unit="in", required=False),
                F("bar", "Bar size #"), F("n_x", "Bars in x"), F("n_y", "Bars in y"), F("cover", "Clear cover", unit="in"),
                F("bottom", "Lowest bars run in", "select", options=["x", "y"]),
                F("q_allow", "Allowable soil bearing", unit="psf"), F("soil_source", "Soil bearing source", "text"),
                F("soil_depth", "Soil over footing", unit="ft", required=False), F("soil_pcf", "Soil weight", unit="pcf", required=False),
                F("ot_required", "Required safety factor, overturning", required=False),
                F("slide_mu", "Friction coefficient, footing on soil", required=False),
                F("slide_required", "Required safety factor, sliding", required=False),
                F("limits_source", "Source of those limits", "text", required=False),
                F("loads_from", "Loads come from", "text", required=False, help="printed on the sheet")],
        tables=[T("service", "Service load cases (at the top of the footing)",
                  [F("name", "Combination", "text"), F("P", "P", unit="lb"), F("M", "M", unit="lb-ft"), F("V", "V", unit="lb")]),
                T("strength", "Factored load cases",
                  [F("name", "Combination", "text"), F("P", "Pu", unit="lb"), F("M", "Mu", unit="lb-ft"), F("V", "Vu", unit="lb"),
                   F("wt_factor", "Dead-load factor", help="applied to the footing and soil weight")])]),
}


# ------------------------------------------------------------------ reading what was typed
def parse_expr(text):
    """ "1.2D + 1.6L" -> {"D": 1.2, "L": 1.6}."""
    out = {}
    s = (text or "").replace(" ", "")
    if not s:
        raise ValueError("no load combination typed")
    for sign, coef, case in re.findall(r"([+-]?)(\d*\.?\d*)\*?([A-Za-z][A-Za-z0-9]*)", s):
        f = float(coef) if coef else 1.0
        out[case] = out.get(case, 0.0) + (-f if sign == "-" else f)
    rebuilt = re.sub(r"[+\-*0-9.]", "", s)
    if not out or rebuilt != "".join(re.findall(r"[A-Za-z][A-Za-z0-9]*", s)):
        raise ValueError(f"cannot read the combination '{text}'")
    return out


class Reader:
    """Pulls typed values, collecting every blank or unreadable box."""

    def __init__(self, form, values):
        self.form, self.v, self.miss = form, values or {}, []
        self.labels = {f["key"]: f["label"] for f in form["fields"]}

    def num(self, key, required=True, label=None):
        raw = self.v.get(key)
        label = label or self.labels.get(key, key)
        if raw in (None, ""):
            if required:
                self.miss.append(f"{label} is blank")
            return None
        try:
            return float(str(raw).replace(",", ""))
        except ValueError:
            self.miss.append(f"{label}: '{raw}' is not a number")
            return None

    def text(self, key, required=True):
        raw = (self.v.get(key) or "").strip() if isinstance(self.v.get(key), str) else self.v.get(key)
        if raw in (None, ""):
            if required:
                self.miss.append(f"{self.labels.get(key, key)} is blank")
            return None
        return raw

    def nums(self, key):
        raw = self.text(key)
        if raw is None:
            return None
        try:
            return [float(x) for x in str(raw).replace(";", ",").split(",") if x.strip()]
        except ValueError:
            self.miss.append(f"{self.labels[key]}: '{raw}' is not a list of numbers")
            return None

    def rows(self, key):
        t = next(t for t in self.form["tables"] if t["key"] == key)
        out = []
        for n, row in enumerate(self.v.get(key) or [], 1):
            if not any(str(v).strip() for v in row.values() if v is not None):
                continue                                           # an empty row is not a row
            r = {}
            for col in t["columns"]:
                raw = row.get(col["key"])
                blank = raw in (None, "")
                if blank and col["required"]:
                    self.miss.append(f"{t['label']}, row {n}: {col['label']} is blank")
                if col["type"] == "number" and not blank:
                    try:
                        raw = float(str(raw).replace(",", ""))
                    except ValueError:
                        self.miss.append(f"{t['label']}, row {n}: {col['label']} '{raw}' is not a number")
                        raw = None
                r[col["key"]] = None if blank else raw
            out.append(r)
        return out

    def done(self):
        if self.miss:
            raise Missing(self.miss)


def combos(project, miss, which=None):
    """The project's load combinations for a design method. A project carries two lists,
    ASD (also the service combinations for soil bearing) and LRFD (also the factored
    combinations for concrete). An older project file has one list, for its own method."""
    which = which or project.get("method")
    if which not in ("ASD", "LRFD"):
        return []                                           # the method message covers this
    rows = project.get("combos_asd" if which == "ASD" else "combos_lrfd")
    if rows is None and (project.get("_file_method") or project.get("method")) == which:
        rows = project.get("combos")                        # older file: one list, for the method it was saved with
    out = []
    for n, c in enumerate(rows or [], 1):
        if not (c.get("expr") or "").strip():
            continue
        try:
            fac = parse_expr(c["expr"])
        except ValueError as e:
            miss.append(f"{which} load combinations, row {n}: {e}")
            continue
        if not (c.get("source") or "").strip():
            miss.append(f"{which} load combinations, row {n}: the source is blank")
            continue
        out.append(Combo(c["expr"].strip(), fac, c["source"].strip()))
    if not out:
        miss.append(f"No {which} load combinations are entered for the project (Project page)")
    return out


def checks(rows, miss, what):
    out = []
    for n, r in enumerate(rows, 1):
        try:
            out.append(DeflCheck(r["label"], parse_expr(r["expr"]), r["ratio"], r["source"]))
        except (ValueError, TypeError) as e:
            miss.append(f"{what}, row {n}: {e}")
    return out


def cases_used(cases, cb, miss):
    """A load whose case is in no combination would be left out without a word."""
    known = set().union(*[set(c.factors) for c in cb]) if cb else set()
    for c in sorted({str(x) for x in cases if x} - known):
        if cb:
            miss.append(f"Load case {c} is not in any load combination, so its loads would be left out")


def method(project, miss):
    m = project.get("method")
    if m not in ("ASD", "LRFD"):
        miss.append("Design method (ASD or LRFD) is not chosen on the Project page")
    return m


def yes(v):
    return {"yes": True, "no": False}.get(v)


# ------------------------------------------------------------------ building each worksheet
def build(kind, values, project):
    """Returns (sheet, pdf kind, keyword arguments for the calc sheet)."""
    form = FORMS[kind]
    r = Reader(form, values)
    mark = (values.get("mark") or "").strip()
    if not mark:
        r.miss.append("Mark is blank")
    if kind == "steel_beam":
        cb, m = combos(project, r.miss), method(project, r.miss)
        shape, Fy, span = r.text("shape"), r.num("Fy"), r.num("span")
        br, sw = r.text("bracing"), yes(r.text("self_weight"))
        pts = []
        if br == "at points":
            pts = r.nums("brace_pts") or []
        loads = []
        more = (r.nums("more_spans") or []) if r.text("more_spans", False) else []
        total = (span or 0.0) + sum(more) + (r.num("oh_left", False) or 0.0) + (r.num("oh_right", False) or 0.0)
        for ld in r.rows("loads"):
            if ld["kind"] == "uniform":
                d = dict(case=ld["case"], kind="uniform", w=ld["mag"])
                if ld["x1"] is not None or ld["x2"] is not None:
                    d.update(x1_ft=ld["x1"] or 0.0, x2_ft=ld["x2"] if ld["x2"] is not None else total)
            else:
                if ld["x1"] is None:
                    r.miss.append("Loads: a point load needs its location (From / at)")
                d = dict(case=ld["case"], kind="point", P=ld["mag"], x_ft=ld["x1"])
            if ld["label"]:
                d["label"] = ld["label"]
            loads.append(d)
        if not loads and sw is False:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([ld["case"] for ld in loads], cb, r.miss)
        r.done()
        s = ws_steel_beam.run(mark, shape, Fy, span, loads, cb, dc, "continuous" if br == "continuous" else pts, m, sw,
                              spans=[span] + more if more else None, overhang_left=r.num("oh_left", False) or 0.0, overhang_right=r.num("oh_right", False) or 0.0)
        return s, "steel_beam", dict(combos=cb)
    if kind == "steel_column":
        cb, m = combos(project, r.miss), method(project, r.miss)
        shape, Fy, H = r.text("shape"), r.num("Fy"), r.num("height")
        ends = r.text("ends") or ""
        sway = () if ends.startswith("held") else ("x",) if "about x" in ends else ("y",) if "about y" in ends else ("x", "y")
        Lx, Ly = r.num("Lx", False), r.num("Ly", False)
        Kx, Ky, ks, sw = r.num("Kx"), r.num("Ky"), r.text("k_source"), yes(r.text("self_weight"))
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        lat = []
        for x in r.rows("lateral"):
            d = dict(case=x["case"], bending=x["bending"], kind=x["kind"])
            if x["kind"] == "uniform":
                d["w"] = x["mag"]
            else:
                if x["x"] is None:
                    r.miss.append("Sideways loads: a point load needs its height")
                d.update(P=x["mag"], x_ft=x["x"])
            if x["label"]:
                d["label"] = x["label"]
            lat.append(d)
        lean = [dict(case=x["case"], P=x["P"]) for x in r.rows("leaning")]
        dc = checks(r.rows("drift"), r.miss, "Drift limits")
        cases_used([x["case"] for x in loads + lat + lean], cb, r.miss)
        r.done()
        s = ws_steel_column.run(mark, shape, Fy, H, loads, cb, Kx, Ky, ks, m, sw, Lx_ft=Lx, Ly_ft=Ly,
                                lateral=lat, sway=sway, leaning=lean, drift_checks=dc)
        return s, "steel_column", dict(combos=cb)
    if kind == "footing_iso":
        a = dict(B_ft=r.num("B"), L_ft=r.num("L"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"),
                 col_x_in=r.num("col_x"), col_y_in=r.num("col_y"), bar=r.num("bar"), n_x=r.num("n_x"), n_y=r.num("n_y"),
                 cover_in=r.num("cover"), P_service=r.num("P_service"), service_combo=r.text("service_combo"),
                 Pu=r.num("Pu"), strength_combo=r.text("strength_combo"), q_allow_psf=r.num("q_allow"),
                 conc_pcf=r.num("conc_pcf"), plate_x_in=r.num("plate_x", False), plate_y_in=r.num("plate_y", False),
                 bottom_layer=r.text("bottom"), soil_depth_ft=r.num("soil_depth", False) or 0.0,
                 soil_pcf=r.num("soil_pcf", False) or 0.0)
        src, sup = r.text("soil_source"), r.text("supported")
        if a["soil_depth_ft"] and not a["soil_pcf"]:
            r.miss.append("Soil weight is blank (soil over the footing was entered)")
        r.done()
        for k in ("bar", "n_x", "n_y"):
            a[k] = int(a[k])
        fs = ws_footing.isolated(mark, src, sup, **a)
        if r.text("loads_from", False):
            fs.result.notes.append("Loads: " + r.text("loads_from", False) + ".")
        return fs, "footing", {}
    if kind == "footing_cont":
        a = dict(W_ft=r.num("W"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"), wall_in=r.num("wall"),
                 bar_t=r.num("bar_t"), spacing_t_in=r.num("spacing_t"), bar_l=r.num("bar_l"), n_l=r.num("n_l"),
                 cover_in=r.num("cover"), P_service_plf=r.num("P_service"), service_combo=r.text("service_combo"),
                 Pu_plf=r.num("Pu"), strength_combo=r.text("strength_combo"), dead_factor=r.num("dead_factor"),
                 q_allow_psf=r.num("q_allow"), conc_pcf=r.num("conc_pcf"), wall_kind=r.text("wall_kind"),
                 stem_h_in=r.num("stem_h", False) or 0.0, stem_pcf=r.num("stem_pcf", False),
                 soil_depth_ft=r.num("soil_depth", False) or 0.0, soil_pcf=r.num("soil_pcf", False) or 0.0)
        src = r.text("soil_source")
        if a["stem_h_in"] and a["stem_pcf"] is None:
            r.miss.append("Stem wall weight is blank (a stem wall height was entered)")
        r.done()
        for k in ("bar_t", "bar_l", "n_l"):
            a[k] = int(a[k])
        return ws_footing.continuous(mark, src, **a), "footing", {}
    if kind == "frame":
        cb, m = combos(project, r.miss), method(project, r.miss)
        bays, stories = r.nums("bays"), r.nums("stories")
        base, roof, rise = r.text("base"), r.text("roof"), r.num("rise", False)
        cs, bs, rs, Fy = r.text("col_shape"), r.text("beam_shape"), r.text("rafter_shape", False), r.num("Fy")
        ub = {"columns": r.num("lb_col"), "beams": r.num("lb_beam")}
        lr = r.num("lb_rafter", False)
        if roof in ("gable", "mono"):
            if lr is None:
                r.miss.append("Rafters braced at is blank")
            if rise is None:
                r.miss.append("Roof rise is blank")
            ub["rafters"] = lr
        sw = yes(r.text("self_weight"))
        loads = []
        for x in r.rows("loads"):
            k, where = x["kind"], (x["where"] or "").strip()
            if k == "joint load":
                loads.append(dict(case=x["case"], node=where.replace("joint", "").strip(), Fx=x["Fx"] or 0.0, Fy=-x["mag"]))
            elif k == "lateral at level":
                try:
                    lv = int(where.lower().replace("lateral", "").replace("level:", "").replace("level", "").strip())
                except ValueError:
                    r.miss.append(f"Loads: '{where}' is not a level (type level:1)")
                    continue
                loads.append(dict(case=x["case"], level=lv, Fx=x["mag"]))
            else:
                d = dict(case=x["case"], on=where, w=x["mag"],
                         kind="projected" if "horizontal" in k else "length")
                if k.startswith("sideways"):
                    d["dir"] = "x"
                loads.append(d)
            if x["label"]:
                loads[-1]["label"] = x["label"]
        lean = [dict(case=x["case"], level=int(x["level"]), P=x["P"]) for x in r.rows("leaning") if x["level"] is not None]
        dc = checks(r.rows("drift"), r.miss, "Story drift limits")
        over = {x["member"]: x["shape"] for x in r.rows("shape_of") if x["member"] and x["shape"]}
        cases_used([x["case"] for x in loads + lean], cb, r.miss)
        r.done()
        lay = ws_frame.layout(bays, stories, base, cs, bs, roof=roof, rise_ft=rise or 0.0, rafter_shape=rs, shape_of=over)
        s = ws_frame.run(mark, lay, Fy, loads, cb, m, sw, ub, leaning=lean, drift_checks=dc)
        return s, "frame", {}
    if kind == "stair_tread":
        m = method(project, r.miss)
        args = (r.num("t"), r.num("b"), r.num("d"), r.num("span"), r.num("Fy"), r.text("Fy_source"), r.num("live_psf"), r.num("live_P"), r.text("live_source"))
        r.done()
        return ws_more.stair_tread_sheet(mark, *args, m), "simple", {}
    if kind == "tension_member":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No tension is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        args = (r.text("shape"), r.num("Fy"), r.num("Fu"), r.text("steel_source"), r.num("length"), r.num("n_holes", False), r.num("bolt_d", False), r.num("hole_t", False),
                r.num("U"), r.text("U_source"))
        r.done()
        return ws_more.tension_member_sheet(mark, *args, loads, cb, m), "simple", {}
    if kind == "wind_enclosure":
        walls = [dict(name=x["name"], gross=x["gross"], open=x["open"]) for x in r.rows("walls")]
        if not walls:
            r.miss.append("No walls are entered")
        rg, ro, ob = r.num("roof_gross"), r.num("roof_open", False), r.text("openings_basis")
        r.done()
        return ws_more.wind_enclosure_sheet(mark, walls, rg, ro or 0.0, ob), "simple", {}
    if kind == "base_plate_uplift":
        m = method(project, r.miss)
        args = (r.text("shape"), r.num("col_Fy"), r.num("N"), r.num("B"), r.num("t"), r.num("Fy"), r.num("rod_d"), r.num("rod_Fu"), r.text("rod_source"), r.num("gauge"), r.num("pitch"),
                r.num("weld"), r.num("FEXX"))
        cases = r.rows("cases")
        if not cases:
            r.miss.append("No load case is entered")
        r.done()
        return ws_more.base_plate_uplift_sheet(mark, *args, cases, m), "simple", {}
    if kind == "single_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No reaction is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        hc = bool(r.text("column", False))
        sup = None if hc else dict(name=r.text("support_name", True) or "", t=r.num("support_t", True, label="Other support: thickness at the weld"), Fu=r.num("support_Fu", True, label="Other support: Fu"))
        args = (r.text("column", False) or "", r.num("col_Fy", hc), r.num("col_Fu", hc), r.text("col_source", hc) or "", r.text("beam"), r.num("beam_Fu"), r.text("beam_source"), r.num("tp"), r.num("plate_Fy"),
                r.num("plate_Fu"), r.text("plate_source"), r.num("d"), r.text("group"), r.text("threads"), r.num("n"), r.num("spacing"), r.num("lev"), r.num("leh"), r.num("a"),
                r.text("holes"), r.num("weld"), r.num("FEXX"))
        r.done()
        return ws_more.single_plate_sheet(mark, *args, loads, cb, m, support=sup), "simple", {}
    if kind in ("weld", "bolts"):
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No force is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        if kind == "weld":
            a = dict(size=r.num("size"), length=r.num("length"), n_lines=r.num("n_lines"), FEXX=r.num("FEXX"),
                     theta_deg=r.num("theta"), directional=yes(r.text("directional")), end_loaded=yes(r.text("end_loaded")),
                     t_thinner=r.num("t_thinner", False), t_edge=r.num("t_edge", False),
                     base_t=r.num("base_t", False), base_Fu=r.num("base_Fu", False))
            if (a["base_t"] is None) != (a["base_Fu"] is None):
                r.miss.append("Base metal: give both the thickness and Fu, or neither")
            r.done()
            return ws_conn.fillet_weld(mark, loads, cb, m, **a), "conn", dict(combos=cb)
        plies = []
        for x in r.rows("plies"):
            ply = (x["t"], x["Fu"], yes(x["has_edge"]))
            plies.append(ply + ((int(x["count"]),) if x["count"] else ()))
        if not plies:
            r.miss.append("No connected parts are entered")
        a = dict(d=r.num("d"), group=r.text("group"), n=r.num("n"), spacing=r.num("spacing"), edge=r.num("edge"),
                 threads=r.text("threads"), planes=r.num("planes"), deformation=yes(r.text("deformation")))
        r.done()
        return ws_conn.bolt_line(mark, loads, cb, m, plies=plies, **a), "conn", dict(combos=cb)
    if kind == "wood_post":
        cb = combos(project, r.miss, "ASD")
        sp, gr, size, H = r.text("species"), r.text("grade"), r.text("size"), r.num("height")
        Ke1, Ke2, ks = r.num("Ke1"), r.num("Ke2"), r.text("k_source")
        wet = {"dry service": False, "wet service": True}.get(r.text("service"))
        inc = yes(r.text("incised"))
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        lat = []
        for x in r.rows("lateral"):
            if x["kind"] == "uniform":
                d = dict(case=x["case"], kind="uniform", w=x["mag"])
            else:
                if x["x"] is None:
                    r.miss.append("Lateral load: a point load needs its location")
                d = dict(case=x["case"], kind="point", P=x["mag"], x_ft=x["x"])
            if x["label"]:
                d["label"] = x["label"]
            lat.append(d)
        if not loads and not lat:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads + lat], cb, r.miss)
        r.done()
        return ws_wood.post(mark, sp, gr, size, H, loads, cb, Ke1, Ke2, ks, wet, inc, r.num("lu1", False), r.num("lu2", False),
                            r.num("unit_weight", False), lateral=lat, e1_in=r.num("e1", False) or 0.0, e2_in=r.num("e2", False) or 0.0), "simple", {}
    if kind == "glulam_post":
        cb = combos(project, r.miss, "ASD")
        co, b_, d_, n_, H = r.text("combination"), r.num("b"), r.num("d"), r.num("lams"), r.num("height")
        Kd, Kb, ks = r.num("Ke_d"), r.num("Ke_b"), r.text("k_source")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_wood.glulam_post(mark, co, b_, d_, int(n_), H, loads, cb, Kd, Kb, ks, r.num("lu_d", False), r.num("lu_b", False),
                                   r.num("e_d", False) or 0.0, r.num("e_b", False) or 0.0, r.num("unit_weight", False)), "simple", {}
    if kind == "builtup_post":
        cb = combos(project, r.miss, "ASD")
        sp, gr, size, n_, fa, H = r.text("species"), r.text("grade"), r.text("size"), r.text("plies"), r.text("fastening"), r.num("height")
        Kd, Ks, ks = r.num("Ke_d"), r.num("Ke_stack"), r.text("k_source")
        wet = {"dry service": False, "wet service": True}.get(r.text("service"))
        inc = yes(r.text("incised"))
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_wood.builtup_post(mark, sp, gr, size, int(n_), fa, H, loads, cb, Kd, Ks, ks, wet, inc, r.num("lu_d", False),
                                    r.num("lu_stack", False), r.num("unit_weight", False)), "simple", {}
    if kind == "ijoist":
        from .. import ws_ijoist
        cb = combos(project, r.miss, "ASD")
        nm, dep, span, bearing = r.text("name"), r.text("depth"), r.num("span"), r.num("bearing")
        stf, flg = yes(r.text("stiffeners")), yes(r.text("flange"))
        loads = []
        for ld in r.rows("loads"):
            if ld["kind"] in ("uniform", "area"):
                d = dict(case=ld["case"], kind="uniform", w=ld["mag"]) if ld["kind"] == "uniform" else dict(case=ld["case"], kind="area", q=ld["mag"])
                if ld.get("mag2") is not None:
                    d.update({"w2" if ld["kind"] == "uniform" else "q2": ld["mag2"]})
                if ld["x1"] is not None or ld["x2"] is not None:
                    d.update(x1_ft=ld["x1"] or 0.0, **({"x2_ft": ld["x2"]} if ld["x2"] is not None else {}))
            else:
                if ld["x1"] is None:
                    r.miss.append("Loads: a point load needs its location (From / at)")
                d = dict(case=ld["case"], kind="point", P=ld["mag"], x_ft=ld["x1"])
            if ld["label"]:
                d["label"] = ld["label"]
            loads.append(d)
        if not loads:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([ld["case"] for ld in loads], cb, r.miss)
        r.done()
        if any(ld["kind"] == "area" for ld in loads) and r.num("spacing", False) is None:
            raise Missing(["Joist spacing is blank; an area load in psf needs it"])
        more = r.nums("more_spans") if r.text("more_spans", False) else None
        if more and r.num("bearing_int", False) is None:
            raise Missing(["Bearing length at intermediate supports is blank"])
        return ws_ijoist.joist(mark, nm, float(dep), span, r.num("spacing", False), loads, cb, dc, bearing, stf, flg,
                               spans=[span] + more if more else None, overhang_left=r.num("oh_left", False) or 0.0,
                               overhang_right=r.num("oh_right", False) or 0.0, bearing_int_in=r.num("bearing_int", False),
                               stiffeners_int=bool(yes(r.text("stiffeners_int", False))),
                               snow_partial=not (r.text("snow_partial", False) or "").startswith("not required"),
                    rise_on_12=r.num("rise", False) or 0.0), "simple", {}
    if kind in ("lvl_post", "wey_post"):
        cb = combos(project, r.miss, "ASD")
        gr, b_, d_, H = r.text("grade"), r.num("b"), r.num("d"), r.num("height")
        prod = "Versa-Lam LVL"
        if kind == "wey_post" and gr:
            prod = next(p_ for p_ in scl.WEY if gr.startswith(p_ + " "))
            gr = gr[len(prod) + 1:]
        Ke1, Ke2, ks = r.num("Ke1"), r.num("Ke2"), r.text("k_source")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        lat = []
        for x in r.rows("lateral"):
            if x["kind"] == "uniform":
                d = dict(case=x["case"], kind="uniform", w=x["mag"])
            else:
                if x["x"] is None:
                    r.miss.append("Lateral load: a point load needs its location")
                d = dict(case=x["case"], kind="point", P=x["mag"], x_ft=x["x"])
            if x["label"]:
                d["label"] = x["label"]
            lat.append(d)
        if not loads and not lat:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads + lat], cb, r.miss)
        r.done()
        return ws_wood.lvl_post(mark, gr, b_, d_, H, loads, cb, Ke1, Ke2, ks, r.num("lu1", False), r.num("lu2", False),
                                r.num("e1", False) or 0.0, r.num("e2", False) or 0.0, r.num("unit_weight", False), product=prod, lateral=lat,
                                plies=int(r.text("plies", False) or 1), fastening=r.text("fastening", False) or None), "simple", {}
    if kind in ("wood_beam", "lvl_beam", "glulam_beam", "wey_beam"):
        cb = combos(project, r.miss, "ASD")
        lvl, glu = kind in ("lvl_beam", "wey_beam"), kind == "glulam_beam"
        if glu:
            gr, sp_, thk, dep, span = r.text("stress_class"), r.text("species"), r.num("b"), r.num("d"), r.num("span")
        elif lvl:
            gr, thk, dep, plies, span = r.text("grade"), r.num("thickness"), r.num("depth"), r.text("plies"), r.num("span")
        else:
            sp, gr, size, plies, span = r.text("species"), r.text("grade"), r.text("size"), r.text("plies"), r.num("span")
        br, bearing = r.text("bracing"), r.num("bearing")
        lu = r.num("lu", br == "braced at a spacing", label="Brace spacing") if br == "braced at a spacing" else 0.0
        uw = r.num("unit_weight", False)
        rep = None if glu else yes(r.text("repetitive"))
        if not lvl:
            wet = {"dry service": False, "wet service": True}.get(r.text("service"))
        if not lvl and not glu:
            inc = yes(r.text("incised"))
        loads = []
        for ld in r.rows("loads"):
            if ld["kind"] in ("uniform", "area"):
                d = dict(case=ld["case"], kind="uniform", w=ld["mag"]) if ld["kind"] == "uniform" else \
                    dict(case=ld["case"], kind="area", q=ld["mag"])
                if ld.get("mag2") is not None:
                    d.update({"w2" if ld["kind"] == "uniform" else "q2": ld["mag2"]})
                if ld["x1"] is not None or ld["x2"] is not None:
                    d.update(x1_ft=ld["x1"] or 0.0, **({"x2_ft": ld["x2"]} if ld["x2"] is not None else {}))
            else:
                if ld["x1"] is None:
                    r.miss.append("Loads: a point load needs its location (From / at)")
                d = dict(case=ld["case"], kind="point", P=ld["mag"], x_ft=ld["x1"])
            if ld["label"]:
                d["label"] = ld["label"]
            loads.append(d)
        if not loads:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([ld["case"] for ld in loads], cb, r.miss)
        r.done()
        if any(ld["kind"] == "area" for ld in loads) and r.num("spacing", False) is None:
            raise Missing(["Member spacing is blank; an area load in psf needs it"])
        more = r.nums("more_spans") if r.text("more_spans", False) else None
        cont = dict(spans=[span] + more if more else None, overhang_left=r.num("oh_left", False) or 0.0,
                    overhang_right=r.num("oh_right", False) or 0.0, lu_neg_ft=r.num("lu_neg", False),
                    bearing_int_in=r.num("bearing_int", False),
                    snow_partial=not (r.text("snow_partial", False) or "").startswith("not required"),
                    rise_on_12=r.num("rise", False) or 0.0)
        if glu:
            return ws_wood.glulam_beam(mark, gr, sp_ == "Southern Pine", thk, dep, span, loads, cb, dc, lu or 0.0, bearing, wet, uw,
                                       spacing_in=r.num("spacing", False), **cont), "simple", {}
        if lvl:
            prod = "Versa-Lam LVL"
            if kind == "wey_beam":
                prod = next(p_ for p_ in scl.WEY if gr.startswith(p_ + " "))
                gr = gr[len(prod) + 1:]
            return ws_wood.lvl_beam(mark, gr, thk, dep, int(plies), span, loads, cb, dc, lu or 0.0, bearing, rep, uw,
                                    spacing_in=r.num("spacing", False), product=prod, **cont), "simple", {}
        return ws_wood.beam(mark, sp, gr, size, int(plies), span, loads, cb, dc, lu or 0.0, bearing, wet, inc, rep, uw,
                            spacing_in=r.num("spacing", False), flat=bool(yes(r.text("flat", False))), **cont), "simple", {}
    if kind == "decking":
        cb = combos(project, r.miss, "ASD")
        sp, gr, th, span, lay_ = r.text("species"), r.text("grade"), r.text("thickness"), r.num("span"), r.text("layout")
        rep, wet = yes(r.text("repetitive")), {"dry service": False, "wet service": True}.get(r.text("service"))
        loads = [dict(case=x["case"], q=x["q"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_wood.decking(mark, sp, gr, int(th), span, lay_, bool(rep), bool(wet), loads, cb, dc), "simple", {}
    if kind == "perforated_wall":
        m = method(project, r.miss)
        panel, sp, pt = r.text("panel"), r.text("spacing"), r.text("panel_type")
        G, gs, h, Lw, load, V, vs = r.num("G"), r.text("G_source"), r.num("h"), r.num("length"), r.text("load"), r.num("V"), r.text("v_source")
        sides = 2 if (r.text("sides") or "").startswith("both") else 1
        ops = r.rows("openings")
        if not ops:
            r.miss.append("No opening is entered (a wall without openings is a Wood Shear Wall)")
        r.done()
        return ws_more.perforated_wall_sheet(mark, panel, int(sp), pt, G, gs, h, Lw, ops, V, load, m, vs, yes(r.text("holddown", False)),
                                             sides, r.num("chord_E", False), r.num("chord_A", False), r.num("slip", False)), "simple", {}
    if kind == "shear_wall":
        m = method(project, r.miss)
        panel, sp, pt = r.text("panel"), r.text("spacing"), r.text("panel_type")
        G, gs, h, load, V, vs = r.num("G"), r.text("G_source"), r.num("h"), r.text("load"), r.num("V"), r.text("v_source")
        lengths = r.nums("lengths")
        if lengths is not None and not lengths:             # typed, but no number in it (a blank box is already listed)
            r.miss.append("Full-height segment lengths holds no number")
        sd_ = r.text("sides") or ""
        oth = None
        if "different" in sd_:
            p2, s2, t2 = r.text("panel2", False), r.text("spacing2", False), r.text("panel_type2", False)
            if not (p2 and s2 and t2):
                r.miss.append("Other side: sheathing and nails, edge nail spacing and panel are needed")
            else:
                oth = dict(panel=p2, spacing=int(s2), panel_type=t2)
        sides = 2 if (sd_.startswith("both") and "different" not in sd_) else 1
        blocked = r.text("blocking") != "unblocked"
        ss_, fn_ = r.text("stud_spacing", False), r.text("field_nails", False)
        if not blocked and (not ss_ or not fn_):
            r.miss.append("Unblocked wall: stud spacing and nail spacing at intermediate framing are needed")
        dead = r.num("dead", False)
        if dead and r.num("dead_factor", False) is None:
            r.miss.append("Uplift: dead load factor is blank")
        r.done()
        return ws_more.shear_wall_sheet(mark, panel, int(sp), pt, G, gs, h, lengths, V, load, m, vs, yes(r.text("holddown", False)),
                                        r.num("arm_offset", False) or 0.0, r.num("chord_E", False), r.num("chord_A", False),
                                        r.num("slip", False), sides=sides, blocked=blocked, stud_spacing=int(ss_) if ss_ else None,
                                        field_nails=int(fn_) if fn_ else None, dead_plf=dead or 0.0,
                                        dead_factor=r.num("dead_factor", False), dead_source=r.text("dead_source", False) or "", other=oth), "simple", {}
    if kind == "wind_kzt":
        shape, ex, eb, H, Lh, gs, x = r.text("shape"), r.text("exposure"), r.text("exposure_basis"), r.num("H"), r.num("Lh"), r.text("geometry_source"), r.num("x")
        side, loc = r.text("side"), yes(r.text("located"))
        hs = r.nums("heights") if r.text("heights") else []
        r.done()
        return ws_more.wind_kzt_sheet(mark, shape, ex, eb, H, Lh, gs, x, (side or "").startswith("downwind"), bool(loc), hs), "simple", {}
    if kind == "wind_free_roof":
        args = (r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis"), r.num("h"), r.num("theta"), r.num("L"))
        fl, fb, kzt, ks_ = r.text("flow"), r.text("flow_basis"), r.num("Kzt"), r.text("Kzt_source")
        rf = {"pitched (gable)": "pitched", "troughed": "troughed", "hip": "hip"}.get(r.text("roof") or "", "monoslope")
        if rf == "hip":
            th2, ln = r.num("theta_hip", True, label="Hip roof: angle of the hip ends"), r.num("width", True, label="Roof dimension perpendicular to L (the building length)")
            r.done()
            return ws_more.wind_free_hip_sheet(mark, args[0], args[1], args[2], args[3], args[4], args[5], th2, args[6], ln, fl == "obstructed", fb, kzt, ks_,
                                               r.num("elevation", False), r.text("elevation_source", False) or ""), "simple", {}
        r.done()
        return ws_more.wind_free_roof_sheet(mark, *args, fl == "obstructed", fb, kzt, ks_, r.num("elevation", False), r.text("elevation_source", False) or "", roof=rf, width=r.num("width", False)), "simple", {}
    if kind == "wind_pressure":
        V, vs, ex, eb, h = r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis"), r.num("h")
        kzt, ks_ = r.num("Kzt"), r.text("Kzt_source")
        hs = r.nums("heights") if r.text("heights", False) else []
        r.done()
        return ws_more.wind_pressure_sheet(mark, V, vs, ex, eb, hs, h, kzt, ks_, r.num("elevation", False),
                                           r.text("elevation_source", False) or ""), "simple", {}
    if kind == "wind_mwfrs":
        V, vs, ex, eb, h = r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis"), r.num("h")
        en, enb, ac, al, ev, th = r.text("enclosure"), r.text("enclosure_basis"), r.num("across"), r.num("along"), r.num("eave"), r.num("theta")
        kzt, ks_ = r.num("Kzt"), r.text("Kzt_source")
        thh = r.num("theta_hip", r.text("roof", False) == "hip", label="Hip roof: hip end roof angle")
        r.done()
        return ws_more.wind_mwfrs_sheet(mark, V, vs, ex, eb, h, ev, ac, al, th, en, enb, kzt, ks_, r.num("elevation", False),
                                        r.text("elevation_source", False) or "",
                                        roof={"mon": "monoslope", "hip": "hip"}.get((r.text("roof", False) or "")[:3], "gable"),
                                        parapet=r.num("parapet", False) or 0.0, theta_hip=thh, overhang=r.num("overhang", False) or 0.0), "simple", {}
    if kind == "wind_cc_walls":
        V, vs, ex, eb, h = r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis"), r.num("h")
        en, enb, ld, th = r.text("enclosure"), r.text("enclosure_basis"), r.num("least"), r.num("theta")
        ars = r.nums("areas") if r.text("areas") else []
        kzt, ks_ = r.num("Kzt"), r.text("Kzt_source")
        r.done()
        return ws_more.wind_cc_walls_sheet(mark, V, vs, ex, eb, h, ld, th, en, enb, ars, kzt, ks_, r.num("elevation", False),
                                           r.text("elevation_source", False) or ""), "simple", {}
    if kind == "wind_cc_roof":
        V, vs, ex, eb, h = r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis"), r.num("h")
        en, enb, th = r.text("enclosure"), r.text("enclosure_basis"), r.num("theta")
        mono = (r.text("roof", False) or "").startswith("mono")
        ld = r.num("least", th is not None and th > (3 if mono else 7), label="Least horizontal dimension")
        hipr = r.text("roof", False) == "hip"
        ars = r.nums("areas") if r.text("areas") else []
        kzt, ks_ = r.num("Kzt"), r.text("Kzt_source")
        r.done()
        return ws_more.wind_cc_roof_sheet(mark, V, vs, ex, eb, h, th, en, enb, ars, kzt, ks_, r.num("elevation", False),
                                          r.text("elevation_source", False) or "", least_dim=ld,
                                          roof="monoslope" if mono else "hip" if hipr else "gable", overhang=bool(yes(r.text("overhang", False))),
                                          parapet=bool(yes(r.text("parapet", False)))), "simple", {}
    if kind == "wind_cc_parapet":
        V, vs, ex, eb = r.num("V"), r.text("V_source"), r.text("exposure"), r.text("exposure_basis")
        hp, h, ld, th = r.num("hp"), r.num("h"), r.num("least"), r.num("theta")
        ars = r.nums("areas") if r.text("areas") else []
        kzt, ks_ = r.num("Kzt"), r.text("Kzt_source")
        r.done()
        return ws_more.wind_cc_parapet_sheet(mark, V, vs, ex, eb, hp, h, ld, th, ars, kzt, ks_, r.num("elevation", False),
                                             r.text("elevation_source", False) or ""), "simple", {}
    if kind == "seismic_elf":
        SDS, SD1, S1, TL, gs = r.num("SDS"), r.num("SD1"), r.num("S1"), r.num("TL"), r.text("ground_source")
        from .. import seismic as _seis
        sysn = r.text("system", False)
        sysn = sysn if sysn in _seis.SYSTEMS else None
        if sysn:
            row_ = _seis.SYSTEMS[sysn]
            R, Rs = row_[1], f"{sysn}, Table 12.2-1 line {row_[0]}"
        else:
            R, Rs = r.num("R", True, label="Other system: R"), r.text("R_source")
        Ie, Is, st, hn = r.num("Ie"), r.text("Ie_source"), r.text("structure"), r.num("hn")
        rk = r.text("risk")
        lv = r.rows("levels")
        if not lv:
            r.miss.append("No level is entered")
        dr = None
        if any(x.get("de") is not None for x in lv or []) or (not sysn and r.num("Cd", False) is not None):
            dr = dict(Cd=(_seis.SYSTEMS[sysn][3] if sysn else r.num("Cd", label="Drift: Cd")),
                      Cd_source=(f"Table 12.2-1 line {_seis.SYSTEMS[sysn][0]}" if sysn else r.text("Cd_source")), structure=r.text("drift_type"), de_source=r.text("de_source"),
                      de={str(x["name"]): x.get("de") for x in lv or []})
            for x in lv or []:
                if x.get("de") is None:
                    r.miss.append(f"Levels: the elastic displacement of {x['name']} is blank")
        wl = r.rows("lines")
        rho = r.text("rho", bool(wl)) if wl else None
        rho_s = r.text("rho_source", bool(wl)) if wl else ""
        r.done()
        return ws_more.seismic_elf_sheet(mark, SDS, SD1, S1, TL, gs, R, Rs, Ie, Is, st, hn, [(x["name"], x["w"], x["h"], x.get("wp")) for x in lv],
                                         r.num("T", False), r.text("T_source", False) or "", risk=rk, drift=dr,
                                         wall_lines=[(x["name"], x["level"], x["share"]) for x in wl] or None, rho=float(rho) if rho else None,
                                         rho_source=rho_s or "", system=sysn), "simple", {}
    if kind == "live_load":
        fl, rf = r.rows("floors"), r.rows("roofs")
        if not fl and not rf:
            r.miss.append("No floor member or roof member is entered")
        r.done()
        return ws_more.live_load_sheet(mark, fl, rf), "simple", {}
    if kind == "collector":
        W_, R_, lv, rs_ = r.num("W"), r.num("R"), r.text("level"), r.text("R_source")
        segs = r.rows("walls")
        if not segs:
            r.miss.append("No wall is entered on the line")
        r.done()
        return ws_more.collector_sheet(mark, W_, R_, rs_, lv, segs, r.text("line_name", False) or ""), "simple", {}
    if kind == "diaphragm":
        m = method(project, r.miss)
        blk = r.text("edges") == "blocked"
        panel, face, pt = r.text("panel"), r.text("face"), r.text("panel_type")
        case = r.text("case", not blk)
        if not blk and not case:
            pass
        spc = r.text("spacing", False)
        if blk and not spc:
            r.miss.append("Blocked: nail spacing at the boundaries is blank")
        G, gs, L_, W_, load, w, ws = r.num("G"), r.text("G_source"), r.num("L"), r.num("W"), r.text("load"), r.num("w"), r.text("w_source")
        sp = r.rows("splices")
        r.done()
        return ws_more.diaphragm_sheet(mark, panel, int(face), 1 if case == "Case 1" else 2, pt, G, gs, L_, W_, w, ws, load, m,
                                       r.num("chord_E", False), r.num("chord_A", False), [(x["x"], x["slip"]) for x in sp],
                                       r.num("defl_limit", False), r.text("defl_limit_source", False) or "", blocked=blk,
                                       spacing=({"2-1/2": 2.5}.get(spc) or float(spc)) if blk else None), "simple", {}
    if kind == "nailed_connection":
        cb = combos(project, r.miss, "ASD")
        from .. import dowel as _dowel
        nm, n_ = r.text("nail"), r.num("n")
        if nm in _dowel.NAILS:
            Lg, D = _dowel.NAILS[nm]
        else:
            nm = r.text("nail_name", bool(nm), ) if nm else None
            D, Lg = r.num("D", True, label="Other nail: diameter"), r.num("length", True, label="Other nail: length")
        ts, Gs, Gss, tm, Gm, Gms, sv = r.num("side_t"), r.num("G_side"), r.text("G_side_source"), r.num("main_t"), r.num("G_main"), r.text("G_main_source"), r.text("service")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_more.nailed_connection_sheet(mark, nm, D, Lg, ts, Gs, Gss, tm, Gm, Gms, n_, sv, loads, cb,
                                               end_grain=bool(yes(r.text("end_grain", False))), diaphragm=bool(yes(r.text("diaphragm", False))),
                                               toe_nail=bool(yes(r.text("toe_nail", False)))), "simple", {}
    if kind == "screw_connection":
        cb = combos(project, r.miss, "ASD")
        from .. import dowel as _dowel
        num, n_, Lg = r.text("screw"), r.num("n"), r.num("length")
        ts, Gs, Gss, tm, Gm, Gms, sv = r.num("side_t"), r.num("G_side"), r.text("G_side_source"), r.num("main_t"), r.num("G_main"), r.text("G_main_source"), r.text("service")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        if num not in _dowel.WOOD_SCREWS:
            raise Missing(["The wood screw number is one of " + ", ".join(_dowel.WOOD_SCREWS)])
        return ws_more.nailed_connection_sheet(mark, num, _dowel.WOOD_SCREWS[num][0], Lg, ts, Gs, Gss, tm, Gm, Gms, n_, sv, loads, cb,
                                               end_grain=bool(yes(r.text("end_grain", False))), screw=num), "simple", {}
    if kind == "screw_withdrawal":
        cb = combos(project, r.miss, "ASD")
        num, n_, Lg = r.text("screw"), r.num("n"), r.num("length")
        stl = r.text("side_kind", False) == "steel"
        ts, tm, Gm, Gms, sv = r.num("side_t"), r.num("main_t"), r.num("G_main"), r.text("G_main_source"), r.text("service")
        Gs = r.num("G_side", not stl, label="Side member specific gravity, G")
        Gss = r.text("G_side_source", False) or ""
        if not stl and not Gss:
            r.miss.append("Where the side member G comes from is blank")
        st_ = r.num("steel", False)
        if st_ is not None and not r.text("steel_source", False):
            r.miss.append("Where the allowable tension of the screw comes from is blank")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_more.screw_withdrawal_sheet(mark, num, Lg, n_, ts, Gs, Gss, tm, Gm, Gms, sv, loads, cb, steel=st_,
                                              steel_source=r.text("steel_source", False) or "", steel_side=stl), "simple", {}
    if kind == "nail_withdrawal":
        cb = combos(project, r.miss, "ASD")
        from .. import dowel as _dowel
        nm, n_ = r.text("nail"), r.num("n")
        toe = bool(yes(r.text("toe_nail", False)))
        if nm in _dowel.NAILS:
            (Lg, D), hd = _dowel.NAILS[nm], _dowel.NAIL_HEADS[nm]
        else:
            nm = r.text("nail_name", bool(nm), ) if nm else None
            D, Lg = r.num("D", True, label="Other nail: diameter"), r.num("length", True, label="Other nail: length")
            hd = r.num("head", not toe, label="Other nail: head diameter")
        ts, Gs, Gss, tm, Gm, Gms, sv = r.num("side_t"), r.num("G_side"), r.text("G_side_source"), r.num("main_t"), r.num("G_main"), r.text("G_main_source"), r.text("service")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_more.nail_withdrawal_sheet(mark, nm, D, Lg, hd, ts, Gs, Gss, tm, Gm, Gms, n_, sv, loads, cb, toe_nail=toe), "simple", {}
    if kind == "lag_withdrawal":
        cb = combos(project, r.miss, "ASD")
        Dt, Lt = r.text("D"), r.text("L")
        D = {"1/4": 0.25, "5/16": 0.3125, "3/8": 0.375, "7/16": 0.4375, "1/2": 0.5, "5/8": 0.625, "3/4": 0.75, "7/8": 0.875, "1": 1.0}.get(Dt)
        Lg = {"1": 1.0, "1-1/2": 1.5, "2": 2.0, "2-1/2": 2.5}.get(Lt) or (float(Lt) if Lt and Lt.isdigit() else None)
        n_, ts, tm, Gm, Gms, sv = r.num("n"), r.num("side_t"), r.num("main_t"), r.num("G_main"), r.text("G_main_source"), r.text("service")
        st_ = r.num("steel", False)
        if st_ is not None and not r.text("steel_source", False):
            r.miss.append("Where the allowable tension of the screw comes from is blank")
        brg = None
        if r.num("washer_od", False) is not None or r.num("Fc_perp", False) is not None:
            brg = dict(od=r.num("washer_od", True, label="Washer bearing: washer outside diameter"), hole=r.num("washer_hole", False),
                       Fc_perp=r.num("Fc_perp", True, label="Washer bearing: side member Fc_perp"), source=r.text("Fc_perp_source", False) or "",
                       away=bool(yes(r.text("washer_away", False))))
            if not brg["source"]:
                r.miss.append("Washer bearing: where Fc_perp comes from is blank")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        r.done()
        return ws_more.lag_withdrawal_sheet(mark, D, Lg, n_, ts, tm, Gm, Gms, sv, loads, cb, washer=r.num("washer", False) or 0.0,
                                            end_grain=bool(yes(r.text("end_grain", False))), edge=r.num("edge", False), end=r.num("end", False),
                                            spacing=r.num("spacing", False), steel=st_, steel_source=r.text("steel_source", False) or "",
                                            steel_side=r.text("side_kind", False) == "steel", bearing=brg), "simple", {}
    if kind in ("bolted_connection", "lag_connection"):
        cb = combos(project, r.miss, "ASD")
        Dt = r.text("D")
        islag = kind == "lag_connection"
        D = {"1/4": 0.25, "5/16": 0.3125, "3/8": 0.375, "7/16": 0.4375, "1/2": 0.5, "5/8": 0.625, "3/4": 0.75, "7/8": 0.875, "1": 1.0}.get(Dt)
        lagd = None
        if islag:
            Lt = r.text("L")
            lagd = dict(L={"1": 1.0, "1-1/2": 1.5, "2": 2.0, "2-1/2": 2.5}.get(Lt) or (float(Lt) if Lt and Lt.isdigit() else None), washer=r.num("washer", False), alpha=r.num("alpha", False))
        stl = r.text("side_steel", False) or ""
        stl = "ASTM A36" if "A36" in stl else "ASTM A653 Grade 33" if "A653" in stl else None
        par = not (stl and "main member" in (r.text("grain", False) or ""))        # a wood member is loaded parallel to grain
        sh, rn, nr = ("single" if islag else r.text("shear")), r.num("rows"), r.num("n_row")
        end, edge = r.num("end", par, label="End distance"), r.num("edge", par, label="Edge distance")
        sense, wt = r.text("sense", False), r.text("wood_type", False)
        if par and not sense:
            r.miss.append("Load in the member loaded parallel to grain is blank")
        if par and not wt:
            r.miss.append("Wood (softwood or hardwood) is blank")
        sp = r.num("spacing", bool(nr and nr > 1), label="Spacing in a row")
        rs = r.num("row_spacing", bool(rn and rn > 1), label="Spacing between rows")
        st, sw = r.num("side_t"), r.num("side_w")
        Gs, Es = r.num("G_side", not stl, label="Side member specific gravity, G"), r.num("E_side", not stl, label="Side member E")
        ss = r.text("side_source", False)
        if not stl and not ss:
            r.miss.append("Where the side member values come from is blank")
        mt, mw, Gm, Em, ms, sv = r.num("main_t"), r.num("main_w"), r.num("G_main"), r.num("E_main"), r.text("main_source"), r.text("service")
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        gt = r.text("grain", False) or ""
        gr = "side" if "side" in gt else "main" if "main member" in gt else "parallel"
        pp = None
        if gr != "parallel":
            pp = dict(loaded_edge=r.num("p_loaded", True, label="Perpendicular member: loaded edge distance"),
                      unloaded_edge=r.num("p_unloaded", True, label="Perpendicular member: unloaded edge distance"),
                      end=r.num("p_end", True, label="Perpendicular member: end distance"),
                      Fv=r.num("p_Fv", False), Fv_source=r.text("p_Fv_source", False) or "")
            if pp["Fv"] is not None and not pp["Fv_source"]:
                r.miss.append("Perpendicular member: where Fv comes from is blank")
        loc = None
        lv = {k: (None if islag else r.num(k, False)) for k in ("Ft_main", "Fv_main", "Ft_side", "Fv_side")}
        if any(v is not None for v in lv.values()):
            for k, lab in (("Ft_main", "main member Ft"), ("Fv_main", "main member Fv"), ("Ft_side", "side member Ft"), ("Fv_side", "side member Fv")):
                if lv[k] is None and not (stl and "side" in k):
                    r.miss.append(f"Tear-out: {lab} is blank")
            if not r.text("local_source", False):
                r.miss.append("Tear-out: where Ft and Fv come from is blank")
            loc = dict(lv, source=r.text("local_source", False) or "", hole=r.num("hole", False))
        r.done()
        return ws_more.bolted_connection_sheet(mark, D, rn, nr, sp, rs, end, edge, sh, st, sw, Gs, Es, ss, mt, mw, Gm, Em, ms, sense, wt, sv, loads, cb,
                                               local=loc, grain=gr, perp=pp, lag=lagd, steel=stl), "simple", {}
    if kind == "stair_stringer":
        cb, m = combos(project, r.miss), method(project, r.miss)
        args = (r.text("shape"), r.num("Fy"), r.num("run"), r.num("riser"), r.num("tread"), r.num("trib"), r.num("dead"), r.text("dead_note"),
                r.num("extra", False), r.text("extra_note", False) or "", r.text("occupancy"))
        br = yes(r.text("braced"))
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used(["D", "L"], cb, r.miss)
        r.done()
        return ws_more.stair_stringer_sheet(mark, *args, bool(br), cb, dc, m), "steel_beam", dict(combos=cb)
    if kind == "hss_column":
        m = method(project, r.miss)
        cb = combos(project, r.miss, m)
        ld, mo = r.rows("loads"), r.rows("moments")
        if not ld:
            r.miss.append("No axial load is entered")
        cases_used([x["case"] for x in ld] + [x["case"] for x in mo], cb, r.miss)
        args = (r.text("shape"), r.num("Fy"), r.text("Fy_source"), r.num("height"), r.num("Kx"), r.num("Ky"), r.text("k_source"))
        sw = yes(r.text("self_weight"))
        r.done()
        return ws_more.hss_column_sheet(mark, *args, [dict(case=x["case"], P=x["P"], label=x.get("label") or "") for x in ld],
                                        [dict(case=x["case"], Mx=x.get("Mx"), My=x.get("My"), label=x.get("label") or "") for x in mo], bool(sw), cb, m), "simple", {}
    if kind == "guard":
        m = method(project, r.miss)
        uni = (r.text("uniform") or "") != "exception"
        args = (r.text("rail"), r.num("rail_Fy"), r.text("rail_Fy_source"), r.text("post"), r.num("post_Fy"), r.text("post_Fy_source"), r.num("spacing"), r.num("height"))
        ub = r.text("uniform_basis", not uni) or ""
        stg = r.text("stringer", False) or ""
        sFy, sFs = (r.num("stringer_Fy", True, label="Channel yield stress, Fy"), r.text("stringer_Fy_source", True)) if stg else (None, "")
        r.done()
        return ws_more.guard_sheet(mark, *args, uni, ub, m, stringer=stg or None, stringer_Fy=sFy, stringer_Fy_source=sFs or ""), "simple", {}
    if kind == "rain_load":
        risk, i, i_s, A, ds, ds_s = r.text("risk"), r.num("i"), r.text("i_source"), r.num("A"), r.num("ds"), r.text("ds_source")
        if (r.text("head_type") or "") == "channel scupper":
            head = dict(scupper=r.num("scupper_w", True, label="Channel scupper: width"))
        else:
            head = dict(dh=r.num("dh", True, label="Typed in: hydraulic head"), source=r.text("dh_source", True))
        bay = dp = None
        D, D_s, dp_s = None, "", ""
        if (r.text("pond_type") or "") == "from the bay stiffness":
            D, D_s = r.num("D", True, label="Bay: dead load"), r.text("D_source", True)
            bay = dict(Lp=r.num("Lp", True, label="Bay: primary span"), Ls=r.num("Ls", True, label="Bay: secondary span"),
                       S=r.num("S", True, label="Bay: secondary spacing"), primary=r.text("primary", True), secondary=r.text("secondary", True),
                       Ip=r.num("Ip", True, label="Bay: primary moment of inertia"), Is=r.num("Is", True, label="Bay: secondary moment of inertia"),
                       Ep=r.num("Ep", False), Es=r.num("Es", False))
            for k, nm in (("p", "primary"), ("s", "secondary")):
                if bay[nm] == "other material" and bay["E" + k] is None:
                    r.miss.append(f"Bay: {nm} member E (other material) is blank")
        else:
            dp, dp_s = r.num("dp", True, label="Typed in: ponding head"), r.text("dp_source", True)
        low = None
        if r.num("slope", False) is not None:
            par = bool(yes(r.text("parallel_edge", False)))
            low = dict(slope=r.num("slope", False), parallel_edge=par, Ls=r.num("ls_Ls", False) or (bay or {}).get("Ls"), S=r.num("ls_S", False) or (bay or {}).get("S"))
            if par and (low["Ls"] is None or low["S"] is None):
                r.miss.append("Low slope check: the span and spacing of the secondary members are blank")
        r.done()
        return ws_more.rain_load_sheet(mark, risk, i, i_s, A, ds, ds_s, head, D=D, D_source=D_s or "", bay=bay, dp=dp, dp_source=dp_s or "", low=low), "simple", {}
    if kind == "snow_corner":
        pg, src, W2, w2s, ps, pss = r.num("pg"), r.text("pg_source"), r.num("W2"), r.text("W2_source"), r.num("ps"), r.text("ps_source")
        walls = [dict(name=r.text(k + "_name"), step=r.num(k + "_step"), lu_upper=r.num(k + "_lu_upper"), lu_lower=r.num(k + "_lu_lower")) for k in ("a", "b")]
        r.done()
        return ws_more.snow_corner_sheet(mark, pg, src, W2, w2s, ps, pss, walls), "simple", {}
    if kind == "snow_drift":
        pg, src, W2, w2s = r.num("pg"), r.text("pg_source"), r.num("W2"), r.text("W2_source")
        par = (r.text("at") or "").startswith("a parapet")
        ps, pss, lu2, step = r.num("ps"), r.text("ps_source"), r.num("lu_lower"), r.num("step")
        lu1 = r.num("lu_upper", not par, label="Upper roof length")
        sl = None
        if yes(r.text("slide")) and not par:
            sl = dict(pf=r.num("s_pf", label="Sliding: upper roof pf"), pf_source=r.text("s_pf_source", False) or "",
                      W=r.num("s_W", label="Sliding: eave to ridge W"), rise_on_12=r.num("s_rise", label="Sliding: rise in 12"),
                      slippery=yes(r.text("s_slippery", False)))
            if sl["slippery"] is None:
                r.miss.append("Sliding: slippery upper roof surface is blank")
            if not sl["pf_source"]:
                r.miss.append("Sliding: where pf comes from is blank")
        r.done()
        return ws_more.snow_drift_sheet(mark, pg, src, W2, w2s, ps, pss, lu1, lu2, step, sl, parapet=par, separation=r.num("separation", False)), "simple", {}
    if kind == "snow":
        pg, src, risk = r.num("pg"), r.text("pg_source"), r.text("risk")
        rough, expo, therm = r.text("roughness"), r.text("exposure"), r.text("thermal")
        roof = {"gable or hip": "gable", "monoslope": "monoslope"}.get(r.text("roof"))
        rise, slip, W = r.num("rise"), yes(r.text("slippery")), r.num("W")
        r_roof = r.num("r_roof", therm == snow.HEATED, label="Roof R-value")
        r.done()
        return ws_more.snow_sheet(mark, pg, src, risk, rough, expo, therm, roof, rise, slip, W, r_roof=r_roof,
                                  W2=r.num("W2", False), W2_source=r.text("W2_source", False),
                                  simple_members=yes(r.text("simple", False))), "simple", {}
    if kind == "base_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        shape, N, B, t, Fy, fc = r.text("shape"), r.num("N"), r.num("B"), r.num("t"), r.num("Fy"), r.num("fc")
        full = yes(r.text("full"))
        sup = "full"
        if full is False:
            sup = (r.num("sup_N", label="Support length"), r.num("sup_B", label="Support width"))
        r.done()
        return ws_more.base_plate_sheet(mark, shape, N, B, t, Fy, fc, sup, loads, cb, m), "simple", {}
    if kind == "base_plate_moment":
        m = method(project, r.miss)
        shape, N, B, t, Fy, fc = r.text("shape"), r.num("N"), r.num("B"), r.num("t"), r.num("Fy"), r.num("fc")
        full = yes(r.text("full"))
        sup = "full"
        if full is False:
            sup = (r.num("sup_N", label="Support length"), r.num("sup_B", label="Support width"))
        from .. import anchor_rods as _ar
        _g = _ar.grade(r.text("rod_grade", False) or "")
        if _g:
            _fu, _src = _g[0], _g[3]
        else:
            _fu, _src = r.num("rod_Fu", label="Anchor rod Fu"), r.text("rod_source", False)
            if not _src:
                r.miss.append("Anchor rod grade is blank (or pick other and type Fu and the material)")
        rod = [r.num("rod_d"), _fu, _src, r.num("n_rods"), r.num("rod_edge"),
               r.num("rod_side"), r.num("n_shear")]
        cases = r.rows("cases")
        if not cases:
            r.miss.append("No load case is entered")
        anc, fact = None, None
        if r.num("anc_hef", False) is not None:
            from .. import anchorage as _an
            lab = lambda k: r.labels[k].replace("Anchorage: ", "Anchorage, ")
            pick = lambda k, opts: (opts.index(r.text(k, False)) if r.text(k, False) in opts else
                                    r.miss.append(lab(k) + " is blank"))
            F_, ab = r.num("anc_F", False), r.num("anc_abrg", False)
            tab = _ar.size(rod[0]) if rod[0] else None
            if F_ is not None and ab is not None:
                r.miss.append("Anchorage: give the hex width across flats or the head bearing area, not both")
            nt = r.num("anc_tpi", False)
            if nt is None:
                nt = tab[0] if tab else r.miss.append(lab("anc_tpi") + " is blank (the rod diameter is not in the "
                                                        "Design Guide 1 table)")
            fya = _g[1] if _g else r.num("anc_fy", label=lab("anc_fy"))
            anc = dict(hef=r.num("anc_hef"), ha=r.num("anc_h", label=lab("anc_h")), nt=nt, fya=fya)
            d_ = (0 if _g[2] else 1) if _g else pick("anc_ductile", ["yes", "no"])
            c_, s_, e_, g_ = (pick("anc_cracked", ["cracked", "uncracked"]),
                              pick("anc_supp", ["yes", "no"]),
                              pick("anc_edge", ["none or smaller than No. 4", "No. 4 or larger",
                                                "No. 4 or larger in stirrups at 4 in."]),
                              pick("anc_grout", ["yes", "no"]))
            sdc = r.text("anc_sdc", False)
            if not sdc:
                r.miss.append(lab("anc_sdc") + " is blank")
            if None not in (d_, c_, s_, e_, g_):
                anc.update(ductile=d_ == 0, cracked=c_ == 0, supplementary=s_ == 0, edge_reinf=e_, grout=g_ == 0, sdc=sdc)
            if F_ is not None and rod[0]:
                anc.update(Abrg=_an.hex_bearing_area(F_, rod[0]), head=f"hex head or nut, {F_:g} in across flats")
                if anc["Abrg"] <= 0:
                    r.miss.append("Anchorage: the hex width across flats is not larger than the rod")
            elif ab is not None:
                anc.update(Abrg=ab, head="head bearing area typed in")
            elif tab:
                anc.update(Abrg=tab[1], head="heavy hex nut, AISC Design Guide 1 Table 4-2")
            else:
                r.miss.append("Anchorage: give the hex width across flats or the head bearing area (the rod diameter "
                              "is not in the Design Guide 1 table)")
            fact = r.rows("cases_lrfd")
            if m == "ASD" and not fact:
                r.miss.append("Anchorage: enter the factored (LRFD) load cases; ACI 318-19 Chapter 17 is strength design")
        fw = None
        if r.num("fw_size", False) is not None:
            fw = dict(size=r.num("fw_size", False), FEXX=r.num("fw_FEXX", True, label="Flange weld electrode strength"))
        r.done()
        ss = ws_more.base_plate_moment_sheet(mark, shape, N, B, t, Fy, fc, sup, rod[0], rod[1], rod[2], int(rod[3]),
                                             rod[4], rod[5], int(rod[6]), cases, m, anchorage=anc, cases_factored=fact, flange_weld=fw)
        if r.text("loads_from", False):
            ss.assumptions.insert(0, "Loads: " + r.text("loads_from", False) + ".")
        return ss, "simple", {}
    if kind == "footing_moment":
        a = dict(B_ft=r.num("B"), L_ft=r.num("L"), h_in=r.num("h"), fc=r.num("fc"), fy=r.num("fy"),
                 col_x_in=r.num("col_x"), col_y_in=r.num("col_y"), bar=r.num("bar"), n_x=r.num("n_x"), n_y=r.num("n_y"),
                 cover_in=r.num("cover"), q_allow_psf=r.num("q_allow"), conc_pcf=r.num("conc_pcf"),
                 plate_x_in=r.num("plate_x", False), plate_y_in=r.num("plate_y", False), bottom_layer=r.text("bottom"),
                 soil_depth_ft=r.num("soil_depth", False) or 0.0, soil_pcf=r.num("soil_pcf", False) or 0.0,
                 ot_required=r.num("ot_required", False), slide_mu=r.num("slide_mu", False),
                 slide_required=r.num("slide_required", False))
        src, sup, lim = r.text("soil_source"), r.text("supported"), r.text("limits_source", False)
        a["service"], a["strength"] = r.rows("service"), r.rows("strength")
        if not a["service"]:
            r.miss.append("No service load case is entered")
        if not a["strength"]:
            r.miss.append("No factored load case is entered")
        if a["soil_depth_ft"] and not a["soil_pcf"]:
            r.miss.append("Soil weight is blank (soil over the footing was entered)")
        if (a["slide_mu"] is None) != (a["slide_required"] is None):
            r.miss.append("Sliding needs both the friction coefficient and the required safety factor")
        if any(a[k] is not None for k in ("ot_required", "slide_mu", "slide_required")) and not lim:
            r.miss.append("Source of those limits is blank (a stability limit was entered)")
        r.done()
        for k in ("bar", "n_x", "n_y"):
            a[k] = int(a[k])
        ss = ws_more.footing_moment_sheet(mark, src, sup, lim or "", **a)
        if r.text("loads_from", False):
            ss.assumptions.insert(0, "Loads: " + r.text("loads_from", False) + ".")
        return ss, "simple", {}
    raise WorksheetError(f"unknown worksheet '{kind}'")


def reactions(kind, values, project):
    """Base reactions of a steel column or a frame for every ASD combination (service) and
    every LRFD combination (factored), so a footing or base plate can take them without
    retyping. Each list is the member run with that list of combinations; for a cantilevered
    column or a frame that is a second-order analysis at that load level. Units: lb, lb-ft."""
    if kind not in ("steel_column", "frame"):
        return dict(error="Loads can be taken from a steel column or a moment frame.")
    out = dict(bases=[], service=[], strength=[], messages=[])
    for which, key in (("ASD", "service"), ("LRFD", "strength")):
        try:
            sheet, pk, kw = build(kind, values, dict(project, method=which, _file_method=project.get("method")))
        except Missing as e:
            out["messages"].append(f"{which} combinations: " + "; ".join(e.items))
            continue
        except (WorksheetError, SteelInputError, ValueError, KeyError) as e:
            out["messages"].append(f"{which} combinations: {e}")
            continue
        fac = {c.name: c.factors for c in (kw.get("combos") or getattr(sheet, "combos", []))}
        if pk == "frame":
            best = {}
            for label, per_node in sheet.reactions.items():
                name = label.split(" (")[0]
                for node, (rx, ry, mz) in per_node.items():
                    cur = best.get((name, node))
                    if cur is None or abs(mz) > abs(cur[2]) or (abs(mz) == abs(cur[2]) and abs(rx) > abs(cur[0])):
                        best[(name, node)] = (rx, ry, mz)
            for (name, node), (rx, ry, mz) in best.items():
                out[key].append(dict(base=node, name=name, P=ry * 1000, M=abs(mz) / 12 * 1000, V=abs(rx) * 1000,
                                     wt_factor=fac.get(name, {}).get("D")))
            out["bases"] = sorted({r["base"] for r in out[key]} | set(out["bases"]))
        else:
            for name, b in sheet.base.items():
                if b["Mx"] and b["My"]:
                    out["messages"].append(f"{name}: the column has moment about both axes; a footing with moment "
                                           "about one axis cannot take it")
                ax = "y" if b["My"] > b["Mx"] else "x"
                out[key].append(dict(base="base", name=name, P=b["P"] * 1000, M=b["M" + ax] * 1000,
                                     V=max(b["Vx"], b["Vy"]) * 1000, wt_factor=fac.get(name, {}).get("D")))
            out["bases"] = ["base"]
    return out


def job_of(project):
    return dict(name=(project.get("name") or "").strip(), number=(project.get("number") or "").strip(),
                address=(project.get("address") or "").strip())


def _row(r):
    return dict(check=r.check, combo=r.combo, demand=r.demand, capacity=r.capacity, unit=r.unit,
                dc=r.dc, status=r.status, source=r.source, note=r.note)


def results(kind, values, project):
    """What the screen shows for one member. Never raises: problems come back as messages."""
    try:
        sheet, pk, kw = build(kind, values, project)
    except Missing as e:
        return dict(state="incomplete", messages=e.items)
    except (WorksheetError, SteelInputError, FootingInputError, ValueError, KeyError) as e:
        return dict(state="stopped", messages=[str(e).strip("'").strip('"')])
    out = dict(state="done", rows=[], members=[], steps=[], assumptions=[], not_checked=[])
    if pk == "frame":
        out["members"] = [dict(member=m["member"], shape=m["shape"], combo=m["combo"] + (" *" if m["label"] else ""),
                               axial=m["Pr"], sense="C" if m["axial"] == "compression" else "T", moment=m["Mr"],
                               shear=m["Vr"], ratio=m["ratio"], status=m["status"]) for m in sheet.member_rows]
        out["rows"] = [_row(r) for r in sheet.rows]
        out["governing"] = sheet.governing
        lay = sheet.lay
        out["frame"] = dict(nodes=lay.nodes, supports=lay.supports,
                            members=[dict(name=m.name, i=m.i, j=m.j, role=m.role) for m in lay.members])
    else:
        out["rows"] = [_row(r) for r in sheet.rows]
    steps = getattr(sheet, "steps", None) or []
    out["steps"] = [dict(label=s.label, value=s.value, unit=s.unit, source=s.source, note=s.note) for s in steps]
    out["tables"] = [dict(title=b["title"], lines=list(b["lines"]), after=list(b.get("after") or []))
                     for b in (getattr(sheet, "blocks", None) or []) if b.get("lines")]
    out["assumptions"] = list(getattr(sheet, "assumptions", None) or [])
    res = getattr(sheet, "result", None)
    if res is not None:
        out["assumptions"] += list(res.notes)
        out["not_checked"] = list(res.not_checked)
    else:
        out["not_checked"] = list(getattr(sheet, "not_checked", None) or [])
    ok = all(r["status"] == "OK" for r in out["rows"]) and all(m["status"] == "OK" for m in out["members"])
    out["status"] = "OK" if ok else "FLAG"
    return out


def sheet_pdf(kind, values, project, path):
    sheet, pk, kw = build(kind, values, project)
    fn = {"steel_beam": calcsheet.steel_beam_pdf, "steel_column": calcsheet.steel_column_pdf,
          "footing": calcsheet.footing_pdf, "frame": calcsheet.frame_pdf, "conn": calcsheet.conn_pdf,
          "simple": calcsheet.simple_pdf}[pk]
    fn(sheet, path, job_of(project), getattr(sheet, "code", None) or FORMS[kind]["code"], project.get("date") or "", **kw)
    return path


def package_pdf(project, members, path, cover=True):
    """Every member that calculates, in the order listed, behind a cover sheet.
    Returns (sheets, skipped marks)."""
    items, skipped, contents, flag_lines, codes = [], [], [], [], []
    for m in members:
        try:
            sheet, pk, kw = build(m["kind"], m["values"], project)
        except Exception:
            skipped.append((m["values"].get("mark") or "(no mark)"))
            continue
        code = getattr(sheet, "code", None) or FORMS[m["kind"]]["code"]
        items.append((pk, sheet, code, kw))
        if code not in codes:
            codes.append(code)
        mark = m["values"].get("mark")
        flags = 0
        for r in getattr(sheet, "rows", []):
            if r.status == "FLAG":
                flags += 1
                flag_lines.append(f"{mark}: {r.check}, D/C {r.dc:.2f} ({r.combo})")
        for r in getattr(sheet, "member_rows", []):
            if r["status"] == "FLAG":
                flags += 1
                flag_lines.append(f"{mark}: member {r['member']} ({r['shape']}), ratio {r['ratio']:.2f} ({r['combo']})")
        contents.append(dict(mark=mark, title=FORMS[m["kind"]]["title"], code=code, flags=flags))
    if not items:
        raise WorksheetError("no member is complete yet, so there is nothing to print")
    cov = None
    if cover:
        def lst(key):
            return [(c["expr"].strip(), (c.get("source") or "").strip()) for c in project.get(key) or []
                    if (c.get("expr") or "").strip()]
        asd, lrfd = lst("combos_asd"), lst("combos_lrfd")
        if not asd and not lrfd and project.get("combos"):
            (asd if project.get("method") == "ASD" else lrfd).extend(lst("combos"))
        names = {"AISC 360-22": "ANSI/AISC 360-22, Specification for Structural Steel Buildings",
                 "ACI 318-19": "ACI 318-19, Building Code Requirements for Structural Concrete"}
        basis = [names.get(c, c) for c in codes]
        if "AISC 360-22" in codes:
            basis.append(f"Steel is designed by {project.get('method')}. Section properties are from the AISC Shapes "
                         "Database v16.0.")
        basis.append("Load combinations are entered by the engineer with their source and are listed below. "
                     "Loads on each member are entered by the engineer; each sheet lists them.")
        basis.append("Each sheet states its own assumptions and what it does not check.")
        cov = dict(basis=basis, asd=asd, lrfd=lrfd, contents=contents, flag_lines=flag_lines, skipped=skipped)
    n = calcsheet.package_pdf(items, path, job_of(project), project.get("date") or "", cover=cov)
    return n, skipped
