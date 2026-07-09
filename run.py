"""Orchestrateur du pipeline : scrape → fraîcheur → anti-répétition → qualify →
select → write → publication de DEUX brouillons Ghost (brut + formaté).

Chaque étape persiste son artefact dans out/<date>/ pour inspection et debug.
La mémoire anti-répétition (history.json) est mise à jour en fin de run réussi.

Usage :
  python run.py                 # pipeline complet + publication des 2 brouillons
  python run.py --no-publish    # tout sauf la publication Ghost
  python run.py --date 2026-07-20
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import config
from agents import digest, publish, qualify, scrape, select, write
from agents.curate import History, TopicsMemory, filter_fresh


def _save(day_dir, name: str, content: str) -> None:
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / name).write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--hybrid-body", action="store_true",
                         help="Publie le corps du numéro final en blocs Ghost natifs "
                              "(éditables) ; header/footer restent en carte HTML.")
    parser.add_argument("--test", action="store_true",
                         help="Slug/titre préfixés [TEST], et la mémoire anti-répétition "
                              "(history.json/topics.json) n'est PAS mise à jour.")
    args = parser.parse_args()

    day = args.date
    day_dir = config.OUT_DIR / day
    print(f"=== Newsletter BRVM — édition {day} ===")

    # 1. Scrape (hors LLM)
    scraped = scrape.run(day)

    # 1b. Fraîcheur : ne garder que les actus de la veille (fenêtre [J-lookback, J[).
    scraped.items = filter_fresh(scraped.items, day)

    # 1c. Anti-répétition : écarter ce qui a déjà servi dans un numéro précédent.
    history = History.load()
    scraped.items = history.filter_unseen(scraped.items)
    _save(day_dir, "01_scrape.json", scraped.model_dump_json(indent=2))

    if not scraped.items:
        print("[run] aucune actu fraîche et inédite — pas de numéro à générer.")
        # On n'écrit pas dans l'historique, rien n'a été consommé.
        return 0

    # Mémoire éditoriale : notions/chiffres déjà publiés, à ne pas répéter.
    topics = TopicsMemory.load()
    avoid_lecons = topics.recent("lecon")
    avoid_chiffres = topics.recent("sack_chiffre")
    avoid_funfacts = topics.recent("sack_funfact")

    # 2. Qualifie
    qualified = qualify.run(scraped)
    _save(day_dir, "02_qualified.json", qualified.model_dump_json(indent=2))

    # 3. Sélectionne 5 candidats/section (leçons déjà données exclues)
    selection = select.run(scraped, qualified, avoid_lecons=avoid_lecons)
    _save(day_dir, "03_selection.json", selection.model_dump_json(indent=2))

    # 4a. Brouillon BRUT (draft 1) : infos candidates + score, non formatées — déterministe.
    digest_html = digest.build_digest_html(selection, scraped.items, day)
    _save(day_dir, f"digest-brut-{day}.html", digest_html)

    # 4b. Rédige la version formatée (draft 2)
    written = write.run(scraped, selection,
                        avoid_lecons=avoid_lecons, avoid_chiffres=avoid_chiffres,
                        avoid_funfacts=avoid_funfacts)
    _save(day_dir, f"newsletter-brvm-{day}.html", written.html)

    # 5. Publie les DEUX brouillons sur Ghost
    title_final = f"[TEST] {written.title}" if args.test else written.title
    slug_brut = f"cauri-news-test-{day}-brut" if args.test else f"cauri-news-{day}-brut"
    slug_final = f"cauri-news-test-{day}" if args.test else f"cauri-news-{day}"
    title_brut = f"[TEST][BRUT] Cauri News — {day}" if args.test else f"[BRUT] Cauri News — {day}"

    if args.no_publish:
        print("[run] --no-publish : étape Ghost ignorée.")
    else:
        if args.hybrid_body:
            url_brut = publish.publish_fragment_native(title_brut, slug_brut, digest_html, "draft")
        else:
            url_brut = publish.publish_post(
                title_brut, slug_brut, digest_html, "draft", is_full_document=False,
            )
        publish_final = publish.publish_post_hybrid if args.hybrid_body else publish.publish_post
        final_kwargs = {} if args.hybrid_body else {"is_full_document": True}
        url_final = publish_final(
            title_final, slug_final, written.html, config.PUBLISH_STATUS,
            email_subject=written.subject, custom_excerpt=written.preview, **final_kwargs,
        )
        _save(day_dir, "05_publish.txt", f"brut : {url_brut}\nformaté : {url_final}\n")

    if args.test:
        print("[run] --test : mémoire anti-répétition (history.json/topics.json) NON mise à jour.")
        print(f"=== Terminé (test). Artefacts : {day_dir} ===")
        return 0

    # 6. Mémorise les infos consommées (candidats du numéro) pour ne pas les répéter.
    used_ids = {c.source_id for s in selection.sections for c in s.candidats if c.source_id}
    used_items = [it for it in scraped.items if it.id in used_ids]
    history.record(used_items, day)
    history.prune(day)
    history.save()
    print(f"[run] historique mis à jour (+{len(used_items)} infos, total {len(history.records)})")

    # 6b. Mémorise les notions/chiffres réellement publiés (leçon, Sack) — anti-répétition éditoriale.
    topics.record("lecon", written.lecon, day)
    topics.record("sack_chiffre", written.sack_chiffre, day)
    topics.record("sack_funfact", written.sack_funfact, day)
    topics.prune(day)
    topics.save()
    print(f"[run] mémoire éditoriale : leçon={written.lecon!r}, chiffre={written.sack_chiffre!r}")

    print(f"=== Terminé. Artefacts : {day_dir} ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — échec propre + code non-zéro pour le CI
        print(f"❌ ÉCHEC pipeline : {e}", file=sys.stderr)
        sys.exit(1)
