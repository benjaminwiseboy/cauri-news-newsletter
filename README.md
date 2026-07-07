# Newsletter BRVM — pipeline d'agents IA

Génère et publie automatiquement l'édition quotidienne de **Cauri News** sur Ghost.
Pipeline séquentiel de 5 agents, orchestré en Python, exécuté chaque soir via GitHub Actions.

## Pipeline

```
scrape → [fraîcheur + anti-répétition] → qualify → select → write → publish ×2
(1)                (1b/1c)                 (2)       (3)      (4)      (5)
```

## Fraîcheur, anti-répétition et double brouillon

- **Fraîcheur (1b)** : l'édition du jour J ne retient que les actus datées de la fenêtre
  `[J - EDITION_LOOKBACK_DAYS, J[` — par défaut **la veille (J-1)** uniquement. Réglé par
  `EDITION_LOOKBACK_DAYS`. Les dates sont extraites des RSS (feedparser) et des pages HTML
  (`<time datetime>` pour Sika, `span.date-display-single` pour BRVM Avis, etc.). En mode
  `STRICT_FRESHNESS=true` (défaut), une actu sans date exploitable est écartée : ça garantit
  « seulement J-1 ». En pratique seul **Agence Ecofin** reste non daté (page rendue en JS,
  vide en GET simple) et donc écarté en mode strict ; passe à `false` pour le tolérer. Les
  stats macro (World Bank) et le marché BRVM sont exemptés (données de référence).
- **Anti-répétition (1c)** : `history.json` mémorise (par URL/titre) les infos déjà utilisées
  dans un numéro précédent ; elles sont écartées avant le triage. Fichier **committé dans le
  repo** à chaque run (le FS de GitHub Actions est éphémère) → voir le step "Persister" du workflow.
  Rétention : `HISTORY_RETENTION_DAYS` (45 j par défaut).
- **Deux brouillons Ghost** (tous deux en `draft`) :
  1. `[BRUT] Cauri News — <date>` : liste **non formatée** des infos candidates du numéro
     (les 3 pistes par section + sources), générée sans LLM. Document de travail.
  2. `Cauri News — <date>` : la version **formatée** avec les infos choisies.

| # | Agent | Techno | LLM ? |
|---|-------|--------|-------|
| 1 | `agents/scrape.py`  | requests + BeautifulSoup + feedparser | ❌ (données factuelles) |
| 2 | `agents/qualify.py` | OpenRouter (modèle rapide) | ✅ scoring /12 du filtre |
| 3 | `agents/select.py`  | OpenRouter (modèle rapide) | ✅ 3 candidats / section |
| 4 | `agents/write.py`   | OpenRouter (modèle soigné) | ✅ rédige le HTML complet |
| 5 | `agents/publish.py` | Ghost Admin API (carte HTML) | ❌ |

Chaque étape valide sa sortie avec **Pydantic** (`agents/models.py`) et persiste un
artefact dans `out/<date>/` pour inspection.

## Choix techniques

- **Pas de framework d'agents** : chaîne déterministe → Python nu + SDK OpenAI sur OpenRouter.
- **Les chiffres de marché ne passent jamais par le LLM** : ils transitent verbatim du
  scraper jusqu'au HTML. Le LLM trie, choisit et rédige — il ne calcule pas.
- **Publication en carte HTML Lexical** (port de `ghost-publish-card.mjs`) : préserve les
  styles inline, contrairement à `?source=html`.
- **Idempotence** : un slug daté (`cauri-news-<date>`) évite les doublons ; un re-run met à jour.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # puis renseigne les clés
```

## Lancer en local

```bash
python run.py --no-publish          # génère sans publier (test, nécessite OPENROUTER_API_KEY)
python run.py                       # génère + publie (status = PUBLISH_STATUS)
python run.py --date 2026-07-06     # forcer une date

python smoke_test.py 2026-07-07     # test hors-LLM : scrape + dates + fraîcheur + marché (aucune clé requise)
```

## Sources câblées (`sources.yaml`)

Issues de `rapport-sources-scrapables-newsletter-brvm.md` :
- **Marché** : parser dédié BRVM `/fr/indices` — indices (Composite, BRVM-30) + Top 5 / Flop 5,
  validé sur la structure HTML réelle du site.
- **Actus RSS** (fiables) : RFI Afrique, Africanews (news + culture), AllAfrica Ouest.
- **Actus HTML** (extraction générique, sélecteurs affinables) : Sika Finance, Agence Ecofin,
  APA News, BRVM Avis.
- **Macro chiffrée** : API Banque mondiale (croissance PIB, bancarisation, population — pays UEMOA).

## À compléter avant la mise en prod

1. **Affiner les sources HTML** (optionnel) : Sika Finance / Ecofin / APA / BRVM Avis utilisent une
   extraction générique de titres dans `agents/scrape.py::_fetch_html`. Les flux RSS + BRVM + World
   Bank suffisent à faire tourner le pipeline ; affine les sélecteurs HTML seulement si le bruit gêne.
   Vérifie aussi les `robots.txt` avant automatisation.
2. **GitHub Secrets** (Settings > Secrets and variables > Actions) :
   `OPENROUTER_API_KEY`, `GHOST_URL`, `GHOST_ADMIN_KEY`, `PUBLISH_STATUS`.
   **Variables** (non secrètes) : `MODEL_QUALIFY`, `MODEL_SELECT`, `MODEL_WRITE`.
3. **Régénérer la clé Ghost** : celle de `ghost.env` a été exposée en clair — révoque-la
   dans Ghost et crée-en une nouvelle, uniquement en Secret.
4. **Vérifier les slugs de modèles** sur https://openrouter.ai/models.
5. **Planning du cron** : `.github/workflows/daily.yml`, en UTC (voir commentaire). Le cron
   génère le numéro **la veille** : il tourne dimanche→jeudi (`0-4`) et produit l'édition
   de J+1 (dimanche→lundi, …, jeudi→vendredi). Le brouillon est donc prêt la veille au soir.

## Points d'attention

- **Timezone & retards GHA** : cron en UTC, pas d'heure d'été, décalage possible de 5-30 min.
- **Commencer en `draft`** : garder `PUBLISH_STATUS=draft` quelques semaines, relire, puis passer
  à `published` une fois la qualité prouvée.
- **Jours fériés / marché fermé** : le cron produit des éditions lun→ven mais ne gère pas les fériés UEMOA.
- **Coût** : router les étapes de tri vers un modèle bon marché, la rédaction vers un modèle fort.
