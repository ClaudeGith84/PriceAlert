# Preiswächter (Black Friday)

Prüft alle 30 Minuten die Preise deiner Artikel und schickt eine Push-Nachricht aufs Handy, sobald ein Preis sinkt.
Läuft kostenlos über GitHub Actions; der Preisverlauf landet als CSV im Repo.

## Einrichtung (ca. 10 Minuten)

1. **Repo anlegen**: auf GitHub ein neues, **öffentliches** Repository erstellen und diese Dateien hochladen
   (Ordner `.github` nicht vergessen).
2. **ntfy einrichten**: App „ntfy“ installieren (iOS/Android) → `+` → einen Kanalnamen abonnieren.
   Nimm einen schwer erratbaren Namen, z. B. `bf-preise-k7x29q` – wer den Namen kennt, kann mitlesen.
3. **Secret hinterlegen**: im Repo *Settings → Secrets and variables → Actions → New repository secret*
   - Name: `NTFY_TOPIC`, Wert: dein Kanalname
4. **Test**: *Actions → Preiswächter → Run workflow*, Haken bei „Nur Testnachricht senden“ → die Nachricht sollte aufs Handy kommen.
5. **Erster echter Lauf**: noch einmal *Run workflow* ohne Haken. Danach solltest du „Überwachung gestartet“ bekommen.
   Im Log von „Preise prüfen“ steht pro Shop der gelesene Preis oder der Fehler.

Danach läuft alles automatisch. Aktuelle Preise: `data/summary.md`, kompletter Verlauf: `data/prices.csv`.

## Artikel hinzufügen

`watchlist.yaml` bearbeiten (geht auch im GitHub-Webeditor am Handy). Pro Artikel eine oder mehrere Produktseiten;
verglichen wird jeweils der günstigste Preis. Geizhals-Seiten decken viele Shops auf einmal ab.

```yaml
  - name: Sony WH-1000XM6
    target_price: 299        # optional: zusätzlicher Alarm mit hoher Priorität
    sources:
      - url: https://geizhals.de/...
      - url: https://www.shop.de/produkt/123
        selector: ".price"   # nur nötig, wenn der Preis nicht automatisch gefunden wird
```

## Wann kommt eine Nachricht?

- **Preis gesunken**: bester Preis liegt mindestens 1 % unter dem Referenzpreis (einstellbar: `min_drop_pct`, `0` = jede Senkung).
  Kleine Senkungen summieren sich. Steigt der Preis wieder, wird ab dem höheren Niveau neu gemessen.
- **Zielpreis erreicht** (falls gesetzt): einmalig, mit hoher Priorität.
- **Warnung**, wenn ein Artikel 6 Läufe in Folge keinen Preis liefert (Shop blockiert oder Seite geändert).

## Wenn ein Shop blockiert

Manche Shops (v. a. Amazon) sperren Abrufe aus Rechenzentren. Dann im Log `blocked` oder `HTTP 403`.
Optionen: Geizhals-Seite statt Shopseite nutzen, oder das Tool auf dem eigenen PC laufen lassen:

```bash
pip install -r requirements.txt
python -m pricewatch --probe "https://www.shop.de/produkt/123"   # einzelne Seite testen
export NTFY_TOPIC=bf-preise-k7x29q                               # Windows: set NTFY_TOPIC=...
python -m pricewatch                                             # ein Durchlauf
```

Regelmäßig ausführen per `cron` (Linux/macOS) oder Aufgabenplanung (Windows).

## Optionen

| Befehl | Wirkung |
|---|---|
| `python -m pricewatch` | ein Durchlauf: prüfen, speichern, benachrichtigen |
| `--dry-run` | prüfen ohne Speichern/Senden |
| `--only airpods-pro-3` | nur einen Artikel prüfen |
| `--probe URL [--selector CSS]` | eine Seite testen, HTML wird in `probe.html` gesichert |
| `--test-notify` | nur Testnachricht |

Tests: `pip install pytest && pytest`
