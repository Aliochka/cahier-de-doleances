# Corpus complet local — RAG-026

**État : corpus et index validés, recherches exploratoires terminées.**
Compte rendu : [rapport-rag-026.md](rapport-rag-026.md). Le corpus RAG-007 reste le défaut de
l'interface personnelle.

## Inventaire et précontrôle mesurés

Source `cahier_doleances_local`, PostgreSQL 17.11 ; cible `cahier_rag`, pgvector
0.8.7. Transactions sources READ ONLY, aucune modification du corpus source.

- 1 589 285 contributions, 15 792 750 lignes de réponses.
- 5 172 356 TextUnit exploitables : 5 004 470 réponses ouvertes et 167 886 « Autre ».
- 31 éléments « Autre » blancs exclus suivant `str.strip()` ; textes conservés
  sans normalisation supplémentaire. Aucun JSON incompatible ni rattachement
  incohérent constaté pendant l'audit.
- 1 688 267 unités de moins de 60 caractères, 30 843 de plus de 2 000 caractères.
- 551 000 contributions avec texte exploitable, dont 490 678 avec plusieurs unités.
- 716 347 occurrences textuelles répétées, estimées par empreinte MD5 ; aucune
  déduplication. Cette mesure ne vérifie pas les collisions MD5.

Le pilote déterministe de 100 000 unités possède 100 258 segments. Le tirage
porte sur les contributions, `hashtextextended(id,26) mod 50 = 0`, plafonné à
100 000 unités dans l'ordre des réponses. Il ne constitue pas un échantillon
représentatif. Les versions du serveur et les règles sont figées dans son manifeste.

Le pilote vérifié occupe environ 1,62 Go, dont 0,78 Go de HNSW. Enveloppe préalable
prudente du traitement complet : 303 Go libres, contre 1,42 To disponibles sur
le volume NVMe partagé avec PostgreSQL. Ces estimations comprennent stockage,
construction, temporaire et réserve ; elles ne sont pas la taille finale mesurée.

## Espaces et recettes

Les tables `rag_full.spaces`, `rag_full.documents`, `rag_full.segments` et leurs
partitions `pilot100k`/`full` sont indépendantes des tables historiques `rag.*`.
Les migrations RAG `rag_0004` à `rag_0006` créent ces structures et leurs index.
La migration ANN complète refuse un espace complet non vérifié.

BGE-M3 dense, révision `5617a9f61b028005a4858fdac845db406aefb181`, inférence BF16,
normalisation L2, stockage float32/1024 dimensions. Représentation B inchangée,
budget de 1 024 tokens incluant la question, chevauchement de 128 tokens ;
positions Unicode et empreintes traçables. Regroupement technique par longueur
pour limiter le padding, sans changement du texte préparé.

Lexical pondéré réponse seule : mêmes préparation française et formule que
RAG-009 ; statistiques calculées sur le nouveau périmètre. H1 : RRF non pondérée,
`k=60`, profondeur 50. ANN explicite, HNSW `m=16`, `ef_construction=64` ; recherche
exacte disponible. Le pilote montre une perte de voisins avec les faibles
`ef_search` : consulter les mesures, ne pas assimiler ANN à l'exact. Les plans
contrôlés utilisent effectivement HNSW ; une demande ANN peut sinon être exécutée
par un parcours exact choisi par PostgreSQL. Aucun benchmark de charge concurrente.

Les anciennes partitions documentaires sont conservées comme métadonnées pour
les documents RAG-007 ; les nouveaux documents sont sans partition expérimentale
attribuée. Aucun catalogue de requêtes réservées n'est exécuté.

## Suivi et reprise

Depuis `rag/`, définir explicitement les deux connexions locales :

```bash
export RAG_SOURCE_DATABASE_URL=postgresql:///cahier_doleances_local
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.fullcorpus.cli status --space full
cat evaluation/local/rag026/phase.json
tail -f evaluation/local/rag026/full-run.log
```

Les phases extraction/embedding ajoutent des compteurs à `progress.jsonl`.
La vérification affiche sa progression dans le journal du processus. Un ancien
`status: running` ne prouve pas que le processus est vivant : consulter aussi
les erreurs et les connexions PostgreSQL.

Pour reprendre, **vérifier qu'aucun autre processus complet ne tourne** :

```bash
.cache/embeddings-venv/bin/python -m cahier_rag.fullcorpus.cli complete \
  --directory evaluation/local/rag026 --batch-size 32 \
  >> evaluation/local/rag026/full-run.log 2>&1
```

Les checkpoints évitent de recalculer les unités vectorielles terminées.
L'insertion des segments et le checkpoint sont atomiques. L'extraction source
ferme ses transactions avant les écritures RAG. La construction HNSW est une
opération PostgreSQL transactionnelle qui doit repartir du début si interrompue ;
les documents et vecteurs demeurent persistés. Le budget de maintenance de cette
phase est local à la transaction et conditionné au précontrôle de RAM.

Artefacts, diagnostics et données restent dans `evaluation/local/rag026/`, ignoré
par Git. Les vecteurs ne sont pas gardés intégralement en RAM.

## Mesures déjà observées sur le traitement complet

- Extraction : 842,66 s, environ 14 minutes.
- Embeddings : 9 971,93 s, environ 2 h 46, 519 unités/s.
- Unités : 5 172 356 ; segments générés : 5 187 190.
- Pic de VRAM allouée : 1 976 075 264 octets ; pic RSS : 4 475 265 024 octets.

**La première vérification s'est arrêtée sur une différence d'empreinte.** Les
positions ne dépassent pas les textes sources. Le diagnostic a confirmé un double arrondi décimal sur cinq coordonnées d'un
vecteur. Le réencodage de son lot original de 256 unités reproduit exactement
le SHA-256 attendu ; le vecteur a été restauré à ces octets float32, sans changer
son empreinte ni ses métadonnées. Les preuves et différences restent dans
`diagnostics/restored-vector.json`. Le transport arrondit désormais en float32
avant sa sérialisation ; le contrôle relit le protocole binaire pgvector. La
vérification intégrale suivante a réussi, sans recalcul global des embeddings.
Tests : 574 réussis, 3 ignorés.
Les mesures finales et limites sont détaillées dans le rapport RAG-026.

## Recherche et interface après validation seulement

```bash
.cache/embeddings-venv/bin/python -m cahier_rag.fullcorpus.cli search \
  --space full --query 'Comment améliorer les transports ruraux ?' --ann
.cache/judges-venv/bin/python -m cahier_rag.personal.cli serve --corpus rag026 --ann
```

Omettre `--ann` pour une recherche exacte. Omettre `--corpus rag026` conserve
l'interface historique sur 20 000 unités. Le nouveau corpus est refusé tant que
le contrôle d'intégrité n'est pas terminé. Les générateur et reranker ne changent
pas. Aucun déploiement Wallace, modèle supplémentaire ou jugement nouveau.
