"""Refresh de la banque de leçons — quand le réservoir de « La leçon » s'épuise.

Va relire l'offre pédagogique publique de Richbourse (mini-bourse, articles, lexique),
compare aux thématiques DÉJÀ DÉPOUILLÉES (lecons-source-index.json), et fait rédiger les
nouveautés DANS NOTRE TON (prompts/lecons-refresh.md) avant de les ajouter à
banque-lecons.yaml. On ne reprend que des SUJETS : aucun texte de la source n'est copié,
même pas les définitions du lexique (seuls les intitulés servent d'amorce).

Usage :
  python refresh_lecons.py                  # état de la banque (ni réseau, ni LLM)
  python refresh_lecons.py --scan           # + relève des thématiques inédites (sans LLM)
  python refresh_lecons.py --refresh        # + rédaction et ajout à la banque
  python refresh_lecons.py --refresh --dry-run   # tout sauf l'écriture des fichiers
  python refresh_lecons.py --refresh --max 10    # plafonne le lot rédigé

Accès : richbourse.com renvoie 403 à l'User-Agent du scraper de la newsletter et 200 à un
UA navigateur (config.LECONS_SOURCE_UA). Leur robots.txt autorise nommément les crawlers
d'IA sur le contenu pédagogique gratuit ; seule la page de tarifs leur est fermée.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

import config
from agents.curate import TopicsMemory
from agents.lecons import Banque, _correspond
from agents.llm import complete_json

TIMEOUT = 25
MAX_PAGES = 20          # garde-fou pagination
HEADERS = {"User-Agent": config.LECONS_SOURCE_UA}


# --- Sortie attendue du rédacteur -----------------------------------------
class NouvelleLecon(BaseModel):
    id: str
    notion: str
    famille: str
    niveau: int
    titre: str
    metaphore: str
    angle: str
    brille: str
    origine: str = "lexique"


class RefreshOutput(BaseModel):
    lecons: list[NouvelleLecon] = Field(default_factory=list)


# --- Relève des thématiques (aucun LLM) -----------------------------------
def _get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def _jsonld(html: str) -> list[dict]:
    """Tous les nœuds JSON-LD de la page, @graph aplati."""
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        out.extend(data.get("@graph") or [data])
    return out


def scan_mini() -> list[tuple[str, str]]:
    """[(titre, clé)] des « Mini-bourse ». La page expose un ItemList JSON-LD propre."""
    vus, page = [], 1
    while page <= MAX_PAGES:
        url = config.LECONS_SOURCE_PAGES["mini"] + (f"?page={page}" if page > 1 else "")
        noeuds = [n for n in _jsonld(_get(url)) if n.get("@type") == "ItemList"]
        titres = [e.get("name", "").strip()
                  for n in noeuds for e in n.get("itemListElement", []) if e.get("name")]
        neufs = [t for t in titres if t not in vus]
        if not neufs:
            break
        vus.extend(neufs)
        page += 1
    return [(t, t) for t in vus]


def scan_articles() -> list[tuple[str, str]]:
    """[(titre, slug)] des articles pédagogiques. Pas de JSON-LD ici : on lit les liens.
    Le slug sert de clé (stable), le titre part au rédacteur."""
    vus: dict[str, str] = {}
    for page in range(1, MAX_PAGES + 1):
        url = f"{config.LECONS_SOURCE_PAGES['articles']}?page={page}&per-page=10"
        soup = BeautifulSoup(_get(url), "html.parser")
        trouves = 0
        for a in soup.select('a[href*="/common/apprendre/article/"]'):
            titre = a.get_text(" ", strip=True)
            slug = a["href"].rstrip("/").split("/")[-1]
            if len(titre) < 8 or "Lire la suite" in titre or slug in vus:
                continue
            vus[slug] = titre
            trouves += 1
        if not trouves:
            break
    return [(titre, slug) for slug, titre in vus.items()]


def scan_lexique() -> list[tuple[str, str]]:
    """[(terme, terme)] du lexique. On ne prend QUE les intitulés : les définitions du
    site ne sont ni lues ni transmises au rédacteur."""
    noeuds = [n for n in _jsonld(_get(config.LECONS_SOURCE_PAGES["lexique"]))
              if n.get("@type") == "DefinedTermSet"]
    termes = [t.get("name", "").strip()
              for n in noeuds for t in n.get("hasDefinedTerm", []) if t.get("name")]
    return [(t, t) for t in termes]


SCANNERS = {"mini": scan_mini, "articles": scan_articles, "lexique": scan_lexique}


# --- Index des thématiques déjà dépouillées -------------------------------
def load_index() -> dict:
    if config.LECONS_SOURCE_INDEX_PATH.exists():
        return json.loads(config.LECONS_SOURCE_INDEX_PATH.read_text(encoding="utf-8"))
    return {"richbourse": {"lexique": [], "mini": [], "articles": []}}


def save_index(index: dict) -> None:
    index.setdefault("richbourse", {})["derniere_ingestion"] = date.today().isoformat()
    config.LECONS_SOURCE_INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def releve(index: dict) -> dict[str, list[tuple[str, str]]]:
    """Par type de source : les thématiques jamais examinées jusqu'ici."""
    connu = index.get("richbourse", {})
    neuf = {}
    for typ, scanner in SCANNERS.items():
        try:
            items = scanner()
        except requests.RequestException as e:   # une source KO ne bloque pas les autres
            print(f"[refresh] {typ} : injoignable ({e})")
            neuf[typ] = []
            continue
        deja = set(connu.get(typ, []))
        neuf[typ] = [(titre, cle) for titre, cle in items if cle not in deja]
        print(f"[refresh] {typ} : {len(items)} thématiques en ligne, {len(neuf[typ])} inédites")
    return neuf


# --- Rédaction dans notre ton ---------------------------------------------
def rediger(candidats: list[tuple[str, str, str]], banque: Banque) -> RefreshOutput:
    """candidats = [(titre, clé, type)]. Renvoie les leçons rédigées."""
    familles = sorted({x.famille for x in banque.lecons})
    exemples = [x for x in banque.lecons if x.id in
                ("detachement-dividende", "risque-de-credit", "epargner-vs-investir")]
    system = config.load_prompt("lecons-refresh")
    user = (
        "FAMILLES AUTORISÉES (n'en invente aucune) :\n- " + "\n- ".join(familles) + "\n\n"
        "NOTIONS DÉJÀ EN BANQUE (n'en refais AUCUNE, même reformulée) :\n- "
        + "\n- ".join(x.notion for x in banque.lecons) + "\n\n"
        "TROIS ENTRÉES EXISTANTES, POUR LE TON (à égaler, pas à copier) :\n"
        + json.dumps([{"notion": x.notion, "titre": x.titre, "metaphore": x.metaphore,
                       "angle": x.angle, "brille": x.brille} for x in exemples],
                     ensure_ascii=False, indent=2) + "\n\n"
        "THÉMATIQUES À TRAITER (intitulés relevés chez la source ; ne reprends que le "
        "sujet, réécris tout) :\n"
        + json.dumps([{"intitule": t, "origine": "article" if typ == "articles" else typ}
                      for t, _, typ in candidats], ensure_ascii=False, indent=2) + "\n\n"
        "Écarte tout ce qui est promotionnel, daté, déjà couvert ou inexplicable en une "
        "métaphore simple. Réponds : {\"lecons\": [...]}"
    )
    return complete_json(config.MODEL_LECONS, system, user, RefreshOutput, temperature=0.8)


def valide(sortie: RefreshOutput, banque: Banque) -> list[NouvelleLecon]:
    """Filtre les sorties inutilisables : famille inconnue, doublon, champ vide."""
    familles = {x.famille for x in banque.lecons}
    ids = {x.id for x in banque.lecons}
    gardees: list[NouvelleLecon] = []
    for l in sortie.lecons:
        if l.famille not in familles:
            print(f"  ✗ {l.notion!r} : famille inconnue ({l.famille})")
            continue
        if l.niveau not in (1, 2, 3):
            print(f"  ✗ {l.notion!r} : niveau invalide ({l.niveau})")
            continue
        if not all([l.notion, l.titre, l.metaphore, l.angle, l.brille]):
            print(f"  ✗ {l.notion!r} : champ vide")
            continue
        if any(_correspond(l.notion, x.notion) for x in banque.lecons):
            print(f"  ✗ {l.notion!r} : doublon d'une notion déjà en banque")
            continue
        if any(_correspond(l.notion, x.notion) for x in gardees):
            print(f"  ✗ {l.notion!r} : doublon dans le lot")
            continue
        l.id = re.sub(r"[^a-z0-9-]", "", l.id.lower()) or re.sub(r"\W+", "-", l.notion.lower())
        while l.id in ids:
            l.id += "-2"
        ids.add(l.id)
        gardees.append(l)
    return gardees


# --- Écriture (append : les commentaires du YAML sont préservés) -----------
def _q(s: str) -> str:
    return '"' + str(s).strip().replace("\\", "\\\\").replace('"', '\\"') + '"'


def append_banque(lecons: list[NouvelleLecon]) -> None:
    bloc = [f"\n  # ─── Ajouté par refresh_lecons.py le {date.today().isoformat()} ───"]
    for l in lecons:
        bloc.append(
            f"  - id: {l.id}\n"
            f"    notion: {_q(l.notion)}\n"
            f"    famille: {l.famille}\n"
            f"    niveau: {l.niveau}\n"
            f"    titre: {_q(l.titre)}\n"
            f"    metaphore: {_q(l.metaphore)}\n"
            f"    angle: {_q(l.angle)}\n"
            f"    brille: {_q(l.brille)}\n"
            f"    origine: {l.origine}"
        )
    with config.BANQUE_LECONS_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(bloc) + "\n")


# --- CLI ------------------------------------------------------------------
def etat() -> dict:
    banque, topics = Banque.load(), TopicsMemory.load()
    e = banque.etat(topics)
    print(f"Banque de leçons : {e['restantes']}/{e['total']} notions inédites "
          f"({e['publiees']} déjà publiées)")
    for famille, n in e["par_famille"].items():
        print(f"  {famille:24} {n}")
    if e["epuisee"]:
        print("⚠️  ÉPUISÉE — le pipeline recycle les plus anciennes en attendant un refresh.")
    elif e["alerte"]:
        print(f"⚠️  Sous le seuil d'alerte ({config.LECONS_SEUIL_ALERTE}) — refresh conseillé.")
    return e


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scan", action="store_true", help="relève les thématiques inédites")
    p.add_argument("--refresh", action="store_true", help="scan + rédaction + ajout")
    p.add_argument("--dry-run", action="store_true", help="n'écrit aucun fichier")
    p.add_argument("--max", type=int, default=config.LECONS_REFRESH_MAX)
    args = p.parse_args()

    etat()
    if not (args.scan or args.refresh):
        return 0

    print("\n=== Relève des thématiques source ===")
    index = load_index()
    neuf = releve(index)
    candidats = [(titre, cle, typ) for typ, items in neuf.items() for titre, cle in items]

    if not candidats:
        print("\nRien de neuf chez la source : la banque ne peut pas grandir pour l'instant.\n"
              "Une fois épuisée, le pipeline recyclera automatiquement les plus anciennes "
              "notions (angle et métaphore neufs imposés au rédacteur).")
        return 0

    print(f"\n{len(candidats)} thématiques inédites :")
    for titre, _, typ in candidats[:40]:
        print(f"  [{typ}] {titre}")
    if len(candidats) > 40:
        print(f"  … et {len(candidats) - 40} autres")

    if not args.refresh:
        print("\n(--scan seulement : rien n'a été rédigé ni écrit)")
        return 0

    lot = candidats[: args.max]
    print(f"\n=== Rédaction de {len(lot)} thématiques ({config.MODEL_LECONS}) ===")
    banque = Banque.load()
    gardees = valide(rediger(lot, banque), banque)
    print(f"\n{len(gardees)} leçons retenues sur {len(lot)} thématiques soumises :")
    for l in gardees:
        print(f"  ✓ [{l.niveau}·{l.famille}] {l.notion} — {l.titre}")
        if args.dry_run:   # en simulation, on montre le texte : c'est lui qu'on juge
            print(f"      métaphore : {l.metaphore}\n"
                  f"      angle     : {l.angle}\n"
                  f"      briller   : {l.brille}")

    if args.dry_run:
        print("\n--dry-run : banque-lecons.yaml et lecons-source-index.json inchangés.")
        return 0

    if gardees:
        append_banque(gardees)
        print(f"\n→ {len(gardees)} entrées ajoutées à {config.BANQUE_LECONS_PATH.name}")
    # Tout ce qui a été SOUMIS est marqué dépouillé, y compris les thématiques écartées :
    # inutile de les resoumettre à chaque refresh.
    for typ in SCANNERS:
        deja = set(index.setdefault("richbourse", {}).setdefault(typ, []))
        deja.update(cle for _, cle, t in lot if t == typ)
        index["richbourse"][typ] = sorted(deja)
    save_index(index)
    print(f"→ {config.LECONS_SOURCE_INDEX_PATH.name} mis à jour ({len(lot)} thématiques dépouillées)")
    reste = len(candidats) - len(lot)
    if reste:
        print(f"→ {reste} thématiques en attente : relance --refresh pour le lot suivant")
    print("\n⚠️  Relis les nouvelles entrées avant de committer : c'est du ton, pas du calcul.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"❌ ÉCHEC refresh : {e}", file=sys.stderr)
        sys.exit(1)
