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
    q = urllib.parse.quote(f"{query} when:14d")
    if lang == "hu":
        return f"https://news.google.com/rss/search?q={q}&hl=hu&gl=HU&ceid=HU:hu"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def get_news(src, max_age, skip_titles=()):
    url = src.get("url") or google_news_url(src["google_news"], src.get("google_nyelv", "en"))
    out = []
    for it in parse_feed(fetch(url)):
        if not it["datum"] or it["datum"] < NOW - max_age or not it["link"]:
            continue
        if any(s.lower() in it["cim"].lower() for s in skip_titles):
            continue  # pl. szerzői vagy gyűjtőoldalak, nem cikkek
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

    def run(kind, src):
        try:
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
         "kezdes": t["kezdes"].isoformat(), "vege": t["vege"].isoformat(), "megjegyzes": t.get("megjegyzes", "")}
        for t in tournaments if t["vege"] >= today
    ]

    data = {
        "frissitve": NOW.isoformat(),
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
    print(f"Kész: {len(hirek)} hír, {len(videok)} videó, {len(versenyek)} közelgő verseny, {len(hiba)} hiba.")


if __name__ == "__main__":
    main()
