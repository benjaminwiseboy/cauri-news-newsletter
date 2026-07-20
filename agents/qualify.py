"""Étape 2 — Qualification. Applique le filtre éditorial (scoring /12) à chaque actu.

Pour maîtriser le coût : on tronque le texte, on plafonne le nombre d'actus envoyées
(en priorisant les sources économiques), et le schéma de sortie est allégé.

Le pool retenu est traité par LOTS (QUALIFY_BATCH_SIZE actus/appel), pas en un seul appel
géant : un modèle léger perd en fiabilité sur un lot trop volumineux et "oublie" de statuer
sur une partie des actus (incident 2026-07 : ~80 actus envoyées en un seul appel, 11 verdicts
rendus seulement). Des lots plus petits, quitte à multiplier les appels, restent dans la
capacité fiable du modèle. Un lot en échec (JSON invalide après retries) est journalisé et
ignoré — comme scrape.py, une défaillance isolée ne bloque pas le reste du run.
"""
from __future__ import annotations

import json

import config
from agents.llm import complete_json
from agents.models import QualifiedItem, QualifyOutput, ScrapedItem, ScrapeOutput

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


def _chunks(items: list[ScrapedItem], size: int) -> list[list[ScrapedItem]]:
    return [items[i: i + size] for i in range(0, len(items), size)]


def _qualify_batch(batch: list[ScrapedItem], system: str, day: str) -> list[QualifiedItem]:
    payload = [
        {"id": it.id, "source": it.source, "title": it.title,
         "text": it.text[: config.QUALIFY_TEXT_CHARS]}
        for it in batch
    ]
    user = (
        f"Date du numéro : {day}\n"
        f"Qualifie CHAQUE actu selon le filtre (score global /12, cercle, red flags, "
        f"décision, section cible). Il y a EXACTEMENT {len(batch)} actus ci-dessous : "
        f"renvoie EXACTEMENT {len(batch)} objets dans `items`, un par actu (un statut "
        f"'ecarte' compte comme un objet à part entière) — n'en saute aucune.\n\n"
        f"ACTUS :\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    out = complete_json(config.MODEL_QUALIFY, system, user, QualifyOutput)

    sent_ids = {it.id for it in batch}
    got_ids = {i.id for i in out.items}
    missing = len(sent_ids - got_ids)
    if missing:
        print(f"[qualify] ⚠️ lot incomplet : {missing}/{len(batch)} actu(s) sans verdict "
              f"(le modèle n'a pas statué dessus — ignorée(s))")
    return out.items


def run(scraped: ScrapeOutput) -> QualifyOutput:
    if not scraped.items:
        print("[qualify] aucune actu à qualifier")
        return QualifyOutput(date=scraped.date, items=[])

    items = _cap(scraped.items)
    system = config.load_prompt("qualify") + "\n\n---\nFILTRE DE RÉFÉRENCE :\n" + \
        config.read_reference(config.FILTRE_PATH)

    batches = _chunks(items, config.QUALIFY_BATCH_SIZE)
    all_items: list[QualifiedItem] = []
    for n, batch in enumerate(batches, start=1):
        try:
            all_items += _qualify_batch(batch, system, scraped.date)
        except Exception as e:  # noqa: BLE001 — un lot en échec ne bloque pas les autres
            print(f"[qualify] lot {n}/{len(batches)} échec ({len(batch)} actus) : {e}")

    out = QualifyOutput(date=scraped.date, items=all_items)
    retenus = sum(1 for i in out.items if i.decision == "retenu")
    print(f"[qualify] {len(items)} envoyées en {len(batches)} lot(s) de "
          f"{config.QUALIFY_BATCH_SIZE} → {len(out.items)} qualifiées, {retenus} retenues")
    return out
