# RAG-004 — Contrat documentaire et extraction PostgreSQL

Le contrat décrit les **unités textuelles consultables extraites**, pas les
représentations sémantiques ou segments d'embedding. Il n'assemble pas les
réponses d'une contribution et n'impose aucune stratégie parent-enfant.

## Contrat v1

`cahier_rag.contracts.TextUnit` est une dataclass immuable. Les champs sont
génériques ; les noms de tables et la structure JSON GDN sont confinés à
`sources.gdn`.

| Champ | Type Python | Signification |
|---|---|---|
| `corpus_id` | `str` | Namespace explicite de consultation, `gdn-2019` par défaut |
| `unit_type` | `UnitType` | `open_answer` ou `other_text` |
| `answer_id`, `contribution_id`, `question_id`, `questionnaire_id` | `int` | Références sources, BIGINT positif vérifié |
| `unit_index` | `int` | 0 pour une ouverte ; indice d'origine dans `other_text` sinon |
| `text` | `str` | Texte exact de l'unité normalisée par l'importeur |
| `question_text`, `questionnaire_name` | `str` | Libellé et contexte conservés séparément |
| `contribution_title` | `str` ou `None` | Titre distinct, jamais préfixé au texte |
| `answer_position` | `int` | Position de la réponse source |
| `question_position` | `int` ou `None` | Ordre de la question |
| `question_section`, `question_code` | `str` ou `None` | Contexte structurel |
| `question_type` | `str` | Type source, sans recodage sémantique |
| `questionnaire_version`, `questionnaire_source` | `str` ou `None` | Version et origine du questionnaire |
| `contribution_source`, `external_contribution_id` | `str` ou `None` | Origine et identifiant externe, sans conversion |
| `submitted_at` | `datetime` ou `None` | Date source ; le schéma GDN utilise un timestamp sans fuseau |

Le lecteur fournit le libellé, la source et la version du questionnaire, car
ils permettent de contextualiser et de distinguer les consultations. La date
est conservée sans lui inventer de fuseau. Les identifiants permettent de
retrouver `public.answers`, `public.questions`, `public.forms` et
`public.contributions` ; les futurs adaptateurs garderont leur propre mapping.
Le namespace doit distinguer les corpus réellement différents. Une restauration
conservant les IDs garde les identités ; une réimportation réattribuant les IDs
nécessitera une correspondance explicite, pas une supposition.

### Identité

```text
text-unit:v1:<corpus encodé URL>:<type>:<answer_id>:<unit_index>
```

`urllib.parse.quote(corpus_id, safe="")` encode les séparateurs du namespace.
L'identité ne dépend ni de l'ordre de parcours, ni du texte, ni d'un UUID.
Deux réponses identiques restent deux documents. Les éléments répétés d'un
même tableau restent des occurrences distinctes ; leurs indices ne sont pas
compactés lorsqu'un élément blanc est ignoré. Le type réserve des namespaces
distincts pour les futures unités.

### Empreinte et JSON

`CONTRACT_VERSION = 1`. `to_dict()` et `to_json()` incluent cette version,
`document_id` et `content_hash`. Les quatre IDs PostgreSQL deviennent des
**chaînes décimales** ; aucune conversion flottante. Les positions et indices
restent des entiers. Les identifiants externes restent des chaînes intactes.
Les valeurs facultatives sont explicites (`null`), les dates sont ISO 8601.

L'empreinte SHA-256 porte sur **tous les champs du tableau ci-dessus et la
version du contrat**, après cette sérialisation des IDs et dates. Elle exclut
uniquement les propriétés dérivées `document_id` et `content_hash`. Elle couvre
donc texte, contexte et provenance : elle n'est pas une clé de déduplication.
Une modification de titre ou de question change l'empreinte sans changer l'ID.

Le JSON canonique utilise UTF-8, `ensure_ascii=False`, clés triées, séparateurs
sans espaces et `allow_nan=False`. Aucune normalisation Unicode, d'accents ou
d'espaces n'est appliquée. Deux graphies Unicode distinctes ont des empreintes
distinctes. `to_json()` produit une représentation déterministe ; aucun export
sur disque n'est effectué par le lecteur.

## Adaptation du Grand Débat

### Réponses ouvertes

Seules les questions de type `text` produisent `open_answer`. Le texte vient
de `answers.text`. NULL et les chaînes dont `str.strip()` est vide ne produisent
pas d'unité. Ce test inclut les blancs Unicode ; **le texte non vide reste
inchangé**, avec ses espaces, retours à la ligne, accents et caractères spéciaux.
Aucun seuil de longueur : « Non », les doublons et les textes de plusieurs
centaines de milliers de caractères sont conservés.

Il s'agit du texte consultable, pas d'une reconstruction brute : l'importeur
privilégie parfois `formattedValue` et remplace U+0000 par U+FFFD. Le lecteur
ne lit ni `raw_json` ni les données d'auteurs.

### Textes « Autre »

Pour `single_choice` et `multi_choice`, `answers.text` n'est **jamais** utilisé
pour extraire du texte libre : il mélange les libellés et les « Autre ».
`value_json` est du TEXT décodé par Python, sans conversion SQL globale en JSONB.

Le code d'ingestion actuel produit un objet contenant `other_text: []` ou
`other_text: [chaîne]`. Le lecteur accepte une liste de plusieurs chaînes sans
inventer d'autre convention. Il ignore les éléments blancs, conserve leur
indice d'origine et ne coupe pas sur `|` ou les retours à la ligne.

| Cas | Politique |
|---|---|
| `value_json IS NULL` | Aucune unité |
| Objet sans `other_text`, ou tableau vide | Aucune unité |
| Tableau de chaînes | Une unité par chaîne non blanche |
| JSON malformé, objet remplacé par scalaire/tableau | Erreur `SourceDataError` |
| `other_text` non tableau ou élément non chaîne | Erreur `SourceDataError` |

Un JSON vide sous forme de chaîne ou `other_text: null` n'est pas une structure
produite par l'importeur actuel : il est signalé plutôt que silencieusement
assimilé à une absence. Aucune récupération depuis les libellés ou le JSON brut.
Les erreurs ne contiennent que le type d'anomalie et l'ID de réponse.

### Jointures et incohérences

Une requête paramétrée joint `answers → questions → forms` et
`answers → contributions`. Elle sélectionne uniquement les champs du contrat.
Les contributions et formulaires sont joints à gauche afin de détecter un
rattachement manquant. Le schéma migré garantit la présence de la question
par clé étrangère ; les questions sont jointes directement.

`q.form_id` et `c.form_id` sont sélectionnés séparément et comparés en Python.
Un désaccord provoque une erreur bloquante : pas de correction, de changement
de formulaire ou de rejet silencieux. Le filtre par questionnaire porte sur
la question et ne masque pas un désaccord de rattachement de la contribution.
La transaction est déjà fermée au moment de cette validation.

Les autres types de question ne sont pas sélectionnés. Les extensions futures
exigeront une règle explicite. Aucune jointure avec `authors`, `users`,
`options`, `answer_options`, `topics` ou `contribution_topics` n'est nécessaire.
Les thèmes ne sont pas considérés comme une classification opérationnelle.

`get_contribution(id)` fournit `ContributionMetadata` même sans réponse ouverte
ou sans réponse du tout. Cela garde les titres seuls identifiables, sans les
transformer en documents et sans parcourir toutes les contributions.

## Lots, curseurs et cohérence

`GdnReader` reçoit un moteur explicite et les filtres optionnels de questionnaire,
contribution et type d'unité. Les filtres pertinents sont paramétrés en SQL.
Le type se traduit par le type de question ; les tableaux JSON sont validés
ensuite en Python. Il n'y a pas de requête par document ni de pagination OFFSET.

Chaque lecture sélectionne au plus `batch_size` lignes, triées par `a.id ASC`.
La pagination utilise la clé primaire BIGINT de `answers`. Un lot peut être
vide en documents tout en contenant des lignes : son curseur avance quand même.
`source_rows` compte les lignes récupérées, y compris si une limite documentaire
interrompt leur adaptation.

`Cursor(answer_id, unit_index)` décrit une position **après** consommation :

- `unit_index=None` : toute la réponse a été traitée, SQL suivant `a.id > ID`.
- `unit_index=N` : l'unité N a été remise ; SQL suivant `a.id >= ID`, puis
  exclusion des indices `<= N` de cette même réponse.

`Cursor.after_document(document)` fournit le second cas. Un curseur sérialisé
par `to_dict()` contient l'ID en chaîne décimale et se recharge avec
`Cursor.from_dict()`. Il n'est ni un checkpoint persistant ni un token signé.
Le consommateur devra enregistrer sa progression seulement après avoir traité
les objets précédents. Il doit conserver avec elle le corpus, les filtres et
la version : le curseur seul ne détecte pas un changement de périmètre.

`read_batch(max_documents=N)` peut s'arrêter au milieu d'un tableau. La réponse
sera relue à la reprise, avec exclusion des unités déjà remises. `iter_batches`
et `iter_documents` acceptent une limite globale de documents ; zéro ne déclenche
aucune requête. Une fin exacte sur la taille de lot peut nécessiter un dernier
lot vide pour constater la fin. Une limite atteinte ne prétend pas que le corpus
est épuisé.

Les résultats SQL sont fermés et la transaction READ ONLY terminée avant le
retour du lot et avant tout `yield` au consommateur. L'arrêt anticipé ne garde
pas de connexion ouverte. L'appelant possède le moteur et doit le libérer.
Les données d'un lot correspondent au snapshot de son SELECT ; il n'existe
pas de snapshot global entre lots. La reproductibilité suppose le corpus et
les règles figés. Une modification ou suppression concurrente peut changer
une reprise ; la gestion de snapshots/manifests sera à préciser ultérieurement.

La mémoire dépend des lignes du lot et de la taille de leurs textes/JSON, pas
du corpus complet. Une ligne peut produire plusieurs unités, sans plafond
arbitraire sur le texte. Le lecteur n'accumule pas tout le corpus ; le consommateur
doit éviter de convertir un parcours complet en `list`.

## Schéma, performances et confidentialité

Les index existants comprennent la clé primaire de `answers`, les index sur
`answers.contribution_id` et `answers.question_id`, ainsi que les clés de
jointure. Ils permettent la progression par ID et les lectures ciblées.
Les index lexicaux partiels excluant les textes courts ne sont pas utilisés.
Aucun nouvel index ni aucune migration ajouté.

Les filtres par formulaire/type peuvent nécessiter de parcourir de nombreuses
lignes avant de trouver du texte libre, surtout pour les « Autre ». Une limite
documentaire ne borne pas le nombre de lots SQL nécessaires. Les filtres ne
garantissent pas un plan PostgreSQL précis ; évaluer ultérieurement les plans
sur des parcours représentatifs. La taille du lot ne borne pas le temps SQL.

Les tests PostgreSQL utilisent la base dédiée déjà migrée, pas une copie ORM
partielle. Le schéma actuel garde `question_stats.question_id` en INTEGER :
les déclencheurs empêchent d'y insérer des IDs de question proches de la borne
BIGINT. Ces IDs sont donc vérifiés dans les tests unitaires ; les intégrations
testent les BIGINT élevés sur réponses, contributions et questionnaires, avec
des questions compatibles avec les compteurs. Aucun changement du schéma.

Les textes peuvent contenir des données personnelles. Les exemples et tests
utilisent des textes synthétiques ; les contrôles du corpus ne journalisent
ni contenu ni profil. Aucun texte n'est envoyé à une API externe. Ne pas
journaliser les objets complets ou les paramètres de connexion.

## Suite RAG-005

Le stockage expérimental pourra recevoir des unités typées, un identifiant
stable, une empreinte, une version et des curseurs sérialisables. Il restera à
définir son schéma, ses manifestes de corpus/filtres, ses transactions et son
idempotence. Aucun stockage, checkpoint, modèle, recherche ou transformation
destinée aux embeddings n'est implémenté ici.
