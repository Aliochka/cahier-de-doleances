# Laboratoire multicorpus — phase 3

Voie expérimentale distincte de H1 et des routes publiques. Aucun import à l’initialisation de l’application, migration, index nouveau, serveur distant ou droit PostgreSQL supplémentaire. Le laboratoire écoute uniquement sur **127.0.0.1:1792**.

## Démarrer sur les bases locales vérifiées

Depuis la racine du dépôt, avec l’environnement `.venv` existant :

```sh
.venv/bin/python -m multicorpus.lab serve \
  --gdn-env rag/search-reader.env \
  --hydration-url 'postgresql+psycopg2:///cahier_doleances_local?host=/var/run/postgresql' \
  --identities private/search/phase3/identities.json \
  --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487' \
  --expected-data-directory /tmp/documentary-phase1-45FiOt/data \
  --expected-system-id 7705356223649726476 \
  --port 1792
```

Ouvrir **http://127.0.0.1:1792/**. Arrêter par Ctrl-C. Aucun démarrage automatique ni montage dans FastAPI/React. Le laboratoire 1789 de phase 2 reste indépendant, sur le port 1791 si lancé.

Ces paramètres désignent cette machine, pas une configuration transportable à accepter sans vérification. Le fichier `private/search/phase3/identities.json` est local et ignoré par Git. Il contient les identités **pré-vérifiées** suivantes, sans secret :

```json
{
  "source": {"cluster_id":"7697259424657850634","database_oid":16385,"database_name":"cahier_doleances_local","schema_revision":"forms_statistics_v1"},
  "target": {"cluster_id":"7697259424657850634","database_oid":2106636,"database_name":"cahier_rag","schema_revision":null}
}
```

S’il manque, le créer avec ces valeurs uniquement sur cet environnement déjà identifié ; sur une autre machine, faire constater les vraies identités locales avant de fournir le fichier. Si le cluster documentaire sous `/tmp` disparaît, restaurer/reconstruire selon [le guide de phase 2](../documentary/PHASE2.md), puis utiliser sa véritable identité. Aucun repli vers une URL applicative ou de production n’existe.

Le lecteur GDN accepte uniquement les deux bases locales connues, rôle existant `cahier_search_reader`, adresses loopback numériques, port 5432, sans paramètres de redirection. Il vérifie les identités physiques attendues, le manifeste, la révision `rag_0007`, les statistiques figées et les index GIN/HNSW existants. Les connexions du laboratoire sont non persistantes (`NullPool`) pour respecter la limite existante de quatre connexions du rôle. Le rôle du lecteur reste non propriétaire et limité à SELECT. Les permissions de ce rôle n’incluent pas la lecture des réponses sources : l’hydratation utilise donc explicitement le socket applicatif local, avec la même identité source contrôlée et des transactions READ ONLY. Aucun GRANT n’a été effectué.

## Utilisation

- `tous` par défaut ; `2019` et `1789` sélectionnent un adaptateur seulement pendant la requête.
- Lexical, vectoriel, hybride ou comparaison des trois branches ; profondeurs documentaires 50, 100, 200, **sortie finale limitée à 50**.
- Question réservée à `2019` seul. Volume, ordre et lieu/titre réservés à `1789` seul. Un filtre incompatible, y compris en mode `tous`, renvoie 422 au lieu d’être ignoré. Pour comparer sans restriction, vider ces champs.
- Recherche libre analysée par `pg_catalog.french` : union des termes, au plus 32 lexèmes / 512 caractères. Les guillemets, `-` et autres signes ne constituent pas une syntaxe avancée de phrases/exclusions dans cette recette. H1 conserve sa propre analyse inchangée.
- Les cartes distinguent les corpus, montrent les témoins et permettent la lecture locale des cahiers ou d’une réponse complète. Les références de contribution GDN sont fournies pour une future intégration ; le laboratoire ne développe pas une nouvelle navigation publique par contribution.
- Le bouton H1 lance un **calcul de référence séparé**, avec l’implémentation actuelle, profondeur 50. Il possède son propre encodage et son budget de référence ; le calcul multicorpus, lui, encode une seule fois. H1 expose ses unités historiques avant regroupement : comparer les réponses via `answer_id`, pas seulement les lignes.
- Une recherche active au plus ; les recherches simultanées supplémentaires reçoivent 409. Erreurs de validation 422, expiration 504, indisponibilité 503. Pas de file illimitée ni de résultats partiels silencieux.

## Recette commune

`MultiSearch` collecte N/DF des corpus sélectionnés et calcule une seule IDF. `GdnAdapter` lit `rag_tuning.statistics` / `term_statistics`, `DocumentaryAdapter` lit les statistiques de phase 2. Il ne recalcule aucune DF GDN. Les filtres ne changent pas la population statistique de référence.

Score d’unité : `0,5 × couverture IDF + 0,3 × couverture simple + 0,2 × fréquence`. GDN : `fréquence = ts_rank(texte, requête, 32)`. Documentaire : fréquence `0,75 × ts_rank(texte) + 0,25 × ts_rank(métadonnées)`. Un terme apparié dans les deux champs ne compte qu’une fois dans la couverture. Les métadonnées restent une seule représentation par document.

Le meilleur score d’unité détermine le score de réponse/cahier. Le GDN calcule son maximum par `answer_id` **sur toutes les unités lexicalement correspondantes avant LIMIT** (DISTINCT ON avec départage par ID). Le documentaire réutilise le regroupement de phase 2 sur sa petite population. Aucun préfiltrage lexical approximatif.

Le vecteur de requête BGE-M3 commun est calculé une fois, CPU float32, avec révision/snapshot validés identiques aux représentations stockées. Les vecteurs existants GDN sont contextualisés par la question ; ceux de 1789 portent uniquement sur le passage. Ils ont été produits en bfloat16 puis normalisés/stockés float32 ; cette différence de préparation demeure et doit être jugée, pas corrigée silencieusement.

GDN : paramètres HNSW H1 ef1000, parcours strict, 20 000 tuples et multiplicateur mémoire 1 ; 400 segments au départ, augmentation jusqu’à D réponses ou limite/plafond/budget. Plafond de segments 50 000 ; le rappel reste ANN. Une petite question utilise la protection exacte existante (au plus 5 000 unités). Documentaire : toutes les distances admissibles sont calculées exactement. Les traces distinguent segments demandés/lus, documents retenus et limitation ANN éventuelle.

Chaque adaptateur propose ses D meilleurs documents ; l’union est triée par **score commun**, puis tronquée à D et reçoit des rangs globaux. Ce D local est une profondeur de candidats, pas un quota d’affichage. La RRF `Σ 1/(60+rang_global)` ne s’applique qu’une fois aux deux listes globales. Départage par clé stable `corpus:document_id`, identifiants traités comme chaînes, ordre lexicographique. Aucun score RRF local n’est fusionné.

Chaque branche conserve un témoin. Le plus fort rang global choisit le témoin affiché, priorité lexicale en cas d’égalité ; si les témoins sont identiques, origine `both`. Les correspondances uniquement documentaires sont identifiées. Les offsets Unicode sont appliqués sur le serveur, et les textes ne sont ni corrigés ni résumés.

## Contrats et extensions

Les adaptateurs exposent `identity`, `parse`, `statistics`, `lexical`, `vector`, `hydrate` et `capabilities`. Un candidat porte `key`, `corpus`, `document_id`, `unit_id`, score, branche et positions/segment éventuels. L’ID documentaire GDN est une réponse (`answer_id`), jamais une contribution. La clé historique est l’identifiant stable du cahier. Les résultats conservent les témoins des deux branches, avertissements, références, rangs et identités de génération/publication au niveau de l’instantané retourné.

`DocumentaryAdapter` accepte un scope corpus/release et son validateur explicite : un futur corpus documentaire peut réutiliser ses requêtes et regroupements. Le validateur 1789 reste volontairement attaché à sa collection et à son éditorial ; une autre release ne peut pas l’utiliser implicitement. Il faudra fournir sa politique et vérifier ses métadonnées/recettes, sans créer de modèle universel de questionnaires. Les sélecteurs du laboratoire ne proposent que les deux corpus autorisés par cette mission.

Aucun cache de curseur public ni pagination exhaustive : fenêtre bornée uniquement. Pas d’abstention vectorielle calibrée. Tout instantané d’essai conserve les identités et le caractère laboratoire ; il ne constitue pas une publication. Le GDN local vérifié n’est pas assimilé à une autorisation de déploiement.

## Tests et mesures

```sh
DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin .venv/bin/pytest \
  tests/test_multicorpus.py tests/test_documentary.py tests/test_documentary_search.py \
  tests/test_hybrid_search.py tests/test_search_packaging.py -q
node multicorpus/smoke.cjs
```

Les écritures des tests ont lieu exclusivement dans des clusters temporaires nouvellement créés ; jamais dans les deux bases de travail. Les vecteurs synthétiques des tests ne servent pas de mesures représentatives.

Remplacer `serve` dans la commande complète par `benchmark` pour les comparaisons, matrice modes/corpus/profondeurs, filtres, plans et concurrence ; sortie privée par défaut `private/search/phase3/results.json`. `--resume` reprend explicitement les cases déjà enregistrées de cette recette ; conserver des fichiers séparés si les sources/recettes changent. `search --query 'Gabelle' --corpus tous --mode compare --depth 100` fournit le JSON du moteur. `verify` vérifie les deux identités après chargement du modèle.

Budget conservé : 18 s globales, encodage 3 s, statistiques/SQL des deux corpus **ensemble 10 s**, hydratation 2 s. Les connexions sont enregistrées auprès du moniteur d’annulation existant. Les erreurs ne relancent pas une recherche avec un budget neuf. Le regroupement GDN est inclus dans la mesure SQL et identifiable dans EXPLAIN ; le regroupement Python documentaire est mesuré séparément dans les diagnostics. Les temps moteur excluent HTTP, JSON et navigateur. Les observations ne constituent pas une validation humaine de pertinence. Voir le [rapport mesuré de phase 3](../1789/docs/rapport-phase3-recherche-multicorpus.md).
