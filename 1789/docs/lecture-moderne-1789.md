# Lecture moderne des cahiers — 8 novembre 2026

Implémentation locale uniquement, sans publication ni déploiement.

## Présentation

Le lecteur utilise les `xml_blocks` déjà conservés dans les métadonnées documentaires : leurs positions absolues sont ramenées au texte du cahier. Les paragraphes XML deviennent des paragraphes de lecture ; les titres et rubriques identifiés dans ces blocs conservent une présentation distincte. Les jalons de page vides ne créent pas de paragraphes. Aucun découpage en articles n'est ajouté.

Les retours à la ligne internes, tabulations et espaces multiples sont réduits à un espace dans les fragments affichés. Le navigateur recompose les lignes naturellement, sans justification. Les espaces entre fragments restent conservés et sont fusionnés visuellement par CSS. Les mots coupés, traits d'union, graphies et erreurs OCR ne sont pas corrigés.

Si les positions XML manquent ou sont incohérentes, le repli utilise uniquement les lignes blanches comme séparations ; un retour à la ligne simple ne suffit pas à créer un paragraphe. Le texte situé entre les blocs XML n'est jamais perdu.

La largeur existante, Literata pour la prose, Special Elite pour les titres, les métadonnées, les avertissements et les navigations sont conservés. Cette présentation est propre au lecteur historique : le style partagé de lecture du Grand Débat reste inchangé.

## Sources et surlignage

`app/documentary_presentation.py` produit une projection de lecture, sans écriture en base. Chaque paragraphe conserve ses positions et ses fragments canoniques. Le contrat du lecteur ajoute `paragraphs` tout en conservant les anciens `blocks`.

Le passage sélectionné est intersecté avec les paragraphes **en Python, sur les positions Unicode canoniques**, avant la normalisation d'affichage. Un passage traversant plusieurs paragraphes est surligné en plusieurs fragments, avec une seule ancre stable. Aucune recherche approximative et aucun découpage UTF-16 dans le navigateur ne sont employés. Les vérifications d'empreintes et les URL versionnées restent en place.

Aucun texte PostgreSQL ou Stanford, passage, offset, identifiant, empreinte, embedding, index, règle de recherche ou permission de publication n'est modifié. Aucune migration ni opération d'import n'a été exécutée.

## Vérifications réalisées

- **58 tests backend réussis**, comprenant la projection, les protections documentaires et les tests H1 ; trois avertissements existants Starlette/OpenAPI.
- Conservation exacte du texte à travers la projection sur les **1 267 documents** des artefacts locaux immuables.
- Vérification des **18 passages du tiers état d'Agen**, incluant le premier et le dernier. Son affichage utilise 83 blocs de lecture, dont trois titres/rubriques.
- Cas synthétiques : passage interne ou traversant plusieurs paragraphes, espaces et retours à la ligne, emoji hors BMP, caractère accentué décomposé, texte hors blocs XML et repli conservateur.
- **190 tests frontend réussis** ; TypeScript, contrats OpenAPI/types, lint et build hors réseau vérifiés.
- Chromium réel : neuf ouvertures de passages, premier/médian/dernier, dans Agen, les trois ordres réunis de Bourg-en-Bresse et Vaires-près-Lagny. Contrôle du texte canonique et de son empreinte renvoyés par l'API, du surlignage exact, de l'ancre et du positionnement. Ces exemples incluent des rubriques nombreuses et un paragraphe XML de 8 926 caractères.
- Vérification visuelle sur ordinateur et mobile de 375 pixels : prose continue, paragraphes espacés, absence de débordement, polices conservées.
- Smoke multicorpus existant réussi : navigation du Grand Débat, catalogue, lecteur, précédent/suivant, recherche, filtres/URL, historique, pagination et clavier. Aucune erreur JavaScript dans les deux parcours Chromium.

Commandes de reprise, depuis la racine :

```sh
.venv/bin/pytest tests/test_documentary_presentation.py tests/test_phase4_documentary.py tests/test_hybrid_search.py -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build:offline
```

Après démarrage de l'application locale avec `scripts/run_multicorpus_local.py` :

```sh
pnpm --dir frontend exec node tests/smoke-historical-reading-local.mjs
pnpm --dir frontend exec node tests/smoke-multicorpus-local.mjs
```

Les limites de la transcription et de sa structuration XML restent visibles : cette amélioration ne restaure pas les paragraphes absents des sources et ne répare aucun mélange documentaire.
