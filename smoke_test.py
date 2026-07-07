"""Test de fumée des étapes hors-LLM : scrape, extraction de dates, fraîcheur, marché.
Ne touche ni OpenRouter ni Ghost. Usage : python smoke_test.py [YYYY-MM-DD]"""
import sys
from collections import Counter

from agents import scrape
from agents.curate import filter_fresh

edition = sys.argv[1] if len(sys.argv) > 1 else "2026-07-07"

print(f"\n########## SCRAPE (édition cible {edition}) ##########")
out = scrape.run(edition)

print("\n----- Marché BRVM -----")
m = out.market
print("Composite :", m.brvm_composite)
print("BRVM-30   :", m.brvm_30)
print("Top hausses :", m.top_hausses[:3])
print("Top baisses :", m.top_baisses[:3])

print("\n----- Couverture des dates par source -----")
by_src = Counter(it.source for it in out.items)
dated = Counter(it.source for it in out.items if it.published_at)
for src in sorted(by_src):
    print(f"  {src:20} {dated[src]:3}/{by_src[src]:<3} datés")

print("\n----- Échantillon (5 actus) -----")
for it in out.items[:5]:
    print(f"  [{it.published_at or '   ??   '}] ({it.source}) {it.title[:70]}")

print(f"\n########## FRAÎCHEUR ##########")
fresh = filter_fresh(out.items, edition)
print("\n----- Répartition des dates gardées -----")
for d, n in sorted(Counter(it.published_at for it in fresh).items(), key=lambda kv: kv[0] or ""):
    print(f"  {d or '(exempté/sans date)'}: {n}")
print(f"\nRÉSULTAT : {len(out.items)} scrapées → {len(fresh)} fraîches pour l'édition {edition}")
