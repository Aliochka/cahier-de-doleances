# Constitution du corpus expérimental — RAG-007

## Procédure bornée

Le script `scripts/constitute_corpus.py`, exécuté depuis `rag/`, réalise quatre
étapes séparées : `plan`, `extract`, `select`, `verify`.

`plan` vérifie au moins 1 Gio libre et un `statement_timeout` de cinq secondes.
Il lit les bornes d’ID des contributions des quatre questionnaires, puis découpe
chaque intervalle en quarante zones. Dans chaque zone, un générateur Python de
graine 20261018 choisit une ancre dans les trois premiers quarts de l’intervalle.
Une requête indexée prend au plus quarante contributions à partir de cette
ancre, sans dépasser la zone. Les zones vides ne sont pas remplacées par les
premiers IDs d’une autre zone. Ce plan évite une sélection des seules premières
ou dernières contributions, mais ne constitue pas un tirage probabiliste uniforme.
L’agrégat de bornes porte sur les métadonnées des contributions, pas les textes.

Les IDs sont mélangés de manière déterministe par questionnaire, puis regroupés
par listes de 500 au maximum. Le plan est refusé au-delà de vingt extractions.
Chaque extraction conserve les limites RAG-005 : 10 000 unités, 100 000 lignes
sources retournées, lots de cent lignes. L’opération réelle a nécessité douze
extractions. Les lectures SQL utilisent l’index des réponses par contribution,
les paramètres liés et la pagination par ID de réponse.

L’ajout `ExtractionSpec.contribution_ids` est un filtre optionnel, trié, unique,
limité à 500 BIGINT et incompatible avec le filtre individuel simultané.
Il est sérialisé en chaînes décimales et fait partie de l’empreinte du manifeste.
Lorsqu’il est absent, sa clé est omise : les anciennes sérialisations et
empreintes restent inchangées. Le lecteur, le pipeline et le stockage vérifient
le périmètre ; une reprise avec une liste différente est refusée. La CLI
existante accepte aussi `--contribution-ids ID`, répété pour plusieurs IDs.
Aucun schéma ni numéro de contrat documentaire n’est modifié : le texte extrait
et les règles de transformation restent ceux de RAG-004.

`extract` crée et enregistre chaque manifeste avant son premier lot. Chaque
appel au pipeline ne valide qu’un lot, puis enregistre sa progression et sa durée.
Le checkpoint PostgreSQL est la référence après interruption ; la progression
locale peut être en retard sans provoquer de réinsertion des lots déjà validés.
Les connexions sources sont fermées avant toute écriture RAG. Les fichiers
opérationnels de progression sont remplacés atomiquement ; les jugements humains
ne sont jamais concernés. Une interruption juste après création d’un manifeste
mais avant enregistrement de son UUID peut laisser un manifeste orphelin, sans
corruption documentaire ; conserver les fichiers de progression évite ce cas.

`select` relit le cadre stocké par lots, vérifie les manifestes contre le plan,
et conserve seulement les résumés documentaires bornés de RAG-006. Le tirage
aléatoire compte 10 000 unités, graine 20261018. La graine stratifiée est 20261019.
Une recherche déterministe de taille, entre 10 000 et 20 000, obtient une union
de **20 000 IDs distincts** ; les quotas par défaut sont stables dans cette plage.
Les sélections partagent le cadre entier et la graine de partition 1729.
Aucun plafond RAG-005/006 n’est relevé. Tous les quotas doivent être satisfaits,
sans option d’acceptation silencieuse d’un déficit.

`verify` relit les unités depuis PostgreSQL avec contrôle de leurs empreintes,
rejoue les deux sélections et compare leurs empreintes et celles du cadre.
Il vérifie aussi les partitions par contribution et par texte exact. Les
quarante requêtes d’évaluation ne sont jamais modifiées par cette opération.

## Commandes

Les deux bases doivent déjà exister et le schéma RAG être migré. Configurer les
variables RAG ou sélectionner explicitement un fichier local sans secret versionné.
Aucune base n’est créée par ces commandes.

```bash
cd rag
uv sync --locked
export PGOPTIONS='-c statement_timeout=5000 -c lock_timeout=2000'
# Pour un nouveau plan, choisir un autre dossier local si rag007 existe déjà.
uv run --locked python scripts/constitute_corpus.py plan --env-file .env.local
uv run --locked python scripts/constitute_corpus.py extract --env-file .env.local
uv run --locked python scripts/constitute_corpus.py select --env-file .env.local
uv run --locked python scripts/constitute_corpus.py verify --env-file .env.local
uv run --locked cahier-rag-eval describe --sample evaluation/local/rag007/corpus.json
```

Après interruption, relancer uniquement `extract`, puis `select` si les
sélections n’existent pas encore. `plan` et `select` refusent d’écraser leurs
manifestes. `--directory evaluation/local/NOUVELLE_OPERATION` choisit un autre
dossier pour rejouer une opération complète. Même corpus figé, mêmes règles et
graines donnent les mêmes sélections ; UUID, dates et mesures temporelles de
nouveaux manifestes peuvent différer.

## Localisation et usage

Les fichiers locaux ignorés par Git se trouvent dans `evaluation/local/rag007/` :

- `plan.json` : zones, ancres, IDs de contribution, graine et identité source.
- `progress.json` : douze UUID d’extraction, états et durées par lot.
- `random.json`, `stratified.json`, `corpus.json` : listes d’IDs, empreintes,
  références aux extractions et partitions ; le dernier fichier définit le corpus final.
- `statistics.json` : statistiques du cadre, des deux sélections et de l’union,
  avec détails par type documentaire.
- `verification.json`, `source-verification.json` : contrôles locaux effectués.

Les 20 000 unités sont toutes présentes dans `rag.text_units` de `cahier_rag`.
Les associations `rag.extraction_documents` référencent le cadre de 42 318 unités,
pas uniquement le corpus final : ne pas confondre cadre stocké et corpus retenu.
Les manifestes de sélection sont des fichiers locaux, pas de nouvelles tables.
Pour traiter les seules unités finales, utiliser la liste de `corpus.json`.

Exemple de lecture bornée, sans afficher le texte :

```python
from sqlalchemy import select
from cahier_rag.schema import units
from cahier_rag.storage import restore_document
from cahier_rag.evaluation.cli import load_sample

sample = load_sample("evaluation/local/rag007/corpus.json")
# store est un RagStore construit avec les fabriques et DatabaseGuard existants.
for start in range(0, len(sample["documents"]), 100):
    expected = {d["document_id"]: d for d in sample["documents"][start : start + 100]}
    with store.guard.transaction() as (connection, source):
        records = (
            connection.execute(select(units).where(units.c.document_id.in_(expected)))
            .mappings()
            .all()
        )
    assert len(records) == len(expected)
    for record in records:
        document = restore_document(record)
        assert document.content_hash == expected[document.document_id]["content_hash"]
        # Transmettre ensuite document au traitement local, sans journaliser son corps.
```

Les partitions concernent ce cadre gelé. Les fichiers diagnostiques RAG-006
provenant d’un autre cadre ne doivent pas être fusionnés avec celui-ci : la
composition des groupes transitifs peut changer. Aucun modèle n’a été réglé
sur ces anciens diagnostics. La partition des requêtes et la règle de partition
RAG-006 sont conservées. La cible indicative 80/20 n’est pas imposée au détriment
des grands groupes de doublons.

Les limites méthodologiques et la comparaison avec l’audit initial figurent dans
[le compte rendu](rapport-rag-007.md). Aucune fréquence d’opinion ni représentativité
nationale ne peut être déduite de ces sélections enrichies et regroupées.
