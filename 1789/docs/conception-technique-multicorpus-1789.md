# Conception technique — multicorpus et intégration de 1789

Date initiale : 6 novembre 2026. Mise à jour : 7 novembre 2026. Orientation validée ; phase 1 implémentée en local, phases de recherche et publication non autorisées.

Ce document complète l’[audit architectural](audit-architecture-multicorpus-1789.md). Il décrit des structures et contrats futurs : aucun schéma, import, embedding, exclusion ou changement applicatif n’est appliqué par sa rédaction.

## Clarification définitive — deux familles de corpus

La plateforme conserve **deux modèles métier indépendants** :

- **Corpus documentaires** : Corpus → Document → Passage technique. `documentary` est générique uniquement au sein de cette famille : 1789, archives et collections documentaires futures. Le document est l’unité de résultat.
- **Corpus de questionnaires** : Corpus → Questionnaire → Question → Contribution → Réponse. Cette notation décrit la famille ; les relations réelles restent celles du modèle métier (question et contribution rattachées au questionnaire, réponse reliant question et contribution). Un deuxième corpus de questionnaires réutilisera et fera évoluer l’architecture métier du Grand Débat. Cette adaptation est hors périmètre de la phase 1 et ne doit pas être anticipée dans `documentary`. La réponse individuelle est l’unité de résultat.

Un seul moteur principal réunira leurs **adaptateurs de recherche**, avec deux classements globaux lexical/vectoriel, une seule RRF et aucun quota. Tous les corpus activés seront sélectionnés par défaut. Les contrats communs sont des contrats de recherche, pas un modèle métier universel. Le registre logique commun pourra référencer les deux familles sans recopier leurs données.

La consultation conserve deux expériences autonomes : catalogue/métadonnées/lecture intégrale/navigation documentaire et questionnaires/questions/contributions/réponses. L’accueil « Parcourir » et la recherche commune ne fusionnent pas leurs modèles métier.

La présente autorisation porte sur la phase 1 uniquement : aucun calcul lexical/vectoriel, aucune API publique, aucun frontend ni activation publique. Les propositions des phases suivantes restent des contrats de conception à expérimenter ultérieurement.

## 1. Décisions acquises et périmètre

**Acquis dans la demande :**

- Préserver les tables applicatives, identifiants, embeddings et index du Grand Débat ; aucune copie des millions de réponses dans le stockage générique.
- Installer les nouveaux corpus **documentaires** dans la même base PostgreSQL de recherche, avec un stockage générique indépendant des questionnaires. Les futurs questionnaires réutiliseront le modèle métier GDN après étude distincte.
- Commencer par l’exact vectoriel sur les passages admissibles de 1789, avec BGE-M3 et texte du passage seul.
- Construire deux listes globales de documents, lexicale et vectorielle, puis une seule RRF. Un résultat GDN est une réponse ; un résultat 1789 est un cahier.
- Conserver une sélection bornée ; rendre les profondeurs documentaires 50, 100 et 200 expérimentables.
- Conserver les sources historiques immuables ; décisions éditoriales externes, traçables et réversibles.
- Artois : exclure les passages 3 et 4 des deux branches ; conserver 1 et 2 et tout le texte intégral.
- Aunay-la-Côte/Avallon : conserver les huit passages, préciser le titre de présentation et signaler la lacune initiale de Stanford.
- Aucune exclusion retenue pour Castelnaudary, Albret, Auxerre, Châteauneuf-en-Thimerais et Montaigut ; conserver les incertitudes connues.
- Les 43 autres textes attendent une qualification éditoriale distincte. La navigation géographique reste hors périmètre.

**Recommandations de conception :** schéma, politique de publication initiale, formule lexicale expérimentale, contrats et étapes ci-dessous. Elles ne constituent pas des mesures de performance ni une autorisation de publication.

**Hypothèse de travail :** les 1 224 cahiers probables forment le périmètre candidat initial, sans assimilation à 1 224 validations humaines. La publication de ce périmètre reste à approuver explicitement. Aucun statut de frontières, même humain, ne vaut automatiquement décision de publication.

## 2. Contraintes de l’existant vérifiées

| Élément | Constat et conséquence |
|---|---|
| Stockage GDN | `rag_full.documents` représente une unité `TextUnit`, pas nécessairement une réponse entière ; `segments` contient ses représentations vectorielles. Les colonnes questionnaire/réponse sont obligatoires. Ne pas y insérer de faux identifiants historiques. |
| Partitionnement | LIST sur `space_id`, espaces `pilot100k` et `full`, pas sur corpus. Aucun changement de partitionnement GDN requis. |
| Recette H1 | `h1-public-v2-ts-rank` ; profondeur 50 par branche, sortie 50 unités, RRF 60 ; regroupement par `answer_id` après classement. |
| Plafonds | `HybridConfig` et `FullSearch.parameters()` plafonnent à 100 unités ; 200 documents ne s’obtiennent pas par un simple paramètre public. |
| Lexical | Français PostgreSQL, couverture IDF 0,5, couverture de termes 0,3, `ts_rank(...,32)` 0,2. Fréquences figées dans `rag_tuning`, liées à l’empreinte du corpus. |
| Vectoriel | BGE-M3, 1024 dimensions ; HNSW GDN conservé ; segments contextualisés par la question. Cette recette diffère volontairement de celle de 1789. |
| Publication | `SearchReader.validate()` vérifie notamment `rag_0007`, le corpus GDN, ses statistiques et son index HNSW ; ne pas désactiver ces contrôles. |
| HTTP/pagination | Budget global de 18 s, travail borné, instantanés en mémoire de 600 s et curseurs authentifiés ; pas de total exhaustif. |

Références : [contrats](../../rag/src/cahier_rag/contracts.py), [schéma GDN](../../rag/src/cahier_rag/migrations/versions/rag_0004_fullcorpus.py), [service H1](../../rag/src/cahier_rag/search/service/core.py), [lexical](../../rag/src/cahier_rag/tuning/lexical.py), [vectoriel](../../rag/src/cahier_rag/tuning/vector.py), [lecteur](../../rag/src/cahier_rag/search/service/reader.py), [instantanés](../../app/services/search_snapshots.py), [route publique](../../app/routers/api_hybrid_search.py).

## 3. Schéma générique proposé

### 3.1 Principes

Nom de schéma proposé : `documentary`. Pas de partitionnement initial, pas de base supplémentaire, pas de service d’indexation permanent ni de back-office éditorial. Le corpus GDN est connu du registre logique du service, mais ses documents restent exclusivement dans les structures existantes.

Identité publique : `(corpus_id, document_id)` et `(corpus_id, unit_id)`. Une **release** est une matérialisation versionnée d’un corpus et de ses recettes ; elle n’entre pas dans son identité stable. Deux releases peuvent conserver le même document et les mêmes unités, ou exposer de nouvelles étendues explicitement reliées à leurs prédécesseurs.

Le stockage permet plusieurs releases, mais ne conserve initialement qu’une release chargée par corpus documentaire ; une nouvelle copie n’est créée que pour tester/publier une évolution. Le registre référence la release active par corpus. Les noms SQL et colonnes ci-dessous sont des propositions, pas du DDL à exécuter.

### 3.2 Tables de contenu et de publication

**`documentary.corpus` — registre des nouveaux corpus**

| Colonne | Type proposé | Rôle |
|---|---|---|
| `corpus_id` | text, PK | Identité opaque stable ; reprendre `cahiers-1789-ap-stanford` |
| `slug`, `label` | text, slug UNIQUE | Routes et nom public ; slug indépendant de l’identité source |
| `description`, `metadata` | text, jsonb | Présentation et propriétés du corpus |
| `active_release_id` | text nullable | Release publiquement active ; NULL avant activation |

FK composite `(corpus_id, active_release_id)` vers `release`, établie après création des deux tables ; NULL autorise le chargement initial. Pas de ligne GDN exigée ici : l’adaptateur expose son manifeste existant au même registre logique. Un slug GDN réservé dans la configuration empêche une collision de routes.

**`documentary.release` — version et état de préparation**

PK `(corpus_id, release_id)`, FK corpus. Colonnes : `source_generation text`, `source_manifest jsonb`, `source_manifest_hash text`, `lexical_recipe jsonb`, `embedding_recipe jsonb`, `editorial_revision text`, `state text`, `counts jsonb`, `lexical_statistics jsonb`, `created_at timestamptz`, `validated_at timestamptz` nullable.

États bornés : `loading`, `verified`, `ready`. La phase 1 produit uniquement `verified` : `representations_ready=false`, `statistics_ready=false`, `publication_authorized=false`, pointeur actif NULL. Le champ `candidate` du document distingue les 1 224 cahiers candidats des 43 autres textes ; il ne donne aucun droit public. `source_inventory` conserve les 1 305 notices et les métadonnées des 38 notices sans texte, sans créer de faux documents extraits. `ready` implique intégrité et projections éditoriales cohérentes, statistiques lexicales prêtes et vecteurs présents pour toutes les unités admissibles à la recherche hybride. Seul le pointeur du corpus active une release. La recette garde modèle/révision, normalisation, précision de calcul/stockage et texte d’entrée ; aucun préfixe de métadonnées pour 1789.

Le manifeste et ses hash restent des copies fidèles des sources. L’identité de publication effective est une empreinte séparée de `(release, source_manifest_hash, editorial_revision, lexical_recipe, embedding_recipe, statistics_hash)`. Une correction de titre ne change jamais le hash du texte source.

**`documentary.document` — texte intégral et notice**

| Groupe | Colonnes proposées |
|---|---|
| Identité | `corpus_id text`, `release_id text`, `document_id text`, `extent_id text` |
| Source immuable | `source_title text`, `full_text text`, `text_sha256 text`, `source_metadata jsonb`, `provenance jsonb` |
| Ordre | `edition_order bigint`, `order_locator jsonb` |
| État documentaire | `document_kind text`, `boundary_status jsonb` |
| Projection éditoriale dérivée | `display_title text`, `warnings jsonb`, `catalogue_visible boolean`, `readable boolean`, `searchable boolean` |
| Recherche dérivée | `metadata_vector tsvector`, `filter_metadata jsonb` |

PK `(corpus_id, release_id, document_id)` ; FK composite release ; UNIQUE `(corpus_id, release_id, edition_order)`. `edition_order > 0`, hash SHA-256 de forme valide, titres non vides. Les trois booléens publics valent false au chargement ; le projecteur les établit à partir d’une décision explicite. Invariants proposés : recherche ⇒ lecture ; catalogue ⇒ lecture. Lecture seule sans catalogue/recherche reste possible.

`source_metadata` conserve notamment les titres Persée/Stanford distincts, catégories, annotations, rôles de composantes et statuts d’attribution. `provenance` contient source/révision/hash, positions absolues, URL Stanford/Persée, citation et pages avec leur méthode d’attribution. `filter_metadata` expose uniquement des champs normalisés autorisés, avec leur niveau de certitude ; il ne remplace pas les métadonnées originales.

Ordre 1789 : classement initial déterministe par `(volume, source_start, source_end, document_id COLLATE C)`, confronté à l’ordre du catalogue, puis matérialisé en `edition_order`. Conserver la clé source dans `order_locator`. Cet ordre est celui de l’édition, pas une chronologie historique. Une release nouvelle peut changer l’ordinal, jamais l’identité du document.

**`documentary.search_unit` — passage, positions et représentations**

| Groupe | Colonnes proposées |
|---|---|
| Identité | `corpus_id text`, `release_id text`, `unit_id text`, `document_id text`, `ordinal integer`, `unit_type text` |
| Tranche canonique | `start_offset integer`, `end_offset integer`, `text_sha256 text`, `source_metadata jsonb` |
| Représentations | `search_vector tsvector`, `embedding vector(1024)` nullable, `embedding_hash text` nullable |
| Projection éditoriale | `searchable boolean` |

PK `(corpus_id, release_id, unit_id)` ; FK composite document ; UNIQUE `(corpus_id, release_id, document_id, ordinal)` ; `ordinal > 0` et `0 <= start_offset < end_offset`. Conserver les IDs et les ordinals actuels ; les recouvrements de passages sont autorisés. `source_metadata` conserve leurs règles, tokens, références XML, positions absolues et liens historiques.

Le texte du passage est extrait de `full_text` par ses positions : pas de seconde copie obligatoire dans une colonne texte. Le `tsvector` sera produit en phase 2 à partir de la tranche exacte ; il reste NULL en phase 1, comme `metadata_vector`, `embedding` et `embedding_hash`. L’import vérifie le texte et son hash contre `passages.jsonl.gz`, sans produire de dérivé de recherche en phase 1. Au besoin, l’hydratation calcule la tranche côté serveur.

Les contraintes portant sur deux tables — borne de fin dans le texte parent, hash de tranche, document lisible pour une unité recherchable — sont vérifiées par l’import/projecteur dans une transaction puis par le contrôle de release. Un simple CHECK PostgreSQL ne suffit pas à exprimer ces vérifications croisées. Les comptes lecteurs n’écrivent pas dans ces tables ; les écritures de maintenance passent par le chemin contrôlé. Le prédicat public vérifie aussi les deux niveaux document/unité.

Une unité générique est initialement définie comme un texte encodable par la recette de sa release. Une seule représentation dense par unité suffit à 1789 ; refuser un dépassement de fenêtre sans troncature silencieuse. Un futur corpus nécessitant plusieurs segments pourra ajouter une table de représentations sous l’unité. Ce besoin ne justifie pas de la créer maintenant ni de modifier les segments GDN.

### 3.3 Index initiaux

| Table | Index requis | Justification |
|---|---|---|
| `document` | UNIQUE ordre par corpus/release | Catalogue et précédent/suivant par clé |
| `document` | GIN `metadata_vector` | Titre, lieu, ordre historique et contexte territorial |
| `search_unit` | UNIQUE document/ordinal | Lecture et extraction des unités d’un document |
| `search_unit` | GIN `search_vector` | Correspondances lexicales du texte |
| `editorial_decision` | UNIQUE révision/séquence ; B-tree cible/révision | Rejeu des décisions et consultation de leur historique |
| `lexical_term_statistics` | PK release/lexème | Lecture de fréquences pour les termes d’une requête |

Les PK/FK composites commençant par corpus/release donnent les accès aux releases. Pas d’index JSONB global par défaut ; ajouter uniquement un index d’expression pour un filtre réellement mesuré. Pas de B-tree sur un booléen seul. Les petits filtres documentaires peuvent être évalués sur les notices puis joints aux unités.

Pas de HNSW initial. L’ajouter ultérieurement sur le nouveau stockage ne nécessite ni réencodage ni reconstruction GDN. Il faudra mesurer le rappel sous filtres/exclusions ; un B-tree et un HNSW ne garantissent pas ensemble les meilleurs voisins d’un petit périmètre. L’exact reste le chemin de référence et le recours pour petits ensembles.

### 3.4 Pourquoi ces structures

Quatre tables structurent corpus, version publiable, texte intégral et unités. La release évite de mélanger nouvelles représentations et anciennes sources pendant une préparation. Une table de décisions et une table de fréquences, décrites ci-dessous, complètent le schéma : **six tables métier/dérivées au total**. Aucun système de tâches, workflow éditorial, table de lieux, table d’articles historiques ou copie des réponses GDN.

Le suivi technique des migrations est séparé de ces tables. Proposition : une petite chaîne Alembic propre à `documentary`, avec table de version dédiée, explicitement exécutée en maintenance. Cela préserve la révision `rag_0007` que le lecteur H1 actuel exige littéralement. Une future unification des chaînes reste possible ; modifier la révision RAG sans adapter ce contrôle rendrait H1 indisponible. Ne pas lancer automatiquement les migrations au démarrage du lecteur public.

## 4. Décisions éditoriales externes

### 4.1 Un fichier versionné et son registre SQL

Source de vérité proposée pour ce petit périmètre : un fichier déclaratif dans le dossier `1789/editorial/`, versionné dans Git, sans recopier les textes. Le fichier `1789/editorial/decisions.json` est créé en phase 1 ; il n’accorde aucune publication. Il contient des événements immuables et une version de format. Leur import idempotent alimente **`documentary.editorial_decision`**.

Colonnes proposées : `decision_id text PK`, `revision_id text`, `sequence integer`, `corpus_id text`, `source_generation text`, `document_id text`, `unit_id text nullable`, `expected_document_hash text`, `expected_extent_id text`, `expected_unit_hash text nullable`, `property text`, `value jsonb`, `reason_code text`, `justification text`, `evidence jsonb`, `decided_by text`, `decided_at timestamptz`, `supersedes_id text nullable`.

FK corpus ; FK optionnelle vers la décision précédente ; UNIQUE `(revision_id, sequence)`. La cible source n’a pas de FK vers une unique release SQL : la décision doit survivre à son retrait et pouvoir s’appliquer à une autre matérialisation du même artefact. Son existence et ses empreintes sont vérifiées au moment du rejeu. CHECK : propriété d’unité ⇒ `unit_id` et hash unité présents ; décisions de document ⇒ `unit_id` absent. Valeurs et codes de propriétés sont limités par le validateur de format.

Propriétés initiales : `search_enabled` pour une unité ; `display_title`, `warning`, `publication` pour un document. Une incertitude non bloquante est un avertissement motivé, pas une exclusion implicite. Un avertissement a une clé stable et éventuellement un intervalle source ; sa suppression est un nouvel événement. `publication` porte un objet explicite `{catalogue, read, search}`.

Une réintégration positionne `search_enabled=true` en succédant à la décision d’exclusion ; elle ne réactive pas un document non publié. Un retrait de titre de présentation utilise une valeur nulle pour revenir au titre source. Rejeter deux événements concurrents pour la même propriété sans succession explicite ; ne pas choisir le dernier selon une horloge ou un ordre de fichiers accidentel.

Le journal conserve l’auteur/provenance déclarés et les preuves ; pas de signature cryptographique ni interface de validation complexe à ce stade. Les noms internes et notes de travail ne sont pas exposés par l’API publique. Une révision possède une empreinte calculée sur le fichier canonique ; le commit Git est une provenance supplémentaire.

### 4.2 Application atomique et faille de réintroduction à éviter

1. Charger la release en `loading`, projections publiques désactivées.
2. Vérifier sources, IDs, offsets et empreintes.
3. Rejouer la révision éditoriale demandée sur les cibles exactes. Une cible absente ou une empreinte différente bloque la préparation ; aucune décision n’est ignorée silencieusement.
4. Construire titres, avertissements, autorisations et vecteurs lexicaux effectifs. `unit.searchable` exprime la permission individuelle ; `document.searchable` exprime la permission globale. Le prédicat d’admissibilité joint les deux.
5. Calculer les statistiques et représentations requises, puis vérifier leurs versions et leurs comptes. Passer à `ready` seulement après les contrôles.
6. Activer le pointeur de corpus après autorisation de publication, sans modifier l’artefact historique.

Une modification éditoriale ultérieure est préparée sous verrou de maintenance du corpus. Dans une transaction, rejouer les projections, mettre à jour les statistiques affectées et l’empreinte de publication ; une erreur annule toute la transaction. Pour une réintégration nécessitant un vecteur absent, préparer ce vecteur avant activation. Si la préparation devient longue, utiliser une nouvelle release inactive au lieu de maintenir un verrou long.

Le lecteur prend une identité de publication au début de la requête, la vérifie à la fin, et refuse un résultat si elle a changé. Les curseurs portent cette identité ; aucune ancienne page ne peut réafficher un passage retiré après leur création. Un retrait éditorial impose expiration de l’instantané, pas maintien d’un extrait interdit pendant dix minutes.

À chaque réimport, `editorial_revision` est obligatoire ; aucune option par défaut « tout indexer ». Une empreinte de contenu inchangée n’implique pas une politique inchangée. Les deux branches et le choix d’extrait utilisent le même périmètre admissible avant top-K.

### 4.3 Jeu initial à transcrire lors de l’implémentation

| Cible | Décision acquise | Contrôle attendu |
|---|---|---|
| Artois, `…2_1_1578` | Exclure `ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c` et `ap1789-technical-passage-1:32ae8c839247d77b503fba421372` | Passages 3 et 4 uniquement ; 1 et 2 recherchables |
| Artois, document | Avertissement de mélange de colonnes, zone relative `[5204,8878)` | Texte entier inchangé ; avertissement visible dans la lecture et sur la carte |
| Aunay-la-Côte, `…2_1_1602` | Huit passages conservés ; titre « Cahier des habitants d'Aunay-la-Côte, présenté au bailliage d'Avallon — 16 mars 1789 » | Titre source/Persée préservé ; métadonnées de présentation distinctes |
| Aunay-la-Côte, document | Avertissement : début de l’article premier absent de Stanford | Pas de correction OCR ni d’insertion du texte manquant ; attribution étayée par les pages imprimées 133–136 |
| Cinq autres dossiers | Pas d’exclusion ; réserves documentaires conservées | Une réserve de périmètre ne se transforme pas en exclusion automatique |
| 43 autres documents | Publication non acquise | Projections publiques false jusqu’à décision nominative ou liste explicite approuvée |

Sources des décisions initiales : instructions de l’utilisateur dans la présente mission ; pour Avallon, [notice Persée](https://www.persee.fr/doc/arcpa_0000-0000_1879_num_2_1_1602) et pages imprimées déjà examinées dans la vérification documentaire. Le futur fichier doit transcrire ces preuves et les hash réels, sans inventer une date de validation historique ni une validation humaine de frontières.

Inventaire de référence : 1 267 textes et 11 391 passages, dont 1 224 cahiers probables et 10 750 passages. Après les seules exclusions d’Artois : **11 389 unités individuellement admissibles** si l’on considère tous les textes ; **10 748** si seuls les cahiers probables sont autorisés à la recherche. Ce sont des comptes attendus conditionnels, pas des comptes d’import effectué. Les 641 passages des 43 autres textes restent conservés en préparation sans publication implicite.

## 5. Recherche autonome historique

### 5.1 Périmètre et filtres

Chaque appel résout d’abord une release active ou une release de laboratoire explicitement désignée. Périmètre effectif : document lisible et recherchable, unité individuellement recherchable, puis critères documentaires demandés. Le mode de laboratoire peut examiner des documents non publiés avec une autorisation distincte ; il applique toujours les exclusions, sauf expérience explicitement nommée et non publique.

Filtres structurés initiaux : corpus, type documentaire, volume, ordre historique et libellé de lieu/contexte. Leur disponibilité est déclarée par corpus ; un filtre non applicable ne disparaît pas silencieusement. Les champs spécifiques sont typés et autorisés côté serveur, jamais traduits en chemins JSON arbitraires fournis par le client.

Séparer les critères obligatoires et le texte libre : « ordre = clergé, lieu = Agen, sujet = impôt » définit un ensemble admissible avant les deux branches. Les métadonnées recherchées librement contribuent aussi au score lexical, sans devenir des préfixes vectoriels.

### 5.2 Vectoriel exact

Recette : BGE-M3 existant, même révision validée par le registre du projet, dimension 1024, normalisation et stockage float32 explicités ; entrée = tranche exacte du passage, sans titre ni contexte ajouté. Conserver l’empreinte du vecteur et de la recette. Les unités exclues peuvent rester sans vecteur ; une réintégration exige alors un calcul autorisé ultérieur, pas un vecteur fictif.

Pour chaque requête, encoder une fois puis calculer la distance cosinus de **toutes les unités admissibles**. Garder le minimum de distance par document et son unité témoin, puis trier les documents. Ne pas appliquer un top-50 de passages avant regroupement : un seul long cahier pourrait l’occuper.

À environ 11 000 vecteurs, un balayage représente environ 11 millions de coordonnées et 44,5 Mio de données vectorielles brutes au maximum de la collection complète. Ce sont des ordres de grandeur, pas une latence. Les IO, TOAST, caches et tris doivent être mesurés. Une sélection relationnelle matérialisée avant calcul garantit le périmètre exact ; conserver les index relationnels, ne pas désactiver tous les index par commodité.

### 5.3 Lexical : deux champs, une seule voix par cahier

`search_unit.search_vector` contient uniquement le passage. `document.metadata_vector` contient une liste contrôlée : titre de présentation, titre historique comme alias dédupliqué, lieu, territoire et ordre explicitement établis. Écarter les grandes citations/ancêtres bibliographiques répétés, les avertissements et les notes de décision. Ne pas indexer tout JSONB sans sélection.

Les métadonnées sont **stockées/indexées une seule fois par document**. La requête sélectionne les passages appariés ou les documents dont les métadonnées correspondent ; dans ce second cas, elle évalue leurs unités admissibles. Cela permet une combinaison de termes entre sujet et métadonnées sans copier les champs dans chaque ligne d’unité.

Formule expérimentale initiale commune aux futurs adaptateurs :

`L(p,d) = 0,5 × couverture_IDF(Tp ∪ Md) + 0,3 × couverture_termes(Tp ∪ Md) + 0,2 × fréquence(p,d)`

`fréquence(p,d) = (1−β) × ts_rank(texte_p, requête, 32) + β × ts_rank(métadonnées_d, requête, 32)`

`L(d) = max sur les unités admissibles p de L(p,d)`.

`Tp` et `Md` désignent les lexèmes positifs appariés dans le texte et les métadonnées. Un terme présent dans les deux ne compte qu’une fois en couverture. β initial proposé : 0,25 lorsque des métadonnées sont disponibles ; pour GDN sans champ documentaire ajouté, fréquence = `ts_rank` texte. β, la normalisation et l’effet des alias sont **à évaluer**, pas acquis. Les scores utilisent les mêmes poids, règles de tokenisation et statistiques par requête dans tous les stockages.

Le maximum, et non une somme des passages, évite de récompenser mécaniquement la répétition des métadonnées. Pour 1789, évaluer les unités admissibles avant maximum/top-K est abordable et garantit le classement selon la formule, sous réserve du plan SQL. Ne pas préfiltrer par un score texte seul puis ajouter les métadonnées : ce préfiltre pourrait perdre les meilleurs résultats combinés.

Les phrases exigées doivent apparaître intégralement dans un champ autorisé ; ne pas créer une phrase artificielle à la jonction titre/texte. Proposition pour la nouvelle recette : expressions exigées et exclusions littérales deviennent des contraintes communes sur le contexte unité+champs documentaires, appliquées aux deux branches avant sélection ; les exclusions correspondent à un match dans l’un ou l’autre champ. H1 historique garde sa sémantique actuelle. Ce changement doit être documenté et validé par tests produit ; une requête réduite à des mots vides produit un état explicite, pas une recherche vectorielle interprétée arbitrairement.

### 5.4 Passage présenté et fenêtre

Chaque branche conserve son témoin. Après RRF, choisir dans l’union des deux témoins celui soutenu par les deux branches ; sinon prendre celui de la branche ayant la plus forte contribution RRF au document, départage lexical puis ordinal et ID. Cela donne une règle explicable sans sommer des votes de passages. Garder les deux témoins dans les traces pour évaluation.

En cas de correspondance uniquement documentaire, le témoin lexical peut être choisi par la composante texte puis l’ordinal ; si aucune unité n’a de signal textuel, présenter la première unité admissible avec `match_origin=metadata` et `excerpt_selection=opening`. Ne pas la qualifier de passage textuellement pertinent. Un document sans aucune unité admissible ne produit pas de carte de recherche, même si son titre correspond ; il peut rester dans le catalogue.

L’extrait est une tranche de l’unité admissible, rendue par le serveur avec offsets et hash ; pas le préfixe d’une unité exclue. La pertinence du document ne dépend pas d’un raccourcissement cosmétique de l’extrait. Les offsets Unicode sont appliqués côté Python ; côté JavaScript, ne pas utiliser directement des indices UTF-16 pour les mêmes bornes.

Fenêtre : paramètres internes `branch_document_depth` D et `result_document_limit` W, avec `W <= D` initialement et valeurs 50/100/200. Page publique de 20 au maximum, indépendamment de D/W. Initialement D=W=50 ; les autres recettes sont accessibles au laboratoire avant exposition publique. Au plus 2D documents entrent dans la fusion des deux branches ; W cartes sont figées après hydratation et contrôle des autorisations.

## 6. Contrats internes multicorpus

### 6.1 Interfaces et objets

Ces signatures sont descriptives et ne constituent pas du code ajouté :

| Contrat | Champs/opérations essentiels |
|---|---|
| `SearchRequest` | texte, corpus sélectionnés, filtres typés, D/W, mode/recette ; filtre absent = tous les corpus activés |
| `PublicationIdentity` | identité stable de chaque corpus, génération source, révision éditoriale, recettes et statistiques ; hash global |
| `DocumentKey` | `corpus_id`, `document_id` opaque ; 2019 dérive une clé stable de `answer_id` |
| `UnitWitness` | clé document, ID unité existant, ID représentation éventuel, offsets, hash et origine du match |
| `Candidate` | clé document, score de branche, témoin, score secondaire/départage ; aucun rang local utilisé comme rang global |
| `CandidateBatch` | candidats, profondeur documentaire demandée/obtenue, exhaustion/cap atteint, mode exact/ANN et mesures |
| `CorpusAdapter` | `capabilities`, `publication_identity`, `lexical_candidates(request, stats, budget)`, `vector_candidates(request, query_vector, budget)`, `hydrate(keys, witnesses, budget)` |
| `LexicalStatisticsProvider` | prépare une seule fois N/DF/IDF des lexèmes de la requête pour l’ensemble sélectionné, avec empreinte de génération |

Le service conserve un encodeur commun. Les adaptateurs ne chargent pas chacun leur modèle et ne produisent pas des réponses hybrides finales indépendantes. L’adaptateur GDN traduit `TextUnit`/segments vers ces objets ; celui des nouveaux corpus joint les tables génériques.

Le registre logique réunit un adaptateur GDN et un adaptateur générique pouvant gérer plusieurs corpus documentaires. Ajouter un futur corpus documentaire au schéma générique ne crée pas un nouveau service ou une nouvelle implémentation de recherche si ses besoins sont déjà couverts.

### 6.2 Pipeline global

1. Valider la requête, canonicaliser les corpus (ensemble trié/dédupliqué), résoudre la publication ; un corpus inconnu est une erreur, pas un retour à tous.
2. Construire les ensembles admissibles avant toute sélection ; n’appeler que les adaptateurs concernés. Résoudre une seule fois les statistiques communes et le vecteur de requête.
3. Chaque stockage génère ses D meilleurs **documents distincts** lexicaux, avec la formule commune. GDN : maximum sur les `TextUnit` de chaque `answer_id`, jamais sur `contribution_id`.
4. Chaque stockage génère ses D meilleurs documents vectoriels : GDN par meilleur segment de toute unité de la réponse ; nouveau stockage par meilleur passage admissible.
5. Réunir et trier globalement les candidats lexicaux par score décroissant et clé stable ; garder D et attribuer leurs rangs globaux. Faire de même pour les distances vectorielles croissantes.
6. Appliquer une seule RRF documentaire : `RRF(d)=Σbranche 1/(60+rang_global_branche(d))`. Une absence d’une branche apporte zéro, pas un rang inventé. Départage final par `(corpus_id, document_id)` en collation C/ordre d’octets défini de manière identique en Python et SQL.
7. Garder W documents, choisir les témoins, hydrater et vérifier publication/intégrité. Retirer une source indisponible et compléter depuis la réserve classée si le budget le permet ; figer ensuite la sélection et les rangs de cartes.
8. Paginer cet instantané ; ne pas relancer H1 à chaque page ni dédupliquer page par page.

Obtenir D documents par stockage sert la génération de candidats, **pas un quota d’affichage** : après tri global, un corpus peut occuper zéro ou toutes les places. Pour un score commun et des top-D locaux exacts avec les mêmes départages, leur union contient le top-D global. Cette propriété ne garantit ni le rappel d’un ANN local ni le top-W d’une RRF à profondeur infinie : la RRF reste une recette bornée D, dont la sensibilité doit être mesurée.

Ne pas fusionner par RRF les rangs propres à chaque corpus : cela donnerait artificiellement une importance égale à leurs premiers résultats. Ne pas comparer non plus les scores RRF H1 déjà fusionnés à ceux du moteur historique ; l’adaptateur doit exposer ses branches séparées.

### 6.3 Adapter GDN sans reconstruire ses index

Pour le lexical, nouvelle requête sur le GIN existant : score des unités correspondantes, puis maximum par `answer_id` avant limite documentaire. Un agrégat sur toutes les unités lexicalement correspondantes peut coûter cher pour un terme fréquent : mesurer le plan ; aucun préfiltrage approximatif n’est introduit silencieusement. Un mode plafonné éventuel doit annoncer sa limite et être évalué séparément.

Pour le vectoriel, réutiliser les paramètres HNSW et la lecture des segments, mais agréger les candidats directement par réponse, pas seulement par `TextUnit`. Augmenter progressivement les segments demandés jusqu’à D réponses ou jusqu’au plafond de visites/candidats/budget. Les exclusions/filtres interviennent dans la requête ; leur présence SQL ne garantit pas le rappel du HNSW. Ne jamais basculer une grande population GDN en exact sans plafond.

La voie existante `ann_search()` et `FullSearch.parameters()` plafonne les unités à 100 et restaure des `TextUnit`. Créer un lecteur de candidats pour la nouvelle recette, en réutilisant les gardes, plutôt que modifier arbitrairement la recette H1 pour supporter 200. Les scores lexicaux doivent être calculés avec les statistiques communes **avant** le top-D local ; reclasser seulement un top-50 H1 ne suffit pas.

Un mode par question peut rester lexical comme aujourd’hui, avec corpus GDN implicite. La recherche commune n’introduit pas de vectoriel par question sans décision spécifique. Pour de petits filtres GDN, le précédent `exact-question` peut inspirer un plan, mais son seuil en unités n’est pas un seuil universel en vecteurs.

## 7. Statistiques lexicales sans recalcul massif GDN

### 7.1 Choix proposé dès maintenant

Conserver l’unité statistique existante : **unité textuelle**, et non réponse/cahier. Pour la nouvelle formule, définir une unité virtuelle par passage dont le lexique est l’union du texte et des métadonnées documentaires autorisées. Les métadonnées ne sont pas copiées dans les lignes, mais leur présence est comptée une fois dans chaque unité virtuelle ; cette convention rend la DF cohérente avec le score `Tp ∪ Md`.

Ajouter **`documentary.lexical_term_statistics`** : PK `(corpus_id, release_id, term text)` ; `document_frequency bigint > 0`. FK release ; nombre total d’unités admissibles N, recette et hash dans `release.lexical_statistics`. DF doit être <= N, contrôlé lors de la construction. Les unités/documents non recherchables ne comptent pas. Un terme présent dans le texte et les métadonnées d’une unité ne compte qu’une fois.

Pour une requête multicorpus, sommer les N et les DF des corpus sélectionnés, puis utiliser la formule H1 `idf(t)=ln(1+(N−df(t)+0,5)/(df(t)+0,5))`. La DF GDN vient directement de `rag_tuning.term_statistics`, N de ses statistiques existantes. Pas de nouvelle lecture de ses millions d’unités. Les nouveaux corpus apportent des fréquences calculées sur leur seul petit stockage.

La requête 1789 seule utilise ses propres fréquences. La requête GDN seule peut retrouver les fréquences H1 d’origine. Pour des filtres de volume, lieu ou question, conserver les statistiques du corpus sélectionné plutôt que recalculer des DF à chaque sous-périmètre. Cette convention est explicite, stable, et proche du mode H1 par question ; les filtres affectent les candidats, pas la population statistique de référence.

Les fréquences GDN sont conservées dans leur périmètre publié historique ; elles ne deviennent pas des fréquences de réponses uniques par simple changement de regroupement. Les filtres rares et l’IDF des petits corpus feront partie de l’évaluation.

### 7.2 Limites et expériences

- Les passages chevauchants et la répétition conceptuelle de métadonnées influencent leurs DF ; le maximum documentaire évite une somme de voix mais ne supprime pas tous les biais de longueur.
- β, le poids des titres/alias, le français avec ou sans normalisation d’accents adaptée, et l’orthographe historique doivent être évalués. Commencer avec la même configuration `pg_catalog.french` que les index H1 pour éviter une incompatibilité de lexèmes. Un autre analyseur impose des statistiques compatibles ; ne pas réutiliser des DF d’un analyseur différent.
- Une statistique au niveau de la réponse/cahier serait conceptuellement plus homogène, mais exigerait des DF distinctes par réponse GDN, donc un calcul initial substantiel. Ce n’est pas requis pour la version initiale.
- Comparer une variante de couverture sans IDF à la formule commune fournit une expérience peu coûteuse. Ne pas remplacer les scores par des rangs locaux pour éviter la question de leur comparabilité.
- Ajouter un corpus met à jour les fréquences de ce corpus et la composition de la publication. Une correction éditoriale historique exige de reconstruire ou ajuster uniquement ses fréquences. Aucun nouveau calcul GDN n’est nécessaire si sa génération reste inchangée.

## 8. Performances, pagination et référence H1

### 8.1 Paramètres séparés

| Paramètre | Sens | Valeur initiale proposée |
|---|---|---|
| D | Documents par branche globale et profondeur demandée à chaque stockage | 50 ; recettes de laboratoire 100 et 200 |
| W | Documents conservés après RRF | 50 ; W <= D |
| Taille de page | Cartes rendues par requête HTTP | 20 maximum |
| Candidats ANN | Segments GDN explorés, différents de D | Base actuelle 400, augmentation bornée à mesurer |
| `ef_search`, visites, mémoire | Effort HNSW, pas profondeur documentaire garantie | Profil H1 comme référence ; expériences séparées |
| Budget | Encodage, SQL, fusion, hydratation et attente | Budget commun explicite, référence actuelle 18 s |

Conserver le worker/encodeur persistant et l’admission bornée. La fédération peut commencer séquentiellement sous le même budget ; n’introduire une concurrence SQL limitée qu’après mesure. Pas de multiplication des pools et threads par corpus. Instrumenter attente de file, encodage, lexical, vectoriel, agrégation, fusion et hydratation séparément.

### 8.2 Instantanés

Réutiliser le principe `SnapshotCache` : pas de texte canonique complet en mémoire. Références = clé documentaire, témoins, hash, rang, identité de publication et recette. Empreinte de requête : texte normalisé, corpus triés, filtres, mode, D/W et taille de page. Modifier un filtre supprime le curseur ; expiration, changement de publication ou recette renvoient une erreur de sélection expirée.

Les reprises ne recalculent pas la recherche. L’hydratation vérifie encore la politique et les empreintes. Une indisponibilité tardive peut raccourcir une page avec avertissement ; ne pas recomposer les rangs entre pages. L’API affiche `document_count` et `exhaustive=false`, jamais un total de correspondances dans le corpus.

Le cache actuel est local au processus. Conserver une seule instance de recherche ou un routage cohérent pour les curseurs pendant les premiers essais. Une réplication multi-processus non coordonnée provoquerait des expirations ; un cache partagé n’est à ajouter que si le déploiement le nécessite.

### 8.3 H1 comme référence

Conserver recette, statistiques, index et route publique actuels jusqu’à validation de la nouvelle voie. Introduire une entrée de laboratoire distincte pour `historical-v1` et `multicorpus-v1`, sans activation implicite en production. H1 utilise son propre lecteur et manifeste GDN ; la nouvelle publication encapsule cette identité au lieu de la remplacer.

Comparer sur les mêmes requêtes et la même génération GDN : H1 inchangé ; nouvelle recette GDN seul ; nouvelle recette GDN+1789. Le premier écart isole regroupement/statistiques/formule, le second l’effet multicorpus. Enregistrer rangs de réponse, unités et segments témoins, union des branches, nombre de documents, durée et rappel ANN. Une différence de classement n’est pas en soi une régression : la faire juger au niveau de la réponse, pas de la contribution.

Mesures : nDCG/precision@10, rappel documentaire à 50/100/200 sur un sous-ensemble jugé, qualité de l’extrait, biais de longueur, résultats manquants sous filtre, p50/p95/p99 et débit concurrent. Pour 1789, l’exact constitue la référence vectorielle. L’exact massif GDN, s’il devient nécessaire pour une petite campagne, exige un protocole isolé autorisé et borné.

## 9. Contrats backend/frontend et consultation

### 9.1 API documentaire proposée

| Route logique future | Réponse essentielle |
|---|---|
| `GET /api/v1/corpora` | Corpus activés, slug, label, description, capacités de filtres/parcours ; GDN fourni par l’adaptateur |
| `GET /api/v1/corpora/{slug}/documents` | Catalogue publié, filtres simples, cartes et curseur d’ordre d’édition versionné |
| `GET /api/v1/corpora/{slug}/documents/{opaque_id}` | Titre de présentation, titre(s) source, texte, métadonnées publiques, références, avertissements, identité/version, voisins |
| Paramètre `unit_id` de lecture | Unité rattachée au document, offsets/ancres et avertissements ; autorisée même exclue de la recherche si le document est lisible |
| Recherche commune, contrat versionné | Requête/corpus/filtres normalisés, recette, sélection bornée, cartes typées, curseurs, avertissements de disponibilité |

Encoder les identifiants opaques et vérifier l’appartenance corpus/document/unité. Les IDs 1789 ne passent pas dans le type numérique `PublicId`. Une ancre `unit-<id encodé>` reste fondée sur l’ID source. Un lien de recherche conserve aussi la version ; si la version n’est plus servie, proposer le document courant avec indication explicite, sans appliquer d’anciens offsets au nouveau texte.

Catalogue : ordre d’édition et clé stable, pagination keyset liée à la release. Précédent/suivant parcourent le même ensemble catalogue publié ; ne pas suivre les voisins techniques de passages ni l’ordre de pertinence d’une requête. Le lecteur reçoit du texte sûr ; aucun HTML source arbitraire n’est injecté.

### 9.2 Carte de recherche commune

Champs communs : `key`, `kind` (`gdn_answer` ou `historical_document`), `corpus`, `title`, `rank`, `excerpt` (texte, unité, offsets, origine de sélection), `metadata`, `warnings`, `url`. Champs GDN propres : réponse, question, formulaire, contribution. Champs historiques propres : titre source, lieu/ordre avec certitude, volume/pages et références.

Les traces de scores, notes internes et identités des décideurs ne sont pas publiques. La carte GDN continue de pointer vers sa réponse dans la contribution ; aucune fusion des différentes réponses de cette contribution. Les clés React et le rapprochement de pages utilisent la clé documentaire complète.

Le document 1789 affiche tout le texte, y compris passages exclus. L’avertissement Artois peut marquer la zone par une note discrète ; le lecteur ne masque pas des caractères et ne modifie pas la tranche canonique. Un avertissement de lacune initiale Avallon reste au niveau documentaire. Le choix des passages de recherche et les ancres sont calculés côté serveur pour préserver Unicode et espaces.

### 9.3 Parcourir et réutilisation

Créer `/parcourir` comme accueil par corpus ; rediriger `/enquetes` vers la nouvelle entrée canonique. Le GDN conserve ses routes formulaires/questions/contributions et son catalogue interne ; un corpus ne se confond pas avec un questionnaire. Routes historiques proposées : `/parcourir/cahiers-1789` et son lecteur documentaire ; les slugs finaux restent à valider.

Réutiliser [PageContainer et DocumentNavigation](../../frontend/app/components/layout/document-navigation.tsx), les cartes/styles de lecture, états de données et [ListNavigation](../../frontend/app/features/pagination/list-navigation.tsx). Adapter [surveys.tsx](../../frontend/app/routes/surveys.tsx), l’en-tête, [search-url.ts](../../frontend/app/features/search/search-url.ts), loader SSR, contrôles et [résultats](../../frontend/app/features/search/search-results.tsx). Étendre les [schémas publics](../../app/schemas/hybrid_search.py), l’hydratation et les types OpenAPI de façon coordonnée.

Le filtre de corpus est conservé dans l’URL, défaut tous ; sa modification réinitialise la sélection. Aucun quota ni nouvelle carte géographique. Le lecteur local `/passages` sert de référence pour les offsets et les avertissements, pas de backend public : ses modes Cahiers/Articles et journaux privés restent distincts.

Par défaut, une recherche « tous corpus » ne doit pas masquer un corpus indisponible. Proposition initiale : erreur explicite si un adaptateur requis manque ; le mode partiel ne sera ajouté qu’avec `partial=true` et corpus absents affichés, après arbitrage.

## 10. Réalisation progressive et réversible

La phase 1 est autorisée et implémentée ; les phases 2 à 4 nécessitent chacune une autorisation ultérieure. Les essais commencent dans une base isolée et avec des URL de source vérifiées ; aucun script ne déduit sa destination d’une variable de production par défaut.

### Phase 1 — Stockage et décisions

- **Réutiliser :** principes d’empreintes, gardes de base/rôles et imports reprenables ; lire directement les fichiers de référence. Ne pas relancer l’extraction G6.
- **Créer :** migrations génériques additives, import idempotent, validateur de décisions et projecteur, manifeste de release, commande de contrôle réellement en lecture seule.
- **Dépendances :** archive locale restaurable et hash vérifiés ; choix du périmètre éditorial ; source de décisions versionnée.
- **Risques :** mauvaise cible SQL, données locales absentes d’un clone, mauvais UTF-16/Unicode, perte d’une exclusion au réimport, confusion entre hash source et projection.
- **Tests :** import/reprise sans doublons, 1 267 textes/11 391 unités conservés, tranches et empreintes exactes, ordre et FK, décisions Artois/Avallon, 43 textes non publics, refus d’une décision périmée, rejouabilité et réintégration sans effacement d’historique. Comparer comptes et empreintes GDN sans les modifier.
- **Passage de phase :** intégrité complète ; décisions projetées et documentées ; aucun effet sur la lecture H1. L’autorisation publique n’est pas requise pour passer aux essais isolés.
- **Retour arrière :** aucun corpus actif ; désactiver le lecteur générique et conserver les tables inactives. Ne pas imposer un downgrade destructeur.

### Phase 2 — Recherche 1789

- **Réutiliser :** BGE-M3, gestion de modèle, budgets, normalisation lexicale et principe RRF/instantanés.
- **Créer :** préparation lexicale texte/métadonnées, fréquences, calcul des seuls vecteurs historiques admissibles, exact vectoriel, regroupement et témoin, route/outil de laboratoire.
- **Dépendances :** phase 1 vérifiée ; recette d’encodage fixée ; protocole de requêtes historiques jugées.
- **Risques :** métadonnées trop fortes, biais des longs cahiers, extrait exclu, latence IO, vocabulaire historique/OCR.
- **Tests :** oracle exact de maximum par cahier ; unicité pour D=50/100/200 ; expression mêlant filtres documentaires et sujet ; aucun des deux passages Artois dans aucune branche ni extrait ; huit passages Avallon admissibles ; exclusions chevauchantes ; corpus sans unités admissibles ; pagination/expiration ; p95 et débit à chaud/froid.
- **Passage de phase :** résultats jugés exploitables, exclusions démontrées, budget mesuré acceptable selon seuils convenus ; publication toujours désactivable.
- **Retour arrière :** désactiver la route historique ; conserver source et décisions, supprimer/recalculer uniquement les dérivés après autorisation si nécessaire.

### Phase 3 — Recherche multicorpus

- **Réutiliser :** GIN/HNSW GDN, statistiques existantes, lecteurs protégés, worker et cache ; préserver la voie H1.
- **Créer :** adaptateurs de candidats, statistiques communes, agrégats par réponse/cahier avant limite, classements globaux, nouvelle recette et instrumentation comparée.
- **Dépendances :** phase 2 validée ; exemplaire isolé représentatif du GDN ; seuils de rappel/latence et jeu transversal jugé.
- **Risques :** lexical fréquent coûteux, HNSW sous filtre pauvre en candidats, comparabilité de scores, épuisement du budget, effet de la nouvelle profondeur.
- **Tests :** filtrage avant top-K, corpus unique/multiple/tous, aucune fusion par contribution, aucune RRF de rangs locaux ; comparaison H1/GDN nouveau/GDN+1789 ; sensibilité D/β ; absence de quotas ; cas de branche vide, corpus indisponible et changement de révision en cours de requête.
- **Passage de phase :** validation humaine de pertinence et des écarts H1 ; seuils de performance respectés à la charge cible ; aucune reconstruction d’index GDN requise.
- **Retour arrière :** sélectionner H1 et retirer l’activation multicorpus. Conserver index/statistiques GDN inchangés et artefacts d’évaluation.

### Phase 4 — Interface publique

- **Réutiliser :** SSR, composants de lecture/navigation, catalogue GDN, routes existantes et contrat d’erreurs.
- **Créer :** Parcourir par corpus, catalogue/lecteur historique, cartes typées et filtre de corpus ; redirection canonique.
- **Dépendances :** phases précédentes validées ; décision explicite de publication ; API typée versionnée et sources consultables sans moteur chargé.
- **Risques :** liens cassés, perte de filtres/cursors, avertissements invisibles, fuite de notes privées, ancre erronée après changement de version.
- **Tests :** SSR et accessibilité, URL/rechargement/retour, précédent/suivant selon catalogue, ancres Unicode, lecture des passages exclus avec avertissement, absence des 43 textes non autorisés, affichage Avallon, anciens liens GDN, chargement progressif sans doublon, panne de recherche laissant la lecture disponible.
- **Passage public :** feu vert documentaire et produit, essais de restauration/retour arrière, métriques observables et aucune régression bloquante.
- **Retour arrière :** désactiver nouvelles entrées/recherche par drapeau de déploiement, revenir à la publication et au frontend précédents. Conserver une stratégie explicite pour les URLs historiques déjà publiées ; ne pas les servir avec des offsets faux.

## 11. Points à arbitrer et critères à mesurer

| Sujet | Statut |
|---|---|
| Artois, Avallon, absence d’autres exclusions | Décisions acquises, à transcrire fidèlement |
| Publication des 1 224 cahiers probables | Périmètre candidat proposé ; approbation explicite à obtenir avant activation |
| Qualification des 43 autres textes | Décision documentaire au cas par cas, hors automatisme de type |
| Six tables génériques et migrations isolées | Proposition à valider ; aucune nécessité de toucher au schéma GDN |
| Statistiques communes d’unités + fréquences GDN existantes | Solution initiale proposée ; pas de recalcul massif GDN |
| Formule lexicale, β, choix de champs et analyseur | Recette expérimentale ; comparer avant adoption |
| Passage témoin | Règle déterministe proposée ; évaluer la qualité des extraits et le cas métadonnées seules |
| Expressions/exclusions communes aux deux branches | Sémantique produit à confirmer ; H1 reste inchangé |
| D/W 50, 100, 200 | Paramétrage conçu ; choix public dépend des mesures |
| Performance | Fixer budgets p95/débit, plafond ANN, rappel minimal sous filtres et tolérance aux écarts H1 avant le benchmark |
| Panne d’un corpus | Erreur explicite recommandée initialement ; résultats partiels demanderaient une décision supplémentaire |
| URLs et présentation des incertitudes | À valider sans refonte graphique |

Les invariants non négociables des tests sont : aucun passage exclu dans les deux branches ou les extraits, aucune réintroduction silencieuse, aucune modification des sources/IDs/hash historiques, aucun regroupement GDN par contribution, et aucun quota de résultats par corpus. Les autres paramètres doivent être départagés par les performances réelles et les jugements documentaires, pas par la seule proportion de résultats historiques affichés.

## Phase 1 effectivement livrée

Le package indépendant `documentary/` contient une migration `doc_0001`, une validation des artefacts, un import atomique idempotent, un rejeu éditorial append-only et une vérification sans écriture. Le mode local strict exige un socket privé sous `/tmp`, le nom `documentary_*_test`, le répertoire physique et l’identifiant système PostgreSQL attendus. Il refuse les bases applicatives et les schémas RAG. Ce garde volontairement restrictif ne constitue pas encore un outil de déploiement vers la base de recherche partagée : une mission ultérieure devra prévoir ce déploiement sans perdre les garanties d’identité.

Les notices sans texte sont conservées dans le manifeste SQL de release, les textes des passages ne sont pas dupliqués. Les futures colonnes de recherche restent NULL, les statistiques lexicales restent vides et aucune release n’est publiquement active. Les décisions individuelles d’unité ne rendent pas les documents publics. Le rejeu ne modifie aucune colonne source et refuse les décisions supprimées, modifiées ou liées à de mauvaises empreintes.

Consulter [le mode d’emploi](../../documentary/README.md) et [le rapport de phase 1](rapport-phase1-documentary.md) pour les commandes, preuves et limites effectives.
