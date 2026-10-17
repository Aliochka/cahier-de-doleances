# Audit du corpus pour un RAG local

Mesuré le **16 octobre 2026**, sur `cahier_doleances_local`, PostgreSQL **17.11**, révision Alembic `remove_runtime_caches`. Audit du corpus présent localement ; aucune vérification de la production.

## Constats principaux

- **1 589 285 contributions**, **15 792 750 réponses**, dont **5 004 470 réponses ouvertes**. Les 10 788 280 autres lignes sont des réponses à choix, pas autant de documents rédigés par les citoyens.
- **167 886 éléments « Autre » non vides** apportent du texte libre supplémentaire dans les questions à choix.
- La réponse ouverte médiane mesure **102 caractères** ; le P99 atteint **1 523 caractères**. Seules **30 627 réponses ouvertes (0,61 %)** dépassent 2 000 caractères, mais le maximum est de **350 874 caractères**.
- Un index par réponse représenterait environ **5,17 millions d’unités textuelles** en incluant les « Autre ». Un index regroupé par contribution ouverte partirait de **549 920 parents avec réponses ouvertes**, avec des unités plus longues et multithématiques.
- Les titres sont une source distincte : **569 022 titres**, dont **19 102 sur des contributions sans réponse ouverte**.
- Les choix, les textes courts et les doublons rendent nécessaire une distinction entre recherche documentaire et calcul analytique. Ces mesures ne désignent pas une architecture unique.

## 1. Méthode, périmètre et coût

Les accès SQL ont été exécutés dans des transactions `REPEATABLE READ`, explicitement `READ ONLY`, puis terminés par `ROLLBACK`. Aucune table temporaire, migration, extension ou index créé ; aucune donnée modifiée. Aucun modèle téléchargé, aucune dépendance installée, aucun embedding calculé. Seuls des fichiers de travail et ce rapport ont été écrits sur le système de fichiers.

Le relevé principal a commencé à **16:41:46 +02:00**. Les mesures complémentaires ont utilisé des snapshots distincts rapprochés : cohérence interne par transaction, mais pas de garantie de snapshot unique pour tout le rapport si un import concurrent avait eu lieu. Les contrôles agrégés concordent.

Les longueurs exactes proviennent d’histogrammes SQL `GROUP BY form_id, type, char_length(text)`, puis de cumuls pondérés locaux. Cela évite de transférer les textes et de trier plusieurs millions de lignes pour chaque percentile. Les quantiles sont discrets : première longueur atteignant `ceil(p × N)`. Les longueurs ne sont pas nettoyées ; `char_length` compte les caractères PostgreSQL, pas les octets ni les tokens du futur modèle.

Requêtes bornées à 240 s, attente de verrou à 2 s, `work_mem` local de 64 Mo. Plusieurs parcours séquentiels ont été nécessaires ; les traitements ont regroupé les mesures compatibles. Les agrégations peuvent utiliser des fichiers temporaires internes PostgreSQL, sans modification des données applicatives. La comparaison des doublons est fondée sur MD5, sans export des textes : empreintes identiques, collision théorique non vérifiée par comparaison des corps.

| Mesure | Durée observée (s) |
| --- | --- |
| contributions | 1,53 |
| lengths | 1,63 |
| per_question | 4,66 |
| choice_extra | 27,10 |
| duplicates | 7,26 |
| dup_text_global | 5,25 |
| normalized_dup | 19,28 |
| parent_lengths | 1,65 |
| question_lengths | 1,42 |
| dup_question | 4,79 |
| other_lengths | 1,07 |

Les durées dépendent du cache et de cette machine ; ce ne sont pas des benchmarks. Un premier diagnostic lexical SQL a été annulé après environ 70 s pour éviter un traitement disproportionné. Il a été remplacé par un échantillon traité en Python avec les dépendances déjà présentes. Les compteurs `pg_stat_user_tables.n_live_tup` étaient des estimations et ne servent pas aux totaux du rapport.

## 2. Modèles et schéma réel

Chaîne documentaire : `forms → questions → answers`, avec `contributions → answers` et `authors → contributions`. Les choix sont normalisés dans `options` et `answer_options`.

| Objet | Observation réelle et conséquence |
| --- | --- |
| answers | IDs et clés de rattachement BIGINT ; text TEXT, value_json TEXT. Unicité (contribution_id, question_id, position). Toutes les positions observées valent 1. |
| questions | 120 questions ; types présents : text, single_choice, multi_choice. 72 ouvertes et 48 à choix. Conserver question_id, type, ordre et libellé dans la provenance. |
| contributions | Titre séparé, source et identifiant source, date, author_id et raw_json TEXT. Ne pas considérer raw_json comme un second document à indexer intégralement. |
| authors / users | Les auteurs importés sont distincts des comptes du site. Le code postal est une métadonnée déclarative, pas une résidence vérifiée ; aucun besoin de l’inclure dans les embeddings. |
| Écarts ORM | Aucune colonne ORM manquante, aucun écart de type ou de nullabilité observé sur les colonnes modélisées. Colonnes supplémentaires : questions.prompt_unaccent, prompt_tsv, tsv_prompt ; answers.text_tsv. |
| Infrastructure DB | Tables et contraintes gérées par les migrations, dont gdn_import_runs et contraintes d’unicité absentes de certaines déclarations ORM. Le modèle seul ne décrit pas toute la base. |
| Extensions | plpgsql, unaccent, pg_trgm. Aucune extension vectorielle installée au moment de l’audit ; aucune installation réalisée. |
| Index | Index B-tree sur clés de jointure et GIN de recherche textuelle ; plusieurs index partiels excluent les réponses de moins de 60 caractères. Aucun inventaire de ces index ne vaut validation de leur pertinence pour le futur RAG. |
| Intégrité | 0 réponse rattachée à un formulaire de contribution différent de celui de sa question ; 0 position différente de 1. Contraintes de clés étrangères et unicité présentes. |

Taille totale de la base : **15 281 772 211 octets** (~14,23 Gio), index et données brutes compris. Les seules réponses ouvertes représentent **981 506 298 caractères**, soit **1 011 151 655 octets UTF-8** (~0,94 Gio). La taille de la base entière ne permet donc pas d’estimer directement le volume à vectoriser.

## 3. Répartition exacte par questionnaire

| ID | Questionnaire | Contributions | Questions ouvertes / simples / multiples | Réponses ouvertes | Choix simples | Choix multiples | Total réponses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | Organisation de l'État & services publics (questions rapides) | 333 793 | 0 / 9 / 3 | 0 | 2 943 200 | 964 424 | 3 907 624 |
| 4 | Organisation de l'État & services publics | 111 953 | 25 / 8 / 0 | 852 920 | 565 836 | 0 | 1 418 756 |
| 5 | Démocratie & citoyenneté | 116 549 | 30 / 7 / 0 | 2 132 401 | 636 050 | 0 | 2 768 451 |
| 7 | Fiscalité & dépenses publiques | 186 711 | 7 / 0 / 1 | 945 925 | 0 | 155 657 | 1 101 582 |
| 10 | Transition écologique | 153 809 | 10 / 5 / 1 | 1 073 224 | 688 092 | 96 105 | 1 857 421 |
| 11 | Démocratie & citoyenneté (questions rapides) | 335 157 | 0 / 6 / 1 | 0 | 1 984 413 | 320 408 | 2 304 821 |
| 12 | Transition écologique (questions rapides) | 351 313 | 0 / 6 / 1 | 0 | 2 087 543 | 346 552 | 2 434 095 |

Les quatre questionnaires détaillés totalisent **569 022 contributions** ; les trois rapides, **1 020 263**. Les rapides ne contiennent **aucune question ouverte et aucun « Autre » non vide** dans cet import. Il n’existe pas de questionnaire rapide Fiscalité dans les sept sources présentes : ne pas traiter cette absence comme une non-participation à ce thème.

Tous les formulaires ont des contributions entre le 22 janvier et le 18 mars 2019, sans date ni auteur manquant dans `contributions`. Il s’agit des questionnaires numériques, pas d’une collection exhaustive des cahiers manuscrits, courriers et contributions hors plateforme.

| Questionnaire détaillé | Contributions | Auteurs distincts dans ce formulaire | Avec réponse ouverte | Sans réponse ouverte | Sans aucune réponse |
| --- | --- | --- | --- | --- | --- |
| 4 | 111 953 | 95 935 | 106 803 | 5 150 | 4 638 |
| 5 | 116 549 | 102 126 | 112 219 | 4 330 | 4 044 |
| 7 | 186 711 | 152 477 | 180 399 | 6 312 | 5 308 |
| 10 | 153 809 | 134 177 | 150 499 | 3 310 | 2 534 |

Un auteur peut contribuer plusieurs fois et à plusieurs questionnaires : les auteurs distincts par formulaire ne sont pas additionnables pour obtenir des personnes uniques. Les **16 524 contributions sans aucune réponse** ont néanmoins un titre et un enregistrement brut. Les **19 102 sans réponse ouverte** comprennent aussi **2 578 contributions avec choix seulement**. Un export fondé exclusivement sur les réponses ouvertes perdrait leurs titres.

## 4. Longueurs des réponses

| Ensemble | N | Min | Moyenne | Médiane | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| text | 5 004 470 | 1 | 196,13 | 102 | 404 | 621 | 1 523 | 350 874 |
| single_choice | 8 905 134 | 1 | 11,59 | 3 | 31 | 57 | 82 | 23 909 |
| multi_choice | 1 883 146 | 1 | 37,59 | 25 | 65 | 93 | 248 | 21 190 |
| Tous types | 15 792 750 | 1 | 73,17 | 13 | 177 | 302 | 819 | 350 874 |
| Autre non vide, extrait seul | 167 886 | 1 | 119,88 | 80 | 235 | 332 | 698 | 23 909 |

La médiane globale de 13 caractères est dominée par les choix. Elle est impropre au dimensionnement des passages rédigés. Les longueurs des choix incluent les libellés et, parfois, le texte « Autre ».

| Ensemble | N | Min | Moyenne | Médiane | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 — Organisation de l'État & services publics | 852 920 | 1 | 205,47 | 97 | 433 | 707 | 1 720 | 79 628 |
| 5 — Démocratie & citoyenneté | 2 132 401 | 1 | 164,50 | 96 | 339 | 491 | 1 081 | 350 874 |
| 7 — Fiscalité & dépenses publiques | 945 925 | 1 | 233,94 | 110 | 500 | 785 | 1 982 | 80 412 |
| 10 — Transition écologique | 1 073 224 | 1 | 218,20 | 114 | 447 | 689 | 1 731 | 308 280 |

| Ensemble | N | Min | Moyenne | Médiane | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 — single_choice | 2 943 200 | 3 | 7,89 | 11 | 14 | 14 | 14 | 14 |
| 2 — multi_choice | 964 424 | 9 | 28,70 | 24 | 55 | 69 | 69 | 78 |
| 4 — single_choice | 565 836 | 3 | 3,00 | 3 | 3 | 3 | 3 | 3 |
| 5 — single_choice | 636 050 | 3 | 5,27 | 3 | 15 | 15 | 18 | 18 |
| 7 — multi_choice | 155 657 | 1 | 141,91 | 99 | 261 | 351 | 665 | 21 190 |
| 10 — single_choice | 688 092 | 1 | 17,46 | 3 | 54 | 60 | 147 | 23 909 |
| 10 — multi_choice | 96 105 | 1 | 52,69 | 34 | 98 | 144 | 278 | 15 766 |
| 11 — single_choice | 1 984 413 | 3 | 5,05 | 3 | 13 | 14 | 23 | 23 |
| 11 — multi_choice | 320 408 | 10 | 30,04 | 39 | 44 | 44 | 44 | 84 |
| 12 — single_choice | 2 087 543 | 3 | 25,33 | 3 | 72 | 82 | 82 | 82 |
| 12 — multi_choice | 346 552 | 13 | 18,26 | 13 | 35 | 35 | 66 | 66 |

### Réponses ouvertes courtes et longues

| Caractères | Réponses | Part des réponses ouvertes |
| --- | --- | --- |
| 1–5 | 158 480 | 3,17 % |
| 6–10 | 127 341 | 2,54 % |
| 11–20 | 289 943 | 5,79 % |
| 21–59 | 1 049 250 | 20,97 % |
| 60–100 | 848 493 | 16,95 % |
| 101–500 | 2 174 544 | 43,45 % |
| 501–1 000 | 244 427 | 4,88 % |
| 1 001–2 000 | 81 365 | 1,63 % |
| 2 001–4 000 | 22 179 | 0,44 % |
| 4 001–8 000 | 6 271 | 0,13 % |
| 8 001–20 000 | 1 877 | 0,04 % |
| Plus de 20 000 | 300 | 0,01 % |

**575 764 réponses (11,50 %) ont au plus 20 caractères** ; **1 625 014 (32,47 %) ont moins de 60 caractères**. Un seuil automatique à 60 supprimerait donc presque un tiers des réponses ouvertes selon la longueur brute ; le filtre applicatif porte sur `btrim`, ce qui peut en exclure davantage. Court ne signifie pas sans intérêt : une réponse peut nommer une institution ou exprimer une position seulement compréhensible avec sa question. Aucun filtre sémantique de qualité n’a été appliqué.

Il reste **8 448 réponses au-delà de 4 000 caractères**, **2 177 au-delà de 8 000**, **300 au-delà de 20 000**, **113 au-delà de 32 000**. Ce sont les premières candidates à une segmentation conditionnelle. Leur longueur ne prouve pas qu’elles sont du bruit.

## 5. Choix et textes « Autre »

| Formulaire | Type | Réponses à choix | Avec tableau other_text non vide | Éléments Autre non blancs |
| --- | --- | --- | --- | --- |
| 2 | multi_choice | 964 424 | 0 | 0 |
| 2 | single_choice | 2 943 200 | 0 | 0 |
| 4 | single_choice | 565 836 | 0 | 0 |
| 5 | single_choice | 636 050 | 0 | 0 |
| 7 | multi_choice | 155 657 | 91 717 | 91 686 |
| 10 | multi_choice | 96 105 | 26 181 | 26 181 |
| 10 | single_choice | 688 092 | 50 019 | 50 019 |
| 11 | multi_choice | 320 408 | 0 | 0 |
| 11 | single_choice | 1 984 413 | 0 | 0 |
| 12 | multi_choice | 346 552 | 0 | 0 |
| 12 | single_choice | 2 087 543 | 0 | 0 |

L’import écrit dans `answers.text` les libellés sélectionnés, suivis du texte « Autre ». `value_json` conserve `source_value`, `labels`, `selected_codes` et `other_text`. Les liens `answer_options` restent la référence structurée des sélections.

Au total, **167 917 réponses** ont un tableau `other_text` non vide, mais seulement **167 886 éléments non blancs** après `btrim` : 31 éléments ne doivent pas être comptés comme documents utiles. Leur longueur totale est de **20 126 163 caractères** ; **216 dépassent 2 000 caractères**, **85 dépassent 4 000**, **27 dépassent 8 000**.

Deux options à tester : indexer uniquement les `other_text` avec question et choix en contexte ; ou indexer le texte composé complet en identifiant explicitement sa nature. Indexer simultanément le texte composé et les éléments « Autre » comme documents indépendants doublerait leur contenu. Les libellés répétés des choix peuvent rester des métadonnées et des faits SQL plutôt que des millions de vecteurs.

## 6. Identité et répétition des textes

| Périmètre de déduplication | Occurrences | Empreintes distinctes | Occurrences excédentaires |
| --- | --- | --- | --- |
| Réponses ouvertes, global | 5 004 470 | 4 308 111 | 696 359 |
| Réponses ouvertes, question_id + empreinte | 5 004 470 | 4 416 851 | 587 619 |
| Réponses ouvertes, global après normalisation légère | 5 004 470 | 4 255 379 | 749 091 |

Normalisation légère : `lower(regexp_replace(btrim(text), '[[:space:]]+', ' ', 'g'))`. Ni accents ni ponctuation retirés. Les 696 359 occurrences excédentaires représentent **13,91 %** des réponses ouvertes ; **809 975 réponses (16,19 %)** appartiennent à un groupe répété au moins deux fois. **523 324** appartiennent à des groupes d’au moins dix occurrences. La fréquence maximale est **13 609** pour une empreinte brute et **26 786** après normalisation. Aucun contenu de ces groupes n’est exposé ici.

| Formulaire | Réponses ouvertes | Distinctes dans le formulaire | Excédent | Fréquence maximale |
| --- | --- | --- | --- | --- |
| 4 | 852 920 | 703 720 | 149 200 | 5 756 |
| 5 | 2 132 401 | 1 852 903 | 279 498 | 9 813 |
| 7 | 945 925 | 800 232 | 145 693 | 4 654 |
| 10 | 1 073 224 | 967 338 | 105 886 | 1 281 |

Les répétitions ne sont pas limitées aux réponses très courtes : au sein d’une même question, **36 571 occurrences de textes d’au moins 200 caractères** appartiennent à des groupes répétés ; elles représentent **24 393 occurrences excédentaires**. Cela repère des textes recopiés ou des formulations identiques, sans établir de coordination, d’automatisation ou d’intention. Les quasi-doublons paraphrasés ne sont pas mesurés.

Les trois questionnaires rapides ne produisent respectivement que **103**, **59** et **76** empreintes distinctes de `answers.text` en additionnant les ensembles de choix simples et multiples de chaque questionnaire. Cette forte répétition est attendue pour un catalogue de choix ; elle n’est pas du spam. Une empreinte partagée entre questions n’implique pas une signification identique.

Dédupliquer les corps peut réduire le travail documentaire, mais il faut conserver **toutes les occurrences, les question_id, les contributions et les auteurs associés** dans une table de provenance future ou une représentation équivalente. Un seul texte « canonique » sans ces liens fausserait les fréquences et pourrait mélanger des réponses identiques à des questions différentes. Aucun effacement recommandé à ce stade.

### Diagnostic exploratoire des répétitions internes

Échantillon physique `TABLESAMPLE SYSTEM (1) REPEATABLE (5090)` : **50 118 réponses ouvertes**, soit **1,00 %** du corpus ouvert. Les textes ont été traités en mémoire, sans les enregistrer dans le rapport.

| Formulaire | Échantillon | Médiane mots | P90 mots | P99 mots | ≥ 50 mots | Diversité ≤ 20 % parmi ≥ 50 mots | Suite ≥ 10 caractères identiques non blancs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 8 685 | 16 | 71 | 279 | 1 419 | 0 | 23 |
| 5 | 21 292 | 15 | 54 | 174 | 2 522 | 0 | 27 |
| 7 | 9 339 | 18 | 81 | 352 | 1 797 | 0 | 23 |
| 10 | 10 802 | 18 | 71 | 257 | 1 804 | 0 | 8 |

Les « mots » sont les éléments séparés par des espaces Unicode (`str.split`), sans analyse linguistique ; la diversité est le nombre de formes minuscules distinctes divisé par le nombre de mots. **81 textes** contiennent une suite d’au moins dix caractères identiques non blancs ; cela peut être de la ponctuation expressive. **0** franchit le seuil arbitraire de faible diversité. Un texte contient une séquence ressemblant à une balise HTML ; aucun saut de ligne LF n’a été trouvé dans cet échantillon. Ces diagnostics n’excluent ni répétition de phrases, ni HTML ou paragraphes ailleurs. L’échantillonnage par pages présente un biais de regroupement physique et ne constitue pas un sondage aléatoire indépendant par réponse ; aucune extrapolation chiffrée au corpus entier.

## 7. Titres et intérêt documentaire

| Ensemble | N | Min | Moyenne | Médiane | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 — titres | 111 953 | 1 | 42,95 | 32 | 85 | 111 | 205 | 255 |
| 5 — titres | 116 549 | 1 | 40,35 | 30 | 81 | 108 | 203 | 255 |
| 7 — titres | 186 711 | 2 | 40,18 | 30 | 82 | 107 | 185 | 255 |
| 10 — titres | 153 809 | 1 | 41,52 | 32 | 83 | 107 | 176 | 255 |
| Tous titres présents | 569 022 | 1 | 41,12 | 31 | 82 | 108 | 189 | 255 |

Les questionnaires détaillés ont tous un titre renseigné ; les rapides n’en ont aucun. Les titres sont très courts (médiane 31 caractères, maximum 255), soit **23 398 576 caractères** au total. La borne observée à 255 ne permet pas de conclure à une troncature à l’import : `contributions.title` est un VARCHAR sans limite déclarée dans le modèle.

| Formulaire | Titres | Distincts dans le formulaire | Excédent | Fréquence maximale |
| --- | --- | --- | --- | --- |
| 4 | 111 953 | 85 173 | 26 780 | 3 777 |
| 5 | 116 549 | 87 256 | 29 293 | 1 244 |
| 7 | 186 711 | 132 875 | 53 836 | 2 079 |
| 10 | 153 809 | 120 895 | 32 914 | 1 257 |

La somme des titres distincts **par formulaire** est de **426 199** (pas une mesure globale de titres uniques). Un petit lexique prédéfini de titres génériques repère **1 411 titres** ; **330** sont composés uniquement de chiffres, ponctuation et espaces selon la regex SQL. Les catégories peuvent se recouper. Ce contrôle limité ne mesure pas tous les titres vagues.

Intérêt à évaluer : fournir le titre au reranker ou à l’affichage ; l’utiliser comme champ lexical ; l’ajouter au contexte d’un parent ; ou construire une entrée distincte pour les **19 102 contributions sans réponse ouverte**. Répéter le titre dans chacun des millions de petits passages peut dominer leur représentation ou favoriser les titres génériques : comparer avec et sans titre. La valeur sémantique supplémentaire ne peut être déduite des seules longueurs ; elle demande une évaluation de recherche.

## 8. Contributions regroupées et besoin de segmentation

Mesure « parent » : somme des longueurs des seules réponses ouvertes d’une contribution. Elle exclut titre, questions, séparateurs, choix et « Autre » ; elle ne correspond pas à un document final déjà assemblé.

| Ensemble | N | Min | Moyenne | Médiane | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 — parent ouvert | 106 803 | 1 | 1 640,83 | 1 043 | 3 482 | 4 801 | 9 294 | 169 875 |
| 5 — parent ouvert | 112 219 | 1 | 3 125,95 | 2 330 | 6 392 | 8 413 | 14 696 | 742 314 |
| 7 — parent ouvert | 180 399 | 1 | 1 226,68 | 810 | 2 524 | 3 530 | 7 014 | 213 601 |
| 10 — parent ouvert | 150 499 | 1 | 1 556,01 | 1 102 | 3 130 | 4 227 | 7 854 | 308 599 |
| Tous parents ouverts | 549 920 | 1 | 1 784,82 | 1 122 | 3 874 | 5 418 | 10 245 | 742 314 |

Sur **549 920** parents ouverts, **152 911 (27,81 %)** dépassent 2 000 caractères, **51 708 (9,40 %)** dépassent 4 000, **10 715 (1,95 %)** dépassent 8 000 et **821** dépassent 20 000. Les parents Démocratie sont particulièrement longs parce qu’ils regroupent beaucoup de questions, même si leurs réponses individuelles sont plus courtes.

Les questions finales « autres points » concentrent à elles seules **19,11 %** des caractères ouverts et **44,65 %** des réponses ouvertes dépassant 2 000 caractères (questions 47, 84, 163, 293). Elles appellent souvent une segmentation thématique ; à l’inverse, certaines réponses brèves ou conditionnelles réclament le libellé de la question précédente.

Candidats à examiner : réponses au-delà du budget du futur encodeur ; réponses finales très longues et multithématiques ; parents regroupant plusieurs questions ; textes « Autre » exceptionnellement longs. Découper prioritairement sur des frontières de phrase ou de section si elles existent, puis utiliser une limite ferme pour les cas sans ponctuation. L’échantillon sans LF invite à ne pas dépendre exclusivement des paragraphes.

## 9. Estimations de documents et de segments

Pour rendre les scénarios comparables, les simulations utilisent une fenêtre **en caractères** L et un chevauchement O. Pour un corps de longueur n : `1` segment si `n ≤ L`, sinon `1 + ceil((n − L)/(L − O))`. Les calculs sont exacts pour cette règle sur les longueurs mesurées ; ils restent des **projections**, pas le résultat d’un découpage linguistique ou d’une tokenisation.

| Unité documentaire, sans segmentation | Nombre | Précision |
| --- | --- | --- |
| Toutes les lignes answers | 15 792 750 | Inclut 10,79 M de choix ; scénario naïf de comparaison |
| Réponses ouvertes seulement | 5 004 470 | Une provenance par réponse |
| Réponses ouvertes + éléments Autre non vides | 5 172 356 | Deux catégories identifiées ; ne pas reprendre en plus leur texte composé |
| Corps ouverts dédupliqués globalement | 4 308 111 | Empreintes ; provenance multiple indispensable |
| Réponses ouvertes dédupliquées par question | 4 416 851 | Préserve le contexte question ; avant segmentation |
| Réponses ouvertes après exclusion ≤ 20 caractères | 4 428 706 | Illustration du coût d’un seuil, pas une recommandation de suppression |
| Parents contenant au moins une réponse ouverte | 549 920 | Une contribution peut couvrir plusieurs sujets |
| Parents des quatre questionnaires détaillés, titre inclus | 569 022 | Inclut 19 102 contributions sans réponse ouverte |
| Titres en entrées séparées | 569 022 | À ajouter uniquement si stratégie distincte, risque de doublons de récupération |

| Fenêtre / chevauchement (car.) | Segments réponses ouvertes | Segments Autre | Total ouvert + Autre | Parents : corps ouverts seuls |
| --- | --- | --- | --- | --- |
| 1 000 / 0 | 5 198 285 | 169 320 | 5 367 605 | 1 269 766 |
| 2 000 / 0 | 5 056 087 | 168 303 | 5 224 390 | 807 181 |
| 4 000 / 0 | 5 017 860 | 168 010 | 5 185 870 | 620 563 |
| 8 000 / 0 | 5 007 719 | 167 916 | 5 175 635 | 563 529 |
| 2 000 / 200 | 5 059 313 | 168 335 | 5 227 648 | 824 272 |
| 4 000 / 400 | 5 018 705 | 168 022 | 5 186 727 | 624 050 |
| 8 000 / 800 | 5 007 899 | 167 919 | 5 175 818 | 564 053 |

Les titres peuvent ajouter jusqu’à **569 022 vecteurs** s’ils sont tous indexés séparément, ou **19 102** si seules les contributions sans réponse ouverte reçoivent une entrée titre. Les « Autre » doivent aussi être rattachés aux parents si cette stratégie est testée : les chiffres de la dernière colonne ne les intègrent pas. Leurs segments ne sont pas directement additionnables aux segments de parents fusionnés.

L’ajout de questions, titres et séparateurs augmente les longueurs et parfois le nombre de segments. Aucun coefficient caractères/tokens universel n’est utilisé : une estimation en tokens exige le tokenizer exact du modèle choisi, non téléchargé ici. Les variantes de découpage par phrases, regroupement de petites réponses et déduplication après découpage ne sont donc pas quantifiées comme des mesures exactes.

### Plusieurs stratégies à comparer

| Stratégie | Avantages | Inconvénients / hypothèses à tester |
| --- | --- | --- |
| A. Une réponse ouverte ou un Autre par document ; découpage seulement des longues | Source précise ; peu de découpage supplémentaire ; contexte question facilement attaché | ~5,17 M d’unités majoritairement très courtes ; vocabulaire isolé et réponses conditionnelles ; contexte indispensable |
| B. Parent contribution + enfants par question / segment | Retrouver un passage puis restituer le contexte ; garde la voix et la source du contributeur | Stockage et déduplication des liens plus complexes ; ne pas compter chaque enfant comme une personne ou un avis indépendant |
| C. Concaténation par contribution puis fenêtres de 2 000 à 8 000 caractères | Beaucoup moins de vecteurs ; plus de contexte par unité | Risque de mêler des sujets et des questions ; coût d’en-têtes non simulé ; effet de longueur plus marqué pour Démocratie |
| D. Regroupement de réponses courtes voisines d’une même contribution | Réduit les micro-documents et garde un contexte local | Règle de voisinage et budget à définir ; ne pas fusionner les textes de citoyens différents ; volumes non mesurés pour cette règle |
| E. Corps dédupliqué avec provenance multivaluée | Évite certains calculs et résultats identiques ; ~4,31 M de corps ouverts globaux avant découpage | Question, fréquence et toutes les occurrences doivent rester accessibles ; MD5 à confirmer pour une déduplication définitive |
| F. Index documentaire pour les textes + interrogation SQL pour les choix | Évite de vectoriser massivement des libellés ; statistiques exactes et explicables | Orchestration documentaire/analytique et choix des dénominateurs à évaluer ; les Autre doivent rester dans le volet textuel |

### Ordres de grandeur du stockage vectoriel

Calcul arithmétique, sans choix de modèle : `nombre_de_vecteurs × dimension × octets_par_composante`. Les valeurs suivantes **excluent** index de voisinage, IDs, corps, provenance et métadonnées ; elles ne décrivent pas la mémoire GPU requise par l’encodeur.

| Scénario | Vecteurs | 768 dimensions float32 (Gio) | 1 024 dimensions float32 (Gio) |
| --- | --- | --- | --- |
| Réponses ouvertes + Autre sans découpage | 5 172 356 | 14,80 | 19,73 |
| Ouvert + Autre, fenêtre 2 000 / 200 | 5 227 648 | 14,96 | 19,94 |
| Parents ouverts, fenêtre 4 000 / 400, sans contexte | 624 050 | 1,79 | 2,38 |
| Toutes réponses, scénario naïf | 15 792 750 | 45,18 | 60,24 |

En float16, le seul payload numérique serait divisé par deux, si le stockage retenu le permet. Une RTX 5090 annoncée à 32 Go de VRAM est une contrainte de traitement local, pas une garantie que corpus, modèle et index y tiennent ensemble. Aucun débit, durée d’embedding ou budget de batch n’a été benchmarké ; la RAM et le disque de l’index se dimensionnent séparément.

## 10. Particularités qui influencent le RAG

| Questionnaire | Particularité | Conséquence à évaluer |
| --- | --- | --- |
| Organisation détaillé (4) | 25 questions ouvertes, plusieurs formulations conditionnelles ; 852 920 réponses ouvertes | Préserver l’ordre des questions et les dépendances ; ne pas filtrer seulement par longueur |
| Démocratie détaillé (5) | 30 ouvertes ; 2 132 401 réponses, soit 42,61 % des réponses ouvertes ; parents les plus longs | Évaluation stratifiée et contrôle de domination du thème ; segmentation par question ou parent à comparer |
| Fiscalité détaillé (7) | 7 ouvertes, 1 choix multiple ; 91 686 Autre non blancs ; moyenne ouverte la plus longue | Ne pas perdre les Autre ; longues réponses de propositions et question finale à couvrir |
| Écologie détaillé (10) | 10 ouvertes, 6 questions à choix ; 76 200 Autre non blancs | Coexistence faits structurés / arguments libres ; éviter de doubler les Autre et leur texte composé |
| Organisation rapide (2) | 12 questions exclusivement à choix, aucun titre ni Autre | Pertinent pour statistiques et filtres ; peu de bénéfice attendu à un vecteur par ligne de choix |
| Démocratie rapide (11) | 7 questions exclusivement à choix ; ~335 000 contributions | Ne pas assimiler volume de participation aux textes disponibles ni fusionner avec le questionnaire détaillé |
| Écologie rapide (12) | 7 questions exclusivement à choix ; ~351 000 contributions | Même thème ≠ mêmes questions ni mêmes dénominateurs ; conserver form_id et question_id |

Le nombre de réponses dépend aussi du nombre de questions et de leur caractère optionnel. Une analyse de fréquence peut porter sur les occurrences de réponses, les contributions distinctes ou les auteurs distincts : le dénominateur doit être explicite et les trois mesures ne sont pas interchangeables. Les pourcentages de choix multiples peuvent dépasser 100 %. Une synthèse à partir des seuls passages top-k ne mesure pas la prévalence d’une opinion.

## 11. Extraction, provenance et confidentialité

Pour un futur export exhaustif, lire la base avec pagination par identifiant ou curseur et garder `answer_id`, `contribution_id`, `form_id`, `question_id`, type, ordre et offsets des segments. Ces opérations ne sont pas implémentées par cet audit. Les listes publiques actuelles ne sont pas un export RAG : filtre de longueur autour de 60 caractères, troncature de liste à 20 000 ; recherche avec aperçu de 1 000 caractères et plafond historique de 1 789 candidats. L’API de contribution expose les textes complets, mais sa boucle HTTP n’est pas évaluée comme voie d’ingestion massive.

`raw_json` conserve les données sources et les variantes de présentation ; l’import privilégie `formattedValue` non vide, sinon `value`, et remplace U+0000 dans le texte destiné à PostgreSQL. Ne pas indexer simultanément le JSON complet et les réponses normalisées. L’audit ne fait pas une comparaison exhaustive de toutes les valeurs brutes avec leur projection : l’absence de texte utile uniquement dans le brut n’est pas certifiée. Les contributions sans réponses et leurs titres méritent un contrôle ciblé lors de l’export.

Les auteurs ont **496 390 codes postaux renseignés sur 496 395**, mais aucun nom, âge ou genre renseigné dans les champs correspondants. Le drapeau d’anonymat à l’affichage ne certifie pas l’absence de renseignements personnels dans les textes ou titres. Ne pas inclure par défaut identifiants source, email, profils ou code postal dans le texte encodé. Les statistiques géographiques éventuelles doivent rester explicitement déclaratives et agrégées. Aucun texte citoyen complet ni exemple de code postal individuel n’est reproduit.

## 12. Limites et suite proposée

- Les volumes et histogrammes concernent la base locale observée, pas la production ni tous les matériaux du Grand Débat.
- Les décomptes sont exacts, sauf les indicateurs explicitement échantillonnés et les groupes d’identité basés sur empreinte. Les doublons proches et la qualité argumentative restent non mesurés.
- Aucun audit de langue, de données personnelles dans les textes, de vérité factuelle ou de représentativité des participants n’a été réalisé.
- Les titres et réponses courts ne sont pas classés automatiquement comme utiles ou inutiles ; les critères heuristiques ne sont pas des décisions de suppression.
- Les segments simulés sont en caractères et sans contexte ajouté. Ni limite de tokens, ni vitesse de traitement sur GPU, ni qualité de retrieval ne sont établies.
- Les compteurs d’usage n’ont pas été pris pour des statistiques exactes du corpus ; aucune réorganisation ou maintenance de la base n’a été exécutée.

Étape possible, après décision distincte : constituer un petit jeu d’évaluation stratifié par questionnaire, question, longueur, duplication et présence d’Autre ; comparer les stratégies A/B/C et les variantes de contexte avec et sans titre. Mesurer qualité des citations, couverture des réponses courtes, diversité des sources et séparation des questions conditionnelles. Pour le volet analytique, tester des questions à dénominateur connu contre des agrégats SQL, sans déduire des fréquences du classement documentaire. Le choix d’un encodeur, du tokenizer, du stockage vectoriel et du découpage définitif reste ouvert.

## Annexe A — Mesures par question ouverte

Les libellés des questions sont ceux du questionnaire public, pas des réponses de citoyens. Les percentiles ci-dessous sont calculés sur toutes les réponses de chaque question. Les 48 questions à choix sont détaillées dans l’annexe B.

| Form. | Question | Libellé public | N | Min | Moy. | Méd. | P90 | P95 | P99 | Max | ≤ 20 | > 2 000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 15 | Que pensez-vous de l'organisation de l'Etat et des administrations en France ? De quelle manière cette organisation devrait-elle évoluer ? | 84 454 | 1 | 375,79 | 173 | 814 | 1 266 | 3 271 | 75 947 | 3 145 | 1 997 |
| 4 | 17 | Si oui, lesquelles ? | 39 870 | 1 | 170,87 | 99 | 359 | 524 | 1 173 | 11 070 | 2 986 | 127 |
| 4 | 19 | Si non, quels types de services publics vous manquent dans votre territoire et qu'il est nécessaire de renforcer ? | 34 982 | 1 | 178,40 | 102 | 385 | 571 | 1 216 | 11 357 | 3 854 | 124 |
| 4 | 20 | Quels nouveaux services ou quelles démarches souhaitez-vous voir développées sur Internet en priorité ? | 46 910 | 1 | 142,55 | 92 | 308 | 431 | 840 | 15 961 | 6 965 | 51 |
| 4 | 23 | Quelles améliorations préconiseriez-vous ? | 30 862 | 1 | 149,03 | 94 | 312 | 441 | 900 | 9 077 | 2 366 | 51 |
| 4 | 24 | Quand vous pensez à l'évolution des services publics au cours des dernières années, quels sont ceux qui ont évolué de manière positive ? | 61 485 | 1 | 86,70 | 44 | 203 | 297 | 617 | 21 687 | 18 166 | 32 |
| 4 | 25 | Quels sont les services publics qui doivent le plus évoluer selon vous ? | 62 100 | 1 | 149,65 | 55 | 338 | 546 | 1 407 | 23 376 | 14 384 | 321 |
| 4 | 28 | Si oui, à quelle occasion en avez-vous fait usage ? | 8 838 | 1 | 104,43 | 54 | 242 | 357 | 679 | 6 795 | 2 059 | 4 |
| 4 | 29 | Pouvez-vous identifier des règles que l'administration vous a déjà demandé d'appliquer et que vous avez jugées inutiles ou trop complexes ? | 40 484 | 1 | 161,91 | 98 | 362 | 517 | 1 034 | 11 929 | 6 236 | 72 |
| 4 | 31 | Si oui, comment ? | 40 005 | 1 | 122,51 | 85 | 247 | 343 | 654 | 7 689 | 2 750 | 24 |
| 4 | 33 | Si oui, comment ? | 58 956 | 1 | 185,69 | 114 | 387 | 560 | 1 180 | 11 455 | 3 462 | 172 |
| 4 | 34 | Comment l'Etat et les collectivités territoriales peuvent-ils s'améliorer pour mieux répondre aux défis de nos territoires les plus en difficulté ? | 58 593 | 1 | 186,04 | 114 | 381 | 558 | 1 180 | 14 696 | 3 037 | 191 |
| 4 | 35 | Si vous avez été amené à chercher une formation, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 21 601 | 1 | 149,20 | 81 | 347 | 502 | 1 044 | 11 766 | 6 503 | 46 |
| 4 | 36 | Si vous avez été amené à scolariser votre enfant, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 27 723 | 1 | 214,40 | 119 | 477 | 700 | 1 562 | 33 166 | 5 618 | 162 |
| 4 | 37 | Si vous avez été amené à chercher un emploi, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 24 953 | 1 | 169,35 | 100 | 390 | 557 | 1 099 | 14 732 | 5 855 | 56 |
| 4 | 38 | Si vous avez été amené à préparer votre retraite, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 32 142 | 1 | 150,68 | 98 | 331 | 459 | 867 | 6 795 | 4 980 | 34 |
| 4 | 39 | Si vous avez été amené à demander un remboursement de soins de santé, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 35 626 | 1 | 144,67 | 90 | 322 | 454 | 854 | 11 919 | 5 997 | 35 |
| 4 | 40 | Si vous avez été amené à faire une demande d'aide pour une situation de handicap, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 17 305 | 1 | 147,44 | 47 | 369 | 557 | 1 252 | 17 451 | 7 412 | 60 |
| 4 | 41 | Si vous avez été amené à créer une entreprise, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 17 551 | 1 | 147,12 | 75 | 348 | 500 | 1 061 | 53 366 | 5 380 | 32 |
| 4 | 42 | Si vous avez été amené à recruter du personnel, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 14 406 | 1 | 112,81 | 54 | 286 | 402 | 793 | 6 795 | 5 428 | 17 |
| 4 | 43 | Si vous avez été amené à former du personnel, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 10 856 | 1 | 88,39 | 16 | 244 | 362 | 704 | 6 795 | 5 612 | 10 |
| 4 | 44 | Si vous avez été amené à rémunérer du personnel, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 13 261 | 1 | 98,40 | 38 | 248 | 358 | 760 | 6 795 | 5 566 | 12 |
| 4 | 45 | Si vous avez été amené à mettre fin à votre activité, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 10 682 | 1 | 86,52 | 15 | 231 | 353 | 746 | 6 795 | 5 676 | 10 |
| 4 | 46 | Si vous avez été amené à recruter une personne portant un handicap, pouvez-vous indiquer les éléments de satisfaction et/ou les difficultés rencontrés en précisant, pour chaque point, l'administration concernée : | 7 941 | 1 | 42,72 | 12 | 114 | 210 | 541 | 6 795 | 6 174 | 2 |
| 4 | 47 | Y a-t-il d'autres points sur l'organisation de l'Etat et des services publics sur lesquels vous souhaiteriez vous exprimer ? | 51 334 | 1 | 713,79 | 356 | 1 327 | 2 197 | 5 923 | 79 628 | 2 213 | 2 931 |
| 5 | 48 | En qui faites-vous le plus confiance pour vous faire représenter dans la société et pourquoi ? | 89 266 | 1 | 147,71 | 68 | 281 | 440 | 1 262 | 56 909 | 18 243 | 494 |
| 5 | 50 | Si oui, à quel type d'associations ou d'organisations ? Et avec quel rôle ? | 59 074 | 1 | 175,54 | 118 | 362 | 507 | 967 | 11 500 | 3 436 | 103 |
| 5 | 51 | Que faudrait-il faire pour renouer le lien entre les citoyens et les élus qui les représentent ? | 89 911 | 1 | 249,35 | 141 | 517 | 777 | 1 779 | 43 265 | 3 095 | 700 |
| 5 | 53 | Pourquoi ? | 84 109 | 1 | 148,21 | 108 | 293 | 390 | 687 | 10 113 | 1 527 | 40 |
| 5 | 54 | Que faudrait-il faire pour mieux représenter les différentes sensibilités politiques ? | 79 794 | 1 | 131,24 | 70 | 285 | 418 | 923 | 14 277 | 7 783 | 149 |
| 5 | 56 | Si oui, lesquels ? | 67 417 | 1 | 134,60 | 81 | 291 | 414 | 838 | 37 103 | 8 405 | 75 |
| 5 | 57 | Que pensez-vous de la participation des citoyens aux élections et comment les inciter à y participer davantage ? | 88 078 | 1 | 174,51 | 111 | 374 | 530 | 1 021 | 14 400 | 5 833 | 138 |
| 5 | 59 | Si oui, de quelle manière ? | 71 885 | 1 | 134,91 | 95 | 273 | 373 | 679 | 11 624 | 4 487 | 47 |
| 5 | 60 | Que faudrait-il faire aujourd'hui pour mieux associer les citoyens aux grandes orientations et à la décision publique ? Comment mettre en place une démocratie plus participative ? | 86 157 | 1 | 199,44 | 123 | 414 | 595 | 1 235 | 55 224 | 6 486 | 332 |
| 5 | 62 | Si oui, comment ? | 48 132 | 1 | 146,26 | 92 | 299 | 422 | 847 | 37 116 | 3 478 | 78 |
| 5 | 63 | Que faudrait-il faire pour consulter plus directement les citoyens sur l'utilisation de l'argent public, par l'Etat et les collectivités ? | 78 567 | 1 | 150,43 | 99 | 321 | 443 | 827 | 26 260 | 8 200 | 78 |
| 5 | 64 | Quel rôle nos assemblées, dont le Sénat et le Conseil économique, social et environnemental, doivent-elles jouer pour représenter nos territoires et la société civile ? | 65 181 | 1 | 150,48 | 99 | 320 | 441 | 836 | 10 675 | 6 991 | 88 |
| 5 | 66 | Si oui, comment ? | 58 927 | 1 | 141,62 | 82 | 299 | 431 | 949 | 37 103 | 9 046 | 139 |
| 5 | 67 | Que proposez-vous pour renforcer les principes de la laïcité dans le rapport entre l'Etat et les religions de notre pays ? | 77 019 | 1 | 197,96 | 122 | 418 | 605 | 1 240 | 37 103 | 4 172 | 246 |
| 5 | 68 | Comment garantir le respect par tous de la compréhension réciproque et des valeurs intangibles de la République ? | 75 146 | 1 | 157,92 | 95 | 334 | 477 | 985 | 37 103 | 6 760 | 149 |
| 5 | 69 | Que faudrait-il faire aujourd'hui pour renforcer l'engagement citoyen dans la société ? | 72 844 | 1 | 150,43 | 94 | 309 | 436 | 872 | 43 211 | 6 111 | 138 |
| 5 | 70 | Quels sont les comportements civiques qu'il faut promouvoir dans notre vie quotidienne ou collective ? | 73 381 | 1 | 113,18 | 69 | 241 | 342 | 670 | 37 103 | 8 168 | 57 |
| 5 | 71 | Que faudrait-il faire pour favoriser le développement de ces comportements civiques et par quels engagements concrets chacun peut-il y participer ? | 63 400 | 1 | 150,31 | 98 | 313 | 435 | 836 | 37 103 | 6 150 | 71 |
| 5 | 72 | Que faudrait-il faire pour valoriser l'engagement citoyen dans les parcours de vie, dans les relations avec l'administration et les pouvoirs publics ? | 51 290 | 1 | 129,34 | 86 | 274 | 379 | 715 | 37 103 | 7 473 | 39 |
| 5 | 73 | Quelles sont les incivilités les plus pénibles dans la vie quotidienne et que faudrait-il faire pour lutter contre ces incivilités ? | 75 408 | 1 | 169,25 | 114 | 348 | 482 | 921 | 37 103 | 4 025 | 95 |
| 5 | 74 | Que peuvent et doivent faire les pouvoirs publics pour répondre aux incivilités ? | 74 531 | 1 | 120,20 | 73 | 258 | 366 | 734 | 37 103 | 10 144 | 63 |
| 5 | 75 | Quel pourrait être le rôle de chacun pour faire reculer les incivilités dans la société ? | 60 582 | 1 | 95,09 | 62 | 204 | 278 | 517 | 37 103 | 9 605 | 18 |
| 5 | 76 | Quelles sont les discriminations les plus répandues dont vous êtes témoin ou victime ? | 61 090 | 1 | 96,91 | 51 | 217 | 319 | 677 | 11 653 | 12 645 | 56 |
| 5 | 77 | Que faudrait-il faire pour lutter contre ces discriminations et construire une société plus solidaire et plus tolérante ? | 60 825 | 1 | 140,02 | 85 | 297 | 427 | 861 | 37 103 | 6 872 | 96 |
| 5 | 79 | Si oui, lesquelles ? | 61 268 | 1 | 143,32 | 91 | 302 | 420 | 817 | 37 103 | 3 651 | 70 |
| 5 | 80 | Que pensez-vous de la situation de l'immigration en France aujourd'hui et de la politique migratoire ? Quelles sont, selon vous, les critères à mettre en place pour définir la politique migratoire ? | 79 772 | 1 | 245,21 | 162 | 515 | 719 | 1 404 | 37 103 | 3 736 | 318 |
| 5 | 81 | En matière d'immigration, une fois nos obligations d'asile remplies, souhaitez-vous que nous puissions nous fixer des objectifs annuels définis par le Parlement ? | 75 325 | 1 | 80,34 | 33 | 208 | 298 | 590 | 37 103 | 33 905 | 26 |
| 5 | 82 | Que proposez-vous afin de répondre à ce défi qui va durer ? | 72 445 | 1 | 180,62 | 121 | 374 | 516 | 988 | 37 103 | 4 629 | 139 |
| 5 | 83 | Quelles sont, selon vous, les modalités d'intégration les plus efficaces et les plus justes à mettre en place aujourd'hui dans la société ? | 73 332 | 1 | 156,70 | 106 | 325 | 449 | 856 | 37 103 | 6 051 | 84 |
| 5 | 84 | Y a-t-il d'autres points sur la démocratie et la citoyenneté sur lesquels vous souhaiteriez vous exprimer ? | 58 245 | 1 | 516,94 | 212 | 1 011 | 1 718 | 5 420 | 350 874 | 6 212 | 2 395 |
| 7 | 156 | Quelles sont toutes les choses qui pourraient être faites pour améliorer l'information des citoyens sur l'utilisation des impôts ? | 129 141 | 1 | 217,95 | 127 | 430 | 634 | 1 497 | 77 580 | 5 406 | 739 |
| 7 | 157 | Que faudrait-il faire pour rendre la fiscalité plus juste et plus efficace ? | 154 154 | 1 | 358,29 | 193 | 773 | 1 178 | 2 623 | 80 412 | 3 233 | 2 838 |
| 7 | 158 | Quels sont selon vous les impôts qu'il faut baisser en priorité ? | 140 620 | 1 | 137,36 | 70 | 305 | 460 | 1 024 | 42 750 | 26 001 | 338 |
| 7 | 160 | S'il faut selon vous revoir les conditions d'attribution de certaines aides sociales, lesquelles doivent être concernées ? | 123 275 | 1 | 194,43 | 116 | 428 | 620 | 1 267 | 70 617 | 13 758 | 391 |
| 7 | 161 | Quels sont les domaines prioritaires où notre protection sociale doit être renforcée ? | 131 122 | 1 | 108,33 | 49 | 252 | 372 | 823 | 22 995 | 32 320 | 189 |
| 7 | 162 | Pour quelle(s) politique(s) publique(s) ou pour quels domaines d'action publique, seriez-vous prêts à payer plus d'impôts ? | 132 426 | 1 | 103,68 | 50 | 240 | 356 | 758 | 19 034 | 33 865 | 138 |
| 7 | 163 | Y a-t-il d'autres points sur les impôts et les dépenses sur lesquels vous souhaiteriez vous exprimer ? | 135 187 | 1 | 493,36 | 244 | 1 001 | 1 596 | 4 144 | 79 628 | 4 074 | 4 675 |
| 10 | 279 | Que faudrait-il faire selon vous pour apporter des réponses à ce problème ? | 136 840 | 1 | 403,75 | 199 | 882 | 1 381 | 3 277 | 64 537 | 1 720 | 3 598 |
| 10 | 281 | Si oui, de quelle manière votre vie quotidienne est-elle touchée par le changement climatique ? | 92 795 | 1 | 127,81 | 86 | 263 | 366 | 693 | 13 102 | 6 288 | 63 |
| 10 | 283 | Si oui, que faites-vous aujourd'hui pour protéger l'environnement et/ou que pourriez-vous faire ? | 131 190 | 1 | 199,47 | 139 | 406 | 561 | 1 037 | 64 700 | 3 363 | 192 |
| 10 | 284 | Qu'est-ce qui pourrait vous inciter à changer vos comportements comme par exemple mieux entretenir et régler votre chauffage, modifier votre manière de conduire ou renoncer à prendre votre véhicule pour de très petites distances ? | 120 043 | 1 | 168,75 | 108 | 367 | 512 | 966 | 9 987 | 10 829 | 169 |
| 10 | 285 | Quelles seraient pour vous les solutions les plus simples et les plus supportables sur un plan financier pour vous inciter à changer vos comportements ? | 103 299 | 1 | 164,24 | 106 | 351 | 491 | 953 | 55 218 | 8 368 | 129 |
| 10 | 287 | Si oui, que faudrait-il faire pour vous convaincre ou vous aider à changer de mode de chauffage ? | 85 429 | 1 | 123,16 | 81 | 264 | 365 | 675 | 7 461 | 9 217 | 39 |
| 10 | 289 | Si oui, que faudrait-il faire pour vous convaincre ou vous aider à utiliser ces solutions alternatives ? | 72 753 | 1 | 140,39 | 88 | 299 | 417 | 810 | 15 785 | 6 265 | 80 |
| 10 | 291 | Et qui doit selon vous se charger de vous proposer ce type de solutions alternatives ? | 107 378 | 1 | 83,08 | 41 | 196 | 284 | 577 | 5 608 | 27 601 | 42 |
| 10 | 292 | Que pourrait faire la France pour faire partager ses choix en matière d'environnement au niveau européen et international ? | 112 921 | 1 | 175,82 | 112 | 368 | 526 | 1 057 | 35 283 | 9 744 | 238 |
| 10 | 293 | Y a-t-il d'autres points sur la transition écologique sur lesquels vous souhaiteriez vous exprimer ? | 110 576 | 1 | 489,87 | 241 | 1 003 | 1 561 | 4 092 | 308 280 | 4 569 | 3 675 |

## Annexe B — Répartition par question à choix

| Form. | Question | Type | Libellé public | Réponses | Moyenne caractères | Max caractères |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | 2 | single_choice | Savez-vous quels sont les différents échelons administratifs (Etat, collectivités territoriales comme la région, la commune, opérateurs comme par exemple Pole Emploi ou la CAF) qui gèrent les différents services publics dans votre territoire ? | 331 454 | 3,00 | 3 |
| 2 | 3 | single_choice | Pensez-vous qu’il y a trop d’échelons administratifs en France ? | 328 880 | 3,00 | 3 |
| 2 | 4 | multi_choice | Quels sont les niveaux de collectivités territoriales auxquels vous êtes le plus attaché ? | 329 079 | 21,45 | 54 |
| 2 | 5 | single_choice | Lorsqu'un déplacement est nécessaire pour effectuer une démarche administrative, quelle distance pouvez-vous parcourir sans difficulté ? | 328 334 | 13,72 | 14 |
| 2 | 6 | multi_choice | Pour accéder à certains services publics, vous avez avant tout des besoins... | 327 302 | 33,52 | 69 |
| 2 | 7 | multi_choice | Si vous rencontrez des difficultés pour effectuer vos démarches administratives sur Internet, de quel accompagnement souhaiteriez-vous bénéficier ? | 308 043 | 31,32 | 78 |
| 2 | 8 | single_choice | Seriez-vous d'accord pour qu'un agent public effectue certaines démarches à votre place ? | 325 520 | 3,00 | 3 |
| 2 | 9 | single_choice | Que pensez-vous du regroupement dans un même lieu de plusieurs services publics (Maisons de services au public) ? | 329 178 | 11,12 | 14 |
| 2 | 10 | single_choice | Que pensez-vous des services publics itinérants (bus de services publics) ? | 324 145 | 11,41 | 14 |
| 2 | 11 | single_choice | Que pensez-vous du service public sur prise de rendez-vous ? | 324 794 | 11,48 | 14 |
| 2 | 12 | single_choice | Que pensez-vous des agents publics polyvalents susceptibles de vous accompagner dans l'accomplissement de plusieurs démarches quelle que soit l'administration concernée ? | 324 501 | 11,40 | 14 |
| 2 | 13 | single_choice | Avez-vous déjà renoncé à des droits / des allocations en raison de démarches administratives trop complexes ? | 326 394 | 3,00 | 3 |
| 4 | 16 | single_choice | Selon vous, l'Etat doit-il aujourd'hui transférer de nouvelles missions aux collectivités territoriales ? | 78 072 | 3,00 | 3 |
| 4 | 18 | single_choice | Estimez-vous avoir accès aux services publics dont vous avez besoin ? | 85 341 | 3,00 | 3 |
| 4 | 21 | single_choice | Avez-vous déjà utilisé certaines de ces nouvelles formes de services publics ? | 82 262 | 3,00 | 3 |
| 4 | 22 | single_choice | Si oui, en avez-vous été satisfait ? | 25 126 | 3,00 | 3 |
| 4 | 26 | single_choice | Connaissez-vous le "droit à l'erreur", c'est-à-dire le droit d'affirmer votre bonne foi lorsque vous faites un erreur dans vos déclarations ? | 83 079 | 3,00 | 3 |
| 4 | 27 | single_choice | Si oui, avez-vous déjà utilisé ce droit à l'erreur ? | 72 193 | 3,00 | 3 |
| 4 | 30 | single_choice | Faut-il donner plus d'autonomie aux fonctionnaires de terrain ? | 69 473 | 3,00 | 3 |
| 4 | 32 | single_choice | Faut-il revoir le fonctionnement et la formation de l'administration ? | 70 290 | 3,00 | 3 |
| 5 | 49 | single_choice | En dehors des élus politiques, faut-il donner un rôle plus important aux associations et aux organisations syndicales et professionnelles ? | 95 596 | 3,00 | 3 |
| 5 | 52 | single_choice | Le non-cumul des mandats instauré en 2017 pour les parlementaires (députés et sénateurs) est : | 98 630 | 15,31 | 18 |
| 5 | 55 | single_choice | Pensez-vous qu'il serait souhaitable de réduire le nombre d'élus (hors députés et sénateurs) ? | 93 262 | 3,00 | 3 |
| 5 | 58 | single_choice | Faut-il prendre en compte le vote blanc ? | 97 670 | 3,00 | 3 |
| 5 | 61 | single_choice | Faut-il faciliter le déclenchement du référendum d'initiative partagée (le RIP est organisé à l'initiative de membres du Parlement soutenu par une partie du corps électoral) qui est applicable depuis 2015 ? | 95 404 | 5,40 | 14 |
| 5 | 65 | single_choice | Faut-il les transformer ? | 71 719 | 3,00 | 3 |
| 5 | 78 | single_choice | Pensez-vous qu'il faille instaurer des contreparties aux différentes allocations de solidarité ? | 83 769 | 3,00 | 3 |
| 7 | 159 | multi_choice | Afin de financer les dépenses sociales, faut-il selon vous... | 155 657 | 141,91 | 21 190 |
| 10 | 278 | single_choice | Quel est aujourd'hui pour vous le problème concret le plus important dans le domaine de l'environnement ? | 143 303 | 60,51 | 23 909 |
| 10 | 280 | single_choice | Diriez-vous que votre vie quotidienne est aujourd'hui touchée par le changement climatique ? | 138 562 | 3,00 | 3 |
| 10 | 282 | single_choice | À titre personnel, pensez-vous pouvoir contribuer à protéger l'environnement ? | 138 752 | 3,00 | 3 |
| 10 | 286 | single_choice | Par rapport à votre mode de chauffage actuel, pensez-vous qu'il existe des solutions alternatives plus écologiques ? | 131 188 | 3,00 | 3 |
| 10 | 288 | single_choice | Avez-vous pour vos déplacements quotidiens la possibilité de recourir à des solutions de mobilité alternatives à la voiture individuelle comme les transports en commun, le covoiturage, l'auto-partage, le transport à la demande, le vélo, etc. ? | 136 287 | 15,55 | 60 |
| 10 | 290 | multi_choice | Si non, quelles sont les solutions de mobilité alternatives que vous souhaiteriez pouvoir utiliser ? | 96 105 | 52,69 | 15 766 |
| 11 | 306 | multi_choice | Selon vous, faut-il introduire une dose de proportionnelle pour certaines élections, lesquelles ? | 320 408 | 30,04 | 84 |
| 11 | 307 | single_choice | Pensez-vous qu'il serait souhaitable de réduire le nombre de parlementaires (députés + sénateurs = 925) ? | 331 378 | 3,00 | 3 |
| 11 | 308 | single_choice | Faut-il rendre le vote obligatoire ? | 331 065 | 3,00 | 3 |
| 11 | 309 | single_choice | Faut-il avoir davantage recours au référendum au niveau national ? | 330 652 | 3,00 | 3 |
| 11 | 310 | single_choice | Faut-il avoir davantage recours au référendum au niveau local ? | 331 003 | 3,00 | 3 |
| 11 | 311 | single_choice | Faut-il tirer au sort des citoyens non élus pour les associer à la décision publique ? | 332 119 | 4,49 | 14 |
| 11 | 312 | single_choice | Diriez-vous que l'application de la laïcité en France est aujourd'hui: | 328 196 | 13,87 | 23 |
| 12 | 313 | single_choice | Pensez-vous que vos actions en faveur de l'environnement peuvent vous permettre de faire des économies ? | 349 391 | 3,00 | 3 |
| 12 | 314 | single_choice | Diriez-vous que vous connaissez les aides et dispositifs qui sont aujourd'hui proposés par l'Etat, les collectivités, les entreprises et les associations pour l'isolation et le chauffage des logements, et pour les déplacements ? | 349 809 | 3,00 | 3 |
| 12 | 315 | single_choice | Pensez-vous que les taxes sur le diesel et sur l’essence peuvent permettre de modifier les comportements des utilisateurs ? | 349 491 | 3,00 | 3 |
| 12 | 316 | single_choice | À quoi les recettes liées aux taxes sur le diesel et l’essence doivent-elles avant tout servir ? | 345 671 | 69,42 | 82 |
| 12 | 317 | single_choice | Selon vous, la transition écologique doit être avant tout financée : | 348 249 | 15,83 | 31 |
| 12 | 318 | multi_choice | Et qui doit être en priorité concerné par le financement de la transition écologique ? | 346 552 | 18,26 | 66 |
| 12 | 319 | single_choice | Que faudrait-il faire pour protéger la biodiversité et le climat tout en maintenant des activités agricoles et industrielles compétitives par rapport à leurs concurrents étrangers, notamment européens ? | 344 932 | 58,62 | 72 |

## Annexe C — Sources et reproductibilité

Sources internes examinées : `app/models.py`, `ingest/postgres.py` (projection des réponses et choix), `app/routers/api_questions.py`, `app/services/questions.py`, `app/services/search.py`, `app/services/contributions.py`, `docs/ingestion-resultats.md`, ainsi que les catalogues PostgreSQL `information_schema`, `pg_constraint`, `pg_indexes` et `pg_extension`. Les mesures reprennent les sept formulaires présents, sans télécharger les exports officiels.

Le fichier voisin [audit-corpus-rag.sql](audit-corpus-rag.sql) contient les requêtes agrégées utilisées, encadrées par une transaction en lecture seule. Il produit des compteurs et histogrammes sans réponses brutes ; le diagnostic lexical échantillonné est décrit en section 6. Les histogrammes suffisent à recalculer les percentiles discrets et les simulations en caractères.
