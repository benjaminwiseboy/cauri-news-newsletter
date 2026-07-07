"""Construit le brouillon BRUT (draft 1) : liste non formatée des infos qui
POUVAIENT être sélectionnées pour le numéro — soit les candidats proposés par
l'étape de sélection (3 par section), avec leur source. Aucun LLM, purement
déterministe : c'est un document de travail pour relecture, pas la newsletter.
"""
from __future__ import annotations

from html import escape

from agents.models import ScrapedItem, SelectOutput

SECTION_LABELS = {
    "hot_news": "Hot news",
    "la_lecon": "La leçon",
    "sur_le_continent": "Sur le continent",
    "sack_afrique": "Sack d'Afrique",
    "le_radar": "Le radar",
}


def build_digest_html(selection: SelectOutput, items: list[ScrapedItem], edition_date: str) -> str:
    url_by_id = {it.id: it.url for it in items}
    parts = [
        f"<h1>Cauri News — brut du {escape(edition_date)}</h1>",
        "<p><em>Document de travail : toutes les infos candidates du numéro "
        "(non formatées). La version finale est dans le brouillon « Cauri News » du jour.</em></p>",
    ]
    for sec in selection.sections:
        parts.append(f"<h2>{escape(SECTION_LABELS.get(sec.section, sec.section))}</h2>")
        if not sec.candidats:
            parts.append("<p><em>Aucun candidat.</em></p>")
            continue
        parts.append("<ul>")
        for c in sec.candidats:
            src = url_by_id.get(c.source_id)
            src_html = f' — <a href="{escape(src)}">source</a>' if src else ""
            faits = "".join(f"<li>{escape(f)}</li>" for f in c.faits_cles)
            faits_html = f"<ul>{faits}</ul>" if faits else ""
            parts.append(
                f"<li><strong>{escape(c.titre)}</strong>{src_html}"
                f"<br><em>Angle :</em> {escape(c.angle)}{faits_html}</li>"
            )
        parts.append("</ul>")
    return "\n".join(parts)
