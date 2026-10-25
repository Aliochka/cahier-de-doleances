# Recherche lexicale H1 par question — compte rendu

25 octobre 2026. Implémentation locale, sans déploiement en production.

## Fonctionnement final

L’endpoint existant `GET /api/v1/search` conserve deux périmètres, sans sélecteur de moteur :

- Sans `question_id` : parcours hybride global existant, avec lexical H1, encodage BGE-M3, HNSW et fusion RRF. La recette `h1-public-v2-ts-rank`, ses poids et paramètres sont conservés.
- Avec `question_id` : `HybridSearch.retrieve` délègue à `retrieve_question`, qui appelle exclusivement `H1LexicalSearch(..., statistics=True, prefilter=None).lexical(..., limit=50, question_id=...)`. Il n’y a ni encodage de requête, ni lecture vectorielle, ni RRF dans ce parcours. Les temps d’encodage, de vectoriel et de fusion valent zéro ; aucun score RRF n’est attribué aux résultats lexicaux.

Le SQL et le classement lexical H1 n’ont pas été dupliqués ni modifiés : configuration `pg_catalog.french`, couverture IDF globale 0,5, couverture des termes 0,3, `ts_rank(..., 32)` 0,2 et départage documentaire existant. Le filtre `CAST(d.record->>'question_id' AS bigint)=:question` est déjà présent dans le SQL avant le tri et la limite. Le champ plein texte est construit à partir des textes de réponses, sans leur titre de question. Pour les questions à choix, seuls les textes libres « Autre » sont indexés.

Il s’agit d’une recherche plein texte et de ses formes linguistiques françaises, pas d’une recherche littérale de sous-chaîne ou d’un Ctrl+F. L’interface conserve les onglets et les composants actuels ; elle invite désormais à saisir des mots-clés et indique le caractère limité de la sélection. Les textes de la recherche globale sont conservés.

Le contrat de réponse existant est réutilisé ; `mode` accepte maintenant `lexical` pour une question et reste `hybrid` pour la recherche globale. Les loaders vérifient le mode attendu : un ancien backend encore hybride sur une question est refusé plutôt que présenté silencieusement comme lexical. OpenAPI et les types générés ont été actualisés.

## Pagination et ordre

La profondeur reste **50 unités documentaires** et la page reste à **20 réponses au maximum**, avec « Afficher davantage ». Aucune pagination profonde ni total exhaustif n’est ajouté.

Le classement lexical H1 est conservé tel quel. Le regroupement existant conserve une carte par réponse, au rang de sa première unité retenue ; plusieurs textes « Autre » d’une réponse ne créent pas plusieurs cartes. Cinquante unités peuvent donc produire moins de cinquante réponses distinctes.

L’hydratation et les instantanés existants sont réutilisés. Le curseur parcourt une sélection figée sans nouveau calcul lexical. L’identité inclut toujours la question et la saisie ; une recette distincte `h1-question-lexical-v1-ts-rank` et le mode de l’instantané empêchent de réutiliser une ancienne sélection hybride filtrée. Celle-ci reçoit 410, avec la relance existante. Son refus n’évince pas les instantanés globaux indépendants. La durée de vie reste de dix minutes.

Les états de saisie vide, absence de résultat, sources retirées et erreurs restent disponibles. Une saisie vide ne lance pas de recherche. Les boutons de réessai et de relance conservent leur contexte de question.

**Passer à 100 unités :** ce serait simple techniquement, en ajustant la profondeur et la limite de la seule `QuestionLexicalRecipe`. Le lecteur accepte déjà jusqu’à 100 candidats ; il ne faudrait ni nouvelle pagination ni nouveau moteur. Le tri, le regroupement et l’hydratation seraient toutefois à vérifier à cette profondeur, notamment leur délai. **Aucune augmentation à 100 n’a été effectuée.**

## Tests et vérifications

- **62 tests backend/unitaires ciblés réussis** : contrat HTTP et service de recherche. Les tests de la recherche par question font échouer explicitement tout appel au chargement du modèle, à l’encodage, à `ann_search` ou à `fuse` ; ils vérifient l’ordre lexical et la recette distincte. Le worker admet le parcours lexical sans exiger que le modèle soit prêt.
- **12 tests d’intégration PostgreSQL réussis**, sur les deux bases isolées suffixées `_test` : ordre identique au moteur H1, requêtes filtrées, provenance, pagination et gardes existantes. Un test question utilise de vrais textes synthétiques et interdit l’encodage, le vectoriel et RRF après le démarrage du backend. La seconde page interdit également toute nouvelle récupération de candidats.
- Un scénario HTTP vérifie **45 réponses**, dont une avec plusieurs textes « Autre », parcourues en **20 / 20 / 5**, sans doublons et avec un seul calcul initial. Un autre vérifie que le refus d’un ancien instantané local laisse un curseur global utilisable.
- **185 tests frontend réussis**. Le client accepte le mode lexical local et les loaders refusent les modes incorrects, y compris un résultat lexical présenté à la recherche globale.
- **27 tests navigateur ciblés réussis** : recherche globale, pages questions et recherche par question, avec et sans JavaScript, pagination cumulative, expiration, erreurs, mobile, clavier et transition des onglets. Les **5 tests de la recherche locale ont ensuite été rejoués avec succès** après ajout des assertions sur le plein texte et la sélection non exhaustive.
- TypeScript, compilation frontend de test, Biome, Ruff, vérification du format Python, export OpenAPI et contrôle des types générés : réussis. La correction de paramétrage d’une fixture de test a été vérifiée en rejouant le test d’intégration concerné.

Les tests globaux existants vérifient toujours les appels aux deux branches, la recette, les scores RRF et la pagination. Les tests PostgreSQL n’ont écrit que leurs données synthétiques dans les bases de test dédiées, avec leur nettoyage habituel ; les mesures sur le corpus local réel sont strictement en lecture seule.

## Performances sur le corpus local complet

Mesures séquentielles du moteur `H1LexicalSearch` réel, avec `ReadGuard` / `ReadConnection`, transactions READ ONLY, limite de 50 unités et budget de **3 secondes par recherche**. Un seul travail à la fois, arrêt prévu si la pression d’E/S dépassait le seuil prudent ; aucun arrêt n’a été nécessaire. Aucun modèle n’a été chargé pour ces mesures, aucun embedding ni index n’a été modifié.

Machine locale : Ryzen 9 7950X, 32 threads, environ 114 Gio de mémoire disponible lors des contrôles. Le corpus reste à 5 172 356 unités et 5 187 190 segments ; les questions contrôlées comportent respectivement 7 941 unités (46), 21 601 (35), 26 181 (290) et 110 576 (293).

Temps en millisecondes. Le premier passage est la première mesure de cette requête dans cette série ; il n’est **pas un test à froid garanti**. Le second est une répétition immédiate. Les temps comprennent la préparation H1, les gardes d’accès et la restauration des unités. Ils ne comprennent pas la validation complète `SearchReader.validate` du service, l’hydratation HTTP ni le rendu frontend, couverts fonctionnellement par les tests d’intégration et navigateur.

| Question | Recherche | Premier passage (ms) | Répétition (ms) | Unités | Réponses après regroupement |
|---|---|---:|---:|---:|---:|
| 46 | handicap | 33 | 19 | 50 | 50 |
| 35 | formation | 90 | 44 | 50 | 50 |
| 290 | vélo | 24 | 16 | 50 | 50 |
| 293 | bonjour | 23 | 21 | 50 | 50 |
| 293 | isolation thermique | 186 | 169 | 50 | 50 |
| 293 | transition écologique | 375 | 362 | 50 | 50 |
| 293 | environnement | 215 | 210 | 50 | 50 |
| 293 | "transition écologique" | 182 | 178 | 50 | 50 |
| 293 | zzzxqvzznontrouvable | 13 | 13 | 0 | 0 |

Toutes les unités retournées appartiennent à la question attendue et le regroupement ne contient aucun doublon de réponse. Le terme volontairement absent produit bien une sélection vide. Aucun délai n’a été dépassé dans ces 18 recherches ; la plus lente observée est d’environ **375 ms**.

Les `EXPLAIN` sans `ANALYZE`, avec les paramètres réellement produits par H1, montrent :

```text
Limit 50
  Sort sur le score lexical et document_id
    Bitmap Heap Scan documents_full
      BitmapAnd
        Bitmap Index Scan documents_full_space_id_int8_idx
        Bitmap Index Scan documents_full_search_vector_idx
```

Les index question et GIN existants sont donc combinés pour réduire les candidats avant leur classement. Aucun parcours HNSW ou calcul de distance vectorielle n’intervient. Aucun `ANALYZE`, changement de statistique, index, schéma ou configuration persistante n’a été effectué.

La première tentative du script de mesure a échoué dans son `EXPLAIN` à cause de la réutilisation du format de paramètres du pilote SQL ; le script temporaire a été corrigé pour reprendre les paramètres SQLAlchemy d’origine. Le tableau présente uniquement la série complète après correction, pas une mesure d’erreur applicative. Mesures et plans conservés temporairement dans `/tmp/benchmark-question-lexical.json`.

## Fichiers modifiés

Les modifications applicatives et leurs tests sont les suivantes ; les fichiers générés sont inclus pour la cohérence du contrat :

- `app/routers/api_hybrid_search.py`
- `app/schemas/hybrid_search.py`
- `app/services/search_snapshots.py`
- `docs/api-search.md`
- `docs/pages-questions.md`
- `frontend/app/features/search/search-controls.tsx`
- `frontend/app/features/search/search-loader.server.ts`
- `frontend/app/features/search/search-panel.tsx`
- `frontend/app/features/search/search-results.tsx`
- `frontend/app/lib/api.ts`
- `frontend/app/lib/search-api.test.ts`
- `frontend/app/routes/question.test.ts`
- `frontend/app/routes/search.test.tsx`
- `frontend/contracts/api.generated.ts`
- `frontend/contracts/openapi.json`
- `frontend/e2e/question-search.spec.ts`
- `frontend/tests/mock-api.mjs`
- `rag/src/cahier_rag/search/service/core.py`
- `rag/src/cahier_rag/search/service/worker.py`
- `rag/tests/integration/test_search_service.py`
- `rag/tests/unit/test_search_service.py`
- `tests/test_hybrid_search.py`
- `tests/test_hybrid_search_integration.py`
- `docs/recherche-lexicale-par-question.md` : présent compte rendu.

Le module `tuning/lexical.py` et la formule H1 existante dans `H1LexicalSearch` n’ont pas été changés. Le module `core.py` est étendu pour orchestrer le parcours lexical par question. Le module de recherche vectorielle `tuning/vector.py`, les embeddings, les index et le schéma PostgreSQL sont également inchangés dans cette intervention.

`readme.md` et le rapport antérieur `docs/benchmark-recherche-par-question-2026-10-25.md` préexistaient avec des modifications ou comme fichier non suivi ; ils n’ont pas été modifiés dans le cadre de cette intervention. Ce benchmark antérieur décrit le parcours hybride filtré désormais remplacé, pas les performances du parcours lexical actuel.

## Limites et mise en service

- Le top 50 est une sélection bornée et non exhaustive ; il ne permet pas d’énumérer toutes les correspondances. Aucune augmentation de profondeur n’est incluse.
- Les statistiques IDF restent globales, comme dans le H1 existant. Aucun réglage de pertinence ni seuil de score supplémentaire n’a été ajouté.
- Le parcours question réutilise le lecteur de corpus, les gardes, le worker borné et l’hydratation du backend existant. Une panne de cette infrastructure ou une saturation peut toucher les deux recherches. Le processus peut toujours charger BGE-M3 au démarrage pour la recherche globale ; ce n’est pas une opération lancée par la recherche lexicale d’une question. Le lecteur conserve sa validation du corpus partagé.
- Les temps locaux ne sont pas une garantie sur le serveur cible et ne constituent pas une mesure à froid ou en charge concurrente. Les budgets de sécurité applicatifs sont conservés.
- Le serveur local de travail déjà lancé n’a pas été redémarré dans cette intervention. Les tests ont utilisé leurs serveurs et bases isolés, et la mesure SQL a utilisé le corpus réel en lecture seule. **Un redémarrage du backend et du frontend de travail est nécessaire pour une recette manuelle de la nouvelle version.** Aucun déploiement en production n’a été effectué.

La fonctionnalité est désormais implémentée dans le périmètre lexical demandé, sans refonte du moteur ni modification PostgreSQL. La recherche globale reste hybride. La mise en production reste une étape séparée, avec les procédures habituelles de déploiement du backend, du frontend et de vérification des index déjà requis.
