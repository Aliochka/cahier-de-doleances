# RAG-024 — Audit ciblé de fidélité

## Bilan et périmètre

**Oui, certaines synthèses déforment des contributions. La sortie contrainte corrige le format, mais introduit aussi des défauts rédactionnels importants.** Pour un usage personnel, quelques corrections ciblées sont nécessaires avant de s’appuyer sur ces réponses ; une infrastructure d’évaluation supplémentaire n’est pas nécessaire.

Lecture assistée réalisée par **Codex**, sans juge local ni inférence GPU. **Ce n’est pas une validation humaine indépendante, ni une mesure de fiabilité générale.** Les vingt réponses v3 et les dix-sept réponses v2 valides ont été lues. La vérification sémantique est ciblée : **136 passages source associés à leurs requêtes**, parmi 397 occurrences de sources disponibles, et non toutes les affirmations de chaque bloc. Les contrôles techniques couvrent en revanche les 397 correspondances, représentant 368 unités distinctes.

| Mesure | v2 | v3 contrainte |
|---|---:|---:|
| JSON analysables, campagne complète | 19/20 | 20/20 |
| Contrat accepté, campagne complète | 17/20 | 20/20 |
| Blocs sur les **17 requêtes communes** | 83 | 67 |
| Occurrences de références sur ces **17 requêtes** | 268 | 167 |

Les chiffres historiques **338 → 198** portent sur les JSON analysables des campagnes entières, donc sur des périmètres différents ; ils ne mesurent pas la fidélité. La comparaison qualitative commune exclut `democratie-05`, `fiscalite-04`, `services_publics-03` côté v2. Leurs sorties v3 restent auditées séparément.

Entrées strictement identiques : H1 + Qwen3-Reranker-4B → S2/P1/8192, vingt requêtes de développement. Réponses, contextes et citations proviennent des artefacts gelés RAG-021/022/023. Aucun moteur, assemblage, reranker ou générateur n’a été relancé. Aucun usage des requêtes réservées.

Grille employée dans les notes locales : **Étayé**, **Partiel**, **Non étayé**, **Contredit**, **Incertain**. L’intitulé « Étayé » est correctement orthographié. Ces statuts concernent les passages examinés, pas une note globale de réponse.

## Problèmes vérifiés

B1, B2… désignent les blocs, numérotés à partir de 1. Les références Sxx sont locales à chaque requête. Les extraits citoyens exacts, positions, identifiants et passages générés sont dans `evaluation/local/rag024/observations.json`, aux identifiants A01…A13 ; ils ne sont pas recopiés ici. Les détails permettent de distinguer une source effectivement citée d’une source du contexte qui aurait dû l’être.

| ID / priorité | Requête, version, passage | Références concernées | Observation et correction envisageable |
|---|---|---|---|
| **A01 — P0** | `fiscalite-03`, v3 B3 | S02, S15, S16 | **Contredit** : une réserve sur le rétablissement de l’ISF est présentée comme une critique de son absence. Un argument sur l’attractivité est également ajouté sans support dans ces citations. Séparer réserve et soutien, sans compléter leurs motifs. |
| **A02 — P0** | `fiscalite-05`, v3 B4 | S11, S18, S19 | **Contredit** : remplacement de la TVA attribué à des textes proposant une baisse compensée par l’IR ou conservant explicitement les deux impôts. V2 B3 évitait cette confusion. Préserver la différence entre baisse, compensation et suppression. |
| **A03 — P0** | `democratie-04`, v3 B1 | S08 | **Non étayé** : un seuil de pétition pour présenter des candidats est transféré à l’initiative législative. V2 B1 n’ajoutait pas ce seuil. Rattacher chaque chiffre à son objet précis. |
| **A04 — P0** | `democratie-05`, v3 B4, hors comparaison commune | S13, S17 | **Contredit pour S17** : une succession de votes jusqu’à majorité est soutenue par S13, mais S17 prévoit un second vote unique sans nouveau comptage du vote blanc. Présenter séparément les mécanismes et leurs conditions. Le bloc entier n’est pas dépourvu de support : c’est l’attribution commune qui déforme S17. |
| **A05/A06 — P1** | `fiscalite-02`, v3 B1/B4 | B1 : S01–S03 ; B4 : S05/S06/S15 | **Non étayé pour les détails signalés** : GAFA/exilés fiscaux figurent dans S05, non cité en B1 ; les références de B4 ne développent pas les contrôles, amendes et moyens administratifs annoncés. S02 évoque contrôles/sanctions. Scinder les propositions et citer leur support exact, supprimer les détails ajoutés. |
| **A07 — P1** | `ecologie-01`, v3 B3 et B1 ; risque déjà présent en v2 B1 | S12 ; S01 | **Partiel** : appréciations citoyennes sur les coûts ou la responsabilité des entreprises formulées comme constats généraux. Le champ `reported_opinion` ne suffit pas : attribuer l’estimation dans la prose, sans généraliser à la population. |
| **A08 — P1** | `services_publics-06`, v3 B3 et synthèse | S02, S08 ; réserve S05 | **Partiel** : le recours en ligne de S02 est bien présent, mais S08 cité réclame l’arrêt de la dématérialisation ; cette divergence disparaît. V2 B4 conservait au moins la réserve de S05 sur le contact physique. Distinguer les positions au lieu de les placer sous une même proposition. |
| **A09/A10/A11 — P1** | `ecologie-03`, limite v3 ; `fiscalite-04`, B4/limite ; `services_publics-03`, limites | Respectivement S01, S02, S08 | **Contredit** : annonces d’absence d’application internationale, de mesures patrimoniales spécifiques ou d’indication d’existence des MSAP, alors que le contexte en contient. Remplacer ces absences fictives par les limites réelles : propositions non évaluées, témoignages locaux, absence de bilan systématique. Les deux dernières requêtes sont hors comparaison v2 commune. |
| **A12 — P1** | `democratie-04`, v3 B3 | S03/S07 cités ; S02 dans le contexte | **Non étayé** : absence de tout mécanisme annoncée alors que S02 décrit une voie institutionnelle de proposition de lois. Distinguer manque de preuve de faisabilité et absence de proposition détaillée. |
| **A13 — P1** | `democratie-03`, **v2 B5** | S03, S11 | **Non étayé** : incapacité des citoyens à comprendre des sujets complexes ajoutée aux objections. Les sources critiquent la simplification d’une question et la manipulation, sans formuler cette incapacité générale. V3 B2 évite cette attribution. |

La gravité est une appréciation de priorité pour cet usage personnel, pas une métrique scientifique. « Non étayé » signifie ici non justifié par les passages examinés et les références indiquées, pas nécessairement faux dans le monde.

## Effets des contraintes et des sources

**Blocs à 600 caractères.** Les vingt blocs concernés, répartis sur treize requêtes, ont été examinés individuellement : **19 fins manifestement inachevées**, souvent au milieu d’un mot ; une fin dégradée probable mais moins certaine (`fiscalite-03`, B1). `ecologie-04` B1 termine aussi sur un caractère parasite. Les quatre blocs de `services_publics-04` atteignent la borne. Quatre entrées de `limits` atteignent 300 caractères et sont également inachevées. Les observations complètes figurent dans `bounded_block_reviews`.

La contrainte ferme le JSON sans garantir une phrase achevée. Les réserves sont particulièrement exposées lorsqu’elles arrivent en fin de bloc. **On ne peut cependant pas reconstituer une suite que le modèle n’a pas générée**, ni affirmer quel argument précis aurait suivi. Des blocs proches de la borne, sans l’atteindre exactement, présentent également des fins dégradées ; le défaut n’est donc pas détectable par le seul test `len == 600`. Les causes respectives du schéma, du filtre et du comportement du modèle ne sont pas isolées par cet audit.

**Références moins nombreuses.** Leur réduction ne garantit pas une meilleure sélection : A05/A06 montrent un contenu effectivement présent ailleurs dans le contexte mais rattaché aux mauvaises références. Inversement, une référence peut suffire pour une proposition précise. Priorité à des blocs moins composites et à l’association affirmation/source, pas à un quota global de références.

**Deux réponses utilisant un extrait incomplet.** `services_publics-01` B3/S16 : difficultés numériques et handicap visibles dans le passage ; l’extension générale au contexte rural reste partielle, ce témoignage étant localisé. `services_publics-04` B3/S14 : accompagnement, thesaurus et IA présents dans l’extrait. **Pas de conclusion manifeste sur la totalité des contributions établie dans ces passages contrôlés**, mais les réponses ne localisent pas clairement l’incomplétude au niveau de chaque citation. Les suites omises n’ont pas été utilisées pour combler le contexte ni auditées comme si elles avaient été lues par le générateur. Détails dans `incomplete_source_reviews`.

**Insuffisance documentaire.** Les deux recettes déclarent toujours `false`. Ce seul fait ne prouve pas une erreur : le prompt réserve surtout `true` à l’absence de source utile, alors que ces contextes contiennent des propositions. Le problème vérifié est plutôt la mauvaise description des limites et les réponses seulement partielles : voir A09–A12. Définir simplement la différence entre réponse partielle et absence de matière utile ; ne pas ajouter un mécanisme complexe d’abstention sur cette seule observation.

## Comparaison qualitative des recettes

V2 est généralement plus courte et évite les fins forcées de v3. Elle contient toutefois des attributions excessives (A13), des opinions présentées comme constats et des divergences omises. Ses grandes listes de références ne constituent pas une garantie d’étayage.

V3 apporte quelques **gains locaux vérifiés** : option de flat tax rendue visible à côté des propositions progressives (`fiscalite-01`, B4/S18–S19), banque du climat correctement ajoutée (`ecologie-06`, B1/S01), précision sur le diagnostic et la revente (`ecologie-02`, B4/S19), préférence pour des discussions au moment des élections (`democratie-02`, B2/S02). Les deux versions restituent une opposition au RIC (`democratie-03`, S03/S11/S18). Les preuves sont conservées sous G01–G05.

Ces gains ne compensent pas automatiquement les régressions A01–A04 et les coupures. **Aucun gagnant global n’est établi.** Le journal `comparison_17` contient une observation pour chacune des dix-sept requêtes communes ; `reading_scope` précise les références effectivement lues. Les autres affirmations, les contributions complètes et la vérité externe des propos restent non validées.

## Priorités pour RAG-025

- **P0 — Préserver le sens.** Traiter explicitement soutien/opposition, baisse/suppression, conditions et objet des chiffres. Garder A01–A04 comme cas de régression concrets. Écarter les arguments ajoutés par connaissance générale. Aucun ajustement des moteurs n’est nécessaire pour ces corrections.
- **P1 — Rendre la réponse lisible et attribuable.** Sortir de la fermeture forcée à 600/300 caractères sans supprimer le validateur ; demander des paragraphes réellement plus courts et achevés, prévoir une réserve de sortie suffisante et signaler les réponses interrompues. Préférer peu de propositions par bloc avec les bonnes références. Attribuer les opinions dans la prose, conserver les divergences, supprimer les limites génériques contredites par le contexte et signaler les extraits incomplets à la citation.
- **P2 — Confort personnel.** Afficher côte à côte passage cité et synthèse, avec accès aux sources complètes disponibles. Conserver les gains G01–G05 et une courte checklist de lecture. Pas de score global, de nouveau juge ou de campagne d’annotation nécessaire pour commencer.

## Artefacts et validations

Depuis `rag/` :

```sh
uv run --locked --no-sync python scripts/extract_fidelity_audit.py
uv run --locked --no-sync python scripts/extract_fidelity_audit.py \
  --output evaluation/local/rag024/extraction-replay.json
```

Le script lit les caches SQLite en **mode lecture seule**, réutilise les contrats existants et ne charge aucun modèle. Il contrôle les empreintes des plans et tentatives, l’identité des entrées, les textes/positions des contextes, les métadonnées contre les `TextUnit` stockés localement et l’appartenance au développement RAG-007. Les BIGINT sont comparés comme chaînes décimales exactes. Les sources citoyennes, les métadonnées et la synthèse restent dans des champs distincts.

- `evaluation/local/rag024/extraction.json` : sources, tables de citations, sorties et signaux de longueur ; SHA-256 `89376004f36a80da29e9e235af6509419443e4635f78392579034ee058c29957`.
- `evaluation/local/rag024/observations.json` : treize problèmes ciblés, cinq constats favorables, vingt fins de blocs examinées, deux extraits incomplets, comparaison des dix-sept requêtes et périmètre de lecture. Ce sont des notes d’audit assistées, **pas des jugements à intégrer aux référentiels humains ou LLM**.
- `evaluation/local/rag024/validation.json` : intégrité, résolution, reproductibilité et résultats des vérifications.

Les deux extractions finales sont identiques octet pour octet. Les passages documentaires des observations sont vérifiés contre les textes et positions conservés. Les fichiers contenant des textes restent locaux, ignorés par Git, avec permissions restrictives ; seuls le script, ses tests et ce rapport sont destinés au dépôt.

**67 tests pertinents réussis** (extraction, génération, décodage contraint, contextes), Ruff et `uv lock --check` conformes. Deux tests ajoutés : conservation de sources/BIGINT et rejet des altérations ; distinction entre signal de longueur et jugement sémantique. Le Python 3.11 référencé par l’environnement pointait vers un répertoire temporaire disparu : le même interpréteur 3.11.17 a été restauré, sans modification du verrou ou des dépendances.

Aucune réponse historique, annotation, contexte, moteur, dépendance, base source, backend, frontend ou configuration Wallace n’a été modifié. Aucun commit ni push. La conservation des fichiers historiques est vérifiée avant/après extraction et dans le relevé de validation local.
