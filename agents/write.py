"""Étape 4 — Rédaction. Assemble le numéro HTML complet selon la charte.

Le modèle choisit UN candidat par section parmi les 3 proposés, puis rédige.
Les données de marché sont injectées comme FAITS à ne jamais modifier.
Un numéro de référence (nettoyé) est fourni comme exemple de ton/style/HTML.
"""
from __future__ import annotations

import re
from datetime import date

import config
from agents.llm import complete_text
from agents.models import ScrapeOutput, SelectOutput, WriteOutput

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
         "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def french_date(iso: str) -> str:
    """'2026-07-07' -> 'Mardi 7 juillet 2026' (sans dépendre de la locale système)."""
    d = date.fromisoformat(iso)
    return f"{_JOURS[d.weekday()].capitalize()} {d.day} {_MOIS[d.month - 1]} {d.year}"


def _template() -> str:
    return config.TEMPLATE_PATH.read_text(encoding="utf-8") if config.TEMPLATE_PATH.exists() else ""


_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)


def _enforce_style(model_html: str, template_html: str) -> str:
    """Remplace le <style> produit par le modèle par le <style> canonique du template.
    Les styles (header centré, tailles, tableau marché, footer, bouton) ne peuvent donc
    plus dériver d'un run à l'autre. On suppose que le modèle réutilise les mêmes classes
    (imposé par le prompt + l'exemple)."""
    m = _STYLE_RE.search(template_html)
    if not m:
        return model_html
    canonical = m.group(0)
    if _STYLE_RE.search(model_html):
        return _STYLE_RE.sub(lambda _: canonical, model_html, count=1)
    # pas de <style> dans la sortie : on l'injecte dans le <head>
    return re.sub(r"</head>", canonical + "\n</head>", model_html, count=1, flags=re.IGNORECASE)


_HEADER_RE = re.compile(r'<(?:div|table)[^>]*class="[^"]*header[^"]*".*?</(?:div|table)>\s*</div>',
                        re.DOTALL | re.IGNORECASE)


def canonical_header(date_fr: str) -> str:
    """En-tête email BULLETPROOF : table width=100% (ne peut jamais déborder la largeur
    du conteneur, contrairement à un <div> à fond coloré). Contenu fixe sauf la date."""
    return (
        '<table role="presentation" class="header" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:#0e2f44;border-collapse:collapse;">'
        '<tr><td style="padding:18px 16px;text-align:center;color:#ffffff;">'
        '<div class="logo">Cauri <span>News</span></div>'
        '<div class="tagline">La BRVM et l\'économie africaine, expliquée simplement.</div>'
        f'<div class="date">{date_fr}</div>'
        '</td></tr></table>'
    )


def _fix_body(html: str, date_fr: str) -> str:
    """Normalise le body pour l'email :
    - remplace l'en-tête par la table canonique (anti-débordement mobile garanti) ;
    - dans le bloc soutien (dernier bloc), les <p> deviennent des <div class="support-line">
      pour que le texte reste BLANC (Ghost force la couleur des <p> en foncé)."""
    if _HEADER_RE.search(html):
        html = _HEADER_RE.sub(lambda _: canonical_header(date_fr), html, count=1)
    idx = html.find('<div class="pad support">')
    if idx != -1:  # tout ce qui suit = bloc soutien + fermetures, aucun autre <p>
        head, tail = html[:idx], html[idx:]
        tail = tail.replace("<p>", '<div class="support-line">').replace("</p>", "</div>")
        html = head + tail
    return html


def _parse_meta(raw: str) -> tuple[str, str, str]:
    """Extrait 'SUBJECT:' et 'PREVIEW:' produits en tête par le modèle, puis renvoie
    (subject, preview, reste_html)."""
    m_s = re.search(r"(?im)^\s*SUBJECT\s*:\s*(.+?)\s*$", raw)
    m_p = re.search(r"(?im)^\s*PREVIEW\s*:\s*(.+?)\s*$", raw)
    subject = m_s.group(1).strip() if m_s else ""
    preview = m_p.group(1).strip() if m_p else ""
    # le HTML commence au doctype / html / body
    low = raw.lower()
    i = min((p for p in (low.find("<!doctype"), low.find("<html"), low.find("<body")) if p != -1),
            default=-1)
    html_part = raw[i:] if i != -1 else raw
    return subject, preview, html_part


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def derive_meta(html: str) -> tuple[str, str]:
    """Secours (sans LLM) : déduit (subject, preview) du HTML. Best-effort — la vraie
    qualité vient des lignes SUBJECT/PREVIEW produites par le modèle."""
    body = html.split("</style>")[-1]
    # subject : titre Hot news si présent, sinon <title> du document
    ht = re.search(r'class="hot-title"[^>]*>(.*?)</', body, re.DOTALL)
    if ht:
        subject = _clean_text(ht.group(1))
    else:
        t = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        subject = _clean_text(t.group(1)) if t else "Cauri News"
    # preview : 1re phrase du 1er paragraphe du corps
    p = re.search(r"<p[^>]*>(.*?)</p>", body, re.DOTALL)
    preview = re.split(r"(?<=[.!?])\s", _clean_text(p.group(1)))[0][:150] if p else ""
    return subject, preview


def _extract_html(raw: str) -> str:
    fenced = re.search(r"```(?:html)?\s*(.*?)```", raw, re.DOTALL)
    return (fenced.group(1) if fenced else raw).strip()


def run(scraped: ScrapeOutput, selection: SelectOutput) -> WriteOutput:
    template_html = _template()
    system = (
        config.load_prompt("write")
        + "\n\n---\nCHARTE ÉDITORIALE (à respecter à la lettre) :\n"
        + config.read_reference(config.CHARTE_PATH)
        + f"\n\n---\nURL D'ABONNEMENT (bouton S'abonner) : {config.SUBSCRIBE_URL}\n"
        + "\n---\nTEMPLATE DE RÉFÉRENCE (reprends sa structure, ses classes CSS et son ton — "
        "NE COPIE PAS son contenu, qui est un exemple) :\n"
        + template_html
    )

    date_fr = french_date(scraped.date)
    user = (
        f"DATE D'ÉDITION (à utiliser telle quelle, ne recalcule pas le jour) : {date_fr}\n"
        f"(date ISO {scraped.date})\n\n"
        f"DONNÉES DE MARCHÉ (FAITS — à recopier tels quels, ne jamais inventer ni "
        f"recalculer un chiffre) :\n"
        f"{scraped.market.model_dump_json(indent=2)}\n\n"
        f"CANDIDATS PAR SECTION (choisis-en UN par section, celui qui sert le mieux le "
        f"lecteur investisseur ; ignore une section si aucun candidat n'est pertinent) :\n"
        f"{selection.model_dump_json(indent=2)}\n\n"
        f"Produis le document HTML COMPLET de l'édition, prêt à publier, en suivant "
        f"l'anatomie et le gabarit de la charte. Réponds UNIQUEMENT avec le HTML."
    )

    raw = complete_text(config.MODEL_WRITE, system, user, temperature=0.7)
    subject, preview, html_part = _parse_meta(raw)
    html = _extract_html(html_part)
    if "<body" not in html.lower():
        raise RuntimeError("La rédaction n'a pas renvoyé de document HTML valide.")
    html = _enforce_style(html, template_html)  # verrouille le CSS (styles non dérivants)
    html = _fix_body(html, date_fr)              # header table + textes soutien (email-safe)

    # Secours si le modèle n'a pas fourni sujet/preview.
    d_subject, d_preview = derive_meta(html)
    subject = subject or d_subject
    preview = preview or d_preview

    title = f"Cauri News — {date_fr}"
    print(f"[write] HTML généré ({len(html)} caractères) — {date_fr}")
    print(f"[write] sujet : {subject!r} | preview : {preview!r}")
    return WriteOutput(date=scraped.date, title=title, html=html, subject=subject, preview=preview)
