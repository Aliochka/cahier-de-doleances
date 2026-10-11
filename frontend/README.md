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
  components/layout/       PageContainer
  components/ui/           Disclosure, seule démonstration Ark UI
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
interaction clavier après hydratation. FRONT-002 construira les autres
composants progressivement. Biome est le seul outil de lint et formatage du
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

Prochaines tâches : FRONT-002 (composants communs), FRONT-003 (client API,
loaders/erreurs) et CONTRACT-001 (types générés depuis OpenAPI). Aucune n'est
entamée par ce socle.
