from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


RECORD_FIELDS = [
    "workbook",
    "sheet",
    "week_label",
    "row",
    "column",
    "street",
    "street_normalized",
    "period",
    "day",
    "point_id",
    "status",
    "source",
    "color",
    "confidence",
    "note",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in RECORD_FIELDS})


def record_key(record: dict[str, str]) -> tuple[str, str]:
    return (
        (record.get("street_normalized") or record.get("street") or "").strip().upper(),
        str(record.get("point_id") or "").strip(),
    )


def mark_origin(record: dict[str, str], origin: str) -> dict[str, str]:
    updated = dict(record)
    note = updated.get("note", "")
    updated["note"] = f"{note}; origin={origin}".strip("; ")
    return updated


def merge_records(
    google_records: list[dict[str, str]],
    excel_records: list[dict[str, str]],
) -> list[dict[str, str]]:
    google_pending = [
        mark_origin(record, "google_pending")
        for record in google_records
        if record.get("status") == "pending"
    ]
    google_collected = [
        mark_origin(record, "google_collected")
        for record in google_records
        if record.get("status") == "collected"
    ]
    active_pending_keys = {record_key(record) for record in google_pending}
    google_collected_keys = {record_key(record) for record in google_collected}

    excel_collected = []
    for record in excel_records:
        if record.get("status") != "collected":
            continue
        if record_key(record) in active_pending_keys:
            continue
        if record_key(record) in google_collected_keys:
            continue
        excel_collected.append(mark_origin(record, "excel_collected_history"))

    return google_pending + google_collected + excel_collected


def week_status_for_pending(pending_count: int) -> str:
    if pending_count <= 100:
        return "excellent"
    if pending_count < 300:
        return "good"
    return "red"


def build_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    pending = [row for row in rows if row.get("status") == "pending"]
    collected = [row for row in rows if row.get("status") == "collected"]
    unknown = [row for row in rows if row.get("status") == "unknown"]

    collected_by_day = Counter(row.get("day") for row in collected if row.get("day"))
    resolved_previous = sum(
        1
        for row in collected
        if not row.get("day") and (row.get("period") or "").startswith("ΕΚΚΡΕΜΟΤΗΤΕΣ")
    )
    pending_by_day = Counter(row.get("day") or row.get("period") for row in pending if row.get("day") or row.get("period"))
    pending_by_source = Counter(row.get("source") or "unknown" for row in pending)
    pending_previous_weeks = sum(1 for row in pending if row.get("source") == "previous_weeks")
    top_pending = Counter(row.get("street_normalized") or row.get("street") for row in pending).most_common(15)

    first = rows[0] if rows else {}
    return {
        "workbook": first.get("workbook", ""),
        "sheet": first.get("sheet", ""),
        "week_label": first.get("week_label", ""),
        "data_mode": "hybrid_google_pending_excel_collected",
        "total_records": len(rows),
        "pending": len(pending),
        "collected": len(collected),
        "unknown_status": len(unknown),
        "pending_by_source": dict(sorted(pending_by_source.items())),
        "pending_previous_weeks": pending_previous_weeks,
        "collected_by_day": dict(sorted(collected_by_day.items())),
        "resolved_previous_week_records": resolved_previous,
        "pending_by_day": dict(sorted(pending_by_day.items())),
        "top_pending_streets": [
            {"street": street, "pending": count}
            for street, count in top_pending
        ],
        "week_status": week_status_for_pending(len(pending)),
        "extraction_warnings": [],
    }


def run_hybrid(output_dir: Path) -> dict[str, Any]:
    google_records = load_csv(output_dir / "google_dashboard_records.csv")
    excel_records = load_csv(output_dir / "dashboard_records.csv")
    rows = merge_records(google_records, excel_records)
    summary = build_summary(rows)

    write_csv(rows, output_dir / "hybrid_dashboard_records.csv")
    (output_dir / "hybrid_dashboard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine Google pending records with Excel inferred collected history.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_hybrid(args.output_dir.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
