import unittest

from dashboard_hybrid import build_summary, merge_records, record_key


class DashboardHybridTests(unittest.TestCase):
    def test_record_key_uses_normalized_street_and_point_id(self) -> None:
        record = {"street_normalized": "ΑΙΓΑΙΟΥ", "point_id": "2"}
        self.assertEqual(record_key(record), ("ΑΙΓΑΙΟΥ", "2"))

    def test_merge_keeps_google_pending_and_excel_collected_history(self) -> None:
        google_records = [
            {
                "street_normalized": "ΑΙΓΑΙΟΥ",
                "street": "ΑΙΓΑΙΟΥ",
                "point_id": "2",
                "status": "pending",
                "source": "supervisor",
            }
        ]
        excel_records = [
            {
                "street_normalized": "ΚΡΗΤΗΣ",
                "street": "ΚΡΗΤΗΣ",
                "point_id": "8",
                "status": "collected",
                "source": "unknown",
                "day": "ΔΕΥΤΕΡΑ",
            }
        ]

        merged = merge_records(google_records, excel_records)

        self.assertEqual([record["status"] for record in merged], ["pending", "collected"])

    def test_merge_drops_excel_collected_when_same_point_is_pending_again(self) -> None:
        google_records = [{"street_normalized": "ΑΙΓΑΙΟΥ", "point_id": "2", "status": "pending"}]
        excel_records = [{"street_normalized": "ΑΙΓΑΙΟΥ", "point_id": "2", "status": "collected"}]

        merged = merge_records(google_records, excel_records)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["status"], "pending")

    def test_merge_keeps_google_collected_and_drops_duplicate_excel_history(self) -> None:
        google_records = [{"street_normalized": "ΑΙΓΑΙΟΥ", "point_id": "2", "status": "collected"}]
        excel_records = [{"street_normalized": "ΑΙΓΑΙΟΥ", "point_id": "2", "status": "collected"}]

        merged = merge_records(google_records, excel_records)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["status"], "collected")
        self.assertIn("google_collected", merged[0]["note"])

    def test_build_summary_counts_hybrid_records(self) -> None:
        rows = [
            {"status": "pending", "source": "supervisor", "day": "ΤΡΙΤΗ", "street_normalized": "ΑΙΓΑΙΟΥ"},
            {
                "status": "pending",
                "source": "previous_weeks",
                "period": "ΕΚΚΡΕΜΟΤΗΤΕΣ ΠΡΟΗΓΟΥΜΕΝΩΝ ΕΒΔΟΜΑΔΩΝ 1Η",
                "street_normalized": "ΝΕΑΠΟΛΗ",
            },
            {"status": "collected", "source": "unknown", "day": "ΔΕΥΤΕΡΑ", "street_normalized": "ΚΡΗΤΗΣ"},
        ]

        summary = build_summary(rows)

        self.assertEqual(summary["pending"], 2)
        self.assertEqual(summary["pending_previous_weeks"], 1)
        self.assertEqual(summary["collected"], 1)
        self.assertEqual(summary["pending_by_source"], {"previous_weeks": 1, "supervisor": 1})
        self.assertEqual(summary["collected_by_day"], {"ΔΕΥΤΕΡΑ": 1})


if __name__ == "__main__":
    unittest.main()
