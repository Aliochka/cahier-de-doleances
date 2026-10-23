# RAG personnel local — démarrage et limites

Cette interface interroge librement les **20 000 unités RAG-007**, avec H1 (lexical pondéré + BGE-M3), Qwen3-Reranker-4B, contexte S2/P1 de 8 192 tokens, puis Qwen3-14B. Elle reste sur la machine locale. Les réponses sont expérimentales : des attributions ou conditions peuvent encore être erronées, même lorsque les références existent.

## Démarrer

Depuis la racine du dépôt :

```sh
cd rag
UV_PROJECT_ENVIRONMENT=.cache/judges-venv uv sync --locked --inexact \
  --extra judges --extra annotation --extra personal
```

Cette installation optionnelle utilise le verrou du RAG ; elle n’installe pas de modèle. Les snapshots existants de BGE-M3, Qwen3-Reranker-4B et Qwen3-14B doivent être présents dans `models/`. PostgreSQL local et les index RAG-008/013 existants doivent être disponibles. La sélection de recette est enregistrée dans `evaluation/local/rag025/selected.json`.

Pour les noms de bases locaux actuellement utilisés, sans mot de passe stocké :

```sh
RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local \
RAG_DATABASE_URL=postgresql:///cahier_rag \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve
```

Ouvrir **http://127.0.0.1:8770**. Poser une question dans le formulaire. Le traitement affiche ses étapes ; une seule question est traitée à la fois pour maîtriser la VRAM. Cliquer sur une référence pour ouvrir son passage, sa question, son questionnaire et ses métadonnées. Les extraits incomplets sont signalés avec leurs positions et plages omises. La synthèse n’est pas du texte citoyen original ; les passages présentés séparément restent exacts.

**Arrêter : Ctrl+C dans le terminal.** Si un calcul est en cours, l’arrêt attend sa fin ; laisser le processus terminer pour conserver son résultat. Une interruption forcée avant l’écriture finale oblige à recalculer l’étape courante, sans effacer les étapes déjà enregistrées.

`--port 8771` permet de choisir un autre port local. Il n’existe pas d’option d’écoute réseau. Pour d’autres identifiants de connexion, utiliser les variables RAG explicites ou `serve --env-file /chemin/vers/un/fichier-local.env`. Aucun chargement automatique du `.env` du backend, aucun repli sur `DATABASE_URL`. L’identité des bases distinctes est contrôlée par les primitives existantes ; la base source n’est pas modifiée.

## Ce que fait la chaîne

- La recherche lexicale porte sur tout le manifeste RAG-007. La requête vectorielle est encodée une seule fois ; les deux partitions documentaires sont recherchées séparément, puis leurs résultats sont réunis en top 50 global par cosinus. H1 fusionne les top 50 lexicaux/vectoriels avec RRF `k=60`.
- Les **questions libres ne sont pas un jeu d’évaluation**. Aucun fichier de requêtes de développement ou réservées n’est lu par la chaîne libre. Ses résultats portent `purpose=personal-free-query`, sans partition de requête.
- Le reranker évalue question originale + réponse avec son tokenizer, segments de 1 024 tokens maximum et chevauchement de 128 caractères ; score maximal par unité. Les modèles sont libérés entre recherche, reclassement et génération, pour rester dans les 32 Go de VRAM.
- Les primitives RAG-021 sélectionnent les contributions distinctes et construisent des passages exacts. La chaîne libre utilise les deux partitions **documentaires** du corpus, sans altérer leurs attributions ; elle ne se fait pas passer pour une campagne de développement. Aucune expansion parentale hors des documents sélectionnés.
- La génération `generation-fr-v6-personal` utilise XGrammar 0.2.8, le prompt renforcé et le validateur RAG-022 inchangé, complété par un contrôle de fin de phrase et de limite de sortie.

## Génération et reprises

Pas de coupe à 600 caractères ni de limite à 300 sur la rédaction des réserves. Le schéma exige une ponctuation finale pour les textes et limites, sans borne de caractères pour les forcer à finir. Le validateur historique conserve ses plafonds de sécurité ; **4 096 tokens générés maximum**. Si cette limite est atteinte, si le JSON est interrompu ou si la validation échoue, la sortie est conservée et n’est pas présentée comme une synthèse validée. Il n’y a pas de fermeture automatique ni de correction des phrases.

Le filtre global de tokens LMFE est supprimé. Le schéma limite les guillemets dans les champs de paraphrase, tout en conservant les références exactes et les autres champs structurés. Une ponctuation finale n’est pas une preuve de grammaire correcte ni de fidélité.

Les enregistrements restent ignorés par Git :

- `evaluation/local/rag025/personal-generation.sqlite3` : cache transactionnel par recette, étape, sources et question ; seules les étapes manquantes sont recalculées.
- `evaluation/local/rag025/requests/<hash>.json` : question personnelle, recettes, classements, positions des segments, contexte, citations, résultat brut et mesures.
- `evaluation/local/rag025/direct-v6/` : campagne figée de développement, distincte des questions libres.

Une fermeture de l’onglet ne supprime pas le calcul côté serveur. Après redémarrage, reposer la question : la recherche et le reclassement sont réexécutés ; la génération réutilise son cache si recette et contexte sont identiques. Ce n’est pas une reprise des états GPU au token près.

## Vérifier et expérimenter

```sh
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

La comparaison directe/deux étapes et les échecs des premières variantes restent locaux. Pour une **nouvelle** expérience pilote, choisir un dossier neuf :

```sh
.cache/judges-venv/bin/python -m cahier_rag.personal.cli run \
  --directory evaluation/local/rag025/nouvel-essai --stage pilot
# Variante d’analyse puis synthèse, avec sources originales aux deux étapes :
.cache/judges-venv/bin/python -m cahier_rag.personal.cli run \
  --directory evaluation/local/rag025/autre-essai --method two-step --stage pilot
```

La campagne complète exige une sélection explicite après inspection du pilote. Ne pas recopier les fichiers `selection.json` pour contourner cette étape. Les recettes v2/v3 et sorties historiques ne sont pas remplacées. Les anciens plans très stricts peuvent signaler que le verrou racine a changé lors de l’ajout optionnel de XGrammar ; leurs caches et sorties restent conservés, avec les anciens fichiers de dépendances archivés sous `evaluation/local/rag025/historical-environment/`.

Les mesures et les limites résiduelles sont détaillées dans [rapport-rag-025.md](rapport-rag-025.md). Aucune promesse de représentativité, de fiabilité générale ou de conversation multi-tour : chaque question est traitée indépendamment. Aucun service distant, déploiement Wallace ou intégration au site public.
