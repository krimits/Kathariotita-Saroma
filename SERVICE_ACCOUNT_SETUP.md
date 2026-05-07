# Google Service Account Setup

## Τι λείπει τώρα

Το dashboard είναι έτοιμο να διαβάσει live από Google Sheets, αλλά λείπει το αρχείο:

```text
C:\Users\e.krimitsas\Downloads\Dashboard\service-account.json
```

Αυτό το αρχείο δεν πρέπει να ανεβαίνει σε GitHub ή να στέλνεται δημόσια, γιατί περιέχει private key.

## Βήματα στο Google Cloud

### 1. Άνοιγμα Google Cloud Console

Άνοιξε:

```text
https://console.cloud.google.com/
```

Δημιούργησε νέο project ή επίλεξε υπάρχον.

### 2. Ενεργοποίηση Google Sheets API

Πήγαινε:

```text
APIs & Services -> Library
```

Αναζήτησε:

```text
Google Sheets API
```

Πάτησε:

```text
Enable
```

### 3. Δημιουργία Service Account

Πήγαινε:

```text
IAM & Admin -> Service Accounts
```

Πάτησε:

```text
Create service account
```

Προτεινόμενο όνομα:

```text
kathariotita-dashboard-reader
```

Δεν χρειάζεται να του δώσεις project-wide ρόλους για αυτή τη χρήση. Η πρόσβαση θα δοθεί απευθείας στο συγκεκριμένο Google Sheet.

### 4. Δημιουργία JSON key

Μέσα στο service account:

```text
Keys -> Add key -> Create new key -> JSON
```

Κατέβασε το JSON και μετονόμασέ το σε:

```text
service-account.json
```

Τοποθέτησέ το εδώ:

```text
C:\Users\e.krimitsas\Downloads\Dashboard\service-account.json
```

### 5. Share του Google Sheet στο service account

Πριν το share, βεβαιώσου ότι το αρχείο είναι native Google Sheet και όχι απλώς ανεβασμένο `.xlsx`.

Αν στο Google Drive το αρχείο εμφανίζεται ως Excel/Office file, άνοιξέ το και κάνε:

```text
File -> Save as Google Sheets
```

Μετά χρησιμοποίησε το νέο URL του Google Sheet. Το Google Sheets API δεν μπορεί να διαβάσει `effectiveFormat` από Office/XLSX document.

Άνοιξε το JSON με Notepad μόνο για να δεις το πεδίο:

```json
"client_email": "..."
```

Αντέγραψε αυτό το email.

Άνοιξε το Google Sheet:

```text
https://docs.google.com/spreadsheets/d/1ZobtO6S0n2ogpKobVkRHR6vdldqIiNdk/edit?gid=1505732445#gid=1505732445
```

Πάτησε:

```text
Share
```

Πρόσθεσε το `client_email` του service account ως:

```text
Viewer
```

### 6. Εκτέλεση extraction

Από τον φάκελο:

```text
C:\Users\e.krimitsas\Downloads\Dashboard
```

Τρέξε:

```powershell
.\run_google_extraction.cmd
```

Αν όλα είναι σωστά, θα δημιουργηθούν:

```text
output\google_dashboard_records.csv
output\google_dashboard_summary.json
```

Το web dashboard θα τα προτιμήσει αυτόματα έναντι των τοπικών Excel outputs.

## Έλεγχος

Μετά την επιτυχή εξαγωγή, άνοιξε:

```text
http://127.0.0.1:8000
```

ή ξανατρέξε:

```powershell
.\run_dashboard.cmd
```

## Συνήθη σφάλματα

### 403 ή permission denied

Το Google Sheet δεν έχει γίνει share στο `client_email` του service account.

### API has not been used or is disabled

Δεν έχει ενεργοποιηθεί το Google Sheets API στο Google Cloud project.

### Missing credentials file

Το αρχείο δεν βρίσκεται εδώ:

```text
C:\Users\e.krimitsas\Downloads\Dashboard\service-account.json
```

### Δεν ξεχωρίζει κόκκινο/πορτοκαλί

Τρέχει ακόμη το local Excel extraction και όχι το Google Sheets extraction. Πρέπει να υπάρχουν τα αρχεία:

```text
output\google_dashboard_records.csv
output\google_dashboard_summary.json
```
