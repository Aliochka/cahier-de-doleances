# Stockage documentaire — maintenance locale, phase 1

Ce package indépendant traite les **corpus documentaires** (document → passage). Les questionnaires présents et futurs restent dans le modèle métier du Grand Débat ; aucun code applicatif ou lecteur public n’importe ce package.

La phase 1 n’indexe pas de texte, ne calcule pas de vecteurs et ne publie rien. Les six tables métier se trouvent dans `documentary`, avec une table Alembic dédiée. Voir [le schéma SQL](migrations/versions/doc_0001.sql), [la conception](../1789/docs/conception-technique-multicorpus-1789.md) et [le bilan réel](../1789/docs/rapport-phase1-documentary.md).

## Prérequis et destination

Utiliser l’environnement Python existant (`.venv/bin/python`), PostgreSQL 17 et pgvector disponible sur le serveur. La migration installe l’extension `vector` dans **la nouvelle base locale isolée seulement**, si elle est absente.

Toutes les commandes SQL exigent explicitement :

- Une URL `postgresql+psycopg2://ROLE@/documentary_NOM_test?host=/tmp/CHEMIN/socket&port=PORT` sans hôte TCP.
- Le chemin physique attendu du cluster et son identifiant système attendu.
- Un socket et un répertoire de données sous `/tmp`, appartenant à l’utilisateur courant.

À chaque transaction, le garde compare nom de base, répertoire physique, identifiant système et absence d’adresse TCP **avant toute écriture**. Il refuse toute base avec des tables métier ou des schémas/version RAG. Aucun chargement de `.env`, `DATABASE_URL`, configuration de production ou repli vers une autre destination. Les options de connexion supplémentaires sont refusées. Un nom `_test` seul ne suffit pas.

Ce garde est volontairement plus strict que la future architecture partagée : le déploiement vers une base de recherche contenant GDN fera l’objet d’une autre mission. Ne pas élargir le garde pour contourner un refus local.

## Créer une destination neuve

Exemple à adapter, exécuté uniquement sur une machine de développement :

```sh
DOC_PHASE1_ROOT=$(mktemp -d /tmp/documentary-local-XXXXXX)
mkdir "$DOC_PHASE1_ROOT/socket"
/usr/lib/postgresql/17/bin/initdb -D "$DOC_PHASE1_ROOT/data" --username=documentary_admin --auth=trust --encoding=UTF8 --locale=C
/usr/lib/postgresql/17/bin/pg_ctl -D "$DOC_PHASE1_ROOT/data" -l "$DOC_PHASE1_ROOT/postgres.log" -o "-k $DOC_PHASE1_ROOT/socket -p 55487 -c listen_addresses=''" -w start
/usr/lib/postgresql/17/bin/createdb -h "$DOC_PHASE1_ROOT/socket" -p 55487 -U documentary_admin documentary_1789_test
/usr/lib/postgresql/17/bin/pg_controldata "$DOC_PHASE1_ROOT/data"
```

Le répertoire `mktemp` privé protège le socket sans écoute TCP. Dans un environnement qui supprime les sous-processus détachés à la fin d’une commande, laisser `postgres -D ... -k ... -p ... -c listen_addresses=''` au premier plan dans une session dédiée. Ne pas réinitialiser le répertoire pour redémarrer un cluster existant.

Récupérer le `Database system identifier` affiché par `pg_controldata`. Puis passer **les trois arguments explicites à chaque commande** :

```sh
.venv/bin/python -m documentary migrate --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/CHEMIN/socket&port=55487' --expected-data-directory /tmp/CHEMIN/data --expected-system-id IDENTIFIANT
.venv/bin/python -m documentary import --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/CHEMIN/socket&port=55487' --expected-data-directory /tmp/CHEMIN/data --expected-system-id IDENTIFIANT
.venv/bin/python -m documentary verify --url 'postgresql+psycopg2://documentary_admin@/documentary_1789_test?host=/tmp/CHEMIN/socket&port=55487' --expected-data-directory /tmp/CHEMIN/data --expected-system-id IDENTIFIANT
```

`migrate` ne lance que la chaîne `doc_0001` et enregistre `documentary.alembic_version`. Il n’y a ni migration automatique au démarrage, ni migration de `rag_full`, ni commande de publication. Le downgrade destructeur est refusé ; le retour arrière consiste à conserver ce stockage inactif ou à reconstruire une autre base locale.

## Artefacts et import

La source par défaut est `1789/data/documents/reference-documents-2-7cbcaea79991`. Le pointeur actif doit correspondre ; une autre génération nécessite une adaptation explicite de cet importeur 1789. Les tables SQL restent génériques pour les futurs corpus documentaires.

```sh
.venv/bin/python -m documentary validate-artifacts
```

Cette commande n’utilise aucune base. Elle vérifie l’empreinte figée du manifeste, les empreintes de tous les fichiers du manifeste, les volumes attendus, les identités, textes, tranches Unicode, rattachements, ordinals et recouvrements. `--collection` permet une copie locale fidèle de la même génération ; pas une extraction nouvelle. Les sources locales ne sont pas toutes versionnées : un clone seul ne suffit pas.

L’import est atomique sous verrou transactionnel de maintenance. Une interruption avant commit ne laisse pas une release partiellement validée. Réexécuter `import` sur une release identique contrôle intégralement son contenu et renvoie `imported=false` ; il ne réécrit pas des lignes altérées pour les rendre conformes. Il faut investiguer une divergence, pas la masquer par un upsert.

`document.full_text` contient le texte canonique une seule fois ; `search_unit` conserve offsets et hash, sans copie du texte. Le texte exact se retrouve par `substring(full_text FROM start_offset+1 FOR end_offset-start_offset)` ; PostgreSQL utilise des positions de caractères à partir de 1, les artefacts des intervalles Unicode à partir de 0. Le contrôle compare chacune des 11 391 tranches SQL au passage original. Métadonnées, références XML, annotations, liens et statuts sont conservés dans les JSON source. La release conserve les 1 305 notices et les métadonnées des 38 notices sans texte.

## Éditorial et publication

Source de vérité : [decisions.json](../1789/editorial/decisions.json), format 1, révision `1789-editorial-1`. Les timestamps à minuit indiquent le jour d’autorisation, pas l’heure d’une session de revue. Les 13 événements enregistrent deux exclusions Artois, un avertissement Artois, le titre et l’avertissement Aunay-la-Côte et huit décisions explicites de conservation de ses passages.

Une décision est liée au document, à son étendue, à son hash et, pour une unité, au hash de celle-ci. Toute nouvelle valeur d’une même propriété doit citer le dernier événement par `supersedes_id`. Une décision initiale reste dans l’historique. Pour une réintégration, ajouter une décision `search_enabled=true`, avec les mêmes empreintes ; pour une réexclusion, ajouter un autre événement. Titres et avertissements sont réversibles de la même manière.

Le fichier est versionné dans Git ; les décisions déjà chargées ne peuvent ni disparaître ni être modifiées. Pour changer la révision dans une base existante, employer la commande distincte :

```sh
.venv/bin/python -m documentary apply-editorial --previous-decisions /chemin/revision-precedente.json --decisions /chemin/nouvelle-revision.json --url 'URL_EXPLICITE' --expected-data-directory /tmp/CHEMIN/data --expected-system-id IDENTIFIANT
```

Le nouveau fichier doit conserver le préfixe complet de l’ancien journal et avoir une nouvelle révision. Tout est rejoué et contrôlé dans une transaction, sans modifier les colonnes source. `import` avec un fichier ancien échoue au lieu de remettre silencieusement son ancienne politique. La base propre doit toujours être reconstruite depuis la révision éditoriale versionnée approuvée, pas depuis un fichier incomplet ou non révisé.

`search_unit.searchable` exprime seulement une permission **individuelle**. La future recherche devra joindre cette permission à celle du document et à la release active/autorisée, avant le top-K, dans les deux branches. En phase 1, tous les documents ont `readable=searchable=catalogue_visible=false`, y compris les 1 224 candidats. Les 43 autres textes sont en plus `candidate=false`.

L’état `verified` signifie intégrité documentaire et éditoriale ; il ne signifie pas recherche prête. `ready` est interdit sans `representations_ready` et `statistics_ready`. Une activation est interdite sans release prête et `publication_authorized`. Aucune commande ne donne ces autorisations dans cette phase.

## Tests et sauvegarde

```sh
DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin .venv/bin/pytest tests/test_documentary.py -q
.venv/bin/ruff check documentary tests/test_documentary.py
```

La suite PostgreSQL crée elle-même un **nouveau** cluster sous `/tmp`, deux bases propres, puis les arrête et nettoie leurs fichiers temporaires. Elle ne lit aucun DSN de production. Sans opt-in, ces deux tests PostgreSQL sont ignorés ; les contrôles purs continuent. Les essais qui exigent les artefacts historiques sont ignorés s’ils ne sont pas restaurés localement. Les décisions synthétiques de réintégration ne sont enregistrées que dans ces bases temporaires.

Le cluster de démonstration sous `/tmp` n’est pas une sauvegarde durable. Le rapport indique une sauvegarde locale privée du dump ; elle est exclue de Git. Une restauration doit viser une nouvelle base locale isolée et être suivie de `verify`. Aucun texte historique ni dump ne doit être ajouté aux fichiers versionnés.
