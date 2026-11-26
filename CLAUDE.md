# StruKit — instructions for every Claude session

StruKit is Zach Thatcher's in-house structural calculation and report program (Thatcher Engineering, LLC; Zach is a Colorado PE and the
engineer of record). It works like StruCalc or RISA: member and connection screens you type into, live results, calc-package PDFs, and a
building model with a 3D frame on top. Python package `strukit`; window in `strukit/gui`; installed on Zach's laptop from the `release` branch.

Start every session with the **"Current state" section at the top of `docs/STRUKIT-BUILD-LOG.md`**: where everything lives, readings
waiting for Zach, what is needed from him, and the Next list in order. Update that section before the session ends. The full history is the
rest of the log; every ruling Zach has made is in `docs/STRUKIT-RULINGS.md`. Read the rulings file before asking Zach anything: if it is
ruled there, do not ask again. The same two files also live in the claude.ai Project "ProgeCAD" as
`claude/STRUKIT-BUILD-LOG.md` and `claude/STRUKIT-RULINGS.md`; keep both copies in step when either changes.

## How to work with Zach
- He is an engineer, not a software developer, and usually reads on his phone. Bottom line first, plain engineering language, short.
  Do software steps for him rather than telling him how.
- Each weekday morning (5:10 AM Denver, scheduled session) starts with ONE check-in: the Next list in order with rough sizes, readings
  waiting for him, what he needs to supply. Build nothing until he replies with a go (Zach, 2026-11-25 12:43). If the scheduled task is
  ever edited, keep this check-in-first rule.
- Once he says go: build what he picked, in stretches of about 30 minutes, and check in at the end of each stretch (what StruKit can now
  do, what changed, what needs his ruling), not after every build.
- Ask only for a real decision that is his: a reading of a code provision that could go two ways, or something only he can supply.

## Hard rules
- Every number cites its source. Nothing is assumed silently.
- Every module is validated against an independent reference (a published worked example from AISC, ASCE, AWC, APA, a Design Guide, a
  manufacturer's table) recorded as an automated test before it is released. Where no example exists, say so in the log and test by hand.
- Where a provision can be read two ways, use the more conservative value and tell Zach (in chat, never on a sheet). Record it in the
  rulings file under "applied, not ruled" until he rules.
- Look up current code adoptions and amendments; do not rely on memory.
- Never write to Zach's drawing files or job folders. Read only. Ask before rebuilding anything he made.
- StruKit work does not write ProgeCAD LISP. The ProgeCAD side waits until Zach says.
- Jobs 2026-001, 2026-011 and 2026-030 are finished, built jobs used as test material only. Do not report what fails or is missing on those
  jobs, and do not ask him for rulings, reactions or dimensions for them. StruKit itself keeps flagging exactly as it does.
- The 2026-030 (Wayfarer carports) workbook shows the scope and layout of a whole-building package. Its numbers and methods are NOT a
  reference for anything (Zach, 2026-11-24: "don't use those wayfarer calcs as gospel").
- Do not ask for RISA; he will supply it later as the 3D comparison tool. Do not raise the licence marks on the reference PDFs again.
- The TMS 402/602-16 PDF is sign-in protected. Do not work around the protection. CMU walls wait for a copy that opens normally.
- Every member and connection screen stays a stand-alone check forever. The building model and 3D frame are an optional layer on top.

## Printed sheets
- Sheets read professional and factual, not as a design log. A sheet states what was used and its code reference. Never on a sheet: why
  one reading was chosen, what another reading would give, that Zach ruled something, what documents are on file, how a module was
  validated, or anything about StruKit's history. Stated assumptions and a "not checked on this sheet" list are fine.
- "Thatcher Engineering standard" appears on a sheet only where Zach has actually ruled. Never his name.
- No seal or signature box anywhere: Zach stamps his own cover sheet, which goes in front of StruKit's package.
- **High visual detail standard (Zach, 2026-11-26 02:13 and 02:26; applies to every StruKit chat, every picture, forever).** StruKit is
  designed to a high visual detail standard: every picture must look like the real member or connection, the way a detailer would draw it,
  not a diagram of boxes. In particular:
  - HSS look like HSS: in plan or section the wall at its thickness with rounded corners and the hollow inside
    (`memberart.hss_plan`); in elevation the corner lines (`memberart.hss_elevation`); cut lengthwise, two hatched walls
    (`memberart.hss_cut_side`). Pipe and round HSS are round.
  - W shapes show their flanges and web in every view (`memberart.steel_section`, `memberart.w_side`); channels, angles and tees by
    their own shape. Plates show their thickness; bolts show heads and nuts in section; welds are drawn where they are.
  - Wood shows grain; sawn, LVL and glulam look distinct. Concrete is stippled; grout and soil read as what they are.
  - Every member that is part of the connection is drawn (the column on a base plate, the beam on a seat), cut short with break lines
    rather than left out. Cut surfaces are darker than surfaces seen beyond the cut; hidden edges are dashed.
  - Connections get the views that show how they go together: an elevation plus a plan or section when one view is not enough.
  - Before releasing any new or changed picture, render it and look at it; a picture that reads as boxes or lines is not finished.
- Members are drawn as what they are (steel as steel shapes, wood with grain; sawn, LVL and glulam look distinct). Beams and columns carry
  loading diagrams; beams also shear and moment diagrams. Every connection sketch is dimensioned (plan and section where one view is not enough).
- No text may overlap other text or run past the margin. `tests/conftest.py` audits every sheet the suite builds with
  `tools/overlap_audit.py`; a finding fails the test. The audit cannot see text lying on a drawn line, so look at new pictures.

## Build, test, release
- `export PYTHONPATH=<repo>`; run `python -m pytest -q` (about 2 minutes). Every test must pass before anything is committed.
- Bump `strukit/__init__.py` `__version__` for each build, add an entry to `docs/STRUKIT-BUILD-LOG.md`, then run
  `sh tools/release.sh "subject"`: it runs the tests, refuses to commit on any failure, commits, pushes `main`, and rebuilds the `release`
  branch (`tools_make_release.sh`), which the laptop's updater downloads. Push after every build; never keep the only copy in a session.
- Open each new or changed screen in a browser before release: `python tools/browser_check.py project.strukit [--select MARK]` loads a
  project in the window headlessly and reports every member's result and any page error.
- A new screen type is registered in `strukit/gui/calc.py` `FORMS` and `build()`, `strukit/cli.py` `KIND_OF`, and the set assertion in
  `tests/test_gui.py`; its picture is dispatched in `strukit/calcsheet.py` `_block_picture`.

## Code map (main pieces)
- `strukit/gui/calc.py`: screen schema (`FORMS`), `build(kind, values, project)`, reactions, takedown, building model, 3D frame runs
  (`model_frame_sway`), bent quick start (`bent_building`), `package_pdf`, design summary and frame sheets.
- `strukit/gui/server.py`, `strukit/gui/static/app.js`: the window.
- `strukit/calcsheet.py`: page layout, check summary, every picture. `strukit/memberart.py`: drawing helpers and dimensions.
- `strukit/ws_*.py`: worksheet (sheet) builders. `strukit/frame3d.py`: space frame, second order. `strukit/wind.py`, `snow.py`,
  `seismic.py`, `liveload.py`, `rain.py`: loads. `strukit/wood.py`, `dowel.py`, `shearwall.py`, `diaphragm.py`: wood.
  `steel_beam.py`, `steel_column.py`, `hss.py`, `bolts.py`, `welds.py`, `base_plate.py`, `cope.py`: steel. `strukit/data/`: tables.
- `tests/data/*.strukit`: stored job projects (test material only); `jobs/`: their builders.

## References
Every standard is in Zach's folder `C:\Users\zacht\OneDrive\Desktop\StrucutralDesign` (spelled that way) on his laptop. `docs/REFERENCES.md`
says which file is which (several have numbered names) and which pages and examples StruKit reads. Stage only what the item in hand needs;
never put the standards or their text in the repo. Missing references (design guides and standards a build is waiting on) are logged in `docs/REFERENCES.md`,
"Missing references log": keep it current as you build (Zach, 2026-11-26) and list it in check-ins. TMS 402 is unreadable.
