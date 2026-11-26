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
      list: f.type === "shape" ? "shapes" : f.type === "shape_any" ? "shapes_any" : f.type === "hss_shape" ? "shapes_hss" : f.type === "shape_col" ? "shapes_col" : f.type === "shape_tension" ? "shapes_tension" : null, spellcheck: "false", autocomplete: "off" });
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
  for (const t of (r.tables || [])) box.append(el("details", { open: "" }, el("summary", {}, t.title),
    el("pre", { class: "mono", style: "overflow-x:auto;font-size:11px;line-height:1.45;margin:6px 0" }, t.lines.join("\n")),
    t.after.map(x => el("div", { class: "small" }, x))));
  if (r.assumptions.length) box.append(el("details", {}, el("summary", {}, "Assumptions"), el("ul", { class: "msg small" }, r.assumptions.map(t => el("li", {}, t)))));
  if (r.not_checked.length) box.append(el("details", {}, el("summary", {}, "Not checked on this sheet"), el("ul", { class: "msg small" }, r.not_checked.map(t => el("li", {}, t)))));
}

// ---------------------------------------------------------------- loads from another member
function fillFromDiaphragmBar(m, changed) {
  const src = S.members.filter(x => x.kind === "diaphragm");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a diaphragm"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + (x.values.load || "") + " diaphragm")));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the diaphragm first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/diaphragm_reaction", { values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    Object.assign(m.values, { V: String(Math.round(got.reaction)), load: got.load || m.values.load,
      v_source: "reaction of diaphragm " + (s.values.mark || "") + " (w L / 2), at " + S.project.method + " level" });
    changed(); drawMain();
    toast("Shear " + Math.round(got.reaction).toLocaleString() + " lb from one end of " + (s.values.mark || "the diaphragm") + ". Add the shear from any wall above and from a diaphragm on the other side of this line.", 12000);
  } }, "Fill Shear");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the shear from a diaphragm reaction"), pick, go);
}

function fillDriftBar(m, changed) {
  const src = S.members.filter(x => x.kind === "shear_wall" || x.kind === "perforated_wall");
  const lv = (m.values.levels || []).filter(r => (r.name || "").trim());
  if (!src.length || !lv.length) return el("div", { class: "fill small" }, "For the drift check, a level's elastic displacement can be filled in from a shear wall sheet's deflection once the project has one and the levels are listed.");
  const pick = el("select", {}, el("option", { value: "" }, "choose a shear wall"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const level = el("select", {}, el("option", { value: "" }, "story below level"), lv.map(r => el("option", { value: r.name }, r.name)));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "" || level.value === "") return toast("Choose the shear wall and the level first.");
    if (S.project.method !== "ASD" && S.project.method !== "LRFD") return toast("Choose the design method on the Project page first.", 9000);
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/wall_deflection", { kind: s.kind, values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    if (got.load !== "seismic") return toast("That shear wall sheet is for " + (got.load || "another load") + ", not seismic. Use the wall sheet that carries the seismic shear.", 12000);
    const asd = S.project.method === "ASD", story = got.defl / (asd ? 0.7 : 1.0);
    const num = t => parseFloat(String(t || "").replace(/,/g, ""));
    const rows = lv.slice().sort((a, b) => num(a.h) - num(b.h)), i = rows.findIndex(r => r.name === level.value);
    if (rows.some(r => isNaN(num(r.h)))) return toast("Give every level its height first.", 9000);
    let base = 0;
    if (i > 0) { base = num(rows[i - 1].de); if (isNaN(base)) return toast("Fill the level below (" + rows[i - 1].name + ") first: displacements add up from the base.", 12000); }
    rows[i].de = (base + story).toFixed(3);
    const note = "story below " + rows[i].name + ": shear wall " + (s.values.mark || "") + ", " + got.defl.toFixed(3) + " in. at " + S.project.method + " level" + (asd ? " divided by 0.7" : "");
    const old = (m.values.de_source || "").split("; ").filter(t => t && !t.startsWith("story below " + rows[i].name + ":"));
    m.values.de_source = old.concat(note).join("; ");
    changed(); drawMain();
    toast("Story deflection " + story.toFixed(3) + " in. under the design seismic forces" + (asd ? " (the wall sheet's " + got.defl.toFixed(3) + " in. divided by 0.7)" : "") + "; level " + rows[i].name + " is now " + rows[i].de + " in. Use the wall line with the largest deflection in each story.", 14000);
  } }, "Fill Displacement");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Drift: take a story deflection from"), pick, level, go);
}

function fillSnowBar(m, changed) {
  const src = S.members.filter(x => x.kind === "snow");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a roof snow sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 roof snow")));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the roof snow sheet first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/snow_loads", { values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    const mark = s.values.mark || "roof snow sheet", tag = "sheet " + mark + ":";
    m.values.loads = (m.values.loads || []).filter(r => !(String(r.label || "").startsWith(tag)) && (r.case || r.mag));
    m.values.loads.push({ case: "S", kind: "area", mag: String(Math.round(got.uniform_design * 10) / 10), mag2: "", x1: "", x2: "", label: tag + " " + got.governs });
    changed(); drawMain();
    toast("Snow load " + got.uniform_design.toFixed(1) + " psf added as an area load (" + got.governs + "), on the horizontal projection. It needs the member spacing."
      + (got.unbalanced ? " The unbalanced loads on that sheet are not carried over: enter them where this member must take them." : ""), 14000);
  } }, "Add Snow Load");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the uniform snow load from"), pick, go);
}

function fillKztBar(m, changed) {
  const src = S.members.filter(x => x.kind === "wind_kzt");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a topographic factor sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 topographic factor")));
  const row = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; row.style.display = "none"; row.textContent = "";
    if (pick.value === "") return;
    try {
      got = await post("/api/kzt", { values: S.members[+pick.value].values, project: S.project });
      got.rows.forEach((r, i) => row.append(el("option", { value: i }, "z = " + r.z + " ft: Kzt = " + r.Kzt.toFixed(2))));
      let best = 0; got.rows.forEach((r, i) => { if (r.Kzt > got.rows[best].Kzt) best = i; });
      row.value = String(best); row.style.display = "";
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got) return toast("Choose the topographic factor sheet first.");
    const r = got.rows[+row.value], mark = S.members[+pick.value].values.mark || "topographic factor sheet";
    m.values.Kzt = String(Math.round(r.Kzt * 100) / 100);
    m.values.Kzt_source = got.applies ? "sheet " + mark + ": Kzt at z = " + r.z + " ft" : "sheet " + mark + ": Sect. 26.8.1 not met";
    changed(); drawMain();
    toast("Kzt = " + m.values.Kzt + " filled. One Kzt is used for every height on this sheet; the value nearest the ground is the largest.", 10000);
  } }, "Fill Kzt");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take Kzt from"), pick, row, go);
}

function fillEnclosureBar(m, changed) {
  const src = S.members.filter(x => x.kind === "wind_enclosure");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose an enclosure classification sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 enclosure classification")));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the enclosure classification sheet first.");
    let got;
    try { got = await post("/api/enclosure", { values: S.members[+pick.value].values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    const mark = S.members[+pick.value].values.mark || "enclosure classification sheet";
    if (got.classification === "open") return toast("Sheet " + mark + " classifies the building as open. Open buildings go on the Open Building wind screen; nothing was filled.", 12000);
    m.values.enclosure = got.classification;
    m.values.enclosure_basis = "sheet " + mark + ": " + got.classification + " (ASCE/SEI 7-22 Sect. 26.2)";
    changed(); drawMain();
    toast("Enclosure filled: " + got.classification + ".", 8000);
  } }, "Fill Enclosure");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the enclosure from"), pick, go);
}

function fillLiveBar(m, changed) {
  const src = S.members.filter(x => x.kind === "live_load");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a live load sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 live load reduction")));
  const row = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; row.style.display = "none"; row.textContent = "";
    if (pick.value === "") return;
    try {
      got = await post("/api/live_loads", { values: S.members[+pick.value].values, project: S.project });
      got.members.forEach((r, i) => row.append(el("option", { value: i }, r.name + ": " + r.case + " " + r.psf.toFixed(1) + " psf")));
      row.style.display = "";
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.members.length) return toast("Choose the live load sheet first.");
    const s = S.members[+pick.value], r = got.members[+row.value], tag = "sheet " + (s.values.mark || "live load") + ", member " + r.name + ":";
    m.values.loads = (m.values.loads || []).filter(x => !(String(x.label || "").startsWith("sheet " + (s.values.mark || "live load") + ", member ")) && (x.case || x.mag));
    m.values.loads.push({ case: r.case, kind: "area", mag: String(Math.round(r.psf * 10) / 10), mag2: "", x1: "", x2: "", label: tag + " reduced " + (r.case === "L" ? "live load" : "roof live load") });
    changed(); drawMain();
    toast((r.case === "L" ? "Live load " : "Roof live load ") + r.psf.toFixed(1) + " psf added as an area load. It needs the member spacing.", 10000);
  } }, "Add Live Load");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take a reduced live load from"), pick, row, go);
}

function fillRainBar(m, changed) {
  const src = S.members.filter(x => x.kind === "rain_load");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a rain load sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 rain load")));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the rain load sheet first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/rain_load", { values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    const mark = s.values.mark || "rain load sheet", tag = "sheet " + mark + ":";
    m.values.loads = (m.values.loads || []).filter(r => !(String(r.label || "").startsWith(tag)) && (r.case || r.mag));
    m.values.loads.push({ case: "R", kind: "area", mag: String(Math.round(got.R * 10) / 10), mag2: "", x1: "", x2: "", label: tag + " rain load R" });
    changed(); drawMain();
    toast("Rain load " + got.R.toFixed(1) + " psf added as an area load, case R, uniform over the member. It needs the member spacing, and load case R in the project's combinations.", 14000);
  } }, "Add Rain Load");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the rain load from"), pick, go);
}

function fillDriftBar(m, changed) {
  const src = S.members.filter(x => x.kind === "snow_drift");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a snow drift sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 snow drift")));
  const how = el("select", {}, el("option", { value: "left" }, "member runs out from the wall, wall at its left end"),
    el("option", { value: "right" }, "member runs out from the wall, wall at its right end"), el("option", { value: "par" }, "member parallel to the wall, at this distance (ft):"));
  const dist = el("input", { type: "text", size: 5, style: "display:none", placeholder: "ft" });
  how.addEventListener("change", () => { dist.style.display = how.value === "par" ? "" : "none"; });
  const num = v => { const x = parseFloat(v); return isFinite(x) ? x : 0; };
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the snow drift sheet first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/snow_drift", { values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    const mark = s.values.mark || "snow drift sheet", tag = "sheet " + mark + ":";
    const r1 = x => String(Math.round(x * 10) / 10), r2 = x => String(Math.round(x * 100) / 100);
    const at = x => got.pd * Math.max(0, 1 - x / got.width);
    let row;
    if (how.value === "par") {
      const d = parseFloat(dist.value);
      if (!isFinite(d) || d < 0) return toast("Type the distance from the wall to the member, in feet (to the edge of its tributary strip nearest the wall).");
      if (d >= got.extent) return toast("At " + d + " ft the member is beyond the drift (" + r2(got.extent) + " ft wide). Nothing was added.", 10000);
      row = { case: "S", kind: "area", mag: r1(at(d)), mag2: "", x1: "", x2: "", label: tag + " " + got.kind + " drift surcharge at " + d + " ft from the wall" };
    } else {
      const L = num(m.values.oh_left) + num(m.values.span) + String(m.values.more_spans || "").split(",").reduce((a, v) => a + num(v), 0) + num(m.values.oh_right);
      if (!(L > 0)) return toast("Enter the span of the member first.");
      const x = Math.min(got.extent, L);
      row = how.value === "left"
        ? { case: "S", kind: "area", mag: r1(got.pd), mag2: r1(at(x)), x1: "0", x2: r2(x), label: tag + " " + got.kind + " drift surcharge, wall at the left end" }
        : { case: "S", kind: "area", mag: r1(at(x)), mag2: r1(got.pd), x1: r2(L - x), x2: r2(L), label: tag + " " + got.kind + " drift surcharge, wall at the right end" };
    }
    m.values.loads = (m.values.loads || []).filter(r => !(String(r.label || "").startsWith(tag)) && (r.case || r.mag));
    m.values.loads.push(row);
    changed(); drawMain();
    toast("Drift surcharge added (peak " + r1(got.pd) + " psf, " + r2(got.extent) + " ft wide), on top of the balanced snow load: add that too if it is not on the member yet."
      + (got.sliding ? " The sliding snow on that sheet is a separate case and is not carried over." : ""), 14000);
  } }, "Add Drift");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the snow drift from"), pick, how, dist, go);
}

const TD_BEAMS = ["steel_beam", "wood_beam", "lvl_beam", "glulam_beam", "wey_beam", "ijoist"];
const TD_POSTS = ["wood_post", "builtup_post", "lvl_post", "wey_post", "glulam_post", "steel_column", "hss_column"];
const TD_KIP = ["steel_beam", "steel_column", "hss_column", "single_plate", "end_plate", "seat", "base_plate"];
const TD_TARGET_P = ["wood_post", "builtup_post", "lvl_post", "wey_post", "glulam_post", "steel_column", "hss_column", "single_plate", "end_plate", "seat", "base_plate"];

let LINKS = [];
// Runs every stored takedown link from the top of the load path down and puts the refreshed loads on the members.
async function runTakedown(quiet = false) {
  let out;
  try { out = await post("/api/takedown", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return null; }
  if (out.problems.length) toast(out.problems.join("  "), 16000);
  out.members.forEach((nm, i) => { S.members[i].values = nm.values; });
  LINKS = out.links;
  setDirty(); await recalcAll();
  if (!quiet && !out.problems.length) toast(out.links.length ? out.links.length + " link" + (out.links.length > 1 ? "s" : "") + " recalculated, from the top of the load path down." : "No member takes its loads from another member yet.", 9000);
  return out;
}

// Gravity takedown: the reaction of another member, by load case, added to this member as loads.
function fillTakedownBar(m, changed) {
  const isBeam = TD_BEAMS.includes(m.kind);
  if (!isBeam && !TD_TARGET_P.includes(m.kind)) return null;
  const src = S.members.filter(x => x !== m && (TD_BEAMS.includes(x.kind) || TD_POSTS.includes(x.kind)));
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose the member above"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const sup = el("select", { style: "display:none" });
  const count = el("input", { type: "text", value: "1", style: "width:3.2em", title: "how many of these members land here" });
  const at = el("input", { type: "text", placeholder: "at ft", style: "width:4.5em" + (isBeam ? "" : ";display:none"), title: "distance from the left end of this member" });
  const line = el("select", { style: "display:none", title: "a row of joists or rafters bearing along this member" }, el("option", { value: "" }, "one member, as a point load"), el("option", { value: "line" }, "a row of them, as a load per foot"));
  line.addEventListener("change", () => { at.placeholder = line.value ? "from ft (blank = all)" : "at ft"; at.style.width = line.value ? "9em" : "4.5em"; });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; sup.style.display = "none"; sup.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/case_reactions", { kind: s.kind, values: s.values, project: S.project });
      got.supports.forEach((r, i) => sup.append(el("option", { value: i }, r.name + ": " + Object.entries(r.cases).map(([c, v]) => c + " " + Math.round(v).toLocaleString()).join(", ") + " lb")));
      sup.style.display = "";
      const sp = parseFloat(s.values.spacing);
      line.style.display = (isBeam && sp > 0) ? "" : "none"; line.value = (isBeam && sp > 0) ? "line" : ""; line.dispatchEvent(new Event("change"));
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.supports.length) return toast("Choose the member above first.");
    const s = S.members[+pick.value], r = got.supports[+sup.value], n = parseFloat(count.value) || 1;
    const x = at.value.trim();
    if (isBeam && !line.value && (x === "" || isNaN(parseFloat(x)))) return toast("Type where the reaction lands on this member, in feet from its left end.");
    if (!(s.values.mark || "").trim()) return toast("Give the member above a mark first; the link is kept by mark.");
    const lk = { src: s.values.mark, support: r.name, count: n };
    if (isBeam) lk.x = x;
    if (isBeam && line.value) { lk.mode = "line"; lk.spacing_in = parseFloat(s.values.spacing); lk.count = 1; }
    m.values.loads = (m.values.loads || []).filter(q => !(q.link && q.link.src === lk.src && q.link.support === lk.support) && (q.case || q.mag || q.P));
    m.values.loads.push(isBeam ? { case: "D", kind: "point", mag: "0", mag2: "", x1: x, x2: "", label: "", link: lk } : { case: "D", P: "0", label: "", link: lk });
    changed();
    runTakedown(true).then(o => { drawMain(); if (o && !o.problems.length) toast("Loads added from " + s.values.mark + " by load case and linked. They are recalculated by “Recalculate the load path” on the Project page." + (got.notes && got.notes.length ? " Note: " + got.notes.join("; ") + "." : ""), 14000); });
  } }, "Add Reaction");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the reaction of the member above"), pick, sup, line, el("span", { class: "small" }, "x"), count, at, go);
}

// Gravity takedown into an isolated or continuous footing: the governing service and factored reaction of the member above.
function fillFootingTakedownBar(m, changed) {
  const src = S.members.filter(x => TD_BEAMS.includes(x.kind) || TD_POSTS.includes(x.kind));
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose the member above"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const sup = el("select", { style: "display:none" });
  const count = el("input", { type: "text", value: "1", style: "width:3.2em", title: m.kind === "footing_cont" ? "members per foot of wall (1 / spacing in ft)" : "how many of these members land here" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; sup.style.display = "none"; sup.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/case_reactions", { kind: s.kind, values: s.values, project: S.project });
      got.supports.forEach((r, i) => sup.append(el("option", { value: i }, r.name + (r.service ? ": " + Math.round(r.service.P).toLocaleString() + " lb service" : ""))));
      sup.style.display = "";
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.supports.length) return toast("Choose the member above first.");
    const s = S.members[+pick.value], r = got.supports[+sup.value], n = parseFloat(count.value) || 1;
    if (!r.service || !r.strength) return toast("Both ASD and LRFD load combinations are needed on the Project page: service loads size the footing on the soil, factored loads design the concrete.", 12000);
    if (!(s.values.mark || "").trim()) return toast("Give the member above a mark first; the link is kept by mark.");
    m.values.link = { src: s.values.mark, support: r.name, count: n };
    changed();
    runTakedown(true).then(o => { drawMain(); if (o && !o.problems.length) toast("Service and factored loads filled from " + s.values.mark + " and linked.", 10000); });
  } }, "Fill Loads");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the reaction of a beam, joist or post above"), pick, sup, el("span", { class: "small" }, "x"), count, go);
}

function fillLoadsBar(m, changed) {
  const a = fillSnowBar(m, changed), d = fillDriftBar(m, changed), b = fillLiveBar(m, changed), c = fillRainBar(m, changed);
  return (a || b || c || d) ? el("div", {}, a, d, b, c) : null;
}

function fillCollectorBar(m, changed) {
  const src = S.members.filter(x => x.kind === "diaphragm");
  if (!src.length) return el("div", { class: "fill small" }, "The force and the line length can be filled in from a Wood Diaphragm sheet once the project has one.");
  const pick = el("select", {}, el("option", { value: "" }, "choose a diaphragm"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + (x.values.load || "") + " diaphragm")));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the diaphragm first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/diaphragm_reaction", { values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    Object.assign(m.values, { R: String(Math.round(got.reaction)), W: got.W || m.values.W, level: (got.load || "lateral load") + ", " + S.project.method + " level",
      R_source: "reaction of diaphragm " + (s.values.mark || "") + " (w L / 2)" });
    changed(); drawMain();
    toast("Force " + Math.round(got.reaction).toLocaleString() + " lb from one end of " + (s.values.mark || "the diaphragm") + ". Add the force from a diaphragm on the other side of this line.", 12000);
  } }, "Fill Force and Length");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the force from a diaphragm reaction"), pick, go);
}

function fillAboveBar(m, changed) {
  if (m.kind !== "shear_wall" && m.kind !== "ftao_wall") return null;
  const src = S.members.filter(x => x !== m && (x.kind === "shear_wall" || x.kind === "perforated_wall" || x.kind === "ftao_wall"));
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose the wall above"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const go = el("button", { class: "btn", onclick: async () => {
    if (pick.value === "") return toast("Choose the wall above first.");
    const s = S.members[+pick.value];
    let got;
    try { got = await post("/api/wall_above", { kind: s.kind, values: s.values, project: S.project }); } catch (e) { return toast(e.message, 12000); }
    Object.assign(m.values, { above_T: String(Math.round(got.T)), above_source: "largest chord force of shear wall " + (s.values.mark || "") + ", " + (got.load || "") + ", " + S.project.method });
    changed(); drawMain();
    toast("Chord force " + Math.round(got.T).toLocaleString() + " lb from " + (s.values.mark || "the wall above") + " added at each segment end. The shear from the wall above is part of this wall's design shear.", 12000);
  } }, "Fill Chord Force");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Stack on the wall above"), pick, go);
}

function fillWallBar(m, changed) {
  const src = S.members.filter(x => x.kind === "seismic_elf" && (x.values.lines || []).some(r => (r.name || "").trim()));
  if (!src.length) return el("div", {}, fillFromDiaphragmBar(m, changed) ||
    el("div", { class: "fill small" }, "The shear can be filled in from a diaphragm sheet, or from a Seismic Base Shear sheet once it lists its wall or frame lines."));
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
  return el("div", {}, el("div", { class: "fill" }, el("span", { class: "small" }, "Take the seismic shear from"), pick, line, go), fillFromDiaphragmBar(m, changed));
}

function fillDiaphragmBar(m, changed) {
  const src = S.members.filter(x => x.kind === "seismic_elf");
  if (!src.length) return el("div", {}, fillWindBar(m, changed) ||
    el("div", { class: "fill small" }, "The load can be filled in from a main-system wind sheet or a Seismic Base Shear sheet once the project has one."));
  const pick = el("select", {}, el("option", { value: "" }, "choose a seismic sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const lvl = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; lvl.style.display = "none"; lvl.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/wall_lines", { values: s.values, project: S.project });
      got.levels.forEach((r, i) => lvl.append(el("option", { value: i }, "diaphragm at " + r.level)));
      lvl.style.display = "";
    } catch (e) { toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.levels.length) return toast("Choose the seismic sheet first.");
    if (S.project.method !== "ASD" && S.project.method !== "LRFD") return toast("Choose the design method on the Project page first.", 9000);
    const L = parseFloat(String(m.values.L || "").replace(/,/g, ""));
    if (!(L > 0)) return toast("Type the span between the lines of resistance, L, first: the diaphragm force is spread along it.", 10000);
    const s = S.members[+pick.value], r = got.levels[+lvl.value], asd = S.project.method === "ASD";
    const w = r.Fpx * 1000 * (asd ? 0.7 : 1.0) / L;
    Object.assign(m.values, { w: w.toFixed(1), load: "seismic",
      w_source: "sheet " + (s.values.mark || "seismic") + ", Fpx at " + r.level + " = " + r.Fpx.toFixed(2) + " kips (" + r.by + ")" + (asd ? " x 0.7" : "") + " over L = " + L + " ft; rho = 1.0, ASCE/SEI 7-22 Sect. 12.3.4.1" });
    changed(); drawMain();
  } }, "Fill Load");
  return el("div", {}, el("div", { class: "fill" }, el("span", { class: "small" }, "Take the seismic load from"), pick, lvl, go), fillWindBar(m, changed));
}

function fillWindBar(m, changed) {
  const src = S.members.filter(x => x.kind === "wind_mwfrs");
  if (!src.length) return null;
  const pick = el("select", {}, el("option", { value: "" }, "choose a wind sheet"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 main system wind")));
  const dir = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; dir.style.display = "none"; dir.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/wind_line", { values: s.values, project: S.project, z1: m.values.trib_low || "", z2: m.values.trib_high || "" });
      got.directions.forEach((r, i) => dir.append(el("option", { value: i }, r.title.toLowerCase())));
      dir.style.display = "";
    } catch (e) { pick.value = ""; toast(e.message, 12000); }
  });
  const go = el("button", { class: "btn", onclick: () => {
    if (!got || !got.directions.length) return toast("Type the two tributary wall heights, then choose the wind sheet.", 9000);
    if (S.project.method !== "ASD" && S.project.method !== "LRFD") return toast("Choose the design method on the Project page first.", 9000);
    const s = S.members[+pick.value], r = got.directions[+dir.value], asd = S.project.method === "ASD";
    const w = r.w * (asd ? 0.6 : 1.0);
    Object.assign(m.values, { w: w.toFixed(1), load: "wind",
      w_source: "sheet " + (s.values.mark || "wind") + ", " + r.title.toLowerCase() + ", walls from " + m.values.trib_low + " to " + r.to + " ft: " + r.w.toFixed(1) + " plf (" + r.governs + ")" + (asd ? " x 0.6" : "") });
    changed(); drawMain();
    toast("Wind load " + w.toFixed(1) + " plf. The span L of this diaphragm should be the building dimension normal to that wind (" + r.B + " ft on the wind sheet).", 12000);
  } }, "Fill Load");
  return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the wind load from"), pick, dir, go);
}

function fillBar(m, changed) {
  if (m.kind === "shear_wall" || m.kind === "perforated_wall" || m.kind === "ftao_wall") { const a = fillWallBar(m, changed), b = fillAboveBar(m, changed); return b ? el("div", {}, a, b) : a; }
  if (m.kind === "diaphragm") return fillDiaphragmBar(m, changed);
  if (m.kind === "collector") return fillCollectorBar(m, changed);
  if (m.kind === "seismic_elf") return fillDriftBar(m, changed);
  if (["wind_mwfrs", "wind_cc_walls", "wind_cc_roof"].includes(m.kind)) {
    const a = fillKztBar(m, changed), b = fillEnclosureBar(m, changed);
    return a && b ? el("div", {}, a, b) : (a || b);
  }
  if (m.kind.startsWith("wind_") && m.kind !== "wind_kzt" && m.kind !== "wind_enclosure") return fillKztBar(m, changed);
  if (["wood_beam", "lvl_beam", "glulam_beam", "wey_beam", "ijoist"].includes(m.kind)) { const a = fillLoadsBar(m, changed), b = fillTakedownBar(m, changed); return (a || b) ? el("div", {}, a, b) : null; }
  if (TD_BEAMS.includes(m.kind) || TD_TARGET_P.includes(m.kind)) { const b = fillTakedownBar(m, changed); if (b) return b; }
  if (m.kind === "footing_cont") return fillFootingTakedownBar(m, changed);
  if (m.kind === "base_plate_biaxial") {
    const cols = S.members.filter(x => (x.kind === "steel_column" || x.kind === "hss_column") && x.values.at_x1 && x.values.at_level);
    if (!cols.length) return el("div", { class: "fill small" }, "The loads can be filled from a column of the 3D frame once the project has columns placed in the building model.");
    const pick = el("select", {}, el("option", { value: "" }, "choose a frame column"), cols.map(x => el("option", { value: x.values.mark }, x.values.mark || "(no mark)")));
    const go = el("button", { class: "btn", onclick: async () => {
      if (!pick.value) return toast("Choose the column first.");
      let got;
      try { got = await post("/api/frame_base_biaxial", { project: S.project, members: S.members, mark: pick.value }); } catch (e) { return toast(e.message, 12000); }
      if (!got.rows || !got.rows.length) return toast((got.messages || []).join("  ") || "The frame did not run.", 12000);
      const comp = got.rows.filter(r => r.P >= 0), up = got.rows.filter(r => r.P < 0);
      if (!comp.length) return toast("Every governing run puts this column in uplift; this screen is for axial compression. Use the Base Plate with Moment or uplift screen.", 14000);
      m.values.cases = comp.map(r => ({ name: r.name, P: r.P.toFixed(2), Mx: r.Mx.toFixed(2), My: r.My.toFixed(2) }));
      m.values.loads_from = "base forces of column " + pick.value + " in the 3D frame analysis, second-order analysis";
      got.uplift = up;
      if (!m.values.shape) { const c = cols.find(x => x.values.mark === pick.value); if (c) m.values.shape = c.values.shape; }
      changed(); drawMain();
      toast("Filled " + comp.length + " runs from the frame." + (up.length ? " Left out, because the column is in uplift (" + up.map(r => r.P.toFixed(1) + " kip").join(", ") + "): " + up.map(r => r.name).join("; ") + ". Check those on the Base Plate with Moment or uplift screen." : ""), 16000);
    } }, "Fill Loads");
    return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the loads from the 3D frame"), pick, go);
  }
  if (m.kind === "flush_end_plate") {
    const bms = S.members.filter(x => x.kind === "steel_beam" && x.values.at_x1 && x.values.at_level);
    if (!bms.length) return el("div", { class: "fill small" }, "The combined loads can be filled from a beam of the 3D frame once the project has steel beams placed in the building model.");
    const pick = el("select", {}, el("option", { value: "" }, "choose a frame beam"), bms.map(x => el("option", { value: x.values.mark }, x.values.mark || "(no mark)")));
    const end = el("select", {}, ["left", "right"].map(a => el("option", { value: a }, a + " end")));
    const go = el("button", { class: "btn", onclick: async () => {
      if (!pick.value) return toast("Choose the beam first.");
      let got;
      try { got = await post("/api/frame_beam_end", { project: S.project, members: S.members, mark: pick.value }); } catch (e) { return toast(e.message, 12000); }
      const rows = (got.ends || {})[end.value];
      if (!rows || !rows.length) return toast((got.messages || []).join("  ") || "The frame did not run.", 12000);
      m.values.runs = rows.map(r => ({ name: r.name, M: r.M.toFixed(2), T: r.T.toFixed(2), V: r.V.toFixed(2) }));
      m.values.loads_from = "forces at the " + end.value + " end of beam " + pick.value + " in the 3D frame analysis, second-order analysis";
      if (!m.values.beam) { const b = bms.find(x => x.values.mark === pick.value); if (b) m.values.beam = b.values.shape; }
      changed(); drawMain();
      toast("Filled " + rows.length + " runs from the frame: largest moment, shear and axial tension at that end.", 9000);
    } }, "Fill Loads");
    return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the loads from the 3D frame"), pick, end, go);
  }
  if (m.kind === "beam_hss_moment") {
    const bms = S.members.filter(x => x.kind === "steel_beam" && x.values.at_x1 && x.values.at_level);
    if (!bms.length) return el("div", { class: "fill small" }, "The combined loads can be filled from a beam of the 3D frame once the project has steel beams placed in the building model.");
    const pick = el("select", {}, el("option", { value: "" }, "choose a frame beam"), bms.map(x => el("option", { value: x.values.mark }, x.values.mark || "(no mark)")));
    const end = el("select", {}, ["left", "right"].map(a => el("option", { value: a }, a + " end")));
    const go = el("button", { class: "btn", onclick: async () => {
      if (!pick.value) return toast("Choose the beam first.");
      let got;
      try { got = await post("/api/frame_beam_hss", { project: S.project, members: S.members, mark: pick.value, end: end.value }); } catch (e) { return toast(e.message, 12000); }
      if (!got.rows || !got.rows.length) return toast((got.messages || []).join("  ") || "The frame did not run.", 12000);
      m.values.runs = got.rows.map(r => ({ name: r.name, M: r.M.toFixed(2), P: r.P.toFixed(2), Mc: r.Mc.toFixed(2) }));
      m.values.loads_from = "forces at the " + end.value + " end of beam " + pick.value + " and at the top of column " + got.column + " in the 3D frame analysis, second-order analysis";
      m.values.face = got.face;
      if (!m.values.beam) { const b = bms.find(x => x.values.mark === pick.value); if (b) m.values.beam = b.values.shape; }
      if (!m.values.column && got.column_shape) m.values.column = got.column_shape;
      changed(); drawMain();
      toast("Filled " + got.rows.length + " runs from the frame (column " + got.column + ", face " + got.face + "): largest beam moment, column load and column moment.", 10000);
    } }, "Fill Loads");
    return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the joint loads from the 3D frame"), pick, end, go);
  }
  if (m.kind === "cap_plate") {
    const cols = S.members.filter(x => (x.kind === "steel_column" || x.kind === "hss_column") && x.values.at_x1 && x.values.at_level);
    if (!cols.length) return el("div", { class: "fill small" }, "The combined loads can be filled from a column of the 3D frame once the project has columns placed in the building model.");
    const pick = el("select", {}, el("option", { value: "" }, "choose a frame column"), cols.map(x => el("option", { value: x.values.mark }, x.values.mark || "(no mark)")));
    const axis = el("select", {}, ["strong-axis moment", "weak-axis moment"].map(a => el("option", { value: a }, a)));
    const go = el("button", { class: "btn", onclick: async () => {
      if (!pick.value) return toast("Choose the column first.");
      let got;
      try { got = await post("/api/frame_knee", { project: S.project, members: S.members, mark: pick.value }); } catch (e) { return toast(e.message, 12000); }
      const rows = (got.axes || {})[axis.value];
      if (!rows || !rows.length) return toast((got.messages || []).join("  ") || "The frame did not run.", 12000);
      m.values.runs = rows.map(r => ({ name: r.name, P: r.P.toFixed(2), M: r.M.toFixed(2) }));
      m.values.loads_from = "forces at the top of column " + pick.value + " in the 3D frame analysis, " + axis.value + ", second-order analysis";
      if (!m.values.column) { const c = cols.find(x => x.values.mark === pick.value); if (c && c.kind === "hss_column") m.values.column = c.values.shape; }
      changed(); drawMain();
      toast("Filled " + rows.length + " runs from the frame: largest moment, largest and least column load.", 9000);
    } }, "Fill Loads");
    return el("div", { class: "fill" }, el("span", { class: "small" }, "Take the joint loads from the 3D frame"), pick, axis, go);
  }
  if (m.kind !== "footing_moment" && m.kind !== "footing_iso" && m.kind !== "base_plate_moment") return null;
  const src = S.members.filter(x => x.kind === "steel_column" || x.kind === "frame" || (x.kind === "hss_column" && x.values.at_x1 && x.values.at_level) || (x.kind === "guard" && m.kind === "base_plate_moment"));
  const td = m.kind === "footing_iso" ? fillFootingTakedownBar(m, changed) : null;
  if (!src.length && td) return td;
  if (!src.length) return el("div", { class: "fill small" }, "Loads can be filled in from a steel column or moment frame" + (m.kind === "base_plate_moment" ? ", or a guard post," : "") + " once the project has one.");
  const pick = el("select", {}, el("option", { value: "" }, "choose a column, frame or guard"), src.map(x => el("option", { value: S.members.indexOf(x) }, (x.values.mark || "(no mark)") + " \u00b7 " + INFO.forms[x.kind].title)));
  const base = el("select", { style: "display:none" });
  let got = null;
  pick.addEventListener("change", async () => {
    got = null; base.style.display = "none"; base.textContent = "";
    if (pick.value === "") return;
    const s = S.members[+pick.value];
    try {
      got = await post("/api/reactions", { kind: s.kind, values: s.values, project: S.project, members: S.members });
      if (got.bases.length > 1) { got.bases.forEach(b => base.append(el("option", { value: b }, /moment$/.test(b) ? b : "base " + b))); base.style.display = ""; }
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
      m.values.loads_from = s.kind === "guard" ? "post base moment and shear of guard " + (s.values.mark || "") + ", no axial load"
        : /moment$/.test(b) ? "base forces of column " + (s.values.mark || "") + " in the 3D frame analysis, " + b + ", second-order analysis"
        : "base reactions of " + (s.values.mark || "member") + (got.bases.length > 1 ? " at " + b : "") + (s.kind === "frame" || (s.values.ends || "").startsWith("free") ? ", second-order analysis" : "");
      if (s.kind === "guard") { m.values.shape = m.values.shape || s.values.post; toast("Guard post base loads filled. The guard load acts in any direction: check the plate with the moment about each axis if the base is not the same both ways.", 12000); }
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
  const first = el("div", { class: "fill" }, el("span", { class: "small" }, "Take the loads from"), pick, base, go);
  return td ? el("div", {}, first, td) : first;
}

// ---------------------------------------------------------------- pages
// ---------------------------------------------------------------- building model
const MODEL_WALLS = ["shear_wall", "perforated_wall", "ftao_wall"];
const FRAME_BRACES = ["tension_member", "angle_strut"];
const MODEL_KINDS = () => TD_BEAMS.concat(TD_POSTS, ["footing_iso", "footing_cont"], MODEL_WALLS, FRAME_BRACES);
function modelOf() { const p = S.project; p.model = p.model || {}; ["levels", "grids_x", "grids_y", "existing"].forEach(k => { p.model[k] = p.model[k] || []; }); return p.model; }

// Placement boxes on a member screen: where the member sits in the building model. Optional; a member works without them.
function placementCard(m, changed) {
  if (m.kind === "diaphragm") {
    const levels_ = modelOf().levels.map(l => (l.name || "").trim()).filter(Boolean);
    if (!levels_.length) return null;
    return el("div", {}, el("h2", {}, "Place in the Building Model (optional)"), el("div", { class: "grid" },
      field({ key: "at_level", label: "Level", type: "select", options: levels_, required: false }, m.values, changed),
      field({ key: "at_dir", label: "Load direction", type: "select", options: ["X", "Y"], required: false, help: "the diaphragm spans between the wall lines parallel to the load" }, m.values, changed)),
      el("div", { class: "help" }, "“Fill the diaphragms from the model” on the Project page writes the governing span, depth and load of this level and direction."));
  }
  if (!MODEL_KINDS().includes(m.kind)) return null;
  const mdl = modelOf(), levels = mdl.levels.map(l => (l.name || "").trim()).filter(Boolean);
  if (!levels.length) return el("div", { class: "help" }, "To place this member in the building model, list the levels (and grids, if you use them) on the Project page first. Placement is optional.");
  const wall = MODEL_WALLS.includes(m.kind);
  const brace = FRAME_BRACES.includes(m.kind);
  const beam = TD_BEAMS.includes(m.kind) || wall || brace, post = TD_POSTS.includes(m.kind) || brace, ftg = !beam && !post;
  const pos = "feet, or a grid name such as B or B+2.5";
  const fs = [];
  if (!ftg) fs.push({ key: "at_level", label: wall ? "Level at its top (the floor or roof it braces)" : brace ? "Level at its upper end" : beam ? "Level it frames" : "Level at its top", type: "select", options: levels, required: false });
  if (post) fs.push({ key: "at_base", label: brace ? "Level at its lower end" : "Level at its base", type: "select", options: levels, required: false, help: "blank = " + levels[0] });
  fs.push({ key: "at_x1", label: brace ? "Lower end, X" : beam ? "Left end, X" : "Position, X", type: "text", required: false, help: pos }, { key: "at_y1", label: brace ? "Lower end, Y" : beam ? "Left end, Y" : "Position, Y", type: "text", required: false, help: pos });
  if (beam) fs.push({ key: "at_x2", label: brace ? "Upper end, X" : "Right end, X", type: "text", required: false, help: pos }, { key: "at_y2", label: brace ? "Upper end, Y" : "Right end, Y", type: "text", required: false, help: pos });
  if (m.kind === "footing_cont") fs.push({ key: "at_x2", label: "Other end of the footing, X", type: "text", required: false, help: "blank = a point; with both ends the footing is a line that walls and joist rows bear on" },
    { key: "at_y2", label: "Other end of the footing, Y", type: "text", required: false, help: pos },
    { key: "at_spread", label: "Footing line: length of footing that takes a point load (post, column, header end)", unit: "ft", type: "text", required: false,
      help: "each point load is checked as a pad: this length of the footing with the point load and the footing's own load over it; where the soil bearing is exceeded a larger pad is sized. Blank = the footing width" },
    { key: "at_spread_source", label: "Where that length comes from", type: "text", required: false },
    { key: "at_pad_width", label: "Larger pads: width across the footing line", unit: "ft", type: "text", required: false, help: "blank = square pads; with a width the pad is lengthened along the line" });
  if (wall) fs.push({ key: "at_wall_psf", label: "Wall weight (gravity load path)", unit: "psf", type: "text", required: false, help: "of wall face; carried down as dead load x the story height (from the level elevations) x the wall length; blank = not included" },
    { key: "at_wall_psf_source", label: "Where the wall weight comes from", type: "text", required: false });
  if (brace) fs.push({ key: "at_brace", label: "In the 3D frame this brace takes", type: "select", options: ["tension only", "tension and compression"], required: false, help: m.kind === "tension_member" ? "blank = tension only" : "blank = tension and compression" });
  if (TD_BEAMS.includes(m.kind)) fs.push({ key: "at_dz1", label: "Left end above the level (sloped member)", unit: "ft", type: "text", required: false, help: "blank = at the level, or following the sloped beam it sits on" },
    { key: "at_dz2", label: "Right end above the level", unit: "ft", type: "text", required: false });
  if (TD_BEAMS.includes(m.kind)) fs.push({ key: "at_row", label: "Joists or rafters: the row runs on, to its left or right, for", unit: "ft", type: "text", required: false,
    help: "for a member with a spacing; + to the right of its line looking from the left end to the right end, - to the left; blank = the row covers the whole beam it lands on. " +
      "A beam placed in a wall line at the wall's top level is a header: it takes what bears on the wall over its length, and its ends go down to what is under the wall." });
  if (m.kind === "steel_beam") fs.push({ key: "at_fix_i", label: "Left end connection (3D frame)", type: "select", options: ["pinned", "moment"], required: false, help: "blank = pinned (shear connection)" },
    { key: "at_fix_j", label: "Right end connection (3D frame)", type: "select", options: ["pinned", "moment"], required: false });
  if (m.kind === "steel_column" || m.kind === "hss_column") fs.push({ key: "at_base_fix", label: "Base (3D frame)", type: "select", options: ["pinned", "fixed", "fixed for sway in X only", "fixed for sway in Y only"], required: false, help: "blank = pinned" },
    { key: "at_web", label: "Web runs along (3D frame)", type: "select", options: ["X", "Y"], required: false, help: "the direction in which the column bends about its strong axis; blank = X" });
  return el("div", {}, el("h2", {}, "Place in the Building Model (optional)"), el("div", { class: "grid" }, fs.map(f => field(f, m.values, changed))),
    el("div", { class: "help" }, wall ? "Placed walls take their wind shear from “Send the wind to the wall lines” on the Project page."
      : brace ? "A placed brace is part of the 3D frame when it is run free to sway (Project page). Each end must be on a placed column or beam, or come down to the lowest level."
      : "Placed members are linked by position with “Link members by position” on the Project page: what sits under each support takes its reaction."));
}

function planSvg(plan, level) {
  const items = plan.items[level] || [];
  const pts = [];
  items.forEach(i => { pts.push(i.p1); if (i.p2) pts.push(i.p2); });
  plan.grids_x.forEach(g => pts.push([g[1], null])); plan.grids_y.forEach(g => pts.push([null, g[1]]));
  const xs = pts.map(p => p[0]).filter(v => v != null), ys = pts.map(p => p[1]).filter(v => v != null);
  if (!xs.length || !ys.length) return el("div", { class: "small" }, "Nothing is placed on this level yet.");
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const w = (x1 - x0) || 10, h = (y1 - y0) || 10, pad = Math.max(w, h) * 0.14, fsz = Math.max(w, h) * 0.042;
  const X = x => x - x0 + pad, Y = y => h - (y - y0) + pad;
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w + 2 * pad} ${h + 2 * pad}`); svg.setAttribute("class", "frame");
  const add = (tag, a, text) => { const n = document.createElementNS(ns, tag); for (const k in a) n.setAttribute(k, a[k]); if (text) n.textContent = text; svg.append(n); };
  plan.grids_x.forEach(g => { add("line", { x1: X(g[1]), y1: pad * 0.45, x2: X(g[1]), y2: h + 1.55 * pad, stroke: "#9AA6B4", "stroke-width": fsz * 0.06, "stroke-dasharray": `${fsz * 0.5} ${fsz * 0.3}` });
    add("text", { x: X(g[1]), y: pad * 0.36, "font-size": fsz, fill: "#3A4756", "text-anchor": "middle" }, g[0]); });
  plan.grids_y.forEach(g => { add("line", { x1: pad * 0.45, y1: Y(g[1]), x2: w + 1.55 * pad, y2: Y(g[1]), stroke: "#9AA6B4", "stroke-width": fsz * 0.06, "stroke-dasharray": `${fsz * 0.5} ${fsz * 0.3}` });
    add("text", { x: pad * 0.3, y: Y(g[1]) + fsz * 0.35, "font-size": fsz, fill: "#3A4756", "text-anchor": "middle" }, g[0]); });
  items.forEach(i => {
    if (i.p2) {
      const joist = false;
      const ftg = i.kind === "footing_cont";
      add("line", Object.assign({ x1: X(i.p1[0]), y1: Y(i.p1[1]), x2: X(i.p2[0]), y2: Y(i.p2[1]), stroke: i.existing ? "#9AA6B4" : i.wall ? "#8A5A2B" : ftg ? "#3A4756" : "#213651",
        "stroke-width": fsz * (i.wall ? 0.7 : ftg ? 0.9 : 0.28), "stroke-linecap": i.wall || ftg ? "butt" : "round" }, ftg ? { "stroke-opacity": 0.35 } : {}, i.existing ? { "stroke-dasharray": `${fsz * 0.3} ${fsz * 0.2}` } : {}));
      const horiz = Math.abs(i.p2[0] - i.p1[0]) >= Math.abs(i.p2[1] - i.p1[1]);
      add("text", { x: (X(i.p1[0]) + X(i.p2[0])) / 2 + (horiz ? 0 : fsz * 0.4), y: (Y(i.p1[1]) + Y(i.p2[1])) / 2 - (horiz ? fsz * 0.4 : 0), "font-size": fsz, fill: "#1B2430", "text-anchor": horiz ? "middle" : "start" }, i.mark);
    } else if (i.kind === "footing_iso" || i.kind === "footing_cont") {
      const s = fsz * 1.6;
      add("rect", { x: X(i.p1[0]) - s, y: Y(i.p1[1]) - s, width: 2 * s, height: 2 * s, fill: "none", stroke: "#3A4756", "stroke-width": fsz * 0.1, "stroke-dasharray": `${fsz * 0.4} ${fsz * 0.25}` });
      add("text", { x: X(i.p1[0]) + s * 1.15, y: Y(i.p1[1]) + s * 1.0, "font-size": fsz, fill: "#3A4756" }, i.mark);
    } else {
      const s = fsz * 0.55;
      add("rect", { x: X(i.p1[0]) - s, y: Y(i.p1[1]) - s, width: 2 * s, height: 2 * s, fill: i.below ? "#1B2430" : "none", stroke: "#1B2430", "stroke-width": fsz * 0.14 });
      add("text", { x: X(i.p1[0]) + s * 1.5, y: Y(i.p1[1]) - s * 1.3, "font-size": fsz, fill: "#1B2430" }, i.mark);
    }
  });
  return svg;
}

// 3D view of the placed members: a parallel projection that can be turned and tilted.
let VIEW = { yaw: 35, tilt: 25 };
function view3dSvg(view) {
  const items = view.items;
  if (!items.length) return el("div", { class: "small" }, "Nothing is placed in the model yet.");
  const yaw = VIEW.yaw * Math.PI / 180, tilt = VIEW.tilt * Math.PI / 180, cy = Math.cos(yaw), sy = Math.sin(yaw), ct = Math.cos(tilt), st = Math.sin(tilt);
  const P = p => { const xr = p[0] * cy + p[1] * sy, yr = -p[0] * sy + p[1] * cy; return [xr, -(p[2] * ct + yr * st), yr * ct - p[2] * st]; };   // screen x, screen y, depth
  const segs = [];
  items.forEach(i => {
    if (i.type === "wall") { const a2 = [i.a[0], i.a[1], i.zb], b2 = [i.b[0], i.b[1], i.zb]; segs.push({ poly: [i.a, i.b, b2, a2], item: i }); }
    else if (i.type === "footing" && i.b) { const z = i.a[2], dx = i.b[0] - i.a[0], dy = i.b[1] - i.a[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, s = 1.0;
      segs.push({ poly: [[i.a[0] + nx * s, i.a[1] + ny * s, z], [i.b[0] + nx * s, i.b[1] + ny * s, z], [i.b[0] - nx * s, i.b[1] - ny * s, z], [i.a[0] - nx * s, i.a[1] - ny * s, z]], item: i }); }
    else if (i.type === "footing") { const s = 1.5, z = i.a[2]; segs.push({ poly: [[i.a[0] - s, i.a[1] - s, z], [i.a[0] + s, i.a[1] - s, z], [i.a[0] + s, i.a[1] + s, z], [i.a[0] - s, i.a[1] + s, z]], item: i }); }
    else segs.push({ line: [i.a, i.b], item: i });
  });
  const all = segs.flatMap(g => (g.poly || g.line).map(P));
  const xs = all.map(p => p[0]), ys = all.map(p => p[1]);
  const x0 = Math.min(...xs), y0 = Math.min(...ys), w = (Math.max(...xs) - x0) || 10, h = (Math.max(...ys) - y0) || 10, pad = Math.max(w, h) * 0.1, fsz = Math.max(w, h) * 0.03;
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${w + 2 * pad} ${h + 2 * pad}`); svg.setAttribute("class", "frame");
  const add = (tag, a, text) => { const n = document.createElementNS(ns, tag); for (const k in a) n.setAttribute(k, a[k]); if (text) n.textContent = text; svg.append(n); };
  const S2 = p => { const q = P(p); return [q[0] - x0 + pad, q[1] - y0 + pad, q[2]]; };
  segs.forEach(g => { const q = (g.poly || g.line).map(S2); g.q = q; g.depth = q.reduce((t, p) => t + p[2], 0) / q.length; });
  segs.sort((a, b) => b.depth - a.depth);                    // far things first
  const col = { beam: "#213651", joist: "#6C7C90", column: "#1B2430" };
  segs.forEach(g => {
    const i = g.item, q = g.q;
    if (g.poly) add("polygon", { points: q.map(p => p[0] + "," + p[1]).join(" "), fill: i.existing ? "#C3C9D1" : i.type === "wall" ? "#C9A27A" : "#D5DAE1", "fill-opacity": i.type === "wall" ? 0.55 : 0.8, stroke: i.existing ? "#7A8594" : i.type === "wall" ? "#8A5A2B" : "#3A4756", "stroke-width": fsz * 0.08 });
    else add("line", { x1: q[0][0], y1: q[0][1], x2: q[1][0], y2: q[1][1], stroke: col[i.type] || "#213651", "stroke-width": fsz * (i.type === "column" ? 0.42 : i.type === "joist" ? 0.14 : 0.3), "stroke-linecap": "round" });
    const mx = q.reduce((t, p) => t + p[0], 0) / q.length, my = q.reduce((t, p) => t + p[1], 0) / q.length;
    add("text", { x: mx + fsz * 0.3, y: my - fsz * 0.3, "font-size": fsz * 0.85, fill: "#1B2430" }, i.mark);
  });
  return svg;
}

let PLAN_LEVEL = null;
function modelCard(changed) {
  const mdl = modelOf();
  const lv = { key: "levels", label: "Levels (lowest first)", columns: [{ key: "name", label: "Level", type: "text", required: true }, { key: "elev", label: "Elevation", unit: "ft", type: "text", required: false }] };
  const gx = { key: "grids_x", label: "Grid lines across (X)", columns: [{ key: "name", label: "Grid", type: "text", required: true }, { key: "at", label: "At X", unit: "ft", type: "text", required: true }] };
  const gy = { key: "grids_y", label: "Grid lines up the plan (Y)", columns: [{ key: "name", label: "Grid", type: "text", required: true }, { key: "at", label: "At Y", unit: "ft", type: "text", required: true }],
    help: "Grids are optional: a member can be placed by feet alone. Where a grid has the same name as a number, the grid is meant." };
  const ex = { key: "existing", label: "Existing construction (by others, not designed here)", columns: [{ key: "name", label: "Name", type: "text", required: true },
      { key: "kind", label: "Is a", type: "select", options: ["wall", "beam", "post", "footing"], required: false },
      { key: "level", label: "Level at its top", type: "text", required: true }, { key: "x1", label: "End 1 (or point), X", type: "text", required: true }, { key: "y1", label: "End 1 (or point), Y", type: "text", required: true },
      { key: "x2", label: "End 2, X", type: "text", required: false }, { key: "y2", label: "End 2, Y", type: "text", required: false }],
    help: "Optional, for additions: existing walls, beams, posts and footings take what bears on them, and the loads are listed for checking the existing construction; an existing wall is also a wall line for wind and seismic. A post or footing may be a point (End 2 blank). Blank Is a = wall." };
  const holder = el("div", {});
  const levels = mdl.levels.map(l => (l.name || "").trim()).filter(Boolean);
  const pickLevel = el("select", {}, levels.map(l => el("option", { value: l }, l)).concat([el("option", { value: "(3D)" }, "3D view")]));
  if (PLAN_LEVEL && (levels.includes(PLAN_LEVEL) || PLAN_LEVEL === "(3D)")) pickLevel.value = PLAN_LEVEL; else if (levels.length) pickLevel.value = levels[levels.length - 1];
  const drawPlan = async () => {
    holder.textContent = ""; PLAN_LEVEL = pickLevel.value;
    if (!levels.length) return;
    try {
      if (pickLevel.value === "(3D)") {
        const view = await post("/api/model_view", { project: S.project, members: S.members });
        const turn = (dy, dt) => () => { VIEW.yaw = (VIEW.yaw + dy + 360) % 360; VIEW.tilt = Math.max(5, Math.min(85, VIEW.tilt + dt)); drawPlan(); };
        holder.append(el("div", { class: "fillbar" }, el("button", { class: "btn", onclick: turn(-15, 0) }, "Turn left"), el("button", { class: "btn", onclick: turn(15, 0) }, "Turn right"),
          el("button", { class: "btn", onclick: turn(0, 10) }, "Look from higher"), el("button", { class: "btn", onclick: turn(0, -10) }, "Look from lower")), view3dSvg(view));
        if (view.problems.length) holder.append(el("ul", { class: "msg small" }, view.problems.map(t => el("li", {}, t))));
      } else { const plan = await post("/api/model_plan", { project: S.project, members: S.members }); holder.append(planSvg(plan, pickLevel.value)); }
    } catch (e) { toast(e.message, 9000); }
  };
  pickLevel.addEventListener("change", drawPlan);
  const link = el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/model_links", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return; }
    S.members = S.members.filter(m => !(m.values || {}).pad_of);
    out.members.forEach((nm, i) => { if (i < S.members.length) S.members[i].values = nm.values; else S.members.push({ kind: nm.kind, values: nm.values }); });
    LINKS = out.links; MODEL_NOTES = out.problems.concat((out.pads || []).map(p => p.mark + ": " + (p.enlarged ? "pad " + p.B + " x " + p.L + " ft sized for " + Math.round(p.P).toLocaleString() + " lb service (the continuous footing is not enough)" :
      "the continuous footing over " + p.L + " ft carries it (" + Math.round(p.q) + " of " + p.q_allow + " psf)") + "; see its Isolated Footing sheet"), (out.existing || []).map(e => "On " + e.wall + ": " + e.source + ", " + e.support + ", " +
      Object.entries(e.cases).map(([c, v]) => c + " " + v.toLocaleString()).join(", ") + " " + e.unit + " (existing construction; check it separately)"));
    setDirty(); await recalcAll(); select("project");
    toast(out.placed + " member" + (out.placed === 1 ? "" : "s") + " placed; " + out.made + " link" + (out.made === 1 ? "" : "s") + " made by position; the load path is recalculated." + (out.problems.length ? " See the notes under the plan." : ""), 12000);
  } }, "Link members by position");
  const latBtn = (which, text) => el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/lateral_wind", { project: S.project, members: S.members, load: which }); } catch (e) { toast(e.message, 12000); return; }
    if (out.lines.length) out.members.forEach((nm, i) => { S.members[i].values = nm.values; });
    WIND_LINES = out.lines; MODEL_NOTES = out.problems;
    setDirty(); await recalcAll(); select("project");
    toast(out.lines.length ? "The walls now carry " + (which === "governing" ? "the governing load of wind and seismic" : "the " + which + " shear") + ", by tributary width, stacked from the top down." : "The load was not distributed. See the notes under the plan.", 12000);
  } }, text);
  const wtBtn = el("button", { class: "btn", onclick: async () => {
    const eq = S.members.filter(m => m.kind === "seismic_elf");
    if (!eq.length) { toast("Add a Seismic Base Shear sheet first; its Levels table names the levels to fill.", 10000); return; }
    let out;
    try { out = await post("/api/model_seismic_weights", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return; }
    let n = 0;
    eq.forEach(m => { (m.values.levels || []).forEach(row => { const nm = (row.name || "").trim(); if (nm in out.levels && out.levels[nm] > 0) { row.w = (out.levels[nm] / 1000).toFixed(1); n++; } });
      m.values.w_source = "building model weight takeoff (ASCE/SEI 7-22 Sect. 12.7.2): dead load of the placed members and walls; " + out.notes[0];
      m.values.w_parts = Object.entries(out.parts).filter(([k, v]) => v.length).map(([k, v]) => k + ": " + Math.round(out.levels[k]).toLocaleString() + " lb").concat(
        ...Object.entries(out.parts).filter(([k, v]) => v.length).map(([k, v]) => v.map(t => "  " + k + ", " + t))); });
    MODEL_NOTES = out.problems.concat(out.notes);
    setDirty(); await recalcAll(); select("project");
    toast(n ? n + " level weight" + (n === 1 ? "" : "s") + " written to the seismic sheet." + (out.problems.length ? " See the notes under the plan." : "") : "No level of the seismic sheet matches a level of the model by name.", 12000);
  } }, "Fill the seismic weights from the model");
  const diaBtn = el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/model_diaphragms", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return; }
    out.members.forEach((nm, i) => { if (nm.kind === "diaphragm") S.members[i].values = nm.values; });
    MODEL_NOTES = out.problems.concat(out.filled.map(f => f.mark + ": span " + f.L + " ft between " + f.lines[0] + " and " + f.lines[1] + ", depth " + f.W + " ft, " + f.w.toFixed(1) + " plf " + f.load));
    setDirty(); await recalcAll(); select("project");
    toast(out.filled.length ? out.filled.length + " diaphragm" + (out.filled.length === 1 ? "" : "s") + " filled from the model." : "No diaphragm was filled. See the notes under the plan.", 12000);
  } }, "Fill the diaphragms from the model");
  const lat = el("span", {}, wtBtn, diaBtn, latBtn("wind", "Send the wind to the wall lines"), latBtn("seismic", "Send the seismic forces"), latBtn("governing", "Use whichever governs each wall"));
  const frameBtn = el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/model_frame", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return; }
    FRAME_CHECK = out; MODEL_NOTES = out.problems.concat(out.notes || []);
    select("project");
    toast(out.columns.length ? "The placed steel framing was analysed as one 3D frame (" + out.size.joints + " joints, " + out.size.members + " members). Column loads are listed beside the takedown's." : "The 3D frame was not run. See the notes under the plan.", 12000);
  } }, "Check the load path with a 3D frame analysis");
  const swayBtn = el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/model_frame_sway", { project: S.project, members: S.members }); } catch (e) { toast(e.message, 12000); return; }
    SWAY = out; MODEL_NOTES = out.problems.concat(out.notes || []);
    if (out.members) { out.members.forEach((nm, i) => { S.members[i].values = nm.values; }); setDirty(); await recalcAll(); }
    select("project");
    toast(out.levels.length ? "The frame was run free to sway by the direct analysis method: " + out.runs + " second-order runs." : "The sway frame was not run. See the notes under the plan.", 12000);
  } }, "Run the 3D frame free to sway (direct analysis method)");
  const ratioCell = (c) => el("td", { class: c.ratio > 1 ? "st FLAG" : "", title: c.ratio_combo || "" }, c.ratio == null ? "not checked" : c.ratio.toFixed(2) + (c.ratio > 1 ? " FLAG" : " OK") + " (Eq. " + c.eq + ")");
  const n1 = (v, d = 1) => (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toLocaleString();
  const bentFields = [["n", "Number of bents"], ["spacing", "Bent spacing, ft (one number, or a list)"], ["end_start", "Roof past the first bent, ft"], ["end_end", "Roof past the last bent, ft"],
    ["col_spacing", "Column spacing across the bent, ft"], ["cant_low", "Rafter cantilever past line A, ft"], ["cant_high", "Rafter cantilever past line B, ft"], ["height", "Height to the top of the line A columns, ft"], ["slope", "Roof rise in 12, up toward line B (blank = level)"],
    ["col_shape", "Column section"], ["col_Fy", "Column Fy, ksi"], ["raf_shape", "Rafter section"], ["raf_Fy", "Rafter Fy, ksi"], ["D", "Roof dead load, psf"], ["S", "Roof snow load, psf"], ["Lr", "Roof live load, psf"],
    ["eave_shape", "Eave beam section along the building, moment-connected (optional)"], ["eave_Fy", "Eave beam Fy, ksi"], ["eave_bays", "Portal bays with eave beams (bay numbers, or all)"],
    ["strut_shape", "Eave strut section in the other bays, pinned (optional)"], ["strut_Fy", "Eave strut Fy, ksi"],
    ["prefix", "Mark prefix (optional)"]];
  const bentBtn = el("button", { class: "btn", onclick: async () => {
    let out;
    try { out = await post("/api/bent_building", { project: S.project, members: S.members, spec: BENT }); } catch (e) { toast(e.message, 12000); return; }
    if (out.problems.length) { MODEL_NOTES = out.problems; select("project"); toast("Nothing was added. See the notes under the plan.", 10000); return; }
    S.project = out.project; S.members = out.members; MODEL_NOTES = out.notes || [];
    setDirty(); await recalcAll(); select("project");
    toast(out.added + " members were added and placed. Run the 3D frame to check them.", 12000);
  } }, "Add the bents to the model");
  const bentCard = el("details", {}, el("summary", {}, "Start a building of bents (carport, pavilion, shed frame)"),
    el("div", { class: "help" }, "Two columns and a rafter at every bent, rigid at the column tops. The roof loads go on each rafter by its tributary width. Everything added can be edited on its own screen afterward."),
    el("div", { class: "grid" }, bentFields.map(([k, label]) => field({ key: k, label, type: "text", required: false }, BENT, () => {})),
      field({ key: "base", label: "Column bases", type: "select", options: ["pinned", "fixed", "fixed for sway in Y only", "fixed for sway in X only"], required: false, help: "The bents stand in the Y direction; X runs along the building. 'Fixed for sway in Y only' fixes the bases for the bents and leaves them pinned along the building." }, BENT, () => {}),
      field({ key: "roof", label: "Roof", type: "select", options: ["single slope or level", "pitched (ridge between the column lines)"], required: false }, BENT, () => {}),
      field({ key: "ridge", label: "Pitched: ridge from column line A, ft (blank = midway)", type: "text", required: false }, BENT, () => {})),
    el("div", { class: "fillbar" }, bentBtn));
  drawPlan();
  return el("div", { class: "card" }, el("h2", {}, "Building Model"), bentCard,
    el("div", { class: "help" }, "Optional. List the levels and grids, place members on their own screens, then link them by position. Every member can still be checked alone."),
    table(lv, mdl.levels, changed), table(gx, mdl.grids_x, changed), table(gy, mdl.grids_y, changed), table(ex, mdl.existing, changed),
    el("div", { class: "grid" }, field({ key: "drift_ratio", label: "Wind drift limit: story height over", type: "text", required: false, help: "for example 240; blank = drift is reported, not checked" }, mdl, changed),
      field({ key: "drift_factor", label: "Wind drift: factor on W", type: "text", required: false, help: "the service wind as a factor on the strength-level wind, for example 0.6" }, mdl, changed),
      field({ key: "drift_source", label: "Wind drift: where the limit and factor come from", type: "text", required: false }, mdl, changed)),
    el("div", { class: "fillbar" }, link, lat, levels.length ? el("span", { class: "small" }, " View ") : null, levels.length ? pickLevel : null),
    holder,
    el("div", { class: "fillbar" }, frameBtn),
    (FRAME_CHECK && FRAME_CHECK.columns && FRAME_CHECK.columns.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Column", "Case", "3D frame", "Takedown", "Difference"].map(t => el("th", {}, t)))),
      el("tbody", {}, FRAME_CHECK.columns.flatMap(c => Object.entries(c.cases).map(([k, v]) => { const d = v[1] ? (v[0] - v[1]) / v[1] * 100 : (Math.abs(v[0]) < 1 ? 0 : null);
        return el("tr", {}, el("td", {}, c.mark), el("td", {}, k), el("td", {}, Math.round(v[0]).toLocaleString() + " lb"), el("td", {}, Math.round(v[1]).toLocaleString() + " lb"),
          el("td", { class: d != null && Math.abs(d) > 5 ? "st FLAG" : "" }, d == null ? "no takedown load" : (d >= 0 ? "+" : "") + d.toFixed(1) + "%")); })))) : null,
    el("div", { class: "fillbar" }, swayBtn),
    (SWAY && SWAY.levels && SWAY.levels.length) ? el("div", {},
      el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Level", "Dir.", "Drift, first-order", "Drift, second-order", "Ratio", "Governing run"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.levels.map(l => el("tr", {}, el("td", {}, l.level), el("td", {}, l.dir), el("td", {}, n1(Math.abs(l.first), 3) + " in"), el("td", {}, n1(Math.abs(l.second), 3) + " in"),
          el("td", { class: l.ratio > 1.5 ? "st FLAG" : "" }, l.ratio.toFixed(2)), el("td", { class: "small" }, l.combo))))),
      el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Column", "Axial at base", "Uplift at base", "Moment, strong axis", "Moment, weak axis", "Axial + bending"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.columns.map(c => el("tr", {}, el("td", {}, c.mark), el("td", { title: c.P_combo }, n1(c.P) + " kip"), el("td", { title: c.T_combo }, c.T > 0.005 ? n1(c.T) + " kip" : "none"), el("td", { title: c.Ms_combo }, n1(c.Ms / 12) + " kip-ft"), el("td", { title: c.Mw_combo }, n1(c.Mw / 12) + " kip-ft"), ratioCell(c))))),
      el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Beam", "Moment", "Shear", "Axial", "Axial + bending", "Shear check"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.beams.map(b => el("tr", {}, el("td", {}, b.mark), el("td", { title: b.M_combo }, n1(b.M / 12) + " kip-ft"), el("td", {}, n1(b.V) + " kip"), el("td", {}, n1(b.N) + " kip"), ratioCell(b), el("td", { class: b.v_ratio > 1 ? "st FLAG" : "" }, b.v_ratio == null ? "not checked" : b.v_ratio.toFixed(2)))))),
      (SWAY.elastic && SWAY.elastic.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Drift under", "Level", "Dir.", "Displacement", "Story drift", "Story height / drift"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.elastic.map(e => el("tr", {}, el("td", {}, e.load === "wind" ? "1.0 W" : "seismic story forces"), el("td", {}, e.level), el("td", {}, e.dir), el("td", {}, n1(e.disp, 3) + " in"),
          el("td", {}, n1(e.story, 3) + " in"), el("td", {}, e.ratio == null ? "" : "H / " + Math.round(e.ratio).toLocaleString()))))) : null,
      (SWAY.drift_checks && SWAY.drift_checks.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Wind drift check", "Dir.", "Drift", "Limit", "D/C"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.drift_checks.map(d => el("tr", {}, el("td", {}, d.level + ", " + d.factor + " W, H / " + d.ratio), el("td", {}, d.dir), el("td", {}, n1(d.drift, 3) + " in"), el("td", {}, n1(d.limit, 3) + " in"),
          el("td", { class: d.drift > d.limit ? "st FLAG" : "" }, (d.drift / d.limit).toFixed(2) + (d.drift > d.limit ? " FLAG" : " OK")))))) : null,
      (SWAY.braces && SWAY.braces.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Brace", "Takes", "Tension", "Compression", "Demand / capacity"].map(t => el("th", {}, t)))),
        el("tbody", {}, SWAY.braces.map(b => el("tr", {}, el("td", {}, b.mark), el("td", {}, b.tension_only ? "tension only" : "tension and compression"), el("td", { title: b.T_combo }, n1(b.T, 2) + " kip"),
          el("td", { title: b.C_combo }, n1(b.C, 2) + " kip"), el("td", { class: b.ratio > 1 ? "st FLAG" : "", title: b.ratio_combo }, b.ratio == null ? "not checked" : b.ratio.toFixed(2) + (b.ratio > 1 ? " FLAG" : " OK")))))) : null,
      el("div", { class: "help" }, "Largest value of each over every run, at the " + SWAY.method + " level. Axial + bending is demand over capacity (1.00 is the limit); hover for the governing run. The member screens are not changed.")) : null,
    (WIND_LINES && WIND_LINES.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Level", "Dir.", "Wall", "Load", "Tributary", "Shear", "From above", "Chord"].map(t => el("th", {}, t)))),
      el("tbody", {}, WIND_LINES.map(l => el("tr", { style: l.governs === false ? "opacity:.55" : "" }, el("td", {}, l.level), el("td", {}, l.wind), el("td", {}, l.wall), el("td", {}, (l.load || "wind") + (l.governs ? " (governs)" : "")), el("td", {}, l.trib.toFixed(1) + " ft"),
        el("td", {}, Math.round(l.V).toLocaleString() + " lb"), el("td", {}, l.from_above ? Math.round(l.from_above).toLocaleString() + " lb" : ""), el("td", {}, l.T == null ? "" : Math.round(l.T).toLocaleString() + " lb"))))) : null, (MODEL_NOTES && MODEL_NOTES.length) ? el("ul", { class: "msg small" }, MODEL_NOTES.map(t => el("li", {}, t))) : null);
}
let MODEL_NOTES = [], WIND_LINES = [], FRAME_CHECK = null, SWAY = null, BENT = {};

function drawMain() {
  const main = $("#main"); main.textContent = "";
  if (sel === "project") return drawProject(main);
  const m = S.members[sel], form = INFO.forms[m.kind];
  const changed = () => { setDirty(); recalc(m); };
  const markF = { key: "mark", label: "Mark", type: "text", required: true };
  const left = el("div", { class: "card" }, fillBar(m, changed), el("h2", {}, form.title),
    el("div", { class: "grid" }, field(markF, m.values, () => { changed(); drawNav(); }), form.fields.map(f => field(f, m.values, changed))),
    form.tables.map(t => { m.values[t.key] = m.values[t.key] || []; return table(t, m.values[t.key], changed); }), placementCard(m, changed));
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
    { key: "seismic_no_ev", label: "Vertical seismic effect Ev", type: "select", options: ["0.2 SDS D", "zero (Seismic Design Category B)"], required: false, help: "ASCE 7-22 Sect. 12.4.2.2" },
    { key: "seismic_omega0", label: "Overstrength factor (optional)", type: "text", required: false, help: "ASCE 7-22 Table 12.2-1; blank = no combinations with overstrength. Members designed for overstrength carry their seismic load under load case Em in place of E." }];
  fillBtns.push(el("button", { class: "btn", onclick: async () => {
    let r;
    try { r = await post("/api/seismic_combos", { sds: p.seismic_sds || "", rho: p.seismic_rho || "1.0", no_ev: (p.seismic_no_ev || "").startsWith("zero"), omega0: p.seismic_omega0 || "" }); }
    catch (e) { toast(e.message, 9000); return; }
    S.prevCombos = { asd: p.combos_asd, lrfd: p.combos_lrfd };
    const keep = rows => (rows || []).filter(c => !/Sect\. 2\.(3\.6|4\.5),/.test(c.source || ""));
    p.combos_asd = keep(p.combos_asd).concat(r.ASD); p.combos_lrfd = keep(p.combos_lrfd).concat(r.LRFD);
    changed(); select("project");
    toast("The seismic combinations are added to both lists. Load case E is the effect of the horizontal seismic forces; enter it with both signs where the force reverses."
      + ((p.seismic_omega0 || "").trim() ? " The combinations with overstrength use load case Em: on a member that must be designed for overstrength, enter the same seismic load under Em in place of E." : ""), 16000);
  } }, "Add the ASCE/SEI 7-22 seismic combinations"));
  if (S.prevCombos) fillBtns.push(el("button", { class: "btn", onclick: () => {
    p.combos_asd = S.prevCombos.asd; p.combos_lrfd = S.prevCombos.lrfd; S.prevCombos = null; changed(); select("project"); } }, "Put back the previous lists"));
  main.append(el("div", { class: "head" }, el("h1", {}, "Project")),
    el("div", { class: "cols" }, el("div", { class: "card" }, el("h2", {}, "Job"), el("div", { class: "grid" }, fs.map(f => field(f, p, () => { changed(); drawFile(); }))),
      el("div", { class: "grid" }, seis.map(f => field(f, p, changed))), el("div", { class: "fillbar" }, fillBtns), table(asd, p.combos_asd, changed), table(lrfd, p.combos_lrfd, changed)),
      modelCard(changed),
      el("div", { class: "card" }, el("h2", {}, "Members"),
        S.members.length ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Mark", "Type", "Result"].map(t => el("th", {}, t)))),
          el("tbody", {}, S.members.map((m, i) => { const r = R.get(m) || {}; const st = r.state === "done" ? r.status : r.state === "stopped" ? "Stopped" : "Not complete";
            return el("tr", { style: "cursor:pointer", onclick: () => select(i) }, el("td", {}, m.values.mark || "(no mark)"), el("td", {}, INFO.forms[m.kind].title),
              el("td", { class: "st " + (r.status || "") }, st)); })))
          : el("div", { class: "small" }, "No members yet. Use “Add a member” at the left, or load the example project to see how the screens work."),
        el("h2", {}, "Load path"),
        el("div", { class: "fillbar" }, el("button", { class: "btn", onclick: async () => { await runTakedown(); select("project"); } }, "Recalculate the load path")),
        (LINKS && LINKS.length) ? el("table", { class: "r" }, el("thead", {}, el("tr", {}, ["Member", "takes the reaction of", "at", "x", "Load"].map(t => el("th", {}, t)))),
          el("tbody", {}, LINKS.map(l => el("tr", {}, el("td", {}, l.target), el("td", {}, l.source), el("td", {}, l.support), el("td", {}, String(l.count)),
            el("td", {}, l.total == null ? "" : Math.round(l.total).toLocaleString() + " " + l.unit)))))
          : el("div", { class: "small" }, "Members linked with “Take the reaction of the member above” are listed here after the load path is recalculated. The links are kept in the project file."),
        el("h2", {}, "What StruKit covers today"),
        el("ul", { class: "msg small" }, ["Steel: beams (spans, overhangs, or fixed at one column), columns, moment frames, tension members, angle struts, HSS; shear tabs, shear end plates, seats, welds, bolts (AISC 360-22).",
          "Steel moment connections: beam over an HSS column on a cap plate; flush end plates with two or four tension bolts; four-bolt extended end plate (AISC Design Guides 24 and 39).",
          "Column bases: centred, with moment about one axis, with moment about both axes (four rods), uplift; anchor rods in concrete (AISC Design Guide 1, ACI 318-19 Ch. 17).",
          "Wood: sawn lumber, glulam, LVL, PSL, LSL and I-joists; posts and built-up columns; nailed, screwed, lagged and bolted connections (2018 NDS).",
          "Lateral: wood shear walls (segmented, perforated, force transfer around an opening), hold-downs, diaphragms, collectors (SDPWS-2021).",
          "Loads: snow, drift, rain, live load reduction, wind and seismic (ASCE/SEI 7-22).",
          "Concrete: isolated and continuous footings, footings with moment (ACI 318-19). Stairs and guards.",
          "Gravity takedown: a member can take the reaction of the member above it; see Load path.",
          "Building model: levels and grids, members placed in plan, sloped members, a quick start for a row of bents (carport, pavilion), plan and 3D views; wind and seismic to the wall lines.",
          "3D frame: the placed steel beams, columns and braces as one frame, run free to sway by the direct analysis method with wind (enclosed or open building), seismic and notional loads; member checks, drift, column base and connection forces carried to their screens.",
          "Every calc package starts with a Design Summary of every check and, with a placed frame, a 3D Frame Analysis sheet.",
          "Not yet: masonry, retaining walls, cold-formed purlins and girts, built-up (three-plate) sections, wood members in the 3D frame.",
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
    if (r.imported) {
      setDirty(true);
      toast("Brought across from StruCalc file " + r.imported + ": " + r.data.members.length + " members. It is a new StruKit project; save it under its own name."
        + (r.notes && r.notes.length ? " Not carried across: " + r.notes.join(" | ") : ""), 30000);
    }
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
  const src = "ASCE/SEI 7-22 Sect. 2.4.1 (typed in)", src2 = "ASCE/SEI 7-22 Sect. 2.3.1 (typed in)";
  return { format: "strukit-project", version: 1,
    project: { name: "Example Project", number: "0000-000", address: "", date: INFO.today, method: "ASD",
      combos_asd: [{ expr: "D + L", source: src }, { expr: "D + 0.7S", source: src }, { expr: "D + 0.6W", source: src }, { expr: "D + 0.75L + 0.45W + 0.525S", source: src }],
      combos_lrfd: [{ expr: "1.2D + 1.6L + 0.3S", source: src2 }, { expr: "1.2D + 1.0S + 0.5W", source: src2 }, { expr: "1.2D + 1.0W + 1.0L + 0.3S", source: src2 }, { expr: "0.9D + 1.0W", source: src2 }] },
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
  document.body.append(el("datalist", { id: "shapes_hss" }, (INFO.hss_shapes || []).map(s => el("option", { value: s }))));
  document.body.append(el("datalist", { id: "shapes_col" }, INFO.shapes.concat(INFO.hss_shapes || []).map(s => el("option", { value: s }))));
  document.body.append(el("datalist", { id: "shapes_tension" }, INFO.shapes.concat(INFO.channel_shapes || [], INFO.hss_shapes || [], INFO.angle_shapes || []).map(s => el("option", { value: s }))));
  document.body.append(el("datalist", { id: "shapes_any" }, INFO.shapes.concat(INFO.channel_shapes || [], INFO.hss_shapes || []).map(s => el("option", { value: s }))));
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
