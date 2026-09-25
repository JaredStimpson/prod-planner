const $ = (selector) => document.querySelector(selector);
const svgNS = "http://www.w3.org/2000/svg";
const state = {
  items: [], stations: [], profile: null, selected: new Map(), capacities: new Map(), plan: null,
  graph: { nodes: new Map(), edges: [], scale: 1, tx: 30, ty: 30, dragging: null, panning: null },
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

function duration(seconds) {
  const value = Number(seconds || 0);
  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m`;
  return `${value}s`;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { element.hidden = true; }, 3200);
}

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { message = (await response.json()).detail || message; } catch (_) { /* response was not JSON */ }
    throw new Error(message);
  }
  return response;
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach(button => button.classList.toggle("active", button.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.toggle("active", panel.id === `tab-${name}`));
}

async function loadCatalog() {
  const [items, stations, profiles] = await Promise.all([
    api("/v1/items?producible=true").then(r => r.json()),
    api("/v1/stations").then(r => r.json()),
    api("/v1/capacity-profiles").then(r => r.json()),
  ]);
  state.items = items;
  state.stations = stations;
  state.profile = profiles[0] || null;
  state.capacities = new Map(stations.map(station => [station.station_key, state.profile?.capacities?.[station.station_key] || 1]));
  state.selected.clear();
  renderStations();
  renderSelected();
  $("#source-card").innerHTML = `<span class="source-icon">DB</span><div><strong>${items.length} producible items ready</strong><small>${stations.length} stations · ${escapeHtml(state.profile?.name || "default capacity")}</small></div>`;
  $("#catalog-title").textContent = "Build a clear production path";
  $("#status-dot").classList.add("ready");
  $("#status-text").textContent = "Catalog ready";
}

function renderStations() {
  const needle = $("#station-search").value.trim().toLowerCase();
  const stations = state.stations.filter(row => !needle || row.name.toLowerCase().includes(needle));
  $("#station-list").innerHTML = stations.map(station => `
    <div class="station-row" data-station="${escapeHtml(station.station_key)}">
      <div><strong>${escapeHtml(station.name)}</strong><small>${escapeHtml((station.station_type || "station").replaceAll("_", " "))}</small></div>
      <div class="stepper"><button data-delta="-1">−</button><input type="number" min="1" value="${state.capacities.get(station.station_key) || 1}"><button data-delta="1">+</button></div>
    </div>`).join("");
  document.querySelectorAll(".station-row").forEach(row => {
    const key = row.dataset.station;
    const input = row.querySelector("input");
    const setValue = value => {
      const valid = Math.max(1, Number.parseInt(value, 10) || 1);
      input.value = valid;
      state.capacities.set(key, valid);
    };
    input.addEventListener("change", () => setValue(input.value));
    row.querySelectorAll("button").forEach(button => button.addEventListener("click", () => setValue(Number(input.value) + Number(button.dataset.delta))));
  });
}

function searchItems() {
  const needle = $("#item-search").value.trim().toLowerCase();
  const results = needle ? state.items.filter(item => item.name.toLowerCase().includes(needle) || item.item_key.toLowerCase().includes(needle)).slice(0, 12) : [];
  const element = $("#search-results");
  element.classList.toggle("visible", results.length > 0);
  element.innerHTML = results.map(item => `
    <button class="result-row" data-item="${escapeHtml(item.item_key)}"><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.category_name || "Produced item")} · Lv ${item.unlock_level ?? "—"}</small></span><b>+</b></button>`).join("");
  element.querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
    const item = state.items.find(candidate => candidate.item_key === button.dataset.item);
    state.selected.set(item.item_key, { item, quantity: 1, priority: state.selected.size + 1 });
    $("#item-search").value = "";
    searchItems();
    renderSelected();
  }));
}

function renderSelected() {
  const rows = [...state.selected.values()];
  $("#output-count").textContent = rows.length;
  $("#calculate-button").disabled = rows.length === 0 || !state.profile;
  $("#selected-list").innerHTML = rows.length ? rows.map(({item, quantity}) => `
    <div class="selected-row" data-item="${escapeHtml(item.item_key)}">
      <div><strong>${escapeHtml(item.name)}</strong><small>Qty · priority follows list order</small></div>
      <input type="number" min="0.01" step="0.01" value="${quantity}">
      <button class="remove" aria-label="Remove ${escapeHtml(item.name)}">×</button>
    </div>`).join("") : `<p style="color:var(--muted);font-size:11px;margin:8px 0">No outputs selected yet.</p>`;
  document.querySelectorAll(".selected-row").forEach((row, index) => {
    const selected = state.selected.get(row.dataset.item);
    selected.priority = index + 1;
    row.querySelector("input").addEventListener("change", event => { selected.quantity = Math.max(.01, Number(event.target.value) || 1); });
    row.querySelector(".remove").addEventListener("click", () => { state.selected.delete(row.dataset.item); renderSelected(); });
  });
}

async function calculate() {
  const button = $("#calculate-button");
  button.disabled = true;
  button.firstChild.textContent = "Calculating… ";
  try {
    const defaults = state.profile?.capacities || {};
    const overrides = Object.fromEntries([...state.capacities].filter(([key, count]) => count !== (defaults[key] || 1)));
    const request = {
      outputs: [...state.selected.values()].map(({item, quantity, priority}) => ({item_key: item.item_key, quantity: String(quantity), priority})),
      capacity_profile: state.profile.profile_key,
      station_overrides: overrides,
    };
    state.plan = await api("/v1/plans/compute", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(request)}).then(r => r.json());
    renderPlan(state.plan);
    toast("Production plan calculated");
  } catch (error) { toast(error.message); }
  finally {
    button.firstChild.textContent = "Calculate production plan ";
    button.disabled = state.selected.size === 0;
  }
}

function renderPlan(plan) {
  state.plan = plan;
  $("#empty-state").hidden = true;
  $("#empty-state").style.display = "none";
  $("#save-button").disabled = false;
  $("#status-text").textContent = `Plan ready · ${duration(plan.overall_completion_seconds)}`;
  renderGraph(plan);
  renderResults(plan);
}

function renderResults(plan) {
  const element = $("#plan-results");
  element.hidden = false;
  const outputs = plan.outputs.map(row => `<tr><td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.quantity)} · ${duration(row.completion_seconds)}</td></tr>`).join("");
  const materials = plan.bom.slice(0, 12).map(row => `<tr><td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.quantity)} ${escapeHtml(row.unit)}</td></tr>`).join("");
  const stations = plan.station_summary.filter(row => row.job_count).sort((a,b) => b.busy_seconds - a.busy_seconds).slice(0, 10)
    .map(row => `<tr><td>${escapeHtml(row.station_name)}</td><td>${row.station_count} × · ${Math.round(Number(row.utilization) * 100)}%</td></tr>`).join("");
  element.innerHTML = `
    <div class="metric-grid"><div class="metric"><small>Completion</small><strong>${duration(plan.overall_completion_seconds)}</strong></div><div class="metric"><small>Input cost</small><strong>${escapeHtml(plan.actual_input_cost ?? "—")}</strong></div><div class="metric"><small>Jobs</small><strong>${plan.jobs.length}</strong></div><div class="metric"><small>Raw inputs</small><strong>${plan.bom.length}</strong></div></div>
    <div class="result-section requested-outputs"><h3>Requested outputs</h3><table class="result-table">${outputs}</table></div>
    <div class="result-section"><h3>Raw materials${plan.bom.length > 12 ? " · first 12" : ""}</h3><table class="result-table">${materials || "<tr><td>None</td><td>—</td></tr>"}</table></div>
    <div class="result-section"><h3>Used stations</h3><table class="result-table">${stations}</table></div>
    ${(plan.warnings || []).map(warning => `<p class="warning">${escapeHtml(warning)}</p>`).join("")}`;
}

function svgElement(name, attrs = {}) {
  const element = document.createElementNS(svgNS, name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function renderGraph(plan) {
  const graph = state.graph;
  graph.nodes.clear(); graph.edges = [];
  const jobById = new Map(plan.jobs.map(job => [job.job_id, job]));
  const rawKeys = new Set(plan.bom.map(row => row.item_key));
  const stageCache = new Map();
  const stageOf = job => {
    if (stageCache.has(job.job_id)) return stageCache.get(job.job_id);
    const dependencyStages = job.dependencies.map(id => stageOf(jobById.get(id)));
    const hasRaw = Object.keys(job.ingredients || {}).some(key => rawKeys.has(key));
    const stage = dependencyStages.length ? Math.max(...dependencyStages) + 1 : hasRaw ? 1 : 0;
    stageCache.set(job.job_id, stage);
    return stage;
  };
  plan.bom.forEach(row => graph.nodes.set(`raw:${row.item_key}`, {id:`raw:${row.item_key}`, kind:"raw", stage:0, name:row.name, quantity:row.quantity, unit:row.unit, average_value:row.average_value, data:row}));
  const groupByJob = new Map();
  plan.jobs.forEach(job => {
    const stage = stageOf(job);
    const groupId = `group:${stage}:${job.item_key}`;
    if (!graph.nodes.has(groupId)) {
      graph.nodes.set(groupId, {id:groupId, kind:"job", stage, name:job.item_name, critical:false, jobs:[], data:job});
    }
    const node = graph.nodes.get(groupId);
    node.jobs.push(job);
    node.critical ||= Boolean(job.is_critical);
    groupByJob.set(job.job_id, groupId);
  });
  graph.nodes.forEach(node => {
    if (node.kind !== "job") return;
    node.count = node.jobs.length;
    node.criticalCount = node.jobs.filter(job => job.is_critical).length;
    node.startSeconds = Math.min(...node.jobs.map(job => Number(job.start_seconds || 0)));
    node.endSeconds = Math.max(...node.jobs.map(job => Number(job.end_seconds || 0)));
  });
  const edgeMap = new Map();
  const addEdge = (source, target, critical) => {
    if (!source || !target || source === target) return;
    const key = `${source}→${target}`;
    const existing = edgeMap.get(key);
    if (existing) {
      existing.critical ||= critical;
      existing.count += 1;
    } else {
      edgeMap.set(key, {source, target, critical, count:1});
    }
  };
  plan.jobs.forEach(job => {
    const target = groupByJob.get(job.job_id);
    job.dependencies.forEach(source => addEdge(groupByJob.get(source), target, Boolean(job.is_critical && jobById.get(source)?.is_critical)));
    Object.keys(job.ingredients || {}).filter(key => rawKeys.has(key)).forEach(key => addEdge(`raw:${key}`, target, Boolean(job.is_critical)));
  });
  graph.edges = [...edgeMap.values()];
  const stages = new Map();
  [...graph.nodes.values()].forEach(node => { if (!stages.has(node.stage)) stages.set(node.stage, []); stages.get(node.stage).push(node); });
  [...stages].sort((a,b) => a[0]-b[0]).forEach(([stage, nodes]) => {
    nodes.sort((a,b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    nodes.forEach((node, index) => { node.x = 54 + stage * 270; node.y = 62 + index * 108; });
  });
  drawGraph();
  requestAnimationFrame(fitGraph);
}

function drawGraph() {
  const graph = state.graph;
  const stageLayer = $("#stage-layer"), edgeLayer = $("#edge-layer"), nodeLayer = $("#node-layer");
  stageLayer.replaceChildren(); edgeLayer.replaceChildren(); nodeLayer.replaceChildren();
  const maxY = Math.max(440, ...[...graph.nodes.values()].map(node => node.y + 100));
  const stageNumbers = [...new Set([...graph.nodes.values()].map(node => node.stage))].sort((a,b) => a-b);
  stageNumbers.forEach(stage => {
    const x = 28 + stage * 270;
    stageLayer.append(svgElement("rect", {x, y:28, width:238, height:maxY, rx:12, class:"stage-band"}));
    const text = svgElement("text", {x:x+12, y:49, class:"stage-label"});
    text.textContent = stage === 0 ? "SOURCE" : `STAGE ${stage}`;
    stageLayer.append(text);
  });
  graph.edges.forEach(edge => {
    const path = svgElement("path", {class:`edge${edge.critical ? " critical" : ""}`, "data-source":edge.source, "data-target":edge.target});
    edgeLayer.append(path);
  });
  graph.nodes.forEach(node => {
    const group = svgElement("g", {class:`graph-node ${node.kind}${node.critical ? " critical" : ""}`, "data-id":node.id, transform:`translate(${node.x} ${node.y})`, tabindex:"0"});
    group.append(svgElement("rect", {x:0,y:0,width:210,height:78,rx:9,class:"node-card"}));
    group.append(svgElement("rect", {x:0,y:0,width:5,height:78,rx:3,class:"node-accent"}));
    const nodeLabel = node.kind === "job" && node.count > 1 ? `${node.name} ×${node.count}` : node.name;
    const title = svgElement("text", {x:16,y:22,class:"node-title"}); title.textContent = nodeLabel.length > 25 ? `${nodeLabel.slice(0,24)}…` : nodeLabel; group.append(title);
    const meta = svgElement("text", {x:16,y:42,class:"node-meta"});
    meta.textContent = node.kind === "raw" ? `Input · ${node.quantity} ${node.unit}` : node.count > 1 ? `${node.count} runs · ${node.data.station_name} · cost ${node.data.average_value ?? "—"}` : `${node.data.station_name} · unit cost ${node.data.average_value ?? "—"}`; group.append(meta);
    const time = svgElement("text", {x:16,y:61,class:"node-time"});
    time.textContent = node.kind === "raw" ? `Extended cost ${node.data.extended_cost ?? "—"}` : node.count > 1 ? `${duration(node.data.duration_seconds)} each · finish ${duration(node.endSeconds)}` : `${duration(node.data.duration_seconds)} · completes ${duration(node.data.end_seconds)}`; group.append(time);
    group.addEventListener("pointerdown", startNodeDrag);
    group.addEventListener("click", event => { event.stopPropagation(); showNodeDetails(node); });
    nodeLayer.append(group);
  });
  updateEdges();
  applyViewport();
}

function updateEdges() {
  document.querySelectorAll(".edge").forEach(path => {
    const source = state.graph.nodes.get(path.dataset.source), target = state.graph.nodes.get(path.dataset.target);
    if (!source || !target) return;
    const x1 = source.x + 210, y1 = source.y + 39, x2 = target.x, y2 = target.y + 39, bend = Math.max(40, (x2-x1) * .45);
    path.setAttribute("d", `M ${x1} ${y1} C ${x1+bend} ${y1}, ${x2-bend} ${y2}, ${x2} ${y2}`);
  });
}

function showNodeDetails(node) {
  const element = $("#node-details");
  const data = node.data;
  element.hidden = false;
  element.innerHTML = node.kind === "raw" ? `<h3>${escapeHtml(node.name)}</h3><dl><dt>Required</dt><dd>${escapeHtml(data.quantity)} ${escapeHtml(data.unit)}</dd><dt>Average cost</dt><dd>${escapeHtml(data.average_value ?? "—")}</dd><dt>Extended cost</dt><dd>${escapeHtml(data.extended_cost ?? "—")}</dd></dl>` : `<h3>${escapeHtml(node.name)}${node.count > 1 ? ` ×${node.count}` : ""}</h3><dl><dt>Runs</dt><dd>${node.count}</dd><dt>Station</dt><dd>${escapeHtml(data.station_name)}</dd><dt>Run time</dt><dd>${duration(data.duration_seconds)}</dd><dt>Mastered</dt><dd>${data.mastered_duration_seconds == null ? "—" : duration(data.mastered_duration_seconds)}</dd><dt>Unlock level</dt><dd>${data.unlock_level ?? "—"}</dd><dt>First start</dt><dd>${duration(node.startSeconds)}</dd><dt>Final completion</dt><dd>${duration(node.endSeconds)}</dd><dt>Batch output</dt><dd>${escapeHtml(data.output_quantity)}</dd><dt>Critical runs</dt><dd>${node.criticalCount}</dd></dl>`;
}

function canvasPoint(event) {
  const rect = $("#graph").getBoundingClientRect();
  return {x:(event.clientX-rect.left-state.graph.tx)/state.graph.scale, y:(event.clientY-rect.top-state.graph.ty)/state.graph.scale};
}

function startNodeDrag(event) {
  event.stopPropagation();
  const node = state.graph.nodes.get(event.currentTarget.dataset.id), point = canvasPoint(event);
  state.graph.dragging = {node, dx:point.x-node.x, dy:point.y-node.y, element:event.currentTarget};
  event.currentTarget.setPointerCapture(event.pointerId);
}

function applyViewport() { $("#viewport").setAttribute("transform", `translate(${state.graph.tx} ${state.graph.ty}) scale(${state.graph.scale})`); }

function fitGraph() {
  if (!state.graph.nodes.size) return;
  const rect = $("#graph").getBoundingClientRect();
  const minX = Math.min(...[...state.graph.nodes.values()].map(node => node.x)) - 30;
  const maxX = Math.max(...[...state.graph.nodes.values()].map(node => node.x + 210)) + 30;
  const minY = 25, maxY = Math.max(...[...state.graph.nodes.values()].map(node => node.y + 100));
  state.graph.scale = Math.min(.98, Math.max(.25, Math.min(rect.width/(maxX-minX), rect.height/(maxY-minY))));
  state.graph.tx = (rect.width-(maxX-minX)*state.graph.scale)/2-minX*state.graph.scale;
  state.graph.ty = (rect.height-(maxY-minY)*state.graph.scale)/2-minY*state.graph.scale;
  applyViewport();
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => setTab(button.dataset.tab)));
  $("#station-search").addEventListener("input", renderStations);
  $("#item-search").addEventListener("input", searchItems);
  $("#clear-button").addEventListener("click", () => { state.selected.clear(); renderSelected(); });
  $("#calculate-button").addEventListener("click", calculate);
  $("#fit-button").addEventListener("click", fitGraph);
  $("#load-db-button").addEventListener("click", () => $("#db-file").click());
  $("#load-json-button").addEventListener("click", () => $("#json-file").click());
  $("#convert-button").addEventListener("click", () => $("#xlsx-file").click());
  $("#save-button").addEventListener("click", savePlan);
  $("#db-file").addEventListener("change", event => uploadDatabase(event.target.files[0]));
  $("#json-file").addEventListener("change", event => loadPlanFile(event.target.files[0]));
  $("#xlsx-file").addEventListener("change", event => convertWorkbook(event.target.files[0]));
  const graph = $("#graph");
  graph.addEventListener("selectstart", event => event.preventDefault());
  graph.addEventListener("pointerdown", event => {
    if (event.target.closest(".graph-node")) return;
    event.preventDefault();
    state.graph.panning = {x:event.clientX, y:event.clientY, tx:state.graph.tx, ty:state.graph.ty};
    graph.classList.add("panning"); graph.setPointerCapture(event.pointerId);
    $("#node-details").hidden = true;
  });
  graph.addEventListener("pointermove", event => {
    if (state.graph.dragging) {
      const point = canvasPoint(event), drag = state.graph.dragging;
      drag.node.x = point.x-drag.dx; drag.node.y = point.y-drag.dy;
      drag.element.setAttribute("transform", `translate(${drag.node.x} ${drag.node.y})`); updateEdges();
    } else if (state.graph.panning) {
      state.graph.tx = state.graph.panning.tx + event.clientX-state.graph.panning.x;
      state.graph.ty = state.graph.panning.ty + event.clientY-state.graph.panning.y; applyViewport();
    }
  });
  const finishPointer = () => { state.graph.dragging = null; state.graph.panning = null; graph.classList.remove("panning"); };
  graph.addEventListener("pointerup", finishPointer); graph.addEventListener("pointercancel", finishPointer);
  graph.addEventListener("wheel", event => {
    event.preventDefault();
    const rect = graph.getBoundingClientRect(), px = event.clientX-rect.left, py = event.clientY-rect.top;
    const old = state.graph.scale, next = Math.min(2.5, Math.max(.2, old * Math.exp(-event.deltaY*.001)));
    state.graph.tx = px-(px-state.graph.tx)*(next/old); state.graph.ty = py-(py-state.graph.ty)*(next/old); state.graph.scale = next; applyViewport();
  }, {passive:false});
  document.addEventListener("keydown", event => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable;
    if (!typing && !event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === "f") {
      event.preventDefault();
      fitGraph();
    }
  });
}

async function uploadDatabase(file) {
  if (!file) return;
  const form = new FormData(); form.append("file", file);
  try { await api("/v1/catalog/load", {method:"POST", body:form}); await loadCatalog(); setTab("outputs"); toast(`${file.name} loaded`); }
  catch (error) { toast(error.message); }
}

async function convertWorkbook(file) {
  if (!file) return;
  const form = new FormData(); form.append("file", file);
  try {
    const blob = await api("/v1/tools/databases/convert", {method:"POST", body:form}).then(r => r.blob());
    const databaseFile = new File([blob], `${file.name.replace(/\.xlsx$/i, "")}.sqlite`, {type:"application/vnd.sqlite3"});
    await uploadDatabase(databaseFile);
    const url = URL.createObjectURL(blob), link = document.createElement("a"); link.href = url; link.download = databaseFile.name; link.click(); URL.revokeObjectURL(url);
    toast("Workbook converted, loaded, and downloaded");
  } catch (error) { toast(error.message); }
}

async function loadPlanFile(file) {
  if (!file) return;
  try { const plan = JSON.parse(await file.text()); if (!Array.isArray(plan.jobs) || !Array.isArray(plan.outputs)) throw new Error("This is not a planner plan file"); renderPlan(plan); toast(`${file.name} opened`); }
  catch (error) { toast(error.message); }
}

function savePlan() {
  if (!state.plan) return;
  const blob = new Blob([JSON.stringify(state.plan, null, 2) + "\n"], {type:"application/json"});
  const url = URL.createObjectURL(blob), link = document.createElement("a"); link.href = url; link.download = `production-plan-${new Date().toISOString().slice(0,10)}.json`; link.click(); URL.revokeObjectURL(url);
}

async function boot() {
  bindEvents(); renderSelected();
  try {
    const health = await api("/health").then(r => r.json());
    if (health.mode === "database") { await loadCatalog(); setTab("outputs"); }
    else if (health.mode === "viewer") { renderPlan(await api("/v1/viewer/plan").then(r => r.json())); }
    else { $("#status-text").textContent = "Load a catalog"; }
  } catch (error) { $("#status-text").textContent = "Connection error"; toast(error.message); }
}

boot();
