"""Étape 3 — Sélection. Pour chaque section, propose 3 candidats/angles."""
from __future__ import annotations

import json

import config
from agents.llm import complete_json
from agents.models import QualifyOutput, ScrapeOutput, SelectOutput


def run(scraped: ScrapeOutput, qualified: QualifyOutput) -> SelectOutput:
    system = (
        config.load_prompt("select")
        + "\n\n---\nCHARTE ÉDITORIALE :\n" + config.read_reference(config.CHARTE_PATH)
    )

    # On donne au modèle les items qualifiés + leur texte source pour construire les angles.
    text_by_id = {it.id: it.text for it in scraped.items}
    retained = [
        {
            "id": q.id, "title": q.title, "section_cible": q.section_cible,
            "score": q.score, "cercle": q.cercle,
            "text": text_by_id.get(q.id, "")[: config.SELECT_TEXT_CHARS],
        }
        for q in qualified.items if q.decision in ("retenu", "reserve")
    ]

    user = (
        f"Date : {scraped.date}\n"
        f"À partir des actus qualifiées ci-dessous, propose pour CHAQUE section "
        f"(hot_news, la_lecon, sur_le_continent, sack_afrique, le_radar) EXACTEMENT "
        f"3 candidats (titre + angle + faits_clés), en respectant les seuils et les "
        f"règles anti-redondance de la charte.\n\n"
        f"ACTUS QUALIFIÉES :\n{json.dumps(retained, ensure_ascii=False, indent=2)}"
    )
    out = complete_json(config.MODEL_SELECT, system, user, SelectOutput)
    out.date = scraped.date
    print(f"[select] {len(out.sections)} sections avec candidats")
    return out
