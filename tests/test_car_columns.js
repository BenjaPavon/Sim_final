// Ejecutar: node --test tests/test_car_columns.js
// SIM_PYTHON permite indicar el Python disponible para la prueba integrada.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const element = {
  elements: [],
  addEventListener() {}, querySelector() { return element; }, querySelectorAll() { return []; },
  classList: { add() {}, toggle() {}, remove() {} }, value: "all",
};
const context = vm.createContext({
  Intl, document: { querySelector: () => element, querySelectorAll: () => [] },
  // La petición inicial queda pendiente; los tests proporcionan los datos.
  fetch: () => new Promise(() => {}),
});
vm.runInContext(readFileSync(path.join(root, "static/app.js"), "utf8"), context);
const evaluate = code => vm.runInContext(code, context);
const plain = value => JSON.parse(JSON.stringify(value));

const policy = {
  cars: [
    { id: "P1-0001", stop: 1, arrival_time: 1, deadline: 13, state: "Entregado", board_time: 1, wait_time: 0, trip_id: 1, delivered_time: 6, lost_time: null, system_time: 5, current_wait: 0 },
    { id: "P2-0001", stop: 2, arrival_time: 1, deadline: 13, state: "Perdido", board_time: null, wait_time: 12, trip_id: null, delivered_time: null, lost_time: 13, system_time: null, current_wait: 12 },
  ],
  rows: [
    { row: 0, time: 0 },
    { row: 1, time: 1, arrived_ids: ["P1-0001"] },
    { row: 2, time: 1, arrived_ids: ["P2-0001"] },
    { row: 3, time: 1, loaded_ids: ["P1-0001"] },
    { row: 4, time: 6, delivered_ids: ["P1-0001"] },
    { row: 5, time: 13, abandoned_ids: ["P2-0001"] },
    { row: 6, time: 20 },
  ],
};
context.fixture = policy;
evaluate("globalThis.columns = carColumnsForPolicy(fixture)");
const snapshot = (car, row) => plain(evaluate(`carAtRow(columns[${car}], fixture.rows[${row}])`));

test("una columna por auto después de las columnas económicas", () => {
  evaluate('state.result = { policies: { A: fixture } }; state.view = "rows"');
  const labels = plain(evaluate("columnsForView().map(column => column.label)"));
  assert.deepEqual(labels.slice(-3), ["Resultado neto", "P1-0001", "P2-0001"]);
  assert.equal(evaluate("columnsForView().length - ROW_COLUMNS.length"), 2);
  assert.equal(evaluate("formatCarAtRow(columns[0], fixture.rows[0])"), "—");
});

test("no anticipa llegada ni subida aunque los eventos compartan reloj", () => {
  assert.equal(snapshot(0, 0), null);
  assert.equal(snapshot(1, 1), null);
  assert.equal(snapshot(0, 1).state, "En cola");
  assert.equal(snapshot(0, 2).board_time, null);
  assert.equal(snapshot(0, 2).trip_id, null);
  assert.equal(snapshot(0, 3).state, "En viaje");
  assert.equal(snapshot(0, 3).board_time, 1);
  assert.equal(snapshot(0, 3).delivered_time, null);
  assert.equal(snapshot(0, 3).system_time, null);
  assert.equal(snapshot(0, 4).state, "Entregado");
  assert.equal(snapshot(0, 4).system_time, 5);
});

test("la espera crece en cola y queda fija al abandonar", () => {
  assert.equal(snapshot(1, 4).current_wait, 5);
  assert.equal(snapshot(1, 4).lost_time, null);
  assert.equal(snapshot(1, 5).state, "Perdido");
  assert.equal(snapshot(1, 5).lost_time, 13);
  assert.equal(snapshot(1, 6).current_wait, 12);
  assert.equal(snapshot(0, 6).current_wait, 0);
});

test("renderiza todos los atributos y resiste filtrado de filas intermedias", () => {
  const html = evaluate("formatCarAtRow(columns[0], fixture.rows[4])");
  for (const label of ["Parada", "Hora llegada", "Límite espera", "Estado", "Tiempo espera", "Hora de subida", "Traslado", "Hora entrega", "Tiempo sistema", "Hora abandono"]) {
    assert.ok(html.includes(`${label}:`), label);
  }
  // Consultar directamente la última fila equivale a paginar/filtrar la tabla.
  assert.equal(snapshot(0, 6).state, "Entregado");
  assert.equal(snapshot(1, 6).state, "Perdido");
});

test("los encabezados admiten más de 1000 autos sin exceder colspan", () => {
  const html = evaluate('groupHeaders(Array.from({length: 1001}, () => ({group: "cars"})))');
  assert.ok(html.includes('colspan="1000"'));
  assert.ok(html.includes('colspan="1"'));
});

test("la historia coincide con colas, carga y contadores reales de ambas políticas", () => {
  const python = process.env.SIM_PYTHON || "python";
  const payload = execFileSync(python, ["-c", 'import json; from simulation import simulate_both; print(json.dumps(simulate_both({"horizon":40,"replications":1,"seed":7})))'], { cwd: root, encoding: "utf8", maxBuffer: 10 * 1024 * 1024 });
  for (const result of Object.values(JSON.parse(payload).policies)) {
    context.actual = result;
    const histories = plain(evaluate(`(() => {
      const columns = carColumnsForPolicy(actual);
      return actual.rows.map(row => columns.map(column => carAtRow(column, row)).filter(Boolean));
    })()`));
    result.rows.forEach((row, index) => {
      const cars = histories[index];
      assert.equal(cars.length, row.arrived_p1 + row.arrived_p2);
      for (const stop of [1, 2]) {
        assert.deepEqual(cars.filter(car => car.stop === stop && car.state === "En cola").map(car => car.id), row[`queue_p${stop}`].map(car => car.id));
      }
      assert.deepEqual(cars.filter(car => car.state === "En viaje").map(car => car.id), row.wagon_load_ids);
      assert.equal(cars.filter(car => car.state === "Entregado").length, row.delivered_total);
      assert.equal(cars.filter(car => car.state === "Perdido").length, row.lost_p1 + row.lost_p2);
    });
    for (const car of histories.at(-1)) {
      const final = result.cars.find(item => item.id === car.id);
      for (const [key, value] of Object.entries(car)) {
        if (typeof value === "number") assert.ok(Math.abs(value - final[key]) < 1e-8, key);
        else assert.equal(value, final[key], key);
      }
    }
  }
});
