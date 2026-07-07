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
| Agence Ecofin | `[HTML libre]` | https://www.agenceecofin.com/ |
| Africanews FR — flux général | `[RSS]` | https://fr.africanews.com/feed/rss?themes=news |
| Africanews FR — filtré par pays (ex. Sénégal) | `[RSS]` | https://fr.africanews.com/feed/rss?tag=senegal |
| AllAfrica — Afrique de l'Ouest (FR) | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
| APA News | `[HTML libre]` | https://fr.apanews.net/ |
| BRVM — Avis & publications | `[HTML libre]` | https://www.brvm.org/fr/marche/avis-et-publications/avis |
| BCEAO — Publications | `[HTML libre]` | https://www.bceao.int/fr/publications |

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
| Africultures | Culture (cinéma, musique, littérature, société) | `[HTML libre]` | https://africultures.com/ |
| RFI Afrique | Actu + culture/société (même flux) | `[RSS]` | https://www.rfi.fr/fr/afrique/rss |
| Africanews FR — filtré culture | Culture/société | `[RSS]` | https://fr.africanews.com/feed/rss?themes=culture |
| AllAfrica — Afrique de l'Ouest (FR) | Mix actu/société, filtrable par mot-clé | `[RSS]` | https://fr.allafrica.com/tools/headlines/rdf/westafrica/headlines.rdf |
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
| Agence Ecofin | `[HTML libre]` | https://www.agenceecofin.com/ |
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
