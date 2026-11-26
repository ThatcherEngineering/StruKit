# StruKit references: which file is which, and where in it StruKit reads

Zach's reference folder: `C:\Users\zacht\OneDrive\Desktop\StrucutralDesign` (spelled that way) on his laptop. Every standard StruKit uses is
there. A session stages only the file the item in hand needs (device tools), extracts text with `pdftotext -layout`, and reads tables and
figures from page images (`pdftoppm -r 220` to `-r 330`; `tesseract` for scanned pages). Nothing from these files goes into the repo: the
values StruKit uses are typed into `strukit/data/` and the code, each with its table, figure or equation number. "pdf p." below is the
page number in the PDF file, not the printed page number. More page numbers are in the build log entry of the build that used them.

| Standard | File in the folder | Used for, and where |
|---|---|---|
| AISC 360-22 Specification | `A360-22W-ewr.pdf` | All steel. Has text. Commentary benchmark problems C-C2.2, C-C2.3 (3D frame tests). Chapter K for HSS connections. |
| AISC Design Examples v16.0, Vol. 1 | `P901-23W.pdf` (also `790747119-AISC-Steel-Design-Examples-v16-0.pdf`) | Validation of beams, columns, tension, connections (Examples C.1A, D.1, D.2, E.9 to E.14, E.14B, F.2 to F.9, G.2 to G.5, G.8A, G.8B, II.A-6, II.A-7, II.A-11, II.A-12, II.A-13, II.A-17, II.B-1, II.B-2, J.6, J.7). Cites the 16th Ed. Manual (its Manual equation numbers are the 16th's). Figures with beam sizes are images, not in the text. |
| AISC Design Examples v16.0, Vol. 2 | `P902-23W.pdf` | Design tables; not yet used. |
| AISC Shapes Database v16.0 | `SHAPE160.xlsx` | All section properties (`tools/parse_*.py`, `tools/add_k1.py`, `tools/add_T.py`). |
| AISC Manual, 15th Ed. | `424307777-AISC-15th-Steel-Construction-Manual-pdf.pdf` | Low-resolution scan; embedded text unusable. Read pages as 520 to 560 dpi images. Table 10-9 at pdf p. 1177; Part 10 seated connections pp. 10-69 to 10-71. |
| AISC Manual, 14th Ed. | `329391877-AISC-Steel-Construction-Manual-14th-edition-...pdf` | 300 dpi scan, OCR (tesseract) works. Part 10 stiffened seats pdf pp. 1250-1258 (Fig. 10-10, column web limits, Tables 10-7 and 10-8 with the column-web limitation rows). |
| AISC Design Guide 1, 3rd Ed. (base plates) | `Steel-Structures2024-[www.konkur.in].pdf` | Base plates and anchor rods: Sect. 4.3.1, 4.3.7, 4.3.8; Examples 4.7-3, 4.7-9, 4.7-14. |
| AISC Design Guide 21, 2nd Ed. (welds) | `683124131-Steel-Design-Guide-21-...pdf` | Not yet used. |
| AISC Design Guide 22 (facade attachments) | `532198909-Design-Guide-22-...pdf` | Not yet used. |
| AISC Design Guide 24, 2nd Ed. (HSS connections) | `719353933-AISC-Design-Guide-24-...pdf` | Shear tab to HSS (Ex. 5.1, 5.3), cap plate (Ex. 6.1), beam to HSS column moment connections (Ex. 6.2 to 6.5), Eq. 2-19. Cites the 16th Ed. Manual. |
| AISC Design Guide 34 (stairs) | `674562233-34-AISC-Design-Guide-34-...pdf` | Stringers, treads, guards (Examples 10.1.2 to 10.2.3). |
| AISC Design Guide 37 (hybrid steel and CLT) | `654785860-AISC-DG-37-...pdf` | Not yet used. |
| AISC Design Guide 39 (end-plate moment connections) | `676665841-End-Plate-Moment-Connections.pdf` | End plates: Examples 5.2-1, 5.2-2, 5.3-1, 5.3-2; Appendix A Tables A-2 (text p. 13507 of the extract). Cites the 15th Ed. Manual. Fractions extract as odd glyphs. |
| AISC Design Guide 40 (rain and ponding) | `719353002-Steel-Design-Guide-40-...pdf` | Rain Load screen: Examples 1, 2, 5. |
| AISC connection teaching toolkit | `635084757-AISC-Connection-Teaching-AISC-Toolkit.pdf` | Not yet used. |
| ACI 318-19 | `ACI-318-19.pdf` | Footings, anchorage (Chapter 17). |
| ASCE/SEI 7-22 | `885219892-ASCE-SE-7-22.pdf` (240 MB, page images only; OCR) | Combinations pdf pp. 68-70; live load 74-79; rain 132; snow ch. 7 (drifts Sect. 7.7 p. 126, sliding Sect. 7.9 pp. 128-129); seismic ch. 11-12 pp. 162-195 (Table 12.2-1 sideways pp. 173-175); wind ch. 26 pp. 322-342, ch. 27 pp. 343-353, ch. 29 pp. 360-365, ch. 30 pp. 376-400. |
| SEAOC Wind Design Manual (ASCE 7-16) | `526025875-Wind-Design-Manual-...pdf` | Wind validation: Examples 1, 2, 8A, 8B, 16. |
| NDS 2018 | `NDS-2018-National-Design-Specification-for-Wood-Construction.pdf` | All wood. Connections ch. 11-12 (pdf pp. 80-103), Appendix E. Copied into the folder 2026-11-25 from Zach's chat upload. |
| NDS 2018 Supplement | `NDS-2018-Supplement-Design-Values.pdf` | Tables 4A to 4E, 5A, 5B. Copied into the folder 2026-11-25. |
| SDPWS 2021 with commentary | `721340051-Special-Design-Provisions-...pdf` | Shear walls and diaphragms: Tables 4.2A, 4.2C, 4.3A (pdf pp. 33, 35); Sect. 4.2.6 open front structures (pdf p. 27); Commentary Example C4.2.6.1-2, Eq. 4.2-2 (pdf p. 99, image). |
| AWC shear wall slides; WoodWorks mid-rise slides | `318966905-Shearwall-Design-Examples.pdf`; `471022586-Lateral-Design-...pdf` | Background and factor tables only. |
| Boise and Weyerhaeuser code reports and guides | `ESR-1040...`, `ESR-1153.pdf`, `ESR-1336.pdf`, `ESR-1387.pdf`, `GLM-5000...`, `LVL-*`, `MTP-W7000...`, `MTP-W7010...` | LVL, PSL, LSL, glulam, I-joists. |
| Simpson C-C-2026 catalog | `Simpson\C-C-2026.pdf` | Hold-downs (pp. 59-67). |
| TMS 402/602-16 | `715304102-TMS-402-602-16-Masonry-Code.pdf` | Sign-in protected; cannot be read. Do not work around it. |

Not on file: ASCE 7-16, AISI S100, ASABE EP484 / EP486.
