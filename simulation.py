"""Simulación estocástica del cruce ferroviario del ejercicio 34.

El módulo no depende de paquetes externos. Expone ``simulate`` para una política
y ``simulate_both`` para comparar las dos alternativas del enunciado.
"""

from __future__ import annotations

import heapq
import math
import random
import statistics
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


EPSILON = 1e-9
MAX_ARRIVALS_PER_REPLICATION = 100_000


@dataclass(frozen=True)
class SimulationConfig:
    horizon: float = 480.0
    capacity: int = 5
    arrival_count_p1: float = 1.0
    arrival_window_p1: float = 1.0
    arrival_count_p2: float = 3.0
    arrival_window_p2: float = 5.0
    loaded_trip_time: float = 5.0
    empty_trip_time: float = 3.0
    patience: float = 12.0
    fare_per_car: float = 2.0
    cost_per_trip: float = 6.0
    loss_per_abandoned_car: float = 1.0
    seed: int = 20260919
    replications: int = 100

    @classmethod
    def from_mapping(cls, values: Optional[Dict[str, Any]]) -> "SimulationConfig":
        if not values:
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: values[key] for key in allowed if key in values}
        integer_fields = {"capacity", "seed", "replications"}
        for key in integer_fields:
            if key in clean:
                number = float(clean[key])
                if not math.isfinite(number) or not number.is_integer():
                    raise ValueError(f"{key} debe ser un número entero")
                clean[key] = int(number)
        for key in set(clean) - integer_fields:
            clean[key] = float(clean[key])
        config = cls(**clean)
        config.validate()
        return config

    def validate(self) -> None:
        for name in ("capacity", "seed", "replications"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} debe ser un número entero")
        for name in (
            "horizon", "arrival_count_p1", "arrival_window_p1",
            "arrival_count_p2", "arrival_window_p2", "loaded_trip_time",
            "empty_trip_time", "patience", "fare_per_car", "cost_per_trip",
            "loss_per_abandoned_car",
        ):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} debe ser un número finito")
        positive = {
            "horizon": self.horizon,
            "capacity": self.capacity,
            "arrival_count_p1": self.arrival_count_p1,
            "arrival_window_p1": self.arrival_window_p1,
            "arrival_count_p2": self.arrival_count_p2,
            "arrival_window_p2": self.arrival_window_p2,
            "loaded_trip_time": self.loaded_trip_time,
            "empty_trip_time": self.empty_trip_time,
            "patience": self.patience,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError("Deben ser positivos: " + ", ".join(invalid))
        if self.horizon > 100_000:
            raise ValueError("El horizonte maximo admitido es 100000 minutos")
        if self.seed < 0 or self.seed > 2**32 - 1:
            raise ValueError("La semilla debe estar entre 0 y 4294967295")
        if not 1 <= self.replications <= 500:
            raise ValueError("La cantidad de réplicas debe estar entre 1 y 500")
        expected_arrivals = self.horizon * (
            self.arrival_count_p1 / self.arrival_window_p1
            + self.arrival_count_p2 / self.arrival_window_p2
        )
        if expected_arrivals > MAX_ARRIVALS_PER_REPLICATION:
            raise ValueError("La tasa configurada produce demasiadas llegadas")
        for name in ("fare_per_car", "cost_per_trip", "loss_per_abandoned_car"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} no puede ser negativo")


@dataclass
class Car:
    id: str
    stop: int
    arrival_time: float
    deadline: float
    state: str = "En cola"
    board_time: Optional[float] = None
    wait_time: Optional[float] = None
    delivered_time: Optional[float] = None
    lost_time: Optional[float] = None
    trip_id: Optional[int] = None


@dataclass(frozen=True)
class ArrivalSample:
    """Una llegada individual y los valores que permiten auditar su cálculo."""

    time: float
    rnd: float
    interarrival: float


def generate_arrivals(config: SimulationConfig, seed: int) -> Dict[int, List[ArrivalSample]]:
    """Genera una trayectoria común para comparar A y B con las mismas llegadas.

    En cada parada se usa una secuencia independiente de RND U[0, 1). La
    transformada inversa del apunte es T = -mu * ln(1 - RND), donde
    mu = ventana / autos esperados. Se incluye una muestra posterior al
    horizonte para mantener visible el calendario de la próxima llegada.
    """
    config.validate()
    root_rng = random.Random(seed)
    arrivals: Dict[int, List[ArrivalSample]] = {}
    rates = {
        1: config.arrival_count_p1 / config.arrival_window_p1,
        2: config.arrival_count_p2 / config.arrival_window_p2,
    }
    for stop in (1, 2):
        rng = random.Random(root_rng.getrandbits(64))
        mean_interarrival = 1.0 / rates[stop]
        samples: List[ArrivalSample] = []
        time = 0.0
        while time <= config.horizon:
            rnd = rng.random()
            interval = -mean_interarrival * math.log1p(-rnd)
            if interval <= 0.0:
                continue
            time += interval
            samples.append(ArrivalSample(time, rnd, interval))
            if len(samples) > MAX_ARRIVALS_PER_REPLICATION:
                raise ValueError("La trayectoria excedió el límite de llegadas")
        arrivals[stop] = samples
    return arrivals


EVENT_PRIORITY = {
    "wagon_arrival": 10,
    "arrival_p1": 20,
    "arrival_p2": 21,
    "dispatch": 30,
    # A los 12 minutos exactos el auto aun puede subir: el abandono se
    # procesa despues de arribos y despacho simultaneos.
    "abandonment": 40,
    "horizon": 99,
}


class Simulation:
    def __init__(
        self,
        policy: str,
        config: SimulationConfig,
        arrivals: Dict[int, List[ArrivalSample]],
        record_detail: bool = True,
    ):
        if policy not in {"A", "B"}:
            raise ValueError("La política debe ser A o B")
        self.policy = policy
        self.config = config
        self.arrival_samples = arrivals
        self.record_detail = record_detail
        self.row_count = 0
        self.clock = 0.0
        self.last_clock = 0.0
        self.sequence = 0
        self.events: List[Tuple[float, int, int, str, Any]] = []
        self.pending_dispatch_times: set[float] = set()

        self.queues: Dict[int, Deque[str]] = {1: deque(), 2: deque()}
        self.queue_counts = {1: 0, 2: 0}
        self.abandonment_calendars: Dict[int, List[Tuple[float, str]]] = {1: [], 2: []}
        self.cars: Dict[str, Car] = {}
        self.stop_sequences = {1: 0, 2: 0}

        self.wagon_state = "Libre"
        self.wagon_position: Optional[int] = 1
        self.wagon_origin: Optional[int] = None
        self.wagon_destination: Optional[int] = None
        self.wagon_load: List[str] = []
        self.wagon_trip_id: Optional[int] = None
        self.wagon_departure: Optional[float] = None
        self.wagon_arrival: Optional[float] = None

        self.trips: List[Dict[str, Any]] = []
        self.rows: List[Dict[str, Any]] = []
        self.arrived = {1: 0, 2: 0}
        self.boarded = {1: 0, 2: 0}
        self.delivered = 0
        self.lost = {1: 0, 2: 0}
        self.trip_count = 0
        self.loaded_trip_count = 0
        self.full_trip_count = 0
        self.empty_trip_count = 0
        self.revenue = 0.0
        self.operating_cost = 0.0
        self.loss_cost = 0.0
        self.wait_served = 0.0
        self.wait_lost = 0.0
        self.queue_area = {1: 0.0, 2: 0.0}
        self.wagon_busy_area = 0.0
        self.max_queue = {1: 0, 2: 0}
        self.next_arrival = {stop: arrivals[stop][0].time for stop in (1, 2)}
        self.arrival_rnd = {stop: arrivals[stop][0].rnd for stop in (1, 2)}
        self.interarrival = {stop: arrivals[stop][0].interarrival for stop in (1, 2)}
        self.arrival_index = {1: 0, 2: 0}

    @staticmethod
    def _clean_time(value: float) -> float:
        # El calendario usa 9 decimales; la interfaz muestra solo 2.
        # No se ordenan eventos con los valores redondeados de la pantalla.
        return round(float(value), 9)

    def _schedule(self, time: float, kind: str, payload: Any = None) -> None:
        time = self._clean_time(time)
        self.sequence += 1
        # El heap ordena primero por tiempo y luego por EVENT_PRIORITY. De esta
        # forma se resuelven de manera reproducible los eventos simultaneos.
        heapq.heappush(
            self.events,
            (time, EVENT_PRIORITY[kind], self.sequence, kind, payload),
        )

    def _schedule_dispatch(self, time: float) -> None:
        key = self._clean_time(time)
        if key not in self.pending_dispatch_times:
            self.pending_dispatch_times.add(key)
            self._schedule(key, "dispatch")

    def _update_time_areas(self, new_time: float) -> None:
        delta = new_time - self.last_clock
        if delta < -EPSILON:
            raise RuntimeError("El calendario de eventos retrocedió en el tiempo")
        if delta > 0:
            for stop in (1, 2):
                # Entre dos eventos la longitud de la cola no cambia.
                # Area de cola = cantidad en cola * tiempo transcurrido.
                # Al finalizar: cola promedio = area de cola / horizonte.
                self.queue_area[stop] += self.queue_counts[stop] * delta
            if self.wagon_state == "En viaje":
                # Acumula los minutos en los que el vagon estuvo ocupado.
                # Al finalizar: utilizacion = tiempo ocupado / horizonte.
                self.wagon_busy_area += delta
        self.last_clock = new_time

    def _valid_queue_ids(self, stop: int) -> List[str]:
        return [car_id for car_id in self.queues[stop] if self.cars[car_id].state == "En cola"]

    def _next_abandonment(self, stop: int) -> Optional[float]:
        calendar = self.abandonment_calendars[stop]
        # Los abandonos se programan al llegar el auto. Si luego el auto sube
        # al vagon, su evento queda obsoleto y se descarta al consultar el heap.
        while calendar and self.cars[calendar[0][1]].state != "En cola":
            heapq.heappop(calendar)
        return calendar[0][0] if calendar else None

    def _board(self, stop: int, limit: int) -> List[str]:
        result: List[str] = []
        queue = self.queues[stop]
        while queue and len(result) < limit:
            # popleft implementa FIFO: se atiende primero al que llego primero.
            car_id = queue.popleft()
            car = self.cars[car_id]
            if car.state != "En cola":
                continue
            car.state = "En viaje"
            car.board_time = self.clock
            # Tiempo de espera individual = hora de subida - hora de llegada.
            car.wait_time = self._clean_time(self.clock - car.arrival_time)
            # Se acumula para calcular la espera promedio de autos atendidos.
            self.wait_served += car.wait_time
            self.queue_counts[stop] -= 1
            self.boarded[stop] += 1
            result.append(car_id)
        return result

    def _start_trip(self) -> Dict[str, Any]:
        if self.wagon_state != "Libre" or self.wagon_position not in (1, 2):
            return {}
        origin = self.wagon_position
        queue_count = self.queue_counts[origin]
        # Politica A: el vagon solo puede salir cuando completa su capacidad.
        # Politica B no pasa por esta restriccion y puede salir parcialmente
        # cargado o vacio.
        if self.policy == "A" and queue_count < self.config.capacity:
            return {}

        # Se cargan como maximo "capacity" autos respetando el orden FIFO.
        load = self._board(origin, self.config.capacity)
        destination = 2 if origin == 1 else 1
        # El enunciado fija 5 minutos con autos y 3 minutos si viaja vacio.
        duration = self.config.loaded_trip_time if load else self.config.empty_trip_time

        self.trip_count += 1
        trip_id = self.trip_count
        for car_id in load:
            self.cars[car_id].trip_id = trip_id
        self.loaded_trip_count += int(bool(load))
        self.full_trip_count += int(len(load) == self.config.capacity)
        self.empty_trip_count += int(not load)
        # Ingreso del viaje = autos que suben * tarifa por auto.
        # Cada salida genera el costo completo, incluso una salida vacia.
        self.revenue += len(load) * self.config.fare_per_car
        self.operating_cost += self.config.cost_per_trip

        # Fin de traslado = reloj actual + duracion correspondiente.
        arrival_time = self._clean_time(self.clock + duration)
        trip = {
            "id": trip_id,
            "origin": origin,
            "destination": destination,
            "departure_time": self.clock,
            "arrival_time": arrival_time,
            "duration": duration,
            "load_count": len(load),
            "car_ids": load.copy(),
            "kind": "Con carga" if load else "Vacío",
            "revenue": len(load) * self.config.fare_per_car,
            "cost": self.config.cost_per_trip,
            "completed": False,
        }
        self.trips.append(trip)

        self.wagon_state = "En viaje"
        self.wagon_position = None
        self.wagon_origin = origin
        self.wagon_destination = destination
        self.wagon_load = load.copy()
        self.wagon_trip_id = trip_id
        self.wagon_departure = self.clock
        self.wagon_arrival = arrival_time
        self._schedule(arrival_time, "wagon_arrival", trip_id)
        return trip

    def _arrive_cars(self, stop: int, quantity: int) -> List[str]:
        created: List[str] = []
        for _ in range(quantity):
            self.stop_sequences[stop] += 1
            car_id = f"P{stop}-{self.stop_sequences[stop]:04d}"
            # Limite de espera = hora de llegada + paciencia maxima (12 min).
            deadline = self._clean_time(self.clock + self.config.patience)
            car = Car(car_id, stop, self.clock, deadline)
            self.cars[car_id] = car
            self.queues[stop].append(car_id)
            self.queue_counts[stop] += 1
            self.arrived[stop] += 1
            heapq.heappush(self.abandonment_calendars[stop], (deadline, car_id))
            # Se agenda un evento individual para poder saber exactamente que
            # auto abandona y conservar su tiempo de espera.
            self._schedule(deadline, "abandonment", car_id)
            created.append(car_id)
        # Guarda la mayor cantidad simultanea observada en esta parada.
        self.max_queue[stop] = max(self.max_queue[stop], self.queue_counts[stop])
        return created

    def _event_context(self) -> Dict[str, Any]:
        return {
            "arrivals_now_p1": 0,
            "arrivals_now_p2": 0,
            "arrived_ids": [],
            "arrival_rnd_used": None,
            "interarrival_used": None,
            "loaded_now": 0,
            "loaded_ids": [],
            "delivered_now": 0,
            "delivered_ids": [],
            "abandoned_now_p1": 0,
            "abandoned_now_p2": 0,
            "abandoned_ids": [],
            "trip_started_id": None,
            "trip_finished_id": None,
        }

    def _snapshot(
        self,
        event_type: str,
        event: str,
        details: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        row_number = self.row_count
        self.row_count += 1
        if not self.record_detail:
            return
        context = context or self._event_context()
        # Cada fila de la tabla es una fotografia posterior al evento indicado.
        # Por eso conserva todos los estados aunque en esa fila solo haya
        # cambiado una llegada, un abandono o el vagon.
        queue_ids = {stop: self._valid_queue_ids(stop) for stop in (1, 2)}
        queue_detail: Dict[int, List[Dict[str, Any]]] = {}
        oldest_wait: Dict[int, float] = {}
        for stop in (1, 2):
            queue_detail[stop] = [
                {
                    "id": car_id,
                    "arrival_time": self.cars[car_id].arrival_time,
                    # Espera actual = reloj de la fila - llegada del auto.
                    "wait": self._clean_time(self.clock - self.cars[car_id].arrival_time),
                    "deadline": self.cars[car_id].deadline,
                }
                for car_id in queue_ids[stop]
            ]
            oldest_wait[stop] = max(
                (item["wait"] for item in queue_detail[stop]), default=0.0
            )

        elapsed = self.clock if self.clock > 0 else 0.0
        # Resultado neto acumulado hasta esta fila.
        net_result = self.revenue - self.operating_cost - self.loss_cost
        # Estos dos indicadores son parciales: usan el tiempo transcurrido hasta
        # la fila actual, no el horizonte completo.
        avg_queue_to_now = (
            (self.queue_area[1] + self.queue_area[2]) / elapsed if elapsed else 0.0
        )
        utilization_to_now = self.wagon_busy_area / elapsed if elapsed else 0.0
        route = (
            f"P{self.wagon_origin} -> P{self.wagon_destination}"
            if self.wagon_state == "En viaje"
            else "-"
        )
        row = {
            "row": row_number,
            "event_type": event_type,
            "event": event,
            "details": details,
            "time": self.clock,
            **context,
            "next_arrival_p1": self.next_arrival[1],
            "next_arrival_p2": self.next_arrival[2],
            "arrival_rnd_p1": self.arrival_rnd[1],
            "arrival_rnd_p2": self.arrival_rnd[2],
            "interarrival_p1": self.interarrival[1],
            "interarrival_p2": self.interarrival[2],
            "next_abandon_p1": self._next_abandonment(1),
            "next_abandon_p2": self._next_abandonment(2),
            "wagon_state": self.wagon_state,
            "wagon_location": f"P{self.wagon_position}" if self.wagon_position else "En río",
            "wagon_route": route,
            "wagon_trip_id": self.wagon_trip_id,
            "wagon_load_count": len(self.wagon_load),
            "wagon_load_ids": self.wagon_load.copy(),
            "trip_departure": self.wagon_departure,
            "next_wagon_arrival": self.wagon_arrival,
            "queue_p1_count": self.queue_counts[1],
            "queue_p1": queue_detail[1],
            "oldest_wait_p1": oldest_wait[1],
            "queue_p2_count": self.queue_counts[2],
            "queue_p2": queue_detail[2],
            "oldest_wait_p2": oldest_wait[2],
            "arrived_p1": self.arrived[1],
            "arrived_p2": self.arrived[2],
            "boarded_p1": self.boarded[1],
            "boarded_p2": self.boarded[2],
            "delivered_total": self.delivered,
            "lost_p1": self.lost[1],
            "lost_p2": self.lost[2],
            "trips_total": self.trip_count,
            "trips_empty": self.empty_trip_count,
            "acc_wait_served": self._clean_time(self.wait_served),
            "acc_wait_lost": self._clean_time(self.wait_lost),
            "queue_area": self._clean_time(self.queue_area[1] + self.queue_area[2]),
            "avg_queue": self._clean_time(avg_queue_to_now),
            "wagon_utilization": self._clean_time(utilization_to_now),
            "revenue": self._clean_time(self.revenue),
            "operating_cost": self._clean_time(self.operating_cost),
            "loss_cost": self._clean_time(self.loss_cost),
            "net_result": self._clean_time(net_result),
        }
        self.rows.append(row)

    def _process_arrival(self, stop: int) -> None:
        context = self._event_context()
        # Cada evento representa un auto individual. El RND y el intervalo
        # pertenecen a esta llegada y permiten reconstruir su hora.
        sample = self.arrival_samples[stop][self.arrival_index[stop]]
        if abs(self.clock - sample.time) > EPSILON:
            raise RuntimeError("La llegada no coincide con su calendario")
        created = self._arrive_cars(stop, 1)
        context[f"arrivals_now_p{stop}"] = 1
        context["arrived_ids"] = created
        context["arrival_rnd_used"] = sample.rnd
        context["interarrival_used"] = sample.interarrival

        # La proxima fila de la secuencia fue generada con otro RND usando
        # T = -(ventana/autos esperados) * ln(1 - RND).
        self.arrival_index[stop] += 1
        next_sample = self.arrival_samples[stop][self.arrival_index[stop]]
        self.arrival_rnd[stop] = next_sample.rnd
        self.interarrival[stop] = next_sample.interarrival
        self.next_arrival[stop] = next_sample.time
        if next_sample.time <= self.config.horizon + EPSILON:
            self._schedule(next_sample.time, f"arrival_p{stop}")

        if (
            self.wagon_state == "Libre"
            and self.wagon_position == stop
            and self.queue_counts[stop] >= self.config.capacity
        ):
            # Si el vagon esta en esta parada y ya hay capacidad completa, se
            # agenda la salida en el mismo instante, luego de las llegadas.
            self._schedule_dispatch(self.clock)

        self._snapshot(
            f"arrival_p{stop}",
            f"Llegada de 1 auto a P{stop}",
            f"{created[0]} · RND {sample.rnd:.2f} · T {sample.interarrival:.2f} min",
            context,
        )

    def _process_wagon_arrival(self, trip_id: int) -> None:
        if self.wagon_trip_id != trip_id:
            raise RuntimeError("Arribo de vagón inconsistente")
        context = self._event_context()
        delivered_ids = self.wagon_load.copy()
        # Al finalizar el traslado, todos los autos que estaban en el vagon
        # pasan de "En viaje" a "Entregado" en el mismo instante.
        for car_id in delivered_ids:
            car = self.cars[car_id]
            car.state = "Entregado"
            car.delivered_time = self.clock
        self.delivered += len(delivered_ids)
        self.trips[trip_id - 1]["completed"] = True
        context["delivered_now"] = len(delivered_ids)
        context["delivered_ids"] = delivered_ids
        context["trip_finished_id"] = trip_id

        destination = self.wagon_destination
        origin = self.wagon_origin
        self.wagon_state = "Libre"
        self.wagon_position = destination
        self.wagon_origin = None
        self.wagon_destination = None
        self.wagon_load = []
        self.wagon_trip_id = None
        self.wagon_departure = None
        self.wagon_arrival = None

        # Politica B: siempre vuelve a salir, aunque no haya autos.
        # Politica A: solo sale si en la nueva parada ya esperan 5 autos.
        if self.policy == "B" or self.queue_counts[destination] >= self.config.capacity:
            self._schedule_dispatch(self.clock)

        self._snapshot(
            "wagon_arrival",
            f"Fin traslado {trip_id}: P{origin} -> P{destination}",
            f"Descarga: {len(delivered_ids)} auto(s)",
            context,
        )

    def _process_dispatch(self) -> None:
        self.pending_dispatch_times.discard(self._clean_time(self.clock))
        # _start_trip realiza juntos los calculos de carga, duracion, ingreso,
        # costo y hora programada de llegada.
        trip = self._start_trip()
        if not trip:
            return
        context = self._event_context()
        context["loaded_now"] = trip["load_count"]
        context["loaded_ids"] = trip["car_ids"].copy()
        context["trip_started_id"] = trip["id"]
        qualifier = "vacío" if trip["load_count"] == 0 else f"con {trip['load_count']} auto(s)"
        self._snapshot(
            "dispatch",
            f"Inicio traslado {trip['id']}: P{trip['origin']} -> P{trip['destination']}",
            f"Sale {qualifier}; arribo previsto {trip['arrival_time']:.2f}",
            context,
        )

    def _process_abandonment(self, car_id: str) -> None:
        car = self.cars[car_id]
        # El evento puede seguir en el calendario aunque el auto ya haya sido
        # cargado. En ese caso no corresponde registrar una perdida.
        if car.state != "En cola":
            return
        stop = car.stop
        car.state = "Perdido"
        car.lost_time = self.clock
        # Espera del perdido = hora de abandono - hora de llegada.
        car.wait_time = self._clean_time(self.clock - car.arrival_time)
        self.queue_counts[stop] -= 1
        self.lost[stop] += 1
        # Acumuladores usados para la espera promedio de perdidos y el costo.
        self.wait_lost += car.wait_time
        self.loss_cost += self.config.loss_per_abandoned_car
        context = self._event_context()
        context[f"abandoned_now_p{stop}"] = 1
        context["abandoned_ids"] = [car_id]
        self._snapshot(
            "abandonment",
            f"Abandono {car_id} en P{stop}",
            f"Espera alcanzada: {car.wait_time:.2f} min",
            context,
        )

    def run(self) -> Dict[str, Any]:
        self.config.validate()
        # La primera llegada de cada parada se obtiene de la transformada
        # exponencial, no de un intervalo fijo ni de un lote de autos.
        for stop in (1, 2):
            if self.next_arrival[stop] <= self.config.horizon + EPSILON:
                self._schedule(self.next_arrival[stop], f"arrival_p{stop}")
        self._schedule(self.config.horizon, "horizon")

        self._snapshot(
            "initialization",
            "Inicialización",
            "Vagón libre en P1; colas vacías",
        )
        if self.policy == "B":
            # Criterio de inicializacion adoptado: la operacion continua de B
            # comienza en t=0. Como las colas estan vacias, el primer viaje es
            # vacio desde P1 hacia P2.
            self._schedule_dispatch(0.0)

        processed = 0
        while self.events:
            # Extrae siempre el evento con menor tiempo. Si hay empate, el heap
            # usa EVENT_PRIORITY: arribo del vagon, llegadas, despacho, abandono.
            time, _, _, kind, payload = heapq.heappop(self.events)
            if time > self.config.horizon + EPSILON:
                break
            # Las areas deben actualizarse antes de modificar colas o estados,
            # usando el estado que estuvo vigente desde el evento anterior.
            self._update_time_areas(time)
            self.clock = time
            if kind == "arrival_p1":
                self._process_arrival(1)
            elif kind == "arrival_p2":
                self._process_arrival(2)
            elif kind == "wagon_arrival":
                self._process_wagon_arrival(int(payload))
            elif kind == "dispatch":
                self._process_dispatch()
            elif kind == "abandonment":
                self._process_abandonment(str(payload))
            elif kind == "horizon":
                self._snapshot(
                    "horizon",
                    "Fin de simulación",
                    f"Horizonte de {self.config.horizon:g} minutos",
                )
                break
            processed += 1
            if processed > 1_000_000:
                raise RuntimeError("Se excedió el límite de eventos")

        return self._result()

    def _result(self) -> Dict[str, Any]:
        # Clasificacion final de autos para comprobar la conservacion:
        # llegados = entregados + en viaje + en cola + perdidos.
        waiting = sum(1 for car in self.cars.values() if car.state == "En cola")
        in_transit = sum(1 for car in self.cars.values() if car.state == "En viaje")
        boarded_total = self.boarded[1] + self.boarded[2]
        lost_total = self.lost[1] + self.lost[2]
        total_arrivals = self.arrived[1] + self.arrived[2]

        # Formulas economicas finales.
        net_result = self.revenue - self.operating_cost - self.loss_cost

        # Promedio de espera atendidos = suma de esperas / autos que subieron.
        avg_wait_boarded = self.wait_served / boarded_total if boarded_total else 0.0
        # Promedio de espera perdidos = suma de esperas / autos perdidos.
        avg_wait_lost = self.wait_lost / lost_total if lost_total else 0.0
        # Longitud promedio de cola = integral de la cola / horizonte.
        avg_queue_p1 = self.queue_area[1] / self.config.horizon
        avg_queue_p2 = self.queue_area[2] / self.config.horizon
        avg_queue_total = (self.queue_area[1] + self.queue_area[2]) / self.config.horizon
        # Utilizacion = minutos viajando / duracion total de la simulacion.
        wagon_utilization = self.wagon_busy_area / self.config.horizon
        # Tasa de perdida = autos perdidos / total de autos llegados.
        loss_rate = lost_total / total_arrivals if total_arrivals else 0.0

        summary = {
            "policy": self.policy,
            "policy_name": (
                f"Espera completar {self.config.capacity} autos"
                if self.policy == "A"
                else "Sale siempre al finalizar cada traslado"
            ),
            "arrivals_total": total_arrivals,
            "arrivals_p1": self.arrived[1],
            "arrivals_p2": self.arrived[2],
            "boarded_total": boarded_total,
            "boarded_p1": self.boarded[1],
            "boarded_p2": self.boarded[2],
            "delivered_total": self.delivered,
            "waiting_at_end": waiting,
            "in_transit_at_end": in_transit,
            "lost_total": lost_total,
            "lost_p1": self.lost[1],
            "lost_p2": self.lost[2],
            "trips_total": self.trip_count,
            "trips_loaded": self.loaded_trip_count,
            "trips_full": self.full_trip_count,
            "trips_empty": self.empty_trip_count,
            "revenue": self._clean_time(self.revenue),
            "operating_cost": self._clean_time(self.operating_cost),
            "loss_cost": self._clean_time(self.loss_cost),
            "net_result": self._clean_time(net_result),
            "avg_wait_boarded": self._clean_time(avg_wait_boarded),
            "avg_wait_lost": self._clean_time(avg_wait_lost),
            "avg_queue_p1": self._clean_time(avg_queue_p1),
            "avg_queue_p2": self._clean_time(avg_queue_p2),
            "avg_queue_total": self._clean_time(avg_queue_total),
            "max_queue_p1": self.max_queue[1],
            "max_queue_p2": self.max_queue[2],
            "wagon_utilization": self._clean_time(wagon_utilization),
            "loss_rate": self._clean_time(loss_rate),
            "event_rows": self.row_count,
        }
        cars = []
        if self.record_detail:
            for car in self.cars.values():
                item = asdict(car)
                # Para un auto que termina aun en cola, la espera visible es
                # horizonte - llegada. Para los demas ya fue fijada al subir o salir.
                item["current_wait"] = (
                    car.wait_time
                    if car.wait_time is not None
                    else self._clean_time(self.config.horizon - car.arrival_time)
                )
                item["system_time"] = (
                    self._clean_time(car.delivered_time - car.arrival_time)
                    if car.delivered_time is not None
                    else None
                )
                cars.append(item)
        return {
            "policy": self.policy,
            "summary": summary,
            "rows": self.rows,
            "cars": cars,
            "trips": self.trips if self.record_detail else [],
        }


def simulate(
    policy: str,
    config: Optional[SimulationConfig] = None,
    arrivals: Optional[Dict[int, List[ArrivalSample]]] = None,
    record_detail: bool = True,
) -> Dict[str, Any]:
    config = config or SimulationConfig()
    config.validate()
    if arrivals is None:
        arrivals = generate_arrivals(config, config.seed)
    return Simulation(policy, config, arrivals, record_detail).run()


def simulate_both(values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = SimulationConfig.from_mapping(values)
    results: Dict[str, Dict[str, Any]] = {}
    summaries: Dict[str, List[Dict[str, Any]]] = {"A": [], "B": []}
    paired_differences: List[float] = []
    winner_counts = {"A": 0, "B": 0, "tie": 0}

    for replication in range(config.replications):
        # Se reutiliza la misma trayectoria de llegadas en A y B. Asi, cada
        # diferencia de resultado depende de la politica y no de un sorteo
        # diferente de autos (numeros aleatorios comunes).
        arrivals = generate_arrivals(config, config.seed + replication)
        pair = {
            policy: simulate(policy, config, arrivals, record_detail=(replication == 0))
            for policy in ("A", "B")
        }
        if replication == 0:
            results = pair
        for policy in ("A", "B"):
            summaries[policy].append(pair[policy]["summary"])
        difference = pair["A"]["summary"]["net_result"] - pair["B"]["summary"]["net_result"]
        paired_differences.append(difference)
        winner_counts["A" if difference > 0 else "B" if difference < 0 else "tie"] += 1

    compared_metrics = (
        "arrivals_total", "boarded_total", "delivered_total", "lost_total",
        "trips_total", "trips_empty", "avg_wait_boarded", "avg_queue_total",
        "revenue", "operating_cost", "loss_cost", "net_result",
    )
    metrics = {
        key: {
            policy: round(statistics.fmean(item[key] for item in summaries[policy]), 9)
            for policy in ("A", "B")
        }
        for key in compared_metrics
    }
    mean_difference = statistics.fmean(paired_differences)
    ci95 = None
    if config.replications > 1:
        # IC normal aproximado del promedio de las diferencias pareadas A-B.
        margin = 1.96 * statistics.stdev(paired_differences) / math.sqrt(config.replications)
        ci95 = [round(mean_difference - margin, 9), round(mean_difference + margin, 9)]
    best = "A" if mean_difference > 0 else "B" if mean_difference < 0 else "Empate"
    confident = ci95 is not None and (ci95[0] > 0 or ci95[1] < 0)
    return {
        "config": asdict(config),
        "policies": results,
        "recommended_policy": best,
        "comparison": {
            "metrics": metrics,
            "net_difference_mean": round(mean_difference, 9),
            "net_difference_ci95": ci95,
            "recommendation_confident": confident,
            "winner_counts": winner_counts,
            "replications": config.replications,
            "sample_replication": 1,
        },
        "comparison_basis": "Mayor resultado neto promedio = ingresos - costos de traslados - pérdidas por abandono",
        "assumptions": [
            "Se interpreta '1 auto/min' y '3 autos/5 min' como tasas medias, no como llegadas exactas ni lotes simultáneos.",
            "Cada auto llega individualmente; el tiempo entre llegadas es exponencial negativa: T = -mu * ln(1 - RND), con mu = minutos/autos.",
            "Los RND, el reloj y los tiempos se muestran con dos decimales; el calendario de eventos usa nueve decimales y la generación exponencial usa la precisión de float.",
            "Cada réplica usa las mismas llegadas para A y B; la semilla permite reproducirlas.",
            "La tabla muestra la primera réplica; la comparación usa el promedio de todas las réplicas.",
            "Los autos se atienden FIFO en cada parada.",
            f"Un auto puede subir con {config.patience:g} minutos exactos de espera; si no sube, abandona en ese instante.",
            "En eventos simultáneos se procesa: arribo del vagón, llegadas de autos, despacho y abandono.",
            "La política B inicia en t=0 con un traslado vacío desde P1.",
            "Los eventos ocurridos exactamente en el minuto final se incluyen.",
            "El ingreso se registra al subir el auto y el costo al iniciar cada traslado, incluso si queda en viaje al cierre.",
        ],
    }


def compact_summary(result: Dict[str, Any]) -> Iterable[Tuple[str, Any, Any]]:
    """Ayuda de consola: produce promedios comparativos A/B."""
    metrics = result["comparison"]["metrics"]
    for key in (
        "arrivals_total",
        "boarded_total",
        "delivered_total",
        "lost_total",
        "trips_total",
        "trips_empty",
        "avg_wait_boarded",
        "avg_queue_total",
        "revenue",
        "operating_cost",
        "loss_cost",
        "net_result",
    ):
        yield key, metrics[key]["A"], metrics[key]["B"]


if __name__ == "__main__":
    comparison = simulate_both()
    print("Indicador\tPolítica A\tPolítica B")
    for metric, value_a, value_b in compact_summary(comparison):
        print(f"{metric}\t{value_a:.2f}\t{value_b:.2f}")
    print(f"Recomendación: política {comparison['recommended_policy']}")
