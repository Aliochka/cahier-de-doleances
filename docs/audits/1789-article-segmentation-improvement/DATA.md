# Reproduction et formats

## Sources inchangées

- Parents et unités : `../1789-first-article-corpus/data/parents.jsonl.gz`, `units-A/B/C.jsonl.gz`.
- Règles de départ : `../1789-extraction-v2/rules_v2.py`, non modifiées, chargées par les utilitaires existants.
- Stanford local : `../1789-extraction-v2/.cache/sources/`, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`.
- Instantané d’analyse du journal : `.local/article-decisions.snapshot.jsonl`, privé, ignoré par Git. Le journal réel demeure `../../tools/1789-document-review/.local/article-decisions.jsonl`.

Tous les chemins de commande ci-dessous partent de la racine du dépôt. Aucune dépendance ajoutée ; Python système avec lxml déjà installé.

```sh
python3 docs/audits/1789-article-segmentation-improvement/experiment.py evaluate
python3 docs/audits/1789-article-segmentation-improvement/summarize.py
python3 -m unittest discover -s docs/tools/1789-document-review -p 'test_*.py'
```

`experiment.py freeze` refuse d’écraser le gel existant. `windows --volume 1` (jusqu’à 6) permet de relire la source des fenêtres. `make_reference.py` encode les décisions de lecture explicites et refuse d’écraser une référence existante ; **il ne constitue pas un nouvel annotateur automatique**. Pour reproduire les mesures, utiliser la référence conservée. Le code et les fenêtres sont contrôlés contre leurs empreintes gelées avant chaque évaluation.

## Sorties

`data/comparison.jsonl.gz` : une ligne par parent avec :

- Identifiant et version du parent, empreinte Stanford, version de méthode.
- Anciennes plages V2 et nouvelles propositions (`new`), textes exacts par `spans`, marqueur original, indices, statut B explicite.
- Candidats reconnus et statuts `existing`, `proposed`, `suspect`, `rejected`.
- Changements de rôle, liste des références initiales non reproduites.
- Table `correspondence` : ancien identifiant, anciennes plages, identifiants des propositions qui les recouvrent. Aucun ancien identifiant n’est réattribué à une autre segmentation.

Les identifiants de proposition utilisent le hachage de la version parentale, de ses positions et de la version d’extraction. Ils ne deviennent pas automatiquement des identifiants de décisions humaines. Les identifiants humains issus des corrections sont toujours calculés et conservés par l’outil existant, jamais remplacés par cette table.

Les positions sont des indices Unicode demi-ouverts dans le texte XML décodé par les utilitaires de provenance existants. Elles ne désignent pas des octets du fichier XML. Le `xpath` du marqueur et les références XML des unités restent disponibles. Les notes exclues des tranches d’une proposition restent dans le document parent conservé.

- `data/development-comparison.json` : corrections de l’instantané comparées aux règles, sans publication du journal nominatif.
- `data/validation-plan.json`, `validation-reference.json`, `freeze.json` : sélection, référence et gel.
- `data/metrics.json`, `checks.json`, `browser-checks.json` : résultats et contrôles.
- `data/review-notes.json` : deux signalements documentaires Codex ajoutés après évaluation, affichés séparément des prédictions automatiques.
- `data/suspects.json` : alertes automatiques ; les cas non détectés sont documentés séparément dans le rapport.
- `prior-files-sha256.json`, `data/journal-snapshots.json`, `manifest.json` : provenance et intégrité.

Les fichiers de données contenant les textes complets, les résultats volumineux et les journaux sont ignorés par Git. Les petites configurations, références de positions et métriques peuvent être suivies. Aucun modèle, embedding ou nouveau corpus n’est téléchargé.

## Interface

```sh
python3 docs/tools/1789-document-review/server.py
```

Le serveur habituel reste lié à l’interface de boucle locale. Dans Articles, le nouveau panneau utilise le fichier local de comparaison lorsqu’il est présent et compatible avec le parent. S’il manque ou correspond à une autre version, le découpage existant continue de fonctionner. Aucun fichier de comparaison ne doit être substitué aux `units-A/B/C` du corpus initial.

Tests navigateur : démarrer `article_test_server.py --port 17896`, puis exécuter `REVIEW_TEST_URL=http://127.0.0.1:17896 node docs/tools/1789-document-review/segmentation-smoke.cjs`. Ce serveur utilise uniquement des journaux temporaires synthétiques. Relancer une fixture neuve pour `article-smoke.cjs`.
