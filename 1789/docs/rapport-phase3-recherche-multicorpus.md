# Phase 3 — Recherche multicorpus en laboratoire

Date : 7 novembre 2026. Mission : moteur expérimental distinct de H1, sans modification des routes publiques, du frontend public ou des données existantes. Aucune publication de 1789. La phase 4 reste à autoriser.

## Résultat livré et environnement réellement utilisé

Le laboratoire propose `tous` par défaut, `2019` seul et `1789` seul, en lexical, vectoriel, hybride ou comparaison des trois listes. Il utilise les vrais stockages locaux, pas une copie miniature : **5 172 356 unités GDN / 5 187 190 segments**, et **1 224 cahiers / 10 748 passages admissibles**. Les bases restent séparées et sont reliées en lecture seule par les adaptateurs.

Accès : **http://127.0.0.1:1792/**. Le [guide de lancement](../../multicorpus/README.md) donne la commande complète et les identités physiques pré-vérifiées. Il faut lancer le serveur si son processus a été arrêté. Il n’existe aucun démarrage automatique dans l’application publique.

Destination GDN : PostgreSQL local `127.0.0.1:5432`, cluster `7697259424657850634` ; base applicative `cahier_doleances_local`, OID 16385, révision `forms_statistics_v1` ; recherche `cahier_rag`, OID 2106636, révision RAG vérifiée `rag_0007`. Le rôle `cahier_search_reader` existant est utilisé pour la recherche, sans droit nouveau. L’hydratation utilise explicitement le socket applicatif `/var/run/postgresql`, avec identité source identique et transactions READ ONLY.

Destination documentaire : base isolée de phase 2 `documentary_1789_test`, socket `/tmp/documentary-phase1-45FiOt/socket`, port 55487, cluster `7705356223649726476`, répertoire `/tmp/documentary-phase1-45FiOt/data`. Collection `reference-documents-2-7cbcaea79991`. Si `/tmp` disparaît, utiliser la procédure de reconstruction/restauration de phase 2 avant de fournir une nouvelle identité explicite.

Machine : Ryzen 9 7950X, CPU, PostgreSQL 17.11. Les mesures ne représentent pas une charge de production concurrente. Le moteur conserve le budget de référence : 18 s globales, encodage 3 s, statistiques et recherches SQL des deux bases ensemble 10 s, hydratation 2 s. Les opérations SQL sont annulables par le moniteur existant. Les temps excluent le transport HTTP, JSON et le navigateur.

## Composants et contrats

| Fichier | Rôle |
|---|---|
| [core.py](../../multicorpus/core.py) | Requête, sélection des corpus, statistiques cumulées, encodage unique, scores communs, deux listes globales et RRF unique |
| [adapters.py](../../multicorpus/adapters.py) | Adaptateurs GDN/documentaire, candidats par réponse/cahier, témoins, hydratation et références |
| [environment.py](../../multicorpus/environment.py) | Refus des destinations distantes, identités physiques explicites, connexions READ ONLY |
| [lab.py](../../multicorpus/lab.py), [interface](../../multicorpus/static/multi.html) | CLI, serveur loopback, essais libres, filtres, comparaison H1 et lecteurs locaux |
| [evaluation.py](../../multicorpus/evaluation.py) | Comparaisons A/B/C, matrice des profondeurs, filtres, plans, termes très fréquents et concurrence |
| [tests](../../tests/test_multicorpus.py), [smoke Chromium](../../multicorpus/smoke.cjs) | Identités de résultats, absence de quotas, statistiques communes, filtrage, SQL réel et interface |

**Aucune adaptation du stockage, migration, index ou service permanent n’a été nécessaire.** Aucun fichier de moteur GDN/H1 n’a été modifié. Le laboratoire réutilise son encodeur, ses validateurs, son budget, les gardes lecteurs, les protections ANN et ses index. Le documentaire réutilise les représentations, statistiques, règles d’admissibilité, regroupement et lecteur intégral de phase 2.

Les adaptateurs exposent `identity`, `statistics`, `lexical`, `vector`, `hydrate` et leurs capacités. Chaque candidat contient une clé documentaire composée, corpus, ID documentaire, ID d’unité, score de branche et témoin. `2019:<answer_id>` identifie une réponse entière ; `1789:<document_id>` identifie un cahier. La contribution n’intervient jamais dans le regroupement GDN. Les entiers d’identité sont conservés sous forme de chaînes dans le contrat de présentation pour éviter les pertes de précision JavaScript.

`DocumentaryAdapter` reçoit un scope corpus/release et un validateur explicite. Les requêtes documentaires et le regroupement sont réutilisables pour une future collection documentaire ; sa politique de publication, ses champs et sa recette devront être déclarés et validés. Aucun autre corpus n’a été ajouté et le sélecteur de ce laboratoire reste limité à 1789/2019. Les questionnaires ne sont pas déplacés dans `documentary`.

Le résultat garde les deux témoins, les rangs globaux, la RRF, les métadonnées propres au contenu et les identités de release/éditorial/recettes/publication dans l’instantané retourné. Les réponses GDN sont relues depuis la source et comparées aux empreintes des unités indexées avec l’extracteur existant. Seuls les champs nécessaires à la présentation sont exposés ; les contextes internes de contribution ne sont pas copiés dans les cartes.

## Classement lexical commun

Une seule analyse `pg_catalog.french` produit les lexèmes. La nouvelle recette de laboratoire interprète la recherche libre comme une union de termes, sans syntaxe avancée de phrases/exclusions ; H1 conserve son analyse d’origine. Au plus 512 caractères et 32 lexèmes.

Pour les corpus sélectionnés, `N = Σ N_corpus`, `df(t) = Σ df_corpus(t)` puis `IDF(t) = ln(1 + (N − df + 0,5)/(df + 0,5))`. Les N/DF proviennent des statistiques figées GDN `rag_tuning` et des statistiques préparées de phase 2 `documentary.lexical_term_statistics`. **Aucun recalcul des millions d’unités GDN.** Population commune : 5 183 104 unités statistiques lorsque les deux corpus sont sélectionnés. Unité GDN : TextUnit historique ; unité documentaire virtuelle : passage avec union de son texte et des métadonnées du cahier. Il ne s’agit pas d’une DF de réponses/cahiers distincts.

Score : **0,5 couverture IDF + 0,3 couverture simple + 0,2 fréquence**. Fréquence GDN : `ts_rank(texte, requête, 32)`. Fréquence documentaire : `0,75 ts_rank(texte) + 0,25 ts_rank(métadonnées)`. Les titres et lieux restent associés au cahier ; une correspondance répartie entre métadonnées et texte compte dans la couverture sans double compter un terme présent dans les deux. Les statistiques ne sont pas recalculées pour chaque sous-filtre.

Le SQL GDN calcule le score sur toutes les unités lexicalement correspondantes, choisit le meilleur témoin par `answer_id`, puis applique la limite documentaire. Aucun top-N d’unités approximatif n’est interposé. Le documentaire calcule ses meilleurs passages avec les poids IDF communs, puis regroupe par cahier comme en phase 2. Les D candidats locaux sont triés selon leur score commun et clé stable pour former **un classement lexical global de D documents**.

## Vectoriel et fusion

La requête est encodée **une seule fois** pour le nouveau moteur, BGE-M3, révision `5617a9f61b028005a4858fdac845db406aefb181`, snapshot vérifié identique à phase 2, dimension 1 024, CPU float32, normalisation L2, sans téléchargement ni recalcul de vecteurs documentaires.

Les embeddings GDN existants sont contextualisés par leur question, avec segments de 1 024 tokens et chevauchement. Ceux de 1789 portent exclusivement sur le passage technique ; les titres et lieux ne sont pas ajoutés. Les vecteurs stockés ont été produits en bfloat16 puis normalisés/stockés float32. L’encodage commun float32 reprend le choix du service public pour les requêtes. Ces différences sont documentées, sans recalibrage automatique des similarités.

GDN : HNSW existant, ef_search 1 000, parcours itératif strict, max_scan_tuples 20 000, scan_mem_multiplier 1. La profondeur initiale de **400 segments** peut croître jusqu’à 50 000 si D réponses ne sont pas obtenues. Le meilleur segment de chaque réponse est retenu avant la limite documentaire. Un filtre question sur au plus 5 000 unités utilise la protection exacte existante ; pas de bascule d’un grand ensemble vers un exact non borné. Les traces distinguent segments demandés/retournés, réponses, plafond et limitation ANN éventuelle ; les segments retournés ne sont pas le nombre de nœuds visités dans le graphe.

1789 : parcours vectoriel exact sur les unités admissibles, meilleur passage par cahier avant D. Aucun HNSW ajouté. Les candidats des deux adaptateurs sont triés ensemble par similarité cosinus et clé stable, puis limités à D : **aucune RRF de listes vectorielles locales**.

Une seule RRF `Σ 1/(60 + rang_global)` fusionne les deux branches documentaires globales. Profondeur D 50/100/200 ; sortie toujours limitée à 50 documents. Les D candidats par stockage sont une profondeur de collecte, jamais une garantie de place. Le résultat peut ne contenir aucun cahier ou aucun GDN. Les tests vérifient explicitement ce cas.

Le témoin de la branche au meilleur rang global est affiché ; priorité lexicale en cas d’égalité, origine `both` si les témoins coïncident. Les deux témoins sont conservés pour l’évaluation. Les cartes historiques utilisent le même extrait textuel PostgreSQL que la phase 2, ou une ouverture explicitement signalée pour les métadonnées seules. Les offsets concernent le passage canonique entier, appliqués sur le serveur. Les passages ne deviennent jamais des articles historiques.

## Filtres, laboratoire et protection des publications

`2019` et `1789` n’interrogent que l’adaptateur choisi pendant la requête ; `tous` interroge les deux. Les filtres interviennent dans les requêtes avant la sélection des candidats. Pour éviter toute ambiguïté, le filtre question exige `2019` seul ; volume/ordre/lieu exigent `1789` seul. Toute combinaison incompatible, y compris avec `tous`, est refusée explicitement (422).

Le laboratoire compare les trois listes, affiche corpus, extraits, rangs, RRF et mesures. Le bouton H1 exécute séparément le moteur H1 inchangé à profondeur 50 : il s’agit d’une autre expérience, avec son propre encodage et son propre budget, et non d’un deuxième encodage dans la recherche multicorpus. Les réponses et cahiers possèdent leurs lecteurs locaux et leurs références de navigation futures. Aucune route de l’application publique n’est ajoutée.

Une recherche active au plus ; surplus refusé 409, sans file illimitée. Échéance 504 et indisponibilité 503 explicites, jamais une sélection partielle silencieusement présentée comme complète. L’écoute est limitée à 127.0.0.1, Host/Origin sont contrôlés et les accès API cross-site refusés. Les journaux HTTP n’exposent pas les requêtes ou textes. Les sorties brutes de benchmark restent privées et ignorées par Git.

Une limite effective de **quatre connexions** existe pour le rôle lecteur GDN. Des processus de laboratoire avec pools persistants pouvaient immobiliser cette capacité. La version livrée utilise donc `NullPool` dans son environnement local uniquement : connexion fermée au retour de chaque transaction, sans ALTER ROLE, GRANT ou changement du pool public. Les mesures finales ont été reprises avec ce réglage. Deux processus calculant simultanément peuvent toujours atteindre la limite : ne pas lancer plusieurs benchmarks/serveurs concurrents avec ce rôle et ne pas relever sa limite sans arbitrage.

## Intégrité et non-régression

La vérification complète de phase 2 a été rejouée en lecture : **1 305 notices, 1 267 documents, 11 391 passages**, textes/slices/empreintes conformes, **10 748 vecteurs** conformes et statistiques **90 943 lexèmes / 1 788 101 DF cumulées** cohérentes. Aucun embedding nouveau ni aucune réindexation n’a été nécessaire.

Artois conserve deux unités admissibles (passages 1 et 2), les passages 3 et 4 restent exclus avant les deux branches et ne peuvent fournir de témoin. Aunay conserve ses huit passages, son titre de présentation validé et son avertissement. Les 43 autres documents restent stockés mais hors du laboratoire de recherche/lecture courant ; les notices sans texte restent au manifeste.

La release documentaire reste `verified`, `publication_authorized=false`, `active_release_id=NULL`, **zéro document publiquement autorisé**. Les drapeaux de préparation de phase 2 restent distincts d’une autorisation publique. Les identités et permissions accompagnent les résultats. La validation d’un index GDN local n’est pas traitée comme une autorisation de déploiement.

Les tests écrivent uniquement dans des clusters temporaires créés pour eux. Le lecteur des vraies bases est READ ONLY, sans méthode de migration/import. Les fichiers sous `rag/`, `app/` et `frontend/`, la recette H1, ses statistiques/index/embeddings, les sources historiques et les décisions éditoriales n’ont pas été modifiés. Les fingerprints de génération GDN restent ceux de l’index existant ; aucun rescan cryptographique des 5,17 millions d’unités n’a été lancé pour prétendre prouver leur immobilité.

## Tests et mesures finales

**70 tests réussis**, trois avertissements existants (dépréciation Starlette/httpx et deux IDs OpenAPI SEO dupliqués). La suite couvre les phases 1/2, le contrat H1 existant et les nouvelles garanties multicorpus : IDF cumulée, un seul encodage, absence de quotas, identités distinctes, groupement SQL par réponse avant LIMIT, filtres incompatibles refusés, sécurité Host/Origin/cross-site et absence de route publique.

Le smoke Chromium réel vérifie les deux corpus, la lecture du passage historique et d’une réponse, la comparaison H1, zéro résultat lexical, le refus de filtre incompatible et l’affichage 375/1 280 pixels. Zéro erreur JavaScript. Les résultats restent exploratoires, sans annotations humaines de vérité terrain.

### Matrice de latence

**108 recherches réussies sur 108** : deux requêtes (`Gabelle`, `impôt`), deux répétitions, trois corpus, trois modes, trois profondeurs. Quatre observations par ligne : p50 médiane, p95 égal au maximum de ce petit échantillon. Temps muraux à l’appel du moteur, en millisecondes, hors HTTP/JSON/navigateur. Modèle et pages OS déjà utilisés ; aucun cache disque n’a été purgé. Une partie des validations automatisées sur d’autres clusters a eu lieu pendant la campagne : ces observations locales ne sont pas un benchmark de machine dédiée ni un SLO public.

| Corpus | Mode | D | p50 ms | p95 ms | min–max ms |
|---|---|---:|---:|---:|---:|
| 2019 | lexical | 50 | 419.6 | 726.9 | 116.7–726.9 |
| 2019 | lexical | 100 | 422.5 | 750.5 | 116.9–750.5 |
| 2019 | lexical | 200 | 429.3 | 741.8 | 118.1–741.8 |
| 2019 | vector | 50 | 250.0 | 251.3 | 235.1–251.3 |
| 2019 | vector | 100 | 250.1 | 256.9 | 240.4–256.9 |
| 2019 | vector | 200 | 260.7 | 263.8 | 241.3–263.8 |
| 2019 | hybrid | 50 | 554.4 | 855.7 | 261.1–855.7 |
| 2019 | hybrid | 100 | 564.0 | 853.4 | 269.7–853.4 |
| 2019 | hybrid | 200 | 584.9 | 884.2 | 274.2–884.2 |
| 1789 | lexical | 50 | 111.7 | 118.1 | 108.1–118.1 |
| 1789 | lexical | 100 | 116.5 | 218.5 | 106.3–218.5 |
| 1789 | lexical | 200 | 118.0 | 124.7 | 107.8–124.7 |
| 1789 | vector | 50 | 189.1 | 314.8 | 178.0–314.8 |
| 1789 | vector | 100 | 194.4 | 337.4 | 192.1–337.4 |
| 1789 | vector | 200 | 193.3 | 339.3 | 188.2–339.3 |
| 1789 | hybrid | 50 | 237.6 | 342.3 | 229.9–342.3 |
| 1789 | hybrid | 100 | 242.3 | 376.1 | 218.5–376.1 |
| 1789 | hybrid | 200 | 243.4 | 370.3 | 225.2–370.3 |
| tous | lexical | 50 | 507.9 | 835.9 | 183.1–835.9 |
| tous | lexical | 100 | 503.7 | 821.4 | 183.3–821.4 |
| tous | lexical | 200 | 512.8 | 848.4 | 185.8–848.4 |
| tous | vector | 50 | 353.6 | 496.9 | 346.4–496.9 |
| tous | vector | 100 | 361.0 | 503.7 | 338.0–503.7 |
| tous | vector | 200 | 348.9 | 498.5 | 333.1–498.5 |
| tous | hybrid | 50 | 792.0 | 1023.4 | 405.2–1023.4 |
| tous | hybrid | 100 | 795.1 | 1074.0 | 428.0–1074.0 |
| tous | hybrid | 200 | 796.5 | 1031.1 | 422.5–1031.1 |

Les durées individuelles séparent validation, encodage, statistiques, lexical GDN, lexical 1789, vectoriel GDN, vectoriel 1789, tri global, RRF, hydratation et total. Le regroupement Python documentaire est fourni dans les diagnostics ; le regroupement GDN est inclus dans son SQL, dont les nœuds Sort/Unique sont détaillés par EXPLAIN. On ne prétend pas fournir un temps exclusif de regroupement SQL que PostgreSQL n’a pas mesuré séparément.

Exemple mesuré « Gabelle », mode tous/compare, D=50 (les calculs des deux branches sont ceux de l’hybride) :

| Étape | ms |
|---|---:|
| validation | 38.12 |
| encoding | 47.00 |
| statistics | 27.61 |
| lexical_1789 | 30.96 |
| vector_1789 | 148.30 |
| lexical_2019 | 15.97 |
| vector_2019 | 88.21 |
| global_sort | 0.17 |
| fusion | 0.49 |
| hydration | 91.03 |
| total | 488.89 |

### Plans réels et termes fréquents

Les plans JSON privés contiennent les véritables requêtes et paramètres de recette. L’EXPLAIN vectoriel GDN réapplique explicitement les mêmes paramètres HNSW que le moteur ; le défaut PostgreSQL ef40 ne sert pas à mesurer ef1000.

| Plan | Temps EXPLAIN ANALYZE ms | Structure principale |
|---|---:|---|
| 2019_lexical | 3.27 | GIN/scan lexical → tri score par réponse → Unique → tri documentaire → limite |
| 2019_vector | 76.89 | Index Scan segments_full_hnsw → jointure → maximum par réponse → limite |
| 2019_frequent_actual | 641.95 | GIN/scan lexical → tri score par réponse → Unique → tri documentaire → limite |
| 1789_lexical | 27.15 | Parcours des unités admissibles, Hash Join des cahiers ; regroupement Python séparé |
| 1789_vector | 34.39 | Parcours des unités admissibles, Hash Join des cahiers ; regroupement Python séparé |
| 1789_frequent_actual | 39.38 | Parcours des unités admissibles, Hash Join des cahiers ; regroupement Python séparé |

Aucun préfiltrage lexical approximatif et aucun nouvel index. Le plan du terme fréquent permet d’observer le coût du score et du tri avant la déduplication des réponses. Les essais supplémentaires très fréquents sont :

| Requête | Corpus | Temps moteur à l’appel ms | État |
|---|---|---:|---|
| France | 2019 | 1488.9 | réussi |
| France | tous | 946.0 | réussi |
| faire | 2019 | 988.3 | réussi |
| faire | tous | 1104.7 | réussi |

Les filtres volume+ordre, lieu documentaire et question GDN ont également abouti. Les quatre recherches soumises simultanément à **une instance** ont produit une recherche complète et trois refus immédiats `search_busy`, conformément à l’admission choisie. Ce n’est pas une mesure de quatre inférences parallèles. Il n’y a pas eu de dépassement du budget de référence dans cette campagne ; cela ne démontre pas que toute formulation libre passera sous dix secondes de SQL.

### Comparaisons H1 / nouveau GDN / multicorpus

**22 requêtes × trois configurations**, toutes réussies. A : implémentation H1 actuelle, profondeur 50 et son unité historique ; B : nouveau moteur GDN seul, réponse comme document ; C : nouveau moteur multicorpus. H1 est exécuté dans l’environnement local lecteur de laboratoire (connexions non persistantes) : sa recette est celle de production, sa latence n’est pas un benchmark du serveur public.

Le tableau compare les **identités de réponses**, pas seulement les unités. `A uniques` est le nombre de réponses représentées dans les 50 unités H1 ; `A ∩ B` le nombre de réponses communes avec les 50 réponses du nouveau moteur. Un chevauchement n’est pas un score de pertinence. Les comptes historiques décrivent l’observation, sans objectif de répartition ni jugement automatique.

| Requête | A uniques | A ∩ B | Cahiers dans C top10 | Cahiers dans C top50 | Temps C ms |
|---|---:|---:|---:|---:|---:|
| Suppression des privilèges | 50 | 49 | 0 | 0 | 622.0 |
| Justice | 50 | 50 | 0 | 0 | 654.6 |
| Fiscalité | 50 | 50 | 0 | 0 | 730.0 |
| Représentation des citoyens | 50 | 35 | 0 | 0 | 1301.4 |
| Éducation | 50 | 50 | 5 | 10 | 322.6 |
| Agriculture | 50 | 50 | 0 | 1 | 668.8 |
| Liberté d'expression | 50 | 50 | 1 | 7 | 644.5 |
| Inégalités sociales | 50 | 50 | 0 | 0 | 1005.4 |
| Gabelle | 50 | 49 | 5 | 25 | 488.9 |
| Justice seigneuriale | 50 | 50 | 10 | 48 | 585.2 |
| Corvées | 50 | 50 | 5 | 25 | 343.5 |
| États généraux | 50 | 50 | 10 | 50 | 730.7 |
| Abolition des corporations | 50 | 50 | 2 | 13 | 454.2 |
| Transition écologique | 50 | 50 | 0 | 0 | 832.2 |
| Pouvoir d'achat | 50 | 50 | 0 | 0 | 977.8 |
| Services publics | 50 | 50 | 0 | 0 | 1318.6 |
| Fiscalité écologique | 50 | 50 | 0 | 0 | 1026.1 |
| Agen | 50 | 50 | 0 | 0 | 319.0 |
| Agen agriculture | 50 | 50 | 2 | 4 | 587.0 |
| impôt | 50 | 50 | 0 | 0 | 1149.6 |
| zxqv1789inexistant | 50 | 50 | 0 | 0 | 321.2 |
| jurandes | 50 | 50 | 10 | 50 | 330.7 |

## Pertinence observée et limites avant interface publique

- **Absence de quotas effective** : « États généraux » et « jurandes » donnent une sélection historique, plusieurs formulations contemporaines une sélection GDN. Cette répartition n’est pas forcée et n’est pas un objectif à optimiser.
- **Géographie délicate** : « Agen » n’affiche aucun cahier dans le top50 multicorpus observé, bien que le mode 1789 et le filtre documentaire le retrouvent. L’analyse française rapproche `Agen` d’`agens`, et les métadonnées ne sont pas présentes dans le vectoriel. Il faut examiner la qualité des réponses complètes et des correspondances lexicales ; la simple présence d’un lieu ne garantit pas une intention géographique correctement comprise.
- **Écarts avec H1** : « Représentation des citoyens » montre un changement notable de la sélection GDN. Le regroupement préalable par réponse et les règles d’analyse libre peuvent changer des rangs ; l’écart n’est pas automatiquement une régression. Les unités autres de la même réponse doivent être jugées ensemble.
- **Pas d’abstention calibrée** : le terme sans correspondance lexicale renvoie toujours des voisins vectoriels et des résultats hybrides. Leur présence n’atteste pas la pertinence. Aucun seuil de confiance n’a été inventé pour masquer ce cas.
- **Témoins historiques** : l’extrait vient du meilleur passage de branche, avec la règle déterministe commune et les deux témoins conservés. Pour « Justice seigneuriale », les premiers cahiers comprennent Chelles et Mirabeau ; pour « Gabelle », Amponville et Bouzonville figurent parmi les premiers historiques. Ces observations servent de points d’entrée à une lecture humaine, pas de validation documentaire automatisée.
- **Comparabilité vectorielle** : une question contextualisant une réponse GDN et un passage historique seul ne produisent pas exactement les mêmes distributions de similarité. Le classement les compare directement, comme demandé ; il faudra juger les exemples transversaux avant toute calibration. Aucun rang vectoriel local n’a été artificiellement privilégié.
- **Fenêtre bornée** : top50 final, deux branches à D 50/100/200. La collecte GDN reste ANN, avec limites de parcours et de segments explicites. Un petit filtre ne garantit pas le rappel d’un HNSW ; les cas restrictifs et les plafonds doivent rester visibles.
- **Validation de charge limitée** : une seule recherche active et refus du surplus ; quatre demandes ne valident pas la capacité publique. Les budgets, rôles, annulations et contraintes de connexion devront être confrontés à l’environnement de déploiement avant la phase 4. Aucun nouveau service permanent ni relèvement de budget n’est proposé sur la seule base de cette campagne.

Les coefficients initiaux, β, RRF60 et les recettes existantes n’ont pas été modifiés à partir des exemples. Aucune nouvelle campagne d’optimisation de la phase 2 n’a été engagée.

## Livrables, retour arrière et suites

Les sources du laboratoire sont dans `multicorpus/`, les tests dans `tests/test_multicorpus.py`, le lancement dans [README](../../multicorpus/README.md). Les sorties détaillées sont ignorées par Git : `private/search/phase3/results-final.json`, `documentary-integrity.json`, `tests-final.log`, `browser.json`. Les premières mesures exploratoires restent distinctes dans `results.json` ; elles précèdent le passage aux connexions non persistantes et ne sont pas mélangées aux chiffres finaux. Les traces comportent les identités et permissions de chaque sélection ; aucun journal historique privé n’est servi.

Le retour arrière consiste à arrêter le processus de laboratoire. H1 public reste disponible sans bascule, migration inverse ou restauration de données. Aucune migration, représentation, statistique, transcription ou décision éditoriale n’a été écrite dans les bases de travail pendant cette phase ; seules les fixtures des tests ont créé des données dans leurs nouveaux clusters privés.

Avant phase 4 : validation humaine des réponses complètes et extraits sur un jeu plus large, examen des cas géographiques et sans signal lexical, choix explicite de la politique de publication historique et contrôle de charge dans l’environnement cible. L’intégration publique, ses curseurs et sa navigation ne sont pas implémentés ici. La qualité technique observée permet d’essayer le multicorpus ; elle n’autorise pas implicitement la publication.
