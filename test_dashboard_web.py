import unittest
from pathlib import Path

from dashboard_web import filter_records, first_existing, record_matches


class DashboardWebTests(unittest.TestCase):
    def test_first_existing_uses_first_available_file(self) -> None:
        folder = Path(__file__).resolve().parent / "test_output"
        folder.mkdir(exist_ok=True)
        path = folder / "second.json"
        try:
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(first_existing(folder, ("first.json", "second.json")).name, "second.json")
        finally:
            if path.exists():
                path.unlink()
            if folder.exists():
                folder.rmdir()

    def test_record_matches_status_source_day_and_street(self) -> None:
        record = {
            "status": "pending",
            "source": "supervisor",
            "day": "ΤΡΙΤΗ",
            "period": "ΤΡΙΤΗ",
            "street_normalized": "ΑΙΓΑΙΟΥ",
        }

        self.assertTrue(record_matches(record, "PENDING", "SUPERVISOR", "ΤΡΙΤΗ", "ΑΙΓ"))
        self.assertFalse(record_matches(record, "COLLECTED", "SUPERVISOR", "ΤΡΙΤΗ", "ΑΙΓ"))

    def test_filter_records_keeps_matching_records(self) -> None:
        records = [
            {"status": "pending", "source": "unknown", "day": "ΤΡΙΤΗ", "street_normalized": "ΑΙΓΑΙΟΥ"},
            {"status": "collected", "source": "unknown", "day": "ΔΕΥΤΕΡΑ", "street_normalized": "ΚΡΗΤΗΣ"},
        ]

        result = filter_records(records, status="pending", street="αιγ")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["street_normalized"], "ΑΙΓΑΙΟΥ")


if __name__ == "__main__":
    unittest.main()
