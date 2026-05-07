import unittest

from google_sheets_extractor import (
    classify_row_value,
    classify_google_color,
    google_color_to_rgb,
    numeric_cell_value,
    parse_gid,
    parse_spreadsheet_id,
    rgb_to_hex,
)


class GoogleSheetsExtractorTests(unittest.TestCase):
    def test_parse_spreadsheet_id_from_url(self) -> None:
        url = "https://docs.google.com/spreadsheets/d/1ZobtO6S0n2ogpKobVkRHR6vdldqIiNdk/edit?gid=1505732445"
        self.assertEqual(parse_spreadsheet_id(url), "1ZobtO6S0n2ogpKobVkRHR6vdldqIiNdk")

    def test_parse_gid_from_url(self) -> None:
        url = "https://docs.google.com/spreadsheets/d/abc/edit?gid=1505732445#gid=1505732445"
        self.assertEqual(parse_gid(url), 1505732445)

    def test_google_color_to_rgb_converts_fractional_channels(self) -> None:
        self.assertEqual(google_color_to_rgb({"red": 1, "green": 0.6, "blue": 0}), (255, 153, 0))

    def test_numeric_cell_value_reads_formatted_numeric_text(self) -> None:
        self.assertEqual(numeric_cell_value({"formattedValue": "168"}), 168)

    def test_rgb_to_hex_returns_argb_hex(self) -> None:
        self.assertEqual(rgb_to_hex((255, 153, 0)), "FFFF9900")

    def test_classify_red_as_pending_veltio(self) -> None:
        self.assertEqual(classify_google_color((255, 0, 0))[:2], ("pending", "veltio"))

    def test_classify_orange_as_pending_supervisor(self) -> None:
        self.assertEqual(classify_google_color((255, 192, 0))[:2], ("pending", "supervisor"))

    def test_classify_green_as_collected(self) -> None:
        self.assertEqual(classify_google_color((146, 208, 80))[:2], ("collected", "unknown"))

    def test_same_row_match_is_collected_even_without_green_color(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=7,
            column_number=5,
            value_counts={7: 2},
            rgb=(255, 192, 0),
        )

        self.assertEqual((status, source, confidence), ("collected", "unknown", "same_row_numeric_match"))

    def test_unmatched_day_value_keeps_orange_as_supervisor_pending(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=2,
            column_number=7,
            value_counts={2: 1},
            rgb=(255, 192, 0),
        )

        self.assertEqual((status, source), ("pending", "supervisor"))
        self.assertEqual(confidence, "pending_day_orange_fill_default_supervisor")

    def test_unmatched_day_orange_background_red_foreground_is_veltio(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=2,
            column_number=7,
            value_counts={2: 1},
            rgb=(255, 192, 0),
            fg_rgb=(255, 0, 0),
        )

        self.assertEqual((status, source), ("pending", "veltio"))
        self.assertEqual(confidence, "pending_day_orange_fill_red_font")

    def test_unmatched_day_orange_background_black_foreground_is_supervisor(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=2,
            column_number=7,
            value_counts={2: 1},
            rgb=(255, 192, 0),
            fg_rgb=(0, 0, 0),
        )

        self.assertEqual((status, source), ("pending", "supervisor"))
        self.assertEqual(confidence, "pending_day_orange_fill_dark_font")

    def test_unmatched_day_value_keeps_red_as_veltio_pending(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=2,
            column_number=7,
            value_counts={2: 1},
            rgb=(255, 0, 0),
        )

        self.assertEqual((status, source), ("pending", "veltio"))
        self.assertEqual(confidence, "pending_day_red_fill")

    def test_unmatched_previous_week_value_is_pending_previous_weeks(self) -> None:
        status, source, confidence = classify_row_value(
            point_id=12,
            column_number=5,
            value_counts={12: 1},
            rgb=(194, 162, 24),
        )

        self.assertEqual((status, source, confidence), ("pending", "previous_weeks", "unmatched_previous_week_value"))


if __name__ == "__main__":
    unittest.main()
