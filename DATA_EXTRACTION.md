# Data Extraction - Φάση 1

## Αρχεία

| Αρχείο | Ρόλος |
|---|---|
| `dashboard_extractor.py` | Διαβάζει το Excel και παράγει καθαρά δεδομένα για dashboard |
| `google_sheets_extractor.py` | Διαβάζει απευθείας Google Sheets values και effective cell formats |
| `test_dashboard_extractor.py` | Ελέγχει τους βασικούς κανόνες ταξινόμησης |
| `output/dashboard_records.csv` | Αναλυτικές εγγραφές ανά σημείο/κελί |
| `output/dashboard_summary.json` | Συγκεντρωτικά KPIs για την πρώτη οθόνη |

## Εκτέλεση

Από τον φάκελο `C:\Users\e.krimitsas\Downloads\Dashboard`:

```powershell
python dashboard_extractor.py --output-dir output
```

Για tests:

```powershell
python -m unittest test_dashboard_extractor.py -v
```

## Τρέχον αποτέλεσμα από το αρχείο

Για την εβδομάδα `4/5/26 εως 8/5/26`:

| KPI | Τιμή |
|---|---:|
| Σύνολο εγγραφών με αριθμητικό σημείο | 150 |
| Εκκρεμή σημεία | 24 |
| Συλλεχθέντα / επιλυμένα σημεία | 126 |
| Συλλεχθέντα σε στήλες ημερών | 87 |
| Επιλυμένες προηγούμενες εκκρεμότητες | 39 |
| Κατάσταση εβδομάδας | Άριστη |

Η εβδομάδα χαρακτηρίζεται άριστη επειδή τα εκκρεμή σημεία είναι κάτω από το όριο των 100.

## Περιορισμός πηγής κόκκινο/πορτοκαλί

Το τοπικό XLSX συχνά αποθηκεύει το conditional formatting ως «διαφανές» fill (`00000000`) στο openpyxl. Το `dashboard_extractor.py` διακρίνει **επόπτη vs Βελτιώνω την πόλη μου** από το **χρώμα γραμματοσειράς** (κόκκινο κείμενο → `veltio`, μαύρο/σκούρο ή Excel theme 1 → `supervisor`) όταν το φόντο δεν είναι αναγνώσιμο.

Για παραγωγική συμφωνία με το live Google Sheet, η διαδρομή `google_sheets_extractor.py` διαβάζει `effectiveFormat.backgroundColor` **και** `effectiveFormat.textFormat.foregroundColor`.

## Google Sheets API extraction

Το αρχείο `google_sheets_extractor.py` είναι η παραγωγική διαδρομή για ακριβή διάκριση πηγής, επειδή διαβάζει το τελικό χρώμα του κελιού από το Google Sheets API.

### Προαπαιτούμενα

1. Δημιουργία Google Cloud project.
2. Ενεργοποίηση Google Sheets API.
3. Δημιουργία Service Account.
4. Λήψη του service account JSON key σε τοπικό αρχείο.
5. Share του Google Sheet με το email του service account, π.χ. `dashboard-reader@project.iam.gserviceaccount.com`, με δικαίωμα Viewer.
6. Εγκατάσταση Python πακέτων:

```powershell
python -m pip install google-api-python-client google-auth
```

### Εκτέλεση

Αν το service account JSON τοποθετηθεί στον φάκελο με όνομα `service-account.json`, μπορεί να τρέξει απευθείας:

```powershell
.\run_google_extraction.cmd
```

Εναλλακτικά, με explicit path:

```powershell
python google_sheets_extractor.py `
  --spreadsheet "https://docs.google.com/spreadsheets/d/1ZobtO6S0n2ogpKobVkRHR6vdldqIiNdk/edit?gid=1505732445#gid=1505732445" `
  --credentials "C:\path\to\service-account.json" `
  --output-dir output
```

Η εκτέλεση παράγει:

| Αρχείο | Περιγραφή |
|---|---|
| `output/google_dashboard_records.csv` | Αναλυτικές εγγραφές από Google Sheets |
| `output/google_dashboard_summary.json` | Συγκεντρωτικά KPIs από Google Sheets |

Το αρχείο `google_sheets_extractor.py` είναι η παραγωγική διαδρομή για αντιστοίχιση με τα τελικά χρώματα του Google Sheets API (φόντο και πρώτο πλάνο κειμένου).

### Χρωματικοί κανόνες Google Sheets (effective format)

| Φόντο ημέρας | Κείμενο | Αποτέλεσμα (χωρίς ταύτιση στη γραμμή) |
|---|---|---|
| Πράσινο οικογένειας | (οποιοδήποτε) | `pending`, πηγή `unknown` (μοναδικός αριθμός σε πράσινο χωρίς διπλότυπο) |
| Πορτοκαλί / κίτρινο | Σκούρο / μαύρο | `pending`, `supervisor` |
| Πορτοκαλί / κίτρινο | Κόκκινο | `pending`, `veltio` |
| Κόκκινο | (οποιοδήποτε) | `pending`, `veltio` |
| Λευκό / διαφανές API | Κόκκινο κείμενο | `pending`, `veltio` |
| Λευκό / διαφανές API | Λείπει / προεπιλογή | `pending`, `supervisor` |

Το Google Sheets extractor χρησιμοποιεί ανοχή κοντινού χρώματος, ώστε μικρές διαφορές RGB από theme/formatting να μην χαλάνε την ταξινόμηση.
