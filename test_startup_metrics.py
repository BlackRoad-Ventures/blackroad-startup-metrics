"""Tests for BlackRoad Startup Metrics."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["STARTUP_DB"] = str(Path(tempfile.mkdtemp()) / "test_startup.db")
sys.path.insert(0, str(Path(__file__).parent))
from main import StartupMetricsService, init_db


class TestStartupMetrics(unittest.TestCase):
    def setUp(self):
        init_db()
        self.svc = StartupMetricsService()
        self.startup = self.svc.create_startup("TestCorp", stage="series_a")

    def test_create_startup(self):
        s = self.svc.create_startup("AnotherCorp")
        self.assertIsNotNone(s.id)
        self.assertEqual(s.name, "AnotherCorp")

    def test_mrr_calculation(self):
        self.svc.add_customer(self.startup.id, "Customer A", mrr=500.0)
        self.svc.add_customer(self.startup.id, "Customer B", mrr=300.0)
        mrr = self.svc.calculate_mrr(self.startup.id)
        self.assertAlmostEqual(mrr, 800.0)

    def test_arr_is_12x_mrr(self):
        self.svc.add_customer(self.startup.id, "Annual Customer", mrr=1000.0)
        mrr = self.svc.calculate_mrr(self.startup.id)
        arr = self.svc.calculate_arr(self.startup.id)
        self.assertAlmostEqual(arr, mrr * 12)

    def test_churn_rate(self):
        c = self.svc.add_customer(self.startup.id, "Soon Gone", mrr=200.0)
        self.svc.churn_customer(c["id"])
        result = self.svc.calculate_churn_rate(self.startup.id)
        self.assertIn("churn_rate_pct", result)

    def test_runway(self):
        self.svc.add_funding(self.startup.id, "Seed", 500_000.0)
        result = self.svc.calculate_runway(self.startup.id, monthly_burn=50_000.0)
        self.assertIn("runway_months", result)
        self.assertGreater(result["runway_months"], 0)

    def test_headcount(self):
        self.svc.add_employee(self.startup.id, "Alice", "Engineer", department="eng", salary=120_000)
        self.svc.add_employee(self.startup.id, "Bob", "Designer", department="design", salary=100_000)
        hc = self.svc.headcount(self.startup.id)
        self.assertEqual(hc["total_headcount"], 2)
        self.assertAlmostEqual(hc["total_salary_cost"], 220_000.0)

    def test_kpi_dashboard(self):
        self.svc.add_customer(self.startup.id, "Cust", mrr=1000.0)
        dash = self.svc.kpi_dashboard(self.startup.id, monthly_burn=5000.0)
        self.assertIn("mrr", dash)
        self.assertIn("arr", dash)
        self.assertIn("headcount", dash)


if __name__ == "__main__":
    unittest.main()
