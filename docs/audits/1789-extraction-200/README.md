# Découverte et extraction de 200 fiches documentaires de 1789

Étude du 26 octobre 2026. Source principale : les six volumes Stanford, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`. Aucun accès SQL, embedding, service ou changement applicatif.

**Le registre contient 200 fiches, pas 200 cahiers certifiés : 30 parents hérités, 6 nouveaux documents examinés et retenus, 153 nouvelles hypothèses non certifiées, et 11 faux parents mis en quarantaine.** Les 170 nouvelles fiches ont été sélectionnées parmi des découvertes automatiques, sans choix manuel de leurs titres. Aucun échec n'a été remplacé pour atteindre le nombre cible.

La difficulté principale mesurée est la découverte des **parents**, davantage que la segmentation des articles dans les fenêtres contrôlées. Sur 12 candidats nouveaux évalués, 6 sont retenus comme cahiers ou sous-documents revendicatifs ; 5 de leurs 6 frontières sont correctes automatiquement. Sur 48 articles de référence, 46 sont proposés avec les deux limites exactes avant correction. Ces petits lots ne permettent pas d'annoncer une précision ou un rappel sur les six volumes.

## Livrables

| Document ou données | Contenu |
|---|---|
| [Évaluation](EVALUATION.md) | Mesures, dénominateurs, avant/après, limites de l'annotation |
| [Galerie](PROBLEMS.md) | Faux parents, cahiers manqués, fusions, fragments, OCR et contaminations |
| [Généralisation](GENERALIZATION.md) | Conditions d'une prochaine itération, sans intégration |
| [Données et reproduction](DATA.md) | Scripts, statuts, positions, versions et commandes |
| [Inventaire](data/candidates.jsonl), [résumé](data/inventory-summary.json) | Tous les signaux, y compris mentions, rejets, extraits et continuations |
| [Sélection](data/selection.jsonl), [protocole](protocol.json), [gel](freeze.json) | Les 170 ajouts, leurs strates et les identifiants de validation |
| [Registre](data/register.json) | Les 200 fiches avec statuts, frontières, pages, sections et incertitudes |
| [Parents](data/documents.jsonl.gz) | Textes intégraux et structure ; filtrer les fiches en quarantaine |
| [Unités A](data/units-A.jsonl), [unités B](data/units-B.jsonl.gz), [plages C](data/retained-C.jsonl.gz) | Fichiers séparés pour éviter de confondre vérification et proposition |
| [Prédictions initiales](data/automatic-units.jsonl), [parents initiaux](data/automatic-parents.jsonl.gz) | Résultats avant corrections documentaires |
| [Référence](data/reference-documents.jsonl), [zones non détectées](data/reference-negative.json) | Annotations source conservées et gelées avant les prédictions d'articles |
| [Correspondances](data/crosswalk.json), [journal](data/review-log.json) | Identifiants anciens, corrections et décisions |
| [Contrôles](data/checks.json), [reproductibilité](data/reproducibility.json) | Fidélité, conservation du texte, erreurs injectées, identité de deux exécutions |

## 1. Réutilisation et sources

Les rapports et outils des audits [multicorpus](../1789-multicorpus/README.md), [comparaison des sources](../1789-sources-comparison/README.md), [pilote](../1789-extraction-pilot/README.md), [recherche sémantique](../1789-semantic-search/README.md), [passage à l'échelle](../multicorpus-scale-study/README.md) et [Pecqueuse](../1789-pecqueuse-comparison/README.md) servent de contexte et de contrôles. Les six XML présents dans `/tmp/cahier-1789-extraction-pilot/sources/` sont vérifiés contre les empreintes du premier inventaire. Aucun téléchargement de corpus ou collecte Persée n'est effectué.

Les primitives `Source` du pilote sont réutilisées en lecture : positions Unicode du texte XML décodé, XPath, pagination et empreintes. Les règles du précédent segmenteur sont reprises dans `pilot_segment.py`, puis adaptées dans `rules.py` avant validation. Les 30 parents et 759 unités du pilote conservent leurs identifiants, textes et informations antérieures. Les 269 A hérités ne sont pas présentés comme nouvellement vérifiés.

Les 30 cahiers du pilote et **Pecqueuse** sont du développement. Pecqueuse est découvert automatiquement, mais exclu du nouveau tirage et évalué comme régression supplémentaire : 38 articles, dont l'article 37 sur deux paragraphes. Il n'est ni un 201e parent du registre ni une preuve de généralisation.

## 2. Découverte avant sélection

L'inventaire parcourt les divisions de tous niveaux possédant des titres ou paragraphes, les formules d'ouverture et les titres internes balisés en `p`. Il examine les mots documentaires, les mentions d'ordres et le voisinage ; il ne se limite pas à `div3`. Les propositions de regroupement utilisent les continuations sœurs ; les titres internes peuvent couper une division en plusieurs hypothèses.

Résultat **avant tout tirage** : **4 448 signaux**, dont **1 278 hypothèses de documents**, 3 078 mentions dans le corps et 92 autres signaux classés en continuation, document joint, extrait, notice d'absence ou cas incertain. Ces nombres ne sont pas un inventaire validé des vrais cahiers. Les 7 notices d'absence reconnues ne couvrent pas toutes les formulations possibles : deux autres ont échappé au filtre dans la validation.

| Volume | Hypothèses de documents détectées | Nouveaux candidats sélectionnés | Parents hérités |
|---:|---:|---:|---:|
| I | 31 | 26 | 5 |
| II | 187 | 29 | 5 |
| III | 212 | 29 | 5 |
| IV | 356 | 29 | 6 |
| V | 299 | 29 | 4 |
| VI | 193 | 28 | 5 |

Les types de classement et leurs signaux constituent les raisons automatiques de proposition ou d'exclusion. Les rejets restent dans l'inventaire. Les classifications documentaires revues sont séparées : elles n'écrasent pas la prédiction initiale.

## 3. Sélection et séparation du développement

Le cadre exclut tout chevauchement avec les 30 anciens parents ainsi que Pecqueuse. La sélection répartit les places entre volumes, terciles de longueur, mentions littérales d'ordres et structures ordinaires/composites/internes. Dans chaque cellule, l'ordre est fixé par SHA-256 de `selection-1789-200-v1|identifiant` ; un tour de cellules fournit les quotas. Le volume I n'a que 26 candidats admissibles après exclusions, d'où la redistribution des places restantes.

Cette stratification favorise la diversité, **pas la représentativité statistique**. Une mention de « clergé » ou « noblesse » dans une ouverture ne prouve pas l'ordre de l'auteur : elle sert au tirage, et reste une `estate_mention` non certifiée dans les nouvelles métadonnées. Les dates/localités ne sont pas fabriquées ; leur texte reste accessible même sans extraction structurée.

Le lot de validation prend deux candidats par volume : un court et un long ou structurellement difficile, selon le même principe déterministe. Les règles, l'inventaire, la sélection et douze fenêtres non couvertes sont gelés dans `freeze.json`. La référence est ensuite écrite et gelée dans `reference-freeze.json`, **avant** la production des nouvelles prédictions d'articles.

Codex a lu les titres, débuts, clôtures et voisins pour les parents ; les articles sont examinés dans des fenêtres source explicites. L'annotateur connaît les candidats et les difficultés du développement : il ne s'agit ni d'une annotation humaine indépendante ni d'un test aveugle. Les débuts/fins ont été examinés ; les longs corps n'ont pas tous été collationnés intégralement. Aucune nouvelle collation sur image n'est revendiquée pour ces douze candidats ; A certifie les limites dans le TEI, pas l'OCR ou le manuscrit.

## 4. Reconstruction et statuts

Chaque parent conserve son texte exact, y compris notes, titres, signatures et pièces de rôle incertain. La structure est repérée par des blocs et annotations ; elle n'est pas une réécriture du texte. Les pièces regroupées sont qualifiées de continuations ou d'annexes hypothétiques, avec une décision explicite lorsque la référence les examine.

Une correction documentaire est appliquée dans le nouveau lot : les doléances des médecins d'Arles doivent s'arrêter avant celles des procureurs. Les sections de Montargis et de Claye, deux notices d'absence et sept résumés hors 1789 sont mis en quarantaine. Les cinq résumés supplémentaires ont été repérés lors d'un contrôle postérieur des titres du volume I ; ils ne sont pas ajoutés aux mesures du lot gelé. Les textes et prédictions initiaux restent disponibles, et aucune règle n'a été retouchée à partir de ces résultats.

| État final | Nombre | Interprétation |
|---|---:|---|
| Parents du pilote | 30 | Frontières revues antérieurement |
| Nouveaux parents examinés et retenus | 6 | Dont un sous-document professionnel annexé à Arles ; cinq frontières correctes avant correction |
| Nouveaux parents proposés sans certification | 153 | Hypothèses de cahiers ; pas 153 vrais cahiers validés |
| Faux parents conservés en quarantaine | 11 | Exclus de l'usage comme cahiers de 1789 |
| Unités A | **317** | 269 héritées + **48 nouvelles** limites examinées |
| Unités B | **5 872** | Propositions non certifiées individuellement |
| Plages C | **812** | Texte conservé sans prétendre à autant d'articles |

Les 170 ajouts produisent 5 445 propositions initiales d'articles. Après décisions, ils apportent 5 430 unités A/B ; avec les 759 anciennes, le total est **6 189**. Les A représentent 5,12 % des unités finales ; les 48 nouveaux A représentent 0,88 % des nouvelles unités. Leur couverture non blanche est de 1,64 % du texte des parents hors quarantaine, titres et annexes compris. Cette couverture faible traduit le contrôle partiel, pas un taux d'extractibilité automatique.

## 5. Mesures et portée

Le lot de découverte contrôlé contient 6 vrais documents retenus et 6 faux parents : **50 % de précision dans ce lot intentionnellement contrasté**, sans extrapolation. Parmi les 6 vrais documents, 5 ont des frontières conformes avant correction. Le contrôle des zones non couvertes révèle trois cahiers formels manqués et un procès-verbal contenant des doléances perdues par le filtre. Une autre pièce professionnelle reste ambiguë. Aucun rappel global n'est calculé.

Dans les fenêtres des six documents retenus : **48 articles attendus, 46 proposés, 46 avec début et fin exacts**. Les deux autres débuts sont `ArtIer.` à La Rochelle et `Àri. er.` à Vernouillet. La précision conditionnelle est 46/46 et le rappel 46/48 ; cela ne signifie pas que les milliers de B sont exacts. Les 11 propositions provenant des six faux parents de validation sont comptées séparément comme erreurs d'association documentaire.

Le calcul ne sélectionne pas seulement les sorties réussies : les deux articles manqués sont dans la référence, Rognac fournit une fenêtre entière sans article numéroté, et les faux parents restent dans les dénominateurs de découverte. Après remplacement des seules fenêtres revues par leurs références, les 48 articles portent A ; annoncer alors une précision de 100 % serait tautologique. [Détail des mesures](EVALUATION.md).

La régression de développement retrouve les 30 débuts et les mêmes étendues non blanches des anciens parents. Sur les 37 anciennes fenêtres, 250 des 269 unités de référence ont leurs limites exactes avec les nouvelles règles. Ces résultats restent du développement et ne sont pas mêlés aux 48 unités nouvelles.

## 6. Contrôles et effort

Les contrôles vérifient la reconstruction des parents, tous les textes A/B/C, leurs positions, le bon rattachement, l'ordre, les voisins, les identifiants et les références XML. Chaque caractère non blanc des nouveaux parents est conservé entre A/B et C. Aucun chevauchement de parents hors quarantaine n'est constaté. Six erreurs injectées sont rejetées. Les 30 anciens parents et 759 unités gardent leurs références ; **314 fichiers des audits antérieurs sont inchangés**.

Deux exécutions produisent les mêmes fichiers de corpus, hors durées/horodatages. Le dernier traitement complet prend environ cinq secondes et environ 395 Mio de RSS maximal dans cet environnement ; voir les mesures exactes et empreintes dans [reproducibility.json](data/reproducibility.json). Deux essais préliminaires ont été interrompus en raison d'un parcours quadratique des frères XML. Une mise en cache équivalente, contrôlée sur les douze candidats de validation, corrige ce coût sans changer les règles gelées.

Le journal dénombre 17 nouveaux candidats examinés — 12 de validation et 5 rejets chronologiques supplémentaires —, une correction de frontière de parent, 48 nouvelles unités contrôlées et 12 fenêtres non couvertes, totalisant 68 paragraphes source. Les horodatages sont ceux du travail Codex ; **aucun temps humain n'est mesuré et aucun validateur humain indépendant n'est intervenu**. Il n'est pas possible d'en déduire honnêtement des minutes ou euros par cahier.

## 7. Réponses finales

**Q1. Candidats détectés ?** 1 278 propositions de documents, parmi 4 448 signaux conservés dans les six volumes. Ni ce nombre ni les occurrences du mot « cahier » ne constituent un compte de vrais cahiers de 1789.

**Q2. Vrais cahiers reconstitués dans le nouveau lot ?** Six documents nouveaux ont été examinés et retenus, dont les doléances professionnelles jointes à Arles. Les 153 autres fiches hors quarantaine restent proposées. Le corpus compte 36 parents revus en incluant les 30 anciens, pas 189 ou 200 parents certifiés.

**Q3. Fiabilité de découverte ?** 6/12 candidats nouveaux retenus dans le contrôle stratifié ; 5/6 frontières exactes parmi les retenus. C'est un signal d'insuffisance du détecteur, pas une estimation nationale. Aucun rappel global défendable.

**Q4. Faux positifs et manqués ?** Contexte chronologique ignoré, notices d'absence formulées autrement, rubriques prises pour des débuts ; à l'inverse, « Mandats », titres OCR dégradés, titres en `p[1]` et doléances dans un procès-verbal sont manqués.

**Q5. Articles extraits ?** 5 445 propositions nouvelles initiales ; 5 430 nouvelles unités après décisions ; 6 189 A/B au total. Les 812 plages C ne sont pas des articles supplémentaires.

**Q6. Proportion vérifiée ?** 317/6 189 unités finales (5,12 %), dont 48 nouvelles et 269 héritées. A signifie limites examinées dans le XML, sans certification historique indépendante.

**Q7. Articles évalués correctement extraits ?** 46/48 articles attendus dans les nouvelles fenêtres, soit 95,83 % de rappel ; les 46 propositions ont les deux limites exactes. Cette mesure est conditionnelle aux vrais parents et aux fenêtres choisies avant prédiction.

**Q8. Documents difficiles ?** Dossiers de plusieurs cahiers dans une division, sections ressemblant à des documents, annexes, prose non numérotée, titres atypiques ou corrompus, citations et notices éditoriales.

**Q9. Travail restant ?** Les 153 nouveaux parents non certifiés et 5 872 B demandent un contrôle adapté ; les 11 rejets et les cas manqués orientent une nouvelle itération. Une charge horaire n'est pas établie. Prioriser les frontières des parents plutôt qu'une validation aveugle de chaque B.

**Q10. Plusieurs milliers de cahiers ?** Oui pour produire des hypothèses traçables, non pour fabriquer un corpus validé automatiquement. L'évaluation démontre des erreurs de découverte qui doivent être corrigées avant une extraction systématique utilisée comme référence.

**Q11. Quelles validations maintenir ?** Chronologie, autonomie du document, limites de regroupement, pièces jointes, titres internes, marqueurs illisibles et distinction entre clôture et corps. Une numérotation régulière n'autorise pas le statut A.

**Q12. Prochaine étape ?** Ouvrir explicitement une version 2 sur les erreurs de cette étude, puis un nouveau lot de validation jamais utilisé pour régler les règles, avec une référence de zones continues et un contrôle humain indépendant chronométré. Aucune intégration applicative avant ce contrôle. [Proposition détaillée, non commencée](GENERALIZATION.md).
