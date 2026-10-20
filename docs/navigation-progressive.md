# Navigation et chargement progressif

20 octobre 2026 — modification frontend locale sur Hal9000.

## Comportement

Un composant commun `ListNavigation` remplace les liens de pagination isolés :

- Recherche et réponses aux questions : « Afficher davantage de réponses ».
- Auteur : « Afficher davantage de contributions ».
- Retour au début lorsqu'un curseur est présent ; la recherche conserve aussi
  le lien précédent fourni par son contrat.
- Contributions complètes : précédente/suivante en haut et en bas, sans cumul
  des questionnaires complets dans une seule page.

Avec JavaScript, le contrôle charge le prochain lot et l'ajoute aux éléments
existants. L'ordre initial est conservé. La déduplication porte sur les IDs
historiques, sans fusionner des réponses différentes ou leurs contenus. Les
contributions d'un même auteur sont regroupées sous leur formulaire, y compris
lorsqu'il réapparaît dans un lot suivant.

Il n'y a aucun chargement automatique au scroll. Le visiteur garde le contrôle
et le pied de page reste accessible. Sans JavaScript, les contrôles sont des
liens HTML vers les lots suivants, utilisables au clavier, en nouvel onglet
et par les mécanismes habituels du navigateur.

## URL, historique et mémoire

Chaque chargement met à jour l'URL avec le curseur du dernier lot. Une URL copiée
ou rechargée affiche ce lot seul. Le HTML SSR reste celui d'une page valide,
jamais une page vide attendant JavaScript.

`useProgressivePage` garde les lots précédents dans une mémoire propre à l'onglet,
indexée par l'entrée d'historique et le contexte de la recherche/question/auteur.
Au retour depuis une contribution, la liste cumulative et la position de lecture
sont restaurées. Cette mémoire est limitée à 16 entrées, 10 minutes et 4 Mio de
charge utile JSON cumulée ; ce plafond ne représente pas une mesure exacte du
tas JavaScript. Les listes actuellement affichées peuvent continuer à grandir
par action explicite, même au-delà du budget de restauration.

Aucun contenu n'est écrit dans localStorage, sessionStorage ou des cookies.
Aucun cache de ces listes n'est créé côté SSR. Après fermeture/rechargement
complet, expiration ou éviction, la navigation reste fonctionnelle et affiche
le lot correspondant à l'URL ; la restauration de tous les lots n'est plus garantie.

## Chargement, erreurs et accessibilité

Le chargement supplémentaire est annoncé près du bouton, avec état occupé et
protection contre les clics répétés. Le bandeau global ne décale pas la liste
pendant cette opération. Le premier nouvel élément reçoit le focus sans
imposer de défilement, et les compteurs annoncent uniquement le nombre affiché.

Les navigations obsolètes utilisent les annulations React Router existantes.
Une erreur ne supprime pas les éléments déjà lus. Les réessais restent explicites.
Pour la recherche, les pages suivantes réutilisent les curseurs de la sélection
conservée : aucun encodage ni classement supplémentaire. En cas d'expiration,
un message et une action de relance sont présentés. Une erreur n'est pas
présentée comme la fin normale de la sélection.

Les anciens contrats HTTP, statuts SSR, BIGINT sous forme de chaînes, liens
ancrés, règles d'anonymat, `private, no-store` et règles de référencement restent
conservés. Aucun changement FastAPI/PostgreSQL, du corpus ou du moteur hybride.
La recette réelle reste bornée et en lecture seule.

## Réutilisation

Fichiers dans `frontend/app/features/pagination/` :

- `list-navigation.tsx` et `pagination.module.css` : navigation HTML commune.
- `use-progressive-page.ts` : cumul, historique, restauration et limites mémoire.
- `merge-pages.ts` : fusion ordonnée des réponses, résultats et groupes d'auteur.

Aucune nouvelle dépendance. Le composant Pagination d'Ark UI est orienté pages
numérotées et total connu ; le composant local reçoit directement les URL opaques
fournies par les contrats existants.

## Vérification

- 156 tests unitaires frontend réussis, dont fusion, déduplication et ordre.
- 61 tests navigateur réussis, dont cumul et retour depuis une contribution,
  restauration du défilement, focus, rechargement du dernier lot, fonctionnement
  sans JavaScript, expiration explicite et absence de nouveau classement.
- TypeScript, Biome, builds normaux/de test et 6 tests SSR/build sans réseau réussis.
- Corpus local réel : question 159, passage de 20 à 40 réponses Autre puis
  contribution et retour avec position restaurée ; recherche, passage de 2 à
  4 réponses dans la même sélection ; sans JavaScript, ouverture du lot suivant
  de 20 réponses. Aucun changement des bases ni du moteur pour cette recette.

La recette avec lecteur d'écran complet reste à effectuer. Les vérifications
clavier et automatisées ne constituent pas une validation d'accessibilité complète.
