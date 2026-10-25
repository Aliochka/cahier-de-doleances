# Benchmark prudent de la recherche par question — 25 octobre 2026

**État examiné :** dépôt local au commit `97cd0cc60e67dfedba2079a38b8bd32158a069a5` (`fix 504 in search in question`).

**Périmètre :** moteur existant et corpus local complet. Aucune modification du code applicatif, des index, des données ou de la configuration persistante. Seul ce rapport est ajouté au dépôt ; la modification de `readme.md` préexistait au benchmark et n’a pas été touchée.

**Conclusion : ne pas considérer la fonctionnalité comme prête à déployer en l’état.** Les mesures complètes sur la plus petite question sont encourageantes, mais une question intermédiaire a produit zéro candidat vectoriel et les tests ont atteint deux fois le seuil préventif de pression d’E/S. La référence exacte de la question 293 n’a pas été exécutée. La validation du rappel sur les grandes questions reste donc à faire.

## 1. Préparation et version de l’API

### Code et processus réellement observés

- API locale : `http://127.0.0.1:8000`, contrôlée par `/healthz` et par les appels de recherche mesurés.
- Processus hôte : PID **28213**, lancé le **25 octobre à 11:18:26 CET**, commande `uvicorn app.app:app --host 127.0.0.1 --port 8000`, dans `/home/ro/cahier-de-doleances`, avec le Python de `.venv`.
- Les fichiers du correctif étaient déjà présents à **11:14:51**, avant ce lancement, et sont identiques à ceux du commit audité. Le commit a été créé ensuite, à 12:34:37 ; cela ne signifie pas que son contenu a changé après le lancement.
- L’import RAG de ce virtualenv pointe vers `rag/src/cahier_rag` du dépôt.
- Les réponses API mesurées annoncent la recette `h1-public-v2-ts-rank`.

Ces éléments concordent avec l’utilisation du code actuel, comprenant la suppression de la relance exacte massive. Limite de provenance : l’API n’expose pas une empreinte des fonctions effectivement chargées en mémoire ; le SHA provient du dépôt et de la concordance processus/fichiers, pas d’une attestation retournée par l’API. Aucun serveur n’a été redémarré ni instrumenté.

### Corpus, index et paramètres

| Élément | Valeur observée |
|---|---|
| PostgreSQL / pgvector | 17.11 / 0.8.7 |
| Corpus `space_id='full'` | 5 172 356 unités documentaires, 5 187 190 segments |
| Modèle | `BAAI/bge-m3`, révision `5617a9f61b028005a4858fdac845db406aefb181` |
| Embeddings | `rag_full.segments_full.embedding`, 1 024 dimensions, distance cosinus |
| Documents et question | `rag_full.documents_full`, question lue dans `record->>'question_id'` |
| HNSW | `segments_full_hnsw`, `vector_cosine_ops`, `m=16`, `ef_construction=64` |
| Filtre question | B-tree `documents_full_space_id_int8_idx`, expression `(space_id, ((record->>'question_id')::bigint))` |
| Lexical | GIN `documents_full_search_vector_idx` |
| Paramètres HNSW | `ef_search=1000`, `iterative_scan=strict_order`, `max_scan_tuples=20000`, `scan_mem_multiplier=1` |
| Candidats et profondeur | 400 segments initialement ; doublement si nécessaire jusqu’à 50 000 ; sortie vectorielle limitée à 50 unités |
| Hybride | 50 unités par branche au maximum, fusion RRF `k=60`, sélection finale de 50 unités au maximum, regroupement par réponse |
| Pagination | 20 réponses par page par défaut ; instantané mémoire et curseurs |
| Seuil exact actuel | Au plus 5 000 unités de la question ; ANN au-delà, sans relance exacte massive |

Le HNSW couvre toutes les questions du corpus complet. Le filtre SQL reste dans la CTE avant son `LIMIT`, mais il ne constitue pas un graphe HNSW distinct pour chaque question.

### Ressources et garde-fous

Machine : **AMD Ryzen 9 7950X**, 16 cœurs / 32 threads, environ **124 Gio de RAM**, **115 Gio disponibles** au départ, swap inutilisé, environ **1,2 Tio libre** sur NVMe. Charge système initiale : environ 0,25. Pression mémoire nulle et pression d’E/S initiale quasi nulle.

PostgreSQL : `shared_buffers=128 Mio`, `work_mem=4 Mio`, deux workers parallèles par gather au maximum. L’index HNSW occupe environ **36 Gio** ; la seule abondance de RAM ne garantit donc pas que ses pages soient déjà en cache. Aucun de ces paramètres n’a été modifié durablement.

Garde-fous appliqués :

- Une seule recherche de benchmark à la fois ; pas de test de charge ni de concurrence synthétique.
- Connexions SQL dédiées avec `default_transaction_read_only=on` et transactions annulées après chaque mesure. Les tables concernées n’activent pas RLS.
- Paramètres HNSW reproduits uniquement avec `SET LOCAL` / `set_config(..., true)`, comme dans le moteur. Les réglages disparaissent à la fin de la transaction.
- Lecture des compteurs bornée à 3 s par requête ; recherches vectorielles SQL limitées à **6 s pour l’ensemble d’une mesure**, avec délai SQL résiduel ; attente de verrou bornée à 300 ms.
- Requêtes HTTP complètes soumises aux budgets applicatifs existants : 18 s globales, 10 s pour lexical + vectoriel, 2 s pour l’hydratation. Arrêt du benchmark prévu dès une erreur API ou une réponse complète supérieure à 8 s.
- Arrêt si mémoire disponible inférieure à 16 Gio, charge système supérieure à 70 % des CPU logiques, ou pression d’E/S `full avg10` supérieure à **10 %**.
- Avant les références exactes : volume de segments, `EXPLAIN` sans `ANALYZE` et, après le premier petit cas, extrapolation conservatrice. Pas de référence exacte si la prédiction dépasse 5 s.
- Modèle déjà disponible chargé hors ligne, sur CPU. Seules les requêtes du benchmark ont été encodées ; **aucun embedding de document n’a été recalculé ou écrit**.
- Aucune migration, aucun `CREATE INDEX`, aucun `ANALYZE`, aucun `VACUUM`, aucune purge des caches PostgreSQL ou du système.

Les mesures directes SQL passent par le rôle local dans une transaction strictement en lecture seule, afin de ne pas consommer le quota de connexions du rôle public. Les mesures HTTP passent bien par l’API et son rôle habituel. Les timings SQL et API ne sont donc pas interchangeables.

## 2. Sélection des questions et coût prévisionnel de l’exact

Les **120 questions** ont été contrôlées par des comptages indexés. La somme retrouvée est exactement celle du corpus : **5 172 356 unités**. Ce contrôle a duré environ **9,5 s au total**.

**Il n’existe aucune question non vide sous 5 000 unités dans ce corpus.** Les questions vides ne constituent pas un test valable de qualité vectorielle. La plus petite question non vide est la 46 ; elle remplace donc le petit cas demandé, avec cette réserve explicite.

| Question | Rôle dans le protocole | Unités | Segments |
|---|---|---:|---:|
| 46 | Plus petite question non vide | 7 941 | 7 942 |
| 35 | Intermédiaire retenue après réestimation | 21 601 | 21 617 |
| 290 | Intermédiaire initialement prévue | 26 181 | 26 193 |
| 293 | Grande question demandée | 110 576 | 112 657 |

- **46** : recrutement d’une personne portant un handicap.
- **35** : démarches de recherche d’une formation.
- **290** : solutions de mobilité alternatives souhaitées, textes libres « Autre ».
- **293** : autres points sur la transition écologique.

Le coût indiqué par `EXPLAIN` pour l’exact était identique sur les questions 46, 290 et 35 : environ **476 646 unités de coût**, avec une estimation de **25 862 documents éligibles**. Les effectifs réels diffèrent fortement. Les statistiques de l’index d’expression ne sont pas présentes dans `pg_stats` ; ce plan est donc utile pour identifier les accès, mais insuffisant pour prédire la latence par question.

La sélection exacte emploie le B-tree question, puis lit les embeddings des segments admissibles et les trie par distance ; elle n’utilise pas HNSW pour choisir les voisins. Les composantes vectorielles seules représentent environ 31 Mio pour la 46 et 440 Mio pour la 293, hors surcoûts de pages, TOAST, jointures et tri.

Après calibration sur la première référence de la question 46, la règle prudente était :

```text
latence de référence la plus lente sur Q46
× nombre de segments de la question / 7 942
× marge de sécurité de 1,5
```

| Question | Estimation conservatrice | Décision sur l’exact |
|---|---:|---|
| 46 | Petit volume initial, délai maximal de 6 s | Exécuté : 3 requêtes, 2 passages chacune |
| 35 | 4,58 s | Préautorisé par le protocole, mais non exécuté après l’arrêt E/S |
| 290 | 5,55 s | Écarté avant exécution |
| 293 | 23,88 s | Écarté avant exécution ; cette valeur est extrapolée, pas mesurée |

L’extrapolation est une borne de prudence du protocole, **pas un modèle de performance validé**. Elle peut surestimer ou sous-estimer un autre état de cache. Aucun calcul exact sur la question 293 n’a été lancé.

## 3. Méthode de comparaison

Le SQL ANN et le SQL exact ont été extraits des chaînes du fichier `rag/src/cahier_rag/tuning/vector.py`, sans modifier le moteur. Même vecteur de requête, même question, même distance cosinus et même agrégation des segments vers l’unité documentaire ; le chemin exact est forcé uniquement dans la session du benchmark pour fournir une référence.

La référence exacte ne se limite pas à un échantillon de la question : elle calcule les distances dans son périmètre complet, puis retient les meilleurs documents. La limite initiale de 400 segments suffit dans les six références exécutées pour obtenir 50 unités distinctes.

```text
Recall@k = | top-k ANN ∩ top-k exact | / min(k, nombre de résultats exacts)
```

La comparaison porte sur les identifiants des unités, pas sur la simple égalité de leur texte. Les écarts de rang sont calculés uniquement sur les unités communes aux deux top 50 ; les unités manquantes sont comptées séparément. La vérification par seuil de score tolérant les ex æquo n’améliore pas les couvertures des trois comparaisons complètes.

Les temps vectoriels comprennent la connexion/session et le SQL vectoriel, mais excluent l’encodage de la requête, le lexical, la restauration des documents et l’hydratation applicative. Ce ne sont pas des chronométrages intégraux de `ann_search` : la sonde de 5 001 unités et les vérifications de génération du lecteur public sont également hors de ces mesures SQL directes ; elles restent incluses dans les mesures HTTP. La petite requête de contrôle du périmètre des identifiants est hors chronométrage vectoriel. Les timings API incluent le calcul hybride complet, l’encodage, les gardes, l’hydratation et le transport HTTP ; ils ne mesurent pas le rendu SSR du frontend.

**« Premier » ne signifie pas « à froid garanti ».** Les caches n’ont pas été vidés. Le premier passage est la première observation de cette requête dans le protocole, sur un cache partiellement présent et non contrôlé. Le deuxième passage immédiat est qualifié de chaud. Les appels API viennent après les lectures SQL, donc dans un état déjà préchauffé. Aucun P95 fiable ni débit soutenu ne peut être déduit de deux passages.

## 4. Résultats effectivement obtenus

### Qualité vectorielle : comparaisons complètes

| Question | Requête | Segments retenus par la CTE ANN | Unités ANN distinctes / de la bonne question | Recall@10 | Recall@50 | Unités exactes manquées dans le top 50 |
|---|---|---:|---:|---:|---:|---:|
| 46 | handicap | 400 | 50 / 50 | 90 % | 92 % | 4 |
| 46 | Comment faciliter le recrutement des personnes handicapées ? | 400 | 50 / 50 | 100 % | 100 % | 0 |
| 46 | obligation d’emploi des travailleurs handicapés | 400 | 50 / 50 | 100 % | 96 % | 2 |

Les répétitions ANN retournent le même ensemble de 50 unités pour ces trois cas. Aucune unité d’une autre question n’a été détectée. Les 400 segments de la CTE sont déjà soumis au filtre question ; le nombre de nœuds globalement visités dans HNSW n’a pas été mesuré. Le nombre d’unités distinctes intermédiaires parmi ces 400 segments n’est pas instrumenté ; la colonne « unités » mesure la sortie après agrégation et limite.

| Requête | Premier résultat identique ? | Écart absolu moyen de rang, unités communes | Recouvrement ANN premier/chaud, top 50 |
|---|---|---:|---:|
| handicap | Non : le premier ANN est deuxième dans la référence | 2,109 | 100 % |
| Comment faciliter le recrutement des personnes handicapées ? | Oui | 0,000 | 100 % |
| obligation d’emploi des travailleurs handicapés | Oui | 0,792 | 100 % |

### Performances : comparaisons complètes

Toutes les durées sont en **secondes**, présentées sous la forme **premier passage / passage chaud**.

| Question | Requête | Vectoriel ANN | Référence exacte | Hybride complet via API | Relecture du curseur |
|---|---|---:|---:|---:|---:|
| 46 | handicap | 2,368 / 0,175 | 1,122 / 0,192 | 0,348 / 0,321 | 0,003 |
| 46 | Comment faciliter le recrutement des personnes handicapées ? | 0,097 / 0,011 | 0,175 / 0,176 | 0,239 / 0,192 | 0,004 |
| 46 | obligation d’emploi des travailleurs handicapés | 1,250 / 0,102 | 0,186 / 0,176 | 0,310 / 0,279 | 0,004 |

Les six nouveaux calculs hybrides API ont tous renvoyé **HTTP 200**, 20 réponses sur une sélection de 50, exclusivement de la question 46. Les trois relectures de curseur ont également réussi. Aucun dépassement des budgets applicatifs n’a été observé dans ces seuls cas complets. Le premier chargement du modèle de benchmark, hors de ces mesures, a pris environ 3,78 s ; l’API était déjà démarrée.

### Mesures partielles et tests non exécutés

| Question | Requête | Mesure ANN réalisée | Unités distinctes retournées | Recall@10 / Recall@50 | Exact / hybride complet |
|---|---|---:|---:|---|---|
| 290 | vélo | 1,851 s, premier passage ; 400 segments retenus | 50, toutes de la bonne question | Non mesurés : référence absente | Exact écarté ; hybride non exécuté après arrêt |
| 35 | formation | 5,774 s, premier passage ; aucun segment retenu en sortie | 0 | Non mesurés : référence absente | Non exécutés après arrêt |
| 293 | bonjour | Non exécutée dans ce benchmark | — | Non mesurés | Exact écarté ; autres mesures non exécutées |
| 293 | Comment encourager la transition écologique au quotidien ? | Non exécutée | — | Non mesurés | Non exécutés |
| 293 | isolation thermique des logements | Non exécutée | — | Non mesurés | Non exécutés |

Les formulations naturelles et précises prévues pour les questions 290 et 35 n’ont pas été exécutées non plus. Les observations d’un diagnostic antérieur sur la question 293 ne sont pas recyclées comme des mesures de ce benchmark.

Le zéro vectoriel de « formation » ne prouve pas que les réponses seraient sans pertinence humaine. Il indique que le parcours ANN n’a retourné aucun candidat d’une question dont le corpus indexé est non vide. Sans référence exacte, aucun Recall@k empirique n’est annoncé. Mathématiquement, une liste ANN vide n’a aucun recouvrement avec une référence non vide ; l’identité et l’ordre de cette référence n’ont toutefois pas été calculés ici. Le résultat hybride de cette requête reste inconnu : le lexical pourrait fournir des résultats et masquer la faiblesse vectorielle.

## 5. Arrêts de sécurité et charge observée

Fenêtre des mesures instrumentées : **19:46:56 à 19:49:38 CET**, le 25 octobre 2026.

1. Première phase : après les trois comparaisons complètes de la question 46 et le premier ANN « vélo » de la 290, `io.full avg10` atteint **12,67 %**, au-dessus du seuil de 10 %. Le protocole s’arrête avant le passage suivant.
2. Après retour de la pression d’E/S vers le niveau initial, une seconde phase est tentée avec une pause préalable tant que `avg10` dépasse 2 %, et les mêmes seuils d’arrêt. La question 35 est choisie pour rester sous l’estimation maximale autorisée pour l’exact.
3. Son premier ANN « formation » prend **5,774 s** et renvoie zéro unité. Le contrôle suivant constate **15,37 %** de pression d’E/S et arrête la phase avant répétition, exact ou appel hybride. Aucun autre test coûteux n’est lancé.

Sur les points de contrôle : mémoire disponible minimale **114,00 Gio**, pression mémoire nulle, charge système maximale observée environ **0,48**. La pression d’E/S revient ensuite à **0,00 % sur avg10** ; aucun signe de saturation durable n’a été observé après l’arrêt.

Ces valeurs sont des points de contrôle, pas une capture continue des pics. La métrique PSI représente du temps d’attente et ne mesure pas un pourcentage de débit maximal du SSD. La hausse coïncide avec les tests, sans permettre d’attribuer toutes les E/S au seul benchmark ; d’éventuelles activités externes n’ont pas été isolées.

Le garde-fou de charge a donc fonctionné. Il limite volontairement les conclusions : ni test à froid contrôlé, ni campagne complète sur les grandes questions, ni mesure de résistance à la concurrence n’ont été réalisés.

## 6. Analyse et seuil de 5 000 unités

### Faits mesurés

- Le périmètre des résultats retournés est correct dans tous les cas vérifiables : aucune fuite vers une autre question.
- Sur la plus petite question, HNSW retrouve entre **92 % et 100 % du top 50 exact** dans cet échantillon. Une formulation naturelle obtient une concordance complète ; le terme court « handicap » manque quatre unités du top 50 et change le premier résultat.
- L’exact sur 7 941 unités a pris **0,175 à 1,122 s** dans les conditions testées. Il a parfois été plus rapide que le premier passage HNSW, mais ces observations ne constituent pas un comparatif à froid contrôlé.
- Une question de taille intermédiaire peut produire **zéro candidat ANN** et une latence de plusieurs secondes avec les paramètres actuels.
- Le seuil de 5 000 n’active l’exact pour **aucune question non vide du corpus actuel**. Il ne protège donc aucune recherche utile contre les limites de rappel de l’ANN filtré.

### Limites et hypothèses restantes

- Trois comparaisons exactes sur une seule question ne valident pas la pertinence humaine, le rappel du corpus entier ou une valeur de seuil universelle.
- Le filtre sur la table des documents est appliqué à des voisins issus du HNSW global ; l’épuisement du parcours borné est une explication cohérente du zéro de « formation », mais le nombre de nœuds visités et la cause précise de l’arrêt HNSW n’ont pas été instrumentés.
- Les bons temps API mesurés sont préchauffés et ne valident pas les délais à froid sur une autre machine, notamment celle de déploiement.
- Les estimations de cardinalité identiques malgré des tailles différentes et l’absence de statistiques visibles pour l’index d’expression justifient une vérification des statistiques. Leur influence exacte sur le plan ANN n’est pas démontrée ici.
- Un seuil fondé sur les segments, les accès disque et le budget résiduel pourrait être préférable au seul nombre d’unités. Aucun changement de seuil n’a été essayé.

**Appréciation du seuil : 5 000 ne paraît pas adapté comme règle de finalisation pour ce corpus.** Il est prudent en volume, mais inopérant sur les questions non vides. Les résultats justifient un pilote autour de 8 000 à 10 000 unités, sans constituer une autorisation de relever ce seuil en production ni d’étendre l’exact aux grandes questions.

## 7. Optimisations éventuelles, par priorité

Aucune des actions suivantes n’a été appliquée.

| Priorité | Action | Impact attendu | Complexité | Risques / validation nécessaire |
|---|---|---|---|---|
| P0 | Détecter et tracer la pénurie de candidats ANN sur une question non vide : effectifs de chaque branche, mode effectif, latence, limites atteintes | Évite qu’un résultat lexical seul soit interprété comme une recherche hybride pleinement évaluée ; rend les futurs incidents explicables | Faible | Ne pas enregistrer les textes citoyens ou les requêtes brutes ; une alerte ne répare pas le rappel |
| P0 | Définir le comportement en cas de pénurie vectorielle, sans réintroduire un exact massif automatique | Maîtrise du compromis rappel / délai ; évite les faux « aucun résultat » et les dégradations silencieuses | Moyenne | Ne pas présenter une sélection approximative comme exhaustive ; ne pas élargir silencieusement la question recherchée |
| P0 | Reprendre la recette sur la question 35 et la 293 dans une fenêtre dédiée, à charge stable, après définition de cette politique | Condition de validation avant déploiement | Faible à moyenne | Conserver l’arrêt de charge, les limites SQL et l’estimation préalable ; ne pas forcer l’exact 293 pour compléter un tableau |
| P1 | Tester une extension très bornée du chemin exact autour de 8 000–10 000 unités et mesurer plusieurs états de cache | Rappel exact pour les petites questions effectivement présentes ; coût possiblement inférieur au parcours HNSW global | Faible pour le code, moyenne pour la validation | Unités et segments diffèrent ; pas de généralisation aux 21 601 ou 110 576 unités à partir du seul cas 46 |
| P1 | Vérifier les statistiques de l’index d’expression et les plans ; envisager leur actualisation en maintenance distincte si nécessaire | Meilleure estimation de la sélectivité et choix de plan potentiellement plus adapté | Faible à moyenne | Actualisation non effectuée ici ; opération avec ses propres E/S, à planifier ; effet sur le rappel HNSW non garanti |
| P1 | Comparer une seule variante bornée de paramètres ANN à la fois, avec mesure du rappel et du délai | Peut améliorer le rappel dans le budget disponible | Moyenne | Augmenter `ef_search`, `max_scan_tuples` ou la mémoire peut aggraver fortement les E/S ; ne pas augmenter simultanément tous les plafonds |
| P1 | Versionner la politique exact/ANN et calibrer les critères d’acceptation avant la recette | Cohérence entre code, API, métriques et comportement attendu | Faible | Ne pas confondre nom de recette inchangé et politique inchangée |
| P2 | Étudier seulement si les solutions simples échouent : question_id relationnel sur les segments, index ciblés ou partitionnement | Meilleure maîtrise de l’isolation et du rappel vectoriel par question | Élevée | Migration, stockage, construction et maintenance des index ; aucune création recommandée sans benchmark comparatif |

## 8. Traçabilité et décision

Sources principales :

- [Recette et fusion du service](../rag/src/cahier_rag/search/service/core.py) : `SearchRecipe`, `HybridSearch.retrieve`.
- [SQL vectoriel testé](../rag/src/cahier_rag/tuning/vector.py) : `ann_search`, seuil, paramètres et deux stratégies.
- [Endpoint complet](../app/routers/api_hybrid_search.py) : `search_hybrid`, `calculate`, pagination et délais.
- [RRF](../rag/src/cahier_rag/search/hybrid/core.py) et [lexical](../rag/src/cahier_rag/tuning/lexical.py).
- [Documentation du contrat](api-search.md).

Les scripts temporaires de benchmark sont `/tmp/question-search-benchmark.py`, `/tmp/question-search-benchmark-resume.py` et `/tmp/question-benchmark-prep.py`. Les mesures brutes sont dans `/tmp/question-search-benchmark.json` et les effectifs dans `/tmp/question-benchmark-prep.json`. Ces fichiers temporaires ne sont pas une interface applicative et peuvent disparaître ; les tableaux de ce rapport constituent le relevé conservé dans le dépôt. Ils ne contiennent pas de textes de réponses citoyennes dans les résultats enregistrés.

Bilan des recherches : **8 passages ANN**, **6 passages exacts limités à la question 46**, **6 calculs hybrides via l’API**, **3 relectures de curseur**. Tous sont séquentiels. Deux arrêts préventifs de charge ; aucune relance exacte massive ; aucun dépassement SQL ni erreur HTTP dans les recherches complètes exécutées. Le reste de la matrice est explicitement non exécuté.

**Recommandation finale : ne pas déployer la fonctionnalité en l’état comme une fonctionnalité finalisée.** Il faut d’abord traiter explicitement la pénurie de candidats vectoriels et valider le comportement sur les questions intermédiaires et grandes. Ce benchmark ne démontre ni la nécessité d’un nouvel index structurel ni la sûreté d’un relèvement général des délais. Les premières étapes doivent rester simples : observabilité, politique de dégradation explicite, essai exact limité aux petits périmètres et nouvelle recette bornée.
