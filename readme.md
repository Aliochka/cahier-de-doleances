# Cahier de doléances

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

> **Vision** : *Un pas de plus vers la révolution.*

---

## 🚀 Objectif du projet

Cahier de doléances est un site/service permettant d’explorer, rechercher et analyser les contributions citoyennes du **Grand Débat National**.  
L’idée : donner un accès simple et puissant à cette matière brute, pour nourrir les réflexions et ouvrir la voie à de nouvelles perspectives collectives.

Gros merci a chat gpt qui a codé l'ultra majorité de ce que vous voyez !




---

## 🗺️ Roadmap v0

- [x] Mise en place du backend (FastAPI + SQLite pour démarrage local)  
- [x] Ingestion massive des contributions (CSV compressés)  
- [x] Indexation plein texte (FTS5) pour recherche rapide  
- [x] Front-end minimaliste mobile-first
  - [x] ui
  - [ ] page accueil
    - [x] back
    - [ ] ux
    - [ ] ui
    - [ ] contenu
  - [x] page question
    - [x] back
    - [x] ux
    - [x] ui
  - [x] page auteur
    - [x] back
    - [x] ux
    - [x] ui
  - [x] recherche par question
    - [x] back
    - [x] ux
    - [x] ui
    - [x] optimisation
  - [x] recherche par réponses
    - [x] back
    - [x] ux
    - [x] ui
    - [x] optimisation
- [x] migration postgresql
- [x] MEP !

## V0+

- [ ] page formulaire
- [ ] bugs
  - [ ] l'url partial qui pop
  - [ ]  page answer contenu responsive
- [ ] SEO technique
- [ ] perf page question
- [ ] rework page question
- [ ] check bdd (questions sans réponses ?)

 
## v1
- [ ] optimisations SEO
- [ ] ux/ui 
  - [ ] refaire le _card answer
  - [ ] navigation
  - [ ] pagination (loader)
- [ ] page thème
- [ ] mentions légales
- [ ] footer
- [ ] menu joli
- [ ] quelques tests bien pensés
- [ ] logo
- [ ] accueil

## v2
- [ ] secret secret




---

## 🛠️ Guide pour les développeurs

### 1. Lancer le projet

\`\`\`bash
git clone https://github.com/[ton-org]/cahier-de-doleances.git
cd cahier-de-doleances
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```bash
# Lancer le serveur
gunicorn -k uvicorn.workers.UvicornWorker app.app:app --reload
```

### 2. Créer la base de test

# Sandbox DB Setup (SQLite)

This sets `sandbox.db` as the **default** database for dev/tests, while keeping your heavy `gdn.db` for full ingestion.

## Resolution order
1. `--db` CLI flag (if your scripts accept it)
2. `GDN_DB_PATH` env var (e.g., from `.env`)
3. Default: `./sandbox.db`

## Files in this bundle
- `scripts/make_sandbox.py` – creates/refreshes `sandbox.db`, runs Alembic migrations, then ingests test CSVs from `data/example`.
- `app/config_db.py` – small helper to resolve the DB path/URL consistently.
- `.env.example` – sample env file with `GDN_DB_PATH=./sandbox.db`.
- `.gitignore.additions.txt` – lines to add to your repo's `.gitignore`.

## Usage

1. Copy files into your repo (keep relative paths).
2. Add `.env` based on `.env.example` (or export `GDN_DB_PATH`).
3. Ensure Alembic is configured (has `alembic.ini`, `alembic/`).
4. Put small CSVs in `data/example/` (the seed).
5. Run:

   ```bash
   python scripts/make_sandbox.py
   ```

   Or customize:

   ```bash
      python scripts/make_sandbox.py \       
        --ingest-pairs 'data/example/democratie-et-citoyennete-tiny.csv::ingest/mappings/democratie_citoyennete.yml' \
        --ingest-pairs 'data/example/la-fiscalite-et-les-depenses-publiques-tiny.csv::ingest/mappings/fiscalite_depenses.yml' \
        --ingest-pairs 'data/example/la-transition-ecologique-tiny.csv::ingest/mappings/transition_ecologique.yml' \
        --ingest-pairs 'data/example/organisation-de-letat-et-des-services-publics-tiny.csv::ingest/mappings/organisation_etat_services.yml'
   ```

## Alembic note

The script sets `DATABASE_URL` during migration if not already set, using `GDN_DB_PATH`. You can also wire your `alembic/env.py` to read `DATABASE_URL` if present, otherwise fall back to `GDN_DB_PATH` or `./sandbox.db`.

## Safety

- `make_sandbox.py` **removes** any existing `sandbox.db` before recreating it.
- It exits gracefully if no CSVs are found in `data/example/`.


### 3. Ingestion des données

```bash
python gdn_ingest.py ingest   --csv /chemin/vers/contributions.csv   --db gdn.db   --chunksize 5000
```

### 4. Recherche plein texte

```bash
python gdn_ingest.py search   --db gdn.db   --query "culture NEAR/5 patrimoine"   --limit 20
```

### 5. Rebuild du script en Rust (optionnel, pour performance)

```bash
cargo build --release
./target/release/gdn_ingest ...
```

---

## 📜 Licence

Ce projet est distribué sous licence **MIT**.  
Voir le fichier [LICENSE](./LICENSE) pour plus de détails.

---

## ✊ Un pas de plus vers la révolution

