from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dashboard_extractor import (
    DATA_COLUMNS,
    DATA_START_ROW,
    DAY_COLUMNS,
    PREVIOUS_WEEK_COLUMNS,
    DashboardRecord,
    build_summary,
    canonical_data_column_for_duplicate_point,
    classify_background_bucket,
    is_effective_transparent_sheet_background,
    normalize_street,
    pending_day_source_from_rgb,
    write_records_csv,
    write_summary_json,
)


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

CANONICAL_COLORS = {
    "green": ((146, 208, 80), "collected", "unknown"),
    "orange": ((255, 192, 0), "pending", "supervisor"),
    "orange_alt": ((255, 153, 0), "pending", "supervisor"),
    "red": ((255, 0, 0), "pending", "veltio"),
}


def parse_spreadsheet_id(value: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]+", value):
        return value
    raise ValueError("Could not parse Google Sheets spreadsheet id.")


def parse_gid(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"[?&#]gid=(\d+)", value)
    if match:
        return int(match.group(1))
    if value.isdigit():
        return int(value)
    return None


def google_color_to_rgb(color: dict[str, Any] | None) -> tuple[int, int, int] | None:
    if not color:
        return None
    red = round(float(color.get("red", 0.0)) * 255)
    green = round(float(color.get("green", 0.0)) * 255)
    blue = round(float(color.get("blue", 0.0)) * 255)
    return red, green, blue


def rgb_to_hex(rgb: tuple[int, int, int] | None) -> str:
    if rgb is None:
        return ""
    return "FF" + "".join(f"{part:02X}" for part in rgb)


def classify_google_color(rgb: tuple[int, int, int] | None) -> tuple[str, str, str]:
    if rgb is None:
        return "unknown", "unknown", "missing_effective_format"

    best_name = ""
    best_distance = float("inf")
    best_status = "unknown"
    best_source = "unknown"

    for name, (canonical_rgb, status, source) in CANONICAL_COLORS.items():
        distance = math.sqrt(
            sum((current - canonical) ** 2 for current, canonical in zip(rgb, canonical_rgb))
        )
        if distance < best_distance:
            best_name = name
            best_distance = distance
            best_status = status
            best_source = source

    if best_distance <= 90:
        return best_status, best_source, f"effective_format_{best_name}"

    return "unknown", "unknown", "unmatched_effective_format"


def classify_row_value(
    *,
    point_id: int,
    column_number: int,
    value_counts: dict[int, int],
    rgb: tuple[int, int, int] | None,
    fg_rgb: tuple[int, int, int] | None = None,
) -> tuple[str, str, str]:
    """Το ταίριασμα ίδιου αριθμού σε >1 κελιά στην ίδια γραμμή ορίζει «συλλεχθέν».

    Η εξαγωγή CSV δέχεται μόνο **μία** εγγραφή ανά (σειρά, point_id)· τα υπόλοιπα κελιά με τον ίδιο αριθμό παραλείπονται,
    ώστε τα KPI να μετρούν +1 συλλεγμένο όχι +N κελιά.
    """
    if value_counts.get(point_id, 0) > 1:
        return "collected", "unknown", "same_row_numeric_match"

    if column_number in PREVIOUS_WEEK_COLUMNS:
        return "pending", "previous_weeks", "unmatched_previous_week_value"

    if column_number in DAY_COLUMNS:
        transparent_fill = rgb is None or is_effective_transparent_sheet_background(rgb)
        bg_tuple = None if transparent_fill else rgb
        bucket = classify_background_bucket(bg_tuple, transparent_fill=transparent_fill)
        if bucket == "green":
            return "pending", "unknown", "unmatched_day_green_fill"
        source, confidence = pending_day_source_from_rgb(
            bg_tuple,
            fg_rgb,
            transparent_fill=transparent_fill,
            font_theme_dark=False,
        )
        return "pending", source, confidence

    return "unknown", "unknown", "unclassified_numeric_value"


def numeric_cell_value(cell_data: dict[str, Any]) -> int | None:
    value = cell_data.get("userEnteredValue") or cell_data.get("effectiveValue") or {}
    if "numberValue" not in value:
        formatted_value = str(cell_data.get("formattedValue") or "").strip()
        if not re.fullmatch(r"\d+([,.]\d+)?", formatted_value):
            return None
        return int(float(formatted_value.replace(",", ".")))
    number = value["numberValue"]
    if isinstance(number, bool):
        return None
    return int(number)


def string_cell_value(cell_data: dict[str, Any]) -> str:
    value = cell_data.get("formattedValue")
    if value is not None:
        return str(value)
    entered = cell_data.get("userEnteredValue") or cell_data.get("effectiveValue") or {}
    if "stringValue" in entered:
        return str(entered["stringValue"])
    return ""


def effective_background_rgb(cell_data: dict[str, Any]) -> tuple[int, int, int] | None:
    effective_format = cell_data.get("effectiveFormat") or {}
    style = effective_format.get("backgroundColorStyle") or {}
    if "rgbColor" in style:
        return google_color_to_rgb(style["rgbColor"])
    return google_color_to_rgb(effective_format.get("backgroundColor"))


def effective_foreground_rgb(cell_data: dict[str, Any]) -> tuple[int, int, int] | None:
    effective_format = cell_data.get("effectiveFormat") or {}
    text_format = effective_format.get("textFormat") or {}
    return google_color_to_rgb(text_format.get("foregroundColor"))


def require_google_client() -> tuple[Any, Any]:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Missing Google API packages. Install them with: "
            "python -m pip install google-api-python-client google-auth"
        ) from exc
    return service_account, build


def build_service(credentials_path: Path) -> Any:
    service_account, build = require_google_client()
    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=credentials)


def sheet_title_for_gid(service: Any, spreadsheet_id: str, gid: int | None) -> str:
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    sheets = metadata.get("sheets", [])
    if not sheets:
        raise RuntimeError("Spreadsheet has no sheets.")

    if gid is None:
        return sheets[0]["properties"]["title"]

    for sheet in sheets:
        properties = sheet.get("properties", {})
        if properties.get("sheetId") == gid:
            return properties["title"]

    raise RuntimeError(f"No sheet found with gid/sheetId {gid}.")


def fetch_grid(service: Any, spreadsheet_id: str, sheet_title: str) -> dict[str, Any]:
    range_name = f"'{sheet_title}'!A1:L2000"
    return service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[range_name],
        includeGridData=True,
        fields=(
            "sheets(properties(title),data(rowData(values("
            "formattedValue,userEnteredValue,effectiveValue,"
            "effectiveFormat(backgroundColor,backgroundColorStyle,textFormat(foregroundColor))))))"
        ),
    ).execute()


def cell_at(rows: list[dict[str, Any]], row_index: int, column_index: int) -> dict[str, Any]:
    if row_index >= len(rows):
        return {}
    values = rows[row_index].get("values", [])
    if column_index >= len(values):
        return {}
    return values[column_index]


def extract_records_from_grid(
    spreadsheet_id: str,
    grid_response: dict[str, Any],
) -> list[DashboardRecord]:
    sheets = grid_response.get("sheets", [])
    if not sheets:
        return []

    sheet = sheets[0]
    sheet_title = sheet.get("properties", {}).get("title", "")
    rows = sheet.get("data", [{}])[0].get("rowData", [])
    week = string_cell_value(cell_at(rows, 1, 5))

    records: list[DashboardRecord] = []
    for row_number in range(DATA_START_ROW, len(rows) + 1):
        row_index = row_number - 1
        street = string_cell_value(cell_at(rows, row_index, 1))
        normalized = normalize_street(street)
        if not normalized:
            continue

        row_values = {
            column_number: numeric_cell_value(cell_at(rows, row_index, column_number - 1))
            for column_number in DATA_COLUMNS
        }
        value_counts: dict[int, int] = {}
        for value in row_values.values():
            if value is not None:
                value_counts[value] = value_counts.get(value, 0) + 1

        for column_number in DATA_COLUMNS:
            column_index = column_number - 1
            cell_data = cell_at(rows, row_index, column_index)
            point_id = row_values[column_number]
            if point_id is None:
                continue

            header = string_cell_value(cell_at(rows, 4, column_index)) or string_cell_value(cell_at(rows, 5, column_index))
            day = header if column_number in DAY_COLUMNS else ""
            rgb = effective_background_rgb(cell_data)
            fg_rgb = effective_foreground_rgb(cell_data)

            canon = canonical_data_column_for_duplicate_point(
                row_values, point_id, value_counts=value_counts
            )
            if canon is not None and column_number != canon:
                continue

            status, source, confidence = classify_row_value(
                point_id=point_id,
                column_number=column_number,
                value_counts=value_counts,
                rgb=rgb,
                fg_rgb=fg_rgb,
            )

            records.append(
                DashboardRecord(
                    workbook=spreadsheet_id,
                    sheet=sheet_title,
                    week_label=week,
                    row=row_number,
                    column=f"R{row_number}C{column_number}",
                    street=street.strip(),
                    street_normalized=normalized,
                    period=header.strip(),
                    day=day.strip(),
                    point_id=point_id,
                    status=status,
                    source=source,
                    color=rgb_to_hex(rgb),
                    confidence=confidence,
                    note="from_google_sheets_effective_format",
                )
            )

    return records


def run(
    spreadsheet_or_url: str,
    credentials_path: Path,
    output_dir: Path,
    gid_or_url: str | None = None,
) -> dict[str, Any]:
    spreadsheet_id = parse_spreadsheet_id(spreadsheet_or_url)
    gid = parse_gid(gid_or_url or spreadsheet_or_url)
    service = build_service(credentials_path)
    try:
        sheet_title = sheet_title_for_gid(service, spreadsheet_id, gid)
        grid = fetch_grid(service, spreadsheet_id, sheet_title)
    except Exception as exc:
        message = str(exc)
        if "must not be an Office file" in message:
            raise RuntimeError(
                "Google Sheets API cannot read effective formats from an Office/XLSX file. "
                "Open the file in Google Drive and convert it to a native Google Sheet first: "
                "File -> Save as Google Sheets. Then update run_google_extraction.cmd with the new native Sheet URL."
            ) from exc
        raise
    records = extract_records_from_grid(spreadsheet_id, grid)
    warnings = []
    unknown_sources = sum(1 for record in records if record.status == "pending" and record.source == "unknown")
    if unknown_sources:
        warnings.append(f"{unknown_sources} pending records had an unrecognized effective background color.")

    summary = build_summary(Path(spreadsheet_id), records, warnings)
    write_records_csv(records, output_dir / "google_dashboard_records.csv")
    write_summary_json(summary, output_dir / "google_dashboard_summary.json")
    return asdict(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract dashboard data directly from Google Sheets effective formats.")
    parser.add_argument("--spreadsheet", required=True, help="Google Sheets URL or spreadsheet id.")
    parser.add_argument("--credentials", required=True, type=Path, help="Service account JSON credentials path.")
    parser.add_argument("--gid", default=None, help="Optional gid/sheetId or URL containing gid.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Directory for CSV/JSON exports.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run(
        spreadsheet_or_url=args.spreadsheet,
        credentials_path=args.credentials.resolve(),
        output_dir=args.output_dir.resolve(),
        gid_or_url=args.gid,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
