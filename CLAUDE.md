# StruKit — instructions for every Claude session

StruKit is Zach Thatcher's in-house structural calculation and report program (Thatcher Engineering, LLC; Zach is a Colorado PE and the
engineer of record). It works like StruCalc or RISA: member and connection screens you type into, live results, calc-package PDFs, and a
building model with a 3D frame on top. Python package `strukit`; window in `strukit/gui`; installed on Zach's laptop from the `release` branch.

The full history is in `docs/STRUKIT-BUILD-LOG.md`; every ruling Zach has made is in `docs/STRUKIT-RULINGS.md`. Read the rulings file before
asking Zach anything: if it is ruled there, do not ask again. The same two files also live in the claude.ai Project "ProgeCAD" as
`claude/STRUKIT-BUILD-LOG.md` and `claude/STRUKIT-RULINGS.md`; keep both copies in step when either changes.

## How to work with Zach
- He is an engineer, not a software developer, and usually reads on his phone. Bottom line first, plain engineering language, short.
  Do software steps for him rather than telling him how.
- Standing instruction: work down the "Next" list in the build log without asking. Work in stretches; check in once at the end of a
  stretch (what StruKit can now do, what changed, what needs his ruling), not after every build.
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
- Members are drawn as what they are (steel as steel shapes, wood with grain; sawn, LVL and glulam look distinct). Beams and columns carry
  loading diagrams; beams also shear and moment diagrams. Every connection sketch is dimensioned (plan and section where one view is not enough).
- No text may overlap other text or run past the margin. `tests/conftest.py` audits every sheet the suite builds with
  `tools/overlap_audit.py`; a finding fails the test. The audit cannot see text lying on a drawn line, so look at new pictures.

## Build, test, release
- `export PYTHONPATH=<repo>`; run `python -m pytest -q` (about 2 minutes). Every test must pass before anything is committed.
- Bump `strukit/__init__.py` `__version__` for each build, add an entry to `docs/STRUKIT-BUILD-LOG.md`, then run
  `sh tools/release.sh "subject"`: it runs the tests, refuses to commit on any failure, commits, pushes `main`, and rebuilds the `release`
  branch (`tools_make_release.sh`), which the laptop's updater downloads. Push after every build; never keep the only copy in a session.
- Open each new or changed screen in a browser before release (the window: `python -m strukit.gui --port N --no-browser`).
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
Zach's reference folder: `C:\Users\zacht\OneDrive\Desktop\StrucutralDesign` (spelled that way). On file: AISC 360-22, AISC Design Examples
v16.0, AISC Shapes Database v16.0, AISC Manual 15th Ed. (low-resolution scan), AISC Design Guides 1 (3rd), 21, 24 (2nd), 34, 39, 40,
ACI 318-19, ASCE/SEI 7-22 (page images), NDS 2018 and Supplement, SDPWS 2021, the engineered lumber code reports and guides, the Simpson
C-C-2026 catalog, the SEAOC Wind Design Manual. Not on file: ASCE 7-16, AISI S100, ASABE EP484/EP486. A cloud session keeps text copies
under `/home/claude/refs` (not in the repo).
