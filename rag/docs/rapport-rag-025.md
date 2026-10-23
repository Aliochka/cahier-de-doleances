# RAG-025 — Génération améliorée et interface personnelle

## Résultat

Le RAG personnel est utilisable localement pour des **questions libres sur les 20 000 unités RAG-007**. La chaîne réelle H1 → Qwen3-Reranker-4B → S2/P1/8192 → Qwen3-14B a été testée par HTTP, avec affichage des sources. Le serveur de test a ensuite été arrêté.

La recette retenue, **`generation-fr-v6-personal` en génération directe**, produit **20/20 réponses structurellement valides**, sans les fins forcées à 600 caractères. Elle améliore plusieurs erreurs ciblées de RAG-024, mais **ne garantit pas la fidélité documentaire** : omissions, conditions perdues et réserves génériques persistent. Elle est destinée à un usage personnel avec vérification des passages, pas à une publication automatique.

Pour démarrer et arrêter : [personnel.md](personnel.md). Aucun moteur, index, contexte historique, jugement, modèle ou composant du site public n’est modifié.

## Recette et contraintes

Même Qwen3-14B, révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, NF4/BF16, RTX 5090, Transformers 4.57.6, graine 42, mode non-thinking et génération gloutonne. Maximum **4 096 tokens générés** ; le prompt complet avec gabarit est compté sans troncature, plafond d’entrée 24 576 et fenêtre totale 32 768. Une pénalité de répétition de **1,05**, enregistrée dans la recette, complète les instructions de brièveté.

Le prompt demande une idée principale et deux phrases courtes par bloc, avec une ou deux références directement utiles. Il distingue soutien/opposition/réserve, baisse/suppression/compensation/remplacement, objet des chiffres, conditions, opinion rapportée et fait établi. Il interdit les arguments absents, les absences fictives et les généralisations représentatives. L’analyse intermédiaire éventuelle est présentée comme faillible, jamais comme une nouvelle source.

**XGrammar 0.2.8** remplace LM Format Enforcer pour cette nouvelle recette seulement. Son intégration Transformers par `LogitsProcessor` est [documentée officiellement](https://xgrammar.mlc.ai/docs/latest/start/quick_start.html). Le schéma impose JSON, champs, types, références connues et ponctuation finale des paraphrases/limites, **sans borne de caractères qui force leur fermeture**. Le validateur RAG-022 reste inchangé ; un contrôle supplémentaire refuse les fins inachevées et les sorties atteignant la limite de tokens. Une phrase ponctuée peut néanmoins être maladroite ou inexacte.

Le filtre global de tokens RAG-023 est supprimé : la restriction des guillemets est portée par les champs de paraphrase du schéma. Les sources originales ne sont jamais filtrées. Les garde-fous de longueur du validateur historique restent des motifs de refus, pas des mécanismes de coupe. Aucune fermeture automatique, suppression de passage ou réparation silencieuse d’une sortie invalide.

L’extra uv **`personal`** ajoute uniquement `xgrammar==0.2.8` et `apache-tvm-ffi==0.1.12` ; **aucune version déjà verrouillée n’est mise à jour**. Les dépendances lourdes restent optionnelles et ne sont pas imposées aux tests légers, au lexical, à l’annotation ou au backend public. Aucun modèle téléchargé, service d’inférence supplémentaire ou framework agentique.

## Pilotes et comparaison des deux méthodes

Les quatre cas P0 sont `democratie-04`, `democratie-05`, `fiscalite-03`, `fiscalite-05`. Les essais restent séparés et bruts :

- `direct-no-filter/` : premier échec technique, CUDA indisponible dans l’exécution initiale isolée ; aucun résultat valide.
- `direct-pilot/` : variante LMFE v4 à grandes bornes, trois sorties invalides conservées ; quatrième calcul interrompu. Un cas atteint 4 096 tokens avec répétitions. Augmenter les bornes seul ne suffit donc pas.
- `xgrammar-direct/` : variante directe v5, **4/4 valides**, 9,25 à 11,53 s de génération.
- `xgrammar-two-step/` : première analyse exigeant des preuves littérales exactes ; **4/4 analyses refusées**, certaines citations reproduites approximativement. Elles n’ont pas été réparées ni utilisées en synthèse.
- `two-step-v6/` : nouvelle analyse structurée par `reference`, `stance`, `statement`, `conditions`, puis synthèse avec **toutes les sources originales**. **4/4 chaînes valides**. Les références sont vérifiées, pas la vérité des paraphrases intermédiaires.
- `direct-v6/` : nouvelle version cohérente avec le contrat intermédiaire ; pilote **4/4 valide**. Ses quatre sorties directes sont identiques aux sorties directes v5 : le changement de contrat d’analyse n’a pas changé leur prompt de synthèse.

| Cas | Directe, génération (s) | Analyse + synthèse (s) |
|---|---:|---:|
| `democratie-04` | 11,16 | 31,23 |
| `democratie-05` | 9,39 | 24,08 |
| `fiscalite-03` | 11,13 | 21,71 |
| `fiscalite-05` | 9,23 | 29,11 |

Hors chargement et préparation. L’analyse puis synthèse formule clairement la réserve sur l’ISF et explicite une voie de pétition parlementaire. Elle tend toutefois à énumérer les premières sources, ne rétablit pas la variante S17 du vote blanc et ne préserve pas toutes les conditions de la TVA. **Gain ponctuel, sans bénéfice suffisant pour doubler ou tripler le coût personnel.** La méthode directe a été sélectionnée et figée **avant** les seize autres générations. L’option deux étapes reste un outil expérimental, pas le chemin de l’interface.

Gel : `evaluation/local/rag025/direct-v6/recipe.json` et `selection.json`, sélection personnelle dans `evaluation/local/rag025/selected.json`. Les copies de code des premiers pilotes et leurs caches restent disponibles ; aucune variante antérieure n’est remplacée.

## Campagne des vingt requêtes

Les vingt requêtes de développement réutilisent exactement leurs entrées documentaires RAG-022 ; aucune recherche, aucun reranking ni assemblage historique n’est relancé. Les quatre résultats pilotes sont réutilisés.

| Mesure | RAG-022 v2 | RAG-023 v3 | RAG-025 directe v6 |
|---|---:|---:|---:|
| Contrat accepté | 17/20 | 20/20 | **20/20** |
| Latence médiane de génération (s) | 11,07 | 27,90 | **10,23** |
| P95 (s) | 13,52 | 31,97 | **11,52** |
| Tokens de sortie, 20 tentatives | 9 998 | 13 585 | **8 858** |
| Références extraites | 338 | 198 | **134** |
| Blocs exactement à 600 caractères | — | 20 | **0** |

Les références historiques sont comptées sur leurs JSON analysables, dont deux sorties v2 rejetées pour schéma. Leur quantité n’est pas un indicateur de qualité. Les chronométrages historiques n’incluent pas exactement les mêmes préparations ; prompt, longueur et pénalité changent aussi. Ces résultats **n’isolent pas le seul effet du décodeur**.

V6 : **120 blocs**, au plus **180 caractères observés**, **2 226 mots**, phrases ponctuées, aucune référence inconnue et aucune sortie au plafond de tokens. Il n’existe pas de plafond à 180 caractères : c’est le comportement observé. L’indicateur d’insuffisance reste toujours `false` ; cela ne prouve pas la complétude des réponses.

GPU : pic alloué **13,99 Go**, chargements **16,36–16,63 s**. Somme des vingt temps de génération **202,76 s**, compilation des grammaires environ **1,00 s** en plus, pic RSS du processus de campagne **5,70 Go**. Quatre générations viennent du pilote, seize de la campagne. Mesures propres au PC local.

Détails par requête et paramètres : `evaluation/local/rag025/validation.json`. Sorties brutes, prompts, recettes et checkpoints : `direct-v6/generation.sqlite3` et `development-results.json`.

## Vérification ciblée A01–A13

Lecture assistée par Codex des passages concernés et de leurs sources ; **pas une validation humaine indépendante ni un score global**. Les réponses complètes, références et observations restent dans `evaluation/local/rag025/targeted-review.json`.

| Cas RAG-024 | Observation sur v6 |
|---|---|
| **A01 — ISF** | La réserve S02 est rapportée dans le bon sens, sans la présenter comme un soutien au rétablissement. Une autre attribution, sur la progressivité associée à S05, reste discutable. |
| **A02 — TVA** | Le remplacement de toute la TVA n’est plus affirmé ; la compensation par l’IR est associée à S11. **La condition de S01 sur les importations également produites en France est encore perdue.** |
| **A03 — pétition** | Aucun seuil de candidature n’est transféré à l’initiative législative. La distinction RIC/candidature est mieux conservée. Un qualificatif ajouté sur les candidats reste plus précis que la source. |
| **A04 — vote blanc** | Aucun cycle illimité n’est attribué à S17 ; **sa variante est omise**. L’inversion n’est pas reproduite, mais la couverture des conditions n’est pas corrigée intégralement. |
| **A05 — bonnes références** | GAFA/exilés maintenant cités avec S05 ; le terme de sanction ajouté dépasse néanmoins cette proposition de taxation. Correction seulement partielle. |
| **A06 — détails ajoutés** | Contrôles rattachés à S02 ; les moyens administratifs et amendes spécifiques non soutenus de v3 ne sont plus ajoutés. |
| **A07 — opinions devenant constats** | **Persiste**, notamment `ecologie-01` B1. L’interface rappelle le statut d’opinions rapportées, mais ne transforme pas ce rappel en preuve de fidélité. |
| **A08 — divergences numériques** | La réserve de S05 sur le contact physique est restituée dans `services_publics-06` ; l’opposition plus radicale de S08 reste omise. |
| **A09 — international** | La contribution carbone internationale S01 est décrite ; la fausse absence correspondante n’est plus déclarée. |
| **A10 — patrimoine** | Les mesures patrimoniales sont reconnues ; aucune absence générale de mesures spécifiques n’est affirmée. |
| **A11 — existence des MSAP** | L’absence d’information sur leur existence n’est plus inventée ; une réserve générique sur leur financement reste sans attribution précise. |
| **A12 — mécanismes législatifs** | Plus de déclaration globale d’absence de mécanisme ; la réponse reste parfois un catalogue avec des propositions périphériques. |
| **A13 — opposition au RIC** | L’incapacité des citoyens n’est plus attribuée aux opposants, mais **leurs positions S03/S11/S18 disparaissent de la synthèse** : régression de diversité par rapport à v2/v3. |

Des limites documentaires artificielles subsistent ailleurs : `democratie-01` qualifie notamment le financement des partis par l’impôt d’idée non développée, malgré les détails de S16. La brièveté et les références individuelles réduisent certains blocs composites, **sans garantir que chaque proposition soit soutenue**.

Ces défauts ne sont pas corrigés après observation de la campagne figée. Ils doivent rester visibles : l’amélioration de lisibilité est nette ; la fidélité sémantique reste partielle et dépend de la vérification des passages. Pour la suite, les conditions omises, les oppositions et les limites inventées sont plus utiles à traiter qu’un nouveau benchmark global.

## Interface libre et exécution réelle

Nouveau package `cahier_rag.personal` : contrats/prompt, backend contraint, cache et campagnes, orchestration libre, CLI et interface FastAPI/HTML/JS/CSS. Aucun framework frontend. Les imports lourds restent paresseux.

La recherche libre couvre exactement les 20 000 unités. Le lexical utilise le périmètre complet ; BGE-M3 encode la question une fois, recherche les deux partitions documentaires et réunit les résultats en top 50 global. La fusion H1 utilise RRF `k=60`. Les sources, identifiants BIGINT et scores restent traçables. **Aucun catalogue de requêtes expérimentales n’est chargé par la chaîne libre.**

Le reranker R2 existant est appliqué par lots de quatre segments, budget 1 024 tokens, chevauchement 128 caractères, agrégation maximale. L’assembleur libre réutilise les primitives RAG-021 pour S2/P1/8192, avec métadonnée explicite `personal-free-query` plutôt qu’une fausse partition de développement. Les modèles sont libérés successivement pour maîtriser la VRAM.

**Test HTTP réel réussi** sur une question nouvelle relative à l’accueil humain dans les démarches administratives :

- Périmètre contrôlé : **20 000 unités** ; vingt sources sélectionnées, dont **18 documents de développement et 2 d’évaluation**. Ce sont des partitions documentaires, aucune requête réservée n’a été exécutée.
- Recherche et chargement : **18,94 s** ; reclassement et chargement : **16,12 s** ; chaîne complète à froid : **76,16 s**, contexte et chargement du générateur compris.
- Synthèse et sources consultables via l’API locale ; l’application signale son caractère expérimental et les extraits incomplets. Le serveur temporaire est arrêté après validation.

Le premier démarrage révélait une dépendance transitive web absente de l’environnement GPU ; les dépendances de l’extra `annotation` ont été installées depuis le verrou, sans mise à jour de versions existantes. Aucun nouveau modèle.

Écoute imposée à **127.0.0.1:8770**, vérifications Host/Origin/Fetch-Site et jeton de session pour les écritures. Les contenus passent par `textContent`, jamais par du HTML injecté ; aucun contenu documentaire journalisé. Une seule requête GPU à la fois, erreurs explicites, résultats invalides conservés mais non présentés comme validés. Les sources originales, métadonnées et synthèse restent séparées.

## Validation et limites pratiques

- **557 tests réussis, 3 ignorés** : les ignorés sont les tests PyTorch optionnels dans l’environnement léger. Dix tests ajoutés : fins incomplètes, références, analyse/sources originales, reprise et cache, sorties invalides, partitions documentaires et BIGINT, questions libres, sécurité locale et erreurs.
- Vérification réelle de la grammaire sur tokenizer Qwen : Unicode et texte de plus de 600 caractères acceptés ; phrase inachevée et référence inconnue rejetées.
- Rejeu sur une copie du cache : **20 résultats réutilisés, aucun modèle chargé**.
- `ruff check`, formatage des nouveaux fichiers, JavaScript syntaxique et `uv lock --check` conformes. Le contrôle global de formatage signale **quatre fichiers historiques inchangés** : `recherche-hybride.md`, `judges/evaluation.py`, `judges/markdown.py`, `tests/unit/test_bm25.py`. Ils ne sont pas reformattés pour préserver les expériences. Installation légère séparée : **8 tests réussis, 2 tests web ignorés**, sans PyTorch, Transformers, FastAPI ou XGrammar ; ressources HTML/JS/CSS présentes dans la distribution.
- **1 450 fichiers historiques surveillés inchangés**, empreintes des entrées RAG-024 toujours conformes ; aucun paquet déjà verrouillé mis à jour. Les anciens fichiers de dépendances sont archivés pour les validateurs historiques qui refusent un environnement modifié.
- Les données personnelles et sorties restent sous `evaluation/local/rag025/`, ignorées par Git et avec permissions restrictives.

L’interface n’est pas une conversation multi-tour : chaque question est indépendante. Les questions éloignées du corpus peuvent obtenir des documents voisins peu utiles. La sélection des premiers extraits des réponses longues reste celle des primitives existantes, pas une recherche des meilleurs passages. La ponctuation finale ne détecte ni mauvais sens, ni condition omise, ni limite inventée. Aucun score automatique de qualité ne masque ces limites.

Aucun changement des moteurs/index, annotations, modèles d’embedding, sources PostgreSQL, backend/frontend publics ou Wallace. Aucun commit ni push. Les instructions de lancement, d’arrêt et de reprise sont dans [personnel.md](personnel.md).
