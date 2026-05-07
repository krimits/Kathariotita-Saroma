import unittest

from dashboard_stats import (
    build_stats_payload,
    build_weekly_report,
    compute_daily_series,
    compute_street_metrics,
    monthly_aggregate_from_snapshots,
    weekly_trend_from_snapshots,
)


class DashboardStatsTests(unittest.TestCase):
    def test_compute_daily_series_empty(self) -> None:
        daily = compute_daily_series([])
        self.assertEqual(daily["series"], [])
        self.assertEqual(daily["ratio_stats"]["sample_days"], 0)

    def test_compute_daily_series_ratio_and_mean(self) -> None:
        records = [
            {"day": "ΔΕΥΤΕΡΑ", "status": "pending", "street_normalized": "Α"},
            {"day": "ΔΕΥΤΕΡΑ", "status": "collected", "street_normalized": "Α"},
            {"day": "ΤΡΙΤΗ", "status": "collected", "street_normalized": "Β"},
            {"day": "ΤΡΙΤΗ", "status": "collected", "street_normalized": "Β"},
        ]
        daily = compute_daily_series(records)
        mon = next(r for r in daily["series"] if r["day"] == "ΔΕΥΤΕΡΑ")
        tue = next(r for r in daily["series"] if r["day"] == "ΤΡΙΤΗ")
        self.assertEqual(mon["ratio_collected"], 0.5)
        self.assertEqual(tue["ratio_collected"], 1.0)
        rs = daily["ratio_stats"]
        self.assertEqual(rs["sample_days"], 2)
        self.assertIsNotNone(rs["ratio_mean"])

    def test_weekly_and_monthly_from_snapshots(self) -> None:
        snaps = [
            {
                "week_label": "49 / 2025",
                "extracted_at_utc": "2025-12-01T10:00:00+00:00",
                "pending": 100,
                "collected": 50,
                "pending_by_day": {},
                "collected_by_day": {},
            },
            {
                "week_label": "50 / 2025",
                "extracted_at_utc": "2025-12-08T10:00:00+00:00",
                "pending": 80,
                "collected": 70,
                "pending_by_day": {},
                "collected_by_day": {},
            },
        ]
        wt = weekly_trend_from_snapshots(snaps)
        self.assertEqual(len(wt["labels"]), 2)
        self.assertEqual(wt["pending"], [100, 80])

        mo = monthly_aggregate_from_snapshots(snaps)
        self.assertIn("2025-12", mo["labels"])
        idx = mo["labels"].index("2025-12")
        self.assertGreater(mo["pending_avg"][idx], 0)
        self.assertGreater(mo["collected_avg"][idx], 0)

    def test_build_stats_payload_includes_report(self) -> None:
        summary = {"week_label": "Τρέχουσα", "pending": 10, "collected": 5}
        records = [
            {"day": "ΔΕΥΤΕΡΑ", "status": "pending", "street_normalized": "ΟΔΟΣΑ"},
            {"day": "ΔΕΥΤΕΡΑ", "status": "collected", "street_normalized": "ΟΔΟΣΑ"},
        ]
        payload = build_stats_payload(summary, records, [])
        self.assertIn("weekly_report", payload)
        self.assertTrue(payload["weekly_report"])
        self.assertEqual(payload["totals"]["pending"], 10)
        streets = compute_street_metrics(records)
        report = build_weekly_report("Τρέχουσα", payload["daily"], streets, [])
        self.assertIn("Εβδομαδιαία ανασκόπηση", report)


if __name__ == "__main__":
    unittest.main()
