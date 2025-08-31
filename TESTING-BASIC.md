# Tests Anti-Production-Breakage 🛡️

**Version basique qui fonctionne MAINTENANT**

## 🚀 Setup Rapide (2 minutes)

```bash
# Setup complet
python scripts/setup_basic_testing.py

# Ou manuel
pip install pytest httpx beautifulsoup4 psutil
python scripts/run_tests.py --critical
```

## ⚡ Tests Critiques (30 secondes)

```bash
# Tests ESSENTIELS - à lancer avant chaque commit
python scripts/run_tests.py --critical
```

**Ce qui est testé :**
- ✅ **Cache TTL Logic** : Popularité → TTL (0-30min)
- ✅ **Template existence** : `_answers_list.html` vs `_answers_list_append.html` 
- ✅ **Import functions** : Cache + Search fonctions
- ✅ **App startup** : L'app se lance

## 📋 Commandes Disponibles

### Tests Rapides
```bash
python scripts/run_tests.py --quick    # Tests de base (< 10s)
```

### Tests Individuels
```bash
# Test cache logic
pytest tests/test_basic.py::test_cache_logic_only -v

# Test templates
pytest tests/test_basic.py::test_template_logic -v

# Test import
pytest tests/test_basic.py::test_app_import -v
```

### Tests avec Markers
```bash
pytest tests/test_basic.py -m cache   # Tests cache uniquement
pytest tests/test_basic.py -m scroll  # Tests scroll uniquement
```

## 🛡️ Protection Pre-commit

Si installé, à chaque `git commit` :
1. ✅ Tests critiques automatiques  
2. ✅ Vérification syntax Python
3. ✅ Cleaning whitespace/files

```bash
# Installation pre-commit
cp .pre-commit-config-simple.yaml .pre-commit-config.yaml
pip install pre-commit
pre-commit install
```

## 🎯 Ce qui est Protégé

### 1. Cache Intelligence 
- **Popularité → TTL** : 1-4 req = 0min, 5-19 req = 5min, 20-99 req = 15min, 100+ req = 30min
- **Functions exist** : `get_cache_ttl_minutes`, `get_cache_key`, etc.

### 2. Infinite Scroll Templates
- **Templates exist** : `_answers_list.html`, `_answers_list_append.html`
- **No duplication** : Différents templates pour full vs append

### 3. Core Application
- **App loads** : FastAPI app se lance sans erreur
- **Imports work** : Toutes les fonctions critiques importables

## 🔧 Debug Tests

```bash
# Run avec détails
pytest tests/test_basic.py -v -s

# Run test spécifique avec debug
pytest tests/test_basic.py::test_cache_logic_only -vvv

# Check markers
pytest tests/test_basic.py --collect-only
```

## 🚀 Prochaines Étapes (Expansion)

Quand on voudra plus de tests :

1. **Fix database fixtures** → Tests avec vraie DB
2. **Add HTTP client tests** → Tests endpoints réels  
3. **Add Playwright** → Tests E2E navigateur
4. **Add benchmarks** → Tests performance

## ✅ Résultats Attendus

```bash
$ python scripts/run_tests.py --critical

Running: Critical tests (cache + scroll basic)
✅ Critical tests (cache + scroll basic) passed

Running: Cache TTL logic test  
✅ Cache TTL logic test passed

🎉 All selected tests passed!
```

Cette stratégie garantit qu'on détecte les régressions **avant** la production avec un minimum de setup ! 🛡️

---

**⚡ TL;DR : `python scripts/run_tests.py --critical` avant chaque deploy !**