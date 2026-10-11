# API publique des formulaires (v1)

Le contrat complet est généré par FastAPI dans `/openapi.json` et consultable
sur `/docs`. Aucune authentification n'est nécessaire. Ce lot n'expose ni
réponses individuelles, ni statistiques, ni données de compte ou d'importation.

- `GET /api/v1/forms` : tableau complet, trié par identifiant, de
  `{id, name, questions_count, url}`. Sans formulaire : `200` avec `[]`.
- `GET /api/v1/forms/{form_id}` : mêmes champs, plus `questions`, tableau complet
  de `{id, form_id, prompt, type, position, slug, url}`. Un formulaire sans
  questions retourne `questions: []`.

Tous les identifiants de réponse sont des **chaînes décimales** : les colonnes
PostgreSQL BIGINT peuvent dépasser la précision des nombres JavaScript. Ne pas
les convertir en `Number` dans le futur client. Le paramètre de chemin accepte
un entier décimal positif jusqu'à `9223372036854775807`.

`position` peut être `null`. L'ordre reprend exactement les pages historiques :
`COALESCE(position, 999999), id`. Les types ne sont pas recodés : les mappings
actuels utilisent `text`, `single_choice` et `multi_choice`, mais la colonne
n'est pas un enum. Le contrat reste donc une chaîne ouverte, compatible avec
les autres catégories prévues par le modèle. Les questions sans réponse sont
incluses. Il n'existe pas de description de formulaire à exposer dans le modèle.

Les chemins `url` sont relatifs : `/forms/{id}` et `/questions/{id}-{slug}`.
Les slugs utilisent le helper historique. La consultation HTML `?contrib=…`,
les dashboards et leurs règles sont conservés.

Les erreurs sont toujours JSON, même avec `Accept: text/html` :

- `404` : formulaire absent (`{"detail":"Formulaire introuvable"}`).
- `422` : identifiant invalide, au format de validation FastAPI documenté.
- `503` : erreur opérationnelle de base (`{"detail":"Service indisponible"}`).
- `500` : erreur SQL inattendue ou applicative, message générique sans détails.
- `408` : expiration du middleware HTTP existant, `detail: "Request timeout"`.

Les opérations OpenAPI sont `list_public_forms` et `get_public_form`. Les
avertissements de doublons des anciennes routes HTML restent hors périmètre.
La liste utilise une seule requête avec jointure sur les questions ; le détail
en utilise deux. Aucune contribution, réponse ou statistique n'est chargée.
Pas de cache applicatif ni politique CDN ajoutée. La présence d'un cookie de
session conserve la protection existante `private, no-store`, sans influencer
le contenu public ; ces endpoints n'émettent pas de `Set-Cookie`.
