# RAG-001 — Audit architectural du dépôt

**Recommandation principale :** intégrer `rag/` à la racine, avec un environnement Python autonome, deux connexions PostgreSQL explicites et un moteur de recherche indépendant du LLM. Aucun package partagé ni service supplémentaire n’est nécessaire au démarrage.

L’audit a été réalisé en lecture seule. Aucun fichier créé ou modifié, aucune migration ni aucun test exécuté, aucune connexion PostgreSQL ouverte, aucun modèle téléchargé et aucune intervention sur Wallace. L’état Git est resté propre.

> Cette description concerne l’exécution de l’audit. Le présent fichier en est la copie, enregistrée ensuite à la demande de l’utilisateur.

## 1. État actuel du dépôt

### 1.1. Documentation et périmètre vérifié

Les documents structurants sont déjà présents :

- [docs/plan-rag.md](plan-rag.md) : cadrage du 17 octobre 2026, décisions actées et choix expérimentaux ouverts.
- [docs/audit-corpus-rag.md](audit-corpus-rag.md) : mesures du corpus local du 16 octobre.
- [docs/ingestion.md](ingestion.md) : procédure d’import actuelle.
- [TESTING.md](../TESTING.md) : organisation des vérifications.
- [docs/deploiement.md](deploiement.md) : déploiement Wallace.

Les chiffres du corpus et les caractéristiques matérielles sont **documentés, mais non revérifiés pendant cet audit**. L’égalité entre les données locales et celles de Wallace n’a pas été contrôlée.

### 1.2. Organisation constatée

```text
/
├── app/                    Backend Python
│   ├── models.py           Modèles SQLAlchemy
│   ├── db.py               Moteur et sessions
│   ├── config.py           Configuration applicative
│   ├── routers/            API, comptes, marque-pages, SEO, santé
│   ├── schemas/            Contrats Pydantic publics
│   └── services/           Requêtes et logique applicative
├── frontend/               React Router avec SSR, TypeScript, pnpm
├── ingest/                 Import structuré GDN, vérification, mappings
├── migrations/             Historique Alembic du backend
├── scripts/                Maintenance, analyses, export OpenAPI
├── tests/                  Tests backend et ingestion
├── docs/                   Documentation fonctionnelle et technique
├── notebooks/              Analyses exploratoires
├── data/                   Données locales, ignorées par Git
├── .github/workflows/      CI backend, frontend et contrat API
├── requirements*.txt       Dépendances Python
└── Dockerfile / Compose    Construction et déploiement du backend
```

**Constats :**

- Aucun dossier `rag/` identifié.
- `app` est un package Python explicite ; `ingest` est exécuté par `python -m ingest…`.
- Aucun `pyproject.toml`, `setup.py` ou mécanisme de workspace Python identifié pour le code applicatif.
- Le partage actuel passe par les imports internes au dépôt. L’importeur finit notamment par importer `app.db.engine`.
- Les modules Python suivent principalement `snake_case`. Les couches backend sont organisées par responsabilité et domaine.
- Les scripts mélangent outils actuels et outils historiques : ils ne constituent pas une interface homogène à réutiliser sans examen.
- Le frontend possède son environnement et son verrouillage pnpm propres.

**Emplacement recommandé :** `rag/`, au même niveau que `app/`, `frontend/` et `ingest/`.

### 1.3. Dépendances Python

| Élément | Fait constaté |
|---|---|
| Version de référence | Python 3.11 dans `.python-version`, Docker et CI |
| Installation | `pip` et environnement `venv` documentés |
| Backend | FastAPI, SQLAlchemy 2, Alembic, psycopg2, Pydantic, dotenv, authentification et e-mail |
| Développement | `requirements-dev.txt` inclut les dépendances du backend |
| Analyses | `requirements-analysis.txt` inclut le backend et des dépendances NLP/GPU |
| Verrouillage | Versions directes fixées ; aucun verrou Python transitif complet identifié |
| Qualité | Ruff, pytest, hooks pre-commit |
| Typage Python | Aucun contrôle mypy ou Pyright identifié |

Références : [requirements.txt](../requirements.txt), [requirements-dev.txt](../requirements-dev.txt), [requirements-analysis.txt](../requirements-analysis.txt).

**Point important :** les dépendances lourdes existent déjà dans le fichier d’analyse, mais ce fichier inclut aussi l’application publique. Il ne constitue donc pas une isolation appropriée pour le RAG.

### 1.4. SQLAlchemy, connexions et transactions

Dans [app/db.py](../app/db.py) :

- moteur SQLAlchemy synchrone utilisant psycopg2 ;
- moteur et fabrique `SessionLocal` construits à l’import ;
- chargement automatique de `.env` ;
- configuration du pool et des délais de connexion ;
- sessions sans autocommit, sans autoflush, avec `expire_on_commit=False`.

La sélection de connexion dépend de l’environnement :

- en production : `DATABASE_URL` ;
- hors production : `TEST_DATABASE_URL`, puis `DATABASE_URL`, puis ancienne variable Scalingo.

Importer `app.db` entraîne également le chargement de [app/config.py](../app/config.py), qui traite des paramètres propres au site : sessions, cookies, URL publique, messagerie.

Les routes actuelles utilisent souvent directement `with SessionLocal()`. Les écritures valident explicitement leurs transactions ; les recherches disposent d’un mécanisme de rollback sur erreur SQL dans [app/search_errors.py](../app/search_errors.py).

**Conséquence :** réutiliser `app.db` ferait hériter le RAG de choix de configuration et de connexions sans rapport avec son cycle d’exécution.

### 1.5. Modèles et chaîne documentaire

Les modèles sont regroupés dans [app/models.py](../app/models.py).

| Table | Champs utiles au RAG | Relations |
|---|---|---|
| `forms` | `id`, `name`, `version`, `source` | Questionnaire parent |
| `questions` | `id`, `form_id`, `question_code`, `prompt`, `section`, `position`, `type` | Question → questionnaire |
| `contributions` | `id`, `form_id`, `title`, `source`, `source_contribution_id`, `submitted_at` | Contribution → questionnaire |
| `answers` | `id`, `contribution_id`, `question_id`, `position`, `text`, `value_json` | Réponse → contribution et question |
| `answer_options` | `answer_id`, `option_id` | Association réponse–choix |
| `options` | `id`, `question_id`, `code`, `label`, `position` | Définition des choix |

Pour reconstruire un document :

```text
answers.question_id      → questions.id → forms.id
answers.contribution_id  → contributions.id → contributions.title
```

Il faut également vérifier que `questions.form_id = contributions.form_id`. Les deux rattachements existent séparément ; leur cohérence ne doit pas être seulement supposée.

**Stockage des textes :**

- Réponse ouverte : `answers.text`.
- Réponse à choix : `answers.text` contient les libellés sélectionnés, éventuellement suivis du texte « Autre ».
- Texte « Autre » isolable : `answers.value_json`, propriété `other_text`.
- `value_json` est une colonne **TEXT contenant du JSON**, pas une colonne JSONB.
- `contributions.raw_json` conserve l’enregistrement source complet en TEXT.

L’importeur [ingest/postgres.py](../ingest/postgres.py) privilégie `formattedValue` lorsqu’il est renseigné pour les réponses ouvertes. Il remplace les caractères nuls par `U+FFFD` et consigne cette normalisation.

**Conséquence :** `answers.text` représente le texte consultable normalisé ; il n’est pas systématiquement identique à la valeur brute de l’export.

Pour le premier extracteur :

- sélectionner explicitement les questions de type `text` ;
- traiter séparément les `other_text` des questions à choix ;
- conserver question, questionnaire et contribution ;
- ne pas réindexer intégralement `raw_json` ;
- conserver les titres comme information distincte ;
- ne pas exploiter `topics` et `contribution_topics` comme classification opérationnelle.

### 1.6. Identifiants et précision

Les identifiants documentaires sont des **BIGINT** dans les migrations et les modèles. `Answer.contribution_id` hérite du type de la clé référencée.

Deux identités doivent rester distinctes :

- les identifiants internes PostgreSQL ;
- les identifiants des exports, conservés sous forme textuelle, notamment `source_contribution_id`.

L’importeur construit ce dernier avec un préfixe de source. Il ne faut donc pas remplacer ces identifiants par une conversion numérique.

Le contrat public possède déjà un type `PublicId`, chaîne décimale, dans [app/schemas/forms.py](../app/schemas/forms.py). Les routes convertissent explicitement leurs identifiants en chaînes.

**Règle recommandée :**

- SQL : BIGINT ;
- Python : `int`, sans passage par `float` ;
- JSON et contrats destinés au frontend : chaînes décimales ;
- identifiants externes : chaînes conservées telles quelles.

Une reconstruction indépendante de la base peut attribuer d’autres IDs internes : tout export futur d’index devra vérifier la correspondance du corpus cible.

### 1.7. Migrations et schéma

[migrations/env.py](../migrations/env.py) utilise `app.models.Base.metadata` et dispose de sa propre priorité de sélection d’URL. La dernière révision identifiée est `remove_runtime_caches`.

Le schéma SQL dépasse les seules déclarations ORM :

- colonnes de recherche calculées ;
- index GIN et index partiels ;
- contraintes d’unicité ;
- compteurs et déclencheurs ;
- suivi des imports.

Les modèles seuls ne suffisent donc pas à reconstruire une base source représentative.

### 1.8. Tests et CI

**Backend :**

- pytest ;
- tests d’ingestion utilisant aussi `unittest` ;
- tests PostgreSQL nécessitant une base migrée ;
- fixtures HTTP avec transaction extérieure et savepoints, annulée en fin de test.

Référence : [tests/conftest.py](../tests/conftest.py).

**Qualité :**

- Ruff pour lint, imports et formatage ;
- configuration Ruff ciblant `py310`, alors que l’exécution de référence est Python 3.11 ;
- absence de vérification statique des types Python identifiée.

**CI :**

- [.github/workflows/test.yml](../.github/workflows/test.yml) : Python 3.11, PostgreSQL 17, migrations, Ruff et tests ;
- workflow frontend : Biome, TypeScript, Vitest, build SSR et Playwright ;
- workflow contrat : export OpenAPI et vérification des types TypeScript générés.

### 1.9. Docker et divergences documentaires

Le [Dockerfile](../Dockerfile) installe uniquement `requirements.txt`, puis copie explicitement `app`, `migrations` et `alembic.ini`. Il n’installe pas les dépendances d’analyse.

[compose.deploy.yml](../compose.deploy.yml) utilise le réseau d’un PostgreSQL externe et lance FastAPI et Caddy. Aucun service React SSR n’y figure.

**Écarts explicites :**

| Documentation ou attente | Code/configuration constaté |
|---|---|
| PostgreSQL 17 comme référence | `docker-compose.yml` local utilise encore PostgreSQL 15 ; la CI utilise 17 |
| Application publique React SSR sur Wallace | SSR configuré dans `frontend/`, mais aucun déploiement SSR Wallace identifié ; Caddy transmet les requêtes à FastAPI |
| Installation locale décrite comme accès au site sur `:8000` | Le README précise désormais que FastAPI ne sert plus les pages ; plusieurs instructions de lancement restent héritées |
| Monorepo nommé `cahier-de-doleances-app` | Checkout local nommé `cahier-de-doleances` ; le nom Compose de production est bien `cahier-de-doleances-app` |

La configuration Netlify du frontend constitue une autre cible identifiée. **Elle ne prouve pas son déploiement effectif.**

## 2. Composants réutilisables

| Composant | Réutilisation recommandée |
|---|---|
| Modèles SQLAlchemy | Référence du schéma ; éviter leur import direct au démarrage |
| Migrations du backend | Référence du schéma source et préparation des bases de test sources |
| Importeur structuré | Référence pour interpréter `text`, choix et `other_text` ; ne pas le relancer pour alimenter le RAG |
| Contrats d’IDs publics | Reprendre les règles de précision et de sérialisation |
| Recherche SQL existante | Référence lexicale historique et source de conventions SQL |
| Fixtures PostgreSQL | Reprendre le principe des transactions annulées dans des fixtures RAG autonomes |
| Ruff, pytest, CI PostgreSQL 17 | Conserver ces outils pour rester cohérent |
| Contrat OpenAPI/TypeScript | Point d’intégration futur, lorsqu’une API publique sera effectivement envisagée |

La recherche de [app/services/search.py](../app/services/search.py) importe peu de dépendances, mais son comportement est spécifique au site :

- exclusion des textes de moins de 60 caractères ;
- exclusion des réponses à choix, donc de leurs « Autre » ;
- sélection plafonnée à 1 789 candidats ;
- ordre par identifiant décroissant.

Elle peut servir de **référence historique mesurée**, mais ne doit pas devenir directement le moteur hybride du RAG.

## 3. Contraintes et risques

1. **Configuration implicite.** Importer `app.db` ou charger automatiquement le `.env` racine risque de sélectionner une connexion non souhaitée.

2. **Propagation des dépendances.** `requirements-analysis.txt` et `requirements-dev.txt` incluent le backend. Le RAG doit avoir ses propres fichiers.

3. **Générateur global de dépendances.** [scripts/gen_requirements.py](../scripts/gen_requirements.py) parcourt les imports du dépôt puis réécrit le `requirements.txt` racine. Une future utilisation pourrait y faire entrer des dépendances RAG. Cet outil devra rester hors du processus RAG.

4. **Couverture lexicale inadaptée.** Les seuils actuels écartent des réponses courtes que le cadrage demande de conserver.

5. **Schéma incomplet dans l’ORM.** Une extraction ou des tests fondés uniquement sur `Base.metadata.create_all()` ne reproduiraient pas les migrations.

6. **Isolation logique partielle.** Deux bases dans la même instance PostgreSQL partagent CPU, mémoire, stockage et entrées-sorties.

7. **Contexte Docker.** Les copies explicites protègent actuellement l’image finale. Le futur contenu de `rag/`, ses caches et ses modèles devront aussi être exclus du contexte de construction : image finale et contexte sont deux frontières différentes.

8. **Artefacts ignorés.** Le `.gitignore` racine ignore notamment `*.json`, `*.csv` et `*.parquet` ; `*.jsonl` n’est pas explicitement couvert. Le format et le suivi des jeux d’évaluation devront être explicites.

9. **Outillage global.** `ruff check .` parcourra aussi le futur RAG. Une configuration locale et l’exclusion des artefacts devront être prévues.

10. **Provenance.** Segmentation et déduplication doivent préserver toutes les occurrences sources ; un texte identique ne signifie pas une contribution identique.

**Non vérifié :** droits PostgreSQL actuels, extensions installées aujourd’hui, espace disque disponible, état réel des services Wallace, compatibilité effective des modèles GPU et performances CPU/GPU.

## 4. Architecture recommandée

L’arborescence suivante est une cible progressive. Les dossiers ne doivent être créés que lorsque leur première tâche les utilise.

```text
rag/
├── README.md
├── .env.example
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── requirements-gpu.txt
├── alembic.ini
├── migrations/
├── src/
│   └── cahier_rag/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── contracts.py
│       ├── sources/
│       │   └── gdn.py
│       ├── documents.py
│       ├── storage.py
│       ├── indexing/
│       ├── search/
│       ├── reranking/
│       ├── generation/
│       └── evaluation/
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── fixtures/
```

| Élément | Responsabilité et dépendances | Réutilisation publique |
|---|---|---|
| `config.py` | Paramètres RAG explicites, validation des connexions, aucun import applicatif | Partielle |
| `contracts.py` | Documents, provenance, requêtes, filtres et résultats ; bibliothèque standard privilégiée | Oui |
| `sources/gdn.py` | Lecture du schéma source avec SQLAlchemy Core et psycopg2 | Préparation hors ligne |
| `documents.py` | Normalisation documentaire, contextualisation, segments et traçabilité | Oui |
| `storage.py` | Connexion RAG, écritures par lots et lecture des documents/index | Oui |
| `indexing/` | Embeddings, versions des représentations, reprise ; dépendances GPU optionnelles | Traitements hors ligne |
| `search/` | Recherche lexicale/vectorielle, fusion et diversification | Oui, sans import GPU |
| `reranking/` | Classement optionnel ; implémentation GPU isolée | Selon implémentation |
| `generation/` | Contexte, LLM, réponses et citations | Local initialement |
| `evaluation/` | Échantillons, jugements, métriques et mesures de ressources | Outil de développement |
| `__main__.py` | Commandes locales ; chargement des composants selon la commande | Pas nécessaire au site |
| `migrations/` | Schéma expérimental RAG uniquement | Historique autonome |
| `tests/` | Tests indépendants du backend | Conventions réutilisables |

**Sens des dépendances :**

- les composants échangent des objets définis dans `contracts.py` ;
- la génération appelle la recherche ;
- la recherche reçoit son encodeur de requêtes et son reranker optionnel ;
- la recherche n’importe ni le LLM ni les traitements d’indexation GPU ;
- aucun import entre `app` et `cahier_rag` au démarrage.

La vectorisation des requêtes reste nécessaire en recherche sémantique. Son indépendance vis-à-vis du GPU devra être démontrée par un encodeur CPU compatible, même si les documents ont été encodés sur GPU.

## 5. Décisions techniques à éclairer

### 5.1. Isolation Python

**Faits :** pip/venv déjà utilisés ; absence de workspace Python ; fichiers de dépendances directs fixés.

**Options :**

| Option | Avantage | Compromis |
|---|---|---|
| Venv et requirements propres | Continuité avec le dépôt | Verrouillage transitif à organiser |
| Projet autonome avec uv | Gestion intégrée des environnements et verrouillage | Nouvel outil et conventions |
| Projet Poetry | Packaging et verrouillage intégrés | Changement d’outillage plus important |

**Recommandation :** Python 3.11 initialement, `rag/.venv`, pip et dépendances propres. Un `pyproject.toml` local définit le package installable et les configurations des outils.

Séparer les profils de base, développement et GPU ; aucun ne doit inclure les requirements racine. Avant les expériences reproductibles, figer également les dépendances transitives et documenter l’origine des distributions GPU.

**Risque :** des versions directes fixées ne suffisent pas à reproduire complètement un environnement. Le choix du mécanisme de verrouillage reste un arbitrage limité à `rag/`.

### 5.2. Accès aux données sources

**Faits :** `app.models` dépend essentiellement de SQLAlchemy ; son import ne nécessite pas à lui seul FastAPI. Il regroupe toutefois corpus, comptes, marque-pages et statistiques. `app.db` ajoute des effets de configuration.

**Options :**

- importer les modèles existants avec une connexion indépendante ;
- extraire un package partagé ;
- écrire un lecteur source RAG spécifique.

**Recommandation :** lecteur spécifique, utilisant des requêtes SQL paramétrées via SQLAlchemy Core. Il retourne des objets documentaires et ne connaît ni FastAPI ni la configuration du site.

**Compromis :** quelques définitions de colonnes seront répétées. Des tests de contrat de schéma devront détecter leur dérive. Cette duplication limitée coûte moins qu’une extraction prématurée du modèle applicatif.

### 5.3. Organisation PostgreSQL

**Faits :** une seule connexion applicative est actuellement configurée ; aucune infrastructure RAG identifiée.

| Possibilité | Intérêt | Limite |
|---|---|---|
| Deux bases, deux connexions | Isolation simple, aucun objet ajouté à la source | Pas de jointure SQL directe entre bases |
| Base RAG avec copie documentaire | Recherche autonome, provenance reproductible | Duplication de textes et métadonnées |
| `postgres_fdw` | Accès interbases depuis SQL | Administration et couplage supplémentaires |
| Schéma RAG dans la base source | Jointures simples | Séparation et protection plus faibles |

**Recommandation :** combiner les deux premières possibilités :

- connexion source avec un rôle limité à la lecture du corpus ;
- connexion vers une base locale RAG distincte ;
- copie des documents et métadonnées nécessaires à la recherche dans la base RAG ;
- aucune copie des comptes ou profils ;
- manifeste d’extraction décrivant corpus, révision source, règles et empreintes.

Utiliser des paramètres distincts, par exemple `RAG_SOURCE_DATABASE_URL` et `RAG_DATABASE_URL`, sans repli sur `DATABASE_URL`. Prévoir des transactions sources explicitement en lecture seule et des délais bornés.

**Compromis :** pas de transaction atomique entre les deux bases. Pour ce corpus figé, un manifeste, des lots idempotents et un contrôle de fin d’extraction suffisent initialement.

### 5.4. Migrations

**Faits :** Alembic existant gère toute la base publique et sa metadata.

**Options :** branche supplémentaire dans l’environnement existant, SQL manuel, environnement RAG autonome.

**Recommandation :** environnement Alembic propre dès l’introduction du premier schéma persistant RAG, avec metadata et historique distincts.

Il doit refuser une cible source et ne manipuler que la base RAG. Les éventuelles extensions vectorielles seront provisionnées explicitement dans cette base, après décision.

**Compromis :** deux historiques à maintenir, mais des cycles d’évolution indépendants. Ne pas choisir dès maintenant dimension vectorielle ou index approximatif.

### 5.5. Interface de recherche réutilisable

**Faits :** services SQL déjà séparés des routes ; contrats publics d’IDs existants ; aucun moteur vectoriel identifié.

**Options :** bibliothèque légère, API autonome, appel futur au PC local.

**Recommandation :** commencer par une interface Python légère recevant requête, filtres et limite, et retournant résultats classés et provenance. Les scores restent numériques ; les identifiants JSON restent textuels.

Le moteur doit fonctionner avec un encodeur et un reranker substituables. Son import et son mode lexical doivent fonctionner sans PyTorch, CUDA ou LLM.

Une extraction en package partagé pourra intervenir lorsqu’un premier consommateur public concret existera. Une API locale ou un microservice ne sont pas nécessaires maintenant.

**Risque :** le déploiement public exigera aussi un benchmark de vectorisation des requêtes sur CPU, une correspondance des modèles et un manifeste d’index compatible.

### 5.6. Tests initiaux

**Faits :** pytest et PostgreSQL 17 sont déjà utilisés en CI ; les tests backend ont leurs propres fixtures applicatives.

**Recommandation :** fixtures RAG indépendantes, deux bases de test explicites et trois niveaux :

- **Unitaires sans réseau ni GPU :** extraction logique, provenance, choix/« Autre », réponses courtes, Unicode, textes longs, segmentation.
- **Intégration PostgreSQL :** contrat source, migrations RAG, lecture par lots, reprise, idempotence et contraintes.
- **Contrats d’exécution :** absence de repli sur l’environnement backend, import de la recherche sans dépendances GPU, refus des cibles incorrectes.

Dès le début, vérifier des IDs supérieurs à `2^53` et jusqu’à la borne BIGINT signée, avec aller-retour SQL/Python/JSON sans perte.

Les benchmarks GPU et évaluations de pertinence doivent rester séparés des tests courants et explicitement déclenchés.

## 6. Arbitrages avant implémentation et découpage proposé

### Arbitrages nécessaires pour RAG-002

1. Valider **pip/venv autonome**, et préciser le mécanisme de verrouillage transitif.
2. Valider **deux connexions et une copie documentaire dans une base RAG distincte**.
3. Confirmer les noms de bases et la séparation des rôles source, ingestion et migrations.
4. Valider le **contrat documentaire minimal** : IDs, origine, type de texte, question, questionnaire, titre, empreinte et version de transformation.

Le modèle d’embedding, le LLM, la dimension des vecteurs, la segmentation définitive et le type d’index peuvent rester ouverts.

### Premières tâches proposées

| Tâche | Dépendances | Critères d’acceptation principaux |
|---|---|---|
| **RAG-002 — Socle autonome** | Arbitrages d’isolation | Package dans `rag/`, environnement propre, configuration explicite, pytest/Ruff locaux ; aucun import de `app`, aucune modification du déploiement |
| **RAG-003 — Contrat documentaire et lecteur source** | RAG-002 | Lecture seule par lots ; réponses ouvertes et « Autre » distingués ; provenance complète ; IDs exacts ; aucun chargement de `raw_json` intégral inutile |
| **RAG-004 — Stockage expérimental** | Contrat RAG-003 | Base distincte, Alembic propre, écritures idempotentes, reprise après interruption et contrôles de cible |
| **RAG-005 — Échantillon et référence d’évaluation** | RAG-003, persistance si nécessaire | Sélection reproductible, couverture des questionnaires/cas limites, jugements de pertinence et séparation réglage/évaluation |
| **RAG-006 — Référence lexicale locale** | RAG-004 et RAG-005 | Recherche sans GPU, conservation des textes courts, classement déterministe, métriques de référence |
| **RAG-007 — Expériences embeddings et recherche hybride** | RAG-006 | Comparaison sur échantillon, contexte et segmentation versionnés, qualité/latence/mémoire/stockage mesurés |
| **RAG-008 — Reranking et diversification** | RAG-007 | Gain mesuré, mode sans reranker, toutes les provenances conservées |
| **RAG-009 — Génération documentaire** | Recherche validée | LLM isolé, contexte borné, citations vérifiables ; recherche utilisable indépendamment |

**RAG-002 peut donc rester une tâche de fondation limitée : isolation, configuration, packaging et contrôles des frontières. Elle ne nécessite encore ni installation vectorielle, ni choix de modèle, ni modification de Wallace.**
