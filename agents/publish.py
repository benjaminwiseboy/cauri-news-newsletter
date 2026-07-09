"""Étape 5 — Publication Ghost.

Port Python de ghost-publish-card.mjs : on inline le CSS (premailer) et on
insère le corps VERBATIM dans une "carte HTML" Lexical, ce qui préserve styles
inline, fonds de couleur et <div> décorés (contrairement à ?source=html).

Idempotence : si un post au même slug existe déjà pour la date, on le met à jour
au lieu d'en créer un doublon.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from premailer import transform

import config
from agents.models import WriteOutput

API_VERSION = "v5.0"

# Bits de format Lexical (standard Meta Lexical, repris par l'éditeur Koenig de Ghost).
_BOLD = 1
_ITALIC = 2


def _b64url(b: bytes) -> str:
    return base64.b64encode(b).decode().rstrip("=").replace("+", "-").replace("/", "_")


def _jwt(admin_key: str) -> str:
    key_id, secret = admin_key.split(":")
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode())
    payload = _b64url(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(bytes.fromhex(secret), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def _headers(admin_key: str) -> dict:
    return {
        "Authorization": f"Ghost {_jwt(admin_key)}",
        "Content-Type": "application/json",
        "Accept-Version": API_VERSION,
    }


def _body_html(full_html: str) -> str:
    """Inline le CSS puis extrait le contenu du <body>, sans les <style>."""
    inlined = transform(full_html)
    m = re.search(r"<body[^>]*>([\s\S]*)</body>", inlined, re.IGNORECASE)
    body = m.group(1) if m else inlined
    return re.sub(r"<style[\s\S]*?</style>", "", body, flags=re.IGNORECASE).strip()


def _text_node(text: str, fmt: int = 0) -> dict:
    return {"detail": 0, "format": fmt, "mode": "normal", "style": "", "text": text, "type": "text", "version": 1}


def _inline_children(tag: Tag, fmt: int = 0) -> list[dict]:
    """Convertit le contenu INLINE d'une balise (texte, <b>, <i>, <a>) en nœuds Lexical.
    Les styles/classes CSS (pills, couleurs...) sont perdus : un bloc natif Ghost ne
    connaît que gras/italique/lien — c'est le compromis attendu du mode 'corps éditable'."""
    out: list[dict] = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            s = re.sub(r"\s+", " ", str(child))
            if s:  # préserve un espace seul entre deux balises inline (ex. </b> <b>)
                out.append(_text_node(s, fmt))
            continue
        if child.name in ("b", "strong"):
            out.extend(_inline_children(child, fmt | _BOLD))
        elif child.name in ("i", "em"):
            out.extend(_inline_children(child, fmt | _ITALIC))
        elif child.name == "a" and child.get("href"):
            link_children = _inline_children(child, fmt | _BOLD)  # liens de source toujours en gras
            out.append({
                "type": "link", "version": 1, "direction": None, "format": "", "indent": 0,
                "rel": None, "target": None, "title": None, "url": child["href"],
                "children": link_children or [_text_node(child.get_text(), fmt)],
            })
        elif child.name == "br":
            out.append({"type": "linebreak", "version": 1})
        elif child.name in ("ul", "ol"):
            # liste imbriquée (ex. faits_clés dans le digest brut) : pas de nesting Lexical
            # ici, on l'aplatit en puces texte séparées par des sauts de ligne.
            for li in child.find_all("li", recursive=False):
                if out:
                    out.append({"type": "linebreak", "version": 1})
                out.append(_text_node("• ", fmt))
                out.extend(_inline_children(li, fmt))
        else:
            out.extend(_inline_children(child, fmt))
    return out


def _paragraph(tag: Tag) -> dict:
    return {"type": "paragraph", "version": 1, "direction": None, "format": "", "indent": 0,
            "children": _inline_children(tag) or [_text_node(tag.get_text())]}


def _heading(tag: Tag, level: str) -> dict:
    return {"type": "heading", "tag": level, "version": 1, "direction": None, "format": "", "indent": 0,
            "children": _inline_children(tag) or [_text_node(tag.get_text())]}


def _quote(tag: Tag) -> dict:
    return {"type": "quote", "version": 1, "direction": None, "format": "", "indent": 0,
            "children": _inline_children(tag) or [_text_node(tag.get_text())]}


def _list_node(li_tags: list[Tag], ordered: bool = False) -> dict:
    items = [
        {"type": "listitem", "version": 1, "value": i + 1, "direction": None, "format": "", "indent": 0,
         "children": _inline_children(li) or [_text_node(li.get_text())]}
        for i, li in enumerate(li_tags)
    ]
    tag_name = "ol" if ordered else "ul"
    return {"type": "list", "version": 1, "direction": None, "format": "", "indent": 0,
            "listType": "number" if ordered else "bullet", "tag": tag_name, "start": 1, "children": items}


def _horizontal_rule() -> dict:
    return {"type": "horizontalrule", "version": 1}


def _lecon_nodes(lecon_box: Tag) -> list[dict]:
    """'La leçon' : le titre pédagogique reste un heading bien mis en valeur ; chaque
    paragraphe d'explication devient une citation (blockquote) — le callout donnait une
    mise en page jugée mauvaise."""
    nodes: list[dict] = []
    for child in lecon_box.find_all(recursive=False):
        if child.name == "p" and "lecon-title" in (child.get("class") or []):
            nodes.append(_heading(child, "h3"))
        elif child.name == "p":
            nodes.append(_quote(child))
    return nodes


_TITLE_CLASSES = {"section-title", "edito-title"}
_SMALL_TEXT_CLASSES = {"disclaimer", "foot-note"}


def _walk_block(tag: Tag, out: list[dict]) -> None:
    """Aplati récursivement un bloc HTML (les <div class='pad'> ne sont que des conteneurs
    de mise en page) en une suite de nœuds Lexical natifs (heading/paragraph/list/hr)."""
    if isinstance(tag, NavigableString):
        return
    if tag.name == "hr":
        out.append(_horizontal_rule())
        return
    classes = set(tag.get("class") or [])
    if tag.name == "table" and "mkt" in classes:
        # Tableau marché : carte HTML verbatim (déjà stylé par premailer), pas de conversion
        # native — pas d'équivalent Ghost fiable pour les badges colorés ▲/▼.
        out.append({"type": "html", "version": 1, "html": str(tag)})
        return
    if tag.name == "ul":
        out.append(_list_node(tag.find_all("li", recursive=False)))
        return
    if tag.name == "div" and "lecon-box" in classes:
        out.extend(_lecon_nodes(tag))
        return
    if tag.name == "div" and "hot-title" in classes:
        out.append(_heading(tag, "h3"))
        return
    if tag.name == "p" and classes & _SMALL_TEXT_CLASSES:
        # Disclaimer / note de bas de section : italique + petite police, non disponible
        # nativement dans un bloc Ghost → reste une mini carte HTML (déjà stylée par premailer).
        out.append({"type": "html", "version": 1, "html": str(tag)})
        return
    if tag.name == "p" and "lecon-title" in classes:
        out.append(_heading(tag, "h3"))
        return
    if tag.name == "p":
        out.append(_paragraph(tag))
        return
    if tag.name == "div" and classes & _TITLE_CLASSES:
        out.append(_heading(tag, "h3"))
        return
    if tag.name == "div":
        for child in tag.find_all(recursive=False):
            _walk_block(child, out)
        return
    out.append(_paragraph(tag))  # repli : bloc inconnu traité comme paragraphe


def _split_sections(inlined_html: str) -> tuple[str, list[dict], str]:
    """Découpe le document HTML (CSS déjà inliné) en 3 zones :
    (header_html, body_lexical_nodes, footer_html). Header/footer restent des cartes HTML
    verbatim ; le corps devient des blocs Ghost natifs (éditables directement dans Ghost)."""
    soup = BeautifulSoup(inlined_html, "html.parser")
    wrap = soup.find("div", class_="wrap") or soup
    header_tag = wrap.find("table", class_="header")
    support_tag = wrap.find("div", class_="support")
    header_html = str(header_tag) if header_tag else ""
    footer_html = str(support_tag) if support_tag else ""

    body_nodes: list[dict] = []
    started = header_tag is None
    for child in wrap.find_all(recursive=False):
        if child is header_tag:
            started = True
            continue
        if child is support_tag:
            break
        if not started:
            continue
        _walk_block(child, body_nodes)
    return header_html, body_nodes, footer_html


def _fragment_to_lexical_nodes(fragment_html: str) -> list[dict]:
    """Convertit un fragment HTML simple (sans header/footer/wrap — ex. le digest brut)
    en blocs Lexical natifs. Contrairement à `_walk_block`, les titres h1/h2 sont conservés
    tels quels (pas de contrainte h3 : c'est un document de travail, pas la newsletter)."""
    soup = BeautifulSoup(f"<div>{fragment_html}</div>", "html.parser")
    nodes: list[dict] = []
    for child in soup.div.find_all(recursive=False):
        if child.name in ("h1", "h2", "h3", "h4"):
            nodes.append(_heading(child, child.name))
        elif child.name == "p":
            nodes.append(_paragraph(child))
        elif child.name in ("ul", "ol"):
            nodes.append(_list_node(child.find_all("li", recursive=False), ordered=child.name == "ol"))
        elif child.name == "hr":
            nodes.append(_horizontal_rule())
        else:
            nodes.append(_paragraph(child))
    return nodes


def _find_existing(base: str, headers: dict, slug: str):
    r = requests.get(f"{base}/posts/slug/{slug}/", headers=headers, timeout=20)
    if r.status_code == 200:
        return r.json()["posts"][0]
    return None


def _upsert(url: str, admin_key: str, slug: str, fields: dict, status: str) -> str:
    """POST ou PUT idempotent (par slug) d'un post Ghost déjà construit (title/slug/lexical/...)."""
    base = f"{url}/ghost/api/admin"
    headers = _headers(admin_key)
    existing = _find_existing(base, headers, slug)
    payload = {"posts": [fields]}

    if existing:
        payload["posts"][0]["updated_at"] = existing["updated_at"]  # collision optimiste Ghost
        r = requests.put(
            f"{base}/posts/{existing['id']}/?source=html",
            headers=_headers(admin_key), data=json.dumps(payload), timeout=30,
        )
        action = "mis à jour"
    else:
        r = requests.post(
            f"{base}/posts/?source=html",
            headers=_headers(admin_key), data=json.dumps(payload), timeout=30,
        )
        action = "créé"

    if not r.ok:
        raise RuntimeError(f"Ghost HTTP {r.status_code} : {r.text}")

    post = r.json()["posts"][0]
    editor = f"{url}/ghost/#/editor/post/{post['id']}"
    print(f"[publish] '{slug}' {action} ({status}) : {editor}")
    return editor


def publish_post(
    title: str,
    slug: str,
    html: str,
    status: str,
    is_full_document: bool = True,
    email_subject: str | None = None,
    custom_excerpt: str | None = None,
) -> str:
    """Crée/met à jour un brouillon Ghost via carte HTML Lexical (verbatim, un seul bloc).

    is_full_document : True pour un document HTML complet (on inline le CSS et on
    extrait le <body>) ; False pour un simple fragment (digest brut) utilisé tel quel.
    email_subject : sujet de l'email envoyé (défaut Ghost = titre du post).
    custom_excerpt : extrait utilisé comme texte de PREVIEW/preheader de l'email.
    Idempotent : un slug existant est mis à jour au lieu d'être dupliqué.
    """
    url = config.require("GHOST_URL", config.GHOST_URL)
    admin_key = config.require("GHOST_ADMIN_KEY", config.GHOST_ADMIN_KEY)

    body = _body_html(html) if is_full_document else html
    lexical = json.dumps({
        "root": {
            "type": "root", "format": "", "indent": 0, "version": 1, "direction": None,
            "children": [{"type": "html", "version": 1, "html": body}],
        }
    })

    fields = {"title": title, "slug": slug, "lexical": lexical, "status": status}
    if email_subject:
        fields["email_subject"] = email_subject
    if custom_excerpt:
        fields["custom_excerpt"] = custom_excerpt
    return _upsert(url, admin_key, slug, fields, status)


def publish_post_hybrid(
    title: str,
    slug: str,
    html: str,
    status: str,
    email_subject: str | None = None,
    custom_excerpt: str | None = None,
) -> str:
    """Variante EXPÉRIMENTALE de publish_post : header et footer restent des cartes HTML
    verbatim (branding, bouton d'abonnement) ; tout le corps entre les deux (marché, hot
    news, la leçon, sur le continent, sack d'afrique, radar) est converti en blocs Ghost
    NATIFS (heading/paragraph/list), éditables directement dans l'éditeur Ghost.

    Compromis assumé : les styles/classes CSS du corps (couleurs, badges pill...) sont
    perdus — un bloc natif Ghost ne connaît que gras/italique/lien. Header et footer, eux,
    gardent tout leur style (CSS inliné comme dans publish_post).
    """
    url = config.require("GHOST_URL", config.GHOST_URL)
    admin_key = config.require("GHOST_ADMIN_KEY", config.GHOST_ADMIN_KEY)

    inlined = transform(html)
    header_html, body_nodes, footer_html = _split_sections(inlined)
    children = []
    if header_html:
        children.append({"type": "html", "version": 1, "html": header_html})
    children.extend(body_nodes)
    if footer_html:
        children.append({"type": "html", "version": 1, "html": footer_html})

    lexical = json.dumps({
        "root": {"type": "root", "format": "", "indent": 0, "version": 1, "direction": None,
                 "children": children}
    })

    fields = {"title": title, "slug": slug, "lexical": lexical, "status": status}
    if email_subject:
        fields["email_subject"] = email_subject
    if custom_excerpt:
        fields["custom_excerpt"] = custom_excerpt
    return _upsert(url, admin_key, slug, fields, status)


def publish_fragment_native(title: str, slug: str, fragment_html: str, status: str) -> str:
    """Publie un fragment HTML simple (le digest brut, sans header/footer) en blocs Ghost
    natifs plutôt qu'en carte HTML verbatim — éditable directement dans Ghost."""
    url = config.require("GHOST_URL", config.GHOST_URL)
    admin_key = config.require("GHOST_ADMIN_KEY", config.GHOST_ADMIN_KEY)

    nodes = _fragment_to_lexical_nodes(fragment_html)
    lexical = json.dumps({
        "root": {"type": "root", "format": "", "indent": 0, "version": 1, "direction": None,
                 "children": nodes}
    })
    fields = {"title": title, "slug": slug, "lexical": lexical, "status": status}
    return _upsert(url, admin_key, slug, fields, status)


def run(written: WriteOutput) -> str:
    """Publie la version formatée (draft 2). Conservé pour compat ; run.py appelle
    publish_post directement pour les deux brouillons."""
    return publish_post(
        written.title, f"cauri-news-{written.date}", written.html, config.PUBLISH_STATUS,
        is_full_document=True,
    )
