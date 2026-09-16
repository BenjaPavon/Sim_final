import unittest

from simulation import SimulationConfig, simulate, simulate_both


class DefaultScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = simulate_both()

    def test_default_totals_and_recommendation(self):
        self.assertEqual(self.result["recommended_policy"], "A")
        summary_a = self.result["policies"]["A"]["summary"]
        summary_b = self.result["policies"]["B"]["summary"]
        self.assertEqual(summary_a["arrivals_total"], 768)
        self.assertEqual(summary_b["arrivals_total"], 768)
        self.assertEqual(summary_a["net_result"], 112.0)
        self.assertEqual(summary_b["net_result"], 96.0)

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
            self.assertTrue(all(car["wait_time"] <= patience for car in served))
            self.assertTrue(all(car["wait_time"] == patience for car in lost))
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


class TieBreakingTests(unittest.TestCase):
    def test_car_can_board_at_exact_patience_limit(self):
        config = SimulationConfig(
            horizon=3,
            capacity=2,
            arrival_interval_p1=1,
            arrival_batch_p1=1,
            arrival_interval_p2=100,
            arrival_batch_p2=1,
            loaded_trip_time=5,
            empty_trip_time=3,
            patience=1,
        )
        result = simulate("A", config)
        first = result["cars"][0]
        self.assertEqual(first["id"], "P1-0001")
        self.assertEqual(first["board_time"], 2.0)
        self.assertEqual(first["wait_time"], 1.0)
        self.assertNotEqual(first["state"], "Perdido")

    def test_policy_b_starts_empty_at_zero(self):
        result = simulate("B", SimulationConfig(horizon=4))
        first_trip = result["trips"][0]
        self.assertEqual(first_trip["departure_time"], 0.0)
        self.assertEqual(first_trip["origin"], 1)
        self.assertEqual(first_trip["destination"], 2)
        self.assertEqual(first_trip["load_count"], 0)
        self.assertEqual(first_trip["arrival_time"], 3.0)


if __name__ == "__main__":
    unittest.main()
