# RAG-021 — Construction du contexte documentaire

## Résultat

Un assembleur documentaire indépendant est disponible sous `src/cahier_rag/context/`. Il réutilise les top 50 gelés RAG-020, sans relancer les modèles. Les essais réels ont produit **420 contextes** : trois classements × sept configurations × vingt requêtes de développement. Les 20 requêtes réservées restent non exécutées.

Les vérifications ont contrôlé **8 370 blocs sources** : textes exacts, positions, références, rangs, contributions, questionnaires, partitions et budgets. Aucun texte citoyen n’est reproduit dans ce rapport. Il ne contient aucune mesure de qualité d’une future réponse générée.

## 1. Contrat et modules

| Module | Responsabilité |
|---|---|
| `contracts.py` | `ContextConfig` figée, `ContextSource` distinct de `TextUnit` |
| `assembly.py` | Sélection, extraits, JSON du futur modèle, citations et bilan de budget |
| `repository.py` | Lecture locale contrôlée, liens parentaux réels et périmètre RAG-007 |
| `tokenization.py` | Tokenizer Rust local, aucun poids ni import GPU |
| `experiments.py` | Protocole figé, vérification des classements RAG-020, traitement progressif et statistiques |
| `validation.py` | Vérification indépendante des artefacts et des sources originales |
| `cli.py` | Gel, construction, inspection statistique et vérification |

Chaque source sépare `citizen_text`, `metadata` et `technical`. Le texte est une portion exacte du texte consultable normalisé RAG-004, pas une reconstruction du JSON brut de 2019. La question, le questionnaire, le titre éventuel, les identifiants internes/externes, les positions, la méthode, le rang et l’empreinte sont conservés. Les BIGINT restent des entiers Python dans `TextUnit` et des chaînes décimales en JSON.

Référence stable : `context-source:v1:SHA256([sample_hash, document_id, start, end])`. La table `citation_map` relie chaque référence à une unité réelle et un extrait `[start,end)` en points de code Unicode. Des contributions distinctes gardent leurs identités même si leurs réponses sont identiques. Les champs `omitted_ranges` montrent explicitement ce qui n’est pas transmis.

`public_url` reste `null` ; `link_target` expose contribution, question, réponse et corpus pour une résolution publique ultérieure. Aucun ID de réponse n’est interprété comme une URL. La table de citations reste hors bande ; chaque bloc du futur modèle contient sa référence. Aucun contrat RAG-004, moteur ou index n’a été modifié.

## 2. Sélection et expansion

- **S1** : premiers rangs, jusqu’au budget ou au plafond de vingt sources principales.
- **S2** : au plus une source principale par contribution, en conservant les exclusions et leurs rangs.
- **S3** : suppression locale des répétitions à question identique. Comparaison exacte, égalité de mots NFKC/casefold, puis Jaccard ≥0,90 et ratio de longueurs ≥0,90 sur au moins huit mots. Des négations ou nombres différents bloquent la comparaison approchée. Aucune de ces normalisations ne modifie le texte exporté.
- **P0** : réponse/référence seules dans le JSON du modèle ; provenance complète hors bande.
- **P1** : question, questionnaire et titre éventuel de la réponse sélectionnée.
- **P2** : P1 et au plus deux voisins structurels par source, même corpus/contribution/questionnaire. Réserve d’expansion de 20 % ; 80 % du plafond disponible pour les principales. Compléments marqués explicitement, sans rang direct, jamais doublés avec une source déjà présente.

Les occurrences S3 restent attachées à des documents et contributions distincts : aucune source citoyenne composite. Le nombre d’occurrences porte sur le préfixe de candidats examiné, pas sur la population, le corpus entier, ni nécessairement tout le top 50. Les répétitions entre questions différentes ne sont pas éliminées : « oui » peut répondre à des demandes différentes.

Les parents sont disponibles par les identifiants réels des `TextUnit`. Politique conservée de RAG-011 : **RAG-007 sélectionné seulement, développement seulement**. La copie SQLite documentaire RAG-018 est lue en mode strictement read-only ; empreintes vérifiées contre le manifeste. Aucun accès à la base source. Les autres unités du cadre de 42 318 documents ne sont pas utilisées. Les contributions parentes peuvent donc être incomplètes.

## 3. Tokenizer et budgets

Tokenizer réel réutilisé : `Qwen/Qwen3-Reranker-4B`, révision `22e683669bc0f0bd69640a1354a6d0aebcfeede5`, avec contrôle du manifeste RAG-020 et SHA-256. `tokenizers` est importé directement depuis l’environnement existant ; ni poids, ni PyTorch, ni Transformers, ni GPU, ni téléchargement supplémentaire nécessaires à l’assemblage. Aucune dépendance ou verrou n’est modifié.

Comptage du **JSON canonique exact** destiné au modèle : Unicode conservé, échappements JSON réels, sans tokens spéciaux, padding, troncature ou gabarit de chat. Le budget documentaire inclut références et métadonnées présentes dans ce JSON. Le coût hors texte est recompté avec les réponses vidées ; la différence donne l’apport des textes, sans supposer que des tokenizations séparées s’additionnent.

Réserves distinctes : **512 instructions + 1 024 réponse future + 128 enveloppe**, auxquels s’ajoutent les tokens de la requête. Aucun prompt génératif complet n’est produit. Le futur modèle devra recompter son prompt et son gabarit réels ; ce tokenizer est une référence expérimentale, pas le choix du futur LLM.

Réponses longues : premier extrait de 768 tokens maximum, avec préférence pour une frontière de phrase/paragraphe, puis réduction explicite au budget restant si nécessaire. Minimum pour un extrait réduit : 32 tokens, ou toute la réponse si elle est plus courte. Le premier document long n’est pas sauté au profit d’un document court moins bien classé. La segmentation est sans chevauchement et reconstruit l’original par concaténation ; l’assembleur utilise pour l’instant seulement le premier segment. Toutes les plages omises restent identifiables.

## 4. Protocole et résultats structurels

Protocole figé : `57b4d985a53c22519f9ee512ffb4118313fdc82f6c088d38eb21262139074a4c`.

Sept configurations prédéfinies : S1/P1/8192, S2/P1/8192, S3/P1/8192 ; puis S2/P0/8192 et S2/P2/8192 ; puis S2/P1/4096 et S2/P1/16384. Ce protocole progressif évite les 27 combinaisons complètes et **ne permet pas d’estimer toutes leurs interactions**. Aucun jugement LLM ou humain n’a été utilisé, même pour choisir les documents.

Moyennes par contexte sur les 20 requêtes ; H1+R2 = Qwen reranker, H1+R1 = BGE reranker, V = BGE-M3 seul.

| Classement / configuration | Principales | Contributions | Compléments | Tokens | Occupation | Écartées budget |
|---|---:|---:|---:|---:|---:|---:|
| H1+R1 / S1-P1-8192 | 18.70 | 18.20 | 0.00 | 6643 | 81.1% | 13.30 |
| H1+R1 / S2-P0-8192 | 19.20 | 19.20 | 0.00 | 5817 | 71.0% | 8.15 |
| H1+R1 / S2-P1-16384 | 20.00 | 20.00 | 0.00 | 7343 | 44.8% | 0.00 |
| H1+R1 / S2-P1-4096 | 12.10 | 12.10 | 0.00 | 4044 | 98.7% | 34.70 |
| H1+R1 / S2-P1-8192 | 18.65 | 18.65 | 0.00 | 6648 | 81.2% | 13.15 |
| H1+R1 / S2-P2-8192 | 17.30 | 17.30 | 7.75 | 7519 | 91.8% | 17.50 |
| H1+R1 / S3-P1-8192 | 18.70 | 18.20 | 0.00 | 6701 | 81.8% | 13.30 |
| H1+R2 / S1-P1-8192 | 19.80 | 19.50 | 0.00 | 6055 | 73.9% | 3.20 |
| H1+R2 / S2-P0-8192 | 20.00 | 20.00 | 0.00 | 4975 | 60.7% | 0.00 |
| H1+R2 / S2-P1-16384 | 20.00 | 20.00 | 0.00 | 6167 | 37.6% | 0.00 |
| H1+R2 / S2-P1-4096 | 13.85 | 13.85 | 0.00 | 4032 | 98.4% | 34.55 |
| H1+R2 / S2-P1-8192 | 19.85 | 19.85 | 0.00 | 6054 | 73.9% | 3.10 |
| H1+R2 / S2-P2-8192 | 19.10 | 19.10 | 8.05 | 7282 | 88.9% | 6.80 |
| H1+R2 / S3-P1-8192 | 19.80 | 19.50 | 0.00 | 6047 | 73.8% | 3.20 |
| V / S1-P1-8192 | 19.90 | 19.60 | 0.00 | 4440 | 54.2% | 1.60 |
| V / S2-P0-8192 | 20.00 | 20.00 | 0.00 | 3355 | 41.0% | 0.00 |
| V / S2-P1-16384 | 20.00 | 20.00 | 0.00 | 4524 | 27.6% | 0.00 |
| V / S2-P1-4096 | 17.85 | 17.85 | 0.00 | 3837 | 93.7% | 17.00 |
| V / S2-P1-8192 | 19.90 | 19.90 | 0.00 | 4479 | 54.7% | 1.60 |
| V / S2-P2-8192 | 19.70 | 19.70 | 8.40 | 5951 | 72.6% | 3.20 |
| V / S3-P1-8192 | 19.90 | 19.65 | 0.00 | 4485 | 54.8% | 1.60 |

Le plafond de vingt principales explique l’occupation faible à 16 384 tokens : une fenêtre plus grande ne force pas à ajouter des documents. La réserve P2 inutilisée n’est pas réaffectée aux principales. Les documents écartés pour budget incluent les rangs restants non examinés après l’arrêt, pas des documents déclarés non pertinents.

### Diversité et longueurs

| Classement / configuration | Courtes <60 car. | Longues >2 000 car. | Questions | Questionnaires | Répétitions exactes principales | Répétitions S3 écartées |
|---|---:|---:|---:|---:|---:|---:|
| H1+R1 / S1-P1-8192 | 1.95 | 3.20 | 5.85 | 2.10 | 0.30 | 0.00 |
| H1+R1 / S2-P0-8192 | 2.05 | 3.50 | 6.00 | 2.15 | 0.30 | 0.00 |
| H1+R1 / S2-P1-16384 | 2.05 | 3.60 | 6.20 | 2.20 | 0.30 | 0.00 |
| H1+R1 / S2-P1-4096 | 1.45 | 1.95 | 4.60 | 1.65 | 0.30 | 0.00 |
| H1+R1 / S2-P1-8192 | 1.95 | 3.20 | 5.85 | 2.10 | 0.30 | 0.00 |
| H1+R1 / S2-P2-8192 | 1.95 | 2.65 | 5.60 | 2.00 | 0.30 | 0.00 |
| H1+R1 / S3-P1-8192 | 1.65 | 3.25 | 5.95 | 2.15 | 0.00 | 0.50 |
| H1+R2 / S1-P1-8192 | 1.65 | 1.65 | 5.60 | 1.85 | 0.05 | 0.00 |
| H1+R2 / S2-P0-8192 | 1.65 | 1.75 | 5.60 | 1.85 | 0.05 | 0.00 |
| H1+R2 / S2-P1-16384 | 1.65 | 1.75 | 5.60 | 1.85 | 0.05 | 0.00 |
| H1+R2 / S2-P1-4096 | 1.05 | 0.95 | 4.40 | 1.55 | 0.00 | 0.00 |
| H1+R2 / S2-P1-8192 | 1.65 | 1.70 | 5.60 | 1.85 | 0.05 | 0.00 |
| H1+R2 / S2-P2-8192 | 1.60 | 1.45 | 5.40 | 1.75 | 0.05 | 0.00 |
| H1+R2 / S3-P1-8192 | 1.65 | 1.65 | 5.60 | 1.85 | 0.00 | 0.10 |
| V / S1-P1-8192 | 5.75 | 0.40 | 5.05 | 1.65 | 0.50 | 0.00 |
| V / S2-P0-8192 | 5.75 | 0.45 | 5.10 | 1.70 | 0.50 | 0.00 |
| V / S2-P1-16384 | 5.75 | 0.45 | 5.10 | 1.70 | 0.50 | 0.00 |
| V / S2-P1-4096 | 5.30 | 0.30 | 4.80 | 1.65 | 0.45 | 0.00 |
| V / S2-P1-8192 | 5.75 | 0.45 | 5.05 | 1.70 | 0.50 | 0.00 |
| V / S2-P2-8192 | 5.70 | 0.40 | 5.00 | 1.70 | 0.45 | 0.00 |
| V / S3-P1-8192 | 5.35 | 0.40 | 5.15 | 1.70 | 0.00 | 0.90 |

Les colonnes de longueur portent sur les réponses sources complètes, même lorsqu’un extrait seulement est transmis.

S2 apporte un gain modeste de contributions distinctes dans ces listes ; S3 retire peu de répétitions, notamment parce que les réponses identiques à des questions différentes sont conservées. P2 augmente le contexte structurel, mais peut remplacer une partie des principales par des voisins dont la pertinence n’est pas présumée. Le vectoriel présente davantage de réponses courtes que les deux classements reclassés, sans que ce constat mesure une qualité de génération.

### Coût documentaire et coût de préparation

Premier essai complet : **118.20 s**, pic RSS **241.6 Mo**, JSONL **30.20 Mo** (unités décimales). Mesures locales incluant lecture et tokenization ; pas un benchmark isolé de production. Les premiers lots ont coïncidé avec l’exécution des tests.

| Classement / configuration | Métadonnées/références (tokens) | Expansion (tokens) | Temps moyen (ms) | Médiane/P95 (ms) |
|---|---:|---:|---:|---|
| H1+R1 / S1-P1-8192 | 2850 | 0 | 181.0 | 120.1/347.1 |
| H1+R1 / S2-P0-8192 | 1780 | 0 | 149.2 | 107.7/308.5 |
| H1+R1 / S2-P1-16384 | 3054 | 0 | 149.4 | 113.7/303.3 |
| H1+R1 / S2-P1-4096 | 1838 | 0 | 118.4 | 122.1/160.2 |
| H1+R1 / S2-P1-8192 | 2845 | 0 | 179.1 | 122.0/358.0 |
| H1+R1 / S2-P2-8192 | 3830 | 1600 | 1292.0 | 1208.6/1716.9 |
| H1+R1 / S3-P1-8192 | 2856 | 0 | 187.4 | 126.6/347.3 |
| H1+R2 / S1-P1-8192 | 2998 | 0 | 121.6 | 92.8/276.4 |
| H1+R2 / S2-P0-8192 | 1847 | 0 | 99.0 | 81.5/158.5 |
| H1+R2 / S2-P1-16384 | 3032 | 0 | 104.9 | 93.1/158.0 |
| H1+R2 / S2-P1-4096 | 2100 | 0 | 100.3 | 92.8/136.2 |
| H1+R2 / S2-P1-8192 | 3005 | 0 | 121.5 | 97.8/292.4 |
| H1+R2 / S2-P2-8192 | 4119 | 1590 | 1399.9 | 1317.4/1784.0 |
| H1+R2 / S3-P1-8192 | 2998 | 0 | 125.0 | 98.8/284.2 |
| V / S1-P1-8192 | 2986 | 0 | 78.1 | 60.7/105.7 |
| V / S2-P0-8192 | 1835 | 0 | 61.8 | 54.8/107.1 |
| V / S2-P1-16384 | 3004 | 0 | 71.5 | 65.3/121.5 |
| V / S2-P1-4096 | 2672 | 0 | 80.1 | 71.1/134.1 |
| V / S2-P1-8192 | 2988 | 0 | 79.6 | 63.4/118.8 |
| V / S2-P2-8192 | 4224 | 1580 | 1121.7 | 1057.8/1529.1 |
| V / S3-P1-8192 | 2987 | 0 | 79.8 | 64.9/113.7 |

Les répétitions de titres/questions et les références SHA-256 complètes ont un coût : sur H1+R2/S2/P1/8192, environ 3 005 des 6 054 tokens correspondent au JSON vidé des seules réponses. Ce coût reste visible plutôt que dissimulé dans un budget « texte ». Une éventuelle optimisation de format sera une autre recette, pas une modification silencieuse de ces artefacts.

## 5. Cas concrets traçables, sans texte personnel

- Répétition : `democratie-01`, unités originales distinctes `text-unit:v1:gdn-2019:open_answer:3439904:0` et `text-unit:v1:gdn-2019:open_answer:3433510:0` ; la seconde reste dans le journal S3, pas fusionnée avec la première.
- Parent : `democratie-01`, complément `text-unit:v1:gdn-2019:open_answer:2318933:0` rattaché à `text-unit:v1:gdn-2019:open_answer:2318930:0`, même contribution `150203`, sans rang de récupération direct.
- Réponse longue : `democratie-02`, `text-unit:v1:gdn-2019:open_answer:22141:0`, extrait Unicode `[0,2864)` sur 13548 caractères. La suite est explicitement omise et récupérable par la provenance.
- Diversité : `democratie-02`, réponse `text-unit:v1:gdn-2019:open_answer:2392581:0` au rang 19, conservée dans le journal avec `same_contribution` plutôt que supprimée des données.

Ces exemples sont des références vers les artefacts, pas des citations ou jugements de pertinence. Les textes réels restent consultables localement dans `contexts.jsonl` et la source documentaire.

## 6. Artefacts et commandes

- `evaluation/local/rag021/protocol/protocol.json` : paramètres, entrées, tokenizer et hashes de code.
- `evaluation/local/rag021/pilot/` : essai initial sur deux requêtes, 42 contextes et 858 blocs vérifiés.
- `evaluation/local/rag021/development/{contexts.jsonl,statistics.json,manifest.json}` : essai complet.
- `evaluation/local/rag021/development-replay/` : rejeu indépendant du même protocole.
- `evaluation/local/rag021/protected.json` : empreintes des artefacts historiques avant travaux.

Les fichiers contenant les sources restent ignorés par Git ; seuls le code, les tests et cette documentation sont destinés au suivi de versions. Les commandes `freeze`, `build`, `inspect`, `verify` et l’interface Python sont détaillées dans [contexte-documentaire.md](contexte-documentaire.md). Les dossiers de sortie doivent être nouveaux ; le manifeste de succès est écrit en dernier. Pas de reprise persistante dans cette version : relancer un calcul interrompu dans un autre dossier.

## 7. Validations

- Suite complète : **501 tests réussis**, trois tests optionnels PyTorch ignorés dans l’environnement léger ; avertissement de dépréciation FastAPI/HTTPX préexistant. Les intégrations PostgreSQL utilisent les bases de test isolées.
- Ruff et formatage des nouveaux fichiers conformes ; `uv lock --check` réussi (73 paquets), `git diff --check` conforme.
- Rejeu complet : **420 contextes identiques octet pour octet**, SHA-256 `dc18021bfab1636f0aab55cea5551625a6c3e35f7a2cdf43aec7b71d18c663c4`. Deuxième exécution : 124,62 s. Les durées et manifestes d’exécution sont volontairement distincts.
- Contrôle SHA-256 de **1 360 fichiers historiques** : aucun changement, y compris données expérimentales, sessions, jugements, moteurs, dépendances et verrou backend/RAG. Résumé local : `evaluation/local/rag021/validation.json`.

- Vingt et un nouveaux tests autonomes : fidélité Unicode, BIGINT, citations, doublons légitimes, S1/S2/S3, voisins, texte long, trois budgets, recomposition, métadonnées, données absentes, erreurs de partition, falsifications, compte de tokens et isolation des dépendances.
- Contrôle réel : 420 contextes et 8 370 sources vérifiés contre les unités RAG-007 de développement et les classements gelés.
- Aucune génération de réponse, aucun nouveau téléchargement, aucune inférence GPU, aucune écriture PostgreSQL ou source, aucun jugement consulté ou modifié.

## 8. Limites et recommandation pour RAG-022

Point de départ proposé : **H1+R2, S2/P1, 8 192 tokens documentaires**. S2 conserve la diversité par contribution à faible coût dans ces listes, P1 garde le contexte de la question, et 8 192 évite une partie des exclusions du budget 4 096 sans les coûts ni le remplissage faible d’une fenêtre 16 384. Cette recommandation est structurelle, pas une preuve de qualité de réponse.

Conserver P2 comme option explicite pour des réponses courtes ou dépendantes de leur contexte, plutôt que l’activer systématiquement : il récupère des voisins structurels, pas nécessairement utiles, et coûte davantage. Conserver S3 comme variante expérimentale et journalisée : les quasi-doublons ne sont pas une équivalence sémantique, et la fréquence locale n’est pas une représentativité statistique.

RAG-022 devra choisir le générateur, recompter son prompt complet et sa réserve de sortie, traiter les sources comme des données citées et vérifier que toute référence produite appartient à la table de citations. Évaluer ensuite fidélité des citations et réponse à l’intention, sans déduire ces qualités des seuls scores de récupération ou de l’occupation du contexte.

Limites : premier segment seulement (biais vers le début des longues réponses), parents incomplets, segmentation susceptible de couper un mot ou graphème, heuristique de quasi-égalité, plafond de vingt principales, réserves P2 non réaffectées, métadonnées parfois coûteuses. La diversité peut écarter une seconde réponse pourtant bien classée et faire entrer une réponse de rang inférieur ; cet arbitrage n’a pas été évalué en pertinence dans ce ticket. Aucun de ces paramètres n’a été optimisé sur les notes LLM. Aucun commit ou push.
