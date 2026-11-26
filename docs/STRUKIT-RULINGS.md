# StruKit — Zach's Rulings (so no chat asks twice)

Dated entries. Each is Zach's own decision; open questions live in the proposal and findings docs until he rules. Build history and what is / is not built: `STRUKIT-BUILD-LOG.md`.

## 2026-11-20
- **Name:** the tool is "StruKit" (the brief's "StructKit" was a working name).
- **Calc types wanted ("Yes to 1-6"):** wood beams / joists / posts (NDS); steel beams and columns incl. mezzanine framing (AISC); spread and continuous footings; post-frame embedment and pier foundations; wind / snow / seismic load generation (ASCE 7); CMU walls.
- **Loads standard by jurisdiction (13:53):** ASCE 7-22 is the main engine, built and validated first. ASCE 7-16 is carried only where a jurisdiction still on the 2021 IBC needs it (snow and load combinations for Pueblo / PRBD and El Paso County / PPRBD), and drops out when those agencies adopt the 2024 code. Zach first proposed 7-22 for everything; he agreed to by-jurisdiction because the agencies' prescribed ground snow values are 7-16-style numbers that under-design if run through 7-22.
- **What StruKit is like (14:00):** a program like StruCalc or RISA: structural calc software you open and work in. Full building modeling is not expected yet. Member-by-member worksheets you type into (project tree, inputs, live results); the run from a file uses the same calculations.
- **Worksheet scope (14:05):** all of it: beams, headers and rafters; posts and columns; footings; shear walls and lateral; connections; retaining walls.
- **Input is one plain text file (17:23; proposal 8.4 / roadmap decision 6):** yes. Format: `STRUKIT-INPUT-SPEC.md`.
- **The bridge may run StruKit (17:23; roadmap decision 7):** yes. Approved commands: preflight, run, version.
- **File formats (17:23):** Zach accepts whatever the StruKit and ProgeCAD chats agree between them.
- **ACI 318-19 (17:51):** Zach owns the PDF and approved StruKit using it.
- **StruCalc (17:51, 17:54):** Zach no longer has StruCalc and uses no structural calc software now. Past StruCalc output (e.g. job 2026-011) is still a valid comparison; new comparison runs are not possible.
- **No steel job available (18:02):** Zach cannot supply a past steel job. Steel is validated against the AISC Design Examples only.
- **Footing shear follows ACI 318-19 as written (18:08):** one-way shear by Table 22.5.5.1(c) at d from the critical section, two-way shear with the average d (22.6.2.1), size effect neglected per 13.2.6.2. StruKit does NOT reproduce StruCalc's method (2√f'c with a depth of 8 in on a 10 in footing; section at d/2), which gave higher shear capacities on 2026-011 (Footing A: 19,718 vs 10,993 lb one-way, 61,455 vs 47,662 lb two-way; continuous footing: 15,774 vs 4,138 lb/ft). Where StruKit and old StruCalc output differ for this reason, that is expected.

## 2026-11-21
- **Stem wall weight is part of the footing's factored load (08:02):** a continuous footing's strength checks include the stem wall's own weight times the dead-load factor of the governing combination. StruCalc left it out (2026-011 continuous footing: Mu 297.2 lb-ft without, 335.9 with).
- **Build order (08:02):** bolts, then the worksheet screens and calc sheets.
- **Calc sheet layout approved (08:10):** "I think it looks good." Member data, pictures, loads, load combinations, governing calculation line by line with equation references, check summary, FLAG boxes, assumptions.
- **Members are drawn to look like what they are (08:10, approved 08:15):** steel drawn as a steel shape (flanges and web in the side view, a to-scale cut section), wood drawn as wood (grain in the side view, end-grain rings per ply in the section). Extended on the same principle to concrete (stipple, bars shown) for footings.
- **Columns must handle lateral load, including shear (08:34).** Built in 0.12.0 for columns held against sidesway.
- **Cantilevered and moment-frame columns are needed (08:46).** Cantilevered columns built in 0.13.0.
- **Frames: every shape, not one (08:54):** "Single bay, multiple bays, single story, multiple story, sloped rafters, everything." One general plane-frame engine (0.14.0); the frame worksheet (0.15.0) offers the shapes as starting layouts on top of it.
- **Sheet header and footer match HydroKit's (09:08, relayed by Zach from the HydroKit chat, HydroKit build 2026-11-21e):** logo; "Thatcher Engineering, LLC"; e-mail and phone; **no street address**; project name, job number, site address; date as "Nov 21, 2026"; "Sheet N of M"; navy rule; footer with the basis of the sheet at left and **"Prepared with StruKit <build> · Thatcher Engineering, LLC"** at right; IBM Plex Sans / Mono; colours navy #213651, ink #1B2430, secondary #3A4756. Built in 0.15.0. Details: `STRUKIT-TO-HYDROKIT-2026-11-21.md`.
  - **The tool name in the footer is confirmed (09:17, "Everything looks fine")** after it was pointed out that it replaces the older preference that calc sheets never carry tool names. Still in force: no run IDs on worksheet sheets, no design or revision logs, PE stamp on the cover only, titles in title case.
- **Frame sheets and the direct analysis method for frames and sway columns: seen and accepted (09:17, "Everything looks fine").** The stability method was stated to Zach three times on 2026-11-21 and is printed on every sheet; he has raised no objection. Columns held against sidesway use the effective length method (AISC 360-22 App. 7.2, K as entered) with the App. 8 B1 multiplier; sway columns and frames use the direct analysis method (Ch. C).
- **"Keep working and finishing your list" (09:17, repeated 09:33, 09:47, 09:56):** standing instruction to work through the not-built list in `STRUKIT-BUILD-LOG.md` without asking, checking in with what changed.
- **Sketches of steel connections, connectors and base plates carry dimensions (09:47, 09:51, 09:57):** "I like the dimensions, specifically anything to do with steel connections and connectors and anything like that ... It's very helpful." Bolt sketch: spacing and edge distance on a dimension line. Weld sketch: a plan and a section, weld length and leg dimensioned ("Plan view and section view would be amazing"). Base plate: plate and support dimensioned. Standing rule for every connection-type sketch StruKit draws from now on: dimension it, and give a plan and a section where one view does not show the detail.
- **Order of work (10:03):** "Do the column bases now. We can work on ProgeCAD later." The ProgeCAD side (reading `<name>-struct.csv`, input spec draft 2, schedules) waits until Zach says.
- **No footing-with-moment calc exists (10:03):** "I don't have a footing with moment." Do not ask again. That module stays validated by hand statics and the centred case.
- **Wood and loads (10:03):** "I will get the wood and loads soon" (NDS and ASCE 7). Supplied 2026-11-23.
- **Rod anchorage in concrete approved to build (10:12):** "Yes let's do the anchorage." Built in 0.21.0 (ACI 318-19 Chapter 17).
- **Zach asked what is built without the books (10:12).** He was given the list (it is in `STRUKIT-BUILD-LOG.md`) and told which documents cost nothing.

## 2026-11-23
- **AISC Design Guide 1, 3rd Edition supplied (06:36).** Zach uploaded it; StruKit's base plate with moment follows and is tested against it (build 0.22.0).
- **Where two readings of a provision exist, use the more conservative value (06:43):** "I would rather use the more conservative value." Asked about breakout of a row of anchor rods with 11 to 25 in. embedment: ACI 318-19 Eq. 17.6.2.2.3 (higher) is worded for a single anchor, while AISC Design Guide 1 Example 4.7-11 applies it to a row. **StruKit uses Eq. 17.6.2.2.1 (lower) for a row and Eq. 17.6.2.2.3 only for a single rod.** Do not ask this again. Applied since on the same principle, each told to Zach when built:
  - LVL stability modulus: the code report's NDS Appendix D formula (factor 1.03), not Boise's guide value (1.05).
  - LVL and PSL deflection: bending plus the shear deflection the code reports call for (StruCalc showed bending only).
  - Square composite columns: the lower (plank) bending and shear values about both axes.
  - Table 4.3A note 2 increase, Southern Pine glulam shear increase, single-species bearing increases: not taken.
  - Windward snow drift taller than the clear height at a roof step: width 8 x (0.75 hd) as ASCE 7-22 Sect. 7.7.1 says, height capped at the clear height (the larger load of the readings).
- **Report sheets read professional and factual, not as a design log (06:45):** "I don't like that note going on the report sheet. These report sheets need to read professional and factual. Not as a design log." Standing rule for every sheet StruKit prints:
  - A sheet states what was used and its code reference. Nothing else.
  - **Never on a sheet:** why one reading or method was chosen over another; what the other reading would have given; that Zach ruled something or that it is a "Thatcher Engineering standard" choice between readings; what documents are or are not on file; how a module was validated; anything about StruKit's own history.
  - That material lives here and in `STRUKIT-BUILD-LOG.md`, and in the code's comments.
  - Still fine on a sheet: stated design assumptions (for example "normalweight concrete", "the plate is centred on the concrete") and the list of checks not made on that sheet.
  - Sheets built before 06:45 on 2026-11-23 (steel, footings, connections, frames) have not all been re-read against this rule yet.
- **Loads order (07:05):** snow first among the ASCE 7-22 loads ("Snow sounds fine").
- **Wood is built to the 2018 NDS (07:05):** "I am going to be rolling with the 2018 since I found a free copy of it. I know its outdated but it will work just fine." The 2021 IBC references NDS 2018; the 2024 IBC references NDS 2024; Zach was told.
- **More timber species (07:33):** done in 0.27.0.
- **Reference folder (07:39):** `C:\Users\zacht\OneDrive\Desktop\StrucutralDesign` (spelled that way) holds every design manual he has supplied. Check it for new files; the list is in the build log.
- **Engineered lumber documents (07:49, 07:50):** Zach asked to be guided to them and for links; he added the Boise and Weyerhaeuser code reports and guides the same morning.
- **Materials look different on the sheets (08:41):** "Can you make the LVLs look a touch different than wood and the glulams look a touch different than LVLs. Just visually." Built in 0.31.1 (`kind` = sawn, lvl, glulam in the drawing code). Keep the three distinct in every new picture.
- **Loading diagrams on beams and columns (10:05), and shear and moment diagrams on wood beams (10:24, "Yes I do").** Built in 0.38.0 and 0.39.0. Every new beam or column sheet type carries a loading diagram; beams also carry shear and moment diagrams.
- **How to work (11:32):** Zach does not want a check-in after every build: "Just go. Keep going for roughly 30 minutes and then check in or if you have a question, or if you finish your list." Standing rule: work in stretches of about 30 minutes, releasing builds as they finish, and check in once at the end of the stretch, or sooner only for a real question or when the list is done. No per-build check-ins.
- **Glulam columns: cap at Boise's table (11:57):** "I think it's fine that theirs used the 2024 NDS let's roll with that version so let's go with your option 2." Asked because StruKit's 2018 NDS calculation matches Boise's glulam column table (GLM-5000, Combination 3, written to the 2024 NDS) for 3-1/8 in. columns and 5-1/8 x 6, but runs 4 to 12 percent above it for other sizes, and Boise's table is not consistent with itself between depths of one width. Ruling: for sizes Boise lists, the column must pass both the calculation and Boise's table value (the lower governs). Built in 0.51.0. Do not ask again.

- **Applied on the "more conservative value" rule on 2026-11-23 afternoon, each told to Zach at a check-in (no objection):**
  - Wind, main system: the area reduction of the -1.3 roof coefficient (Figure 27.3-1 note b) is not taken.
  - Wind, low-slope roof overhang chart (Figure 30.3-2A): the scan shows two end values at 500 ft2 (-1.1 and -1.0) without showing which line takes which; -1.1 is used for every zone.
  - Seismic: for an SD1 between rows of Table 12.8-1 the smaller Cu is used; the permission to set the Seismic Design Category from Table 11.6-1 alone is not taken.
- **Shipped bug, told to Zach 13:34:** the seismic screen's results pane did not draw in builds 0.62.0 to 0.69.0 (the printed sheet was right). Fixed in 0.70.0. Since then every new screen is opened in a headless browser before its build is released.

- **Hip roofs, wind on the main system (14:03):** "I agree with your hip roof design." For each wind direction the roof plane facing the wind takes the windward roof coefficients of Figure 27.3-1 at its own slope, the opposite plane the leeward coefficients, and the planes at the sides go by distance from the windward edge. Do not ask again.
- **Toe-nail penetration (14:03):** "I agree with your toe nail reading." Penetration into the main member = L cos 30 - L/3 (geometry of NDS Figure 12A). Do not ask again.

## Brief rules in force
Every number cites its source; nothing assumed silently; each module validated against an independent reference before use; flags hard or accepted with reason and date; jurisdiction data in a table; same run contract as HydroKit; calc-package-quality reports; private GitHub repo from day one; StruKit chat writes no LISP and never writes to drawings; ambiguous provisions shown both ways for Zach to rule (shown to Zach in chat, not on the sheet; see 2026-11-23). Every picture is drawn to a high visual detail standard: members and connections look like the real thing (see 2026-11-26 02:26).

## Open (not ruled)
- Proposal section 8, items 2-3 (ASD as default; which schedules first). On the StruKit screens the design method is a required choice per project; nothing defaults.
- Findings section 3, items 1-7 (`STRUKIT-JURIS-FINDINGS-2026-11-20.md`).
- Which checks print at the member on the sheets (size and mark only, or D/C too).
- Zach's reaction to the StruKit window itself. It is installed (2026-11-21 09:33); he has not yet said how it looks or works on his machine.
- Rod anchorage, steel shear when both rows are counted on and the rows are farther apart than the edge distance: ACI 318-19 R17.7.2.1 says Case 2 puts the steel shear on the far row alone. StruKit checks the rod steel that way (half the rods), in addition to the AISC J3 rod shear on all the rods counted. This is already the conservative reading, consistent with the 2026-11-23 ruling; Zach has not addressed it specifically.
- The copies of several standards (Design Guide 1, ASCE 7-22, NDS 2018 and Supplement, SDPWS 2021, TMS 402/602-16) carry file-sharing-site or third-party licence marks. Zach was told once on 2026-11-23; whether he replaces them is his call. Do not raise it again.
- **Parapet's own load beside a roof corner (told 13:01):** StruKit uses the full zone 3 roof suction of Figure 30.3-2A for the parapet (Sect. 30.6, Load Case A); note 5 of that figure could be read to allow zone 2 values there. The higher load is used. Zach has not ruled.
- **Group action, one row of bolts in a member loaded perpendicular to grain (told 14:20 on 2026-11-23):** NDS 11.3.6.3 sets that member's area to thickness x "the minimum parallel to grain spacing of the fasteners" for a single row; a single row along the load has no such spacing. StruKit uses the lesser of the spacing in the row and 4 D (lower Cg). Zach has not ruled.
- **Steel special cantilever column systems, Table 12.2-1 line G.1:** left out of the system list; the scan appears to print an overstrength factor of 2-1/2. Enter it from a clean copy of ASCE 7-22 p. 114.
- **Story drift from shear wall sheets:** not connected. A shear wall sheet's deflection is at the load level of the project's method (ASD or LRFD); the drift check needs displacements under the strength-level seismic forces. How to convert (for example ASD deflection x 1.4, or recomputing at strength level) is not decided; the elastic displacements are typed for now.
- Closed 2026-11-23: the 45-degree spread of rod tension into the plate. Design Guide 1 (Sect. 4.3.2 item 4, Appendix B) gives it as the conservative effective width; StruKit uses the lesser of it and the full plate width.

## Standards and references on file (StruKit chat's workspace; originals in Zach's reference folder unless noted)
- Steel: AISC 360-22; AISC Design Examples v16.0 (Vol. 1; Vol. 2 design tables not yet used); AISC Shapes Database v16.0; AISC Design Guide 1, 3rd Edition (2024).
- Concrete: ACI 318-19.
- Loads: ASCE/SEI 7-22 (page images; read by OCR and checked against the page image).
- Wood: NDS 2018 and its Supplement (uploaded to the chat, not in the folder); SDPWS 2021 with commentary; AWC shear wall slides (2008 SDPWS); WoodWorks mid-rise lateral slides.
- Engineered lumber: ICC-ES ESR-1040 (Versa-Lam LVL), ESR-1387 (Microllam, Parallam, TimberStrand), ESR-1336 (BCI joists), ESR-1153 (TJI joists); Boise guides LVL-W2000, LVL-W2003, LVL-W2031, LVL-W2015, LVL-2020, GLM-5000, MTP-W7000, MTP-W7010.
- Masonry: TMS 402/602-16 is in Zach's folder but is a sign-in protected PDF that cannot be read outside its licensed viewer; not usable. CMU walls need a copy that opens normally.
- Real job: 2026-011 Humbargar Residence addition, Castle Rock (`OneDrive\Documents\ZET\JobList\2026-011`): sealed StruCalc calc package (31 pp; 2024 IBC, ASCE 7-22, 2024 NDS, ACI 318-19) and the StruCalc project file `2026-011-StruCalc.vtx`. Wood and LVL members, columns, one isolated footing, one continuous footing. No steel.
- HydroKit's install on the laptop (`OneDrive\Documents\hydrokit`, read 2026-11-21 with Zach's approval, nothing changed): the model for StruKit's Windows folder, setup and update scripts.
- Not on file: ASCE 7-16 (needed for Pueblo / PRBD and El Paso County / PPRBD while on the 2021 IBC), the AISC Steel Construction Manual, ASABE EP484 / EP486, a Weyerhaeuser beam and column guide (no independent check of the Weyerhaeuser products yet).

- **Open, told to Zach 2026-11-23 14:30 check-in (no ruling yet; conservative reading in use):** main wind system roof overhang (Sect. 27.3.3) - the standard does not name the velocity pressure for the bottom surface; StruKit uses qh (not less than q at the eave height).
- **Applied 2026-11-23 15:30, told to Zach at the 15:32 check-in:** wood screw withdrawal counts the tapered tip in the thread penetration (NDS 12.2.2.2 does not exclude it; 12.2.1.2 excludes it for lag screws only). The 1.2 allowable stress increase for the overstrength combinations (ASCE/SEI 7-22 Sect. 2.4.5) is not taken. Steel side plates on a main member loaded perpendicular to grain: full geometry factor at a spacing of 3 D or more in a row (Table 12.5.1B makes the full-value spacing that of the attached member, here the steel plate).
- **Zach 15:30 on 2026-11-23: "I agree"** to the readings listed at the 15:30 check-in. Now rulings, do not ask again: (1) wood screw withdrawal counts the tapered tip in the thread penetration (NDS 12.2.2.2); (2) the 1.2 allowable stress increase for the overstrength combinations (ASCE/SEI 7-22 Sect. 2.4.5) is not taken, and overstrength runs on load case Em with one Omega0 per project; (3) a steel side plate on a main member loaded perpendicular to grain takes the full geometry factor at a spacing in a row of 3 D or more, the plate itself not checked; (4) Mixed Southern Pine and the Dense Structural grades are left out of the Southern Pine build.
- **Applied 2026-11-23 15:45, told to Zach at the 15:47 check-in (conservative readings, no ruling yet):** snow drift on a separated lower structure: the windward drift is not truncated and the hc/hb under 0.2 exemption is not used (Sect. 7.7.2 names neither for separated structures). Washer bearing: Cb is taken only when the user states the washer is 3 in. or more from the member end. Shear walls with different sheathing each side: segments in one line must be equal length (SDPWS 4.3.5.5.1 exception 1 names only walls under 4.3.5.4.1). Collector force: walls on a line share by length.
- **Zach 16:05 on 2026-11-23: "Sounds good"** to the plan stated at the 15:46 check-in: shear wall deflections go into the seismic drift check converted back to strength level, with the redundancy factor kept in them (the rho = 1.0 permission of ASCE/SEI 7-22 Sect. 12.3.4.1 for drift is not taken). Built 0.110.0. Do not ask again. This closes the open item "Story drift from shear wall sheets".

## 2026-11-23 16:49, applied under the standing "more conservative value" ruling (Zach told at the next check-in)
- **Topographic factor, K1.** ASCE/SEI 7-22 Figure 26.8-1 gives K1/(H/Lh) by exposure in its parameter table (ridge: B 1.30, C 1.45, D 1.55) and a table of K1 multipliers built on the Exposure C values whose note d says the multipliers are used for any exposure. StruKit uses the larger of the exposure's value and the Exposure C value. Exposure B gets the C value; D gets its own.
- **Guard top rail** is checked as a simple span between posts (no continuity over the posts).

## 2026-11-23 17:16 to 18:00, readings applied (told to Zach at the 18:01 check-in; none ruled yet)
- **Guard of square or rectangular HSS, load "in any direction" (ASCE/SEI 7-22 Sect. 4.5.1):** StruKit takes the load direction that makes Mrx/Mcx + Mry/Mcy largest, so Mc = 1/(1/Mcx^2 + 1/Mcy^2)^0.5 (0.71 Mcx for a square tube). Checking the horizontal and vertical directions separately, the common office practice, gives 1.41 times that capacity for a square tube. Conservative reading in use; **for Zach to rule.**
- **Round HSS and pipe columns with moments about both axes:** the two moment ratios are added in Eq. H1-1 as the equation is written (not combined as one resultant moment).
- **Slender flange of a square or rectangular HSS in bending:** effective section modulus by taking the ineffective width off both flanges (the simpler, slightly conservative method of AISC Design Example F.8B).
- **Stair stringer deflection:** the horizontal-span deflection times 1/cos^2 of the slope, against the horizontal run over the limit (AISC Design Guide 34 Example 10.1.2). The wood rafter screens compare against the sloped length; the stair screen follows the Design Guide.
- **Continuous steel beams:** each brace point and each support is taken to brace whichever flange is in compression there (stated on the sheet).
- **Open-building minimum wind force (Sect. 27.1.5):** Af is taken as the roof projected on a vertical plane normal to the wind; framing and fascia are not included and the sheet says so.
- **Intersecting drifts:** each wall's drift is the larger of its leeward and windward drifts by peak surcharge.
- **Closed by the 18:05 ruling below.** Asked 2026-11-23 18:01: load duration factor for rain (load case R) on wood members. NDS 2018 Table 2.3.2 lists no duration for rain or ponding. Choices put to Zach: CD = 1.15 (two months, as for snow), CD = 1.0 (ten years, as for occupancy live load), or CD = 0.9 (permanent). StruKit stops on case R in wood members until he rules.

## 2026-11-23 18:05, Zach's rulings (do not ask again)
- **Rain load on wood members: CD = 1.15, as snow** ("Let's do 1.15 as snow"). Built 0.143.0.
- **Guard of square or rectangular HSS: keep the conservative check** ("I like the conservative one"): the load direction that makes Mrx/Mcx + Mry/Mcy largest.
- **Guards:** he wants several guard designs in time (other members and layouts); the simple square tube is fine for now.
- **Ruled 18:10 ("Yes add hip"), built 0.144.0, do not ask again:** wind on an open building with a hip roof. ASCE/SEI 7-22 has no free-roof figure for hip roofs. Proposed: for each wind direction use the pitched free roof figure (27.3-5) with the slope and the dimension L of the roof planes facing that direction, and Figure 27.3-7 is not used. Waits for his answer.


## 2026-11-23 18:10 to 19:10, readings applied (told to Zach at the 19:10 check-in; none ruled yet)
- **Open hip roof where h/L is outside Figure 27.3-5 in one direction** (for example the hip-end direction of a long pavilion, h/L under 0.25): the Figure 27.3-7 zones are used for that direction. Not part of his 18:10 ruling.
- Cladding on an open hip roof: ruled 19:00, see below.
- **Free roof cladding at exactly 10 degrees:** the ridge or valley is taken as an edge (more zone 3 area).
- **Guard posts on a channel stringer:** the channel web is checked for the governing post moment, including 50 lb/ft x post spacing where it applies (Design Guide 34's example uses the 200 lb load only); a square or rectangular post uses its smaller side as N in Eq. 7-1.
- Bent plate stair tread, local buckling of the tread plate: ruled 19:00, see below.
- **Shear tab to HSS:** limited to 2 to 5 bolts until the AISC Manual (Table 10-9) is on file.
- **Flange weld on the base plate with moment:** axial compression is not counted on to reduce the flange force (M / d used whole); axial tension adds half.
- **Base plate in uplift:** rod strength 0.75 Fu Ab (AISC 360-22 Table J3.2), lower than Design Guide 1's Fu Ase; plate bending width limited to the rod spacing along the web where the 45 degree widths would overlap.
- **Snow drift carried to a member parallel to the wall:** the surcharge at the typed distance is used over the member's whole tributary width (type the distance to the near edge of the strip).

## 2026-11-23 19:00, Zach's rulings (do not ask again)
- **Bent plate stair tread: add the reduced width check** ("Add a reduced width check. That's the right thing to do"). The tread plate between the legs is checked as a stiffened compression element: Table B4.1b Case 17 limits, AISC 360-22 Sect. F7.2 (Eq. F7-2; Eq. F7-3 with the effective width of Eq. F7-4). Built 0.163.0. This goes beyond AISC Design Guide 34 Example 10.2.2, whose tread fails under it.
- **Cladding on an open hip roof: yes** ("Sure go number 2"): the pitched free roof cladding figure (30.5-2) on each roof plane at its own slope, hips as edges. Built 0.163.0.
- **AISC Steel Construction Manual:** Zach was surprised it is missing (19:00). It is not in the reference folder. Waiting on him to add it; it opens shear tabs with 6 to 12 bolts (Table 10-9), and lets several items now cited through Design Examples and Design Guides be cited directly (Parts 7, 9, 10, 14).

## 2026-11-23 19:33, real jobs run through StruKit (Zach: "What if you ran it on 2026-011? And 2026-001?")
- Job folder `OneDrive\Documents\ZET\JobList\2026-001` connected with Zach's approval (read only; nothing changed). Its StruCalc working file is machine-readable; its sealed submittals are drawing sheets with no calc text.
- Applied without asking (code provisions, not readings; told to Zach 19:50): NDS 3.10.4 bearing area factor at interior supports; ESR-1336 interpolation of joist reactions between bearing lengths; AISC Eq. A-8-4 Cm for HSS columns when the end moment ratio is entered.
- Zach's 3D goal (19:27): keep building until StruKit works as an efficient 3D design calculator. Plan given: (1) gravity takedown between linked members, (2) a building model of levels and grids, (3) lateral distribution, (4) a 3D frame solver, (5) a 3D view. Open: whether he means the load path handled for him (1 to 3) or true 3D frame analysis.

## 2026-11-23 20:41 — jobs 2026-001 and 2026-011 are built
Zach: "Those two jobs you're running numbers on are built. Like fully built so anything you are flagging is irrelevant to me. However, StruKit needs to be flagging those things. It's just useless information from those two jobs. We fixed those issues in the field already."
- Jobs 2026-001 (Rusler mezzanine) and 2026-011 (Humbargar addition) are finished construction. They are test material for StruKit only. Do not report what fails, is missing or disagrees on those two jobs' drawings, and do not ask him for rulings, reactions or dimensions for them.
- StruKit itself keeps flagging exactly as it does: a row that does not pass is flagged on the sheet. Nothing is relaxed.
- Check-ins say what StruKit can now do and what the job runs showed about StruKit (a missing check, a wrong number, a gap), not about the jobs.
(This replaces a 20:40 entry that misread his first message as "stop reporting failing connections".)

## 2026-11-23 20:54 — both modes, permanently
Zach: "this program needs to do what it's doing now, but also needs to do the eventual 3D goal. I want to be able to check individual pieces if needed like beams, joists, etc."
- Every member and connection screen stays a stand-alone check: open one beam, joist, post, footing or connection, type its loads, get its sheet. Nothing built for the 3D goal may require a building model to use them.
- The takedown and building model are a layer on top: they link members and fill their loads, and every member they fill is the same member screen and sheet, still editable and checkable by itself.
- This answers the open question from 19:27 only in part: whether "3D" means the load path handled for him or true 3D frame analysis is still open.
- **20:59, the 3D question answered:** "I would eventually like to get to the true 3D frame analysis point but that will take a lot." The end goal is true 3D frame analysis. Order stays: gravity takedown, building model, lateral distribution, 3D frame solver, 3D view. Do not ask again.
- **20:59:** "Eventually I will download RISA or a version of it for you to use as a comparison tool. We aren't there yet." The 3D frame solver will be checked against RISA when he supplies it; until then it is validated against AISC benchmark problems and hand solutions. Do not ask for it.

## 2026-11-23 22:31 to 2026-11-24 01:30 — three-hour unattended stretch; the Wayfarer carports are the model
- **22:31** Zach: "I will be away for about 3 hours so you get my permission to just keep building for 3 hours." Builds 0.184.0 on were made in that stretch; each is in STRUKIT-BUILD-LOG.md.
- **22:43 / 22:46** Zach: "try building a project similar to job 2026-032 the wayfarer car ports. That's a prime example of what I'm looking to have StruKit do" and "2026-030 maybe". The job is **2026-030, Wayfarer Vans carports** (2026-032 is another job). His sealed calc reports for it come from his own Excel workbook (`Structural-Calculator-MetalBldg-*.xlsm`): a design summary of every check, parametric input, loads, columns, rafters, portal frame by bent, knee and base connections, purlins, panel, bracing, cross-checks. **That report is the model for what a whole-building StruKit package should do.**
- Job 2026-030 is test material for StruKit, like 2026-001 and 2026-011: read only, nothing in the folder changed, no job findings reported to him.
- **Readings applied and waiting for Zach's ruling (asked at the check-ins, not yet answered):**
  1. Wind on open-building columns: StruKit takes Cf from ASCE 7-22 Figure 29.4-1 by the column's own height / width (1.76 for an HSS8x8 about 11.8 ft tall). His workbook uses 1.30 for columns and fascia.
  2. Wind on the roof-edge fascia: Cf = 2.0 (Figure 29.4-2, flat-sided member), both edges that face the wind counted.
  3. Anchor rod tensile strength: StruKit uses 0.75 x 0.75 Fu Ab (AISC 360-22 Table J3.2) everywhere; Design Guide 1 Table 4-1 values are slightly lower for some sizes (5/8 in.) and slightly higher for others (7/8 in.). Should the lower of the two always be used?
- **Needed from Zach, do not build without them:** the ASCE 7-16 text (edition choice; PPRBD is on 7-16), AISI S100 (cold-formed purlins, girts, panel), a reference or his own method as a Thatcher Engineering standard for an HSS rafter on an HSS column cap plate (the 2026-030 knee).
- Standing practice added this stretch: the release script runs the whole test suite and refuses to push when any test fails.

## 2026-11-24 02:10 — the Wayfarer (2026-030) calcs are not a reference
Zach: "Oh wait don't use those wayfarer calcs as gospel... it was done before I knew any better".
- The 2026-030 workbook and its sealed reports show **what a whole-building package should cover and how it is laid out** (summary of every check, parametric start, frame, connections, bases). That part of the 22:43 direction stands.
- **Its numbers, coefficients and methods are not a reference for anything.** Do not validate StruKit against them, do not adopt a value because the workbook uses it (for example Cf 1.30 on columns and fascia, the 0.6 W / h over 240 drift limit, CN envelope values), and do not present agreement with it as evidence StruKit is right. StruKit's references stay the standards and the published examples.
- The carport test no longer names the workbook's ratios as its reference (it checks statics and equilibrium; the two ratios are a regression pin on StruKit's own values).
- Effect on the readings waiting for a ruling: reading 1 (column wind Cf by Figure 29.4-1) no longer has the workbook's 1.30 as its other side; it stands as the figure's value unless Zach rules otherwise. Readings 2 and 3 are unchanged.
- The drift limit boxes stay blank until Zach gives his own number and source.

## 2026-11-25 10:47 — CLAUDE.md in the repo
Zach asked about moving this work to Claude Code and agreed to a `CLAUDE.md` in the StruKit repo so any session (this chat, a new chat or
Claude Code) starts with the standing rules. `CLAUDE.md` carries the rules in short form; this file stays the full record of rulings.
Copies of this file and the build log now live in the repo under `docs/` as well as in the Project; keep both in step.

## 2026-11-25 12:43 — morning session: check in first, build on his go
Zach changed the scheduled StruKit session: it runs weekdays only at 5:10 AM Denver time; each morning it sends one check-in with the Next
list (and readings waiting, things he must supply, notes from other chats) and builds nothing until he replies with a go. Once he says go,
it builds what he picked in stretches of about 30 minutes. If the scheduled task is edited again, keep the check-in-first rule. This
replaces the "start building on its own" setting of 10:47 the same day.

## 2026-11-25 14:20, applied under the standing "more conservative value" ruling (tell Zach at the next check-in)
- **Compression flange plate unbraced length (AISC 360-22 Sect. J4.4):** the larger of the bolt spacing and the distance from the column face to the first bolt, with K = 0.65. AISC Design Example II.B-1 uses the bolt spacing alone.
- **Stiffened seat, stiffener thickness for 36 < Fy < 50 ksi (0.214.0):** at least 2 w (the Manual names 2 w for Fy = 36 ksi and 1.5 w for Fy = 50 ksi only).
- **Beam coped at the bottom flange only (0.215.0):** web shear yielding and shear rupture are checked on the remaining depth (Design Example K.3 says these limit states do not apply when only the bottom flange is coped). Lateral-torsional buckling of the remaining tee is checked with Lb = the cope length.
- **(Ruled 16:06, see below.) Force-transfer shear walls, corner zones (0.216.0):** checked for the larger of APA T555's (R - sum F) / L and sum F / L (the corner shear of APA's one-opening Diekmann example). For a pier between two openings the second adds both openings' corner forces; the published two-window example (T555 method) states 473 plf where this reading needs 546 plf.

## 2026-11-25 16:06 — Zach's rulings (do not ask again)
- **Force-transfer shear walls, corner zones: the conservative way** ("I like the conservative way. Let's do that"). Each pier's corner zones are checked for the larger of APA T555's net (R - sum F) / L and the corner force per foot of pier, sum F / L (both openings' forces added on a pier between two openings).
- **No seal box on StruKit sheets.** Zach puts his own cover sheet on his calculations and stamps that one. StruKit's package cover keeps the project, basis of design, combinations, contents and flagged checks, with no place for a seal or signature. (This replaces the 2026-11-21 note "PE stamp on the cover only".)
- **Single-angle beam with lateral-torsional restraint at midspan only (0.217.0):** leg local buckling uses Sc = 0.80 of the geometric section modulus, as Design Example F.11B does (Sect. F10.3 names 0.80 for angles with no lateral-torsional restraint).
- **Crane runway beam (0.218.0), AISC Design Guide 7 not on file:** the lateral wheel loads of ASCE/SEI 7-22 Sect. 4.9.4 are taken by the top flange alone (half the section's Sect. F6 y-axis strength) with Eq. H1-1b; Cb = 1.0 for moving wheels; the share of the lateral force to each runway and the deflection limits are typed by the engineer with their basis.

## 2026-11-25 16:51 — no more StruCalc import work
Zach: "I don't use StruCalc anymore and would like to move away from it. That's what StruKit is for." Item 8 of the Next list (reading wood, LVL,
I-joist, post and footing members from StruCalc files) is dropped. Do not propose StruCalc import or StruCalc comparisons as work items. The
existing steel .vtx reader (0.165.0) and the tests that use past StruCalc output as a comparison stay as they are.

## 2026-11-25 18:00 to 18:30, building model readings applied (conservative; tell Zach at the check-in; not ruled)
- (Replaced by 0.226.0, Zach 18:22, see below.) Point loads on a continuous footing line were added to its per-foot load as if at one place (0.223.0 to 0.225.0).
- **Wall weight (0.222.0):** psf x story height x the whole placed length; openings in the wall are not deducted.
- **Existing walls (0.221.0):** both the wind and the seismic shear on an existing wall line are listed (no governing load picked).

## 2026-11-25 18:22 — point loads on continuous footings get pads (Zach's direction)
Zach: "beams and headers ... generate point loads. If those point loads exceed the footer bearing capacity of the continuous footer we need to
be able to size a larger square/rectangular footer at that point load." Built 0.226.0. Applied in it (conservative, not ruled):
- The continuous footing's own capacity under a point load is checked over a length Le of footing: the length typed on the footing for point
  loads (with its source), else the footing width (no spread through the stem wall counted).
- The pad carries the point load plus the footing line's own load and stem wall over the pad's length along the line.
- On the pad's sheet the load arrives through a block the stem wall thickness square (the column size for shear and flexure).
- Larger pads go up in 3 in. steps; their thickness starts at the line's (kept if the engineer changes it), bars at the line's transverse
  bar size and spacing both ways; the pad's own sheet checks bearing, shear, flexure and minimum steel.

## 2026-11-25 19:28, header studs (0.230.0), applied (not ruled; tell Zach at the check-in)
- Jack studs carry the whole end reaction of the header; king studs carry no part of it.
- Jack and king studs: Ke = 1.0 both ways (pinned top and bottom, NDS Appendix G); unbraced out of the wall plane over their full height;
  along the wall at the bracing typed (blank = full height).
- King studs take the wind on the wall (strength-level pressure typed with its source) over half the opening plus half a stud space, shared
  equally among the king studs at that side, as a uniform load over their height; no axial load.

## 2026-11-25 19:40, wood members in the 3D frame (0.231.0), applied (not ruled; tell Zach at the check-in)
- Stiffness of a wood member in the frame: the reference E of its grade (NDS Supplement Tables 4A-4D, 5A; ESR-1040 / ESR-1387), not adjusted;
  glulam columns take Emin (StruKit's Table 5B file has no E). Gross section b x d. Torsion: J of the rectangle, G = E / 16 (approximate).
- In the sway run the frame's 0.8 stiffness reduction (AISC direct analysis method) applies to wood members too.
- Rows of joists or rafters (members with a spacing) and I-joists are not frame members; their loads reach the frame through the load path.
- Wood members are not checked from the frame forces; their own sheets (NDS) are the check.

## 2026-11-25 20:12, shear walls and wood checks in the 3D frame (0.232.0), applied (not ruled; tell Zach at the check-in)
- Shear wall stiffness in the frame: the design shear over the SDPWS Eq. 4.3-1 deflection of its own sheet (a secant stiffness at the design
  load; segments in parallel). It needs the end post area and E and the anchorage slip typed on the wall screen; without them the wall is
  left out of the frame and reported.
- Force-transfer walls: Eq. 4.3-1 for each pier over the full wall height, the sheathing above and below the openings not counted (softer
  than the wall, so more drift).
- In the frame each level is tied by a stiff diaphragm (the walls' design shears still come from the flexible wall-line distribution).
  Existing walls are not in the frame; the new walls take all the lateral load there.
- Column tops bearing on or under wood beams are pinned in the frame (a post cap).
- Wood members checked from the frame forces (ASD projects): NDS Eq. 3.9-1 to 3.9-3, 3.7 and shear at every station; CD from each
  combination; Cr, Cfu, CM, Ct, Ci = 1.0 (wet service or incised members only on their own sheets); a beam's strong-axis buckling length is
  the length between frame joints; CP for built-up columns with Kf in the stack direction. LVL Ft taken without a length factor. Glulam and
  Weyerhaeuser beams carrying axial force from the frame are reported (no Fc or Ft in StruKit's tables for them).

## 2026-11-25 20:33 — Zach's rulings (do not ask again)
- **Existing walls in the 3D frame:** "existing walls need to have the option to be accounted for but also need to just be assumed that they
  work and are just unaccounted for." Built 0.233.0: each existing wall's "Wall in the 3D frame" is assumed to work (rigid, 10,000 kip/in.,
  not checked) unless the engineer types its stiffness or leaves it out. Modelling existing construction in detail is not to be built
  ("It would be a massive build").
- **3D model on the calcs:** "I wish you would include that 3D model on the calcs. It would be really cool if it was near the beginning of
  the report, multiple angles of the model." Built 0.233.0: a Building Model sheet right after the cover with four views.

## 2026-11-25 21:16, rod anchorage on the uplift and biaxial base plates (0.234.0), applied (not ruled; tell Zach at the check-in)
- Biaxial base plate: each corner rod takes half the rod tension from each direction (Tx/2 + Ty/2), the two directions added at the corner
  (the larger, not a square-root combination).
- Biaxial rod tensions for the anchorage come from the bearing block at 0.65 x fp(max) (LRFD) under the factored loads.
- With the concrete length and width left blank, the rods are taken 1.5 hef or more from every edge; the sheet states that as an assumption.

## 2026-11-25 21:24 — Zach's rulings (do not ask again)
- **"Sounds good"** to the 0.234.0 check-in readings, now ruled: (1) biaxial base plate corner rod takes Tx/2 + Ty/2 (added, not a square-root
  combination); (2) biaxial rod tensions for the anchorage from the bearing block at 0.65 fp(max) under the factored loads; (3) with the
  concrete size left blank the rods are taken 1.5 hef or more from every edge, stated on the sheet.
- **Anchor rod calcs link to the foundation or stand alone:** "The anchor rod calcs need to be able to link to a foundation system or be
  independent." Built 0.235.0: each base plate screen can name its footing (live link both ways) or stay stand-alone.

## 2026-11-25 21:46, rods of the shear lug in the concrete (0.236.0), applied (not ruled; tell Zach at the check-in)
- The two rods behind the lug share the bearing-block tension T equally; the rods toward the edge the shear faces take none.
- That T is from Design Guide 1's large-moment procedure at 0.65 fp under the LRFD combinations (the same procedure the lug's steel checks use).
- The rods take no shear (the lug takes it all), so no tension-shear interaction for the rods.

## 2026-11-25 22:20 — Zach's rulings (do not ask again)
- **"Agree"** to the 0.236.0 shear lug readings: the two rods behind the lug share the bearing-block tension equally (the rods toward the edge
  take none); that tension is from Design Guide 1's large-moment procedure at 0.65 fp under the LRFD combinations; the lug takes all the shear,
  so the rods take none and no tension-shear interaction is checked on them.
- **Overnight run:** "I vote you do 1-5 even if you run past the 4 hour time frame": (1) shear lug with net uplift and two-way shear, (2) wall
  weight less the openings, (3) built-up three-plate beams and columns, (4) the column side of the extended end plate, (5) the through-plate
  beam-to-HSS moment connection (Design Guide 24 Example 6.2). Unattended: no questions; conservative readings applied and recorded here.

## 2026-11-25 22:28, shear lug with net uplift (0.237.0), applied (not ruled; tell Zach in the morning)
- Net uplift with the lug moment V e not over uplift x f: no bearing; the two rod rows take Tu/2 +/- V e/(2f) (rigid plate, statics).
  Above that, the Design Guide 1 bearing block with the axial load negative.
- Eq. 17.11.2.2.1a: n = the rods in tension under that combination; Nsa = Ase futa per rod, futa not over 1.9 fya or 125 ksi (fya from the
  rod grade when given, otherwise Fu is used uncapped by 1.9 fya; for F1554 grades the cap does not bind).
- Shear across a single plate lug is not carried by the lug (refused, not checked as a resultant).
- (0.238.0, applied) Deducting openings from the wall weight is the engineer's choice per wall (default: not deducted); when deducted, the
  window and door weight is not added back.

## 2026-11-25 22:54, built-up three-plate sections (0.239.0), applied (not ruled; tell Zach in the morning)
- Where the sign of the moment is not known (columns with moments, the frame's column checks), a singly symmetric section takes the lower of its
  two flexural strengths (either flange in compression).
- Webs without transverse stiffeners only: h/tw not over 0.40 E/Fy (Eq. F13-4, a/h over 1.5), kv = 5.34, no tension field action.
- J and Cw from AISC Design Guide 9 (J = sum b t^3 / 3 with the web's clear height; Cw = ho^2 Iyc Iyt / (Iyc + Iyt)).
- Weight 490 pcf (steel), no allowance for welds.

## 2026-11-25 23:07, column side of the four-bolt extended end plate (0.240.0), applied (not ruled; tell Zach in the morning)
- Column web local yielding at the tension flange uses Eq. 3-47 as written, lb = tbf + 2w + 2tp (Example 5.3-2 leaves out 2w; its flange
  welds are not fillets).
- Panel zone shear adds half the beam axial tension (Example 5.3-1 adds it; Example 5.3-2 subtracts it for its load direction) and takes off
  only the column shear the engineer types.
- Stiffener local buckling: both AISC 360-22 J10.8(b) (ts at least bs/16) and Table B4.1a Case 2 with kc from the column web (Example 5.3-2).
- Stiffener-to-flange welds are sized for the stiffener yield strength (the Design Guide's recommendation), more than J10.8's difference force.
- pso and psi are taken as pfo and pfi (stiffeners centred on the beam flanges, as Example 5.3-2), not over s.

## 2026-11-25 23:23, through-plate moment connection (0.241.0), applied (not ruled; tell Zach in the morning)
- One plate size, bolt pattern and weld for both flanges and both sides, designed for the larger beam moment (as Example 6.4, whose loads can
  reverse).
- Plate in compression between the HSS face and the first bolt with K = 1.0 (the example's value; no end fixity counted on).
- Tearout is taken in its own direction for each part: toward the plate end for the plate, toward the beam end for the flange; the same
  pattern is used at the compression flange (conservative there).
- The plate-to-HSS weld takes the joint's axial force and moment together on the compression side (elastic weld group, throat neglected in
  (H/2)^2, as the example).


## 2026-11-26 01:11 — Zach: go on a two-hour run
"Perfect go ahead" to: (1) external diaphragm (cut-out plate) moment connection, Design Guide 24 Example 6.2; (2) four-bolt extended end
plate at a column top (Design Guide 39 Table A-2(d), (e)); (3) cruciform shear lug; (4) directly welded and welded-tee beam-to-HSS moment
connections (Design Guide 24 Examples 6.3, 6.5); (5) story forces spread by mass; (6) every sheet type re-read against the "factual, not a
design log" rule. Unattended: no questions; conservative readings applied and recorded here.

## 2026-11-26 01:18, cut-out plate (0.242.0), applied (not ruled)
- The unbalanced flange force between the two beams goes to the HSS side walls through the plate welds on those two walls only (the
  example has balanced moments and checks no weld); the weld on the HSS face toward the beams is not counted on.
- Beam flexure at the holes uses the larger beam moment and Mn = Fy Zx where F13.1 does not apply (no lateral-torsional buckling at the joint).

## 2026-11-26 01:25, four-bolt extended end plate at a column top (0.243.0), applied (not ruled)
- Ct = 0.5 when the column top is less than a column depth above the beam's tension flange face (de + pfo < dc).
- The cap plate is checked as a stiffener on its area outside the column web, for the force by Eq. 3-48; its welds for the same force.

## 2026-11-26 01:36, cruciform shear lug (0.244.0), applied (not ruled)
- ACI 318-19 gives no rule for a lug with shear in two directions: the concrete bearing ratios of the two directions are added, and the
  breakout ratios are added (linear interaction), each plate counted only for the shear across its face.
- The corner rod takes half the rod tension of each direction added (as the biaxial base plate ruling of 2026-11-25 21:24); with net uplift
  the uplift is counted in both directions.
- The base plate bending at the lug is checked for each direction separately.

## 2026-11-26 01:45, welded WT flange connection (0.245.0), applied (not ruled)
- With the column moment at the joint left blank, U (Eq. K1-6) uses the beam moment, as Example 6.5 does.
- The HSS crippling uses Qf of the combination with the largest force over Qf; the other checks use the largest force.
- A reinforcing fillet on the flare-bevel welds is not counted on.

## 2026-11-26 01:51, story force by weight (0.246.0), applied (not ruled)
- The default stays "evenly over the building width"; "by the weight in the building model" is the engineer's choice per seismic sheet.
- By weight, the story force is shared by the placed seismic weight between the half-way lines (flexible diaphragm, as the even spread);
  accidental torsion and the weight not placed in the model (typed on the seismic sheet only) are not distributed differently.

## 2026-11-26 02:13 and 02:26 — high visual detail standard (Zach's direction; do not ask again)
- 02:13: "make sure the connections are actually drawn to look like the connections. If it's an HSS make sure it looks like an HSS."
- 02:26: "You then need to put that into the standards and logs for this StruKit design process. Every single chat needs to know that we
  design this application to a high visual detail standard."
- In force for every StruKit chat and every picture: members and connections are drawn as a detailer would draw them (HSS with its wall and
  rounded corners, W shapes with flanges, plates at thickness, bolts and welds shown, every connected member drawn and broken off, cut
  surfaces darker, hidden edges dashed, plan or section added where one view is not enough). New or changed pictures are rendered and looked
  at before release. The full wording is in CLAUDE.md, "Printed sheets".


## 2026-11-26 05:58 and 07:30 — Zach: go on the Next list
05:58: go on Next items 1 to 8 (HSS moment joint, stiffened seats, Manual editions, force-transfer walls, single angles, crane runway, end
plate and built-up, carport). 07:30: add and build the drawing upgrade of the flush and extended end plates, stiffened seat and coped beam end
(with the real support shape behind them), and cantilevered diaphragms and diaphragm openings (item 8(e)). Crane runway: build only web
yielding and crippling under the wheels and continuous runway beams; the rest waits on Design Guide 7 and MHI MH27.1 / CMAA 74.

## 2026-11-26 07:40, welded flange plates (0.248.0), applied (not ruled)
- Plate tensile rupture: U from AISC 360-22 Table D3.1 Case 4 on the longitudinal welds alone; the transverse end weld is not counted on
  (Case 1, U = 1.0, could be read to apply when the end is welded too).

## 2026-11-26 08:30, stiffened seats (0.249.0), applied (not ruled)
- Angle stiffeners (all-bolted) take the plate rule t at least tw Fy,beam / Fy,stiffener.
- The bolts of the angles to the support are checked for bearing and tearout in the angles and the support as well as shear (Table 10-7 counts
  shear only).
- An all-bolted stiffened seat on one face of a column web is refused: the Manual's simplified punching limits are for welded seats.
- A seat width between Table 10-8's widths takes the B limit of the narrower width.

## 2026-11-26 09:05, force-transfer wall deflection (0.250.0), for Zach's ruling
- The sheet's deflection follows APA's pier method (SEAOC 2015): a pier pushed toward an opening is taken from the top of the sheathing below
  it to the top of the wall; away from the openings, the full height; the average of the pier values. The 3D frame stiffness (0.232.0) still
  takes every pier at the full height (softer). 20 ft two-window test wall: 0.47 in. (APA) against 0.60 in. (full height). Not the more
  conservative of the two on the sheet: asked.

## 2026-11-26 10:30, crane runway (0.252.0), applied (not ruled)
- Web local yielding and crippling under a wheel: the wheel taken at the beam end (Eq. J10-3, J10-5a / b); no bearing length unless typed with
  its source.
- Continuous runway beam: Mcx with Lb = the longest span and Cb = 1.0 for positive and negative moment; deflection limit over the shortest span.

## 2026-11-26 10:35 — Zach's ruling (do not ask again)
- **Force-transfer wall deflection: the more conservative way** ("Whichever is more conservative is what I would like to use, and yes the 3D
  frame should match it"). Every pier over the full wall height in both directions, each at its own unit shear, averaged (APA's pier method
  otherwise). The 3D frame takes the wall's stiffness as V over that deflection. Built 0.252.1. This replaces the 09:05 entry.

## 2026-11-26 11:30, end plate at a column top stiffened between the bolts, and stiffened built-up girders (0.253.0), applied (not ruled)
- Design Guide 39 Table A-2(f) prints "dce" in the h1 term; de (column top to the outer bolt row) is used, as in Table A-4(e).
- Stiffened built-up girder: one spacing along the girder; no tension field action in the end panel; the first interior panel checked at a
  from each support.

## 2026-11-26 12:10, carport (0.254.0), applied (not ruled)
- Eave beams and struts carry a roof strip of the width typed; the rafters keep their full tributary load (the strip is counted twice).
- At a portal-bay knee the HSS column's moment about its other axis is added to U (Eq. K1-6 is written for one axis).

## 2026-11-26, reply to the closing check-in — Zach's rulings (do not ask again)
- **"I agree with your conservative rulings."** Every reading listed as waiting at the closing check-in is now ruled, as applied:
  - the 2026-11-26 readings above (welded flange plate U on the side welds; the stiffened seat readings; crane wheel at the beam end, no
    bearing length unless typed, continuous runway Lb = the longest span and deflection over the shortest; DG39 A-2(f) "dce" read as de;
    stiffened girders with one spacing, no end-panel tension field, first interior panel at a; the carport strip counted on the rafters too;
    the other-axis column moment added to U at a portal knee);
  - the 2026-11-26 01:11 run readings (cut-out plate, column-top end plate, cruciform lug, WT flange, story force by weight);
  - the overnight 2026-11-25 22:28 to 23:23 readings (lug net uplift, built-up sections, end plate column side, through plate);
  - the crane runway readings of 2026-11-25 16:06 (lateral wheel loads on the top flange alone, Cb = 1.0, deflection limits typed);
  - the bottom-only cope, the stiffened seat stiffener at 2 w for 36 < Fy < 50 ksi, the compression flange plate length (2026-11-25 14:20);
  - open-building column wind Cf from Figure 29.4-1 at the column's own h/D; fascia Cf = 2.0 with both edges that face the wind counted;
  - **anchor rod tensile strength: the lower of 0.75 Fu Ab (AISC 360-22 Table J3.2) and Fu Ase (AISC Design Guide 1 Table 4-1), always.**
    Built 0.257.0 for every threaded part (anchor rods on every base plate screen, shear lug rods, tension rods, rod braces in the 3D frame).
    It governs only for 5/8 in. rods (Ase / 0.75 Ab = 0.98); the larger sizes keep 0.75 Fu Ab.
- **Diaphragm openings: option (a) for now** ("Do option A for now until I get the design guides needed"): the shear wall force-transfer
  analysis turned flat, checked by hand. Built 0.257.0. When a published diaphragm-opening example is supplied, validate against it.
- **Keep a log of missing design guides as the work goes on.** It is `docs/REFERENCES.md`, "Missing references log"; CLAUDE.md points to it.
- "Continue with the list": build the Next list in order, in stretches of about 30 minutes with a check-in at the end of each.

## 2026-11-26, diaphragm opening (0.257.0), applied (not ruled)
- The shear through the region around the opening is the larger of the diaphragm shears at the two ends of the region, used over the whole
  region (the load inside the region is not deducted).
- Corner zones are checked for the larger of APA T555's (v d - F) / d and the corner force per foot F / d (as the wall ruling of 2025-11-25 16:06).
- The lengths e1, e2 the opening's framing runs into full-depth diaphragm are typed (no default); the members along the opening sides take
  |va - vc| x the longer of e1, e2 (both directions of load) and run the whole region; the members across the depth at the opening ends take
  the larger corner force and run chord to chord.
- Deflection: the Eq. 4.2-1 / 4.2-2 shear term is increased over the region by the largest unit shear around the opening less V / W.

## 2026-11-26 11:10 — Zach: send the PDFs
- "When you finish builds, I like to see the pdfs of what you built." Standing: after each build (or each check-in stretch), send Zach the
  printed sheets of what was built or changed (SendUserFile), made with sample inputs, rendered and looked at first.

## 2026-11-26 11:40, single-angle beam deflection (0.258.0), applied (not ruled)
- An angle with lateral-torsional restraint at midspan only is taken to deflect as unrestrained (principal axes) for the deflection check.
- The deflection limit is compared with the resultant of the vertical and sideways components (not the vertical component alone).

## 2026-11-26 12:25, single angle with axial and transverse load (0.259.0), applied (not ruled)
- Cm = 1.0 for both principal axes (Appendix 8 permits it for transverse loading); length for buckling and for Pe1 the span with K = 1.0.
- Tension takes no reduction of the moments (B1 = 1.0) and is checked by yielding only in H2-1; rupture is left to the end connection.
- An equal-leg angle with axial load is designed on the principal axes, not by the geometric axis provisions of Sect. F10.2(2).
