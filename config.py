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
# select en gemini-flash-lite (2026-07) : system prompt allégé (charte retirée, consignes
# de sélection autosuffisantes dans prompts/select.md) pour compenser un modèle plus léger.
# ATTENTION précédent : un essai Haiku sur ce même poste avait laissé passer trop de
# politique/faits divers — à surveiller sur 03_selection.json après ce changement.
MODEL_QUALIFY = os.environ.get("MODEL_QUALIFY", "anthropic/claude-sonnet-4.6")
MODEL_SELECT = os.environ.get("MODEL_SELECT", "google/gemini-2.5-flash-lite")
MODEL_WRITE = os.environ.get("MODEL_WRITE", "anthropic/claude-sonnet-4.6")

# --- Ghost ---
GHOST_URL = os.environ.get("GHOST_URL", "").rstrip("/")
GHOST_ADMIN_KEY = os.environ.get("GHOST_ADMIN_KEY", "")
PUBLISH_STATUS = os.environ.get("PUBLISH_STATUS", "draft")

# Page d'abonnement Ghost (Portal) pour le bouton "S'abonner".
SUBSCRIBE_URL = os.environ.get("SUBSCRIBE_URL") or (f"{GHOST_URL}/#/portal/signup" if GHOST_URL else "")

# --- Maîtrise du coût (tokens envoyés aux modèles) ---
# Plafond d'actus envoyées au tri (les sources économiques passent en priorité).
MAX_QUALIFY_ITEMS = int(os.environ.get("MAX_QUALIFY_ITEMS", "60"))
# Taille des lots pour qualify.py : le pool plafonné (MAX_QUALIFY_ITEMS) est qualifié par
# lots de cette taille (plusieurs appels), pas en un seul appel géant — un modèle léger
# "oublie" de statuer sur une partie des actus au-delà d'une certaine taille de lot
# (cf. commentaire en tête de agents/qualify.py). Coût marginal : le system prompt
# (qualify.md + filtre éditorial, ~10K caractères) est répété par lot.
QUALIFY_BATCH_SIZE = int(os.environ.get("QUALIFY_BATCH_SIZE", "20"))
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

# Correspondance code BRVM -> nom complet de l'entreprise (relevé le 2026-07-10 sur
# https://www.brvm.org/fr/cours-actions/0, table "Activités du marché"). Sert de RÉFÉRENCE
# FIABLE pour "Marché en 30 secondes" : le scraper ne récupère que le code (ETIT, BOAC...)
# dans les tableaux top 5 / flop 5, jamais le nom — donc pas question de laisser le LLM le
# deviner. À réactualiser si la cote BRVM évolue (nouvelles admissions/radiations).
BRVM_TICKER_NAMES = {
    "ABJC": "Servair Abidjan Côte d'Ivoire",
    "BICB": "Banque Internationale pour l'Industrie et le Commerce du Bénin",
    "BICC": "BICI Côte d'Ivoire",
    "BNBC": "Bernabé Côte d'Ivoire",
    "BOAB": "Bank of Africa Bénin",
    "BOABF": "Bank of Africa Burkina Faso",
    "BOAC": "Bank of Africa Côte d'Ivoire",
    "BOAM": "Bank of Africa Mali",
    "BOAN": "Bank of Africa Niger",
    "BOAS": "Bank of Africa Sénégal",
    "CABC": "Sicable Côte d'Ivoire",
    "CBIBF": "Coris Bank International Burkina Faso",
    "CFAC": "CFAO Motors Côte d'Ivoire",
    "CIEC": "CIE Côte d'Ivoire",
    "ECOC": "Ecobank Côte d'Ivoire",
    "ETIT": "Ecobank Transnational Incorporated Togo",
    "FTSC": "Filtisac Côte d'Ivoire",
    "LNBB": "Loterie Nationale du Bénin",
    "NEIC": "NEI-CEDA Côte d'Ivoire",
    "NSBC": "NSIA Banque Côte d'Ivoire",
    "NTLC": "Nestlé Côte d'Ivoire",
    "ONTBF": "Onatel Burkina Faso",
    "ORAC": "Orange Côte d'Ivoire",
    "ORGT": "Oragroup Togo",
    "PALC": "Palm Côte d'Ivoire",
    "PRSC": "Tractafric Motors Côte d'Ivoire",
    "SAFC": "Safca Côte d'Ivoire",
    "SCRC": "Sucrivoire Côte d'Ivoire",
    "SDCC": "Sode Côte d'Ivoire",
    "SDSC": "Africa Global Logistics Côte d'Ivoire",
    "SEMC": "Eviosys Packaging Siem Côte d'Ivoire",
    "SGBC": "Société Générale Côte d'Ivoire",
    "SHEC": "Vivo Energy Côte d'Ivoire",
    "SIBC": "Société Ivoirienne de Banque",
    "SICC": "Sicor Côte d'Ivoire",
    "SIVC": "Erium Côte d'Ivoire",
    "SLBC": "Solibra Côte d'Ivoire",
    "SMBC": "SMB Côte d'Ivoire",
    "SNTS": "Sonatel Sénégal",
    "SOGC": "SOGB Côte d'Ivoire",
    "SPHC": "SAPH Côte d'Ivoire",
    "STAC": "Setao Côte d'Ivoire",
    "STBC": "SITAB Côte d'Ivoire",
    "TTLC": "TotalEnergies Marketing Côte d'Ivoire",
    "TTLS": "TotalEnergies Marketing Sénégal",
    "UNLC": "Unilever Côte d'Ivoire",
    "UNXC": "Uniwax Côte d'Ivoire",
}

# Glossaire des sigles/abréviations récurrents (hors codes BRVM, couverts ci-dessus) —
# newsletter pour novices : chacun doit être explicité à sa première apparition dans un
# numéro. "BRVM" est volontairement exclu : c'est le sujet même de la newsletter, l'expliquer
# à chaque numéro serait redondant avec le tagline/l'édito.
ACRONYM_GLOSSARY = {
    "UEMOA": "Union Économique et Monétaire Ouest-Africaine, les 8 pays qui partagent le "
             "FCFA et la BRVM",
    "BCEAO": "Banque Centrale des États de l'Afrique de l'Ouest",
    "CEDEAO": "Communauté Économique des États de l'Afrique de l'Ouest (15 pays)",
    "FCFA": "Franc CFA, la monnaie commune de la zone UEMOA",
    "PIB": "Produit Intérieur Brut",
    "PND": "Plan National de Développement",
    "OPCVM": "Organisme de Placement Collectif en Valeurs Mobilières, un fonds "
             "d'investissement collectif",
    "SICAV": "Société d'Investissement à Capital Variable, un type d'OPCVM",
    "PER": "Price Earnings Ratio, le ratio cours de l'action / bénéfice par action",
    "BOAD": "Banque Ouest-Africaine de Développement",
    "BIDC": "Banque d'Investissement et de Développement de la CEDEAO",
    "IFC": "International Finance Corporation, filiale de la Banque mondiale dédiée au "
           "secteur privé",
    "MoU": "Memorandum of Understanding, un protocole d'accord",
}


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
