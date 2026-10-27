# Qwen3-14B et frontières documentaires des cahiers de 1789

**L’expérience a réellement été exécutée sur le Qwen3-14B local. La recette testée n’améliore pas les frontières par rapport aux règles actuelles. Ne pas l’utiliser pour corriger automatiquement les 1 305 notices.**

24 cas de développement, dont les 15 erreurs connues, et 36 nouvelles notices (six par tome) ont été préparés. La référence des 36 cas a été rédigée et figée avant leurs inférences Qwen. Codex a réalisé les contrôles : ce n’est pas une validation humaine indépendante. Le modèle était le 14B, jamais le 0.6B.

## Résultat de validation

| Méthode | Bornes exactes /36 | Débuts faux | Fins fausses | Corrige A | Dégrade A correct | Invalide |
| --- | --- | --- | --- | --- | --- | --- |
| A | 31 | 2 | 5 | — | — | 0 |
| B | 4 | 22 | 21 | 0 | 26 | 1 |
| C | 30 | 3 | 4 | 0 | 1 | 0 |

A = registre/règles existants ; B = Qwen sans proposition A ; C = Qwen avec A, sur les mêmes fenêtres. Une paire de bornes est exacte seulement si son début **et** sa fin correspondent à la référence de blocs source. Les invalides restent au dénominateur. Une proposition A existe à Santeny mais ne contient que 25 caractères blancs ; elle n’est pas comptée comme une abstention.

L’hybride conserve les deux bornes A dans 31/36 cas. Il ne répare complètement aucune des cinq erreurs A et introduit une fusion au début de Gray : **bilan net −1**, critère prioritaire non satisfait. Des corrections partielles existent, mais ne donnent pas des parents fiables. Sur les 15 erreurs connues de développement, C en corrige entièrement 2, B 1 ; deux des 15 ne disposent pas d’une référence complète unique dans ce contexte, leurs résultats restent non certifiés.

Aucune abstention structurée dans la campagne finale, et aucun `uncertain=true` sur les 36 nouvelles notices, malgré les erreurs. C présente également 25/36 sorties dont au moins un identifiant de signature est extérieur à ses propres bornes. Des identifiants réels et un JSON valide ne constituent donc pas une validation documentaire.

## Coût et périmètre

Qwen3-14B révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, NF4 double/BF16, Transformers existant, mode non-thinking, génération gloutonne, lot 1. Médiane validation : B 7,32 s, C 7,36 s par requête ; pic PyTorch alloué 12,58 GiB, réservé 13,08 GiB. 72 appels de validation, 48 de développement, 4 essais initiaux conservés à part. Le GPU a été libéré à la fin.

**Aucun fichier applicatif, audit antérieur, source Stanford, index, embedding ou base n’a été modifié.** Aucun poids ni paquet téléchargé, aucun serveur déployé, aucune correction OCR. Les empreintes de 728 fichiers antérieurs et sources de code réutilisées sont conservées et vérifiées.

## Livrables et recommandation

- [ENVIRONMENT.md](ENVIRONMENT.md) : poids, GPU, réutilisation du Python et backend.
- [PROTOCOL.md](PROTOCOL.md) : fenêtres, versions, référence et commandes.
- [EVALUATION.md](EVALUATION.md) : compteurs, coûts et limites.
- [CASES.md](CASES.md) : gains, erreurs, extraits réels et références.
- `data/*-outputs.jsonl` : 120 réponses finales brutes, décisions et ressources.
- `data/reference-validation.jsonl` et `reference_decisions.json` : référence exploratoire figée.
- `data/comparison.jsonl`, `metrics.json`, `freeze.json`, `checks.json` : résultats et contrôles.

Conserver la méthode Persée–Stanford avec contrôles structurels et revue documentaire. **Ni le mode autonome, ni le vérificateur C ne justifient une généralisation.** Une éventuelle nouvelle expérience devrait être limitée, préenregistrée, séparer les deux frontières et tester la représentation des IDs et le mode de raisonnement, sur d’autres notices. Pas de nouveau modèle ni de traitement des 1 305 notices lancé ici. Les performances ne prouvent pas une incapacité générale de Qwen3 : elles concernent précisément cette recette NF4, ces instructions, ce format et ces fenêtres.

## Réponses aux neuf questions

1. **Reconnaissance correcte ?** 4/36 bornes exactes sans A, 30/36 avec A ; les règles en ont 31/36. Beaucoup de justifications ne décrivent pas correctement les blocs sélectionnés.
2. **Mieux que les règles ?** Non sur le nouveau lot ; C perd une frontière correcte sans correction complète d’une erreur initiale.
3. **Autonome ou vérificateur ?** C est bien moins mauvais que B et recopie souvent A, mais son utilité ajoutée n’est pas démontrée sur validation.
4. **Erreurs connues corrigées ?** C 2/15 : Châtellerault clergé et Digne tiers. B 1/15. 13 des 15 ont une référence de paire exacte ; deux restent hors contexte/portée incertaine. Pas de certification artificielle des autres.
5. **Nouvelles erreurs ?** Sur validation, C dégrade 1 des 31 paires A exactes ; B produit 26 nouvelles propositions fausses et rend 1 autre cas A correct inutilisable par sortie invalide.
6. **Incertitudes reconnues ?** Très insuffisamment : aucun signal sur validation ; une incertitude C sur développement, aucune abstention structurée. Les références difficiles d’Artois, Riez et Castelnaudary ne suscitent pas l’abstention attendue.
7. **Coût local ?** Environ 7–8 s par appel pour ces contextes, 13,08 GiB de mémoire réservée au pic d’inférence et environ 16–17 s de chargement GPU par session, hors vérification CPU des empreintes.
8. **Passage aux 1 305 ?** Techniquement envisageable à cette taille de fenêtres, mais sans intérêt documentaire démontré. Projection arithmétique C ≈2,67 h pour une passe similaire, hors revue et variation de contextes ; pas une mesure à cette échelle, aucune campagne massive autorisée ou lancée.
9. **Vérification humaine ?** Périmètres de dossiers, annexes, signatures/certifications, titres internes et homonymes, conflits entre ordres, sources intercalées, absences et toute divergence LLM/règles. Les frontières candidates ne deviennent jamais une certification historique.
