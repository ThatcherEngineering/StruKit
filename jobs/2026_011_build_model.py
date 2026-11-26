"""Job 2026-011 (Humbargar addition) as one building model: the stored gravity and lateral projects placed on levels in plan, so StruKit links the
load path by position and sends the wind and seismic to the wall lines. Test material only (the job is built).

Plan read from sheet S2 (Main Floor Framing Plan, 3/8 in. = 1 ft, 06/30/2026) by scale, so positions are to about 0.1 ft. X runs across the
27'-3" width (left to right on S2), Y from the Line 1 wall (top of S2) toward the existing house (Line 2). Beam lines: Floor Beam B (3-ply)
at Y = 4.5 from X = 0 to the 3-ply Floor Beam C at X = 11.2; Floor Beam C from the Line 1 wall to Floor Beam A; Floor Beam A (2-ply, three
spans) at Y = 14.896 across the width on posts at the walls and two 3 in. pipe columns. Joist rows: deck joists (Y 0 to 4.5, X 0 to 11.2),
floor joists left (Y 4.5 to 14.896, X 0 to 11.2), right (Y 0 to 14.896, X 11.2 to 27.25) and lower (Y 14.896 to 29.75, X 0 to 21.5); roof
joists across Y 0 to 29.75. Spans of B and C are the drawn lengths (the sealed package used 15 and 14.5 ft)."""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "tests", "data")
grav = json.load(open(os.path.join(DATA, "job_2026_011.strukit")))
lat = json.load(open(os.path.join(DATA, "job_2026_011_lateral.strukit")))
G = {m["values"]["mark"]: m for m in grav["members"]}
Lm = {m["values"]["mark"]: m for m in lat["members"]}

proj = copy.deepcopy(grav["project"])
proj["name"] = "Humbargar Residence Addition, building model (test)"
proj["model"] = dict(levels=[dict(name="Foundation", elev="0"), dict(name="Main floor", elev="9.5"), dict(name="Roof", elev="19")],
                     grids_x=[dict(name="1", at="0"), dict(name="2", at="9.0833"), dict(name="3", at="11.2"), dict(name="4", at="18.1667"), dict(name="5", at="27.25")],
                     grids_y=[dict(name="A", at="0"), dict(name="B", at="4.5"), dict(name="C", at="14.896"), dict(name="D", at="29.75")],
                     existing=[dict(name="Existing house wall, main level", level="Roof", x1="0", y1="29.75", x2="27.25", y2="29.75"),
                               dict(name="Existing house wall, lower level", level="Main floor", x1="0", y1="29.75", x2="27.25", y2="29.75")])
M = []


def put(m, mark=None, **at):
    m = copy.deepcopy(m)
    if mark:
        m["values"]["mark"] = mark
    m["values"].update({k: str(v) for k, v in at.items()})
    M.append(m)
    return m


def drop_links(m):
    m["values"]["loads"] = [r for r in m["values"].get("loads", []) if r.get("label") not in ("floor beam",)]


# floor framing at the main floor
fa = put(G["Floor Beam A"], at_level="Main floor", at_x1=0, at_y1=14.896, at_x2=27.25, at_y2=14.896)
fa["values"]["loads"] = [r for r in fa["values"]["loads"] if r.get("label") == "self-weight"]
fb = put(G["Floor Beam B"], at_level="Main floor", at_x1=0, at_y1=4.5, at_x2=11.2, at_y2=4.5)
fb["values"].update(span="11.2")
fb["values"]["loads"] = [r for r in fb["values"]["loads"] if r.get("label") in ("self-weight", "wall dead")]      # the deck-edge wall stays typed
fc = put(G["Floor Beam C"], at_level="Main floor", at_x1=11.2, at_y1=0, at_x2=11.2, at_y2=14.896)
fc["values"].update(span="14.896")
fc["values"]["loads"] = [r for r in fc["values"]["loads"] if r.get("label") == "self-weight"]
fj = G["Floor Joist"]
put(fj, "FJ-left", at_level="Main floor", at_x1=0.5, at_y1=4.5, at_x2=0.5, at_y2=14.896, at_row=10.7)["values"].update(span="10.396")
put(fj, "FJ-right", at_level="Main floor", at_x1=11.7, at_y1=0, at_x2=11.7, at_y2=14.896, at_row=15.55)["values"].update(span="14.896")
put(fj, "FJ-lower", at_level="Main floor", at_x1=0.5, at_y1=14.896, at_x2=0.5, at_y2=29.75, at_row=21)
put(G["Deck Joist"], at_level="Main floor", at_x1=0.5, at_y1=0, at_x2=0.5, at_y2=4.5, at_row=10.7)
# posts and columns under the main floor beams
for mark, x, y in (("Column A", 0, 14.896), ("Column B", 27.25, 14.896)):
    p = put(G[mark], at_level="Main floor", at_base="Foundation", at_x1=x, at_y1=y)
    drop_links(p)
put(G["Deck Stud Pack"], "Post under Beam B", at_level="Main floor", at_base="Foundation", at_x1=0, at_y1=4.5)["values"]["loads"] = []
for mark, x in (("Pipe Column 1", 9.0833), ("Pipe Column 2", 18.1667)):
    M.append(dict(kind="hss_column", values=dict(mark=mark, shape="PIPE3STD", Fy="35", Fy_source="ASTM A53 Gr. B, 3 in. Sch. 40 pipe (sheet S2)", height="9.5", Kx="1", Ky="1",
                                                k_source="pinned top and bottom", self_weight="yes", loads=[], moments=[],
                                                at_level="Main floor", at_base="Foundation", at_x1=str(x), at_y1="14.896")))
for mark, x in (("Footing A", 9.0833), ("Footing A2", 18.1667)):
    put(G["Footing A"], mark, at_x1=x, at_y1=14.896)
# roof joists, wall to wall
put(G["RoofJoist"], "Roof joists", at_level="Roof", at_x1=0.5, at_y1=0, at_x2=0.5, at_y2=29.75, at_row=26.75)
# walls: main level (top at the roof) and lower level (top at the main floor); continuous footings under the lower walls
for mk, top, p1, p2 in (("Line 1, main level", "Roof", (0, 0), (27.25, 0)), ("Line A, main level", "Roof", (0, 0), (0, 29.75)),
                        ("Line B, main level", "Roof", (27.25, 0), (27.25, 22.58)), ("Line 1, lower level", "Main floor", (0, 0), (27.25, 0)),
                        ("Line A, lower level", "Main floor", (0, 0), (0, 29.75)), ("Line B, lower level", "Main floor", (27.25, 0), (27.25, 22.58))):
    w_ = put(Lm[mk], at_level=top, at_x1=p1[0], at_y1=p1[1], at_x2=p2[0], at_y2=p2[1])
    if w_["values"].get("hd_model"):
        w_["values"]["hd_sdc"] = "A or B"                     # sheet S0: Seismic Design Category B
for mk, p1, p2 in (("Footing Line 1", (0, 0), (27.25, 0)), ("Footing Line A", (0, 0), (0, 29.75)), ("Footing Line B", (27.25, 0), (27.25, 22.58))):
    put(G["Continuous Footing"], mk, at_x1=p1[0], at_y1=p1[1], at_x2=p2[0], at_y2=p2[1])
for mk in ("Wind", "Seismic"):
    put(Lm[mk])
# unplaced, stand-alone checks kept in the project
# Roof Beam A: the LVL header in the Line 1 wall at the roof, from the corner at Line A (sheet S3, by scale: 11.25 ft, the span of its sheet)
rba = put(G["Roof Beam A"], at_level="Roof", at_x1=0, at_y1=0, at_x2=11.25, at_y2=0)
rba["values"]["loads"] = [r for r in rba["values"]["loads"] if r.get("label") == "self-weight"]
for mk in ("Deck Column", "Header A LL", "Header B LL"):
    put(G[mk])

data = dict(format="strukit-project", version=1, project=proj, members=M)
OUT = os.path.join(DATA, "job_2026_011_model.strukit")
if __name__ == "__main__":
    json.dump(data, open(OUT, "w"), indent=1)
    print(len(M), "members ->", OUT)
