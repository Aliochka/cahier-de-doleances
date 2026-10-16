# Questions, réponses et statistiques publiques (API v1)

Les schémas et erreurs détaillés sont générés depuis Pydantic dans `/docs` et
dans le contrat versionné `frontend/contracts/openapi.json`. Ce lot ne nécessite
aucune session et ne fournit ni recherche, ni écriture, ni paramètres graphiques.

## Lectures

- `GET /api/v1/questions/{question_id}` : reprend les champs de `FormQuestion`
  (`id`, `form_id`, `prompt`, `type`, `position`, `slug`, `url`), avec `form`
  (`id`, `name`, `url`) et `display_mode`. `choice` désigne `single_choice` et
  `multi_choice` ; les autres types utilisent la consultation textuelle
  historique (`text`). Aucune réponse n'est chargée.
- `GET /api/v1/questions/{question_id}/answers?page_size=20&cursor=…` :
  `{question_id, items, page_size, has_next, next_cursor}`. Une page vide est
  normale et retourne 200. `page_size` vaut 20 par défaut, entre 1 et 100.
- `GET /api/v1/answers/{answer_id}` : réponse complète avec sa question.
  Cet endpoint préserve le parcours des URL individuelles `/answers/{id}` et
  permet de lire un texte tronqué dans une liste.

Une réponse contient uniquement `id`, `question_id`, `contribution_id`, `text`,
`is_truncated`, `submitted_at`, `author` et `url`. Le détail ajoute `question`.
Une date ou un auteur absent vaut `null`. L'auteur utilise la projection publique
d'API-001 : nom public uniquement si explicitement non anonyme ; sinon libellé
neutre et slug sûr. Aucun compte, hash, courriel, JSON brut d'importation ou
`value_json` n'est exposé.

Les textes libres sont publics comme dans les pages historiques, mais ne sont
**pas du HTML fiable**. Le frontend doit les afficher comme du texte échappé.
Cela ne garantit pas l'absence d'informations personnelles écrites dans le corpus.

## Pagination

Ordre inchangé : `submitted_at DESC NULLS FIRST, answer_id DESC`. Le curseur
opaque encode le dernier couple date/identifiant, y compris les dates nulles.
Le recopier pour la même question, sans le décoder ni convertir ses identifiants.
Une ligne sentinelle détermine `has_next` ; `next_cursor` vaut `null` en fin.
Aucun OFFSET ni comptage exact, même sur la première page.

Le filtre de visibilité historique est conservé : texte non vide pour les choix,
au moins 60 caractères après `btrim` pour les autres types. Les textes de liste
sont limités à 20 000 caractères, avec `is_truncated`. Le détail individuel reste
complet, comme la page HTML. Aucun filtre de mots-clés n'est ajouté à cette API.
La consultation et les filtres sont fournis par le frontend React.

Tous les identifiants JSON **et les nouveaux paramètres de chemin** sont des
chaînes décimales positives, limitées au BIGINT PostgreSQL. Les conversions en
entiers ont lieu seulement en Python pour les paramètres SQL, jamais en JavaScript.

## Statistiques

`GET /api/v1/questions/{question_id}/stats` accepte uniquement les deux types à
choix. Chaque `category` contient `option_id`, `kind`, `label`, `position`, `count`
et `percentage`. Les libellés sont complets, sans couleurs ni configuration Chart.js.
Les options, même sans sélection, sont ordonnées par `position ASC NULLS LAST`,
puis `id ASC`. La catégorie synthétique `other_text` est ajoutée en fin si nécessaire,
avec `option_id: null` ; aucun identifiant artificiel d'option n'est inventé.

- `total_answers` : nombre de lignes `answers`, issu du compteur historique
  maintenu par triggers. Ce n'est pas un nombre garanti de personnes.
- `answered_contributions_count` : nombre de contributions distinctes ayant
  une réponse à cette question. Plusieurs réponses dans une même contribution
  ne sont comptées qu'une fois ; ce n'est pas un compte d'auteurs/personnes uniques.
- `total_option_selections` : nombre de liens normalisés `answer_options`.
- `other_text_answers_count` : réponses ayant au moins un `other_text`, une fois
  par réponse, même si plusieurs textes sont présents.
- `total_selections` : somme historique de toutes les catégories, donc sélections
  d'options **plus** réponses avec autre texte.
- `percentage` : `100 × count / total_answers`, avec `round(..., 2)` (deux décimales, zéro si le dénominateur vaut zéro). Le contrat explicite
  `percentage_denominator` et `percentage_decimal_places`. Une somme dépassant
  100 % pour les choix multiples est normale ; les arrondis ne sont pas renormalisés.

Le calcul commun `choice_statistics` est réutilisé par l'API et les dashboards.
Le comptage supplémentaire des contributions distinctes est demandé uniquement
par l'API : les dashboards ne font pas cette agrégation supplémentaire.

## Erreurs, coût et vérification

Les erreurs sont JSON quel que soit `Accept` ou des autres en-têtes : 404 absent, 422 paramètres
invalides, 400 statistiques demandées pour un type non à choix, 503 base
indisponible, 500 inattendu, 504 délai SQL dépassé, 408 délai du middleware HTTP.
Les requêtes SQL de ce lot ont une limite locale de cinq secondes et utilisent
le rollback d'API-003. Aucun détail PostgreSQL n'est renvoyé au visiteur.

Budgets : détail question **1 SELECT**, page **2 SELECT**, statistiques **4 SELECT**,
détail réponse **1 SELECT**, plus un `SET LOCAL` par endpoint. Les statistiques
agrègent les sélections et les réponses de la question : leur coût dépend de son
volume. La pagination borne les résultats, mais la jointure et le tri par date
peuvent encore examiner de nombreuses lignes avec les index actuels. Les mesures
sur une petite base de test ne préjugent pas du corpus complet sur Wallace.
Aucun index, cache, schéma ou migration n'est ajouté.

Pour régénérer le contrat : `cd frontend && pnpm contract:generate`, puis commiter
les deux artefacts générés et exécuter `pnpm contract:check`. Le build frontend
reste indépendant de Python et de l'API. Les tests sont dans
`tests/test_api_questions.py` et les fixtures PostgreSQL existantes ; l'export
OpenAPI reste hors ligne et interdit les connexions à PostgreSQL.
