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
from premailer import transform

import config
from agents.models import WriteOutput

API_VERSION = "v5.0"


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


def _find_existing(base: str, headers: dict, slug: str):
    r = requests.get(f"{base}/posts/slug/{slug}/", headers=headers, timeout=20)
    if r.status_code == 200:
        return r.json()["posts"][0]
    return None


def publish_post(
    title: str,
    slug: str,
    html: str,
    status: str,
    is_full_document: bool = True,
    email_subject: str | None = None,
    custom_excerpt: str | None = None,
) -> str:
    """Crée/met à jour un brouillon Ghost via carte HTML Lexical (verbatim).

    is_full_document : True pour un document HTML complet (on inline le CSS et on
    extrait le <body>) ; False pour un simple fragment (digest brut) utilisé tel quel.
    email_subject : sujet de l'email envoyé (défaut Ghost = titre du post).
    custom_excerpt : extrait utilisé comme texte de PREVIEW/preheader de l'email.
    Idempotent : un slug existant est mis à jour au lieu d'être dupliqué.
    """
    url = config.require("GHOST_URL", config.GHOST_URL)
    admin_key = config.require("GHOST_ADMIN_KEY", config.GHOST_ADMIN_KEY)
    base = f"{url}/ghost/api/admin"
    headers = _headers(admin_key)

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


def run(written: WriteOutput) -> str:
    """Publie la version formatée (draft 2). Conservé pour compat ; run.py appelle
    publish_post directement pour les deux brouillons."""
    return publish_post(
        written.title, f"cauri-news-{written.date}", written.html, config.PUBLISH_STATUS,
        is_full_document=True,
    )
