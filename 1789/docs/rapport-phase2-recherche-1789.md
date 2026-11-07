# Phase 2 — Recherche autonome sur les cahiers de 1789

Date : 7 novembre 2026. Périmètre : laboratoire local, aucun déploiement ni publication. La phase 3 multicorpus n’est pas implémentée.

## Réalisation et accès

Le moteur historique est indépendant du moteur H1 et de l’application publique. Il utilise la base locale de phase 1, `documentary_1789_test`, socket `/tmp/documentary-phase1-45FiOt/socket`, port de socket 55487, répertoire `/tmp/documentary-phase1-45FiOt/data`, identifiant système attendu `7705356223649726476`.

Accès local : **http://127.0.0.1:1791/**. Commande de lancement depuis la racine du dépôt :

```sh
.venv/bin/python -m documentary.lab serve --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/documentary-phase1-45FiOt/socket&port=55487' --expected-data-directory /tmp/documentary-phase1-45FiOt/data --expected-system-id 7705356223649726476 --port 1791
```

Si le cluster sous `/tmp` n’existe plus, il faut le reconstruire ou restaurer la sauvegarde locale, puis utiliser sa véritable identité. Aucun repli vers une configuration de production n’existe. Le [mode d’emploi détaillé](../../documentary/PHASE2.md) décrit préparation, reprise, contrôles et benchmarks.

| Composant | Fonction |
|---|---|
| [representations.py](../../documentary/representations.py) | Métadonnées autorisées, indexation française, DF, encodage BGE-M3 reprenable, contrôle des représentations |
| [search.py](../../documentary/search.py) | Branches documentaires, exact vectoriel, RRF 60, témoins, hydratation et mesures |
| [lab.py](../../documentary/lab.py), [interface](../../documentary/static/lab.html) | CLI explicite, serveur loopback, comparaison des classements, filtres et lecteur intégral |
| [evaluation.py](../../documentary/evaluation.py) | 20 requêtes exploratoires et benchmark à chaud / premier usage applicatif |
| [cold_benchmark.py](../../documentary/cold_benchmark.py) | Essais après redémarrage d’une copie PostgreSQL jetable, sans arrêter la base de travail |
| [tests](../../tests/test_documentary_search.py), [smoke navigateur](../../documentary/smoke.cjs) | Invariants de recherche, sécurité locale, contrôle de lecture et interface |
| [storage.py](../../documentary/storage.py) | Contrôle source réutilisable en présence de dérivés ; invalidation de la préparation après rejeu éditorial |

**Aucune migration supplémentaire n’est nécessaire.** Les colonnes et index prévus par `doc_0001` suffisent. Aucun HNSW documentaire n’a été construit.

## Périmètre, recettes et traçabilité

Population : 1 224 cahiers candidats, 10 750 passages sources, **10 748 passages individuellement admissibles**. Les 43 autres documents, leurs 641 passages et les 38 notices sans texte restent conservés, sans participer à cette recherche.

Le mode laboratoire sélectionne explicitement la release vérifiée, les documents `candidate=true` et les unités `searchable=true`. Il ne change pas les permissions publiques. `publication_authorized=false`, `active_release_id=NULL` et toutes les autorisations publiques des documents restent false. Le passage au statut public `ready` n’est pas utilisé pour contourner ces contrôles : la release reste `verified`, avec des drapeaux de préparation distincts.

Lexical : recette `historical-lexical-1`, configuration `pg_catalog.french`, coefficients 0,5 / 0,3 / 0,2 et β=0,25. Les titres de présentation/source, lieu littéral, contexte territorial spécifique et ordre explicite sont indexés une fois par cahier ; les citations génériques et avertissements ne sont pas ajoutés au champ. Les DF sont calculées sur l’union virtuelle des lexèmes texte + métadonnées pour chaque passage admissible.

Statistiques préparées : **90 943 lexèmes distincts**, **1 788 101 occurrences passage/lexème distinct** cumulées, population **10 748**. Cette somme de DF n’est ni un nombre de mots ni un nombre de revendications. Les mots et variantes OCR restent dans les statistiques ; ils ne sont pas corrigés.

Vectoriel : modèle `BAAI/bge-m3`, révision `5617a9f61b028005a4858fdac845db406aefb181`, snapshot vérifié `fe2f29e9b4699cfeb8ee4d9524c1e99df203cb4f144dbe4b463e28e65e3d1f6d`. Pooling CLS, normalisation L2, stockage float32 1024 dimensions. Entrée : **texte exact du passage, sans métadonnées ni préfixe**. Torch `2.10.0+cpu`, Transformers `4.57.6`, calcul CPU bfloat16 explicite, 3 travailleurs de 4 threads, lots de 16, graine 42, ordre stable par nombre de tokens/ID puis répartition disjointe. Le backend de production H1 est inchangé.

Le processeur disponible est un AMD Ryzen 9 7950X, 32 processeurs logiques, environ 124 Gio de RAM système. Aucun GPU utilisable n’a été détecté. Les poids sont chargés hors ligne ; aucun texte ou requête n’est transmis à un service externe.

Chaque vecteur est lié aux empreintes source existantes et à une recette de release explicite ; son SHA-256 float32 est vérifié par lecture binaire pgvector. Une reprise refuse une recette différente et saute les unités déjà représentées. Les lots committés sont conservés après interruption ; une préparation partielle ne donne pas accès au moteur vectoriel.

## Classement et consultation

Le SQL lexical calcule la formule d’unité avec couverture sur les deux champs. Le SQL vectoriel calcule exactement les distances de toutes les unités du périmètre filtré. Le regroupement Python garde **le meilleur passage par cahier avant toute limite documentaire**. La RRF reçoit donc des classements de cahiers et ne cumule pas les votes de centaines de passages.

Les profondeurs 50, 100 et 200 sont disponibles. Les filtres volume, ordre explicite et lieu/titre s’appliquent aux deux branches avant classement. Les statistiques restent celles de la population de laboratoire entière, sans recalcul de DF par sous-filtre.

Le témoin commun est conservé quand les deux branches désignent la même unité ; sinon le meilleur rang de branche gagne, lexical en cas d’égalité. Les deux témoins restent dans les traces. Les correspondances uniquement documentaires sont signalées comme telles, avec une ouverture admissible, sans prétendre que son texte contient les termes recherchés.

La carte montre une fenêtre textuelle PostgreSQL sans balises, ou le début du passage ; ses espaces sont resserrés uniquement pour l’affichage. Les positions indiquées sont celles du **passage canonique complet**, intégralement surligné dans le lecteur. Aucun résumé n’est généré. Le texte intégral, les notes et avertissements restent consultables ; les passages exclus peuvent être lus mais jamais choisis comme candidats ou témoins de recherche.

Le laboratoire compare les trois listes et expose rangs, RRF, origine du témoin et temps. Une instance accepte une recherche à la fois ; les appels simultanés excédentaires sont rejetés explicitement, sans file illimitée. Il ne s’agit pas d’un serveur public multi-utilisateur.

## Contrôles d’intégrité et résultats expérimentaux

Le calcul et les contrôles sont terminés : **10 748 vecteurs réels**, 1 267 documents et 11 391 passages sources comparés intégralement sans divergence, aucune représentation des unités exclues ou des 43 documents hors population. Les fréquences et les représentations lexicales des textes et métadonnées ont été recalculées indépendamment pour contrôle. Les neuf combinaisons mode/profondeur ont été essayées. Les exemples ne sont pas une vérité terrain ; aucun réglage n’est automatiquement modifié pour les faire réussir.

Un contrôle de reproduction borné a déjà réencodé les trois premiers lots selon leur répartition d’origine : **48 vecteurs sur 48 ont une empreinte identique bit à bit**, dans cet environnement et avec cette recette. Cela ne prouve pas une identité numérique entre architectures matérielles différentes.

Les fichiers détaillés sont locaux et ignorés par Git sous `1789/data/private/documentary/` : `phase2-reproduction.json`, `phase2-benchmark.json`, `phase2-cold-postgres.json`. Les jugements de pertinence du benchmark sont laissés à NULL.

## Difficultés et réserves de pertinence

- La recherche libre française peut confondre un nom propre et une forme ancienne : `Agen` et `agens` produisent le même lexème, contrairement à `agent`. Un cahier de Montfermeil mentionnant les « agens » peut donc remonter dans « Agen agriculture ». Le filtre documentaire littéral permet de restreindre le lieu. Ce comportement observé est conservé pour l’évaluation, sans réglage opportuniste.
- Le vectoriel ne reçoit aucun titre/lieu : il ne remplace pas un filtre géographique. L’hybride doit être jugé sur ce compromis, et non sur la proportion de cahiers d’une ville affichée.
- Le corpus contient de longs cahiers : Nemours possède 212 passages admissibles, Langres 108. Le maximum documentaire évite leur répétition dans les listes mais ne supprime pas leur plus grand nombre d’occasions d’obtenir un score élevé.
- Une requête sans match lexical peut recevoir des voisins vectoriels et donc des résultats hybrides. La présence d’un résultat n’est pas une certification de pertinence ; aucun seuil d’abstention n’a été calibré sur une vérité terrain.
- Les lieux sont des métadonnées littérales, parfois territoriales, sans géocodage ni certification nouvelle. Les exclusions d’Artois ne corrigent pas les autres erreurs OCR du corpus.

Avant la phase 3, examiner humainement les résultats géographiques, thématiques et combinés, les cas sans signal lexical et les extraits choisis. Les coefficients initiaux, l’analyseur, l’éventuelle distinction des noms propres et la règle du témoin restent des hypothèses à évaluer sur un jeu plus large.

## Préservation de l’existant

Aucune modification sous `app/`, `frontend/` ou `rag/`, aucune modification de `rag_full`, d’index HNSW, de recette H1 ou d’embeddings GDN. Les écritures utilisent exclusivement le garde local et le schéma documentaire de la base isolée. Les transcriptions Stanford, la collection de référence, son pointeur et les décisions acquises restent inchangés. Les permissions de publication restent désactivées.

<!-- measured-results -->
## Bilan final mesuré

Reprise réelle : **0 vecteur recalculé, 10748 réutilisés**. Les dernières parts ont terminé leur calcul en environ 1 826 secondes (30,4 minutes), hors initialisation ; ce temps CPU a été observé pendant les travaux et tests, pas dans un benchmark d’encodage isolé.

La release est `verified`, avec `statistics_ready=true` et `representations_ready=true`, mais `publication_authorized=false`, pointeur actif NULL et zéro document publiquement autorisé. Artois possède exactement deux unités admissibles ; Aunay-la-Côte en possède huit. Les exclusions et le titre validé n’ont pas changé.

### Latences à chaud

81 recherches : trois requêtes (`Agen agriculture`, `roi`, terme inexistant), trois répétitions, trois modes et trois profondeurs. Neuf observations par ligne ; les percentiles élevés de ce petit échantillon se rapprochent du maximum. Temps en millisecondes, **moteur hors transport HTTP, sérialisation JSON et rendu du navigateur**.

| Mode | D | Total p50 | Total p95 | Encodage p50 | Lexical p50 | Exact p50 | Regroupement p50 | Hydratation p50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lexical | 50 | 85.7 | 108.4 | 0.0 | 34.2 | 0.0 | 1.1 | 23.4 |
| vector | 50 | 118.0 | 222.2 | 24.4 | 0.0 | 44.4 | 11.0 | 11.4 |
| hybrid | 50 | 166.8 | 274.7 | 24.3 | 35.7 | 41.7 | 11.0 | 24.6 |
| lexical | 100 | 103.2 | 139.2 | 0.0 | 32.7 | 0.0 | 1.1 | 41.3 |
| vector | 100 | 127.2 | 235.8 | 24.6 | 0.0 | 45.0 | 11.4 | 20.4 |
| hybrid | 100 | 183.8 | 310.2 | 24.8 | 35.4 | 42.8 | 11.1 | 44.4 |
| lexical | 200 | 150.2 | 165.7 | 0.0 | 35.0 | 0.0 | 1.1 | 77.8 |
| vector | 200 | 146.5 | 244.1 | 25.8 | 0.0 | 47.5 | 11.9 | 34.2 |
| hybrid | 200 | 234.7 | 355.5 | 24.4 | 36.5 | 44.8 | 12.2 | 81.3 |

La fusion RRF p95 reste entre 0.40 et 1.69 ms. Premier usage applicatif : **4.285 s**, dont **4.136 s** d’encodage/chargement du modèle. Le cache OS n’a pas été vidé : il s’agit d’un modèle froid dans un processus neuf, pas d’une mesure de disque froid.

### Cache PostgreSQL froid et effet des statistiques du planificateur

Une copie jetable a été restaurée puis redémarrée avant chaque recherche. Le modèle restait chargé et le cache OS n’a pas été purgé. Une seule observation par mode/profondeur, sur `Agen agriculture` :

| D | Lexical total | Vectoriel total | Hybride total |
|---|---:|---:|---:|
| 50 | 168.4 ms | 189.8 ms | 228.1 ms |
| 100 | 175.8 ms | 277.3 ms | 247.4 ms |
| 200 | 211.7 ms | 201.8 ms | 398.8 ms |

Le premier essai de copie restaurée, **sans ANALYZE**, donnait environ 2,6–2,7 s en vectoriel et 4,5 s en hybride. Les plans enregistraient des **Nested Loop** mal estimés ; le plan lexical observé prenait environ 2,3 s et le vectoriel 1,0 s, sans JIT. `pg_dump` ne transfère pas les statistiques du planificateur. Après ANALYZE des trois tables de travail sur la copie, les essais ci-dessus redeviennent proches des coûts à chaud. Cette optimisation mesurée ne modifie ni l’architecture ni les données historiques. Les observations initiales sont conservées dans `phase2-cold-unanalysed.json` et les plans avant ANALYZE dans le résultat final du benchmark froid.

La préparation lexicale exécute désormais ANALYZE sur les seules tables documentaires concernées ; une restauration doit aussi être analysée avant une évaluation représentative.

### Plans et concurrence

- lexical : **Hash Join**, 884 lignes de scores, 31.3 ms dans EXPLAIN ANALYZE ; 1660 blocs lus et 52863 blocs trouvés en cache. Aucun LIMIT de passages ni parcours HNSW dans ce plan. Le regroupement documentaire est mesuré séparément en Python.
- vector : **Hash Join**, 10748 lignes de scores, 31.9 ms dans EXPLAIN ANALYZE ; 1628 blocs lus et 40213 blocs trouvés en cache. Aucun LIMIT de passages ni parcours HNSW dans ce plan. Le regroupement documentaire est mesuré séparément en Python.

Quatre appels simultanés : **1 accepté(s), 3 refusé(s)** par l’admission bornée. L’appel accepté a duré 199.0 ms côté appelant ; les refus sont immédiats. Ceci mesure le comportement prévu d’un encodeur unique, pas un débit parallèle de production. Une éventuelle file courte ou plusieurs encodeurs devra être évaluée selon le nombre d’évaluateurs, sans assimiler cette question à un besoin de HNSW.

### Premier tableau comparatif

Premier cahier de chaque liste à D=50, sans filtre obligatoire. Les cinq premiers et leurs extraits sont conservés dans le JSON local. **Titres et rangs ne valent pas jugement de pertinence** ; aucun nDCG ou taux de succès n’est annoncé sans annotations humaines.

| Requête | Lexical nº 1 | Vectoriel nº 1 | Hybride nº 1 |
|---|---|---|---|
| Agen | Cahier de la noblesse de la sénéchaussée d'Agen | Cahier de la noblesse de la sénéchaussée d'Agen | Cahier de la noblesse de la sénéchaussée d'Agen |
| Amiens | Cahier du clergé du bailliage d'Amiens | Cahier du clergé du bailliage d'Amiens | Cahier du clergé du bailliage d'Amiens |
| Beauvais | Cahier du tiers-état du bailliage de Beauvais | Cahier de la communauté de Bouvignies (Bailliage de Douai) | Cahier du tiers-état du bailliage de Beauvais |
| Saint-Pierre-le-Moutier | Cahier de la noblesse du bailliage de Saint-Pierre-le-Moutier | Cahier de la noblesse de la sénéchaussée de Riom | Cahier de la noblesse du bailliage de Saint-Pierre-le-Moutier |
| Suppression des privilèges | Cahier de Mauregard (Paris) | Cahier de Neauphle-le-Château (Paris) | Cahier de Mauregard (Paris) |
| Impôts et fiscalité | Cahier du tiers-état du bailliage de Montargis | Cahier de la noblesse de la Province du Bas-Limousin | Cahier de Fismes du bailliage de Vitry-le-François |
| Justice seigneuriale | Cahier du tiers-état du bailliage de Senlis | Cahier de Chelles (Paris) | Cahier de Chelles (Paris) |
| Abolition des corporations | Cahier du tiers-état de la sénéchaussée de Morlaix | Cahier de la communauté de Megrueil (Sénéchaussée d'Aix) | Cahier du tiers-état de la sénéchaussée de Toulon |
| Éducation des enfants | Cahier de la paroisse de Chevannes (Bailliage de Nemours) | Cahier de la noblesse du bailliage de Château-Thierry | Cahier de la noblesse du bailliage de Château-Thierry |
| Entretien des routes | Cahier du tiers-état du bailliage de Bar-sur-Seine | Cahier du tiers-état du bailliage de Bar-sur-Seine | Cahier du tiers-état du bailliage de Bar-sur-Seine |
| Agen agriculture | Cahier de la noblesse de la sénéchaussée d'Agen | Cahier du tiers-état de la sénéchaussée du Maine | Cahier de la noblesse de la sénéchaussée d'Agen |
| Amiens traitement des curés | Cahier du clergé du bailliage d'Amiens | Cahier de la noblesse du bailliage de Gien | Cahier de la noblesse du bailliage de Gien |
| Beauvais jurandes | Cahier du tiers-état du bailliage de Beauvais | Cahier de la communauté de Bouvignies (Bailliage de Douai) | Cahier de la noblesse du bailliage de Blois |
| Noblesse fiscalité | Cahier de la noblesse du bailliage de Château-Thierry | Cahier de l'ordre de la noblesse du bailliage de Toul | Cahier des trois ordres du bailliage de Langres |
| roi | Cahier de Mesnil-le-Roi (Paris) | Cahier de la communauté de Montmegan (Sénéchaussée d'Aix) | Cahier de Mesnil-le-Roi (Paris) |
| gabelle | Cahier du tiers-état de la province de Poitou | Cahier du tiers-état de la province du Bourbonnais | Cahier du tiers-état de la province de Poitou |
| liberté syndicale | Cahier de la noblesse du bailliage de Châtillon-sur-Seine ou La Montagne | Cahier de la noblesse de la Province du Haut-Limousin | Cahier du baillage d'Etain (Bailliage de Bar-le-Duc) |
| zxqv1789inexistant | Aucun | Cahier du clergé du Pays de Gex | Cahier du clergé du Pays de Gex |
| claire et pruise | Cahier du clergé de la province d'Artois | Cahier du clergé du bailliage d'Amont | Cahier de la communauté de Landas (Bailliage de Douai) |
| suppression des lettres de cachet | Cahier de l'ordre de la noblesse du bailliage de Toul | Cahier du clergé du bailliage de Besançon | Cahier du tiers-état de la Sénéchaussée de Castelmoron d'Albret |

Les requêtes mixtes demandent une attention particulière : pour « Amiens traitement des curés », le premier lexical est bien le clergé d’Amiens mais l’hybride commence par Gien ; pour « Beauvais jurandes », le premier lexical est Beauvais et le premier hybride Blois. La RRF privilégie les documents soutenus par les deux branches, sans imposer une contrainte géographique à la requête libre. Le filtre de lieu séparé permet d’exprimer cette contrainte. La pertinence de ces arbitrages reste à juger, pas à déduire des seuls titres.

### Validation finale, sauvegarde et suite

**63 tests réussis** sur `tests/test_documentary_search.py`, `tests/test_documentary.py`, `tests/test_hybrid_search.py` et `tests/test_search_packaging.py`. Les vecteurs synthétiques et les décisions de réintégration de ces tests restent dans des clusters temporaires distincts de la base réelle. Les contrôles incluent la correspondance documentaire seule, les filtres avant classement, zéro résultat lexical, un cahier long sans répétition, les trois profondeurs, les exclusions, les droits publics inchangés, le refus de lecture des 43 autres documents et l’invalidation de préparation après une décision éditoriale.

Le smoke Chromium réel a validé recherche lexicale, comparaison hybride, lecteur au passage exact, zéro résultat lexical et affichage aux largeurs 375/1 280 pixels, avec **zéro erreur JavaScript**. Le laboratoire local est laissé en fonctionnement sur le port 1791.

Ruff et les contrôles de syntaxe JavaScript sont conformes. Les trois avertissements observés dans les suites existantes concernent Starlette/httpx et deux identifiants OpenAPI SEO dupliqués ; aucun de ces composants publics n’a été modifié.

Sauvegarde locale privée : `1789/data/private/documentary/phase2.dump`, conservée en plus de celle de phase 1 et ignorée par Git. Les recettes, statistiques, décisions et vecteurs peuvent être restaurés ; le contrôle `documentary.lab verify` doit suivre toute restauration. Les textes originaux et décisions versionnées n’ont pas été modifiés.

**Conclusion technique limitée aux conditions mesurées : conserver l’exact vectoriel pour cette population.** Les temps mesurés ne justifient pas un HNSW anticipé. Avant la phase 3, faire juger les vingt requêtes et leurs extraits, compléter le jeu avec des cas indépendants, examiner les recherches mixtes et l’abstention sur les requêtes sans signal. Ni ces exemples ni ces petits échantillons de latence ne constituent une validation générale de pertinence ou une garantie sous charge publique.
