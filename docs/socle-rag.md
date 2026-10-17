# RAG-003 — Compte rendu du socle autonome

Réalisé le 17 octobre 2026. Aucun commit, push, accès PostgreSQL ou accès à
Wallace. Aucune table, base, migration, extension ou donnée documentaire créée.

## État initial et décisions

Le cadrage `plan-rag.md`, l'audit RAG-001 et le compte rendu RAG-002 ont été
consultés avant l'implémentation. Le dépôt disposait du backend uv à la racine,
sans workspace et sans dossier RAG.

La recommandation pip/venv de RAG-001 est historique : la décision uv de
RAG-002 et du ticket actuel la remplace. Les exemples utilisent
`cahier_doleances` pour la source ; la documentation locale cite aussi
`cahier_doleances_local`. Aucun nom n'est imposé dans le code.

## Fichiers créés

```text
rag/
├── .env.example               Exemple sans secret, sélection explicite
├── .gitignore                 Secrets locaux et futurs artefacts
├── .python-version            Référence Python 3.11
├── README.md                  Installation, diagnostic, configuration et limites
├── pyproject.toml             Package, dépendances et outils indépendants
├── uv.lock                    Verrou RAG autonome
├── src/cahier_rag/
│   ├── __init__.py            Import sans effets de bord
│   ├── __main__.py            CLI argparse et code d'erreur 2
│   ├── config.py              Validation hors connexion
│   └── db.py                  Moteurs paresseux et transaction source READ ONLY
└── tests/
    ├── conftest.py             Réseau/psycopg2 interdits, environnement synthétique
    └── unit/
        ├── test_cli.py         Diagnostics et confidentialité
        ├── test_config.py      URL, fichiers explicites et isolation des variables
        ├── test_db.py          Connexions indépendantes et cycle de transaction
        └── test_isolation.py   Imports et diagnostic hors du dépôt
```

Ajouts hors de `rag/` : ce compte rendu et `.github/workflows/rag.yml`, un
workflow autonome d'installation stricte, Ruff, pytest et diagnostic. Aucun
service PostgreSQL, Docker ou GPU n'y est nécessaire. Aucun workflow existant
modifié. `.dockerignore` excluait déjà tout `rag/` ; il est resté inchangé,
comme le Dockerfile, les fichiers Compose, le backend et le frontend.

## Dépendances et configuration

Le package est installable avec `uv_build` 0.13.1 et une organisation `src/`.
Les trois dépendances d'exécution reprennent les versions du backend :

- SQLAlchemy 2.0.43 : moteurs et transactions.
- psycopg2-binary 2.9.10 : pilote PostgreSQL synchrone.
- python-dotenv 1.2.4 : lecture d'un fichier uniquement lorsqu'il est choisi.

Le groupe `dev` contient pytest 9.1.1 et Ruff 0.17.0. La configuration repose
sur les dataclasses de Python ; argparse suffit à la CLI. Aucun framework
web, modèle, dépendance GPU ou bibliothèque vectorielle ajouté.

`RAG_SOURCE_DATABASE_URL` et `RAG_DATABASE_URL` sont les seules variables de
connexion consultées. Aucun repli sur les variables backend, aucun chargement
automatique de `.env` et aucune interpolation dotenv. L'environnement prime
sur le fichier explicitement sélectionné, sans modification de `os.environ`.

Une variable manquante échoue lorsqu'une opération requiert ce rôle. Les URL
invalides et les destinations identiques sont refusées avant toute connexion.
La comparaison ignore les identifiants de connexion et normalise les ports
implicites ainsi que les adresses locales courantes. Les messages d'erreur
et le `repr` de configuration ne dévoilent pas les URL ou les secrets.

Les moteurs ne sont créés qu'à l'appel des fabriques et restent sans connexion
tant qu'ils ne sont pas utilisés. Connexion et attente du pool sont bornées à
cinq secondes. La transaction source fixe `postgresql_readonly=True` avant
`begin()`, et les contextes ferment transaction et connexion sur succès ou
erreur. L'appelant doit libérer le pool par `dispose()`.

## Commandes depuis rag/

```bash
uv sync --locked --dev
uv lock --check
uv run --locked python -m cahier_rag --version
uv run --locked python -m cahier_rag check-config --env-file .env.example
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m pytest
```

La commande installée `cahier-rag` est également disponible via `uv run`.
`--connection source` ou `--connection rag` valide un seul rôle. Aucune
commande de diagnostic ne crée de moteur ni n'ouvre de connexion.

## Validations exécutées

| Contrôle | Résultat |
|---|---|
| Installation propre uv dans `rag/.venv/` | Réussie, Python 3.11.17 |
| Verrou RAG strict | Valide, 13 entrées verrouillées incluant le projet et les variantes de plateforme |
| Tests unitaires | **65 réussis**, sans serveur ni connexion |
| Ruff RAG | Lint réussi, 10 fichiers Python conformes au formatage |
| Ruff global du monorepo | Lint réussi ; formatage backend existant conforme (72 fichiers) |
| CLI avec `.env.example` | Configuration valide, aucune connexion |
| Construction de distribution source et wheel | Réussie ; sorties sous `/tmp` |
| Installation sans mode éditable et sans groupe dev dans un environnement séparé | Réussie, 6 distributions d'exécution |
| Import et diagnostic depuis `/tmp` avec cette installation | Réussis, sockets et psycopg2 bloqués |
| Absence de dépendances interdites | Aucun FastAPI, backend, PyTorch, Transformers ou pgvector dans l'environnement RAG |
| Imports sans moteur ni réseau | Vérifiés dans un processus isolé avec interceptions |
| Secrets, environnements, caches et répertoires d'artefacts ignorés | Vérifié avec `git check-ignore` |
| `.env.example` et `rag/uv.lock` versionnables | Vérifié |
| Nouveau workflow | YAML et syntaxe shell vérifiés ; aucun service |
| `git diff --check` | Réussi |

Les empreintes SHA-256 du `pyproject.toml`, du `uv.lock` et du
`.venv/pyvenv.cfg` **du backend** ont été comparées avant/après et sont
identiques. Les deux environnements restent distincts. Les validations uv
utilisent l'outil et le Python déjà présents sous `/tmp` depuis RAG-002 ;
aucun profil shell ni installation globale modifié.

## Limites et suite

- La lecture seule est vérifiée au niveau des options SQLAlchemy et du cycle
  des contextes, avec doubles de test. Aucun comportement serveur ou privilège
  PostgreSQL n'est vérifié ici ; le futur rôle source devra être limité à SELECT.
- Une validation sans DNS ne peut identifier tous les alias, tunnels ou
  chemins de socket menant au même serveur. Les DSN indirects via `service`,
  multihôtes et options libpq arbitraires sont refusés ; le README décrit les
  paramètres acceptés.
- GitHub Actions n'a pas été exécuté à distance : aucun push demandé. La
  construction Docker du backend reste le point non validé de RAG-002 ; elle
  n'est pas reprise ni modifiée dans cette tâche.
- Aucun contrat documentaire définitif, lecteur, schéma, migration, recherche,
  embedding, reranker, LLM ou jeu d'évaluation n'est implémenté. Les modules
  correspondants ne sont pas créés vides. RAG-004 précisera le contrat et le
  lecteur source, avec conservation exacte des identifiants BIGINT.
