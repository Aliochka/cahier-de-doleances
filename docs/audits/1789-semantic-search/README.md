# Premier test de recherche transhistorique — 1789–2019

Expérience locale du 26 octobre 2026. **BGE-M3 retrouve effectivement des passages historiques utiles à partir de formulations contemporaines. Le signal justifie de poursuivre les essais et une extraction contrôlée, sans valider une intégration publique à ce stade.** Le modèle produit aussi des rapprochements trompeurs et manque des articles pertinents pourtant présents.

Les recherches ont réellement été exécutées : **269 articles A de 1789, 240 réponses locales de 2019, 30 requêtes, cinq méthodes, deux populations, 300 classements**. Les dix premiers résultats de chaque classement ont été examinés : **1 139 couples requête–passage distincts**, auxquels s’ajoutent **16 témoins ciblés**, soit **1 155 jugements**. Leurs textes et références sont conservés. Ce sont des **jugements exploratoires Codex, non indépendants**, pas une évaluation humaine historique ou statistique.

L’application, ses index et ses bases n’ont pas été sollicités ou modifiés. Aucun accès PostgreSQL, téléchargement de modèle, entraînement, déploiement ou publication des cahiers n’a été effectué. Les **147 fichiers** des trois audits précédents sont inchangés.

## Livrables

| Objet | Fichier |
|---|---|
| Protocole et requêtes figés avant les classements | [protocol.json](protocol.json), [queries.json](queries.json), [preregistration.json](preregistration.json) |
| Configuration réelle du moteur et écarts expérimentaux | [ENGINE.md](ENGINE.md) |
| Corpus exact, provenance et contexte séparé | [data/corpus.jsonl](data/corpus.jsonl), [data/preparation.json](data/preparation.json) |
| Représentations effectivement encodées et ressources | [data/historical-segments.jsonl](data/historical-segments.jsonl), [data/encoding.json](data/encoding.json), [vectors/](vectors/) |
| Classements bruts, jusqu’à 50 résultats | [data/rankings.jsonl](data/rankings.jsonl) |
| Dix premiers résultats avec texte, références et jugement | [data/results.jsonl](data/results.jsonl) |
| Jugements réévaluables, indépendants des scores de recherche | [annotations.json](annotations.json), [review-decisions.py](review-decisions.py) |
| Tableau comparatif détaillé et mesures par requête | [COMPARISON.md](COMPARISON.md), [data/metrics.json](data/metrics.json) |
| Six réussites, six rapprochements problématiques et trois passages manqués | [GALLERY.md](GALLERY.md) |
| Diagnostics de couverture, longueur et précision numérique | [data/diagnostics.json](data/diagnostics.json), [data/novelty.json](data/novelty.json) |
| Reproduction, conventions et contrôles | [DATA.md](DATA.md), [data/checks.json](data/checks.json), [data/reproducibility.json](data/reproducibility.json) |

## 1. Corpus et sélection

### 1789

Les trois rapports antérieurs et les fichiers expérimentaux ont été consultés. Le [pilote documentaire](../1789-extraction-pilot/README.md) fournit exactement les **269 unités A**, issues de **28 des 30 parents** : les deux cahiers sans articles A ne sont pas transformés en passages artificiels. Les **490 B et 187 plages C sont exclus**, sans mélange silencieux de statuts.

A certifie des frontières revues dans la transcription XML par Codex ; cela ne certifie ni chaque caractère OCR, ni le manuscrit original, ni une expertise historique indépendante. Le corpus conserve la formulation TEI, ses césures, graphies, ponctuation, blancs et erreurs. Les textes ne sont ni modernisés ni corrigés. Les références, positions et ancres du pilote sont recopiées et contrôlées.

Deux entrées sont comparées : **A, texte seul** ; **B, titre documentaire vérifié dans le pilote + titre exact de section lorsqu’il existe + article**. Le titre d’affichage du pilote peut être éditorial ; il reste un champ de contexte distinct du texte historique. Aucun synonyme moderne ni mot-clé thématique n’a été ajouté. Les contextes B ne sont pas identiques en longueur : c’est la recette réellement testée, pas une ablation à nombre de tokens constant.

Ce sous-ensemble est documentaire et raisonné, avec une surreprésentation de débuts de cahiers et d’articles courts. Sa représentativité thématique n’est pas établie. Les textes vont de **33 à 6 198 caractères**, médiane **235**. Les thèmes absents des A peuvent exister dans les B, C, parents ou cahiers non sélectionnés.

### 2019

Aucune base n’a été ouverte. Les fichiers locaux RAG-007/RAG-013 contiennent un ensemble de **20 000 unités**, union expérimentale enrichie d’un tirage aléatoire et d’un échantillon stratifié antérieur, lui-même non représentatif du corpus national.

Dans cet ensemble, on trie les unités de chaque questionnaire par `sha256("1789-semantic-v1:" + document_id)`, puis on prend **60 réponses par questionnaire**, en excluant toute contribution parente déjà retenue. Résultat : **240 réponses provenant de 240 contributions distinctes**, questionnaires 4, 5, 7 et 10. Le tirage n’utilise ni les requêtes, ni des scores, ni une recherche thématique. Il conserve les réponses minimales, les hors-sujets et les textes longs, sans filtrage opportuniste. Les textes sont reconstruits à partir des plages des représentations locales et vérifiés par l’empreinte du texte d’origine.

La présence des thèmes demandés a été contrôlée après sélection, sans modifier l’échantillon : des réponses abordent impôts, justice, représentation, inégalités, écologie et d’autres sujets. Un simple repérage littéral trouve notamment **24** réponses sur la fiscalité et **4** contenant des termes judiciaires ; ces comptages ne sont pas des annotations exhaustives. La couverture de la justice contemporaine est donc particulièrement faible. Certaines questions ne disent que « Si oui, comment ? » : leur contexte amont n’est pas reconstitué artificiellement.

Les textes vont de **1 à 3 806 caractères**, médiane **94**. Les équilibres 60/60/60/60 concernent seulement le plan de sélection. **Aucun quota de corpus n’intervient dans les classements.**

## 2. Encodage et recherche réellement exécutés

Le modèle local et le code existant sont réutilisés : `BAAI/bge-m3`, révision **`5617a9f61b028005a4858fdac845db406aefb181`**, sortie dense **1 024 dimensions**, pooling **CLS**, normalisation **L2**, sans préfixe de requête. L’adaptateur Transformers existant refuse toute troncature. La [fiche officielle figée](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/README.md) documente la fenêtre de 8 192 tokens et l’absence d’instruction obligatoire pour les requêtes ; la recette segmentée du projet reste plus courte.

Le snapshot déjà présent a été vérifié et chargé hors ligne. L’environnement d’embeddings historique possède un lien d’interpréteur devenu invalide ; l’expérience utilise le `.venv` existant de la racine, compatible : Python 3.11, Torch **2.10.0+cpu**, Transformers **4.57.6**, NumPy **2.2.6**. Aucune dépendance n’est installée. Le GPU étant indisponible, l’encodage historique et les requêtes utilisent **CPU/float32, quatre threads**.

La segmentation reprend la recherche de préfixe, les frontières de phrase et le chevauchement du code existant : **budget de 1 024 tokens, chevauchement de 128**, contexte et tokens spéciaux compris. Seul le préfixe documentaire est adapté aux cahiers. Chaque variante produit **270 segments pour 269 articles** ; un article long a deux segments et reste un seul résultat, agrégé par **cosinus maximum**. Les offsets restent ceux du texte exact de l’article. Aucun ANN n’est nécessaire : tous les segments admissibles sont comparés exactement.

Les **240 vecteurs contemporains existants** sont réutilisés : même snapshot, dimension, pooling, normalisation et recette « Question / Réponse ». Ils avaient été calculés sur GPU en bfloat16 et stockés en float32. Pour vérifier cet écart numérique, **16 représentations réparties sur les longueurs** ont été réencodées sur CPU : cosinus minimal entre versions **0,999812**, écart maximal de similarité parmi les 30 requêtes **0,001504**. Remplacer diagnostiquement ces 16 vecteurs modifie un résultat du top 10 pour une seule des **60 combinaisons requête × variante**. La compatibilité est forte, mais **les ex æquo proches ne sont pas garantis identiques**, et ce contrôle ne porte pas sur les 240 textes.

Les cinq méthodes sont :

| Méthode | Calcul |
|---|---|
| `lexical` | BM25 sur article/réponse seul, Snowball français et stopwords, `k1=1,2`, `b=0,75` ; seuls les scores positifs sont retournés |
| `vector_A` | Articles historiques sans contexte ; représentations B de 2019 conservées |
| `vector_B` | Articles historiques avec contexte documentaire ; mêmes vecteurs contemporains |
| `hybrid_A` | RRF du lexical et de `vector_A` |
| `hybrid_B` | RRF du lexical et de `vector_B` |

La RRF réutilise **la fonction existante**, poids égaux, **k=60**, rangs commençant à 1, **50 candidats par branche**, départage par identifiant. Les branches sont les méthodes, jamais les époques.

Chaque méthode est exécutée sur **1789 seul**, puis sur **les 509 unités ensemble**. Dans la population commune, IDF et longueurs moyennes BM25 sont recalculés globalement ; les vecteurs sont comparés dans un seul espace et les segments regroupés par passage avant fusion. Il n’existe aucun classement séparé par époque à équilibrer.

**Écarts au moteur public :** BM25 est une référence expérimentale, pas la formule lexicale PostgreSQL publique ; pas de GIN, HNSW, statistiques des millions d’unités, hydratation publique, filtrage ou service HTTP. Les représentations historiques et contemporaines restent différentes. Les résultats n’évaluent donc pas exactement le moteur public ni une future population complète.

## 3. Requêtes, jugements et limites de mesure

Les requêtes et le protocole ont été figés à **10:55:09 UTC**, avant calcul et examen des classements ; les empreintes sont conservées. Les 30 requêtes comprennent **12 formulations contemporaines**, **6 historiques**, **6 ambiguës** et **6 contre-exemples numériques**. Elles n’ont pas été modifiées après observation des scores.

Le pool est l’union des dix premiers résultats des cinq méthodes et des deux populations. Les **369 textes uniques** de ce pool ont été lus avec les questions contemporaines, puis les ensembles de candidats examinés par requête, sans rang ni score dans les supports initiaux de notation. Les **61 autres articles historiques** ont aussi été lus pour repérer des absences et des témoins manqués. Seize annotations complémentaires sont explicitement identifiées hors pool ; elles ne constituent pas un jeu de pertinence exhaustif.

Échelle : **3** réponse directe ou revendication substantiellement équivalente ; **2** préoccupation pertinente, proposition différente ; **1** proximité superficielle ; **0** hors sujet ou rapprochement trompeur. Une opposition explicite peut répondre à une question : « aucun impôt à baisser » n’est pas hors sujet. À l’inverse, qui paie l’impôt n’est pas automatiquement une réponse à qui doit y consentir.

Les décisions explicites sont conservées par identifiant, avec texte justificatif. Une seconde lecture a rendu la notation plus stricte sur les faux amis et les thèmes trop larges. **La calibration finale a eu lieu dans la même session que l’examen des résultats : ce n’est pas un test aveugle indépendant.** Les notes ne sont pas calculées à partir des cosinus ou du BM25. Aucun temps de validation humaine n’est revendiqué.

Les notes moyennes @5/@10 utilisent respectivement 5/10 positions, avec zéro pour une position non retournée. Les proportions fortes ou hors sujet portent sur les résultats effectivement retournés, dénominateur affiché. Une note 1 reste inutilisable comme preuve de pertinence, même si elle compte dans la métrique graduée.

Le **nDCG@10 gradué** utilise `2^note−1` et un idéal construit sur **le pool jugé de la même population + les témoins complémentaires**. Il est calculable pour 26 requêtes historiques et 30 mixtes ; les idéaux nuls restent `null`, pas un succès artificiel. Une variante **« utile » met les notes 0 et 1 à zéro** : 21 requêtes historiques et 25 mixtes ont alors un utile connu. Cette variante évite de donner une bonne note à un classement ne contenant que des rapprochements superficiels.

Ces nDCG sont **poolés**, pas des mesures sur tous les passages pertinents. Pas de rappel global, intervalle de confiance, significativité ou extrapolation nationale. Les requêtes, jugements et sources restent assez petits et dépendants pour demander une réévaluation humaine.

## 4. Résultats comparatifs

### Articles historiques seuls

Moyennes sur 30 requêtes ; les colonnes nDCG utilisent leurs populations de requêtes admissibles précisées ci-dessus.

| Méthode | Note@5 /3 | Note@10 /3 | nDCG@10 | nDCG utile | Forts parmi retournés | Hors sujet parmi retournés |
|---|---:|---:|---:|---:|---:|---:|
| Lexicale | 1,373 | 1,313 | 0,555 | 0,536 | 19,1 % | 23,0 % |
| Vectorielle A | 1,600 | 1,450 | 0,696 | 0,696 | 24,3 % | 25,3 % |
| Vectorielle B | 1,573 | 1,440 | 0,687 | 0,696 | 22,7 % | 25,3 % |
| Hybride A | 1,553 | 1,453 | 0,660 | 0,681 | 24,3 % | 26,7 % |
| Hybride B | 1,560 | 1,467 | 0,664 | 0,691 | 24,0 % | 26,3 % |

La référence lexicale retourne **283** résultats sur les 300 positions possibles ; les autres méthodes en retournent 300. **L’amélioration de la pertinence moyenne n’implique pas une capacité à refuser une requête hors sujet.**

Sur les **12 formulations contemporaines**, le vectoriel A atteint **1,992/3 @10**, contre **1,733** en lexical ; nDCG utile **0,681 contre 0,456**. C’est le signal le plus directement lié à l’objectif transhistorique. En vocabulaire historique explicite, l’hybride B obtient un nDCG utile de **0,830** : le lexical conserve un rôle important.

La contextualisation B n’apporte **pas de gain global démontré** : très légère baisse de note moyenne et de nDCG gradué par rapport à A, presque égalité du nDCG utile. Elle aide certains cas, par exemple l’égalité des peines, et en dégrade d’autres. Elle ne doit pas être généralisée comme une amélioration acquise.

### Liste commune 1789–2019

| Méthode | Note@5 /3 | Note@10 /3 | nDCG@10 | nDCG utile | Forts parmi retournés | Hors sujet parmi retournés |
|---|---:|---:|---:|---:|---:|---:|
| Lexicale | 1,360 | 1,280 | 0,448 | 0,435 | 18,0 % | 25,8 % |
| Vectorielle A | 1,660 | 1,540 | 0,633 | 0,570 | 25,0 % | 15,3 % |
| Vectorielle B | 1,527 | 1,467 | 0,597 | 0,500 | 21,7 % | 14,0 % |
| Hybride A | 1,667 | 1,577 | 0,594 | 0,593 | 26,7 % | 18,3 % |
| Hybride B | 1,667 | 1,527 | 0,588 | 0,574 | 24,3 % | 18,0 % |

Le lexical retourne **295** résultats ; les autres 300. **Il n’y a pas de vainqueur universel** : l’hybride A améliore la note moyenne et le nDCG utile sur cette population, mais le vectoriel A garde le meilleur nDCG gradué. Les annotations et les populations admissibles des deux nDCG diffèrent dans leur traitement de la proximité superficielle ; conserver les deux évite une conclusion sélective.

Le contexte historique B réduit la présence historique moyenne dans les dix premiers résultats vectoriels de **3,2 à 1,4**, sans changement des 240 vecteurs contemporains. Cela ne prouve ni discrimination ni correction nécessaire par quota : le texte d’entrée, la longueur, les questions modernes et leurs scores sont différents. Sur « Faut-il réduire les impôts ? », les dix premiers résultats vectoriels A communs viennent tous de 2019. Des passages historiques pertinents existent et sont retrouvés dans la recherche historique seule ; leur présence en première page commune n’est pas garantie.

Six requêtes ont dans leur top 10 vectoriel A commun **au moins un historique et un contemporain de note ≥2** : responsabilité des représentants, abus de pouvoir, aide aux pauvres, privilèges fiscaux, ordre public et représentation nationale. Ce sont des **préoccupations voisines ou des réponses différentes**, pas six démonstrations d’identité entre revendications de 1789 et de 2019. La galerie montre notamment la responsabilité des ministres face à la nation et les demandes contemporaines de révocation ou de respect des promesses.

## 5. Réussites, confusions et échecs observés

Les [15 cas de la galerie](GALLERY.md) incluent textes réels, parents, pages, ancres, rangs et scores par méthode. Quelques constats décisifs :

- **« Justice moins coûteuse » → « Abrégé des frais de procédure »** : Ermenonville, article 11, dixième en vectoriel A historique, absent des 50 lexicaux conservés. Mirecourt, article 12, arrive premier en vectoriel A et décrit les lenteurs et frais des procès. Le rapprochement ne repose pas sur le seul mot « justice ».
- **Équité fiscale → Albertas, article 2** : deuxième en vectoriel A historique, sans résultat dans les 50 lexicaux conservés. Cela montre un accès sémantique à une formulation différente, sans prétendre que le modèle comprend toute la fiscalité d’Ancien Régime.
- **Liberté d’expression → presse et parole**, Ferrières : premier en vectoriel A contre sixième lexical ; le lexical trouvait déjà le passage.
- **« Réduire les impôts » → « Tous impôts réduits à un seul »** : proximité pertinente mais réduction du nombre d’impôts, pas preuve de baisse du prélèvement. Premier résultat vectoriel A, note 2, pas 3.
- **Coopération entre États → retour périodique des États généraux** : premier résultat historique vectoriel A, cosinus **0,571**, note 0. Un score relativement élevé peut être historiquement trompeur.
- **Taille des classes → terres de première classe et taille fiscale** ; **voitures électriques → quatre mulets attelés** : faux amis réels, non corrigés automatiquement par la fusion.
- **Fibre optique → prolongation des baux de campagne** et **cyberattaques → répression des écrivains** : voisins imposés par un classement sans mécanisme d’abstention, pas des analogies valables.
- **Article pertinent manqué** : Pierrelez demande explicitement une modération des impositions, mais reste 26e en A et 28e en B pour la baisse d’impôts. Les bureaux de district du clergé de Vie restent 14es en A pour la proximité des services. Ces échecs ne sont pas des absences documentaires.

Aucun passage historique utile n’a été identifié dans les A pour **neuf requêtes**, dont les six numériques, la taille des classes, la coopération internationale et la représentation politique des femmes. Cette appréciation est limitée aux 269 textes lus. Une recherche sans correspondant historique dans ce lot n’est pas un test de rappel du modèle sur un document inexistant.

Les notes distinguent aussi des **propositions opposées** : aider les pauvres / réduire les secours ; abolir / maintenir des immunités provinciales ; liberté de presse / poursuites d’écrivains. Un thème commun ne suffit pas à attribuer une revendication commune aux contributeurs. Les stéréotypes ou propos discriminatoires présents dans les sources ne sont ni réécrits ni approuvés par la notation de pertinence.

### Longueur et défauts documentaires

Le passage historique le plus long, Alençon article 2, est présent dans **1** top 10 vectoriel A, **6** en B et **8** hybrides B. La longueur moyenne des résultats historiques passe de **434 caractères** en vectoriel A à **639** en B. Ce sont des corrélations descriptives, pas une preuve causale de biais de longueur : titre, mots, numérisation et thèmes changent ensemble.

L’OCR très altéré de Montigny est conservé. Certains passages restent retrouvés, mais cette expérience sans témoin corrigé ne mesure pas l’effet propre de l’OCR. La faiblesse d’un résultat peut aussi venir du contexte documentaire, d’un article multithématique ou de la couverture du sous-corpus ; ne pas tout attribuer au modèle.

## 6. Coût réellement observé

Machine : AMD Ryzen 9 7950X, 16 cœurs physiques / 32 logiques, environ 125 Gio de RAM visible. Inférence limitée à quatre threads CPU ; GPU indisponible.

| Opération | Mesure |
|---|---:|
| Préparation/tokenisation historique et vérification du snapshot dans l’encodeur | 3,65 s |
| Chargement du modèle après préparation | 0,52 s |
| Encodage A : 270 segments, 20 386 tokens utiles | 37,32 s |
| Encodage B : 270 segments, 31 666 tokens utiles | 55,52 s |
| Encodage des 30 requêtes | 1,83 s, soit environ 61 ms/requête |
| Contrôle comparatif CPU de 16 représentations contemporaines | 3,76 s pour la passe mesurée |
| Mémoire RSS maximale échantillonnée pendant l’encodage | 2,62 Gio |

Les durées des documents incluent tokenisation de contrôle, padding et normalisation ; « tokens » compte les entrées non paddées. Les passes ne prétendent pas mesurer le temps total de développement, de lecture ou de transfert des artefacts. La première exécution a également répété les 16 encodages de diagnostic pour leur conservation ; le script livré les conserve directement, sans cette répétition inutile. Les classements n’utilisent que les vecteurs contemporains archivés, pas ces vecteurs de contrôle.

À vecteurs et modèle déjà chargés, le calcul exact des classements est de l’ordre de **quelques dixièmes de milliseconde**, la fusion de l’ordre de la milliseconde sur ce lot. Le coût de requête est dominé par son encodage, environ **61–63 ms** avec récupération et fusion. Les [temps par requête](data/search-timings.json) et [coûts agrégés](data/diagnostics.json) sont conservés ; les reprises font varier ces microdurées. Une seule passe de 30 requêtes ne fournit pas de latence de service ni de capacité concurrente en production.

## 7. Vérifications et reproductibilité

- Empreintes des 147 fichiers des audits antérieurs, des 434 artefacts locaux consultés pour l’échantillon et du snapshot BGE contrôlées.
- Fidélité des 269 textes A, rattachement aux parents, plages sources et séparation du contexte ; reconstruction des textes 2019 vérifiée contre leur empreinte locale.
- Offsets des segments, couverture sans perte, ordre, chevauchement, limite de tokens, dimensions, valeurs finies et normes des vecteurs contrôlés.
- Toutes les occurrences du top 10 ont une note ; identifiants uniques, rangs, scores ordonnés et provenance contrôlés. Six corruptions injectées en mémoire sont détectées.
- Deux reprises **sans réencodage** reproduisent **12 artefacts identiques**, dont corpus, classements bruts, jugements et métriques. Les horodatages et durées ne sont pas comparés octet pour octet.
- **36 tests unitaires existants** des embeddings et de la fusion réussis ; Ruff et vérification des artefacts exécutés. Les suites de base, HTTP et frontend n’ont pas été lancées : aucun de leurs composants n’a changé.

Les commandes et dépendances réellement utilisées figurent dans [DATA.md](DATA.md). Les fichiers NumPy livrés permettent de refaire les recherches sans télécharger un modèle ou relancer l’encodage. Les textes citoyens ne sont pas envoyés à un service externe.

## 8. Recommandations par coût et intérêt

| Priorité | Expérience proposée, non commencée | Intérêt / coût |
|---|---|---|
| 1 | Faire réévaluer anonymement les couples actuels par des annotateurs, avec arbitrage historique et mesure du temps | Faible coût technique, fort besoin de validation des conclusions |
| 2 | Ajouter un lot documentaire nouveau et un échantillon 2019 mieux couvert par thème, figés avant test | Évite de confondre couverture et capacité sémantique ; coût documentaire moyen |
| 3 | Tester des contextes courts comparables, notamment le contrôle « réponses 2019 seules », sur un jeu séparé | Isole les effets de recette et de longueur ; encodage limité supplémentaire |
| 4 | Évaluer les faux amis et l’absence de réponse, avec témoins positifs et négatifs et seuils calibrés sur un autre jeu | Fort intérêt ; aucun seuil universel ne se déduit des cosinus observés ici |
| 5 | Comparer une forme de recherche décésurée/corrigée contre un témoin validé, sans toucher au texte d’affichage | Mesure l’effet propre de l’OCR ; coût de référence non négligeable |
| 6 | Étudier l’effet de taille, des articles longs, des doublons et de la présélection sur une population locale plus grande | Nécessaire avant toute projection sur les millions de réponses |

Ne pas introduire maintenant de traduction moderne, réécriture générative, nouveau modèle ou quota historique pour rendre les exemples plus favorables. Le présent test n’en démontre pas le besoin. Conserver la représentation A comme référence simple et les variantes B/hybrides comme comparaisons à départager.

Les réserves de droits des audits documentaires restent applicables avant une republication ; la présente étude locale ne les résout pas. Aucune collecte Persée ou ARTFL supplémentaire n’a été nécessaire.

## 9. Réponses explicites Q1–Q10

**Q1 — BGE-M3 retrouve-t-il des revendications historiques avec des requêtes contemporaines ?** Oui sur plusieurs cas vérifiables, notamment frais de procédure, équité fiscale, responsabilité ministérielle, presse et garanties contre l’arbitraire. Sur les 12 requêtes contemporaines, le vectoriel A améliore la note moyenne et le nDCG utile par rapport au BM25 de ce lot. Cela reste un signal exploratoire non indépendant.

**Q2 — Quels rapprochements 1789–2019 sont observés ?** La liste commune retrouve, entre autres, responsabilité des gouvernants, secours et représentation politique. Six requêtes ont un résultat utile de chaque époque dans le top 10 vectoriel A. Les acteurs, institutions et propositions diffèrent : ce n’est pas une identité historique. Pour la baisse d’impôts, les premiers résultats communs sont uniquement contemporains.

**Q3 — Valeur ajoutée du vectoriel ?** Des textes pertinents absents des 50 lexicaux sont retrouvés : « frais de procédure », ministres « comptables », équité exprimée par « égale répartition ». Il conserve aussi des erreurs ; ce gain n’est pas un remplacement justifié du lexical.

**Q4 — Gain du contexte documentaire ?** Non démontré globalement. B aide ponctuellement mais baisse plusieurs moyennes, surtout dans le classement commun. Tester des contextes plus courts et des recettes comparables sur un lot distinct avant décision.

**Q5 — Bénéfice hybride mesurable ?** Oui pour certaines mesures et catégories : en population mixte, hybride A atteint 1,577/3 @10 et 0,593 en nDCG utile, contre 1,540 et 0,570 pour vectoriel A. Mais son nDCG gradué est inférieur, 0,594 contre 0,633. Pas de supériorité universelle ni conclusion statistique générale.

**Q6 — Confusions et anachronismes ?** États généraux/pays souverains, taille fiscale/classes scolaires, voitures attelées/électriques, « ordre », lettres de cachet/confidentialité numérique et répression/cyberattaque. La RRF ne les supprime pas systématiquement ; les sources conservent aussi des demandes opposées.

**Q7 — Poursuivre l’extraction à plus grande échelle ?** Oui par lots documentaires contrôlés pour diversifier l’évaluation, car le signal sémantique est réel. Non à un import massif ou à une publication déduite de ces seuls scores. Les risques documentaires du pilote précédent restent entiers.

**Q8 — Adapter l’encodage historique ?** Pas de recette améliorée validée. Le texte seul constitue une bonne référence dans ce test. Conserver le contexte et les segments séparés du texte original, puis évaluer explicitement les alternatives ; ne pas moderniser pour obtenir de meilleurs rangs.

**Q9 — Limites pour le multicorpus complet ?** Corpus minuscules et non représentatifs, annotations non indépendantes et partielles, couverture contemporaine judiciaire faible, contexte asymétrique, précision numérique légèrement différente, BM25 distinct du lexical public, aucune mesure ANN/concurrence ni effet des millions de contributions. Les scores ne sont pas des probabilités comparables par seuil fixe.

**Q10 — Prochaine expérience ?** Une évaluation indépendante du pool actuel puis un lot nouveau, stratifié et gelé avant classement, avec témoins de pertinence hors résultats, contre-exemples et contrôle de contexte comparable entre époques. Mesurer désaccords, absences, rappel sur référence et effort humain avant de spécifier une intégration applicative.
