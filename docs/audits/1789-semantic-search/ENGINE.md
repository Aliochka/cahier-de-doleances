# Configuration du moteur examinée

Code lu à `818b5464f24cac4d8537793c15c8e2c580505f88`. Aucun service public ni base de production interrogé. « Actuel » désigne le chemin de code et les artefacts locaux présents ; les paramètres effectifs d’une instance de production ne sont pas vérifiés à distance.

| Élément | Observation dans le dépôt |
|---|---|
| Modèle | [registry.py](../../../rag/src/cahier_rag/embeddings/registry.py) : `BAAI/bge-m3`, révision `5617a9f61b028005a4858fdac845db406aefb181`, dense 1024, fenêtre documentée 8192 |
| Snapshot | [snapshots.py](../../../rag/src/cahier_rag/embeddings/snapshots.py) : empreintes par fichier, poids/config requis ; snapshot local `rag/models/bge-m3/<révision>` vérifié |
| Architecture | Config locale : XLM-RoBERTa, 24 couches, taille cachée 1024, 16 têtes, 8194 positions internes ; la limite effective reste 8192 |
| Encodage | [transformers_backend.py](../../../rag/src/cahier_rag/embeddings/transformers_backend.py) : `AutoModel`, premier token CLS, mode eval/inference, attention SDPA, padding à droite ; aucun code distant ni réseau |
| Normalisation | [core.py](../../../rag/src/cahier_rag/embeddings/core.py) : norme L2 calculée après pooling, contrôles de dimension/finitude, vecteurs float32 ; aucune normalisation linguistique de la réponse |
| Requête | [service/core.py](../../../rag/src/cahier_rag/search/service/core.py) : validation NFC/trim et longueur, requête seule dans `EmbeddingInput`, sans instruction BGE ni expansion sémantique |
| Réponse GDN | [vector/preparation.py](../../../rag/src/cahier_rag/vector/preparation.py) : `Question :\n{question}\n\nRéponse :\n{réponse}` ; texte citoyen intact, pas de titre de contribution ajouté |
| Segmentation | Même fichier : budget1024, chevauchement128, frontière de phrase/paragraphe si possible ; positions Unicode dans la réponse, contexte répété par segment, aucune troncature silencieuse |
| Agrégation | [tuning/vector.py](../../../rag/src/cahier_rag/tuning/vector.py) et espaces locaux : meilleur cosinus par unité documentaire après récupération de segments |
| Lexical public | [service/core.py](../../../rag/src/cahier_rag/search/service/core.py) : recette `h1-public-v2-ts-rank`, remplace `ts_rank_cd` de la référence par `ts_rank(...,32)` |
| Score lexical | [tuning/lexical.py](../../../rag/src/cahier_rag/tuning/lexical.py), [flexible.py](../../../rag/src/cahier_rag/search/flexible.py) : 0,5 couverture IDF +0,3 couverture des termes +0,2 rang fréquentiel ; IDF `ln(1+(N-df+0,5)/(df+0,5))` |
| Normalisation lexicale | [preparation.py](../../../rag/src/cahier_rag/search/preparation.py) : retrait des termes de consigne génériques, tokenisation de requête puis lexèmes `pg_catalog.french` dans PostgreSQL ; phrases/exclusions gérées séparément |
| Statistiques | Tables de statistiques figées et vérifiées contre l’empreinte du corpus publié ; pas les statistiques de ce petit lot |
| ANN publique | Recette du service : HNSW `ef_search=1000`, candidats400, profondeur50 ; ce pilote emploie une comparaison exacte en mémoire |
| Fusion | [hybrid/core.py](../../../rag/src/cahier_rag/search/hybrid/core.py) : somme des `1/(60+rang)`, fractions exactes, poids égaux, un passage une fois par branche, départage ID en ordre C |
| Contrat | Le service/hydratation public est spécialisé GDN ; le pilote utilise ses propres dictionnaires, sans modifier `TextUnit` ou contourner ses contraintes métier |

Les artefacts RAG-013 effectivement réutilisés précisent : recette B, 1024/128, modèle et snapshot identiques, calcul bfloat16, normalisation L2, stockage float32. Leur ensemble source comprend 20000 unités /20067 segments. Seuls les 240 vecteurs sélectionnés sont copiés ; les lots sources consultés sont vérifiés sans les modifier.

Le service accepte CPU/float32 ou GPU/bfloat16 explicitement. L’expérience reprend CPU/float32 via l’adaptateur existant, avec les versions détaillées dans [encoding.json](data/encoding.json). La fiche BAAI figée est consultée comme référence du modèle ; le protocole exécuté est déterminé par le code et les entrées livrées.

## Écarts expérimentaux à conserver lors de l’interprétation

1. Le BM25 local est une référence lexicale autonome. Il emploie la préparation de requête existante, les stopwords PostgreSQL14 et Snowball français via `libstemmer`. La découpe Unicode/apostrophes et la formule ne reproduisent pas exactement le parseur ni le rang PostgreSQL public. Aucun résultat ne doit être appelé « performance exacte du lexical public ».
2. Le contexte des cahiers est documentaire, celui de2019 est une question. A/B ne change que les historiques ; un contrôle contemporain sans question n’est pas testé ici.
3. Tous les scores lexicaux d’une population utilisent sa population entière. Tous les vecteurs sont classés globalement ; aucune fusion séparée par corpus. Le calcul vectoriel lit le petit tableau joint en mémoire puis restreint aux unités admissibles pour le test historique ; cela ajoute un coût mineur au microbenchmark historique, sans changer ses scores/rangs.
4. Le maximum sur segments permet d’afficher un article entier ; ce n’est pas une moyenne des revendications de l’article. Un article long/multithématique peut obtenir un score élevé pour une partie seulement.
5. CPU float32 et vecteurs GPU bfloat16 restent légèrement différents. Le contrôle des16 textes et la sensibilité des rangs sont fournis, sans les présenter comme une équivalence numérique parfaite.
6. Aucun état PostgreSQL, index GIN/HNSW, publication de génération, API, frontend ou configuration privée n’est modifié ou nécessaire à cette expérience.
