# RAG-022 — Première génération de réponses sourcées

## Résultat et état des recettes

La campagne **generation-fr-v2** a produit 20 générations sur les vingt requêtes de développement, avec **17 sorties structurellement valides**. Les sorties rejetées restent conservées. Aucun moteur, reranker ou assemblage documentaire n’a été relancé, aucune requête réservée exécutée.

La recette initiale **generation-fr-v1** a été testée puis conservée après un pilote de trois sorties invalides. Une v2 explicite a été créée conformément au ticket, sans modifier les essais v1. Le pilote v2 a donné trois sorties valides, examinées qualitativement avant la campagne complète. Cette campagne ne constitue pas une validation humaine ou sémantique des réponses.

## 1. Modèle et inférence

- Qwen/Qwen3-14B, révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, Apache-2.0, snapshot officiel RAG-016 local et vérifié par SHA-256. Le README confirme génération conversationnelle, suivi d’instructions multilingues et modes thinking/non-thinking.
- RTX 5090 32 Go ; NF4 double quantification, calcul BF16, SDPA, CUDA 12.8 ; chargeur RAG-016 réutilisé, sans lecture de ses jugements et sans son cache.
- Graine 42, batch 1, génération gloutonne, un faisceau, thinking désactivé dans le gabarit réel ; maximum 2 048 tokens de sortie. Aucun téléchargement supplémentaire et aucun appel d’IA externe.
- Entrée maximale 24 576 et entrée + sortie réservée ≤32 768 tokens. Toutes les entrées sont comptées avec le tokenizer réel Qwen3-14B, gabarit conversationnel compris. Aucune troncature d’entrée.

Prompts v2 complets : **3107 à 7227 tokens** ; plan `c6fcdc8c992c14a3f939db756fe748b4c1cff6e39a29384a504c1165da5eb679`. Versions des bibliothèques, tokenizer/gabarit, paramètres et code conservés dans le manifeste.

La bibliothèque, le modèle et la quantification restent ceux de `.cache/judges-venv`. Aucun changement des dépendances, du verrou backend/RAG, des index ou des modèles de recherche. La répétition sur un autre matériel n’est pas garantie identique bit à bit ; les résultats déjà calculés sont réutilisés par cache.

## 2. Documents et contrat compact

Les vingt contextes gelés RAG-021 **H1+R2 / S2-P1-8192** sont vérifiés puis convertis en **compact-fr-v1**. Chaque source du prompt contient uniquement `reference`, `question`, `answer`, `questionnaire`, `incomplete`. Le texte `answer` est exactement le passage RAG-021, sans reformulation ni ellipse ajoutée.

Les références `S01`, `S02`, etc. sont uniques dans un contexte et résolues par la table de cette requête. Elles ne sont pas globales. La table hors prompt conserve toute la source RAG-021 et sa référence longue, y compris document, contribution, questionnaire, réponse, BIGINT décimaux, empreintes, positions et plages omises. Aucun SHA ou identifiant technique n’est transmis artificiellement au modèle.

Les réponses longues restent les extraits sélectionnés par RAG-021. `incomplete=true` avertit le modèle, et le prompt interdit d’en déduire une conclusion sur la réponse entière. L’interface compacte traite une liste de passages indépendants, préparant l’association future de plusieurs intervalles d’une même unité, sans recherche de passages dans ce ticket.

## 3. Prompts et protocole progressif

Le prompt initial complet est conservé dans [prompt-generation-fr-v1.md](prompt-generation-fr-v1.md), puis la révision explicite dans [prompt-generation-fr-v2.md](prompt-generation-fr-v2.md). Leur texte exact et leur empreinte sont versionnés dans `generation/contracts.py` et les plans.

v1 exigeait 3 à 6 blocs, des affirmations documentaires attribuées, des références connues et des citations littérales exactes optionnelles. Il interdisait les généralisations à la population, l’ajout de connaissances générales et l’invention de consensus ou de désaccords. Les documents sont des données, pas des instructions.

### Pilote v1 préservé

| Requête | Intention | Statut | Motif |
|---|---|---|---|
| democratie-01 | Thématique | Invalide | `invalid_quotes` : trop de citations dans un bloc pour le contrat |
| fiscalite-02 | Propositions | Invalide | `invalid_json`, limite de 2 048 tokens atteinte |
| services_publics-06 | Difficile | Invalide | `invalid_json`, sortie terminée mais non conforme |

Le premier pilote a aussi montré une attribution problématique : une réserve/opposition au scrutin strictement proportionnel était citée dans un bloc favorable. Cette observation qualitative explique pourquoi des références résolues ne suffisent pas. Aucun jugement humain ou LLM historique n’a été consulté pour ce diagnostic.

La v1 ne bornait pas assez la quantité de citations demandées ; le contrat en refusait plus de huit par bloc. Elle n’a pas été réparée ou relancée pour masquer ses échecs. Plans, prompts, sorties brutes et code exact v1 restent disponibles dans `evaluation/local/rag022/plan/code/`, le cache v1 et ses rapports.

### Pilote v2 puis campagne

La v2 conserve modèle, documents et paramètres d’inférence, mais demande une réponse concise : 2 à 4 blocs, 220 mots, 1 à 3 références utiles par bloc et `quotes: []`. Elle explicite qu’un refus ou une réserve ne constitue pas un soutien à la mesure. Les citations littérales restent validables par le contrat, mais cette expérience v2 privilégie la paraphrase.

Les trois sorties pilotes v2 sont structurellement valides. Une inspection qualitative assistée par **Codex, non humaine, non notée et non exhaustive**, est conservée dans `v2/pilot-review.json`. Les références au Sénat, au financement politique et au vote ont notamment été comparées aux passages fournis. L’inspection a relevé des listes de références plus longues et cinq blocs dans certaines réponses, ainsi qu’une terminologie `reported_claim` employée pour des propositions et le mot ambigu échantillon dans une limite.

Le contrat structurel autorise jusqu’à huit blocs et ne transforme pas ces préférences de style en preuve de qualité. La campagne a été poursuivie pour observation, sans publication ni approbation sémantique globale. Les trois générations pilotes sont réutilisées : **17 nouvelles générations**, aucune répétition des trois couples pilotes dans la recette v2.

## 4. Sortie structurée et contrôles

Objet JSON strict : `blocks`, `limits`, `insufficient_sources`. Chaque bloc : `kind`, `text`, `references`, `quotes`. Types : synthèse, opinion rapportée, fait seulement rapporté, limite. Les blocs substantiels doivent posséder au moins une référence ; une limite peut être sans référence. La réponse affichable est dérivée des blocs en ajoutant les marqueurs techniques.

Le validateur refuse JSON malformé, clés dupliquées, types incorrects, références inconnues/dupliquées, blocs sans référence, citations littérales inexactes et guillemets/références non structurés dans le texte. Une citation déclarée doit être une sous-chaîne exacte du passage fourni. Aucune extraction de JSON depuis du Markdown, correction, ajout de champ ou normalisation silencieuse.

**Limite déterminante : il ne vérifie pas l’étayage sémantique.** Une affirmation fausse ou déformée accompagnée d’une référence existante peut passer. Les catégories de blocs ou limites peuvent être mal utilisées ; les contradictions absentes, omissions de points de vue et généralisations indirectes exigent une inspection distincte. Les tests comprennent explicitement une affirmation non étayée mais structurellement acceptable.

## 5. Résultats déterministes de la campagne v2

- **Validité : 17/20 (85.0%)**. Les sorties rejetées ne sont pas présentées comme des réponses acceptées.
- Références de blocs extractibles : **338/338 résolues**. Ce dénominateur porte sur les références des JSON analysables, pas sur une mesure d’étayage des affirmations.
- Citations littérales acceptées : **0**. La v2 demande des paraphrases : aucun taux réel d’exactitude des citations ne peut être déduit d’un ensemble vide ; leur contrôle est validé sur les exemples synthétiques.
- Réponses valides signalant une insuffisance : **0**. Cet indicateur est déclaré par le modèle, pas vérifié comme correct.
- Réponses valides citant au moins un extrait incomplet : **2**. Les positions et omissions restent dans la provenance.
- Tokens d’entrée cumulés : **100,601** ; tokens générés cumulés : **9,998** (hors EOS selon le compteur du backend).

| Requête | Statut | Sources citées validées | Extraits incomplets cités | Entrée / sortie tokens | Latence (s) | Motif éventuel |
|---|---|---:|---:|---|---:|---|
| democratie-01 | valid | 18 | 0 | 3587 / 459 | 10.23 | — |
| democratie-02 | valid | 9 | 0 | 4771 / 470 | 10.80 | — |
| democratie-03 | valid | 8 | 0 | 4588 / 559 | 12.42 | — |
| democratie-04 | valid | 5 | 0 | 6811 / 447 | 10.43 | — |
| democratie-05 | invalid | 0 | 0 | 3107 / 573 | 12.45 | invalid_block_schema |
| ecologie-01 | valid | 7 | 0 | 7227 / 512 | 11.88 | — |
| ecologie-02 | valid | 9 | 0 | 4252 / 386 | 8.74 | — |
| ecologie-03 | valid | 12 | 0 | 7071 / 635 | 14.46 | — |
| ecologie-04 | valid | 11 | 0 | 4547 / 460 | 10.39 | — |
| ecologie-06 | valid | 8 | 1 | 7205 / 590 | 13.52 | — |
| fiscalite-01 | valid | 14 | 0 | 4127 / 456 | 10.20 | — |
| fiscalite-02 | valid | 19 | 0 | 3983 / 544 | 11.77 | — |
| fiscalite-03 | valid | 19 | 0 | 5500 / 527 | 11.92 | — |
| fiscalite-04 | invalid | 0 | 0 | 5775 / 399 | 9.28 | invalid_json |
| fiscalite-05 | valid | 13 | 0 | 4800 / 488 | 11.02 | — |
| services_publics-01 | valid | 14 | 0 | 3941 / 498 | 11.06 | — |
| services_publics-02 | valid | 7 | 1 | 5904 / 568 | 12.85 | — |
| services_publics-03 | invalid | 0 | 0 | 3869 / 431 | 9.68 | invalid_block_schema |
| services_publics-04 | valid | 9 | 0 | 5093 / 493 | 11.08 | — |
| services_publics-06 | valid | 9 | 0 | 4443 / 503 | 11.44 | — |

## 6. Performances GPU et ressources

Temps de génération cumulé des vingt tentatives : **225.63 s**. Latence par requête : médiane **11.07 s**, P95 **13.52 s**, min./max. **8.74/14.46 s**. Débit agrégé entrée non comptée : **44.31 tokens générés/s**.

Ces latences incluent préremplissage, décodage et contrôle de sortie, mais pas le chargement des poids ni la vérification du snapshot. Elles sont propres à cette machine et à ces prompts, pas à Wallace.

| Étape | Nouvelles / réutilisées | Chargement (s) | Temps exécuteur (s) | RAM pic (Go) | VRAM allouée / réservée (Go) |
|---|---|---:|---:|---:|---|
| Pilote v1 | 3 / 0 | 16.76 | 116.17 | 5.54 | 13.99 / 14.04 |
| Pilote v2 | 3 / 0 | 16.45 | 50.34 | 5.52 | 13.99 / 14.04 |
| Campagne v2 | 17 / 3 | 16.79 | 210.00 | 5.51 | 13.99 / 14.04 |

Unités mémoire décimales. Le temps des vingt générations additionne les trois résultats pilotes v2 et les dix-sept nouveaux de campagne, sans compter deux fois les trois réutilisations. Aucun temps de recherche, reranking ou assemblage n’est mesuré ici : leurs résultats gelés ont été réutilisés.

## 7. Cache, reprise et audit

Cache transactionnel de génération distinct des juges : v1 sous `evaluation/local/rag022/generation.sqlite3`, v2 sous `evaluation/local/rag022/v2/generation.sqlite3`. Chaque tentative brute/structurée et son checkpoint sont écrits atomiquement. Recette, plan, entrée, prompt et sortie sont empreintés. Une sortie valide ne peut pas être écrasée ; une sortie invalide n’est pas complétée ou corrigée. `--retry-errors` concerne les seules erreurs d’inférence, avec conservation des anciennes tentatives.

Rapport courant : `evaluation/local/rag022/v2/reports/546a89628078ffc5047cab0807e7857a4e59b34e98f0206e502811e3dc7ffe6e/`. `answers.json` contient les réponses et tables de citations complètes ; `summary.json` les mesures par requête ; `inspection-template.json` une grille sans notes ni évaluateur attribué. Tous restent locaux et ignorés par Git. Le prompt exact figure aussi dans les rapports.

Les commandes, formats et réserves sont détaillés dans [generation-locale.md](generation-locale.md). Un recalcul avec caches doit réutiliser les sorties plutôt que charger un modèle ou modifier les réponses.

## 8. Évaluation qualitative et recommandations RAG-023

La grille non remplie porte sur intention, fidélité aux sources, attribution, synthèse, désaccords, absence de généralisation abusive et lisibilité. Les seules observations qualitatives effectuées ici sont celles du pilote, explicitement attribuées à Codex ; aucune note de qualité n’a été générée et aucune référence humaine n’a été créée.

La v2 rend la génération exploitable expérimentalement sur 17 réponses acceptées, mais pas prête pour le site public. Trois sorties restent rejetées et n’ont pas été réparées. Aucun indicateur d’insuffisance n’a été activé dans les réponses valides malgré des limites textuelles : ce signal doit être examiné, pas interprété comme une preuve de complétude. Pour RAG-023 : inspection humaine ciblée de l’étayage affirmation/source et des oppositions ; traitement explicite des sorties rejetées par une nouvelle recette ou un décodage contraint, sans réparation silencieuse ; examen des sources incomplètes et des passages manquants ; vérification des formulations non représentatives et des catégories opinion/fait rapporté.

Conserver les deux recettes et leurs résultats comme références. Ne pas confondre références résolues, citation exacte, source disant vrai, paraphrase fidèle et réponse complète. Les contextes sont sélectionnés par un moteur sur le corpus expérimental et ne permettent aucun comptage représentatif des opinions. La chaîne est un premier échange conversationnel documentaire, pas encore une conversation multi-tour avec recherche interactive.

## 9. Validations et limites de vérification

- Suite complète : **526 tests réussis**, trois tests optionnels PyTorch ignorés dans l’environnement léger ; avertissement FastAPI/HTTPX préexistant. Les intégrations PostgreSQL utilisent les bases de test isolées.
- Ruff, formatage des nouveaux fichiers, `uv lock --check` (73 paquets) et `git diff --check` conformes.
- Rejeu sur une copie isolée du plan et du cache : **20 résultats réutilisés, zéro nouveau calcul et aucun modèle chargé** ; cache copié identique après rejeu. Les 17 sorties valides et trois invalides sont conservées.
- **1 380 fichiers historiques contrôlés par SHA-256 : aucun changement**. Les prompts v1, le plan et le code archivé restent vérifiables ; la v2 est une recette distincte. Résumé : `evaluation/local/rag022/validation.json`.

- 25 nouveaux tests autonomes : format compact, références, BIGINT, citations exactes/inventées, JSON et types invalides, fenêtre, reprise, cache indépendant, sorties invalides préservées, atomicité, prompt versionné et dépendances légères.
- Vérifications réelles de tous les prompts et sources RAG-021 avant génération, sans réassemblage. Les contextes restent ceux des unités de développement RAG-007.
- Aucune nouvelle annotation humaine ou LLM, aucun téléchargement, aucune écriture source/PostgreSQL, aucun changement de moteur, index, backend, frontend ou Wallace. Aucun commit ni push.
