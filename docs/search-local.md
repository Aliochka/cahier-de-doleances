# Recherche hybride FastAPI — fonctionnement local

SEARCH-004 et SEARCH-005 sont limités à Hal9000. Aucune commande de ce document ne
cible Wallace. React SSR utilise exclusivement `GET /api/v1/search` pour la
recherche générale. Voir le [contrat HTTP](api-search.md), le
[rapport backend](rapport-search-004.md) et le [rapport frontend](rapport-search-005.md).

## Dépendances reproductibles

Le manifeste racine référence `cahier-rag` par chemin local éditable et le verrou
racine fixe ses dépendances avec celles du backend. L'extra `search` ajoute les
seules dépendances d'encodage nécessaires, dont torch 2.10.0 et Transformers
4.57.6. Le torch Linux x86_64 est la distribution CUDA 12.8, comme SEARCH-003.
Pas de Qwen, reranker, quantification générative ou assemblage de contexte.

Depuis la racine, avec Python 3.11 disponible :

```bash
UV_PROJECT_ENVIRONMENT=.cache/search-api-venv uv sync --locked --extra search --python 3.11
```

L'environnement dédié évite de modifier les environnements expérimentaux RAG.
Le modèle BGE-M3 déjà présent dans `rag/models` est réutilisé, sans téléchargement
ou reconstruction d'embeddings. Le backend ne télécharge jamais un modèle au
démarrage ou pendant une requête. Le venv léger sans extra suffit aux tests et
aux fonctions documentaires ; une absence de torch laisse la recherche en 503,
sans lui substituer un autre moteur. L'extra est un choix de dépendances, pas un
sélecteur fonctionnel de moteur.

Les verrous applicatif et expérimental restent indépendants. Pour une cible CPU
future, le backend d'encodage accepte déjà CPU/float32 ; une distribution torch
CPU et ses performances devront être vérifiées séparément. Aucune modification
de Wallace n'est effectuée ici.

## Configuration

`DATABASE_URL` continue à désigner `cahier_doleances_local`. Le backend conserve
son pool applicatif habituel pour les comptes, écritures et pages documentaires.
Un pool applicatif supplémentaire de lecture sert uniquement à l'hydratation
de recherche. Au démarrage de la recherche, l'identité physique de cette base
doit correspondre à celle de la source déclarée par SEARCH-003.

Le fichier local `rag/search-reader.env` de SEARCH-003 contient les deux URL du
lecteur dédié, ici illustrées avec un mot de passe fictif :

```dotenv
RAG_SOURCE_DATABASE_URL=postgresql://cahier_search_reader:MotDePasseFictif123@127.0.0.1:5432/cahier_doleances_local
RAG_DATABASE_URL=postgresql://cahier_search_reader:MotDePasseFictif123@127.0.0.1:5432/cahier_rag
```

Encoder les caractères réservés du mot de passe dans l'URL. Le login reste non
propriétaire et en lecture seule. Le [provisionnement SEARCH-003](../rag/service-recherche.md)
reste inchangé. Aucun droit d'écriture supplémentaire n'est demandé par SEARCH-004.

La nouvelle configuration est `search-api.env`, à la racine, ignorée par Git :

```dotenv
SEARCH_CURSOR_KEY=REMPLACER_PAR_UN_SECRET_ALEATOIRE_D_AU_MOINS_32_OCTETS
SEARCH_DEVICE=cuda
SEARCH_PRECISION=bfloat16
```

Une vraie clé aléatoire a été créée localement pendant SEARCH-004, sans être
affichée. Pour une nouvelle installation seulement, générer le fichier absent :

```python
import os
import secrets

with os.fdopen(os.open("search-api.env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
    f.write("SEARCH_CURSOR_KEY=" + secrets.token_urlsafe(48) + "\n")
    f.write("SEARCH_DEVICE=cuda\nSEARCH_PRECISION=bfloat16\n")
```

Conserver les deux fichiers de secrets en 0600. Ne jamais publier leur contenu.
La clé HMAC n'est ni `SECRET_KEY` de l'authentification, ni un mot de passe PostgreSQL.
Son renouvellement invalide les signatures ; il ne permet pas de récupérer les
instantanés perdus après redémarrage.

Options de chemin : `SEARCH_CONFIG_FILE` choisit explicitement le fichier de
configuration ; les valeurs `SEARCH_READER_ENV` et `SEARCH_MODELS_DIR` permettent
de déplacer le fichier du lecteur et le répertoire de snapshots de modèles.
Les chemins par défaut sont absolus, résolus depuis la racine du projet.
Les variables d'environnement explicites priment sur `search-api.env`.
Si des chemins relatifs sont renseignés, lancer depuis la racine ou utiliser
des chemins absolus. Aucune option d'activation, ancien moteur ou fallback.

## Démarrage et arrêt

```bash
.cache/search-api-venv/bin/python -m uvicorn app.app:app --host 127.0.0.1 --port 8000 --workers 1
```

Le lifespan crée les pools, le cache et le travailleur ; l'initialisation de
recherche démarre en arrière-plan. Les enquêtes/questions/contributions/statistiques
restent accessibles pendant la vérification des bases et le chargement du modèle.
L'endpoint de recherche répond 503 jusqu'à la fin de l'initialisation.
Une erreur laisse seulement la recherche indisponible ; les diagnostics de
démarrage ne contiennent pas les URL ni les exceptions SQL brutes.

Une instance BGE-M3 est chargée et préparée une seule fois ; elle est réutilisée
pour les nouvelles recherches. Le modèle et les index doivent correspondre au
manifeste vérifié `full`. Le service n'importe pas le parcours RAG génératif et
ne lit aucun fichier de campagne `selection.json`.

Utiliser **un processus** : le modèle, le cache LRU et ses curseurs sont locaux
au processus. Ne pas ajouter plusieurs workers sans cache partagé et stratégie
de possession du modèle. Éviter le reloader pour les observations de performance,
car un redémarrage recharge le modèle et détruit les instantanés.

Arrêt normal avec Ctrl-C : annulation de l'initialisation éventuelle, attente de
la fin réelle des travaux synchrones, puis libération modèle, exécuteurs et pools.
L'annulation ne tue pas une inférence en thread. Un encodeur durablement bloqué
exigerait une supervision de processus, comme documenté dans SEARCH-003.

## Exécution, délais et mémoire

Un calcul H1 actif au plus, deux recherches au plus en attente ; les limites
SEARCH-003 sont conservées. L'hydratation possède deux threads et quatre travaux
admis au maximum, y compris ceux dont le client a abandonné l'attente. Ses
connexions READ ONLY sont indépendantes du pool applicatif de navigation.

L'API crée une échéance monotone de 18 secondes, partagée avec `SearchWorker` puis
l'hydratation et la sérialisation. Admission au plus 1 s, encodage au plus 3 s,
lexical/ANN ensemble au plus 10 s, hydratation au plus 2 s, toujours plafonnés par
le reste de l'échéance globale. Chaque instruction SQL reçoit le budget résiduel.
Un dépassement renvoie 504 sans ouvrir un second budget. Le timeout SSR reste 20 s.

Les traitements bloquants quittent l'event loop. L'annulation HTTP est transmise
au budget ; le moniteur psycopg2 annule une instruction active et la transaction
est annulée/fermée. Un encodage tardif garde sa place jusqu'à sa fin, même après
une réponse d'erreur ou la déconnexion du client. Les résultats tardifs sont ignorés.

Les pages de curseur ne réexécutent aucun classement. L'API revalide leur contenu
par une lecture applicative en lot, reconstruit l'ordre puis sérialise des extraits
bornés. Le cache LRU conserve uniquement références, empreintes et versions :
10 minutes absolues, 256 entrées, 16 Mio de charge utile JSON, hors overhead Python.
Expiration/éviction/redémarrage : 410 explicite, sans recalcul automatique.

Le profil initial reste profondeur 50/sortie top 50, injecté par `SearchRecipe`.
La taille des pages est indépendante (maximum 20). Une extension future à plusieurs
centaines ou 1789 résultats demandera des mesures et l'adaptation des bornes des
lecteurs existants, pas une nouvelle architecture d'API ou de curseurs.

## Vérifications locales

Tests backend, sur les bases isolées déjà migrées uniquement :

```bash
TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
  .venv/bin/pytest tests -q
```

Les fixtures d'écriture refusent les bases dont le nom ne se termine pas par
`_test`. La configuration GPU réelle est isolée des tests ; les tests du lifespan
injectent leur backend. Les corpus de travail ne servent jamais de fixtures.

Export et contrôle du contrat, hors réseau et sans lifespan :

```bash
.venv/bin/python scripts/export_openapi.py --check
pnpm --dir frontend contract:types:check
pnpm --dir frontend typecheck
```

Smoke test réel borné, avec la configuration locale et sans `TEST_DATABASE_URL` :

```bash
.cache/search-api-venv/bin/python scripts/smoke_hybrid_api.py
```

Il utilise les routes HTTP via TestClient/ASGI avec le véritable lifespan,
PostgreSQL et BGE-M3. Il vérifie la consultation documentaire pendant le chargement,
deux nouvelles recherches, une page suivante, le retour à la première, le compteur
d'appels H1, la réutilisation du modèle et une contribution contenant la réponse.
Il ne lance ni serveur permanent, ni benchmark lourd, ni écriture SQL. La sortie
contient seulement des métriques/statuts/effectifs, pas les textes ou identifiants
de réponses citoyennes. Les temps HTTP sont ceux du parcours ASGI local, pas une
mesure réseau entre deux machines ni du rendu React SSR.

Les logs `hybrid_search_metrics` séparent vérification, encodage, lexical, vectoriel,
fusion, hydratation et total. Les pages de cache n'ont aucune durée d'encodage/SQL
de classement, car ces étapes n'ont pas lieu. Les journaux d'accès du nouvel
endpoint masquent les paramètres de recherche et les curseurs.

## Frontend et recette navigateur SEARCH-005

Dans un autre terminal, depuis le dépôt :

```bash
pnpm --dir frontend build:offline
API_BASE_URL=http://127.0.0.1:8000 HOST=127.0.0.1 PORT=3000 pnpm --dir frontend start
```

FastAPI doit être démarré selon les instructions ci-dessus, avec son environnement
`search` et sa configuration locale. Ouvrir `http://127.0.0.1:3000/recherche`.
Une seule API générale subsiste : `/api/v1/search`. Les anciennes routes réponses
et catalogue ont été supprimées dans SEARCH-005. Aucun onglet ni secours historique.
La première recherche stabilise son URL avec `first_cursor` ; les dix minutes
commencent à la création du classement et ne sont pas prolongées par la navigation.

Recette automatisée réelle, après le build normal et avec Chromium Playwright
installé dans le frontend :

```bash
.cache/search-api-venv/bin/python scripts/smoke_search_browser.py
```

Ce script démarre ses propres instances temporaires FastAPI `127.0.0.1:8015` et SSR
`127.0.0.1:4185`, puis les arrête. Ces ports doivent être libres. Il utilise la
configuration ignorée existante, BGE-M3, le rôle lecteur et les deux bases réelles.
Il effectue quatre classements au plus : soumission et relance explicite après
expiration, une fois avec JavaScript et une fois sans. Il compte les appels H1
pour vérifier l'absence de recalcul pendant retour, pagination et rechargement.
Les ancres sont vérifiées par leur position réelle dans le navigateur.

Pour tester l'expiration sans attendre dix minutes, le processus de recette avance
l'horloge injectable du cache de 601 secondes ; le chemin normal répond alors 410.
Pour vérifier l'état vide, il injecte temporairement un `Ranking` vide dans son
instance de test : une requête rare n'est pas une preuve d'absence de voisins ANN.
Ce cas est explicitement indiqué dans la sortie. Il n'existe aucun endpoint de
contrôle ni paramètre de simulation dans l'application. Aucun corpus n'est modifié.
La sortie contient durées et statuts, sans textes citoyens ni secrets ; la capture
locale `/tmp/search-005-desktop.png` reste hors Git.

Les tests synthétiques complets restent `pnpm --dir frontend test:e2e`, avec états
vide, sources retirées, erreurs, mobile, clavier et zoom 200 %. Les vérifications
OpenAPI précédentes restent applicables après la suppression des anciennes routes.
