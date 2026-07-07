"""Étape 1 — Scraping. AUCUN LLM ici.

Récupère les données de marché (chiffres factuels) et les actualités du jour depuis
les sources de sources.yaml. Les chiffres produits ici transitent verbatim jusqu'au
HTML final : le LLM ne les recalcule jamais.

Chaque source échoue de façon isolée (log + continue) pour ne jamais bloquer le run.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import urljoin

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

import config
from agents.models import MarketData, ScrapedItem, ScrapeOutput

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CauriNewsBot/1.0; +newsletter BRVM)"}
TIMEOUT = 25
MAX_PER_HTML = 15   # titres retenus par source HTML générique


def _id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _load_sources() -> dict:
    if not config.SOURCES_PATH.exists():
        return {}
    return yaml.safe_load(config.SOURCES_PATH.read_text(encoding="utf-8")) or {}


def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


# --- Données de marché : parser dédié BRVM /fr/indices --------------------
def _cell_variation(td) -> str:
    """Lit une cellule de variation BRVM (span text-good/text-bad) → '+0,11' / '-0,36'."""
    span = td.find("span", class_=["text-good", "text-bad"])
    if not span:
        return td.get_text(strip=True)
    val = span.get_text(strip=True)
    if "text-good" in span.get("class", []) and not val.startswith(("+", "-")):
        val = f"+{val}"
    return val


def _parse_brvm_indices(html: str) -> MarketData:
    soup = BeautifulSoup(html, "html.parser")
    market = MarketData()

    # Table des indices principaux : celle dont le tbody contient "COMPOSITE".
    for table in soup.select("table.table-hover"):
        body_txt = table.get_text(" ", strip=True).upper()
        if "COMPOSITE" not in body_txt or "BRVM-30" not in body_txt.replace(" ", ""):
            continue
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            nom = tds[0].get_text(strip=True).upper().replace(" ", "")
            fermeture = tds[2].get_text(strip=True)
            variation = _cell_variation(tds[3])
            line = f"{fermeture} ({variation} %)"
            if "COMPOSITE" in nom:
                market.brvm_composite = line
            elif "BRVM-30" in nom:
                market.brvm_30 = line
        break

    # Top 5 hausses / Flop 5 baisses.
    def _movers(css: str) -> list[dict]:
        out = []
        table = soup.select_one(css)
        if not table:
            return out
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            out.append({
                "valeur": tds[0].get_text(strip=True),
                "cours": tds[1].get_text(strip=True),
                "variation": tds[2].get_text(" ", strip=True),
            })
        return out

    market.top_hausses = _movers("table.top-five")
    market.top_baisses = _movers("table.flop-five")
    return market


def fetch_market(sources: list[dict]) -> MarketData:
    market = MarketData()
    for src in sources:
        try:
            if src.get("type") == "brvm_indices":
                market = _parse_brvm_indices(_get(src["url"]).text)
        except Exception as e:  # noqa: BLE001
            print(f"[scrape] market '{src.get('name')}' échec : {e}")
    return market


# --- Actualités : RSS + HTML générique + World Bank -----------------------
def _rss_date(entry) -> str | None:
    """Date de publication en ISO (YYYY-MM-DD) depuis le struct_time de feedparser."""
    import time
    pp = entry.get("published_parsed") or entry.get("updated_parsed")
    return time.strftime("%Y-%m-%d", pp) if pp else None


def _fetch_rss(src: dict) -> list[ScrapedItem]:
    feed = feedparser.parse(src["url"])
    items = []
    for e in feed.entries[:30]:
        summary = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ", strip=True)
        items.append(ScrapedItem(
            id=_id(src["name"], e.get("link", e.get("title", ""))),
            source=src["name"],
            url=e.get("link"),
            published_at=_rss_date(e),
            title=(e.get("title") or "").strip(),
            text=summary[:1500],
            section_hints=src.get("sections", []),
        ))
    return items


_ISO_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _iso_day(s: str) -> str | None:
    m = _ISO_DAY.match((s or "").strip())
    return m.group(1) if m else None


def _title_and_link(container) -> tuple[str | None, str | None]:
    """Meilleur (titre, lien) dans un conteneur de carte article."""
    # 1) un lien avec un texte de titre plausible
    for a in container.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        if 20 <= len(txt) <= 200:
            return txt, a["href"]
    # 2) un lien-image porteur du titre en aria-label (ex. Sika news-thumb)
    for a in container.find_all("a", href=True):
        al = (a.get("aria-label") or "").strip()
        if 20 <= len(al) <= 200:
            return al, a["href"]
    # 3) une cellule/élément "title" (ex. BRVM avis : td.views-field-title)
    tcell = container.find(class_=re.compile("title", re.I))
    if tcell:
        txt = tcell.get_text(" ", strip=True)
        if 10 <= len(txt) <= 200:
            link = container.find("a", href=True)
            return txt, (link["href"] if link else None)
    return None, None


def _fetch_html(src: dict) -> list[ScrapedItem]:
    """Extraction datée : on part des nœuds de date (`<time datetime>` ou
    `span.date-display-single[content]`) et on remonte au conteneur pour trouver
    titre + lien. Si la page n'expose aucune date, fallback non daté (ces items
    seront écartés en mode STRICT_FRESHNESS)."""
    soup = BeautifulSoup(_get(src["url"]).text, "html.parser")
    date_nodes = soup.select("time[datetime]") + soup.select("span.date-display-single[content]")

    seen, items = set(), []
    for dn in date_nodes:
        iso = _iso_day(dn.get("datetime") or dn.get("content") or "")
        if not iso:
            continue
        node, title, link = dn, None, None
        for _ in range(4):  # remonte jusqu'à trouver un titre dans un ancêtre
            node = node.parent
            if node is None:
                break
            title, link = _title_and_link(node)
            if title:
                break
        if not title or title in seen:
            continue
        seen.add(title)
        items.append(ScrapedItem(
            id=_id(src["name"], link or title),
            source=src["name"],
            url=urljoin(src["url"], link) if link else None,
            published_at=iso,
            title=title,
            section_hints=src.get("sections", []),
        ))
        if len(items) >= MAX_PER_HTML:
            break

    return items or _fetch_html_undated(src, soup)


def _fetch_html_undated(src: dict, soup) -> list[ScrapedItem]:
    """Fallback : liens dont le texte fait 30-200 caractères, sans date."""
    seen, items = set(), []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        if not (30 <= len(title) <= 200) or title in seen:
            continue
        seen.add(title)
        items.append(ScrapedItem(
            id=_id(src["name"], title),
            source=src["name"],
            url=urljoin(src["url"], a["href"]),
            title=title,
            section_hints=src.get("sections", []),
        ))
        if len(items) >= MAX_PER_HTML:
            break
    return items


def _fetch_worldbank(src: dict) -> list[ScrapedItem]:
    """API Banque mondiale : valeur la plus récente par (pays, indicateur)."""
    items = []
    for country in src.get("countries", []):
        for ind in src.get("indicators", []):
            # mrv=1 = valeur la plus récente (mrnev est rejeté par l'API).
            url = (f"https://api.worldbank.org/v2/country/{country}/indicator/"
                   f"{ind['code']}?format=json&mrv=1")
            try:
                data = _get(url).json()
                rows = data[1] if isinstance(data, list) and len(data) > 1 else []
                if not rows or rows[0].get("value") is None:
                    continue
                row = rows[0]
                name = row["country"]["value"]
                val, year = row["value"], row["date"]
                title = f"{ind['label']} — {name} ({year}) : {val}"
                items.append(ScrapedItem(
                    id=_id("worldbank", country, ind["code"]),
                    source="worldbank",
                    url=url,
                    title=title,
                    text=title,
                    section_hints=["sack_afrique", "sur_le_continent"],
                ))
            except Exception as e:  # noqa: BLE001
                print(f"[scrape] worldbank {country}/{ind['code']} échec : {e}")
    return items


def fetch_news(news: list[dict], macro: list[dict]) -> list[ScrapedItem]:
    items: list[ScrapedItem] = []
    for src in news:
        try:
            if src.get("type") == "rss":
                items += _fetch_rss(src)
            elif src.get("type") == "html":
                items += _fetch_html(src)
        except Exception as e:  # noqa: BLE001
            print(f"[scrape] news '{src.get('name')}' échec : {e}")
    for src in macro:
        try:
            if src.get("type") == "worldbank":
                items += _fetch_worldbank(src)
        except Exception as e:  # noqa: BLE001
            print(f"[scrape] macro '{src.get('name')}' échec : {e}")

    # Déduplication par titre normalisé (les flux se recoupent souvent).
    seen, deduped = set(), []
    for it in items:
        key = it.title.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


def run(day: str | None = None) -> ScrapeOutput:
    day = day or date.today().isoformat()
    src = _load_sources()
    market = fetch_market(src.get("market", []))
    items = fetch_news(src.get("news", []), src.get("macro", []))
    print(f"[scrape] {len(items)} actus (dédupliquées) | "
          f"Composite={market.brvm_composite or '—'} | "
          f"hausses={len(market.top_hausses)} baisses={len(market.top_baisses)}")
    return ScrapeOutput(date=day, market=market, items=items)
