# Guía para explicar y defender la aplicación

Esta guía describe el código de esta revisión. Las referencias indican archivo, función y línea de inicio; en el editor podés abrir el archivo y usar **Ctrl+G** para ir a esa línea. Si después editás el código, buscá el nombre de la función.

## 1. Qué hace la aplicación y dónde empieza

Simula un vagón que transporta autos entre dos paradas, P1 y P2. Hay una cola independiente en cada parada y un único vagón. Comienza libre en P1, con ambas colas vacías. Los autos llegan individualmente, esperan, suben cuando la política permite un viaje, o abandonan si alcanzan su paciencia sin poder subir.

Es una **simulación de eventos discretos**: el reloj salta al próximo evento. No se ejecuta un paso por cada minuto. Entre eventos, la cantidad en cola y el estado del vagón permanecen constantes; las esperas y las áreas temporales sí crecen.

| Archivo | Responsabilidad y lugar para mostrar |
| --- | --- |
| [run.bat](run.bat) | Inicia el servidor usando el Python disponible. |
| [server.py](server.py#L91), `main`, línea 91 | Levanta el servidor HTTP, por defecto en `127.0.0.1:8000`. |
| [static/index.html](static/index.html#L46) | Formulario, botones, comparación, tabla y filtros. |
| [static/app.js](static/app.js#L253), `readConfig` y `runSimulation` | Lee los números del formulario y envía JSON a `POST /api/simulate`. Al abrir la página ejecuta una simulación automáticamente. |
| [server.py](server.py#L65), `do_POST`, línea 65 | Recibe JSON, llama a `simulate_both` y devuelve los resultados. Los errores de parámetros se devuelven como respuesta 400. |
| [simulation.py](simulation.py#L772), `simulate_both`, línea 772 | Ejecuta las réplicas de A y B con las mismas llegadas dentro de cada réplica. |
| [simulation.py](simulation.py#L616), `Simulation.run`, línea 616 | Agenda inicial, elección de eventos y avance del reloj. |
| [static/app.js](static/app.js#L475), `renderAll`, línea 475 | Dibuja comparación, indicadores y tabla. |
| [static/styles.css](static/styles.css) | Apariencia, encabezados y columnas fijas, desplazamiento y formato de las celdas. No calcula resultados del modelo. |

El flujo completo es: **formulario → JavaScript → API Python → configuración → llegadas → eventos A/B → resultados JSON → tablas**. No hay una base de datos: los resultados quedan en memoria y se reemplazan cuando se vuelve a simular.

## 2. Parámetros de entrada: significado, cálculo y uso

Los valores base están en [SimulationConfig, simulation.py:23](simulation.py#L23), en los `input` de HTML y en `DEFAULT_CONFIG` de JavaScript. Este último sirve para restaurar el formulario. La API también ofrece `GET /api/defaults`, aunque la interfaz actual no lo consulta al iniciar.

Los parámetros son **datos de entrada**. A partir de ellos se calculan tasas, medias, fechas de eventos e indicadores.

| Parámetro | Valor inicial | Cómo y dónde se utiliza |
| --- | --- | --- |
| `horizon` | 480 min | Límite de generación de llegadas, evento de cierre en `run`, y denominador de colas promedio/utilización en `_result`. |
| `capacity` | 5 autos | Máximo que carga `_board`; mínimo para salir con A; conteo de viajes completos en `_start_trip`. |
| `arrival_count_p1` | 1 auto | Numerador de la tasa de llegadas P1 en `generate_arrivals`. Es cantidad **media**, no tamaño de un lote. |
| `arrival_window_p1` | 1 min | Denominador de esa tasa y numerador de la media entre llegadas P1. |
| `arrival_count_p2` | 3 autos | Numerador de la tasa P2; también representa una cantidad media. |
| `arrival_window_p2` | 5 min | Denominador de la tasa P2 y numerador de la media entre llegadas P2. |
| `loaded_trip_time` | 5 min | Duración de cualquier viaje con al menos un auto; `_start_trip`. Incluye carga, traslado y descarga según el enunciado. |
| `empty_trip_time` | 3 min | Duración si no sube ningún auto; `_start_trip`. Con A normalmente no se utiliza porque A nunca sale vacío. |
| `patience` | 12 min | `deadline = llegada + patience`, en `_arrive_cars`. Se agenda el abandono individual. |
| `fare_per_car` | $2 | `autos que suben × tarifa`, registrado al empezar el viaje; `_start_trip`. |
| `cost_per_trip` | $6 | Se suma una vez por salida, incluso vacía; `_start_trip`. |
| `loss_per_abandoned_car` | $1 | Se suma cuando abandona un auto; `_process_abandonment`. |
| `seed` | 20260919 | Inicializa el generador pseudoaleatorio. La réplica de índice `r` usa `seed + r`; `generate_arrivals` y `simulate_both`. |
| `replications` | 100 | Cantidad de experimentos completos para comparar promedios; `simulate_both`. No prolonga el horizonte de cada experimento. |

`readConfig` convierte los valores del formulario con `Number`. `SimulationConfig.from_mapping` (línea 40) convierte los tipos de Python y llama a `validate` (línea 58). Capacidad, semilla y réplicas deben ser enteros; tiempos y tasas deben ser positivos y finitos; importes pueden ser cero pero no negativos. Se admiten entre 1 y 500 réplicas, horizonte hasta 100000 y semilla entre 0 y 4294967295. También hay un límite de llegadas esperadas para impedir escenarios excesivos.

Cambiar un campo no recalcula inmediatamente: hay que pulsar **Simular ambas políticas**. Restaurar parámetros repone el formulario; también requiere simular para obtener nuevos resultados. Los filtros, la política seleccionada y las pestañas solamente cambian la visualización de resultados ya calculados.

## 3. Cómo se generan los tiempos entre llegadas

Mostrar [generate_arrivals, simulation.py:125](simulation.py#L125).

Para cada parada se calcula:

```text
λ = autos promedio / minutos de referencia      [autos/minuto]
μ = 1 / λ = minutos de referencia / autos       [minutos/auto]
RND = uniforme pseudoaleatorio en [0, 1)
T = -μ × ln(1 - RND)
hora de llegada siguiente = hora de llegada anterior + T
```

Con los datos iniciales, P1 tiene `λ = 1` y `μ = 1`; P2 tiene `λ = 3/5 = 0,6` y `μ = 5/3 ≈ 1,6667`. Por ejemplo, si `RND = 0,5`, el intervalo es aproximadamente `0,6931` minutos en P1 y `1,1552` en P2. Si la llegada anterior a P2 fue en el minuto 10, la siguiente será aproximadamente en 11,1552.

La instrucción que genera el intervalo es:

```python
rnd = rng.random()
interval = -mean_interarrival * math.log1p(-rnd)
time += interval
samples.append(ArrivalSample(time, rnd, interval))
```

`log1p(-rnd)` calcula `ln(1-rnd)` de forma numéricamente estable. Un intervalo no positivo se descarta. `ArrivalSample`, línea 117, conserva **hora, RND e intervalo** para poder auditar cada llegada.

Hay un generador raíz inicializado con la semilla y un generador separado por parada, inicializado con `root_rng.getrandbits(64)`. Primero se prepara toda la trayectoria; después cada política consume esa misma lista. La política no altera los números sorteados.

La primera llegada también es aleatoria y se calcula desde cero. Se genera una muestra posterior al horizonte para poder mostrar la próxima llegada pendiente, pero ese auto no ingresa al sistema ni tiene columna si queda fuera del período simulado.

**Supuesto para defender:** el enunciado dice “1 auto por minuto” y “3 autos cada 5 minutos”, pero no nombra una distribución. La aplicación interpreta esas expresiones como tasas medias y adopta tiempos exponenciales. En P2 no llegan tres autos juntos cada cinco minutos. Si la cátedra exigiera llegadas deterministas o lotes, habría que cambiar este modelo. El conteo en intervalos de un proceso de Poisson y sus tiempos exponenciales son conceptos relacionados, pero acá el código sortea directamente los tiempos entre autos.

## 4. Cómo se elige el próximo evento

Mostrar [EVENT_PRIORITY, simulation.py:158](simulation.py#L158), [_schedule, línea 235](simulation.py#L235) y [run, línea 616](simulation.py#L616).

La agenda `self.events` es un **heap**, una estructura que permite extraer eficientemente el menor elemento. Cada entrada tiene:

```python
(time, EVENT_PRIORITY[kind], sequence, kind, payload)
```

Primero se compara la hora; después la prioridad; si ambas coinciden, el número secuencial de inserción. `kind` identifica el tipo y `payload` lleva el ID del auto o del viaje cuando corresponde. Se inserta con `heapq.heappush` y se extrae con `heapq.heappop`.

| Evento | Prioridad en un empate | Efecto |
| --- | --- | --- |
| `wagon_arrival` | 10 | Termina un viaje, entrega la carga y libera el vagón. |
| `arrival_p1` | 20 | Crea un auto en P1. |
| `arrival_p2` | 21 | Crea un auto en P2. |
| `dispatch` | 30 | Intenta iniciar un viaje según la política. |
| `abandonment` | 40 | Retira un auto si todavía está en cola. |
| `horizon` | 99 | Registra el cierre y detiene la simulación. |

Si las próximas horas son P1=4,8; P2=4,2; fin de traslado=5 y abandono=4,5, se procesa la llegada P2 de 4,2. No se elige por la fila visible ni por recorrer las columnas de la tabla: se extrae el mínimo de la agenda.

El ciclo hace esto:

```text
1. Extraer el evento mínimo.
2. Acumular áreas hasta esa hora usando el estado anterior.
3. Actualizar el reloj.
4. Ejecutar el manejador del evento.
5. Registrar la fotografía posterior al evento si corresponde.
6. Repetir hasta el cierre.
```

Los eventos simultáneos producen filas diferentes con el mismo reloj. Un abandono obsoleto se descarta y no genera fila. `_schedule_dispatch` evita agendar dos despachos iguales para el mismo instante.

El calendario usa tiempos redondeados a **9 decimales**; `EPSILON = 1e-9` sirve como tolerancia numérica. La interfaz muestra **2 decimales**. Por eso dos eventos con el mismo tiempo visible pueden tener horas internas distintas y procesarse en ese orden.

## 5. Qué hace cada evento y cómo funcionan las políticas

**Llegada de auto:** [_process_arrival, línea 492](simulation.py#L492) consume la muestra actual, crea exactamente un auto mediante `_arrive_cars`, registra RND e intervalo usados y programa la siguiente llegada de esa parada. Si el vagón está libre en esa parada y se completó la capacidad, agenda un despacho en el mismo instante.

**Inicio de traslado:** [_process_dispatch, línea 571](simulation.py#L571) llama a [_start_trip, línea 298](simulation.py#L298). Se comprueba la política, se cargan autos FIFO, se fija destino opuesto, se calcula duración y fin del viaje, y se actualizan ingresos y costos. El vagón pasa a `En viaje` y se agenda `wagon_arrival`. No hay eventos separados de carga y descarga: sus tiempos están incluidos en la duración con carga.

**Fin de traslado:** [_process_wagon_arrival, línea 531](simulation.py#L531) marca los autos como `Entregado`, suma entregas, marca el viaje como completado, vacía el vagón y lo deja libre en la parada destino. Si corresponde, agenda una nueva salida en ese mismo instante.

**Abandono:** [_process_abandonment, línea 590](simulation.py#L590) comprueba que el auto siga `En cola`. Si es así, lo marca `Perdido`, fija hora y espera, decrementa la cola e incrementa pérdidas y su costo. Si ya subió, no hace nada.

| Regla | Política A | Política B |
| --- | --- | --- |
| Momento de salida | Cuando hay al menos `capacity` autos en la parada actual. | Al terminar cada traslado vuelve a salir inmediatamente. |
| Cantidad que carga | Exactamente la capacidad. | Entre cero y la capacidad, según la cola disponible. |
| Cola insuficiente | Espera. | Sale con carga parcial o vacía. |
| Cola en la otra orilla | No provoca una salida vacía para buscar autos. | El movimiento continuo termina llevando el vagón a esa orilla. |
| Inicio con colas vacías | Permanece en P1 esperando. | El código agenda una salida vacía P1 → P2 en `t=0`. |
| Tiempo de viaje | Tiempo con carga. | Tiempo con carga si lleva algún auto; tiempo vacío si no lleva ninguno. |

La restricción decisiva de A está en `_start_trip`:

```python
if self.policy == "A" and queue_count < self.config.capacity:
    return {}
```

La continuidad de B está en `_process_wagon_arrival`:

```python
if self.policy == "B" or self.queue_counts[destination] >= self.config.capacity:
    self._schedule_dispatch(self.clock)
```

Su salida inicial está en `run`, dentro de `if self.policy == "B"`. Es un criterio de inicialización explícito: el enunciado describe la salida inmediata después de un viaje y la aplicación extiende la operación continua al instante cero.

**Ejemplo de empate:** capacidad 2, paciencia 1; un auto llega en `t=1` y otro en `t=2`. En `t=2` coinciden segunda llegada y vencimiento del primero. Se procesa la llegada, luego el despacho: suben ambos. Cuando se procesa el abandono del primero, ya está viajando y se ignora. El test `test_car_can_board_at_exact_patience_limit` reproduce este caso.

## 6. Colas y atributos de los autos

Mostrar [Car, simulation.py:103](simulation.py#L103), [Simulation.__init__, línea 171](simulation.py#L171), [_arrive_cars, línea 356](simulation.py#L356) y [_board, línea 278](simulation.py#L278).

`self.cars` es el diccionario de todos los autos que ingresaron, indexado por ID. Los IDs son `P1-0001`, `P1-0002`, `P2-0001`, etc. Cada parada tiene su propia secuencia. Un auto entregado o perdido se conserva para consultar su historia.

`self.queues` contiene dos `deque` con IDs: se inserta con `append` y se toma el primero con `popleft`. Eso implementa FIFO: **primero en llegar, primero en ser atendido**. Cada cola guarda su propio orden; no hay una cola global que mezcle las paradas.

`queue_counts` guarda las cantidades activas. Al abandonar se cambia el estado y se decrementa el contador, pero el ID puede permanecer físicamente en el `deque` hasta que se lo encuentre al cargar. `_valid_queue_ids` y `_board` ignoran los que ya no estén `En cola`. Por eso no debe usarse `len(self.queues[stop])` como longitud activa de la cola.

`abandonment_calendars` mantiene un heap de vencimientos por parada para mostrar el próximo abandono válido. `_next_abandonment` elimina entradas de autos que ya salieron de la cola. Este calendario auxiliar no reemplaza la agenda general de eventos.

| Atributo | Significado / momento en que se fija |
| --- | --- |
| `id`, `stop` | Identidad y parada de origen; al llegar. |
| `arrival_time` | Hora de ingreso; al llegar. |
| `deadline` | Llegada + paciencia; al llegar. Sigue siendo el límite original aunque luego suba. |
| `state` | `En cola` → `En viaje` → `Entregado`, o `En cola` → `Perdido`. |
| `board_time` | Hora de subida; en `_board`. |
| `wait_time` | Subida − llegada, o abandono − llegada. Mientras espera todavía no es definitiva. |
| `delivered_time` | Hora de entrega; al finalizar el viaje. |
| `lost_time` | Hora de abandono; si pierde la paciencia. |
| `trip_id` | Identificador del traslado; al iniciar el viaje que lo transporta. |
| `current_wait` | Dato derivado: espera definitiva si salió de la cola; si aún espera, reloj observado − llegada. |
| `system_time` | Entrega − llegada, disponible únicamente para entregados, según la convención actual de la aplicación. |

En la pestaña **Autos**, los atributos son los del cierre. Para los que siguen esperando, `_result` usa `horizon - arrival_time`. No confundir tiempo de espera con tiempo en el sistema: un auto puede esperar 4 minutos y ser entregado 9 minutos después de haber llegado, si su viaje duró 5.

## 7. Las columnas de autos al final del vector: corrección realizada

Antes, `columnsForView` devolvía solamente `ROW_COLUMNS`. El motor tenía los autos y la pestaña Autos los mostraba, pero no existía ninguna columna individual dentro del vector de estado.

Ahora [columnsForView, static/app.js:371](static/app.js#L371) agrega después del resultado económico **una columna física por cada auto de la réplica**, en orden de ingreso. El ID aparece como encabezado y cada celda contiene los mismos atributos visibles en la pestaña Autos, correspondientes a ese evento. Se llega a ellas desplazando horizontalmente la tabla.

Mostrar estas tres funciones:

1. [carColumnsForPolicy, línea 117](static/app.js#L117): recorre las filas completas e identifica en qué fila llegó, subió, fue entregado o abandonó cada auto, a partir de `arrived_ids`, `loaded_ids`, `delivered_ids` y `abandoned_ids`.
2. [carAtRow, línea 136](static/app.js#L136): reconstruye el auto al número de fila pedido. Antes de su llegada devuelve `null` y se muestra `—`. No expone horas de subida, entrega o abandono futuras. Mientras está en cola calcula la espera con el reloj de esa fila.
3. [formatCarAtRow, línea 160](static/app.js#L160): reutiliza las definiciones `CAR_COLUMNS` para presentar los atributos dentro de una celda. El estado se llama “Estado”, porque aquí no es necesariamente el estado final.

Se compara **número de fila**, no solo hora. Si llegada y despacho ocurren en el mismo minuto, el auto está `En cola` en la primera fila y `En viaje` en la segunda.

Las columnas se definen con todos los autos de la corrida y mantienen posiciones estables al filtrar o paginar; las celdas anteriores al ingreso quedan vacías. Los autos que ya terminaron conservan sus datos. No se reutilizan sus columnas para otros autos. La reconstrucción toma siempre la historia completa, aunque en pantalla se filtre únicamente el final.

Esto evita enviar en JSON una copia completa de todos los autos por cada evento. `WeakMap` guarda el índice por resultado/política, y los textos de estados estables se reutilizan. La tabla sigue siendo ancha: es consecuencia de mostrar una columna por cada auto, sin un límite artificial que los oculte.

## 8. Cómo leer todos los grupos del vector de estado

La fotografía se arma en [_snapshot, simulation.py:395](simulation.py#L395). Las columnas visibles se definen en [ROW_COLUMNS, static/app.js:18](static/app.js#L18); `renderTable` las dibuja. Cada fotografía es **posterior al evento indicado**.

| Grupo | Columnas y lectura |
| --- | --- |
| Evento y reloj | `row` es el número de fila; `event` describe lo ocurrido; `time` es el reloj de simulación. La inicialización es la fila 0. |
| Llegada actual | `arrival_rnd_used` y `interarrival_used`: sorteo e intervalo del auto que acaba de llegar. `arrivals_now_p1/p2`: cuántos llegan en esa fila, cero o uno. |
| Próximas llegadas | `arrival_rnd_p1/p2`, `interarrival_p1/p2`, `next_arrival_p1/p2`: RND, intervalo y hora de la **siguiente** llegada pendiente de cada parada. |
| Vagón | Estado, posición y recorrido; viaje que empieza/termina; cantidad e IDs que suben; entregados en la fila; carga actual; hora de salida y fin previsto. |
| Cola P1 / P2 | Cantidad activa; IDs con espera actual; mayor espera entre los que siguen esperando; próximo abandono válido; cantidad que abandona en este evento. |
| Acumuladores | Llegadas, embarques, entregas, pérdidas y viajes acumulados; sumas de esperas; cola promedio y utilización parcial. Estos dos últimos son indicadores derivados, aunque compartan el encabezado. |
| Resultado económico | Ingresos, costo de viajes, pérdidas por abandono y neto acumulados. |
| Autos | Una columna por identidad, con los atributos históricos explicados antes. |

En una fila de llegada, **RND auto** explica la llegada que acaba de ocurrir; **RND P1/P2** ya puede corresponder a la siguiente llegada, porque `_process_arrival` avanza el calendario antes de tomar la fotografía. En filas de otros eventos, los datos de próximas llegadas se conservan: no se vuelve a sortear todo en cada fila.

Los valores `loaded_now`, `delivered_now` y `abandoned_now_p1/p2` son incrementos de esa fila; se reinician mediante `_event_context`. En cambio, `boarded_p1/p2`, `delivered_total` y `lost_p1/p2` acumulan toda la corrida.

## 9. Acumuladores: dónde aumentan y qué representan

Se inicializan en cero en `Simulation.__init__`.

| Acumulador interno | Actualización | Uso |
| --- | --- | --- |
| `arrived[stop]` | +1 en `_arrive_cars`. | Total de ingresados y tasa de pérdida. |
| `boarded[stop]` | +1 por auto en `_board`. | Autos atendidos; denominador de espera promedio de atendidos. |
| `delivered` | +cantidad de la carga en `_process_wagon_arrival`. | Autos cuyo traslado terminó. |
| `lost[stop]` | +1 en `_process_abandonment`. | Autos perdidos y denominador de su espera promedio. |
| `trip_count` | +1 por salida en `_start_trip`. | Viajes iniciados, incluidos los aún no completados. |
| `loaded_trip_count` | +1 si carga > 0. | Viajes con carga. |
| `full_trip_count` | +1 si carga = capacidad. | Viajes completos. |
| `empty_trip_count` | +1 si carga = 0. | Viajes vacíos. |
| `wait_served` | +espera de cada auto al subir, en `_board`. | Suma de esperas de atendidos. |
| `wait_lost` | +espera al abandonar, en `_process_abandonment`. | Suma de esperas de perdidos. |
| `queue_area[stop]` | +cola anterior × tiempo transcurrido, en `_update_time_areas`. | Integral de cada cola, en auto-minutos. |
| `wagon_busy_area` | +tiempo transcurrido si el vagón estaba viajando. | Minutos ocupado, incluidos viajes vacíos. |
| `max_queue[stop]` | Máximo entre valor anterior y cola después de cada llegada. | Pico observado, aunque luego se despache en el mismo instante. |
| `revenue` | +autos que suben × tarifa, en `_start_trip`. | Ingreso acumulado. |
| `operating_cost` | +costo por viaje, en `_start_trip`. | Costo de todas las salidas. |
| `loss_cost` | +penalización por auto, en `_process_abandonment`. | Pérdida acumulada por abandonos. |

`wait_served` y `wait_lost` no crecen por cada minuto ni contienen a los autos que siguen esperando. Se incorporan cuando la espera individual termina. `queue_area`, en cambio, sí contempla el tiempo de todos los que estuvieron en cola, incluidos quienes siguen allí al cierre.

## 10. Estadísticas: fórmulas y denominadores

Mostrar [_update_time_areas, línea 251](simulation.py#L251), [_snapshot, línea 395](simulation.py#L395) y [_result, línea 670](simulation.py#L670).

Antes de procesar un evento en `t`, se calcula `Δt = t - last_clock`. Si había tres autos esperando durante dos minutos, se agregan **6 auto-minutos** al área de esa cola. Se hace antes de modificar el estado para atribuir el intervalo a la cola que realmente existía durante ese tiempo. En eventos simultáneos, `Δt = 0`.

| Indicador | Fórmula |
| --- | --- |
| Espera promedio de atendidos | `wait_served / (boarded[1] + boarded[2])`. Incluye a quienes subieron aunque sigan viajando al cierre. |
| Espera promedio de perdidos | `wait_lost / (lost[1] + lost[2])`. |
| Cola promedio P1/P2 | `queue_area[stop] / horizon`. |
| Cola promedio total | `(queue_area[1] + queue_area[2]) / horizon`. Es la suma de ambas colas promedio, no el promedio aritmético entre las dos. |
| Utilización del vagón | `wagon_busy_area / horizon`, mostrada como porcentaje. Cuenta ocupado aun cuando viaja vacío. |
| Tasa de pérdida | `lost_total / arrivals_total`. |
| Resultado neto | `revenue - operating_cost - loss_cost`. |

Para denominadores sin observaciones, el código muestra cero y evita dividir por cero. Algunos indicadores, como la espera promedio de perdidos, máximos por parada y tasa de pérdida, se calculan en el resumen devuelto por Python aunque no todos tengan una tarjeta en pantalla.

En cada fila del vector, cola promedio y utilización usan **el reloj de esa fila** como denominador, no el horizonte total. En `t=0` se muestran cero. En el cierre coinciden con las estadísticas finales.

La cola promedio no es el promedio de las longitudes de las filas: las filas representan intervalos de distinta duración. Tampoco la utilización mide cuántos asientos se ocuparon: B puede tener utilización del 100 % incluso con viajes vacíos.

Ejemplo económico con valores iniciales: un viaje con 5 autos registra ingreso `$10`, costo `$6` y contribución `$4` antes de pérdidas. Uno con 2 autos registra `$4 - $6 = -$2`; uno vacío, `$0 - $6 = -$6`. Cada abandono resta además `$1`.

## 11. Cierre, réplicas y comparación

El cierre se agenda como un evento. Se incluyen los eventos exactamente en el horizonte porque tienen prioridad anterior a `horizon`. No se continúa hasta vaciar las colas. Un viaje iniciado antes o exactamente al cierre queda cobrado y costeado aunque todavía no entregue sus autos. Su llegada futura se conserva como dato, pero no se procesa.

La conservación permite comprobar que ningún auto desaparece:

```text
llegados = entregados + en viaje + en cola + perdidos
subieron = entregados + en viaje
```

Mostrar [simulate_both, línea 772](simulation.py#L772). Para cada réplica `r` se generan llegadas con `seed + r`, se ejecutan A y B sobre la misma trayectoria y se guardan sus resúmenes. Solo la primera réplica guarda filas, autos y traslados para la interfaz; las restantes se ejecutan con `record_detail=False`.

La comparación superior usa la media aritmética de cada indicador entre réplicas. La tabla y las tarjetas inferiores corresponden únicamente a **la réplica 1**. Por eso sus números pueden ser diferentes. Por ejemplo, la espera comparada es la media de las esperas promedio de cada réplica, no una división de todas las esperas sumadas por todos los autos sumados.

La elección se basa en el neto promedio. Para cada réplica calcula `D_r = neto_A - neto_B` y después:

```text
diferencia media = promedio(D_r)
IC 95 % aproximado = diferencia media ± 1,96 × desvío muestral(D_r) / √réplicas
```

Si la diferencia es positiva favorece A; si es negativa, B. Si el intervalo incluye cero, la interfaz indica que la ventaja no es concluyente. Con una sola réplica no se calcula intervalo. Es un intervalo normal aproximado, no una garantía ni un intervalo basado en Student.

Con los valores y semilla iniciales, las 100 réplicas producen netos promedio de **$43,06 para A y $48,96 para B**. La diferencia A − B es **−$5,90**, con intervalo aproximado **[−$9,38; −$2,42]**. Esa configuración favorece B por resultado económico; no significa que B gane en todos los indicadores ni con cualquier parámetro. De hecho, la espera promedio de atendidos es aproximadamente 7,77 en A y 7,97 en B.

## 12. Vistas, filtros y pruebas para mostrar en una defensa

[filteredItems, static/app.js:390](static/app.js#L390) aplica el intervalo temporal y los filtros. En Vector usa la hora del evento; en Autos, la hora de llegada; en Traslados, la hora de salida. La tabla pagina de a 100 filas. Cambiar filtros no vuelve a ejecutar el modelo y no cambia sus acumuladores.

[showDetail, línea 455](static/app.js#L455) abre el detalle de la fila al pulsarla. La pestaña Traslados muestra origen, destino, salida, llegada prevista, duración, tipo, carga, IDs, si terminó, ingreso y costo. La pestaña Autos muestra los atributos finales. La pestaña Vector muestra su evolución.

Recorrido sugerido para explicar el código:

1. Abrí `SimulationConfig` y relacioná sus nombres con el formulario.
2. Mostrá `generate_arrivals`: tasa, media, RND, transformada y suma al reloj anterior.
3. Mostrá `EVENT_PRIORITY`, `_schedule` y `run`: agenda, mínimo y empates.
4. Mostrá `_arrive_cars`, `_board` y `_process_abandonment`: identidad, FIFO y paciencia.
5. Mostrá `_start_trip` y `_process_wagon_arrival`: diferencia entre políticas y duración.
6. Mostrá `_update_time_areas` y `_result`: áreas, denominadores y dinero.
7. Mostrá `_snapshot` y `ROW_COLUMNS`: cómo llegan los valores al vector.
8. Mostrá `carColumnsForPolicy` y `carAtRow`: una columna por auto sin anticipar su futuro.
9. Mostrá `simulate_both`: llegadas comunes, réplicas, promedio y recomendación.

Las pruebas se ejecutan con:

```powershell
python -m unittest discover -s tests -v
node --test tests/test_car_columns.js
```

Si Python solo está disponible mediante LibreOffice en esta máquina:

```powershell
& 'C:/Program Files/LibreOffice/program/python.exe' -m unittest discover -s tests -v
$env:SIM_PYTHON = 'C:/Program Files/LibreOffice/program/python.exe'
node --test tests/test_car_columns.js
```

[tests/test_simulation.py](tests/test_simulation.py) verifica exponencial, semilla, llegadas comunes, FIFO, conservación, contabilidad, orden, paciencia, salida inicial de B y comparación. [tests/test_form_defaults.py](tests/test_form_defaults.py) controla coherencia de valores iniciales y restricciones HTML. [tests/test_car_columns.js](tests/test_car_columns.js) verifica columnas al final, atributos históricos, eventos simultáneos, esperas, encabezados extensos y consistencia fila por fila con las colas, carga y contadores del motor Python para ambas políticas.

Una explicación breve para empezar la defensa: “Genero las llegadas individuales con una exponencial según la tasa de cada parada. Las dos políticas reciben las mismas llegadas. Una agenda ordenada determina el próximo evento; antes de procesarlo acumulo el tiempo de las colas y del vagón. Después actualizo autos, colas y dinero, y guardo una fila del vector. A espera completar la capacidad; B viaja continuamente. Finalmente comparo el resultado neto promedio de varias réplicas”.
