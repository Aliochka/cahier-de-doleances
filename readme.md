# Cahier de doléances

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

> **Vision** : *Un pas de plus vers la révolution.*

---

## 🚀 Objectif du projet

Cahier de doléances est un site/service permettant d’explorer, rechercher et analyser les contributions citoyennes du **Grand Débat National**.  
L’idée : donner un accès simple et puissant à cette matière brute, pour nourrir les réflexions et ouvrir la voie à de nouvelles perspectives collectives.


---

## 🗺️ Roadmap v0

- [ ] Mise en place du backend (FastAPI + SQLite pour démarrage local)  
- [ ] Ingestion massive des contributions (CSV compressés)  
- [ ] Indexation plein texte (FTS5) pour recherche rapide  
- [ ] Front-end minimaliste mobile-first  
- [ ] Scripts d’analyses exploratoires (Python / Rust)  

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
npm run:dev
```

### 2. Créer la base de test

```bash
# Base SQLite par défaut
touch gdn.db
```

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