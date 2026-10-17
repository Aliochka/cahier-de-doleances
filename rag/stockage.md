# Stockage documentaire expérimental — RAG-005

## Schéma et migrations

La base destination doit être créée manuellement. `schema-upgrade` applique la
révision `rag_0001` avec Alembic 1.16.5. Son environnement indépendant
utilise les paramètres RAG exclusivement ; sa table de version est
`public.rag_alembic_version`. La révision contient une définition figée du schéma,
sans importer les modèles du backend ni les futures définitions modifiables.
Les migrations hors connexion sont refusées : elles contourneraient le contrôle
des destinations. Le package distribué contient les scripts Alembic.

| Table dans le schéma `rag` | Responsabilité |
|---|---|
| `text_units` | Unités immuables identifiées par leur ID documentaire |
| `extractions` | Manifeste UUID, paramètres, empreinte et identité source |
| `extraction_documents` | Association manifeste/unité et ordinal déterministe |
| `checkpoints` | Curseur, compteurs, révision, empreinte du dernier lot et statut |

Le texte, les quatre identifiants sources BIGINT, le corpus, le type d’unité,
son index, la version et l’empreinte occupent des colonnes dédiées. Le contexte
restant du contrat est conservé dans un objet JSONB : question, questionnaire,
titre, positions, section, provenance et date. Le corps et les identifiants ne
sont pas dupliqués dans ce JSONB. La restitution reconstruit `TextUnit` et vérifie
son identité et son empreinte ; ses identifiants restent des entiers Python et
des chaînes décimales dans le JSON public du contrat.

Les clés primaires, clés étrangères et contraintes vérifient identité,
positivité, types d’unité, curseurs et empreintes. Des index B-tree permettent
les parcours par corpus/questionnaire, corpus/contribution, corpus/question,
ainsi que les associations inverses. L’ordinal est unique par extraction.
Aucun index vectoriel, extension ou index supplémentaire du corpus n’est créé.

## Identité et sécurité des bases

Avant chaque transaction de stockage, y compris les lectures d’état, et avant
une migration, `DatabaseGuard` lit l’identité réelle de la source puis celle de
la destination : `pg_control_system().system_identifier`, OID dans
`pg_database`, et nom courant. La paire cluster/OID doit être distincte, même
si les URL, rôles ou alias diffèrent. Le nom réel doit correspondre à la base
explicitement configurée. La présence des tables principales du corpus ou de
`public.alembic_version` dans la destination provoque un refus supplémentaire.

Les rôles doivent pouvoir exécuter `pg_catalog.pg_control_system()` ; sans ce
droit ou sans source accessible, l’opération échoue, sans stratégie de repli.
Aucun droit n’est accordé automatiquement. Les répliques physiques partageant
les mêmes identifiants sont refusées par précaution. Les copies logiques et
restaurations doivent conserver une configuration destination explicitement
vérifiée par l’opérateur : l’identité physique ne prouve pas le rôle métier.

La source utilise les transactions READ ONLY existantes ; prévoir également un
rôle source limité à la lecture. Les contrôles ne provisionnent ni ne certifient
ses privilèges. La destination nécessite les droits de création du schéma pour
les migrations et les droits de stockage pour l’exécution. Les transactions
sources sont fermées avant d’ouvrir les transactions destination. Les manifestes
ne stockent aucune URL, aucun mot de passe et aucun texte brut supplémentaire.

## Manifestes, idempotence et transactions

`ExtractionSpec` fige corpus, filtres questionnaire/contribution/type, taille de
lot, limite documentaire, budget de lignes sources et versions du contrat,
lecteur et pipeline. Les filtres absents sont explicites dans la sérialisation.
Le manifeste enregistre ces paramètres, leur SHA256, l’identité source et sa
révision Alembic lorsqu’elle existe. Une reprise avec une autre identité,
révision, version ou d’autres paramètres est refusée.

Pour un lot, une même transaction destination :

1. Verrouille le checkpoint avec `SELECT FOR UPDATE` et vérifie sa révision.
2. Insère les unités absentes et vérifie les empreintes des unités existantes.
3. Ajoute les associations ordonnées au manifeste.
4. Avance le curseur, les compteurs et le statut.

Même ID et même empreinte réutilisent l’unité ; une empreinte différente produit
une erreur sans écrasement et annule tout le lot. Deux IDs ayant le même texte
restent distincts. Plusieurs manifestes peuvent partager les mêmes unités.
L’échec d’une association ou du checkpoint annule également les insertions.
Une répétition exacte du dernier lot après perte de l’accusé de commit est
reconnue par son empreinte et sa révision ; un lot concurrent différent est
refusé. Deux écritures concurrentes identiques ne doublent pas les compteurs.
Ce protocole ne constitue pas un ordonnanceur de travailleurs distribués.

Le curseur conserve l’ID BIGINT de réponse et, si nécessaire, l’index de l’unité
à l’intérieur de la réponse. Il progresse aussi sur les lots vides et conserve
les garanties de RAG-004. Aucun checkpoint n’est avancé hors du commit des
unités correspondantes. La restitution parcourt les associations par ordinal,
avec des lectures bornées et des transactions fermées avant de rendre les objets.

## Exécution et limites

Depuis `rag/`, après installation avec `uv sync --locked` :

```bash
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag extract --env-file .env.local --limit 20 --questionnaire-id 7 --batch-size 10 --max-source-rows 1000 --max-batches 1
uv run --locked cahier-rag status UUID_DU_MANIFESTE --env-file .env.local
uv run --locked cahier-rag resume UUID_DU_MANIFESTE --env-file .env.local
```

L’UUID est affiché avant le premier lot. Les sorties contiennent état et
provenance technique, sans texte documentaire. `--max-batches` permet de tester
un arrêt volontaire ; le statut reste `running` et ne signifie pas qu’un
processus travaille actuellement. Une interruption reprend au dernier commit.
Un manifeste `completed` reste terminé, avec une raison : `document_limit`,
`source_exhausted` ou `source_row_limit`. Pour changer ses paramètres ou sa
limite, créer une autre extraction. Les champs proposés à `resume` doivent
reproduire exactement ceux du manifeste.

La limite documentaire est obligatoire, entre 1 et 10 000. Le budget
`max_source_rows` vaut 100 000 par défaut et ne peut pas dépasser 100 000.
Il compte les lignes retournées par les requêtes, y compris les relectures
nécessaires aux curseurs partiels. Il ne borne pas les lignes examinées par le
plan PostgreSQL ni la durée d’une requête. La taille de lot vaut 500 par défaut,
au maximum 5 000. La mémoire dépend du lot et des textes, parfois très longs.
Aucune transaction source n’est maintenue pendant l’écriture destination.

La cohérence est celle de transactions distinctes par lot : aucun snapshot
global n’est maintenu. La reproductibilité suppose le corpus figé. Le manifeste
ne détecte pas une modification source supprimant des lignes déjà parcourues.
Un changement de contenu rencontré sous un ID existant provoque un conflit ;
il n’existe pas encore de stratégie d’historisation de ces changements.
Les documents restent potentiellement personnels : accès local maîtrisé,
aucune API externe, aucune journalisation des corps et aucun export massif.

## Vérification

```bash
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m pytest tests/unit
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --locked python -m pytest
```

Les deux bases de test sont explicitement sélectionnées, distinctes et suffixées
`_test`. La source de test doit déjà être migrée avec le backend ; aucune
migration backend n’est exécutée ici. Les migrations RAG sont appliquées sur
la destination de test. Les fixtures insèrent et nettoient uniquement leurs
données synthétiques. Sans ces variables les intégrations concernées sont
ignorées ; les tests unitaires restent sans PostgreSQL ni réseau.
