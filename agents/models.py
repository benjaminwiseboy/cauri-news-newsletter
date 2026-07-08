"""Schémas Pydantic échangés entre les agents.

Chaque étape produit un objet validé ; si un modèle renvoie un JSON malformé,
l'erreur remonte immédiatement au lieu de se propager en aval.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Sections de la newsletter alimentées par le pipeline LLM.
# (Marché en 30s = données factuelles, traité hors sélection LLM.)
SECTIONS = [
    "hot_news",
    "la_lecon",
    "sur_le_continent",
    "sack_afrique",
    "le_radar",
]


# --- Étape 1 : scraping (aucun LLM) ---------------------------------------
class ScrapedItem(BaseModel):
    id: str
    source: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    title: str
    text: str = ""
    # Sections vers lesquelles la source oriente a priori (indice, non contraignant).
    section_hints: list[str] = Field(default_factory=list)


class MarketData(BaseModel):
    """Données de marché factuelles. Transitent VERBATIM jusqu'au HTML.

    Le LLM ne doit jamais recalculer ni inventer ces chiffres.
    """
    brvm_composite: Optional[str] = None
    brvm_30: Optional[str] = None
    top_hausses: list[dict] = Field(default_factory=list)   # [{valeur, variation}]
    top_baisses: list[dict] = Field(default_factory=list)
    valeur_phare: Optional[dict] = None
    fcfa_usd: Optional[str] = None
    commentaire_source: Optional[str] = None                # note brute éventuelle


class ScrapeOutput(BaseModel):
    date: str
    market: MarketData
    items: list[ScrapedItem] = Field(default_factory=list)


# --- Étape 2 : qualification ----------------------------------------------
class QualifiedItem(BaseModel):
    id: str
    title: str
    cercle: str                     # "brvm_uemoa" | "afrique" | "hors_cercle"
    score: int                      # note globale /12 (le détail des 6 critères reste interne)
    section_cible: str
    red_flag: Optional[str] = None
    decision: str                   # "retenu" | "reserve" | "ecarte"
    justification: str = ""


class QualifyOutput(BaseModel):
    date: str
    items: list[QualifiedItem] = Field(default_factory=list)


# --- Étape 3 : sélection (3 candidats par section) ------------------------
class Candidate(BaseModel):
    source_id: str                  # renvoie vers un ScrapedItem
    titre: str                      # titre/angle proposé
    angle: str
    faits_cles: list[str] = Field(default_factory=list)
    score: int = 0                  # priorité/pertinence pour la section (0-100)


class SectionCandidates(BaseModel):
    section: str
    candidats: list[Candidate]      # attendu : 5, triés du plus au moins pertinent


class SelectOutput(BaseModel):
    date: str
    sections: list[SectionCandidates] = Field(default_factory=list)


# --- Étape 4 : rédaction --------------------------------------------------
class WriteOutput(BaseModel):
    date: str
    title: str                      # titre du post Ghost
    html: str                       # document HTML complet (avec <style>)
    subject: str = ""               # sujet de l'email (email_subject)
    preview: str = ""               # texte de preview / preheader (custom_excerpt)
    # Notions/contenus effectivement publiés — mémorisés pour ne pas les répéter.
    lecon: str = ""                 # concept enseigné dans "La leçon"
    sack_chiffre: str = ""          # sujet du "Le chiffre" (Sack d'Afrique)
    sack_funfact: str = ""          # sujet du "Fun fact" (Sack d'Afrique)
