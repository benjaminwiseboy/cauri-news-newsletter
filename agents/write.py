"""Étape 4 — Rédaction. Assemble le numéro HTML complet selon la charte.

Le modèle choisit UN candidat par section parmi les 3 proposés, puis rédige.
Les données de marché sont injectées comme FAITS à ne jamais modifier.
Un numéro de référence (nettoyé) est fourni comme exemple de ton/style/HTML.
"""
from __future__ import annotations

import json
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


_META_KEYS = ("SUBJECT", "PREVIEW", "LECON", "SACK_CHIFFRE", "SACK_FUNFACT")


def _parse_meta(raw: str) -> tuple[dict, str]:
    """Extrait les métadonnées produites en tête (SUBJECT/PREVIEW/LECON/SACK_*) et
    renvoie (meta_dict, reste_html)."""
    meta = {}
    for k in _META_KEYS:
        m = re.search(rf"(?im)^\s*{k}\s*:\s*(.+?)\s*$", raw)
        meta[k] = m.group(1).strip() if m else ""
    low = raw.lower()
    i = min((p for p in (low.find("<!doctype"), low.find("<html"), low.find("<body")) if p != -1),
            default=-1)
    html_part = raw[i:] if i != -1 else raw
    return meta, html_part


_A_RE = re.compile(r'<a\b([^>]*?)href="([^"]*)"([^>]*)>(.*?)</a>', re.DOTALL | re.IGNORECASE)


def _urlnorm(u: str) -> str:
    return (u or "").strip().rstrip("/")


def _fix_links(html: str, allowed: set[str]) -> tuple[str, int]:
    """Anti-URL morte : tout <a> dont l'URL n'est pas dans `allowed` (URLs réellement
    scrapées + liens fonctionnels) est délié — on garde le texte en gras. Renvoie
    (html, nb_liens_déliés)."""
    norm_allowed = {_urlnorm(u) for u in allowed if u}
    removed = 0

    def repl(m):
        nonlocal removed
        if _urlnorm(m.group(2)) in norm_allowed:
            return m.group(0)
        removed += 1
        return f"<b>{m.group(4)}</b>"

    return _A_RE.sub(repl, html), removed


_CONTI_BLOCK_RE = re.compile(r'<div class="pad conti">.*?(?=<hr)', re.DOTALL | re.IGNORECASE)
_LEAD_IN_RE = re.compile(r'<b class="lead-in">\s*([^—<]+?)\s*—', re.IGNORECASE)


def _check_continent_diversity(html: str) -> list[str]:
    """Garde-fou (log uniquement, ne corrige pas) : la charte impose 3 pays DIFFÉRENTS
    dans 'Sur le continent'. On alerte si le modèle a répété un pays, plutôt que de
    laisser l'erreur passer inaperçue."""
    block = _CONTI_BLOCK_RE.search(html)
    if not block:
        return []
    countries = [c.strip() for c in _LEAD_IN_RE.findall(block.group(0))]
    seen, dupes = set(), []
    for c in countries:
        key = c.lower()
        if key in seen and c not in dupes:
            dupes.append(c)
        seen.add(key)
    return dupes


_COUNTRY_EMOJI = {
    "sénégal": "🇸🇳", "senegal": "🇸🇳",
    "côte d'ivoire": "🇨🇮", "cote d'ivoire": "🇨🇮", "côte d’ivoire": "🇨🇮",
    "nigeria": "🇳🇬", "nigéria": "🇳🇬",
    "maroc": "🇲🇦", "ghana": "🇬🇭", "kenya": "🇰🇪", "togo": "🇹🇬", "mali": "🇲🇱",
    "burkina faso": "🇧🇫", "bénin": "🇧🇯", "benin": "🇧🇯", "niger": "🇳🇪",
    "guinée": "🇬🇳", "guinee": "🇬🇳", "guinée-bissau": "🇬🇼",
    "mauritanie": "🇲🇷", "tanzanie": "🇹🇿", "éthiopie": "🇪🇹", "ethiopie": "🇪🇹",
    "égypte": "🇪🇬", "egypte": "🇪🇬", "afrique du sud": "🇿🇦",
    "rdc": "🇨🇩", "république démocratique du congo": "🇨🇩", "congo": "🇨🇬",
    "cameroun": "🇨🇲", "gabon": "🇬🇦", "tchad": "🇹🇩", "sierra leone": "🇸🇱",
    "liberia": "🇱🇷", "gambie": "🇬🇲", "rwanda": "🇷🇼", "ouganda": "🇺🇬",
    "zambie": "🇿🇲", "zimbabwe": "🇿🇼", "algérie": "🇩🇿", "algerie": "🇩🇿",
    "tunisie": "🇹🇳", "angola": "🇦🇴", "mozambique": "🇲🇿",
}
_REGIONAL_EMOJI = "🌍"  # UEMOA, CEDEAO, Régional... (pas un pays unique)
_LEAD_IN_OPEN_RE = re.compile(r'<b class="lead-in">\s*([^—<]+?)\s*—', re.IGNORECASE)


def _add_continent_emojis(html: str) -> str:
    """Ajoute un emoji (drapeau du pays, ou 🌍 pour une entité régionale) devant chaque
    item de 'Sur le continent', pour un scan visuel plus rapide."""
    block = _CONTI_BLOCK_RE.search(html)
    if not block:
        return html
    start, end = block.span()
    segment = html[start:end]

    def repl(m: re.Match) -> str:
        country = m.group(1).strip()
        emoji = _COUNTRY_EMOJI.get(country.lower(), _REGIONAL_EMOJI)
        return f"{emoji} {m.group(0)}"

    return html[:start] + _LEAD_IN_OPEN_RE.sub(repl, segment) + html[end:]


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


def _avoid_block(title: str, items: list[str]) -> str:
    return f"\n{title} (NE REPRENDS AUCUN) :\n- " + "\n- ".join(items) if items else ""


def run(scraped: ScrapeOutput, selection: SelectOutput,
        avoid_lecons: list[str] | None = None,
        avoid_chiffres: list[str] | None = None,
        avoid_funfacts: list[str] | None = None) -> WriteOutput:
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

    # URLs autorisées pour les liens = celles réellement scrapées (donc vivantes) + liens
    # fonctionnels. Le modèle doit utiliser l'URL de la source de chaque info.
    url_by_id = {it.id: it.url for it in scraped.items if it.url}
    cand_ids = {c.source_id for s in selection.sections for c in s.candidats if c.source_id}
    cand_urls = {sid: url_by_id[sid] for sid in cand_ids if sid in url_by_id}
    allowed = set(url_by_id.values()) | {config.SUBSCRIBE_URL} | config.STATIC_ALLOWED_LINKS

    # Noms d'entreprises pour les titres mentionnés dans "Marché en 30 secondes" (codes
    # BRVM du jour uniquement) — référence VÉRIFIÉE (site BRVM), pour que le lecteur novice
    # comprenne quelle entreprise se cache derrière un code comme ETIT ou BOAC.
    mkt = scraped.market
    tickers_today = {
        row.get("valeur") for row in (mkt.top_hausses + mkt.top_baisses)
    } | ({mkt.valeur_phare.get("valeur")} if mkt.valeur_phare else set())
    ticker_names = {t: config.BRVM_TICKER_NAMES[t] for t in tickers_today if t in config.BRVM_TICKER_NAMES}
    ticker_block = (
        f"NOMS DES ENTREPRISES (référence vérifiée, pour un lecteur novice) : dans "
        f"'Marché en 30 secondes', CHAQUE FOIS que tu mentionnes un titre par son code "
        f"({', '.join(ticker_names)}), ajoute son nom complet entre parenthèses juste après, "
        f"en utilisant EXACTEMENT le nom ci-dessous — n'en invente jamais un autre, et si un "
        f"code n'apparaît pas dans cette liste ne lui attribue aucun nom :\n"
        f"{json.dumps(ticker_names, ensure_ascii=False)}\n\n"
    ) if ticker_names else ""

    acronym_block = (
        f"GLOSSAIRE DES SIGLES (référence, lecteur novice) : la PREMIÈRE fois que tu "
        f"utilises l'un de ces sigles dans le numéro (n'importe quelle section), explique-le "
        f"brièvement entre parenthèses ou en incise courte — ensuite, dans le reste du même "
        f"numéro, tu peux le réutiliser sans le réexpliquer (pas de répétition lourde). "
        f"'BRVM' n'a PAS besoin d'être expliqué (c'est le sujet de la newsletter). Pour un "
        f"sigle absent de cette liste, ne l'explique QUE si tu es certain à 100% de sa "
        f"signification — sinon laisse-le tel quel, n'invente jamais un développement :\n"
        f"{json.dumps(config.ACRONYM_GLOSSARY, ensure_ascii=False)}\n\n"
    )

    date_fr = french_date(scraped.date)

    # Sections STRICTEMENT cloisonnées (hot_news, la_lecon, sack_afrique) : le modèle ne doit
    # choisir QUE parmi les candidats propres à CHAQUE section (sauf "la reco", déjà autorisée
    # par la charte à piocher dans tout le pool). "sur_le_continent" et "le_radar" ont un régime
    # ÉLARGI symétrique : en plus de leurs candidats propres, chacune reçoit un pool complémentaire
    # (candidats des AUTRES sections, y compris l'autre section élargie) pour ne pas se contenter
    # des restes quand qualify/select a classé une bonne actu "continentale" sous hot_news/le_radar
    # plutôt que sous sur_le_continent (constat du 2026-07-20 : les meilleures actus du jour
    # atterrissaient ailleurs, laissant sur_le_continent avec les candidats les plus faibles).
    by_section = {s.section: s for s in selection.sections}
    strict_sections = [s for s in selection.sections if s.section not in ("sur_le_continent", "le_radar")]

    def _complementary_pool(exclude: str) -> list[dict]:
        return [
            {"section_origine": s.section, **c.model_dump()}
            for s in selection.sections if s.section != exclude for c in s.candidats
        ]

    conti_own = by_section.get("sur_le_continent")
    conti_pool = _complementary_pool("sur_le_continent")
    radar_own = by_section.get("le_radar")
    radar_pool = _complementary_pool("le_radar")

    user = (
        f"DATE D'ÉDITION (à utiliser telle quelle, ne recalcule pas le jour) : {date_fr}\n"
        f"(date ISO {scraped.date})\n\n"
        f"DONNÉES DE MARCHÉ (FAITS — à recopier tels quels, ne jamais inventer ni "
        f"recalculer un chiffre) :\n"
        f"{scraped.market.model_dump_json(indent=2)}\n\n"
        f"{ticker_block}"
        f"{acronym_block}"
        f"CANDIDATS PAR SECTION — STRICTEMENT CLOISONNÉS (triés par score) : pour \"Hot news\", "
        f"\"La leçon\" et \"Sack d'Afrique\", choisis EXCLUSIVEMENT parmi les candidats listés "
        f"SOUS LA SECTION CORRESPONDANTE ci-dessous. Ne réutilise JAMAIS un candidat proposé pour "
        f"une autre section — SEULE EXCEPTION : \"La reco\" (dans Sack d'Afrique) peut piocher un "
        f"candidat de n'importe quelle section (règle déjà en vigueur dans la charte). À "
        f"pertinence égale, préfère toujours un candidat SOURCÉ (source_id non vide, donc un vrai "
        f"lien) à un candidat sans source :\n"
        f"{json.dumps([s.model_dump() for s in strict_sections], ensure_ascii=False, indent=2)}\n\n"
        f"CANDIDATS POUR \"SUR LE CONTINENT\" (régime élargi) : TROIS candidats de TROIS PAYS "
        f"DIFFÉRENTS. Utilise d'abord ses candidats propres ci-dessous ; s'ils ne suffisent pas "
        f"pour couvrir 3 pays différents avec un vrai ancrage économique/structurel (et non pas "
        f"juste parce qu'il en manque), complète avec le POOL COMPLÉMENTAIRE (candidats proposés "
        f"pour d'autres sections, y compris Le radar, que tu N'AS PAS utilisés ailleurs dans ce "
        f"numéro) — notamment si un candidat plus solide économiquement s'y trouve qu'un candidat "
        f"faible de la liste propre. Priorité aux candidats SOURCÉS. Anti-redondance : jamais un "
        f"sujet déjà utilisé ailleurs dans le même numéro.\n"
        f"CANDIDATS PROPRES À SUR LE CONTINENT :\n"
        f"{json.dumps(conti_own.model_dump() if conti_own else {}, ensure_ascii=False, indent=2)}\n"
        f"POOL COMPLÉMENTAIRE (autres sections, à réserver à Sur le continent seulement si non "
        f"repris ailleurs) :\n"
        f"{json.dumps(conti_pool, ensure_ascii=False, indent=2)}\n\n"
        f"CANDIDATS POUR \"LE RADAR\" (régime élargi) : vise 5 informations au total (jamais "
        f"moins de 3, jamais plus de 6). Utilise d'abord ses candidats propres ci-dessous, PUIS "
        f"complète avec le POOL COMPLÉMENTAIRE (candidats proposés pour d'autres sections, y "
        f"compris Sur le continent, que tu N'AS PAS utilisés ailleurs dans ce numéro) pour "
        f"atteindre 5 si besoin — c'est le rôle du radar : les sujets pertinents qui n'ont pas "
        f"trouvé leur place ailleurs. Priorité systématique aux candidats SOURCÉS (propres ou du "
        f"pool complémentaire) sur les candidats sans source. Respecte l'anti-redondance : "
        f"n'utilise JAMAIS ici un sujet déjà traité dans une autre section du même numéro.\n"
        f"CANDIDATS PROPRES AU RADAR :\n"
        f"{json.dumps(radar_own.model_dump() if radar_own else {}, ensure_ascii=False, indent=2)}\n"
        f"POOL COMPLÉMENTAIRE (autres sections, à réserver au radar seulement si non repris "
        f"ailleurs) :\n"
        f"{json.dumps(radar_pool, ensure_ascii=False, indent=2)}\n\n"
        f"LIENS — pour chaque info, le lien DOIT être exactement l'URL de sa source "
        f"(ci-dessous, par source_id). N'invente JAMAIS d'URL ; si une info n'a pas d'URL "
        f"listée, ne mets pas de lien.\n{json.dumps(cand_urls, ensure_ascii=False)}\n"
        f"{_avoid_block('LEÇONS DÉJÀ DONNÉES', avoid_lecons or [])}"
        f"{_avoid_block('CHIFFRES (Sack) DÉJÀ UTILISÉS', avoid_chiffres or [])}"
        f"{_avoid_block('FUN FACTS (Sack) DÉJÀ UTILISÉS', avoid_funfacts or [])}\n\n"
        f"Produis le document HTML COMPLET de l'édition, prêt à publier. Réponds au format :\n"
        f"SUBJECT: ...\nPREVIEW: ...\nLECON: <concept enseigné>\n"
        f"SACK_CHIFFRE: <sujet du chiffre>\nSACK_FUNFACT: <sujet du fun fact>\n<!DOCTYPE html> … </html>"
    )

    raw = complete_text(config.MODEL_WRITE, system, user, temperature=0.7)
    meta, html_part = _parse_meta(raw)
    html = _extract_html(html_part)
    if "<body" not in html.lower():
        raise RuntimeError("La rédaction n'a pas renvoyé de document HTML valide.")
    html = _enforce_style(html, template_html)   # verrouille le CSS (styles non dérivants)
    html = _fix_body(html, date_fr)              # header table + textes soutien (email-safe)
    html, n_removed = _fix_links(html, allowed)  # anti-URL morte
    if n_removed:
        print(f"[write] {n_removed} lien(s) non sourcé(s) délié(s)")
    html = _add_continent_emojis(html)           # 🇸🇳/🌍 devant chaque item "Sur le continent"
    dupe_countries = _check_continent_diversity(html)
    if dupe_countries:
        print(f"[write] ATTENTION : pays répété(s) dans 'Sur le continent' : {', '.join(dupe_countries)}")

    # Secours si le modèle n'a pas fourni sujet/preview.
    d_subject, d_preview = derive_meta(html)
    subject = meta["SUBJECT"] or d_subject
    preview = meta["PREVIEW"] or d_preview

    title = f"Cauri News — {date_fr}"
    print(f"[write] HTML généré ({len(html)} caractères) — {date_fr}")
    print(f"[write] sujet : {subject!r} | leçon : {meta['LECON']!r}")
    return WriteOutput(
        date=scraped.date, title=title, html=html, subject=subject, preview=preview,
        lecon=meta["LECON"], sack_chiffre=meta["SACK_CHIFFRE"], sack_funfact=meta["SACK_FUNFACT"],
    )
