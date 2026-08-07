"""Filtres de curation en amont du triage LLM :
  - fraîcheur : ne garder que les actus de la fenêtre [J-lookback, J[
  - anti-répétition : exclure ce qui a déjà servi dans un numéro précédent (History)

Aucun LLM. Ces filtres réduisent aussi le volume envoyé au triage (coût tokens).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

import config
from agents.models import ScrapedItem


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def item_key(it: ScrapedItem) -> str:
    """Identité stable d'une info pour la déduplication inter-numéros."""
    if it.url:
        return "u:" + it.url.split("?")[0].split("#")[0].rstrip("/").lower()
    return "t:" + _norm(it.title)


# --- Fraîcheur ------------------------------------------------------------
def lookback_days(edition: date) -> int:
    """Nombre de jours de recul. Le lundi (weekday 0) remonte au vendredi
    (vendredi + samedi + dimanche) puisqu'il n'y a pas d'édition le week-end."""
    return config.MONDAY_LOOKBACK_DAYS if edition.weekday() == 0 else config.EDITION_LOOKBACK_DAYS


def filter_fresh(items: list[ScrapedItem], edition_date: str) -> list[ScrapedItem]:
    end = date.fromisoformat(edition_date)                # exclu (pas le jour même)
    start = end - timedelta(days=lookback_days(end))      # inclus
    kept, dropped = [], 0
    for it in items:
        if it.source in config.FRESHNESS_EXEMPT_SOURCES:
            kept.append(it)
            continue
        d = (it.published_at or "")[:10]
        parsed = None
        try:
            parsed = date.fromisoformat(d) if d else None
        except ValueError:
            parsed = None
        if parsed is not None:
            if start <= parsed < end:
                kept.append(it)
            else:
                dropped += 1
        else:  # pas de date exploitable
            if config.STRICT_FRESHNESS:
                dropped += 1
            else:
                kept.append(it)
    print(f"[freshness] fenêtre [{start} → {end}[ : {len(kept)} gardés, {dropped} écartés")
    return kept


# --- Mémoire anti-répétition ---------------------------------------------
class History:
    """Persistée en JSON dans le repo : { item_key: {"date": "YYYY-MM-DD", "title": "..."} }.
    (Rétro-compatible avec l'ancien format { item_key: "YYYY-MM-DD" } — les entrées de ce
    format n'ont simplement pas de titre exploitable par `recent_titles`.)"""

    def __init__(self, records: dict[str, str | dict] | None = None):
        self.records = records or {}

    @classmethod
    def load(cls) -> "History":
        if config.HISTORY_PATH.exists():
            try:
                return cls(json.loads(config.HISTORY_PATH.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                print(f"[history] lecture impossible ({e}), on repart à vide")
        return cls()

    @staticmethod
    def _date_of(entry: str | dict) -> str:
        return entry.get("date", "") if isinstance(entry, dict) else entry

    def filter_unseen(self, items: list[ScrapedItem], edition_date: str) -> list[ScrapedItem]:
        """Exclut ce qui a servi dans un numéro ANTÉRIEUR. Un item déjà enregistré à
        `edition_date` (même jour) n'est PAS exclu : ça permet de régénérer l'édition du
        jour (nouvelles sources, réglages...) sans s'auto-écarter ses propres articles."""
        kept = [
            it for it in items
            if self._date_of(self.records.get(item_key(it), edition_date)) == edition_date
        ]
        print(f"[history] {len(items) - len(kept)} déjà vus (jours précédents) écartés, {len(kept)} inédits")
        return kept

    def record(self, items: list[ScrapedItem], edition_date: str) -> None:
        for it in items:
            self.records[item_key(it)] = {"date": edition_date, "title": it.title}

    def recent_titles(self, edition_date: str) -> list[str]:
        """Titres des actus utilisées dans le(s) numéro(s) de la fenêtre [J-lookback, J[
        (même fenêtre que la fraîcheur — gère l'écart du lundi). Sert à éviter qu'un sujet
        déjà traité dans le numéro PRÉCÉDENT ne réapparaisse via une source différente
        (une simple URL différente ne suffit pas à faire passer un sujet pour inédit)."""
        end = date.fromisoformat(edition_date)
        start = end - timedelta(days=lookback_days(end))
        out = []
        for v in self.records.values():
            if not isinstance(v, dict) or not v.get("title"):
                continue
            d = _safe_date(v.get("date"))
            if d and start <= d < end:
                out.append(v["title"])
        return out

    def prune(self, edition_date: str) -> None:
        cutoff = date.fromisoformat(edition_date) - timedelta(days=config.HISTORY_RETENTION_DAYS)
        before = len(self.records)
        self.records = {
            k: v for k, v in self.records.items()
            if _safe_date(self._date_of(v)) is None or _safe_date(self._date_of(v)) >= cutoff
        }
        if before != len(self.records):
            print(f"[history] purge : {before - len(self.records)} entrées > {config.HISTORY_RETENTION_DAYS}j")

    def save(self) -> None:
        config.HISTORY_PATH.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _safe_date(s: str):
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# --- Mémoire éditoriale (notions La leçon / chiffres-funfacts Sack) --------
class TopicsMemory:
    """Persistée dans topics.json : par catégorie, { libellé publié: date }.
    Sert à empêcher de reprendre une même leçon ou un même chiffre/fun fact."""

    CATS = ("lecon", "sack_chiffre", "sack_funfact")

    def __init__(self, data: dict | None = None):
        self.data = data or {}
        for c in self.CATS:
            self.data.setdefault(c, {})

    @classmethod
    def load(cls) -> "TopicsMemory":
        if config.TOPICS_PATH.exists():
            try:
                return cls(json.loads(config.TOPICS_PATH.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                print(f"[topics] lecture impossible ({e}), on repart à vide")
        return cls()

    def recent(self, cat: str, limit: int = 30, exclude_date: str | None = None) -> list[str]:
        """Libellés déjà utilisés, du plus récent au plus ancien. `exclude_date` retire
        les entrées de ce jour-là (même logique que History.filter_unseen : régénérer
        l'édition du jour ne doit pas s'auto-interdire ses propres choix)."""
        items = sorted(self.data.get(cat, {}).items(), key=lambda kv: kv[1], reverse=True)
        if exclude_date:
            items = [(label, d) for label, d in items if d != exclude_date]
        return [label for label, _ in items[:limit]]

    def record(self, cat: str, label: str, edition_date: str) -> None:
        label = (label or "").strip()
        if not label:
            return
        norm = _norm(label)
        for existing in list(self.data[cat]):  # remplace un doublon normalisé
            if _norm(existing) == norm:
                self.data[cat][existing] = edition_date
                return
        self.data[cat][label] = edition_date

    def prune(self, edition_date: str) -> None:
        cutoff = date.fromisoformat(edition_date) - timedelta(days=config.TOPICS_RETENTION_DAYS)
        for cat in self.CATS:
            self.data[cat] = {
                k: v for k, v in self.data[cat].items()
                if _safe_date(v) is None or _safe_date(v) >= cutoff
            }

    def save(self) -> None:
        config.TOPICS_PATH.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
