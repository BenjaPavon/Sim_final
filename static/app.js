const DEFAULT_CONFIG = {
  horizon: 480,
  capacity: 5,
  arrival_interval_p1: 1,
  arrival_batch_p1: 1,
  arrival_interval_p2: 5,
  arrival_batch_p2: 3,
  loaded_trip_time: 5,
  empty_trip_time: 3,
  patience: 12,
  fare_per_car: 2,
  cost_per_trip: 6,
  loss_per_abandoned_car: 1,
};

const ROW_COLUMNS = [
  { group: "event", key: "row", label: "Fila", type: "integer", sticky: 0 },
  { group: "event", key: "event", label: "Evento", type: "event", sticky: 1 },
  { group: "event", key: "time", label: "Reloj (min)", type: "time", sticky: 2 },
  { group: "arrivals", key: "arrivals_now_p1", label: "Llegan P1", type: "integer" },
  { group: "arrivals", key: "next_arrival_p1", label: "Próx. llegada P1", type: "time" },
  { group: "arrivals", key: "arrivals_now_p2", label: "Llegan P2", type: "integer" },
  { group: "arrivals", key: "next_arrival_p2", label: "Próx. llegada P2", type: "time" },
  { group: "wagon", key: "wagon_state", label: "Estado", type: "state" },
  { group: "wagon", key: "wagon_location", label: "Posición", type: "text" },
  { group: "wagon", key: "wagon_route", label: "Recorrido", type: "text" },
  { group: "wagon", key: "trip_started_id", label: "Inicia viaje", type: "integer" },
  { group: "wagon", key: "trip_finished_id", label: "Finaliza viaje", type: "integer" },
  { group: "wagon", key: "loaded_now", label: "Suben", type: "integer" },
  { group: "wagon", key: "loaded_ids", label: "Autos que suben", type: "list" },
  { group: "wagon", key: "delivered_now", label: "Entregados", type: "integer" },
  { group: "wagon", key: "wagon_load_count", label: "Carga actual", type: "integer" },
  { group: "wagon", key: "trip_departure", label: "Hora salida", type: "time" },
  { group: "wagon", key: "next_wagon_arrival", label: "Fin traslado", type: "time" },
  { group: "queue1", key: "queue_p1_count", label: "Cola", type: "integer" },
  { group: "queue1", key: "queue_p1", label: "Autos (espera)", type: "queue" },
  { group: "queue1", key: "oldest_wait_p1", label: "Mayor espera", type: "time" },
  { group: "queue1", key: "next_abandon_p1", label: "Próx. abandono", type: "time" },
  { group: "queue1", key: "abandoned_now_p1", label: "Abandonan", type: "integer" },
  { group: "queue2", key: "queue_p2_count", label: "Cola", type: "integer" },
  { group: "queue2", key: "queue_p2", label: "Autos (espera)", type: "queue" },
  { group: "queue2", key: "oldest_wait_p2", label: "Mayor espera", type: "time" },
  { group: "queue2", key: "next_abandon_p2", label: "Próx. abandono", type: "time" },
  { group: "queue2", key: "abandoned_now_p2", label: "Abandonan", type: "integer" },
  { group: "stats", key: "arrived_p1", label: "Llegaron P1", type: "integer" },
  { group: "stats", key: "arrived_p2", label: "Llegaron P2", type: "integer" },
  { group: "stats", key: "boarded_p1", label: "Subieron P1", type: "integer" },
  { group: "stats", key: "boarded_p2", label: "Subieron P2", type: "integer" },
  { group: "stats", key: "delivered_total", label: "Entregados", type: "integer" },
  { group: "stats", key: "lost_p1", label: "Perdidos P1", type: "integer" },
  { group: "stats", key: "lost_p2", label: "Perdidos P2", type: "integer" },
  { group: "stats", key: "trips_total", label: "Viajes", type: "integer" },
  { group: "stats", key: "trips_empty", label: "Viajes vacíos", type: "integer" },
  { group: "stats", key: "acc_wait_served", label: "AC espera atendidos", type: "number" },
  { group: "stats", key: "acc_wait_lost", label: "AC espera perdidos", type: "number" },
  { group: "stats", key: "avg_queue", label: "Cola prom.", type: "number" },
  { group: "stats", key: "wagon_utilization", label: "Utilización", type: "percent" },
  { group: "money", key: "revenue", label: "Ingresos", type: "money" },
  { group: "money", key: "operating_cost", label: "Costo viajes", type: "money" },
  { group: "money", key: "loss_cost", label: "Pérdida abandonos", type: "money" },
  { group: "money", key: "net_result", label: "Resultado neto", type: "money" },
];

const CAR_COLUMNS = [
  { group: "event", key: "id", label: "Auto", type: "text" },
  { group: "event", key: "stop", label: "Parada", type: "stop" },
  { group: "arrivals", key: "arrival_time", label: "Hora llegada", type: "time" },
  { group: "arrivals", key: "deadline", label: "Limite espera", type: "time" },
  { group: "queue1", key: "state", label: "Estado final", type: "state" },
  { group: "queue1", key: "current_wait", label: "Tiempo espera", type: "time" },
  { group: "wagon", key: "board_time", label: "Hora de subida", type: "time" },
  { group: "wagon", key: "trip_id", label: "Traslado", type: "integer" },
  { group: "wagon", key: "delivered_time", label: "Hora entrega", type: "time" },
  { group: "wagon", key: "system_time", label: "Tiempo sistema", type: "time" },
  { group: "queue2", key: "lost_time", label: "Hora abandono", type: "time" },
];

const TRIP_COLUMNS = [
  { group: "event", key: "id", label: "Traslado", type: "integer" },
  { group: "wagon", key: "origin", label: "Origen", type: "stop" },
  { group: "wagon", key: "destination", label: "Destino", type: "stop" },
  { group: "wagon", key: "departure_time", label: "Salida", type: "time" },
  { group: "wagon", key: "arrival_time", label: "Llegada", type: "time" },
  { group: "wagon", key: "duration", label: "Duración", type: "time" },
  { group: "wagon", key: "kind", label: "Tipo", type: "state" },
  { group: "wagon", key: "load_count", label: "Carga", type: "integer" },
  { group: "wagon", key: "car_ids", label: "Autos", type: "list" },
  { group: "stats", key: "completed", label: "Finalizado", type: "boolean" },
  { group: "money", key: "revenue", label: "Ingreso", type: "money" },
  { group: "money", key: "cost", label: "Costo", type: "money" },
];

const GROUP_LABELS = {
  event: "Evento y reloj",
  arrivals: "Llegadas / calendario",
  wagon: "Vagón y traslados",
  queue1: "Cola · Parada 1",
  queue2: "Cola · Parada 2",
  stats: "Acumuladores",
  money: "Resultado económico",
};

const moneyFormat = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", minimumFractionDigits: 2 });
const numberFormat = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const integerFormat = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

const state = {
  result: null,
  policy: "A",
  view: "rows",
  page: 1,
  pageSize: 100,
};

const elements = {
  form: document.querySelector("#configForm"),
  status: document.querySelector("#statusBadge"),
  comparison: document.querySelector("#comparisonGrid"),
  recommendation: document.querySelector("#recommendation"),
  metrics: document.querySelector("#metricCards"),
  table: document.querySelector("#dataTable"),
  rowCount: document.querySelector("#rowCount"),
  pageLabel: document.querySelector("#pageLabel"),
  previous: document.querySelector("#previousPage"),
  next: document.querySelector("#nextPage"),
  detail: document.querySelector("#rowDetail"),
  notice: document.querySelector("#tableNotice"),
  timeFrom: document.querySelector("#timeFrom"),
  timeTo: document.querySelector("#timeTo"),
  eventFilter: document.querySelector("#eventFilter"),
  eventFilterWrap: document.querySelector("#eventFilterWrap"),
  stateFilter: document.querySelector("#stateFilter"),
  stateFilterWrap: document.querySelector("#stateFilterWrap"),
  toast: document.querySelector("#toast"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function classForState(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("perdido")) return "lost";
  if (text.includes("viaje") || text.includes("carga")) return "transit";
  return "";
}

function formatValue(value, type = "text", row = {}) {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "money") return moneyFormat.format(Number(value));
  if (type === "percent") return `${numberFormat.format(Number(value) * 100)} %`;
  if (type === "time" || type === "number") return numberFormat.format(Number(value));
  if (type === "integer") return integerFormat.format(Number(value));
  if (type === "boolean") return value ? "Si" : "No";
  if (type === "stop") return `P${value}`;
  if (type === "list") return Array.isArray(value) && value.length ? value.join(", ") : "—";
  if (type === "queue") {
    if (!Array.isArray(value) || !value.length) return "—";
    return value.map(item => `${item.id} (${numberFormat.format(item.wait)})`).join(", ");
  }
  if (type === "event") {
    return `<span class="event-pill ${escapeHtml(row.event_type || "")}">${escapeHtml(value)}</span>`;
  }
  if (type === "state") {
    return `<span class="state-chip ${classForState(value)}">${escapeHtml(value)}</span>`;
  }
  return escapeHtml(value);
}

function readConfig() {
  return Object.fromEntries(
    [...elements.form.elements]
      .filter(input => input.name)
      .map(input => [input.name, Number(input.value)])
  );
}

function setConfig(config) {
  for (const [key, value] of Object.entries(config)) {
    const input = elements.form.elements.namedItem(key);
    if (input) input.value = value;
  }
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.className = `toast show${error ? " error" : ""}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.className = "toast", 2800);
}

function setLoading(loading) {
  const submit = elements.form.querySelector("button[type=submit]");
  submit.disabled = loading;
  submit.innerHTML = loading ? "Calculando eventos..." : "<span>▶</span> Simular ambas políticas";
  elements.status.textContent = loading ? "Simulando..." : "Modelo listo";
}

async function runSimulation() {
  setLoading(true);
  elements.notice.classList.add("visible");
  elements.notice.textContent = "Generando las dos trazas de eventos...";
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: readConfig() }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Error de simulación");
    state.result = payload;
    state.page = 1;
    elements.timeFrom.value = 0;
    elements.timeTo.value = payload.config.horizon;
    document.querySelector("#assumptionList").innerHTML = payload.assumptions.map(item => `<li>${escapeHtml(item)}</li>`).join("");
    renderAll();
    showToast("Simulación completada");
  } catch (error) {
    elements.notice.textContent = error.message;
    showToast(error.message, true);
  } finally {
    setLoading(false);
  }
}

function renderComparison() {
  const summaries = {
    A: state.result.policies.A.summary,
    B: state.result.policies.B.summary,
  };
  const metrics = [
    ["Resultado neto", "net_result", "money", "high"],
    ["Autos entregados", "delivered_total", "integer", "high"],
    ["Autos perdidos", "lost_total", "integer", "low"],
    ["Espera prom. atendidos", "avg_wait_boarded", "time", "low"],
    ["Cola promedio total", "avg_queue_total", "number", "low"],
    ["Traslados totales", "trips_total", "integer", "none"],
    ["Traslados vacíos", "trips_empty", "integer", "low"],
    ["Costo de traslados", "operating_cost", "money", "low"],
  ];
  let html = `<div class="head">Indicador</div><div class="head">Política A</div><div class="head">Política B</div>`;
  for (const [label, key, type, direction] of metrics) {
    const a = summaries.A[key];
    const b = summaries.B[key];
    const bestA = direction === "high" ? a > b : direction === "low" ? a < b : false;
    const bestB = direction === "high" ? b > a : direction === "low" ? b < a : false;
    html += `<div class="metric-name">${label}</div>`;
    html += `<div class="${bestA ? "best " : ""}${type === "money" ? "money" : ""}">${formatValue(a, type)}</div>`;
    html += `<div class="${bestB ? "best " : ""}${type === "money" ? "money" : ""}">${formatValue(b, type)}</div>`;
  }
  elements.comparison.classList.remove("skeleton-block");
  elements.comparison.innerHTML = html;
  const recommended = state.result.recommended_policy;
  const difference = Math.abs(summaries.A.net_result - summaries.B.net_result);
  elements.recommendation.textContent = `Conviene la política ${recommended} · ventaja ${moneyFormat.format(difference)}`;
}

function renderMetrics() {
  const summary = state.result.policies[state.policy].summary;
  const metrics = [
    ["Resultado neto", summary.net_result, "money", "accent"],
    ["Autos entregados", summary.delivered_total, "integer", ""],
    ["Autos perdidos", summary.lost_total, "integer", summary.lost_total ? "negative" : ""],
    ["Espera prom. atendidos", summary.avg_wait_boarded, "time", ""],
    ["Viajes (vacíos)", `${summary.trips_total} (${summary.trips_empty})`, "text", ""],
    ["Utilización del vagón", summary.wagon_utilization, "percent", ""],
  ];
  elements.metrics.innerHTML = metrics.map(([label, value, type, cls]) =>
    `<div class="metric ${cls}"><span>${label}</span><b>${formatValue(value, type)}</b></div>`
  ).join("");
}

function columnsForView() {
  if (state.view === "cars") return CAR_COLUMNS;
  if (state.view === "trips") return TRIP_COLUMNS;
  return ROW_COLUMNS;
}

function itemsForView() {
  const policy = state.result.policies[state.policy];
  if (state.view === "cars") return policy.cars;
  if (state.view === "trips") return policy.trips;
  return policy.rows;
}

function timeForItem(item) {
  if (state.view === "cars") return item.arrival_time;
  if (state.view === "trips") return item.departure_time;
  return item.time;
}

function filteredItems() {
  const from = Number(elements.timeFrom.value || 0);
  const to = Number(elements.timeTo.value || state.result.config.horizon);
  return itemsForView().filter(item => {
    const time = timeForItem(item);
    if (time < from || time > to) return false;
    if (state.view === "rows" && elements.eventFilter.value !== "all" && item.event_type !== elements.eventFilter.value) return false;
    if (state.view === "cars" && elements.stateFilter.value !== "all" && item.state !== elements.stateFilter.value) return false;
    return true;
  });
}

function groupHeaders(columns) {
  const groups = [];
  for (const column of columns) {
    const previous = groups.at(-1);
    if (previous && previous.name === column.group) previous.count += 1;
    else groups.push({ name: column.group, count: 1 });
  }
  return groups.map(group => `<th colspan="${group.count}" class="group-${group.name}">${GROUP_LABELS[group.name]}</th>`).join("");
}

function renderTable() {
  if (!state.result) return;
  const columns = columnsForView();
  const items = filteredItems();
  const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page - 1) * state.pageSize;
  const pageItems = items.slice(start, start + state.pageSize);

  const labels = columns.map(column => {
    const sticky = column.sticky !== undefined ? ` sticky-col sticky-${column.sticky}` : "";
    const text = ["event", "text", "queue", "state", "list"].includes(column.type) ? " text" : "";
    return `<th class="${sticky}${text}">${escapeHtml(column.label)}</th>`;
  }).join("");
  const body = pageItems.map((item, localIndex) => {
    const cells = columns.map(column => {
      const sticky = column.sticky !== undefined ? ` sticky-col sticky-${column.sticky}` : "";
      const text = ["event", "text", "queue", "state", "list"].includes(column.type) ? " text" : "";
      const queue = column.type === "queue" ? " queue-cell" : "";
      const raw = item[column.key];
      const title = column.type === "queue" || column.type === "list" ? ` title="${escapeHtml(formatValue(raw, column.type, item))}"` : "";
      return `<td class="${sticky}${text}${queue}"${title}>${formatValue(raw, column.type, item)}</td>`;
    }).join("");
    return `<tr data-index="${start + localIndex}" class="event-${escapeHtml(item.event_type || "")}">${cells}</tr>`;
  }).join("");

  elements.table.innerHTML = `<thead><tr>${groupHeaders(columns)}</tr><tr>${labels}</tr></thead><tbody>${body}</tbody>`;
  elements.rowCount.textContent = `${integerFormat.format(items.length)} filas`;
  elements.pageLabel.textContent = `Página ${state.page} de ${totalPages}`;
  elements.previous.disabled = state.page <= 1;
  elements.next.disabled = state.page >= totalPages;
  elements.notice.classList.toggle("visible", items.length === 0);
  if (!items.length) elements.notice.textContent = "No hay filas para los filtros seleccionados.";
  elements.detail.classList.add("hidden");

  elements.table.querySelectorAll("tbody tr").forEach(row => {
    row.addEventListener("click", () => showDetail(items[Number(row.dataset.index)]));
  });
}

function showDetail(item) {
  if (!item) return;
  const pairs = state.view === "rows" ? [
    ["Evento", item.event], ["Detalle", item.details], ["Reloj", formatValue(item.time, "time")],
    ["Estado del vagón", `${item.wagon_state} · ${item.wagon_location}`],
    ["Carga del vagón", item.wagon_load_ids?.join(", ") || "Vacío"],
    ["Cola P1", formatValue(item.queue_p1, "queue")], ["Cola P2", formatValue(item.queue_p2, "queue")],
    ["Próximos eventos", `P1 ${formatValue(item.next_arrival_p1, "time")} · P2 ${formatValue(item.next_arrival_p2, "time")} · Vagón ${formatValue(item.next_wagon_arrival, "time")}`],
    ["Acumulados", `Entregados ${item.delivered_total} · Perdidos ${item.lost_p1 + item.lost_p2} · Viajes ${item.trips_total}`],
    ["Resultado neto", formatValue(item.net_result, "money")],
  ] : Object.entries(item).map(([key, value]) => [key.replaceAll("_", " "), Array.isArray(value) ? value.join(", ") : String(value ?? "—")]);
  elements.detail.innerHTML = `<h3>Detalle de la fila</h3><div class="detail-grid">${pairs.map(([label, value]) => `<div class="detail-item"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join("")}</div>`;
  elements.detail.classList.remove("hidden");
  elements.detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderAll() {
  renderComparison();
  renderMetrics();
  renderTable();
}

elements.form.addEventListener("submit", event => { event.preventDefault(); runSimulation(); });
document.querySelector("#resetConfig").addEventListener("click", () => { setConfig(DEFAULT_CONFIG); showToast("Parametros restaurados"); });
document.querySelectorAll(".policy-tab").forEach(button => button.addEventListener("click", () => {
  state.policy = button.dataset.policy;
  state.page = 1;
  document.querySelectorAll(".policy-tab").forEach(tab => tab.classList.toggle("active", tab === button));
  renderMetrics(); renderTable();
}));
document.querySelectorAll(".view-tab").forEach(button => button.addEventListener("click", () => {
  state.view = button.dataset.view;
  state.page = 1;
  document.querySelectorAll(".view-tab").forEach(tab => tab.classList.toggle("active", tab === button));
  elements.eventFilterWrap.classList.toggle("hidden", state.view !== "rows");
  elements.stateFilterWrap.classList.toggle("hidden", state.view !== "cars");
  renderTable();
}));
[elements.timeFrom, elements.timeTo, elements.eventFilter, elements.stateFilter].forEach(control => control.addEventListener("change", () => { state.page = 1; renderTable(); }));
elements.previous.addEventListener("click", () => { state.page -= 1; renderTable(); });
elements.next.addEventListener("click", () => { state.page += 1; renderTable(); });

const dialog = document.querySelector("#methodDialog");
document.querySelector("#openMethod").addEventListener("click", () => dialog.showModal());
document.querySelector("#closeMethod").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });

runSimulation();
