# FORMS-001 — Audit des pages Formulaires et Statistiques

Date : 20 octobre 2026. Périmètre : Hal9000, base `cahier_doleances_local`.

**Audit et conception uniquement.** Aucun code source, configuration, corpus ou
schéma PostgreSQL modifié ; aucune migration, intervention sur Wallace ou
implémentation de la fusion. Seul ce rapport est ajouté au dépôt. Les scripts
ponctuels et relevés de mesure sont restés dans `/tmp`.

## 1. Résumé et recommandation

La fusion est pertinente, mais doit être précédée d'une correction du mode de
production des statistiques. Le principal coût constaté est PostgreSQL : les
consultations recalculent les sélections, les contributions distinctes et les
réponses comportant un champ « Autre ». Seul le nombre de lignes de réponses par
question est déjà précalculé.

Le dashboard du questionnaire rapide Organisation de l'État a répondu en **3,66 s**
lors de la mesure bornée, dont **3,37 s** pour l'agrégation des contributions et des
champs « Autre ». Le rendu SSR isolé du même dashboard prend **32 ms** environ.
Les graphiques ne sont pas chargés à l'ouverture : ils attendent actuellement le
dépliage. Ils ne peuvent donc pas expliquer à eux seuls l'activité initiale.

Architecture recommandée :

1. Préparer des instantanés statistiques persistants, versionnés et publiés après
   validation, hors requête visiteur. Conserver les règles de calcul actuelles.
2. Enrichir le contrat Formulaire avec toutes ses questions, leurs compteurs et
   leurs statistiques précalculées, en un appel et un nombre constant de lectures.
3. Présenter `/forms/{id}` comme une page continue : introduction, sommaire,
   questions dans l'ordre source, graphiques directement visibles, détails repliés.
4. Pour ces graphiques simples, privilégier des barres HTML/CSS rendues en SSR,
   avec libellés et valeurs textuelles visibles. Aucune nouvelle bibliothèque
   n'est nécessaire ; Recharts reste disponible pour les autres pages.
5. Rediriger l'ancienne page Dashboard vers la page Formulaire par une redirection
   permanente côté serveur. Conserver Enquêtes et les pages Questions.

## 2. Architecture actuelle

### Pages et flux

| Page | Loader / contrat | Contenu |
|---|---|---|
| `/enquetes` | Liste des formulaires | Catalogue à conserver |
| `/forms/{id}` | `getForm()` → `GET /api/v1/forms/{id}` | Nom, nombre de questions, liste ordonnée, lien Dashboard si présence de choix |
| `/forms/{id}/dashboard` | `getFormStats()` → `GET /api/v1/forms/{id}/stats` | Questions à choix uniquement, métriques, tableaux, graphiques à déplier |
| `/questions/{id}-{slug}` | Détail puis réponses ou statistiques | Consultation individuelle à conserver |

Les loaders attendent l'API avant de rendre le contenu essentiel. Les appels
utilisent un signal d'annulation, omettent les cookies publics et ont un délai de
20 s. Formulaire et Dashboard renvoient actuellement `private, no-store`.
Il n'existe pas de cache statistique dans `app/choice_stats.py`.

La page Formulaire demande **deux SELECT** : résumé du formulaire et toutes ses
questions. Le Dashboard demande **cinq SELECT**, plus un `SET LOCAL` de protection :

| Lecture Dashboard | Source | Travail |
|---|---|---|
| 1 | `forms LEFT JOIN questions` | Vérifier le formulaire, compter ses questions |
| 2 | `questions` | Toutes les questions, triées par `COALESCE(position,999999), id` ; choix retenus ensuite en Python |
| 3 | `question_stats` | Lire les compteurs existants des questions à choix |
| 4 | `options LEFT JOIN answer_options` | Recompter chaque option avec `count(ao.answer_id)` |
| 5 | `answers` | Compter les tableaux `other_text` non vides et les contributions distinctes par question |

Ce traitement est déjà effectué **en lot**, sans N+1 ni requête par question.
Il ne charge pas les réponses individuelles en Python, mais doit parcourir leurs
lignes dans PostgreSQL. Un nombre constant de requêtes n'implique pas un coût faible.

### Graphiques et rendu

`Statistics` affiche actuellement cinq métriques, une explication méthodologique,
un tableau complet et, sur Dashboard, un `<details>` « Afficher le graphique ».
`stats-chart.tsx` est importé par `React.lazy` après hydratation et ouverture.
Les barres sont horizontales, monochromes, graduées en effectifs ; leurs labels
sont remplacés par des numéros à retrouver dans le tableau. Les valeurs et libellés
complets sont accessibles au survol, pas directement inscrits sur les barres.

L'animation Recharts est déjà désactivée. La bibliothèque est partagée : un seul
chargement du chunk sert aux différents graphiques. Sans JavaScript, les tableaux
SSR restent disponibles, mais les graphiques ne sont pas rendus. L'actuel
accordéon cache donc précisément ce que la future page doit rendre visible.

Sources principales : [routes Formulaire et Dashboard](../frontend/app/routes),
[statistiques React](../frontend/app/features/questions/statistics.tsx),
[graphique Recharts](../frontend/app/features/questions/stats-chart.tsx),
[route API Formulaires](../app/routers/api_forms.py),
[calculs partagés](../app/choice_stats.py),
[lectures Formulaires](../app/services/forms.py).

## 3. Méthode et mesures de performance

### Protocole borné

- Inventaire des sept formulaires, questions, options, compteurs, index et triggers
  par lectures ciblées des petites tables et des catalogues PostgreSQL.
- Un appel au détail du formulaire 5 ; quatre appels statistiques : formulaires
  7, 2, 5, puis 7 une seconde fois. Aucune boucle de charge ni requête concurrente.
- Routes FastAPI réelles dans une application ASGI temporaire limitée au routeur
  Formulaires ; pas de chargement BGE-M3 ou de service de recherche. Connexions
  applicatives avec `default_transaction_read_only=on` pour cette mesure seulement.
- Chronométrage des instructions via les événements SQLAlchemy et du parcours
  HTTP ASGI complet. Ce chronométrage SQL inclut l'aller-retour du pilote ; il
  n'est pas une mesure séparée du temps CPU du serveur PostgreSQL.
- Deux plans **estimés** sans exécution pour le formulaire 2. Une seule exécution
  `EXPLAIN ANALYZE`, limitée à la question 159, avec délai maximal de 3 s ; elle
  a terminé en 341 ms. Les autres lectures statistiques gardent la limite SQL
  existante de 5 s par instruction. Aucun `ANALYZE`, réglage global ou index ajouté.
- Isolation du rendu : build SSR existant, alimenté par les données statistiques
  relevées et les métadonnées réelles, rejouées en mémoire. Quatre chargements
  navigateur locaux, dont un sans JavaScript ; ouverture unique des douze
  graphiques du formulaire 2. Aucun recalcul SQL pendant cette phase.

Le rôle lecteur RAG ne dispose pas de SELECT sur `forms` : l'audit a donc employé
la connexion applicative avec transactions en lecture seule, sans changer ses
droits. Aucun secret n'a été copié dans le rapport.

### Temps des endpoints et poids JSON

| Endpoint | Total HTTP ASGI | Agrégation options | Agrégation réponses / contributions / Autre | JSON brut |
|---|---:|---:|---:|---:|
| `/api/v1/forms/5` | 11,4 ms | — | — | 11 336 octets |
| `/api/v1/forms/7/stats` | 445 ms | 65,5 ms | 376 ms | 1 326 octets |
| `/api/v1/forms/2/stats` | 3 664 ms | 290 ms | 3 371 ms | 11 096 octets |
| `/api/v1/forms/5/stats` | 1 133 ms | 234 ms | 896 ms | 5 932 octets |
| `/api/v1/forms/7/stats`, deuxième passage | 297 ms | 14,2 ms | 280 ms | 1 326 octets |

Les trois petites lectures du dashboard représentent chacune moins de 0,4 ms
sur ces passages. La différence entre le total ASGI et la somme des instructions
est de quelques millisecondes, incluant le traitement FastAPI/Pydantic,
les échanges Python et la sérialisation. Ce n'est pas une mesure CPU pure de
FastAPI. Le premier détail inclut aussi l'ouverture initiale de connexion.

La répétition du formulaire 7 exécute à nouveau les cinq SELECT. Le réchauffement
des caches PostgreSQL/OS réduit le temps, mais ne supprime pas le calcul. Ces
mesures ne permettent pas d'annoncer une latence garantie ni une capacité sous charge.

### Ce que montrent les plans PostgreSQL

**Constaté par exécution sur la question 159 :**

- 155 657 réponses regroupées pour une seule question.
- Scan bitmap parallèle sur `answers`, avec l'index `idx_answers_question_id`.
- Deux workers lancés en complément du processus principal.
- Tri des contributions par `external merge`, avec fichiers temporaires sur disque.
- Au niveau racine du plan : 8 757 blocs temporaires lus et 8 774 écrits, soit
  environ 68,4 et 68,5 Mio pour des blocs de 8 Kio. Ne pas additionner une seconde
  fois les compteurs des nœuds enfants.
- 71 405 blocs lus vers les buffers PostgreSQL, environ 558 Mio ; cela ne prouve
  pas autant de lectures physiques sur SSD, le cache du système pouvant intervenir.
- JIT présent dans le plan, 14 fonctions. Sa durée propre n'a pas été isolée.
- Temps d'exécution PostgreSQL : **340,9 ms** ; planification : **0,39 ms**.

**Prévu par le plan estimé, non confirmé par un EXPLAIN ANALYZE du formulaire 2 :**
scan séquentiel parallèle d'`answers`, tri et `Gather Merge` pour environ
3,89 millions de lignes retenues. Le comptage des options est prévu en boucles
indexées avec `Index Only Scan` sur `(option_id, answer_id)`.

Cela explique une activité CPU et des entrées/sorties importantes malgré un petit
JSON. Il n'est pas nécessaire d'invoquer le GPU ou BGE-M3 : ces routes ne les utilisent
pas. L'augmentation de `work_mem`, l'ajout d'un index ou la désactivation du JIT
ne sont pas validés par cet audit et ne sont pas la correction prioritaire.

Les vues `pg_stat_user_tables` consultées exposaient des compteurs nuls et des dates
d'analyse absentes. Elles ne permettent pas de reconstituer l'historique de charge.
En revanche, `pg_class.reltuples` contient des estimations : environ 15,79 millions
de réponses et 11,68 millions de liens d'options. On ne peut pas conclure à une
absence de statistiques du planificateur à partir des seules vues précédentes.

### SSR et navigateur, isolés de PostgreSQL

| Page, données API rejouées en mémoire | SSR complet jusqu'au HTML | HTML brut | Gzip indicatif calculé hors transport |
|---|---:|---:|---:|
| Formulaire 2, Dashboard, premier passage | 31,6 ms | 43 986 octets | 8 324 octets |
| Formulaire 5, 37 questions | 9,4 ms | 35 928 octets | 7 132 octets |
| Formulaire 5, Dashboard, 7 choix | 8,5 ms | 27 953 octets | 5 971 octets |
| Formulaire 2, Dashboard sans JavaScript | 12,2 ms | 43 986 octets | 8 324 octets |

Le serveur de mesure n'appliquait pas de compression HTTP : les tailles gzip
ci-dessus sont comparatives, pas des transferts observés. Le JSON statistique est
également sérialisé dans les données du loader, en plus du HTML affiché.

Sur Chromium local, au premier dashboard : environ **40 ms de ScriptDuration**,
**63 ms de TaskDuration** et **8,5 ms de LayoutDuration** cumulés au relevé initial.
Aucun graphique monté et aucune requête du chunk graphique à ce stade. Sans JS,
les douze tableaux restent présents et aucun graphique n'est créé.

L'ouverture des douze graphiques représente environ **97 ms de ScriptDuration**
et **186 ms de TaskDuration supplémentaires** dans ce parcours. La séquence
pilotée dure 1,35 s, incluant clics, attentes et défilements : ce n'est pas 1,35 s
de calcul JavaScript pur. Un seul chunk graphique est chargé : **374 261 octets
non compressés**, environ 108 Kio gzip d'après le build existant.

Le contrôle `networkidle` du navigateur inclut une attente de stabilisation de
500 ms ; les temps muraux de chargement de 0,52 à 0,61 s ne doivent pas être pris
pour le coût du rendu. Ces résultats sont ceux d'un ordinateur local rapide,
sans limitation CPU ni réseau mobile. Le coût d'un montage simultané de tous les
graphiques dans la future page n'a pas été mesuré.

### Diagnostic établi et hypothèses

| Établi | À vérifier ultérieurement |
|---|---|
| Agrégations exécutées à chaque visite | Charge observée historiquement sur la machine, hors fenêtre de mesure |
| Contributions distinctes et JSON dominent les mesures | Part CPU propre du JIT et coûts sur caches froids |
| Parallélisme et tris temporaires réels | Saturation sous concurrence, évictions mémoire, latence disque physique |
| Pas de N+1 Dashboard | Latence sur CPU/réseau mobiles et autres navigateurs |
| Graphiques absents au chargement initial | Coût de tous les graphiques montés automatiquement |
| Payloads et SSR modestes sur les pages mesurées | Taille exacte et performance de la future page fusionnée |

Le timeout SQL est **par instruction**, pas par dashboard complet. Le client SSR
attend au plus 20 s et le middleware FastAPI général 29 s. Des recherches
statistiques concurrentes peuvent donc occuper longtemps des connexions et
plusieurs processus PostgreSQL. L'annulation HTTP ne possède pas ici le
mécanisme coopératif spécifique à SEARCH-003 : ne pas supposer qu'un départ du
visiteur interrompt immédiatement un SELECT synchrone en cours.

## 4. Inventaire statistique et sémantique

### Corpus local réellement observé

| ID | Questionnaire | Questions | Choix uniques | Choix multiples | Ouvertes |
|---|---|---:|---:|---:|---:|
| 2 | Organisation de l'État — rapide | 12 | 9 | 3 | 0 |
| 4 | Organisation de l'État — détaillé | 33 | 8 | 0 | 25 |
| 5 | Démocratie et citoyenneté — détaillé | 37 | 7 | 0 | 30 |
| 7 | Fiscalité et dépenses publiques — détaillé | 8 | 0 | 1 | 7 |
| 10 | Transition écologique — détaillé | 16 | 5 | 1 | 10 |
| 11 | Démocratie et citoyenneté — rapide | 7 | 6 | 1 | 0 |
| 12 | Transition écologique — rapide | 7 | 6 | 1 | 0 |
| **Total** | **7 formulaires** | **120** | **41** | **7** | **72** |

Les 120 questions ont une position et un compteur. Les choix uniques ont entre
2 et 5 options ; les choix multiples entre 3 et 5. **27 questions sont des binaires
stricts « Oui / Non »** d'après leurs modalités. Il existe aussi des oppositions
« Bonne chose / Mauvaise chose », des catégories ordinales de distance, et des
choix à trois modalités comprenant « Je ne sais pas ».

Le cas « nombreuses options » reste donc une préparation de composant : il n'y
a pas actuellement de question à vingt modalités à optimiser. Les champs
`section` sont renseignés, avec 45 valeurs distinctes dans le corpus ; ils ne sont
pas exposés par l'API Formulaire actuelle. Leur découpage doit être examiné avant
d'en faire des titres de regroupement. L'ordre des questions reste prioritaire.

Les rapides et détaillés sont des questionnaires distincts, avec leurs propres
questions et contributions. Ne pas additionner leurs réponses pour produire un
total de participants ou une proportion thématique globale. Le nombre maximum
de graphiques actuel sur un formulaire est **12**, et non 37 : le formulaire de
37 questions comprend seulement sept questions à choix.

### Données et dénominateurs

| Mesure | Définition actuelle | Disponibilité |
|---|---|---|
| `total_answers` | Lignes `answers` de la question, pas personnes uniques | Précalculé dans `question_stats.answers_count` |
| `answered_contributions_count` | `COUNT(DISTINCT contribution_id)` pour la question | Recalculé à chaque lecture statistique |
| Effectif d'une option | Nombre de liens `answer_options` de cette option | Recalculé ; clé primaire `(answer_id, option_id)` évite un même lien dupliqué |
| `other_text_answers_count` | Nombre de réponses avec tableau JSON `other_text` non vide | Recalculé ; une réponse compte une fois même avec plusieurs textes |
| `total_option_selections` | Somme des liens d'options, hors Autre | Dérivé des agrégations d'options |
| `total_selections` | Somme des catégories, Autre inclus une fois par réponse concernée | Dérivé ; peut dépasser le nombre de réponses |
| Pourcentage d'une catégorie | `100 × effectif / total_answers`, arrondi à deux décimales | Dérivé, zéro si dénominateur nul |

`question_stats` est effectivement maintenu par les triggers statement-level
`gdn_stats_insert`, `gdn_stats_delete`, `gdn_stats_update` observés en base, avec
tables de transition. Les anciens triggers ligne à ligne présents dans une
migration historique ne décrivent plus le mécanisme actif. Voir
[migration des compteurs par lot](../migrations/versions/gdn_bulk_counters.py).

Aucun agrégat persistant par option, compteur distinct par question ou vue
matérialisée n'a été trouvé dans le schéma public. `answer_valid_stats` contient
un compteur **global** de textes d'au moins 60 caractères : il ne remplace pas les
statistiques par formulaire ou par question.

### Points d'interprétation à préserver

- Les trois formulaires statistiques mesurés donnent `total_answers =
  answered_contributions_count` sur chaque question examinée. Ce constat ne
  justifie pas de remplacer partout le `COUNT DISTINCT` par le compteur : la
  contrainte historique autorise plusieurs positions pour une paire contribution /
  question. L'import structuré valide actuellement une réponse par question,
  mais il faut préserver le contrat pour les autres données historiques.
- Sur le choix multiple du formulaire 7, question 159 : **155 657 réponses**,
  **189 150 sélections d'options**, **91 717 réponses avec Autre**. Le total des
  catégories atteint **280 867** et leur somme arrondie **180,44 %**. Ce n'est pas
  une erreur à corriger en ramenant artificiellement les barres à 100 %.
- Les trois choix multiples du formulaire 2 atteignent respectivement environ
  172,79 %, 162,46 % et 118,04 %. Les pourcentages sont par réponse, pas par sélection.
- « Autre » peut accompagner une option : ce n'est pas nécessairement une part
  disjointe d'un tout. Conserver `kind=other_text`, son effectif et sa définition.
- Les choix uniques observés sur les formulaires 2 et 5 totalisent 100 % ; ce n'est
  pas une certification de tout le corpus. Arrondis, réponses sans option ou
  incohérences doivent être pris en compte avant d'utiliser une barre à 100 %.
- Une absence de ligne `question_stats` est actuellement ramenée à zéro par le
  service. La future préparation doit la traiter comme une anomalie de complétude
  à vérifier, sans publier un faux « aucune réponse ».

### Questions ouvertes et données manquantes

Le compteur historique permet de présenter « N réponses enregistrées » pour les
questions ouvertes. Il ne mesure ni les personnes, ni un thème, ni la qualité des
textes. Il n'existe pas de répartition statistique sémantique précalculée.

**Attention à la navigation actuelle :** `app/services/questions.py` utilise un
seuil de 60 caractères pour les listes de réponses ouvertes. Le compteur de toutes
les lignes ne correspond donc pas nécessairement au nombre de témoignages visibles
sur cette page. Éviter « N réponses consultables » ou un décompte exact du lien.
Ce ticket ne propose pas de changer le seuil ni d'ajouter une recherche filtrée.

Les types `number`, `date`, `scale`, `free_text` sont prévus dans certains libellés
frontend, mais n'apparaissent pas dans les 120 questions locales : aucun histogramme
numérique ou temporel ne peut être recommandé comme besoin actuel. Pour un type
futur inconnu, garder le texte de la question et son lien, sans inventer de graphique.

Il manque notamment un total précalculé des contributions distinctes par formulaire,
un effectif d'éligibles pour les questions conditionnelles, et un taux de réponse
par question fondé sur ce dénominateur. Ne pas fabriquer ces indicateurs en sommant
les questions. Les compteurs existants ne mesurent pas des personnes uniques.

## 5. Structure proposée pour la page fusionnée

```text
Retour aux enquêtes
Titre et présentation factuelle du questionnaire
Nombre de questions · version rapide/détaillée si donnée validée
Bref repère : contributions volontaires, pas sondage représentatif

Sommaire : liens vers toutes les questions

Question 1 — titre et type
    Graphique principal et libellés/valeurs visibles, ou invitation aux témoignages
    Base : N réponses enregistrées ; précision choix multiples si nécessaire
    Voir les détails [accordéon : tableau, effectifs, méthode]
    Consulter la page de cette question
    Retour au sommaire

Question 2 … jusqu'à la dernière, sans pagination ni virtualisation
```

Le sommaire est une liste ordonnée dans un `<nav aria-label="Sommaire des
questions">`. Chaque section a un h2 et une ancre **`question-{id}`**, indépendante
de son libellé et de sa position. Le numéro affiché suit la position originale ;
le tri de secours actuel par ID reste documenté pour une position manquante future.

Les graphiques et les titres ne sont jamais enfermés dans l'accordéon. Pour les
questions ouvertes, afficher le compteur avec son intitulé exact et « Consulter
les réponses textuelles », vers la page Questions existante. Aucun témoignage
individuel n'est chargé sur la page Formulaire.

Un sommaire de 37 entrées peut occuper de la hauteur : liste lisible, liens à la
ligne, éventuellement deux colonnes sur grand écran, une seule sur mobile.
Ne pas masquer ces liens derrière un contrôle qui dépend de JavaScript. Pas de
menu latéral fixe imposé ni de virtualisation qui casserait les ancres et la
recherche native du navigateur. Les sections peuvent rester de simples blocs
SSR : 37 questions et sept petits graphiques sont une taille raisonnable à valider.

La présentation utilise le nom public et les métadonnées réellement disponibles.
`forms` ne contient pas de description éditoriale : ne pas en inventer une ni
exposer automatiquement son champ interne `source` ou ses métadonnées d'import.

## 6. Visualisations recommandées

| Données | Recommandation | Précautions |
|---|---|---|
| Binaire strict Oui/Non | Barre proportionnelle à 100 %, légende textuelle visible avec les deux effectifs et pourcentages | Seulement si choix exclusifs et couverture complète validés ; N nul → état vide |
| Autre binaire exhaustif | Même possibilité, ou deux barres horizontales | Ne pas appliquer automatiquement le code couleur d'un jugement favorable/défavorable |
| Choix unique à 3–5 modalités | Barres horizontales par pourcentage, libellés au-dessus et valeurs à côté | Ordre source pour catégories ordinales ; axe commun partant de zéro |
| Choix multiples | Barres horizontales indépendantes, normalement sur 0–100 % par option | Mention visible « Plusieurs choix possibles » ; jamais barre empilée à 100 % |
| Autre texte | Ligne/barre distincte, avec sa définition | Ne pas le confondre avec une option exclusive ou des textes comptés individuellement |
| Nombreuses modalités futures | Barres horizontales, hauteur adaptée aux libellés | Aucune troncature silencieuse ; classement décroissant seulement pour catégories nominales, avec règle stable et explicite |
| Réponse ouverte | Compteur simple et accès aux témoignages | Pas de camembert, nuage de mots ou résumé thématique inventé |

Les libellés et valeurs sont lisibles **sans survol ni clic**. Sur mobile, mettre
le libellé au-dessus de chaque barre et le couple « effectif · pourcentage » dans
le flux ; les petites parts d'une barre empilée gardent leurs valeurs à l'extérieur.
Garder les options à effectif nul visibles. Ne pas transformer les arrondis des
valeurs affichées pour forcer leur somme à 100 % ; calculer les largeurs depuis
les effectifs et conserver la méthode d'arrondi publique.

### Couleurs

Créer des jetons dédiés aux graphiques, cohérents avec le bleu existant. Une base
possible à valider visuellement : `#203A8F`, `#176B68`, `#876400`, `#71539B`,
`#A14F2B`, `#526D37`. Leurs contrastes calculés avec la surface actuelle `#fbfaf6`
sont respectivement d'environ 9,75 ; 6,02 ; 5,22 ; 5,89 ; 5,48 ; 5,58:1.

Ces calculs ne prouvent pas le contraste entre toutes les couleurs voisines.
Pour des segments contigus, prévoir séparateurs ou bordures ; laisser les textes
sur le fond de page plutôt qu'à l'intérieur des petites surfaces. Les libellés,
positions et valeurs portent le sens : aucune opposition rouge/vert exclusive,
aucune signification de couleur imposée à toutes les questions politiques.

### Composants et dépendances

Recharts **3.10.1** est déjà installé et sert aux pages Questions. Ses imports
différés, `accessibilityLayer` et l'absence d'animation sont réutilisables pour des
besoins futurs. Le composant actuel doit cependant être adapté pour afficher
libellés et valeurs et ne rend pas ses graphiques en SSR.

Pour cette page, recommander une représentation **HTML/CSS déterministe** : liste
sémantique de modalités, texte visible, barre décorative dont la largeur dérive
des données validées. Elle couvre les 2–5 modalités présentes, fonctionne sans JS,
évite le chunk Recharts et les observateurs de redimensionnement pour chaque
question. Un SVG SSR simple reste une alternative si une forme graphique l'exige.
Il n'est pas nécessaire d'ajouter Chart.js, D3 ou une autre bibliothèque.

Ne pas supprimer globalement Recharts ni le composant `Statistics` : la page
individuelle Question les utilise encore. Extraire les éléments utiles
(formatage français, tableau et méthode) plutôt que changer implicitement toutes
les pages dans le ticket de fusion.

## 7. Stratégie de performance recommandée

### Précalcul persistant avant les requêtes visiteurs

La base applicative demeure la référence ; aucune statistique n'est calculée à
partir de la fenêtre de recherche hybride ou des documents RAG.

Recommandation : stocker un **instantané public par question**, avec génération,
date de calcul et version de méthode. Le stockage recommandé est une petite
structure dédiée dans la base applicative, contenant les agrégats nécessaires et
les compteurs par option, ou un payload public structuré équivalent. Le schéma
exact et sa migration appartiendront au ticket d'implémentation, pas à cet audit.

Une tâche explicite après import ou correction prépare les statistiques par lots,
contrôle les liens et dénominateurs, puis publie une génération complète de manière
atomique. La lecture visiteur ne fait que lire ces petits résultats et les joindre
aux métadonnées des questions. Les options à zéro, les réponses « Autre », les
pourcentages et les contributions distinctes gardent leur définition actuelle.
Les compteurs généraux existants sont réutilisés lorsqu'ils sont cohérents avec
la génération, pas réinterprétés en nombres de personnes.

L'instantané doit inclure le total de réponses utilisé comme dénominateur. Ne pas
mélanger un dénominateur actualisé par trigger avec des numérateurs d'une ancienne
génération. La publication doit conserver la cohérence des valeurs lues pendant
la navigation. Une nouvelle génération peut être calculée avant de remplacer
l'ancienne, sans publier un demi-questionnaire.

### Comparaison des options

| Stratégie | Avantage | Limite | Avis |
|---|---|---|---|
| Agrégats existants uniquement | Compteur de réponses déjà disponible | Ne contient ni options, ni Autre, ni contributions distinctes | À réutiliser, insuffisant seul |
| Cache mémoire TTL autour du calcul actuel | Amélioration rapide des visites répétées | Recalcul aux expirations/démarrages, risque de requêtes simultanées identiques, plusieurs workers | Étape transitoire possible, pas la cible privilégiée |
| Instantané persistant versionné dans la base applicative | Lecture rapide après redémarrage, réutilisation par Formulaire et Question, publication cohérente | Tâche de rafraîchissement et stockage à ajouter | **Cible recommandée** |
| Artefact JSON local versionné | Peu de changements SQL | Distribution, invalidation et disponibilité du fichier à organiser entre processus/environnements | Alternative acceptable si le projet privilégie l'absence de nouvelle table |
| Vue matérialisée générale | Calcul centralisé PostgreSQL | Rafraîchissement, verrouillage, index et publication à maîtriser | Possible, sans avantage démontré sur de petits instantanés explicites |

Éviter d'additionner plusieurs couches de cache avant d'avoir mesuré les lectures
précalculées. Un petit cache serveur par génération pourra être ajouté si utile ;
un cache CDN ou navigateur n'est pas nécessaire pour supprimer le calcul SQL.
Conserver initialement les politiques HTTP privées existantes ; tout changement
de cache public devra être audité séparément pour les comptes et cookies.

### Absence, invalidation et concurrence

Un instantané absent ou incompatible ne doit pas déclencher silencieusement les
agrégations lourdes pendant une visite, ni se transformer en statistiques zéro.
Le questionnaire et ses liens restent consultables avec un avertissement explicite
sur l'indisponibilité des résultats. L'endpoint statistique dédié peut répondre
503. Une ancienne génération ne peut être présentée comme actuelle après un
changement de corpus sans politique de fraîcheur explicite.

La tâche de production doit empêcher deux rafraîchissements identiques simultanés
et annoncer sa complétude ; les visiteurs ne lancent pas cette tâche. Les réponses
API doivent permettre de connaître génération/date/méthode. Le rôle applicatif
public n'a pas à recalculer ou mettre à jour les instantanés lors d'un GET.

### Rendu continu et progressif

Toutes les questions, les barres simples et les textes de synthèse doivent être
présents dans le HTML initial. Le contenu des détails est rendu en SSR également :
ouvrir un tableau ne déclenche aucune requête supplémentaire.

Si des graphiques plus complexes exigent ultérieurement Recharts, ils peuvent être
chargés près du viewport comme amélioration progressive, avec une représentation
SSR équivalente déjà visible. Ne pas différer les libellés ou les données
indispensables, ni masquer le graphique principal dans un accordéon. Cette
optimisation supplémentaire n'est pas nécessaire pour la première version HTML/CSS.

## 8. Accessibilité et détails statistiques

Utiliser de préférence le composant natif **`<details><summary>Voir les détails</summary>`**,
avec contexte de question accessible et focus visible. Il fonctionne sans
JavaScript ; ne pas imposer un accordéon exclusif qui referme une autre question
pendant une comparaison. Le [Disclosure Ark UI existant](../frontend/app/components/ui/disclosure.tsx)
n'est pas un remplacement direct : il repose sur une primitive interactive et
son ouverture/fermeture sans JS n'est pas démontrée.
Le comportement natif est documenté par [MDN, élément details](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/details).

À l'intérieur : tableau complet avec `caption`, en-têtes de colonnes et `scope`,
les cinq métriques existantes et les précisions sur réponses/contributions/options/
Autre. Indiquer le dénominateur, l'arrondi et la génération de calcul. Les
informations complètes restent consultables au clavier et sans script.

**À l'extérieur**, conserver une description textuelle suffisante : question,
modalités, valeurs, base de réponses et avertissement choix multiples. Un lecteur
d'écran doit comprendre la distribution sans ouvrir les détails. Une liste HTML
de modalités peut servir directement d'alternative ; ses barres purement
visuelles portent `aria-hidden=true` pour éviter une double lecture. Ne pas
utiliser `role=progressbar`, qui suggérerait un avancement.

Exigences de recette :

- H1 de questionnaire, H2 de question, H3 éventuels de sous-section ; liens de
  sommaire et retour ; ancres stables et non masquées par l'en-tête.
- Navigation au clavier, activation des détails, retour arrière et URL fragmentée
  avec et sans JavaScript ; focus cohérent après navigation interne.
- Libellés longs repliés sur plusieurs lignes, aucun défilement horizontal à
  320 px ; zoom 200 % ; texte et valeurs jamais uniquement dans un tooltip.
- Au moins 4,5:1 pour le texte courant et contrôle des contrastes des éléments
  graphiques nécessaires à la lecture, notamment 3:1 contre les couleurs adjacentes.
  Voir [W3C, contraste non textuel](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).
- Pas de dépendance exclusive à la couleur ; alternatives lisibles en impression,
  couleurs forcées et mode sans CSS graphique. Pas d'animation nécessaire.
- Vérification avec lecteur d'écran réel, notamment lecture des valeurs avant
  ouverture du tableau et intitulés distinctifs des différents détails.

## 9. Routes et contrat cible

### Navigation

- Conserver `/enquetes` et sa présentation.
- Conserver `/forms/{id}` comme URL canonique de consultation et résultats.
- Remplacer le rendu de `/forms/{id}/dashboard` par une redirection serveur **308**
  vers `/forms/{id}`, sans appel au calcul statistique préalable.
- Conserver les URLs `/questions/{id}-{slug}`, auteurs et contributions.
- Réutiliser `#question-{id}` pour le sommaire ; les anciennes ancres de Dashboard
  ont déjà ce nom pour leurs titres. Un fragment n'arrive pas au serveur : la
  conservation du fragment par le navigateur lors du 308 doit être testée, y
  compris en accès direct à une ancienne URL ancrée.
- Mettre à jour liens, canonical et descriptions ; décider explicitement du
  traitement des anciens paramètres, sans rediriger en boucle ni vers le Dashboard.

### API : évolution limitée

Privilégier l'enrichissement de `GET /api/v1/forms/{id}` plutôt qu'un appel
statistique par question ou l'enchaînement de 37 endpoints. Il renverrait toutes
les questions actuelles, plus :

- Un état de disponibilité des statistiques, leur génération/date/version de méthode.
- `answers_count` par question, nullable si le compteur validé est indisponible.
- `statistics` pour les types à choix, réutilisant le modèle `QuestionStatistics` ;
  null pour les questions ouvertes ou si les résultats sont indisponibles, cas
  distingués grâce au type et à l'état global explicite.

Le loader fait un appel ; le backend lit métadonnées et instantanés en lot. Un
objectif simple est au plus quatre SELECT indépendamment des 37 questions, sans
lecture de `answers` ou `answer_options` sur le parcours visiteur chaud ou après
redémarrage. Les détails et graphiques partagent exactement ces données.

`GET /api/v1/forms/{id}/stats` peut rester un contrat statistique utile, réutilisant
les mêmes instantanés ; supprimer une page React n'impose pas de supprimer cette
API. L'endpoint Question `/stats` reste nécessaire et doit, à terme, utiliser le
même fournisseur pour éviter un nouveau calcul en ouvrant la question individuelle.
Les schémas `ChoiceCategory`, `QuestionStatistics`, les formateurs français,
`question_fields`, les protections d'erreur et les liens publics sont réutilisables.

Une indisponibilité statistique dans la page documentaire peut rester une réponse
200 **partielle explicitement signalée**, puisque la présentation et les questions
sont disponibles. Un formulaire introuvable garde 404 ; les erreurs globales et
l'API statistique seule gardent leurs vrais statuts. Cette distinction doit être
inscrite dans le contrat et testée, sans masquer un zéro réel.

Tous les IDs restent des chaînes JSON. Les modèles TS, validateurs du client,
OpenAPI et tests doivent être régénérés/adaptés. Ne pas exposer automatiquement
les colonnes `source`, les JSON d'importation ou les textes citoyens dans ce contrat.

## 10. Découpage recommandé et critères d'acceptation

### FORMS-002 — Statistiques précalculées et contrat de consultation

Traiter le problème de calcul avant de rendre tous les graphiques visibles.
Réutiliser les définitions actuelles, préparer/publier les instantanés, enrichir
le contrat Formulaire et mutualiser les lectures statistiques dédiées.

Critères d'acceptation :

- Génération explicite hors GET public, cohérente, versionnée et reproductible ;
  interruption avant publication sans exposition de données partiellement calculées.
- Parité avec les calculs actuels sur bases de test isolées, puis contrôles locaux
  bornés : choix unique, multiple, Autre seul ou avec option, option nulle,
  absence de réponses et contributions possédant plusieurs réponses historiques.
- Conservation exacte des dénominateurs, effectifs et arrondis ; pas de réduction
  artificielle des sommes supérieures à 100 %.
- Toutes les questions et leurs compteurs disponibles en lot ; IDs chaînes ;
  instantané manquant distinct du zéro ; version de corpus/méthode contrôlée.
- Aucun agrégat de `answers`/`answer_options` exécuté par la consultation publique,
  y compris après redémarrage et cache mémoire froid.
- Nombre de SELECT constant ; critères de latence fixés à partir de quelques
  mesures bornées, avec cible initiale de lecture API inférieure à 200 ms sur
  Hal9000 à confirmer, sans la présenter comme garantie publique.
- Mise à jour des contrats OpenAPI/TS, gestion de l'indisponibilité, procédure de
  rafraîchissement et tests de non-régression des statistiques Questions.
- Toute migration nécessaire est définie et exécutée uniquement dans ce futur
  ticket autorisé, jamais dans FORMS-001.

### FORMS-003 — Page Formulaire continue, graphiques SSR et bascule Dashboard

Implémenter les représentations HTML/CSS, le sommaire, les détails et la fusion.

Critères d'acceptation :

- `/forms/{id}` contient introduction et toutes les questions dans l'ordre source,
  jusqu'à 37, avec ancres stables et liens Questions ; Enquêtes reste inchangée.
- Graphiques principaux visibles sans accordéon ni JavaScript, libellés et valeurs
  sans interaction ; Oui/Non exhaustif validé, choix unique, multiple et Autre
  traités sans représentation trompeuse.
- Accordéons « Voir les détails » natifs, tableaux et méthode complets ; information
  textuelle essentielle disponible sans les ouvrir.
- Cas zéro, données manquantes et panne statistique explicitement distingués ;
  la présentation du questionnaire reste consultable si les résultats manquent.
- Redirection 308 de Dashboard, conservation des fragments vérifiée, aucune boucle ;
  pas d'appel au calcul ni d'URL cassée depuis Enquêtes, Questions ou un favori.
- Tests SSR et navigateur, JS activé/désactivé, navigation au clavier, lecteur
  d'écran, mobile 320 px, zoom 200 %, libellés longs, impression et couleurs forcées.
- Relevé borné des temps API, SSR et navigateur et des octets transmis, séparément ;
  absence de chargement Recharts pour les graphiques simples de cette page.
- Nettoyage de l'ancien rendu Dashboard et de ses tests au profit du nouveau
  parcours ; conservation des composants encore utilisés par les pages Questions.

Deux tickets suffisent : chacun livre une étape vérifiable et le premier supprime
le coût de calcul avant la bascule UX. Aucun chantier de recherche filtrée,
d'exploration ou de refonte générale n'est nécessaire à cette fusion.

## 11. Décisions et limites de l'audit

Les décisions recommandées sont le précalcul persistant, l'appel Formulaire enrichi,
les barres SSR et le 308. Restent à préciser au début de FORMS-002 : stockage
exact des instantanés, identité de génération du corpus, procédure de publication
après correction/import et niveau de fraîcheur acceptable. Au début de FORMS-003 :
palette finale, repères de sections éventuellement utiles et recette de lecture
avec des technologies d'assistance.

L'audit n'est ni une certification de cohérence exhaustive des 15,79 millions de
réponses ni une campagne de charge. Les compteurs ont été inventoriés, pas tous
recomptés. Les statistiques détaillées des formulaires 4, 10, 11 et 12 n'ont pas
été recalculées. Le navigateur a utilisé des agrégats réels rejoués pour isoler
le rendu ; aucune mesure intégrée de bout en bout à grande échelle n'est revendiquée.
Les coûts de concurrence et des appareils peu puissants restent à qualifier.

Les tests existants ont été lus, pas relancés comme preuve d'une modification
fonctionnelle : [API Formulaires](../tests/test_api_forms.py),
[API Questions](../tests/test_api_questions.py),
[Dashboard React](../frontend/app/routes/dashboard.test.tsx),
[recette navigateur Dashboard](../frontend/e2e/dashboard.spec.ts).
Ils montrent les composants et garanties à préserver, mais devront évoluer lors
de l'implémentation.

**FORMS-001 s'arrête à ce rapport. Aucune implémentation n'a commencé.**
