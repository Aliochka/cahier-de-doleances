# RAG-023 — Génération structurée avec décodage contraint

## Périmètre et recette

Expérience locale sur les **20 requêtes de développement**, avec les entrées compactes RAG-022, issues de H1 + Qwen3-Reranker-4B → S2/P1 → 8 192 tokens documentaires. Les fichiers d’entrée, prompts rendus et comptes de tokens sont identiques à ceux de `generation-fr-v2`. Les contextes ne sont pas reconstruits et les modèles de recherche ne sont pas exécutés.

Modèle : **Qwen3-14B**, révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, chargement local NF4/BF16, Transformers 4.57.6, PyTorch 2.10.0+cu128, RTX 5090. Graine 42, mode non-thinking, génération gloutonne, batch 1, maximum 2 048 tokens générés. Aucun poids téléchargé et aucune API distante utilisée.

Recette : **`generation-fr-v3-constrained`**, schéma final **`rag-response-schema-v4-native-token-filter`**, plan `1f56b3586cb059ca957415757ffb8b47db31b15d0fac62750773abcfdae0e8e4`. Le validateur RAG-022 n’est pas modifié.

## Choix du décodeur et architecture

**LM Format Enforcer 0.11.3 (MIT)** est intégré par `prefix_allowed_tokens_fn` dans la boucle Transformers existante. Il intervient après le calcul des logits, indépendamment du chargement NF4. XGrammar 0.2.8 (Apache-2.0, moteur compilé et dépendances TVM-FFI/Triton) et Outlines 1.3.3 (Apache-2.0, adaptateur plus large) ont été étudiés sans installation. Leur compatibilité effective sur cette configuration n’a pas été mesurée.

L’extra uv `constrained` ajoute LMFE et interegular 0.3.3 au verrou ; aucune version préexistante n’est mise à jour. Les dépendances GPU restent optionnelles. Un premier démarrage a révélé l’absence de Pydantic dans l’environnement GPU constitué antérieurement : les paquets manquants ont été installés aux versions déjà verrouillées, avant toute génération.

Les modules du nouveau sous-package `generation/constrained/` couvrent le schéma par requête, le callback, le plan vérifié, le cache SQLite indépendant, l’exécution reprenable, la comparaison et la CLI. Les modules de génération historiques sont conservés. Voir [la documentation technique](decodage-contraint.md) pour la comparaison des bibliothèques et les sources officielles.

## Contraintes réellement appliquées

Le schéma impose les trois champs racine, les champs de bloc, leurs types, les valeurs autorisées de `kind`, les références propres à chaque contexte, et les bornes natives. Les blocs substantiels demandent au moins une référence.

La variante finale limite la sortie à 4 blocs de 600 caractères, 3 références par bloc et 3 limites de 300 caractères. Un filtre supplémentaire exclut les tokens contenant un backslash ou des guillemets typographiques ; les guillemets JSON structurels restent autorisés. Cela empêche notamment les citations entre guillemets doubles échappés dans les blocs. Les sources ne sont jamais modifiées.

**Ces restrictions sont plus strictes que le contrat historique.** Elles peuvent modifier la longueur, le style et la diversité des références ; les différences ne sont donc pas attribuables au seul décodage contraint. Une borne de caractères peut également contraindre la fin d’une phrase. Le contrat n’a pas été assoupli pour faire accepter des sorties.

LMFE ignore `uniqueItems` dans les tests et ne garantit pas un tableau vide avec `maxItems: 0`. Les doublons de références, chaînes blanches, références de citation appartenant au bloc et citations littérales exactes restent contrôlés après génération. Le validateur original demeure obligatoire. Une limite de génération ou une interruption peut toujours produire un JSON incomplet, conservé sans réparation lorsqu’une sortie est disponible.

## Essais préliminaires conservés

| Variante | Résultat du pilote | Observation |
|---|---|---|
| Schéma initial | 1/3 valide | Une citation non structurée ; une sortie atteint 2 048 tokens sans fermer le JSON. |
| Motif régulier borné | Interrompu avant la première sortie | Saturation d’un cœur CPU dans le parcours de l’arbre des tokens pendant environ 96 minutes. Variante abandonnée. |
| Bornes natives seules | 2/3 valides | JSON analysable mais guillemets interdits dans un bloc de `democratie-05`. |
| Bornes natives + filtre de tokens | **3/3 valides** | Pilote autorisant la campagne complète, sans changement du prompt. |

Les essais sont distincts : `pilot-schema-v1/`, `pilot-schema-v2-interrupted/`, `native/`, `guarded/`, sous `evaluation/local/rag023/`. Les trois échecs historiques RAG-022 restent intacts.

Le pilote final accepte `democratie-05`, `fiscalite-04`, `services_publics-03` en 17,8 s, 15,8 s et 36,2 s. Chargement : 17,29 s ; durée totale du pilote : 87,67 s ; pic VRAM allouée : 13,99 Go décimaux, réservée : 14,04 Go ; pic RSS : 5,41 Go. Le pilote est réutilisé dans les vingt résultats, sans inférence supplémentaire pour ces trois requêtes.

## Campagne de développement

| Indicateur | RAG-022 v2 | RAG-023 contraint |
|---|---:|---:|
| JSON analysables | 19 | 20 |
| Contrat accepté | 17 | 20 |
| Blocs | 90 | 79 |
| Blocs avec champs exacts | 83 | 79 |
| Références extraites | 338 | 198 |
| Références inconnues | 0 | 0 |
| Références dupliquées dans un bloc | 0 | 0 |
| Tokens générés | 9998 | 13585 |
| Mots des blocs analysables | 2745 | 5545 |
| Insuffisances déclarées | 0 | 0 |
| Latence médiane (s) | 11.07 | 27.90 |
| Latence P95 (s) | 13.52 | 31.97 |
| Somme des latences (s) | 225.63 | 517.11 |
| Sources distinctes par réponse (médiane) | 10.0 | 9.0 |
| Contributions distinctes par réponse (médiane) | 10.0 | 9.0 |
| Tokens de sortie / seconde (temps cumulé par requête) | 44.31 | 26.27 |

Les vingt requêtes sont appariées. Les statistiques de blocs et références portent sur les JSON analysables ; une sortie non analysable ne permet pas de les extraire. Les mots sont comptés par séquences alphanumériques Unicode, sans jugement de qualité.

Entrée : **100601 tokens**, identiques à v2. Citations littérales : **0**, dont **0** exactes. Réponses utilisant au moins un extrait incomplet : **2**. Sorties ayant atteint le plafond de tokens : **0**. Blocs atteignant la borne de 600 caractères : **20** (à inspecter pour les fins de phrase).

| Requête | v2 | Contraint | Tokens contraints | Latence (s) | Sources distinctes |
|---|---|---|---:|---:|---:|
| democratie-01 | valid | valid | 734 | 29.91 | 8 |
| democratie-02 | valid | valid | 508 | 18.76 | 8 |
| democratie-03 | valid | valid | 749 | 27.76 | 12 |
| democratie-04 | valid | valid | 721 | 28.03 | 4 |
| democratie-05 | invalid | valid | 417 | 17.77 | 10 |
| ecologie-01 | valid | valid | 788 | 30.51 | 6 |
| ecologie-02 | valid | valid | 453 | 16.06 | 11 |
| ecologie-03 | valid | valid | 741 | 27.66 | 10 |
| ecologie-04 | valid | valid | 800 | 30.21 | 9 |
| ecologie-06 | valid | valid | 521 | 19.73 | 7 |
| fiscalite-01 | valid | valid | 762 | 28.56 | 12 |
| fiscalite-02 | valid | valid | 841 | 31.45 | 11 |
| fiscalite-03 | valid | valid | 592 | 22.44 | 8 |
| fiscalite-04 | invalid | valid | 414 | 15.81 | 8 |
| fiscalite-05 | valid | valid | 845 | 31.97 | 12 |
| services_publics-01 | valid | valid | 782 | 29.65 | 10 |
| services_publics-02 | valid | valid | 559 | 21.23 | 6 |
| services_publics-03 | invalid | valid | 942 | 36.19 | 9 |
| services_publics-04 | valid | valid | 779 | 29.85 | 9 |
| services_publics-06 | valid | valid | 637 | 23.53 | 9 |

### Temps et ressources

| Phase mesurée | Médiane (s) | Somme (s) |
|---|---:|---:|
| grammar_seconds | 0.0004 | 0.0091 |
| tokenizer_preparation_seconds | 0.0000 | 4.8435 |
| prefill_seconds | 0.7366 | 15.9799 |
| generate_seconds | 27.6247 | 510.6451 |
| decode_and_loop_seconds | 26.7712 | 494.6652 |
| callback_wall_seconds | 5.3686 | 101.2081 |
| validation_seconds | 0.0004 | 0.0077 |

Le temps de callback est inclus dans `generate_seconds` et peut inclure des synchronisations : ne pas additionner ces deux mesures. `prefill_seconds` mesure le premier forward ; la compilation du parseur et la construction de l’arbre du tokenizer sont séparées. La référence v2 n’ayant pas cette instrumentation détaillée, le surcoût pur du décodeur n’est pas directement isolable.

- pilot : chargement 17.29 s ; exécution 87.67 s ; pic RSS 5.41 Go ; VRAM allouée 13.99 Go, réservée 14.04 Go. 3 nouvelles inférences, 0 résultats réutilisés.

- development : chargement 17.15 s ; exécution 465.65 s ; pic RSS 5.53 Go ; VRAM allouée 13.99 Go, réservée 14.04 Go. 17 nouvelles inférences, 3 résultats réutilisés.

### Différences observables

20/20 sorties brutes diffèrent ; 19 réponses analysables des deux côtés ont des textes de blocs différents. 20 requêtes changent les références utilisées. Les différences détaillées de références, mots, tokens et latences figurent dans le JSON ; elles ne constituent pas une évaluation sémantique.

Rapport local : `evaluation/local/rag023/guarded/reports/f69e9af4e4e497134a3cdcf1c8aea2825040f1da1c841c4f3b2352fada9f85fa/comparison.json`. Sorties brutes et correspondances complètes : `evaluation/local/rag023/guarded/reports/f69e9af4e4e497134a3cdcf1c8aea2825040f1da1c841c4f3b2352fada9f85fa/answers.json`. Validation et reprise : `evaluation/local/rag023/validation.json`. Aucun texte citoyen n’est reproduit ici.

La reprise sur copie du cache réutilise les **20 résultats**, sans charger le modèle et sans nouvelle inférence. Le rapport régénéré est identique. Les **1 450 fichiers historiques** surveillés restent inchangés après la campagne.

## Reprise et audit

Le cache final est `evaluation/local/rag023/guarded/generation.sqlite3`. Chaque tentative et checkpoint sont écrits atomiquement par requête ; les réponses existantes ne sont pas recalculées par défaut, y compris les réponses invalides. Une interruption avant commit nécessite de reprendre la requête courante ; les états internes du modèle ne sont pas persistés par token.

Le plan contient les paramètres, schémas, empreintes, versions et une copie du code. Les sorties brutes et tables de citations complètes restent dans les artefacts locaux ignorés par Git. Le rapport statistique ne reproduit pas de propos citoyens.

Depuis `rag/` :

```sh
UV_PROJECT_ENVIRONMENT=.cache/judges-venv uv sync --locked --inexact --extra judges --extra constrained
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .cache/judges-venv/bin/python \
  -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/guarded/plan run --stage development
.venv/bin/python -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/guarded/plan report
watch -n 5 cat evaluation/local/rag023/guarded/plan/development-progress.json
```

Ne pas exécuter `prepare` sur le plan existant. Pour une nouvelle expérience, utiliser un nouveau répertoire ; les commandes détaillées figurent dans [decodage-contraint.md](decodage-contraint.md).

## Tests et limites

**545 tests réussis, 3 ignorés**, avec les bases PostgreSQL de test configurées ; les trois tests ignorés nécessitent PyTorch dans l’environnement léger. Les 19 tests spécifiques couvrent le parseur réel, les références, Unicode, contraintes non garanties, sorties interrompues, reprises simulées, cache, rapport reproductible et filtre de tokens. Ruff et `uv lock --check` passent.

Un inventaire SHA-256 vérifie la conservation de **1 450 fichiers historiques**, dont les contextes, annotations, caches et fichiers du backend. Aucun fichier historique surveillé n’a changé lors du contrôle réalisé après les pilotes. Aucun commit ou push.

La validation structurelle ne prouve pas l’étayage des affirmations, la justesse des attributions, la présentation des contradictions ou la reconnaissance d’une insuffisance documentaire. RAG-024 doit inspecter ces dimensions, ainsi que les effets rédactionnels des bornes et du filtre. Aucun juge supplémentaire ou score de qualité automatique n’a été introduit.

## Recommandation pour RAG-024

Conserver cette recette comme **expérience structurellement validée sur les vingt requêtes**, sans la promouvoir automatiquement en recette de meilleure qualité. Le passage de 17/20 à 20/20 est observé, pas une garantie universelle : une interruption, une limite de tokens ou une contrainte non prise en charge peuvent encore échouer.

L’inspection sémantique doit notamment vérifier les attributions, contradictions, insuffisances non reconnues et les deux réponses utilisant des extraits incomplets. Examiner en priorité les **20 blocs sur 79 arrivant exactement à 600 caractères**, leurs fins de phrase et les sources retirées par rapport à v2. Le plafonnement à trois références par bloc réduit aussi le nombre de références citées ; ce n’est pas une preuve de moindre ou meilleure fidélité. Les 0 citations littérales produites ne permettent pas de mesurer leur exactitude sur les réponses réelles ; ce contrôle est vérifié sur des exemples synthétiques.

La longueur augmente malgré les bornes plus strictes : les mots des blocs analysables passent de 2 745 à 5 545 et les tokens de sortie de 9 998 à 13 585. La médiane des sources distinctes passe de 10 à 9. Ces changements de contenu et le filtre supplémentaire empêchent d’isoler parfaitement l’effet du seul décodeur. Le callback cumule environ 101,2 secondes, incluses dans le temps de génération ; XGrammar reste une piste future si ce coût ou les contraintes rédactionnelles deviennent limitants, sans compatibilité locale présumée.

Aucune réponse n’a été notée automatiquement pour sa qualité. Les vingt sorties restent disponibles pour l’inspection documentaire, avec leurs références complètes, dans les artefacts privés. Les annotations humaines et LLM historiques, requêtes réservées, moteurs, backend public et Wallace restent hors de cette expérience.
