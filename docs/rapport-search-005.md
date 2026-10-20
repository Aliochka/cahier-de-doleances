# SEARCH-005 — Nouvelle recherche React SSR

Date : 20 octobre 2026. Réalisation et validation exclusivement sur Hal9000.

## 1. Résultat

`/recherche` utilise désormais exclusivement `GET /api/v1/search`, le moteur
hybride SEARCH-003 intégré par SEARCH-004. Les onglets Réponses / Questions et
enquêtes ont disparu. Les anciennes routes générales, leurs services, schémas,
clients et tests de contrat ont été retirés lors de cette bascule locale.

La recherche, la consultation d'une contribution ancrée, le retour arrière, les
pages suivantes/précédentes et la relance après expiration fonctionnent avec ou
sans JavaScript. Aucune modification du corpus, des embeddings ou des structures
PostgreSQL, aucune migration, aucun déploiement, aucun fallback ou feature flag.

## 2. Organisation de la page et choix UX

L'accueil comporte un titre, une explication du corpus et deux exemples de saisie
naturelle. Un seul formulaire GET propose « Votre question ou votre sujet » et
« Rechercher ». Le libellé, l'aide et les erreurs sont associés au champ. La saisie
reste un brouillon jusqu'à Entrée ou à la soumission ; aucun appel par frappe.

La page respecte les paramètres du contrat : `q` normalisé NFC et espaces
extérieurs retirés, maximum 512 caractères avant normalisation ; `page_size` entre
1 et 20 ; `cursor` opaque. Les paramètres inconnus, répétés et les sélecteurs
historiques sont refusés en 422. Une saisie vide présente l'accueil sans appel API.
Les contraintes lexicales complémentaires restent validées par FastAPI ; aucune
syntaxe booléenne globale n'est promise.

Les cartes privilégient la lecture :

- Question toujours visible, y compris pour une réponse aussi courte que « Non ».
- Réponse principale en citation, corps plus grand, interligne ample, paragraphes
  et sauts de ligne conservés ; colonne de lecture limitée au jeton existant.
- Champs « Autre » séparés et identifiés, sans fusion de leurs textes.
- Mention explicite « Extrait abrégé » lorsque l'API indique une troncature.
- Formulaire en contexte secondaire et lien « Lire la contribution complète »
  utilisant exactement l'URL ancrée de l'API.

Aucun résumé, surlignage généré, filtrage des réponses courtes, identité d'auteur,
score ou détail vectoriel n'est ajouté. React échappe les textes ressemblant à du
HTML. Les BIGINT restent des chaînes, sans conversion en `number`. Les cartes
gardent une zone d'actions simple, extensible ultérieurement, sans bouton Explorer
inactif. La navigation Enquêtes et les autres pages documentaires restent présentes.

Titres h1/h2/h3, listes sémantiques, annonces courtes de résultats, alertes,
libellés et liens explicites réutilisent les composants et couleurs du site. Le
chargement global et l'annulation des navigations obsolètes sont conservés. Une
nouvelle saisie peut être soumise pendant une recherche en cours. Aucun effet ni
animation supplémentaire, aucune refonte graphique globale.

## 3. Architecture et composants

```text
Navigateur, formulaire GET / liens HTML
    → loader React Router SSR /recherche
        → client serveur, API_BASE_URL privée, signal d'annulation, délai 20 s
            → FastAPI GET /api/v1/search
                → SEARCH-003 : BGE-M3 persistant + cahier_rag, classement H1
                → cahier_doleances_local : contenus publics et liens vérifiés
                → instantané mémoire : références et curseurs
        → HTML complet, utilisable sans JavaScript
```

Le navigateur ne contacte aucune base et ne reçoit aucune URL PostgreSQL. Les
lectures publiques n'envoient pas les cookies de compte. La validation du JSON
vérifie notamment IDs, types de textes, liens locaux cohérents et curseurs. Les
erreurs structurées ne transmettent au rendu qu'un code reconnu et le statut ;
les messages bruts et identifiants techniques restent exclus de l'affichage.

| Composant | Intervention SEARCH-005 |
|---|---|
| `frontend/app/routes/search.tsx` | Loader hybride unique, validation, stabilisation de l'URL, accueil et erreurs |
| `features/search/search-controls.tsx` | Formulaire GET unique, suppression des sélecteurs de catégorie |
| `features/search/search-results.tsx` | Cartes question/réponse/formulaire, extraits, alertes et trois liens de pagination |
| `features/search/search-url.ts` | URL contenant seulement q, taille éventuelle et curseur |
| `lib/api.ts`, `lib/api.server.ts`, `lib/api-errors.ts` | Client et validation hybrides, erreur 410, retrait des clients historiques |
| Contrats OpenAPI et TypeScript | Régénérés depuis FastAPI, sans routes ni modèles historiques |
| `app/app.py` | Désenregistrement de l'ancien routeur général ; route hybride conservée |
| `app/routers/api_search.py` | Supprimé |
| `app/schemas/search.py` | Supprimé |
| `app/services/search.py` | Supprimé |
| `tests/test_api_search.py` | Supprimé ; contrat remplacé par les tests hybrides SEARCH-004 et les nouveaux tests React |
| `scripts/test_search_performance.py` | Supprimé : diagnostic SQL de l'ancien moteur, sans consommateur restant |

Conservés : moteur SEARCH-003, cycle de vie SEARCH-004, hydratation et cache,
routes documentaires, services Questions/Formulaires/Contributions/Auteurs,
statistiques, anonymat, authentification, composants communs de navigation et
d'erreur. `app/search_errors.py` reste nécessaire aux lectures documentaires.
Aucune dépendance frontend supplémentaire. Les dépendances Python du moteur
restent celles de SEARCH-004 ; aucune dépendance vers la génération ou un reranker.

## 4. Pagination et stabilité

La première requête sans curseur calcule H1 une seule fois. Si la réponse fournit
`first_cursor`, le loader effectue une unique redirection **303** vers l'URL portant
ce curseur, la requête et la taille de page. La requête de destination réhydrate
le premier lot depuis l'instantané, sans encodage ni lexical, vectoriel ou RRF.
Cela ajoute une lecture applicative courte à l'arrivée et évite de recalculer H1
au retour d'une contribution ou au rechargement de la première page.

Les requêtes déjà munies d'un curseur ne sont jamais redirigées. Les liens HTML
« Page suivante », « Page précédente » et « Première page » reprennent les valeurs
API. L'URL suffit à la navigation : pas de localStorage, sessionStorage ou cache
React persistant. Une nouvelle soumission efface le curseur et crée explicitement
une nouvelle sélection. Le réessai d'une erreur de page conserve son curseur tant
qu'il est valable ; une expiration propose une relance manuelle sans curseur.

Les limites SEARCH-004 restent inchangées : cache LRU mémoire, TTL absolu dix
minutes, 256 instantanés, charge utile maximale 16 Mio. Une éviction ou un
redémarrage peut donc provoquer 410 avant dix minutes. La navigation ne prolonge
pas la durée de vie.

L'interface ne fige pas la profondeur à 50 : elle consomme les curseurs et la
sélection fournie. Le profil H1 initial reste profondeur 50 / top 50 documentaire,
avec éventuellement moins de réponses distinctes. Le nombre de cartes de la
page n'est pas présenté comme un total du corpus. La fin de sélection invite à
préciser ou reformuler, sans annoncer un parcours exhaustif.

## 5. États, HTTP, confidentialité et SSR

| Situation | Rendu |
|---|---|
| Sans requête | Accueil 200, aucun appel au moteur |
| Résultats | 200, sélection par pertinence, contexte et liens |
| Vrai classement vide | 200, message d'absence et invitation à reformuler |
| Sources retirées | Avertissement distinct ; page éventuellement vide, liens de pagination conservés |
| Requête ou curseur invalide | 422, message public et correction/relance explicite |
| Instantané expiré | 410, « Cette sélection a expiré », relance manuelle |
| Moteur indisponible ou saturé | 503, recherche indisponible, aucun secours historique |
| Délai dépassé | 504, réessayer ou préciser la question |
| Erreur interne | 500, message public sans trace technique |
| Réponse JSON API inutilisable | 502, message public de réponse inutilisable |

Le loader conserve les statuts pour les réponses SSR, sans transformer les erreurs
en pages 200. Une panne n'est pas assimilée au vide. Après une erreur, aucun ancien
lot n'est présenté comme résultat de la nouvelle demande. Les avertissements API
reconnus déclenchent un message maîtrisé de sources devenues indisponibles.

Accueil, résultats, redirection et erreurs gérées conservent `Cache-Control:
private, no-store`, `X-Robots-Tag: noindex, follow`, la meta robots et la canonical
fixe `https://cahierdedoleances.fr/recherche`. La page n'est pas prérendue au build ;
son contenu essentiel est attendu par le loader avant le rendu HTML. La recherche
utilise l'échéance API existante de 18 s, sous le délai SSR de 20 s.

## 6. Tests automatisés

Exécution locale après la bascule :

| Vérification | Résultat |
|---|---|
| Pytest backend sur bases isolées `_test` | **315 passés**, 1 ignoré, 7 sous-tests passés |
| Vitest frontend | **131 passés**, 15 fichiers |
| Playwright Chromium, ensemble du site | **49 passés**, dont 11 pour Recherche |
| Tests du build SSR hors réseau | **6 passés** |
| TypeScript / génération des types de routes | Réussi |
| Biome frontend | Réussi |
| Ruff, script de recette et fichiers Python concernés | Réussi |
| Export OpenAPI `--check` et contrôle des types générés | Réussis |
| Builds frontend normal et test, hors réseau | Réussis |

Les tests remplacent les anciens contrats plutôt que de les maintenir. Ils
couvrent normalisation/validation, formulaire GET, absence d'onglets, ordre des
cartes, réponses courtes et longues, textes « Autre », HTML échappé, BIGINT,
ancres, paramètres de pagination et profondeur non figée. Ils vérifient la
redirection initiale unique, la stabilité de l'URL, l'expiration sans recalcul,
la relance manuelle, les erreurs HTTP et l'absence d'informations privées.

La suite backend conserve les vérifications SEARCH-004 de classement, segments,
provenance, lecture en lot, curseurs/LRU/TTL, anonymat, délais et indisponibilités.
Elle vérifie maintenant le 404 des anciens endpoints et leur absence d'OpenAPI.
Les tests documentaires et statistiques passent après retrait du routeur.

La fixture d'ingestion ignorée nécessite une base dédiée
`GDN_IMPORT_TEST_DATABASE_URL` ; elle n'a pas été activée pour ce chantier frontend.
Aucune fixture n'a été écrite dans les corpus locaux de travail. Les avertissements
préexistants de dépréciation TestClient et d'Operation ID des routes SEO hors v1
ne bloquent pas les tests ; l'export v1 contrôlé reste déterministe et valide.

## 7. Observations navigateur réelles

La recette `scripts/smoke_search_browser.py` lance FastAPI sur `127.0.0.1:8015` et
le build React SSR normal sur `127.0.0.1:4185`, puis arrête ces processus. Elle
utilise SEARCH-003, BGE-M3 existant sur le GPU Hal9000, le rôle lecteur provisionné,
`cahier_rag` et `cahier_doleances_local`. Le script navigateur associé se trouve
dans `frontend/tests/smoke-search-local.mjs`, hors du bundle applicatif.

Parcours vérifié **avec JavaScript puis sans JavaScript** :

1. Saisir une question et soumettre le formulaire ; 20 cartes publiques rendues.
2. Vérifier l'URL de première page avec curseur.
3. Ouvrir la contribution complète et contrôler l'existence de l'ancre ainsi que
   sa position réelle près du haut du viewport, sans se limiter à son href.
4. Revenir à la recherche, avancer, recharger et retrouver la première page.
5. Vérifier au compteur du vrai worker qu'une seule recherche H1 a eu lieu.
6. Expirer le cache, constater 410 sans recalcul automatique et relancer explicitement.
7. Vérifier le rendu vide 200 à l'aide d'un classement vide injecté dans la recette.

**Quatre appels H1 réels au total** : une soumission et une relance par mode.
**Zéro appel H1 lors des navigations paginées.** Le modèle a gardé la même instance
pendant toute la recette, avec un chargement initial de **4,86 s**.

Les contrôles d'expiration et de vide sont délibérément distingués : l'expiration
avance de 601 s l'horloge injectable du cache, sans modifier sa TTL ; elle emprunte
ensuite le vrai chemin 410. Le vide injecte temporairement un `Ranking` vide dans
l'instance de recette, sans recherche supplémentaire. H1 n'impose pas de seuil
minimal de proximité ANN : un terme improbable ne garantit pas zéro résultat.
Aucun seuil, flag, endpoint de contrôle ou comportement simulé n'a été ajouté à
l'application. Les sources retirées et pannes sont vérifiées avec l'API synthétique,
sans altérer les bases réelles.

Inspection visuelle : page réelle dans la palette existante, largeur de lecture
contenue et formulaire lisible ; carte synthétique vérifiée séparément pour les
paragraphes, le contexte et la mention d'extrait. Tests à 320 px et texte agrandi
à 200 % sans débordement horizontal. Les parcours documentaires au clavier,
ancres et navigation arrière passent. Pas de qualification exhaustive RGAA ni de
test avec lecteur d'écran réel dans ce ticket.

### Mesures ponctuelles, non garanties publiques

| Étape | Observations des quatre classements réels |
|---|---|
| Encodage BGE-M3 | 10,3–10,7 ms |
| Lexical | 2,530–2,600 s |
| Vectoriel | 48,1–51,4 ms |
| Fusion | 0,50–0,62 ms |
| Hydratation initiale | 16,9–20,7 ms |
| Total API nouveau classement | 2,619–2,696 s |
| Total API d'une page en cache | 7,8–9,8 ms |
| Soumission → affichage navigateur, JS activé / désactivé | 2,84 s / 2,71 s |
| Page suivante → affichage navigateur, JS activé / désactivé | 89 ms / 71 ms |

Les mesures navigateur incluent SSR, redirection initiale éventuelle et transport
local. Les étapes API sont observées côté FastAPI. Les classements vides injectés
sont exclus de ces chiffres. L'ordre de grandeur est cohérent avec la recette
SEARCH-004 ; ces quelques passages sur une question, en environnement chaud, ne
mesurent ni la charge concurrente, ni le rappel, ni les performances CPU/Wallace.
Aucun benchmark lourd n'a été exécuté.

## 8. Limites et suite SEARCH-006

La réalisation suit SEARCH-002 et le contrat SEARCH-004. La précision
supplémentaire est la redirection initiale 303 portant `first_cursor` : une lecture
en cache de plus en échange d'un retour et d'un rechargement stables, y compris
sans JavaScript. Le moteur, sa profondeur initiale et ses algorithmes ne changent pas.

Le cache reste local à un processus, volatile et borné ; ouvrir la même URL après
expiration nécessite une action explicite. Une URL sans curseur désigne toujours
une nouvelle recherche. Les vingt cartes et les extraits longs peuvent demander
du défilement : la largeur et l'interligne privilégient la lecture ; aucune
pagination numérique ou illusion de total exhaustif n'est introduite.

SEARCH-006 devra auditer les dépendances réelles avant toute suppression SQL :
colonnes tsvector, fonctions/triggers de maintenance, index FTS, trigram et index
partiels issus de l'ancienne recherche. Certaines structures servent encore aux
rubriques documentaires, compteurs, imports et migrations historiques. Elles sont
toutes restées intactes ici. Les migrations historiques ne sont pas réécrites.
Les journaux et rapports historiques sont conservés comme tels ; les documents
de lancement et de contrat actifs décrivent désormais seulement la nouvelle API.

L'élargissement de profondeur, le filtre `question_id`, l'exploration et la
qualification d'un déploiement Wallace restent des chantiers distincts, sans
implémentation anticipée. Les contrôles avec lecteurs d'écran et d'autres
navigateurs restent à compléter avant une éventuelle mise en production.

## 9. Documents et reproduction

- [Contrat HTTP et consommation SSR](api-search.md).
- [Configuration, lancement et recette locale](search-local.md).
- [Documentation frontend](../frontend/README.md#recherche-hybride-unique-search-005).
- [Architecture SEARCH-002](architecture-search-002.md).
- [Rapport backend SEARCH-004](rapport-search-004.md).

SEARCH-005 s'arrête à cette bascule locale, ses validations et ce rapport.
Aucune intervention sur Wallace, aucun démarrage de SEARCH-006.
