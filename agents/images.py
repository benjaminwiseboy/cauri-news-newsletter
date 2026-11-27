"""Étape 4c — Illustration automatique du numéro. AUCUN LLM ici.

Reproduit la mise en page faite jusqu'ici à la main dans Ghost : une image juste sous le
titre de "Hot news", "Sur le continent" et "Sack d'Afrique", et l'image de Hot news reprise
en image principale du post (feature_image).

Deux sources d'images, essayées dans l'ordre défini par section (SECTIONS ci-dessous) :
  - "source"   : l'image de partage (og:image) de l'article cité dans la section — on
                 retrouve l'article via les liens que le rédacteur met vers ses sources.
                 Téléchargée, filtrée, convertie en JPEG ≤ 1200 px puis envoyée sur Ghost.
  - "unsplash" : recherche Unsplash avec les mots-clés émis par le rédacteur (IMAGE_HOT /
                 IMAGE_CONTI / IMAGE_SACK). Conformément aux règles de l'API Unsplash, la
                 photo est affichée par son lien d'origine (hotlink, jamais recopiée), le
                 téléchargement est signalé à Unsplash et le photographe est crédité.

Règle de prudence : si aucune image ne passe les filtres, la section reste SANS image
(mieux vaut rien qu'une image hors sujet, un logo ou une vignette floue). Toute erreur est
isolée (log + continue) : l'illustration ne fait jamais échouer le run.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from html import escape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config
from agents.models import ScrapeOutput, WriteOutput
from agents.scrape import HEADERS

TIMEOUT = 20
MAX_IMAGE_BYTES = 20 * 1024 * 1024
# Largeur d'affichage dans l'email (conteneur 600 px − padding 2×18 px) : attribut width
# des <img> pour Outlook desktop, qui ignore le CSS max-width.
EMAIL_IMG_WIDTH = 564
UTM = "utm_source=cauri_news&utm_medium=referral"

# Ordre des stratégies par section — calqué sur la pratique manuelle relevée dans Ghost.
SECTIONS = {
    "hot_news": {"title": r"Hot\s*news", "order": ("source", "unsplash"), "meta": "IMAGE_HOT",
                 "fallback_query": "stock market trading screen"},
    "sur_le_continent": {"title": r"Sur\s+le\s+continent", "order": ("unsplash", "source"),
                         "meta": "IMAGE_CONTI", "fallback_query": "african city business district"},
    "sack_afrique": {"title": r"Sack\s+d['’]Afrique", "order": ("source", "unsplash"),
                     "meta": "IMAGE_SACK", "fallback_query": "african market colorful"},
}

# Sources dont l'og:image est une image générique répétée ou un logo (étude du 2026-10-06).
GENERIC_IMAGE_SOURCES = {"techcabal", "easyequities", "fratmat_economie", "brvm_avis", "worldbank"}
_GENERIC_NAME_RE = re.compile(r"logo|default|placeholder|favicon|avatar|sprite|banner-site", re.I)
_WP_SIZE_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.(?:jpe?g|png|webp)(?:\?|$))", re.I)


@dataclass
class Picked:
    src: str
    width: int
    height: int
    alt: str
    caption_html: str
    kind: str                # "source" | "unsplash"
    unsplash_id: str = ""


# --- Image de l'article source (og:image) ---------------------------------
def _og_image_url(article_url: str) -> str | None:
    r = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    if "html" not in r.headers.get("Content-Type", "html"):
        return None  # PDF (avis BRVM) ou autre : pas d'image de partage
    soup = BeautifulSoup(r.text, "html.parser")
    for attrs in ({"property": "og:image:secure_url"}, {"property": "og:image"},
                  {"name": "twitter:image"}, {"name": "twitter:image:src"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content", "").strip():
            return urljoin(article_url, tag["content"].strip())
    link = soup.find("link", rel="image_src")
    return urljoin(article_url, link["href"]) if link and link.get("href") else None


def _download(url: str) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
    r.raise_for_status()
    data = io.BytesIO()
    for chunk in r.iter_content(64 * 1024):
        data.write(chunk)
        if data.tell() > MAX_IMAGE_BYTES:
            raise ValueError("image trop lourde")
    return data.getvalue()


def _to_email_jpeg(raw: bytes) -> tuple[bytes, int, int] | None:
    """Valide puis normalise une image : renvoie (jpeg, largeur, hauteur) ou None si elle
    est trop petite, mal cadrée (bannière / portrait) ou ressemble à un logo / aplat."""
    from PIL import Image  # import local : Pillow n'est utile qu'ici

    img = Image.open(io.BytesIO(raw))
    img.load()
    w, h = img.size
    if w < config.IMAGE_MIN_WIDTH:
        print(f"[images]   rejetée : trop petite ({w}x{h})")
        return None
    ratio = w / h
    if not 0.9 <= ratio <= 2.6:
        print(f"[images]   rejetée : cadrage inadapté ({w}x{h})")
        return None
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    # Une photo a des milliers de couleurs ; un logo ou un visuel à aplats, très peu.
    colors = img.resize((64, 64)).getcolors(maxcolors=4096)
    if colors is not None and len(colors) < 300:
        print(f"[images]   rejetée : ressemble à un logo/aplat ({len(colors)} couleurs)")
        return None
    if w > config.IMAGE_MAX_WIDTH:
        h = round(h * config.IMAGE_MAX_WIDTH / w)
        w = config.IMAGE_MAX_WIDTH
        img = img.resize((w, h), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue(), w, h


def _ghost_upload(jpeg: bytes, filename: str) -> str:
    from agents.publish import API_VERSION, _jwt
    url = config.require("GHOST_URL", config.GHOST_URL)
    key = config.require("GHOST_ADMIN_KEY", config.GHOST_ADMIN_KEY)
    r = requests.post(
        f"{url}/ghost/api/admin/images/upload/",
        headers={"Authorization": f"Ghost {_jwt(key)}", "Accept-Version": API_VERSION},
        files={"file": (filename, jpeg, "image/jpeg")},
        data={"purpose": "image", "ref": filename},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"upload Ghost HTTP {r.status_code} : {r.text[:200]}")
    return r.json()["images"][0]["url"]


def _from_source(item, slug: str, upload: bool, used_src: set[str]) -> Picked | None:
    if item.source in GENERIC_IMAGE_SOURCES:
        print(f"[images]   source '{item.source}' ignorée (image générique connue)")
        return None
    og = _og_image_url(item.url)
    if not og or _GENERIC_NAME_RE.search(urlparse(og).path):
        print(f"[images]   pas d'image d'article exploitable ({item.source})")
        return None
    # Les vignettes WordPress (-300x200.jpg) ont souvent l'original juste à côté.
    candidates = [_WP_SIZE_RE.sub("", og), og] if _WP_SIZE_RE.search(og) else [og]
    for cand in candidates:
        if cand in used_src:
            return None
        try:
            norm = _to_email_jpeg(_download(cand))
        except Exception as e:  # noqa: BLE001
            print(f"[images]   téléchargement impossible ({e})")
            continue
        if not norm:
            continue
        jpeg, w, h = norm
        used_src.add(cand)
        src = _ghost_upload(jpeg, f"{slug}.jpg") if upload else cand
        domain = urlparse(item.url).netloc.removeprefix("www.")
        caption = f'Photo : <a href="{escape(item.url)}">{escape(domain)}</a>'
        return Picked(src=src, width=w, height=h, alt=item.title[:200],
                      caption_html=caption, kind="source")
    return None


# --- Unsplash ------------------------------------------------------------
def _unsplash(query: str, avoid_ids: set[str]) -> Picked | None:
    if not config.UNSPLASH_ACCESS_KEY:
        print("[images]   Unsplash non configuré (UNSPLASH_ACCESS_KEY absente)")
        return None
    headers = {"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}", "Accept-Version": "v1"}
    r = requests.get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": 15, "orientation": "landscape",
                "content_filter": "high"},
        headers=headers, timeout=TIMEOUT,
    )
    r.raise_for_status()
    for photo in r.json().get("results", []):
        if photo["id"] in avoid_ids:
            continue
        # Signalement du "téléchargement" exigé par les règles de l'API (pas de fichier
        # rapatrié : on affiche l'URL d'origine).
        try:
            requests.get(photo["links"]["download_location"], headers=headers, timeout=TIMEOUT)
        except requests.RequestException:
            pass
        w0, h0 = photo["width"], photo["height"]
        w = min(config.IMAGE_MAX_WIDTH, w0)
        h = round(h0 * w / w0)
        src = f"{photo['urls']['raw']}&w={w}&q=80&fm=jpg&fit=max"
        user = photo["user"]
        caption = (f'Photo : <a href="{escape(user["links"]["html"])}?{UTM}">{escape(user["name"])}</a>'
                   f' / <a href="https://unsplash.com/?{UTM}">Unsplash</a>')
        alt = photo.get("alt_description") or query
        return Picked(src=src, width=w, height=h, alt=alt, caption_html=caption,
                      kind="unsplash", unsplash_id=photo["id"])
    print(f"[images]   aucune photo Unsplash inédite pour « {query} »")
    return None


# --- Assemblage ----------------------------------------------------------
def _section_block(soup: BeautifulSoup, title_re: str):
    """Le <div class="pad"> qui porte le titre de section voulu."""
    pat = re.compile(rf"^\s*{title_re}\s*$", re.I)
    for t in soup.select("div.section-title"):
        if pat.match(t.get_text(" ", strip=True)):
            return t.find_parent("div", class_="pad") or t.parent
    return None


def _figure_html(p: Picked) -> str:
    return (
        f'<figure class="section-img" data-w="{p.width}" data-h="{p.height}">'
        f'<img src="{escape(p.src)}" alt="{escape(p.alt)}" width="{EMAIL_IMG_WIDTH}" '
        f'style="display:block;width:100%;max-width:100%;height:auto;">'
        f"<figcaption>{p.caption_html}</figcaption></figure>"
    )


def illustrate(written: WriteOutput, scraped: ScrapeOutput, upload: bool = True,
               avoid_unsplash: list[str] | None = None) -> WriteOutput:
    if not config.IMAGES_ENABLED:
        print("[images] désactivé (IMAGES_ENABLED=false)")
        return written

    by_url = {it.url.rstrip("/"): it for it in scraped.items if it.url}
    soup = BeautifulSoup(written.html, "html.parser")
    avoid_ids = set(avoid_unsplash or [])
    used_src: set[str] = set()
    html = written.html
    feature: Picked | None = None

    for section, cfg in SECTIONS.items():
        block = _section_block(soup, cfg["title"])
        if block is None:
            print(f"[images] {section} : section introuvable dans le HTML")
            continue
        # Articles cités dans la section, dans l'ordre d'apparition.
        items = []
        for a in block.find_all("a", href=True):
            it = by_url.get(a["href"].rstrip("/"))
            if it and it not in items:
                items.append(it)
        query = (written.image_queries.get(section) or cfg["fallback_query"]).strip()

        picked = None
        for strategy in cfg["order"]:
            try:
                if strategy == "source":
                    for it in items:
                        picked = _from_source(it, f"cauri-{written.date}-{section}", upload, used_src)
                        if picked:
                            break
                else:
                    picked = _unsplash(query, avoid_ids)
            except Exception as e:  # noqa: BLE001 — une image ratée ne bloque jamais le run
                print(f"[images] {section} : échec {strategy} ({e})")
                picked = None
            if picked:
                break

        if not picked:
            print(f"[images] {section} : aucune image retenue — section laissée sans image")
            continue
        if picked.unsplash_id:
            avoid_ids.add(picked.unsplash_id)
            written.unsplash_ids.append(picked.unsplash_id)
        print(f"[images] {section} : {picked.kind} {picked.width}x{picked.height} — {picked.src[:90]}")

        # Insertion juste après le titre de section (même place qu'en mise en page manuelle).
        title_re = re.compile(rf'(<div class="section-title">\s*{cfg["title"]}\s*</div>)', re.I)
        html, n = title_re.subn(lambda m: m.group(1) + _figure_html(picked), html, count=1)
        if n and feature is None:  # Hot news d'abord ; sinon la 1re image du numéro
            feature = picked

    written.html = html
    if feature:
        written.feature_image = feature.src
        written.feature_image_alt = feature.alt[:190]
        written.feature_image_caption = feature.caption_html
    return written
