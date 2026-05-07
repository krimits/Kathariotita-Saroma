from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard_extractor import build_summary as build_google_summary
from dashboard_hybrid import run_hybrid
from google_sheets_extractor import extract_records_from_grid
from google_sheets_extractor import build_service, fetch_grid, parse_gid, parse_spreadsheet_id, sheet_title_for_gid


DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8001"
DEFAULT_SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1Y1lvKhBIEEh5AceA580jSTXlB3ms5AwX5Mo5RC9b5wM/edit?gid=1505732445#gid=1505732445"
)


def read_json_url(url: str, method: str = "GET") -> dict[str, Any]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_expected_google_summary(spreadsheet_url: str, credentials_path: Path) -> dict[str, Any]:
    service = build_service(credentials_path)
    spreadsheet_id = parse_spreadsheet_id(spreadsheet_url)
    sheet_title = sheet_title_for_gid(service, spreadsheet_id, parse_gid(spreadsheet_url))
    grid = fetch_grid(service, spreadsheet_id, sheet_title)
    records = extract_records_from_grid(spreadsheet_id, grid)
    return asdict(build_google_summary(Path(spreadsheet_id), records, []))


def compare_values(label: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "label": label,
        "expected": expected,
        "actual": actual,
        "ok": expected == actual,
    }


def _int_or_zero(value: Any) -> int:
    return 0 if value is None else int(value)


def _snapshot_age_seconds(extracted_at_utc: str | None) -> float | None:
    if not extracted_at_utc:
        return None
    try:
        dt = datetime.fromisoformat(extracted_at_utc.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except ValueError:
        return None


def verify(
    dashboard_url: str,
    spreadsheet_url: str,
    credentials_path: Path,
    output_dir: Path,
    *,
    mode: str,
    max_snapshot_age_seconds: float | None,
    max_refresh_roundtrip_seconds: float | None,
) -> dict[str, Any]:
    expected_google = fetch_expected_google_summary(spreadsheet_url, credentials_path)

    t_request = time.perf_counter()
    try:
        refresh_result = read_json_url(f"{dashboard_url.rstrip('/')}/api/refresh", method="POST")
        dashboard_summary = read_json_url(f"{dashboard_url.rstrip('/')}/api/summary")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Dashboard is not reachable at {dashboard_url}") from exc
    refresh_roundtrip_seconds = time.perf_counter() - t_request

    hybrid_summary = run_hybrid(output_dir)
    google_disk_path = output_dir / "google_dashboard_summary.json"
    google_disk = json.loads(google_disk_path.read_text(encoding="utf-8")) if google_disk_path.exists() else {}

    extracted_at = refresh_result.get("extracted_at_utc")
    snapshot_age_seconds = _snapshot_age_seconds(extracted_at if isinstance(extracted_at, str) else None)

    google_disk_checks = [
        compare_values("google_disk.pending", expected_google["pending"], google_disk.get("pending")),
        compare_values("google_disk.collected", expected_google["collected"], google_disk.get("collected")),
        compare_values("google_disk.total_records", expected_google["total_records"], google_disk.get("total_records")),
        compare_values(
            "google_disk.pending_by_source",
            expected_google["pending_by_source"],
            google_disk.get("pending_by_source"),
        ),
    ]

    hybrid_checks = [
        compare_values("live_google.pending", expected_google["pending"], refresh_result.get("pending")),
        compare_values("hybrid.pending", hybrid_summary["pending"], dashboard_summary.get("pending")),
        compare_values("hybrid.collected", hybrid_summary["collected"], dashboard_summary.get("collected")),
        compare_values("hybrid.total_records", hybrid_summary["total_records"], dashboard_summary.get("total_records")),
        compare_values(
            "hybrid.pending_by_source",
            hybrid_summary["pending_by_source"],
            dashboard_summary.get("pending_by_source"),
        ),
        compare_values("hybrid.pending_by_day", hybrid_summary["pending_by_day"], dashboard_summary.get("pending_by_day")),
        compare_values(
            "hybrid.collected_by_day",
            hybrid_summary["collected_by_day"],
            dashboard_summary.get("collected_by_day"),
        ),
        compare_values(
            "hybrid.pending_previous_weeks",
            _int_or_zero(hybrid_summary.get("pending_previous_weeks")),
            _int_or_zero(dashboard_summary.get("pending_previous_weeks")),
        ),
    ]

    meta_checks: list[dict[str, Any]] = []
    if max_snapshot_age_seconds is not None and snapshot_age_seconds is not None:
        meta_checks.append(
            {
                "label": "snapshot_age_within_limit",
                "expected": f"<= {max_snapshot_age_seconds}",
                "actual": snapshot_age_seconds,
                "ok": snapshot_age_seconds <= max_snapshot_age_seconds,
            }
        )
    if max_refresh_roundtrip_seconds is not None:
        meta_checks.append(
            {
                "label": "refresh_roundtrip_within_limit",
                "expected": f"<= {max_refresh_roundtrip_seconds}",
                "actual": refresh_roundtrip_seconds,
                "ok": refresh_roundtrip_seconds <= max_refresh_roundtrip_seconds,
            }
        )

    if mode == "google-only":
        checks = google_disk_checks + meta_checks
    else:
        checks = hybrid_checks + google_disk_checks + meta_checks

    diagnostic = {
        "dashboard_pending_minus_google_extract": (dashboard_summary.get("pending") or 0)
        - (expected_google.get("pending") or 0),
        "dashboard_collected_minus_google_extract": (dashboard_summary.get("collected") or 0)
        - (expected_google.get("collected") or 0),
    }

    return {
        "ok": all(check["ok"] for check in checks),
        "mode": mode,
        "refresh_roundtrip_seconds": refresh_roundtrip_seconds,
        "snapshot_age_seconds": snapshot_age_seconds,
        "expected_google": {
            "pending": expected_google["pending"],
            "collected": expected_google["collected"],
            "total_records": expected_google["total_records"],
            "pending_by_source": expected_google["pending_by_source"],
            "pending_by_day": expected_google["pending_by_day"],
            "collected_by_day": expected_google["collected_by_day"],
        },
        "google_disk": {
            "pending": google_disk.get("pending"),
            "collected": google_disk.get("collected"),
            "total_records": google_disk.get("total_records"),
            "pending_by_source": google_disk.get("pending_by_source"),
        },
        "dashboard": {
            "data_mode": dashboard_summary.get("data_mode"),
            "pending": dashboard_summary.get("pending"),
            "collected": dashboard_summary.get("collected"),
            "total_records": dashboard_summary.get("total_records"),
            "pending_by_source": dashboard_summary.get("pending_by_source"),
            "pending_previous_weeks": dashboard_summary.get("pending_previous_weeks"),
            "pending_by_day": dashboard_summary.get("pending_by_day"),
            "collected_by_day": dashboard_summary.get("collected_by_day"),
            "extracted_at_utc": dashboard_summary.get("extracted_at_utc"),
        },
        "refresh_result": refresh_result,
        "hybrid_recomputed": {
            "pending": hybrid_summary.get("pending"),
            "collected": hybrid_summary.get("collected"),
            "pending_previous_weeks": hybrid_summary.get("pending_previous_weeks"),
        },
        "diagnostic_hybrid_vs_google_extract": diagnostic,
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify live Google Sheet extraction against dashboard API.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--spreadsheet", default=DEFAULT_SPREADSHEET_URL)
    parser.add_argument("--credentials", type=Path, default=Path("service-account.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--mode",
        choices=("hybrid", "google-only"),
        default="hybrid",
        help="hybrid: full parity checks vs recomputed hybrid; google-only: disk google_* summary vs live grid fetch.",
    )
    parser.add_argument(
        "--max-snapshot-age-seconds",
        type=float,
        default=None,
        help="Fail if extracted_at_utc from /api/refresh is older than this many seconds (optional).",
    )
    parser.add_argument(
        "--max-refresh-roundtrip-seconds",
        type=float,
        default=None,
        help="Fail if POST /api/refresh plus GET /api/summary round-trip exceeds this duration (optional).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(
        dashboard_url=args.dashboard_url,
        spreadsheet_url=args.spreadsheet,
        credentials_path=args.credentials.resolve(),
        output_dir=args.output_dir.resolve(),
        mode=args.mode,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        max_refresh_roundtrip_seconds=args.max_refresh_roundtrip_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
