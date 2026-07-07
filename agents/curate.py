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
    """Persistée en JSON dans le repo : { item_key: 'YYYY-MM-DD' (date d'usage) }."""

    def __init__(self, records: dict[str, str] | None = None):
        self.records = records or {}

    @classmethod
    def load(cls) -> "History":
        if config.HISTORY_PATH.exists():
            try:
                return cls(json.loads(config.HISTORY_PATH.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                print(f"[history] lecture impossible ({e}), on repart à vide")
        return cls()

    def filter_unseen(self, items: list[ScrapedItem]) -> list[ScrapedItem]:
        kept = [it for it in items if item_key(it) not in self.records]
        print(f"[history] {len(items) - len(kept)} déjà vus écartés, {len(kept)} inédits")
        return kept

    def record(self, items: list[ScrapedItem], edition_date: str) -> None:
        for it in items:
            self.records[item_key(it)] = edition_date

    def prune(self, edition_date: str) -> None:
        cutoff = date.fromisoformat(edition_date) - timedelta(days=config.HISTORY_RETENTION_DAYS)
        before = len(self.records)
        self.records = {
            k: v for k, v in self.records.items()
            if _safe_date(v) is None or _safe_date(v) >= cutoff
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
