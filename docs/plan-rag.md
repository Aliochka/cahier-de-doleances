# Projet RAG — Cahier de doléances

> **Statut :** cadrage fonctionnel et architectural terminé — développement non commencé.  
> **Dernière mise à jour :** 17 octobre 2026  
> **Objectif :** développer un moteur de recherche sémantique et un système RAG permettant d'explorer les contributions citoyennes du Grand Débat National, avec une possibilité de réutilisation dans l'application publique.

---

## 1. Contexte du projet

### 1.1. Application existante

**Cahier de doléances** est une application web permettant d'explorer les contributions citoyennes du Grand Débat National de 2019.

Elle permet notamment :

- De rechercher des contributions par mots-clés.
- De parcourir les questionnaires du Grand Débat.
- De consulter les réponses des citoyens.
- De consulter les contributions par auteur.
- De visualiser des statistiques sur les réponses aux questions à choix unique ou multiple.

L'objectif est de rendre les contributions citoyennes accessibles, lisibles et faciles à explorer afin de mieux comprendre les préoccupations et les propositions exprimées.

### 1.2. Architecture actuelle

L'application utilise :

| Composant | Technologie |
|---|---|
| Backend | Python / FastAPI |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Frontend | React avec rendu SSR |
| Base de données | PostgreSQL 17 |
| Conteneurisation | Docker |
| Hébergement public | Serveur personnel Wallace |
| Dépôt | `cahier-de-doleances-app` |

L'application publique fonctionne indépendamment de tout système d'intelligence artificielle.

### 1.3. Objectifs du projet RAG

Le projet poursuit plusieurs objectifs complémentaires :

1. Développer une recherche sémantique capable de retrouver des contributions pertinentes même lorsqu'elles ne contiennent pas les mots exacts de la requête.
2. Construire un RAG documentaire capable de répondre à des questions en s'appuyant sur les contributions originales.
3. Développer ultérieurement des capacités d'analyse comparative et statistique.
4. Permettre une exploration guidée des préoccupations et propositions citoyennes.
5. Réutiliser certaines capacités du moteur de recherche pour améliorer la recherche publique du site.
6. Préparer l'intégration éventuelle d'autres consultations citoyennes et questionnaires.

Le projet doit rester évolutif, sans chercher à développer toutes ces fonctionnalités simultanément.

---

# 2. Périmètre des données

## 2.1. Corpus actuel

Le corpus est constitué des contributions numériques aux sept questionnaires du Grand Débat National actuellement importés.

L'audit réalisé par Codex le 16 octobre 2026 sur la base locale PostgreSQL 17.11 a établi les chiffres suivants :

| Indicateur | Valeur |
|---|---:|
| Contributions | 1 589 285 |
| Réponses totales | 15 792 750 |
| Réponses ouvertes | 5 004 470 |
| Textes libres dans les champs « Autre » | 167 886 |
| Questionnaires | 7 |
| Questions | 120 |
| Questions ouvertes | 72 |
| Questions à choix | 48 |
| Contributions avec réponse ouverte | 549 920 |
| Contributions des questionnaires détaillés | 569 022 |
| Titres de contributions | 569 022 |
| Contributions sans réponse ouverte mais avec titre | 19 102 |

**Important :** une contribution correspond à l'ensemble des réponses d'un participant à un questionnaire.

Une contribution peut donc contenir plusieurs réponses textuelles, plusieurs réponses structurées et un titre.

Le corpus est figé depuis 2019. Aucune synchronisation continue avec une source externe n'est nécessaire.

## 2.2. Questionnaires présents

| ID | Questionnaire | Contributions |
|---|---|---:|
| 2 | Organisation de l'État et services publics — questions rapides | 333 793 |
| 4 | Organisation de l'État et services publics | 111 953 |
| 5 | Démocratie et citoyenneté | 116 549 |
| 7 | Fiscalité et dépenses publiques | 186 711 |
| 10 | Transition écologique | 153 809 |
| 11 | Démocratie et citoyenneté — questions rapides | 335 157 |
| 12 | Transition écologique — questions rapides | 351 313 |

Les quatre questionnaires détaillés contiennent des réponses ouvertes.

Les trois questionnaires rapides ne comportent que des questions à choix.

Le corpus actuel ne constitue pas une collection exhaustive de tous les matériaux du Grand Débat National : les cahiers manuscrits, courriers et autres contributions hors plateforme ne sont pas établis comme présents.

## 2.3. Structure des données PostgreSQL

Les principales tables existantes sont :

| Table | Rôle |
|---|---|
| `forms` | Questionnaires |
| `questions` | Questions des questionnaires |
| `options` | Choix proposés |
| `contributions` | Participations individuelles |
| `answers` | Réponses aux questions |
| `answer_options` | Associations entre réponses et choix sélectionnés |
| `authors` | Auteurs des contributions |
| `topics` | Classification thématique prévue mais non réellement implémentée |
| `contribution_topics` | Association entre contributions et thématiques |
| `question_stats` | Statistiques existantes |
| `answer_valid_stats` | Statistiques existantes |

Les relations essentielles sont :

- Un formulaire possède plusieurs questions.
- Une contribution appartient à un formulaire.
- Une contribution possède plusieurs réponses.
- Chaque réponse est associée à une question.
- Une contribution peut être associée à un auteur.

### Emplacement du contenu

| Champ | Contenu |
|---|---|
| `answers.text` | Texte consultable des réponses |
| `answers.value_json` | Choix et métadonnées de normalisation |
| `contributions.title` | Titre de la contribution |
| `contributions.raw_json` | Enregistrement source complet |
| `answer_options` | Choix sélectionnés sous forme relationnelle |

Les réponses ouvertes sont stockées dans `answers.text`.

Pour les questions à choix, ce champ contient également les libellés sélectionnés et éventuellement les textes libres « Autre ».

Les données structurées doivent rester exploitables via PostgreSQL.

Il ne faut pas indexer simultanément les réponses normalisées et l'intégralité de `raw_json`, ce qui entraînerait des duplications inutiles.

### Classification thématique

Les tables `topics` et `contribution_topics` existent, mais la classification thématique n'a jamais été réellement implémentée.

**Il ne faut donc pas considérer les thèmes comme une donnée fiable déjà disponible.**

Une véritable classification pourra être développée ultérieurement pour le RAG analytique et l'exploration guidée.

---

# 3. Résultats importants de l'audit

Un audit statistique du corpus a été réalisé par Codex.

Il est conservé séparément et constitue la référence pour les mesures détaillées.

## 3.1. Longueur des réponses ouvertes

| Indicateur | Longueur |
|---|---:|
| Minimum | 1 caractère |
| Moyenne | 196 caractères |
| Médiane | 102 caractères |
| P90 | 404 caractères |
| P95 | 621 caractères |
| P99 | 1 523 caractères |
| Maximum | 350 874 caractères |

La majorité des réponses ouvertes est donc relativement courte.

Seules 30 627 réponses, soit 0,61 %, dépassent 2 000 caractères.

Cela suggère de privilégier une indexation par réponse, avec une segmentation conditionnelle des textes longs.

Le découpage définitif devra néanmoins être établi en fonction du tokenizer et du modèle d'embedding retenus.

## 3.2. Réponses courtes

L'audit a identifié :

- 575 764 réponses de 20 caractères ou moins, soit 11,50 %.
- 1 625 014 réponses de moins de 60 caractères, soit 32,47 %.

Ces réponses peuvent être pertinentes malgré leur brièveté.

Certaines ne sont compréhensibles qu'en tenant compte de la question posée, voire d'une question précédente.

Il ne faut donc pas appliquer automatiquement un seuil de longueur supprimant toutes les réponses courtes.

Plusieurs stratégies de contextualisation ou de regroupement devront être évaluées.

## 3.3. Textes très longs

Certaines réponses dépassent largement les longueurs habituelles :

| Seuil | Nombre de réponses |
|---|---:|
| Plus de 2 000 caractères | 30 627 |
| Plus de 4 000 caractères | 8 448 |
| Plus de 8 000 caractères | 2 177 |
| Plus de 20 000 caractères | 300 |

Les réponses finales des questionnaires, permettant de s'exprimer librement sur d'autres sujets, concentrent une part importante des textes longs.

Ces réponses peuvent aborder plusieurs thèmes.

Elles constituent les premières candidates à une segmentation thématique ou linguistique.

## 3.4. Répétitions et doublons

L'audit a identifié :

| Indicateur | Valeur |
|---|---:|
| Réponses ouvertes | 5 004 470 |
| Textes distincts globalement | 4 308 111 |
| Occurrences excédentaires | 696 359 |
| Part des occurrences excédentaires | 13,91 % |

Les répétitions peuvent notamment provenir de réponses très courtes ou de formulations identiques.

Elles posent deux problèmes distincts.

**Pour la recherche documentaire :**

Des résultats identiques peuvent réduire la diversité des contributions proposées.

Une déduplication ou diversification des résultats peut donc être utile.

**Pour le RAG analytique :**

Chaque occurrence doit être préservée.

Deux citoyens ayant donné une réponse identique représentent deux contributions distinctes.

La déduplication documentaire ne doit jamais fausser les fréquences calculées.

Les regroupements de textes identiques devront conserver toutes les références vers leurs réponses et contributions d'origine.

## 3.5. Titres

Les questionnaires détaillés possèdent 569 022 titres.

Leur longueur médiane est de 31 caractères.

Ils peuvent contribuer à la recherche, mais leur intérêt sémantique reste à évaluer.

Plusieurs possibilités existent :

- Ajouter le titre au contexte documentaire.
- Le conserver comme champ de recherche lexicale.
- Créer une représentation vectorielle spécifique.
- Indexer séparément certains titres lorsque la contribution ne contient aucune réponse ouverte.

Le titre ne doit pas être ajouté systématiquement à tous les embeddings sans évaluation préalable.

---

# 4. Infrastructure matérielle

## 4.1. PC local

Le développement et l'expérimentation du RAG auront lieu sur le PC principal.

| Composant | Configuration |
|---|---|
| GPU | NVIDIA GeForce RTX 5090 |
| VRAM | 32 Go |
| CPU | AMD Ryzen 9 7950X |
| RAM | 128 Go |
| Stockage | SSD NVMe de 2 To |
| Espace disponible | Environ 1,4 To |
| PostgreSQL | Version 17 |

Cette configuration permet d'envisager :

- L'exécution locale de modèles de langage.
- La génération massive d'embeddings.
- L'utilisation de rerankers.
- L'expérimentation sur plusieurs millions de documents.
- L'exécution de pipelines de classification thématique.

Les modèles et les performances exactes restent à évaluer.

## 4.2. Serveur Wallace

Wallace héberge l'application publique.

| Composant | Configuration |
|---|---|
| CPU | Intel Xeon E-2134 |
| Cœurs / threads | 4 / 8 |
| RAM | Environ 32 Go |
| Stockage PostgreSQL | 440 Go |
| Espace disponible PostgreSQL | Environ 402 Go |
| Stockage `/srv` | 195 Go |
| Stockage de sauvegarde | 1,8 To |
| Base PostgreSQL | Environ 14 Go |

Wallace est adapté à l'hébergement de l'application et de PostgreSQL.

En revanche, ses ressources sont plus limitées pour les traitements d'intelligence artificielle.

**Le LLM génératif et les traitements GPU ne seront pas exécutés sur Wallace.**

L'hébergement éventuel d'un index vectoriel public devra faire l'objet de benchmarks.

---

# 5. Organisation du projet

## 5.1. Monorepo

Le RAG sera développé dans le dépôt existant :

`cahier-de-doleances-app`

Un dossier `rag/` accueillera les composants propres au RAG.

Il n'est pas prévu de créer un deuxième dépôt Git.

### Raisons

- Les applications exploitent le même domaine métier.
- Les identifiants des contributions, questions et réponses sont communs.
- Certaines définitions et certains contrats pourront être partagés.
- Les évolutions du schéma PostgreSQL pourront être suivies dans un historique commun.
- L'intégration future avec le frontend React sera facilitée.

### Contraintes

Le RAG doit conserver :

- Ses propres dépendances Python.
- Sa propre configuration.
- Ses propres traitements d'indexation.
- Ses propres tests.
- Son propre cycle d'exécution et de déploiement.

Les dépendances lourdes du RAG, notamment CUDA et PyTorch, ne devront pas être intégrées à l'image Docker de l'application publique.

Le déploiement de Wallace devra rester indépendant.

## 5.2. Base PostgreSQL

La base PostgreSQL locale contient les mêmes données que celle de Wallace.

Le RAG utilisera cette instance locale.

Il est recommandé de créer une base logique distincte pour les données expérimentales du RAG, plutôt que de modifier directement les tables de l'application.

Les données originales resteront intactes.

Aucun mécanisme de synchronisation continue n'est nécessaire puisque le corpus est figé.

## 5.3. Extensibilité

Le système doit pouvoir accueillir ultérieurement d'autres questionnaires ou consultations citoyennes.

Pour cela, nous prévoyons une couche d'ingestion capable de transformer différentes sources en une représentation documentaire commune.

Les informations suivantes devront être conservées :

- Corpus et consultation d'origine.
- Identifiant du document source.
- Identifiant de la contribution.
- Identifiant de la question.
- Texte indexé.
- Métadonnées nécessaires à la recherche.
- Informations de provenance.
- Relations permettant de retrouver les documents originaux.

Les données structurées propres à chaque consultation devront rester exploitables pour les analyses statistiques.

Il ne faut pas supposer que toutes les futures consultations utiliseront exactement le schéma des questionnaires du Grand Débat.

---

# 6. Architecture fonctionnelle

Le système est organisé autour de cinq composants logiques.

| Composant | Responsabilité |
|---|---|
| Ingestion | Préparer les documents à partir des données sources |
| Indexation | Produire les représentations vectorielles et les index |
| Recherche | Retrouver, fusionner et classer les résultats |
| Génération | Produire des réponses sourcées à l'aide d'un LLM |
| Analyse | Effectuer des calculs et comparaisons sur le corpus |

L'objectif est de conserver un moteur de recherche indépendant de la génération par LLM.

Cela permettra de réutiliser la recherche dans l'application publique.

## 6.1. Recherche hybride

Le moteur combinera deux approches.

### Recherche lexicale

Recherche basée sur les mots et expressions.

Elle est particulièrement utile pour :

- Les noms propres.
- Les expressions exactes.
- Les termes administratifs.
- Les références précises.

### Recherche vectorielle

Recherche basée sur la proximité sémantique.

Elle permet notamment de retrouver des contributions exprimant une idée avec des formulations différentes.

### Fusion des résultats

Les résultats lexicaux et vectoriels seront fusionnés puis classés selon leur pertinence.

Les méthodes exactes de fusion restent à déterminer expérimentalement.

## 6.2. Reranking

Le reranking consiste à réévaluer les résultats initialement retrouvés pour améliorer leur classement.

Le RAG local pourra utiliser un reranker exécuté sur GPU.

Pour Wallace, nous privilégierons éventuellement des mécanismes de classement plus légers.

Le choix dépendra des performances mesurées.

## 6.3. Génération

Le RAG documentaire utilisera un LLM local pour synthétiser les informations retrouvées.

Les réponses devront :

- S'appuyer sur les contributions effectivement retrouvées.
- Fournir des références vers les sources originales.
- Éviter d'attribuer aux citoyens des positions qu'ils n'ont pas exprimées.
- Reconnaître les limites des informations disponibles.
- Éviter les généralisations statistiques non justifiées.

Le modèle de langage n'est pas encore choisi.

---

# 7. Stratégies documentaires à évaluer

Aucune stratégie d'indexation définitive n'a été retenue.

Plusieurs approches seront comparées.

## 7.1. Une réponse par document

Chaque réponse ouverte constitue un document indépendant.

Le contexte de la question peut être ajouté au texte utilisé pour l'embedding.

**Avantages :**

- Recherche précise.
- Provenance simple.
- Correspondance directe avec les réponses originales.

**Inconvénients :**

- Environ 5,17 millions d'unités textuelles avant segmentation.
- Certaines réponses sont très courtes.
- Le contexte peut être insuffisant.

Cette approche constituera une référence pour les évaluations.

## 7.2. Une contribution par document

Toutes les réponses ouvertes d'une contribution sont regroupées.

**Avantages :**

- Réduction du nombre de documents initiaux.
- Conservation du contexte général de la contribution.

**Inconvénients :**

- Mélange possible de plusieurs sujets.
- Risque de dilution des informations.
- Segmentation nécessaire pour certaines contributions.

Cette stratégie ne semble pas idéale comme solution unique.

## 7.3. Parent-enfant

La contribution constitue le document parent.

Les réponses, ou les segments de réponses, constituent les documents enfants.

La recherche retrouve des passages précis, puis peut récupérer la contribution complète pour fournir davantage de contexte.

**Avantages :**

- Bonne granularité de recherche.
- Contexte disponible à la demande.
- Sources facilement identifiables.
- Adapté au RAG documentaire et à la recherche publique.

**Inconvénients :**

- Gestion supplémentaire des relations.
- Nécessité de décider quand récupérer le parent.

Cette approche est particulièrement naturelle avec le schéma PostgreSQL existant.

Elle constitue une piste privilégiée, mais reste à valider.

## 7.4. Regroupement des réponses courtes

Certaines réponses courtes et liées peuvent être regroupées avec leurs questions voisines.

Exemple :

Une réponse « Non » peut être associée à la question correspondante et à la réponse expliquant pourquoi.

Cette approche pourrait améliorer la compréhension sémantique et réduire le nombre de petits documents.

Elle nécessite toutefois des règles de regroupement précises.

Les réponses de citoyens différents ne devront jamais être fusionnées dans un même document documentaire.

## 7.5. Multi-représentations

Une même contribution peut posséder plusieurs représentations :

- Embeddings de réponses individuelles.
- Embedding du titre.
- Éventuellement embedding de la contribution complète.

Cette stratégie pourrait faciliter les recherches à différentes granularités.

Elle présente néanmoins un coût supplémentaire en stockage et en indexation.

Elle sera envisagée dans un second temps si les évaluations montrent un intérêt.

## 7.6. Enrichissement contextuel

Le texte encodé peut inclure :

- La réponse.
- La question correspondante.
- Le nom du questionnaire.
- Éventuellement le titre de la contribution.
- Éventuellement le contexte d'une question précédente.

Plusieurs variantes devront être comparées.

Un contexte trop volumineux ou mal choisi peut dégrader la qualité des embeddings.

### Stratégies prioritaires pour les tests

Trois variantes seront évaluées en priorité :

1. Réponse contextualisée par sa question.
2. Réponse contextualisée avec récupération du parent.
3. Regroupement de réponses courtes liées.

Les résultats de ces tests guideront les choix définitifs.

---

# 8. RAG documentaire

## 8.1. Objectif

Permettre à l'utilisateur de poser des questions ouvertes sur les contributions citoyennes.

Exemple :

> Quelles solutions les participants proposent-ils pour améliorer les transports dans les zones rurales ?

Le système devra :

1. Comprendre la requête.
2. Rechercher les passages pertinents.
3. Classer les résultats.
4. Récupérer le contexte nécessaire.
5. Générer une synthèse.
6. Citer les contributions utilisées.

## 8.2. Précision des sources

Les citations devront idéalement permettre de retrouver :

- Le questionnaire.
- La question.
- La réponse.
- La contribution complète.

Le lien entre le passage indexé et la réponse originale devra donc être conservé.

## 8.3. Limites

Le RAG documentaire ne doit pas présenter les résultats les plus pertinents comme les opinions les plus fréquentes.

Une recherche top-k ne constitue pas un échantillon statistiquement représentatif.

Les synthèses devront distinguer les propositions identifiées de leur éventuelle prévalence dans le corpus.

---

# 9. RAG analytique

Le RAG analytique constitue une évolution ultérieure.

Il devra permettre de combiner recherche documentaire, données structurées et calculs statistiques.

## 9.1. Exemples

### Analyse statistique

> Quelle proportion des répondants à un questionnaire est favorable à une mesure donnée ?

Cette question relève principalement de SQL.

### Analyse comparative

> Comment les réponses diffèrent-elles selon les territoires ?

Cette analyse nécessite des métadonnées géographiques exploitables et des dénominateurs correctement définis.

### Analyse thématique

> Quelles sont les principales propositions concernant la fiscalité ?

Cette question pourrait nécessiter une classification thématique d'un grand nombre de réponses.

## 9.2. Principes

Le RAG analytique devra s'appuyer sur des calculs contrôlés.

Il ne devra pas déduire des pourcentages à partir des seuls résultats d'une recherche vectorielle.

Nous privilégierons :

- Des requêtes SQL contrôlées.
- Des agrégations explicites.
- Des dénominateurs identifiés.
- Des méthodes de classification évaluées.
- Des résultats vérifiables.

Le LLM servira principalement à orchestrer les outils et à interpréter les résultats, et non à inventer les calculs.

Les requêtes SQL arbitraires générées par le modèle ne devront pas être exécutées librement sur la base de production.

## 9.3. Classification thématique

Une classification stable des réponses pourrait permettre d'identifier automatiquement des thèmes et sous-thèmes.

Elle pourrait ensuite servir :

- À la navigation.
- Aux filtres.
- Aux comparaisons.
- Aux analyses de fréquence.
- À l'exploration guidée.

Cette classification n'est pas prévue pour la première version.

---

# 10. Recherche publique et réutilisation du moteur

Un objectif important est de pouvoir réutiliser le moteur de recherche du RAG dans l'application publique.

**La recherche sémantique n'a pas besoin d'un LLM génératif.**

Cela permettrait de proposer une meilleure recherche à tous les visiteurs sans exposer le RAG complet.

## 10.1. Composants réutilisables

| Composant | RAG local | Application publique |
|---|---|---|
| Préparation documentaire | Oui | Réutilisable |
| Embeddings | Oui | Réutilisables |
| Index vectoriel | Oui | Potentiellement |
| Recherche hybride | Oui | Potentiellement |
| Reranking GPU | Oui | Non prévu initialement |
| Diversification des résultats | Oui | Oui, potentiellement |
| Classification thématique | Future | Future |
| LLM génératif | Oui | Non prévu |
| RAG analytique | Futur | Non prévu initialement |

## 10.2. Fonctionnement envisagé

Les embeddings seront générés sur le PC équipé de la RTX 5090.

Ils pourraient ensuite être transférés sur Wallace.

Wallace effectuerait les recherches vectorielles avec PostgreSQL et une extension comme pgvector, si les benchmarks le permettent.

La vectorisation des requêtes des visiteurs devra également pouvoir être réalisée sans dépendre du PC personnel.

Un modèle d'embedding relativement léger exécuté sur CPU constitue une possibilité à évaluer.

## 10.3. Contraintes matérielles

Avec environ 5,17 millions de vecteurs :

| Dimensions | Stockage brut float32 |
|---|---:|
| 768 | Environ 14,8 Gio |
| 1 024 | Environ 19,7 Gio |

Ces valeurs excluent :

- Les index vectoriels.
- Les métadonnées.
- Les identifiants.
- Les textes.
- Les structures PostgreSQL supplémentaires.

Le stockage disponible sur Wallace paraît suffisant.

En revanche, ses 32 Go de RAM et son processeur constituent des contraintes importantes.

**Aucun déploiement de recherche vectorielle publique ne sera décidé sans benchmarks.**

L'application publique devra conserver sa recherche existante tant que la nouvelle solution n'aura pas été validée.

---

# 11. UX de la recherche publique

## 11.1. Objectif

L'interface doit permettre deux usages complémentaires :

**Rechercher précisément :** retrouver les réponses les plus pertinentes pour une requête.

**Explorer un sujet :** découvrir plusieurs dimensions d'une préoccupation citoyenne.

L'utilisateur ne doit pas avoir besoin de comprendre le fonctionnement des embeddings ou de la recherche vectorielle.

## 11.2. Interface envisagée

Une recherche unique, avec deux présentations possibles des résultats.

### Onglet « Résultats pertinents »

Liste de réponses classées selon leur pertinence.

Chaque résultat présente :

- Un extrait de réponse.
- La question correspondante.
- Le questionnaire.
- Un lien vers la réponse ou la contribution originale.

Le comportement reste proche de la recherche actuelle.

### Onglet « Explorer le sujet »

L'utilisateur découvre différentes facettes de sa recherche.

Exemple pour :

> Améliorer les transports en zone rurale

Sous-thèmes possibles :

- Transports collectifs.
- Covoiturage.
- Réouverture des lignes ferroviaires.
- Transport à la demande.
- Accessibilité des services publics.

Ces exemples sont illustratifs.

Les véritables catégories devront être établies à partir des résultats.

L'utilisateur pourra sélectionner un sous-thème pour approfondir son exploration.

## 11.3. Exploration guidée

**Décision retenue : privilégier l'exploration guidée plutôt qu'une cartographie visuelle des idées.**

L'objectif est de proposer une expérience accessible et progressive.

Une carte interactive n'est pas prévue dans le périmètre actuel.

## 11.4. Évolution des catégories

### Prototype

Sous-thèmes dynamiques identifiés à partir des résultats d'une recherche.

Aucune classification globale préalable n'est nécessaire.

### Version future

Approche hybride combinant :

- Une classification stable des grands thèmes.
- Des sous-thèmes dynamiques propres à chaque recherche.

Les catégories produites automatiquement devront être présentées comme telles.

Elles ne devront pas être confondues avec des statistiques de fréquence calculées sur l'ensemble du corpus.

## 11.5. Diversification des résultats

Pour l'exploration, il pourra être intéressant de ne pas afficher uniquement les réponses les plus similaires.

Le système pourra chercher à présenter plusieurs propositions différentes sur un même sujet.

Des méthodes de diversification, notamment MMR, pourront être évaluées.

L'objectif sera de trouver un compromis entre :

- Pertinence.
- Diversité.
- Couverture des différentes idées.
- Limitation des résultats répétitifs.

Une proposition rare pourra ainsi être présentée sans être décrite comme majoritaire.

---

# 12. Architecture de déploiement

## 12.1. Phase actuelle : fonctionnement local

**Décision retenue : option A.**

Le RAG fonctionne exclusivement sur le PC personnel.

Ses composants sont indépendants de l'application publique.

| Composant | Hébergement |
|---|---|
| Base RAG | PostgreSQL local |
| Index vectoriel | Local |
| Modèle d'embedding | PC / RTX 5090 |
| Reranker | PC / RTX 5090 |
| LLM | PC / RTX 5090 |
| API RAG éventuelle | Locale |
| Application publique | Wallace |

Le site fonctionne normalement lorsque le PC personnel est éteint.

## 12.2. Phase future : preuve de concept privée

**Décision retenue : option B, à long terme.**

Une fois le RAG stabilisé, il pourrait être accessible à un nombre limité d'utilisateurs ciblés depuis `cahierdedoleances.fr`.

Dans cette configuration :

- Le RAG continuerait de fonctionner sur le PC personnel.
- Wallace communiquerait avec le service RAG à travers une connexion privée sécurisée.
- L'accès serait limité aux utilisateurs autorisés.
- L'indisponibilité du RAG ne devrait pas affecter le site public.

Cette étape n'est pas prioritaire.

Elle devra être conçue en fonction des besoins réels de la preuve de concept.

## 12.3. Recherche sémantique publique

La recherche sémantique publique constitue un déploiement distinct de la preuve de concept RAG.

Elle pourrait fonctionner entièrement sur Wallace, sans dépendre de la disponibilité du PC personnel.

Cela nécessitera :

- Le stockage d'index vectoriels sur Wallace.
- Un mécanisme local de vectorisation des requêtes.
- Des recherches suffisamment rapides sur CPU.
- Une consommation de ressources compatible avec l'application publique.

La faisabilité reste à démontrer.

---

# 13. Qualité, fiabilité et confidentialité

## 13.1. Provenance

Chaque document indexé devra conserver ses références d'origine.

Il devra être possible de retrouver précisément la réponse ayant servi à produire un résultat.

La provenance ne devra pas être perdue lors de la segmentation ou de la déduplication.

## 13.2. Représentativité

Les contributions au Grand Débat ne constituent pas un échantillon représentatif de la population française.

Le système devra éviter les formulations du type :

> 65 % des Français pensent que…

Il pourra éventuellement présenter des résultats tels que :

> Parmi les réponses analysées correspondant à ces critères, 65 % expriment…

Uniquement si les calculs et les méthodes de classification permettent réellement de soutenir cette affirmation.

Il faudra distinguer :

- Nombre de réponses.
- Nombre de contributions.
- Nombre d'auteurs distincts.
- Nombre de participants à un questionnaire.

Ces mesures ne sont pas interchangeables.

## 13.3. Données personnelles

Le schéma contient des informations relatives aux auteurs.

Certaines réponses libres peuvent également contenir des données personnelles rédigées directement par les contributeurs.

Par défaut, les documents envoyés au modèle ne devront pas inclure :

- Les empreintes d'e-mails.
- Les identifiants personnels inutiles.
- Les données d'authentification.
- Les informations de profil non nécessaires.
- Les codes postaux individuels lorsqu'ils n'apportent rien à la recherche.

Les éventuelles analyses géographiques devront tenir compte du caractère déclaratif des codes postaux.

L'indexation et l'éventuelle exposition publique de textes libres devront également être examinées sous l'angle de la confidentialité.

## 13.4. Évaluation

Le système devra être évalué avant toute indexation complète ou mise en production.

Les critères comprendront notamment :

- Pertinence des résultats.
- Couverture des réponses courtes.
- Qualité des citations.
- Diversité des sources.
- Gestion des doublons.
- Respect du contexte des questions.
- Performances de recherche.
- Consommation mémoire.
- Coût de stockage.

---

# 14. Démarche expérimentale

## 14.1. Ne pas indexer immédiatement tout le corpus

L'indexation complète des cinq millions de réponses n'est pas la première étape.

Nous commencerons par un échantillon représentatif.

Il devra couvrir :

- Les différents questionnaires.
- Les différents types de questions.
- Les réponses courtes.
- Les réponses longues.
- Les textes « Autre ».
- Les répétitions.
- Les cas nécessitant un contexte supplémentaire.

## 14.2. Jeu d'évaluation

Nous construirons un ensemble de requêtes représentatives des futurs usages.

Exemples :

- Quelles solutions sont proposées pour améliorer l'accès aux soins ?
- Quelles contributions évoquent la suppression de certaines taxes ?
- Quelles propositions concernent la démocratie participative ?
- Quels problèmes de transports sont évoqués dans les territoires ruraux ?
- Quelles réponses expriment une idée sans employer les mots exacts de la requête ?

Pour chaque requête, il faudra établir des jugements de pertinence sur des documents candidats.

L'évaluation ne devra pas reposer uniquement sur l'appréciation d'un LLM.

## 14.3. Comparaison des modèles d'embedding

Plusieurs modèles adaptés au français seront testés.

Critères de sélection :

1. Qualité de la recherche.
2. Capacité à comprendre les formulations citoyennes.
3. Performances sur la RTX 5090.
4. Taille des embeddings.
5. Coût de stockage.
6. Possibilité d'exécuter l'encodage des requêtes sur Wallace sans GPU.

Aucun modèle n'est encore retenu.

## 14.4. Comparaison des stratégies documentaires

Nous comparerons en priorité :

- Réponse seule ou contextualisée.
- Réponse contextualisée avec accès au parent.
- Regroupement de réponses courtes.

Nous évaluerons également l'intérêt d'ajouter les titres.

La segmentation des textes longs sera adaptée au modèle choisi.

## 14.5. Recherche hybride

Après la sélection des premières représentations documentaires, nous évaluerons :

- La recherche lexicale.
- La recherche vectorielle.
- Plusieurs stratégies de fusion.
- Le reranking.
- La diversification des résultats.

Nous chercherons à établir une référence mesurable avant d'ajouter le LLM génératif.

---

# 15. Feuille de route prévisionnelle

Les étapes suivantes constituent une trajectoire de travail, pas un calendrier définitif.

| Phase | Objectif | Statut |
|---|---|---|
| 0 | Cadrage et architecture générale | Terminé |
| 1 | Audit du corpus PostgreSQL | Terminé |
| 2 | Jeu d'évaluation et échantillon | À faire |
| 3 | Comparaison des stratégies documentaires | À faire |
| 4 | Comparaison des modèles d'embedding | À faire |
| 5 | Moteur de recherche hybride local | À faire |
| 6 | Évaluation du reranking et de la diversification | À faire |
| 7 | RAG documentaire local | À faire |
| 8 | Benchmark de recherche vectorielle sur Wallace | À faire |
| 9 | Éventuelle recherche sémantique publique | À décider |
| 10 | Exploration guidée avec sous-thèmes dynamiques | À faire |
| 11 | RAG analytique | À faire ultérieurement |
| 12 | Éventuelle preuve de concept RAG pour utilisateurs ciblés | À long terme |

Certaines phases pourront être menées en parallèle ou réordonnées selon les résultats des évaluations.

---

# 16. Décisions actées

| Sujet | Décision |
|---|---|
| Organisation Git | Monorepo existant |
| Emplacement du RAG | Dossier `rag/` |
| Développement | Local |
| Base de données | PostgreSQL 17 local |
| Données sources | Corpus existant, figé |
| Infrastructure GPU | RTX 5090 |
| Indépendance du site public | Obligatoire |
| Indexation | Plusieurs stratégies à comparer |
| Recherche | Hybride |
| Première fonctionnalité RAG | Documentaire |
| RAG analytique | Prévu ultérieurement |
| Recherche publique | Réutilisation du moteur envisagée |
| UX | Résultats pertinents + exploration guidée |
| Exploration V1 | Sous-thèmes dynamiques |
| Exploration future | Classification stable + dynamique |
| Carte interactive | Non prioritaire |
| Futurs questionnaires | Architecture extensible |
| Accès public au RAG | Non prévu initialement |
| Preuve de concept privée | Possible à long terme |
| Choix des modèles | Après évaluation |
| Indexation complète | Après validation des stratégies |

---

# 17. Questions techniques encore ouvertes

Plusieurs choix restent volontairement non tranchés.

### Indexation

- Quel modèle d'embedding utiliser ?
- Quelle dimension vectorielle retenir ?
- Quelle stratégie de segmentation adopter ?
- Comment contextualiser les réponses courtes ?
- Faut-il dédupliquer les textes avant de générer les embeddings ?
- Les titres doivent-ils disposer de leurs propres embeddings ?
- Quel intérêt présente une représentation globale des contributions ?

### Recherche

- Quelle méthode de recherche hybride utiliser ?
- Comment fusionner les scores lexicaux et vectoriels ?
- Quel reranker utiliser ?
- Comment diversifier les résultats ?
- Comment gérer la pagination des résultats vectoriels ?
- Comment évaluer la pertinence de manière reproductible ?

### Stockage

- Faut-il privilégier pgvector ou comparer d'autres moteurs ?
- Quelle méthode d'indexation vectorielle utiliser ?
- Quel volume mémoire nécessiteront les index ?
- La recherche peut-elle fonctionner efficacement sur Wallace ?
- Quelle stratégie de compression éventuelle adopter ?

### RAG documentaire

- Quel LLM local utiliser ?
- Quelle quantité de contexte fournir au modèle ?
- Comment sélectionner les contributions à citer ?
- Comment détecter les réponses insuffisamment étayées ?
- Comment évaluer la fidélité des synthèses ?

### Exploration guidée

- Comment identifier dynamiquement des sous-thèmes ?
- Comment éviter les catégories redondantes ?
- Comment garantir que les catégories correspondent réellement aux contributions retrouvées ?
- Faut-il utiliser un regroupement vectoriel, une classification ou un LLM ?
- Comment présenter les catégories sans leur attribuer une représentativité statistique injustifiée ?

### RAG analytique

- Comment construire une classification thématique fiable ?
- Quelles analyses statistiques rendre possibles ?
- Comment combiner recherche sémantique et SQL ?
- Comment calculer des fréquences sans biais liés à la sélection des documents ?
- Quelles comparaisons territoriales sont réellement possibles avec les métadonnées disponibles ?

---

# 18. Prochaine étape

La prochaine étape est la **conception du socle d'évaluation de la recherche**, avant toute indexation massive.

Elle comprendra :

1. La définition d'un jeu de requêtes représentatives.
2. La constitution d'un échantillon documentaire couvrant les particularités du corpus.
3. La définition des critères de pertinence et des métriques d'évaluation.
4. La préparation d'un protocole de comparaison des stratégies documentaires.
5. La préparation d'un protocole de comparaison des modèles d'embedding.

Le développement sera confié progressivement à Codex, sous forme de tâches indépendantes accompagnées de critères d'acceptation.

Les décisions techniques définitives seront prises à partir des résultats expérimentaux.

**Principe directeur : construire d'abord un moteur de recherche fiable, mesurable et réutilisable, puis développer les fonctionnalités RAG et d'exploration autour de ce socle.**