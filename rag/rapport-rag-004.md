# RAG-004 — Compte rendu d'implémentation

## A. Architecture

La tâche ajoute uniquement des fichiers et adaptations dans `rag/` :

- `src/cahier_rag/contracts.py` : `TextUnit`, `UnitType`, métadonnées de
  contribution, identité, validation des types, empreinte et JSON canonique.
- `src/cahier_rag/sources/gdn.py` et son package : adaptation GDN,
  `GdnReader`, `Cursor`, `DocumentBatch` et erreurs sources sans contenu textuel.
- `tests/unit/test_contracts.py` et `test_gdn.py` : contrat et lecture simulée.
- `tests/unit/conftest.py` : blocage du réseau et de psycopg2, déplacé ici
  pour ne pas empêcher les intégrations explicitement sélectionnées.
- `tests/integration/` : fixtures synthétiques et tests sur le vrai schéma migré.
- `pyproject.toml` : déclaration du marqueur pytest `integration`, sans changement
  des dépendances. Le verrou RAG reste inchangé.
- `tests/conftest.py` : conserve l'isolation des paramètres d'environnement.
- `tests/unit/test_isolation.py` : vérifie aussi les nouveaux imports hors dépôt.
- `README.md`, `extraction.md` et ce rapport : usages, contrat et limites.

Aucun backend, frontend, workflow, Dockerfile, fichier Compose, index ou
migration modifié dans l'état final. Aucun commit ni push effectué.

Les documents RAG-001 à RAG-003, le cadrage, les modèles, les migrations et
l'importeur structuré ont été examinés. `other_text` est bien une liste de
chaînes dans une colonne TEXT contenant du JSON ; le code actuel produit
zéro ou un texte libre par réponse à choix. Il n'existe pas de classification
thématique exploitable à réutiliser.

## B. Contrat documentaire

Le contrat v1 conserve séparément texte consultable, libellé de question,
questionnaire, titre et provenance. Les champs et types complets sont décrits
dans [extraction.md](extraction.md). Aucune stratégie d'embedding ou de
segmentation n'est encodée dans le contrat.

L'ID est `text-unit:v1:<corpus encodé>:<type>:<answer_id>:<unit_index>`. Il est
indépendant du texte et de l'ordre d'extraction. L'indice d'un « Autre » est
son indice dans le tableau source, même si des éléments blancs le précèdent.
Deux réponses identiques et deux occurrences identiques d'un tableau conservent
des identités distinctes.

Les IDs internes sont des `int` BIGINT positifs, vérifiés sans coercition
flottante. Le JSON les expose en chaînes décimales. Les IDs externes textuels
restent intacts. Les types des positions, chaînes de contexte et dates sont
également vérifiés, sans conversion implicite.

SHA-256 porte sur le JSON canonique de tous les champs documentaires et de la
version, hors propriétés dérivées ID et empreinte. Texte, contexte et provenance
sont donc couverts ; cette empreinte ne sert pas à fusionner des réponses.
Les dates utilisent leur représentation ISO, sans fuseau ajouté au timestamp
naïf du schéma actuel. Aucun nettoyage Unicode ou linguistique n'est appliqué.

Les champs supplémentaires de contexte (version/source du questionnaire et date
de contribution) préservent des informations déjà disponibles sans joindre
d'autres tables. `ContributionMetadata` permet de consulter un titre seul sans
créer de document autonome ni parcourir toutes les contributions.

## C. Extraction et reprise

Le lecteur utilise les primitives READ ONLY de RAG-003 et des requêtes SQL
paramétrées sur `public.answers`, `questions`, `forms` et `contributions`.
Aucun ORM applicatif, auteur, profil, `raw_json`, option ou thème n'est lu.

- Questions `text` : `answers.text` exact, sauf NULL ou texte uniquement blanc,
  qui ne produit pas d'unité. Les espaces d'un texte non vide sont conservés.
- Questions à choix : uniquement les éléments non blancs de `other_text`.
  Aucun repli sur `answers.text`, les libellés ou le JSON brut complet.
- JSON absent ou propriété absente : aucune unité. JSON malformé, racine non
  objet, `other_text` non liste ou élément non chaîne : erreur bloquante.
- Incohérence entre formulaire de question et formulaire de contribution :
  erreur bloquante. Pas de correction ni de rejet silencieux.

Chaque lot utilise `ORDER BY a.id ASC LIMIT :batch_size`. Le curseur contient
un ID de réponse et un indice facultatif ; `None` signifie que la réponse a
été entièrement consommée. Une reprise au milieu d'une réponse relit cette
réponse et exclut les indices déjà remis. Aucun OFFSET, N+1, checkpoint
persistant ou export massif.

Les filtres de questionnaire, contribution et type sont appliqués en SQL.
La limite documentaire est appliquée après adaptation, sans couper ou tronquer
les textes. Les résultats et la transaction sont fermés avant de rendre le
lot au consommateur. Arrêt anticipé et erreur ne laissent pas de connexion
ouverte ; le moteur reste explicitement détenu par l'appelant.

## D. Validations exécutées

| Vérification | Résultat |
|---|---|
| Unités sans serveur/réseau | **112 tests réussis** |
| Intégrations sur `cahier_doleances_test`, schéma existant migré | **10 tests réussis** |
| Suite complète avec PostgreSQL disponible | **122 tests réussis**, aucun ignoré |
| Ruff RAG | Lint réussi, **19 fichiers Python** conformes au formatage |
| Verrou uv | `uv lock --check` réussi ; aucune dépendance ni verrou modifié |
| Package | Distribution source et wheel construits sous `/tmp` |
| Isolation | Imports hors dépôt, backend/GPU interdits et absence de moteur à l'import vérifiés |
| Corpus local, transactions READ ONLY | **13 unités comparées**, quatre questionnaires (4, 5, 7, 10), dont un texte « Autre » |
| Fidélité sur ce contrôle limité | Textes, titres, questions, questionnaires, références externes et internes identiques aux valeurs SQL |
| Ressources | Mode READ ONLY effectif, fermeture sur erreur et arrêt anticipé vérifiés en intégration |
| Nettoyage des fixtures | Aucun formulaire synthétique `rag004:*` restant dans la base de test |
| Diff final | Limité à `rag/`, sans erreur de whitespace |

Les tests PostgreSQL exigent `RAG_TEST_DATABASE_URL` explicitement défini, une
base dont le nom se termine par `_test` et la révision `remove_runtime_caches`.
Ils insèrent puis suppriment leurs seules données synthétiques ; ils n'appliquent
pas de migration et ne créent aucune table. Les unités continuent de bloquer
les sockets et psycopg2 même lorsque cette variable est définie.

Commandes depuis `rag/` :

```bash
uv run --locked python -m pytest tests/unit
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test uv run --locked python -m pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv lock --check
```

Sans URL de test, les intégrations sont ignorées proprement. Aucun contenu réel
n'a été affiché ou transmis à une API. Aucune donnée du corpus n'a été modifiée.

## E. Limites et risques

Le schéma réel garde `question_stats.question_id` en INTEGER et sa contrainte
ne supprime pas les compteurs en cascade. Les fixtures utilisent donc des
questions compatibles avec ces déclencheurs et retirent explicitement leurs
compteurs. Tous les IDs proches de la borne BIGINT sont couverts en unité ;
en intégration, les IDs élevés concernent réponses, contributions et formulaires.
Aucun ajustement de schéma n'a été effectué pour contourner cette limite.

La lecture par ID et les filtres ciblés peuvent utiliser les index B-tree
existants, vérifiés sur la base locale. Les index lexicaux excluant les textes
courts ne sont pas requis. Une limite de documents peut néanmoins nécessiter
beaucoup de lots, notamment pour des « Autre » rares. Les plans et parcours
complets restent à mesurer ultérieurement, sans créer d'index maintenant.

Une première requête auxiliaire d'échantillonnage avec `EXISTS` a atteint la
borne de cinq secondes et a été annulée. Elle a été remplacée par une sélection
limitée utilisant l'index existant `(form_id, submitted_at, id)`, puis des
lectures ciblées par contribution. Aucun benchmark massif n'a été lancé.

Il n'y a pas de snapshot global entre lots. La reprise suppose la même source,
le même corpus, les mêmes filtres et règles, sans modification concurrente.
Un curseur seul n'encode pas tout ce contexte. Les autres formes éventuelles
de `value_json` restent des anomalies explicites, pas des variantes inventées.
Les autres types de question ne sont pas extraits.

Le contrôle du corpus est volontairement petit et non représentatif ; il ne
valide pas toutes ses lignes. Les privilèges d'un futur rôle source limité à
SELECT n'ont pas été provisionnés ni audités. La CI distante n'a pas été
déclenchée, puisqu'aucun push n'a été demandé. Aucun déploiement Wallace.

## F. Préparation de RAG-005

Sont disponibles : unités typées, provenance source complète, IDs stables,
empreintes et version explicite, JSON déterministe, lots et curseurs de reprise,
filtres et lecture ciblée des titres seuls.

RAG-005 devra choisir le schéma expérimental, les migrations propres au RAG,
les manifestes corpus/filtres/version, l'idempotence des écritures et la
validation des checkpoints après persistance. Rien de ce stockage, ni les
embeddings, la recherche ou un LLM, n'est implémenté ici.
