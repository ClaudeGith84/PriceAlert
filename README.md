# Preiswächter (Black Friday)

Prüft alle 30 Minuten die Preise deiner Artikel und schickt eine Push-Nachricht aufs Handy, sobald ein Preis sinkt.
Läuft kostenlos über GitHub Actions; der Preisverlauf landet als CSV im Repo.

## Einrichtung (ca. 10 Minuten)

1. **Repo anlegen**: auf GitHub ein neues Repository erstellen und diese Dateien hochladen
   (Ordner `.github` nicht vergessen).
   Öffentlich = unbegrenzte Actions-Minuten, aber Watchlist, Preisverlauf (`data/`) und Action-Logs sind für alle sichtbar.
   Privat = nichts davon öffentlich, dafür zählen die Läufe gegen das freie Minuten-Kontingent.
2. **ntfy einrichten**: App „ntfy“ installieren (iOS/Android) → `+` → einen Kanalnamen abonnieren.
   Der Kanalname ist bei ntfy.sh das einzige Geheimnis: Wer ihn kennt, kann mitlesen **und dir gefälschte
   Nachrichten (mit beliebigem Link) schicken**. Erzeuge ihn zufällig, statt einen Namen aus einer Anleitung zu
   übernehmen, z. B. mit `python -c "import secrets; print('bf-' + secrets.token_urlsafe(18))"`.
   Noch sicherer: ntfy-Konto mit reserviertem Kanal und Zugriffstoken (dann zusätzlich Secret `NTFY_TOKEN`).
3. **Secret hinterlegen**: im Repo *Settings → Secrets and variables → Actions → New repository secret*
   - Name: `NTFY_TOPIC`, Wert: dein Kanalname
   - optional `NTFY_TOKEN`: dein ntfy-Zugriffstoken
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
pip install --require-hashes -r requirements.txt
python -m pricewatch --probe "https://www.shop.de/produkt/123"   # einzelne Seite testen
export NTFY_TOPIC=<dein-zufälliger-kanalname>                     # Windows: set NTFY_TOPIC=...
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

## Abhängigkeiten aktualisieren

`requirements.txt` ist mit Versionen und Hashes festgeschrieben und wird aus `requirements.in` erzeugt
(Dependabot schlägt Updates wöchentlich vor, ebenso für die gepinnten GitHub Actions):

```bash
uv pip compile requirements.in --python-version 3.12 --generate-hashes -o requirements.txt
```
