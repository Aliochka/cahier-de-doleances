# RAG-017 — Évaluation automatique approfondie

Ce protocole produit deux référentiels **LLM** séparés, sans modifier ni lire les
notes et commentaires humains. Les modèles Qwen3-8B et Qwen3-14B conservent les
révisions, la quantification et les paramètres d'inférence de RAG-016.
Aucun reranker ni génération de réponses aux utilisateurs n'est introduit.

## Grille et séparation des versions

`judges/protocols.py` contient `relevance-fr-v2`, fondé sur l'intention :

- 0 : hors sujet, aucun rapport significatif.
- 1 : rapport indirect sans véritable réponse.
- 2 : réponse directe mais insuffisamment précise pour la demande.
- 3 : intention pleinement satisfaite avec la précision appropriée.

La longueur n'est pas récompensée. Une position courte peut satisfaire une
question fermée ; une proposition doit être suffisamment concrète si la
requête le demande ; une demande d'arguments attend des raisons. Les trois
exemples du ticket sont inclus dans le prompt immuable. Les modèles ne voient
que requête, réponse complète, question originale et titre facultatif : aucun
moteur, rang, score, jugement ou commentaire humain.

Le texte et l'empreinte de v1 restent inchangés. Les plans v1 restent lisibles,
leurs plafonds et commandes historiques restent utilisables. Le nom et
l'empreinte du protocole entrent dans la recette de cache : **aucun jugement
v1 n'est réutilisé comme v2**. Le cache v2 est en outre physiquement séparé.

## Pool et enrichissement contrôlé

Les seuls documents admissibles sont ceux de `rag007/corpus.json`, partition
développement, avec les seules 20 requêtes de développement. Le pool obligatoire
unit les top 50 gelés des trois moteurs RAG-014, les 400 candidats RAG-010,
les 400 RAG-014 et les 101 compléments RAG-016, dédupliqués par
`(query_id, document_id)`. Toutes les origines et occurrences sont conservées.
Les hash des documents et des requêtes sont distincts des hash d'entrées LLM.

L'union réelle comprend **1 931 couples** : déficit de **69** par rapport au
minimum. L'enrichissement vise **2 500**, soit **569 ajouts**. Une nouvelle
récupération locale aux profondeurs 100 est enregistrée sans écraser les
classements gelés. Les préfixes lexicaux et vectoriels 1–50 doivent correspondre
exactement aux originaux et les empreintes de leurs recettes doivent être
identiques. Les nouveaux classements hybrides produits par l'outil existant
ne servent ni au pool complémentaire ni à l'évaluation : seuls les rangs
51–100 lexicaux et vectoriels sont utilisés pour l'enrichissement.

L'ordre est déterministe : rang croissant 51–100, requête triée par ID, puis
lexical et vectoriel ; un couple déjà présent est conservé une fois avec toutes
ses origines. La cible est arrêtée exactement. Aucun document arbitraire ou
hors classement n'est introduit. Les plafonds historiques v1 restent à 1 500 ;
seul le protocole v2 possède un plafond contrôlé de 3 000.

Le manifeste immuable conserve corpus, requêtes, sources, paramètres de
sélection, protocole, empreintes des entrées et métadonnées de pooling.
`pool.json` contient les origines ; `inputs.jsonl`, les seuls contenus admis
aux juges. Ces fichiers et tous les résultats réels restent ignorés par Git.

## Commandes

Depuis `rag/`, utiliser l'environnement dédié existant, sans synchroniser celui
de l'annotation humaine. Aucun nouveau téléchargement ou appel distant n'est
nécessaire, les snapshots officiels étant déjà présents.

```bash
# Seulement pour reconstruire un NOUVEL enrichissement dans un dossier absent :
RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local \
RAG_DATABASE_URL=postgresql:///cahier_rag \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/embeddings-venv/bin/python -m cahier_rag.search.hybrid.cli \
  --depth 100 --limit 100 development --output evaluation/local/rag017/deepening

# Création exclusive du plan ; lecture seule des documents RAG :
RAG_DATABASE_URL=postgresql:///cahier_rag \
.venv/bin/python -m cahier_rag.judges.campaign prepare --target 2500

# Précontrôle des DEUX tokenizers, sans inférence :
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.judges.campaign preflight

# Exécuter successivement ; relancer la même commande pour reprendre :
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.judges.campaign run \
  --judge qwen3-8b --limit 2500
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.cache/judges-venv/bin/python -m cahier_rag.judges.campaign run \
  --judge qwen3-14b --limit 2500

# Rapport nouveau, jamais dans les sessions humaines (dossier absent requis) :
.venv/bin/python -m cahier_rag.judges.campaign report \
  --output evaluation/local/rag017/nouveau-rapport
```

Les options globales `--root`, `--plan`, `--models`, `--env-file` précèdent la
sous-commande. Ne pas réexécuter `prepare` sur un dossier existant. Un dossier
nouveau permet une nouvelle expérience sans écrasement historique.

## Précontrôle, progression et reprise

Les deux précontrôles doivent réussir pour le même plan avant toute génération.
Ils contrôlent les entrées exactes avec les tokenizers locaux à révision fixe.
Le maximum réel est **16 630 tokens**, inférieur au budget de **24 576**, pour
les deux modèles. Le budget comprend le gabarit, le système et le contexte.
Aucune troncature n'est autorisée ; tout dépassement bloque la campagne.

La recette reste : lots de 2, graine 42, génération gloutonne, thinking désactivé,
192 nouveaux tokens maximum, NF4 double et calcul bfloat16, SDPA. Une entrée
et sa recette déterminent la clé de cache. Les lots sont validés atomiquement
dans `evaluation/local/rag017/cache.sqlite3`. Les résultats invalides gardent
un statut explicite sans note ; `--retry-failed` réessaie uniquement ces cas
avec la même recette. Une erreur GPU laisse les lots précédents disponibles.

`--stop-after N` permet un arrêt contrôlé à la fin d'un lot. Les fichiers
`<juge>-progress.json` sont actualisés à chaque lot avec les compteurs et une
estimation du temps restant basée sur le débit réellement observé. Les
manifestes de passages sont archivés dans `pool/history/` ; le fichier
`<juge>-run.json` décrit le dernier passage. Additionner les passages pour
mesurer le temps d'une campagne ayant été reprise. Une simple relance ne doit
pas faire interpréter son temps de lecture de cache comme un débit GPU.
Le rapport additionne automatiquement les historiques du même plan et de la
même recette, sans compter deux fois le dernier passage. Il présente également
une comparaison sur les seules requêtes intégralement jugées par les deux modèles.

Le [bilan de l'exécution réelle](rapport-rag-017.md) documente les trois sorties
14B restant invalides après reprise. Le rapport local de référence est
`evaluation/local/rag017/comparison-verified/report.md`. Les métriques manquantes ne
sont ni complétées ni calculées à partir de notes récupérées dans un JSON invalide.

## Mesures et exports

Le rapport primaire conserve chaque juge séparément et utilise exclusivement
les classements top 50 gelés. Pertinent binaire : notes 2–3.

- Precision@5/10/20/50 : dénominateur k, seulement si tout le top k est jugé.
- Proportion pertinente : dénominateur nombre retourné, distinct de P@k si
  moins de k résultats sont retournés.
- MRR : premier pertinent du classement fourni, limité à 50. Un non-jugé
  avant le premier pertinent rend la mesure indéfinie ; zéro seulement si le
  classement fourni est entièrement jugé sans pertinent.
- nDCG poolée@k : gains `2**grade-1`, décote `log2(rang+1)`, IDCG construit
  avec **toutes les notes du pool de cette requête pour ce juge**, partagé
  entre les trois moteurs. Aucune prétention d'exhaustivité du corpus.
  Si le pool de la requête est incomplet ou son idéal nul, la mesure reste
  indéfinie. Aucun retrait des non-jugés pour modifier les rangs.
- Recall exhaustif : non calculé.

Les agrégations sont des macro-moyennes, avec nombres de requêtes calculables.
Les résultats par requête, domaine, catégorie, note et k restent disponibles.
Les inversions strictes d'ordre entre moteurs sont distinguées des égalités.
L'accord inter-juges utilise les seuls couples valides communs ; échelle
ordinale 0–3, kappa de Cohen pondéré linéairement, matrice et divergences binaires.
Aucune moyenne de notes ou note consensuelle n'est créée.

Chaque export de jugement conserve note, justification, incertitude, date,
évaluateur LLM, modèle/révision, protocole/empreinte, recette, paramètres,
empreintes du document et de la requête, ID d'entrée et manifeste.
Le format plat est accepté par le validateur RAG-006/RAG-015, mais chaque ligne
porte explicitement `judgment_origin: llm`. Les wrappers et rapports portent
aussi `human_reference: false` : **ne pas les fusionner dans les sessions humaines**.

`report-rag015.json` réutilise le rapport conservateur historique : nDCG et
Recall y restent indéfinis en l'absence de référence exhaustive du corpus.
`comparison.json` et `report.md` ajoutent séparément la nDCG poolée explicitée.
`review.json` contient les divergences majeures, binaires et incertitudes,
avec références et justifications privées, sans annoter automatiquement un
accord comme vrai. Le rapport Markdown ne reproduit aucun texte citoyen.

## Tests et limites

```bash
.venv/bin/pytest
.venv/bin/ruff check .
uv lock --check
```

Les tests synthétiques couvrent v1 inchangée, la grille et l'aveuglement v2,
les BIGINT, les quotas, préfixes gelés, déduplication, protocoles/cache séparés,
les précontrôles obligatoires, refus des dépassements, interruptions, sorties
invalides, mesures incomplètes, exports et rapports reproductibles.

Les juges partagent une famille et peuvent partager leurs erreurs. Ces
pseudo-jugements ne sont ni une vérité humaine ni une mesure de fréquence des
opinions. Le pool dépend des moteurs et reste un sous-ensemble du corpus
expérimental. Aucune note humaine n'est utilisée pour ajuster v2. Les 20 requêtes
réservées, les moteurs, modèles d'embedding, index et artefacts historiques
restent inchangés. Les futurs résultats hors pool devront être jugés.
