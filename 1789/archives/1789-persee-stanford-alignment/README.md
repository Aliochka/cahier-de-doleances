# Rapprochement Persée–Stanford — étude de faisabilité

**Recommandation C : combiner les métadonnées Persée avec Stanford et conserver V2 comme instrument complémentaire, dans un processus soumis à validation.** Il est justifié de tester ce registre documentaire avant de multiplier les règles d’une V3 autonome. **Ni Persée seul ni le prototype combiné ne permettent encore de certifier automatiquement tous les parents et leurs frontières.**

## Expérience réalisée

72 notices, 12 par tome I–VI; six catalogues METS de volumes; pagination OAI suivie sur les deux ensembles fournis. 13 contrôles de développement, 53 notices tirées par empreinte et 6 contrôles de types non revendicatifs. Pas d’échantillon statistiquement représentatif.

Après examen : **55 cahiers, 1 procès-verbal revendicatif associé et 16 autres documents**. Parmi les 58 notices `griev`, deux sont des listes de comparants et une décrit le procès-verbal associé. Ce type n’est donc pas synonyme de cahier autonome complet.

| Observation | Résultat local |
|---|---:|
| Notices récupérées | 72/72, toutes avec titre et pagination |
| Documents ciblés, en incluant le PV associé | 56 |
| Rapprochements proposés par B (hors abstentions) | 53/56 |
| Parmi ces propositions : identité compatible après lecture Codex | 50/53, soit 94,3 % |
| Identités encore ambiguës / faux rapprochement proposé | 2 / 1 |
| Propositions fortes B, contrôlées compatibles en identité | 43/43 |
| Abstentions sur des documents cibles | 3 : Domfront, Bugey, Guérande |
| Frontières exactes sur 26 références de contrôle, A / B / C | 21 / 22 / 23 |
| Frontières sur 13 références nouvelles, A / B / C | **10 / 10 / 10** |

Les trois abstentions ont néanmoins le bon passage parmi les candidats faibles : 53/56 premiers candidats sont compatibles au total, **sans que cela constitue 53 admissions automatiques**. Les scores sont heuristiques, pas des probabilités. Les appréciations sont effectuées par Codex en voyant les prédictions, **pas une validation humaine indépendante**.

C conserve 43 propositions fortes, fournit 11 candidats uniques supplémentaires à contrôler et 2 files de candidats multiples. Les ancrages retenus pour le contrôle apparaissent dans ces files pour les 56 documents cibles, dont deux identités/portées restent incertaines; cela **n’est pas un rappel exhaustif du corpus**. Les files multiples contiennent aussi deux alternatives erronées. Sur les 26 notices encore inédites lors de la formalisation de C, aucun gain de frontières n’est démontré : les trois approches obtiennent 10/10 sur le sous-lot dont les limites ont été examinées.

## Les quatre problèmes V2

- **Anjou, clergé : solution documentaire démontrée dans le contrôle.** Une notice, pages 30–32, rattache les trois chapitres Stanford; le détecteur V2 n’admettait pas le parent.
- **Mirecourt, noblesse : identification et correction de statut démontrées.** Persée nomme un cahier nobiliaire, pages 1–6, incluant des pièces complémentaires. Les limites suivent une politique de dossier explicite.
- **Courtiches : correction de statut démontrée.** Un cahier de village, pages 196–200, et non une pièce professionnelle.
- **Grasse : aide partielle.** La notice identifie le dossier général; elle ne donne pas d’identifiant distinct à la pièce commençant au `p[50]` que V2 manque. La structure interne reste à reconstruire.

## Ce qui reste à contrôler

Les métadonnées donnent des pages, pas des positions dans ces pages. Sur les 56 documents cibles, **30 n’ont pas de référence de frontières examinée dans ce test**. Parmi les 26 contrôlés, C conserve trois fins incorrectes : Besançon, Libourne, Marseille. Deux identités/portées restent incertaines et deux files demandent un choix entre candidats. Ces tâches se recouvrent : ne pas en faire une somme de documents ni une estimation de journées humaines. Aucun temps humain indépendant n’a été mesuré.

Les droits des métadonnées et du contenu sont annoncés différemment par l’entrepôt; les conditions du futur usage public doivent être rattachées explicitement aux ressources concernées. L’étude locale n’a publié aucun texte intégral Persée ni engagé de contact.

## Livrables et vérifications

- [METADATA.md](METADATA.md) : champs, pagination, couverture, limites et conditions constatées.
- [ALIGNMENT.md](ALIGNMENT.md) : algorithmes, gels, mesures, comparaison A/B/C et effort de vérification.
- [CASES.md](CASES.md) : quatre erreurs V2 et autres réussites/échecs concrets.
- [data/correspondences.jsonl](data/correspondences.jsonl) : notices, références Stanford, propositions, ambiguïtés et jugements séparés.
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) : scripts, versions, empreintes, cache et commandes de reproduction.
- [data/checks.json](data/checks.json) : contrôles effectivement exécutés.

Les six Stanford locaux restent à la révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, empreintes vérifiées. 448 fichiers des audits précédents sont surveillés par empreinte et restent inchangés. Aucun changement applicatif ou PostgreSQL, aucun embedding, aucune V3 et aucun déploiement.

## Réponses aux sept questions

1. **Inventaire exploitable ?** Oui comme catalogue de candidats documentaires. Les six METS comptent 1 305 entrées `griev`, **pas 1 305 cahiers complets certifiés**. Leurs titres/types doivent être confrontés au texte.
2. **Proportion rapprochée correctement ?** B propose 53 des 56 cibles :50 compatibles,2 incertaines,1 fausse. Les 43 propositions fortes sont compatibles dans le contrôle effectué. Sur les 43 cibles du nouveau tirage,38 propositions sont compatibles,2 incertaines,1 fausse et 2 abstentions. Ne pas extrapoler ces proportions.
3. **Frontières retrouvables avec ces seules informations ?** Non. Les pages réduisent la zone; le XML et ses transitions déterminent les bornes. Les références de limites portent sur une politique Stanford déclarée, pas sur des zones de texte Persée que nous n’avons pas téléchargées.
4. **Erreurs V2 résolues ?** Trois cas connus sont effectivement aidés en identification/statut; Grasse reste partiellement résolu. Ce sont des contrôles de développement.
5. **Difficultés restantes ?** Pages partagées, titres OCR, noms territoriaux différents, qualifications d’ordre, dossiers composites, annexes, listes classées `griev`, portées éditoriales différentes.
6. **Vérifications supplémentaires ?** Au moins les 30 frontières non examinées, les 3 fins incorrectes et les 4 cas d’identité/choix encore ouverts dans la file C, avec recouvrements possibles. Pas d’estimation de durée humaine disponible.
7. **Préférable à V3 seule ?** Oui comme prochaine piste limitée : un registre Persée–Stanford peut éviter certaines règles de découverte ad hoc. La supériorité automatique globale de C n’est pas démontrée; un nouveau test indépendant reste nécessaire avant généralisation.
