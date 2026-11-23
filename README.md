# Teniszhírek – saját hírgyűjtő

Egy oldal, ami 2 óránként magától összegyűjti a teniszhíreket, a YouTube-videókat és a versenynaptárt.
Gépről és telefonról is ugyanazon a linken éred el. Ingyenes, nem használ AI-t és tokent.

## Mi van benne

| Fájl | Mire való |
|---|---|
| `forrasok.json` | A források listája. Itt lehet hozzáadni vagy törölni oldalakat és YouTube-csatornákat. |
| `versenyek.csv` | A 2027-es ATP- és WTA-versenyek (kezdés, vége). Ebből készül a naptár. |
| `build.py` | A program, ami begyűjti a híreket (a GitHub futtatja). |
| `docs/` | Maga a weboldal. |
| `.github/workflows/frissites.yml` | Ez mondja meg a GitHubnak, hogy 2 óránként futtassa a programot. |

## Beállítás (egyszeri, kb. 10 perc)

1. **GitHub-fiók**: lépj be a [github.com](https://github.com) oldalon, vagy regisztrálj (ingyenes).
2. **Új tároló**: jobb felül **+** → **New repository**.
   - Név: `tenisz-hirek`
   - Láthatóság: **Public**
   - Kattints a **Create repository** gombra.
3. **Fájlok feltöltése**: az új tároló oldalán kattints az **uploading an existing file** linkre.
   Nyisd meg a `TeniszHirek` mappát, jelöld ki **a teljes tartalmát** (`.github`, `docs`, `build.py`, `forrasok.json`,
   `versenyek.csv`, `README.md`, `.gitignore`), és húzd be a böngészőbe. Lent: **Commit changes**.
   - Ellenőrizd, hogy a `.github` mappa is feltöltődött-e. Ha nem, a böngészőben kattints az **Add file → Create new file**
     gombra, a névhez írd be: `.github/workflows/frissites.yml`, és másold bele a fájl tartalmát.
4. **Weboldal bekapcsolása**: **Settings** → bal oldalt **Pages** → **Source**: válaszd a **GitHub Actions** lehetőséget.
5. **Első futtatás**: **Actions** fül → bal oldalt **Frissítés** → **Run workflow** → **Run workflow**.
   1-2 perc múlva zöld pipa jelenik meg.
6. **Az oldalad címe**: `https://FELHASZNÁLÓNEVED.github.io/tenisz-hirek/`
   (a **Settings → Pages** oldalon is kiírja).

## Telefonon

Nyisd meg a linket a telefonodon, majd:
- **iPhone (Safari)**: Megosztás gomb → **Főképernyőhöz adás**
- **Android (Chrome)**: ⋮ menü → **Hozzáadás a kezdőképernyőhöz**

Ettől kezdve úgy működik, mint egy alkalmazás.

## Versenynaptár a Google Naptárban

1. **Számítógépen** nyisd meg az oldalt → **Versenyek** fül → **Hozzáadás a Google Naptárhoz** → erősítsd meg.
   (Telefonos Google Naptár alkalmazásban nem lehet linkről naptárat felvenni, ezt egyszer gépen kell megcsinálni.)
2. **Értesítés beállítása**: Google Naptár → bal oldalt a „Tenisz versenyek (ATP/WTA)” naptár melletti ⋮ →
   **Beállítások és megosztás** → **Eseményértesítések** / **Egész napos események értesítései** → pl. „1 nappal előtte, 9:00”.
   Ezután a telefonodon is jön az értesítés.

Minden versenynél két esemény van: **🎾 Kezdődik** (első nap) és **🏆 Döntők** (az utolsó két nap).
A Google naponta kb. egyszer nézi meg, változott-e a naptár.

## Forrás hozzáadása később

Nyisd meg a GitHubon a `forrasok.json` fájlt → ceruza ikon → írd be az újat a többi mintájára → **Commit changes**.
Pár perc múlva megjelenik az oldalon.

- **Weboldal saját hírcsatornával (RSS)**: `{ "nev": "Név", "nyelv": "hu", "url": "https://.../feed/" }`
- **Weboldal hírcsatorna nélkül** (a Google Híreken keresztül): `{ "nev": "Név", "nyelv": "en", "google_news": "site:pelda.com", "google_nyelv": "en" }`
- **YouTube-csatorna**: a csatorna azonosítója (`UC…`) kell hozzá; ezt én szívesen kikeresem.
- **Facebook-oldal**: ha egy szolgáltatással (pl. RSS.app) csinálsz hozzá hírcsatornát, a linket írd az oldal `rss` mezőjébe.

## Tudnivalók

- **ATP, WTA, Eurosport**: ezek az oldalak nem adnak saját hírcsatornát, vagy letiltják a gépi letöltést,
  ezért a cikkeik a Google Híreken keresztül érkeznek. A linkre kattintva a Google átirányít az eredeti cikkre.
- **Versenynaptár**: az ATP-dátumok az ATP hivatalos 2027-es naptárából vannak. A WTA hivatalos teljes naptára még nem
  jelent meg, ezért a WTA-dátumok egy nem hivatalos összesítésből származnak (az oldalon jelölve). A Billie Jean King Kupa
  döntője még nincs benne, mert nincs ismert dátuma. Ha kijön a hivatalos lista, a `versenyek.csv` frissítendő.
- **Wide World of Sports, TNT Sports, Eurosport Magyarország** YouTube-csatornáiról csak a teniszes videók jelennek meg
  (kulcsszavak alapján, ezek a `forrasok.json` végén bővíthetők).
