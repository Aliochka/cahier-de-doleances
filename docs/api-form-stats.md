# Statistiques par formulaire (DASH-001)

`GET /api/v1/forms/{form_id}/stats` charge un tableau de bord en une requête HTTP.
L’identifiant de chemin et les IDs JSON sont des chaînes décimales BIGINT.
La réponse contient `form` (id, name, url) et `questions`, une liste de couples
`question` (`FormQuestion`) / `stats` (`QuestionStatistics`). OpenAPI définit les
modèles et les erreurs JSON, indépendamment de l’en-tête Accept.

L'API inclut toutes les questions à choix, même sans données, et laisse les
questions ouvertes à la page Formulaire React.

Ordre : `COALESCE(position,999999), id` pour les questions ; position ASC NULLS LAST,
ID ASC pour les options, puis « Autre (texte libre) » si présent. Les options à
zéro sont conservées. Un formulaire sans choix retourne 200 avec `questions: []` ;
un choix sans réponses conserve ses options avec effectifs et pourcentages nuls.
Un formulaire absent retourne 404 ; paramètres invalides 422 ; erreur interne 500,
base inaccessible 503, timeout SQL 504 avec rollback, sans détails techniques.

## Calculs et coût

`choice_statistics_many()` est partagé avec `choice_statistics()` utilisé par
l’endpoint individuel. La mise en forme JSON utilise aussi le même helper
`statistics_fields()`. Aucun second calcul ni normalisation frontend.

- `total_answers` vient de `question_stats.answers_count`, maintenu par triggers.
- Les sélections sont les liens `answer_options`, groupés par option.
- Les contributions distinctes sont comptées par question dans les réponses.
- Une réponse avec un tableau `other_text` non vide compte une fois dans la
  catégorie synthétique, même si elle contient plusieurs textes.
- Pourcentage = `round(count * 100.0 / total_answers, 2)`, ou zéro si le total est
  nul. La somme peut dépasser 100 %, notamment pour les choix multiples.
  Contributions distinctes et personnes uniques ne sont pas assimilées.

Budget fixe : **5 SELECT** (formulaire, questions, compteurs, sélections groupées,
agrégat groupé contributions/autre texte), plus un SET LOCAL statement_timeout=5s.
Sans choix : **2 SELECT** seulement. Les endpoints individuels demandent 4 SELECT
par question ; le test à trois questions mesure 12 lectures contre 5 groupées.
Aucun N+1, comptage global, OFFSET ou chargement des textes/réponses en mémoire.
Aucune donnée d’auteur, compte ou texte libre n’est renvoyée.

Seuls les compteurs de réponses sont préagrégés : les liens d’options et les
réponses des questions à choix du formulaire doivent encore être agrégés à la
demande. Les index existants sur question_id et option_id sont réutilisables ; le
planificateur choisit le plan. Sur un grand formulaire, ces agrégations et COUNT
DISTINCT peuvent rester coûteux. Le nombre fixe de requêtes ne garantit pas une
latence fixe. Le timeout porte sur chaque instruction, pas sur tout le dashboard.
Les mesures sur le corpus complet restent à faire avant production ; aucun cache,
index, schéma ou mécanisme d’import n’est modifié dans cette tâche.

Les tests PostgreSQL isolés comparent chaque bloc avec l’endpoint individuel,
vérifient les valeurs attendues, le budget SQL, les BIGINT,
les erreurs JSON et un véritable statement_timeout suivi d’un rollback.
