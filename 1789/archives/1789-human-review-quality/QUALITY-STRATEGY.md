# Stratégie opérationnelle de contrôle qualité

## Décision recommandée

**Abandonner la relecture exhaustive comme régime permanent ; conserver une vérification ciblée avec contrôle régulier des articles non signalés.** Ne pas déployer dès maintenant un tri « aucune alerte = fiable » : deux fusions importantes connues échappent à l’alerte directe, et une omission se trouvait dans les passages C.

Les décisions humaines restent prioritaires. Le présent document propose une politique ; il ne modifie ni les statuts, ni les exports, ni l’éligibilité actuelle de l’outil.

## Trois catégories et leur applicabilité réelle

| Catégorie | Conditions et raisons conservées | Action |
|---|---|---|
| 1 — Candidat à faible risque | Parent établi et version compatible ; numéro/localisation cohérents ; pas de signal de fusion ; pas de chevauchement ; pas de contradiction entre structure XML, limites et éléments éditoriaux reconnus | Proposition automatique conservée, contrôle par échantillonnage après calibration. Aucun statut humain inventé. |
| 2 — À vérifier | Numéro absent/irrégulier, marqueur suspect, changement de section incertain, différence de limites, note/rubrique absorbée ou contradiction avec les voisins | Vérifier l’unité **avec ses voisins**, et les plages C entre eux. Une reprise légitime de numérotation peut être acceptée sans renumérotation. |
| 3 — Bloqué/incertain | Parent ambigu/périmé, frontières contradictoires, unité incertaine, découpage historiquement non justifiable | Exclure du lot publiable ; conserver intégralement source, hypothèses et motif de blocage. |

Les informations actuelles permettent un premier prétri, mais pas de démontrer tous les critères de catégorie 1. Les rubriques sont parfois fausses ; les notes incorporées dans le corps ne sont pas toutes reconnues. Les numérotations régulières peuvent cacher une fusion. Les 640 articles sans alerte dans l’état initial sont donc **des candidats non signalés**, pas 640 articles certifiés.

Les 333 articles humains actuels conservent leur décision indépendamment de ce prétri. Une contradiction ultérieure doit ouvrir une décision historisée, pas invalider silencieusement leur validation. Une correction du parent déclenche le contrôle de compatibilité des articles.

## Première file de travail, sans nouvelle extraction

Sur les 19 cahiers non examinés (397 articles initiaux), préparer une file de **40 articles signalés**, en affichant les voisins ; cela concerne 69 articles distincts au total. Les 328 autres sont le réservoir du contrôle des non-alertés. Ce chiffrage est descriptif : il ne prouve pas qu’il n’existe des erreurs que dans la file.

Avant de décider une exemption de relecture, exécuter le protocole distinct de [SAMPLING.md](SAMPLING.md). Lire aussi des fenêtres de texte parent non conditionnées par les articles proposés, afin de chercher les omissions dans C. Lire un voisin pour comprendre le contexte ne doit pas automatiquement le marquer comme validé humainement.

## Chaîne de progression

1. **Notice documentaire.** Préserver l’identifiant Persée et le type supposé. Les 1 305 notices comprennent des annexes, PV, listes et extraits ; les 1 227 cahiers autonomes probables du registre restent des classifications automatiques.
2. **Parent.** Distinguer identité et frontières. Traiter en priorité ambiguïtés, pages partagées, composites et annexes. Un rapprochement fort ne certifie pas le périmètre. Conserver source complète, XPath, positions, version et décisions humaines. Ne pas lancer l’extraction d’articles à partir d’un parent dont le périmètre reste non établi.
3. **Articles et passages.** Réutiliser l’extracteur figé sur de petits lots de parents établis ; préserver les corrections et références héritées. Un texte sans subdivision fiable reste section ou passage technique, pas article authentique fabriqué.
4. **Contrôles.** Positions, couverture, doublons, ordre, version parentale, marqueurs candidats, ruptures numériques et contradictions de rôle/plage. Comparer aux références humaines : la fusion brute des articles 10/11 de Terre-Franche ne doit pas réapparaître dans un nouveau corpus.
5. **File ciblée.** Réviser les anomalies et leur contexte. Ne pas déclarer une correction sur la base de l’alerte seule ; enregistrer la décision et le motif.
6. **Échantillon silencieux.** Contrôle humain reproductible des non-alertés et de fenêtres du parent. Conserver les erreurs découvertes, arrêter ou réviser les règles si un défaut grave échappe au tri.
7. **Préparation pour la recherche.** Exporter les unités éligibles avec type, statut, version, positions, parent, pagination et provenance. Les segments vectoriels viendront ensuite ; ils ne sont pas des unités historiques nouvelles.

Après le calibrage sur les 19 dossiers, prendre des lots de **20 à 30 nouveaux parents** dans le registre, avec diversité de volumes et de structure, sans assimiler les 1 305 notices à autant de cahiers. Geler les règles avant chaque évaluation distincte. Aucune multiplication mécanique du nombre moyen d’articles des 29 cahiers ne permet de prédire le volume total.

## Index expérimental et publication

- **Expérimental local :** parents établis et compatibles, intégrité vérifiée, cas bloqués exclus, contrôle ciblé terminé et critères de calibration satisfaits. Certains articles automatiques peuvent y entrer avec leur statut explicite et un indicateur de contrôle par échantillonnage. Les incertitudes doivent être filtrables et comptables.
- **Publication :** exige un contrôle des parents et une évaluation supplémentaire des unités automatiques, sur de nouveaux parents et plusieurs familles de documents. La validation individuelle de tous les articles n’est pas une obligation proposée, mais le niveau de risque résiduel doit avoir été évalué et accepté explicitement. Les catégories 2 non résolues et 3 restent exclues.
- **Paratexte :** conservé dans le parent, normalement exclu de l’index de revendications. Un passage technique pertinent peut être indexé comme passage, jamais présenté comme article historique.

Le champ existant `indexing_eligible` n’est pas un score de fiabilité et n’exclut pas à lui seul toutes les anomalies ; `publication_ready` suit actuellement une logique plus stricte. La politique ci-dessus nécessitera un filtre documentaire distinct avant un futur export destiné à l’index. Aucun de ces comportements n’est changé ici.

Conserver distinctement : origine automatique, examen Codex, validation humaine, correction humaine, incertitude et contrôle qualité par échantillonnage. Le dernier ne doit jamais être renommé « validé humainement » pour des articles non lus.
