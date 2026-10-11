# Frontend en développement

Ce socle ne remplace pas l'interface Jinja/HTMX en production. Il ne contient
aucun client FastAPI, proxy API, compte utilisateur ni accès PostgreSQL.

## Installation et commandes

Node **24.21.0 LTS** est fixé dans `.nvmrc` et repris par GitHub Actions et
Netlify. Installer cette version (par exemple `nvm install && nvm use` dans ce
dossier). Le `packageManager` de `package.json` fixe pnpm **12.11.2**.
Avec une installation Node fournissant Corepack :

```sh
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

Si Corepack est absent, l'installer selon sa
[documentation officielle](https://github.com/nodejs/corepack#installation), puis
activer pnpm. Utiliser uniquement pnpm dans ce dossier ; le backend conserve ses
outils Python. Le serveur de développement écoute localement, sans exposer une
nouvelle interface sur le LAN.

```sh
pnpm check          # lint, format et imports, sans modification
pnpm lint
pnpm format:check
pnpm check:fix      # corrections locales
pnpm typecheck     # génération des types React Router puis TypeScript strict
pnpm test          # Vitest, jsdom et React Testing Library
pnpm build         # client, serveur SSR et accueil pré-rendu
pnpm build:offline # même build, connexions externes interdites
pnpm test:build    # contrôler HTML pré-rendu, SSR/404, CSS et adaptateur Node
pnpm start         # servir le build avec l'adaptateur Node portable
pnpm exec playwright install chromium
pnpm test:e2e      # Chromium, hydratation, styling, clavier et contenu sans JS
```

Sur Linux, Playwright peut demander ses dépendances système : utiliser
`pnpm exec playwright install --with-deps chromium` sur une machine de test.
Les navigateurs ne sont nécessaires qu'aux tests E2E. Le test de build suppose
qu'un build a été produit auparavant. Le garde réseau de test permet le loopback
car React Router 8 pré-rend via son propre serveur temporaire ; il interdit les
connexions TCP et `fetch` externes, notamment vers Wallace. Il ne fait pas partie
du bundle applicatif. Aucun service backend n'est nécessaire à ces commandes.

## Organisation

```text
app/
  root.tsx                 document français, assets et erreurs sûres
  routes.ts                configuration officielle du routage framework
  routes/home.tsx          accueil temporaire, titre et description HTML
  routes/dev.components.tsx atelier des composants, développement uniquement
  components/layout/       Header, Footer, PageContainer
  components/ui/           primitives natives, Tabs, Dialog, Disclosure
  styles/global.css        ordre des couches CSS
tests/                     setup RTL et contrôles des artefacts de build
e2e/                       tests navigateur
```

Les futurs composants métier resteront proches de leur fonctionnalité dans
`app/features/`, et le client API ira dans `app/lib/`. Ces dossiers ne sont pas
créés tant qu'ils ne sont pas utilisés. Pas d'alias d'import ni de gestionnaire
d'état supplémentaire. Les tests composants sont placés à côté du code testé.

## Rendu et styles

[React Router 8 en mode framework](https://reactrouter.com/start/framework/rendering)
compile les bundles client et serveur avec Vite. `ssr: true` reste activé ; seule
`/` figure dans `prerender`. L'accueil n'a ni loader ni appel réseau : son contenu
essentiel et ses métadonnées figurent dans `build/client/index.html`. Les futures
pages dynamiques pourront utiliser le SSR sans pré-rendre les contributions.
Les entrées client/serveur officielles par défaut sont conservées ; `isbot` est
requis par l'entrée serveur. L'adaptateur Node local sert aussi à tester le SSR.
Les éléments `<title>` et `<meta>` React 19 sont utilisés selon la
[recommandation React Router](https://reactrouter.com/start/framework/route-module#meta).
Les erreurs racine ne montrent pas les détails internes et portent `noindex`.

[Panda CSS](https://panda-css.com/docs/get-started/vite) utilise son plugin Vite
officiel et génère les utilitaires typés dans `styled-system/`. `prepare` les
génère à l'installation pour TypeScript et l'éditeur ; Vite extrait le CSS au
build. Ce dossier et les sorties de compilation ne sont pas versionnés.
Les tokens et couleurs sémantiques de `panda.config.ts` reprennent le thème
archive de `app/static/css/variables.css` du backend : papier, encre, bleu
`#203A8F`, rouge `#A83A3A`, typographie de machine à écrire avec repli local.
Aucune police distante n'est chargée. Les presets Panda officiels fournissent
les utilitaires ; les fondations du projet restent limitées aux besoins actuels.

[Ark UI](https://ark-ui.com/docs/overview/getting-started) fournit les interactions
accessibles, sans style visuel imposé. `Disclosure` associe sa primitive
Collapsible aux classes Panda : contenu ouvert côté serveur, états ARIA et
interaction clavier après hydratation. Tabs et Dialog encapsulent les primitives Ark pour la navigation clavier, le
focus et les relations ARIA. Biome est le seul outil de lint et formatage du
frontend, avec ses règles recommandées et les fichiers générés exclus.

## Netlify et CI

L'[intégration officielle Netlify](https://docs.netlify.com/build/frameworks/framework-setup-guides/react-router/)
est localisée dans `vite.config.ts` et `netlify.toml`, sans API Netlify dans les
composants. L'adaptateur produit une fonction **Node**, sans Edge Function. Son
option `preferStatic` sert l'accueil pré-rendu avant d'invoquer le SSR. Aucun
service payant ni fonction applicative supplémentaire n'est ajouté.

Pour une future prévisualisation, régler **Base directory** et **Package
directory** sur `frontend` dans Netlify afin d'utiliser le `netlify.toml` local,
le lockfile et `.nvmrc`. Build : `pnpm build` ; publication : `build/client`.
La version majeure du runtime Functions suit Node 24 du build selon Netlify.
Ne pas fournir de secrets backend ni de variables `VITE_*` privées. La mesure
des crédits gratuits et du coût SSR, le proxy API, les DNS et la bascule en
production sont hors FRONT-001. Aucun déploiement n'est effectué ici.

`.github/workflows/frontend.yml` ajoute un contrôle stable **Frontend checks**
sur les PR vers `main` et les pushes sur `main`. Il termine aussi pour les
changements documentaires, sans installer les dépendances ou Chromium si aucun
fichier frontend pertinent n'a changé. Il utilise le cache pnpm et le lockfile
figé, puis Biome, TypeScript, Vitest, build hors réseau, artefacts SSR et
Playwright. Le workflow Python existant est inchangé. Les PR externes n'obtiennent
aucun secret supplémentaire. Les versions exactes installées sont dans
`package.json` et `pnpm-lock.yaml`.

Prochaines tâches : FRONT-003 (client API, loaders/erreurs) et CONTRACT-001
(types générés depuis OpenAPI). Aucune n’est entamée ici.

## Design system

L’identité archive conserve le papier clair, le bleu et le rouge tampon. La
police système sert à la lecture ; la famille machine à écrire marque les titres
et l’identité sans charger de police externe. Le contenu est limité à 1 100 px,
avec un token `reading` plus étroit pour les textes longs.

Les composants utilisent les tokens sémantiques (`surface`, `text`, `muted`,
`primary`, `danger`, etc.) dans `panda.config.ts`, plutôt que des couleurs
littérales. Les recettes Panda `cva` définissent les variantes simples.

| Composant | Usage et variantes |
| --- | --- |
| Button | Bouton natif ; `primary`, `secondary`, `quiet`, `destructive` ; tailles `small`, `medium`, `large` ; `loading` conserve le libellé et désactive l’action. |
| Input | Champ natif avec `label`, `description` et `error` ; conserve `name`, `type`, `required`, `disabled` et les attributs HTML. |
| Card | Article visuel ; donner un titre et éventuellement `aria-labelledby`. Aucune interaction implicite. |
| Tabs | `Root`, `List`, `Trigger`, `Content` ; variantes `underline`, `enclosed`. `value` / `onValueChange` permettent un contrôle externe futur par l’URL. |
| Dialog | `Root`, `Trigger`, `Content`, `CloseTrigger` ; `Content` exige un `title`, accepte une `description`. Utiliser `asChild` sur les déclencheurs avec Button. |
| Alert | `info`, `success`, `warning`, `error` ; aucune annonce par défaut. `announcement="polite"` donne un statut, `"assertive"` une alerte urgente. |
| Skeleton | `line` ou `block`, décoratif et masqué aux lecteurs d’écran ; le parent décrit le chargement et porte `aria-busy` si nécessaire. |

Les composants acceptent leurs attributs HTML et `className`. Ark UI intervient
pour les comportements complexes ; un bouton ou champ simple reste natif.
Pour ajouter un composant, partir du HTML approprié, utiliser les tokens Panda,
limiter ses propriétés et tester son comportement accessible. La logique métier
restera dans les futures fonctionnalités, pas dans `components/ui/`.

`root.tsx` assemble le header, un unique main avec lien d’évitement et le footer.
Recherche et Enquêtes sont indiquées « À venir », sans lien vers une fausse page.

### Atelier et accessibilité

Lancer `pnpm dev`, puis ouvrir `/dev/components`. La configuration des routes
inclut l’atelier uniquement lorsque `NODE_ENV` vaut `development`. Il est absent
du manifeste serveur et des bundles JavaScript de production, hors pré-rendu.
Les tests de build et Playwright vérifient une réponse HTTP **404** en production.
Les styles partagés peuvent naturellement rester dans le CSS extrait.

Après `pnpm build:offline`, `pnpm test:e2e` démarre le serveur de production sur
4173 et le serveur de développement sur 4174. Chromium vérifie SSR/hydratation,
clavier des onglets, piège/restauration du focus des dialogues, lien d’évitement,
réduction des animations et absence de débordement à 320, 768 et 1 280 px.

Vérifier aussi manuellement Tab/Maj+Tab, Échap, les noms et descriptions avec un
lecteur d’écran, le zoom à 200–400 % et les textes longs. Les tests ciblés et Ark
UI ne constituent pas une certification WCAG/RGAA. Toute nouvelle combinaison
de couleurs doit conserver les contrastes AA ; ne pas supprimer le focus visible.

## Contrat FastAPI / TypeScript

FastAPI reste la source de vérité. `contracts/openapi.json` contient uniquement
les routes `/api/v1` et la fermeture transitive de leurs composants référencés.
`contracts/api.generated.ts` est généré automatiquement, sans édition manuelle.
Ces **deux fichiers doivent être commités** après toute évolution de l’API.

Depuis `frontend/`, avec l’environnement Python du backend activé :

```sh
pnpm contract:generate      # export Python puis types TypeScript
pnpm contract:check         # vérifie les snapshots et leur présence dans HEAD
pnpm contract:types:check   # vérification Node seule, sans Python
pnpm typecheck             # compile aussi le contrat et son exemple d’utilisation
```

`scripts/export_openapi.py` appelle `app.openapi()` sans serveur HTTP. Son
processus utilise exclusivement des réglages synthétiques, désactive dotenv et
interdit les connexions réseau et psycopg2. La génération TypeScript réutilise
aussi le garde réseau Node des tests de build. Les créations d’Engine SQLAlchemy
restent paresseuses ; aucune base active ou secret n’est nécessaire. Le JSON
est trié, encodé en UTF-8 et n’inclut aucun horodatage. Les avertissements de
doublons des anciennes routes HTML sont filtrés lors de l’export ; les identifiants
d’opération `/api/v1` doivent être uniques et sont vérifiés explicitement.

Pour ajouter une réponse, définir un modèle Pydantic explicite et le déclarer
sur la route FastAPI enregistrée, avec un `operation_id` stable. Régénérer,
vérifier et commiter les deux artefacts. Les types `components`, `paths` et
`operations` permettent au futur client de sélectionner les réponses et erreurs
sans recopier les modèles. Voir `app/contract.test.ts`. Les identifiants BIGINT
restent des chaînes ; les valeurs nulles et champs facultatifs sont conservés.
Les paramètres de chemin décrits comme entiers dans OpenAPI restent numériques
dans le type généré : FRONT-003 devra préserver les identifiants chaînes lors de
la construction des URL, sans conversion en `Number` pour les grands BIGINT.

`openapi-typescript` 7.13.0 utilise l’API du compilateur TypeScript 5, incompatible
avec TypeScript 7. Le petit package privé `tools/openapi/` fixe TypeScript 5.9.3
pour la génération uniquement. L’application conserve TypeScript 7.0.2 et ses
contrôles stricts. pnpm gère les deux avec un lockfile commun ; aucun compilateur
supplémentaire ne fait partie du bundle public.

La CI **API contract checks** installe Python et Node sans PostgreSQL, contrôle
les dérives et compile les types. Elle régénère deux fois pour contrôler le
déterminisme. Le workflow termine aussi sur les changements documentaires, sans
installer les outils. La CI frontend vérifie les types depuis le JSON versionné,
sans Python. Le build Netlify ne régénère rien et ne dépend jamais de Wallace.

## Client public et loaders (FRONT-003)

`app/lib/api.ts` utilise `fetch`, les types OpenAPI générés et une union de
résultats `{ok: true, data}` / `{ok: false, kind, status?}`. Les corps des erreurs
HTTP ne sont jamais relayés. Les réponses réussies sont validées à la frontière
JSON avec des gardes typées, sans second jeu d’interfaces. `listForms()` et
`getForm(id)` restent des lectures publiques : cookies omis, cache désactivé,
redirections réseau refusées. Les paramètres supplémentaires peuvent être encodés
avec `URLSearchParams` ; aucun paramètre métier de recherche n’est ajouté.

Les paramètres BIGINT utilisent les identifiants chaînes des modèles de réponse
pour construire le chemin. Ce petit adaptateur HTTP n’utilise pas le type
numérique du paramètre OpenAPI comme représentation mémoire de l’identifiant :
aucun `Number` ou `parseInt` n’est appliqué aux identifiants. Le contrat backend
reste inchangé. Les futures opérations ayant leurs propres paramètres devront
s’appuyer sur leurs types générés ; pas de client HTTP générique supplémentaire.

### Serveur et navigateur

Les loaders framework s’exécutent **sur le serveur**, aussi lors des navigations
internes : React Router demande leurs données au serveur via ses propres
requêtes `.data`. Aucun `clientLoader` n’est introduit. Dans un futur loader :

```tsx
import { getForm } from "../lib/api.server";
import { requireApiData } from "../lib/api-errors";

// Exemple seulement : les pages métier ne sont pas encore migrées.
export async function loader({ request, params }) {
  return requireApiData(await getForm(params.id, { signal: request.signal }));
}
```

`api.server.ts` lit **API_BASE_URL**, origine backend complète sans chemin,
identifiants, query ou fragment. HTTPS est requis sauf sur le loopback local.
Elle n’est lue/validée que lorsqu’un loader appelle l’API. Absente ou invalide,
elle donne un secours 503 sans appel réseau. Ne jamais utiliser `VITE_*` pour
cette valeur et ne jamais la passer aux composants ou données du loader.

Exemple local, avec une API de développement indépendante de Wallace :

```sh
API_BASE_URL=http://127.0.0.1:8000 pnpm dev
```

Le navigateur, lorsqu’un appel direct sera nécessaire, utilise
`createPublicApi()` sans origine : `/api/v1/…` reste relatif au site. Il n’existe
pas encore de proxy Vite de développement ; les tests interceptent ces appels.
Le build et l’accueil pré-rendu n’appellent aucune API et ne nécessitent pas
`API_BASE_URL`, Python ou PostgreSQL.

### Erreurs, délais et maintenance

Les catégories distinguent demande invalide (400/422), accès refusé (401/403),
absence (404), erreur applicative (500), indisponibilité (502/503), délai serveur
(408/504), délai client, erreur réseau, annulation et réponse invalide.
Les messages sont définis dans `api-errors.ts`, sans SQL, URL interne ou trace.
Une réponse invalide devient 502 ; un échec réseau ou de configuration devient
503 ; un délai devient 504. Une erreur 500 reste ponctuelle.

Le délai maximal est **20 secondes**, comprenant la lecture du corps. Il reste
sous la limite documentée du [proxy Netlify de 26 secondes](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/), avec une marge ; les [fonctions Node synchrones](https://docs.netlify.com/build/functions/configuration/)
ont une limite distincte, actuellement 60 secondes. Ces limites d’hébergement
restent à vérifier en prévisualisation. `request.signal` est propagé ; React
Router empêche les résultats d’une navigation obsolète de remplacer la suivante.
La propagation jusqu’au backend peut dépendre de la plateforme ; même si une
connexion cliente disparaît, le délai client demeure borné.

`LoadingState` fournit Skeleton et annonce une attente prolongée après huit
secondes. Pendant une navigation, les données précédentes restent affichées.
`EmptyState` et `ErrorState` distinguent absence, erreur ponctuelle et maintenance.
Le réessai est manuel via `useRevalidator`, sans retry automatique ni écriture.
Une panne concerne la route consultée, jamais un état global persistant.

Les loaders **attendent** les données essentielles et `requireApiData` lance une
réponse React Router avec le bon statut et des en-têtes `private, no-store` et
`X-Robots-Tag: noindex, nofollow`. La racine reprend les en-têtes d’erreur et rend
un secours indépendant de FastAPI. Le streaming SSR par défaut est conservé :
les erreurs de loader sont connues avant l’envoi du document. Ne pas différer les
données essentielles dans une promesse/Suspense : une erreur après envoi des
en-têtes ne pourrait plus transformer HTTP 200 en 503. Lors d’une première visite
SSR, le statut doit être déterminé avant de rendre le HTML ; le Skeleton sert
aux navigations internes, pas à un envoi prématuré du document.

### Proxy et sécurité

`netlify.toml` prépare une réécriture fixe :
`/api/* → https://api.cahierdedoleances.fr/api/:splat`, HTTP 200 de proxy, sans
redirect navigateur. Les chemins et query sont conservés. Aucun choix d’upstream
ne provient de l’utilisateur ; aucun Origin/Host d’entrée n’est relayé par le
client serveur. La règle n’ajoute pas d’en-tête pour contourner CSRF.

Netlify doit conserver les politiques `private, no-store` et `Set-Cookie` du
backend. Aucun cache CDN n’est ajouté ici. Les règles de headers pour fichiers
statiques ne sont pas utilisées comme prétendue protection des réponses proxy.
La recette réelle de proxy (méthodes, cookies, Origin, Set-Cookie et cache)
nécessitera une prévisualisation avec un backend de test : aucun déploiement
ou appel de production n’est effectué. Le sous-domaine API et API-004A devront
être disponibles avant utilisation réelle de cette règle.

Cette couche est volontairement publique et sans session. Pour migrer les comptes,
prévoir une politique authentifiée explicite, la vérification d’Origin côté
FastAPI et la propagation séparée des cookies/Set-Cookie lors du SSR. Ne pas
réutiliser implicitement les lectures publiques pour une opération privée.

### Vérification sans Wallace

```sh
pnpm check
pnpm typecheck
pnpm test
pnpm contract:check
pnpm build:offline
pnpm test:build
pnpm test:e2e
```

Playwright compile un build séparé `build-test/` avec une route technique
`/_test/api`, puis lance des serveurs loopback : API synthétique 4176, SSR de test
4175, SSR sans API 4177, production normale 4173 et atelier 4174. Les tests
vérifient les vrais HTTP 404/500/503/504, le HTML initial, le réessai, l’attente
prolongée, les résultats obsolètes, les cookies omis et l’absence d’origine
interne dans les assets. Les règles de proxy sont vérifiées sans API de production.
`FRONTEND_TEST_ROUTES=1` est réservé aux tests ; il est refusé lorsque Netlify
exécute le build. Le build normal exclut cette route et son code. Ne pas définir
cette variable dans les environnements de déploiement.

FRONT-005A pourra utiliser ces loaders et états pour les formulaires. Aucun
parcours métier, compte ou marque-page n’a été migré dans FRONT-003.
