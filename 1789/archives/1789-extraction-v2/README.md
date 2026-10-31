# Fiabilisation de l’extraction des cahiers de 1789 — V2

**Conclusion : des progrès de segmentation, mais pas encore un détecteur assez fiable pour lancer une extraction systématique expérimentale de parents retenus sans corrections bloquantes.** La V2 a été exécutée et évaluée, puis balayée sur les six volumes. Les prédictions initiales et les échecs sont conservés.

## Résultats principaux

| Contrôle | V1 | V2 | Portée |
|---|---:|---:|---|
| Unités A du premier pilote reproduites exactement | 250/269 | 260/269 | Développement; aucune perte parmi les 250 |
| Anciennes fenêtres de 48 articles | 46/48 | 48/48 | Développement |
| Pecqueuse | 38 articles | 38 articles | Régression; article37 sur deux paragraphes |
| 24 nouveaux candidats, précision des autonomes | 15/16 | 14/14 | Gain de précision local, mais un autonome perdu |
| 24 nouveaux candidats, rappel des autonomes | 15/15 | 14/15 | Courtiches mal classé comme associé |
| 12 nouvelles zones, rappel des autonomes | 12/13 | 12/13 | Aucun gain de découverte démontré |
| 79 nouvelles unités, limites exactes | 68/79 | 69/79 | Parents de référence; +2 unités, −1 régression |

Les 19 écarts anciens étaient déjà présents dans l’extracteur brut du premier pilote : **10 résolus, 9 persistants**, sans changement des anciennes annotations. Sept références méritent une relecture complémentaire. Les chiffres nouveaux proviennent d’une lecture Codex du XML; **pas d’une validation humaine indépendante** ni d’une collation complète des imprimés.

Le balayage global produit **1 197 hypothèses autonomes et 43 associées**. Leur nombre ne prouve aucune amélioration de qualité. Il montre notamment une régression sur Anjou clergé et Mirecourt noblesse, et une pièce manquée à Grasse. Les difficultés nouvelles ne sont pas corrigées après gel afin de préserver l’évaluation.

## Documents et données

- [REGRESSIONS.md](REGRESSIONS.md) : tableau des 19 écarts, diagnostics et références à réexaminer.
- [DISCOVERY.md](DISCOVERY.md) : règles, corrections connues, erreurs nouvelles, six classes et leurs limites.
- [EVALUATION.md](EVALUATION.md) : sélection, gels, référence source, mesures comparables, galerie des erreurs et effort réellement observé.
- [GENERALIZATION.md](GENERALIZATION.md) : exécution six volumes, changements suspects, contrôles et prochaine étape.
- [data/](data/) : inventaires V1/V2, nouvelles annotations, prédictions, comparaisons détaillées, journal et contrôles.

L’export local de référence contient **15 parents**, **78 unités A**, **166 propositions B** et **93 plages C**. A : bornes examinées dans le TEI par Codex. B : proposition non certifiée. C : texte hors fenêtres d’articles revues, incluant potentiellement des articles non revus, titres, notes et signatures. **Les B ne forment pas une partition avec A/C** : ils sont un jeu de propositions distinct. Les textes sources complets restent dans les parents; aucune correction OCR ou modernisation.

`corpus-A.jsonl` exclut une référence documentaire ambiguë conservée dans [les réserves explicites](data/reference-review-notes.jsonl), sans modifier les 79 références initialement gelées. C’est un export des décisions sources, distinct des 69 correspondances automatiques V2 exactes. Les identifiants de voisins de cet export désignent les **voisins parmi les unités revues**, pas nécessairement les articles consécutifs du cahier. Les positions permettent de retrouver aussi les passages intermédiaires non revus. Les trente anciens parents et leurs identifiants restent référencés dans [la table de correspondance](data/legacy-document-crosswalk.jsonl), sans remplacement silencieux.

## Sources et isolation

Six XML Stanford, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, vérifiés contre les empreintes de l’audit antérieur. L’ancien cache temporaire était absent après l’arrêt de la machine, ce qui est compatible avec un nettoyage de `/tmp` au redémarrage. **La restauration des six fichiers figés a été expressément autorisée**; ils résident désormais dans `../../sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602/`, ignoré par Git. Aucun autre corpus téléchargé, aucune collecte Persée, aucun embedding.

Les intervalles sont des points de code Unicode dans le texte XML décodé, semi-ouverts `[début,fin)`, avec XPath et lignes XML, pages et liens Stanford. Ce ne sont pas des offsets d’octets XML. Les erreurs OCR, blancs et ponctuation sont préservés. Les notes XML sont traçables séparément; les notes dans des paragraphes ordinaires peuvent encore contaminer une unité aux bornes exactes.

Aucune modification applicative, PostgreSQL, index, route ou déploiement. Les 370 fichiers des audits antérieurs suivis par empreinte restent inchangés. [checks.json](data/checks.json) contient les contrôles effectivement exécutés, y compris fidélité des textes, gels, ordre et reconstruction.

## Reproduction

Exécuter depuis la racine du dépôt avec `/usr/bin/python3` (Python 3.10.12, lxml4.8.0 installé localement). Aucun environnement applicatif ou PostgreSQL nécessaire.

```sh
/usr/bin/python3 1789/archives/1789-extraction-v2/evaluate.py
/usr/bin/python3 1789/archives/1789-extraction-v2/discover_v2.py
/usr/bin/python3 1789/archives/1789-extraction-v2/analyze_global.py
/usr/bin/python3 1789/archives/1789-extraction-v2/check_development_extra.py
/usr/bin/python3 1789/archives/1789-extraction-v2/review_notes.py
/usr/bin/python3 1789/archives/1789-extraction-v2/export_verified.py
/usr/bin/python3 1789/archives/1789-extraction-v2/checks.py
```

Ruff a été exécuté sur les scripts avec exceptions explicites de style pour `annotate_reference.py` (référence gelée) et de variable inutilisée pour `rules_v2.py` (règle gelée), afin de conserver exactement leurs empreintes. La syntaxe Python et les contrôles documentaires passent. Aucun build applicatif n’est requis pour ces fichiers d’audit.

Les mesures de temps peuvent changer; les coordonnées, textes, identifiants, jugements et comptes doivent rester identiques. Les sources vérifiées sont déjà présentes dans le cache persistant local. Après perte du cache, `restore_sources.py` permet la restauration des **six mêmes fichiers** sous réseau autorisé; aucune récupération n’est nécessaire pour lire les résultats archivés.

`review_notes.py` conserve une réserve documentaire et son analyse de sensibilité (78 références sans cette réserve), sans retoucher les résultats primaires sur 79.

Ne pas relancer les scripts de **création** des gels, plans, amendement ou références en écrasant leurs sorties. Ils gardent leurs assertions anti-écrasement. `annotate_reference.py` enregistre des décisions de lecture explicites, pas une référence fabriquée à partir des prédictions. Les scripts V1 et du pilote sont des dépendances lues, empreintes conservées; ils ne sont pas modifiés.

## Réponses aux dix questions

1. **19 différences :** dix corrigées en V2, neuf persistantes. Aucune n’était nouvelle par rapport au premier extracteur brut; sept anciennes références méritent encore une relecture.
2. **Erreurs corrigées :** absences explicites, résumés hors 1789, rubriques abusives; récupération de titres en paragraphes, Mandats et remontrances OCR de cas connus. Les PV revendicatifs sont distingués partiellement.
3. **Erreurs restantes :** formules de début non couvertes, motifs professionnels trop larges, instructions ambiguës, notes et clôtures OCR, numéros dégradés, portée des pièces associées.
4. **Précision V2 :** meilleure sur les 24 candidats autonomes de ce lot (14/14 contre 15/16), avec rappel strict inférieur; aucun gain généralisable établi.
5. **Rappel :** pas amélioré dans les zones nouvelles (12/13 autonomes pour les deux versions); régressions de classification présentes.
6. **Frontières :** 12/12 parents retrouvés exacts dans les zones pour les deux versions; pas de progrès démontré, et Anjou est une régression bloquante hors test nouveau.
7. **Articles :** progrès sur le développement et net +1 sur 79 nouveaux, **avec une nouvelle troncature à Grigny**. L’absence de perte sur 269 ne suffisait pas.
8. **Traitement systématique :** balayage non certifié effectué; ne pas lancer l’extraction systématique de parents réputés fiables avant V3.
9. **Contrôles indispensables :** dates/genre, existence du corps, titres internes, rattachements/annexes, signatures/notes, numéros OCR et conservation du texte; contrôles des zones non détectées et relecture indépendante.
10. **Prochaine étape :** V3 limitée aux défauts observés, gel puis nouvel échantillon inédit et relecture indépendante chronométrée, avant toute intégration applicative.
