# Auteurs et contributions publiques

Les modèles Pydantic et `/docs` décrivent le contrat complet. Les identifiants
BIGINT sont des chaînes décimales, y compris dans les paramètres OpenAPI.

## Lectures

- `GET /api/v1/authors/{author_id}` : projection `public_author()` (nom, slug,
  URL historique, anonymat). Aucun champ de compte ou d'importation.
- `GET /api/v1/authors/{author_id}/forms?page_size=20&after_id=…` : formulaires
  regroupés dans un lot de contributions, avec leurs identifiants, dates et
  `api_url`. Maximum 100 contributions par lot ; curseur `next_after_id`, ordre
  contribution.id croissant, sans OFFSET ni comptage. Aucun doublon de formulaire
  dans un lot ; un formulaire peut réapparaître dans le lot suivant. Le futur
  frontend devra alors regrouper par ID de formulaire, sans fusionner les
  contributions. Seules les contributions avec au moins une réponse à une
  question de leur formulaire sont proposées. Un auteur sans réponse a une
  liste vide.
- `GET /api/v1/forms/{form_id}/contributions/{contribution_id}` : formulaire,
  contribution, auteur public éventuellement absent et toutes les réponses
  réellement présentes. Une association formulaire/contribution incorrecte
  retourne 404.
- `GET /api/v1/forms/{form_id}/contributions?contrib=…` : résolution de l'ancien
  sélecteur **par rang**, puis même restitution complète. `legacy_index` indique
  le rang retenu ; il est null lors d'une lecture par ID.

## Identifiants et compatibilité

Un auteur historique est une ligne `authors`, éventuellement associée à un
compte, mais ce compte n'est jamais exposé. Le modèle n'impose aucune unicité
(auteur, formulaire) : plusieurs contributions au même formulaire restent
séparées. Un auteur peut contribuer à plusieurs formulaires. Une contribution
peut n'avoir aucun auteur ; une question peut avoir plusieurs réponses, avec des
positions distinctes. Il n'existe pas de statut supplémentaire « non publiable ».
Les noms des auteurs anonymes sont remplacés par la projection neutre existante.

Le résolveur JSON des anciens liens `?contrib=…` utilise un rang 1..M selon
la date croissante (NULLS LAST), puis l'ID croissant, avec repli sur 1 pour un
rang invalide et bornage au dernier rang disponible. Le front React utilise
`/forms/{form_id}/contributions/{contribution_id}` avec l'identifiant en base.

`GET /api/v1/answers/{answer_id}` reste disponible : `contribution_id` et
`question.form_id` permettent déjà de retrouver la contribution, puis d'ajouter
le fragment `#answer-{id}` côté frontend. Aucune nouvelle page individuelle de
réponse n'est nécessaire. Le fragment n'est pas traité par le serveur.

## Réponses et confidentialité

Ordre : `COALESCE(question.position, 999999), question.id`, puis position de
réponse NULLS LAST et ID de réponse. Les réponses manquantes ne sont pas
fabriquées ; les lignes existantes vides ou nulles et les réponses multiples
sont conservées. Les réponses à des questions d'un autre formulaire sont exclues.
Les choix normalisés sont restitués par position d'option NULLS LAST puis ID.

Les textes sont complets et doivent être échappés au rendu, jamais interprétés
comme du HTML. Seuls les libellés des choix, `other_text` (chaînes) et la valeur
publique des questions number/scale/date sont extraits du JSON de réponse.
Aucun JSON brut, hash, champ de compte, adresse privée ou métadonnée d'importation
n'est sérialisé. Les textes libres peuvent contenir des informations personnelles
à la source ; aucune identité n'est reconstruite.

## Erreurs et budget SQL

404 pour une ressource absente, 422 pour un ID/curseur/taille invalide ; 500,
503 (base indisponible) et 504 (timeout SQL avec rollback) sans détails internes.
Les erreurs restent JSON, même avec `Accept: text/html`. Les endpoints sont
publics et indépendants de la session ; les protections de cache privé existantes
restent actives lorsqu'un cookie de session est présent.

Budget fixe testé, hors `SET LOCAL statement_timeout` (5 secondes) : auteur
1 SELECT ; formulaires d'auteur 2 SELECT ; contribution par ID 3 SELECT
(en-tête, choix en lot, réponses) ; sélecteur historique 6 SELECT. Aucun N+1 ni
chargement des réponses pour la liste des formulaires. Le résolveur historique
conserve COUNT et OFFSET, potentiellement coûteux sur les rangs profonds ; les
nouveaux liens doivent privilégier la lecture par ID. Aucun cache/index/migration
ajouté. Les tests synthétiques ne constituent pas une mesure sur le corpus complet.

Limite préexistante hors périmètre : `question_stats.question_id` est INTEGER,
alors que les questions utilisent BIGINT ; les triggers de statistiques empêchent
actuellement des réponses à des questions dont l'ID dépasse la plage INTEGER.
Les autres identifiants BIGINT sont testés au-delà de la précision JavaScript.
