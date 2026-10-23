# RAG-021 — Assemblage documentaire local

Le package `cahier_rag.context` transforme des classements gelés en sources citées et en JSON documentaire destiné à un futur générateur. Il ne génère aucune réponse, n'appelle aucune API et ne charge aucun poids de modèle. Les moteurs, indices, requêtes, jugements et contrats `TextUnit` restent inchangés.

## Contrat et citations

`ContextSource` conserve le `TextUnit` original, les positions Unicode `[start,end)`, le corpus sélectionné, le rôle, la méthode et le rang. Son export sépare :

- `citizen_text` : portion **exacte** du texte consultable normalisé RAG-004. Ce n'est pas nécessairement le texte brut de l'export de 2019. Aucun nettoyage, ellipse ou reformulation n'est ajouté.
- `metadata` : question et questionnaire, titre éventuel, références source, positions structurelles, identifiants internes/externe, empreinte documentaire. Les BIGINT sont des `int` dans le contrat original et des chaînes décimales en JSON.
- `technical` : rôle principal/complémentaire, positions de l'extrait, plages omises explicites, rang et méthode, référence au parent, observations de répétition, version et empreinte du corpus.

Référence : `context-source:v1:SHA256([sample_hash, document_id, start, end])`. Elle reste stable entre méthodes et requêtes pour le même extrait. Deux réponses identiques de contributions différentes ont des références différentes. Les collisions et duplications sont refusées.

Chaque contexte comporte `citation_map`, table complète de correspondance entre référence et source. Le bloc transmis au futur modèle conserve sa référence, le texte, le rôle et les positions ; P1/P2 ajoutent question, questionnaire et titre dans un objet de métadonnées séparé. Le rang et la méthode restent dans la table de provenance, pas dans le texte citoyen.

`public_url` reste `null`. `link_target` expose les identifiants nécessaires à un futur résolveur de liens. Aucune URL n'est déduite d'un ID de réponse. Le contexte conserve également les références de contributions et réponses complémentaires effectivement utilisées, sans prétendre reconstruire une contribution complète.

## Sélection figée

Les seuls classements utilisés sont les top 50 RAG-020 de **H1+R2**, **H1+R1**, **V**, respectivement Qwen3-Reranker-4B, BGE reranker et BGE-M3 seul. Les listes sont vérifiées contre les scores RAG-020 et leurs recettes, sans relancer les modèles ni consulter les notes LLM.

- **S1** : ordre initial, au plus 20 sources principales. Arrêt à la limite de nombre ou de budget.
- **S2** : même ordre, au plus une source principale par `(corpus, contribution)`. Les autres réponses restent dans le journal `excluded` avec leur rang ; elles ne sont pas supprimées du corpus.
- **S3** : comparaison des textes à **question et questionnaire identiques**, contre les sources déjà sélectionnées. Texte exact, puis égalité des mots NFKC/casefold, puis Jaccard d'ensembles de mots ≥0,90 et rapport de longueurs ≥0,90 pour au moins huit mots. Des marqueurs de négation ou nombres différents empêchent la correspondance approchée. Ce garde-fou ne transforme pas cette heuristique en équivalence sémantique.

Les transformations S3 servent uniquement à comparer ; les textes exportés restent intacts. Les occurrences écartées conservent document, contribution, rang et empreinte. Leurs nombres portent sur le **préfixe de candidats examiné avant l'arrêt**, pas sur toutes les opinions, les citoyens, ni même nécessairement tout le top 50. Aucun représentant n'est une source composite ; la source retenue reste une réponse précise d'une contribution précise. Les réponses identiques à des questions différentes restent distinctes dans la sélection.

Une réponse longue n'est pas sautée pour faire passer une réponse courte moins bien classée : elle reçoit un extrait explicite dans l'ordre du classement. Si même un extrait minimal admissible ne tient plus, la sélection s'arrête au lieu de rechercher des documents moins chers dans la suite de la liste.

## Modes parentaux

- **P0** : réponse et référence dans le JSON du futur modèle, sans question ni titre. La table de citations conserve toujours toute la provenance.
- **P1** : question, questionnaire et titre éventuel de la source sélectionnée, sans autre réponse.
- **P2** : P1, puis au plus deux réponses voisines par source principale. Ordre structurel du questionnaire ; distance de position dans l'ordre trié, antérieure d'abord en cas d'égalité. Aucune pertinence sémantique de ces voisins n'est présumée.

Le rattachement se fonde sur les vrais identifiants du corpus, de la contribution et du questionnaire. La politique reste celle de RAG-011 : **`rag007-selected-only`**, partition développement uniquement. Aucun accès aux 22 318 unités supplémentaires du cadre, ni au corpus source. Les parents sont donc potentiellement incomplets.

Les données viennent de la copie documentaire SQLite RAG-018 en lecture seule, avec contrôle des empreintes RAG-007. Au plus 500 unités par lecture et 256 par contribution ; plafond de 20 millions de caractères par lot. Les connexions sont fermées avant le traitement. Aucune nouvelle table ou migration.

P2 réserve **20 % du budget documentaire** à l'expansion, après un plafond principal de 80 %. Les compléments sont ajoutés après la sélection principale, sans duplication d'une unité déjà présente. Ils portent `role=complementary`, `direct=false`, sans rang de récupération, et leur lien vers la source principale. La réserve inutilisée n'est pas réaffectée : ce choix conservateur et son coût d'occupation sont mesurés explicitement.

## Budget et tokenization

Le tokenizer réel de **Qwen/Qwen3-Reranker-4B**, révision `22e683669bc0f0bd69640a1354a6d0aebcfeede5`, est réutilisé depuis le snapshot RAG-020. Son SHA-256 est comparé au manifeste et au snapshot figés. La bibliothèque Rust `tokenizers` est utilisée directement, sans Transformers, PyTorch ou GPU ; son numéro de version est enregistré. Aucun téléchargement supplémentaire.

Comptage exact de `model_document_payload` : JSON canonique UTF-8, `ensure_ascii=False`, `add_special_tokens=False`, aucun padding/troncature ni gabarit de chat. Les retours à la ligne et guillemets sont comptés dans leur représentation JSON réellement transmise. Le plafond de **4 096 / 8 192 / 16 384 tokens** inclut l'enveloppe documentaire, toutes les références et métadonnées présentes dans ce JSON.

- `document_used` : total exact du JSON documentaire.
- `metadata_reference_tokens` : même JSON avec les seuls textes de réponse vidés ; question/titre/références restent comptés.
- `citizen_incremental_tokens` : différence exacte entre ces deux comptes. Ce n'est pas la somme de tokenizations indépendantes, car le BPE dépend des frontières.
- La table complète `citation_map` est **hors bande**, destinée au logiciel et à l'interface ; son coût est indiqué séparément. Elle ne doit pas être ajoutée implicitement au prompt sans recompter.
- Réserves distinctes : **512 tokens d'instructions**, **1 024 de réponse**, **128 d'enveloppe future**, plus le coût de la requête. `minimum_total_window` indique le budget total à prévoir. Aucun contenu d'instruction ni réponse n'est créé ici.

Le futur modèle génératif n'est pas choisi. Cette mesure garantit la limite documentaire pour le tokenizer enregistré, pas une fenêtre de chat complète pour n'importe quel modèle : RAG-022 devra recompter le prompt final avec son tokenizer et son gabarit réels.

Chaque réponse est segmentable en portions de **768 tokens de texte citoyen maximum**, sans chevauchement, frontières de phrases/paragraphes privilégiées. Les intervalles reconstruisent le texte sans perte. Cette première sélection utilise **le premier extrait** de chaque unité, éventuellement réduit pour le budget restant. Pour une réduction budgétaire, minimum 32 tokens ou la longueur de l'intégralité d'une réponse plus courte ; les réponses d'un mot restent admissibles. Les bornes et plages non transmises sont conservées : l'absence de la suite est explicite, aucune ellipse n'est insérée dans la citation. La recherche de frontière est déterministe, sans dépendance NLP, et peut couper un mot ou un graphème.

## Protocole progressif et commandes

Sept configurations, sur trois classements et 20 requêtes = **420 contextes**, plutôt qu'un produit cartésien de 27 configurations :

1. S1/P1/8192, S2/P1/8192, S3/P1/8192 : sélection.
2. S2/P0/8192 et S2/P2/8192, avec S2/P1 déjà présent : expansion.
3. S2/P1/4096 et S2/P1/16384, avec 8192 déjà présent : budget.

Depuis `rag/`, utiliser l'environnement optionnel existant qui possède déjà `tokenizers` :

```sh
.cache/embeddings-venv/bin/python -m cahier_rag.context.cli freeze \
  --output evaluation/local/rag021/mon-protocole
.cache/embeddings-venv/bin/python -m cahier_rag.context.cli build \
  --protocol evaluation/local/rag021/mon-protocole \
  --output evaluation/local/rag021/mon-pilote --query-limit 2
.cache/embeddings-venv/bin/python -m cahier_rag.context.cli build \
  --protocol evaluation/local/rag021/mon-protocole \
  --output evaluation/local/rag021/mes-contextes
.cache/embeddings-venv/bin/python -m cahier_rag.context.cli inspect \
  evaluation/local/rag021/mes-contextes
.cache/embeddings-venv/bin/python -m cahier_rag.context.cli verify \
  --protocol evaluation/local/rag021/mon-protocole \
  evaluation/local/rag021/mes-contextes
```

Le gel conserve configurations, tokenizer, hashes de code et entrées. Les sorties sont créées exclusivement dans de nouveaux dossiers ; une sortie existante n'est jamais écrasée. Choisir les chemins locaux ignorés par Git ci-dessus. `contexts.jsonl` contient les textes réels et ne doit pas être versionné. Le manifeste de succès est écrit en dernier ; une exécution interrompue reste identifiable comme incomplète et doit être relancée dans un nouveau dossier, sans checkpoint persistant dans cette version.

L'interface Python pure est `assemble(query, ranked_ids, repository, counter, method=..., config=...)`. Le compteur et le dépôt sont injectables ; les tests fonctionnent sans dépendance de tokenizer ou PostgreSQL. La préparation traite un contexte à la fois et écrit le JSONL progressivement ; les textes du corpus entier ne sont jamais chargés en mémoire. La vérification relit les sources, contrôle textes, offsets, références, partitions, rangs, relations et budgets. Un second build produit le même JSONL ; durée et statistiques d'exécution restent volontairement variables.

```sh
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

Les observations réelles, coûts et limites sont dans [rapport-rag-021.md](rapport-rag-021.md). Les contextes décrivent des sources disponibles pour une réponse future, pas une réponse générée. Diversité et occupation du budget ne sont pas des mesures de pertinence ou de qualité d'une génération.
