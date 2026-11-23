// StruKit window. Everything is calculated by the program on this computer; this page
// only draws the forms and shows what comes back.
"use strict";
const $ = (s, e = document) => e.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v);
  }
  for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
};
const post = async (path, body = {}) => {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return j;
};
const fmt = (v, unit = "") => {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  const a = Math.abs(v);
  const s = a >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : a >= 100 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : v.toFixed(3);
  return unit ? s + " " + unit : s;
};
const toast = (t, ms = 3500) => { const x = $("#toast"); x.textContent = t; x.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => x.classList.remove("on"), ms); };

let INFO = null;
let S = null;            // the open project
let path = null, dirty = false, sel = "project";
const R = new Map();     // member object -> last result

const blank = () => ({ format: "strukit-project", version: 1,
  project: { name: "", number: "", address: "", date: INFO.today, method: "", combos_asd: [{ expr: "", source: "" }], combos_lrfd: [{ expr: "", source: "" }] }, members: [] });

function setDirty(d = true) { dirty = d; drawFile(); }
function drawFile() { $("#file").textContent = (path || "Not saved yet") + (dirty ? "  (changes not saved)" : ""); document.title = "StruKit" + (S.project.name ? " - " + S.project.name : ""); }

// ---------------------------------------------------------------- side bar
function drawNav() {
  const nav = $("#nav"); nav.textContent = "";
  nav.append(el("div", { class: "item" + (sel === "project" ? " sel" : ""), onclick: () => select("project") }, "Project"));
  if (S.members.length) nav.append(el("div", { class: "grp" }, "Members"));
  S.members.forEach((m, i) => {
    const r = R.get(m) || {};
    const st = r.state === "done" ? r.status : r.state === "stopped" ? "stopped" : "";
    nav.append(el("div", { class: "item" + (sel === i ? " sel" : ""), onclick: () => select(i) },
      el("span", { class: "dot " + st }), m.values.mark || "(no mark)", el("span", { class: "kind" }, INFO.forms[m.kind].title)));
  });
}
function select(i) { sel = i; drawNav(); drawMain(); }

// ---------------------------------------------------------------- inputs
function field(f, obj, onchange, inTable = false) {
  let input;
  const val = obj[f.key] ?? "";
  if (f.type === "select") {
    input = el("select", { class: f.required ? "req" + (val === "" ? " blank" : "") : "" }, el("option", { value: "" }, ""), f.options.map(o => el("option", { value: o }, o)));
    input.value = val;
  } else {
    input = el("input", { type: "text", class: (f.type === "number" ? "n " : "") + (f.required ? "req" : ""), placeholder: " ", value: val,
      list: f.type === "shape" ? "shapes" : null, spellcheck: "false", autocomplete: "off" });
  }
  const set = () => { obj[f.key] = input.value; if (f.type === "select") input.classList.toggle("blank", input.value === ""); onchange(); };
  input.addEventListener(f.type === "select" ? "change" : "input", set);
  if (inTable) return input;
  return el("label", { class: "f" }, el("span", { class: "l" }, el("span", {}, f.label + (f.required ? "" : " (optional)")), el("span", { class: "u" }, f.unit || "")), input,
    f.help ? el("div", { class: "help" }, f.help) : null);
}
function table(t, rows, onchange) {
  const body = el("tbody");
  const draw = () => {
    body.textContent = "";
    rows.forEach((row, i) => body.append(el("tr", {}, t.columns.map(c => el("td", {}, field(c, row, onchange, true))),
      el("td", { class: "x" }, el("button", { title: "Remove this row", onclick: () => { rows.splice(i, 1); draw(); onchange(); } }, "✕")))));
  };
  draw();
  return el("div", {}, el("h2", {}, t.label),
    el("table", { class: "t" }, el("thead", {}, el("tr", {}, t.columns.map(c => el("th", {}, c.label + (c.unit ? ", " + c.unit : ""))), el("th"))), body),
    el("button", { class: "addrow", onclick: () => { rows.push({}); draw(); } }, "+ Add a row"),
    t.help ? el("div", { class: "help" }, t.help) : null);
}

// ---------------------------------------------------------------- results
let timer = null;
function recalc(m, now = false) {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    try {
      const r = await post("/api/calc", { kind: m.kind, values: m.values, project: S.project });
      R.set(m, r); drawNav();
      if (S.members[sel] === m) drawResults(m);
    } catch (e) { toast("The calculation could not run: " + e.message, 8000); }
  }, now ? 0 : 280);
}
async function recalcAll() {
  if (!S.members.length) return;
  const r = await post("/api/calc_all", { project: S.project, members: S.members });
  S.members.forEach((m, i) => R.set(m, r.results[i]));
  drawNav(); if (typeof sel === "number") drawResults(S.members[sel]);
}
function frameSvg(fr) {
  const xs = Object.values(fr.nodes).map(p => p[0]), ys = Object.values(fr.nodes).map(p => p[1]);
  const w = Math.max(...xs) - Math.min(...xs) || 1, h = Math.max(...ys) - Math.min(...ys) || 1, pad = Math.max(w, h) * 0.09;
  const X = x => x - Math.min(...xs) + pad, Y = y => h - (y - Math.min(...ys)) + pad;
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w + 2 * pad} ${h + 2.2 * pad}`); svg.setAttribute("class", "frame");
  const add = (tag, a, text) => { const n = document.createElementNS(ns, tag); for (const k in a) n.setAttribute(k, a[k]); if (text) n.textContent = text; svg.append(n); };
  const fs = Math.max(w, h) * 0.035;
  for (const m of fr.members) {
    const a = fr.nodes[m.i], b = fr.nodes[m.j];
    add("line", { x1: X(a[0]), y1: Y(a[1]), x2: X(b[0]), y2: Y(b[1]), stroke: "#2C3847", "stroke-width": fs * 0.42, "stroke-linecap": "round" });
    add("text", { x: (X(a[0]) + X(b[0])) / 2 + (m.role === "column" ? fs * 0.5 : 0), y: (Y(a[1]) + Y(b[1])) / 2 - (m.role === "column" ? 0 : fs * 0.5),
      "font-size": fs, fill: "#3A4756", "text-anchor": m.role === "column" ? "start" : "middle" }, m.name);
  }
  for (const [n, kind] of Object.entries(fr.supports)) {
    const p = fr.nodes[n], x = X(p[0]), y = Y(p[1]), s = fs * 0.9;
    if (kind === "pin") add("polygon", { points: `${x},${y} ${x - s},${y + 1.6 * s} ${x + s},${y + 1.6 * s}`, fill: "none", stroke: "#1B2430", "stroke-width": fs * 0.12 });
    else add("line", { x1: x - 1.6 * s, y1: y + fs * 0.1, x2: x + 1.6 * s, y2: y + fs * 0.1, stroke: "#1B2430", "stroke-width": fs * 0.3 });
  }
  return svg;
}
function drawResults(m) {
  const box = $("#res"); if (!box) return;
  const r = R.get(m); box.textContent = "";
  if (!r) { box.append(el("div", { class: "banner wait" }, "Calculating...")); return; }
  if (r.state === "incomplete") {
    box.append(el("div", { class: "banner wait" }, "Not calculated yet", el("small", {}, r.messages.length + " thing" + (r.messages.length > 1 ? "s" : "") + " still needed")),
      el("ul", { class: "msg" }, r.messages.map(t => el("li", {}, t))));
    return;
  }
  if (r.state === "stopped") {
    box.append(el("div", { class: "banner stopped" }, "Stopped"), el("ul", { class: "msg" }, r.messages.map(t => el("li", {}, t))));
    return;
  }
  const flags = r.rows.filter(x => x.status === "FLAG").length + r.members.filter(x => x.status === "FLAG").length;
  box.append(el("div", { class: "banner " + r.status }, r.status === "OK" ? "All checks pass" : flags + " check" + (flags > 1 ? "s" : "") + " flagged"));
  if (r.frame) box.append(frameSvg(r.frame));
  if (r.members.length) {
    box.append(el("h2", {}, "Members (worst combination for each)"),
      el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Member", "Section", "Combination"].map(t => el("th", {}, t)),
        ["Axial, kip", "Moment, kip-ft", "Shear, kip", "Ratio"].map(t => el("th", { class: "n" }, t)), el("th", {}, ""))),
        el("tbody", {}, r.members.map(x => el("tr", { class: x.status }, el("td", {}, x.member), el("td", { class: "mono" }, x.shape), el("td", { class: "mono" }, x.combo),
          el("td", { class: "n" }, x.axial.toFixed(1) + " " + x.sense), el("td", { class: "n" }, x.moment.toFixed(1)), el("td", { class: "n" }, x.shear.toFixed(1)),
          el("td", { class: "n" }, x.ratio.toFixed(2), el("div", { class: "bar" }, el("i", { class: x.status, style: `width:${Math.min(100, x.ratio * 100)}%` }))),
          el("td", { class: "st " + x.status }, x.status))))),
      el("div", { class: "small" }, "C = compression, T = tension. * = with notional load. Governing member: " + r.governing.member + "."));
  }
  if (r.rows.length) {
    const body = el("tbody");
    for (const x of r.rows) {
      body.append(el("tr", { class: x.status }, el("td", {}, x.check.charAt(0).toUpperCase() + x.check.slice(1)), el("td", { class: "mono" }, x.combo),
        el("td", { class: "n" }, fmt(x.demand, x.unit)), el("td", { class: "n" }, fmt(x.capacity, x.unit)),
        el("td", { class: "n" }, x.dc.toFixed(2), el("div", { class: "bar" }, el("i", { class: x.status, style: `width:${Math.min(100, x.dc * 100)}%` }))),
        el("td", { class: "st " + x.status }, x.status)),
        el("tr", { class: "sub " + x.status }, el("td", { colspan: 6 }, x.source + (x.note ? "  ·  " + x.note : ""))));
    }
    box.append(el("h2", {}, "Checks"), el("table", { class: "r" }, el("thead", {}, el("tr", {}, el("th", {}, "Check"), el("th", {}, "Combination"),
      el("th", { class: "n" }, "Demand"), el("th", { class: "n" }, "Capacity"), el("th", { class: "n" }, "D/C"), el("th", {}, ""))), body));
  }
  if (r.steps.length) box.append(el("details", { open: "" }, el("summary", {}, "Calculation"), el("div", { class: "steps mono" },
    r.steps.map(s => [el("div", { class: "s" }, el("span", {}, s.label + " = " + (typeof s.value === "string" ? s.value : s.unit ? fmt(s.value, s.unit) : s.value.toFixed(2))), el("span", {}, s.source)),
      s.note ? el("div", { class: "note" }, s.note) : null]))));
  if (r.assumptions.length) box.append(el("details", {}, el("summary", {}, "Assumptions"), el("ul", { class: "msg small" }, r.assumptions.map(t => el("li", {}, t)))));
  if (r.not_checked.length) box.append(el("details", {}, el("summary", {}, "Not checked on this sheet"), el("ul", { class: "msg small" }, r.not_checked.map(t => el("li", {}, t)))));
}

// ---------------------------------------------------------------- loads from another member
function fillWallBar(m, changed) {
  const src = S.members.filter(x => x.kind === "seismic_elf" && (x.values.lines || []).some(r => (r.name || "").trim()));
  if (!src.length) return el("div", { class: "fill small" }, "A seismic shear can be filled in from a Seismic Base Shear sheet once it lists its wall or frame lines.");
  const pick = el("select", {}, el("option", { value: "" }, "choose a seismic sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const line = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; line.style.display = "none"; line.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/wall_lines", { values: s.values, project: S.project });
      got.lines.forEach((r, i) => line.append(el("option", { value: i }, "line " + r.line + ", story below " + r.level)));
      line.style.display = "";
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.lines.length) return toast("Choose the seismic sheet first.");
    if (S.project.method !== "ASD" && S.project.method !== "LRFD") return toast("Choose the design method on the Project page first.", 9000);
    const s = S.members[+pick.value], r = got.lines[+line.value], asd = S.project.method === "ASD";
    Object.assign(m.values, { V: String(Math.round((asd ? r.asd : r.Eh) * 1000)), load: "seismic",
      v_source: "sheet " + (s.values.mark || "seismic") + ", line " + r.line + ", story below " + r.level + ": " + (asd ? "0.7 rho QE" : "rho QE") });
    changed(); drawMain();
  } }, "Fill Shear");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the seismic shear from"), pick, line, go);
}

function fillBar(m, changed) {
  if (m.kind === "shear_wall" || m.kind === "perforated_wall") return fillWallBar(m, changed);
  if (m.kind !== "footing_moment" && m.kind !== "footing_iso" && m.kind !== "base_plate_moment") return null;
  const src = S.members.filter(x => x.kind === "steel_column" || x.kind === "frame");
  if (!src.length) return el("div", { class: "fill small" }, "Loads can be filled in from a steel column or moment frame once the project has one.");
  const pick = el("select", {}, el("option", { value: "" }, "choose a column or frame"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const base = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; base.style.display = "none"; base.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/reactions", { kind: s.kind, values: s.values, project: S.project });
      if (got.bases.length > 1) { got.bases.forEach(b => base.append(el("option", { value: b }, "base " + b))); base.style.display = ""; }
      if (got.messages.length) toast(got.messages.join("  "), 12000);
    } catch (e) { toast(e.message, 9000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got) return toast("Choose the column or frame first.");
    const s = S.members[+pick.value], b = got.bases.length > 1 ? base.value : got.bases[0];
    const sv = got.service.filter(r => r.base === b), st = got.strength.filter(r => r.base === b);
    if (m.kind === "base_plate_moment") {
      const use = S.project.method === "LRFD" ? st : sv;
      if (!use.length) return toast("Choose the design method and enter its load combinations on the Project page first.", 10000);
      const f = x => (x / 1000).toFixed(2);
      m.values.cases = use.map(r => ({ name: r.name, P: f(r.P), M: f(r.M), V: f(r.V) }));
      m.values.cases_lrfd = S.project.method === "LRFD" ? [] : st.map(r => ({ name: r.name, P: f(r.P), M: f(r.M), V: f(r.V) }));
      if (S.project.method !== "LRFD" && !st.length) toast("The rod anchorage in the concrete needs the LRFD combinations too (ACI 318 is strength design). Add them on the Project page and fill again.", 12000);
      m.values.loads_from = "base reactions of " + (s.values.mark || "member") + (got.bases.length > 1 ? " at " + b : "") + (s.kind === "frame" || (s.values.ends || "").startsWith("free") ? ", second-order analysis" : "");
      changed(); drawMain(); return;
    }
    if (!sv.length || !st.length) return toast("Both ASD and LRFD load combinations are needed on the Project page: service loads size the footing on the soil, factored loads design the concrete.", 12000);
    const n = x => String(Math.round(x));
    if (m.kind === "footing_moment") {
      m.values.service = sv.map(r => ({ name: r.name, P: n(r.P), M: n(r.M), V: n(r.V) }));
      m.values.strength = st.map(r => ({ name: r.name, P: n(r.P), M: n(r.M), V: n(r.V), wt_factor: r.wt_factor == null ? "" : String(r.wt_factor) }));
    } else {
      const big = Math.max(...sv.concat(st).map(r => Math.abs(r.M)));
      if (big > 50) toast("This base carries moment (up to " + n(big) + " lb-ft). An Isolated Footing ignores it; use Footing with Moment instead.", 14000);
      const a = sv.reduce((p, r) => r.P > p.P ? r : p), u = st.reduce((p, r) => r.P > p.P ? r : p);
      Object.assign(m.values, { P_service: n(a.P), service_combo: a.name, Pu: n(u.P), strength_combo: u.name });
    }
    m.values.loads_from = "base reactions of " + (s.values.mark || "member") + (got.bases.length > 1 ? " at " + b : "") + (s.kind === "frame" || (s.values.ends || "").startsWith("free") ? ", second-order analysis" : "");
    changed(); drawMain();
  } }, "Fill Loads");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the loads from"), pick, base, go);
}

// ---------------------------------------------------------------- pages
function drawMain() {
  const main = $("#main"); main.textContent = "";
  if (sel === "project") return drawProject(main);
  const m = S.members[sel], form = INFO.forms[m.kind];
  const changed = () => { setDirty(); recalc(m); };
  const markF = { key: "mark", label: "Mark", type: "text", required: true };
  const left = el("div", { class: "card" }, fillBar(m, changed), el("h2", {}, form.title),
    el("div", { class: "grid" }, field(markF, m.values, () => { changed(); drawNav(); }), form.fields.map(f => field(f, m.values, changed))),
    form.tables.map(t => { m.values[t.key] = m.values[t.key] || []; return table(t, m.values[t.key], changed); }));
  main.append(el("div", { class: "head" }, el("h1", {}, (m.values.mark || "New member") + " · " + form.title), el("span", { class: "small" }, form.code), el("span", { class: "sp" }),
    el("button", { class: "btn pri", onclick: () => printSheet(m) }, "Print Calc Sheet"),
    el("button", { class: "btn", onclick: () => { const c = JSON.parse(JSON.stringify(m)); c.values.mark = ""; S.members.splice(sel + 1, 0, c); setDirty(); select(sel + 1); } }, "Duplicate"),
    el("button", { class: "btn danger", onclick: () => { if (confirm("Remove " + (m.values.mark || "this member") + " from the project?")) { S.members.splice(sel, 1); setDirty(); select("project"); } } }, "Remove")),
    el("div", { class: "cols" }, left, el("div", { class: "card", id: "res" })));
  drawResults(m); if (!R.get(m)) recalc(m, true);
}
function drawProject(main) {
  const p = S.project;
  const changed = () => { setDirty(); clearTimeout(drawProject.t); drawProject.t = setTimeout(recalcAll, 400); };
  const fs = [{ key: "name", label: "Project name", type: "text", required: true }, { key: "number", label: "Job number", type: "text", required: true },
    { key: "address", label: "Site address", type: "text", required: false }, { key: "date", label: "Date on the sheets", type: "text", required: true, help: "year-month-day, for example 2026-11-21" },
    { key: "method", label: "Design method (steel)", type: "select", options: ["ASD", "LRFD"], required: true }];
  const cols = [{ key: "expr", label: "Combination", type: "text", required: true }, { key: "source", label: "Source", type: "text", required: true }];
  const asd = { key: "combos_asd", label: "ASD load combinations", columns: cols,
    help: "Used for steel designed by ASD, and as the service combinations when a footing takes its loads from a column or frame." };
  const lrfd = { key: "combos_lrfd", label: "LRFD load combinations", columns: cols,
    help: "Used for steel designed by LRFD, and as the factored combinations for concrete. Type each combination the way it is written, for example 1.2D + 1.0S + 0.5W, and give where it comes from, or fill both lists from a standard." };
  const fillBtns = Object.keys(INFO.combo_sets || {}).map(name => el("button", { class: "btn", onclick: () => {
    S.prevCombos = { asd: p.combos_asd, lrfd: p.combos_lrfd };
    p.combos_asd = INFO.combo_sets[name].ASD.map(r => ({ ...r })); p.combos_lrfd = INFO.combo_sets[name].LRFD.map(r => ({ ...r }));
    changed(); select("project");
    toast("Both lists now hold the " + name + " basic combinations. Load case names: D, L, Lr, S, R, W. In " + name + " the snow load S is the strength-level load.", 12000);
  } }, "Fill both lists from " + name));
  const seis = [{ key: "seismic_sds", label: "SDS (for the seismic combinations)", type: "text", required: false, help: "from the ASCE 7 Hazard Tool; used only by the button below" },
    { key: "seismic_rho", label: "Redundancy factor", type: "select", options: ["1.0", "1.3"], required: false, help: "ASCE 7-22 Sect. 12.3.4" },
    { key: "seismic_no_ev", label: "Vertical seismic effect Ev", type: "select", options: ["0.2 SDS D", "zero (Seismic Design Category B)"], required: false, help: "ASCE 7-22 Sect. 12.4.2.2" }];
  fillBtns.push(el("button", { class: "btn", onclick: async () => {
    let r;
    try { r = await post("/api/seismic_combos", { sds: p.seismic_sds || "", rho: p.seismic_rho || "1.0", no_ev: (p.seismic_no_ev || "").startsWith("zero") }); }
    catch (e) { toast(e.message, 9000); return; }
    S.prevCombos = { asd: p.combos_asd, lrfd: p.combos_lrfd };
    const keep = rows => (rows || []).filter(c => !/Sect\. 2\.(3\.6|4\.5),/.test(c.source || ""));
    p.combos_asd = keep(p.combos_asd).concat(r.ASD); p.combos_lrfd = keep(p.combos_lrfd).concat(r.LRFD);
    changed(); select("project");
    toast("The seismic combinations are added to both lists. Load case E is the effect of the horizontal seismic forces; enter it with both signs where the force reverses.", 12000);
  } }, "Add the ASCE/SEI 7-22 seismic combinations"));
  if (S.prevCombos) fillBtns.push(el("button", { class: "btn", onclick: () => {
    p.combos_asd = S.prevCombos.asd; p.combos_lrfd = S.prevCombos.lrfd; S.prevCombos = null; changed(); select("project"); } }, "Put back the previous lists"));
  main.append(el("div", { class: "head" }, el("h1", {}, "Project")),
    el("div", { class: "cols" }, el("div", { class: "card" }, el("h2", {}, "Job"), el("div", { class: "grid" }, fs.map(f => field(f, p, () => { changed(); drawFile(); }))),
      el("div", { class: "grid" }, seis.map(f => field(f, p, changed))), el("div", { class: "fillbar" }, fillBtns), table(asd, p.combos_asd, changed), table(lrfd, p.combos_lrfd, changed)),
      el("div", { class: "card" }, el("h2", {}, "Members"),
        S.members.length ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Mark", "Type", "Result"].map(t => el("th", {}, t)))),
          el("tbody", {}, S.members.map((m, i) => { const r = R.get(m) || {}; const st = r.state === "done" ? r.status : r.state === "stopped" ? "Stopped" : "Not complete";
            return el("tr", { style: "cursor:pointer", onclick: () => select(i) }, el("td", {}, m.values.mark || "(no mark)"), el("td", {}, INFO.forms[m.kind].title),
              el("td", { class: "st " + (r.status || "") }, st)); })))
          : el("div", { class: "small" }, "No members yet. Use “Add a member” at the left, or load the example project to see how the screens work."),
        el("h2", {}, "What StruKit covers today"),
        el("ul", { class: "msg small" }, ["Steel beams, columns (braced, with sideways load, cantilevered) and moment frames: AISC 360-22.",
          "Fillet welds and bolt lines loaded through their centre; base plates under centred load or with moment, with anchor rod steel strength: AISC 360-22 J2, J3, J8, J9.",
          "Isolated and continuous footings, and isolated footings with moment about one axis: ACI 318-19.",
          "Not yet: wood, load generation (snow, wind, seismic), masonry, retaining walls, anchorage of rods in concrete (ACI 318 Chapter 17).",
          "Every blank box is asked for; nothing is assumed."].map(t => el("li", {}, t))))));
}

// ---------------------------------------------------------------- files and printing
async function printSheet(m) {
  try { const r = await post("/api/pdf", { kind: m.kind, values: m.values, project: S.project }); window.open(r.url, "_blank"); }
  catch (e) { toast("This member cannot be printed yet: " + e.message, 9000); }
}
async function printPackage() {
  try {
    const r = await post("/api/package", { project: S.project, members: S.members });
    window.open(r.url, "_blank");
    toast(r.sheets + " sheets." + (r.skipped.length ? " Left out because not complete: " + r.skipped.join(", ") + "." : ""), 8000);
  } catch (e) { toast(e.message, 8000); }
}
async function save(as = false) {
  try {
    const r = await post("/api/save", { path, as, data: S, suggest: (S.project.number || "project") + ".strukit" });
    if (r.cancelled) return;
    path = r.path; setDirty(false); toast("Saved.");
  } catch (e) { toast("Could not save: " + e.message, 9000); }
}
async function open(p = null) {
  if (dirty && !confirm("Changes to this project are not saved. Open another project anyway?")) return;
  try {
    const r = await post("/api/open", { path: p });
    if (r.cancelled) return;
    load(r.data, r.path);
  } catch (e) { toast("Could not open: " + e.message, 9000); }
}
function migrate(d) {      // an older project file has one list of combinations, for its own method
  const p = d.project;
  if (p.combos && !p.combos_asd && !p.combos_lrfd) { p[p.method === "LRFD" ? "combos_lrfd" : "combos_asd"] = p.combos; delete p.combos; }
  p.combos_asd = p.combos_asd || []; p.combos_lrfd = p.combos_lrfd || [];
  return d;
}
function load(data, p) { S = migrate(data); path = p; R.clear(); sel = "project"; setDirty(false); drawNav(); drawMain(); recalcAll().then(() => { if (sel === "project") drawMain(); }); }

function example() {
  const src = "ASCE/SEI 7 Section 2.4 (typed in)", src2 = "ASCE/SEI 7 Section 2.3 (typed in)";
  return { format: "strukit-project", version: 1,
    project: { name: "Example Project", number: "0000-000", address: "", date: INFO.today, method: "ASD",
      combos_asd: [{ expr: "D + L", source: src }, { expr: "D + S", source: src }, { expr: "D + 0.6W", source: src }, { expr: "D + 0.75L + 0.75S + 0.45W", source: src }],
      combos_lrfd: [{ expr: "1.2D + 1.6L + 0.5S", source: src2 }, { expr: "1.2D + 1.6S + 0.5W", source: src2 }, { expr: "1.2D + 1.0W + 1.0L + 0.5S", source: src2 }, { expr: "0.9D + 1.0W", source: src2 }] },
    members: [
      { kind: "steel_beam", values: { mark: "B1", shape: "W18X50", Fy: "50", span: "35", bracing: "at points", brace_pts: "11.67, 23.33", self_weight: "yes",
        loads: [{ case: "D", kind: "uniform", mag: "0.45" }, { case: "L", kind: "uniform", mag: "0.75" }], defl: [{ label: "live", expr: "L", ratio: "360", source: "limit typed in" }] } },
      { kind: "steel_column", values: { mark: "C1", shape: "W10X33", Fy: "50", height: "16", ends: "held sideways (braced)", Kx: "1", Ky: "1", k_source: "pinned top and bottom", self_weight: "yes",
        loads: [{ case: "D", P: "12" }, { case: "L", P: "30" }], lateral: [{ case: "W", bending: "x", kind: "uniform", mag: "1.5", label: "wind on wall" }], leaning: [], drift: [] } },
      { kind: "steel_column", values: { mark: "C2", shape: "W8X31", Fy: "50", height: "14", ends: "free about x (cantilever, strong axis)", Kx: "1", Ky: "1", k_source: "direct analysis method", self_weight: "yes",
        loads: [{ case: "D", P: "4" }, { case: "S", P: "9" }], lateral: [{ case: "W", bending: "x", kind: "point", mag: "4", x: "14", label: "wind at roof" }],
        leaning: [{ case: "D", P: "4" }, { case: "S", P: "9" }], drift: [{ label: "wind", expr: "0.6W", ratio: "100", source: "limit typed in" }] } },
      { kind: "frame", values: { mark: "F1", bays: "24, 30", stories: "14, 12", base: "fixed", roof: "gable", rise: "6", col_shape: "W10X49", beam_shape: "W16X40", rafter_shape: "W14X30", Fy: "50",
        lb_col: "12", lb_beam: "6", lb_rafter: "5", self_weight: "yes", shape_of: [],
        loads: [{ case: "D", where: "level:1", kind: "gravity per ft of member", mag: "0.9", label: "floor dead" }, { case: "L", where: "level:1", kind: "gravity per ft of member", mag: "1.2", label: "floor live" },
          { case: "D", where: "rafters", kind: "gravity per ft of member", mag: "0.35", label: "roof dead" }, { case: "S", where: "rafters", kind: "gravity per ft horizontal", mag: "0.75", label: "roof snow" },
          { case: "W", where: "level:1", kind: "lateral at level", mag: "5" }, { case: "W", where: "level:2", kind: "lateral at level", mag: "3.5" }],
        leaning: [], drift: [{ label: "wind", expr: "0.6W", ratio: "400", source: "limit typed in" }] } },
      { kind: "footing_iso", values: { mark: "F-A", B: "2.5", L: "2.5", h: "10", fc: "3000", fy: "60000", conc_pcf: "145", col_x: "4", col_y: "4", supported: "wood", plate_x: "6", plate_y: "6",
        bar: "5", n_x: "3", n_y: "3", cover: "3", bottom: "x", P_service: "7600", service_combo: "D + L", Pu: "12160", strength_combo: "1.2D + 1.6L", q_allow: "1500", soil_source: "presumptive value (example)" } },
      { kind: "footing_cont", values: { mark: "CF1", W: "2", h: "10", fc: "3000", fy: "60000", conc_pcf: "145", wall: "8", wall_kind: "concrete", stem_h: "36", stem_pcf: "145", bar_t: "5", spacing_t: "12", bar_l: "5", n_l: "2",
        cover: "3", P_service: "1932", service_combo: "D + L", Pu: "2675", strength_combo: "1.2D + 1.6L", dead_factor: "1.2", q_allow: "1500", soil_source: "presumptive value (example)", soil_depth: "3", soil_pcf: "110" } },
      { kind: "weld", values: { mark: "W1", size: "0.25", length: "8", n_lines: "2", FEXX: "70", theta: "0", directional: "no", end_loaded: "no", t_thinner: "0.375", t_edge: "0.375",
        loads: [{ case: "D", P: "12" }, { case: "L", P: "30" }] } },
      { kind: "bolts", values: { mark: "BG1", d: "0.75", group: "A325", n: "4", spacing: "3", edge: "1.5", threads: "N", planes: "1", deformation: "yes",
        plies: [{ t: "0.375", Fu: "58", has_edge: "yes" }, { t: "0.355", Fu: "65", has_edge: "no" }], loads: [{ case: "D", P: "10" }, { case: "L", P: "25" }] } },
      { kind: "base_plate", values: { mark: "BP1", shape: "W10X33", N: "14", B: "12", t: "1", Fy: "36", fc: "3000", full: "no", sup_N: "24", sup_B: "24",
        loads: [{ case: "D", P: "12" }, { case: "L", P: "30" }] } },
      { kind: "base_plate_moment", values: { mark: "BP2", shape: "W8X31", N: "20", B: "12", t: "1.75", Fy: "36", fc: "3000", full: "no", sup_N: "108", sup_B: "72",
        rod_d: "1", rod_grade: "F1554 Gr. 36", n_rods: "2", rod_edge: "2", rod_side: "1.5", n_shear: "4", loads_from: "base reactions of C2, second-order analysis",
        anc_hef: "12", anc_h: "24", anc_cracked: "cracked", anc_supp: "no", anc_edge: "none or smaller than No. 4", anc_grout: "yes", anc_sdc: "A or B",
        cases: [{ name: "D + S", P: "13.43", M: "0.41", V: "0.03" }, { name: "D + 0.6W", P: "4.43", M: "34.51", V: "2.40" }, { name: "D + 0.75L + 0.75S + 0.45W", P: "11.18", M: "27.01", V: "1.80" }],
        cases_lrfd: [{ name: "1.2D + 1.6S + 0.5W", P: "19.72", M: "30.23", V: "2.00" }, { name: "1.2D + 1.0W + 1.0L + 0.5S", P: "9.82", M: "58.12", V: "4.00" }, { name: "0.9D + 1.0W", P: "3.99", M: "56.84", V: "4.00" }] } },
      { kind: "footing_moment", values: { mark: "FM1", B: "9", L: "6", h: "24", fc: "3000", fy: "60000", conc_pcf: "150", col_x: "14", col_y: "12", supported: "steel", plate_x: "14", plate_y: "12",
        bar: "6", n_x: "8", n_y: "11", cover: "3", bottom: "x", q_allow: "2000", soil_source: "presumptive value (example)", ot_required: "1.5", slide_mu: "0.35", slide_required: "1.5", limits_source: "typed in for the example", loads_from: "base reactions of C2, second-order analysis",
        service: [{ name: "D + S", P: "13434", M: "409", V: "27" }, { name: "D + 0.6W", P: "4434", M: "34508", V: "2400" }],
        strength: [{ name: "1.2D + 1.6S + 0.5W", P: "19721", M: "29000", V: "2000", wt_factor: "1.2" }, { name: "0.9D + 1.0W", P: "3991", M: "56839", V: "4000", wt_factor: "0.9" }] } }] };
}

// ---------------------------------------------------------------- start
(async function start() {
  window.addEventListener("error", e => toast("Screen error: " + e.message, 12000));
  INFO = await post("/api/info");
  $("#build").textContent = "build " + INFO.version;
  document.body.append(el("datalist", { id: "shapes" }, INFO.shapes.map(s => el("option", { value: s }))));
  for (const [k, f] of Object.entries(INFO.forms))
    $("#addbtns").append(el("button", { onclick: () => { S.members.push({ kind: k, values: { mark: "" } }); setDirty(); select(S.members.length - 1); } }, f.title));
  $("#bOpen").onclick = () => open(); $("#bSave").onclick = () => save(false); $("#bSaveAs").onclick = () => save(true);
  $("#bPackage").onclick = printPackage;
  $("#bExample").onclick = () => { if (!dirty || confirm("Replace what is on the screen with the example project?")) { load(example(), null); setDirty(true); } };
  window.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(false); } });
  window.addEventListener("beforeunload", e => { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  setInterval(() => post("/api/ping").catch(() => {}), 5000); post("/api/ping").catch(() => {});
  S = blank();
  const q = new URLSearchParams(location.search);
  if (q.get("open")) await open(q.get("open"));
  else if (q.get("demo")) { load(example(), null); await recalcAll(); if (q.get("sel")) select(+q.get("sel")); }
  else { drawNav(); drawMain(); drawFile(); }
})();
