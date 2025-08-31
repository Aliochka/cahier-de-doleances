# Guide de Tests - Cahier de Doléances

Ce guide décrit la stratégie de tests mise en place pour éviter de casser la production.

## 🏗️ Architecture des Tests

### Structure des Tests
```
tests/                          # Tests unitaires et d'intégration
├── conftest.py                 # Configuration pytest, fixtures
├── test_cache.py              # Tests cache intelligent
├── test_performance.py        # Tests de performance
├── routers/
│   ├── test_search.py         # Tests recherche FTS + timeline
│   ├── test_forms.py          # Tests formulaires + dashboard
│   └── test_*.py              # Tests par router
└── integration/
    └── test_infinite_scroll.py # Tests HTMX scroll

e2e/                           # Tests End-to-End
├── conftest.py               # Configuration Playwright
├── pages/                    # Page Objects
└── tests/                    # Tests E2E par fonctionnalité

scripts/
├── run_tests.py             # Script d'exécution des tests
└── setup_testing.py         # Setup environnement test
```

## 🚀 Installation et Setup

### Setup Initial
```bash
# Installation complète environnement de test
python scripts/setup_testing.py

# Ou installation manuelle
pip install -r requirements-dev.txt
playwright install chromium
pre-commit install
```

## 📊 Types de Tests

### 1. Tests Critiques ⚡
**Tests indispensables qui ne doivent jamais échouer**
```bash
# Tests cache + infinite scroll
python scripts/run_tests.py --critical

# Ou directement
pytest tests/ -m "cache or scroll" --no-cov -x
```

**Couvre :**
- Cache intelligent (TTL basé sur popularité)
- Infinite scroll sans duplication de header
- Templates HTMX (full vs append)
- Transaction handling du cache

### 2. Tests Rapides 🏃‍♂️
**Tests unitaires rapides pour le développement**
```bash
python scripts/run_tests.py --quick
```

**Couvre :**
- Tests unitaires < 1s
- Fonctionnalité de base
- Exclude les tests lents/performance

### 3. Tests de Performance 📈
**Tests avec benchmarks et mesures de performance**
```bash
python scripts/run_tests.py --performance
```

**Couvre :**
- Cache hit vs miss (10x+ amélioration)
- Dashboard cache (évite N+1 queries)
- Memory leaks infinite scroll
- Database query performance

### 4. Tests d'Intégration 🔗
**Tests inter-composants**
```bash
python scripts/run_tests.py --integration
```

**Couvre :**
- Cache + Search endpoints
- HTMX + Backend integration
- Error handling cross-system

### 5. Tests E2E 🌐
**Tests navigateur complet**
```bash
# Lancer serveur test + tests E2E
python -m pytest e2e/ --browser=chromium

# Avec interface visuelle (dev)
python -m pytest e2e/ --browser=chromium --headed
```

**Couvre :**
- Scroll infini visuel (pas de duplication header)
- Navigation complète utilisateur
- Performance perçue
- Accessibilité

## 🛡️ Pre-commit Hooks

**Tests automatiques avant chaque commit :**
```bash
# Configurés automatiquement
git commit -m "fix: ..."

# Tests qui s'exécutent :
# 1. Tests critiques (cache + scroll)
# 2. Linting (flake8, black, isort)
# 3. Formatage automatique
```

## 📋 Tests par Fonctionnalité

### Cache Intelligent
```bash
pytest tests/test_cache.py -v
```
- Popularité → TTL (1 req = 0min, 10 req = 15min, 30+ req = 30min)
- Serialization datetime → string
- Transaction commit/rollback
- Cache hit performance

### Infinite Scroll
```bash
pytest tests/ -m scroll -v
```
- Template `_answers_list.html` vs `_answers_list_append.html`
- Pas de duplication header/search bar
- Cursors pagination
- HTMX detection headers

### Recherche
```bash
pytest tests/routers/test_search.py -v
```
- FTS vs timeline mode
- Cache application selon popularité
- Error handling (cursors malformés, etc.)

### Dashboard Formulaires
```bash
pytest tests/routers/test_forms.py -v
```
- Cache PostgreSQL 30min TTL
- Graphiques Chart.js single/multi choice
- Cache invalidation

## 🔧 Configuration et Variables

### Variables d'Environnement Test
```bash
ENV=test                    # Mode test
DATABASE_URL=sqlite:///:memory:  # DB en mémoire (rapide)
# ou postgresql://test:test@localhost:5432/test
```

### Markers Pytest
```bash
-m "cache"        # Tests cache uniquement
-m "scroll"       # Tests infinite scroll
-m "performance"  # Tests performance/benchmark
-m "slow"         # Tests lents (exclus par défaut)
-m "integration"  # Tests d'intégration
-m "e2e"         # Tests End-to-End
```

## 📊 Coverage et Métriques

### Coverage Reports
```bash
# HTML report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Terminal report
pytest tests/ --cov=app --cov-report=term-missing

# Minimum 80% coverage requis
pytest tests/ --cov-fail-under=80
```

### Performance Benchmarks
```bash
# Run benchmarks
pytest tests/ -m performance --benchmark-only

# Compare avec baseline
pytest tests/ -m performance --benchmark-compare

# Sauvegarder baseline
pytest tests/ -m performance --benchmark-save=baseline
```

## 🚨 Debug Tests Échoués

### Tests Critiques Échoués
```bash
# Run avec debug détaillé
pytest tests/ -m "cache or scroll" -vvv --tb=long --pdb

# Test spécifique
pytest tests/test_cache.py::TestCacheIntelligence::test_cache_save_and_retrieve -vvv
```

### Tests E2E Échoués
```bash
# Avec interface pour voir ce qui se passe
pytest e2e/ --browser=chromium --headed --slowmo=1000

# Screenshots et traces automatiques en cas d'échec
ls test-results/
```

### Debugging Cache
```bash
# Vérifier cache en DB
python -c "
from app.db import SessionLocal
from app.models import SearchCache, SearchStats
with SessionLocal() as db:
    print('Cache entries:', db.query(SearchCache).count())
    print('Search stats:', db.query(SearchStats).count())
"
```

## 🔄 CI/CD Pipeline

### GitHub Actions
- **Push main/develop** : Tests complets
- **Pull Request** : Tests critiques + unitaires
- **Staging deploy** : Tests E2E post-deploy
- **Production deploy** : Seulement si tous les tests passent

### Pipeline Stages
1. **Tests Critiques** (2 min)
2. **Tests Unitaires** (5 min)
3. **Tests Intégration** (10 min)
4. **Tests E2E** (15 min) - staging uniquement
5. **Performance Tests** (10 min) - main branch

## 🎯 Stratégie Anti-Régression

### Tests Obligatoires Avant Deploy
```bash
# Minimum viable (pre-commit)
python scripts/run_tests.py --critical

# Recommandé avant push
python scripts/run_tests.py --quick --coverage

# Complet avant release
python scripts/run_tests.py --all
python -m pytest e2e/
```

### Monitoring Production
- Cache hit rate > 80%
- Page load < 2s average
- Zero infinite scroll errors
- Database queries < 100ms

Cette stratégie garantit qu'on détecte les régressions **avant** qu'elles atteignent la production ! 🛡️