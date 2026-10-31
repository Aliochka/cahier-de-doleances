# Vérifier les cahiers de 1789 en local

Cet outil autonome lit directement les 1 305 notices de `1789/data/registry/registry.jsonl.gz` et les six XML Stanford figés déjà présents. Il ne démarre pas l’application publique, ne contacte aucune base ni aucun modèle et ne télécharge rien. Python 3.10+ et `lxml` sont nécessaires ; ils sont déjà disponibles ici avec `/usr/bin/python3`.

Depuis la racine du dépôt :

```sh
/usr/bin/python3 1789/review.py
```

Ouvrir **http://127.0.0.1:1789** dans un navigateur. Pour arrêter : Ctrl-C. Si le port est occupé, ajouter `--port 1790`. L’écoute est imposée sur `127.0.0.1` ; aucune option d’exposition réseau. Les données XML restent dans `1789/sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602/`. Si elles manquent sur une autre machine, restaurer les sources locales figées avant de lancer l’outil ; aucun téléchargement automatique n’est prévu.

## Effectuer une vérification

1. La liste affiche par défaut les **30 dossiers préparés**. Décocher « Lot initial de 30 » pour parcourir tout le registre. Utiliser la recherche, le filtre de statut ou « Priorité haute ».
2. Ouvrir un dossier : titre, notice Persée, pages, numérisation Stanford, identité, état des frontières et alertes apparaissent au-dessus du texte. Les propositions originales, contrôles antérieurs et autres candidats restent consultables. Les alertes sont traduites et dédupliquées ; elles signalent un point à vérifier, pas nécessairement une erreur. Leurs codes bruts restent accessibles dans les détails techniques.
3. Examiner les panneaux « Début » et « Fin ». Les blocs choisis sont surlignés ; leurs ID exacts sont affichés. « Élargir les deux contextes » augmente progressivement le nombre de blocs complets, jusqu’à 2 000 de chaque côté. Aucun texte de bloc n’est tronqué. Les alternatives permettent de déplacer l’ancre de début vers un autre candidat existant.
4. Pour corriger, utiliser « Choisir comme début » ou « Choisir comme fin » sur un bloc. Le dernier bloc choisi fait partie du cahier. La sélection est convertie côté Python en positions exactes ; aucune manipulation d’offset ou de XML n’est nécessaire.
5. Choisir séparément la décision de chaque extrémité. Si une limite se trouve **dans** un paragraphe, choisir « Frontière à l’intérieur d’un bloc » et expliquer le cas : cela conserve l’incertitude sans inventer une découpe. Un cahier composite non représentable par une plage continue doit rester incertain ou bloqué.
6. Saisir un nom/pseudonyme et une remarque si nécessaire. Pour valider le périmètre entier, cocher la confirmation explicite après examen des deux frontières, puis enregistrer. Une décision incertaine ou bloquée ne valide pas le parent.

Après une validation complète réussie, le dossier suivant de la liste filtrée s’ouvre automatiquement. Les décisions incertaines ou bloquées restent sur le dossier courant. Une erreur d’enregistrement ne déclenche aucun passage au suivant. À la fin de la sélection, le dernier dossier reste ouvert et un message l’indique.

Les boutons précédent/suivant suivent la liste filtrée. Un avertissement protège les modifications non enregistrées lors d’une navigation ou fermeture. Le formulaire ne considère jamais une annotation Codex comme une décision humaine. Aucun accès aux fac-similés n’est automatique : les liens s’ouvrent à votre demande.

## Journal et reprise

Le journal est `1789/data/private/document-review/decisions.jsonl`, créé à la première décision. **Il est exclu de Git** et doit être sauvegardé séparément si les décisions doivent survivre à une perte du disque. Les XML et notices originales ne sont jamais écrasés.

Chaque événement conserve l’auteur déclaré, la date UTC, les propositions originales, la référence initiale, les blocs retenus, leurs positions, les deux décisions, les remarques, les versions/empreintes des sources et le lien vers la décision précédente. Une chaîne SHA-256 et un verrou d’écriture détectent les altérations accidentelles et les écritures concurrentes ; ce ne sont ni une signature juridique ni une preuve d’identité. Une page ancienne ne peut pas écraser silencieusement une décision plus récente. Recharger le dossier en cas de conflit.

Après redémarrage du serveur, les dernières décisions sont relues et leur historique reste visible. Les états sont : proposé automatiquement, examiné par Codex, validé humainement, incertain, bloqué. Une décision liée à d’autres empreintes source est bloquée et doit être réexaminée.

Le compteur d’activité mesure approximativement le temps où la fenêtre est visible, focalisée et récemment utilisée ; pause après 60 secondes d’inactivité. Il couvre la session enregistrée, sans compter les scripts, le temps fermé ni une visite abandonnée. Ce n’est pas une étude chronométrique indépendante. Les compteurs d’acceptation/correction concernent les dernières décisions ; une « correction » sans changement d’ID n’augmente pas le compteur des frontières modifiées.

Pour un essai isolé, utiliser `--journal /tmp/mon-essai-review/decisions.jsonl`. Ne pas mélanger ces décisions synthétiques avec le vrai journal.

## Régénérer le corpus après vérification

```sh
/usr/bin/python3 1789/archives/1789-first-article-corpus/build.py
/usr/bin/python3 1789/archives/1789-first-article-corpus/verify.py
```

Les décisions humaines priment sur les contrôles Codex. Les dossiers incertains, bloqués ou liés à une ancienne source sont retirés du nouvel export et consignés dans `withheld.json`. Une correction produit une nouvelle version de périmètre et des identifiants d’unités déterministes. **Valider le parent ne valide pas automatiquement ses articles.** L’export reste limité aux 30 dossiers sélectionnés ; vérifier une autre notice ne déclenche aucune extraction massive.

Voir [le rapport du corpus](../../archives/1789-first-article-corpus/README.md) pour les formats, limites et résultats.

## Tests

```sh
/usr/bin/python3 1789/tools/document-review/test_review.py
/usr/bin/python3 1789/archives/1789-first-article-corpus/test_corpus.py
```

Les tests écrivent uniquement dans des journaux temporaires marqués synthétiques. Pour le test navigateur, Playwright et Chromium déjà présents dans le frontend sont facultatifs :

```sh
/usr/bin/python3 1789/review.py --port 17890 --journal /tmp/essai-review-navigateur/decisions.jsonl
```

Dans un autre terminal :

```sh
node 1789/tools/document-review/smoke.cjs
```

Le serveur local impose Host/Origin de boucle locale et un jeton pour chaque écriture ; il n’ajoute aucune authentification publique. L’interface locale nécessite JavaScript ; les exports et contrôles Python n’en dépendent pas.

## Mode Articles

Le même serveur propose désormais **Cahiers** et **Articles**. Redémarrer le serveur Python après la mise à jour du logiciel, puis recharger le navigateur. Le mode Cahiers et son journal restent conservés.

Le mode Articles lit les 29 parents validés et les 719 articles du premier corpus. Les unités validées ou corrigées humainement se distinguent par un fond vert, un filet latéral et un badge ✓ explicite. Un simple examen Codex ne reçoit pas ce marquage. Lire les textes en continu, puis utiliser **Valider** sur une unité ou ouvrir **Validation rapide par groupes** pour sélectionner explicitement une suite après lecture. Les anomalies et incertitudes bloquent la validation groupée. **Annuler la dernière décision** reste disponible.

L’éditeur partagé permet de choisir le début/la fin ou le point de séparation dans le texte intégral en lecture seule, de fusionner des fragments, d’ajouter un article manquant, d’attribuer un numéro et de classer les C. La prévisualisation montre le résultat avant enregistrement. Classer une prose revendicative ne la transforme pas en article historique.

Les décisions d’unités sont dans `1789/data/private/document-review/article-decisions.jsonl`, distinct du journal des cahiers et ignoré par Git. Le bouton d’export écrit dans `1789/data/review-exports/`. Les décisions liées à un ancien périmètre sont signalées et ne sont pas réutilisées silencieusement.

[Mode d’emploi complet des articles](../../archives/1789-article-review/README.md) · [Formats](../../archives/1789-article-review/DATA.md) · [Tests](../../archives/1789-article-review/TESTS.md)

### Comparer les propositions de segmentation

Le mode Articles dispose d’un panneau **« Comparer les nouvelles propositions de segmentation »**, alimenté par `1789/data/segmentation-proposals/comparison.jsonl.gz` lorsqu’il existe. Relancer le serveur après mise à jour du code.

Ce panneau ne remplace aucune unité. Il affiche les marqueurs supplémentaires, les fusions potentielles, leurs positions et les différences de plages. **« Préparer une séparation à vérifier »** ouvre l’éditeur avec une position proposée ; prévisualisation et confirmation restent obligatoires. Un numéro OCR ambigu est conservé sans attribution automatique d’un numéro historique.

Les nouvelles alertes sur les unités non validées sont également affichées dans les anomalies et empêchent leur validation groupée sans examen individuel. Une décision humaine existante reste prioritaire : aucune correction ou validation n’est effacée et aucun article n’est ressegmenté silencieusement. La comparaison peut manquer certaines erreurs OCR ; son absence d’alerte n’est pas une certification.

### Campagne de cinq cahiers tirés au sort

Dans **Articles**, la section **« Campagne : cinq cahiers tirés au sort »** donne accès aux cinq dossiers et à leur statut courant. Le tirage, la graine, les identifiants et les instructions sont conservés dans [campaigns/README.md](campaigns/README.md). Les propositions initiales restent intactes ; aucune validation n’est créée en ouvrant un dossier.
