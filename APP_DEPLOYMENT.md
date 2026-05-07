# Web Dashboard App

## Οδικός χάρτης προϊόντος (μετά την πρώτη έκδοση)

Αναλυτικότερο σχέδιο οθονών και KPI βρίσκεται στο [`DASHBOARD_DESIGN.md`](DASHBOARD_DESIGN.md). Προτεινόμενη σειρά υλοποίησης:

| Φάση | Περιεχόμενο | Σημειώσεις |
|---|---|---|
| A | Καρτέλα «Ημερήσια ροή»: γραφήματα νέων vs συλλεχθέντων ανά ημέρα, φίλτρο ημέρας | Δεδομένα ήδη σε `pending_by_day` / `collected_by_day` |
| B | «Οδοί υψηλής πίεσης»: επαναλήψεις ανά οδό, drill-down | Απαιτείται snapshot ιστορικού ή εβδομαδιαία αρχεία |
| C | «Παλαιότητα εκκρεμοτήτων»: κάδοι 1η/2η/3η προηγούμενη εβδομάδα | Επέκταση μοντέλου εγγραφής `age_bucket` όπως στο design |
| D | «Ιστορική τάση»: αποθήκευση εβδομαδιαίων snapshots στη βάση ή σε αρχεία | Εξαρτάται από Φάση 3 του design doc |
| E | Επιχειρησιακές προβλέψεις / ειδοποιήσεις | Μετά από επαρκές ιστορικό |

## Τοπική εκτέλεση

Από τον φάκελο `C:\Users\e.krimitsas\Downloads\Dashboard`:

```powershell
.\run_dashboard.cmd
```

Μετά άνοιγμα:

```text
http://127.0.0.1:8001
```

Το app διαβάζει κατά προτεραιότητα:

1. `output/hybrid_dashboard_summary.json`
2. `output/google_dashboard_summary.json`
3. `output/dashboard_summary.json`

και αρχεία εγγραφών:

1. `output/hybrid_dashboard_records.csv`
2. `output/google_dashboard_records.csv`
3. `output/dashboard_records.csv`

Όταν υπάρχουν διαπιστευτήρια Google, το `POST /api/refresh` και ο περιοδικός refresh γράφουν τα `google_*` και επανυπολογίζουν τα `hybrid_*`.

## API endpoints

| Endpoint | Περιγραφή |
|---|---|
| `/` | Κεντρική οθόνη dashboard |
| `/health` | Health check για Render |
| `/api/summary` | KPIs, φίλτρα, `pending_previous_weeks`, `extracted_at_utc`, συγκεντρωτικά |
| `/api/records` | Αναλυτικές εγγραφές με φίλτρα |
| `/api/refresh` | Αναγκαστική ενημέρωση από Google + rebuild hybrid· επιστρέφει `extracted_at_utc` (ISO UTC) και διαστήματα |

Παράδειγμα:

```text
/api/records?status=pending&street=ΑΙΓΑΙΟΥ
/api/records?source=previous_weeks
```

## Επαλήθευση έναντι live φύλλου

Από τον φάκελο project (με να τρέχει το dashboard στο προεπιλεγμένο URL):

```powershell
python verify_live_dashboard.py
python verify_live_dashboard.py --mode google-only
python verify_live_dashboard.py --max-snapshot-age-seconds 90
```

- **`hybrid` (προεπιλογή)**: ελέγχει ότι τα υβριδικά aggregates συμφωνούν με το API μετά το refresh, και ότι το `google_dashboard_summary.json` στο δίσκο συμφωνεί με νέο fetch από το Sheet.
- **`google-only`**: εστιάζει στη συμφωνία live extractor ↔ αρχείο `google_dashboard_summary.json` (χωρίς τα υβριδικά KPI ως μοναδικό κριτήριο επιτυχίας).

Προαιρετικά όρια: `--max-snapshot-age-seconds`, `--max-refresh-roundtrip-seconds`.

## Render deployment

Το αρχείο [`render.yaml`](render.yaml) περιγράφει ένα **Web Service** (Python, health check στο `/health`). Η έκδοση Python ορίζεται στο [`runtime.txt`](runtime.txt).

### Βήματα (σύνοψη)

1. **Git repository**: ανέβασε τον κώδικα σε GitHub / GitLab / Bitbucket (χωρίς `service-account.json` — υπάρχει [`.gitignore`](.gitignore)).
2. Στο [Render Dashboard](https://dashboard.render.com): **New + Blueprint** (αν υπάρχει `render.yaml` στο repo) **ή** **New + Web Service** και σύνδεση του repo.
3. **Build**: `pip install -r requirements.txt` (ή προεπιλογή Python αν το UI το ανιχνεύει).
4. **Start**: `uvicorn dashboard_web:app --host 0.0.0.0 --port $PORT` (το `$PORT` το δίνει το Render).
5. Μετά το deploy, άνοιξε το URL που σου δίνει το Render (`https://…onrender.com`). Το frontend φορτώνει από `/` και στατικά από `/static/…`.

### Μεταβλητές περιβάλλοντος (υποχρεωτικές / προαιρετικές)

| Μεταβλητή | Σκοπός |
|-----------|--------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Ολόκληρο το JSON του service account (πολυγραμμικό)· στην εκκίνηση γράφεται σε προσωρινό αρχείο και χρησιμοποιείται για το Sheets API. |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Εναλλακτικά: το ίδιο JSON κωδικοποιημένο σε Base64 (λιγότερα προβλήματα με ειδικούς χαρακτήρες στο UI). Αρκεί **ένα** από τα δύο. |
| `DASHBOARD_SPREADSHEET_URL` | Προαιρετικό αν χρησιμοποιείτε το default φύλλο· αλλιώς πλήρες URL με `gid` της καρτέλας. |
| `DASHBOARD_OUTPUT_DIR` | Προεπιλογή στο Blueprint: `output` (φάκελος εργασίας του instance). |
| `DASHBOARD_REFRESH_SECONDS` | Διάστημα throttle μεταξύ αναγνώσεων από το Sheet (π.χ. `30`). |
| `DASHBOARD_BASIC_AUTH_USER` / `DASHBOARD_BASIC_AUTH_PASSWORD` | **Προαιρετικό**: κοινός κωδικός για στελέχη (HTTP Basic)· το **`/health`** μένει χωρίς authentication ώστε να περνάει το health check του Render. Ο browser θα ζητήσει username/password. |

### Google Sheets σε παραγωγή

1. Δημιούργησε service account στο Google Cloud και κατέβασε JSON κλειδί· **μην** το κάνεις commit.
2. Στο Render: **Environment → Add Environment Variable** → επικόλλησε ως `GOOGLE_SERVICE_ACCOUNT_JSON` **ή** ανέβασε Base64 σε `GOOGLE_SERVICE_ACCOUNT_JSON_B64`.
3. Στο Google Sheet: **Share** στο email `client_email` του JSON (ρόλος τουλάχιστον **Viewer**).
4. Το φύλλο πρέπει να είναι **native Google Sheet** (όχι μόνο XLSX)· δες μηνύματα λάθους στο [`google_sheets_extractor.py`](google_sheets_extractor.py).
5. Μετά το deploy, έλεγξε logs στο πρώτο φόρτωμα σελίδας ή κάλεσε `POST /api/refresh`· αν τα credentials είναι λάθος, θα φανεί στα logs.

### Persistent disk (προαιρετικό)

Στο free tier τα αρχεία κάτω από `output/` **χάνονται σε redeploy/restart**. Το `weekly_snapshots.json` ξαναρχίζει από την αρχή. Αν χρειάζεστε μόνιμο ιστορικό στατιστικών, στο Render μπορείτε να προσθέσετε **Disk** και να ορίσετε `DASHBOARD_OUTPUT_DIR` στο mount path (πρόγραμμα πληρωμένο / ανάλογα πλάνο).

### Περιορισμοί free πλάνου Render

- Το instance μπορεί να «κοιμάται» μετά από περίοδο αδράνειας· η **πρώτη** πρόσβαση μετά από ύπνο μπορεί να καθυστερήσει κάποια δευτερόλεπτα (cold start).
- Ο δίσκος είναι **προσωρινός**· δείτε παραπάνω για snapshots και ιστορικό.

## Πρόσβαση διοίκησης

- Δώστε στα στελέχη το HTTPS URL του Render.
- **Συνιστάται** να ορίσετε `DASHBOARD_BASIC_AUTH_USER` και `DASHBOARD_BASIC_AUTH_PASSWORD` ώστε το dashboard να μην είναι ανοιχτό σε οποιονδήποτε βρει το URL.
- Για υψηλότερες απαιτήσεις (SSO, ρόλοι), χρειάζεται επιπλέον υλοποίηση (π.χ. OAuth πίσω από reverse proxy).
