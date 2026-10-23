# Compte rendu RAG-005 — 17 octobre 2026

## Résultat

Le stockage documentaire PostgreSQL et le pipeline limité sont implémentés.
Une extraction réelle interrompue puis reprise restitue les mêmes objets JSON
qu’une extraction continue et que le lecteur source : cinq unités, sans perte
ni duplication. Les deux manifestes partagent les cinq documents stockés.
Aucun texte du corpus n’est reproduit dans ce rapport.

## Architecture et fichiers

- `schema.py` : quatre tables SQLAlchemy Core, dans le schéma `rag`.
- `migrations/`, `alembic.ini`, `migrate.py` : environnement Alembic autonome,
  révision initiale `rag_0001`, table `public.rag_alembic_version`.
- `safety.py` : contrôle des identités réelles et des marqueurs du corpus.
- `extraction.py` : paramètres immuables, versions et empreinte du manifeste.
- `storage.py` : persistance atomique, conflits explicites et restitution fidèle.
- `pipeline.py` : lecture bornée, progression et reprise avec les curseurs RAG-004.
- `__main__.py` : commandes `schema-upgrade`, `extract`, `status`, `resume`.
- Tests unitaires et `tests/integration/test_storage.py` : sécurité, migrations,
  fidélité, concurrence, rollback et interruptions avant/après commit.
- `pyproject.toml` et `uv.lock` : ajout d’Alembic 1.16.5, même version que le
  backend, et de ses dépendances Mako/MarkupSafe. Aucun ajout GPU ou recherche.
- README, exemple de configuration et [documentation du stockage](stockage.md)
  actualisés. Aucun fichier extérieur à `rag/` n’a été modifié.

Les documents utilisent des colonnes relationnelles pour le corps, les identités
BIGINT et l’empreinte, et JSONB pour le contexte restant, sans recopier le texte.
Même ID/même empreinte réutilise le document ; une autre empreinte annule le lot.
Même texte/IDs différents conserve deux documents. Les associations permettent
le partage entre manifestes. Documents, associations et checkpoint sont validés
ensemble, sous verrou du checkpoint et contrôle de sa révision.

Les paramètres, versions, identité source et révision source sont enregistrés
au démarrage. Une reprise incompatible est refusée. Le checkpoint contient le
curseur de réponse/unité, les compteurs, l’empreinte du dernier lot et le statut.
La répétition exacte du dernier commit est idempotente, y compris en concurrence.

## Commandes

Depuis `rag/`, avec les deux destinations explicitement configurées :

```bash
uv sync --locked
uv run --locked cahier-rag schema-upgrade --env-file .env.local
uv run --locked cahier-rag extract --env-file .env.local --limit 20 --batch-size 10 --max-source-rows 1000 --max-batches 1
uv run --locked cahier-rag status UUID_DU_MANIFESTE --env-file .env.local
uv run --locked cahier-rag resume UUID_DU_MANIFESTE --env-file .env.local
```

La limite obligatoire est plafonnée à 10 000 documents ; le budget de lignes
sources retournées est plafonné à 100 000. Une extraction terminée n’est pas
prolongée : créer un nouveau manifeste pour modifier les paramètres.

## Validations exécutées

| Validation | Résultat |
|---|---|
| pytest, suite complète avec deux bases de test | **162 réussis**, dont 32 intégrations PostgreSQL |
| pytest, tests unitaires sans PostgreSQL | **130 réussis** |
| Ruff et conformité du formatage | Conformes |
| `uv lock --check` | Conforme |
| Construction wheel et distribution source | Réussie |
| Installation sans dépendances dev, non éditable, hors dépôt | Réussie |
| Découverte de la révision et du modèle Alembic distribués | Réussie |
| Diagnostic installé sans connexion | Réussi |
| Migrations RAG sur destination de test et destination locale | Réussies |
| Extraction réelle limitée, arrêt/reprise et comparaison continue | Identité exacte des cinq objets JSON |
| Verrou et manifeste Python du backend | Empreintes inchangées |
| `git diff --check` | Conforme |

Les bases `cahier_rag` et `cahier_rag_test` ont été créées manuellement par
l’utilisateur avant les migrations. Le code n’a créé aucune base ni aucun rôle.
La source synthétique utilise `cahier_doleances_test`, déjà migrée avec le backend.
Les données synthétiques du stockage ont été nettoyées : zéro unité et zéro
manifeste dans `cahier_rag_test` après les tests.

La vérification réelle utilise `cahier_doleances_local`, en lecture seule.
Les cinq documents restent dans `cahier_rag`, avec deux manifestes, dix
associations et deux checkpoints terminés par `document_limit` :

- Reprise : `d39cfdb2-ecd1-4d40-bc80-2f4c19a70566`.
- Continue : `fe7fbabd-1d82-40a0-bcd2-fa290b847d9d`.

Les requêtes de cette vérification ponctuelle étaient bornées par un délai
PostgreSQL de cinq secondes. Aucune extraction complète ni mesure massive n’a
été lancée. Le corpus source n’a subi aucune écriture.

## Limites et risques

La source doit rester figée : chaque lot possède sa propre transaction, sans
snapshot global. L’identité physique et la révision du schéma ne détectent pas
toutes les modifications du corpus entre lots. Aucun historique de contenu
modifié n’est fourni ; une empreinte différente sous le même ID reste un conflit.

La vérification d’identité nécessite l’accès à `pg_control_system()` pour les
deux rôles et refuse l’opération si ce contrôle est impossible. Les rôles de
production restreints n’ont pas été provisionnés ou certifiés. Les alias pointant
vers la même base sont refusés ; les répliques physiques sont traitées avec
prudence. La source doit aussi être disponible pour lire un état de stockage.

Le budget de lignes concerne les lignes retournées, pas toutes celles examinées
par PostgreSQL. Un filtre peu sélectif peut rester coûteux ; aucun nouvel index
source ni délai maximal de requête général n’est introduit. La mémoire dépend
du lot et de la longueur des textes. Les documents peuvent contenir des données
personnelles : stockage local et maîtrise des droits restent nécessaires.

La CI existante sans PostgreSQL continue d’exécuter les tests unitaires ; les
intégrations sont conditionnées aux deux variables de test explicites. Aucun
service CI, déploiement Wallace, Dockerfile, backend ou frontend n’a été modifié.
Aucun commit ou push effectué. Le build Docker de production n’a pas été testé
pour cette tâche ; aucun de ses fichiers n’a changé.

Les unités persistées et leurs manifestes sont disponibles pour la prochaine
étape. Aucun embedding, pgvector, modèle, recherche ou génération n’est intégré.
