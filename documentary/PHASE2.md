# Recherche historique locale — phase 2

Cette recherche utilise exclusivement les **1 224 cahiers candidats** de la release explicite `reference-documents-2-7cbcaea79991`. La population est de **10 748 passages admissibles** après exclusions Artois. Les 43 autres documents restent stockés mais ne participent ni aux statistiques, ni aux vecteurs, ni à la recherche ou au lecteur du laboratoire.

Le laboratoire n’est jamais monté dans FastAPI ou dans le frontend public. Il écoute uniquement sur `127.0.0.1`, contrôle Host/Origin, sert seulement ses fichiers statiques prévus et n’expose aucune commande d’écriture. Les journaux historiques privés ne sont pas lus ni servis. Les coordonnées de connexion sont fournies exclusivement en ligne de commande, avec les gardes physiques de phase 1.

## Préparer / reprendre

Préparer une base de phase 1 avec le [mode d’emploi](README.md), ou réutiliser la destination réellement vérifiée indiquée dans [le rapport de phase 2](../1789/docs/rapport-phase2-recherche-1789.md). Tous les exemples ci-dessous nécessitent les arguments explicites :

```text
--url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487'
--expected-data-directory /tmp/documentary-phase1-45FiOt/data
--expected-system-id 7705356223649726476
```

Ces valeurs désignent le cluster local de la réalisation ; elles ne sont pas un repli dans le code. Si `/tmp` a disparu, reconstruire une nouvelle destination sûre et utiliser sa véritable identité. Ne jamais remplacer ces arguments par une configuration de production.

1. `.venv/bin/python -m documentary.lab lexical ARGUMENTS_DESTINATION` prépare les champs et fréquences PostgreSQL. Aucun texte source n’est modifié.
2. `.venv/bin/python -m documentary.lab embed ARGUMENTS_DESTINATION --workers 3 --threads 4 --batch-size 16 --precision bfloat16` lance les trois travailleurs sur des parts disjointes. Pour une reprise ciblée, `--shard 0`, `--shard 1` ou `--shard 2` lance uniquement cette part ; conserver les autres paramètres de la recette.
3. `.venv/bin/python -m documentary.lab verify ARGUMENTS_DESTINATION` contrôle sources, projections, tranches, DF, vecteurs, normes et empreintes.
4. `.venv/bin/python -m documentary.lab serve ARGUMENTS_DESTINATION --port 1791` ouvre le laboratoire à **http://127.0.0.1:1791/**.

`ARGUMENTS_DESTINATION` est une notation documentaire, à remplacer par les trois arguments complets ci-dessus. Le CLI ne charge aucun `.env`.

Le chargement du modèle vérifie le snapshot BGE-M3 local et interdit le réseau. La version expérimentale CPU bfloat16 est propre à `documentary` ; le backend H1 n’est pas modifié. Chaque entrée est exactement le passage original. Les mécanismes existants contrôlent les tokens et refusent la troncature. Normalisation L2 avant stockage float32 `vector(1024)`.

Un lot validé est commité atomiquement avec ses hash. Une reprise n’encode que les unités sans vecteur ; la recette doit rester strictement identique, y compris précision, threads, batch et répartition. Les workers partagent le verrou de maintenance pour les écritures ; aucun verrou SQL n’est gardé pendant l’inférence. Un échec ne transforme pas une préparation partielle en préparation terminée. La permission publique reste false et le pointeur actif NULL, même quand les deux drapeaux de préparation sont true.

La commande phase 1 `verify` conserve son contrôle strict d’une base sans dérivés. Après préparation, utiliser **`documentary.lab verify`**, qui réutilise son contrôle source sans exiger des colonnes dérivées vides. La source et l’éditorial sont toujours comparés intégralement. Un rejeu éditorial explicite invalide les statistiques et la préparation, conserve les vecteurs encore réutilisables et efface les représentations des unités devenues inadmissibles ; il faut ensuite préparer/reprendre et vérifier avant de relancer le laboratoire. Aucune décision nouvelle n’est appliquée par la phase 2 livrée.

## Classement et limites

Lexical : `pg_catalog.french`, union virtuelle des lexèmes du passage et des métadonnées documentaires, DF sur les seules unités admissibles. Les métadonnées sont conservées/indexées **une seule fois par document** : titre de présentation, titre source dédupliqué, lieu littéral, contexte territorial spécifique et ordre explicite. Les citations bibliographiques génériques et avertissements sont exclus de ce champ.

Score d’une unité : `0,5 × couverture IDF + 0,3 × couverture des termes + 0,2 × (0,75 × ts_rank(texte) + 0,25 × ts_rank(métadonnées))`, avec normalisation `32`. Les couvertures comptent une seule fois un lexème rencontré dans les deux champs. Le français PostgreSQL fournit la tokenisation et les mots vides ; maximum 32 lexèmes et 512 caractères de requête. La boîte utilise une recherche libre en union de termes, pas une syntaxe de filtres/exclusions littérales ou une recherche de phrase exacte. Le lieu et l’ordre obligatoires se saisissent dans les filtres séparés. Les poids ne sont pas ajustés aux exemples.

Le maximum des scores d’unités donne le score du cahier. Le vectoriel calcule la distance de **toutes les unités admissibles**, puis garde le meilleur passage de chaque document. Les SQL ne limitent pas d’abord les passages. Le regroupement est réalisé en Python sur ces scores PostgreSQL, avant la limite documentaire : son coût est mesuré séparément du SQL/transfert des lignes. Aucun vecteur ni matrice complète n’est chargé dans Python pour le classement exact.

La RRF fusionne uniquement les deux listes de cahiers : constante 60, D=50/100/200, sortie D. Aucun vote additionnel pour les autres passages du document. Si les deux branches choisissent le même témoin, il est conservé ; sinon le meilleur rang de branche gagne, lexical en cas d’égalité. Les deux témoins restent disponibles dans les résultats techniques. Un témoin lexical sans match dans le texte est marqué `metadata` / `opening` et présenté comme une correspondance documentaire.

La branche vectorielle utilise volontairement seulement le texte : une requête de lieu ne doit pas être interprétée comme un filtre géographique. Les filtres documentaires, en revanche, restreignent les deux branches avant classement. L’origine littérale des lieux et les ordres déduits explicitement des titres ne constituent pas une géolocalisation ou une certification historique.

Le moteur accepte une recherche à la fois par instance d’encodeur ; un appel simultané reçoit une erreur d’admission explicite, sans file illimitée. Chaque SQL de recherche a un timeout de 15 secondes. La fenêtre et la longueur des requêtes sont bornées ; il n’existe ni pagination exhaustive ni serveur multi-utilisateur de production dans cette phase.

## Lecture et expérimentation

La page permet de choisir lexical, vectoriel, hybride ou comparaison, profondeur, volume, ordre et lieu/titre. Chaque carte expose son extrait, ses références et avertissements ; les détails montrent rangs, RRF, unité et offsets. Les liens ouvrent le texte intégral avec le témoin surligné. Les extraits de carte sont des fenêtres PostgreSQL `ts_headline` sans balises quand une requête lexicale est disponible, ou le début du passage ; les espaces sont resserrés uniquement pour cet affichage. Les offsets désignent toujours le passage canonique complet, intégralement surligné dans le lecteur. Aucun résumé n’est généré et les textes stockés restent inchangés.

Le lecteur peut montrer une unité exclue dans un cahier candidat et l’indique ; il ne la fait pas entrer dans les résultats. Il refuse les 43 documents hors population.

L’outil conserve les offsets Unicode côté serveur pour produire les fragments du lecteur ; il ne les applique pas à des indices JavaScript UTF-16. Les textes sont insérés par `textContent`, jamais interprétés comme HTML.

Le premier chargement du modèle est compris dans le temps d’encodage à froid applicatif. Les requêtes suivantes réutilisent ce modèle. Les titres des trois listes servent à comparer les classements ; ils ne sont pas une notation de pertinence.

## Évaluation reproductible

```sh
.venv/bin/python -m documentary.lab benchmark ARGUMENTS_DESTINATION --repeats 3
.venv/bin/python -m documentary.lab cold-benchmark ARGUMENTS_DESTINATION
DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin .venv/bin/pytest tests/test_documentary_search.py tests/test_documentary.py -q
node documentary/smoke.cjs
```

Le benchmark enregistre ses observations dans `1789/data/private/documentary/phase2-benchmark.json`, ignoré par Git. Les 20 requêtes de `evaluation.py` couvrent géographie, thèmes, combinaisons, termes fréquents, vocabulaire historique/moderne, OCR et zéro match lexical. Elles ne constituent pas une vérité terrain ; les jugements sont laissés à NULL.

Les mesures séparent encodage, SQL lexical, SQL vectoriel exact, regroupement, fusion, hydratation et total. Le SQL inclut le transfert des scores vers Python ; le total inclut aussi les gardes. Les plans `EXPLAIN ANALYZE BUFFERS` portent sur les vraies instructions du moteur. Les percentiles de petits échantillons, la première requête applicative et les conditions de cache sont décrits sans assimiler un cache OS chaud à un disque froid.

Les tests PostgreSQL utilisent des vecteurs **synthétiques dans de nouvelles bases temporaires**, jamais dans la base réelle de laboratoire. Le calcul réel et ses contrôles de reproduction font l’objet du rapport. Les tests navigateur utilisent le Playwright déjà présent dans le dépôt ; ils n’installent aucun composant du site public.

Le second benchmark crée une copie temporaire de la base dans un nouveau cluster privé, puis redémarre uniquement cette copie avant chaque essai. Il mesure ainsi un cache partagé PostgreSQL froid avec modèle chaud ; le cache disque du système reste non contrôlé. Il ne redémarre pas la base de travail et n’écrit pas dans les sources. Ses neuf observations (une par mode/profondeur) restent un petit échantillon.
