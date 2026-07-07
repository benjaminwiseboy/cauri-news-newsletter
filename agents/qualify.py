"""Étape 2 — Qualification. Applique le filtre éditorial (scoring /12) à chaque actu.

Pour maîtriser le coût : on tronque le texte, on plafonne le nombre d'actus envoyées
(en priorisant les sources économiques), et le schéma de sortie est allégé.
"""
from __future__ import annotations

import json

import config
from agents.llm import complete_json
from agents.models import QualifyOutput, ScrapedItem, ScrapeOutput

# Sources à fort ancrage économique/BRVM — prioritaires quand on plafonne le pool.
_ECON_SOURCES = ("sikafinance", "brvm", "worldbank", "apa")


def _priority(it: ScrapedItem) -> int:
    econ = it.source.startswith(_ECON_SOURCES) or "hot_news" in it.section_hints
    return 0 if econ else 1


def _cap(items: list[ScrapedItem]) -> list[ScrapedItem]:
    """Garde en priorité les actus économiques, plafonne à MAX_QUALIFY_ITEMS."""
    ordered = sorted(items, key=_priority)  # tri stable : éco d'abord
    capped = ordered[: config.MAX_QUALIFY_ITEMS]
    if len(capped) < len(items):
        print(f"[qualify] pool plafonné : {len(items)} → {len(capped)} (éco prioritaires)")
    return capped


def run(scraped: ScrapeOutput) -> QualifyOutput:
    if not scraped.items:
        print("[qualify] aucune actu à qualifier")
        return QualifyOutput(date=scraped.date, items=[])

    items = _cap(scraped.items)
    system = config.load_prompt("qualify") + "\n\n---\nFILTRE DE RÉFÉRENCE :\n" + \
        config.read_reference(config.FILTRE_PATH)

    payload = [
        {"id": it.id, "source": it.source, "title": it.title,
         "text": it.text[: config.QUALIFY_TEXT_CHARS]}
        for it in items
    ]
    user = (
        f"Date du numéro : {scraped.date}\n"
        f"Qualifie CHAQUE actu selon le filtre (score global /12, cercle, red flags, "
        f"décision, section cible).\n\n"
        f"ACTUS :\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    out = complete_json(config.MODEL_QUALIFY, system, user, QualifyOutput)
    out.date = scraped.date
    retenus = sum(1 for i in out.items if i.decision == "retenu")
    print(f"[qualify] {len(out.items)} qualifiées, {retenus} retenues")
    return out
