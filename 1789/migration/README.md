# Réorganisation du travail 1789

Déplacement réalisé sans extraction, téléchargement, accès PostgreSQL, embedding ni modification de l’application publique.

## Correspondances

- `docs/audits/1789-*` et `docs/audits/multicorpus-scale-study` → `1789/archives/`.
- `docs/tools/1789-document-review` → `1789/tools/document-review`.
- Six XML Stanford → `1789/sources/stanford/<révision>/`.
- Caches de collecte Persée → `1789/sources/persee/`.
- Jeux actifs du registre, du corpus initial, des exports et des propositions → `1789/data/`.
- Journaux et sessions actifs → `1789/data/private/document-review/`.
- Segmenteur existant → `1789/extraction/segmentation.py`.

`paths.json` décrit les routes. Des liens symboliques **internes à `1789/`** maintiennent l’accès relatif depuis les anciennes expériences aux jeux actifs uniques. Aucun lien ni copie de compatibilité n’est maintenu sous les anciens dossiers `docs/`.

## Données et histoire

L’inventaire préalable local contient 2 256 fichiers représentant 209 855 170 octets. Tous sont retrouvés. Les fichiers de données, textes et journaux conservent leurs empreintes ; seuls des fichiers de code, documentation et exclusion Git ont été adaptés. Quelques caches Python compilés ont été régénérés par l’interpréteur et ne sont pas assimilés à des données documentaires.

Les manifestes, protocoles, résultats, numéros, identifiants, offsets et journaux historiques ne sont pas réécrits. `cahier1789_paths.resolve_reference()` traduit leurs chemins au moment d’une lecture. `frozen_match()` accepte une empreinte identique ou une correspondance de code/documentation explicitement inventoriée dans `code-path-changes.json`.

Cette compatibilité **ne neutralise pas un contrôle qui échouait déjà avant la réorganisation** : si une empreinte historique ne correspond pas à l’état antérieur au déplacement, elle reste refusée. Les anciens audits conservent les conclusions de leur version ; ils ne sont pas recalculés pour les rendre artificiellement conformes à un état plus récent.

Les copies préalables de code et de documentation, ainsi que l’inventaire complet, restent sous `.local/`, ignoré par Git. Les journaux actifs sont protégés par leurs propres exclusions et par un répertoire privé d’accès limité. Aucune sauvegarde externe n’a été créée.

## Vérifications effectuées

- Vérification de présence et d’empreinte de toutes les données inventoriées, y compris les fichiers ignorés par Git.
- Trois fichiers de règles d’extraction **strictement identiques** à l’état antérieur.
- Six volumes Stanford chargés, 1 305 notices, 29 parents, 719 articles initiaux.
- Rejeu des 346 événements Articles et des 33 événements Cahiers : **333 articles humains actuels, aucune décision d’article périmée**.
- Contrôles matériels des 29 parents et des **1 516 unités stockées**, sans lancer le constructeur de corpus.
- Contrôle du bilan humain avec `--read-only`, sans réécriture de ses résultats.
- **36 tests Python** de l’outil local, avec journaux de tests temporaires séparés des journaux réels. Les cas de segmentation utilisent des textes synthétiques ; aucun corpus n’est réextrait.
- Tests navigateur des modes Cahiers et Articles : correction, validation, historique, reprise, navigation automatique, comparaison des propositions, priorité humaine, campagne et maintien de la position de lecture.
- Responsive 320, 375, 768 et 1280 px, texte à 200 %, navigation clavier ; aucune erreur JavaScript relevée.
- Vérification syntaxique des scripts Python déplacés ; lint des composants actifs et du code de migration.
- Contrôle des liens Markdown locaux et des exclusions Git : aucun journal privé ou nouveau gros fichier n’est exposé.

Les sorties détaillées des tests restent dans `.local/`. La synthèse est `verification.json`. Les anciennes expériences d’inférence, d’encodage, d’extraction ou de collecte n’ont pas été réexécutées. Les environnements et modèles partagés sous `rag/` sont inchangés.

## Refaire les contrôles sûrs

Depuis la racine :

```sh
python3 1789/migration/verify.py
python3 1789/archives/1789-human-review-quality/check.py --read-only
python3 -m unittest discover -s 1789/tools/document-review -p 'test_*.py'
```

`move_workspace.py` documente l’opération unique et refuse de recommencer si son inventaire existe. Ne pas l’utiliser comme outil de synchronisation. Le contrôle complet nécessite l’inventaire local ; un clone sans les données privées ne peut pas certifier leur présence.
