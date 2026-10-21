# SEARCH-DEPLOY-003 — Correctif du garde PostgreSQL

## Diagnostic

Dans le script précédent, `test "${1:-}" = postgres` vérifiait le premier
argument, **pas `POSTGRES_USER`**. La trace `test '' = postgres` signifie que
le garde n’avait reçu aucun argument.

L’[override PostgreSQL](../deploy/postgres/compose.pgvector.override.yml)
redéfinissait `entrypoint` sans `command`. Selon la
[sémantique officielle Docker Compose](https://docs.docker.com/reference/compose-file/services/#entrypoint),
cela ignore le `CMD ["postgres"]` de l’image. Le défaut est présent dans le dépôt
et explique la trace fournie par l’opérateur. Le Compose effectif de Wallace
n’a pas été inspecté pendant cette mission.

`POSTGRES_USER=cahier` désigne le rôle SQL de l’installation ; le processus
serveur et les fichiers appartiennent au compte système `postgres` de l’image.
Ces deux noms n’ont aucune obligation de correspondre.

## Changements

- [Garde](../deploy/postgres/existing-cluster.sh) : une commande omise devient
  explicitement `postgres`. Toute autre commande explicite, y compris une chaîne
  vide, est refusée. Les options d’une commande `postgres` explicite sont conservées.
- Aucun contrôle ni valeur par défaut n’impose `POSTGRES_USER=postgres`.
  `cahier`, `postgres`, une valeur vide et une variable absente sont acceptés.
- Les protections restent obligatoires : `PGDATA` exact, marqueur SSD, répertoire
  existant, fichier `PG_VERSION` lisible avec majeure 17, fichier de contrôle,
  UID/GID compatibles sur le répertoire et les deux fichiers.
- Les versions déclarée **et réelle du binaire** doivent être 17.11. Les variables
  nécessaires absentes produisent un diagnostic explicite plutôt qu’une erreur
  `set -u`. Aucun secret ni environnement complet n’est affiché.
- Exécution uniquement depuis root avec `gosu postgres`, ou depuis l’UID/GID
  du compte système `postgres`. Aucun `initdb`, `chown`, appel SQL ou script
  d’initialisation n’est ajouté.
- [Override](../deploy/postgres/compose.pgvector.override.yml) : ajout de
  `command: [postgres]`. Les deux montages existants et leurs protections restent
  identiques. Lors de la fusion réelle, reporter les éventuelles options serveur
  existantes après `postgres` dans cette commande.
- [Guide](search-deploiement.md) : distinction rôle SQL/compte système,
  explication du défaut et obligation de répéter le Compose fusionné sur copie isolée.

## Pourquoi la validation antérieure ne détectait pas le défaut

**Vérifié dans le dépôt :** l’image définit `CMD ["postgres"]`, mais l’ancien
override Compose le supprimait implicitement. Les tests SQL temporaires de
SEARCH-DEPLOY-002 lançaient les binaires PostgreSQL directement et n’exécutaient
pas ce garde ni Docker Compose. La validation YAML ne vérifiait pas ce contrat.

**Rapporté par l’opérateur :** l’image a été construite et pgvector 0.8.7 a
fonctionné sur une copie physique du cluster, avec PostgreSQL 17.11 et UID/GID
999:999. Cette validation n’a pas été réexécutée ici.

**À confirmer :** la commande exacte et les overrides utilisés lors de cet essai.
Un `docker run IMAGE` sans remplacement d’entrypoint conserve normalement le
`CMD` ; un essai passant explicitement `postgres` évite également le défaut.
Ces différences expliquent qu’une validation de l’image puisse réussir sans
valider la configuration de lancement en production. Il serait injustifié
d’affirmer laquelle a été employée sans sa configuration effective.

## Tests exécutés

Commande locale :

```bash
/tmp/cahier-search-cpu-venv/bin/pytest \
  tests/test_postgres_existing_cluster.py tests/test_search_preparation.py -q
```

**68 tests réussis**, aucun échec ni test ignoré. Un avertissement existant
concerne la dépréciation de `httpx` dans Starlette.

Les **38 nouveaux cas** de
[régression du garde](../tests/test_postgres_existing_cluster.py) exécutent le
script Bash réel, avec lectures de montages et identités simulées, fichiers
factices exclusivement sous le répertoire temporaire du test, et exécutables
inertes à la place de `postgres` et `gosu`. Ils couvrent :

- rôle SQL `cahier`, `postgres`, vide ou absent, avec ou sans commande ;
- conservation des arguments et démarrage root ou UID/GID 999:999 ;
- `PGDATA` absent, vide ou incompatible ; version d’image absente, vide ou incompatible ;
- binaire incompatible malgré une variable de version correcte ;
- mauvais UID ou GID de chacun des fichiers vérifiés ou du processus ;
- répertoire, fichiers ou marqueur manquants, majeure du cluster incompatible ;
- commandes interdites ; contrat YAML de commande et préservation des montages.

Autres contrôles réussis : `bash -n`, Ruff et vérification du format du fichier
de tests, `git diff --check`.

**Non exécuté :** construction Docker, rendu Compose et démarrage d’un conteneur,
car Docker est indisponible dans cet environnement. Aucun test PostgreSQL réel
n’a été lancé pour cette mission ; aucune base n’a été créée ou modifiée.

## État et suite

Le correctif est prêt pour revue et répétition sur une copie isolée avec le
Compose réellement fusionné. Cette répétition doit conserver le rôle SQL
`cahier`, les UID/GID 999:999 et les options serveur existantes, et vérifier
la commande effective du conteneur. Elle reste une opération de l’opérateur.

Aucune connexion à Wallace, modification de base, reconstruction d’index,
intervention en production, commit ou push n’a été effectué.
