# Vérifications réalisées

## Python

```sh
/usr/bin/python3 1789/tools/document-review/test_articles.py
/usr/bin/python3 1789/tools/document-review/test_review.py
.venv/bin/ruff check 1789/tools/document-review 1789/archives/1789-article-review
.venv/bin/ruff format --check 1789/tools/document-review 1789/archives/1789-article-review
```

15 tests d’articles et 8 tests du mode Cahiers passent. Les premiers couvrent :

- état initial réel (719 articles, 217 A, aucune nouvelle validation humaine) ;
- neuf articles de Pierrelez validés ensemble, puis annulation historisée ;
- équivalence matérielle avec neuf validations individuelles ;
- refus d’une validation groupée contenant une incertitude ;
- séparation au milieu d’un paragraphe puis fusion, texte conservé ;
- correction de bornes avec conservation des restes ;
- refus d’absorber un article voisin non sélectionné ;
- classement C en paratexte ou passage revendicatif, distinct d’un ajout explicite d’article ;
- correction de numéro sans réécriture ;
- invalidation lorsque le parent est laissé incertain, lorsque sa fin est corrigée, et après régénération sous une autre version ;
- refus d’un onglet périmé, d’une fausse confirmation et d’offsets hors parent ;
- reprise après réouverture, export reproductible et détection d’altération du journal ;
- rubriques de Ferrières, articles multi-paragraphes et longs passages C.

Les tests de Cahiers continuent de vérifier leurs API, l’enregistrement/reprise, les sources exactes, le verrou de concurrence et les protections Host/Origin/jeton. Aucun événement de test ne rejoint le vrai journal.

## Navigateur réel

Les dépendances Playwright/Chromium déjà disponibles dans le frontend sont réutilisées, sans ajout de paquet. Dans un premier terminal :

```sh
/usr/bin/python3 1789/tools/document-review/article_test_server.py --port 17895
```

Dans un second :

```sh
REVIEW_TEST_URL=http://127.0.0.1:17895 node 1789/tools/document-review/article-smoke.cjs
```

Ce serveur crée des journaux et exports entièrement synthétiques dans un répertoire temporaire, détruit à son arrêt ; il n’utilise pas les journaux réels pour les écritures. Relancer le serveur de test avant chaque nouvelle exécution du scénario.

Le scénario passe par les opérations visibles : Pierrelez, sélection explicite de neuf articles, confirmation, validation groupée, annulation, validation individuelle, rechargement du navigateur, séparation à une position choisie dans le texte, fusion, classement C, ajout explicite d’un article manquant et remise en incertitude. Le groupe comportant cette dernière est refusé.

Ferrières est ouvert et ses 25 articles/rubriques sont affichés. Le clergé d’Alençon fournit le cas riche en B ; la noblesse d’Agen, celui des longs C. Les essais vérifient les largeurs 320/375/768/1280, le texte à 200 %, l’absence de débordement horizontal, le clavier, les caractères hors BMP (conversion UTF-16/points de code), l’export structuré et le retour au mode Cahiers. Les résultats bruts sont dans `data/browser-checks.json`.

Une inspection visuelle a également été faite ; les captures locales de test sont ignorées et ne sont pas des artefacts applicatifs.

## Intégrité et isolation

```sh
/usr/bin/python3 1789/archives/1789-article-review/export.py
/usr/bin/python3 1789/archives/1789-article-review/check.py
```

Le contrôle vérifie le texte contre le volume XML puis le parent, les bornes, les identifiants, les pages/versions, l’absence de perte ou duplication des plages, les règles d’éligibilité et les empreintes d’export. Les 647 fichiers d’audits/sources/journal des cahiers protégés au début restent inchangés. Le nombre réel de décisions d’articles est zéro à la livraison.

Les tests géométriques ne prouvent pas la justesse historique d’une fusion ou séparation ; leurs décisions sont explicitement synthétiques. Les choix documentaires restent à faire par un lecteur, avec recours possible à la page numérisée.
