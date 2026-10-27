# Reproduction et périmètre des fichiers

Python 3.10.12, lxml 4.8.0 disponibles via `/usr/bin/python3`. Scripts autonomes, sans bibliothèque applicative ni base. Les primitives de provenance sont reprises en lecture des audits précédents, sans les modifier.

Les entrées durables nécessaires pour rejouer l’alignement sont `data/metadata.jsonl`, `data/sample.json`, les six Stanford figés dans le cache V2 et les hypothèses V2 archivées. Les réponses OAI brutes sont conservées localement dans `.cache/`; elles ne sont pas indispensables à la réévaluation des correspondances enregistrées.

```sh
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/alignment.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/complementary.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/evaluate.py
/usr/bin/python3 docs/audits/1789-persee-stanford-alignment/checks.py
```

Ces commandes sont locales, sans réseau. Les empreintes des règles, paramètres, notices et annotations sont vérifiées. Ne pas relancer la sélection ou la création des annotations en écrasant le plan et les gels : assertions anti-écrasement. Les sorties initiales restent réexaminables sans refaire la collecte.

`fetch_metadata.py` et `collect_sample.py` documentent la collecte bornée déjà exécutée. Ils réutilisent le cache; ne pas lancer une moisson exhaustive à partir des jetons. Après perte du cache, une nouvelle collecte peut avoir d’autres datestamps/empreintes : elle constituerait une nouvelle observation, pas une reproduction binaire du service. Aucun format TEI n’est autorisé par le client.

- `metadata.jsonl` : métadonnées Persée, producteurs, champs bruts, droits, empreintes et bibliographie. Volume issu de l’identifiant structuré, pas du titre.
- `alignment-predictions.jsonl` : prédictions initiales B; scores, cinq candidats, XPath, offsets, bornes proposées et source figée.
- `complementary-predictions.jsonl` : file C, y compris ambiguïtés et limites V2 sans certification.
- `annotations.jsonl` : décisions documentaires explicites. Les citations de contrôle sont les extrémités de la **division englobante**, qui peut contenir plusieurs cahiers; elles ne remplacent pas les références de limites.
- `comparisons.jsonl` et `correspondences.jsonl` : vues comparées et registre consolidé, sans correction silencieuse des prédictions.
- `page-index.json` : labels imprimés et origine des rares interpolations. Ne pas utiliser le numéro du fichier-image comme numéro de page.
- `access-log.json`, `pagination-check.json`, gels et empreintes : preuve de collecte/version et contrôles.

Les offsets sont des positions Unicode semi-ouvertes dans `itertext()` du XML décodé. Ce ne sont pas des offsets d’octets XML. Le fichier et son SHA-256, la révision Stanford, le XPath et le lien de numérisation permettent le retour à la source. Aucune transcription Persée intégrale ni nouveau corpus d’articles n’est créé.

L’évaluation distingue propositions fortes, files de candidats, identité compatible, identité incertaine, faux rapprochement et référence de frontières. Aucun résultat « fort » n’est automatiquement marqué vérifié. Les rôles de contrôle connus et nouveaux restent séparés. La validation indépendante et son temps humain restent à réaliser.

Ruff passe avec exceptions explicites de style sur `auditlib.py` et `annotations.py`, dont les octets ont été gelés avant évaluation. La syntaxe et les relectures des sorties sont vérifiées. Un conflit initial de résolution du nom `evaluate` a relancé le script de l’audit V2; le seul fichier dont les octets avaient changé (champs de chronométrage) a été restauré avec son SHA-256 original. Les vérifications avant et après reproduction confirment désormais les 448 fichiers antérieurs inchangés. Le contrôle charge les scripts locaux par chemin explicite; voir [replay-incident.json](data/replay-incident.json).
