"""Worksheet screens: the forms, and the bridge from what is typed to the calculations.

Each worksheet kind has a form description (fields and tables) that the screen draws,
and a function that turns the typed values into the same worksheet objects the tests
exercise. Nothing typed is defaulted here: a blank required box comes back as a message
naming the box, and all such messages come back together.
"""
import math
import re

from .. import calcsheet, glulam, ijoist, scl, shapes, shearwall, snow, wood, ws_conn, ws_footing, ws_frame, ws_more, ws_steel_beam, ws_steel_column, ws_wood
from .. import holddowns
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
        fields=[F("shape", "Section", "shape_any", help="W, M, S or HP shape, C or MC channel, square, rectangular or round HSS, or pipe"), F("Fy", "Fy", unit="ksi"),
                F("support_type", "Supports", "select", options=["bearing supports (spans)", "one support, fixed (cantilevers each side of a column)"], required=False,
                  help="blank = bearing supports; for a beam fixed to one column, leave Span blank and give the cantilever lengths in the two overhang boxes"),
                F("span", "Span", unit="ft", required=False),
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
                                     F("dir", "Direction", "select", options=["down (x axis)", "sideways (y axis)"], required=False,
                                       help="blank = down; sideways loads bend the beam about its weak axis (single simple span)"),
                                     F("e", "Off the shear center by", unit="in", required=False,
                                       help="HSS and pipe, single simple span: the load twists the beam by load x this distance; both ends held against twisting"),
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
                F("occupancy", "Live load", "select", options=["stairs and exit ways", "one- and two-family dwellings", "other (type the load)"], help="100 psf or 40 psf, ASCE 7-22 Table 4.3-1"),
                F("live_psf", "Other: uniform live load", unit="psf", required=False),
                F("live_P", "Other: concentrated live load on the stringer", unit="lb", required=False, help="optional; anywhere on the stringer, not with the uniform load"),
                F("live_source", "Other: where those loads come from", "text", required=False),
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
    "angle_strut": dict(
        title="Single-Angle Compression Member (brace or kicker)", code="AISC 360-22", mark="AS",
        fields=[F("shape", "Angle", "shape_tension", help="single angle by its Manual label, for example L3x3x1/4"),
                F("Fy", "Fy", unit="ksi"), F("steel_source", "Where Fy comes from", "text", help="for example: ASTM A36"),
                F("length", "Length between the end connections", unit="ft"),
                F("attached", "Attached leg", "select", options=["long", "short"], required=False, help="unequal-leg angles; either for an equal-leg angle")],
        tables=[T("loads", "Axial compression", [CASE, F("P", "Compression", unit="kip"), F("label", "Note", "text", required=False)])]),
    "shear_lug": dict(
        title="Shear Lug (under a column base plate)", code="AISC 360-22, ACI 318-19", mark="SL",
        fields=[F("bsl", "Lug width (across the shear)", unit="in"), F("tsl", "Lug thickness", unit="in"),
                F("hsl", "Lug embedment into the concrete (below the grout)", unit="in"), F("t_grout", "Grout thickness", unit="in"),
                F("lug_Fy", "Lug Fy", unit="ksi"), F("lug_Fu", "Lug Fu", unit="ksi"), F("lug_source", "Where the lug's Fy and Fu come from", "text"),
                F("weld", "Fillet weld, each face of the lug", unit="in"), F("FEXX", "Electrode strength FEXX", unit="ksi"),
                F("N", "Base plate length N (along the shear)", unit="in"), F("B", "Base plate width B", unit="in"), F("tbp", "Base plate thickness", unit="in"),
                F("bp_Fy", "Base plate Fy", unit="ksi"),
                F("s_rod", "Anchor rod square, side", unit="in", help="four rods, the lug centred between them"), F("rod_d", "Anchor rod diameter", unit="in"),
                F("rod_Fu", "Anchor rod Fu", unit="ksi"), F("rod_source", "Where the rod Fu comes from", "text", help="for example: ASTM F1554 Grade 36"),
                F("hef_rod", "Anchor rod embedment", unit="in", required=False),
                F("fc", "Concrete f'c", unit="psi"), F("A2A1", "Concrete bearing area ratio A2 / A1 (1 to 4)"),
                F("ca1", "Lug face to the concrete edge, in the direction of the shear", unit="in"),
                F("ca2", "Lug side to the side edges of the concrete", unit="in"), F("ha", "Concrete member depth", unit="in"),
                F("psi_c", "Concrete cracking (psi_c,V)", "select", options=["cracked, no supplementary reinforcement (1.0)", "cracked, No. 4 or larger edge bar (1.2)",
                                                                          "cracked, edge bar and stirrups at 4 in. or less (1.4)", "uncracked at service loads (1.4)"],
                  help="ACI 318-19 17.7.2.5.1")],
        tables=[T("loads", "Base shear and axial load", [CASE, F("V", "Shear", unit="kip"), F("P", "Axial compression (+)", unit="kip", required=False),
                                                         F("label", "Note", "text", required=False)])]),
    "crane_runway": dict(
        title="Crane Runway Beam (top-running crane)", code="AISC 360-22", mark="CR",
        fields=[F("beam", "Runway beam", "shape", help="W, M, S or HP shape"), F("Fy", "Fy", unit="ksi"), F("beam_source", "Where Fy comes from", "text"),
                F("span", "Span, simply supported", unit="ft"),
                F("rail", "Rail weight", unit="plf", required=False), F("rail_note", "Rail", "text", required=False, help="for example: ASCE 40 lb rail"),
                F("crane_type", "Crane type (vertical impact)", "select", options=["bridge crane, service class A, B or C", "bridge crane, service class D, E or F",
                                                                                  "monorail crane (powered)", "hand-geared bridge, trolley and hoist"],
                  help="ASCE/SEI 7-22 Sect. 4.9.3 and 4.9.3.1"),
                F("class_basis", "How the service class or type was assigned", "text"),
                F("capacity", "Rated capacity", unit="kip"), F("trolley", "Weight of the hoist and trolley", unit="kip"),
                F("wheel", "Maximum static wheel load", unit="kip", help="crane maker's data: bridge weight plus rated capacity plus trolley (Sect. 4.9.2)"),
                F("wheel_source", "Where the wheel load comes from", "text"),
                F("n", "Wheels on this runway (one end truck)", "select", options=["1", "2", "3", "4"]), F("spacing", "Wheel spacing", unit="ft", required=False),
                F("powered", "Electrically powered trolley", "select", options=["yes", "no"], help="lateral force of Sect. 4.9.4 applies when yes"),
                F("share", "Share of the lateral force taken by this runway", help="for example 0.5 for two equal runway beams; Sect. 4.9.4"),
                F("share_source", "Basis of that share", "text"),
                F("defl_v", "Vertical deflection limit, span over", required=False), F("defl_h", "Lateral deflection limit, span over", required=False),
                F("defl_source", "Where the deflection limits come from", "text", required=False)],
        tables=[]),
    "angle_beam": dict(
        title="Single-Angle Beam", code="AISC 360-22", mark="LB",
        fields=[F("shape", "Angle", "shape_tension", help="single angle by its Manual label, for example L4x4x1/4"),
                F("Fy", "Fy", unit="ksi"), F("steel_source", "Where Fy comes from", "text", help="for example: ASTM A36"),
                F("span", "Span, simply supported", unit="ft"),
                F("vertical", "Vertical leg", "select", options=["long", "short"], required=False, help="unequal-leg angles; either for an equal-leg angle"),
                F("toe", "Toe of the vertical leg", "select", options=["up", "down"]),
                F("restraint", "Lateral-torsional restraint", "select", options=["none between the ends", "at midspan only", "continuous along the length"],
                  help="continuous: for example a deck or sheathing fastened along the angle"),
                F("self_weight", "Add the angle's own weight as dead load", "select", options=["yes", "no"])],
        tables=[T("loads", "Loads", [CASE, F("kind", "Load", "select", options=["uniform, full span", "point"]), F("value", "Value (kip/ft or kip)"),
                                     F("x", "Point load at, from the left support", unit="ft", required=False),
                                     F("dir", "Direction", "select", options=["down", "sideways"], help="sideways: horizontal, positive from the toe of the horizontal leg toward the heel"),
                                     F("label", "Note", "text", required=False)])]),
    "tension_member": dict(
        title="Steel Tension Member", code="AISC 360-22", mark="TM",
        fields=[F("shape", "Section", "shape_tension", required=False, help="W, M, S, HP, C, MC, HSS, pipe or single angle (for example L3x3x3/16); blank for a threaded rod"),
                F("rod_d", "Threaded rod diameter, in place of a section", unit="in", required=False), F("Fy", "Fy", unit="ksi"), F("Fu", "Fu", unit="ksi"),
                F("steel_source", "Where Fy and Fu come from", "text", help="for example: ASTM A992"), F("length", "Length", unit="ft"),
                F("n_holes", "Bolt holes across the critical section", required=False, help="blank or 0 for a welded end"),
                F("bolt_d", "Bolt diameter", unit="in", required=False), F("hole_t", "Thickness of the part the holes are in", unit="in", required=False),
                F("U", "Shear lag factor, U", required=False, help="AISC 360-22 Table D3.1; leave blank for a single angle and fill the three angle boxes"),
                F("U_source", "Which case of Table D3.1", "text", required=False, help="for example: Case 2, 1 - x/l, x = 0.831 in., l = 9 in."),
                F("angle_n", "Single angle: bolts in the line", required=False), F("angle_l", "Single angle: length of the connection", unit="in", required=False, help="first to last bolt"),
                F("angle_leg", "Single angle: connected leg", "select", options=["long", "short"], required=False)],
        tables=[T("loads", "Axial tension", [CASE, F("P", "Tension", unit="kip"), F("label", "Note", "text", required=False)])]),
    "hss_column": dict(
        title="HSS or Pipe Column", code="AISC 360-22", mark="HC",
        fields=[F("shape", "Section", "hss_shape", help="square, rectangular or round HSS, or pipe, by its Manual label: HSS6x6x1/4, HSS8x4x3/16, HSS5.563x0.258, Pipe 4 STD"),
                F("Fy", "Fy", unit="ksi"), F("Fy_source", "Where Fy comes from", "text", help="for example: ASTM A500 Grade C"),
                F("height", "Height", unit="ft"), F("Kx", "Kx"), F("Ky", "Ky"), F("k_source", "K comes from", "text"),
                F("self_weight", "Add self-weight", "select", options=["yes", "no"]),
                F("end_ratio", "End moments: smaller over larger, M1 / M2", required=False,
                  help="blank: Cm = 1.0. 0 for a moment at one end only, 1 for equal moments in reverse curvature, -1 in single curvature (AISC 360-22 Eq. A-8-4)")],
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
    "seat": dict(
        title="Unstiffened Seated Connection (seat angle)", code="AISC 360-22", mark="SE",
        fields=[F("beam", "Beam", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_source", "Source of the beam Fy", "text"),
                F("t", "Seat angle thickness", unit="in"), F("length", "Seat angle length", unit="in"), F("osl", "Outstanding (horizontal) leg", unit="in"),
                F("vleg", "Vertical leg", unit="in"), F("angle_Fy", "Angle Fy", unit="ksi"), F("angle_source", "Source of the angle Fy", "text"),
                F("attach", "Seat to the support", "select", options=["welded", "bolted"]),
                F("weld", "Welded: fillet size at each end of the angle", unit="in", required=False), F("FEXX", "Welded: electrode strength", unit="ksi", required=False),
                F("n_bolts", "Bolted: number of bolts", required=False), F("d", "Bolted: bolt diameter", unit="in", required=False),
                F("group", "Bolted: bolt type", "select", options=["A325", "A490", "F3148"], required=False),
                F("threads", "Bolted: threads", "select", options=["N", "X"], required=False)],
        tables=[T("loads", "Beam end reaction", [CASE, F("P", "Reaction", unit="kip"), F("label", "Note", "text", required=False)])]),
    "base_plate_biaxial": dict(
        title="Column Base Plate, Biaxial Bending (four rods)", code="AISC 360-22", mark="BPX",
        fields=[F("shape", "Column", "shape_col", help="W shape, or square or rectangular HSS"), F("N", "Plate length (along the column depth)", unit="in"), F("B", "Plate width", unit="in"),
                F("t", "Plate thickness", unit="in"), F("Fy", "Plate Fy", unit="ksi"), F("fc", "Concrete f'c", unit="psi"),
                F("area_ratio", "Support area over plate area, A2 / A1", help="1 where the plate covers the whole support; not over 4 counts"),
                F("rod_d", "Anchor rod diameter", unit="in", help="four rods, one near each corner"),
                F("rod_grade", "Anchor rod grade", "select", required=False, options=["F1554 Gr. 36", "F1554 Gr. 55", "F1554 Gr. 105", "other"]),
                F("rod_Fu", "Anchor rod Fu (grade: other)", unit="ksi", required=False), F("rod_source", "Anchor rod material (grade: other)", "text", required=False),
                F("rod_edge", "Rods from the plate ends", unit="in"), F("rod_side", "Rods from the plate sides", unit="in"),
                F("loads_from", "Loads come from", "text", required=False)],
        tables=[T("cases", "Combined loads", [F("name", "Combination or run", "text"), F("P", "Axial compression", unit="kip"), F("Mx", "Moment, column strong axis", unit="kip-ft"),
                                              F("My", "Moment, column weak axis", unit="kip-ft")])]),
    "flush_end_plate": dict(
        title="End-Plate Moment Connection (flush, or four-bolt extended)", code="AISC 360-22", mark="FEP",
        fields=[F("beam", "Beam", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_Fu", "Beam Fu", unit="ksi"),
                F("config", "End plate", "select", options=["flush", "extended, four bolts (two outside and two inside the tension flange; beam side only)"], required=False, help="blank = flush"),
                F("pfo", "Extended: outside of the tension flange to the outer bolts, pfo", unit="in", required=False),
                F("n_shear", "Bolts at the compression flange counted for shear", required=False, help="blank = 2"),
                F("n_rows", "Flush: rows of tension bolts (two bolts a row)", "select", options=["1", "2"], required=False, help="blank = 1"),
                F("pb", "Spacing between the two rows, pb", unit="in", required=False),
                F("col_side", "Checks on the support", "select", options=["column flange with a cap plate (two-bolt only)", "beam side only"], required=False,
                  help="blank = column flange with a cap plate"),
                F("column", "Column (the beam frames to its flange at the column top)", "shape", required=False), F("col_Fy", "Column Fy", unit="ksi", required=False),
                F("col_Fu", "Column Fu", unit="ksi", required=False),
                F("steel_source", "Source of the beam and column steel", "text"),
                F("bp", "End plate width", unit="in"), F("tp", "End plate thickness", unit="in"), F("plate_Fy", "Plate Fy", unit="ksi"), F("plate_Fu", "Plate Fu", unit="ksi"),
                F("plate_source", "Source of the plate Fy and Fu", "text"),
                F("d", "Bolt diameter", unit="in", help="two bolts inside the tension flange, two inside the compression flange"),
                F("group", "Bolt type", "select", options=["A325", "A490", "F3148"]), F("threads", "Threads", "select", options=["N", "X"]),
                F("g", "Gage", unit="in"), F("pfi", "Inside of the tension flange to the bolts, pfi", unit="in"),
                F("w_flange", "Flange fillet weld, both sides", unit="in"), F("w_web", "Web fillet weld, both sides", unit="in"),
                F("below", "End plate past the compression flange weld", unit="in", help="from the outside of the flange weld to the end of the plate"),
                F("tcap", "Column cap plate thickness", unit="in", required=False), F("bcp", "Column cap plate width", unit="in", required=False),
                F("w_cap_flange", "Cap plate to column flange fillet (one side)", unit="in", required=False), F("w_cap_web", "Cap plate to column web fillets (both sides)", unit="in", required=False),
                F("FEXX", "Electrode strength", unit="ksi")],
        tables=[T("loads", "Loads at the connection", [CASE, F("M", "Moment", unit="kip-ft"), F("T", "Beam axial tension", unit="kip", required=False), F("V", "Shear", unit="kip", required=False),
                                                       F("label", "Note", "text", required=False)]),
                T("runs", "Or: combined loads (for example from the 3D frame), used in place of the table above", [F("name", "Combination or run", "text"), F("M", "Moment", unit="kip-ft"),
                                                                                                                     F("T", "Beam axial tension", unit="kip", required=False), F("V", "Shear", unit="kip", required=False)])]),
    "cap_plate": dict(
        title="Beam over HSS Column, Cap Plate Moment Connection", code="AISC 360-22", mark="CP",
        fields=[F("beam", "Beam (continuous over the column)", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_Fu", "Beam Fu", unit="ksi"), F("beam_source", "Source of the beam Fy and Fu", "text"),
                F("column", "Column (square HSS)", "hss_shape"), F("col_Fy", "Column Fy", unit="ksi"), F("col_source", "Source of the column Fy", "text"),
                F("tp", "Cap plate thickness", unit="in"), F("bp", "Cap plate width across the beam", unit="in"),
                F("plate_Fy", "Plate Fy", unit="ksi"), F("plate_Fu", "Plate Fu", unit="ksi"), F("plate_source", "Source of the plate Fy and Fu", "text"),
                F("d", "Bolt diameter", unit="in", help="four bolts, two each side of the column"), F("group", "Bolt type", "select", options=["A325", "A490", "F3148"]),
                F("s", "Bolt spacing along the beam", unit="in", help="the bolts sit outside the HSS walls"), F("g", "Gage across the beam flange", unit="in"),
                F("weld", "Fillet weld, cap plate to the HSS", unit="in"), F("FEXX", "Electrode strength", unit="ksi")],
        tables=[T("loads", "Loads at the joint", [CASE, F("P", "Column compression", unit="kip"), F("M", "Moment across the joint", unit="kip-ft"), F("label", "Note", "text", required=False)]),
                T("runs", "Or: combined loads (for example from the 3D frame), used in place of the table above", [F("name", "Combination or run", "text"), F("P", "Column compression", unit="kip"), F("M", "Moment across the joint", unit="kip-ft")])]),
    "stiffened_seat": dict(
        title="Stiffened Seated Connection (welded to the support, bolted to the beam)", code="AISC 360-22", mark="SS",
        fields=[F("beam", "Beam", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_source", "Source of the beam Fy", "text"),
                F("W", "Stiffener width W (along the beam)", unit="in"), F("L", "Stiffener length L (down the support)", unit="in"),
                F("ts", "Stiffener thickness", unit="in"), F("stiff_Fy", "Stiffener Fy", unit="ksi"), F("stiff_source", "Source of the stiffener Fy", "text"),
                F("tseat", "Seat plate thickness", unit="in"), F("weld", "Fillet weld size to the support", unit="in"), F("FEXX", "Electrode strength", unit="ksi"),
                F("support", "Support (member and part)", "text", help="for example W14x90 flange"), F("t_sup", "Support thickness", unit="in"),
                F("Fu_sup", "Support Fu", unit="ksi"),
                F("both_sides", "Seats welded on both faces of the support (a column web)", "select", options=["no", "yes"], required=False)],
        tables=[T("loads", "End reaction", [CASE, F("P", "R", unit="kip"), F("label", "Note", "text", required=False)]),
                T("runs", "Or: combined reactions, used in place of the table above", [F("name", "Combination or run", "text"), F("R", "R", unit="kip")])]),
    "beam_hss_moment": dict(
        title="Beam to HSS Column Moment Connection (flanges or flange plates welded to the face)", code="AISC 360-22", mark="BHM",
        fields=[F("beam", "Beam", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_source", "Source of the beam Fy", "text"),
                F("column", "Column (square or rectangular HSS)", "hss_shape"), F("col_Fy", "Column Fy", unit="ksi"), F("col_source", "Source of the column Fy", "text"),
                F("face", "HSS face the beam frames into", "select", options=["B", "H"], required=False, help="for a rectangular HSS: B is the face named second in the size (HSS10x6: the 6 in. face), H the first; blank = B"),
                F("flanges", "Flange connection", "select", options=["beam flanges welded directly to the face", "flange plates welded to the face"]),
                F("bp", "Flange plate width", unit="in", required=False), F("tp", "Flange plate thickness", unit="in", required=False),
                F("plate_Fy", "Flange plate Fy", unit="ksi", required=False), F("plate_source", "Source of the flange plate Fy", "text", required=False),
                F("plate_Fu", "Flange plate Fu", unit="ksi", required=False), F("beam_Fu", "Beam Fu", unit="ksi", required=False),
                F("fd", "Flange plate bolts: diameter", unit="in", required=False, help="blank = the flange plate's connection to the beam flange is not checked"),
                F("fgroup", "Flange plate bolts: type", "select", options=["A325", "A490", "F3148"], required=False),
                F("fthreads", "Flange plate bolts: threads", "select", options=["N", "X"], required=False, help="N = in the shear plane, X = excluded"),
                F("fn", "Bolts in each of the two rows", required=False), F("fs", "Bolt spacing along the beam", unit="in", required=False),
                F("fg", "Gage between the two rows", unit="in", required=False), F("flev_p", "Plate end to the last bolt", unit="in", required=False),
                F("flev_b", "Beam end to the first bolt", unit="in", required=False), F("fa1", "Column face to the first bolt", unit="in", required=False),
                F("fweld", "Fillet weld, flange plate to the HSS face (each side of the plate)", unit="in", required=False),
                F("fFEXX", "Electrode strength", unit="ksi", required=False)],
        tables=[T("loads", "Loads at the joint", [CASE, F("M", "Beam end moment", unit="kip-ft"), F("P", "Column axial load at the joint", unit="kip", required=False),
                                                  F("Mc", "Column moment at the joint", unit="kip-ft", required=False), F("label", "Note", "text", required=False)]),
                T("runs", "Or: combined loads (for example from the 3D frame), used in place of the table above",
                  [F("name", "Combination or run", "text"), F("M", "Beam end moment", unit="kip-ft"), F("P", "Column axial load", unit="kip", required=False), F("Mc", "Column moment", unit="kip-ft", required=False)])]),
    "end_plate": dict(
        title="Shear End-Plate Connection", code="AISC 360-22", mark="EP",
        fields=[F("beam", "Beam", "shape"), F("beam_Fy", "Beam Fy", unit="ksi"), F("beam_Fu", "Beam Fu", unit="ksi"), F("beam_source", "Source of the beam Fy and Fu", "text"),
                F("tp", "Plate thickness", unit="in"), F("width", "Plate width", unit="in"), F("length", "Plate length", unit="in"),
                F("plate_Fy", "Plate Fy", unit="ksi"), F("plate_Fu", "Plate Fu", unit="ksi"), F("plate_source", "Source of the plate Fy and Fu", "text"),
                F("d", "Bolt diameter", unit="in"), F("group", "Bolt type", "select", options=["A325", "A490", "F3148"]),
                F("threads", "Threads", "select", options=["N", "X"], help="N = in the shear plane, X = excluded"),
                F("n", "Bolts in each vertical row", help="two vertical rows; 2 to 12 per row"), F("spacing", "Bolt spacing", unit="in"),
                F("lev", "Top of the plate to the first bolts", unit="in"), F("gage", "Gage between the two rows", unit="in"),
                F("weld", "Fillet weld size, each side of the web", unit="in"), F("FEXX", "Electrode strength", unit="ksi"),
                F("support_name", "Support: what the plate bolts to", "text", required=False, help="blank = the support is by others and bearing on it is not checked"),
                F("support_t", "Support: thickness at the bolts", unit="in", required=False), F("support_Fu", "Support: Fu", unit="ksi", required=False)],
        tables=[T("loads", "Beam end reaction", [CASE, F("P", "Reaction", unit="kip"), F("label", "Note", "text", required=False)])]),
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
                F("n", "Number of bolts", help="one vertical row, 2 to 12"), F("spacing", "Bolt spacing", unit="in"),
                F("lev", "Vertical edge distance", unit="in", help="bolt centre to the top and bottom of the plate"),
                F("leh", "Horizontal edge distance", unit="in", help="bolt centre to the free end of the plate"),
                F("a", "Weld line to bolt line, a", unit="in", help="3-1/2 in. or less"),
                F("holes", "Holes in the plate", "select", options=["STD", "SSLT"], help="SSLT = horizontal short slots"),
                F("weld", "Fillet weld size, each side", unit="in"), F("FEXX", "Electrode strength", unit="ksi"),
                F("through", "Through plate: column dimension the plate passes through", unit="in", required=False,
                  help="blank = the plate is welded to the face of the column wall; for a through plate, the outside dimension of the HSS along the plate"),
                F("cope_dc", "Coped beam: cope depth at the top flange", unit="in", required=False, help="blank with the next box blank = the beam is not coped; then the next five boxes are not used"),
                F("cope_dcb", "Coped beam: cope depth at the bottom flange", unit="in", required=False, help="blank = top flange only; top blank = bottom flange only; both copes the same length"),
                F("cope_c", "Coped beam: cope length", unit="in", required=False),
                F("cope_setback", "Coped beam: setback of the beam end from the support", unit="in", required=False, help="usually 1/2 in."),
                F("cope_lev", "Coped beam: cut edge to the nearest bolt", unit="in", required=False, help="from the top cut; for a cope at the bottom flange only, from the bottom cut"),
                F("cope_leh", "Coped beam: bolt line to the beam end", unit="in", required=False),
                F("beam_Fy", "Coped beam: beam Fy", unit="ksi", required=False)],
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
                F("hd_model", "Hold-down", "select", options=holddowns.MODELS, required=False, help="Simpson Strong-Tie catalog C-C-2026; blank = hold-down not checked"),
                F("hd_stem", "Strap tie: stem wall width", "select", options=["6", "8"], unit="in", required=False, help="LSTHD and STHD only; slab on grade and brick ledge: 8"),
                F("hd_position", "Strap tie: position on the wall", "select", options=holddowns.POSITIONS, required=False),
                F("hd_cracked", "Strap tie: concrete", "select", options=["cracked", "uncracked"], required=False),
                F("hd_sdc", "Strap tie, seismic: Seismic Design Category", "select", options=["A or B", "C to F"], required=False),
                F("above_T", "Stacked walls: chord force from the wall above", unit="lb", required=False,
                  help="the hold-down tension (and post compression) the wall above brings down to this wall's end posts; blank = no wall above"),
                F("above_source", "Stacked walls: where that force comes from", "text", required=False, help="for example: shear wall SW3, main level"),
                F("chord_A", "Deflection: end post area", unit="in2", required=False),
                F("chord_E", "Deflection: end post E", unit="psi", required=False),
                F("slip", "Deflection: anchorage slip at the design load", unit="in", required=False)],
        tables=[]),
    "ftao_wall": dict(
        title="Wood Shear Wall, Force Transfer Around Openings", code="SDPWS-2021", mark="FT",
        fields=[F("panel", "Sheathing and nails", "select", options=list(shearwall.PANELS), help="SDPWS Table 4.3A; blocked"),
                F("spacing", "Edge nail spacing", "select", options=["6", "4", "3", "2"], unit="in"),
                F("panel_type", "Panel", "select", options=["OSB", "plywood"]),
                F("sides", "Panels on", "select", options=["one side", "both sides (same panels and nailing)"]),
                F("G", "Framing specific gravity, G", help="0.50 for Douglas Fir-Larch; NDS Table 12.3.3A"), F("G_source", "Where G comes from", "text"),
                F("h", "Wall height", unit="ft"), F("L1", "Pier at the left of the opening", unit="ft", help="2 ft minimum"),
                F("Lo", "Opening width", unit="ft"), F("L2", "Pier at the right of the opening", unit="ft", help="2 ft minimum"),
                F("ho", "Opening clear height", unit="ft"), F("sill", "Sheathing height below the opening", unit="ft", required=False, help="blank or 0 for a door"),
                F("load", "Load", "select", options=["wind", "seismic"]), F("V", "Design shear on the wall", unit="lb", help="at the project's design method (ASD or LRFD)"),
                F("v_source", "Where the shear comes from", "text"),
                F("holddown", "10d nails: hold-down on the inside face of the end post", "select", options=["yes", "no"], required=False, help="Table 4.3A note 10"),
                F("hd_model", "Hold-down", "select", options=holddowns.MODELS, required=False, help="Simpson Strong-Tie catalog C-C-2026; blank = hold-down not checked"),
                F("hd_stem", "Strap tie: stem wall width", "select", options=["6", "8"], unit="in", required=False),
                F("hd_position", "Strap tie: position on the wall", "select", options=holddowns.POSITIONS, required=False),
                F("hd_cracked", "Strap tie: concrete", "select", options=["cracked", "uncracked"], required=False),
                F("hd_sdc", "Strap tie, seismic: Seismic Design Category", "select", options=["A or B", "C to F"], required=False),
                F("above_T", "Stacked walls: chord force from the wall above", unit="lb", required=False),
                F("above_source", "Stacked walls: where that force comes from", "text", required=False)],
        tables=[T("more", "More openings, left to right after the first (the pier at the right of the first opening is then the pier between openings 1 and 2)",
                  [F("w", "Opening width", unit="ft"), F("ho", "Opening clear height", unit="ft"), F("sill", "Sheathing height below (0 for a door)", unit="ft", required=False),
                   F("pier", "Pier at its right", unit="ft")],
                  help="APA Technical Note T555 method for several openings; leave empty for one opening")]),
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
                F("elevation_source", "Where the elevation comes from", "text", required=False),
                F("fascia", "Fascia depth at the roof edges (rafter + purlin + panel)", unit="ft", required=False,
                  help="for the wind on the roof edge when this sheet's cases are put on the building model's frame; blank = none"),
                F("model_axis", "Building model: roof dimension L runs along", "select", options=["X", "Y"], required=False,
                  help="fill to put this sheet's wind cases on the placed frame when it is run free to sway"),
                F("model_low", "Building model: the low eave of a monoslope roof is at the", "select", options=["smaller coordinate", "larger coordinate"], required=False)],
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
        fixed = str(values.get("support_type") or "").lower().startswith("one support")
        shape, Fy, span = r.text("shape"), r.num("Fy"), (None if fixed else r.num("span", False))
        if not fixed and span is None:
            r.miss.append("Span is blank")
        br, sw = r.text("bracing"), yes(r.text("self_weight"))
        pts = []
        if br == "at points":
            pts = ((r.nums("brace_pts") or []) if r.text("brace_pts", False) else []) if fixed else (r.nums("brace_pts") or [])
        loads = []
        more = (r.nums("more_spans") or []) if (r.text("more_spans", False) and not fixed) else []
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
            if str(ld.get("dir") or "").startswith("side"):
                d["dir"] = "sideways"
            if ld.get("e"):
                d["e_in"] = abs(ld["e"])
            loads.append(d)
        if not loads and sw is False:
            r.miss.append("No loads are entered")
        dc = checks(r.rows("defl"), r.miss, "Deflection limits")
        cases_used([ld["case"] for ld in loads], cb, r.miss)
        r.done()
        s = ws_steel_beam.run(mark, shape, Fy, span, loads, cb, dc, "continuous" if br == "continuous" else pts, m, sw,
                              spans=[span] + more if more else None, overhang_left=r.num("oh_left", False) or 0.0, overhang_right=r.num("oh_right", False) or 0.0, fixed=fixed)
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
    if kind == "angle_strut":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        args = (r.text("shape"), r.num("Fy"), r.text("steel_source"), r.num("length"), r.text("attached", False) or "")
        r.done()
        return ws_more.angle_strut_sheet(mark, *args, loads, cb, m), "simple", {}
    if kind == "shear_lug":
        cb, m = combos(project, r.miss), method(project, r.miss)
        cbl = cb if m == "LRFD" else combos(project, r.miss, "LRFD")
        loads = [dict(case=x["case"], V=x["V"], P=x.get("P") or 0.0, **({"label": x["label"]} if x.get("label") else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        pc = r.text("psi_c") or ""
        psi = 1.2 if "(1.2)" in pc else 1.4 if "(1.4)" in pc else 1.0
        n_ = lambda k, req=True: r.num(k, req)
        args = (n_("bsl"), n_("tsl"), n_("hsl"), n_("t_grout"), n_("lug_Fy"), n_("lug_Fu"), r.text("lug_source"), n_("weld"), n_("FEXX"), n_("N"), n_("B"), n_("tbp"),
                n_("bp_Fy"), n_("s_rod"), n_("rod_d"), n_("rod_Fu"), r.text("rod_source"), n_("hef_rod", False), (n_("fc") or 0) / 1000.0, n_("A2A1"), n_("ca1"), n_("ca2"),
                n_("ha"), psi)
        r.done()
        return ws_more.shear_lug_sheet(mark, *args, loads, cb, cbl, m), "simple", {}
    if kind == "crane_runway":
        cb, m = combos(project, r.miss), method(project, r.miss)
        args = (r.text("beam"), r.num("Fy"), r.text("beam_source"), r.num("span"), r.num("rail", False) or 0.0, r.text("rail_note", False) or "",
                r.text("crane_type"), r.text("class_basis"), r.num("capacity"), r.num("trolley"), r.num("wheel"), r.text("wheel_source"),
                int(r.num("n") or 1), r.num("spacing", False) or 0.0, yes(r.text("powered")), r.num("share"), r.text("share_source"))
        dv, dh, ds = r.num("defl_v", False), r.num("defl_h", False), r.text("defl_source", False) or ""
        if (dv or dh) and not ds.strip():
            r.miss.append("Where the deflection limits come from is blank")
        r.done()
        return ws_more.crane_runway_sheet(mark, *args, cb, m, defl=dict(v_ratio=dv, h_ratio=dh, source=ds) if (dv or dh) else None), "simple", {}
    if kind == "angle_beam":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = []
        for n_, x in enumerate(r.rows("loads"), 1):
            uni = (x.get("kind") or "").startswith("uniform")
            if not uni and x.get("x") is None:
                r.miss.append(f"Loads, row {n_}: a point load needs its position")
                continue
            ld = dict(case=x["case"], kind="uniform" if uni else "point", dir=x.get("dir") or "down")
            ld.update(w=x["value"]) if uni else ld.update(P=x["value"], x=x["x"])
            if x.get("label"):
                ld["label"] = x["label"]
            loads.append(ld)
        if not loads:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        rs = r.text("restraint") or ""
        args = (r.text("shape"), r.num("Fy"), r.text("steel_source"), r.num("span"), r.text("vertical", False) or "", r.text("toe"),
                "midspan" if rs.startswith("at midspan") else "continuous" if rs.startswith("continuous") else "none", yes(r.text("self_weight")))
        r.done()
        return ws_more.angle_beam_sheet(mark, *args, loads, cb, m), "simple", {}
    if kind == "tension_member":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No tension is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        if r.num("rod_d", False) is not None:
            if r.text("shape", False):
                r.miss.append("Give a section or a rod diameter, not both")
            args = (r.num("rod_d", False), r.num("Fy"), r.num("Fu"), r.text("steel_source"), r.num("length"))
            r.done()
            return ws_more.tension_rod_sheet(mark, *args, loads, cb, m), "simple", {}
        Uv = r.num("U", False)
        ac = None
        if Uv is None:
            ac = dict(n=r.num("angle_n", True, label="Shear lag factor U, or for a single angle the bolts in the line"), l=r.num("angle_l", True, label="Single angle: length of the connection"),
                      leg=r.text("angle_leg", False) or "long")
        args = (r.text("shape", True), r.num("Fy"), r.num("Fu"), r.text("steel_source"), r.num("length"), r.num("n_holes", False), r.num("bolt_d", False), r.num("hole_t", False),
                Uv, (r.text("U_source", Uv is not None) or "") if Uv is not None else "")
        r.done()
        return ws_more.tension_member_sheet(mark, *args, loads, cb, m, angle_conn=ac), "simple", {}
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
    if kind == "seat":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No reaction is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        args = (r.text("beam"), r.num("beam_Fy"), r.text("beam_source"), r.num("t"), r.num("length"), r.num("osl"), r.num("vleg"), r.num("angle_Fy"), r.text("angle_source"), r.text("attach"))
        kw = dict(weld=r.num("weld", False), FEXX=r.num("FEXX", False), n_bolts=r.num("n_bolts", False), d=r.num("d", False), group=r.text("group", False), threads=r.text("threads", False))
        r.done()
        return ws_more.seat_sheet(mark, *args, loads, cb, m, **kw), "simple", {}
    if kind == "base_plate_biaxial":
        m = method(project, r.miss)
        from .. import anchor_rods as _ar
        _g = _ar.grade(r.text("rod_grade", False) or "")
        if _g:
            _fu, _src = _g[0], _g[3]
        else:
            _fu, _src = r.num("rod_Fu", label="Anchor rod Fu"), r.text("rod_source", False)
            if not _src:
                r.miss.append("Anchor rod grade is blank (or pick other and type Fu and the material)")
        cases = r.rows("cases")
        if not cases:
            r.miss.append("No load case is entered")
        args = (r.text("shape"), r.num("N"), r.num("B"), r.num("t"), r.num("Fy"), r.num("fc"), r.num("area_ratio"), r.num("rod_d"), _fu, _src, r.num("rod_edge"), r.num("rod_side"))
        r.done()
        return ws_more.base_plate_biaxial_sheet(mark, *args, cases, m), "simple", {}
    if kind == "flush_end_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        runs = [dict(name=x["name"], M=x["M"], T=x["T"] or 0.0, V=x["V"] or 0.0) for x in r.rows("runs")]
        loads = [] if runs else [dict(case=x["case"], M=x["M"], T=x["T"] or 0.0, V=x["V"] or 0.0, **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads and not runs:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        ext = str(values.get("config") or "").startswith("extended")
        cside = not str(values.get("col_side") or "").startswith("beam side") and not ext
        nrow = 2 if (str(values.get("n_rows") or "").strip() == "2" and not ext) else 1
        cn = lambda key: r.num(key, cside, label=r.labels[key]) if cside else None
        args = (r.text("beam"), r.num("beam_Fy"), r.num("beam_Fu"), (r.text("column", False) if cside else ""), cn("col_Fy"), cn("col_Fu"), r.text("steel_source"), r.num("bp"), r.num("tp"),
                r.num("plate_Fy"), r.num("plate_Fu"), r.text("plate_source"), r.num("d"), r.text("group"), r.text("threads"), r.num("g"), r.num("pfi"), r.num("w_flange"), r.num("w_web"),
                r.num("below"), cn("tcap"), cn("bcp"), cn("w_cap_flange"), cn("w_cap_web"), r.num("FEXX"))
        if cside and not r.text("column", False):
            r.miss.append("Column is blank")
        pb_ = r.num("pb", nrow == 2, label="Spacing between the two rows")
        pfo_ = r.num("pfo", ext, label="Extended: pfo")
        nsh_ = r.num("n_shear", False)
        r.done()
        return ws_more.flush_end_plate_sheet(mark, *args, loads, cb, m, runs=runs or None, runs_from=str(values.get("loads_from") or ""), n_rows=nrow, pb=pb_, col_side=cside, extended=ext, pfo=pfo_, n_shear=nsh_ or 2), "simple", {}
    if kind == "cap_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        runs = [dict(name=x["name"], P=x["P"], M=x["M"]) for x in r.rows("runs")]
        loads = [] if runs else [dict(case=x["case"], P=x["P"], M=x["M"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads and not runs:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        args = (r.text("beam"), r.num("beam_Fy"), r.num("beam_Fu"), r.text("beam_source"), r.text("column"), r.num("col_Fy"), r.text("col_source"), r.num("tp"), r.num("bp"),
                r.num("plate_Fy"), r.num("plate_Fu"), r.text("plate_source"), r.num("d"), r.text("group"), r.num("s"), r.num("g"), r.num("weld"), r.num("FEXX"))
        r.done()
        return ws_more.cap_plate_sheet(mark, *args, loads, cb, m, runs=runs or None, runs_from=str(values.get("loads_from") or "")), "simple", {}
    if kind == "stiffened_seat":
        cb, m = combos(project, r.miss), method(project, r.miss)
        runs = [dict(name=x["name"], R=x["R"]) for x in r.rows("runs")]
        loads = [] if runs else [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads and not runs:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        args = (r.text("beam"), r.num("beam_Fy"), r.text("beam_source"), r.num("W"), r.num("L"), r.num("ts"), r.num("stiff_Fy"), r.text("stiff_source"),
                r.num("tseat"), r.num("weld"), r.num("FEXX"), r.text("support"), r.num("t_sup"), r.num("Fu_sup"))
        r.done()
        return ws_more.stiffened_seat_sheet(mark, *args, loads, cb, m, both_sides=str(values.get("both_sides") or "").startswith("y"),
                                            runs=runs or None, runs_from=str(values.get("loads_from") or "")), "simple", {}
    if kind == "beam_hss_moment":
        cb, m = combos(project, r.miss), method(project, r.miss)
        z = lambda v: v if v is not None else 0.0
        runs = [dict(name=x["name"], M=x["M"], P=z(x.get("P")), Mc=z(x.get("Mc"))) for x in r.rows("runs")]
        loads = [] if runs else [dict(case=x["case"], M=x["M"], P=z(x.get("P")), Mc=z(x.get("Mc")), **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads and not runs:
            r.miss.append("No load is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        plated = str(values.get("flanges") or "").lower().startswith("flange plate")
        plate = dict(bp=r.num("bp", True, label="Flange plate width"), tp=r.num("tp", True, label="Flange plate thickness"), Fy=r.num("plate_Fy", True, label="Flange plate Fy"),
                     source=r.text("plate_source", False)) if plated else None
        if plated and r.num("fd", False) is not None:
            for key_, lab_ in (("fgroup", "Flange plate bolts: type"), ("fthreads", "Flange plate bolts: threads")):
                if not str(values.get(key_) or "").strip():
                    r.miss.append(f"{lab_} is blank")
            plate.update(d=r.num("fd", False), group=str(values.get("fgroup") or "A325").strip(), threads=str(values.get("fthreads") or "N").strip(),
                         n=r.num("fn", True, label="Bolts in each of the two rows"), s=r.num("fs", True, label="Bolt spacing along the beam"),
                         g=r.num("fg", True, label="Gage between the two rows"), lev_p=r.num("flev_p", True, label="Plate end to the last bolt"),
                         lev_b=r.num("flev_b", True, label="Beam end to the first bolt"), a1=r.num("fa1", True, label="Column face to the first bolt"),
                         Fu=r.num("plate_Fu", True, label="Flange plate Fu"), beam_Fu=r.num("beam_Fu", True, label="Beam Fu"),
                         weld=r.num("fweld", False), FEXX=r.num("fFEXX", False) or 70.0)
        r.text("flanges")
        args = (r.text("beam"), r.num("beam_Fy"), r.text("beam_source"), r.text("column"), r.num("col_Fy"), r.text("col_source"))
        r.done()
        return ws_more.beam_hss_moment_sheet(mark, *args, loads, cb, m, face=str(values.get("face") or "B"), plate=plate, runs=runs or None,
                                             runs_from=str(values.get("loads_from") or "")), "simple", {}
    if kind == "end_plate":
        cb, m = combos(project, r.miss), method(project, r.miss)
        loads = [dict(case=x["case"], P=x["P"], **({"label": x["label"]} if x["label"] else {})) for x in r.rows("loads")]
        if not loads:
            r.miss.append("No reaction is entered")
        cases_used([x["case"] for x in loads], cb, r.miss)
        sn = r.text("support_name", False)
        sup = dict(name=sn, t=r.num("support_t", True, label="Support: thickness at the bolts"), Fu=r.num("support_Fu", True, label="Support: Fu")) if sn else None
        args = (r.text("beam"), r.num("beam_Fy"), r.num("beam_Fu"), r.text("beam_source"), r.num("tp"), r.num("width"), r.num("length"), r.num("plate_Fy"), r.num("plate_Fu"),
                r.text("plate_source"), r.num("d"), r.text("group"), r.text("threads"), r.num("n"), r.num("spacing"), r.num("lev"), r.num("gage"), r.num("weld"), r.num("FEXX"))
        r.done()
        return ws_more.end_plate_sheet(mark, *args, loads, cb, m, support=sup), "simple", {}
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
        cope = None
        if r.num("cope_dc", False) or r.num("cope_dcb", False):
            cope = dict(dc=r.num("cope_dc", False), dcb=r.num("cope_dcb", False), c=r.num("cope_c", True, label="Coped beam: cope length"), setback=r.num("cope_setback", True, label="Coped beam: setback"),
                        lev=r.num("cope_lev", True, label="Coped beam: cut edge to the nearest bolt"), leh=r.num("cope_leh", True, label="Coped beam: bolt line to the beam end"),
                        Fy=r.num("beam_Fy", True, label="Coped beam: beam Fy"))
        thr_ = r.num("through", False)
        r.done()
        return ws_more.single_plate_sheet(mark, *args, loads, cb, m, support=sup, cope=cope, through=thr_), "simple", {}
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
    if kind == "ftao_wall":
        m = method(project, r.miss)
        args = (r.text("panel"), r.text("spacing"), r.text("panel_type"), r.num("G"), r.text("G_source"), r.num("h"), r.num("L1"), r.num("Lo"), r.num("L2"), r.num("ho"),
                r.num("sill", False) or 0.0, r.num("V"), r.text("load"))
        vs, sd_ = r.text("v_source"), r.text("sides") or ""
        hdm = r.text("hd_model", False)
        more = r.rows("more")
        r.done()
        return ws_more.ftao_wall_sheet(mark, args[0], int(args[1]), *args[2:], m, vs, yes(r.text("holddown", False)), 2 if sd_.startswith("both") else 1,
                                       above_T=r.num("above_T", False) or 0.0, above_source=r.text("above_source", False) or "",
                                       holddown=(dict(model=hdm, stem=r.text("hd_stem", False), position=r.text("hd_position", False),
                                                      cracked={"cracked": True, "uncracked": False}.get(r.text("hd_cracked", False)),
                                                      sdc_high={"A or B": False, "C to F": True}.get(r.text("hd_sdc", False))) if hdm else None),
                                       more=more or None), "simple", {}
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
                                        dead_factor=r.num("dead_factor", False), dead_source=r.text("dead_source", False) or "", other=oth,
                                        above_T=r.num("above_T", False) or 0.0, above_source=r.text("above_source", False) or "",
                                        holddown=(dict(model=r.text("hd_model", False), stem=r.text("hd_stem", False), position=r.text("hd_position", False),
                                                       cracked={"cracked": True, "uncracked": False}.get(r.text("hd_cracked", False)),
                                                       sdc_high={"A or B": False, "C to F": True}.get(r.text("hd_sdc", False))) if r.text("hd_model", False) else None)), "simple", {}
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
        lo = None
        if (r.text("occupancy", False) or "").startswith("other"):
            lo = dict(psf=r.num("live_psf", True, label="Other: uniform live load"), source=r.text("live_source", True) or "", P=r.num("live_P", False))
        r.done()
        return ws_more.stair_stringer_sheet(mark, *args, bool(br), cb, dc, m, live_other=lo), "steel_beam", dict(combos=cb)
    if kind == "hss_column":
        m = method(project, r.miss)
        cb = combos(project, r.miss, m)
        ld, mo = r.rows("loads"), r.rows("moments")
        if not ld:
            r.miss.append("No axial load is entered")
        cases_used([x["case"] for x in ld] + [x["case"] for x in mo], cb, r.miss)
        args = (r.text("shape"), r.num("Fy"), r.text("Fy_source"), r.num("height"), r.num("Kx"), r.num("Ky"), r.text("k_source"))
        sw = yes(r.text("self_weight"))
        er = r.num("end_ratio", False)
        r.done()
        return ws_more.hss_column_sheet(mark, *args, [dict(case=x["case"], P=x["P"], label=x.get("label") or "") for x in ld],
                                        [dict(case=x["case"], Mx=x.get("Mx"), My=x.get("My"), label=x.get("label") or "") for x in mo], bool(sw), cb, m, end_ratio=er), "simple", {}
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


TAKEDOWN_BEAMS = ("steel_beam", "wood_beam", "lvl_beam", "glulam_beam", "wey_beam", "ijoist")
TAKEDOWN_POSTS = ("wood_post", "builtup_post", "lvl_post", "wey_post", "glulam_post", "steel_column", "hss_column")


def case_reactions(kind, values, project):
    """Gravity takedown: the reaction at every support of a beam or joist, or at the base of a post or column, by load case (lb, downward
    positive), so the member below can take them as loads without retyping. Each case is the member run under that case alone (all spans
    loaded). Returns dict(supports=[dict(name, x_ft, cases={case: lb})], notes=[...]) or dict(error=...)."""
    v = values or {}
    if kind in TAKEDOWN_POSTS:
        kip = kind in ("steel_column", "hss_column")
        tot = {}
        for row in v.get("loads") or []:
            try:
                P = float(str(row.get("P", "")).replace(",", ""))
            except ValueError:
                continue
            c = str(row.get("case") or "").strip()
            if c:
                tot[c] = tot.get(c, 0.0) + P * (1000.0 if kip else 1.0)
        notes = []
        if kip and str(v.get("self_weight", "")).lower() == "yes":
            try:
                sec = (shapes.hss(v["shape"]) if kind == "hss_column" else shapes.get(v["shape"]))
                tot["D"] = tot.get("D", 0.0) + sec["W"] * float(v.get("height") or 0)
                notes.append("the column's own weight is included in D")
            except Exception:
                pass
        elif not kip:
            notes.append("a post's own weight is carried only if it is typed as a load on the post")
        if not tot:
            return dict(error="That member has no loads yet.")
        return _governing(dict(supports=[dict(name="base", x_ft=0.0, cases=tot)], notes=notes), project)
    if kind in MODEL_WALLS:                                   # a bearing wall in the building model: the loads that bear on it, by case
        tot = {}
        for row in v.get("loads") or []:
            if not (isinstance(row, dict) and isinstance(row.get("link"), dict)):
                continue
            try:
                P = float(str(row.get("P", "")).replace(",", ""))
            except ValueError:
                continue
            c = str(row.get("case") or "").strip()
            if c:
                tot[c] = tot.get(c, 0.0) + P
        notes = ["a wall passes down what bears on it"]
        ww = _wall_weight(project, v)
        if isinstance(ww, str):
            return dict(error=ww)
        if ww:
            tot["D"] = tot.get("D", 0.0) + ww[0]
            notes.append(ww[1])
        else:
            notes.append("its own weight is not included")
        if not tot:
            return dict(error="Nothing in the building model bears on that wall.")
        return _governing(dict(supports=[dict(name="base", x_ft=0.0, cases=tot)], notes=notes), project)
    if kind not in TAKEDOWN_BEAMS:
        return dict(error="Reactions can be taken from a beam, a joist, a post or a column.")
    cases = []
    for row in v.get("loads") or []:
        c = str(row.get("case") or "").strip()
        if c and c not in cases:
            cases.append(c)
    if "D" not in cases:
        cases.insert(0, "D")                                 # self-weight
    p2 = dict(project or {}, method="ASD", combos_asd=[dict(expr=c, source="load case alone") for c in cases])
    try:
        sheet, _, _ = build(kind, v, p2)
    except Missing as e:
        return dict(error="That member is not complete: " + "; ".join(e.items))
    except Exception as e:
        return dict(error=f"That member stopped: {e}")
    num = lambda key: float(str(v.get(key) or 0).replace(",", "") or 0)
    spans = [num("span")] + [float(t) for t in str(v.get("more_spans") or "").replace(";", ",").split(",") if t.strip()]
    xs = [num("oh_left")]
    for sp in spans:
        xs.append(xs[-1] + sp)
    sup = [dict(name=("left support" if i == 0 else "right support" if i == len(xs) - 1 else f"support at {x:g} ft"), x_ft=x, cases={}) for i, x in enumerate(xs)]
    scale = 1000.0 if kind == "steel_beam" else 1.0
    for c in cases:
        R = sheet.reactions.get(c)
        if R is None:
            continue
        if isinstance(R, dict):
            vals = [R[k] for k in sorted(R)]
        elif isinstance(R, (list, tuple)):
            vals = list(R)
        else:
            vals = [R] * len(sup)                            # simple-span joist: one value, the same at both ends
        if len(vals) != len(sup):
            return dict(error="That member's supports could not be matched to its reactions.")
        for sdict, r in zip(sup, vals):
            sdict["cases"][c] = r * scale
    notes = ["each case is run alone with every span loaded"]
    if kind == "ijoist" or num("spacing"):
        notes.append("for a joist or rafter this is the reaction of one member; multiply by the number carried, or divide by the spacing for a load per foot")
    return _governing(dict(supports=sup, notes=notes), project)


TAKEDOWN_KIP = ("steel_beam", "steel_column", "hss_column", "single_plate", "end_plate", "seat", "base_plate")
TAKEDOWN_FOOTINGS = ("footing_iso", "footing_cont")


def _links(member):
    """The takedown links stored on a member: on its load rows (key "link") or, for a footing, on the member itself."""
    v = member.get("values") or {}
    out = []
    if member.get("kind") in TAKEDOWN_FOOTINGS:
        if isinstance(v.get("link"), dict) and v["link"].get("src"):
            out.append(v["link"])
        for lk in v.get("links") or []:
            if isinstance(lk, dict) and lk.get("src") and lk not in out:
                out.append(lk)
        return out
    for row in v.get("loads") or []:
        lk = row.get("link") if isinstance(row, dict) else None
        if isinstance(lk, dict) and lk.get("src") and lk not in out:
            out.append(lk)
    return out


def link_tag(lk):
    n = float(lk.get("count") or 1)
    if lk.get("mode") == "line":
        return f"reaction of {lk['src']}, {lk['support']}, as a line at {float(lk.get('spacing_in') or 0):g} in. o.c."
    if lk.get("spread"):
        return f"reaction of {lk['src']}, {lk['support']}, spread over {float(lk.get('per_ft') or 0):g} ft of footing"
    if lk.get("mode") == "wall":
        return (f"load down wall {lk['src']}, spread over its {float(lk.get('length_ft') or 0):g} ft"
                + (f", the {float(lk['share']) * 100:.0f}% of it not over headers" if "share" in lk and float(lk["share"]) < 1 else ""))
    return f"reaction of {lk['src']}, {lk['support']}" + (f" x {n:g}" if n != 1 else "")


def takedown(project, members):
    """Recalculates every stored takedown link, from the top of the load path down: each linked member's reaction rows (or a footing's
    service and factored loads) are rewritten from the member above as it stands now. Returns dict(members=the updated list, links=[one
    line per link], problems=[...]). Members without links are returned unchanged."""
    import copy
    ms = copy.deepcopy(members or [])
    by_mark = {}
    for m in ms:
        by_mark.setdefault((m.get("values") or {}).get("mark") or "", m)
    deps = {id(m): [by_mark.get(lk["src"]) for lk in _links(m)] for m in ms}
    order, state, problems = [], {}, []

    def visit(m, trail):
        if state.get(id(m)) == 2:
            return
        if state.get(id(m)) == 1:
            problems.append("The load path goes in a circle: " + " -> ".join(trail + [(m.get("values") or {}).get("mark") or "(no mark)"]))
            return
        state[id(m)] = 1
        for dsrc in deps[id(m)]:
            if dsrc is not None:
                visit(dsrc, trail + [(m.get("values") or {}).get("mark") or "(no mark)"])
        state[id(m)] = 2
        order.append(m)

    for m in ms:
        visit(m, [])
    if problems:
        return dict(members=members, links=[], problems=problems)
    report = []
    foot_acc = {}
    for m in order:
        v, kind = m.get("values") or {}, m.get("kind")
        mark = v.get("mark") or "(no mark)"
        for lk in _links(m):
            src = by_mark.get(lk["src"])
            line = dict(target=mark, source=lk["src"], support=lk.get("support"), count=float(lk.get("count") or 1), x=lk.get("x", ""))
            if src is None:
                problems.append(f"{mark}: the member above, {lk['src']}, is no longer in the project (its loads are left as they were)")
                continue
            got = case_reactions(src.get("kind"), src.get("values") or {}, project)
            if "error" in got:
                problems.append(f"{mark}: {lk['src']}: {got['error']} (its loads are left as they were)")
                continue
            sup = next((s_ for s_ in got["supports"] if s_["name"] == lk.get("support")), None)
            if sup is None:
                problems.append(f"{mark}: {lk['src']} no longer has a '{lk.get('support')}' (its loads are left as they were)")
                continue
            n = line["count"]
            if kind in TAKEDOWN_FOOTINGS:
                if not sup.get("service") or not sup.get("strength"):
                    problems.append(f"{mark}: both ASD and LRFD load combinations are needed on the Project page to fill a footing")
                    continue
                per = float(lk.get("per_ft") or 0)                  # a wall or joist row on a continuous footing: load per foot
                k_ = n / per if per else n
                acc = foot_acc.setdefault(id(m), dict(cases={}, tags=[], per=bool(per)))
                for c, val in sup["cases"].items():
                    acc["cases"][c] = acc["cases"].get(c, 0.0) + val * k_
                acc["tags"].append(link_tag(lk) + (f", per foot" if per else ""))
                line.update(total=sup["service"]["P"] * k_, unit="lb/ft service" if per else "lb service")
            elif kind in MODEL_WALLS:
                rows = [r for r in (v.get("loads") or []) if not (isinstance(r, dict) and r.get("link") == lk)]
                for c, val in sup["cases"].items():
                    if abs(val) < 0.5:
                        continue
                    if lk.get("mode") == "line":                     # a row of joists: per joist x 12 / spacing x the length it covers on the wall
                        sp = float(lk.get("spacing_in") or 0)
                        tot = val * 12.0 / sp * float(lk.get("cover_ft") or 0) if sp > 0 else 0.0
                    else:
                        tot = val * n * float(lk.get("share", 1.0))
                    rows.append(dict(case=c, P=str(round(tot)), label=link_tag(lk), link=dict(lk)))
                v["loads"] = rows
                line.update(total=sum(float(r["P"]) for r in rows if r.get("link") == lk), unit="lb, all cases")
            else:
                kip = kind in TAKEDOWN_KIP
                f = (0.001 if kip else 1.0) * n
                beam = kind in TAKEDOWN_BEAMS
                rows = [r for r in (v.get("loads") or []) if not (isinstance(r, dict) and r.get("link") == lk)]
                for c, val in sup["cases"].items():
                    if abs(val) < 0.5:
                        continue
                    amt = str(round(val * f, 3)) if kip else str(round(val * f))
                    if beam and lk.get("mode") == "wall":
                        w = val / float(lk.get("length_ft") or 1) * (0.001 if kip else 1.0)
                        rows.append(dict(case=c, kind="uniform", mag=(str(round(w, 4)) if kip else str(round(w, 1))), mag2="", x1=str(lk.get("x", "")), x2=str(lk.get("x2", "")),
                                         label=link_tag(lk), link=dict(lk)))
                    elif beam and lk.get("mode") == "line":
                        sp = float(lk.get("spacing_in") or 0)
                        if sp <= 0:
                            problems.append(f"{mark}: the joist spacing of {lk['src']} is missing")
                            break
                        w = val * 12.0 / sp * (0.001 if kip else 1.0)
                        rows.append(dict(case=c, kind="uniform", mag=(str(round(w, 4)) if kip else str(round(w, 1))), mag2="", x1=str(lk.get("x", "")), x2=str(lk.get("x2", "")),
                                         label=link_tag(lk), link=dict(lk)))
                    elif beam:
                        rows.append(dict(case=c, kind="point", mag=amt, mag2="", x1=str(lk.get("x", "")), x2="", label=link_tag(lk), link=dict(lk)))
                    else:
                        rows.append(dict(case=c, P=amt, label=link_tag(lk), link=dict(lk)))
                v["loads"] = rows
                line.update(total=sum(sup["cases"].values()) * n, unit="lb, all cases")
            report.append(line)
        acc = foot_acc.get(id(m))
        if acc and kind in TAKEDOWN_FOOTINGS:                  # everything on the footing together, then the governing combinations
            g = _governing(dict(supports=[dict(name="base", x_ft=0.0, cases=acc["cases"])], notes=[]), project)["supports"][0]
            if g.get("service") and g.get("strength"):
                v.update(P_service=str(round(g["service"]["P"])), service_combo=g["service"]["name"], Pu=str(round(g["strength"]["P"])),
                         strength_combo=g["strength"]["name"], loads_from="; ".join(acc["tags"]))
    return dict(members=ms, links=report, problems=problems)


# ---------------------------------------------------------------- building model: levels, grids, members placed on them
MODEL_WALLS = ("shear_wall", "perforated_wall", "ftao_wall")
MODEL_TOL = 0.25                                             # ft: how close two members must be in plan to be taken as bearing on each other


def _coord(text, grids):
    """A plan coordinate typed as a number of feet, a grid name, or a grid name with an offset ("B+2.5", "3-1")."""
    t = str(text if text is not None else "").strip()
    if not t:
        return None
    names = {str(g.get("name") or "").strip().upper(): g for g in grids or []}
    if t.upper() not in names:                               # a grid name wins over a number: with a grid named 2, "2" is the grid
        try:
            return float(t.replace(",", ""))
        except ValueError:
            pass
    base, off = t.upper(), 0.0
    for sign in ("+", "-"):
        if sign in t[1:]:
            i = t.rindex(sign)
            try:
                off = float(t[i:])
                base = t[:i].strip().upper()
            except ValueError:
                pass
            break
    if base in names:
        try:
            return float(str(names[base].get("at")).replace(",", "")) + off
        except (TypeError, ValueError):
            return None
    return None


def _wall_weight(project, v):
    """A placed wall's own weight for the load path: (lb, note) from its typed psf x story height x placed length; None when no weight is
    typed; a message when the weight is typed but cannot be used (no source, no elevations, not placed)."""
    t = str(v.get("at_wall_psf") or "").replace(",", "").strip()
    if not t:
        return None
    try:
        psf = float(t)
    except ValueError:
        return "the wall weight is not a number"
    src = str(v.get("at_wall_psf_source") or "").strip()
    if not src:
        return "the wall weight needs a source (where it comes from)"
    pl = model_place(project, dict(kind="shear_wall", values=v))
    if not pl:
        return "the wall weight needs the wall placed in the building model"
    el = {}
    for l in ((project or {}).get("model") or {}).get("levels") or []:
        try:
            el[str(l.get("name") or "").strip()] = float(str(l.get("elev")).replace(",", ""))
        except (TypeError, ValueError):
            pass
    if pl["level"] not in el or pl["base"] not in el or pl["base"] == pl["level"]:
        return "the wall weight needs elevations for the level at the top of the wall and the level below"
    h = el[pl["level"]] - el[pl["base"]]
    L = math.hypot(pl["p2"][0] - pl["p1"][0], pl["p2"][1] - pl["p1"][1])
    return psf * h * L, f"its own weight {psf:g} psf x {h:g} ft x {L:.2f} ft = {psf * h * L:,.0f} lb dead ({src})"


def model_existing(project):
    """Existing walls of the model (by others, not designed): [(name, dict(level, base, p1, p2))]; unreadable rows are skipped."""
    mdl = (project or {}).get("model") or {}
    gx, gy = mdl.get("grids_x") or [], mdl.get("grids_y") or []
    levels = [str(l.get("name") or "").strip() for l in mdl.get("levels") or []]
    out = []
    for r in mdl.get("existing") or []:
        nm, lv = str(r.get("name") or "").strip(), str(r.get("level") or "").strip()
        p1, p2 = (_coord(r.get("x1"), gx), _coord(r.get("y1"), gy)), (_coord(r.get("x2"), gx), _coord(r.get("y2"), gy))
        if not nm or lv not in levels or None in p1 or None in p2:
            continue
        i = levels.index(lv)
        out.append((nm, dict(level=lv, base=levels[i - 1] if i > 0 else lv, p1=p1, p2=p2)))
    return out


def _lvl_index(project, name):
    lv = [str(l.get("name") or "").strip() for l in ((project or {}).get("model") or {}).get("levels") or []]
    return lv.index(name) if name in lv else 0


def model_place(project, member):
    """Where a member sits in the building model, from its placement boxes: dict(level, base, p1=(x, y), p2=(x, y) or None), or None
    when it is not placed. Raises ValueError with a plain message when the boxes are filled but cannot be read."""
    v = member.get("values") or {}
    mdl = (project or {}).get("model") or {}
    if not str(v.get("at_x1") or "").strip() and not str(v.get("at_level") or "").strip():
        return None
    mark = v.get("mark") or "(no mark)"
    gx, gy = mdl.get("grids_x") or [], mdl.get("grids_y") or []
    x1, y1 = _coord(v.get("at_x1"), gx), _coord(v.get("at_y1"), gy)
    if x1 is None or y1 is None:
        raise ValueError(f"{mark}: its position in plan cannot be read (type feet, or a grid name such as B or B+2.5)")
    p2 = None
    if member.get("kind") in TAKEDOWN_BEAMS + MODEL_WALLS + FRAME_BRACES:
        x2, y2 = _coord(v.get("at_x2"), gx), _coord(v.get("at_y2"), gy)
        if x2 is None or y2 is None:
            raise ValueError(f"{mark}: a beam, joist, wall or brace needs the position of both ends")
        p2 = (x2, y2)
    elif member.get("kind") == "footing_cont" and str(v.get("at_x2") or "").strip():
        x2, y2 = _coord(v.get("at_x2"), gx), _coord(v.get("at_y2"), gy)
        if x2 is None or y2 is None:
            raise ValueError(f"{mark}: the other end of the continuous footing cannot be read")
        p2 = (x2, y2)
    levels = [str(l.get("name") or "").strip() for l in mdl.get("levels") or []]
    lvl = str(v.get("at_level") or "").strip()
    if member.get("kind") in TAKEDOWN_FOOTINGS:
        lvl = lvl or (levels[0] if levels else "")
    elif lvl not in levels:
        raise ValueError(f"{mark}: its level, '{lvl}', is not in the list of levels on the Project page")
    base = str(v.get("at_base") or "").strip() or (levels[0] if levels else "")
    if member.get("kind") in MODEL_WALLS and lvl in levels and levels.index(lvl) > 0:
        base = levels[levels.index(lvl) - 1]                 # a wall stands on the level below its top
    return dict(level=lvl, base=base, p1=(x1, y1), p2=p2)


def model_links(project, members):
    """Links the placed members by position: under each support of a placed beam or joist, and under the base of each placed post or column,
    the member that carries it (a post or column whose top is at that level, else a beam passing under the point, else a footing) takes its
    reaction. Earlier links made this way are replaced; links picked by hand are kept. Then the whole load path is recalculated. Returns
    dict(members, links, problems, placed)."""
    import copy, math
    ms = copy.deepcopy(members or [])
    problems, placed = [], []
    for m in ms:
        try:
            pl = model_place(project, m)
        except ValueError as e:
            problems.append(str(e)); pl = None
        if pl:
            placed.append((m, pl))
    # drop the links made by position last time
    for m in ms:
        v = m.get("values") or {}
        if isinstance(v.get("link"), dict) and v["link"].get("auto"):
            v.pop("link", None)
        if isinstance(v.get("links"), list):
            v["links"] = [lk for lk in v["links"] if not (isinstance(lk, dict) and lk.get("auto"))]
        if isinstance(v.get("loads"), list):
            v["loads"] = [r for r in v["loads"] if not (isinstance(r, dict) and isinstance(r.get("link"), dict) and r["link"].get("auto"))]
    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])

    def along(pt, pl):                                       # (distance from p1 along the member, offset from its line), or None when off its ends
        (ax, ay), (bx, by) = pl["p1"], pl["p2"]
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            return None
        t = ((pt[0] - ax) * (bx - ax) + (pt[1] - ay) * (by - ay)) / L
        off = abs((pt[0] - ax) * (by - ay) - (pt[1] - ay) * (bx - ax)) / L
        return (t, off) if -MODEL_TOL <= t <= L + MODEL_TOL else None

    def carrier(pt, level, me, want_footing, skip_parallel=False):
        posts = [(m, pl) for m, pl in placed if m is not me and m["kind"] in TAKEDOWN_POSTS and pl["level"] == level and dist(pl["p1"], pt) <= MODEL_TOL]
        if posts:
            return posts, None
        beams = []
        mine = next((p_ for m_, p_ in placed if m_ is me), None)
        def parallel(pl):                                    # a member running the same way does not carry this one (two joists end to end)
            if not mine or mine.get("p2") is None or pl.get("p2") is None:
                return False
            (ax_, ay_), (bx_, by_) = mine["p1"], mine["p2"]
            (cx_, cy_), (dx_, dy_) = pl["p1"], pl["p2"]
            u_, w_ = math.hypot(bx_ - ax_, by_ - ay_), math.hypot(dx_ - cx_, dy_ - cy_)
            return u_ > 0 and w_ > 0 and abs((bx_ - ax_) * (dy_ - cy_) - (by_ - ay_) * (dx_ - cx_)) / (u_ * w_) < 0.09
        for m, pl in placed:
            if m is me or m["kind"] not in TAKEDOWN_BEAMS or pl["level"] != level or (parallel(pl) and not skip_parallel):
                continue
            a = along(pt, pl)
            if a and a[1] <= MODEL_TOL:
                beams.append((m, pl, max(0.0, a[0])))
        if beams:
            return [(m, pl) for m, pl, _ in beams], [x for _, _, x in beams]
        walls = []
        for m, pl in placed:
            if m is me or m["kind"] not in MODEL_WALLS or pl["level"] != level:
                continue
            a = along(pt, pl)
            if a and a[1] <= MODEL_TOL:
                walls.append((m, pl, max(0.0, a[0])))
        if walls:
            return [(m, pl) for m, pl, _ in walls], [x for _, _, x in walls]
        for nm, epl in existing:
            if epl["level"] == level:
                a = along(pt, epl)
                if a and a[1] <= MODEL_TOL:
                    return [(dict(kind="existing", values=dict(mark=nm)), epl)], None
        if want_footing:
            foots = [(m, pl) for m, pl in placed if m["kind"] in TAKEDOWN_FOOTINGS and pl.get("p2") is None and pl["level"] == level and dist(pl["p1"], pt) <= MODEL_TOL]
            for m, pl in placed:
                if m["kind"] == "footing_cont" and pl.get("p2") is not None and pl["level"] == level:
                    a = along(pt, pl)
                    if a and a[1] <= MODEL_TOL:
                        foots.append((m, pl))
            if foots:
                return foots, None
        return [], None

    headers, wall_headers = {}, {}                           # a beam lying in a wall line at the wall's top level is a header over an opening
    for hm, hpl in placed:
        if hm["kind"] not in TAKEDOWN_BEAMS or hpl.get("p2") is None:
            continue
        for wm, wpl in placed:
            if wm["kind"] not in MODEL_WALLS or wpl["level"] != hpl["level"]:
                continue
            a1, a2 = along(hpl["p1"], wpl), along(hpl["p2"], wpl)
            if a1 and a2 and a1[1] <= MODEL_TOL and a2[1] <= MODEL_TOL:
                headers[id(hm)] = (wm, wpl, a1[0], a2[0])
                wall_headers.setdefault(id(wm), []).append((hm, hpl, a1[0], a2[0]))
                break

    def split_on_wall(wm, lo, hi):
        """The part of [lo, hi] (ft along wall wm) over each of its headers: [(header, x from the header's left end, x2)], and the rest."""
        parts, rest = [], hi - lo
        for hm, hpl, h1, h2 in wall_headers.get(id(wm), []):
            a, b = max(lo, min(h1, h2)), min(hi, max(h1, h2))
            if b - a > 1e-6:
                parts.append((hm, abs(a - h1), abs(b - h1)))
                rest -= b - a
        return parts, max(0.0, rest)

    fmt = lambda x: f"{x:.3f}".rstrip("0").rstrip(".") or "0"
    existing = model_existing(project)
    on_existing = []
    made = 0
    placed.sort(key=lambda t: (t[0]["kind"] in MODEL_WALLS, -_lvl_index(project, t[1]["level"]) if t[0]["kind"] in MODEL_WALLS else 0))
    for m, pl in placed:
        v, kind = m["values"], m["kind"]
        mark = v.get("mark") or "(no mark)"
        if not str(v.get("mark") or "").strip():
            problems.append("A placed member has no mark; links are kept by mark"); continue
        if kind in TAKEDOWN_FOOTINGS:
            continue
        if kind in MODEL_WALLS:
            if not any(isinstance(r, dict) and isinstance(r.get("link"), dict) for r in (v.get("loads") or [])) and not str(v.get("at_wall_psf") or "").strip():
                continue                                         # nothing bears on this wall and no weight typed: it passes nothing down
            (wx1, wy1), (wx2, wy2) = pl["p1"], pl["p2"]
            wl = math.hypot(wx2 - wx1, wy2 - wy1)
            under = []
            for m2, pl2 in placed:
                if m2 is m:
                    continue
                if ((m2["kind"] in TAKEDOWN_BEAMS + MODEL_WALLS and pl2["level"] == pl["base"] and pl["base"] != pl["level"])
                        or (m2["kind"] == "footing_cont" and pl2.get("p2") is not None and pl2["level"] == pl["base"])):
                    a1, a2 = along(pl["p1"], pl2), along(pl["p2"], pl2)
                    if a1 and a2 and a1[1] <= MODEL_TOL and a2[1] <= MODEL_TOL:
                        under.append((m2, pl2, a1[0], a2[0]))
            if not under:
                continue                                        # a wall with nothing modelled under it keeps its loads; reported below if it carries any
            if len(under) > 1:
                problems.append(f"{mark}: more than one member is under the wall ({', '.join(u[0]['values'].get('mark') or '?' for u in under)}); link it by hand"); continue
            tgt, tpl, t1, t2 = under[0]
            tv = tgt["values"]
            lk = dict(src=v["mark"], support="base", count=1, auto=True)
            if tgt["kind"] == "footing_cont":
                lk["per_ft"] = round(wl, 4)
                tv.setdefault("links", []).append(lk)
            elif tgt["kind"] in MODEL_WALLS:
                lk.update(mode="wall", length_ft=round(wl, 4))
                parts, rest = split_on_wall(tgt, min(t1, t2), max(t1, t2))
                for hm, x1_, x2_ in parts:
                    lkh = dict(lk, x=fmt(x1_), x2=fmt(x2_))
                    hm["values"].setdefault("loads", []).append(dict(case="D", kind="uniform", mag="0", mag2="", x1=lkh["x"], x2=lkh["x2"], label="", link=lkh))
                if parts:
                    lk["share"] = round(rest / wl, 5) if wl > 0 else 1.0
                if rest > 1e-6:
                    tv.setdefault("loads", []).append(dict(case="D", P="0", label="", link=lk))
            else:
                lk.update(mode="wall", length_ft=round(wl, 4), x=f"{min(t1, t2):.3f}".rstrip("0").rstrip("."), x2=f"{max(t1, t2):.3f}".rstrip("0").rstrip("."))
                tv.setdefault("loads", []).append(dict(case="D", kind="uniform", mag="0", mag2="", x1=lk["x"], x2=lk["x2"], label="", link=lk))
            made += 1
            continue
        if kind in TAKEDOWN_POSTS:
            got = dict(supports=[dict(name="base", x_ft=0.0)])   # its loads come down the path; only the position is needed here
        else:
            got = case_reactions(kind, v, project)
            if "error" in got:
                problems.append(f"{mark}: {got['error']}"); continue
        if kind in TAKEDOWN_BEAMS:
            (ax, ay), (bx, by) = pl["p1"], pl["p2"]
            Lm = math.hypot(bx - ax, by - ay)
            Lt = max(s_["x_ft"] for s_ in got["supports"])
            num = lambda key: float(str(v.get(key) or 0).replace(",", "") or 0)
            Lt_all = Lt + num("oh_right")
            if abs(Lm - Lt_all) > max(0.1, 0.005 * Lt_all):
                problems.append(f"{mark}: placed {Lm:.2f} ft long in the model, but its spans add up to {Lt_all:.2f} ft"); continue
            pts = [(s_, (ax + (bx - ax) * s_["x_ft"] / Lm, ay + (by - ay) * s_["x_ft"] / Lm), pl["level"], True) for s_ in got["supports"]]
        else:
            pts = [(got["supports"][0], pl["p1"], pl["base"], True)]
        hdr = headers.get(id(m))
        if hdr:                                               # a header: its ends come down the jack studs to what is under the wall
            pts = [(s_, p_, hdr[1]["base"], True) for s_, p_, _, _ in pts]
        for sup, pt, level, want_footing in pts:
            cs, xs = carrier(pt, level, m, want_footing, skip_parallel=bool(hdr))
            if hdr and cs and cs[0][0] is hdr[0]:
                cs = []
            if not cs:
                problems.append(f"{mark}, {sup['name']}: nothing in the model is under it at ({pt[0]:g}, {pt[1]:g}) ft on level {level}")
                continue
            if len(cs) > 1:
                problems.append(f"{mark}, {sup['name']}: more than one member is under it ({', '.join((c[0]['values'].get('mark') or '?') for c in cs)}); link it by hand")
                continue
            tgt = cs[0][0]
            tv = tgt["values"]
            if tgt["kind"] == "existing":                     # the load goes to existing construction: listed, not carried further
                sp = num("spacing") if kind in TAKEDOWN_BEAMS else 0
                cases = sup.get("cases") or {}
                on_existing.append(dict(wall=tv["mark"], source=v["mark"], support=sup["name"], cases={c: round(x * (12.0 / sp if sp > 0 else 1.0)) for c, x in cases.items()},
                                        unit="lb/ft" if sp > 0 else "lb"))
                continue
            lk = dict(src=v["mark"], support=sup["name"], count=1, auto=True)
            sp_ = num("spacing") if kind in TAKEDOWN_BEAMS else 0
            on_line = None
            if sp_ > 0 and tgt["kind"] in MODEL_WALLS and id(tgt) in wall_headers:
                on_line = (tgt, cs[0][1])
            elif sp_ > 0 and id(tgt) in headers:
                on_line = headers[id(tgt)][:2]
            if on_line:                                       # a row on a wall line with headers: the length over each header goes to the header
                wm, wpl = on_line
                (wx1, wy1), (wx2, wy2) = wpl["p1"], wpl["p2"]
                wl_ = math.hypot(wx2 - wx1, wy2 - wy1)
                a0 = along(pt, wpl)[0]
                lo, hi = 0.0, wl_
                rw = str(v.get("at_row") or "").strip()
                if rw:
                    try:
                        W = float(rw)
                    except ValueError:
                        problems.append(f"{mark}: the row width '{rw}' is not a number"); continue
                    (jx1, jy1), (jx2, jy2) = pl["p1"], pl["p2"]
                    jl = math.hypot(jx2 - jx1, jy2 - jy1)
                    right = ((jy2 - jy1) / jl, -(jx2 - jx1) / jl)
                    proj = (right[0] * (wx2 - wx1) + right[1] * (wy2 - wy1)) / wl_
                    lo, hi = max(0.0, min(a0, a0 + W * proj)), min(wl_, max(a0, a0 + W * proj))
                parts, rest = split_on_wall(wm, lo, hi)
                for hm, x1_, x2_ in parts:
                    lkh = dict(lk, mode="line", spacing_in=sp_, x=fmt(x1_), x2=fmt(x2_))
                    hm["values"].setdefault("loads", []).append(dict(case="D", kind="uniform", mag="0", mag2="", x1=lkh["x"], x2=lkh["x2"], label="", link=lkh))
                if rest > 1e-6:
                    lkw = dict(lk, mode="line", spacing_in=sp_, cover_ft=round(rest, 4))
                    wm["values"].setdefault("loads", []).append(dict(case="D", P="0", label="", link=lkw))
                made += 1
                continue
            if tgt["kind"] in TAKEDOWN_FOOTINGS and tgt["kind"] == "footing_cont" and cs[0][1].get("p2") is not None:
                sp = num("spacing") if kind in TAKEDOWN_BEAMS else 0
                if sp <= 0:
                    try:
                        spread = float(str(tv.get("at_spread") or "").replace(",", ""))
                    except ValueError:
                        spread = 0.0
                    if spread <= 0 or not str(tv.get("at_spread_source") or "").strip():
                        problems.append(f"{mark}, {sup['name']}: a point load on continuous footing {tv.get('mark')} is not spread along it; type the length a point load "
                                        "spreads over (and its source) on that footing's placement card, check it as an isolated footing, or link it by hand")
                        continue
                    lk["per_ft"] = round(spread, 4)          # a point load spread evenly over the typed length of footing
                    lk["spread"] = True
                    tv.setdefault("links", []).append(lk)
                    made += 1
                    continue
                lk["per_ft"] = round(sp / 12.0, 4)           # a row of joists straight onto a footing line: per foot = per joist x 12 / spacing
                tv.setdefault("links", []).append(lk)
            elif tgt["kind"] in TAKEDOWN_FOOTINGS:
                tv.setdefault("links", []).append(lk)
            elif tgt["kind"] in MODEL_WALLS:
                sp = num("spacing") if kind in TAKEDOWN_BEAMS else 0
                if sp > 0:
                    (wx1, wy1), (wx2, wy2) = cs[0][1]["p1"], cs[0][1]["p2"]
                    wl_ = math.hypot(wx2 - wx1, wy2 - wy1)
                    cover = wl_
                    rw = str(v.get("at_row") or "").strip()
                    try:
                        cover = min(abs(float(rw)), wl_) if rw else wl_
                    except ValueError:
                        pass
                    lk.update(mode="line", spacing_in=sp, cover_ft=round(cover, 4))
                rows = tv.setdefault("loads", [])
                if not any(isinstance(r, dict) and isinstance(r.get("link"), dict) and r["link"].get("src") == lk["src"] and r["link"].get("support") == lk["support"] for r in rows):
                    rows.append(dict(case="D", P="0", label="", link=lk))
            else:
                if tgt["kind"] in TAKEDOWN_BEAMS:
                    sp = num("spacing") if kind in TAKEDOWN_BEAMS else 0
                    if sp > 0:
                        lk.update(mode="line", spacing_in=sp, x="")
                        rw = str(v.get("at_row") or "").strip()
                        if rw:                                       # the row covers only part of the beam it lands on
                            try:
                                W = float(rw)
                            except ValueError:
                                problems.append(f"{mark}: the row width '{rw}' is not a number"); W = None
                            if W:
                                (jx1, jy1), (jx2, jy2) = pl["p1"], pl["p2"]
                                jl = math.hypot(jx2 - jx1, jy2 - jy1)
                                right = ((jy2 - jy1) / jl, -(jx2 - jx1) / jl)      # to the right of the joist, looking from p1 to p2
                                tp = cs[0][1]
                                (bx1, by1), (bx2, by2) = tp["p1"], tp["p2"]
                                bl = math.hypot(bx2 - bx1, by2 - by1)
                                proj = (right[0] * (bx2 - bx1) + right[1] * (by2 - by1)) / bl
                                a0 = xs[0]
                                a1 = a0 + W * proj
                                lo, hi = max(0.0, min(a0, a1)), min(bl, max(a0, a1))
                                if hi - lo > 1e-6:
                                    lk.update(x=f"{lo:.3f}".rstrip("0").rstrip("."), x2=f"{hi:.3f}".rstrip("0").rstrip("."))
                    else:
                        lk["x"] = f"{xs[0]:.3f}".rstrip("0").rstrip(".")
                rows = tv.setdefault("loads", [])
                # a link picked by hand for the same member and support stays; the positional one is not added on top of it
                if any(isinstance(r, dict) and isinstance(r.get("link"), dict) and r["link"].get("src") == lk["src"] and r["link"].get("support") == lk["support"] for r in rows):
                    continue
                rows.append(dict(case="D", kind="point", mag="0", mag2="", x1=lk.get("x", ""), x2="", label="", link=lk) if tgt["kind"] in TAKEDOWN_BEAMS
                            else dict(case="D", P="0", label="", link=lk))
            made += 1
    for m, pl in placed:                                     # a wall that carries something but stands on nothing modelled
        if m["kind"] in MODEL_WALLS and any(isinstance(r, dict) and isinstance(r.get("link"), dict) for r in (m["values"].get("loads") or [])):
            mk = m["values"].get("mark")
            if not any(lk2.get("src") == mk for m2, _ in placed for lk2 in _links(m2)):
                problems.append(f"{mk}: loads bear on this wall but nothing in the model is under it (a footing line or a beam on level {pl['base']}); its loads stop here")
    out = takedown(project, ms)
    out["problems"] = problems + out["problems"]
    out["existing"] = on_existing
    out["placed"] = len(placed)
    out["made"] = made
    return out


def lateral_wind(project, members, wind_mark=None, load="wind"):
    """Wind to the wall lines of the building model, flexible diaphragms: at each level the wind load per foot of building width (the main
    system wind sheet between mid-story heights, the larger of its two directions) goes to the placed shear walls parallel to the wind by
    tributary width between wall lines; each wall also takes the shear of the wall on the same line above it, and its chord force. Writes
    the design shear, its source and the stacked chord force on each placed wall. Returns dict(members, lines, problems).
    load="seismic": the same distribution of the story forces of the project's Seismic Base Shear sheet (levels matched by name; the force
    at a level spread evenly over the building width, x the redundancy factor, x 0.7 for an ASD project)."""
    import copy, math
    from .. import wind as _wind
    ms = copy.deepcopy(members or [])
    mdl = (project or {}).get("model") or {}
    problems, lines = [], []
    levels = []
    for l in mdl.get("levels") or []:
        nm = str(l.get("name") or "").strip()
        try:
            levels.append((nm, float(str(l.get("elev")).replace(",", ""))))
        except (TypeError, ValueError):
            if nm:
                problems.append(f"Level {nm} needs an elevation for the wind distribution")
    if len(levels) < 2 or problems:
        return dict(members=members, lines=[], problems=problems or ["List at least two levels with elevations on the Project page"])
    if any(b[1] <= a[1] for a, b in zip(levels, levels[1:])):
        return dict(members=members, lines=[], problems=["The levels must be listed lowest first, each higher than the one before"])
    seis = load == "seismic"
    kind_src = "seismic_elf" if seis else "wind_mwfrs"
    winds = [m for m in ms if m.get("kind") == kind_src and (not wind_mark or (m.get("values") or {}).get("mark") == wind_mark)]
    if not winds:
        return dict(members=members, lines=[], problems=["The project needs a " + ("Seismic Base Shear and Story Forces sheet" if seis else "Wind Pressures, Main System sheet")])
    try:
        ws, _, _ = build(kind_src, winds[0]["values"], project)
    except Missing as e:
        return dict(members=members, lines=[], problems=[("The seismic sheet" if seis else "The wind sheet") + " is not complete: " + "; ".join(e.items)])
    except Exception as e:
        return dict(members=members, lines=[], problems=[("The seismic sheet" if seis else "The wind sheet") + f" stopped: {e}"])
    wmark = winds[0]["values"].get("mark") or ("seismic" if seis else "wind")
    asd = (project or {}).get("method") == "ASD"
    base_el = levels[0][1]
    if seis:
        story = {str(r_["name"]).strip(): float(r_["F"]) * 1000.0 for r_ in ws.seismic["rows"]}
        try:
            rho = float(winds[0]["values"].get("rho") or 1.0)
        except ValueError:
            rho = 1.0
        fac = (0.7 if asd else 1.0) * rho
        cases, top = [], levels[-1][1] - base_el
        for nm, _ in levels[1:]:
            if nm not in story:
                problems.append(f"Level {nm} is not a level of seismic sheet {wmark} (the names must match)")
    else:
        cases = ws.wind["cases"]
        top = max(max(r["top_w"], r["top_l"]) for r in cases)
        if levels[-1][1] - base_el > top + 0.05:
            problems.append(f"The top level is {levels[-1][1] - base_el:g} ft above the lowest; the wind sheet's walls are {top:g} ft high")
        fac = 0.6 if asd else 1.0
    placed = []
    for m in ms:
        if m.get("kind") not in MODEL_WALLS + TAKEDOWN_BEAMS + TAKEDOWN_POSTS:
            continue
        try:
            pl = model_place(project, m)
        except ValueError as e:
            problems.append(str(e)); continue
        if pl:
            placed.append((m, pl))
    placed += [(dict(kind="existing", values=dict(mark=nm + " (existing)")), epl) for nm, epl in model_existing(project)]
    walls = [(m, pl) for m, pl in placed if m["kind"] in MODEL_WALLS]
    if not walls:
        return dict(members=members, lines=[], problems=problems + ["No shear wall is placed in the model yet (use the placement boxes on the wall screens)"])
    carry = {}                                                # (direction, line position, level index) -> (shear, chord force, mark) coming down from above
    for li in range(len(levels) - 1, 0, -1):
        name, el = levels[li]
        z_lo = (levels[li - 1][1] + el) / 2 - base_el
        z_hi = top if li == len(levels) - 1 else (el + levels[li + 1][1]) / 2 - base_el
        z_hi = min(z_hi, top)
        if seis:
            if name not in story:
                continue
            w = None
        else:
            try:
                w = max(_wind.line_load(r, z_lo, min(z_hi, max(r["top_w"], r["top_l"])))["w"] for r in cases)   # each wind case to its own wall top
            except Exception as e:
                problems.append(f"Level {name}: {e}"); continue
        here = [(m, pl) for m, pl in placed if pl["level"] == name]
        for axis, other, label in ((0, 1, "X"), (1, 0, "Y")):   # wind along `axis`; wall lines parallel to it sit at positions on the `other` axis
            ws_here = [(m, pl) for m, pl in here if m["kind"] in MODEL_WALLS + ("existing",) and abs(pl["p2"][axis] - pl["p1"][axis]) >= abs(pl["p2"][other] - pl["p1"][other])]
            if not ws_here:
                if any(m["kind"] in MODEL_WALLS for m, pl in here):
                    problems.append(f"Level {name}: no placed wall runs in the {label} direction; the load in that direction is not distributed")
                continue
            ext = [c for m, pl in here for c in (pl["p1"][other], (pl["p2"] or pl["p1"])[other])]
            lo, hi = min(ext), max(ext)
            if seis:
                if hi - lo < 1e-6:
                    problems.append(f"Level {name}: the plan has no width across the {label} direction"); continue
                w = story[name] / (hi - lo)                  # the story force spread evenly over the building width
            groups = []
            for m, pl in sorted(ws_here, key=lambda t: (t[1]["p1"][other] + t[1]["p2"][other]) / 2):
                pos = (pl["p1"][other] + pl["p2"][other]) / 2
                if groups and abs(groups[-1][0] - pos) <= MODEL_TOL:
                    groups[-1][1].append((m, pl))
                else:
                    groups.append([pos, [(m, pl)]])
            if len(groups) < 2:
                problems.append(f"Level {name}, load in {label}: only one wall line; a flexible diaphragm needs a line each side (the whole load is put on that line)")
            for gi, (pos, grp) in enumerate(groups):
                a = lo if gi == 0 else (groups[gi - 1][0] + pos) / 2
                b = hi if gi == len(groups) - 1 else (pos + groups[gi + 1][0]) / 2
                trib = b - a
                V_level = w * fac * trib
                tot_len = sum(abs(pl["p2"][axis] - pl["p1"][axis]) for m, pl in grp) or 1.0
                for m, pl in grp:
                    share = abs(pl["p2"][axis] - pl["p1"][axis]) / tot_len
                    v = m["values"]
                    mark = v.get("mark") or "(no mark)"
                    up = carry.get((axis, round(pos / MODEL_TOL), li + 1))
                    V_up = up[0] * share if up else 0.0
                    V = V_level * share + V_up
                    src = ((f"sheet {wmark}, story force at {name} {story[name]:,.0f} lb over {hi - lo:g} ft" + (f" x {rho:g}" if rho != 1 else "") + (" x 0.7" if asd else "")
                            if seis else f"sheet {wmark}, level {name}, walls from {z_lo:g} to {z_hi:g} ft: {w:.1f} plf" + (" x 0.6" if asd else "")) + f" x {trib:g} ft tributary"
                           + (f" x {share:.2f} of the line" if share < 0.999 else "") + (f"; plus {V_up:,.0f} lb from {up[2]} above" if up else ""))
                    if m["kind"] == "existing":                  # existing construction takes its share; listed, not designed
                        lines.append(dict(level=name, wind=label, at=pos, wall=mark, trib=trib, V=V, from_above=V_up, T=None, load="seismic" if seis else "wind", existing=True))
                        key = (axis, round(pos / MODEL_TOL), li)
                        prev = carry.get(key)
                        carry[key] = ((prev[0] if prev else 0.0) + V, prev[1] if prev else 0.0, mark)
                        continue
                    v.update(V=str(round(V)), load="seismic" if seis else "wind", v_source=src)
                    if up and m["kind"] in ("shear_wall", "ftao_wall"):
                        v.update(above_T=str(round(up[1])), above_source=f"largest chord force of shear wall {up[2]}, {'seismic' if seis else 'wind'}, {'ASD' if asd else 'LRFD'}")
                    elif m["kind"] in ("shear_wall", "ftao_wall"):
                        v.pop("above_T", None); v.pop("above_source", None)
                    T = None
                    try:
                        sh, _, _ = build(m["kind"], v, project)
                        T = (max(s_.T for s_ in sh.wall.segments) if m["kind"] == "shear_wall" else sh.wall_T if m["kind"] == "ftao_wall" else sh.wall.T)
                    except Missing as e:
                        problems.append(f"{mark}: not complete: " + "; ".join(e.items))
                    except Exception as e:
                        problems.append(f"{mark}: {e}")
                    lines.append(dict(level=name, wind=label, at=pos, wall=mark, trib=trib, V=V, from_above=V_up, T=T, load="seismic" if seis else "wind"))
                    key = (axis, round(pos / MODEL_TOL), li)
                    prev = carry.get(key)
                    carry[key] = ((prev[0] if prev else 0.0) + V, max(prev[1] if prev else 0.0, T or 0.0), mark)
            # a wall above with no wall line under it at this level
            for (ax, kpos, lv), val in list(carry.items()):
                if ax == axis and lv == li + 1 and not any(round(g[0] / MODEL_TOL) == kpos for g in groups):
                    problems.append(f"Level {name}, load in {label}: no wall line under {val[2]} (its {val[0]:,.0f} lb is not carried down by this distribution)")
    return dict(members=ms, lines=lines, problems=problems)


def lateral_governing(project, members):
    """Wind and seismic both sent to the wall lines; each wall keeps the one that uses more of it. A wall's wind capacity is 1.4 times its
    seismic capacity (SDPWS-2021 4.1.4), so seismic governs where 1.4 x the seismic shear is more than the wind shear. Returns
    dict(members, lines (both loads, the governing one marked), problems)."""
    w, e = lateral_wind(project, members, load="wind"), lateral_wind(project, members, load="seismic")
    if not w["lines"] or not e["lines"]:
        one = w if w["lines"] else e
        probs = w["problems"] + [p_ for p_ in e["problems"] if p_ not in w["problems"]]
        return dict(members=one["members"], lines=[dict(l, governs=True) for l in one["lines"]], problems=probs)
    Vw, Ve = {l["wall"]: l["V"] for l in w["lines"]}, {l["wall"]: l["V"] for l in e["lines"]}
    out, lines = [], []
    for mw, me in zip(w["members"], e["members"]):
        mark = (mw.get("values") or {}).get("mark")
        out.append(me if (mark in Ve and 1.4 * Ve[mark] > Vw.get(mark, 0.0)) else mw)
    for l in w["lines"] + e["lines"]:
        seis_gov = 1.4 * Ve.get(l["wall"], 0.0) > Vw.get(l["wall"], 0.0)
        lines.append(dict(l, governs=(l["load"] == "seismic") == seis_gov))
    lines.sort(key=lambda l: (l["wall"], l["load"]))
    return dict(members=out, lines=lines, problems=w["problems"] + [p_ for p_ in e["problems"] if p_ not in w["problems"]])


def _slopes(placed):
    """Sloped members of the model. A beam may carry "Left end above the level" / "Right end above the level" (at_dz1, at_dz2, ft); a member
    without them that sits on such a beam follows it. placed: [(member, place)]. Returns (off, ends): off(level, point, not_mark) = height
    above the level of the sloped beam through that plan point (0.0 when there is none); ends(member, place) = the two end offsets of a beam."""
    import math
    typed = []
    for m, pl in placed:
        v = m.get("values") or {}
        t1, t2 = str(v.get("at_dz1") or "").strip(), str(v.get("at_dz2") or "").strip()
        if pl.get("p2") and (t1 or t2) and m.get("kind") in TAKEDOWN_BEAMS:
            try:
                typed.append((v.get("mark"), pl["level"], pl["p1"], pl["p2"], float(t1 or 0), float(t2 or 0)))
            except ValueError:
                pass

    def off(level, q, not_mark=None):
        for mk, lv, a, b, d1, d2 in typed:
            if lv != level or mk == not_mark:
                continue
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-9:
                continue
            t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / L
            o = abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0])) / L
            if o <= MODEL_TOL and -MODEL_TOL <= t <= L + MODEL_TOL:
                return d1 + (d2 - d1) * min(max(t, 0.0), L) / L
        return 0.0

    def ends(m, pl):
        v = m.get("values") or {}
        mine = next((x for x in typed if x[0] == v.get("mark")), None)
        if mine:
            return mine[4], mine[5]
        return off(pl["level"], pl["p1"], v.get("mark")), off(pl["level"], pl["p2"], v.get("mark"))
    return off, ends


def model_view(project, members):
    """What the 3D view draws: every placed member as a line or a point in space (ft), with its mark and kind.
    dict(items=[dict(mark, kind, a=(x, y, z), b=(x, y, z) or None, type)], levels=[(name, elev)], problems=[...])."""
    mdl = (project or {}).get("model") or {}
    levels, problems = [], []
    for l in mdl.get("levels") or []:
        nm = str(l.get("name") or "").strip()
        try:
            levels.append((nm, float(str(l.get("elev")).replace(",", ""))))
        except (TypeError, ValueError):
            if nm:
                problems.append(f"Level {nm} needs an elevation for the 3D view")
    el = dict(levels)
    order = [n for n, _ in levels]
    items = []
    placed_all = []
    for m in members or []:
        try:
            pl_ = model_place(project, m)
        except ValueError:
            continue
        if pl_:
            placed_all.append((m, pl_))
    zoff, zends = _slopes(placed_all)
    for m, pl in placed_all:
        kind = m.get("kind")
        if kind not in TAKEDOWN_BEAMS + TAKEDOWN_POSTS + TAKEDOWN_FOOTINGS + MODEL_WALLS + FRAME_BRACES:
            continue
        mark = (m.get("values") or {}).get("mark") or ""
        if kind in TAKEDOWN_FOOTINGS:
            z = el.get(pl["base"], levels[0][1] if levels else 0.0)
            items.append(dict(mark=mark, kind=kind, type="footing", a=(*pl["p1"], z), b=(*pl["p2"], z) if pl.get("p2") else None))
            continue
        if pl["level"] not in el:
            continue
        z = el[pl["level"]]
        if kind in FRAME_BRACES:
            items.append(dict(mark=mark, kind=kind, type="brace", a=(*pl["p1"], el.get(pl["base"], levels[0][1])), b=(*pl["p2"], z + zoff(pl["level"], pl["p2"]))))
        elif kind in TAKEDOWN_POSTS:
            zb = el.get(pl["base"], levels[0][1])
            items.append(dict(mark=mark, kind=kind, type="column", a=(*pl["p1"], zb), b=(*pl["p1"], z + zoff(pl["level"], pl["p1"]))))
        elif kind in MODEL_WALLS:
            i = order.index(pl["level"])
            zb = levels[i - 1][1] if i > 0 else z - 9.0
            items.append(dict(mark=mark, kind=kind, type="wall", a=(*pl["p1"], z), b=(*pl["p2"], z), zb=zb))
        else:
            sp = 0.0
            try:
                sp = float(str((m.get("values") or {}).get("spacing") or 0))
            except ValueError:
                pass
            d1_, d2_ = zends(m, pl)
            items.append(dict(mark=mark, kind=kind, type="joist" if (kind == "ijoist" or sp > 0) else "beam", a=(*pl["p1"], z + d1_), b=(*pl["p2"], z + d2_)))
    for nm, epl in model_existing(project):                   # existing walls: grey panels from the level below to their top
        if epl["level"] in el:
            i = order.index(epl["level"])
            z = el[epl["level"]]
            items.append(dict(mark=nm, kind="existing", type="wall", existing=True, a=(*epl["p1"], z), b=(*epl["p2"], z), zb=levels[i - 1][1] if i > 0 else z - 9.0))
    return dict(items=items, levels=levels, problems=problems)


FRAME_BEAMS, FRAME_COLS = ("steel_beam",), ("steel_column", "hss_column")
FRAME_BRACES = ("tension_member", "angle_strut")


def _frame_section(kind, v):
    name = v.get("shape") or ""
    sec = None
    for get in ((shapes.hss, shapes.get, shapes.channel) if kind == "hss_column" else (shapes.get, shapes.channel, shapes.hss)):
        try:
            sec = get(name)
            break
        except Exception:
            continue
    if sec is None:
        raise ValueError(f"'{name}' is not in the shapes table")
    return dict(A=sec["A"], Ix=sec["Ix"], Iy=sec["Iy"], J=max(sec.get("J") or 0.0, 1e-3), W=sec.get("W") or 0.0)


def _model_frame_build(project, members, sway=False):
    """The placed steel framing as one space frame (frame3d.py): columns continuous, pinned at the base unless the column says fixed; beams
    pinned at their ends unless the beam end says moment connection, continuous over what carries them. sway=False: every joint at a level
    is held against sidesway (gravity analysis). Returns a dict with the frame and its loads by case (kips, inches), or dict(problems=...)."""
    import math
    from ..frame3d import Frame3D, Frame3DError
    mdl = (project or {}).get("model") or {}
    elev = {}
    for l in mdl.get("levels") or []:
        try:
            elev[str(l.get("name") or "").strip()] = float(str(l.get("elev")).replace(",", ""))
        except (TypeError, ValueError):
            pass
    problems, notes = [], []
    placed = []
    for m in members or []:
        if m.get("kind") not in FRAME_BEAMS + FRAME_COLS + (FRAME_BRACES if sway else ()):
            continue
        try:
            pl = model_place(project, m)
        except ValueError as e:
            problems.append(str(e)); continue
        if not pl:
            continue
        if pl["level"] not in elev or (m["kind"] in FRAME_COLS + FRAME_BRACES and pl["base"] not in elev):
            problems.append(f"{(m.get('values') or {}).get('mark')}: its level needs an elevation on the Project page"); continue
        placed.append((m, pl))
    left_out = sorted({(m.get("values") or {}).get("mark") or "(no mark)" for m in members or []
                       if m.get("kind") in TAKEDOWN_BEAMS + TAKEDOWN_POSTS and m.get("kind") not in FRAME_BEAMS + FRAME_COLS and (m.get("values") or {}).get("at_x1")})
    if left_out:
        notes.append("Wood members are not in the frame yet: " + ", ".join(left_out) + ". Loads they put on steel members stay as the takedown loads.")
    if not any(m["kind"] in FRAME_COLS for m, _ in placed) or not any(m["kind"] in FRAME_BEAMS for m, _ in placed):
        return dict(problems=problems + ["The frame needs at least one placed steel beam and one placed steel or HSS column"], notes=notes)
    in_frame = {(m.get("values") or {}).get("mark") for m, _ in placed}
    E_, G_, FT = 29000.0, 11200.0, 12.0
    fr = Frame3D()
    node_at = {}

    def node(x, y, z):
        key = (round(x / 0.05), round(y / 0.05), round(z / 0.05))
        if key not in node_at:
            node_at[key] = f"n{len(node_at) + 1}"
            fr.node(node_at[key], x * FT, y * FT, z * FT)
        return node_at[key]

    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    # points where something meets a beam at each level: beam support points and column tops and bases
    pts = {}
    beam_info = []
    for m, pl in placed:
        v = m["values"]
        if m["kind"] in FRAME_COLS:
            pts.setdefault(pl["level"], []).append(pl["p1"]); pts.setdefault(pl["base"], []).append(pl["p1"])
            continue
        if m["kind"] in FRAME_BRACES:
            pts.setdefault(pl["level"], []).append(pl["p2"]); pts.setdefault(pl["base"], []).append(pl["p1"])
            continue
        num = lambda key: float(str(v.get(key) or 0).replace(",", "") or 0)
        spans = [num("span")] + [float(t) for t in str(v.get("more_spans") or "").replace(";", ",").split(",") if t.strip()]
        sup_x = [num("oh_left")]
        for sp in spans:
            sup_x.append(sup_x[-1] + sp)
        Lt = sup_x[-1] + num("oh_right")
        (ax, ay), (bx, by) = pl["p1"], pl["p2"]
        Lm = math.hypot(bx - ax, by - ay)
        if abs(Lm - Lt) > max(0.1, 0.005 * Lt):
            problems.append(f"{v.get('mark')}: placed {Lm:.2f} ft long in the model, but its spans add up to {Lt:.2f} ft"); continue
        at = lambda t: (ax + (bx - ax) * t / Lm, ay + (by - ay) * t / Lm)
        beam_info.append((m, pl, sup_x, Lm, at))
        for x in sup_x:
            pts.setdefault(pl["level"], []).append(at(x))
    zoff, zends = _slopes(placed)
    sloped = False
    if problems:
        return dict(problems=problems, notes=notes)
    cases = []
    bearing, held = set(), set()
    # columns
    col_nodes, col_fixed, level_tops, beam_elems, level_of_node = {}, {}, {}, {}, {}
    for m, pl in placed:
        if m["kind"] not in FRAME_COLS:
            continue
        v = m["values"]
        try:
            sec = _frame_section(m["kind"], v)
        except ValueError as e:
            problems.append(f"{v.get('mark')}: {e}"); continue
        ztop = elev[pl["level"]] + zoff(pl["level"], pl["p1"])
        if ztop - elev[pl["base"]] < 0.5:
            problems.append(f"{v.get('mark')}: its top is not above its base"); continue
        nb, nt = node(*pl["p1"], elev[pl["base"]]), node(*pl["p1"], ztop)
        web_y = str(v.get("at_web") or "").strip().upper().startswith("Y")
        fr.member("col:" + v["mark"], nb, nt, E_, G_, sec["A"], sec["Ix"], sec["Iy"], sec["J"], up=(0.0, 1.0, 0.0) if web_y else None)
        col_nodes[v["mark"]] = (nb, nt, sec, ztop - elev[pl["base"]])
        col_fixed[v["mark"]] = _base_flags(v.get("at_base_fix"))
        held.add(nt)
        level_tops.setdefault(pl["level"], []).append((nt, pl["p1"]))
    # beams, cut at every point where something meets them
    beam_loads = []                                          # (element name, case, w kip/in.) and joint loads
    joint_loads = {}
    for m, pl, sup_x, Lm, at in beam_info:
        v = m["values"]
        try:
            sec = _frame_section(m["kind"], v)
        except ValueError as e:
            problems.append(f"{v.get('mark')}: {e}"); continue
        z = elev[pl["level"]]
        cuts = {0.0, Lm}
        cuts.update(sup_x)
        (ax, ay), (bx, by) = pl["p1"], pl["p2"]
        for q in pts.get(pl["level"], []):
            t = ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / Lm
            off = abs((q[0] - ax) * (by - ay) - (q[1] - ay) * (bx - ax)) / Lm
            if off <= MODEL_TOL and -MODEL_TOL <= t <= Lm + MODEL_TOL:
                cuts.add(min(max(t, 0.0), Lm))
        rows = []
        for r in v.get("loads") or []:
            lk = r.get("link") if isinstance(r, dict) else None
            if isinstance(lk, dict) and lk.get("src") in in_frame:
                continue                                     # the member above is in the frame; it brings this load itself
            try:
                mag = float(str(r.get("mag", "")).replace(",", ""))
            except ValueError:
                continue
            c = str(r.get("case") or "").strip()
            if not c:
                continue
            f_ = lambda key, dflt: (float(str(r.get(key)).replace(",", "")) if str(r.get(key) or "").strip() else dflt)
            if r.get("kind") == "point":
                x = f_("x1", None)
                if x is None:
                    continue
                cuts.add(min(max(x, 0.0), Lm)); rows.append((c, "point", mag, x, x))
            else:
                x1, x2 = f_("x1", 0.0), f_("x2", Lm)
                cuts.update((min(max(x1, 0.0), Lm), min(max(x2, 0.0), Lm))); rows.append((c, "uniform", mag, x1, x2))
        if str(v.get("self_weight", "")).lower() == "yes":
            rows.append(("D", "uniform", sec["W"] / 1000.0, 0.0, Lm))
        cl = sorted(cuts)
        cl = [c_ for i, c_ in enumerate(cl) if i == 0 or c_ - cl[i - 1] > 0.02]
        dz1, dz2 = zends(m, pl)
        sloped = sloped or abs(dz1) > 1e-9 or abs(dz2) > 1e-9
        names = [node(*at(t), z + dz1 + (dz2 - dz1) * t / Lm) for t in cl]
        for t, nd in zip(cl, names):
            held.add(nd)
            level_of_node[nd] = pl["level"]
        for i in range(len(cl) - 1):
            nm = f"bm:{v['mark']}:{i}"
            mom_i = str(v.get("at_fix_i") or "").strip().lower().startswith("moment") or sup_x[0] > 1e-6       # an overhang tip is a free end, not a pin
            mom_j = str(v.get("at_fix_j") or "").strip().lower().startswith("moment") or Lm - sup_x[-1] > 1e-6
            fr.member(nm, names[i], names[i + 1], E_, G_, sec["A"], sec["Ix"], sec["Iy"], sec["J"],
                      release_i=("my", "mz") if (i == 0 and not mom_i) else (), release_j=("my", "mz") if (i == len(cl) - 2 and not mom_j) else ())
            beam_elems.setdefault(v["mark"], []).append(nm)
            for c, kind_, mag, x1, x2 in rows:
                if kind_ == "uniform" and x1 <= cl[i] + 1e-6 and x2 >= cl[i + 1] - 1e-6:
                    beam_loads.append((nm, c, mag / FT))
        for c, kind_, mag, x1, x2 in rows:
            if c not in cases:
                cases.append(c)
            if kind_ == "point":
                nd = names[min(range(len(cl)), key=lambda i: abs(cl[i] - x1))]
                joint_loads.setdefault((nd, c), 0.0)
                joint_loads[(nd, c)] += mag
        for x in sup_x:                                      # a beam support with no column and no beam under it: taken as a bearing
            nd = names[min(range(len(cl)), key=lambda i: abs(cl[i] - x))]
            bearing.add((nd, v["mark"], x))
    # typed (unlinked) loads on columns go on at the top
    for mark, (nb, nt, sec, h) in col_nodes.items():
        v = next(m["values"] for m, _ in placed if m["values"].get("mark") == mark)
        for r in v.get("loads") or []:
            lk = r.get("link") if isinstance(r, dict) else None
            if isinstance(lk, dict) and lk.get("src") in in_frame:
                continue
            try:
                P = float(str(r.get("P", "")).replace(",", ""))
            except ValueError:
                continue
            c = str(r.get("case") or "").strip()
            if c:
                joint_loads[(nt, c)] = joint_loads.get((nt, c), 0.0) + P
                if c not in cases:
                    cases.append(c)
        if str(v.get("self_weight", "")).lower() == "yes":
            joint_loads[(nt, "D")] = joint_loads.get((nt, "D"), 0.0) + sec["W"] * h / 1000.0
            if "D" not in cases:
                cases.append("D")
    if problems:
        return dict(problems=problems, notes=notes)
    # supports: column bases pinned (twist held); levels held against sidesway; beam supports with nothing under them bear on a support
    members_at = {}
    for mm in fr.members:
        members_at.setdefault(mm.i, []).append(mm.name); members_at.setdefault(mm.j, []).append(mm.name)
    base_nodes = {nb for nb, nt, _, _ in col_nodes.values() if nb not in {t for _, t, _, _ in col_nodes.values()}}
    extra = []
    for nd, mark, x in sorted(bearing):
        carried = any(n.startswith("col:") for n in members_at.get(nd, [])) or len({n.split(":")[1] for n in members_at.get(nd, []) if n.startswith("bm:")}) > 1
        if not carried:
            extra.append((nd, mark, x))
    if not sway:
        for nd in held:
            fr.support(nd, (1, 1, 0, 0, 0, 0))
    for mark, (nb, nt, _, _) in col_nodes.items():
        if nb in base_nodes:
            fr.support(nb, col_fixed[mark])
    for nd, mark, x in extra:
        fr.support(nd, "fixed")
    if extra:
        notes.append("Taken as bearing on a support (nothing in the frame is under them): " + "; ".join(f"{mark} at {x:g} ft" for nd, mark, x in extra) + ".")
    if sloped:
        notes.append("Sloped beams are modelled at their slope; a column or beam that sits on one follows it. Loads typed per foot act per foot of member length.")
    # diagonal braces (sway runs only): pinned at both ends, axial force only
    braces = {}
    low = min(elev.values())
    for m, pl in placed:
        if m["kind"] not in FRAME_BRACES:
            continue
        v = m["values"]; mark = v.get("mark")
        try:
            name = str(v.get("shape") or "").strip()
            if name:
                pr = None
                for get in (shapes.angle, shapes.get, shapes.channel, shapes.hss):
                    try:
                        pr = get(name); break
                    except Exception:
                        continue
                if pr is None:
                    raise ValueError(f"'{name}' is not in the shapes table")
                A, I1, I2, J = pr["A"], pr.get("Ix") or 1.0, pr.get("Iy") or 1.0, max(pr.get("J") or 0.0, 1e-3)
            else:
                d = float(v.get("rod_d") or 0)
                if d <= 0:
                    raise ValueError("it needs a section or a rod diameter")
                pr, A = None, math.pi * d * d / 4
                I1 = I2 = math.pi * d ** 4 / 64; J = 2 * I1
        except (ValueError, TypeError) as e:
            problems.append(f"{mark}: {e}"); continue
        za, zb = elev[pl["base"]], elev[pl["level"]] + zoff(pl["level"], pl["p2"])
        ka = (round(pl["p1"][0] / 0.05), round(pl["p1"][1] / 0.05), round(za / 0.05)); kb = (round(pl["p2"][0] / 0.05), round(pl["p2"][1] / 0.05), round(zb / 0.05))
        if kb not in node_at or (ka not in node_at and abs(za - low) > 1e-6):
            problems.append(f"{mark}: an end of this brace is not on a placed column or beam of the frame"); continue
        new_base = ka not in node_at
        na, nb_ = node(*pl["p1"], za), node(*pl["p2"], zb)
        if new_base:
            fr.support(na, "fixed")                           # a brace that comes down to the foundation beside no column
        fr.member("br:" + mark, na, nb_, E_, G_, A, I1, I2, J, release_i=("my", "mz"), release_j=("my", "mz"))
        t_only = str(v.get("at_brace") or "").strip().lower()
        t_only = (m["kind"] == "tension_member") if not t_only else t_only.startswith("tension only")
        braces[mark] = dict(name="br:" + mark, A=A, pr=pr, kind=m["kind"], values=v, tension_only=t_only, L=math.dist(fr.nodes[na], fr.nodes[nb_]))
    return dict(fr=fr, cases=cases, joint_loads=joint_loads, beam_loads=beam_loads, col_nodes=col_nodes, extra=extra, notes=notes, problems=problems, placed=placed, braces=braces,
                level_tops=level_tops, beam_elems=beam_elems, level_of_node=level_of_node, elev=elev, FT=FT)


def model_frame(project, members):
    """Gravity analysis of the placed steel framing as one space frame, every level held against sidesway, each load case run alone. Returns
    the base reaction of every column by case beside the load the takedown put on that column, so the two methods check each other.
    dict(columns=[dict(mark, cases={case: (frame lb, takedown lb)})], supports=[...], notes=[...], problems=[...])."""
    from ..frame3d import Frame3DError
    B = _model_frame_build(project, members, sway=False)
    if "fr" not in B:
        return dict(columns=[], supports=[], notes=B.get("notes") or [], problems=B["problems"])
    fr, cases, joint_loads, beam_loads, col_nodes, extra, notes, problems, placed = (B[k_] for k_ in ("fr", "cases", "joint_loads", "beam_loads", "col_nodes", "extra", "notes", "problems", "placed"))
    out_cols = {mark: {} for mark in col_nodes}
    sup_out = {}
    for c in cases:
        nl = {}
        for (nd, cc), P in joint_loads.items():
            if cc == c:
                nl[nd] = (0, 0, -P, 0, 0, 0)
        ml = [(nm, "global", (0, 0, -w)) for nm, cc, w in beam_loads if cc == c]
        try:
            res = fr.solve(nl, ml)
        except Frame3DError as e:
            return dict(columns=[], supports=[], notes=notes, problems=[str(e).replace("frame: ", "").capitalize()])
        for mark, (nb, nt, sec, h) in col_nodes.items():
            qi, qj = res.ends["col:" + mark]
            out_cols[mark][c] = qi[0] * 1000.0               # axial force at the base, compression positive, lb
        for nd, mark, x in extra:
            sup_out.setdefault((mark, x), {})[c] = res.reactions[nd][2] * 1000.0
    cols = []
    for mark, by_case in out_cols.items():
        v = next(m["values"] for m, _ in placed if m["values"].get("mark") == mark)
        kip = True
        td = {}
        for r in v.get("loads") or []:
            try:
                td[str(r.get("case")).strip()] = td.get(str(r.get("case")).strip(), 0.0) + float(str(r.get("P", "")).replace(",", "")) * 1000.0
            except ValueError:
                pass
        if str(v.get("self_weight", "")).lower() == "yes":
            td["D"] = td.get("D", 0.0) + col_nodes[mark][2]["W"] * col_nodes[mark][3]
        cols.append(dict(mark=mark, cases={c: (by_case.get(c, 0.0), td.get(c, 0.0)) for c in cases}))
    return dict(columns=cols, supports=[dict(mark=k[0], x=k[1], cases=vv) for k, vv in sup_out.items()], notes=notes, problems=problems, cases=cases,
                size=dict(joints=len(fr.nodes), members=len(fr.members)))


def model_frame_sway(project, members):
    """The placed steel framing as a 3D frame free to sway, by the direct analysis method of AISC 360-22 Chapter C: second-order analysis
    (frame3d.py) with every stiffness x 0.8 (C2.3(a)), tau_b taken as 1.0 with a notional load of 0.003 of the gravity load at each level
    (C2.2b, C2.3(c)), added to the wind in the wind's direction and applied alone in each direction for the gravity combinations; ASD
    combinations are run at 1.6 times the loads and the results divided by 1.6 (C2.1(d)). Wind (load case W) comes from the project's main
    system wind sheet between mid-story heights, x the building width, shared to the column tops by tributary width. Returns
    dict(runs, levels=[drift rows], columns=[...], beams=[...], notes, problems)."""
    import math
    from .. import wind as _wind
    from ..frame3d import Frame3DError
    B = _model_frame_build(project, members, sway=True)
    if "fr" not in B:
        return dict(levels=[], columns=[], beams=[], notes=B.get("notes") or [], problems=B["problems"])
    fr, cases, joint_loads, beam_loads, col_nodes, notes, problems = (B[k_] for k_ in ("fr", "cases", "joint_loads", "beam_loads", "col_nodes", "notes", "problems"))
    method_ = (project or {}).get("method")
    cbs = combos(project or {}, [], method_)
    if not cbs:
        return dict(levels=[], columns=[], beams=[], notes=notes, problems=["Choose the design method and enter its load combinations on the Project page first"])
    alpha = 1.6 if method_ == "ASD" else 1.0
    elev, FT, level_tops, level_of_node = B["elev"], B["FT"], B["level_tops"], B["level_of_node"]
    order = sorted((nm for nm in level_tops), key=lambda nm: elev[nm])
    base_el = min(elev.values())
    mlen = {}
    for mm in fr.members:
        a_, b_ = fr.nodes[mm.i], fr.nodes[mm.j]
        mlen[mm.name] = math.dist(a_, b_)
        if mm.name.startswith("bm:"):
            level_of_node.setdefault(mm.i, level_of_node.get(mm.j))
    for mark, (nb, nt, _, _) in col_nodes.items():
        pl = next(pl for m, pl in B["placed"] if m["values"].get("mark") == mark)
        level_of_node.setdefault(nt, pl["level"])
    # wind force per level and direction, kips, strength level
    need_w = any(abs(cb.factors.get("W", 0.0)) > 0 for cb in cbs) and not any(
        m.get("kind") == "wind_free_roof" and str((m.get("values") or {}).get("model_axis") or "").strip().upper() in ("X", "Y") for m in members or [])
    wind_F = {}
    if need_w:
        winds = [m for m in members or [] if m.get("kind") == "wind_mwfrs"]
        if not winds:
            problems.append("The combinations use wind (W) but the project has no Wind Pressures, Main System sheet; wind is left out of this run")
            need_w = False
        else:
            try:
                ws, _, _ = build("wind_mwfrs", winds[0]["values"], project)
                wcases = ws.wind["cases"]
                top = max(max(r["top_w"], r["top_l"]) for r in wcases)
                lv_sorted = sorted(elev.items(), key=lambda t: t[1])
                for li, (nm, el_) in enumerate(lv_sorted):
                    if nm not in level_tops:
                        continue
                    z_lo = (lv_sorted[li - 1][1] + el_) / 2 - base_el if li > 0 else 0.0
                    z_hi = min(top, (el_ + lv_sorted[li + 1][1]) / 2 - base_el) if (li + 1 < len(lv_sorted) and lv_sorted[li + 1][0] in level_tops) else top
                    w = max(_wind.line_load(r, z_lo, max(z_hi, z_lo + 0.01))["w"] for r in wcases) / 1000.0     # kip per ft of width
                    xs = [p_[0] for _, p_ in level_tops[nm]]; ys = [p_[1] for _, p_ in level_tops[nm]]
                    wind_F[nm] = (w * (max(ys) - min(ys)), w * (max(xs) - min(xs)))     # force in X (width in Y), force in Y
                notes.append("Wind width at each level is the extent of the column lines; cladding beyond them is not counted.")
            except Exception as e:
                problems.append(f"The wind sheet could not be used: {e}"); need_w = False

    # open building: the free-roof sheet's cases as loads on the rafters (kip/in. at 1.0 W), each with the direction the wind travels
    fr_sets = []
    frees = [m for m in members or [] if m.get("kind") == "wind_free_roof" and str((m.get("values") or {}).get("model_axis") or "").strip().upper() in ("X", "Y")]
    if frees and any(abs(cb.factors.get("W", 0.0)) > 0 for cb in cbs):
        fv = frees[0]["values"]
        try:
            fs_, _, _ = build("wind_free_roof", fv, project)
            fd = fs_.free_roof
            roof_kind = str(fv.get("roof") or "")
            if not (roof_kind.startswith("monoslope") or roof_kind.startswith("pitched")) or not fd.get("across"):
                raise ValueError("only monoslope and pitched roofs within the range of Figures 27.3-4 and 27.3-5 are put on the frame")
            ax = "XY".index(str(fv["model_axis"]).strip().upper()); ot = 1 - ax
            tan_t = math.tan(math.radians(float(fv.get("theta") or 0)))
            low_small = not str(fv.get("model_low") or "").startswith("larger")
            raf = []                                          # (mark, position across, element list)
            for m, pl in B["placed"]:
                mk = m["values"].get("mark")
                if mk in B["beam_elems"] and pl["p2"] and abs(pl["p1"][ot] - pl["p2"][ot]) <= MODEL_TOL and abs(pl["p1"][ax] - pl["p2"][ax]) > MODEL_TOL:
                    raf.append((mk, pl["p1"][ot], B["beam_elems"][mk], min(pl["p1"][ax], pl["p2"][ax]), max(pl["p1"][ax], pl["p2"][ax])))
            if not raf:
                raise ValueError("no placed steel beam runs along the roof dimension L")
            c0, c1 = min(r_[3] for r_ in raf), max(r_[4] for r_ in raf)
            cm = (c0 + c1) / 2
            pos = sorted({round(r_[1], 3) for r_ in raf})
            extra = max(0.0, (float(fv.get("width") or 0) - (pos[-1] - pos[0])) / 2) if str(fv.get("width") or "").strip() else 0.0
            trib = {}
            for i_, q in enumerate(pos):
                trib[q] = ((q - pos[i_ - 1]) / 2 if i_ else extra) + ((pos[i_ + 1] - q) / 2 if i_ < len(pos) - 1 else extra)
            hmean = float(fv.get("h") or 0)

            def across_set(row):
                if roof_kind.startswith("monoslope"):
                    travel = (-1 if low_small else 1) if row["gamma"] == 0 else (1 if low_small else -1)     # gamma = 0: from the high edge toward the low edge
                    high = 1 if low_small else -1                                                           # downward pressure pushes the roof toward the high side
                else:
                    travel, high = (1 if row["gamma"] == 0 else -1), None
                loads = []
                for mk, q, els, _, _ in raf:
                    for e_ in els:
                        mm = by_elem[e_]
                        a_, b_ = fr.nodes[mm.i][ax] / FT, fr.nodes[mm.j][ax] / FT
                        lo_, hi_ = min(a_, b_), max(a_, b_)
                        if hi_ - lo_ < 1e-9:
                            continue
                        # share of the element on the windward half (the half the wind reaches first)
                        on_small = max(0.0, min(hi_, cm) - lo_) / (hi_ - lo_)
                        fw_ = on_small if travel > 0 else 1 - on_small
                        pw = fw_ * row["pW"] + (1 - fw_) * row["pL"]
                        w = pw * trib[round(q, 3)] / 1000.0 / FT              # kip/in., plus = toward the roof surface
                        rise = (fr.nodes[mm.j][2] - fr.nodes[mm.i][2]) * (1 if b_ > a_ else -1)      # rise of this element toward the larger coordinate
                        if abs(rise) > 1e-6:                                  # modelled at its slope: the pressure acts normal to it
                            ang = math.atan2(rise, (hi_ - lo_) * FT)
                            hz, w = w * math.sin(ang), w * math.cos(ang)
                        elif high is not None:
                            hz = w * tan_t * high
                        else:                                                # pitched: each slope is pushed toward the ridge side it faces away from
                            hz = (fw_ * row["pW"] * travel - (1 - fw_) * row["pL"] * travel) * tan_t * trib[round(q, 3)] / 1000.0 / FT
                        g = [0.0, 0.0, -w]; g[ax] = hz
                        loads.append((e_, tuple(g)))
                side = ("from the high side" if row["gamma"] == 0 else "from the low side") if roof_kind.startswith("monoslope") else ("in +" if travel > 0 else "in -") + "XY"[ax]
                loads += drag(ax, travel)
                hsum = sum(g[ax] * math.dist(fr.nodes[by_elem[e_].i], fr.nodes[by_elem[e_].j]) for e_, g in loads)
                push = (1 if hsum > 0 else -1) if abs(hsum) > 1e-9 else travel      # the notional load goes the way the frame is pushed (the destabilizing direction, Sect. C2.2b)
                return dict(axis=ax, sign=push, loads=loads, label=f"wind across the roof {side}, Case {row['case']}")

            by_elem = {mm.name: mm for mm in fr.members}
            fascia = float(fv.get("fascia") or 0) if str(fv.get("fascia") or "").strip() else 0.0
            qf = fd["factor"]                                 # qh Kd G, psf
            col_drag = []                                     # (element, force per inch of height at Cf, by wind axis)
            for m, pl in B["placed"]:
                mk = m["values"].get("mark")
                if mk not in col_nodes:
                    continue
                pr_ = None
                for get in (shapes.hss, shapes.get):
                    try:
                        pr_ = get(m["values"].get("shape") or ""); break
                    except Exception:
                        continue
                if pr_ is None:
                    continue
                Hc = col_nodes[mk][3]
                if pr_.get("OD"):
                    Dc = pr_["OD"] / 12.0
                    sect = "round_slow" if Dc * math.sqrt(fd["qh"]) <= 2.5 else "round_smooth"
                    wide = Dc
                else:
                    dims = [pr_.get(k) for k in ("B", "Ht", "d", "bf") if pr_.get(k)]
                    Dc, wide, sect = min(dims) / 12.0, max(dims) / 12.0, "square"
                cf = _wind.other_cf(sect, Hc / Dc)
                col_drag.append(("col:" + mk, qf * cf * wide / 1000.0 / FT, cf))

            def drag(axis_, travel_):
                """Wind on the columns (Figure 29.4-1) and on the roof-edge fascia (Figure 29.4-2, flat-sided member), Eq. 29.4-1 with qh, along the wind."""
                out_ = []
                for e_, w_, _ in col_drag:
                    g = [0.0, 0.0, 0.0]; g[axis_] = w_ * travel_
                    out_.append((e_, tuple(g)))
                if fascia > 0:
                    if axis_ == ax:                           # wind across the roof: the two eave edges, to every rafter by its tributary width
                        for mk, q, els, r0, r1 in raf:
                            F_ = 2 * qf * FLAT_CF * fascia * trib[round(q, 3)] / 1000.0
                            for e_ in els:
                                g = [0.0, 0.0, 0.0]; g[axis_] = F_ / ((r1 - r0) * FT) * travel_
                                out_.append((e_, tuple(g)))
                    else:                                     # wind along the eaves: each end edge onto its end rafter
                        for mk, q, els, r0, r1 in raf:
                            if round(q, 3) in (pos[0], pos[-1]):
                                for e_ in els:
                                    g = [0.0, 0.0, 0.0]; g[axis_] = qf * FLAT_CF * fascia / 1000.0 / FT * travel_ * (2 if len(pos) == 1 else 1)
                                    out_.append((e_, tuple(g)))
                return out_

            FLAT_CF = _wind.FLAT_MEMBER_CF
            for row in fd["across"]:
                fr_sets.append(across_set(row))
            tot = fd.get("totals") or {}
            if tot.get("F_min"):                              # Sect. 27.1.5: not less than 16 psf x Af, as a case of its own in each direction across the roof
                wsum = sum(trib.values())
                for travel in (1, -1):
                    loads = []
                    for mk, q, els, r0, r1 in raf:
                        for e_ in els:
                            g = [0.0, 0.0, 0.0]; g[ax] = tot["F_min"] / 1000.0 * trib[round(q, 3)] / wsum / ((r1 - r0) * FT) * travel
                            loads.append((e_, tuple(g)))
                    fr_sets.append(dict(axis=ax, sign=travel, loads=loads, label=f"minimum wind across the roof in {'+' if travel > 0 else '-'}{'XY'[ax]} (Sect. 27.1.5)"))
            for travel in ((1, -1) if fd.get("parallel") else ()):
                for case in ("A", "B"):
                    loads = []
                    for mk, q, els, _, _ in raf:
                        dist_ = (q - pos[0] + extra) if travel > 0 else (pos[-1] + extra - q)
                        zone = next((z for z in fd["parallel"] if z["x0"] - 1e-9 <= dist_ and (z["x1"] is None or dist_ < z["x1"])), fd["parallel"][-1])
                        w = zone["p" + case] * trib[round(q, 3)] / 1000.0 / FT
                        loads += [(e_, (0.0, 0.0, -w)) for e_ in els]
                    loads += drag(ot, travel)
                    fr_sets.append(dict(axis=ot, sign=travel, loads=loads, label=f"wind along the eaves in {'+' if travel > 0 else '-'}{'XY'[ot]}, Case {case}"))
            need_w = False
            notes.append(f"Open building: the wind cases of sheet {fv.get('mark')} are put on the beams that run along the roof dimension L, by tributary width "
                         f"({', '.join(f'{trib[q]:g}' for q in pos)} ft): for wind across the roof the windward-half and leeward-half net pressures of each case and direction, "
                         "normal to the roof (the roof is modelled level; the horizontal part is pressure x tan(roof angle)); for wind along the eaves the Figure 27.3-7 "
                         "pressure by the beam's distance from the windward edge. Wind loads typed on those members under load case W are left out of these runs. "
                         "Wind on the columns: F = qh Kd G Cf Af (Eq. 29.4-1) with Cf from Figure 29.4-1 by each column's height / width ("
                         + ", ".join(sorted({f"{c_:.2f}" for _, _, c_ in col_drag})) + "), along the wind"
                         + (f"; on the fascia, {fascia:g} ft deep on both roof edges that face the wind, Cf = 2.0 (Figure 29.4-2, flat-sided member), the far edge not taken as shielded" if fascia > 0 else "; no fascia depth is entered, so none on the roof edges")
                         + ". qh is used for both. The Sect. 27.1.5 minimum (16 psf x Af of the sheet) is run as a case of its own in each direction across the roof. "
                         "Not included: wind on purlins and other framing below the roof.")
        except Exception as e:
            problems.append(f"The open-building wind sheet could not be put on the frame: {e}")
            fr_sets = []
    # unbalanced snow on pitched rafters (ASCE/SEI 7-22 Sect. 7.6.1, from the project's roof snow sheet), as arrangements of load case S
    us_sets, unb_elems = [], set()
    snows = [m for m in members or [] if m.get("kind") == "snow"]
    if snows and any(abs(cb.factors.get("S", 0.0)) > 0 for cb in cbs):
        try:
            rs = build("snow", snows[0]["values"], project)[0].snow
        except Exception:
            rs = None
        if rs is not None and rs.unbalanced and rs.balanced > 0:
            by_el = {mm.name: mm for mm in fr.members}
            S_on = {}
            for nm_, c, w in beam_loads:
                if c == "S":
                    S_on[nm_] = S_on.get(nm_, 0.0) + w
            lines = {}                                        # (axis along the rafter, position across) -> sloped elements carrying S
            for mk, els in B["beam_elems"].items():
                for e_ in els:
                    mm = by_el[e_]
                    a_, b_ = fr.nodes[mm.i], fr.nodes[mm.j]
                    if abs(b_[2] - a_[2]) < 1e-6 or e_ not in S_on:
                        continue
                    ax_ = 0 if abs(b_[0] - a_[0]) > abs(b_[1] - a_[1]) else 1
                    lines.setdefault((ax_, round(a_[1 - ax_] / FT / MODEL_TOL)), []).append(e_)
            u = rs.unbalanced
            for lee in (1, -1):                               # the leeward side is toward the larger (+1) or the smaller (-1) coordinate
                loads, axis_ = [], None
                for (ax_, _), els in lines.items():
                    ends = [fr.nodes[by_el[e_].i] for e_ in els] + [fr.nodes[by_el[e_].j] for e_ in els]
                    top = max(ends, key=lambda q: q[2])
                    if top[2] - min(q[2] for q in ends) < 1e-6 or all(abs(q[ax_] - top[ax_]) < 1e-6 or (q[ax_] - top[ax_]) > 0 for q in ends) or \
                            all(abs(q[ax_] - top[ax_]) < 1e-6 or (q[ax_] - top[ax_]) < 0 for q in ends):
                        continue                              # no ridge on this line (a single slope)
                    axis_ = ax_
                    xr_ = top[ax_] / FT
                    for e_ in els:
                        mm = by_el[e_]
                        x1_, x2_ = sorted((fr.nodes[mm.i][ax_] / FT, fr.nodes[mm.j][ax_] / FT))
                        mid = (x1_ + x2_) / 2
                        if (mid - xr_) * lee > 0:             # leeward: ps, plus the surcharge within its extent from the ridge
                            d1, d2 = abs(x1_ - xr_), abs(x2_ - xr_)
                            lo_, hi_ = min(d1, d2), max(d1, d2)
                            inside = max(0.0, min(hi_, u["extent"]) - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.0
                            p_ = u["leeward"] + u["surcharge"] * inside
                        else:
                            p_ = u["windward"]
                        loads.append((e_, (0.0, 0.0, -S_on[e_] * p_ / rs.balanced)))
                if loads:
                    us_sets.append(dict(axis=axis_, loads=loads, case="S", label=f"unbalanced snow, leeward side toward {'+' if lee > 0 else '-'}{'XY'[axis_]}"))
                    unb_elems.update(e_ for e_, _ in loads)
            if us_sets:
                notes.append(f"Unbalanced snow (ASCE/SEI 7-22 Sect. 7.6.1, sheet {snows[0]['values'].get('mark')}): on the pitched rafters, windward side {u['windward']:.1f} psf and leeward side "
                             f"{u['leeward']:.1f} psf" + (f" plus {u['surcharge']:.1f} psf within {u['extent']:.1f} ft of the ridge" if u["surcharge"] else "") +
                             f", each way, in place of the balanced load in every combination with S that has no wind. The S load typed on each rafter is taken as the balanced "
                             f"{rs.balanced:.1f} psf x its tributary width. Unbalanced snow with wind in the same combination is not run.")
    need_e = any(abs(cb.factors.get("E", 0.0)) > 0 for cb in cbs)
    eq_F, eq_mark = {}, ""
    seis = [m for m in members or [] if m.get("kind") == "seismic_elf"]
    if seis:
        try:
            es, _, _ = build("seismic_elf", seis[0]["values"], project)
            story = {str(r_["name"]).strip(): float(r_["F"]) for r_ in es.seismic["rows"]}
            eq_mark = seis[0]["values"].get("mark") or "seismic"
            for lv in level_tops:
                if lv in story:
                    eq_F[lv] = story[lv]
                elif need_e:
                    problems.append(f"Level {lv} is not a level of seismic sheet {eq_mark} (the names must match); it gets no seismic force")
        except Exception as e:
            if need_e:
                problems.append(f"The seismic sheet could not be used: {e}")
    elif need_e:
        problems.append("The combinations use seismic load (E) but the project has no Seismic Base Shear and Story Forces sheet; seismic is left out of this run")
    if need_e and eq_F:
        notes.append(f"Seismic (load case E): the story forces of sheet {eq_mark} at each level, shared to the column tops by tributary width, in each direction; the "
                     "redundancy factor and the vertical effect are in the combination factors.")
    if any(abs(cb.factors.get("Em", 0.0)) > 0 for cb in cbs):
        notes.append("Combinations with overstrength (load case Em) are run on the frame for gravity only; Em applies to particular members and is not applied to the whole frame.")

    def spread(level, axis, total):
        """`total` kips in direction `axis` (0 = X, 1 = Y) shared to the column tops of a level by tributary width across the wind."""
        tops = level_tops[level]
        other = 1 - axis
        rows = {}
        for nd, p_ in tops:
            rows.setdefault(round(p_[other] / MODEL_TOL), []).append(nd)
        keys = sorted(rows)
        pos = [k_ * MODEL_TOL for k_ in keys]
        out = {}
        span = (pos[-1] - pos[0]) if len(pos) > 1 else 0.0
        for i_, k_ in enumerate(keys):
            if span <= 0:
                share = 1.0
            else:
                lo_ = pos[0] if i_ == 0 else (pos[i_ - 1] + pos[i_]) / 2
                hi_ = pos[-1] if i_ == len(pos) - 1 else (pos[i_] + pos[i_ + 1]) / 2
                share = (hi_ - lo_) / span
            for nd in rows[k_]:
                out[nd] = out.get(nd, 0.0) + total * share / len(rows[k_])
        return out

    # member strengths for the checks from the frame's forces (kips, kip-in.)
    from .. import steel_column as _sc, steel_beam as _sb, steel_beamcol as _bc
    strength, kinds = {}, {}
    for m, pl in B["placed"]:
        v = m["values"]; mark = v.get("mark")
        if not (mark in col_nodes or mark in B["beam_elems"]):
            continue
        try:
            Fy = float(v.get("Fy") or 0)
            if Fy <= 0:
                raise ValueError("no Fy on its screen")
            pr = None
            for get in ((shapes.hss, shapes.get, shapes.channel) if m["kind"] == "hss_column" else (shapes.get, shapes.channel, shapes.hss)):
                try:
                    pr = get(v.get("shape") or ""); break
                except Exception:
                    continue
            if mark in col_nodes:
                L = col_nodes[mark][3] * 12.0
                strength[mark] = dict(Pc=_sc.check(pr, Fy, L, L, method=method_).P_avail, Mcx=_sb.check(pr, Fy, L, 1.0, method_).M_avail,
                                      Mcy=_bc.weak_axis_flexure(pr, Fy, method_).available, Pt=Fy * pr["A"] * (0.9 if method_ == "LRFD" else 1 / 1.67), L=L)
            else:
                Ltot = sum(mlen[e_] for e_ in B["beam_elems"][mark])
                br = str(v.get("bracing") or "")
                Lb_pos = 0.01
                if br.startswith("at"):
                    try:
                        pts = sorted(set([0.0, Ltot / 12.0] + [float(t) for t in str(v.get("brace_pts") or "").replace(",", " ").split()]))
                        Lb_pos = max(b_ - a_ for a_, b_ in zip(pts, pts[1:])) * 12.0
                    except ValueError:
                        Lb_pos = Ltot
                Lb_neg = max(mlen[e_] for e_ in B["beam_elems"][mark]) if not br.startswith("at") else Lb_pos
                cp, cn = _sb.check(pr, Fy, Lb_pos, 1.0, method_), _sb.check(pr, Fy, Lb_neg, 1.0, method_)
                strength[mark] = dict(Mpos=cp.M_avail, Mneg=cn.M_avail, V=cp.V_avail, Pc=_sc.check(pr, Fy, Ltot, max(Lb_pos, Lb_neg), method=method_).P_avail,
                                      Pt=Fy * pr["A"] * (0.9 if method_ == "LRFD" else 1 / 1.67), Lb_neg=Lb_neg, Lb_pos=Lb_pos, pr=pr, Fy=Fy, neg={}, pts=br.startswith("at"))
        except Exception as e:
            notes.append(f"{mark}: not checked from the frame forces ({str(e) or type(e).__name__}).")
    if strength:
        notes.append("Member checks from the frame forces: AISC 360-22 Eq. H1-1 at every station of every run, with the second-order forces and effective length = the "
                     "member length (Sect. C3). Columns: unbraced over their full height about both axes, Cb = 1.0. Beams: the screen's bracing for the top flange; where the "
                     "bottom flange is in compression the unbraced length is the distance between framing points with Cb by Eq. F1-1 from that run's moments; beam axial strength "
                     "with the same length about the weak axis. Tension with bending by Sect. H1.2, yielding only.")

    braces, brace_res = B["braces"], {}
    phi_t = (lambda y, u: min(0.9 * y, 0.75 * u)) if method_ == "LRFD" else (lambda y, u: min(y / 1.67, u / 2.0))
    for mark, b in braces.items():
        v = b["values"]
        b["Pt"] = b["Pc"] = None
        try:
            Fy = float(v.get("Fy") or 0)
            if Fy <= 0:
                raise ValueError("no Fy on its screen")
            if b["pr"] is None:                              # threaded rod: body yielding and 0.75 Fu Ab at the threads
                Fu = float(v.get("Fu") or 0)
                b["Pt"] = phi_t(Fy * b["A"], 0.75 * Fu * b["A"]) if Fu > 0 else Fy * b["A"] * (0.9 if method_ == "LRFD" else 1 / 1.67)
            else:
                b["Pt"] = Fy * b["A"] * (0.9 if method_ == "LRFD" else 1 / 1.67)
            if not b["tension_only"]:
                if b["kind"] == "angle_strut":
                    sh, _, _ = build("angle_strut", dict(v, length=str(b["L"] / 12.0), loads=[dict(case=next(iter(cbs[0].factors)), P="0.001", label="")]), project)
                    b["Pc"] = next(r_.capacity for r_ in sh.rows if r_.capacity)
                elif b["pr"] is not None:
                    b["Pc"] = _sc.check(b["pr"], Fy, b["L"], b["L"], method=method_).P_avail
        except Exception as e:
            notes.append(f"{mark}: not checked from the frame forces ({str(e) or type(e).__name__}).")
    if braces:
        notes.append("Braces are pinned at both ends and carry axial force only; their own weight is left out. Tension-only braces are taken out of any run that would put them in "
                     "compression, and the run is repeated. Brace tension is checked against yielding of the gross section (rods: also 0.75 Fu Ab); net section rupture and the "
                     "end connections are on the brace's own screen.")
    by_name = {mm.name: mm for mm in fr.members}
    any_tension_only = any(b["tension_only"] for b in braces.values())
    if any_tension_only:
        notes.append("With tension-only braces each run also carries 0.0001 of the gravity load across its direction, so that one brace of each cross line is working.")

    def solve_run(nl, grav_members, sf=0.8, second=True):
        """First- and second-order solutions. A tension-only brace works only while it is being stretched: the set of working braces is found by
        repeating the first-order solution (a slack brace keeps a millionth of its area, so the sign of its strain can still be read), then
        confirmed on the second-order solution."""
        SL = 1e-6
        slack = set()
        tens = [mark for mark, b in braces.items() if b["tension_only"]]

        def setA():
            for mark, b in braces.items():
                by_name[b["name"]].A = b["A"] * (SL if mark in slack else 1.0)
        try:
            r1 = r2 = None
            for stage in (("first", "second") if second else ("first",)):
                for _ in range(12):
                    setA()
                    r1 = fr.solve(nl, grav_members, second_order=False, stiffness_factor=sf)
                    rr = r1
                    if stage == "second":
                        r2 = rr = fr.solve(nl, grav_members, second_order=True, n_sub=4, stiffness_factor=sf)
                    want = {mark for mark in tens if rr.stations[braces[mark]["name"]][0][0][0] > 0}       # shortening: slack
                    if want == slack:
                        break
                    slack = want
            return r1, r2, slack
        finally:
            for mark, b in braces.items():
                by_name[b["name"]].A = b["A"]

    def h1(P, Pc, Pt, Mx, Mcx, My=0.0, Mcy=None):
        r_ = (P / Pc) if P >= 0 else (-P / Pt)
        mm_ = abs(Mx) / Mcx + ((abs(My) / Mcy) if Mcy else 0.0)
        return (r_ + 8.0 / 9.0 * mm_, "H1-1a") if r_ >= 0.2 else (r_ / 2 + mm_, "H1-1b")

    drift, col_res, beam_res, worst_ratio, runs, unchecked = {}, {}, {}, 0.0, 0, set()
    free_elems = {e_ for st_ in fr_sets for e_, _ in st_["loads"]}
    audit = []
    for cb in cbs:
        fW = cb.factors.get("W", 0.0) if need_w else 0.0
        fE = cb.factors.get("E", 0.0) if eq_F else 0.0
        grav_nodes, grav_members, Y = {}, [], {nm: 0.0 for nm in order}
        for (nd, c), P in joint_loads.items():
            f_ = cb.factors.get(c, 0.0) * alpha
            if f_:
                grav_nodes[nd] = grav_nodes.get(nd, 0.0) + f_ * P
                if level_of_node.get(nd) in Y:
                    Y[level_of_node[nd]] += f_ * P
        wsets = fr_sets if (fr_sets and abs(cb.factors.get("W", 0.0)) > 0) else None
        grav_noS = []
        for nm_, c, w in beam_loads:
            f_ = cb.factors.get(c, 0.0) * alpha
            if c == "W" and wsets and nm_ in free_elems:
                continue
            if f_:
                grav_members.append((nm_, "global", (0, 0, -f_ * w)))
                if not (c == "S" and nm_ in unb_elems):
                    grav_noS.append(grav_members[-1])
                lv = level_of_node.get(next(mm for mm in fr.members if mm.name == nm_).i)
                if lv in Y:
                    Y[lv] += f_ * w * mlen[nm_]
        dirs = [(st_["axis"], st_["sign"], st_) for st_ in wsets] if wsets else [(0, 1, None), (0, -1, None), (1, 1, None), (1, -1, None)]
        if us_sets and abs(cb.factors.get("S", 0.0)) > 0 and not wsets:
            dirs = list(dirs) + [(u_["axis"], sg_, u_) for u_ in us_sets for sg_ in (1, -1)]
        for axis, sign, wset in dirs:
            wcase = (wset or {}).get("case", "W")
            gm_run = (grav_noS if wcase == "S" else grav_members) + ([(e_, "global", tuple(cb.factors[wcase] * alpha * g_ for g_ in g)) for e_, g in wset["loads"]] if wset else [])
            nl = {nd: [0, 0, -P, 0, 0, 0] for nd, P in grav_nodes.items()}
            for lv in order:
                lat = 0.003 * max(Y[lv], 0.0) + (abs(fW) * alpha * wind_F[lv][axis] if (fW and lv in wind_F) else 0.0) + abs(fE) * alpha * eq_F.get(lv, 0.0)
                for nd, share in spread(lv, axis, lat * sign).items():
                    nl.setdefault(nd, [0, 0, 0, 0, 0, 0])[axis] += share
                if any_tension_only:                          # a nudge across the run so one brace of each cross line engages
                    for nd, share in spread(lv, 1 - axis, 0.0001 * max(Y[lv], 0.0)).items():
                        nl.setdefault(nd, [0, 0, 0, 0, 0, 0])[1 - axis] += share
            nl = {nd: tuple(v_) for nd, v_ in nl.items()}
            label = f"{cb.name}, " + ((wset["label"] + (f", notional load in {'+' if sign > 0 else '-'}{'XY'[axis]}" if wcase == "S" else "")) if wset else
                                      ("wind" if fW else "seismic" if fE else "notional load") + f" in {'+' if sign > 0 else '-'}{'XY'[axis]}")
            try:
                r1, r2, slack = solve_run(nl, gm_run)
            except Frame3DError as e:
                msg = str(e).replace("frame: ", "")
                return dict(levels=[], columns=[], beams=[], braces=[], notes=notes, problems=problems + [f"{label}: {msg}. A frame free to sway needs braces, moment connections, fixed column bases, or a mix, in each direction."])
            runs += 1
            audit.append(dict(run=label, Rx=sum(float(v_[0]) for v_ in r2.reactions.values()) / alpha, Ry=sum(float(v_[1]) for v_ in r2.reactions.values()) / alpha,
                              Rz=sum(float(v_[2]) for v_ in r2.reactions.values()) / alpha))
            for lv in order:
                d1 = sum(r1.disp[nd][axis] for nd, _ in level_tops[lv]) / len(level_tops[lv]) / alpha
                d2 = sum(r2.disp[nd][axis] for nd, _ in level_tops[lv]) / len(level_tops[lv]) / alpha
                ratio = abs(d2 / d1) if abs(d1) > 1e-9 else 1.0
                worst_ratio = max(worst_ratio, ratio)
                cur = drift.get((lv, axis))
                if cur is None or abs(d2) > abs(cur["second"]):
                    drift[(lv, axis)] = dict(level=lv, dir="XY"[axis], first=d1, second=d2, ratio=ratio, combo=label)
            for mark in col_nodes:
                st_ = r2.stations["col:" + mark]
                P = st_[0][0][0]                             # compression at the base end
                Ms = max(max(abs(a_[4]), abs(b_[4])) for a_, b_ in st_)
                Mw = max(max(abs(a_[5]), abs(b_[5])) for a_, b_ in st_)
                cur = col_res.setdefault(mark, dict(mark=mark, T=0.0, T_combo="", P=0.0, P_combo="", Ms=0.0, Ms_combo="", Mw=0.0, Mw_combo="", ratio=None, eq="", ratio_combo=""))
                S_ = strength.get(mark)
                if S_:
                    for a_, b_ in st_:
                        for P_, Mx_, My_ in ((a_[0], a_[4], a_[5]), (-b_[0], b_[4], b_[5])):
                            val, eq = h1(P_ / alpha, S_["Pc"], S_["Pt"], Mx_ / alpha, S_["Mcx"], My_ / alpha, S_["Mcy"])
                            if cur["ratio"] is None or val > cur["ratio"]:
                                cur.update(ratio=val, eq=eq, ratio_combo=label, at=dict(P=P_ / alpha, Mx=abs(Mx_) / alpha, My=abs(My_) / alpha), cap=dict(Pc=S_["Pc"], Mcx=S_["Mcx"], Mcy=S_["Mcy"]))
                if P / alpha > cur["P"]:
                    cur.update(P=P / alpha, P_combo=label)
                if -P / alpha > cur["T"]:
                    cur.update(T=-P / alpha, T_combo=label)
                e1 = st_[-1][1]
                cur.setdefault("top", []).append(dict(run=label, P=-float(e1[0]) / alpha, Ms=abs(float(e1[4])) / alpha, Mw=abs(float(e1[5])) / alpha))
                b0 = st_[0][0]
                cur.setdefault("base", []).append(dict(run=label, P=float(b0[0]) / alpha, Ms=abs(float(b0[4])) / alpha, Mw=abs(float(b0[5])) / alpha,
                                                       Vs=abs(float(b0[2])) / alpha, Vw=abs(float(b0[1])) / alpha, fD=cb.factors.get("D", 0.0)))
                if Ms / alpha > cur["Ms"]:
                    cur.update(Ms=Ms / alpha, Ms_combo=label)
                if Mw / alpha > cur["Mw"]:
                    cur.update(Mw=Mw / alpha, Mw_combo=label)
            for mark, b in braces.items():
                N = -r2.stations[b["name"]][0][0][0] / alpha                  # tension positive
                cur = brace_res.setdefault(mark, dict(mark=mark, T=0.0, T_combo="", C=0.0, C_combo="", tension_only=b["tension_only"], ratio=None, ratio_combo="", Pt=b["Pt"], Pc=b["Pc"], L=b["L"] / 12.0))
                if mark in slack:
                    continue
                if N > cur["T"]:
                    cur.update(T=N, T_combo=label)
                if -N > cur["C"]:
                    cur.update(C=-N, C_combo=label)
                if N < -1e-6 and not b["Pc"] and mark not in unchecked:
                    unchecked.add(mark)
                    problems.append(f"{mark} goes into compression in the frame and has no compression strength here (see the notes); make it tension only, or use a section that can be checked")
                val = (N / b["Pt"] if (N >= 0 and b["Pt"]) else (-N / b["Pc"] if (N < 0 and b["Pc"]) else None))
                if val is not None and (cur["ratio"] is None or val > cur["ratio"]):
                    cur.update(ratio=val, ratio_combo=label)
            for mark, els in B["beam_elems"].items():
                M = max(max(abs(a_[4]), abs(b_[4])) for e_ in els for a_, b_ in r2.stations[e_])
                V = max(max(abs(a_[2]), abs(b_[2])) for e_ in els for a_, b_ in r2.stations[e_])
                Nax = max(max(abs(a_[0]), abs(b_[0])) for e_ in els for a_, b_ in r2.stations[e_])
                cur = beam_res.setdefault(mark, dict(mark=mark, M=0.0, M_combo="", V=0.0, N=0.0, ratio=None, eq="", ratio_combo="", v_ratio=None))
                a0, b1 = r2.stations[els[0]][0][0], r2.stations[els[-1]][-1][1]
                cur.setdefault("ends", {"left": [], "right": []})
                cur["ends"]["left"].append(dict(run=label, M=abs(float(a0[4])) / alpha, V=abs(float(a0[2])) / alpha, T=-float(a0[0]) / alpha))
                cur["ends"]["right"].append(dict(run=label, M=abs(float(b1[4])) / alpha, V=abs(float(b1[2])) / alpha, T=float(b1[0]) / alpha))
                S_ = strength.get(mark)
                if S_:
                    cur["v_ratio"] = max(cur["v_ratio"] or 0.0, V / alpha / S_["V"])
                    for e_ in els:
                        ste = r2.stations[e_]
                        Mq = [abs(ste[0][0][4])] + [abs(b_[4]) for _, b_ in ste]          # at the element's quarter points (n_sub = 4)
                        Cb = round(min(_sb.cb_factor(max(Mq), Mq[1], Mq[2], Mq[3]), 3.0), 2) if max(Mq) > 1e-9 else 1.0
                        key = (round(mlen[e_], 2), Cb)
                        if key not in S_["neg"]:
                            S_["neg"][key] = _sb.check(S_["pr"], S_["Fy"], mlen[e_] if not S_["pts"] else S_["Lb_pos"], Cb, method_).M_avail
                        for a_, b_ in ste:
                            for P_, sag in ((a_[0], a_[4]), (-b_[0], -b_[4])):
                                Mc_ = S_["Mpos"] if sag >= 0 else S_["neg"][key]
                                val, eq = h1(P_ / alpha, S_["Pc"], S_["Pt"], sag / alpha, Mc_)
                                if cur["ratio"] is None or val > cur["ratio"]:
                                    cur.update(ratio=val, eq=eq, ratio_combo=label, at=dict(P=P_ / alpha, Mx=sag / alpha), cap=dict(Pc=S_["Pc"], Mcx=Mc_))
                if M / alpha > cur["M"]:
                    cur.update(M=M / alpha, M_combo=label)
                cur["V"], cur["N"] = max(cur["V"], V / alpha), max(cur["N"], Nax / alpha)
    # displacements for the drift checks: each lateral load alone, first-order, full stiffness
    elastic = []
    for kind_, F_of in (("wind", (lambda lv, ax: wind_F[lv][ax]) if wind_F else None), ("seismic", (lambda lv, ax: eq_F.get(lv, 0.0)) if eq_F else None)):
        if F_of is None:
            continue
        for axis in (0, 1):
            nl = {}
            for lv in order:
                for nd, share in spread(lv, axis, F_of(lv, axis)).items():
                    nl.setdefault(nd, [0, 0, 0, 0, 0, 0])[axis] += share
            try:
                r1, _, _ = solve_run({nd: tuple(v_) for nd, v_ in nl.items()}, [], sf=1.0, second=False)
            except Frame3DError:
                continue
            below, zb = 0.0, base_el
            for lv in order:
                d_ = abs(sum(r1.disp[nd][axis] for nd, _ in level_tops[lv]) / len(level_tops[lv]))
                hs = (elev[lv] - zb) * 12.0
                elastic.append(dict(load=kind_, level=lv, dir="XY"[axis], disp=d_, story=d_ - below, h=hs, ratio=(hs / (d_ - below)) if d_ - below > 1e-9 else None))
                below, zb = d_, elev[lv]
    for st_ in fr_sets:
        try:
            r1, _, _ = solve_run({}, [(e_, "global", g) for e_, g in st_["loads"]], sf=1.0, second=False)
        except Frame3DError:
            continue
        below, zb = 0.0, base_el
        for lv in order:
            d_ = abs(sum(r1.disp[nd][st_["axis"]] for nd, _ in level_tops[lv]) / len(level_tops[lv]))
            hs = (elev[lv] - zb) * 12.0
            cur = next((e_ for e_ in elastic if e_["load"] == "wind" and e_["level"] == lv and e_["dir"] == "XY"[st_["axis"]]), None)
            if cur is None:
                elastic.append(dict(load="wind", level=lv, dir="XY"[st_["axis"]], disp=d_, story=d_ - below, h=hs, ratio=(hs / (d_ - below)) if d_ - below > 1e-9 else None, case=st_["label"]))
            elif d_ > cur["disp"]:
                cur.update(disp=d_, story=d_ - below, ratio=(hs / (d_ - below)) if d_ - below > 1e-9 else None, case=st_["label"])
            below, zb = d_, elev[lv]
    if elastic:
        notes.append("Drift table: each lateral load alone at its strength level (1.0 W; the seismic story forces), first-order, full stiffness. Wind drift limits are the "
                     "designer's; seismic displacements go to the seismic sheet's drift check (Cd, Ie and the Table 12.12-1 limit).")
    # wind drift against the limit typed on the Building Model card (ratio, wind factor and source are the engineer's)
    drift_checks = []
    mdl_ = (project or {}).get("model") or {}
    try:
        d_ratio = float(str(mdl_.get("drift_ratio") or "").strip() or 0)
        d_fac = float(str(mdl_.get("drift_factor") or "").strip() or 0)
    except ValueError:
        d_ratio = d_fac = 0.0
        problems.append("The wind drift limit on the Building Model card cannot be read (type numbers)")
    if d_ratio > 0 and d_fac > 0:
        if not str(mdl_.get("drift_source") or "").strip():
            problems.append("The wind drift limit needs its source on the Building Model card; drift is not checked")
        else:
            for e_ in elastic:
                if e_["load"] == "wind":
                    drift_checks.append(dict(level=e_["level"], dir=e_["dir"], drift=d_fac * e_["story"], limit=e_["h"] / d_ratio, ratio=d_ratio, factor=d_fac,
                                             source=str(mdl_["drift_source"]).strip(), case=e_.get("case", "")))
    out_members = None
    if eq_F and any(e_["load"] == "seismic" for e_ in elastic):
        import copy
        out_members = copy.deepcopy(members)
        for m in out_members:
            if m.get("kind") == "seismic_elf" and (m["values"].get("mark") or "seismic") == eq_mark:
                for row in m["values"].get("levels") or []:
                    got = [e_["disp"] for e_ in elastic if e_["load"] == "seismic" and e_["level"] == str(row.get("name") or "").strip()]
                    if got:
                        row["de"] = f"{max(got):.4f}"
                m["values"]["de_source"] = "3D frame analysis, first-order, full stiffness, the larger of the two directions"
                break
    notes.insert(0, f"Direct analysis method, AISC 360-22 Chapter C: {runs} second-order runs ({len(cbs)} {method_} combinations; each in four directions, or once for each wind case of an open building), stiffness x 0.8, "
                    "notional load 0.003 of the gravity load at each level with tau_b = 1.0" + (", loads x 1.6 and results / 1.6 (ASD)" if alpha != 1 else "") + ".")
    if worst_ratio > 1.5:
        problems.append(f"Second-order drift is {worst_ratio:.2f} times first-order drift (at the reduced stiffness). The frame is flexible; stiffen it.")
    return dict(levels=[drift[k_] for k_ in sorted(drift, key=lambda t: (elev[t[0]], t[1]))], columns=list(col_res.values()), beams=list(beam_res.values()), braces=list(brace_res.values()),
                notes=notes, problems=problems, ratio=worst_ratio, runs=runs, method=method_, elastic=elastic, members=out_members, audit=audit, drift_checks=drift_checks,
                units="drift in.; column P kips (compression at the base), moments kip-in. about the column's strong and weak axes; beam M kip-in., V and axial kips")


def model_plan(project, members):
    """What the plan view draws: per level, the placed members as lines (beams, joists) and points (posts, columns, footings)."""
    mdl = (project or {}).get("model") or {}
    levels = [str(l.get("name") or "").strip() for l in mdl.get("levels") or [] if str(l.get("name") or "").strip()]
    out = {lv: [] for lv in levels}
    for m in members or []:
        try:
            pl = model_place(project, m)
        except ValueError:
            continue
        if not pl:
            continue
        item = dict(mark=(m.get("values") or {}).get("mark") or "", kind=m.get("kind"), p1=pl["p1"], p2=pl["p2"], wall=m.get("kind") in MODEL_WALLS, brace=m.get("kind") in FRAME_BRACES)
        if m.get("kind") in TAKEDOWN_FOOTINGS:
            out.setdefault(pl["base"] if pl["base"] in out else (levels[0] if levels else ""), []).append(item)
        else:
            out.setdefault(pl["level"], []).append(item)
            if m.get("kind") in TAKEDOWN_POSTS and pl["base"] in out and pl["base"] != pl["level"]:
                out[pl["base"]].append(dict(item, below=True))
    for nm, epl in model_existing(project):                   # existing walls, drawn on the level at their top and grey
        out.setdefault(epl["level"], []).append(dict(mark=nm, kind="existing", p1=epl["p1"], p2=epl["p2"], wall=True, brace=False, existing=True))
    gx = [(str(g.get("name") or ""), _coord(g.get("at"), [])) for g in mdl.get("grids_x") or []]
    gy = [(str(g.get("name") or ""), _coord(g.get("at"), [])) for g in mdl.get("grids_y") or []]
    return dict(levels=levels, items=out, grids_x=[g for g in gx if g[1] is not None], grids_y=[g for g in gy if g[1] is not None])


def _governing(out, project):
    """Adds to each support the largest downward reaction under the project's ASD combinations (service) and LRFD combinations (strength),
    each with the combination's name, for a footing."""
    for which, key in (("ASD", "service"), ("LRFD", "strength")):
        cbs = combos(project or {}, [], which)
        for sdict in out["supports"]:
            best = None
            for cb in cbs:
                P = sum(cb.factors.get(c, 0.0) * r for c, r in sdict["cases"].items())
                if best is None or P > best[1]:
                    best = (cb.name, P)
            sdict[key] = dict(name=best[0], P=best[1]) if best else None
    return out


def frame_reactions(project, members, mark):
    """Base forces of one column of the placed 3D frame, from the sway run at the ASD level (service) and the LRFD level (strength), in the
    shape of reactions(): the runs with the largest moment, the largest shear, the largest compression and the least compression or largest
    uplift, for bending about the column's strong axis and about its weak axis (two "bases" to choose from). Units: lb, lb-ft."""
    out = dict(bases=["strong-axis moment", "weak-axis moment"], service=[], strength=[], messages=[])
    for which, key in (("ASD", "service"), ("LRFD", "strength")):
        run = model_frame_sway(dict(project or {}, method=which), members)
        if not run.get("levels"):
            out["messages"].append(f"{which} combinations: " + ("; ".join(run.get("problems") or []) or "the frame did not run"))
            continue
        col = next((c for c in run["columns"] if c["mark"] == mark), None)
        if col is None or not col.get("base"):
            out["messages"].append(f"{mark} is not a column of the placed frame"); continue
        for base, mk_, vk in (("strong-axis moment", "Ms", "Vs"), ("weak-axis moment", "Mw", "Vw")):
            picks = []
            for chooser in (lambda b: b[mk_], lambda b: b[vk], lambda b: b["P"], lambda b: -b["P"]):
                b = max(col["base"], key=chooser)
                if b not in picks:
                    picks.append(b)
            for b in picks:
                out[key].append(dict(base=base, name=b["run"], P=b["P"] * 1000.0, M=b[mk_] * 1000.0 / 12.0, V=b[vk] * 1000.0, wt_factor=(b["fD"] or None) if key == "strength" else None))
    return out


def frame_knee(project, members, mark):
    """Forces at the top of one column of the placed 3D frame (the beam-to-column joint), from the sway run at the project's method: for bending
    about the column's strong axis and about its weak axis, the runs with the largest moment, the largest compression and the least compression.
    dict(axes={"strong-axis moment": [dict(name, P kips, M kip-ft)], ...}, messages)."""
    run = model_frame_sway(project, members)
    if not run.get("levels"):
        return dict(axes={}, messages=run.get("problems") or ["the frame did not run"])
    col = next((c for c in run["columns"] if c["mark"] == mark), None)
    if col is None or not col.get("top"):
        return dict(axes={}, messages=[f"{mark} is not a column of the placed frame"])
    axes = {}
    for nm, mk_ in (("strong-axis moment", "Ms"), ("weak-axis moment", "Mw")):
        picks = []
        for chooser in (lambda b: b[mk_], lambda b: b["P"], lambda b: -b["P"]):
            b = max(col["top"], key=chooser)
            if b not in picks:
                picks.append(b)
        axes[nm] = [dict(name=b["run"], P=b["P"], M=b[mk_] / 12.0) for b in picks]
    return dict(axes=axes, messages=run.get("problems") or [], method=run["method"])


def frame_beam_end(project, members, mark):
    """Forces at each end of one beam of the placed 3D frame, from the sway run at the project's method: for the left and the right end, the runs
    with the largest moment, the largest shear and the largest axial tension, each with its concurrent moment (kip-ft), tension (kips, zero when
    the beam is in compression) and shear (kips). dict(ends={"left": [...], "right": [...]}, messages, method)."""
    run = model_frame_sway(project, members)
    if not run.get("levels"):
        return dict(ends={}, messages=run.get("problems") or ["the frame did not run"])
    bm = next((b for b in run["beams"] if b["mark"] == mark), None)
    if bm is None or not bm.get("ends"):
        return dict(ends={}, messages=[f"{mark} is not a beam of the placed frame"])
    out = {}
    for end, recs in bm["ends"].items():
        picks = []
        for chooser in (lambda b: b["M"], lambda b: b["V"], lambda b: b["T"]):
            b = max(recs, key=chooser)
            if b not in picks:
                picks.append(b)
        out[end] = [dict(name=b["run"], M=b["M"] / 12.0, T=max(b["T"], 0.0), V=b["V"]) for b in picks]
    return dict(ends=out, messages=run.get("problems") or [], method=run["method"])


def frame_beam_hss(project, members, mark, end):
    """Joint forces for the beam to HSS column moment connection screen, from one sway run at the project's method: the moment at one end of a
    frame beam, with the axial load and the moment in the beam's plane at the top of the frame column the beam frames into, all from the same
    run. Picks the runs with the largest beam end moment, the largest column load and the largest column moment.
    dict(rows=[dict(name, M, P, Mc)], column, column_shape, face, messages, method); M and Mc in kip-ft, P in kips (compression positive)."""
    run = model_frame_sway(project, members)
    if not run.get("levels"):
        return dict(rows=[], messages=run.get("problems") or ["the frame did not run"])
    bm = next((b for b in run["beams"] if b["mark"] == mark), None)
    if bm is None or not bm.get("ends") or end not in bm["ends"]:
        return dict(rows=[], messages=[f"{mark} is not a beam of the placed frame"])
    by_mark = {(x.get("values") or {}).get("mark"): x for x in members or []}
    try:
        bp = model_place(project, by_mark[mark])
    except (KeyError, ValueError) as e:
        return dict(rows=[], messages=[str(e)])
    pt = bp["p1"] if end == "left" else bp["p2"]
    other = bp["p2"] if end == "left" else bp["p1"]
    along_x = abs(other[0] - pt[0]) >= abs(other[1] - pt[1])
    col = cplace = None
    for c in run["columns"]:
        m_ = by_mark.get(c["mark"])
        try:
            cp = model_place(project, m_) if m_ else None
        except ValueError:
            cp = None
        if cp and cp["level"] == bp["level"] and math.hypot(cp["p1"][0] - pt[0], cp["p1"][1] - pt[1]) <= 0.25 + 1e-9:
            col, cplace = c, m_
            break
    if col is None or not col.get("top"):
        return dict(rows=[], messages=[f"No frame column of {bp['level']} stands at the {end} end of {mark} ({pt[0]:g}, {pt[1]:g})"])
    web_x = not str((cplace.get("values") or {}).get("at_web") or "X").strip().upper().startswith("Y")
    face = "B" if along_x == web_x else "H"        # the beam runs along the column's depth: it frames into the B face; the column bends about its strong axis
    key = "Ms" if face == "B" else "Mw"
    tops = {t["run"]: t for t in col["top"]}
    joined = [dict(name=b["run"], M=b["M"] / 12.0, P=tops[b["run"]]["P"], Mc=tops[b["run"]][key] / 12.0) for b in bm["ends"][end] if b["run"] in tops]
    picks = []
    for chooser in (lambda r: r["M"], lambda r: r["P"], lambda r: r["Mc"]):
        r = max(joined, key=chooser)
        if r not in picks:
            picks.append(r)
    return dict(rows=picks, column=col["mark"], column_shape=(cplace.get("values") or {}).get("shape") if cplace.get("kind") == "hss_column" else "",
                face=face, messages=run.get("problems") or [], method=run["method"])


def frame_base_biaxial(project, members, mark):
    """Base forces of one frame column for the biaxial base plate screen, at the project's method: the runs with the largest strong-axis moment,
    the largest weak-axis moment, the largest compression and the least compression, each with its concurrent axial load and both moments.
    dict(rows=[dict(name, P kips, Mx, My kip-ft)], messages, method)."""
    run = model_frame_sway(project, members)
    if not run.get("levels"):
        return dict(rows=[], messages=run.get("problems") or ["the frame did not run"])
    col = next((c for c in run["columns"] if c["mark"] == mark), None)
    if col is None or not col.get("base"):
        return dict(rows=[], messages=[f"{mark} is not a column of the placed frame"])
    picks = []
    for chooser in (lambda b: b["Ms"], lambda b: b["Mw"], lambda b: b["P"], lambda b: -b["P"]):
        b = max(col["base"], key=chooser)
        if b not in picks:
            picks.append(b)
    return dict(rows=[dict(name=b["run"], P=b["P"], Mx=b["Ms"] / 12.0, My=b["Mw"] / 12.0) for b in picks], messages=run.get("problems") or [], method=run["method"])


def reactions(kind, values, project, members=None):
    """Base reactions of a steel column or a frame for every ASD combination (service) and
    every LRFD combination (factored), so a footing or base plate can take them without
    retyping. Each list is the member run with that list of combinations; for a cantilevered
    column or a frame that is a second-order analysis at that load level. Units: lb, lb-ft."""
    if kind in FRAME_COLS and members and str((values or {}).get("at_x1") or "").strip() and str((values or {}).get("at_level") or "").strip():
        got = frame_reactions(project, members, (values or {}).get("mark"))
        if got["service"] or got["strength"] or kind == "hss_column":
            return got
    if kind not in ("steel_column", "frame", "guard"):
        return dict(error="Loads can be taken from a steel column, a moment frame or a guard.")
    out = dict(bases=[], service=[], strength=[], messages=[])
    if kind == "guard":
        # the governing post base moment and shear of the guard sheet, at each load level; no axial load is carried over
        for which, key in (("ASD", "service"), ("LRFD", "strength")):
            try:
                sheet, _, _ = build(kind, values, dict(project, method=which))
            except Missing as e:
                out["messages"].append("The guard sheet is not complete: " + "; ".join(e.items))
                continue
            except (WorksheetError, SteelInputError, ValueError, KeyError) as e:
                out["messages"].append(f"The guard sheet stopped: {e}")
                continue
            cs = sheet.guard["cases"]
            out[key].append(dict(base="post base", name=sheet.combo_lines[0][0] + ", guard load", P=0.0, M=max(c[3] for c in cs), V=max(c[4] for c in cs), wt_factor=None))
        out["bases"] = ["post base"]
        return out
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


def _base_flags(text):
    """Support of a frame column base from the placement choice: "pinned" (or blank), "fixed", "fixed for sway in X only" (held against turning
    about the Y axis, free about X) or "fixed for sway in Y only". Twist is always held. Flags are (ux, uy, uz, rx, ry, rz)."""
    t = str(text or "").strip().lower()
    if not t.startswith("fix"):
        return (1, 1, 1, 0, 0, 1)
    if "x only" in t:
        return (1, 1, 1, 0, 1, 1)
    if "y only" in t:
        return (1, 1, 1, 1, 0, 1)
    return (1, 1, 1, 1, 1, 1)


def bent_building(project, members, spec):
    """Fills the building model with a row of two-column bents (carport, pavilion, shed frame): levels, grids, a column pair and a rafter at every
    bent, with the roof loads on each rafter by its tributary width. spec (text values, feet unless noted): n (bents), spacing (one number, or a
    list separated by commas, one fewer than n), end_start, end_end (roof past the first and last bent), col_spacing, cant_low, cant_high, height
    (top of the line A columns), slope (roof rise in 12 toward line B, blank = level), col_shape, col_Fy, raf_shape, raf_Fy, base ("pinned" /
    "fixed"), D, S, Lr (psf, blank = none), prefix. Returns dict(project, members, added, problems); nothing is changed when there is a problem."""
    import copy
    sp, problems = spec or {}, []

    def num(key, label, required=True, low=None):
        t = str(sp.get(key) or "").strip().replace(",", "")
        if not t:
            if required:
                problems.append(f"{label} is blank")
            return None
        try:
            v = float(t)
        except ValueError:
            problems.append(f"{label}: '{t}' is not a number"); return None
        if low is not None and v < low:
            problems.append(f"{label} must be {low:g} or more"); return None
        return v
    n = num("n", "Number of bents", low=2)
    cs, H = num("col_spacing", "Column spacing", low=0.5), num("height", "Height to the roof level", low=1)
    cl, ch = num("cant_low", "Cantilever past the first column line", False, 0) or 0.0, num("cant_high", "Cantilever past the second column line", False, 0) or 0.0
    e0, e1 = num("end_start", "Roof past the first bent", False, 0) or 0.0, num("end_end", "Roof past the last bent", False, 0) or 0.0
    cFy, rFy = num("col_Fy", "Column Fy", low=1), num("raf_Fy", "Rafter Fy", low=1)
    rise = (num("slope", "Roof rise in 12", False, 0) or 0.0) / 12.0
    pitched = str(sp.get("roof") or "").strip().lower().startswith("pitch")
    xr = num("ridge", "Ridge from column line A", False, 0)
    if pitched:
        if not rise:
            problems.append("A pitched roof needs its rise in 12")
        if cs is not None:
            xr = cs / 2 if xr is None else xr
            if not 0 < xr < cs:
                problems.append("The ridge must be between the two column lines")
    col, raf = str(sp.get("col_shape") or "").strip(), str(sp.get("raf_shape") or "").strip()
    for nm, lab in ((col, "Column section"), (raf, "Rafter section")):
        if not nm:
            problems.append(f"{lab} is blank")
    loads = [(c, num(c, f"{lab} load", False, 0)) for c, lab in (("D", "Dead"), ("S", "Snow"), ("Lr", "Roof live"))]
    spac = []
    if n is not None:
        n = int(round(n))
        parts = [t for t in str(sp.get("spacing") or "").replace(";", ",").split(",") if t.strip()]
        try:
            spac = [float(t) for t in parts]
        except ValueError:
            problems.append("Bent spacing: type one number, or the spacings separated by commas")
        if len(spac) == 1:
            spac = spac * (n - 1)
        if not problems and (len(spac) != n - 1 or any(v <= 0 for v in spac)):
            problems.append(f"Bent spacing: give one spacing, or {n - 1} spacings for {n} bents")
    pre = str(sp.get("prefix") or "").strip()
    # beams along the building at the column tops: moment-connected in the portal bays, pinned struts in the others
    eave, strut = str(sp.get("eave_shape") or "").strip(), str(sp.get("strut_shape") or "").strip()
    eFy = num("eave_Fy", "Eave beam Fy", bool(eave), 1)
    sFy = num("strut_Fy", "Eave strut Fy", bool(strut), 1)
    portal = set()
    bays_txt = str(sp.get("eave_bays") or "").strip().lower()
    for nm, lab in ((eave, "Eave beam section"), (strut, "Eave strut section")):
        if nm:
            try:
                _frame_section("steel_beam", dict(shape=nm))
            except ValueError as e:
                problems.append(f"{lab}: {e}")
    if eave and n is not None and not problems:
        if not bays_txt:
            problems.append("Portal bays is blank: type the bay numbers with eave beams (bay 1 is between bents 1 and 2), or 'all'")
        elif bays_txt == "all":
            portal = set(range(1, n))
        else:
            try:
                portal = {int(t) for t in bays_txt.replace(";", ",").split(",") if t.strip()}
            except ValueError:
                problems.append("Portal bays: type bay numbers separated by commas, or 'all'")
            if portal and (min(portal) < 1 or max(portal) > n - 1):
                problems.append(f"Portal bays: with {n} bents the bays are 1 to {n - 1}")
    elif bays_txt and not eave:
        problems.append("Portal bays are listed but the eave beam section is blank")
    kind_col = None
    if col:
        try:
            shapes.hss(col); kind_col = "hss_column"
        except Exception:
            try:
                shapes.get(col); kind_col = "steel_column"
            except Exception:
                problems.append(f"Column section '{col}' is not in the shapes table")
    if raf:
        try:
            _frame_section("steel_beam", dict(shape=raf))
        except ValueError as e:
            problems.append(f"Rafter section: {e}")
    if problems:
        return dict(project=project, members=members, added=0, problems=problems)
    xs = [0.0]
    for v in spac:
        xs.append(xs[-1] + v)
    marks = {(m.get("values") or {}).get("mark") for m in members or []}
    new = []
    base_txt = str(sp.get("base") or "").strip().lower()
    base_txt = base_txt if base_txt.startswith("fix") else "pinned"
    g = lambda v: f"{v:g}"
    for i, x in enumerate(xs, 1):
        trib = ((x - xs[i - 2]) / 2 if i > 1 else e0) + ((xs[i] - x) / 2 if i < len(xs) else e1)
        for line, y in (("A", 0.0), ("B", cs)):
            v = dict(mark=f"{pre}C{i}{line}", shape=col, Fy=g(cFy), height=g(H), self_weight="yes", loads=[], at_level="Roof", at_base="Base", at_x1=g(x), at_y1=g(y),
                     at_base_fix=base_txt)
            v.update(dict(Fy_source="", Kx="1.0", Ky="1.0", k_source="direct analysis method (the frame run)", moments=[]) if kind_col == "hss_column" else
                     dict(ends="held sideways (braced)", Kx="1.0", Ky="1.0", k_source="direct analysis method (the frame run)", lateral=[], leaning=[], drift=[]))
            new.append(dict(kind=kind_col, values=v))
        rows = [dict(case=c, kind="uniform", mag=f"{q * trib / 1000:.5f}", x1="", x2="", label=f"roof {dict(D='dead', S='snow', Lr='live')[c]} load {q:g} psf x {trib:g} ft")
                for c, q in loads if q]
        if pitched:
            zr = xr * rise                                    # ridge above the line A column tops
            base_ = dict(shape=raf, Fy=g(rFy), support_type="", more_spans="", bracing="continuous", brace_pts="", self_weight="yes", defl=[], at_level="Roof", at_x1=g(x), at_x2=g(x))
            new.append(dict(kind="steel_beam", values=dict(base_, mark=f"{pre}R{i}A", span=g(xr), oh_left=g(cl) if cl else "", oh_right="", loads=[dict(r_) for r_ in rows],
                                                           at_y1=g(-cl), at_y2=g(xr), at_dz1=g(round(-cl * rise, 4)), at_dz2=g(round(zr, 4)), at_fix_j="moment")))
            new.append(dict(kind="steel_beam", values=dict(base_, mark=f"{pre}R{i}B", span=g(cs - xr), oh_left="", oh_right=g(ch) if ch else "", loads=[dict(r_) for r_ in rows],
                                                           at_y1=g(xr), at_y2=g(cs + ch), at_dz1=g(round(zr, 4)), at_dz2=g(round(zr - (cs - xr + ch) * rise, 4)), at_fix_i="moment")))
            continue
        new.append(dict(kind="steel_beam", values=dict(mark=f"{pre}R{i}", shape=raf, Fy=g(rFy), support_type="", span=g(cs), more_spans="", oh_left=g(cl) if cl else "", oh_right=g(ch) if ch else "",
                   bracing="continuous", brace_pts="", self_weight="yes", loads=rows, defl=[], at_level="Roof", at_x1=g(x), at_y1=g(-cl), at_x2=g(x), at_y2=g(cs + ch),
                   **(dict(at_dz1=g(round(-cl * rise, 4)), at_dz2=g(round((cs + ch) * rise, 4))) if rise else {}))))
    n_eave = n_strut = 0
    if eave or strut:
        zB = (xr * rise - (cs - xr) * rise) if pitched else cs * rise          # line B column tops above line A's
        for j in range(1, len(xs)):
            sec, fy, rigid = (eave, eFy, True) if j in portal else (strut, sFy, False)
            if not sec:
                continue
            n_eave, n_strut = n_eave + (2 if rigid else 0), n_strut + (0 if rigid else 2)
            for line, y, dz in (("A", 0.0, 0.0), ("B", cs, zB)):
                v = dict(mark=f"{pre}{'E' if rigid else 'ES'}{j}{line}", shape=sec, Fy=g(fy), support_type="", span=g(xs[j] - xs[j - 1]), more_spans="", oh_left="", oh_right="",
                         bracing="at points", brace_pts="", self_weight="yes", loads=[], defl=[], at_level="Roof", at_x1=g(xs[j - 1]), at_y1=g(y), at_x2=g(xs[j]), at_y2=g(y))
                if dz:
                    v.update(at_dz1=g(round(dz, 4)), at_dz2=g(round(dz, 4)))
                if rigid:
                    v.update(at_fix_i="moment", at_fix_j="moment")
                new.append(dict(kind="steel_beam", values=v))
    clash = sorted(m["values"]["mark"] for m in new if m["values"]["mark"] in marks)
    if clash:
        return dict(project=project, members=members, added=0, problems=["These marks are already in the project: " + ", ".join(clash[:8]) + (" ..." if len(clash) > 8 else "") + ". Give a prefix."])
    proj = copy.deepcopy(project or {})
    mdl = proj.setdefault("model", {})
    lv = mdl.setdefault("levels", [])
    have = {str(l.get("name") or "").strip() for l in lv}
    if "Base" not in have:
        lv.insert(0, dict(name="Base", elev="0"))
    if "Roof" not in have:
        lv.append(dict(name="Roof", elev=g(H)))
    if not mdl.get("grids_x"):
        mdl["grids_x"] = [dict(name=str(i), at=g(x)) for i, x in enumerate(xs, 1)]
    if not mdl.get("grids_y"):
        mdl["grids_y"] = [dict(name="A", at="0"), dict(name="B", at=g(cs))]
    extra = []
    if n_eave:
        extra.append(f"{n_eave} eave beams ({eave}) at the column tops with moment connections at both ends, in bay{'s' if len(portal) > 1 else ''} "
                     + ", ".join(str(j) for j in sorted(portal)) + " of each column line: with the columns they are the portal frames along the building. "
                     "Their own sheets carry only their weight, braced at the ends; the 3D frame run is their check. The beam-to-column moment connection is not checked.")
    if n_strut:
        extra.append(f"{n_strut} eave struts ({strut}) with pinned ends in the other bays; they carry axial force between the bents in the 3D frame run.")
    if base_txt != "pinned" and "only" in base_txt:
        extra.append("Column bases: " + base_txt + " (free to turn in the other direction).")
    if pitched:
        return dict(project=proj, members=list(members or []) + new, added=len(new), problems=[],
                    notes=extra + [f"{len(xs)} bents: {2 * len(xs)} columns and {2 * len(xs)} rafter halves joined rigidly at the ridge, roof {g(xs[-1] + e0 + e1)} ft long by {g(cs + cl + ch)} ft wide, "
                           f"rising {g(rise * 12)} in 12 from {g(H)} ft at column line A to the ridge {g(xr)} ft from line A at {g(round(H + xr * rise, 3))} ft. "
                           "Each rafter half's own sheet treats the ridge as a support; for a ridge frame the 3D frame run is the check."])
    return dict(project=proj, members=list(members or []) + new, added=len(new), problems=[],
                notes=extra + [f"{len(xs)} bents: {2 * len(xs)} columns and {len(xs)} rafters, roof {g(xs[-1] + e0 + e1)} ft long by {g(cs + cl + ch)} ft wide, "
                       + (f"rising {g(rise * 12)} in 12 from {g(H)} ft at column line A to {g(round(H + cs * rise, 3))} ft at line B." if rise else f"level at {g(H)} ft.")])


def frame_sheet(project, members):
    """The 3D frame run (model_frame_sway) as a calc sheet for the package, or None when the project has no placed frame or the run did not finish."""
    from ..ws_more import SimpleSheet
    from ..ws_steel_beam import Row
    try:
        out = model_frame_sway(project, members)
    except Exception:
        return None
    if not out.get("levels") or not (out.get("columns") or out.get("beams")):
        return None
    m_ = out["method"]
    rows = []
    for c in out["columns"]:
        if c.get("ratio") is not None:
            rows.append(Row(f"column {c['mark']}, axial + bending", c["ratio_combo"], c["ratio"], 1.0, "", f"AISC 360-22 Eq. {c['eq']}",
                            f"Pr = {c['at']['P']:.1f} kip, Mrx = {c['at']['Mx'] / 12:.1f} kip-ft, Mry = {c['at']['My'] / 12:.1f} kip-ft; "
                            f"Pc = {c['cap']['Pc']:.1f} kip, Mcx = {c['cap']['Mcx'] / 12:.1f} kip-ft, Mcy = {c['cap']['Mcy'] / 12:.1f} kip-ft"))
    for b in out["beams"]:
        if b.get("ratio") is not None:
            rows.append(Row(f"beam {b['mark']}, axial + bending", b["ratio_combo"], b["ratio"], 1.0, "", f"AISC 360-22 Eq. {b['eq']}",
                            f"Pr = {b['at']['P']:.1f} kip, Mr = {abs(b['at']['Mx']) / 12:.1f} kip-ft ({'top' if b['at']['Mx'] >= 0 else 'bottom'} flange in compression); "
                            f"Pc = {b['cap']['Pc']:.1f} kip, Mc = {b['cap']['Mcx'] / 12:.1f} kip-ft"))
            rows.append(Row(f"beam {b['mark']}, shear", b["M_combo"], b["v_ratio"], 1.0, "", "AISC 360-22 Ch. G", f"Vr = {b['V']:.1f} kip"))
    for b in out.get("braces") or []:
        if b.get("ratio") is not None:
            rows.append(Row(f"brace {b['mark']}, axial", b["ratio_combo"], b["ratio"], 1.0, "", "AISC 360-22 Ch. D, E",
                            f"tension {b['T']:.2f} kip, compression {b['C']:.2f} kip" + ("; tension only" if b["tension_only"] else "")))
    for dc_ in out.get("drift_checks") or []:
        rows.append(Row(f"wind drift, {dc_['level']}, {dc_['dir']} direction", f"{dc_['factor']:g} W", dc_["drift"], dc_["limit"], "in", dc_["source"],
                        f"story height / {dc_['ratio']:g}; first-order, full stiffness" + (f"; {dc_['case']}" if dc_["case"] else "")))
    blocks = [dict(title="Sway of Each Level (reduced stiffness, with notional loads)", lines=[f"{'Level':<10}{'Dir.':<6}{'First-order':>13}{'Second-order':>14}{'Ratio':>8}   Governing run"] + [
        f"{l['level']:<10}{l['dir']:<6}{abs(l['first']):>10.3f} in{abs(l['second']):>11.3f} in{l['ratio']:>8.2f}   {l['combo']}" for l in out["levels"]])]
    if out.get("elastic"):
        blocks.append(dict(title="Drift under Each Lateral Load Alone (first-order, full stiffness, strength level)", lines=[
            f"{'Load':<10}{'Level':<10}{'Dir.':<6}{'Displacement':>14}{'Story drift':>13}{'Height / drift':>16}"] + [
            f"{e['load']:<10}{e['level']:<10}{e['dir']:<6}{e['disp']:>11.3f} in{e['story']:>10.3f} in{('H / ' + format(round(e['ratio']), ',')) if e['ratio'] else '':>16}" for e in out["elastic"]]))
    blocks.append(dict(title=f"Column Base Forces, Largest of Each over Every Run ({m_} level)", lines=[
        f"{'Column':<9}{'Compression':>13}{'Uplift':>10}{'M strong':>13}{'M weak':>13}"] + [
        f"{c['mark']:<9}{c['P']:>9.1f} kip{c['T']:>6.1f} kip{c['Ms'] / 12:>7.1f} kip-ft{c['Mw'] / 12:>7.1f} kip-ft" for c in out["columns"]]))
    blocks.append(dict(title=f"Sum of the Base Reactions in Each Run ({m_} level)", lines=[f"{'Rx':>9}{'Ry':>9}{'Rz':>9}   Run"] + [
        f"{a['Rx']:>9.2f}{a['Ry']:>9.2f}{a['Rz']:>9.2f}   {a['run']}" for a in out["audit"]], after=["kips; Rz is upward on the structure."]))
    cbs = combos(project or {}, [], m_)
    n = lambda k, w: f"{len(out[k])} {w}" + ("" if len(out[k]) == 1 else "s")
    sh = SimpleSheet("FR", "3D Frame Analysis", "Frame", m_,
                     [("Members", ", ".join([n("columns", "column"), n("beams", "beam")] + ([n("braces", "brace")] if out.get("braces") else []))),
                      ("Method", "Second-order elastic analysis, direct analysis method (AISC 360-22 Chapter C)"), ("Runs", str(out["runs"]))],
                     ["Member loads, self-weight and positions are those on each member's own sheet."], [(cb.name, cb.source) for cb in cbs], "Analysis", [], rows,
                     list(out["notes"]), ["Connections, base plates and foundations (their own sheets)", "Column shear and torsion", "Serviceability limits on drift (the designer's)"])
    try:
        view = model_view(project, members)
        marks = {c["mark"] for c in out["columns"]} | {b["mark"] for b in out["beams"]} | {b["mark"] for b in out.get("braces") or []}
        its = [i for i in view["items"] if i["mark"] in marks]
        if its:
            blocks.insert(0, dict(title="Frame", picture=("frame3d", dict(items=its)), lines=[]))
    except Exception:
        pass
    sh.blocks = blocks
    sh.problems = out["problems"]
    return sh


def summary_sheet(project, entries):
    """Design summary: every check of every sheet in the package in one table, with the governing check first. entries: (mark, title, sheet)."""
    from ..ws_more import SimpleSheet
    lines, worst, n_flag, n_all = [f"{'Mark':<7}{'Check':<46}{'D/C':>6}  {'Result':<6} Combination"], None, 0, 0
    last = None
    for mark, title, sheet in entries:
        got = [(r.check, r.dc, r.status, r.combo) for r in getattr(sheet, "rows", [])] + \
              [(f"member {r['member']} ({r['shape']})", r["ratio"], r["status"], r["combo"]) for r in getattr(sheet, "member_rows", [])]
        if not got:
            continue
        if title != last:
            lines.append(f"{title[:70]}"); last = title
        for check, dc, status, combo in got:
            n_all += 1; n_flag += status == "FLAG"
            lines.append(f"{str(mark)[:6]:<7}{str(check)[:45]:<46}{dc:>6.2f}  {status:<6} {str(combo)}")
            if worst is None or dc > worst[1]:
                worst = (mark, dc, check)
    if worst is None:
        return None
    m_ = (project or {}).get("method") or ""
    sh = SimpleSheet("SUM", "Design Summary", "Summary", m_,
                     [("Checks", f"{n_all}"), ("Status", "ALL CHECKS OK" if not n_flag else f"{n_flag} FLAGGED"), ("Governing", f"{worst[0]}: {worst[2]}, D/C {worst[1]:.2f}")],
                     [], [], "", [], [], ["D/C is demand over capacity; 1.00 is the limit. Each check is worked on its own sheet."], [])
    sh.blocks = [dict(title="Every Check", lines=lines)]
    return sh


def existing_sheet(project, members):
    """Loads the building model puts on existing walls (by others): gravity by load case per source, and each wall line's lateral shear.
    None when the model lists no existing walls."""
    from ..ws_more import SimpleSheet
    ex = model_existing(project)
    if not ex:
        return None
    try:
        out = model_links(project, members)
        g = lateral_governing(project, out["members"])
    except Exception:
        return None
    asd = (project or {}).get("method") == "ASD"
    grav = [f"{'Existing wall':<38}{'From':<16}{'Support':<15}Service load by case"]
    for e in out.get("existing") or []:
        grav.append(f"{e['wall'][:37]:<38}{e['source'][:15]:<16}{e['support'][:14]:<15}" + ", ".join(f"{c} {v:,.0f}" for c, v in e["cases"].items()) + f" {e['unit']}")
    lat = [f"{'Existing wall':<38}{'Level':<12}{'Dir.':<6}{'Trib. ft':>9}{'V, lb':>9}  Load"]
    for l in g.get("lines") or []:
        if l.get("existing"):
            lat.append(f"{l['wall'].replace(' (existing)', '')[:37]:<38}{str(l['level'])[:11]:<12}{str(l['wind']):<6}{l['trib']:>9.2f}{l['V']:>9,.0f}  {l['load']}")
    blocks = [dict(title="Gravity Loads Bearing on Existing Walls", lines=grav if len(grav) > 1 else grav + ["(none)"]),
              dict(title="Lateral Shear Taken by Existing Wall Lines", lines=lat if len(lat) > 1 else lat + ["(none)"])]
    sh = SimpleSheet("EX", "Loads on Existing Construction", "Existing", (project or {}).get("method") or "",
                     [("Existing walls", ", ".join(nm for nm, _ in ex))], [], [], "", [], [],
                     ["Gravity loads are service loads per foot of wall from the members that bear on the wall, by load case.",
                      "Lateral shear is distributed to wall lines by tributary width (flexible diaphragm) at the same level as the new walls of the "
                      "model" + (" (ASD: 0.6 W, 0.7 E)." if asd else " (strength level W and E).")],
                     ["The existing walls, their foundations and their connections are not checked on this sheet"])
    sh.blocks = blocks
    return sh


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
    fs = frame_sheet(project, members)
    if fs is not None:
        items.append(("simple", fs, "AISC 360-22", {}))
        flags = sum(r.status == "FLAG" for r in fs.rows)
        flag_lines += [f"FR: {r.check}, D/C {r.dc:.2f} ({r.combo})" for r in fs.rows if r.status == "FLAG"]
        contents.append(dict(mark="FR", title="3D Frame Analysis", code="AISC 360-22", flags=flags))
    es = existing_sheet(project, members)
    if es is not None:
        items.append(("simple", es, "", {}))
        contents.append(dict(mark="EX", title="Loads on Existing Construction", code="", flags=0))
    sm = summary_sheet(project, [(c["mark"], c["title"], it[1]) for c, it in zip(contents, items)])
    if sm is not None:
        items.insert(0, ("simple", sm, "", {}))
        contents.insert(0, dict(mark="SUM", title="Design Summary", code="", flags=0))
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
