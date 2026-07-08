"""Configuration centrale : env, routage des modèles, chemins."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Force stdout/stderr en UTF-8 (console Windows cp1252 sinon, sur é/→/…).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

load_dotenv()  # charge .env en local ; no-op si absent (prod = env GitHub Actions)

ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = ROOT / "prompts"
OUT_DIR = ROOT / "out"

# Documents de référence injectés dans les prompts (source de vérité éditoriale).
CHARTE_PATH = ROOT / "charte-editoriale-newsletter-brvm.md"
FILTRE_PATH = ROOT / "filtre-selection-editoriale-newsletter-brvm.md"
SOURCES_PATH = ROOT / "sources.yaml"
# Template canonique : sert d'exemple ton/style au rédacteur ET de source du <style>
# (le CSS du modèle est remplacé par celui-ci après génération → styles verrouillés).
TEMPLATE_PATH = ROOT / "newsletter-template.html"

# --- OpenRouter ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Routage des modèles par étape (surchargeable via env).
# Tri/sélection en sonnet : le jugement éditorial (pertinence économique/BRVM) exige
# un modèle solide — haiku laissait passer trop de politique/faits divers.
MODEL_QUALIFY = os.environ.get("MODEL_QUALIFY", "anthropic/claude-sonnet-4.6")
MODEL_SELECT = os.environ.get("MODEL_SELECT", "anthropic/claude-sonnet-4.6")
MODEL_WRITE = os.environ.get("MODEL_WRITE", "anthropic/claude-sonnet-4.6")

# --- Ghost ---
GHOST_URL = os.environ.get("GHOST_URL", "").rstrip("/")
GHOST_ADMIN_KEY = os.environ.get("GHOST_ADMIN_KEY", "")
PUBLISH_STATUS = os.environ.get("PUBLISH_STATUS", "draft")

# Page d'abonnement Ghost (Portal) pour le bouton "S'abonner".
SUBSCRIBE_URL = os.environ.get("SUBSCRIBE_URL") or (f"{GHOST_URL}/#/portal/signup" if GHOST_URL else "")

# --- Maîtrise du coût (tokens envoyés aux modèles) ---
# Plafond d'actus envoyées au tri (les sources économiques passent en priorité).
MAX_QUALIFY_ITEMS = int(os.environ.get("MAX_QUALIFY_ITEMS", "80"))
# Troncature du texte des actus dans les prompts (le résumé suffit au tri/sélection).
QUALIFY_TEXT_CHARS = int(os.environ.get("QUALIFY_TEXT_CHARS", "350"))
SELECT_TEXT_CHARS = int(os.environ.get("SELECT_TEXT_CHARS", "500"))

# --- Fraîcheur & anti-répétition ---
# Fenêtre de fraîcheur : une édition du jour J ne retient que les actus datées de
# [J - lookback, J[. En semaine (mar→ven) : 1 jour (la veille). Le LUNDI : 3 jours
# (vendredi + samedi + dimanche), car la newsletter ne paraît pas le week-end.
EDITION_LOOKBACK_DAYS = int(os.environ.get("EDITION_LOOKBACK_DAYS", "1"))
MONDAY_LOOKBACK_DAYS = int(os.environ.get("MONDAY_LOOKBACK_DAYS", "3"))
# En mode strict, une actu sans date exploitable est ÉCARTÉE (garantit "seulement J-1").
# Mets STRICT_FRESHNESS=false pour conserver les sources HTML non datées.
STRICT_FRESHNESS = os.environ.get("STRICT_FRESHNESS", "true").lower() == "true"
# Sources exemptées du filtre de fraîcheur (stats annuelles, non datées au jour).
FRESHNESS_EXEMPT_SOURCES = {"worldbank"}

# Mémoire anti-répétition d'un numéro à l'autre (persistée dans le repo).
HISTORY_PATH = ROOT / "history.json"
HISTORY_RETENTION_DAYS = int(os.environ.get("HISTORY_RETENTION_DAYS", "45"))

# Mémoire éditoriale : notions de "La leçon" et chiffres/fun facts de "Sack d'Afrique"
# déjà publiés → interdits de reprise. Rétention plus longue (une leçon ne se répète
# pas avant des mois).
TOPICS_PATH = ROOT / "topics.json"
TOPICS_RETENTION_DAYS = int(os.environ.get("TOPICS_RETENTION_DAYS", "120"))

# Liens fonctionnels toujours autorisés (en plus des URLs scrapées, vivantes par
# construction). Tout <a> pointant ailleurs est délié à la publication (anti-URL morte).
STATIC_ALLOWED_LINKS = {"https://www.brvm.org/fr/indices"}


def require(name: str, value: str) -> str:
    """Échoue tôt et clairement si un secret obligatoire manque."""
    if not value:
        raise RuntimeError(
            f"Variable d'environnement '{name}' manquante. "
            f"Renseigne-la dans .env (local) ou en GitHub Secret (prod)."
        )
    return value


def read_reference(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_prompt(name: str) -> str:
    """Charge un prompt système depuis prompts/<name>.md."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
