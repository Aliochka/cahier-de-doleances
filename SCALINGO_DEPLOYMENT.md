# Déploiement sur Scalingo - Guide spécialisé

## 🚨 **Challenges Scalingo identifiés**

1. **Playwright** peut ne pas fonctionner (limitations conteneur)
2. **Cache local** perdu à chaque redémarrage (file system éphémère)
3. **Limites mémoire** strictes sur les plans de base

## 🎯 **Solutions recommandées**

### **Option 1 : Alternative avec service externe (Recommandé)**

Utiliser un service comme **htmlcsstoimage.com** ou **API Screenshot** :

```python
# Alternative dans app/routers/seo.py
import httpx

async def _generate_og_image_external(template_html: str, cache_key: str) -> Path:
    """Génère une image via service externe (plus fiable sur Scalingo)"""
    
    # Service externe (ex: htmlcsstoimage.com)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://hcti.io/v1/image",
            json={
                "html": template_html,
                "css": "body { width: 1200px; height: 630px; }",
                "viewport_width": 1200,
                "viewport_height": 630
            },
            auth=("your-user-id", "your-api-key")  # Depuis env vars
        )
        
        if response.status_code == 200:
            image_url = response.json()["url"]
            
            # Télécharger et sauvegarder
            img_response = await client.get(image_url)
            cache_path = OG_CACHE_DIR / f"{cache_key}.png"
            
            with open(cache_path, "wb") as f:
                f.write(img_response.content)
                
            return cache_path
```

### **Option 2 : Cache Redis (pour persistance)**

```python
# Configuration Redis sur Scalingo
import redis
import pickle
from pathlib import Path

# Utiliser Redis comme cache au lieu du file system
redis_client = redis.from_url(os.getenv("REDIS_URL"))

async def _get_cached_image(cache_key: str) -> bytes | None:
    """Récupère une image depuis Redis"""
    try:
        image_data = redis_client.get(f"og:{cache_key}")
        return image_data
    except:
        return None

async def _cache_image(cache_key: str, image_data: bytes):
    """Sauvegarde une image dans Redis (expire après 7 jours)"""
    redis_client.setex(f"og:{cache_key}", 604800, image_data)
```

### **Option 3 : Buildpack personnalisé**

```yaml
# .buildpacks (pour Scalingo)
https://github.com/heroku/heroku-buildpack-python
https://github.com/heroku/heroku-buildpack-nodejs  # Pour Playwright
```

## ⚙️ **Configuration Scalingo**

### Variables d'environnement

```bash
# Via dashboard Scalingo ou CLI
scalingo -a votre-app env-set \
  OG_CACHE_STRATEGY=redis \
  REDIS_URL=redis://... \
  HCTI_USER_ID=your-user-id \
  HCTI_API_KEY=your-api-key \
  OG_FALLBACK_ENABLED=true
```

### Addons recommandés

```bash
# Redis pour cache persistant
scalingo -a votre-app addons-add scalingo-redis redis-starter

# Monitoring
scalingo -a votre-app addons-add scalingo-logs-monitoring
```

## 🔧 **Code adapté pour Scalingo**

Créons une version hybride qui fonctionne avec ou sans Playwright :

```python
# app/routers/seo_scalingo.py - Version compatible Scalingo

import os
import redis
import httpx
from pathlib import Path

# Configuration adaptative
USE_EXTERNAL_SERVICE = os.getenv("OG_EXTERNAL_SERVICE", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL")

# Redis client (si disponible)
redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None

async def _generate_og_image_scalingo(content_data: dict, cache_key: str) -> bytes:
    """Version adaptée pour Scalingo"""
    
    # 1. Vérifier cache Redis d'abord
    if redis_client:
        cached = redis_client.get(f"og:{cache_key}")
        if cached:
            return cached
    
    # 2. Générer via service externe ou Playwright
    if USE_EXTERNAL_SERVICE:
        image_data = await _generate_via_external_service(content_data)
    else:
        try:
            # Tenter Playwright (peut échouer sur Scalingo)
            image_data = await _generate_via_playwright(content_data, cache_key)
        except Exception as e:
            logger.warning(f"Playwright failed: {e}, falling back to external service")
            image_data = await _generate_via_external_service(content_data)
    
    # 3. Sauvegarder dans Redis
    if redis_client and image_data:
        redis_client.setex(f"og:{cache_key}", 604800, image_data)  # 7 jours
    
    return image_data

async def _generate_via_external_service(content_data: dict) -> bytes:
    """Génération via service externe (htmlcsstoimage.com)"""
    html_content = _create_og_html_template(content_data)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://hcti.io/v1/image",
            json={
                "html": html_content,
                "viewport_width": 1200,
                "viewport_height": 630,
                "ms_delay": 1000  # Attendre 1s pour le rendu
            },
            auth=(
                os.getenv("HCTI_USER_ID"), 
                os.getenv("HCTI_API_KEY")
            )
        )
        
        if response.status_code == 200:
            image_url = response.json()["url"]
            img_response = await client.get(image_url)
            return img_response.content
            
    raise Exception("Failed to generate image via external service")
```

## 📋 **Plan de déploiement Scalingo**

### **Phase 1 : Test de compatibilité**
```bash
# 1. Déployer version basique
git push scalingo main

# 2. Tester Playwright
scalingo -a votre-app run python -c "import playwright; print('OK')"

# 3. Si échec, activer service externe
scalingo -a votre-app env-set OG_EXTERNAL_SERVICE=true
```

### **Phase 2 : Configuration optimale**
```bash
# 1. Ajouter Redis
scalingo -a votre-app addons-add scalingo-redis redis-starter

# 2. Configurer service externe (backup)
scalingo -a votre-app env-set \
  HCTI_USER_ID=your-id \
  HCTI_API_KEY=your-key

# 3. Activer logs détaillés
scalingo -a votre-app env-set LOG_LEVEL=DEBUG
```

## 💰 **Coûts estimés**

| Service | Prix/mois | Usage |
|---------|-----------|-------|
| Scalingo M | ~15€ | App + Redis |
| htmlcsstoimage.com | $9 (1000 images) | Service externe |
| **Total** | ~25€/mois | Setup robuste |

## ✅ **Tests de validation Scalingo**

```bash
# Test après déploiement
curl -f https://votre-app.scalingo.io/og/form/1.png -o test-scalingo.png

# Vérifier les logs
scalingo -a votre-app logs --tail

# Monitoring Redis
scalingo -a votre-app redis-console
> INFO memory
```

---

## 🎯 **Verdict : Oui, ça marchera sur Scalingo !**

**Recommandation** : 
1. **Commencer** avec la version Playwright actuelle
2. **Si problème** → basculer sur service externe
3. **Redis obligatoire** pour cache persistant
4. **Plan M minimum** (1GB RAM) requis

Le code actuel marchera probablement, mais avoir le backup externe te garantit 100% de fonctionnement ! 🚀