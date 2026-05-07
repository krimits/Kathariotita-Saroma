from __future__ import annotations

import base64
import binascii
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from secrets import compare_digest
from threading import Lock
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from dashboard_hybrid import run_hybrid
from dashboard_stats import build_stats_payload, load_snapshots, upsert_weekly_snapshot
from google_sheets_extractor import run as run_google_extraction


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.getenv("DASHBOARD_OUTPUT_DIR", BASE_DIR / "output"))
STATIC_DIR = BASE_DIR / "web" / "static"
SPREADSHEET_URL = os.getenv(
    "DASHBOARD_SPREADSHEET_URL",
    "https://docs.google.com/spreadsheets/d/1Y1lvKhBIEEh5AceA580jSTXlB3ms5AwX5Mo5RC9b5wM/edit?gid=1505732445#gid=1505732445",
)


def _resolve_google_credentials_path() -> Path:
    """Τοπικό αρχείο ή εγγραφή runtime από secret env (Render / CI)."""
    runtime_path = Path(os.getenv("GOOGLE_CREDENTIALS_RUNTIME_PATH", "/tmp/render_google_sa.json"))
    raw_json = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    b64 = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64") or "").strip()
    if b64:
        try:
            raw_json = base64.b64decode(b64).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raw_json = ""
    if raw_json:
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(raw_json, encoding="utf-8")
        return runtime_path
    explicit = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if explicit:
        return Path(explicit)
    return BASE_DIR / "service-account.json"


GOOGLE_CREDENTIALS = _resolve_google_credentials_path()
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "20"))
_refresh_lock = Lock()
_last_refresh = 0.0
_last_extracted_at_utc: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refresh_payload(refreshed: bool, reason: str, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "refreshed": refreshed,
        "reason": reason,
        "extracted_at_utc": _last_extracted_at_utc,
        "refresh_interval_seconds": REFRESH_SECONDS,
    }
    if summary is not None:
        payload["pending"] = summary.get("pending")
        payload["collected"] = summary.get("collected")
        payload["pending_previous_weeks"] = summary.get("pending_previous_weeks")
        payload["total_records"] = summary.get("total_records")
    return payload


SUMMARY_FILES = (
    "hybrid_dashboard_summary.json",
    "google_dashboard_summary.json",
    "dashboard_summary.json",
)
RECORD_FILES = (
    "hybrid_dashboard_records.csv",
    "google_dashboard_records.csv",
    "dashboard_records.csv",
)


app = FastAPI(title="Dashboard Αποκομιδής Ογκωδών")


@app.middleware("http")
async def dashboard_basic_auth(request: Request, call_next: Any) -> Response:
    """Προαιρετικό HTTP Basic· το /health μένει ανοιχτό για health checks του Render."""
    user = (os.getenv("DASHBOARD_BASIC_AUTH_USER") or "").strip()
    password = (os.getenv("DASHBOARD_BASIC_AUTH_PASSWORD") or "").strip()
    if not user or not password:
        return await call_next(request)
    path = request.url.path
    if path == "/health" or path.startswith("/health/"):
        return await call_next(request)
    # CSS/JS χωρίς δεύτερο challenge: με Basic Auth πολλά browsers δεν στέλνουν Authorization σε /static/* → σελίδα χωρίς styling/scripts.
    if path == "/static" or path.startswith("/static/"):
        return await call_next(request)
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Basic "):
        return _basic_auth_challenge()
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        offered_user, _, offered_pw = decoded.partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return _basic_auth_challenge()
    if not (compare_digest(offered_user, user) and compare_digest(offered_pw, password)):
        return _basic_auth_challenge()
    return await call_next(request)


def _basic_auth_challenge() -> Response:
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Dashboard Αποκομιδής"'},
        content="Απαιτείται έλεγχος ταυτότητας.".encode("utf-8"),
        media_type="text/plain; charset=utf-8",
    )


def _snapshot_after_refresh(summary: dict[str, Any]) -> None:
    global _last_extracted_at_utc
    _last_extracted_at_utc = _utc_now_iso()
    upsert_weekly_snapshot(OUTPUT_DIR, summary, _last_extracted_at_utc)


def refresh_google_and_hybrid(force: bool = False) -> dict[str, Any]:
    global _last_refresh, _last_extracted_at_utc
    now = time.monotonic()
    with _refresh_lock:
        if not force and now - _last_refresh < REFRESH_SECONDS:
            return _refresh_payload(False, "fresh_enough")
        if not GOOGLE_CREDENTIALS.exists():
            summary = run_hybrid(OUTPUT_DIR)
            _last_refresh = now
            _snapshot_after_refresh(summary)
            return _refresh_payload(False, "missing_google_credentials", summary)

        run_google_extraction(
            spreadsheet_or_url=SPREADSHEET_URL,
            credentials_path=GOOGLE_CREDENTIALS,
            output_dir=OUTPUT_DIR,
            gid_or_url=SPREADSHEET_URL,
        )
        summary = run_hybrid(OUTPUT_DIR)
        _last_refresh = now
        _snapshot_after_refresh(summary)
        return _refresh_payload(True, "google_and_hybrid_ok", summary)


def first_existing(directory: Path, candidates: tuple[str, ...]) -> Path:
    for candidate in candidates:
        path = directory / candidate
        if path.exists():
            return path
    raise FileNotFoundError(f"None of these files exist in {directory}: {', '.join(candidates)}")


def load_summary(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir == OUTPUT_DIR:
        refresh_google_and_hybrid()
    path = first_existing(output_dir, SUMMARY_FILES)
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(output_dir: Path = OUTPUT_DIR) -> list[dict[str, str]]:
    if output_dir == OUTPUT_DIR:
        refresh_google_and_hybrid()
    path = first_existing(output_dir, RECORD_FILES)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_filter(value: str | None) -> str:
    return (value or "").strip().upper()


def record_matches(
    record: dict[str, str],
    status: str,
    source: str,
    day: str,
    street: str,
) -> bool:
    if status and record.get("status", "").upper() != status:
        return False
    if source and record.get("source", "").upper() != source:
        return False
    if day and (record.get("day") or record.get("period") or "").upper() != day:
        return False
    if street and street not in record.get("street_normalized", "").upper():
        return False
    return True


def filter_records(
    records: list[dict[str, str]],
    status: str = "",
    source: str = "",
    day: str = "",
    street: str = "",
) -> list[dict[str, str]]:
    normalized_status = normalize_filter(status)
    normalized_source = normalize_filter(source)
    normalized_day = normalize_filter(day)
    normalized_street = normalize_filter(street)
    return [
        record
        for record in records
        if record_matches(record, normalized_status, normalized_source, normalized_day, normalized_street)
    ]


def available_filters(records: list[dict[str, str]]) -> dict[str, list[str]]:
    return {
        "days": sorted({record.get("day") or record.get("period") or "" for record in records if record.get("day") or record.get("period")}),
        "statuses": sorted({record.get("status", "") for record in records if record.get("status")}),
        "sources": sorted({record.get("source", "") for record in records if record.get("source")}),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/refresh")
def api_refresh() -> dict[str, Any]:
    return refresh_google_and_hybrid(force=True)


@app.get("/api/summary")
def api_summary() -> dict[str, Any]:
    summary = load_summary()
    records = load_records()
    ppw = summary.get("pending_previous_weeks")
    summary["pending_previous_weeks"] = 0 if ppw is None else int(ppw)
    summary["filters"] = available_filters(records)
    summary["extracted_at_utc"] = _last_extracted_at_utc
    summary["refresh_interval_seconds"] = REFRESH_SECONDS
    return summary


@app.get("/api/stats")
def api_stats() -> dict[str, Any]:
    """Στατιστικά από το τρέχον CSV/summary χωρίς νέο refresh Google (χρησιμοποιεί αρχεία στον δίσκο)."""
    summary_path = first_existing(OUTPUT_DIR, SUMMARY_FILES)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    records_path = first_existing(OUTPUT_DIR, RECORD_FILES)
    with records_path.open("r", encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    snapshots = load_snapshots(OUTPUT_DIR)
    return build_stats_payload(summary, records, snapshots)


@app.get("/api/records")
def api_records(
    status: str = Query("", description="pending, collected, unknown"),
    source: str = Query("", description="veltio, supervisor, previous_weeks, unknown"),
    day: str = Query("", description="Greek day or period label"),
    street: str = Query("", description="Street search text"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    records = filter_records(load_records(), status=status, source=source, day=day, street=street)
    return {
        "total": len(records),
        "records": records[:limit],
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR.resolve())), name="static")
