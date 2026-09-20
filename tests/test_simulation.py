import math
import unittest
from dataclasses import asdict

from simulation import ArrivalSample, SimulationConfig, generate_arrivals, simulate, simulate_both


class ArrivalGenerationTests(unittest.TestCase):
    def test_exponential_inverse_transform_and_individual_arrivals(self):
        config = SimulationConfig(horizon=40, replications=1, seed=7)
        paths = generate_arrivals(config, config.seed)
        for stop, mean in ((1, 1.0), (2, 5.0 / 3.0)):
            previous_time = 0.0
            for sample in paths[stop]:
                self.assertGreater(sample.time, previous_time)
                self.assertGreaterEqual(sample.rnd, 0.0)
                self.assertLess(sample.rnd, 1.0)
                self.assertAlmostEqual(
                    sample.interarrival, -mean * math.log1p(-sample.rnd), places=10
                )
                self.assertAlmostEqual(
                    sample.time - previous_time, sample.interarrival, places=10
                )
                previous_time = sample.time
            self.assertGreater(paths[stop][-1].time, config.horizon)

    def test_seed_reproduces_both_arrival_streams(self):
        config = SimulationConfig(horizon=40, replications=1, seed=7)
        self.assertEqual(generate_arrivals(config, 7), generate_arrivals(config, 7))
        self.assertNotEqual(generate_arrivals(config, 7), generate_arrivals(config, 8))

    def test_config_rates_match_statement(self):
        config = SimulationConfig()
        self.assertEqual(config.arrival_count_p1 / config.arrival_window_p1, 1.0)
        self.assertEqual(config.arrival_count_p2 / config.arrival_window_p2, 0.6)

    def test_invalid_nonfinite_and_fractional_inputs_are_rejected(self):
        for values in (
            {"arrival_window_p2": float("nan")},
            {"arrival_count_p1": float("inf")},
            {"replications": 2.5},
            {"seed": "3.5"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                SimulationConfig.from_mapping(values)

    def test_single_replication_has_no_confidence_interval(self):
        result = simulate_both({"horizon": 20, "replications": 1, "seed": 7})
        self.assertIsNone(result["comparison"]["net_difference_ci95"])
        self.assertFalse(result["comparison"]["recommendation_confident"])


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = SimulationConfig(seed=12345, replications=12)
        cls.result = simulate_both(asdict(cls.config))

    def test_policies_receive_exactly_the_same_individual_arrivals(self):
        arrivals = {}
        for policy in ("A", "B"):
            arrivals[policy] = [
                (car["id"], car["stop"], car["arrival_time"])
                for car in self.result["policies"][policy]["cars"]
            ]
        self.assertEqual(arrivals["A"], arrivals["B"])
        self.assertTrue(all(row["arrivals_now_p2"] <= 1 for row in self.result["policies"]["A"]["rows"]))

    def test_initial_row_exposes_rnd_time_and_next_arrival(self):
        row = self.result["policies"]["A"]["rows"][0]
        self.assertEqual(row["event_type"], "initialization")
        self.assertAlmostEqual(row["interarrival_p1"], -math.log1p(-row["arrival_rnd_p1"]))
        self.assertAlmostEqual(
            row["interarrival_p2"], -(5 / 3) * math.log1p(-row["arrival_rnd_p2"])
        )
        self.assertAlmostEqual(row["next_arrival_p1"], row["interarrival_p1"])
        self.assertAlmostEqual(row["next_arrival_p2"], row["interarrival_p2"])

    def test_flow_conservation(self):
        for policy in ("A", "B"):
            summary = self.result["policies"][policy]["summary"]
            accounted = (
                summary["delivered_total"]
                + summary["in_transit_at_end"]
                + summary["waiting_at_end"]
                + summary["lost_total"]
            )
            self.assertEqual(summary["arrivals_total"], accounted)
            self.assertEqual(
                summary["boarded_total"],
                summary["delivered_total"] + summary["in_transit_at_end"],
            )

    def test_economic_identity(self):
        config = self.result["config"]
        for policy in ("A", "B"):
            summary = self.result["policies"][policy]["summary"]
            self.assertEqual(summary["revenue"], summary["boarded_total"] * config["fare_per_car"])
            self.assertEqual(summary["operating_cost"], summary["trips_total"] * config["cost_per_trip"])
            self.assertEqual(summary["loss_cost"], summary["lost_total"] * config["loss_per_abandoned_car"])
            self.assertEqual(
                summary["net_result"],
                summary["revenue"] - summary["operating_cost"] - summary["loss_cost"],
            )

    def test_policy_a_only_leaves_full(self):
        policy_a = self.result["policies"]["A"]
        self.assertEqual(policy_a["summary"]["trips_empty"], 0)
        self.assertTrue(all(trip["load_count"] == 5 for trip in policy_a["trips"]))

    def test_waiting_limits_and_fifo(self):
        patience = self.result["config"]["patience"]
        for policy in ("A", "B"):
            cars = self.result["policies"][policy]["cars"]
            served = [car for car in cars if car["board_time"] is not None]
            lost = [car for car in cars if car["state"] == "Perdido"]
            self.assertTrue(all(car["wait_time"] <= patience + 1e-9 for car in served))
            self.assertTrue(all(abs(car["wait_time"] - patience) < 1e-8 for car in lost))
            for stop in (1, 2):
                boarded = [car for car in served if car["stop"] == stop]
                arrivals = [car["arrival_time"] for car in boarded]
                self.assertEqual(arrivals, sorted(arrivals))

    def test_rows_are_chronological_and_end_at_horizon(self):
        for policy in ("A", "B"):
            rows = self.result["policies"][policy]["rows"]
            times = [row["time"] for row in rows]
            self.assertEqual(times, sorted(times))
            self.assertEqual(rows[-1]["event_type"], "horizon")
            self.assertEqual(rows[-1]["time"], 480.0)

    def test_comparison_uses_replicate_averages(self):
        comparison = self.result["comparison"]
        self.assertEqual(comparison["replications"], self.config.replications)
        self.assertEqual(sum(comparison["winner_counts"].values()), self.config.replications)
        mean_a = comparison["metrics"]["net_result"]["A"]
        mean_b = comparison["metrics"]["net_result"]["B"]
        self.assertAlmostEqual(mean_a - mean_b, comparison["net_difference_mean"])
        self.assertEqual(len(comparison["net_difference_ci95"]), 2)


class TieBreakingTests(unittest.TestCase):
    def test_car_can_board_at_exact_patience_limit(self):
        config = SimulationConfig(
            horizon=3,
            capacity=2,
            arrival_count_p1=1,
            arrival_window_p1=1,
            arrival_count_p2=1,
            arrival_window_p2=100,
            patience=1,
            replications=1,
        )
        # Trayectoria controlada: el segundo auto llega al mismo tiempo en que
        # vence la paciencia del primero. El despacho precede al abandono.
        arrivals = {
            1: [
                ArrivalSample(1.0, 1 - math.exp(-1), 1.0),
                ArrivalSample(2.0, 1 - math.exp(-1), 1.0),
                ArrivalSample(4.0, 1 - math.exp(-2), 2.0),
            ],
            2: [ArrivalSample(100.0, 1 - math.exp(-1), 100.0)],
        }
        result = simulate("A", config, arrivals)
        first = result["cars"][0]
        self.assertEqual(first["id"], "P1-0001")
        self.assertEqual(first["board_time"], 2.0)
        self.assertEqual(first["wait_time"], 1.0)
        self.assertNotEqual(first["state"], "Perdido")

    def test_policy_b_starts_empty_at_zero(self):
        result = simulate("B", SimulationConfig(horizon=4, replications=1))
        first_trip = result["trips"][0]
        self.assertEqual(first_trip["departure_time"], 0.0)
        self.assertEqual(first_trip["origin"], 1)
        self.assertEqual(first_trip["destination"], 2)
        self.assertEqual(first_trip["load_count"], 0)
        self.assertEqual(first_trip["arrival_time"], 3.0)


if __name__ == "__main__":
    unittest.main()
