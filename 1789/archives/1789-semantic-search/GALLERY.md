# Galerie de résultats réels

Jugements exploratoires Codex, non indépendants. Blancs réduits uniquement dans cette galerie ; textes exacts dans [le corpus](data/corpus.jsonl) et [les résultats détaillés](data/results.jsonl). Chaque rang se rapporte à la population indiquée ; « >50 / absent » ne distingue pas rang inférieur et absence de correspondance lexicale. Les scores sont des cosinus, BM25 ou RRF, pas des probabilités.

## 1. réussite — Comment répartir plus équitablement la fiscalité ?

Habitants d’Albertas · Art. 2. · note **3/3**.

> Art. 2. Une égale répartition dans la taxe des impôts. Cette taxe doit être proportionnée aux besoins de l'Etat, y compris la dette nationale qui doit être reconnue et consolidée.

La répartition équitable retrouve « égale répartition dans la taxe des impôts ». Le terme fiscalité n'est pas nécessaire. Aucun résultat lexical dans les50 conservés.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 2 | 0.598877 |
| historical | vector_B | 1 | 0.553076 |
| historical | hybrid_A | 17 | 0.016129 |
| historical | hybrid_B | 18 | 0.016393 |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | 13 | 0.598877 |
| mixed | vector_B | 21 | 0.553076 |
| mixed | hybrid_A | 27 | 0.013699 |
| mixed | hybrid_B | 38 | 0.012346 |

Référence : AP, tome6, p.237. [Volume numérisé](https://purl.stanford.edu/wg983ft3682). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml). Identifiant `ap1789-pilot-u1:c33d108ba660e47d2e75:86dc54259152040e`, parent `ap1789-pilot-d1:wg983ft3682:c33d108ba660e47d2e75`, ancre `unit-86dc54259152040e`.

## 2. réussite — Les citoyens doivent-ils contrôler les dépenses publiques ?

Noblesse du Beaujolais · Art. 9. · note **3/3**.

> Art. 9. Que les ministres soient comptables aux Etats généraux et responsables de leur conduite en tout ce qui sera relatif aux lois du royaume finances et administration.

Les ministres comptables aux États généraux répondent à la préoccupation de contrôle des finances. Ce contrôle représentatif historique n'est pas identique à un contrôle direct par tous les citoyens.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 9 | 0.491187 |
| historical | vector_B | 23 | 0.434003 |
| historical | hybrid_A | 24 | 0.014493 |
| historical | hybrid_B | 41 | 0.012048 |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | >50 / absent | — |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | >50 / absent | — |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome2, p.281, 282. [Volume numérisé](https://purl.stanford.edu/fz023dp4399). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml). Identifiant `ap1789-pilot-u1:3e6a4db201abec55cb3e:5b1bcf263ad9c50b`, parent `ap1789-pilot-d1:fz023dp4399:3e6a4db201abec55cb3e`, ancre `unit-5b1bcf263ad9c50b`.

## 3. réussite — Comment rendre la justice moins coûteuse pour les justiciables ?

Ermenonville / Arnouville · Art. 11. · note **3/3**.

> Art. 11. Abrégé des frais de procédure.

« Abrégé des frais de procédure » répond au coût de la justice sans contenir justice ou justiciables. C'est un gain vectoriel concret hors des50 résultats lexicaux.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 10 | 0.487438 |
| historical | vector_B | >50 / absent | — |
| historical | hybrid_A | 20 | 0.014286 |
| historical | hybrid_B | >50 / absent | — |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | 15 | 0.487438 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 29 | 0.013333 |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome4, p.316. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:2d9eb8a19442dcf619d3:ab2670417201247c`, parent `ap1789-pilot-d1:xg914wh0253:2d9eb8a19442dcf619d3`, ancre `unit-ab2670417201247c`.

## 4. réussite — Comment protéger la liberté d'expression ?

Tiers état de Ferrières en Brie · Art. 12. · note **3/3**.

> Art. 12. Que la liberté de* la presse soit aussi peu gênée que celle de la parole.

Liberté de la presse et de la parole : correspondance forte. Le lexical trouve aussi cet article, au6e rang ; le vectoriel le promeut en tête.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 6 | 3.988074 |
| historical | vector_A | 1 | 0.585643 |
| historical | vector_B | 1 | 0.543524 |
| historical | hybrid_A | 1 | 0.031545 |
| historical | hybrid_B | 1 | 0.031545 |
| mixed | lexical | 8 | 4.586726 |
| mixed | vector_A | 1 | 0.585643 |
| mixed | vector_B | 1 | 0.543524 |
| mixed | hybrid_A | 2 | 0.031099 |
| mixed | hybrid_B | 1 | 0.031099 |

Référence : AP, tome4, p.546. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:4133d7972888544d97cb:aac52165de4e92db`, parent `ap1789-pilot-d1:xg914wh0253:4133d7972888544d97cb`, ancre `unit-aac52165de4e92db`.

## 5. réussite — Comment limiter les abus de pouvoir ?

Clergé d’Agenois · Art. 5. · note **3/3**.

> Art. 5. L'abolition entière des lettres de cachet et de tout acte de pouvoir arbitraire, et qu'aucun ci- toyen qui sera arrêté ne pourra être détenu que le temps nécessaire pour être remis à ses juges naturels.

Limitation du pouvoir arbitraire par abolition des lettres de cachet et remise au juge. Le contexte B retrouve cette garantie au4e rang historique, contre une récupération A moins favorable.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 13 | 3.370537 |
| historical | vector_A | 18 | 0.482276 |
| historical | vector_B | 4 | 0.480105 |
| historical | hybrid_A | 6 | 0.026519 |
| historical | hybrid_B | 3 | 0.029324 |
| mixed | lexical | 29 | 3.159637 |
| mixed | vector_A | 38 | 0.482276 |
| mixed | vector_B | 24 | 0.480105 |
| mixed | hybrid_A | 10 | 0.021440 |
| mixed | hybrid_B | 8 | 0.023141 |

Référence : AP, tome1, p.pagination absente, vue jt959wc5586_00_0675. [Volume numérisé](https://purl.stanford.edu/jt959wc5586). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/jt959wc5586/jt959wc5586.xml). Identifiant `ap1789-pilot-u1:64bb7420785d8cb8ea4b:afc371ef1020507f`, parent `ap1789-pilot-d1:jt959wc5586:64bb7420785d8cb8ea4b`, ancre `unit-afc371ef1020507f`.

## 6. réussite — Les représentants doivent-ils rendre des comptes aux citoyens ?

Noblesse de Mirecourt · 7° · note **3/3**.

> 7° Que les ministres doivent être comptables à la nation de leur administration.

Rendre des comptes / être comptable de son administration : lien solide. Des ministres historiques ne sont pas pour autant les mêmes acteurs que des élus contemporains.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 2 | 5.744288 |
| historical | vector_A | 1 | 0.587580 |
| historical | vector_B | 5 | 0.516118 |
| historical | hybrid_A | 1 | 0.032522 |
| historical | hybrid_B | 1 | 0.031514 |
| mixed | lexical | 6 | 5.863172 |
| mixed | vector_A | 4 | 0.587580 |
| mixed | vector_B | 30 | 0.516118 |
| mixed | hybrid_A | 1 | 0.030777 |
| mixed | hybrid_B | 8 | 0.026263 |

Référence : AP, tome4, p.2. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:b6a30344f86d9da9f1ea:4a836da916014603`, parent `ap1789-pilot-d1:xg914wh0253:b6a30344f86d9da9f1ea`, ancre `unit-4a836da916014603`.

## 7. partiel — Faut-il réduire les impôts ?

Ermenonville / Arnouville · Art. ler. · note **2/3**.

> Art. ler. Tous impôts réduits à un seul.

Réduire tous les impôts à un seul en change le nombre, pas nécessairement le montant. Premier résultat vectoriel A, mais note2 seulement ; aucune baisse globale ne doit être inférée.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 10 | 2.664708 |
| historical | vector_A | 1 | 0.605868 |
| historical | vector_B | 44 | 0.430655 |
| historical | hybrid_A | 1 | 0.030679 |
| historical | hybrid_B | 25 | 0.023901 |
| mixed | lexical | 32 | 3.025700 |
| mixed | vector_A | 12 | 0.605868 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 9 | 0.024758 |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome4, p.316. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:2d9eb8a19442dcf619d3:fd4887460eb7771f`, parent `ap1789-pilot-d1:xg914wh0253:2d9eb8a19442dcf619d3`, ancre `unit-fd4887460eb7771f`.

## 8. échec — Les États doivent-ils coopérer entre eux ?

Noblesse de Mirecourt · 3° · note **0/3**.

> 3° Que le retour périodique des Etats généraux doit être assuré.

États généraux et coopération entre États souverains sont deux objets différents. Similarité élevée sans pertinence utile : un cosinus n'est pas une probabilité.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 1 | 0.571333 |
| historical | vector_B | >50 / absent | — |
| historical | hybrid_A | 15 | 0.016393 |
| historical | hybrid_B | >50 / absent | — |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | 2 | 0.571333 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 16 | 0.016129 |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome4, p.1. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:b6a30344f86d9da9f1ea:88c2e94347f1a8a1`, parent `ap1789-pilot-d1:xg914wh0253:b6a30344f86d9da9f1ea`, ancre `unit-88c2e94347f1a8a1`.

## 9. échec — Comment limiter la taille des classes à l'école ?

Tiers état de Périgny-en-Brie · Art. 5. · note **0/3**.

> Art. 5. Nos terres sont de la première classe, et par la quantité de remises qui se trouve sur ledit terroir, cela les fait devenir à la dernière classe.

« Première classe » décrit des terres, pas un effectif scolaire. Le premier résultat lexical est trompeur ; les résultats vectoriels historiques ne trouvent pas davantage de réponse utile.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 1 | 6.392434 |
| historical | vector_A | 39 | 0.392591 |
| historical | vector_B | 46 | 0.352256 |
| historical | hybrid_A | 1 | 0.026494 |
| historical | hybrid_B | 2 | 0.025827 |
| mixed | lexical | 1 | 6.630003 |
| mixed | vector_A | >50 / absent | — |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 7 | 0.016393 |
| mixed | hybrid_B | 7 | 0.016393 |

Référence : AP, tome5, p.14. [Volume numérisé](https://purl.stanford.edu/xx284sn7328). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml). Identifiant `ap1789-pilot-u1:0e4e17a10525b854d367:99c8f66fd5ac8df6`, parent `ap1789-pilot-d1:xx284sn7328:0e4e17a10525b854d367`, ancre `unit-99c8f66fd5ac8df6`.

## 10. échec — Comment déployer la fibre optique dans les campagnes ?

Ermenonville / Arnouville · Art. 8. · note **0/3**.

> Art. 8. Prolongation des baux des biens de campagne.

Un bail de biens de campagne ne répond pas au déploiement de la fibre optique. Premier résultat vectoriel A et hybride A dans le sous-corpus historique.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 2 | 6.491646 |
| historical | vector_A | 1 | 0.456506 |
| historical | vector_B | 3 | 0.374514 |
| historical | hybrid_A | 1 | 0.032522 |
| historical | hybrid_B | 1 | 0.032002 |
| mixed | lexical | 3 | 6.650534 |
| mixed | vector_A | 6 | 0.456506 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 2 | 0.031025 |
| mixed | hybrid_B | 12 | 0.015873 |

Référence : AP, tome4, p.316. [Volume numérisé](https://purl.stanford.edu/xg914wh0253). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xg914wh0253/xg914wh0253.xml). Identifiant `ap1789-pilot-u1:2d9eb8a19442dcf619d3:4932b9d96cfbf913`, parent `ap1789-pilot-d1:xg914wh0253:2d9eb8a19442dcf619d3`, ancre `unit-4932b9d96cfbf913`.

## 11. échec — Comment lutter contre les cyberattaques ?

Clergé d’Anjou · 2° · note **0/3**.

> 2° Que l'incrédulité qui conduit à l'oubli de tous les devoirs soit réprimée, que les écrivains licencieux qui attaquent la religion et les mœurs soient poursuivis comme fléaux de la tranquillité publique.

Poursuivre des écrivains jugés irréligieux n'est pas lutter contre une cyberattaque. Le modèle retrouve une notion d'attaque/répression sans l'objet technique de la requête.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 22 | 0.737749 |
| historical | vector_A | 1 | 0.447382 |
| historical | vector_B | 2 | 0.383928 |
| historical | hybrid_A | 2 | 0.028589 |
| historical | hybrid_B | 2 | 0.028324 |
| mixed | lexical | 36 | 0.933168 |
| mixed | vector_A | 25 | 0.447382 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 5 | 0.022181 |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome2, p.30. [Volume numérisé](https://purl.stanford.edu/fz023dp4399). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/fz023dp4399/fz023dp4399.xml). Identifiant `ap1789-pilot-u1:b1c515d7e3ec55e7f988:1ba7c4990e0e3fca`, parent `ap1789-pilot-d1:fz023dp4399:b1c515d7e3ec55e7f988`, ancre `unit-1ba7c4990e0e3fca`.

## 12. partiel — Faut-il subventionner l'achat de voitures électriques ?

Habitants d’Albertas · Art. 8. · note **1/3**.

> Art. 8. L'assemblée désirerait, pour la facilité du commerce, et pour favoriser l'industrie d'une partie des habitants de la communauté qui est adonnée au roulage, qu'il fût permis aux rouliers de mettre çpiatre mulets ou chevaux à leurs voitures, ainsi qu'il est permis dans les autres provinces du royaume.

Les voitures sont ici attelées de mulets ou chevaux. Le lexical place ce passage en tête historique ; aucune propulsion électrique ni subvention n'existe dans ce texte.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | 1 | 5.197204 |
| historical | vector_A | 10 | 0.432888 |
| historical | vector_B | 14 | 0.403044 |
| historical | hybrid_A | 1 | 0.030679 |
| historical | hybrid_B | 1 | 0.029907 |
| mixed | lexical | 17 | 3.862992 |
| mixed | vector_A | >50 / absent | — |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | 32 | 0.012987 |
| mixed | hybrid_B | 32 | 0.012987 |

Référence : AP, tome6, p.237. [Volume numérisé](https://purl.stanford.edu/wg983ft3682). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml). Identifiant `ap1789-pilot-u1:c33d108ba660e47d2e75:2812c4ceb1368ee0`, parent `ap1789-pilot-d1:wg983ft3682:c33d108ba660e47d2e75`, ancre `unit-2812c4ceb1368ee0`.

## 13. manqué — Comment rapprocher les services publics des habitants ?

Clergé du bailliage de Vie [graphie TEI] · Art. 7. · note **3/3**.

> Art. 7. C'est le vœu de toute la province qu'il lui soit accordé des Etats provinciaux organisés dans la forme que Sa Majesté a prescrite pour les Etats généraux, avec des bureaux de district, pour rendre le recours à leur administration plus facile et moins dispendieux.

L'article pertinent sur des bureaux de district est présent mais reste14e en vectoriel A et36e en B. L'échec du top10 ne vient donc pas de l'absence documentaire.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 14 | 0.448204 |
| historical | vector_B | 36 | 0.404513 |
| historical | hybrid_A | 26 | 0.013514 |
| historical | hybrid_B | >50 / absent | — |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | >50 / absent | — |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | >50 / absent | — |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome6, p.16. [Volume numérisé](https://purl.stanford.edu/wg983ft3682). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml). Identifiant `ap1789-pilot-u1:72447fb17ff8b4b6f261:eacd20493def862f`, parent `ap1789-pilot-d1:wg983ft3682:72447fb17ff8b4b6f261`, ancre `unit-eacd20493def862f`.

## 14. manqué — Faut-il réduire les impôts ?

Habitants de Pierrelez · Art. 1er. · note **3/3**.

> Art. 1er. Nous supplions de vouloir bien nous accorder une modération des impositions, attendu la très-grande modicité du terrain et qui se trouve encore dévasté par les lapins et autres gibiers.

La modération des impositions de Pierrelez est directement pertinente, mais n'arrive qu'au26e rang A et28e rang B, hors top10 de toutes les méthodes.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 26 | 0.502067 |
| historical | vector_B | 28 | 0.449252 |
| historical | hybrid_A | 45 | 0.011628 |
| historical | hybrid_B | 44 | 0.011364 |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | >50 / absent | — |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | >50 / absent | — |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome5, p.21. [Volume numérisé](https://purl.stanford.edu/xx284sn7328). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/xx284sn7328/xx284sn7328.xml). Identifiant `ap1789-pilot-u1:12cdaced3d457962e532:c115459d0d48b64c`, parent `ap1789-pilot-d1:xx284sn7328:12cdaced3d457962e532`, ancre `unit-c115459d0d48b64c`.

## 15. manqué — Comment rendre la justice moins coûteuse pour les justiciables ?

Habitants de Beaurecueil · 3° · note **3/3**.

> 3° Que les petites communautés de la Provence aient un défenseur ou syndic ou un bureau de syndics, défendeurs libres, indépendants; et qu'on ne soit pas obligé de payer à l'effet de faire valoir les droits des petites communautés contre leur seigneur. Les- grandes communautés ont des moyens pour se défendre ; les petites n'en ont point; et souvent même elles ont des droits à faire valoir contre les grandes communautés. La petite ^communauté de Beaurecueil est dans ce cas vis-à-vis de la communauté d'Aix. Elle était exempte autrefois des droits d'entrée ; elle venait y vendre ses denrées librement. Depuis quelque temps, on y a mis obstacle : le seigneur seul en jouit aujourd'hui, ainsi que les possédants biens qui résident à Aix. r , Un moyen plus simple et plus naturel encore de donner de la consistance à cette communauté, ce serait de la réunir à la communauté de Roquet-Hautes, dépendant du même seigneur, et déjà comprise sous un même rôle de capitation.

Un défenseur indépendant sans paiement pour les petites communautés répond à l'accès économique à la justice. Il demeure28e en A et32e en B, avec une longue unité multithématique.

| Population | Méthode | Rang | Score |
|---|---|---:|---:|
| historical | lexical | >50 / absent | — |
| historical | vector_A | 28 | 0.445926 |
| historical | vector_B | 32 | 0.397037 |
| historical | hybrid_A | 49 | 0.011364 |
| historical | hybrid_B | >50 / absent | — |
| mixed | lexical | >50 / absent | — |
| mixed | vector_A | 48 | 0.445926 |
| mixed | vector_B | >50 / absent | — |
| mixed | hybrid_A | >50 / absent | — |
| mixed | hybrid_B | >50 / absent | — |

Référence : AP, tome6, p.262. [Volume numérisé](https://purl.stanford.edu/wg983ft3682). [Source TEI figée](https://github.com/StanfordUniversityLibraries/ap_tei/blob/926fd3cd986a3c3d411e93d1845fff6475cb2602/wg983ft3682/wg983ft3682.xml). Identifiant `ap1789-pilot-u1:f7df571f2f7d6b380e1b:cb07e7de95a2da0e`, parent `ap1789-pilot-d1:wg983ft3682:f7df571f2f7d6b380e1b`, ancre `unit-cb07e7de95a2da0e`.

## Une liste commune réellement calculée

Pour « Les représentants doivent-ils rendre des comptes aux citoyens ? », les dix premiers résultats de vector_A mélangent les deux corpus sans quota. Les propositions restent distinctes : révocation ou promesses des élus en2019, responsabilité des ministres en1789.

| Rang | Corpus | Passage | Note | Cosinus |
|---:|---|---|---:|---:|
| 1 | gdn-2019 | m026 : Responsabiliser les citoyens et les élus et pénaliser fortement les mensonges avérés - Trouver un financement pour permettre à des salariés de se présenter aux législatives | 3 | 0.648105 |
| 2 | gdn-2019 | m050 : un président élu avec prise en compte des votes blanc. des députés élus qui portent la voix du peuple et sont hermetiques aux lobbyistes, un système de révocation en cas de manquement aux promesses ou défaillance ( abus de pouvoir, de bien social, etc..) | 3 | 0.622525 |
| 3 | gdn-2019 | m037 : Il faut instaurer une bonne fois pour toutes la proportionnelle à l'Assemblée Nationale (totale ou partielle), et surtout développer l'idée de citoyen tirés au sort dans certaines assemblées, au moins au niveau local, pour rendre la démocratie plus directe. | 1 | 0.589338 |
| 4 | cahiers-1789-ap-stanford | h133 : 7° Que les ministres doivent être comptables à la nation de leur administration. | 3 | 0.587580 |
| 5 | gdn-2019 | m085 : Arrêter les fausses promesses, et leur crises pour le pouvoir | 3 | 0.585710 |
| 6 | gdn-2019 | m042 : Je pense globalement que le français n'a pas à se plaindre...par contre trop de corps Intermédiaires entre le peuple et les dirigeants polluent la démocratie car agissent dans leur intérêt et caricaturent souvent. Pourquoi ne pas mettre en place une sentinelle numérique citoyenne qui permettrai d écouter en direct les bruits de la société et piloter la politique plus précisément et dans le bon timing. Les problèmes et les soluions sont connues de longues dates, regarder les innombrables rapports, le plus difficile c la mise en scène du changement et en écoutant via le net les vibrations du peuples on ne rame pas à contre courant. Rendre obligatoire ses consultations par secteur socioprofessionnel...plutôt que l élection de super héros tous les 5 ans. | 2 | 0.579514 |
| 7 | gdn-2019 | m045 : Respecter ses promesses de campagne | 3 | 0.568833 |
| 8 | gdn-2019 | m089 : Peu importe, il faut surtout que les élus se préoccupent vraiment de l’intérêt général! | 2 | 0.556459 |
| 9 | cahiers-1789-ap-stanford | h023 : Art. 4. Lesdits députés insisteront à ce que la matière de l'impôt et des autres secours nécessaires, tant aux besoins de l'Etat qu'au payement de la dette, quand elle sera jugée, ne soit traitée qu après la sanction de la charte nationale. Charte nationale. La succession au trône conservée dans l'ordre consacré. La liberté générale et individuelle des citoyens. La liberté de la presse, sous les modifications que les Etats généraux jugeront convenable d'v prescrire. L'abolition absolue des lettres de cachet, tant pour exil que pour emprisonnement; de l'usage dangereux et illégal de toutes commissions particulières pour juger les délits, et de tous les mandats des cours supérieures aux juges inférieurs, connus sous le nom de veniat. Que la foi publique ne puisse, sous aucun prétexte, être violée dans les bureaux de la poste aux lettres,' Que l'on assure la périodicité des Etats généraux, dont la première tenue sera indiquée au plus tard dans trois ans, à compter de la fin des Etats prochains, et les autres tenues seront fixées à cinq ans de "distance de l'une à l'autre, s'en référant au surplus au vœu général des députés aux Etats généraux. Que l'assemblée prochaine des Etats généraux détermine toutes les précautions à prendre pour assurer l'exercice du pouvoir souverain, dans le cas où il y aurait lieu à la régence, et jusqu'à ce qu'elle ait été déférée par lesdits Etats généraux. Que les députés aux Etats généraux, comme personnes sacrées, ne puissent, sous aucun prétexte, être troublés dans leurs fonctions. Qu'aucun citoyen, occupant un emploi légal, civil ou militaire, ne puisse être destitué que par ses juges naturels. Que tout citoyen accusé par le ministère public, et renvoyé absous, ait droit à une indemnité qui sera payée par l'Etat. Qu'aucune loi générale ne puisse avoir lieu qu'autant qu'elle aura été consentie ou propo- sée par les Etats généraux, et sanctionnée par le roi pour être incontinent transcrite sur les registres des cours, sans vérification, publiée et affichée Que nul impôt, emprunt, création ou suppression d'offices ne puisse avoir lieu sans le consentement des Etats généraux. Que les ministres soient responsables envers la nation des fonds qui leur seront confies pour leurs départements, et des abus de leur administration. Lesdits députés proposeront aux Etats généraux d'autoriser particulièrement le ministère public à poursuivre les ministres prévaricateurs dans l'intervalle d'une tenue à l'autre. | 3 | 0.553762 |
| 10 | gdn-2019 | m114 : A l'image des entreprises, les différentes recettes et postes de dépenses devraient être présentées afin que chaque citoyen puisse voir la problématique de l'équilibre des comptes et juger. Ne pas voir entretient le doute et la méfiance. | 2 | 0.548844 |
