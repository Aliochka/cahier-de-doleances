# SEARCH-001 — Audit des bases locales sur Hal9000

**Audit du 20 octobre 2026. Périmètre : Hal9000 uniquement.**

Seul ce rapport est créé, conformément à l'autorisation complémentaire. Aucune
connexion applicative, donnée, configuration persistante, table, fonction ou index
n'a été modifié. Aucune migration, inférence, réindexation ou intervention sur
Wallace n'a été réalisée.

## 1. Résumé exécutif

**La base `cahier_rag` ne peut pas remplacer directement
`cahier_doleances_local`.** Elle contient des documents de recherche et des vecteurs,
mais aucune des tables applicatives `answers`, `contributions`, `questions`,
`forms`, `authors`, `users`, `bookmarks`, etc.

Deux blocages indépendants interdisent une simple bascule :

1. Les requêtes FastAPI attendent le schéma relationnel historique dans `public`,
   avec ses statistiques, extensions et index. Il est absent de la base RAG.
2. `DatabaseGuard.transaction()` refuse une destination contenant le schéma
   applicatif. Cette protection est également utilisée par les **lectures** du
   moteur RAG : copier les tables historiques dans la base RAG bloquerait le
   moteur actuel, même avec deux URL distinctes.

Les vecteurs existants restent réutilisables : l'espace complet est déclaré vérifié,
les index contrôlés sont valides et les **25 unités comparées** correspondent aux
réponses sources, avec les mêmes identifiants, contexte et empreintes. Cela ne
constitue pas une comparaison exhaustive de tous les documents.

**Recommandation : scénario B, adaptation préalable.** Pour la première intégration,
conserver la base applicative et ajouter une connexion de recherche distincte vers
la base RAG est moins invasif qu'une unification. Si la base unique reste souhaitée,
il faudra d'abord transférer le schéma applicatif complet et adapter explicitement
les protections et responsabilités d'accès, sans affaiblir les garde-fous d'écriture.

## 2. Inventaire des bases et connexions

### Instance locale réellement interrogée

- Machine : `hal9000`.
- PostgreSQL **17.11**, paquet Ubuntu `17.11-1.pgdg22.04+2`.
- Cluster actif : **17/cahierlocal17**, port **5432**.
- Connexions d'audit par socket Unix ; adresse et port réseau retournés par
  `inet_server_addr()`/`inet_server_port()` nuls, comportement normal sur socket.
- Identifiant du cluster : `7697259424657850634`, commun aux deux bases.
- Répertoire du cluster indiqué par `pg_lsclusters` :
  `/var/lib/postgresql/17/cahierlocal17`.
- Tablespace des deux bases : `pg_default`.

| Élément | Historique | RAG |
|---|---|---|
| Base | `cahier_doleances_local` | `cahier_rag` |
| OID PostgreSQL | `16385` | `2106636` |
| Taille `pg_database_size` | **15 281 772 211 octets**, 15,28 Go / 14,23 Gio | **83 649 935 027 octets**, 83,65 Go / 77,91 Gio |
| Emplacement logique | `base/16385/` sous le répertoire du cluster | `base/2106636/` sous le même répertoire |
| Exemple de fichier relatif, fourni par PostgreSQL | `base/16385/16894` pour `public.answers` | `base/2106636/2142610` pour `rag_full.segments_full` |
| Propriétaire SQL / rôle d'audit | `ro` / `ro` | `ro` / `ro` |
| Extensions | `plpgsql` 1.0, `unaccent` 1.1, `pg_trgm` 1.6 | `plpgsql` 1.0, `vector` **0.8.7** |
| Schémas non système | `public` | `public`, `rag`, `rag_full`, `rag_tuning` |
| Tables, parents partitionnés compris | 16 | 19, dont 2 parents partitionnés et 4 partitions |
| Séquences / vues / vues matérialisées | 10 / 0 / 0 | 0 / 0 / 0 |
| Index de ces schémas | 59 | 46, y compris les index des partitions et parents |

Les chemins de fichiers sont des observations, pas des instructions de copie.
`data_directory` n'est pas accessible via `pg_settings` au rôle courant ; le chemin
du cluster provient de `pg_lsclusters`. Aucun privilège supplémentaire demandé.

Aucune table étrangère ni aucun serveur FDW n'est configuré dans ces deux bases.
Les dépendances entre elles sont donc applicatives, pas des jointures distantes
déjà provisionnées dans PostgreSQL.

### Configuration effective et fichiers responsables

| Composant | Configuration constatée | Résolution |
|---|---|---|
| Backend local | `.env` racine : `ENV=dev`, `DATABASE_URL=postgresql:///cahier_doleances_local` | `app/config.py` et `app/db.py` chargent dotenv sans écraser l'environnement |
| Backend en développement | `TEST_DATABASE_URL` puis `DATABASE_URL` puis `SCALINGO_POSTGRESQL_URL` | `app/db.py:31` ; la priorité de test peut masquer une modification de `DATABASE_URL` |
| Backend en production | `DATABASE_URL` uniquement ; alternatives refusées par la configuration | Constat de code uniquement, aucun environnement de production interrogé |
| Alembic applicatif | `-x db_url`, puis `ALEMBIC_DATABASE_URL`, puis `DATABASE_URL`, puis `alembic.ini` | `migrations/env.py` ; priorité différente de celle de l'exécution applicative |
| RAG source | `RAG_SOURCE_DATABASE_URL`, destination locale documentée `cahier_doleances_local` | `rag/src/cahier_rag/config.py` et `db.py` |
| RAG stockage | `RAG_DATABASE_URL`, destination locale documentée `cahier_rag` | Environnement ou fichier choisi explicitement avec `--env-file` |
| Frontend SSR | `API_BASE_URL`, origine HTTP(S) du backend | `frontend/app/lib/api.server.ts:22` ; **aucune connexion PostgreSQL directe** |

Le processus d'audit ne possédait aucune des variables PostgreSQL inventoriées.
La `.env` racine a été examinée uniquement pour les clés utiles, sans afficher de
secret. Aucun `rag/.env` n'était présent. Le RAG ne charge pas automatiquement la
`.env` racine et ne se replie pas sur `DATABASE_URL` : ses commandes documentent
des exports explicites, notamment dans `rag/corpus-complet.md` et
`rag/optimisation-recherche.md`. Son manifeste confirme la base source réelle,
comme détaillé ci-dessous.

Les connexions d'audit ont été construites explicitement vers les deux bases
locales. Ces constats ne prouvent pas les variables héritées par chaque processus
applicatif éventuellement lancé depuis un autre terminal. Aucun redémarrage ou
changement d'environnement n'a été effectué.

## 3. Comparaison des schémas et impact applicatif

Le `search_path` observé est `"$user", public` dans les deux bases. Changer ce
paramètre ne résoudrait pas les différences : `rag_full.documents` n'est pas une
table `answers`, et il n'existe pas de tables relationnelles de remplacement.

| Objets historiques dans `public` | Structure ou fonction utile | Dans la base RAG | Impact d'une bascule directe |
|---|---|---|---|
| `forms` | ID BIGINT, nom, version, source, `name_unaccent`, `tsv_name` TEXT | Absents | Liste et pages de questionnaires, recherche catalogue et liens impossibles |
| `questions` | ID/form_id BIGINT, libellé, type, positions ; `prompt_tsv` TSVECTOR généré, `prompt_unaccent`, `tsv_prompt` TEXT | Absents | Questions, contexte, statistiques et pagination indisponibles |
| `contributions` | ID/form_id/author_id BIGINT, titre, date, identifiant externe, données d'import | Absents | Pages de contributions et relations aux auteurs impossibles |
| `answers` | ID/contribution_id/question_id BIGINT, position, texte, `value_json` TEXT, `text_tsv` TSVECTOR généré | Absents | Lecture des réponses et recherche historique en erreur SQL |
| `options`, `answer_options` | Choix et associations réponse–choix, PK/FK | Absents | Réponses fermées et tableaux de bord incomplets ou en erreur |
| `authors` | Identité publique/anonymat, métadonnées et lien utilisateur | Absents | Pages auteurs et projection d'anonymat non disponibles |
| `users` | Compte, e-mail, activité, profil, nationalités, liens auteur | Absents | Authentification, création de compte et profils non fonctionnels |
| `bookmarks` | Utilisateur, type de page, ID BIGINT, unicité du couple utilisateur/page | Absents | Favoris non fonctionnels |
| `question_stats` | Compteur par question ; identifiants et compteurs INTEGER dans ce schéma réel | Absents | Compteurs et statistiques de questions/formulaires indisponibles |
| `answer_valid_stats` | Compteur historique de réponses selon un filtre applicatif | Absents | Donnée auxiliaire perdue ; ne pas confondre avec le nombre de TextUnit |
| `topics`, `topic_aliases`, `contribution_topics` | Tables et relations de thèmes, vides ici | Absents | Objets de compatibilité ORM manquants ; aucune classification opérationnelle à récupérer |
| `gdn_import_runs` | Suivi d'import et compteurs JSONB | Absent | Traçabilité/reprise d'import absente |
| `alembic_version` | Version applicative | Absent | Contrôle de déploiement et gestion des migrations applicatives incompatibles |
| `rag.*`, `rag_full.*`, `rag_tuning.*` | Stockage et recherche expérimentaux | Uniquement dans RAG | Structures supplémentaires, pas des substituts aux tables ci-dessus |

### Contraintes, séquences, index et fonctions

L'historique possède **16 PK, 16 FK, 10 contraintes uniques et une CHECK** au
catalogue ; toutes les contraintes examinées sont validées. Exemples déterminants :

- `answers → contributions`, `answers → questions`, `questions → forms`,
  `contributions → forms/authors`, `answer_options → answers/options` ;
- liens `users ↔ authors` et `bookmarks → users` ;
- unicités `(contribution_id, question_id, position)`, `(form_id, question_code)`,
  e-mail utilisateur et favoris ;
- dix séquences nécessaires aux insertions et à la préservation des futurs IDs.

La base RAG possède **19 PK, 18 entrées FK, 9 uniques et 66 CHECK** au catalogue.
Ces chiffres incluent les objets hérités/étendus par le partitionnement : ce ne
sont pas autant de règles logiques indépendantes. Ses FK sont **internes au RAG**,
notamment `segments → documents → spaces`. Il n'existe pas de FK vers
`public.answers` ou `public.contributions`, absentes, ni vers une autre base.

Les 14 index critiques du contrôle de déploiement applicatif sont présents et
acceptés dans l'historique, absents dans RAG. Ils comprennent les GIN de
`answers.text_tsv`, dont le partiel sur les textes d'au moins 60 caractères, ceux
des questions/formulaires, les trigrammes, les accès contribution/question et
les unicités de comptes/favoris. Les index RAG sur `search_vector` ne remplacent
pas ceux-ci pour le SQL existant.

Configuration FTS **`public.fr_unaccent` présente uniquement dans l'historique**.
Neuf fonctions applicatives hors extensions y sont présentes :
`answers_valid_stats_upd`, `gdn_answer_stats_delete/insert/update`,
`trg_answers_dec/inc/upd`, `trg_forms_update_search`,
`trg_questions_update_search`. Cinq triggers non internes sont actifs dans le
catalogue : trois sur `answers`, un sur `forms`, un sur `questions`.
Certaines anciennes fonctions subsistent sans trigger associé.

Dans RAG : aucun trigger non interne, aucune fonction SQL personnalisée hors
extensions, aucune configuration FTS personnalisée. Les primitives vectorielles
et opérateurs cosinus sont fournis par l'extension `vector`, pas par une fonction
SQL hybride autonome.

### Migrations et contrôle de compatibilité réellement exécuté

| Élément | Historique | RAG |
|---|---|---|
| Table de version | `public.alembic_version` | `public.rag_alembic_version` |
| Révision constatée | `remove_runtime_caches` | `rag_0007` |
| Tête du graphe correspondant dans le dépôt | `remove_runtime_caches` | `rag_0007` |
| `app.deployment_check.inspect_schema(..., 'remove_runtime_caches')` | **0 erreur** | **28 erreurs de compatibilité applicative** |

Les deux graphes sont indépendants et chacun est aligné avec sa propre base. Les
révisions différentes ne signalent pas un simple retard de migration à rattraper.
Le contrôle a seulement lu les catalogues et testé la normalisation d'un mot
synthétique ; aucune migration n'a été appelée.

Les modèles ORM ne décrivent pas seuls toutes les colonnes générées, triggers,
extensions et index physiques : un `Base.metadata.create_all()` ne constituerait
pas une préparation équivalente à l'historique.

## 4. Données et conservation des identifiants

### Volumes constatés et nature de la mesure

| Entité | Historique | Base RAG | Méthode et réserve |
|---|---:|---:|---|
| Contributions relationnelles | **1 589 285** | Table absente | COUNT historique borné à 2 s ; concorde avec les sept imports terminés |
| Réponses relationnelles | **15 792 750 selon les compteurs** | Table absente | Somme des 120 `question_stats`, identique à la somme des compteurs de réponses des imports ; pas de COUNT complet des 15,79 millions de lignes |
| Questions | **120** | Table absente | COUNT exact de la petite table |
| Formulaires | **7** | Table absente | COUNT exact ; IDs 2, 4, 5, 7, 10, 11, 12 |
| Options | **123** | Table absente | COUNT exact |
| Auteurs | **496 395** | Table absente | COUNT historique borné à 2 s |
| Utilisateurs / favoris | **0 / 0** | Tables absentes | COUNT exact ; absence de données aujourd'hui ne rend pas le schéma facultatif |
| Tables de thèmes | **0 ligne chacune** | Tables absentes | COUNT exact |
| TextUnit historiques partagées | Sans objet | **42 380** | COUNT exact de `rag.text_units`, tous corpus `gdn-2019` |
| Membres du corpus expérimental | Sans objet | **20 000** | COUNT exact de `rag.lexical_members` |
| Représentations vectorielles expérimentales | Sans objet | **20 067** | COUNT exact de `rag.vector_representations` |
| Documents complets | Sans objet | **5 172 356** | Compteur du manifeste `rag_full.spaces`, déclaré complet et vérifié ; pas de nouveau parcours intégral |
| Segments complets | Sans objet | **5 187 190** | Même méthode, pas de lecture intégrale des embeddings |

Les estimations `pg_class.reltuples` ont été distinguées des mesures ci-dessus :
elles ne sont pas utilisées comme totaux exacts. Par exemple, le catalogue estime
5 138 446 lignes dans `documents_full`, alors que le manifeste vérifié en annonce
5 172 356. Cela ne prouve pas une perte de documents : la comparaison exhaustive
n'a pas été refaite dans cet audit léger.

Le stockage partagé `rag.text_units` contient actuellement **41 277 réponses
ouvertes et 1 103 textes « Autre »**, avec 22 extractions et 42 390 associations
extraction-document. Les associations ne sont pas un nombre de documents distincts.
Les anciens tickets citant un cadre de 42 318 unités ne décrivent donc pas le
nombre actuel de lignes de cette table partagée. La cause historique de ces unités
supplémentaires n'a pas été recherchée ; cela ne modifie pas, à soi seul, le
manifeste gelé de 20 000 membres ni l'espace complet distinct.

**Les 5 172 356 TextUnit ne représentent pas l'intégralité des réponses de
l'application.** Elles conservent les réponses ouvertes et les textes « Autre »
exploitables, pas toutes les réponses à choix, associations d'options, profils
d'auteurs ou contributions sans texte retenu. Les probes indexées montrent des
documents complets pour les formulaires **4/5/7/10**, aucun pour **2/11/12**
(questionnaires rapides). Il n'existe pas de catalogue relationnel complet de
remplacement dans RAG.

Le compteur historique `answer_valid_stats` vaut **3 985 572**. Sa définition
applicative est différente du périmètre documentaire RAG ; il ne doit être ni
comparé comme un total équivalent ni remplacé par 5 172 356.

### Contrôles d'identité, de texte et de relations

Le manifeste complet désigne exactement le cluster courant et l'OID source
**16385**, la base `cahier_doleances_local`, sa révision `remove_runtime_caches`
et une borne `max_answer_id=15915250`. Cette borne correspond au dernier ID de
réponse lu par l'index historique, sans assimiler cet ID à un nombre de lignes.

Échantillon déterministe de **25 documents** : extrémités et quartiles des ordinaux,
15 positions pseudo-aléatoires de graine **1001**, complétés par des probes
questionnaire/type. Couverture des quatre questionnaires détaillés et des deux
types d'unités ; aucun `ORDER BY random()` ni OFFSET massif.

Pour chacun : lecture de la réponse historique par PK, jointures vers contribution,
question et formulaire, reconstruction via l'adaptateur existant
`sources.gdn.row_to_documents`, comparaison avec `storage.restore_document`.

**25/25 contrôles conformes** :

- réponse retrouvée et même identifiant documentaire dérivé ;
- IDs de réponse, contribution, question et formulaire conservés ;
- questionnaire de la question égal à celui de la contribution ;
- texte, titre, question, contexte et provenance identiques selon l'empreinte du
  contrat complet ;
- colonnes relationnelles RAG cohérentes avec le document JSONB.

Exemples vérifiés, sans recopier de texte citoyen :

| Document | Contribution | Question | Formulaire |
|---|---:|---:|---:|
| `text-unit:v1:gdn-2019:open_answer:11687:0` | 1005 | 47 | 4 |
| `text-unit:v1:gdn-2019:open_answer:3745849:0` | 210071 | 56 | 5 |
| `text-unit:v1:gdn-2019:other_text:81453:0` | 5389 | 159 | 7 |
| `text-unit:v1:gdn-2019:open_answer:7268702:0` | 579035 | 293 | 10 |

Cela établit une provenance concordante sur cet échantillon, **pas une égalité
exhaustive** de deux corpus. Il n'existe d'ailleurs pas de copie complète du
corpus relationnel dans RAG à comparer ligne à ligne.

### Liens et BIGINT

Les IDs relationnels pertinents sont BIGINT. `document_id`/`representation_id`
sont des identifiants textuels distincts des IDs de réponse. Une même réponse
peut produire plusieurs unités « Autre » et une unité plusieurs segments :
ne pas utiliser le document ou le segment comme une nouvelle contribution.

Les JSONB internes de `documents.record` stockent les IDs comme nombres exacts
PostgreSQL, restaurés en `int` Python. Ils ne doivent pas être envoyés bruts au
navigateur : le contrat `TextUnit.to_dict()` et les schémas API existants produisent
des **chaînes décimales**, nécessaires pour préserver de futurs BIGINT > 2^53.
Aucune conversion flottante n'a été utilisée dans les comparaisons.

Pour conserver les liens existants, il faudra garder les IDs, libellés servant aux
slugs et relations. Les pages actuelles comprennent notamment
`/forms/{form_id}`, `/questions/{id}-{slug}` et
`/forms/{form_id}/contributions/{contribution_id}#answer-{answer_id}`.
Le sélecteur historique `?contrib=<rang>` dépend aussi de l'ensemble des
contributions et de l'ordre `(submitted_at, id)` : recopier seulement les unités
indexées casserait cette correspondance, même avec des IDs individuels corrects.

## 5. Dépendances applicatives

| Fonctionnalité | Code examiné | Dépendance réelle et conséquence |
|---|---|---|
| Liste/détail des formulaires | `app/services/forms.py`, `routers/api_forms.py` | `forms`, `questions` ; absents de RAG |
| Questions, réponses et pages suivantes | `services/questions.py`, `services/answers.py`, `routers/api_questions.py` | `answers`, `questions`, `contributions`, `authors`, FTS et index ; filtres et curseurs propres à ces routes |
| Contribution complète et options | `services/contributions.py`, `routers/api_contributions.py` | Toutes les réponses et options d'une contribution, pas seulement les unités indexées |
| Auteurs publics | `services/authors.py`, `helpers.py` | Relations auteur-contributions et règles d'anonymat absentes du stockage documentaire |
| Recherche de réponses actuelle | `services/search.py`, `routers/api_search.py` | `answers.text_tsv`, `fr_unaccent`, jointures ; candidats récents, filtre de longueur et curseur ID, pas H1/RRF |
| Recherche de questions/formulaires | Mêmes services, deux sections de catalogue | `tsv_prompt`, `tsv_name`, `unaccent`, `question_stats` ; pas l'index documentaire RAG |
| Tableaux de bord/statistiques | `app/choice_stats.py`, API de statistiques, `frontend/app/routes/dashboard.tsx` | `options`, `answer_options`, `answers.value_json`, `question_stats` ; ne pas calculer sur un corpus de textes libres filtrés |
| Authentification et profils | `services/auth.py`, `routers/auth.py`, `app/models.py` | Lectures et écritures dans `users`/`authors`, séquences et liens croisés |
| Favoris | `routers/bookmarks.py` | `bookmarks`, utilisateur et ID/type de page ; unicités et écritures |
| SEO/sitemap | `routers/seo.py` | Contributions, dates, auteurs, formulaires, questions et compteurs |
| SSR React/Vite | `frontend/app/lib/api.server.ts`, `api.ts`, routes | Appels FastAPI via `API_BASE_URL`, validation des IDs chaînes et des contrats JSON ; aucune adaptation automatique au schéma RAG |

Les anciens caches `dashboard_cache`, `search_cache`, `search_stats` sont retirés
par la tête applicative `remove_runtime_caches` et absents des catalogues observés.
Ils ne sont **pas** une dépendance manquante à recréer pour cette application.

La recherche hybride future ne sera pas activée par une connexion différente :
il faudra relier un service de recherche à l'API et définir les résultats et la
pagination. Le classement ID/rang historique et les curseurs associés ne sont pas
directement des curseurs RRF. Les délais courants (SQL API 5 s, client public
20 s, middleware 29 s) devront être pris en compte, sans reprendre les réglages
expérimentaux de 30 s comme s'ils étaient déjà compatibles.

Le contrôle de santé `SELECT 1` peut réussir contre RAG malgré toutes ces tables
absentes : ce n'est pas un contrôle de compatibilité applicative.

## 6. Composants de recherche réutilisables

| Composant observé | Objets / état | Réutilisation et limites |
|---|---|---|
| Stockage documentaire expérimental | `rag.text_units`, extractions, associations, checkpoints | 42 380 unités partagées ; corpus de recherche gelé sélectionné par membres/manifeste, pas toute cette table |
| Lexical expérimental | `rag.lexical_corpora`, `lexical_members`, `lexical_vectors` | 20 000 membres et 60 000 vecteurs FTS pour les trois représentations |
| Vecteurs expérimentaux | `rag.vector_spaces`, `vector_representations` | Espace complet de 20 000 unités / 20 067 segments |
| Corpus complet | `rag_full.spaces`, `documents`, `segments`, partitions `full`/`pilot100k` | `full` déclaré vérifié : 5 172 356 unités / 5 187 190 segments ; pilote 100 000 / 100 258 |
| Embeddings complets | `segments_full.embedding`, `vector(1024)` | BGE-M3 dense, float32 stocké, normalisé ; pas besoin de les regénérer pour créer une nouvelle API |
| HNSW | `segments_full_hnsw` ; pilote séparé | Cosinus, `m=16`, `ef_construction=64` ; index `indisvalid` et `indisready` vrais |
| Recherche lexicale complète | `documents_full.search_vector` + GIN | Déjà présente, index valide/prêt ; séparation d'espace indispensable |
| Accès relationnels RAG | B-tree `(space_id, document_id)`, ordinal, formulaire/type et contribution | Permettent de relier les résultats aux IDs sources et de charger les documents |
| Statistiques lexicales | `rag_tuning.statistics`, `term_statistics` | Manifeste 314 656 lexèmes / 5 172 356 documents ; empreinte de corpus conforme à l'espace complet |
| Recherche et fusion | Python `fullcorpus/search.py`, `tuning/lexical.py`, `tuning/vector.py`, `search/hybrid/core.py` | SQL explicite, agrégation des segments et RRF côté Python ; aucun point d'entrée SQL autonome de recherche hybride |

Modèle figé dans le manifeste : **BAAI/bge-m3**, révision
`5617a9f61b028005a4858fdac845db406aefb181`, dimension 1024, préparation B,
budget 1024 tokens et chevauchement 128. Trois segments contrôlés ponctuellement
ont la dimension attendue et une norme compatible avec la normalisation ; aucun
balayage de l'ensemble des vecteurs ni test de rappel HNSW effectué.

Le manifeste RAG complet conserve l'empreinte
`bf1bac7a6c9af63c1cb5d465cd4611310f77e7923b75ce5d9fc105afedbcf4d3`.
Il référence la source historique par identité PostgreSQL, pas seulement par nom.
Une future copie dans une autre base devra formaliser son rattachement au corpus
sans réécrire silencieusement les manifestes historiques.

L'intégration dépend encore du package expérimental `cahier_rag` : stockage,
contrats, contrôles d'identité, préparation des requêtes, fusion et chargement du
modèle. L'encodage d'une nouvelle requête exige le modèle et sa recette compatibles,
même lorsque les vecteurs documentaires existent déjà. Les dépendances lourdes sont
optionnelles ; ce n'est pas une raison de les rendre obligatoires pour tout FastAPI.
L'adaptateur personnel charge actuellement BGE-M3 sur CUDA ; son orchestration avec
reranker/générateur n'est pas le simple service de recherche à intégrer.

Le profil RAG-027 personnel lit également un `selection.json` local ignoré par Git.
Les paramètres utiles à une application devront être explicites et reproductibles,
sans dépendance implicite aux répertoires de campagnes. Aucun de ces constats
n'impose de reconstruire les vecteurs ou leurs index.

## 7. Incompatibilités et risques

| Importance | Risque vérifié ou limite | Adaptation nécessaire avant bascule |
|---|---|---|
| **Bloquant** | Aucune table applicative dans RAG | Garder l'historique, ou transférer intégralement schéma et données applicatives |
| **Bloquant** | Garde RAG refusant toute destination avec `public.answers`, `forms`, `questions`, `contributions` ou `alembic_version` | Concevoir un accès de recherche strictement en lecture seule compatible avec la topologie retenue ; conserver les protections d'écriture existantes |
| **Bloquant** | Si source et destination sont unifiées, leur identité devient identique | Le design actuel l'interdit indépendamment des URL/rôles ; ne pas contourner le contrôle en changeant une chaîne de connexion |
| **Bloquant pour le code actuel** | `unaccent`, `pg_trgm`, `fr_unaccent`, colonnes générées et index applicatifs absents | Préparation explicite du schéma complet, pas de simple `search_path` ni de renommage de tables RAG |
| **Majeur** | Documents textuels ≠ totalité des réponses/contributions ; catalogues et choix manquants | Conserver les données normalisées complètes ; ne pas reconstruire l'application depuis les TextUnit |
| **Majeur** | Graphes Alembic distincts | Préserver deux tables de version et isoler les migrations ; ne pas confondre les têtes ni appliquer un stamp pour simuler une migration |
| **Majeur** | Rôle local `ro` propriétaire, avec droits INSERT/UPDATE/DELETE sur les tables contrôlées des deux bases | Séparer les rôles/connexions de recherche, application et maintenance ; l'audit reste protégé par READ ONLY, pas par un rôle réellement limité à SELECT |
| **Majeur** | Authentification/favoris nécessitent des écritures, même avec 0 compte aujourd'hui | Séquences, droits, contraintes et données de comptes à préserver ; éviter une connexion générale en lecture seule pour ces fonctionnalités |
| **Majeur** | Exposition directe du JSONB interne, des auteurs ou des métadonnées d'import | Adapter via les contrats publics, BIGINT en chaînes et projection d'anonymat existante |
| **Important** | Curseurs, règles de recherche et délais API ne correspondent pas au moteur hybride | Définir un service/contrat d'intégration ; ne pas réutiliser aveuglément la pagination ID historique |
| **Important** | RAG complet/pilote/20 000 unités coexistent | Imposer l'espace et le manifeste dans chaque recherche ; pas de sélection implicite de tous les documents |
| **Important** | Copie de schéma `public` potentiellement destructive pour `vector` et les versions | Ne pas supprimer/recréer `public`, la base ou l'extension vectorielle ; filtrer les objets à restaurer et contrôler la conservation de `rag*` |
| **Important, à vérifier dans une préparation future** | Autogénération Alembic non isolée sur une base unifiée | Examiner les filtres de métadonnées pour ne pas proposer de supprimer des objets de l'autre projet, notamment `rag_alembic_version` |

Les droits EXECUTE sur `pg_control_system()` ont permis le contrôle d'identité avec
le rôle actuel ; un futur rôle restreint devra être vérifié séparément. Les
politiques READ ONLY du moteur source et de cet audit sont actives, mais `ro`
n'est pas un rôle source matériellement protégé de toute écriture.

## 8. Recommandation : comparaison des scénarios

### A — Bascule directe

**À refuser en l'état.** Modifier `DATABASE_URL` vers `cahier_rag` ferait échouer
les fonctions de consultation, recherche, statistiques, comptes et favoris.
Cela ne sélectionnerait pas H1 à la place du SQL existant. L'absence de données
utilisateurs aujourd'hui n'enlève aucune de ces dépendances de schéma.

### B — Adaptation préalable

Deux variantes réalistes, sans recalcul des vecteurs :

1. **Variante recommandée pour commencer : deux bases, deux connexions.**
   Maintenir `DATABASE_URL` sur l'historique ; ajouter ensuite un accès de recherche
   à RAG, avec résultats reliés aux IDs historiques et hydratation bornée des
   métadonnées publiques. Les requêtes applicatives restent inchangées. Cela
   respecte l'architecture séparée de RAG-003/005 et évite une copie d'environ
   15 Go avant même d'avoir intégré le moteur. Aucune jointure SQL interbases
   n'existe aujourd'hui : prévoir deux lectures applicatives explicites.
2. **Variante base unifiée : application dans `cahier_rag`.**
   Copier le schéma historique et ses données sans renuméroter, préserver les
   séquences et deux graphes Alembic, installer les prérequis applicatifs manquants,
   puis adapter les accès RAG. Il faudra distinguer les opérations de recherche
   READ ONLY des migrations/écritures expérimentales que le garde actuel interdit
   volontairement sur une base contenant le corpus. Les nouveaux rattachements
   d'identité seront documentés sans modifier les expériences gelées.

La variante 2 est techniquement envisageable, mais **pas prête** et plus invasive.
L'intérêt d'une base unique doit être arbitré avant un ticket d'implémentation.
L'audit ne démontre aucun besoin de reconstruire les embeddings ou HNSW pour
l'une de ces variantes ; il ne certifie pas non plus une future migration physique.

## 9. Procédure locale proposée et vérifications restantes

**Procédure à préparer dans un ticket ultérieur ; aucune étape de mutation exécutée.**

1. Choisir explicitement la variante B et le périmètre de la première API hybride,
   sans génération conversationnelle imposée.
2. Conserver les configurations de référence, versions Alembic, nombres/empreintes,
   définitions d'index et sauvegardes récupérables des deux bases. Vérifier espace
   libre, taille des sauvegardes, WAL/temporaire et procédure de restauration avant
   toute copie. Les tailles observées ne sont pas une enveloppe de migration.
3. Préparer et tester le service de lecture de recherche avec rôles dédiés, contrôle
   d'identité et paramètres explicites. Préserver les garde-fous de maintenance,
   les manifestes et les artefacts historiques. Tester les écritures de comptes
   uniquement sur une base de test isolée.
4. Si base unifiée : préparer une restauration contrôlée des **objets applicatifs**
   (données, séquences, FK, triggers, extensions, FTS, statistiques et version)
   sans effacer `public`, `vector`, `rag`, `rag_full` ou `rag_tuning`. Ne pas recopier
   les données en réattribuant les IDs. Revalider les attaches source/manifeste et
   le fonctionnement des nouveaux accès READ ONLY avant de changer la connexion.
5. Vérifier compatibilité de schéma avec `inspect_schema`, comptes/relations,
   préservation des séquences, IDs et textes sur un échantillon plus large, puis
   couverture exhaustive par une méthode planifiée si une migration de données a
   effectivement lieu. Contrôler séparément l'intégrité des espaces vectoriels.
6. Valider en local les listes/formulaires, questions, pages suivantes, réponses
   ouvertes/à choix/« Autre », contributions complètes et liens anciens, auteurs
   anonymes, tableaux de bord, recherche catalogue, favoris et authentification.
   Vérifier les IDs chaînes et les réponses d'erreur côté SSR. Ne pas se limiter
   au healthcheck.
7. Pour la variante à deux bases : activer seulement le nouveau service de recherche
   par configuration explicite, avec désactivation possible sans toucher au corpus.
   Pour une base unifiée validée : prévoir une fenêtre locale sans nouvelles
   écritures de comptes/favoris, retirer les overrides de test/migration ambigus,
   puis seulement changer la connexion applicative et redémarrer l'application.
8. **Retour arrière :** désactiver le service hybride ou restaurer l'ancienne valeur
   de connexion, redémarrer et refaire les contrôles applicatifs. Conserver les
   deux bases et les index RAG. S'il y a eu des écritures utilisateurs sur la
   nouvelle base, les sauvegarder/réconcilier explicitement avant le retour ; un
   changement d'URL seul ne les rapatrie pas.

### Vérifications réellement effectuées

- Hôte, cluster local, identité réelle des deux bases, tailles, propriétaires,
  tablespaces et extensions.
- Catalogues de tables/vues/colonnes/types/défauts, PK/FK/uniques/CHECK, séquences,
  index, triggers, fonctions hors extensions et configuration FTS.
- Droits du rôle courant et absence de dépendance FDW.
- Têtes Alembic lues depuis les scripts, versions des bases et contrôle de schéma
  applicatif existant, sans appeler de commande de migration.
- Petits comptages exacts et comptages contributions/auteurs bornés à 2 s ;
  rapprochement des compteurs de réponses et des imports.
- 25 rapprochements document/source par accès indexés, avec empreintes complètes,
  relations et identifiants ; trois segments contrôlés ponctuellement.
- Lecture des services, routes et contrats FastAPI/SSR, des garde-fous et du
  mécanisme de configuration RAG.

Toutes les transactions SQL ont été explicitement READ ONLY, avec délais locaux
de 2 à 5 s et verrou borné à 500 ms. Les seuls changements de paramètres étaient
limités à ces transactions d'audit. Aucun benchmark de recherche, EXPLAIN ANALYZE,
export massif, scan intégral des embeddings ou appel GPU effectué. Un EXPLAIN sans
ANALYZE des agrégats historiques a servi à apprécier leur coût ; le COUNT massif
des réponses n'a pas été exécuté.

### Limites explicites

- Aucun COUNT intégral nouveau sur `answers`, `answer_options` ou les tables du
  corpus vectoriel complet ; les compteurs et manifestes ne sont pas présentés
  comme une nouvelle certification physique exhaustive.
- Aucun contrôle exhaustif des IDs/empreintes des 5,17 millions de documents.
- Aucun test HTTP fonctionnel, login, création de favori ou restauration : ces
  opérations seraient hors du périmètre de cet audit strictement en lecture seule.
- Aucun audit des variables privées de tous les processus lancés, de la capacité
  de restauration des sauvegardes ou des futurs droits d'un rôle non encore créé.
- Aucune nouvelle mesure HNSW, de latence ou de pertinence ; voir RAG-027 pour les
  réserves expérimentales déjà connues, sans les réévaluer ici.
- Aucun test pytest, Ruff ou uv requis pour une modification exclusivement
  documentaire ; ne pas lancer des fixtures potentiellement écrivantes pendant
  cet audit. Aucun code d'audit persistant ajouté.

### Références principales du dépôt

- Configuration : [app/db.py](../app/db.py), [app/config.py](../app/config.py),
  [migrations/env.py](../migrations/env.py),
  [configuration RAG](../rag/src/cahier_rag/config.py).
- Schéma/contrôle : [app/models.py](../app/models.py),
  [app/deployment_check.py](../app/deployment_check.py),
  [migrations RAG](../rag/src/cahier_rag/migrations/versions/).
- Lecture/provenance : [sources/gdn.py](../rag/src/cahier_rag/sources/gdn.py),
  [storage.py](../rag/src/cahier_rag/storage.py),
  [safety.py](../rag/src/cahier_rag/safety.py).
- Recherche/API : [app/services/search.py](../app/services/search.py),
  [contrat de recherche actuel](api-search.md),
  [services de contribution](../app/services/contributions.py),
  [statistiques](../app/choice_stats.py),
  [client SSR](../frontend/app/lib/api.server.ts).
- Cadrage/historique : [plan RAG](plan-rag.md), [audit initial](audit-rag.md),
  [audit du corpus](audit-corpus-rag.md),
  [rapport RAG-027](../rag/rapport-rag-027.md).

**VERDICT — NO GO : la bascule directe vers `cahier_rag` présente des
incompatibilités majeures de schéma, de données applicatives et de garde-fous.
Le scénario B doit être préparé avant toute bascule ; les vecteurs existants
peuvent être conservés.**
