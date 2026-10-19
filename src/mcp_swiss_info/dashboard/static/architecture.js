// Animated walk-through of one question through the MCP server. Adapted from the Smurf MCP flow
// showcase (trista1208.github.io/smurf-mcp-flow); tool descriptions and sector scores are live.
(() => {
const NS = "http://www.w3.org/2000/svg";
const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, parent, text) => {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
};
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const escH = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

/* ---------- layout ---------- */
const HUBS = {
  user: {x: 95,  y: 280, t: "User",      s: "asks a question"},
  llm:  {x: 330, y: 280, t: "LLM",       s: "the model"},
  mcp:  {x: 565, y: 280, t: "Smurf MCP", s: "mcp-swiss-info"}
};
// Fallback descriptions; replaced by the server's own tool docs once /api/tools answers.
const TOOLS = [
  {id: "geo_search", name: "swiss_geo_search",                  y: 70,  c: "--geo", src: "s_geo",
   d: "Searches map.geo.admin.ch for addresses, ZIP areas and place names. Returns WGS84 coordinates.", a: "query: str, limit: int = 5"},
  {id: "geo_ctx",    name: "swiss_geo_context",                 y: 152, c: "--geo", src: "s_geo",
   d: "Identifies the current municipality, its BFS code, canton and postal area at a WGS84 coordinate.", a: "latitude: float, longitude: float"},
  {id: "permit",     name: "swiss_residence_permit_guidance",   y: 234, c: "--mig", src: "s_sem",
   d: "Retrieves SEM residence guidance for EU/EFTA, third-country and UK nationals, with citations.", a: "group: str, topic: str = \"residence\""},
  {id: "licence",    name: "get_driving_licence_exchange_info", y: 316, c: "--lic", src: "s_db",
   d: "Documented fees, deadlines and requirements for exchanging a foreign licence. A missing fee means unknown, not free.", a: "canton: str = \"CH\", fact_type = \"all\""},
  {id: "health",     name: "swiss_health_insurance_premiums",   y: 398, c: "--hea", src: "s_csv",
   d: "2026 minimum basic premiums. Needs a BFS municipality number, not a postal code. Valid only for 2026.", a: "age: int, municipality_code: int, franchise: int"},
  {id: "vat",        name: "swiss_import_parcel_vat",           y: 480, c: "--cus", src: "s_bazg",
   d: "Estimates import VAT on an online purchase delivered to Switzerland, using BAZG parcel rules.", a: "goods_value_chf, shipping_chf = 0, vat_rate = \"standard\", customs_duty_chf = None"}
];
const SRCS = [
  {id: "s_geo",  n: "geo.admin.ch",       k: "Live federal map API",   y: 111, kind: "web"},
  {id: "s_sem",  n: "sem.admin.ch",       k: "Fetched at query time",  y: 234, kind: "web"},
  {id: "s_db",   n: "Driving licence DB", k: "Local SQLite, reviewed", y: 316, kind: "db"},
  {id: "s_csv",  n: "KVG premiums 2026",  k: "Bundled CSV",            y: 398, kind: "db"},
  {id: "s_bazg", n: "bazg.admin.ch",      k: "Fetched at query time",  y: 480, kind: "web"}
];
const TX = 805, TW = 262, SX = 1080, SW = 180, PX = 1200, PW = 250;
let toolCount = 23, toolNames = [];

const gBg = $("#bg"), gE = $("#edges"), gN = $("#nodes"), gK = $("#peeks"), gF = $("#fx"), gP = $("#packets");

/* ---------- alpine ridges and swirl watermark ---------- */
(function ridges() {
  let seed = 7; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  for (let i = 0; i < 6; i++) {
    const base = 548 - i * 13;
    let d = `M0,${base}`;
    for (let x = 0; x <= 1470; x += 35) {
      const peak = Math.sin(x / 190 + i * 1.3) * 22 + Math.sin(x / 67 + i) * 6 + (rnd() - .5) * 8;
      d += ` L${x},${(base - Math.max(0, peak) * (1 - i * .08)).toFixed(1)}`;
    }
    el("path", {d, class: "ridge", opacity: 1 - i * .12}, gBg);
  }
  const swirl = el("g", {transform: "translate(1280,90) scale(2.4)", opacity: ".09"}, gBg);
  el("path", {d: "M0,-22 C-18,-14 -22,6 -8,20 C4,28 18,16 14,2 C11,-8 0,-6 0,-22Z", fill: "var(--red)"}, swirl);
  el("path", {d: "M0,-22 C18,-14 22,6 8,20 C-4,28 -18,16 -14,2 C-11,-8 0,-6 0,-22Z", fill: "var(--sky)"}, swirl);
})();

/* ---------- edges ---------- */
const edges = {};
function curve(x1, y1, x2, y2) { const mx = (x1 + x2) / 2; return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`; }
function addEdge(a, b, d) { const p = el("path", {d, class: "edge"}, gE); edges[a + ">" + b] = {p, len: p.getTotalLength()}; }
addEdge("user", "llm", curve(139, 280, 286, 280));
addEdge("llm", "mcp", curve(374, 280, 521, 280));
TOOLS.forEach(t => {
  addEdge("mcp", t.id, curve(609, 280, TX - TW / 2, t.y));
  addEdge(t.id, t.src, curve(TX + TW / 2, t.y, SX - SW / 2, SRCS.find(s => s.id === t.src).y));
});
const seg = (a, b) => edges[a + ">" + b] ? {...edges[a + ">" + b], rev: false, key: a + ">" + b} : {...edges[b + ">" + a], rev: true, key: b + ">" + a};

/* ---------- nodes ---------- */
const ICONS = {
  user: g => { el("circle", {cx: 0, cy: -8, r: 8, class: "aico"}, g); el("path", {d: "M-15,16 C-15,4 15,4 15,16", class: "aico"}, g); },
  llm:  g => { el("path", {d: "M0,-17 C2,-5 5,-2 17,0 C5,2 2,5 0,17 C-2,5 -5,2 -17,0 C-5,-2 -2,-5 0,-17Z", class: "aico fill"}, g); },
  mcp:  g => {
    el("path", {d: "M-2,-16 C-14,-10 -16,4 -6,14 C2,20 12,12 10,2 C8,-6 0,-4 -2,-16Z", fill: "var(--red)", stroke: "none"}, g);
    el("path", {d: "M2,-16 C14,-10 16,4 6,14 C-2,20 -12,12 -10,2 C-8,-6 0,-4 2,-16Z", fill: "var(--sky)", stroke: "none", opacity: .95}, g);
  }
};
const hubEls = {};
const MR = 52, MC = 2 * Math.PI * MR;
let meter, ctxText, toolCap;
for (const k in HUBS) {
  const h = HUBS[k];
  const g = el("g", {class: `hub ${k}`, transform: `translate(${h.x},${h.y})`}, gN);
  el("circle", {class: "halo", r: 44}, g);
  if (k === "llm") {
    el("circle", {class: "ameter-track", r: MR}, g);
    meter = el("circle", {class: "ameter", r: MR, "stroke-dasharray": MC, "stroke-dashoffset": MC, transform: "rotate(-90)"}, g);
  }
  el("circle", {class: "body", r: 44}, g);
  ICONS[k](el("g", {}, g));
  el("text", {class: "t", y: 76}, g, h.t);
  el("text", {class: "s", y: 94}, g, h.s);
  if (k === "llm") ctxText = el("text", {class: "ctx", y: 112}, g, "context 0 tokens");
  hubEls[k] = {g, st: el("text", {class: "st", y: -70}, g)};
}
toolCap = el("text", {class: "cap", x: TX - TW / 2, y: 30}, gN, `6 of the server's ${toolCount} tools`);
el("text", {class: "cap", x: SX - SW / 2, y: 30}, gN, "Where the data lives");
el("text", {class: "cap", x: PX, y: 30}, gN, "What the source hands over");
const toolEls = {};
TOOLS.forEach(t => {
  const g = el("g", {class: "tool", transform: `translate(${TX - TW / 2},${t.y - 19})`, tabindex: 0, "aria-label": `${t.name}: ${t.d}`}, gN);
  el("rect", {width: TW, height: 38, rx: 8}, g);
  el("circle", {class: "chip", cx: 15, cy: 19, r: 5, fill: `var(${t.c})`}, g);
  el("text", {x: 27, y: 23}, g, t.name);
  toolEls[t.id] = g;
  const show = () => showTip(t, g), hide = () => $("#atip").classList.remove("show");
  g.addEventListener("mouseenter", show); g.addEventListener("focus", show);
  g.addEventListener("mouseleave", hide); g.addEventListener("blur", hide);
});
const srcEls = {};
SRCS.forEach(s => {
  const g = el("g", {class: "src", transform: `translate(${SX - SW / 2},${s.y - 24})`}, gN);
  el("rect", {width: SW, height: 48, rx: 8}, g);
  const ig = el("g", {transform: "translate(20,24)"}, g);
  if (s.kind === "web") {
    el("circle", {r: 9, class: "si"}, ig);
    el("path", {d: "M-9,0 H9 M0,-9 C-5,-4 -5,4 0,9 C5,4 5,-4 0,-9", class: "si"}, ig);
  } else {
    el("ellipse", {cx: 0, cy: -6, rx: 8, ry: 3.5, class: "si"}, ig);
    el("path", {d: "M-8,-6 V6 C-8,11 8,11 8,6 V-6 M-8,0 C-8,5 8,5 8,0", class: "si"}, ig);
  }
  el("text", {class: "n", x: 38, y: 21}, g, s.n);
  el("text", {class: "k", x: 38, y: 37}, g, s.k);
  srcEls[s.id] = g;
});

function showTip(t, g) {
  const tip = $("#atip"), box = $("#stagebox");
  tip.innerHTML = `<b>${escH(t.name)}</b><div>${escH(t.d)}</div><code>(${escH(t.a)})</code>`;
  const r = g.getBoundingClientRect(), b = box.getBoundingClientRect();
  tip.style.left = (r.left - b.left + box.scrollLeft) + "px";
  tip.style.top = (r.bottom - b.top + 8) + "px";
  tip.classList.add("show");
}

/* ---------- source peek cards ---------- */
const CH = [[5.97,46.2],[6.1,46.6],[6.45,46.95],[6.95,47.25],[7.0,47.5],[7.6,47.6],[8.2,47.62],[8.55,47.8],[8.9,47.65],[9.5,47.55],[9.6,47.2],[9.53,47.05],[10.1,46.85],[10.47,46.85],[10.4,46.55],[10.05,46.23],[9.3,46.5],[9.0,46.0],[8.9,45.83],[8.45,46.25],[8.1,46.1],[7.85,45.93],[7.0,45.9],[6.8,46.4],[6.2,46.25]];
const mx = lon => (lon - 5.9) * 30, my = lat => (47.85 - lat) * 44;
function card(g, h, c, title) {
  el("rect", {class: "pcard", width: PW, height: h, rx: 10, stroke: `var(${c})`}, g);
  el("rect", {width: 4, height: h - 20, x: 0, y: 10, fill: `var(${c})`}, g);
  el("text", {class: "h", x: 14, y: 20}, g, title);
}
function mapInto(g, x, y, c, mode) {
  const m = el("g", {transform: `translate(${x},${y})`}, g);
  el("path", {class: "ch", d: "M" + CH.map(([a, b]) => `${mx(a).toFixed(1)},${my(b).toFixed(1)}`).join(" L") + "Z"}, m);
  const zx = mx(8.54), zy = my(47.377);
  if (mode === "blob") el("path", {class: "blob", d: `M${zx-7},${zy-3} L${zx-2},${zy-8} L${zx+6},${zy-6} L${zx+8},${zy+2} L${zx+2},${zy+7} L${zx-6},${zy+5}Z`, fill: `var(${c})`, opacity: .55}, m);
  const pin = el("g", {class: "pin"}, m);
  const pg = el("g", {transform: `translate(${zx},${zy})`}, pin);
  el("path", {d: "M0,0 C-2,-5 -6,-8 -6,-12 A6,6 0 1 1 6,-12 C6,-8 2,-5 0,0Z", fill: "var(--red)"}, pg);
  el("circle", {cx: 0, cy: -12, r: 2.2, fill: "#fff"}, pg);
}
function lines(g, c, rs) {
  rs.forEach((r, i) => {
    const y = 29 + i * 15;
    if (r.hi) el("rect", {x: 10, y, width: PW - 20, height: 14, rx: 3, fill: `var(${c})`, opacity: r.hi === 2 ? .1 : .2}, g);
    el("text", {class: r.hi ? "hi" : "", x: 14, y: y + 10.5}, g, r.t);
  });
}
const PEEKS = {
  geo_search: {h: 116, t: "Found: 8004 Zürich", f: (g, c) => { mapInto(g, 14, 28, c, "pin"); el("text", {x: 160, y: 60}, g, "lat 47.377"); el("text", {x: 160, y: 76}, g, "lon 8.519"); el("text", {x: 160, y: 92}, g, "via zipcode"); }},
  geo_ctx:    {h: 116, t: "Municipality at that point", f: (g, c) => { mapInto(g, 14, 28, c, "blob"); el("text", {class: "hi", x: 160, y: 60}, g, "Zürich"); el("text", {x: 160, y: 76}, g, "BFS 261"); el("text", {x: 160, y: 92}, g, "canton ZH"); }},
  permit:     {h: 80, t: "sem.admin.ch, fetched now", f: (g, c) => lines(g, c, [{t: "B EU/EFTA permit"}, {t: "job of 1 year or unlimited", hi: 1}, {t: "valid for five years", hi: 1}])},
  licence:    {h: 80, t: "Rows matched in SQLite", f: (g, c) => lines(g, c, [{t: "CH rule  group A: no drive test", hi: 1}, {t: "ZH fee   application review  50", hi: 1}, {t: "ZH fee   identity check      20", hi: 1}])},
  health:     {h: 80, t: "Rows matched in the CSV", f: (g, c) => lines(g, c, [{t: "Winterthur  230  2500   …"}, {t: "Zürich 261 2500 excl.  366.90", hi: 1}, {t: "Zürich 261 2500 incl.  389.40", hi: 2}])},
  vat:        {h: 80, t: "bazg.admin.ch, fetched now", f: (g, c) => lines(g, c, [{t: "VAT on goods value + shipping", hi: 1}, {t: "standard 8.1%, reduced 2.6%", hi: 1}, {t: "VAT up to CHF 5 not levied"}])}
};
function showPeek(toolId) {
  const t = TOOLS.find(x => x.id === toolId), P = PEEKS[toolId];
  if (!P) return;
  const s = SRCS.find(x => x.id === t.src);
  const outer = el("g", {transform: `translate(${PX},${s.y - P.h / 2})`}, gK);
  el("path", {d: `M${SX + SW / 2 - PX},${P.h / 2} H0`, stroke: `var(${t.c})`, "stroke-width": 1.5, "stroke-dasharray": "3 3"}, outer);
  const g = el("g", {class: "peek"}, outer);
  card(g, P.h, t.c, P.t);
  P.f(g, t.c);
  requestAnimationFrame(() => requestAnimationFrame(() => g.classList.add("show")));
}

/* ---------- scenarios ---------- */
const toolOf = id => TOOLS.find(t => t.id === id);
const call = (tool, label, payload) => ({route: ["llm", "mcp", tool, toolOf(tool).src], label, c: toolOf(tool).c, payload, tool: toolOf(tool).name, dir: "call"});
const back = (tool, label, payload) => ({route: [toolOf(tool).src, tool, "mcp", "llm"], label, c: toolOf(tool).c, payload, tool: toolOf(tool).name, dir: "result"});
const discover = {route: ["mcp", "llm"], label: "tools", c: "--red", after: true, discover: true, payload: {tools: []}};

const SC = {
  move: {
    question: "I'm Belgian, 31, and moving to 8004 Zürich for a permanent job. Which permit do I get, what's the cheapest health insurance with a CHF 2,500 franchise, and can I just swap my Belgian driving licence?",
    picked: ["geo_search", "geo_ctx", "permit", "licence", "health"],
    answer: [
      {c: "--mig", lead: "Permit.", text: " As a Belgian (EU/EFTA) with a permanent Swiss job, you get a B EU/EFTA permit, issued for five years."},
      {c: "--hea", lead: "Health insurance.", text: " In the city of Zürich (BFS 261), the cheapest 2026 basic cover at a CHF 2,500 franchise is CHF 366.90 a month with Assura (Qualimed), without accident cover. Employees are covered for accidents through work, so you likely don't need the CHF 389.40 Atupri HMO option that includes it."},
      {c: "--lic", lead: "Driving licence.", text: " Yes. Belgium is on the ASTRA group A list, so no control drive. You must switch within 12 months of living here: eye test at a Swiss optician, passport photo, form ZFO104AUSL, identity check at your Einwohnerkontrolle. Fees: CHF 50 for the application plus CHF 20 for the identity check."}
    ],
    sources: [["--mig","SEM"],["--geo","geo.admin.ch"],["--hea","Priminfo 2026"],["--lic","Strassenverkehrsamt ZH"]],
    steps: [
      {t: "User asks a question", who: "User → LLM",
       why: "Your message is the first packet. It carries three separate questions and two clues the tools will need: your nationality and your postal code.",
       packets: [{route: ["user", "llm"], label: "User question", c: "--red", payload: {role: "user", content: "I'm Belgian, 31, moving to 8004 Zürich… permit? health insurance? driving licence?"}}],
       status: {llm: "reading"}},
      {t: "The LLM asks what the server can do", short: "Discover", who: "LLM ↔ MCP server",
       why: "Through the MCP protocol, the client lists the server's tools once per session. Each tool comes with a name, a description and a typed argument schema. That catalogue is what the LLM chooses from.",
       packets: [{route: ["llm", "mcp"], label: "tools/list", c: "--red", payload: {jsonrpc: "2.0", method: "tools/list"}}, discover],
       status: {llm: "discovering", mcp: "FastMCP"}},
      {t: "The LLM plans which tools to call", who: "LLM",
       why: "No data moves yet. The LLM matches each sub-question to a tool by reading the descriptions, and spots a dependency hidden in one of them.",
       think: true,
       notes: [
         "Permit → swiss_residence_permit_guidance(group=\"eu_efta\", topic=\"B\")",
         "Licence → get_driving_licence_exchange_info(canton=\"ZH\")",
         "Premium needs a BFS municipality number, and the description says a postal code will not work. So 8004 must be resolved first: geo_search, then geo_context.",
         "Permit, licence and the first geo lookup are independent, so they go out together."
       ],
       status: {llm: "planning"}},
      {t: "Round 1: three tools, out and back", short: "Round 1", who: "LLM ⇄ MCP ⇄ tools ⇄ sources",
       why: "Each call leaves with its arguments and returns carrying data from its source: a live API, a page fetched now, or a local database. The three questions don't depend on each other, so they run at the same time.",
       packets: [
         call("geo_search", "\"8004 Zürich\"", {tool: "swiss_geo_search", arguments: {query: "8004 Zürich", limit: 1}}), {...back("geo_search", "47.377, 8.519", {status: "answered", results: [{label: "8004 Zürich", origin: "zipcode", latitude: 47.3772, longitude: 8.5189}]}), after: true},
         call("permit", "eu_efta / B", {tool: "swiss_residence_permit_guidance", arguments: {group: "eu_efta", topic: "B"}}), {...back("permit", "B permit, 5 yrs", {status: "answered", title: "B EU/EFTA permit (Resident foreign nationals)", source_url: "https://www.sem.admin.ch/…/ausweis_b_eu_efta.html", excerpt: "…employment of at least one year or unlimited… valid for five years…"}), after: true},
         call("licence", "canton ZH", {tool: "get_driving_licence_exchange_info", arguments: {canton: "ZH", fact_type: "all"}}), {...back("licence", "no control drive", {jurisdiction: "ZH", country_group: "ASTRA_A (BE)", fees_chf: {application_review: 50, identity_check: 20}, deadline: "Swiss licence required after 12 months of residence", requirements: ["eye test", "colour passport photo", "form ZFO104AUSL", "identity check in person"]}), after: true}],
       status: {llm: "3 calls in flight", mcp: "routing"}},
      {t: "Round 2: postal code to municipality", short: "Round 2", who: "LLM ⇄ swiss_geo_context",
       why: "The coordinates from round 1 go straight into the next tool. It returns Zürich's BFS number 261, the only identifier the premium tool accepts.",
       packets: [call("geo_ctx", "47.377, 8.519", {tool: "swiss_geo_context", arguments: {latitude: 47.3772, longitude: 8.5189}}), {...back("geo_ctx", "BFS 261", {status: "answered", municipality: "Zürich", bfs_number: 261, canton: "ZH", postal_code: "8004", map_url: "https://map.geo.admin.ch/…"}), after: true}],
       status: {llm: "chaining"}},
      {t: "Round 3: the premium lookup", short: "Round 3", who: "LLM ⇄ swiss_health_insurance_premiums",
       why: "Age and franchise come from your message, BFS 261 from round 2. The tool reads the bundled 2026 CSV and returns both accident-cover options.",
       packets: [call("health", "31 / 261 / 2500", {tool: "swiss_health_insurance_premiums", arguments: {age: 31, municipality_code: 261, franchise: 2500}}), {...back("health", "CHF 366.90", {status: "answered", year: 2026, municipality: "Zürich", age_group: "adult_26_plus", franchise_chf: 2500, premiums: [{accident_cover: "excluded", minimum_premium: "366.9", insurer: "Assura-Basis SA", model: "Qualimed"}, {accident_cover: "included", minimum_premium: "389.4", insurer: "Atupri", model: "HMO"}], message: "2026 only; not valid for 2027."}), after: true}],
       status: {llm: "chaining"}},
      {t: "The LLM merges five results", who: "LLM",
       why: "Nothing new is fetched. The LLM lines up the facts, drops what you didn't ask for, and makes one judgement call: with a job, accident cover is normally provided by the employer, so the cheaper option fits.",
       think: true, merge: [
         ["--mig", "Permit", "B EU/EFTA, 5 years"],
         ["--geo", "Location", "8004 → Zürich, BFS 261, canton ZH"],
         ["--hea", "Premium", "CHF 366.90/month, Assura Qualimed, no accident cover"],
         ["--lic", "Licence", "No control drive, 12-month deadline, CHF 50 + 20"]],
       status: {llm: "merging"}},
      {t: "The answer comes back to the user", who: "LLM → User",
       why: "One reply, three answers, each traceable to an official source.",
       packets: [{route: ["llm", "user"], label: "Answer", c: "--red", payload: {role: "assistant", content: "Permit: B EU/EFTA… Premium: CHF 366.90… Licence: exchange within 12 months…", citations: 4}}],
       status: {llm: "writing"}, answer: true}
    ]
  },
  vat: {
    question: "I ordered a jacket from a Belgian shop: CHF 180 plus CHF 20 shipping, no foreign VAT charged. How much import VAT will I pay?",
    picked: ["vat"], cached: true,
    answer: [
      {c: "--cus", lead: "About CHF 16.20.", text: " Swiss import VAT is charged on the goods plus shipping, so CHF 200 at the standard 8.1% rate. Clothing doesn't qualify for the reduced rate."},
      {c: "--cus", lead: "Not included:", text: " customs duty on the jacket and the carrier's own clearance fee, which the courier bills separately."}
    ],
    sources: [["--cus","BAZG parcels page"]],
    steps: [
      {t: "User asks a question", who: "User → LLM",
       why: "A single, well-scoped question with every number the tool needs.",
       packets: [{route: ["user", "llm"], label: "Your question", c: "--red", payload: {role: "user", content: "Jacket from Belgium, CHF 180 + CHF 20 shipping. Import VAT?"}}],
       status: {llm: "reading"}},
      {t: "One tool fits", who: "LLM",
       why: "The tool catalogue is already known from the session start. Only one tool matches, and all its arguments are in the message.",
       think: true,
       notes: [
         "Import VAT on an online purchase → swiss_import_parcel_vat",
         "Clothing is not a reduced-rate good → vat_rate=\"standard\"",
         "Customs duty unknown → leave it out and warn the user"],
       status: {llm: "planning"}},
      {t: "One call, out and back", short: "Round 1", who: "LLM ⇄ MCP ⇄ BAZG",
       why: "The tool fetches the current BAZG parcel page, applies the rule and returns the estimate with its caveats.",
       packets: [call("vat", "180 + 20, standard", {tool: "swiss_import_parcel_vat", arguments: {goods_value_chf: 180, shipping_chf: 20, vat_rate: "standard"}}), {...back("vat", "CHF 16.20", {status: "answered", vat_basis_chf: 200.0, vat_rate_pct: 8.1, import_vat_chf: 16.2, not_included: ["customs duty", "carrier clearance charges"], source_url: "https://www.bazg.admin.ch/en/receipt-of-letters-and-parcels"}), after: true}],
       status: {llm: "1 call in flight", mcp: "routing"}},
      {t: "Little to merge", who: "LLM",
       why: "One result, so merging is mostly about keeping the caveats.",
       think: true, merge: [["--cus", "Import VAT", "CHF 16.20 on a CHF 200 basis"], ["--cus", "Caveat", "Customs duty and courier fee not included"]],
       status: {llm: "merging"}},
      {t: "The answer comes back to the user", who: "LLM → User",
       why: "Short question, short answer, with the limits stated.",
       packets: [{route: ["llm", "user"], label: "Answer", c: "--red", payload: {role: "assistant", content: "About CHF 16.20…"}}],
       status: {llm: "writing"}, answer: true}
    ]
  }
};

/* ---------- state ---------- */
let sc = "move", idx = 0, playing = !reduce, speed = 1;
let live = [], stepStart = 0, stepDur = 0, stepToken = 0, typed = null, ctx = 0, fx = [];
const HOP = 950;
const S = () => SC[sc];
const isOut = p => HUBS[p.route[0]] ? (pos(p.route.at(-1)).x > pos(p.route[0]).x) : false;
function pos(id) { if (HUBS[id]) return HUBS[id]; const t = TOOLS.find(x => x.id === id); if (t) return {x: TX, y: t.y}; const s = SRCS.find(x => x.id === id); return {x: SX, y: s.y}; }

/* ---------- context meter ---------- */
function tokens(p) {
  if (p.discover) return 3100;
  if (p.route[0] === "user") return Math.round(S().question.length / 4) + 40;
  if (p.route.at(-1) === "user") return Math.round(S().answer.map(a => a.lead + a.text).join("").length / 4);
  return Math.round(JSON.stringify(p.payload).length / 3.2);
}
const counts = p => p.route.at(-1) === "llm" || p.route.at(-1) === "user";
function ctxBefore(i) {
  let n = S().cached ? 3100 : 0;
  S().steps.slice(0, i).forEach(st => (st.packets || []).forEach(p => { if (counts(p)) n += tokens(p); }));
  return n;
}
function setCtx(n) {
  ctx = n;
  meter.setAttribute("stroke-dashoffset", MC * (1 - Math.min(1, n / 6000)));
  ctxText.textContent = `context ${n >= 1000 ? (n / 1000).toFixed(1) + "k" : n} tokens`;
}

/* ---------- packets ---------- */
function makePacket(p, startAt, k) {
  const out = isOut(p);
  const g = el("g", {class: "pk", opacity: 0}, gP);
  const col = `var(${p.c})`;
  const lab = el("g", {transform: `translate(0,${k % 2 ? 28 : -26})`}, g);
  const r = el("rect", {rx: 10, height: 20, y: -10}, lab);
  const t = el("text", {y: 4, "text-anchor": "middle"}, lab, p.label);
  if (out) { r.style.fill = "var(--card)"; r.style.stroke = col; r.style.strokeWidth = 1.5; t.style.fill = col; }
  else { r.style.fill = col; t.style.fill = "var(--on-fill)"; }
  const w = t.getComputedTextLength() + 16;
  r.setAttribute("width", w); r.setAttribute("x", -w / 2);
  const c = el("circle", {r: out ? 7 : 9.5}, g);
  if (out) { c.style.fill = "var(--card)"; c.style.stroke = col; c.style.strokeWidth = 3; }
  else { c.style.fill = col; c.style.stroke = "var(--card)"; c.style.strokeWidth = 2.5; }
  const segs = [];
  for (let i = 0; i < p.route.length - 1; i++) segs.push(seg(p.route[i], p.route[i + 1]));
  const hop = HOP / speed * (reduce ? 0.15 : 1);
  return {g, segs, p, k, start: startAt, dur: hop * segs.length, fired: false};
}
const ease = x => x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
function place(pk, now) {
  let t = (now - pk.start) / pk.dur;
  if (t < 0) { pk.g.setAttribute("opacity", 0); return 0; }
  if (t > 1) t = 1;
  pk.g.setAttribute("opacity", t >= 1 ? 0 : 1);
  const f = t * pk.segs.length, i = Math.min(pk.segs.length - 1, Math.floor(f)), e = ease(f - i), s = pk.segs[i];
  const pt = s.p.getPointAtLength(s.rev ? s.len * (1 - e) : s.len * e);
  pk.g.setAttribute("transform", `translate(${pt.x},${pt.y})`);
  pk.cur = i;
  return t;
}

/* ---------- timeline ---------- */
let wfBars = {};
function buildWF() {
  const s = S(), cols = [];
  s.steps.forEach((st, i) => { if (st.short) cols.push(i); });
  const grid = $("#wf");
  grid.style.gridTemplateColumns = `minmax(200px,260px) repeat(${cols.length}, minmax(80px,1fr)) minmax(110px,150px)`;
  let h = `<div></div>` + cols.map(i => `<div class="wfh" data-col="${i}">${s.steps[i].short}</div>`).join("") + `<div class="wfh">Returned</div>`;
  cols.forEach(i => {
    let k = 0;
    s.steps[i].packets.forEach((p, pi) => {
      if (p.after) return;
      const res = s.steps[i].packets[pi + 1];
      h += `<div class="wfl"><i style="background:var(${p.c})"></i>${escH(p.tool || p.label)}</div>`;
      cols.forEach(cj => {
        h += cj === i ? `<div class="track"><span class="o"><b id="wo-${i}-${k}" style="background:var(${p.c})"></b></span><span><b id="wb-${i}-${k}" style="background:var(${p.c})"></b></span></div>` : `<div></div>`;
      });
      h += `<div class="wfr" id="wr-${i}-${k}" style="color:var(${p.c})">${res ? escH(res.label) : ""}</div>`;
      k++;
    });
  });
  grid.innerHTML = h;
  wfBars = {};
  s.steps.forEach((st, i) => { if (st.short) { let k = 0; st.packets.forEach(p => { if (!p.after) { wfBars[i + ":" + k] = {o: $(`#wo-${i}-${k}`), b: $(`#wb-${i}-${k}`), r: $(`#wr-${i}-${k}`)}; k++; } }); } });
}
function syncWF() {
  for (const key in wfBars) {
    const i = +key.split(":")[0], w = i < idx ? 100 : 0, bar = wfBars[key];
    bar.o.style.width = bar.b.style.width = w + "%";
    bar.r.classList.toggle("show", i < idx);
  }
  document.querySelectorAll(".wfh[data-col]").forEach(h => h.classList.toggle("cur", +h.dataset.col === idx));
}

/* ---------- step rendering ---------- */
function unlight() { document.querySelectorAll("#stage .lit").forEach(n => n.classList.remove("lit")); }
function clearStage() {
  gP.innerHTML = ""; gK.innerHTML = ""; gF.innerHTML = ""; live = []; fx = [];
  Object.values(edges).forEach(e => e.p.classList.remove("live"));
  unlight();
}
function setPicked(progress) {
  const s = S(), planIdx = s.steps.findIndex(x => x.think);
  TOOLS.forEach(t => {
    const pi = s.picked.indexOf(t.id);
    let on = pi >= 0 && idx > planIdx;
    if (idx === planIdx && pi >= 0) on = progress != null && progress >= .15 + pi * .13;
    const node = toolEls[t.id];
    if (on && !node.classList.contains("picked") && idx === planIdx) { node.classList.add("pop"); setTimeout(() => node.classList.remove("pop"), 500); }
    node.classList.toggle("picked", on);
  });
}
function setStatus(st) { for (const k in hubEls) hubEls[k].st.textContent = (st && st[k]) || ""; }
function hl(id, on) { const n = hubEls[id] ? hubEls[id].g : toolEls[id] || srcEls[id]; if (n) n.classList.toggle("lit", on); }

function runStep(i) {
  const token = ++stepToken;
  idx = i;
  clearStage();
  $("#rail").style.width = (S().steps.length < 2 ? 100 : (i / (S().steps.length - 1)) * 100) + "%";
  const st = S().steps[i];
  setPicked(0); setStatus(st.status); setCtx(ctxBefore(i));
  renderSteps(); renderNow(); renderChat(); syncWF();
  const now = performance.now();
  stepStart = now;
  if (st.packets) {
    let ci = 0, prev = null;
    st.packets.forEach(p => {
      let pk;
      if (p.after && prev) pk = makePacket(p, prev.start + prev.dur + 250 / speed, prev.k);
      else { pk = makePacket(p, now + ci * 450 / speed, ci); ci++; prev = pk; }
      live.push(pk);
    });
    stepDur = Math.max(...live.map(pk => pk.start + pk.dur)) - now + (st.short ? 900 / speed : 0);
  } else {
    stepDur = (reduce ? 600 : st.merge ? 4200 : 3600) / speed;
    hl("llm", true);
    if (st.merge) buildOrbit(st);
  }
  if (st.answer) startTyping(token);
  requestAnimationFrame(t => frame(t, token));
}

/* ---------- merge orbit ---------- */
function buildOrbit(st) {
  fx = st.merge.map(([c], j) => {
    const g = el("g", {}, gF);
    el("circle", {r: 16, fill: `var(${c})`, opacity: .18}, g);
    el("circle", {r: 8, fill: `var(${c})`}, g);
    const tool = TOOLS.find(t => t.c === c) || TOOLS[0];
    return {g, from: {x: TX - TW / 2, y: tool.y}, a0: j / st.merge.length * Math.PI * 2};
  });
  const core = el("g", {opacity: 0}, gF);
  el("circle", {r: 24, fill: "var(--red)", opacity: .2}, core);
  el("circle", {r: 11, fill: "var(--red)"}, core);
  fx.core = core;
  fx.c = HUBS.llm;
}
function orbit(T) {
  if (!fx.length) return;
  const {x: cx, y: cy} = fx.c;
  fx.forEach(o => {
    let x, y, op = 1;
    const a = o.a0 + T * 9;
    if (T < .22) {
      const u = ease(T / .22), ox = cx + Math.cos(o.a0) * 80, oy = cy + Math.sin(o.a0) * 80;
      x = o.from.x + (ox - o.from.x) * u; y = o.from.y + (oy - o.from.y) * u;
    } else {
      const r = T < .6 ? 80 : 80 * Math.max(0, 1 - (T - .6) / .22);
      x = cx + Math.cos(a) * r; y = cy + Math.sin(a) * r;
      if (T > .82) op = 0;
    }
    o.g.setAttribute("transform", `translate(${x},${y})`);
    o.g.setAttribute("opacity", op);
  });
  const k = T < .8 ? 0 : Math.min(1, (T - .8) / .1);
  fx.core.setAttribute("opacity", k);
  fx.core.setAttribute("transform", `translate(${cx},${cy}) scale(${.4 + .6 * k + (T > .9 ? Math.sin((T - .9) * 30) * .06 : 0)})`);
}

function frame(now, token) {
  if (token !== stepToken) return;
  const st = S().steps[idx], T = Math.min(1, (now - stepStart) / stepDur);
  const active = new Set(), edgeLive = new Set();
  live.forEach(pk => {
    const t = place(pk, now);
    const bar = wfBars[idx + ":" + pk.k];
    if (bar) (pk.p.after ? bar.b : bar.o).style.width = (t * 100) + "%";
    if (t > 0 && t < 1) {
      edgeLive.add(pk.segs[pk.cur].key);
      active.add(pk.p.route[pk.cur]); active.add(pk.p.route[pk.cur + 1]);
    }
    if (t >= 1 && !pk.fired) {
      pk.fired = true;
      if (isOut(pk.p) && pk.p.route.length === 4) showPeek(pk.p.route[2]);
      if (counts(pk.p)) setCtx(ctx + tokens(pk.p));
      if (bar && pk.p.after) bar.r.classList.add("show");
    }
  });
  if (live.length) {
    Object.entries(edges).forEach(([k, e]) => e.p.classList.toggle("live", edgeLive.has(k)));
    ["user", "llm", "mcp", ...TOOLS.map(t => t.id), ...SRCS.map(s => s.id)].forEach(n => hl(n, active.has(n)));
  }
  if (st.think && !st.merge) setPicked(T);
  if (st.merge) orbit(T);
  const typingBusy = typed && !typed.done;
  if (T >= 1 && !typingBusy) {
    Object.values(edges).forEach(e => e.p.classList.remove("live"));
    unlight();
    gP.innerHTML = "";
    if (st.answer) setStatus({});
    renderSteps();
    if (playing && idx < S().steps.length - 1) {
      setTimeout(() => { if (token === stepToken && playing) runStep(idx + 1); }, 700 / speed);
    } else if (idx === S().steps.length - 1) { playing = false; updatePlay(); }
    return;
  }
  requestAnimationFrame(t => frame(t, token));
}

/* ---------- panels ---------- */
const COLNAME = {"--red": "Message", "--geo": "Geo", "--mig": "Migration", "--lic": "Driving licence", "--hea": "Health insurance", "--cus": "Customs"};
function renderNow() {
  const st = S().steps[idx];
  let h = `<div class="head"><div class="stepno">${idx + 1}</div><div><h3>${escH(st.t)}</h3><div class="sub">${escH(st.who)}</div></div></div>`;
  h += `<p class="why">${escH(st.why)}</p>`;
  if (st.notes) h += `<ul class="notes">${st.notes.map(n => `<li>${escH(n)}</li>`).join("")}</ul>`;
  if (st.merge) h += `<table class="facts">${st.merge.map(([c, k, v]) => `<tr><td><span class="sw" style="background:var(${c})"></span></td><td class="k">${escH(k)}</td><td>${escH(v)}</td></tr>`).join("")}</table>`;
  if (st.packets) st.packets.forEach(p => {
    const out = isOut(p);
    const title = p.tool ? `${out ? "Request" : "Data back"}: ${p.tool}` : p.label;
    h += `<div class="pl"><div class="ph"><span class="sw ${out ? "ring" : ""}" style="background:var(${p.c});border-color:var(${p.c})"></span>${escH(title)}</div><pre>${escH(JSON.stringify(p.payload, null, 2))}</pre></div>`;
  });
  $("#now").innerHTML = h;
}
const AV_U = `<svg viewBox="-20 -20 40 40"><circle cx="0" cy="-5" r="6" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M-11,13 C-11,3 11,3 11,13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`;
const AV_A = `<svg viewBox="-20 -20 40 40"><path d="M0,-13 C1.5,-4 4,-1.5 13,0 C4,1.5 1.5,4 0,13 C-1.5,4 -4,1.5 -13,0 C-4,-1.5 -1.5,-4 0,-13Z" fill="currentColor"/></svg>`;
function renderChat() {
  const s = S(), st = s.steps[idx];
  let h = `<div class="amsg"><div class="av u">${AV_U}</div><div><div class="who">User</div><div class="bub"><p>${escH(s.question)}</p></div></div></div>`;
  if (idx >= 1) {
    const calls = s.steps.slice(0, idx + 1).reduce((n, x) => n + (x.packets || []).filter(p => p.dir === "call").length, 0);
    h += `<div class="amsg"><div class="av a">${AV_A}</div><div><div class="who">LLM</div><div class="bub" id="ans">`;
    if (!st.answer) {
      const label = st.think ? (st.merge ? "Combining results" : "Choosing tools") : calls ? `Used ${calls} tool call${calls > 1 ? "s" : ""} so far` : "Reading the tool list";
      h += `<div class="status"><span class="dots"><span></span><span></span><span></span></span>${label}</div>`;
    }
    h += `</div></div></div>`;
  }
  $("#chat").innerHTML = h;
}
function startTyping(token) {
  const s = S(), box = $("#ans");
  const total = s.answer.reduce((n, a) => n + a.lead.length + a.text.length, 0);
  typed = {done: false};
  const cps = reduce ? 1e9 : 95 * speed, t0 = performance.now();
  (function draw() {
    if (token !== stepToken) return;
    let n = Math.min(total, Math.floor((performance.now() - t0) / 1000 * cps)), rem = n, html = "";
    s.answer.forEach(a => {
      if (rem <= 0) return;
      const lead = a.lead.slice(0, Math.min(rem, a.lead.length)); rem -= lead.length;
      const txt = rem > 0 ? a.text.slice(0, Math.min(rem, a.text.length)) : ""; rem -= txt.length;
      html += `<p><span class="adot" style="background:var(${a.c})"></span><b>${escH(lead)}</b>${escH(txt)}${rem <= 0 && n < total ? '<span class="caret"></span>' : ""}</p>`;
    });
    if (n >= total) html += `<div class="chips">${s.sources.map(([c, t], i) => `<span style="color:var(${c});border-color:var(${c});animation-delay:${i * .12}s">${escH(t)}</span>`).join("")}</div>`;
    box.innerHTML = html;
    if (n < total) requestAnimationFrame(draw); else typed.done = true;
  })();
}
function renderSteps() {
  const box = $("#steps");
  box.innerHTML = S().steps.map((s, i) => `<button class="${i === idx ? "cur" : i < idx ? "done" : ""}" aria-label="Step ${i + 1}: ${escH(s.t)}" title="${escH(s.t)}">${i + 1}</button>`).join("");
  box.querySelectorAll("button").forEach((b, i) => b.onclick = () => { playing = false; updatePlay(); runStep(i); });
}
function renderLegend() {
  const used = new Set(["--red"]);
  S().picked.forEach(id => used.add(toolOf(id).c));
  $("#alegend").innerHTML = `<span><i class="ring"></i>Request going out</span><span><i class="full"></i>Data coming back</span>` +
    [...used].map(c => `<span><i style="background:var(${c})"></i>${COLNAME[c]}</span>`).join("");
}

/* ---------- controls ---------- */
function updatePlay() { $("#play").textContent = playing ? "Pause" : (idx === S().steps.length - 1 ? "Replay" : "Play"); }
$("#play").onclick = () => {
  if (playing) { playing = false; updatePlay(); return; }
  playing = true; updatePlay();
  if (idx === S().steps.length - 1) runStep(0);
  else if (performance.now() - stepStart >= stepDur) runStep(idx + 1);
};
$("#next").onclick = () => { playing = false; updatePlay(); runStep(Math.min(idx + 1, S().steps.length - 1)); };
$("#prev").onclick = () => { playing = false; updatePlay(); runStep(Math.max(idx - 1, 0)); };
$("#restart").onclick = () => { playing = true; updatePlay(); runStep(0); };
document.querySelectorAll("[data-sc]").forEach(b => b.onclick = () => {
  document.querySelectorAll("[data-sc]").forEach(x => x.setAttribute("aria-pressed", x === b));
  sc = b.dataset.sc; typed = null; renderLegend(); buildWF(); playing = true; updatePlay(); runStep(0);
});
document.querySelectorAll("[data-sp]").forEach(b => b.onclick = () => {
  document.querySelectorAll("[data-sp]").forEach(x => x.setAttribute("aria-pressed", x === b));
  speed = +b.dataset.sp;
});
document.addEventListener("keydown", e => {
  if (e.target.closest("button, a, input")) return;
  if (e.code === "Space") { e.preventDefault(); $("#play").click(); }
  if (e.code === "ArrowRight") $("#next").click();
  if (e.code === "ArrowLeft") $("#prev").click();
});

/* ---------- live data: registered tools and benchmark sectors ---------- */
const SECTORS = [
  [1, "Premiums", ["swiss_health_insurance_premiums"], "No premium tool is registered."],
  [2, "Taxes", ["compute_swiss_tax"], "No tax tool is registered (VAT, household levy)."],
  [3, "Law", ["search_knowledge"], "No knowledge-base search is registered."],
  [4, "Waste", [], "No tool returns a waste pickup date."],
  [5, "Residence", [], "No arrival-registration tool is registered."],
  [6, "Migration", ["swiss_residence_permit_guidance"], "No permit tool is registered."],
  [7, "Social insurance", [], "No pension (AHV) tool is registered."],
  [8, "Work", [], "No unemployment (RAV) tool is registered."],
  [9, "Schools", ["swiss_school_holidays"], "No school-holiday tool is registered."],
  [10, "Public transport", [], "No timetable tool is registered."],
  [11, "Licences", ["get_driving_licence_exchange_info"], "No licence tool is registered."],
  [12, "Housing", ["swiss_housing_info", "swiss_reference_interest_rate"], "No housing tool is registered."],
  [13, "Voting", ["swiss_federal_political_rights"], "No voting tool is registered."],
  [14, "Companies", ["company_info"], "No company tool is registered."],
  [15, "Customs", ["swiss_import_parcel_vat"], "No customs tool is registered."],
  [16, "Statistics", ["bfs_population", "opendata_search_datasets"], "No statistics tool is registered."]
];
function renderSectors(run) {
  const scores = {};
  ((run && run.by_topic) || []).forEach(t => {
    const n = parseInt(t.name); if (!n) return;
    const s = scores[n] || (scores[n] = {passed: 0, total: 0});
    s.passed += t.passed; s.total += t.total;
  });
  const known = new Set(toolNames);
  let gaps = 0;
  $("#sg").innerHTML = SECTORS.map(([n, name, tools, gap]) => {
    const have = tools.filter(t => !toolNames.length || known.has(t));
    if (!have.length) gaps++;
    const sc = scores[n];
    const score = sc ? `<span class="score ${sc.passed === sc.total ? "ok" : sc.passed / sc.total >= .7 ? "mid" : "low"}">${sc.passed}/${sc.total} passed</span>`
      : `<span class="score none">Not in latest run</span>`;
    return `<article class="${have.length ? "has" : "gap"}"><span class="n">${String(n).padStart(2, "0")}</span><span class="name">${escH(name)}</span>` +
      `<span class="path">${have.length ? have.map(escH).join(" · ") : escH(gap)}</span>${score}</article>`;
  }).join("");
  $("#sectorsub").textContent = `${16 - gaps} of 16 areas have a registered Smurf tool (blue); ${gaps} still have none (red). ` +
    (run ? `Scores are from the latest benchmark run, ${run.run}.` : "No benchmark run found, so no scores yet.");
}
Promise.all([
  fetch("/api/tools").then(r => r.json()).catch(() => null),
  fetch("/api/benchmark").then(r => r.json()).catch(() => null)
]).then(([t, b]) => {
  if (t && t.tools) {
    toolCount = t.tools.length; toolNames = t.tools.map(x => x.name);
    const byName = Object.fromEntries(t.tools.map(x => [x.name, x]));
    TOOLS.forEach(x => { const live = byName[x.name]; if (live) { x.d = live.description; x.a = live.args; toolEls[x.id].setAttribute("aria-label", `${x.name}: ${x.d}`); } });
    toolCap.textContent = `6 of the server's ${toolCount} tools`;
    discover.label = `${toolCount} tools`;
    discover.payload = {tools: toolNames.slice(0, 7).concat(toolCount > 7 ? [`…${toolCount - 7} more`] : [])};
  } else {
    discover.label = "tool list";
  }
  renderSectors(b && b.run);
  if (idx === 1) renderNow();
});

renderLegend(); buildWF(); updatePlay();
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(() => runStep(0));
})();
