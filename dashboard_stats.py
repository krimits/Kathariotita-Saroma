from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


GREEK_DAY_ORDER = ["ΔΕΥΤΕΡΑ", "ΤΡΙΤΗ", "ΤΕΤΑΡΤΗ", "ΠΕΜΠΤΗ", "ΠΑΡΑΣΚΕΥΗ", "ΣΑΒΒΑΤΟ", "ΚΥΡΙΑΚΗ"]

SNAPSHOT_FILE = "weekly_snapshots.json"


def day_sort_key(day: str) -> int:
    u = day.upper().strip()
    if u in GREEK_DAY_ORDER:
        return GREEK_DAY_ORDER.index(u)
    return 99


def _is_calendar_day(day: str) -> bool:
    return day.upper().strip() in GREEK_DAY_ORDER


def upsert_weekly_snapshot(output_dir: Path, summary: dict[str, Any], extracted_at_utc: str) -> None:
    """Κρατά έως ~2 έτη εβδομαδιαία στιγμιότυπα για τάσεις (ένα ενεργό ανά week_label)."""
    path = output_dir / SNAPSHOT_FILE
    week_label = str(summary.get("week_label") or "").strip()
    if not week_label:
        return

    entry: dict[str, Any] = {
        "week_label": week_label,
        "extracted_at_utc": extracted_at_utc,
        "pending": int(summary.get("pending") or 0),
        "collected": int(summary.get("collected") or 0),
        "pending_by_day": dict(summary.get("pending_by_day") or {}),
        "collected_by_day": dict(summary.get("collected_by_day") or {}),
    }

    data: list[dict[str, Any]] = []
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                data = json.loads(text)
        except json.JSONDecodeError:
            data = []

    data = [row for row in data if str(row.get("week_label", "")).strip() != week_label]
    data.append(entry)
    data.sort(key=lambda row: str(row.get("extracted_at_utc") or ""))
    data = data[-104:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshots(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / SNAPSHOT_FILE
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def compute_daily_series(records: list[dict[str, str]]) -> dict[str, Any]:
    pending_by_day: dict[str, int] = defaultdict(int)
    collected_by_day: dict[str, int] = defaultdict(int)

    for row in records:
        day = (row.get("day") or "").strip()
        if not _is_calendar_day(day):
            continue
        key = day.upper().strip()
        status = (row.get("status") or "").strip().lower()
        if status == "pending":
            pending_by_day[key] += 1
        elif status == "collected":
            collected_by_day[key] += 1

    days_sorted = sorted(set(pending_by_day) | set(collected_by_day), key=day_sort_key)
    series: list[dict[str, Any]] = []
    ratios: list[float] = []

    for d in days_sorted:
        p = pending_by_day[d]
        c = collected_by_day[d]
        total = p + c
        ratio = (c / total) if total > 0 else 0.0
        if total > 0:
            ratios.append(ratio)
        series.append(
            {
                "day": d,
                "pending": p,
                "collected": c,
                "total_points": total,
                "ratio_collected": round(ratio, 4),
            }
        )

    ratio_stats = _ratio_statistics(series, ratios)
    return {"series": series, "ratio_stats": ratio_stats}


def _ratio_statistics(series: list[dict[str, Any]], ratios: list[float]) -> dict[str, Any]:
    outlier_days: list[dict[str, Any]] = []
    if len(ratios) >= 2:
        mu = mean(ratios)
        sigma = pstdev(ratios)
        for item in series:
            if item["total_points"] == 0:
                continue
            r = float(item["ratio_collected"])
            if sigma > 1e-9 and abs(r - mu) > 2 * sigma:
                outlier_days.append(
                    {
                        "day": item["day"],
                        "ratio_collected": r,
                        "note": "Απόκλιση μεταβλητότητας ημέρας έναντι μέσου όρου εβδομάδας (>2σ)",
                    }
                )
        return {
            "ratio_mean": round(mu, 4),
            "ratio_stdev": round(sigma, 4),
            "sample_days": len(ratios),
            "outlier_days": outlier_days,
        }
    if len(ratios) == 1:
        return {
            "ratio_mean": round(ratios[0], 4),
            "ratio_stdev": 0.0,
            "sample_days": 1,
            "outlier_days": [],
        }
    return {
        "ratio_mean": None,
        "ratio_stdev": None,
        "sample_days": 0,
        "outlier_days": [],
    }


def compute_street_metrics(records: list[dict[str, str]], *, min_volume: int = 2) -> dict[str, Any]:
    pending_by_street: dict[str, int] = defaultdict(int)
    collected_by_street: dict[str, int] = defaultdict(int)

    for row in records:
        day = (row.get("day") or "").strip()
        if not _is_calendar_day(day):
            continue
        street = (row.get("street_normalized") or row.get("street") or "").strip().upper()
        if not street:
            continue
        status = (row.get("status") or "").strip().lower()
        if status == "pending":
            pending_by_street[street] += 1
        elif status == "collected":
            collected_by_street[street] += 1

    scores: list[dict[str, Any]] = []
    for street in sorted(set(pending_by_street) | set(collected_by_street)):
        p = pending_by_street[street]
        c = collected_by_street[street]
        total = p + c
        ratio = (c / total) if total > 0 else 0.0
        scores.append(
            {
                "street": street,
                "pending": p,
                "collected": c,
                "total": total,
                "ratio_collected": round(ratio, 4),
            }
        )

    pressure = sorted(scores, key=lambda x: x["pending"], reverse=True)[:12]
    performers = sorted(
        [x for x in scores if x["total"] >= min_volume],
        key=lambda x: (x["ratio_collected"], x["collected"]),
        reverse=True,
    )[:12]

    pending_positive = [x["pending"] for x in scores if x["pending"] > 0]
    street_outliers: list[dict[str, Any]] = []
    if len(pending_positive) >= 3:
        mu_p = mean(pending_positive)
        sigma_p = pstdev(pending_positive)
        if sigma_p > 1e-9:
            for x in scores:
                if x["pending"] > mu_p + 2 * sigma_p:
                    street_outliers.append(
                        {
                            "street": x["street"],
                            "pending": x["pending"],
                            "note": "Υψηλές εκκρεμότητες έναντι κατανομής οδών (>2σ)",
                        }
                    )

    return {
        "pressure": pressure,
        "performers": performers,
        "street_outliers": street_outliers[:15],
    }


def weekly_trend_from_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    labels: list[str] = []
    pending_s: list[int] = []
    collected_s: list[int] = []
    ratio_s: list[float | None] = []

    for row in snapshots:
        wl = str(row.get("week_label") or "")
        labels.append(wl[:24] + ("…" if len(wl) > 24 else ""))
        p = int(row.get("pending") or 0)
        c = int(row.get("collected") or 0)
        pending_s.append(p)
        collected_s.append(c)
        t = p + c
        ratio_s.append(round(c / t, 4) if t > 0 else None)

    return {"labels": labels, "pending": pending_s, "collected": collected_s, "ratio_collected": ratio_s}


def monthly_aggregate_from_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Μέσοι όροι ανά ημερολογιακό μήνα (εξαγωγής snapshot), για τάση όταν υπάρχουν πολλές εβδομάδες."""

    def month_key(row: dict[str, Any]) -> str:
        iso = str(row.get("extracted_at_utc") or "")
        return iso[:7] if len(iso) >= 7 else "άγνωστο"

    buckets: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in snapshots:
        buckets[month_key(row)].append((int(row.get("pending") or 0), int(row.get("collected") or 0)))

    months_sorted = sorted(buckets.keys())
    labels: list[str] = []
    pending_avg: list[float] = []
    collected_avg: list[float] = []
    ratio_avg: list[float | None] = []

    for m in months_sorted:
        pairs = buckets[m]
        if not pairs:
            continue
        labels.append(m)
        p_avg = mean([p for p, _ in pairs])
        c_avg = mean([c for _, c in pairs])
        pending_avg.append(round(p_avg, 2))
        collected_avg.append(round(c_avg, 2))
        ratio_parts = []
        for p, c in pairs:
            t = p + c
            if t > 0:
                ratio_parts.append(c / t)
        ratio_avg.append(round(mean(ratio_parts), 4) if ratio_parts else None)

    return {
        "labels": labels,
        "pending_avg": pending_avg,
        "collected_avg": collected_avg,
        "ratio_collected_avg": ratio_avg,
    }


def _fmt_ratio_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "—"


def _fmt_float(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "—"


def build_weekly_report(
    week_label: str,
    daily: dict[str, Any],
    streets: dict[str, Any],
    snapshots: list[dict[str, Any]],
) -> str:
    rs = daily.get("ratio_stats") or {}
    lines: list[str] = [
        f"Εβδομαδιαία ανασκόπηση αποκομιδής ογκωδών — {week_label}",
        "",
        "Σύνοψη ημερών εργασίας (στο στιγμιότυπο του φύλλου):",
    ]

    for row in daily.get("series") or []:
        if row.get("total_points", 0) == 0:
            continue
        lines.append(
            f"• {row['day']}: εκκρεμή {row['pending']}, συλλεχθέντα {row['collected']}, "
            f"λόγος συλλεχθέντων επί συνόλου εγγραφών ημέρας {float(row['ratio_collected']):.1%}"
        )

    lines.extend(
        [
            "",
            f"Μέσος όρος ημερήσιου λόγου συλλεχθέντων: {_fmt_ratio_pct(rs.get('ratio_mean'))}",
            f"Τυπική απόκλιση ημερήσιου λόγου (ως κλάσμα 0–1): {_fmt_float(rs.get('ratio_stdev'))}",
        ]
    )

    outliers = rs.get("outlier_days") or []
    if outliers:
        lines.append("")
        lines.append("Ημέρες με ακραία τιμή λόγου (έναντι υπόλοιπων ημερών της εβδομάδας):")
        for o in outliers:
            lines.append(f"• {o.get('day')}: λόγος {float(o.get('ratio_collected', 0)):.1%}")

    st_out = streets.get("street_outliers") or []
    if st_out:
        lines.append("")
        lines.append("Οδοί με εξαιρετικά υψηλό απόθεμα εκκρεμοτήτων (στατιστικό outlier):")
        for o in st_out[:8]:
            lines.append(f"• {o.get('street')}: {o.get('pending')} εκκρεμή")

    perf = streets.get("performers") or []
    if perf:
        lines.append("")
        lines.append("Οδοί με σχετικά καλή απόδοση (υψηλός λόγος συλλεχθέντων σε σχέση με το φορτίο της οδού):")
        for row in perf[:8]:
            lines.append(
                f"• {row['street']}: συλλεχθέντα {row['collected']}, εκκρεμή {row['pending']}, "
                f"λόγος {float(row['ratio_collected']):.1%}"
            )

    pres = streets.get("pressure") or []
    if pres:
        lines.append("")
        lines.append("Οδοί με υψηλότερη πίεση εκκρεμοτήτων (προτεραιότητα διοίκησης):")
        for row in pres[:8]:
            lines.append(f"• {row['street']}: {row['pending']} εκκρεμή σημεία")

    lines.extend(
        [
            "",
            f"Αποθηκευμένα ιστορικά στιγμιότυπα εβδομάδας για τάσεις: {len(snapshots)}.",
            "Σημείωση: η πολυετής ανάλυση εμβαθύνει όσο συσσωρεύονται snapshots μετά από διαδοχικά refresh.",
        ]
    )

    return "\n".join(lines)


def build_stats_payload(
    summary: dict[str, Any],
    records: list[dict[str, str]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    week_label = str(summary.get("week_label") or "Τρέχουσα εβδομάδα")
    daily = compute_daily_series(records)
    streets = compute_street_metrics(records)
    weekly_trend = weekly_trend_from_snapshots(snapshots)
    monthly = monthly_aggregate_from_snapshots(snapshots)
    report = build_weekly_report(week_label, daily, streets, snapshots)

    total_pending = int(summary.get("pending") or 0)
    total_collected = int(summary.get("collected") or 0)
    grand_total = total_pending + total_collected
    overall_ratio = (total_collected / grand_total) if grand_total > 0 else None

    return {
        "week_label": week_label,
        "totals": {
            "pending": total_pending,
            "collected": total_collected,
            "ratio_collected": round(overall_ratio, 4) if overall_ratio is not None else None,
        },
        "daily": daily,
        "streets": streets,
        "snapshots_count": len(snapshots),
        "weekly_trend": weekly_trend,
        "monthly": monthly,
        "weekly_report": report,
    }
