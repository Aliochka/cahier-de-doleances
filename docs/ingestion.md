# Import complet du Grand Débat National dans PostgreSQL

Cette procédure part de l'installation locale décrite dans le README et
permet de reconstruire la base depuis les sources publiques sur un nouveau
PC. Le dépôt doit contenir les migrations et scripts décrits ici.

## 1. Télécharger les sept snapshots complets

Depuis la racine du projet, avec PostgreSQL configuré dans `.env` :

```bash
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked python -m ingest.sources fetch --full
uv run --locked python -m ingest.structured_sources fetch
```

Le [catalogue officiel](https://www.data.gouv.fr/datasets/donnees-ouvertes-du-grand-debat-national)
fournit quatre exports de contributions du 21 mars 2019 et trois exports de
questions rapides du 8 avril 2019. Leurs identifiants sont fixés dans les
scripts. Les exports antérieurs se recouvrent : ne pas les empiler.

Les CSV sont conservés dans `data/gdn/raw/` (environ 1,6 Go), les JSON dans
`data/gdn/raw-json/` (environ 7,1 Go une fois décompressés). PostgreSQL et ses
index occupent de l'espace supplémentaire ; la taille mesurée est indiquée
dans le rapport final. Le dossier `data/` est ignoré par Git.

Chaque fichier possède un manifeste : ressource officielle, URL, date de
récupération, taille et SHA-256. Un fichier déjà vérifié est réutilisé. Les
JSON sont téléchargés avec trois connexions au maximum (`--workers 1` pour
un téléchargement séquentiel). Le JSON démocratie est fourni dans une
archive ZIP, décompressée par le script sans outil système supplémentaire.

En cas d'interruption, relancer la commande. Le téléchargement JSON reprend
un `.part` par HTTP Range si le serveur le permet, sinon repart du début.
Les CSV interrompus sont retéléchargés depuis le début. Les téléchargements
ne modifient pas PostgreSQL.

## 2. Vérifier les sources et les questions

```bash
uv run --locked python -m ingest.structured_sources profile
```

Le profilage lit les fichiers progressivement. Il compare les identifiants,
l'ordre et le nombre de contributions entre CSV et JSON, et vérifie que
chaque question est couverte une seule fois. Il produit
`data/gdn/full-profile.json` et met à jour les mappings YAML à partir des
labels explicitement sélectionnés dans les JSON, jamais à partir du texte
« autre ». Ce profil complet est requis par l'importeur.

Les JSON officiels peuvent omettre le crochet final du tableau. Le lecteur
accepte cette anomalie uniquement après un objet complet ; un objet coupé
ou une virgule finale provoque une erreur. Les empreintes, tailles et la
comparaison avec tous les identifiants CSV contrôlent la complétude.

Certaines cellules CSV sont vides alors que le JSON contient une réponse.
Ces écarts sont comptés dans le profil et le rapport final. Le JSON fait
référence pour conserver ces réponses et distinguer exactement `labels`
et `other`, y compris lorsque le texte libre contient `|`.

Les formulaires longs et les questions rapides ont des identités distinctes.
Le titre est une métadonnée de contribution, pas une question artificielle.
Les dates, identifiants d'auteur, codes postaux (avec leurs zéros initiaux),
titres et valeurs d'origine sont conservés.

## 3. Importer un pilote de 1 000 contributions par formulaire

```bash
uv run --locked python -m ingest.structured_sources samples --rows 1000
uv run --locked python -m ingest.postgres --samples
```

Les échantillons JSON sont conservés dans `data/gdn/samples-json/`.
Ils contiennent les premiers enregistrements complets ; ils ne constituent
pas un échantillon aléatoire représentatif.

Les choix multiples restent regroupés dans une seule réponse :

- `questions` : une ligne par question du formulaire d'origine ;
- `answers` : une ligne par contribution/question, à `position=1` ;
- `options` : uniquement les labels officiels du questionnaire ;
- `answer_options` : un lien pour chaque choix sélectionné, sans répétition ;
- `answers.value_json` : choix, valeur structurée source et texte « autre » ;
- `contributions.raw_json` : contribution JSON d'origine complète.

Ainsi « Transports en commun + Vélo » ne devient pas deux questions Oui/Non.
Les véritables réponses Oui/Non, « Je ne sais pas » et autres labels restent
à leur place. Une proposition libre ne crée pas une nouvelle option.

Les caractères nuls U+0000 sont incompatibles avec le texte et le JSONB de
PostgreSQL : ils sont remplacés par U+FFFD dans le texte affiché/indexé et
signalés dans `value_json.normalizations`. Leur valeur exacte reste encodée
dans `contributions.raw_json` (colonne TEXT) et le fichier JSON original.
Cette colonne brute peut être décodée avec `json.loads` ; ne pas la convertir
sans précaution en JSONB si elle contient U+0000.

Ouvrir http://127.0.0.1:8000 pour vérifier les formulaires, une réponse avec
plusieurs choix et leurs statistiques. Les pourcentages des choix multiples
utilisent le nombre de répondants ; leur somme peut dépasser 100 %.
Les graphiques incluent les personnes qui n'ont coché qu'un seul choix.

Pour vérifier la réimportation du pilote, **avant l'import complet** :

```bash
uv run --locked python -m ingest.postgres --samples --restart
```

Cette commande relit les données et actualise les mêmes identifiants. Les
contrôles vérifient les compteurs et l'absence de réponses supplémentaires.
L'importeur refuse un pilote réduit lorsque la base contient déjà davantage
de contributions pour ce formulaire. Utiliser une base séparée dans ce cas.

## 4. Importer toutes les contributions et vérifier le résultat

```bash
uv run --locked python -m ingest.postgres
uv run --locked python -m ingest.verify
```

Le même importeur complète les contributions du pilote par upserts. Les
identifiants d'import sont préfixés par le formulaire pour distinguer les
sources ; les identifiants d'origine et références restent dans `raw_json`.
Aucune table n'est vidée, aucun fichier export intermédiaire SQLite n'est
nécessaire et les séquences PostgreSQL génèrent les identifiants internes.

L'import est exécuté par lots de 1 000 contributions (réglable avec
`--batch-size`). Chaque lot valide les réponses et leurs liens avant de
commettre les données et sa progression dans `gdn_import_runs`. Les compteurs
sont maintenus par des triggers SQL par instruction, les index plein texte
par les colonnes et triggers de recherche. Les statistiques du planificateur
SQL sont actualisées pendant l’import et à sa fin ; le site n’utilise plus de
cache applicatif.

La vérification finale contrôle les sept empreintes, les nombres de
contributions et de réponses contre le profil source, les questions, les
catalogues d'options, les liens, les compteurs et la fin de chaque import.
Elle écrit [ingestion-resultats.md](ingestion-resultats.md), sans recopier les
textes libres ni les identifiants personnels.

## Reprendre ou limiter un import

Après une interruption :

```bash
uv run --locked python -m ingest.postgres
```

La reprise repart après le dernier lot commis, en vérifiant que le fichier
et le mapping sont identiques. Les formulaires déjà terminés sont ignorés.
Un verrou empêche deux imports simultanés.

Pour travailler sur un seul formulaire (possible aussi avec plusieurs
arguments `--source`) :

```bash
uv run --locked python -m ingest.postgres --source transition_ecologique
```

Si un mapping ou fichier a changé pendant un import incomplet, l'importeur
s'arrête. Après vérification de ce changement, `--restart` permet de relire
le snapshot depuis le début avec des upserts, sans effacer les données.
Cette option ne supprime pas des contributions absentes d'un nouveau fichier :
elle convient aux snapshots fixes décrits ici, pas au remplacement par un
jeu de données réduit.

Si une erreur concerne un enregistrement, le lot entier est annulé et le
message indique le formulaire et le numéro de l'enregistrement. Corriger
le problème puis reprendre ; ne pas ignorer silencieusement les réponses.

## Tests et ancien audit CSV

```bash
uv run --locked python -m unittest discover -s tests/ingest -v
GDN_IMPORT_TEST_DATABASE_URL=postgresql:///cahier_doleances_test uv run --locked python -m unittest discover -s tests/ingest -v
```

La première commande teste les lecteurs et transformations sans réseau ;
la seconde ajoute un test PostgreSQL qui annule ses données à la fin, après
création de la base de test et application des migrations selon
[TESTING.md](../TESTING.md). Il
vérifie la réimportation, le remplacement des choix, les pourcentages,
les mises à jour et suppressions, et les compteurs.

L'audit initial des CSV reste disponible :

```bash
uv run --locked python -m ingest.sources fetch --rows 1000
uv run --locked python -m ingest.sources audit
```

Il écrit [ingestion-audit.md](ingestion-audit.md). C'est un audit préliminaire
des premiers enregistrements ; le profil JSON complet et la vérification
PostgreSQL sont les contrôles de référence pour l'import final.

L’ancien importeur `ingest/gdn_ingest.py` et `scripts/import_from_csv.sh`
ne doivent pas être combinés avec cette procédure.
