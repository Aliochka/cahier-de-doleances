# Audit et nettoyage du dépôt

## Tests

| Ancienne partie | Constat | Décision |
| --- | --- | --- |
| `tests/test_basic.py` | Arithmétique triviale, imports et présence de fichiers ; ne détecte pas une régression du produit. | Supprimé. |
| `tests/test_cache.py` et tests de cache dans les routes | Vérifient une fonctionnalité retirée et dupliquent les seuils TTL. | Supprimés. |
| `tests/test_performance.py` | Certains contrôles acceptent toute liste, tout temps positif ou ne comparent aucun résultat. Dépendances benchmark et psutil non installées. | Supprimé ; aucune promesse de performance déduite de ces tests. |
| Tests HTTP et scroll anciens | Curseurs factices, conditions pouvant éviter toutes les assertions, comparaison de deux HTTP 200 sans vérifier les données. | Remplacés par des contrôles sur les vrais curseurs et l'ensemble des identifiants attendus. |
| Anciennes fixtures | Données commises sans nettoyage ; création du schéma ORM sans les triggers ; remplacement d'une dépendance non utilisée par plusieurs routes. | Base migrée séparée, sessions des routes remplacées, transaction extérieure annulée après chaque test. |
| Playwright et tests d'images OG | Navigateur imposé alors que les images dynamiques sont désactivées. | Retirés pour le moment. |
| Tests d'ingestion récents | Vérifient fidélité des données, fichiers tronqués, reprise, choix multiples et idempotence. | Conservés. |

La nouvelle suite vérifie aussi les statistiques qui changent immédiatement
après une modification en base et les sitemaps générés pour deux hôtes
différents. Elle a révélé puis couvert des défauts de pagination : utilisation
de la ligne sentinelle comme curseur, comparaison du score FTS avec une
précision différente du type PostgreSQL `real`, et alias de score utilisé dans
`HAVING`.

## Fonctionnalités et installation

- Suppression de Babel, middleware de langue, route de sélection, catalogues
  et scripts de traduction. Les textes de l'interface restent en français.
- Suppression de Playwright, diagnostic navigateur, routes d'images OG qui
  renvoyaient 503, copie de secours du routeur SEO, hook de compilation,
  paquets Chromium, configuration et consignes de buildpack navigateur, et
  volume OG Docker. L'image de partage statique existante
  est utilisée sur les pages.
- Suppression du cache de recherche, du suivi de popularité, du cache dashboard,
  du cache sitemap, des routes et scripts d'invalidation. La migration
  `remove_runtime_caches` retire `search_cache`, `search_stats` et
  `dashboard_cache`. Les compteurs de réponses et index PostgreSQL restent
  utilisés pour les statistiques et la recherche.
- Suppression des routes `/mentions` et `/topics` sans templates et du lien
  inactif vers les mentions. Les véritables pages d'erreur restent nécessaires.
- Suppression du pied de page flottant et de son script, dont le seul contenu
  était le sélecteur de langue.
- Ruff remplace les configurations Black/isort/flake8 concurrentes. Les fichiers
  Python actifs ont été nettoyés et formatés. L'historique des migrations est
  conservé ; une migration supplémentaire applique le retrait des caches.
- Les dépendances de développement se limitent à pytest, httpx et Ruff. Les
  bibliothèques d'analyse sont déplacées dans `requirements-analysis.txt`.
  Le doublon PyYAML d'une autre version est supprimé.
- La CI utilise les migrations et une base PostgreSQL distincte ; ses tâches
  navigateur, benchmarks et seuil de couverture arbitraire ont été retirées.

Le cache des fichiers sources téléchargés et les mécanismes internes de
PostgreSQL ne sont pas des caches de pages : ils restent utilisés. La suppression
des caches applicatifs implique que chaque requête recalcule ses résultats.
Les requêtes sitemap évitent les jointures sur toutes les réponses nationales.

L’ancien importeur Rust (`gdn_ingest/`) a également été retiré : il n’a pas
été utilisé pour l’import complet. Le parcours conservé utilise
`ingest.sources`, `ingest.structured_sources`, `ingest.postgres` et
`ingest.verify`, sans dépendance à Cargo.

## Validation locale

- Migrations appliquées sur la base locale et sur une base de test vide.
- Dépendances et suite complète également vérifiées dans un environnement
  Python neuf, sans Babel ni Playwright.
- Suite complète : 21 tests réussis ; aucune donnée de test conservée.
- Ruff et contrôle de formatage réussis.
- Recherche, détails, tableaux de bord, robots et sitemap contrôlés sur les
  données nationales, sans Playwright ni tables de cache.

Commandes reproductibles dans [TESTING.md](../TESTING.md).

Docker n’est pas installé dans l’environnement de vérification : les fichiers
Docker et Compose ont été simplifiés et la syntaxe YAML contrôlée, mais l’image
n’a pas été construite ici.
