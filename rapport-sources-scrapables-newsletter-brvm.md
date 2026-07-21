# Rapport — Sources exploitables automatiquement, par rubrique
*Newsletter BRVM — uniquement les sources scrapables (HTML libre, RSS) ou accessibles via API ouverte*

**Légende**
- `[API]` — accès structuré JSON/XML, pas de scraping HTML, le plus stable
- `[RSS]` — flux structuré standard, parsable par n'importe quel lecteur RSS
- `[HTML libre]` — pas de paywall détecté, scraping HTML nécessaire (vérifier robots.txt avant automatisation)
- `[Données ouvertes]` — fichiers exportables (Excel/PDF/SPSS), pas de flux temps réel

---

## 1. Marché en 30 secondes

| Source | Accès | URL |
|---|---|---|
| BRVM — Indices | `[HTML libre]` | https://www.brvm.org/fr/indices |
| BRVM — Cours actions | `[HTML libre]` | https://www.brvm.org/fr/cours-actions/0 |
| BRVM — Bulletin officiel de la cote | `[HTML libre]` | https://www.brvm.org/fr/bulletins-officiels-de-la-cote |
| BRVM — Volumes/Valeurs | `[HTML libre]` | https://www.brvm.org/fr/volumes/0 |
| Sika Finance — Cotation BRVM Composite | `[HTML libre]` | https://www.sikafinance.com/marches/cotation_BRVMC |
| Sika Finance — Cotation BRVM 30 | `[HTML libre]` | https://www.sikafinance.com/marches/cotation_BRVM30 |
| BCEAO — Base de données économiques et financières (export Excel) | `[Données ouvertes]` | https://www.bceao.int/fr/content/la-base-des-donnees-economiques-et-financieres |

---

## 2. Hot news

| Source | Accès | URL |
|---|---|---|
| Sika Finance — Actualités BRVM | `[HTML libre]` | https://www.sikafinance.com/marches/actualites_bourse_brvm |
| Agence Ecofin — flux RSS officiel (toutes rubriques) | `[RSS]` | https://www.agenceecofin.com/obrss-2/ecofin-ugb-all-secteurs |
| Bénin Web TV — rubrique Économie | `[RSS]` | https://beninwebtv.com/economie/feed/ |
| EcoMatin — 1er média économique d'Afrique Centrale (CEMAC) | `[RSS]` | https://ecomatin.net/feed.xml |
| Africanews FR — flux général | `[RSS]` | https://fr.africanews.com/feed/rss?themes=news |
| Africanews FR — filtré par pays (ex. Sénégal) | `[RSS]` | https://fr.africanews.com/feed/rss?tag=senegal |
| AllAfrica — Afrique de l'Ouest (FR) | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
| APA News | `[HTML libre]` | https://fr.apanews.net/ |
| BRVM — Avis & publications | `[HTML libre]` | https://www.brvm.org/fr/marche/avis-et-publications/avis |
| BCEAO — Publications | `[HTML libre]` | https://www.bceao.int/fr/publications |
| Afreximbank — Press releases (dates fiables, EN) | `[HTML libre]` | https://www.afreximbank.com/category/press-releases/ |
| Fratmat.info — Rubrique Économie (dates injectées en JS, best-effort) | `[HTML libre]` | https://www.fratmat.info/rubrique/economie |
| African Capital Markets News (EN) | `[RSS]` | https://africancapitalmarketsnews.com/feed/ |
| Nairametrics — catégorie Énergie (EN, pétrole/raffineries) | `[RSS]` | https://nairametrics.com/category/energy/feed/ |
| Businessday NG — catégorie Énergie (EN) | `[RSS]` | https://businessday.ng/category/energy/feed/ |
| Businessday NG — catégorie Afrique (EN) | `[RSS]` | https://businessday.ng/africa/feed/ |

*Note AllAfrica : attribution + lien vers la page d'origine obligatoires (usage gratuit, conditions précisées sur allafrica.com/misc/tools/rss.html).*

---

## 3. La leçon

| Source | Accès | URL |
|---|---|---|
| AMF-UMOA — réglementation/organisation | `[HTML libre]` | https://www.amf-umoa.org |
| BRVM — espace pédagogique débutant | `[HTML libre]` | https://www.brvm.org/fr |
| Sika Finance — simulateurs & formations | `[HTML libre]` | https://www.sikafinance.com |

---

## 4. Sur le continent

**Données macro (API)**

| Source | Accès | URL |
|---|---|---|
| Banque mondiale — Indicators API | `[API]` | https://api.worldbank.org/v2/country/{ISO3}/indicator/{code}?format=json |
| Banque mondiale — doc API | — | https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation |
| FMI — DataMapper API (indicateurs macro) | `[API]` | https://www.imf.org/external/datamapper/api/v1/{indicateur} |
| FMI — doc API | — | https://www.imf.org/external/datamapper/api/help |
| FMI — dataset dédié Afrique subsaharienne (AFRREO) via API SDMX | `[API]` | https://data.imf.org/en/Resource-Pages/IMF-API |
| BAD/AfDB — African Economic Outlook / MEO (PDF) | `[HTML libre]` | https://www.afdb.org/fr/knowledge/publications/african-economic-outlook |

**Presse panafricaine**

| Source | Accès | URL |
|---|---|---|
| RFI Afrique | `[RSS]` | https://www.rfi.fr/fr/afrique/rss |
| Africanews FR | `[RSS]` | https://fr.africanews.com/feed/rss?themes=news |
| AllAfrica — Afrique de l'Ouest (FR) | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
| APA News | `[HTML libre]` | https://fr.apanews.net/ |
| TechCabal (EN, tech/fintech panafricain) | `[RSS]` | https://techcabal.com/feed/ |
| Tustex — Bourse de Tunis (FR, couvre aussi Tunisie Valeurs) | `[RSS]` | https://www.tustex.com/rss/bourse.xml |
| CMA Rwanda — News & publications (EN, dates seulement sur pages détail, best-effort) | `[HTML libre]` | https://www.cma.rw/news-publications |

**Statistiques nationales (UEMOA)**

| Pays | Institut | Accès | URL |
|---|---|---|---|
| Côte d'Ivoire | ANStat | `[HTML libre]` | https://www.anstat.ci/ |
| Sénégal | ANSD | `[HTML libre]` | https://www.ansd.sn/ |
| Bénin | INStaD | `[HTML libre]` | https://instad.bj/ |
| Burkina Faso | INSD | `[HTML libre]` | https://www.insd.bf/ |
| Togo | INSEED | `[HTML libre]` | https://inseed.tg/ |
| Mali | INSTAT | `[HTML libre]` | https://instat-mali.org/fr |
| Niger | INS | `[HTML libre]` | https://www.stat-niger.org/ |
| Régional | AFRISTAT | `[HTML libre]` | https://www.afristat.org/ |

---

## 5. Sack d'Afrique

| Source | Type de contenu | Accès | URL |
|---|---|---|---|
| Africultures — flux RSS | Culture (cinéma, musique, littérature, société) | `[RSS]` | https://africultures.com/feed/ |
| RFI Afrique | Actu + culture/société (même flux) | `[RSS]` | https://www.rfi.fr/fr/afrique/rss |
| Africanews FR — filtré culture | Culture/société | `[RSS]` | https://fr.africanews.com/feed/rss?themes=culture |
| AllAfrica — Afrique de l'Ouest (FR) | Mix actu/société, filtrable par mot-clé | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
| EasyEquities blog (EN, ZA) | Éducation financière/investissement grand public | `[RSS]` | https://blogs.easyequities.co.za/rss.xml |
| Banque mondiale — Indicators API | Chiffres insolites (démographie, mobile money, etc.) | `[API]` | https://api.worldbank.org/v2/... |
| Afrobarometer | Perceptions/opinions Afrique (insight) | `[Données ouvertes]` | https://www.afrobarometer.org/data/ |
| Instituts nationaux de statistique | "Le chiffre" | `[HTML libre]` | cf. tableau rubrique 4 |

*Pas d'API/flux fiable identifié pour le volet "fun fact léger non économique" — à défaut, puiser dans Africultures/RFI/Africanews-culture ci-dessus plutôt que dans des comptes sociaux non vérifiés (Africa Facts Zone et équivalents), qui ne sont de toute façon pas scrapables (CGU Facebook/X).*

---

## 6. Le radar

| Source | Accès | URL |
|---|---|---|
| APA News | `[HTML libre]` | https://fr.apanews.net/ |
| AllAfrica — Afrique de l'Ouest (FR) | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
| Africanews FR | `[RSS]` | https://fr.africanews.com/feed/rss?themes=news |
| Agence Ecofin — flux RSS officiel | `[RSS]` | https://www.agenceecofin.com/obrss-2/ecofin-ugb-all-secteurs |
| Bénin Web TV — rubrique Économie | `[RSS]` | https://beninwebtv.com/economie/feed/ |
| BRVM — Avis & publications | `[HTML libre]` | https://www.brvm.org/fr/marche/avis-et-publications/avis |

---

## Rubriques sans source externe nécessaire

- **Bonjour. (édito)** — contenu interne (signature, ton du jour)
- **Le menu** — sommaire interne
- **Partenaire du jour** — contenu commercial fourni par l'annonceur
- **Comment soutenir Cauri News ?** — mécanique interne (partage)
- **Footer** — mentions légales internes

---

## Sources écartées de ce rapport (non scrapables) — pour mémoire

Financial Afrik, La Tribune Afrique, Jeune Afrique/The Africa Report, Le Monde Afrique (paywall total ou partiel) ; X/Twitter et Facebook (CGU interdisant le scraping, API payante) ; notes de recherche des SGI (diffusion email, pas d'URL publique) ; Afrobarometer hors data portal (questionnaires en ligne, pas de flux).

**Évaluées le 2026-07-13** (liste fournie par l'utilisateur) — écartées après vérification directe (curl avec le User-Agent réel du scraper) :
- **Bloomberg Africa** — paywall quasi-total + robots.txt bloque `/press-releases/`, `/search`.
- **African Markets (african-markets.com)** — robots.txt `Disallow: /` explicite pour les bots IA (ClaudeBot, GPTBot, etc.).
- **Chase/JPMorgan** — pas de flux Afrique public, recherche réservée aux clients connectés.
- **Safaricom / Ziidi Trader** — newsroom protégée par WAF (403) ; sujet de toute façon trop ponctuel (lancement produit) pour un flux d'actu régulier.
- **Mansa Markets** — diffusion uniquement par email ("The Mansa Brief"), aucune archive web datée.
- **TLP Advisory** — blog existant mais centré droit des startups/venture (Nigeria), hors périmètre marchés financiers.
- **OCDE** — page publications Afrique bloquée par WAF (403) ; rapports à fréquence annuelle, déjà couverts de façon équivalente par AfDB/African Economic Outlook.
- **Tunisie Valeurs** — page "Nos publications" statique avec une seule balise `<time>` datée de 2021 (pas de dates par article dans le HTML brut) ; remplacée par **Tustex** (RSS Bourse de Tunis, dates fiables, couvre aussi l'actu Tunisie Valeurs).

Retenues et ajoutées à `sources.yaml` le même jour : Afreximbank, Fratmat.info (rubrique Économie), CMA Rwanda, African Capital Markets News, TechCabal, EasyEquities, Tustex. Fratmat et CMA Rwanda ont des dates injectées en JS (absentes du HTML statique) — comme Agence Ecofin (à l'époque), leurs items sont best-effort et écartés en mode `STRICT_FRESHNESS`.

**Ajout du 2026-07-16** : demande explicite du user d'ajouter Agence Ecofin et Bénin Web TV.
- **Agence Ecofin** était déjà présent en `html` sur la home (rendue en JS, résultat souvent vide — cf. note ci-dessus). En regardant son `robots.txt`, le site publie lui-même un lien vers un **flux RSS officiel** (`RSS : https://www.agenceecofin.com/obrss-2/ecofin-ugb-all-secteurs`) — testé en direct : 30 items, tous datés, contenu frais et pertinent. Remplace l'ancienne entrée HTML. ⚠️ Point de vigilance repéré dans ce même `robots.txt` : le site bloque explicitement `ClaudeBot` (et d'autres crawlers IA nommés) sur son contenu général (`Content-Signal: ai-train=no, use=reference`), mais publie et documente lui-même ce flux RSS pour la syndication — usage jugé conforme à leur intention (`use=reference`, comme les autres flux RSS déjà utilisés dans le pipeline).
- **Bénin Web TV** : le flux général (`/feed/`) s'est révélé inadapté (majoritairement du people/sport français syndiqué, sans rapport avec l'Afrique). La **rubrique Économie** (`/economie/feed/`) est en revanche pertinente et panafricaine (Togo, Sénégal, Bénin, Nigeria/Dangote...) — retenue à la place. `robots.txt` très permissif (Allow explicite pour ClaudeBot/Anthropic-AI).

**Ajout du 2026-07-20 (angle mort insolite/culture pour "Sack d'Afrique")** : le user a remarqué que "Sack d'Afrique" reprenait les mêmes idées que "Sur le continent". Diagnostic sur le run réel du 2026-07-13 conservé localement : 121 actus scrapées → seulement 9 qualifiées "retenu" ce jour-là, dont **1 seule** pour Sack d'Afrique (et 0 pour Le radar). `select.py` étant contraint de produire EXACTEMENT 5 candidats/section, il comblait avec des candidats **inventés sans source** (ex. "le poids économique du tourisme animalier", "l'économie des réseaux sociaux") — des généralités économiques qui finissent par ressembler au contenu réel de "Sur le continent", d'où la sensation de répétition. Cause structurelle : aucune source du pipeline n'est dédiée à l'insolite/culture/humain (seul `africanews_culture` ciblait `sack_afrique`) — toutes les sources ajoutées depuis (Nairametrics, BusinessDay, Afreximbank, Tustex...) sont économiques/financières et n'aident pas ce manque spécifique. **Africultures** (déjà repéré dans la version d'origine de ce rapport mais jamais câblé dans `sources.yaml`) ajouté en RSS (`africultures.com/feed/`) — testé en direct : 24 items, tous datés, contenu culture/cinéma/société africaine pertinent pour cette section. Options non retenues à ce stade (proposées mais déclinées par le user) : assouplir la contrainte "exactement 5 candidats" dans `select.md`, et revenir sur le modèle de `select` (passé de Sonnet à Gemini 2.5 Flash Lite le 2026-07-10 pour réduire les coûts — un modèle plus faible, plus enclin à halluciner du remplissage générique).

**Ajout du 2026-07-21** : demande du user ("Ecomatin est-ce que c'est une source scrapable ?"). Confirmé : `ecomatin.net`, 1er média économique d'Afrique Centrale (CEMAC), flux RSS officiel `ecomatin.net/feed.xml` (listé en sitemap dans son propre robots.txt, très permissif, ClaudeBot explicitement autorisé) — testé en direct : 30 items, tous datés du jour, contenu économique/financier substantiel (dette souveraine, résultats d'entreprises, marché bancaire CEMAC : Cameroun, Gabon, Tchad, Congo, RCA, Guinée Équatoriale). Point vérifié : le site affiche une offre "Abonnement Premium" mais l'article testé était intégralement accessible (~96K caractères de texte visible, pas de mur payant sur ce contenu) — pas un blocant pour le scraping RSS (qui n'utilise de toute façon que le titre/résumé du flux, jamais la page complète).

**Ajout du 2026-07-13 (angle mort énergie/pétrole)** : l'utilisateur a signalé que l'actu « Dangote Refinery dépasse les USA en export de kérosène/jet fuel vers l'Europe » (juin 2026, ~466 000 tonnes, publiée début juillet par BusinessDay NG/Punch/Nairametrics/Arbiterz) n'était couverte par aucune source du pipeline — vérifié en direct (aucune mention « Dangote » dans les flux RFI/Africanews/AllAfrica/Sika/APA à date). Cause : aucune source dédiée à l'énergie/pétrole nigérian, alors que Dangote Refinery est un acteur majeur de l'actu économique ouest-africaine. Ajout de 3 flux RSS ciblés (catégories dédiées, pas les flux généraux du site — trop bruités par le politique/sport/faits divers, cf. mésaventure du run #1 de la newsletter) : Nairametrics/Énergie, Businessday NG/Énergie, Businessday NG/Afrique. Testés en direct : tous 200, tous datés, contenu pertinent confirmé (Dangote/pétrole/raffineries en tête de flux).
