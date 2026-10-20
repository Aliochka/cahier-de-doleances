# SEARCH-003 — Service de recherche hybride persistant

Le package [`search/service`](src/cahier_rag/search/service/) fournit le service
H1 réutilisable prévu par [SEARCH-002](../docs/architecture-search-002.md).
Son intégration FastAPI est réalisée dans [SEARCH-004](../docs/rapport-search-004.md).
React reste le chantier SEARCH-005. Le service décrit ici reste indépendant de
FastAPI ; le nouveau [contrat HTTP](../docs/api-search.md) appartient au backend.

## Recette et résultats

Référence initiale : lexical optimisé RAG-027 avec DF exactes figées,
`statistics=True`, sans préfiltrage approximatif ; BGE-M3 dense 1024 dimensions ;
HNSW ef1000, 400 segments candidats initiaux, `strict_order`, plafond de parcours
20 000 tuples et multiplicateur mémoire 1 ; RRF non pondérée k=60.

**La profondeur 50 et la sortie top 50 sont des valeurs initiales provisoires,
pas une limite structurelle du service.** Une `SearchRecipe` injectée sépare
`depth`, `result_limit`, `rrf_k` et la configuration ANN. Son empreinte inclut tous
ces paramètres. Par exemple, une expérience peut utiliser
`SearchRecipe(depth=80, result_limit=75, version="experience-80")` sans modifier
le service ou son contrat de résultats. Les lecteurs expérimentaux réutilisés
acceptent actuellement au plus 100 documents par branche ; étendre cette borne
nécessiterait d'adapter ces lecteurs, sans changer l'architecture du service.
Aucune profondeur par défaut n'est augmentée par SEARCH-003.

`Ranking` contient une génération de corpus, une recette versionnée et son hash,
des durées par étape et un tuple immuable de `Hit`. Chaque hit conserve une
`TextUnit` immuable (IDs réponse/question/contribution/formulaire, type, indice
d'unité, texte et empreinte), son score RRF, ses rangs lexical/vectoriel et le
segment vectoriel gagnant éventuel. `document_id`, `representation_id` et les
identifiants historiques restent distincts.

La branche vectorielle déduplique les segments par document, conformément à H1.
Deux documents « Autre » issus de la même réponse restent des documents distincts
dans ce contrat interne : le regroupement en cartes de réponses et la projection
publique relèvent de SEARCH-004. Ce contrat n'est pas à sérialiser tel quel
pour le navigateur ; les BIGINT publics devront être des chaînes, comme le permet
déjà `TextUnit.to_dict()`.

Le moteur ne propose ni génération, ni contextes RAG assemblés, ni reranking,
ni fallback lexical ou historique. Une branche exécutée mais vide est admise ;
une branche défaillante fait échouer la recherche. `question_id` est explicitement
refusé jusqu'au chantier Questions ; aucun filtre n'est ignoré silencieusement.
Les limites de rappel ANN documentées dans RAG-027 restent applicables.

## Lecture seule et rôles locaux

Les deux URL sont obligatoires et explicites, chargées par `load_settings()`.
Aucune connexion à `DATABASE_URL` et aucun fichier `.env` implicite. Le service
possède deux pools SQLAlchemy distincts (taille 2, sans overflow, attente 1 s).
Ils imposent READ ONLY avant `begin`, avec valeurs de session protectrices.
Leurs connexions sont fermées avant encodage, attente ou fusion.

`ReadGuard` conserve les contrôles d'identité physique/distinction des bases et
le refus d'une destination contenant le schéma applicatif. `ReadStore` n'expose
que la lecture de manifeste, sans méthodes d'import ou d'écriture. Les gardes,
fabriques et opérations de maintenance existants ne sont pas modifiés.

Au démarrage et avant chaque recherche : contrôle du rôle non écrivain/non
propriétaire, de l'absence d'appartenance à d'autres rôles, de la révision RAG,
de l'espace `full` complet/vérifié, de la recette BGE/tokenisation, de la source
physique déclarée dans le manifeste, des statistiques et des index valides/prêts.
Une génération différente de celle du démarrage est refusée : redémarrage
explicite après publication d'un corpus. Le corpus doit rester immuable pendant
le fonctionnement ; aucun contrôle par requête ne constitue une transaction
distribuée entre les deux bases.

Le rôle propriétaire `ro` est volontairement refusé. Le script local
[`sql/search-reader.sql`](sql/search-reader.sql) crée un login non privilégié,
limité à la lecture des tables nécessaires dans `cahier_rag` et de la révision
applicative dans `cahier_doleances_local`. Il donne le droit ciblé d'inspection
d'identité et configure seulement les valeurs par défaut de ce rôle.
Il ne change aucune table, donnée, index, migration ou configuration serveur.
L'hydratation publique future utilisera le pool applicatif, pas ce login.

Provisionnement par l'administrateur local :

```bash
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -f - < /home/ro/cahier-de-doleances/rag/sql/search-reader.sql
sudo -u postgres psql -X -c '\password cahier_search_reader'
```

La redirection est effectuée par l'utilisateur courant : le compte système
`postgres` n'a pas besoin de traverser le répertoire personnel pour lire le fichier.

Conserver ensuite les URL dans `rag/search-reader.env` (ignoré par Git, droits
0600), avec un mot de passe URL-encodé, sans le recopier dans les logs :

```dotenv
RAG_SOURCE_DATABASE_URL=postgresql://cahier_search_reader:MOT_DE_PASSE_ENCODE@127.0.0.1:5432/cahier_doleances_local
RAG_DATABASE_URL=postgresql://cahier_search_reader:MOT_DE_PASSE_ENCODE@127.0.0.1:5432/cahier_rag
```

Le script n'accorde au lecteur ni création, ni écriture, ni appartenance à un rôle écrivain.
Sur les bases locales, le schéma `public` accordait CREATE à PUBLIC : le script
retire ce droit collectif tout en l'accordant explicitement au propriétaire de
chaque base, afin de conserver ses capacités de migration. Cela corrige un droit
hérité qu'un REVOKE ciblant seulement le lecteur ne pourrait pas supprimer.
Les éventuels droits excessifs hérités de PUBLIC sont détectés au démarrage ;
ne pas désactiver ce contrôle pour démarrer. Aucun privilège n'est accordé par le
service lui-même. Le script est réservé aux noms de bases locales ci-dessus,
sans intervention sur Wallace.

## Modèle et cycle de vie

Réutiliser l'extra `embeddings` et son verrou existant ; ne pas synchroniser le
venv léger utilisé pour les annotations. Le venv GPU local déjà préparé est
`rag/.cache/embeddings-venv`. Si une installation est nécessaire :

```bash
cd rag
UV_PROJECT_ENVIRONMENT=.cache/embeddings-venv uv sync --locked --extra embeddings --dev
```

`create_service(settings, models, device=..., precision=...)` ne connecte ni ne
charge le modèle. `start()` vérifie les bases, charge le snapshot BGE-M3 immuable,
effectue une inférence de préparation, puis déclare le moteur prêt. Répéter
`start()` sur un service déjà prêt ne recharge pas le modèle. `retrieve()` utilise
la même instance. `close()` attend le travail réel, libère le modèle et les pools.

Les poids et le tokenizer sont vérifiés localement ; réseau interdit, aucun code
distant exécuté, aucun téléchargement par requête. Aucun `selection.json`, fichier
de campagne, Qwen, contexte génératif ou reranker n'est importé. Importer le service
ne charge même pas torch/transformers.

Hal9000 peut utiliser CUDA/bfloat16 explicitement. CPU/float32 est également
supporté par le backend existant, sans fallback automatique en cas de panne GPU.
La distribution torch CUDA actuelle devra être adaptée pour une installation
CPU dédiée ; aucune adaptation de Wallace n'est effectuée ici.

Exécution de vérification locale, au plus trois recherches, sans exposer les textes
ou les requêtes dans la sortie :

```bash
rag/.cache/embeddings-venv/bin/python -m cahier_rag.search.service \
  --env-file rag/search-reader.env --models rag/models \
  --device cuda --precision bfloat16 \
  --query 'Comment améliorer les transports publics ?' \
  --query 'Comment réduire les dépenses contraintes ?'
```

Cette commande appelle une seule fois `start()` puis plusieurs `retrieve()` et
affiche les effectifs et durées ; elle ne constitue pas un benchmark de pertinence.

## Utilisation asynchrone et annulation

```python
from cahier_rag.config import load_settings
from cahier_rag.search.service import SearchWorker, create_service

service = create_service(
    load_settings(env_file="rag/search-reader.env"), "rag/models",
    device="cuda", precision="bfloat16",
)
worker = SearchWorker(service)
# Dans le futur lifespan :
await worker.start()
# Hors création du modèle et sans réserver de session applicative :
ranking = await worker.retrieve("Comment améliorer les transports publics ?")
# Au shutdown :
await worker.close()
```

L'exécuteur possède un thread et admet un calcul actif plus deux en attente.
Admission au plus 1 s, encodage au plus 3 s, ensemble lexical/ANN au plus 10 s,
le tout sous échéance absolue de 18 s par défaut. Une `Budget` peut être injectée
dans l'interface synchrone et, depuis SEARCH-004, dans `SearchWorker.retrieve()` ;
l'API partage ainsi son échéance avec l'hydratation et la sérialisation.
Les limites s'appliquent aux deux branches réunies,
pas à chaque répétition de la boucle ANN. Chaque instruction SQL reçoit le budget
résiduel, même après les `SET LOCAL` de 30 s des lecteurs historiques.

Un moniteur annule la connexion psycopg2 empruntée en cas d'expiration/annulation,
sans pouvoir annuler une connexion rendue au pool. Les contextes transactionnels
effectuent rollback et fermeture. Les exceptions sont typées et ne contiennent
ni URL ni texte citoyen : `InvalidQuery`, `SearchNotReady`, `SearchUnavailable`,
`SearchBusy`, `SearchTimeout(stage)` et `SearchCancelled`. La traduction HTTP
appartient à SEARCH-004.

Annuler l'attente asynchrone retire une tâche encore en file et signale le travail
actif. Une inférence en thread n'est pas tuée : le résultat tardif est ignoré et
la capacité reste occupée jusqu'à sa fin effective. Le shutdown attend lui aussi
la fin réelle du travail. Une interruption dure d'un encodeur bloqué nécessiterait
un processus supervisé ; elle n'est pas prétendue ici.

Une instance par processus : plusieurs workers du futur serveur dupliqueraient
le modèle. Le choix initial reste un processus local. Le cache et les curseurs
ne sont pas implémentés dans SEARCH-003.

## Validation SEARCH-003

Commandes reproductibles depuis la racine :

```bash
rag/.venv/bin/pytest rag/tests/unit -q
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
  rag/.venv/bin/pytest rag/tests/integration/test_search_service.py -q
rag/.venv/bin/ruff check rag/src/cahier_rag/search/service \
  rag/tests/unit/test_search_service.py rag/tests/integration/test_search_service.py
```

Les intégrations n'acceptent que des bases `_test` déjà migrées. Elles insèrent
des données synthétiques, valident puis nettoient seulement leur espace de test ;
elles refusent d'écraser un espace `full` déjà présent. Aucune migration n'est
lancée par les nouvelles fixtures. Les tests vérifient la correspondance à H1,
BIGINT, plusieurs segments/documents/réponses, READ ONLY réel, rollback après
timeout, refus du propriétaire, dérive des statistiques/génération et distinction
physique des deux bases.

Pour les tests fonctionnels de classement sur fixtures, le propriétaire de test
est utilisé sous READ ONLY et le seul contrôle de rôle est simulé : aucun
rôle n'est créé par les tests. Le refus réel du propriétaire est testé séparément.
Cela ne remplace pas le smoke test avec le login dédié sur les bases locales.

Vérification ponctuelle du vrai BGE-M3 le 20 octobre 2026, avec le venv existant,
sur RTX 5090 : chargement/vérification 4,90 s ; deux encodages 97,6 puis 9,9 ms ;
même instance de modèle, dimension 1024 et norme L2 voisine de 1. Pic mémoire CUDA
allouée 1 170 493 440 octets, réservée 1 178 599 424 octets ; pic RSS processus
4 334 264 Kio. Ces deux observations n'incluent pas le classement SQL et ne sont
ni une mesure sous concurrence ni un SLA.

Le login dédié a été provisionné par l'administrateur local, avec correction du
droit CREATE hérité de PUBLIC. Le fichier de connexion est ignoré par Git et
protégé en 0600. Aucun mot de passe n'est consigné dans ce document.

Le smoke test complet a ensuite réussi sur les deux bases locales et le corpus
réel, sous ce login : un chargement BGE-M3 (4,68 s, puis une inférence de
préparation), deux recherches successives dans la même instance, chacune avec
50 documents/50 réponses distinctes. Durées observées :

| Étape | Première recherche | Deuxième recherche |
|---|---:|---:|
| Vérification du corpus | 4,45 ms | 4,85 ms |
| Encodage chaud | 10,17 ms | 10,38 ms |
| Lexical optimisé | 2,587 s | 2,574 s |
| ANN et restauration documentaire | 0,262 s | 0,462 s |
| Fusion | 0,62 ms | 0,61 ms |
| Total hors chargement initial | **2,865 s** | **3,052 s** |

Ces temps incluent les contrôles et lectures du service, sans hydratation publique
ni HTTP/SSR. Deux observations ne permettent pas de déduire un P95 ou une capacité
sous concurrence. Aucun embedding ni index n'a été reconstruit ; aucune donnée
du corpus local n'a été modifiée. Les seules écritures de fixtures concernent
les bases `_test` et sont nettoyées après les tests.

Vérifications automatiques : 20 tests unitaires propres au service et cinq tests
d'intégration PostgreSQL réussis ; Ruff et formatage conformes. La suite unitaire
RAG a également été exécutée pendant l'implémentation : 532 réussites et trois
tests PyTorch ignorés dans le venv léger, avant l'ajout des trois derniers tests
de configuration/import/CLI, vérifiés ensuite dans la suite ciblée.
