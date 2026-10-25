# Recherche publique JSON — contrat SEARCH-004 / bascule SEARCH-005

## Endpoint unique

`GET /api/v1/search?q=…&page_size=20&cursor=…`

Une recherche générale hybride, portant sur les réponses textuelles indexées.
FastAPI réutilise SEARCH-003 (lexical RAG-027, BGE-M3/HNSW, RRF) ; la base
applicative vérifie les sources et fournit tous les textes affichés. Aucun
choix de moteur, fallback historique, génération ou reranker.

### Paramètres et validation

| Paramètre | Règle |
|---|---|
| `q` | 512 caractères maximum avant normalisation NFC et retrait des espaces extérieurs ; langage naturel |
| `page_size` | Entier entre 1 et 20, défaut 20 ; conservé pendant toute la navigation |
| `question_id` | Optionnel : BIGINT positif transmis comme chaîne décimale ; limite les deux branches aux réponses de cette question |
| `cursor` | Opaque, authentifié HMAC, versionné, 1 à 1024 caractères ; reprendre exactement la valeur renvoyée |

Les paramètres inconnus et répétés sont refusés en 422, notamment `engine`, `tab`,
`section` et les anciens curseurs multiples. `question_id` filtre les candidats
avant classement, sans filtrer une sélection générale déjà calculée. La branche
vectorielle calcule les distances exactes pour les questions contenant au plus
5 000 unités textuelles. Au-delà, elle utilise HNSW avec le filtre SQL appliqué
avant la limite de candidats ; si le parcours borné ne fournit pas assez de
résultats, elle reprend le calcul exact dans le budget partagé. Les statistiques
lexicales globales et la fusion RRF restent identiques. Un identifiant absent du
corpus produit une sélection vide. Les choix ne fournissent que leurs textes « Autre ».

Avant d’activer cette interface sur un corpus complet, installer l’index additif
avec `psql -X -d <base_recherche> -f deploy/postgres/index-question-search.sql`
sous le rôle de maintenance. Le script vérifie la destination spécialisée et ne
modifie ni les documents, ni les embeddings, ni la révision `rag_0007`. Le rôle
public reste en lecture seule. L’index n’est jamais créé au démarrage de l’application.
Une saisie vide donne `state="idle"` sans appeler le moteur, même s'il est indisponible.
La ponctuation seule, les guillemets déséquilibrés, plus de 32 lexèmes significatifs
ou les autres entrées refusées par la préparation H1 donnent 422.

Aucune syntaxe booléenne globale n'est promise. La préparation lexicale existante
reste utilisée par cette branche ; ses guillemets/exclusions ne constituent pas
une contrainte globale appliquée à la branche vectorielle.

### Réponse

```json
{
  "q": "Comment améliorer les transports publics ?",
  "state": "results",
  "mode": "hybrid",
  "recipe_version": "h1-public-v1",
  "items": [{
    "answer_id": "9007199254741993",
    "contribution_id": "9007199254742993",
    "rank": 1,
    "texts": [{"unit_type": "open_answer", "unit_index": 0, "text": "Exemple de réponse."}],
    "is_truncated": false,
    "question": {"id": "47", "prompt": "Pourquoi ?", "url": "/questions/47-pourquoi"},
    "form": {"id": "4", "name": "Exemple d’enquête", "url": "/forms/4"},
    "url": "/forms/4/contributions/9007199254742993#answer-9007199254741993"
  }],
  "page_size": 20,
  "has_next": true,
  "next_cursor": "opaque",
  "previous_cursor": null,
  "first_cursor": "opaque-premiere-page",
  "expires_at": "2026-10-20T15:10:00+00:00",
  "window": {"document_limit": 50, "retrieval_depth": 50, "answer_count": 48, "exhaustive": false},
  "warnings": []
}
```

Les identifiants historiques sont tous des chaînes JSON ; `rank` et `unit_index`
sont des entiers ordinaires. La question est toujours fournie, y compris pour
« oui » ou « non ». Les textes restent fidèles aux sources applicatives, avec
1000 caractères au total par carte et `is_truncated`. Les champs « Autre » gardent
leur type/indice et leur ordre source. Une carte représente une réponse, au rang
de son premier document retenu ; les scores ne sont pas additionnés. Plusieurs
segments ne créent pas de cartes supplémentaires. Des réponses distinctes avec
le même texte restent distinctes.

Ni auteur ni identité personnelle ne sont nécessaires à ce contrat : ils ne sont
pas exposés. Aucun JSONB interne, titre/métadonnée d'import, hash, segment, vecteur,
distance ou score ne parvient au navigateur. Les liens sont construits depuis
les relations applicatives vérifiées. Le contenu HTML éventuel de la source est
une chaîne brute, à rendre comme texte par React.

### Fenêtre, curseurs et sources retirées

La recette initiale conserve une profondeur de 50 par branche et le top 50
documentaire fusionné. Ce sont des paramètres de SEARCH-003, pas une limite
structurelle du contrat API. `page_size` ne change jamais la profondeur.
`window.answer_count` compte les cartes initialement validées de cette fenêtre,
sans prétendre dénombrer toutes les correspondances du corpus.

La sélection est conservée dans un cache mémoire LRU : TTL absolu 600 s,
256 instantanés au plus, 16 Mio de charge utile JSON au plus (hors overhead Python).
Le cache contient uniquement des références/empreintes, les paramètres de
navigation et les versions ; aucun texte complet, requête brute, nom ou vecteur.
Un seul processus backend possède ce cache et son modèle. L’identité d’une
sélection inclut `question_id` : les curseurs ne sont pas interchangeables entre
questions ni avec la recherche générale.

La page suivante, la précédente, la première et le rechargement d'un curseur
relisent seulement un lot applicatif ; aucun encodage, lexical, ANN ou RRF.
Les curseurs sont liés à la requête normalisée et à la taille de page ; ne pas les
décoder ni les construire côté React. Le champ `first_cursor` permet d'établir
une URL de première page figée, y compris sans JavaScript.

Une source devenue absente ou incohérente est omise avec
`warnings=[{"code":"source_unavailable","count":1,"message":"…"}]`.
Les cartes suivantes ne sont pas déplacées pour remplir les places manquantes :
le rang reste stable et une page peut être plus courte, voire vide avec un lien
suivant. `has_next` parle des positions restantes de l'instantané, pas du corpus.
Le compteur d'avertissement cumule les omissions initiales et celles de la page
courante, pas toutes les suppressions découvertes dans d'autres pages.

`state="empty"` signifie un vrai classement vide. `state="sources_unavailable"`
signifie que des sources classées ont été retirées. Une incohérence importante
(au moins cinq cartes contrôlées et au moins la moitié incohérentes) bloque la
recherche en 503 et invalide les instantanés ; c'est un seuil opérationnel prudent,
pas une preuve statistique d'intégrité du corpus. Un changement de génération ou
de recette invalide également la navigation ; les corpus sont supposés immuables
pendant l'exécution. Aucun snapshot transactionnel distribué n'est promis.

### Erreurs

```json
{"error":{"code":"search_expired","message":"Cette sélection a expiré. Relancez la recherche.","retryable":false},"request_id":"identifiant-technique"}
```

| HTTP | Codes et comportement |
|---|---|
| 200 | `idle`, `results`, `empty` ou `sources_unavailable`, distincts des pannes |
| 422 | `invalid_query`, `invalid_cursor` ; corriger les paramètres |
| 410 | `search_expired` ; expiration, éviction, redémarrage ou génération invalidée ; relancer sans curseur |
| 503 | `search_not_ready`, `search_unavailable`, `search_metadata_unavailable`, `search_busy` ; pas de fallback |
| 504 | `search_timeout`, `search_encoding_timeout`, `search_sql_timeout`, `search_metadata_timeout`, `search_cancelled` |
| 500 | `search_internal_error` ; aucune trace interne exposée |

`search_busy` inclut `Retry-After: 1`. Les réponses portent `private, no-store`,
un identifiant de requête et `noindex`. L'échéance totale de 18 s est partagée entre
admission, encodage, SQL, fusion, hydratation et sérialisation ; le client SSR reste
borné à 20 s. Le timeout n'accorde pas un nouveau budget à l'hydratation.
Une branche défaillante ne peut pas être présentée comme une recherche hybride
complète ; une branche exécutée avec succès mais vide reste valide.

Voir [configuration et exécution locale](search-local.md) et
[rapport SEARCH-005](rapport-search-005.md). OpenAPI et
`frontend/contracts/api.generated.ts` décrivent le contrat utilisé par React SSR.

## Consommation React SSR

`/recherche` possède un seul formulaire GET et une liste de réponses. Sans `q`,
aucun appel API. La première recherche réussie avec `first_cursor` entraîne une
unique redirection **303** vers `/recherche?q=…&cursor=…` (et `page_size` si différent
de 20). La relecture du curseur hydrate la première page sans relancer H1. Cette
URL conserve le classement au rechargement et au retour de contribution. Une URL
portant déjà un curseur ne provoque jamais de nouvelle redirection.

Les liens suivant/précédent/premier conservent la requête, la taille de page et
le curseur API. Le formulaire principal lance une nouvelle recherche sans curseur.
Un classement expiré affiche 410, avec relance **manuelle** sans curseur. Les
autres erreurs gardent leur statut HTTP, des messages publics maîtrisés et un
réessai explicite. Les avertissements de sources ne sont pas assimilés à un état
vide. Toutes ces actions fonctionnent sans JavaScript, sans stockage navigateur.
La page garde `private, no-store`, `noindex, follow` et sa canonical fixe, y compris
pour les erreurs rendues et la redirection de stabilisation.

Les anciens endpoints `/api/v1/search/answers` et `/api/v1/search/catalog` sont
supprimés et répondent 404. Aucun adaptateur de compatibilité ne les remplace.
Les lectures documentaires par question, formulaire, contribution et auteur,
ainsi que les statistiques, sont conservées. Les structures SQL historiques
attendent l'audit de dépendances SEARCH-006 : aucune migration dans SEARCH-005.
