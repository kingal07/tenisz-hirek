"""Tenisz hírgyűjtő: letölti a hírcsatornákat, és elkészíti a docs/ mappát
(data.js az oldalnak, versenyek.ics a naptárnak). Csak a Python alapkönyvtárát használja."""

import csv
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
NOW = datetime.now(timezone.utc)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "hu,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def clean_text(s, limit=260):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "…"


def first_img(s):
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', s or "")
    return html.unescape(m.group(1)) if m else ""


def parse_feed(raw):
    """RSS 2.0 vagy Atom -> elemek listája."""
    root = ET.fromstring(raw)
    items = []
    if root.tag.endswith("rss") or root.find("channel") is not None:
        for it in root.iter("item"):
            desc = it.findtext("description") or ""
            body = it.findtext("content:encoded", namespaces=NS) or ""
            img = ""
            for tag in ("media:content", "media:thumbnail"):
                el = it.find(tag, NS)
                if el is not None and el.get("url"):
                    img = el.get("url")
                    break
            enc = it.find("enclosure")
            if not img and enc is not None and (enc.get("type") or "").startswith("image"):
                img = enc.get("url", "")
            img = img or first_img(body) or first_img(desc)
            src = it.find("source")
            items.append({
                "cim": html.unescape((it.findtext("title") or "").strip()),
                "link": (it.findtext("link") or "").strip(),
                "datum": parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                "kivonat": clean_text(desc),
                "kep": img,
                "forras_nev": src.text.strip() if src is not None and src.text else "",
            })
    else:  # Atom (pl. YouTube)
        for e in root.findall("atom:entry", NS):
            link = e.find("atom:link", NS)
            thumb = e.find("media:group/media:thumbnail", NS)
            desc = e.findtext("media:group/media:description", namespaces=NS) or ""
            items.append({
                "cim": (e.findtext("atom:title", namespaces=NS) or "").strip(),
                "link": link.get("href") if link is not None else "",
                "datum": parse_date(e.findtext("atom:published", namespaces=NS)),
                "kivonat": clean_text(desc, 200),
                "kep": thumb.get("url") if thumb is not None else "",
                "video_id": e.findtext("yt:videoId", namespaces=NS) or "",
            })
    return items


def google_news_url(query, lang):
    q = urllib.parse.quote(query)
    if lang == "hu":
        return f"https://news.google.com/rss/search?q={q}&hl=hu&gl=HU&ceid=HU:hu"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def news_feed_items(src, max_age):
    if src.get("url"):
        return parse_feed(fetch(src["url"]))
    # A Google Hírek egy kérésre legfeljebb 100 találatot ad, ezért napokra bontva kérdezzük le.
    lang = src.get("google_nyelv", "en")
    days = max(1, max_age.days)
    queries = []
    for i in range(days + 1):
        d = NOW.date() - timedelta(days=i)
        queries.append(f"{src['google_news']} after:{d} before:{d + timedelta(days=1)}")
    items = []
    for q in queries:
        try:
            items += parse_feed(fetch(google_news_url(q, lang)))
        except Exception as e:
            print(f"Google Hírek ({src['nev']}, {q}): {e}", file=sys.stderr)
    if not items:
        raise RuntimeError("a Google Hírek egyik napra sem adott találatot")
    return items


def is_article(src, title, desc="", skip_titles=()):
    """Forrásonkénti szűrők (forrasok.json): kizart (címrészlet), min_szavak, kizart_minta (regex), kizart_leiras."""
    low = title.lower()
    if any(s.lower() in low for s in list(skip_titles) + src.get("kizart", [])):
        return False
    if len(title.split()) < src.get("min_szavak", 0):
        return False
    if any(re.search(p, title) for p in src.get("kizart_minta", [])):
        return False
    if desc and any(s.lower() in desc.lower() for s in src.get("kizart_leiras", [])):
        return False
    return True


def get_news(src, max_age, skip_titles=()):
    out = []
    for it in news_feed_items(src, max_age):
        if not it["datum"] or it["datum"] < NOW - max_age or not it["link"]:
            continue
        if any(s.lower() in it["cim"].lower() for s in list(skip_titles) + src.get("kizart", [])):
            continue  # pl. szerzői vagy gyűjtőoldalak, nem cikkek
        cim_tiszta = re.sub(r"\s+-\s+[^-]+$", "", it["cim"]) if "google_news" in src else it["cim"]
        if not is_article(src, cim_tiszta, it.get("kivonat", "")):
            continue  # pl. csak egy játékosnév (profiloldal)
        cim = it["cim"]
        if "google_news" in src:
            # A Google Hírek a cím végére teszi a forrást (" - ATP Tour"), és a kivonata csak egy link.
            if it["forras_nev"] and cim.endswith(" - " + it["forras_nev"]):
                cim = cim[: -len(it["forras_nev"]) - 3]
            it["kivonat"] = ""
        out.append({
            "tipus": "hir", "forras": src["nev"], "nyelv": src.get("nyelv", ""),
            "cim": cim, "link": it["link"], "datum": it["datum"].isoformat(),
            "kivonat": it["kivonat"], "kep": it["kep"],
        })
    return out


def page_meta(html_text):
    def meta(name):
        m = re.search(r'<meta[^>]+(?:property|name)="' + re.escape(name) + r'"[^>]+content="([^"]*)"', html_text)
        return html.unescape(m.group(1)) if m else ""
    return {"cim": meta("og:title"), "kivonat": clean_text(meta("og:description")), "kep": meta("og:image"),
            "datum": parse_date(meta("article:published_time"))}


def get_sitemap_news(src, max_age, prev):
    """Cikkek egy oldaltérképből (sitemap); a már ismert cikkeket az előző futásból veszi át,
    csak az újakat tölti le."""
    root = ET.fromstring(fetch(src["sitemap"]))
    sm = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = []
    for u in root.iter(sm + "url"):
        loc, mod = u.findtext(sm + "loc"), parse_date(u.findtext(sm + "lastmod"))
        if loc and mod and mod >= NOW - max_age and "/news/" in loc:
            urls.append((mod, loc.strip()))
    urls.sort(reverse=True)
    urls = urls[: src.get("max", 80)]

    def one(item):
        _, loc = item
        if loc in prev:
            return prev[loc]
        try:
            m = page_meta(fetch(loc).decode("utf-8", "replace"))
        except Exception:
            return None
        if not m["cim"] or not is_article(src, m["cim"], m["kivonat"]):
            return None
        return {"tipus": "hir", "forras": src["nev"], "nyelv": src.get("nyelv", "en"), "cim": m["cim"], "link": loc,
                "datum": (m["datum"] or item[0]).isoformat(), "kivonat": m["kivonat"], "kep": m["kep"]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        found = [x for x in ex.map(one, urls) if x]
    # az előző futásból átvett cikkekre is érvényesek a (közben esetleg bővített) szűrők
    return [x for x in found if parse_date(x["datum"]) >= NOW - max_age and is_article(src, x["cim"], x.get("kivonat", ""))]


def load_previous(url):
    """Az előző futás hírei link szerint (hogy a már ismert cikkeket ne kelljen újra letölteni)."""
    if not url:
        return {}
    try:
        txt = fetch(url).decode("utf-8")
        data = json.loads(txt[txt.index("{"): txt.rstrip().rstrip(";").rindex("}") + 1])
        return {h["link"]: h for h in data.get("hirek", [])}
    except Exception as e:
        print(f"Előző adat nem olvasható ({e}), minden cikket újra letölt.", file=sys.stderr)
        return {}


def get_videos(src, max_age, max_n, keywords):
    # UULF = a csatorna hosszú videói (Shorts nélkül), UULV = élő adások felvételei
    cid = src["csatorna"][2:]
    out = []
    for prefix in ("UULF", "UULV"):
        try:
            raw = fetch(f"https://www.youtube.com/feeds/videos.xml?playlist_id={prefix}{cid}")
        except Exception:
            continue  # nem minden csatornának van élő adása
        for it in parse_feed(raw):
            if not it["datum"] or it["datum"] < NOW - max_age:
                continue
            if src.get("csak_tenisz") and not keywords.search(it["cim"] + " " + it["kivonat"]):
                continue
            out.append({
                "tipus": "video", "forras": src["nev"], "cim": it["cim"], "link": it["link"],
                "datum": it["datum"].isoformat(), "kep": it["kep"], "video_id": it["video_id"],
            })
    out.sort(key=lambda x: x["datum"], reverse=True)
    return out[:max_n]


def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\W+", "", it["cim"].lower())[:80] or it["link"]
        if key in seen or it["link"] in seen:
            continue
        seen.update((key, it["link"]))
        out.append(it)
    return out


# ---------------- Meccsek és ranglista (ESPN) ----------------

ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis"
GROUP_KAT = {"mens-singles": "ferfi", "womens-singles": "noi", "mens-doubles": "ferfi_paros",
             "womens-doubles": "noi_paros", "mixed-doubles": "vegyes"}
# Ha a verseny neve nem szerepel a versenyek.csv-ben, ezek a kulcsszavak döntenek a szintről
LEVEL_ALIASES = [
    ("australian open", "Grand Slam"), ("roland garros", "Grand Slam"), ("french open", "Grand Slam"),
    ("wimbledon", "Grand Slam"), ("us open", "Grand Slam"),
    ("finals", "Finals"), ("united cup", "Csapat"), ("davis cup", "Csapat"), ("billie jean", "Csapat"),
    ("laver cup", "Csapat"), ("italian open", "1000"), ("internazionali", "1000"), ("indian wells", "1000"),
    ("bnp paribas open", "1000"), ("miami", "1000"), ("madrid", "1000"), ("monte carlo", "1000"),
    ("canadian open", "1000"), ("national bank open", "1000"), ("cincinnati", "1000"), ("shanghai", "1000"),
    ("paris masters", "1000"), ("wuhan", "1000"),
]


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(s).lower()).strip()


def find_tournament(event_name, tour, tournaments):
    n = norm_name(event_name)
    for t in tournaments:
        tn = norm_name(re.sub(r"\(.*?\)", "", t["nev"]))
        if tn and (tn in n or n in tn) and (tour.upper() in t["tura"]):
            return t
    return None


def level_of(event_name, tour, tournaments):
    """Szint: Grand Slam / 1000 / 500 / 250 / 125 / Finals / Csapat."""
    n = norm_name(event_name)
    t = find_tournament(event_name, tour, tournaments)
    if t:
        kat = t["kategoria"]
        if "/" in kat:  # pl. "ATP 250 / WTA 500" -> a túrának megfelelő rész
            parts = [p.strip() for p in kat.split("/")]
            kat = next((p for p in parts if p.upper().startswith(tour.upper())), parts[-1 if tour == "wta" else 0])
    else:
        kat = next((lvl for key, lvl in LEVEL_ALIASES if key in n), None)
        if kat is None:
            # Az ESPN WTA-listájában a nem túraszintű versenyek WTA 125-ösök
            kat = "WTA 125" if tour == "wta" else "ATP 250"
    for key, lvl in (("grand slam", "Grand Slam"), ("1000", "1000"), ("500", "500"), ("250", "250"), ("125", "125"),
                     ("finals", "Finals"), ("next gen", "Finals"), ("cup", "Csapat")):
        if key in kat.lower():
            return lvl
    return kat


def side(comp):
    if comp.get("roster"):
        names = [a.get("displayName", "") for a in comp["roster"].get("athletes", [])]
        nev = comp["roster"].get("displayName") or " / ".join(names)
        orszag = ", ".join(a.get("flag", {}).get("alt", "") for a in comp["roster"].get("athletes", []))
    else:
        a = comp.get("athlete", {})
        nev, orszag = a.get("displayName", ""), a.get("flag", {}).get("alt", "")
    return {"nev": nev, "orszag": orszag, "gyoztes": bool(comp.get("winner")),
            "kiemeles": comp.get("curatedRank", {}).get("current") if isinstance(comp.get("curatedRank"), dict) else None}


def set_scores(c1, c2):
    """Szettenként [saját, ellenfél, rövidítés vagy None] a két játékos linescores mezőjéből."""
    out = []
    for a, b in zip(c1.get("linescores", []), c2.get("linescores", [])):
        x, y = int(a.get("value", 0)), int(b.get("value", 0))
        tb_a, tb_b = a.get("tiebreak"), b.get("tiebreak")
        if x + y == 1 and (tb_a is not None or tb_b is not None):
            # Szuper-rövidítés (a 3. szett helyett): a vesztes pontjai ismertek, a győztesé legalább 10
            lose = tb_a if tb_a is not None else tb_b
            win = max(10, (lose or 0) + 2)
            out.append({"r": True, "a": win if x else lose, "b": lose if x else win})
        else:
            tb = tb_a if tb_a is not None else tb_b
            out.append({"a": x, "b": y, "tb": tb})
    return out


def get_matches(tournaments, days=7):
    end = NOW.date() + timedelta(days=1)
    start = NOW.date() - timedelta(days=days)
    out = []
    for tour in ("atp", "wta"):
        data = json.loads(fetch(f"{ESPN}/{tour}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}"))
        for ev in data.get("events", []):
            szint = level_of(ev.get("name", ""), tour, tournaments)
            row = find_tournament(ev.get("name", ""), tour, tournaments) or {}
            ered = row.get(f"eredmenyek_{tour}", "")
            for g in ev.get("groupings", []):
                kat = GROUP_KAT.get(g.get("grouping", {}).get("slug", ""))
                if not kat:
                    continue
                for c in g.get("competitions", []):
                    state = c.get("status", {}).get("type", {}).get("state")
                    if state not in ("post", "in") or len(c.get("competitors", [])) != 2:
                        continue
                    p1, p2 = c["competitors"]
                    detail = c.get("status", {}).get("type", {}).get("shortDetail", "")
                    out.append({
                        "tura": tour.upper(), "verseny": ev.get("name", ""), "szint": szint, "kat": kat,
                        "ered": ered, "vid": row.get("nev", ""),
                        "kor": c.get("round", {}).get("displayName", ""), "datum": c.get("date", ""),
                        "allapot": "elo" if state == "in" else "vege",
                        "megjegyzes": "" if detail in ("Final", "FT") else detail,
                        "j1": side(p1), "j2": side(p2), "szettek": set_scores(p1, p2),
                    })
    # Vegyes párosnál az ATP és a WTA listája ugyanazt a meccset adja
    seen, uniq = set(), []
    for m in sorted(out, key=lambda m: m["datum"], reverse=True):
        key = (m["verseny"], m["kat"], frozenset((m["j1"]["nev"], m["j2"]["nev"])))
        if key not in seen:
            seen.add(key)
            uniq.append(m)
    return uniq


def get_rankings():
    out = {}
    for tour in ("atp", "wta"):
        data = json.loads(fetch(f"{ESPN}/{tour}/rankings"))
        rk = (data.get("rankings") or [{}])[0]
        out[tour] = {
            "datum": rk.get("update", ""),
            "lista": [{
                "hely": r.get("current"), "elozo": r.get("previous"), "pont": int(r.get("points") or 0),
                "nev": r.get("athlete", {}).get("displayName", ""),
                "orszag": r.get("athlete", {}).get("flagAltText") or r.get("athlete", {}).get("citizenshipCountry", ""),
                "zaszlo": r.get("athlete", {}).get("flag", ""),
            } for r in rk.get("ranks", [])],
        }
    return out


# ---------------- Versenynaptár ----------------

def load_tournaments():
    rows = []
    with open(ROOT / "versenyek.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["kezdes"] = date.fromisoformat(r["kezdes"])
            r["vege"] = date.fromisoformat(r["vege"])
            rows.append(r)
    return rows


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    b = line.encode("utf-8")
    if len(b) <= 74:
        return line
    parts, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > 73:
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += e
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def build_ics(tournaments):
    stamp = NOW.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//tenisz-hirek//versenyek//HU", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "X-WR-CALNAME:Tenisz versenyek (ATP/WTA)", "X-WR-TIMEZONE:Europe/Budapest",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
    ]
    for t in tournaments:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{t['tura']}-{t['nev']}-{t['kezdes']}".lower()).strip("-")
        desc = f"{t['tura']} · {t['kategoria']} · {t['varos']}\n{t['kezdes']:%Y.%m.%d.} – {t['vege']:%Y.%m.%d.}"
        if t.get("megjegyzes"):
            desc += f"\nMegjegyzés: {t['megjegyzes']}"
        final_start = t["vege"] - timedelta(days=1)
        events = [
            (f"{slug}-kezdes", f"🎾 Kezdődik: {t['nev']} ({t['tura']})", t["kezdes"], t["kezdes"] + timedelta(days=1)),
            (f"{slug}-dontok", f"🏆 Döntők: {t['nev']} ({t['tura']})", final_start, t["vege"] + timedelta(days=1)),
        ]
        for uid, summary, start, end in events:
            lines += [
                "BEGIN:VEVENT", f"UID:{uid}@tenisz-hirek", f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                f"SUMMARY:{ics_escape(summary)}", f"LOCATION:{ics_escape(t['varos'])}",
                f"DESCRIPTION:{ics_escape(desc)}", "TRANSP:TRANSPARENT",
                "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_escape(summary)}",
                "TRIGGER:-PT15H", "END:VALARM", "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ---------------- Fő program ----------------

def main():
    cfg = json.loads((ROOT / "forrasok.json").read_text(encoding="utf-8"))
    kw = re.compile(r"\b(" + "|".join(re.escape(k) for k in cfg["tenisz_kulcsszavak"]) + r")\b", re.I)
    news_age = timedelta(days=cfg["napok_hirek"])
    vid_age = timedelta(days=cfg["napok_videok"])

    hiba = []
    news_sources = list(cfg["hirek"]) + [
        {"nev": fb["nev"] + " (Facebook)", "nyelv": "hu", "url": fb["rss"]} for fb in cfg["facebook"] if fb.get("rss")
    ]

    prev = load_previous(cfg.get("elozo_adat"))

    def run(kind, src):
        try:
            if kind == "hir" and src.get("sitemap"):
                return get_sitemap_news(src, news_age, prev)
            if kind == "hir":
                return get_news(src, news_age, cfg.get("kizart_cimek", []))
            return get_videos(src, vid_age, cfg["max_video_csatornankent"], kw)
        except Exception as e:  # egy hibás forrás ne állítsa le az egészet
            hiba.append(f"{src['nev']}: {e}")
            print(f"HIBA – {src['nev']}: {e}", file=sys.stderr)
            return []

    jobs = [("hir", s) for s in news_sources] + [("video", s) for s in cfg["youtube"]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda j: run(*j), jobs))

    hirek = dedupe(sorted([x for (k, _), r in zip(jobs, results) if k == "hir" for x in r],
                          key=lambda x: x["datum"], reverse=True))
    videok = dedupe(sorted([x for (k, _), r in zip(jobs, results) if k == "video" for x in r],
                           key=lambda x: x["datum"], reverse=True))

    tournaments = load_tournaments()
    today = NOW.date()
    versenyek = [
        {"tura": t["tura"], "kategoria": t["kategoria"], "nev": t["nev"], "varos": t["varos"],
         "kezdes": t["kezdes"].isoformat(), "vege": t["vege"].isoformat(), "megjegyzes": t.get("megjegyzes", ""),
         "ea": t.get("eredmenyek_atp", ""), "ew": t.get("eredmenyek_wta", "")}
        for t in tournaments if t["vege"] >= today - timedelta(days=14)
    ]

    try:
        meccsek = get_matches(tournaments)
    except Exception as e:
        meccsek = []
        hiba.append(f"Meccsek (ESPN): {e}")
    try:
        ranglista = get_rankings()
    except Exception as e:
        ranglista = {}
        hiba.append(f"Ranglista (ESPN): {e}")

    data = {
        "frissitve": NOW.isoformat(),
        "meccsek": meccsek,
        "ranglista": ranglista,
        "hirek": hirek,
        "videok": videok,
        "facebook": [{"nev": f["nev"], "url": f["url"]} for f in cfg["facebook"]],
        "versenyek": versenyek,
        "hibak": hiba,
    }
    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.js").write_text(
        "window.TENISZ = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    (DOCS / "versenyek.ics").write_text(build_ics(tournaments), encoding="utf-8", newline="")
    print(f"Kész: {len(hirek)} hír, {len(videok)} videó, {len(meccsek)} meccs, {len(versenyek)} közelgő verseny, "
          f"{len(hiba)} hiba.")
    for h in hiba:
        print("  -", h)


if __name__ == "__main__":
    main()
