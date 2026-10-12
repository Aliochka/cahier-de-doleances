# Recherche publique JSON

Deux lectures indépendantes :

- `GET /api/v1/search/answers?q=…&page_size=20&cursor=…`
- `GET /api/v1/search/catalog?q=…&page_size=20&cursor_forms=…&cursor_questions=…`

`q` : maximum 512 caractères avant suppression des espaces extérieurs. Taille
par défaut 20, maximum 100 ; curseurs opaques de 1 à 1 024 caractères, validés.
Une absence de résultats retourne 200 avec des listes vides. Paramètres invalides :
422 JSON ; erreurs SQL : 500, base inaccessible : 503, timeout SQL : 504 avec
rollback. Le format JSON ne dépend pas d’Accept ni de HX-Request.

## Réponses

Le moteur existant utilise `answers.text_tsv @@
websearch_to_tsquery('fr_unaccent', :q)` : normalisation française avec unaccent,
casse ignorée, mots vides et racinisation du dictionnaire. Les termes ordinaires
sont combinés, les guillemets servent aux expressions, `OR` aux alternatives et
`-` à l’exclusion. Il ne s’agit pas d’un moteur BM25, sémantique ou approximatif.
Les tests vérifient ces comportements sur des données synthétiques ; ils ne
constituent pas une évaluation de pertinence sur tout le corpus.

**Classement historique conservé : answer.id DESC**, sans score de pertinence
ni tri par date. L’ID décroissant définit le curseur. Les réponses à choix sont
exclues et le texte doit compter au moins 60 caractères après btrim. Le moteur
présélectionne les **1 789 derniers candidats FTS** avant les jointures, le filtre
de type et le curseur. Cette limite historique reste en place : les résultats
situés hors de ce jeu de candidats ne sont pas parcourables, même si le terme
correspond à davantage de réponses. Aucun total exact n’est calculé.

Les recherches de moins de deux caractères retournent une liste vide, sans
ouvrir de session SQL. La route Jinja conserve son ancien comportement : pour
ces recherches, une consultation des réponses récentes (minimum 40 caractères).

Chaque résultat fournit `id`, `contribution_id`, `question`, `form`, `author`
public éventuellement absent, `submitted_at`, `text`, `is_truncated` et `url` :
`/forms/{form_id}/contributions/{contribution_id}#answer-{answer_id}`. Tous les IDs
BIGINT restent des chaînes décimales. Le texte JSON est un préfixe fidèle de
1 000 caractères, chargé avec cette borne depuis SQL ; paragraphes conservés,
aucun résumé ni balise de surlignage ajoutée. Il peut contenir du texte ressemblant
à du HTML : le frontend doit l’échapper. Les textes complets sont accessibles
par l’API de contribution. Les associations incohérentes question/formulaire de
contribution sont exclues uniquement en JSON pour éviter une ancre introuvable.

## Questions et enquêtes

Réutilisation des deux sections Jinja : noms de formulaires et libellés de
questions seulement, sans recherche de descriptions (champ absent), d’auteurs
ou de réponses. `plainto_tsquery('french', unaccent(:q))` combine les lexèmes
français ; les opérateurs web des réponses ne sont pas interprétés ici.

Chaque section est classée par **ts_rank DESC, id DESC**. Le curseur contient le
score PostgreSQL réel et l’ID ; les comparaisons restent converties en `real`
comme dans Jinja. Les tests couvrent scores différents et ex æquo, sans doublons
ni omissions dans des données inchangées. Les curseurs doivent être réutilisés
avec le même terme et la même section ; changer le terme exige leur remise à zéro.
Aucun snapshot n’est garanti en cas de modification du corpus entre deux pages.

La réponse distingue `forms` (`kind: form`, nombre de questions, lien `/forms/{id}`)
et `questions` (`kind: question`, contexte formulaire, compteur historique,
lien `/questions/{id}-{slug}`). Slugs construits par le helper existant.
`has_next_forms`, `has_next_questions` et leurs curseurs permettent de paginer
les sections séparément. `section=forms` ou `section=questions` limite le SQL à
une seule section ; sans ce paramètre, deux lectures de catalogue sont faites.
`page_size` s’applique à chaque section. Aucun classement commun entre catégories
n’est inventé. Une recherche vide retourne deux listes vides sans SQL ; la
consultation générale Jinja reste inchangée.

## Mutualisation, confidentialité et coût

`app/services/search.py` contient les lectures et les curseurs historiques.
Les routes HTML conservent leur représentation, surlignage et fragments HTMX ;
les modèles Pydantic JSON sélectionnent explicitement les champs publics. La
projection `public_author()` protège les noms anonymes ; aucun champ de compte,
hash, donnée brute ou métadonnée d’importation n’est exposé. Les textes libres
peuvent néanmoins contenir des informations personnelles à la source.

Budget : réponses **1 SELECT**, catalogue **2 SELECT** ou **1 SELECT** si une
section est demandée, indépendamment du nombre de résultats. LIMIT page_size+1,
pas d’OFFSET ni de comptage exact du corpus. Le compte des questions par formulaire
et le compteur `question_stats` sont hérités de Jinja. Timeout JSON 5 secondes ;
réponses FTS conservent aussi les SET LOCAL work_mem=64MB et enable_seqscan=false.
Ces réglages historiques peuvent consommer des ressources sous concurrence ;
aucun nouveau réglage global, index, cache ou moteur n’est ajouté.

Index définis par les migrations : GIN `idx_answers_text_tsv` et partiel
`idx_answers_fts_length_id_critical`, index ID décroissant/long texte, GIN
`ix_forms_tsv_name` et `ix_questions_tsv_prompt`, clés primaires pour les jointures.
Les index trigram existants ne sont pas utilisés par ces lectures. Le choix réel
est celui du planificateur ; l’existence des index en production n’a pas été
vérifiée. Un test EXPLAIN ANALYZE/BUFFERS sur une petite fixture isolée confirme
un plan utilisant des index et la borne de page, sans prétendre mesurer les
1,6 million de contributions. Les termes très fréquents peuvent rester coûteux.

Les modèles et opérations sont documentés dans OpenAPI ; `pnpm contract:generate`
régénère les deux artefacts versionnés, `pnpm contract:check` vérifie leur dérive.
Aucune page React de recherche n’est créée ici.
