# Passage à une extraction systématique

**La chaîne technique peut traiter davantage de documents ; le détecteur documentaire ne permet pas encore de les considérer automatiquement comme de vrais cahiers de 1789.** L'expérience ne justifie pas une intégration des 189 parents hors quarantaine comme corpus certifié.

## Règles à conserver

- Provenance figée, positions Unicode et XPath, texte parent intégral, annotations séparées et navigation entre unités.
- Articles pouvant traverser plusieurs paragraphes, pages et notes ; plusieurs articles possibles dans un paragraphe ; priorité à `Art.` sur les sous-listes ordinales.
- Hypothèses de regroupement de divisions sœurs avec conservation des pièces jointes, sans les transformer toutes en parents autonomes.
- A attribué uniquement à des limites examinées, B comme proposition et C comme texte conservé. Les 48 nouveaux A ajoutent un petit sous-corpus contrôlé sans certifier les autres sorties.
- Conservation des prédictions avant revue et table de correspondance : une correction ne détruit ni l'hypothèse initiale ni son contexte.

## Règles à améliorer dans une version 2 explicite

1. **Chronologie et genre du contexte englobant.** Les premiers volumes comprennent des récits d'États généraux antérieurs et des mémoires : un titre interne « Cahier » ne suffit pas à faire un document de 1789.
2. **Absence de document.** Étendre les alertes aux formulations « manque aux Archives », « ne se trouvent pas », sans présumer que cette liste suffira à tout détecter.
3. **Titres de début versus rubriques.** « Doléances pour le clergé » ou « Plaintes locales » peuvent être des sections. Il faut rapprocher leur portée du cahier englobant et de sa clôture.
4. **Ouvertures hors `head`.** Les titres en `p[1]`, « Mandats », variantes OCR de « Remontrances » et doléances dans des procès-verbaux échappent encore à l'admission.
5. **Dossiers professionnels et annexes.** Arles impose des limites entre corps de métiers ; un dossier peut contenir de vrais sous-documents sans que tout soit un cahier autonome au même niveau.
6. **Marqueurs OCR et rubriques.** Les deux nouveaux débuts manqués et les fusions du développement appellent des alertes contrôlées ; une suite numérique attendue ne doit pas réécrire un numéro illisible.

Aucune de ces améliorations n'a été appliquée au lot de validation après ses résultats. La mise en cache du parcours XML est une optimisation équivalente contrôlée, pas une modification de règle documentaire.

## Validation encore nécessaire

Les 153 nouvelles hypothèses non certifiées ne doivent pas recevoir A au seul motif qu'elles semblent régulières. Vérifier d'abord leur autonomie, leur période et leurs limites ; les grands dossiers et titres internes sont prioritaires. Les 5 872 B n'exigent pas nécessairement autant de décisions manuelles : des contrôles de sections et de parent peuvent résoudre des familles de défauts, mais le coût n'est pas mesuré.

Un futur classement des formes faciles/difficiles doit être évalué sur un échantillon distinct, pas déduit de cette sélection de diversité. Les fenêtres d'articles et zones non couvertes de cette mission sont trop petites et orientées pour projeter une précision globale sur plusieurs milliers de cahiers.

## Prochaine mission limitée, non commencée

1. Utiliser cette version et ses erreurs comme **développement** d'une version 2 ; conserver les sorties et références actuelles.
2. Définir un cadre de zones continues dans les six volumes, incluant des zones sans titre documentaire reconnu. Tirer ces zones indépendamment de la détection, puis y relever tous les vrais débuts et leurs prolongements : ce cadre permettrait un rappel local défendable.
3. Faire annoter les parents et des articles complets par un lecteur humain compétent, avec une seconde lecture partielle et arbitrage ; enregistrer séparément le temps réellement consacré aux opérations.
4. Geler les nouvelles règles avant de découvrir les jugements d'un nouveau lot. Inclure des documents brefs, composites, non numérotés et professionnels. Aucun des 30 anciens, Pecqueuse ou 12 candidats actuels ne doit être annoncé comme validation neuve.
5. Comparer les erreurs avant/après sans remplacer les échecs ; décider alors d'un traitement progressif de lots supplémentaires. Préserver les textes sources, versions, identifiants et statuts de confiance.

Les textes A peuvent servir à de futurs essais locaux, avec leur provenance et leurs limites ; B et C restent consultables dans leur contexte. Aucun embedding, index ou parcours applicatif n'est créé dans cette étude. Les réserves documentaires et de republication signalées dans les audits antérieurs restent à traiter avant publication.
