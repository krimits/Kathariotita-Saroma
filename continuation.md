# Continuation - Dashboard Αποκομιδής Ογκωδών

## Workspace

```text
C:\Users\e.krimitsas\Downloads\Dashboard
```

## Current Goal

Υλοποιείται dashboard για αποκομιδή ογκωδών αντικειμένων Δήμου Θεσσαλονίκης, με πηγή δεδομένων ένα Google Sheet/Excel αρχείο.

Το dashboard πρέπει να δείχνει:

- εκκρεμή σημεία,
- συλλεχθέντα σημεία,
- πηγή εκκρεμότητας,
- top οδούς,
- εβδομαδιαία κατάσταση με όρια:
  - 0-100: άριστη,
  - 101-299: καλή,
  - 300+: κόκκινη.

## Important Files

| File | Purpose |
|---|---|
| `dashboard_web.py` | FastAPI backend |
| `web/static/index.html` | Dashboard UI |
| `web/static/styles.css` | Dashboard styling |
| `web/static/app.js` | Frontend logic |
| `dashboard_extractor.py` | Local Excel extractor fallback |
| `google_sheets_extractor.py` | Google Sheets API extractor |
| `dashboard_hybrid.py` | Combines Google pending data with Excel-inferred collected history |
| `run_dashboard.cmd` | Starts local dashboard at port 8001 |
| `run_google_extraction.cmd` | Pulls data from Google Sheets API and rebuilds hybrid outputs |
| `service-account.json` | Local Google service account credentials, do not expose |
| `output/dashboard_summary.json` | Excel fallback summary |
| `output/dashboard_records.csv` | Excel fallback records |
| `output/google_dashboard_summary.json` | Google Sheets summary, preferred by app |
| `output/google_dashboard_records.csv` | Google Sheets records, preferred by app |
| `output/hybrid_dashboard_summary.json` | Hybrid summary, preferred by app |
| `output/hybrid_dashboard_records.csv` | Hybrid records, preferred by app |
| `APP_DEPLOYMENT.md` | Local/Render deployment notes |
| `SERVICE_ACCOUNT_SETUP.md` | Google service account setup notes |

## Current Data Source State

Google Sheets extraction has succeeded against native Google Sheet:

```text
https://docs.google.com/spreadsheets/d/1Y1lvKhBIEEh5AceA580jSTXlB3ms5AwX5Mo5RC9b5wM/edit?gid=1505732445#gid=1505732445
```

The app prefers hybrid outputs when present:

1. `output/hybrid_dashboard_summary.json`
2. `output/hybrid_dashboard_records.csv`

Hybrid mode:

```text
Google Sheets pending/current state + Google collected/current state + Excel-inferred collected history
```

Current hybrid result from the last successful run:

```text
total_records: 157
pending: 35
collected: 122
pending_by_source: supervisor = 35
week_status: excellent
```

Important interpretation:

Business rules (κοινό υποστρωμα `dashboard_extractor.py`, χρησιμοποιείται και από `google_sheets_extractor.py`):

```text
same numeric value appears more than once in the same row C:L -> collected/matched
unmatched numeric value in previous-week columns C:E -> pending, source previous_weeks (mustard)
unmatched numeric value in day columns F:L -> pending; source from fill + font:
  orange/yellow fill + red foreground -> veltio (ΒΠΠΜ / χειριστής)
  orange/yellow fill + dark/black foreground -> supervisor
  red fill -> veltio (legacy)
  transparent / white effective background -> use foreground (red -> veltio, dark/default -> supervisor)
Google Sheets API requests effectiveFormat.backgroundColor and textFormat.foregroundColor.
Local .xlsx often stores conditional fill as transparent (00000000); font RGB or Excel theme (e.g. theme 1) still distinguishes supervisor vs veltio.
```

Το hybrid layer κρατά την τρέχουσα εκκρεμότητα από Google και προσθέτει ιστορικό συλλεχθέντων από το τοπικό Excel· αν ένα σημείο εμφανίζεται ξανά ως pending στο Google, το αντίστοιχο κλειδί από το Excel-collected αφαιρείται για αποφυγή διπλομέτρησης.

Μετά την ενημέρωση κανόνων χρωματοσειράς, το `pending_by_source` στο JSON ενδέχεται να **μετατοπίζει** μετοχές από `supervisor` προς `veltio` (ή το αντίστροφο) σε σχέση με παλιές εξαγωγές που διάβαζαν μόνο φόντο—ξανατρέξτε `run_google_extraction.cmd` και συγκρίνετε με `verify_live_dashboard.py`.

The backend also refreshes Google data automatically every 20 seconds when `/api/summary` or `/api/records` is called. The frontend refreshes the dashboard every 20 seconds.

## Local Run

Start dashboard:

```powershell
.\run_dashboard.cmd
```

Open:

```text
http://127.0.0.1:8001
```

If the page does not load, check whether a server is running:

```powershell
Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue
```

## Refresh Google Data

Run:

```powershell
.\run_google_extraction.cmd
```

This requires:

- network access,
- valid `service-account.json`,
- the native Google Sheet shared with the `client_email` in `service-account.json`.

## Verification Commands

Run tests:

```powershell
python -m unittest discover -v
```

Check backend import:

```powershell
python -c "import dashboard_web; print('app import ok')"
```

Check API when server is running:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/health"
Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/summary"
```

Verify live Google Sheet against dashboard API:

```powershell
python verify_live_dashboard.py
python verify_live_dashboard.py --mode google-only
python verify_live_dashboard.py --max-snapshot-age-seconds 120
```

The verifier forces `POST /api/refresh` (και `GET /api/summary`), reads the Google Sheet through the API, recomputes hybrid locally against `output/`, και συγκρίνει aggregates. Το `--mode google-only` ελέγχει κυρίως `google_dashboard_summary.json` έναντι live grid· προαιρετικά όρια latency/ηλικίας snapshot με `--max-*`.

Μετά από αλλαγές σε `dashboard_extractor.py` ή `google_sheets_extractor.py`, **ξανάνοιξε το dashboard** (`run_dashboard.cmd`) ώστε το uvicorn να φορτώσει τον νέο κώδικα· αλλιώς το `POST /api/refresh` από τον verifier μπορεί να ξαναγράψει τα αρχεία στο `output/` με την παλιά λογική και να διαστρεβλώσει το `pending_by_source`.

## Last Verified State

On 2026-05-07:

```text
34 tests OK
dashboard_web import OK
google_dashboard_* files exist
hybrid_dashboard_* files exist
After extractor changes: restart dashboard before verify_live_dashboard.py (uvicorn module cache)
Live extraction sample: pending_by_source supervisor + veltio split via foregroundColor on orange cells
```

## Next Work

1. Keep the local server running on `8001`.
2. Decide whether dashboard should show Google current state only or combine Google current pending data with local Excel inferred collected history.
3. Επαλήθευση live Sheet μετά την ανάγνωση `foregroundColor`: `verify_live_dashboard.py` και έλεγχος `pending_by_source`· αν το API λείπει συχνά το foreground, εξετάστε fallback ή διόρθωση στο template του φύλλου.
4. Add Render deployment credentials handling before public deployment.

Προαιρετικό εργαλείο βαθμονόμησης χρωμάτων από τοπικό `.xlsx`: `python scripts/sample_xlsx_colors.py` (από τον φάκελο του project).
