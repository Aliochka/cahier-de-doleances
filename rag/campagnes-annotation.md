# RAG-015 — Campagnes et comparaison progressive

Les campagnes utilisent les mêmes pages locales à l'aveugle et la même
sauvegarde atomique RAG-010. Leur sélection est explicite ; aucun moteur, rang
ou score source n'est transmis à l'interface d'annotation.

## Campagnes disponibles et compatibilité

| ID | Pool immuable | Session |
|---|---|---|
| `rag010` | `evaluation/local/rag009/annotations/pool.json` | `evaluation/local/rag010/session.json` |
| `rag014` | `evaluation/local/rag014/candidates-final/pool.json` | `evaluation/local/rag015/campaigns/rag014/session.json` |

La campagne initiale conserve exactement son identité, sa graine, son ordre,
son évaluateur, ses notes, commentaires, brouillons et position. Aucune migration
n'est appliquée à son JSON. L'identité des nouvelles sessions ajoute seulement
`campaign_id` au format existant ; la version `rag010-v1` reste celle du format
des jugements, pas un identifiant de campagne.

Le catalogue vérifie les empreintes du pool, du corpus et des requêtes. RAG-014
relie ses requêtes au rapport/runs de `development-replay`, sans modifier son
manifeste gelé. Les deux pools comptent 400 couples chacun ; aucun couple ne
se recouvre dans les données réelles actuelles.

## Commandes exactes

Depuis `rag/`, l'environnement d'annotation déjà installé suffit. Les commandes
`python -m` évitent de resynchroniser l'environnement pendant une annotation.
Le nouveau point d'entrée installé est aussi `cahier-rag-campaign` après une
installation/synchronisation ultérieure du projet. Aucun GPU n'est nécessaire.

```bash
# Consulter sans créer de session ni se connecter à PostgreSQL :
.venv/bin/python -m cahier_rag.annotation.campaign_cli list
.venv/bin/python -m cahier_rag.annotation.campaign_cli status --campaign rag010

# Reprendre la campagne initiale : évalueur et graine déduits de sa session.
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.annotation.campaign_cli open --campaign rag010
```

La commande historique continue de fonctionner et cible `rag010` par défaut :

```bash
uv run --locked --extra annotation cahier-rag-annotate --evaluator ro
```

Utiliser l'identifiant d'évaluateur enregistré si ce n'est pas `ro`.
L'identité incompatible provoque un refus, jamais une réinitialisation.
Le verrou historique `rag010/session.lock` reste utilisé.

**La seconde session n'a pas été créée ni lancée par RAG-015.** Pour l'activer
explicitement lorsque vous le souhaitez :

```bash
# Crée uniquement une session vide ; ne lance aucun serveur.
.venv/bin/python -m cahier_rag.annotation.campaign_cli create \
  --campaign rag014 --evaluator ro

# Puis, quand vous souhaitez annoter :
export RAG_DATABASE_URL=postgresql:///cahier_rag
.venv/bin/python -m cahier_rag.annotation.campaign_cli open --campaign rag014
```

Ouvrir **http://127.0.0.1:8765**. Arrêter le serveur de la première campagne avant
de réutiliser ce port, ou choisir explicitement `--port 8766` pour l'autre.
Aucune option n'expose le serveur hors de `127.0.0.1`. `--env-file` reste disponible.
Le lancement direct suivant est également possible **après création** :

```bash
.venv/bin/python -m cahier_rag.annotation.cli --campaign rag014 --evaluator ro
```

La graine initiale de la seconde campagne est `20261021`, celle de RAG-010
`20261020`. Une graine personnalisée se fournit à `create --seed ...` ; `open`
reprend automatiquement la valeur stockée. Les verrous sont indépendants.
Une commande `create` sur une session existante est refusée. Un `open` de la
seconde campagne non créée est également refusé.

Les touches 0–3, commentaires, sauvegarde automatique, navigation, texte entier
et consultation de la contribution parente sont conservés. Un libellé neutre
indique la campagne courante et sa progression. Un échec de sauvegarde ne fait
pas avancer les annotations. L'interface reste compatible avec une page servie
par l'ancien processus RAG-010 jusqu'à son redémarrage.

## Exports séparés et consolidation

Toutes les destinations doivent être des **nouveaux dossiers**. Les exports
locaux peuvent contenir des commentaires humains : les conserver sous
`evaluation/local/`, ignoré par Git, sans les partager automatiquement.

```bash
.venv/bin/python -m cahier_rag.annotation.campaign_cli export \
  --campaign rag010 --output evaluation/local/rag015/exports/initiale-001
.venv/bin/python -m cahier_rag.annotation.campaign_cli export \
  --campaign rag014 --output evaluation/local/rag015/exports/complement-001

.venv/bin/python -m cahier_rag.annotation.campaign_cli consolidate \
  --output evaluation/local/rag015/references/001
.venv/bin/python -m cahier_rag.annotation.campaign_cli conflicts
```

`export` conserve le format original des jugements RAG-006 et ajoute un fichier
de métadonnées de campagne. L'export navigateur de RAG-010 garde le nom
`judgments.json` ; celui de la seconde campagne est `rag014-judgments.json`.

La consolidation lit des snapshots validés **en lecture seule**. Elle ne prend
pas le verrou d'écriture du serveur ; les remplacements atomiques garantissent
un JSON complet. Si la session évolue entre les lectures de contrôle, le rapport
est refusé et peut être relancé. Un snapshot déjà lu peut naturellement devenir
ancien si l'utilisateur poursuit ensuite l'annotation.

La clé est strictement `(query_id, document_id)`. Une note n'est jamais réutilisée
pour une autre requête. Toutes les observations conservent campagne, évaluateur,
note, commentaire, date, version d'origine, empreintes de session/pool/requêtes/
corpus. Quand plusieurs observations ont la même note, le couple est dédupliqué ;
le premier représentant selon un ordre déterministe fournit l'export compact,
et **tous les commentaires restent dans la provenance**.

Quand les notes diffèrent, le couple entre dans `conflicts.json`, sans sélection
de la note la plus récente ni d'un évaluateur prioritaire. Il est exclu de
l'export résolu et des métriques jusqu'à une adjudication explicite ultérieure.
La commande `conflicts` retourne le code 3 s'il existe un désaccord. Aucun outil
d'adjudication écrivant dans les sessions originales n'est introduit.

Fichiers consolidés :

- `reference.json` : sources, progression, observations, jugements résolus et conflits.
- `judgments.json` : format RAG-006, version d'export uniforme `rag015-consolidated-v1`.
- `provenance.json` : observations originales de chaque couple résolu.
- `conflicts.json` : observations contradictoires conservées intégralement.

La normalisation de la version concerne uniquement l'export consolidé, pas les
notes originales. Elle permet au validateur RAG-006 de lire un référentiel
commun ; les versions originales restent conservées dans les observations.

## Rapport et métriques

```bash
.venv/bin/python -m cahier_rag.annotation.campaign_cli report \
  --output evaluation/local/rag015/reports/nouveau-bilan

# Même évaluation, commande explicite et source de classements facultative :
.venv/bin/python -m cahier_rag.annotation.campaign_cli evaluate \
  --rankings evaluation/local/rag014/development-replay \
  --output evaluation/local/rag015/reports/nouvelle-evaluation
```

Le défaut réutilise les trois listes profondes de RAG-014, calculées avec les
recettes RAG-009/RAG-013 gelées. Les empreintes, les méthodes et les références
au corpus et aux requêtes sont vérifiées. Aucun moteur n'est réexécuté et aucune
requête réservée n'est évaluée. Le rapport ajoute `report.json` et `pending.json`
aux exports consolidés.

La couverture par requête et moteur distingue, pour top 5/10/20 : retournés,
jugés résolus, non jugés et conflits. Le rapport fournit les identifiants à
annoter, les requêtes insuffisamment couvertes et les résultats sans candidats.
Il identifie aussi les documents absents des deux pools : finir les campagnes
ne garantit pas à lui seul une couverture complète des premiers rangs.

Les mesures réutilisent `evaluation.metrics.evaluate` de RAG-006 :

- Pertinence binaire : notes **2 et 3**. Precision@k n'est publiée que lorsque
  tous les documents effectivement retournés dans le top k sont jugés résolus.
  Son dénominateur reste k, même si le moteur retourne moins de k résultats.
- MRR porte sur **le classement fourni**, indépendamment de k (50 rangs ici).
  Il est calculable si tous les rangs jusqu'au premier pertinent sont connus.
  Un inconnu avant ce pertinent interdit le calcul. L'absence de pertinent vaut
  zéro uniquement si toute la liste fournie est jugée. Ce n'est pas une preuve
  d'absence de document pertinent dans le reste du corpus.
- Recall@k et nDCG@k stricts exigent une référence exhaustive sur les unités de
  la partition pour cette requête ; une référence pertinente/IDCG nulle reste
  indéfinie. Aucun commutateur ne permet de déclarer arbitrairement les 60 notes
  actuelles exhaustives. nDCG utilise les gains `2**note - 1`, discount log2.
- Aucun jugement manquant ou contradictoire n'est remplacé par une note 0.
  L'absence de mesure est `null` et accompagnée d'une explication.

Une section **descriptive sur les seuls documents jugés** donne la proportion
pertinente et la note moyenne parmi les documents connus du top k. Elle expose
aussi MRR/nDCG d'un classement condensé, où les non-jugés sont retirés et les
rangs changent. L'idéal de cette nDCG est limité au référentiel jugé disponible.
Ces valeurs sont explicitement distinctes des métriques strictes : elles sont
biaisées par les documents choisis pour annotation et ne prouvent pas la qualité
générale d'un moteur. Leur profondeur effective est indiquée.

Les moyennes strictes indiquent le nombre de requêtes calculables. Les
comparaisons communes utilisent seulement les **mêmes requêtes calculables
pour les trois moteurs** ; elles ne désignent aucun gagnant. Des moyennes sur
une seule requête ne permettent aucune conclusion générale.

## Tests et validations

```bash
uv run --no-sync pytest tests/unit/test_campaigns.py tests/unit/test_annotation.py
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
uv run --no-sync pytest
uv run --no-sync ruff check .
uv lock --check
```

Tous les tests d'écriture utilisent des pools et sessions synthétiques sous
les dossiers temporaires pytest. La session réelle n'est utilisée qu'en lecture
pour un bilan et une vérification d'empreintes. Aucune seconde campagne réelle
ni annotation simulée n'est créée par les validations.
