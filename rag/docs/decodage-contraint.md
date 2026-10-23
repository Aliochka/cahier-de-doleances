# RAG-023 — Génération structurée par décodage contraint

Le sous-package `cahier_rag.generation.constrained` ajoute un décodeur local à l'exécuteur Transformers existant. Les contrats et validateurs RAG-022, les moteurs, les contextes et les caches historiques ne sont pas modifiés.

## Solutions étudiées

| Solution | Licence / version étudiée | Mécanisme et intégration | Décision |
|---|---|---|---|
| LM Format Enforcer | MIT, 0.11.3 | Parseur de caractères + arbre des tokens ; callback `prefix_allowed_tokens_fn` de Transformers. Dépendances Pydantic, interegular, packaging et PyYAML. | Retenu et exécuté localement. Ajout léger au chargeur NF4 existant. |
| XGrammar | Apache-2.0, 0.2.8 | Grammaires compilées, masques et `LogitsProcessor` Hugging Face ; dépend notamment de TVM-FFI et, sous Linux x86_64, Triton. | Non installé. Candidat si le filtrage Python devient trop coûteux. Compatibilité locale NF4/5090 non mesurée. |
| Outlines | Apache-2.0, 1.3.3 | Adaptateur Transformers et moteur compilé `outlines_core`, avec une couche plus large et plusieurs dépendances. | Non installé : n'apporte pas d'avantage démontré pour notre unique boucle `generate()`. |

Sources primaires : [LMFE](https://github.com/noamgat/lm-format-enforcer), [métadonnées LMFE](https://pypi.org/project/lm-format-enforcer/0.11.3/), [XGrammar/Hugging Face](https://xgrammar.mlc.ai/docs/latest/start/quick_start.html), [métadonnées XGrammar](https://pypi.org/project/xgrammar/0.2.8/), [Outlines](https://github.com/dottxt-ai/outlines), [métadonnées Outlines](https://pypi.org/project/outlines/1.3.3/). Les licences sont vérifiées dans les fichiers officiels des dépôts. Les possibilités des solutions non exécutées ne sont pas des performances validées sur notre machine.

L'extra uv `constrained` ajoute `lm-format-enforcer==0.11.3`. Le verrou ajoute uniquement LMFE et interegular 0.3.3 ; les autres dépendances étaient déjà verrouillées et leurs versions sont conservées. L'environnement GPU existant a reçu les seules dépendances manquantes, à ces versions. Pas de nouveau modèle, framework agentique ou serveur.

## Recette et comparaison

**`generation-fr-v3-constrained`** conserve le texte exact du prompt **generation-fr-v2**, les messages, les vingt entrées compactes et tables de citations RAG-022, Qwen3-14B à sa révision RAG-016, NF4/BF16, SDPA, thinking désactivé, graine 42, génération gloutonne et limite de 2 048 tokens. Chaque prompt rendu et chaque compte d'entrée sont comparés à v2 avant le lancement. Les fichiers `inputs.jsonl` sont copiés octet pour octet, sans recherche, reranking ni assemblage supplémentaire.

Les schémas sont adaptés par requête, avec les références `S01`, `S02`, etc. réellement disponibles. Leur version, contenu, empreintes, configuration LMFE et versions sont conservés avec le plan. Aucun schéma ne contient les textes citoyens.

### Premier schéma, essai conservé

Le premier schéma reproduisait les bornes hautes du contrat RAG-022. Sur les trois échecs historiques, une sortie seulement a passé le validateur complet : une autre contenait des guillemets non structurés dans `text`, et une troisième atteignait la limite de sortie avant la fin du JSON. Ce pilote est conservé sous `evaluation/local/rag023/pilot-schema-v1/`, avec code, sorties et rapport ; il n'a pas été réparé.

Un premier lancement préalable avait également échoué sur l'import de Pydantic absent de l'environnement GPU, avant toute génération. L'installation des dépendances déjà verrouillées a corrigé cet incident sans modifier le modèle ou le prompt. Voir `technical-failures.json`.

Une seconde variante avec un motif régulier borné a été interrompue : le parcours de l’arbre des tokens dans LMFE saturait un cœur CPU sans terminer la première sortie. Le plan et son code sont conservés dans `pilot-schema-v2-interrupted/`. Le schéma suivant remplace ce motif par les bornes natives, sans changer le prompt ni le validateur. Ce blocage a été identifié après environ 96 minutes de calcul CPU sans sortie ; aucune campagne complète n’a été lancée avec ce schéma.

La variante native seule (`native/`) a donné 2/3 sorties valides : le JSON était valide, mais un bloc contenait une citation entre guillemets doubles interdite par RAG-022. Elle est conservée sans correction. La variante suivante ajoute un filtre de tokens explicite.

### Schéma retenu : `rag-response-schema-v4-native-token-filter`

Les contraintes sont **plus strictes**, jamais assouplies par rapport au contrat original :

- Objet JSON avec exactement `blocks`, `limits`, `insufficient_sources` et tous les champs de bloc obligatoires.
- 1 à 4 blocs, types `kind` connus. Les blocs substantiels exigent 1 à 3 références parmi celles de la requête ; les blocs `limitation` peuvent avoir une liste vide.
- `text` : 1 à 600 caractères via les bornes natives du parseur. Les guillemets et références non structurées restent contrôlés par le validateur original.
- 0 à 3 limites, chacune de 1 à 300 caractères.
- Champ `quotes` obligatoire, tableau de 0 à 8 objets de citation, références connues. Le prompt v2 demande déjà `[]` ; le décodeur ne considère pas l'absence de citations comme une preuve de fidélité.
- `insufficient_sources` booléen, propriétés supplémentaires interdites.

Une borne de caractères peut contraindre la fin d’une phrase : son effet rédactionnel doit être inspecté dans RAG-024, même si le JSON est valide.

Le durcissement des bornes ne change pas les documents ou le prompt, mais **confond partiellement la comparaison** : les changements de longueur, de sources citées ou de formulation ne sont pas attribuables au seul masquage des tokens. L'imposition de trois références par bloc traduit une préférence déjà présente dans le prompt v2 en borne dure ; le contrat original en autorise davantage.

L'alphabet du parseur couvre ASCII, latin étendu, ponctuation française et caractères des entrées, en excluant les contrôles C0 bruts. Les nouvelles lignes restent correctement échappées dans les chaînes JSON où elles sont autorisées. Un filtre supplémentaire conserve seulement les tokens ne contenant ni backslash ni guillemets typographiques. Il empêche notamment les guillemets doubles échappés dans les textes ; les guillemets JSON structurels restent permis. Ce choix restreint aussi les retours à la ligne échappés dans la sortie générée : il ne modifie jamais les sources ni les entrées. Le validateur original vérifie toujours les citations non structurées et les références entre crochets. Ce filtre porte sur les décodages de tokens du tokenizer figé ; ce n’est pas une preuve formelle d’exclusion de toute séquence Unicode assemblée sur plusieurs tokens. Le validateur reste requis. Il ne constitue pas une preuve sémantique et son effet est un facteur supplémentaire dans la comparaison. Les sources transmises ne subissent aucune transformation.

### Limites réellement testées

- `uniqueItems` est ignoré par LMFE 0.11.3 dans nos tests. Les références dupliquées restent rejetées par le **validateur RAG-022 inchangé**, après génération.
- `maxItems: 0` ne suffit pas à empêcher le premier élément dans cette version ; ne pas le présenter comme une garantie de tableau strictement vide. Nos contextes réels possèdent tous des sources ; l'absence hypothétique de sources est toujours contrôlée par le validateur.
- Les chaînes uniquement blanches, l'appartenance d'une citation à ses références de bloc et l'exactitude des citations littérales restent des contrôles après génération.
- Une interruption ou la limite de 2 048 tokens peut laisser un préfixe JSON incomplet : aucune fermeture ou réparation automatique.
- Le décodeur et le validateur ne prouvent ni étayage sémantique, ni justesse des positions/oppositions, ni représentativité, ni couverture de la question, ni reconnaissance correcte de l'insuffisance.

## Architecture et mesures

- `schema.py` : schéma par requête et configuration du parseur, diagnostics synthétiques.
- `backend.py` : chargeur Qwen/NF4 réutilisé, arbre de tokenizer partagé dans une session, callback LMFE et chronométrages.
- `planning.py` : vérification des entrées v2, schémas, paramètres et empreintes de code/dépendances.
- `cache.py`, `pipeline.py` : cache indépendant, tentatives et checkpoint atomiques par requête ; reprise sans recalcul des réponses déjà enregistrées.
- `reporting.py` : comparaison en lecture seule avec v2, métriques structurelles et différences observables sans notation de qualité.
- `cli.py` : préparation, pilote, campagne, rapport.

Le chargeur du modèle est inchangé. Le préremplissage est mesuré sur le premier forward, avec synchronisation CUDA. Le reste de `generate()` inclut décodage, filtrage et boucle Transformers. Le temps de callback est un temps mural pouvant inclure des synchronisations, **pas un coût CPU parfaitement isolé** ; il est déjà inclus dans `generate()` et ne doit pas être ajouté une seconde fois. La construction de l'arbre du tokenizer (une fois par processus), la préparation du schéma et la validation finale sont comptées séparément.

Le cache de la variante native est `evaluation/local/rag023/guarded/generation.sqlite3`, strictement séparé des caches RAG-022 et des juges. Les résultats valides et invalides sont conservés, sans correction silencieuse. La reprise ne recalcule pas un résultat existant. Une erreur d'inférence arrête la campagne et peut être retentée explicitement par `--retry-errors`. Une interruption avant commit recalcule seulement la requête en cours ; les états KV ne sont pas persistés par token.

## Commandes locales

Depuis `rag/`, pour préparer l'environnement optionnel à partir du verrou :

```sh
UV_PROJECT_ENVIRONMENT=.cache/judges-venv uv sync --locked --inexact --extra judges --extra constrained
```

Les poids existants sont réutilisés, sans téléchargement. Pour une **nouvelle** expérience :

```sh
.cache/judges-venv/bin/python -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/nouvel-essai/plan prepare
.cache/judges-venv/bin/python -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/nouvel-essai/plan run --stage pilot
# Les trois échecs historiques doivent être structurellement valides avant la campagne.
.cache/judges-venv/bin/python -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/nouvel-essai/plan run --stage development
.venv/bin/python -m cahier_rag.generation.constrained.cli \
  --plan evaluation/local/rag023/nouvel-essai/plan report
```

Pour l'expérience native, préciser `--plan evaluation/local/rag023/guarded/plan` ; le chemin par défaut conserve le pilote précédent `evaluation/local/rag023/plan` ; **ne pas relancer `prepare` sur un dossier existant**. Les trois requêtes pilotes sont `democratie-05`, `fiscalite-04`, `services_publics-03`. Leurs résultats sont réutilisés dans la campagne complète, sans génération en double.

```sh
watch -n 5 cat evaluation/local/rag023/guarded/plan/development-progress.json
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

Les tests du parseur réel demandent l'extra léger `constrained`, mais pas de GPU. Ils sont ignorés explicitement si cet extra n'est pas installé ; les tests de reprise simulée restent autonomes. Les fichiers contenant des textes et les modèles sont locaux, ignorés par Git. Les rapports ne créent aucun jugement humain ou LLM.

Résultats et coût observé : [rapport-rag-023.md](rapport-rag-023.md). L'évaluation sémantique approfondie reste celle de RAG-024.
