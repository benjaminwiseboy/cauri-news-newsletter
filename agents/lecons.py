"""Banque de leçons — réservoir de notions pour la rubrique « La leçon ».

Aucun LLM ici : lecture de banque-lecons.yaml, filtrage de ce qui a déjà été publié
(topics.json), rotation thématique, rendu du bloc injecté dans le prompt de sélection.

Épuisement de la banque — deux mécanismes, dans cet ordre :
  1. `refresh_lecons.py --refresh` : ré-ingère les nouveautés de la source pédagogique
     (Richbourse) et rédige de nouvelles entrées DANS NOTRE TON. C'est le refresh « qui
     agrandit » la banque. Manuel, car il coûte des tokens et mérite une relecture.
  2. Recyclage automatique (ici) : si plus AUCUNE notion inédite n'est disponible, on
     repropose les plus anciennes en les marquant `rappel` — le rédacteur doit alors
     changer d'angle et de métaphore. Filet de sécurité : le pipeline ne se retrouve
     jamais sans matière, même si personne n'a lancé le refresh.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date

import yaml

import config
from agents.curate import TopicsMemory


# --- Normalisation & rapprochement des libellés ---------------------------
def _norm(s: str) -> str:
    """Minuscule, sans accents, sans parenthèses, ponctuation réduite à l'espace.

    Sert à rapprocher la `notion` de la banque du libellé `LECON:` réellement émis par
    le rédacteur (« PER » vs « PER (ratio cours/bénéfice) », « le dividende » vs
    « dividende »…). Les articles initiaux sont retirés pour la même raison.
    """
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)              # « (BAT) », « (ratio…) »
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^(le|la|les|l|un|une|des|du|de|d)\s+", "", s)


# Mots longs mais vides de sens pour identifier une notion.
_VIDES = {"votre", "vous", "dans", "pour", "avec", "comme", "quand", "entre", "chose",
          "meme", "faut", "celui", "cette", "autre", "toute", "tous", "quoi", "sans",
          "plus", "moins", "avant", "apres", "leur", "notion"}


def _mots(s: str) -> set[str]:
    return {m for m in _norm(s).split() if len(m) >= 5 and m not in _VIDES}


def _correspond(notion: str, publiee: str) -> bool:
    """Vrai si `publiee` (libellé de topics.json) désigne bien `notion` (banque).

    Volontairement STRICT : un faux positif consomme silencieusement une leçon jamais
    donnée, alors qu'un faux négatif reste rattrapé en aval (la liste brute des leçons
    déjà données est de toute façon envoyée au sélectionneur ET au rédacteur).
    D'où : égalité après normalisation, ou recouvrement complet des mots porteurs — et
    au moins deux mots porteurs, sinon « dividende » avalerait « le détachement du
    dividende », qui est une tout autre leçon.
    """
    a, b = _norm(notion), _norm(publiee)
    if not a or not b:
        return False
    if a == b:
        return True
    ma, mb = _mots(notion), _mots(publiee)
    court, long_ = (ma, mb) if len(ma) <= len(mb) else (mb, ma)
    return len(court) >= 2 and court <= long_


# --- Modèle ---------------------------------------------------------------
@dataclass
class Lecon:
    id: str
    notion: str
    famille: str
    niveau: int
    titre: str
    metaphore: str
    angle: str
    brille: str
    origine: str = ""
    rappel: str | None = None      # date de la 1re publication, si on la recycle

    def as_prompt(self, rang: int) -> str:
        tete = f"{rang}. [niveau {self.niveau} · {self.famille}] NOTION : {self.notion}"
        if self.rappel:
            tete += (f"\n   ⚠️ DÉJÀ DONNÉE le {self.rappel} — à ne reprendre qu'avec un ANGLE "
                     f"et une MÉTAPHORE entièrement NEUFS (l'exemple ci-dessous a déjà servi)")
        return (
            f"{tete}\n"
            f"   titre proposé : {self.titre}\n"
            f"   métaphore : {self.metaphore}\n"
            f"   angle : {self.angle}\n"
            f"   pour briller : {self.brille}"
        )


# --- Banque ---------------------------------------------------------------
class Banque:
    def __init__(self, lecons: list[Lecon]):
        self.lecons = lecons

    @classmethod
    def load(cls) -> "Banque":
        if not config.BANQUE_LECONS_PATH.exists():
            print("[lecons] banque-lecons.yaml absent — le pipeline continue sans banque")
            return cls([])
        data = yaml.safe_load(config.BANQUE_LECONS_PATH.read_text(encoding="utf-8")) or {}
        return cls([Lecon(**e) for e in data.get("lecons", [])])

    # -- état
    def _publiees(self, topics: TopicsMemory, exclude_date: str | None) -> dict[str, str]:
        """{ id de leçon : date de publication } pour ce que topics.json connaît déjà."""
        deja = dict(topics.data.get("lecon", {}))
        if exclude_date:  # régénérer l'édition du jour ne doit pas s'auto-interdire
            deja = {k: v for k, v in deja.items() if v != exclude_date}
        out = {}
        for lecon in self.lecons:
            dates = [d for label, d in deja.items() if _correspond(lecon.notion, label)]
            if dates:
                out[lecon.id] = max(dates)
        return out

    def inedites(self, topics: TopicsMemory, exclude_date: str | None = None) -> list[Lecon]:
        publiees = self._publiees(topics, exclude_date)
        return [x for x in self.lecons if x.id not in publiees]

    def etat(self, topics: TopicsMemory, exclude_date: str | None = None) -> dict:
        publiees = self._publiees(topics, exclude_date)
        restantes = [x for x in self.lecons if x.id not in publiees]
        par_famille: dict[str, int] = {}
        for x in restantes:
            par_famille[x.famille] = par_famille.get(x.famille, 0) + 1
        return {
            "total": len(self.lecons),
            "publiees": len(publiees),
            "restantes": len(restantes),
            "par_famille": dict(sorted(par_famille.items(), key=lambda kv: -kv[1])),
            "epuisee": not restantes,
            "alerte": len(restantes) <= config.LECONS_SEUIL_ALERTE,
        }

    # -- proposition
    def _familles_recentes(self, topics: TopicsMemory, profondeur: int = 4) -> list[str]:
        """Familles des dernières leçons publiées (plus récente en tête), pour éviter
        d'enchaîner quatre leçons « dividende » de suite."""
        out = []
        for label in topics.recent("lecon", limit=profondeur * 2):
            for lecon in self.lecons:
                if _correspond(lecon.notion, label):
                    if lecon.famille not in out:
                        out.append(lecon.famille)
                    break
            if len(out) >= profondeur:
                break
        return out

    def propose(self, topics: TopicsMemory, exclude_date: str | None = None,
                n: int | None = None) -> list[Lecon]:
        """Les `n` meilleures notions à servir aujourd'hui.

        Ordre : niveau croissant (on enseigne les fondamentaux d'abord), puis rotation
        des familles (celles servies récemment passent derrière), puis ordre du fichier.
        Si la banque est épuisée, on recycle les plus anciennes en les marquant `rappel`.
        """
        n = n or config.LECONS_PAR_NUMERO
        publiees = self._publiees(topics, exclude_date)
        pool = [x for x in self.lecons if x.id not in publiees]
        recyclage = not pool

        if recyclage:
            # Épuisée : on repart des plus anciennement publiées, angle neuf obligatoire.
            print(f"[lecons] ⚠️ banque ÉPUISÉE ({len(self.lecons)} notions toutes publiées) — "
                  f"recyclage des plus anciennes. Pense à `python refresh_lecons.py --refresh`.")
            pool = sorted(self.lecons, key=lambda x: (publiees.get(x.id, ""), x.niveau))
            # `replace` et non mutation : les Lecon de la banque sont partagées entre appels.
            return [replace(x, rappel=publiees.get(x.id)) for x in pool[:n]]

        # Pénalité de famille : celle servie au dernier numéro passe tout en bas, la
        # précédente juste au-dessus, etc. Les familles non servies récemment sortent
        # en tête à niveau égal.
        recentes = self._familles_recentes(topics)
        penalite = {f: len(recentes) - i for i, f in enumerate(recentes)}
        ordre = {x.id: i for i, x in enumerate(self.lecons)}
        pool.sort(key=lambda x: (x.niveau, penalite.get(x.famille, 0), ordre[x.id]))
        return pool[:n]

    @staticmethod
    def as_prompt_block(lecons: list[Lecon]) -> str:
        if not lecons:
            return ""
        corps = "\n".join(x.as_prompt(i) for i, x in enumerate(lecons, 1))
        return (
            "\n\nBANQUE DE LEÇONS CAURI — pioche les candidats `la_lecon` EXCLUSIVEMENT "
            "ici, dans l'ordre proposé (la n°1 est la plus indiquée aujourd'hui) :\n"
            f"{corps}\n"
            "Règles pour la_lecon :\n"
            "- Reprends la NOTION telle quelle dans le `titre`/`angle` du candidat, et "
            "recopie la métaphore, l'angle et la phrase « pour briller » dans `faits_cles` "
            "— ils descendent jusqu'au rédacteur, c'est eux qui portent notre ton.\n"
            "- N'invente PAS une notion hors de cette banque, et ne reprends aucune leçon "
            "listée comme déjà donnée.\n"
            "- Si une notion de la banque colle en plus à l'actu du jour, remonte-la en "
            "tête : une leçon qui éclaire l'actu vaut mieux qu'une leçon isolée.\n"
        )


def bloc_du_jour(topics: TopicsMemory, edition_date: str) -> tuple[str, dict]:
    """Raccourci pour run.py : (bloc à injecter dans select, état de la banque)."""
    banque = Banque.load()
    etat = banque.etat(topics, exclude_date=edition_date)
    bloc = Banque.as_prompt_block(banque.propose(topics, exclude_date=edition_date))
    if etat["alerte"] and not etat["epuisee"]:
        print(f"[lecons] ⚠️ plus que {etat['restantes']} notions inédites en banque "
              f"(seuil {config.LECONS_SEUIL_ALERTE}) — lance `python refresh_lecons.py --refresh`")
    else:
        print(f"[lecons] {etat['restantes']}/{etat['total']} notions inédites disponibles")
    return bloc, etat


if __name__ == "__main__":  # `python -m agents.lecons` → état rapide
    b = Banque.load()
    t = TopicsMemory.load()
    e = b.etat(t)
    print(f"Banque : {e['restantes']}/{e['total']} inédites ({e['publiees']} déjà données)")
    for famille, n in e["par_famille"].items():
        print(f"  {famille:24} {n}")
    print("\nProchaines proposées :")
    for x in b.propose(t, n=5):
        print(f"  - [{x.niveau}] {x.notion}" + (f"  (RAPPEL {x.rappel})" if x.rappel else ""))
    print(f"\nDate du jour : {date.today().isoformat()}")
