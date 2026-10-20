# FORMS-002 — Statistiques précalculées et nouveau contrat Formulaire

Date : 20 octobre 2026. Réalisation locale sur Hal9000 uniquement.

## 1. Résultat

Les statistiques des **sept formulaires et 120 questions** sont persistées et
publiées dans `cahier_doleances_local`. Les GET Formulaire, Dashboard statistique
et Question statistique ne recalculent plus les agrégats sur les réponses.

Une commande de maintenance explicite calcule, vérifie et publie atomiquement une
génération. Les changements de source invalident sa disponibilité. L'API distingue
les statistiques absentes/incompatibles/incomplètes des réponses réellement nulles.
Le détail documentaire d'un formulaire reste disponible même sans statistiques.

La génération initiale complète a pris **80,68 s**, une seule fois. Sur deux
processus de validation neufs, les formulaires enrichis ont répondu en
**1,3 à 4,1 ms** avec trois SELECT, sous la cible locale de 200 ms. Le Dashboard
statistique du formulaire 2 est passé de **3 664 ms** dans FORMS-001 à **12,6 ms**
lors du passage de contrôle après précalcul, avec le même poids JSON de 11 096 octets.
Ces mesures ASGI locales ne constituent pas une garantie de production.

Aucune modification des contributions originales, du moteur hybride ou des
embeddings. Aucune intervention sur Wallace, nouvelle infrastructure de cache,
refonte frontend ou suppression de Dashboard.

## 2. Modifications et architecture

Principaux fichiers :

- [Migration additive](../migrations/versions/forms_statistics_v1.py).
- [Génération et validation](../app/services/statistics_generation.py).
- [Fournisseur commun de statistiques publiées](../app/services/published_statistics.py).
- [Commande de génération](../scripts/generate_statistics.py).
- [Recette locale en lecture seule](../scripts/smoke_form_statistics.py).
- [API Formulaires](../app/routers/api_forms.py) et [Questions](../app/routers/api_questions.py).
- Schémas partagés dans `app/schemas/choice_statistics.py` et `public_ids.py` ;
  enrichissement de `FormDetail`, sans changer le modèle documentaire `FormQuestion`
  utilisé dans les autres contrats.
- OpenAPI et types TypeScript régénérés ; validation du nouveau contrat dans le
  client frontend, fixtures et tests adaptés.

Les routes React Formulaire et Dashboard **ne sont pas modifiées**. Les graphiques,
la navigation et les composants statistiques actuels restent en place. Le service
historique de calcul reste utilisable par la maintenance et les contrôles de
parité, mais aucun endpoint public ne l'appelle pour obtenir ses statistiques.

```text
Import / correction → révision de corpus incrémentée transactionnellement

Commande de maintenance explicite
  → snapshot PostgreSQL REPEATABLE READ
  → contrôles + agrégations en lot + comparaison historique ciblée
  → nouvelle génération complète
  → contrôle final de la révision + publication atomique

GET public → métadonnées documentaires + génération publiée + petits instantanés
             aucune agrégation answers / answer_options
```

## 3. Schéma PostgreSQL

Migration `forms_statistics_v1`, descendante de `remove_runtime_caches`. Les
migrations historiques ne sont pas réécrites. Les tables et triggers de compteurs
existants sont conservés.

| Table | Données |
|---|---|
| `statistics_source` | Singleton, UUID de corpus, révision BIGINT, UUID de génération publiée |
| `statistics_generations` | UUID, corpus/révision source, version de méthode, date de calcul, nombres de questions/formulaires, empreinte SHA-256 globale |
| `question_statistics_snapshots` | Génération/question, formulaire, nombre de réponses, statistiques JSONB pour les choix, empreinte SHA-256 de la ligne |

Clé primaire `(generation_id, question_id)` et index `(generation_id, form_id)`.
Une clé étrangère rattache les instantanés à leur génération ; une autre protège
le pointeur de publication. Les identifiants de source dans les instantanés sont
historiques, sans FK vers les questions/formulaires courants : une suppression
source invalide la génération sans détruire son historique ou bloquer la correction.

**Choix JSONB structuré :** les colonnes relationnelles portent identité, recherche,
compteur et version ; le JSONB réutilise exactement `QuestionStatistics`, un petit
contrat imbriqué de modalités. Il évite une seconde logique de reconstruction et
plusieurs tables d'options agrégées. Pydantic valide le contenu à la lecture et
les empreintes détectent une altération de ligne. Les options à zéro restent dans
le payload. Les instantanés ne contiennent aucun auteur, contribution individuelle,
texte citoyen, champ Autre original ou métadonnée privée. Les libellés d'options
sont ceux du questionnaire public.

La méthode est **`historical-answers-v1`**. Une question ouverte conserve uniquement
son compteur dans l'instantané, avec `statistics=null`. Le dénominateur d'un choix
est stocké dans le même payload que ses numérateurs : il n'est pas relu depuis un
compteur vivant d'une génération différente.

## 4. Génération, publication et fraîcheur

### Calcul cohérent

La commande refuse les destinations distantes et les bases locales non autorisées.
Elle ouvre une transaction `REPEATABLE READ`. Un advisory lock transactionnel
`pg_try_advisory_xact_lock` réserve le calcul à un seul générateur, sans attente
pour un deuxième lancement concurrent.

Le traitement lit les questions, valide les rattachements existants et les champs
Autre, agrège toutes les réponses par question en une lecture groupée, puis les
options en une autre. Il compare les nombres de lignes aux compteurs historiques.
Un compteur manquant est accepté uniquement si le recomptage réel confirme zéro.
Une divergence avec des réponses existantes arrête la génération.

Les pourcentages et catégories utilisent `_format_statistics` et la projection
publique existante, sans nouvelle définition de calcul. Avant publication, un
échantillon est recalculé par le service historique et comparé au payload préparé.
Les effectifs ne sont jamais calculés en faisant la somme des questions ou en
remplaçant les contributions distinctes par les réponses.

### Publication atomique et concurrence

Une seule transaction contient calcul, validation, insertion des 120 instantanés
et modification du pointeur publié. Avant publication, une lecture `FOR UPDATE`
de la petite ligne de révision vérifie que la source n'a pas changé. Une mise à
jour concurrente sous `REPEATABLE READ` provoque un échec de sérialisation ou un
refus de publication ; un changement après le verrou attend le bref COMMIT, puis
invalide la nouvelle génération.

Les lectures HTTP utilisent elles aussi une transaction REPEATABLE READ en lecture
seule : métadonnées documentaires et publication sont ainsi lues dans la même vue,
même si une correction et une nouvelle publication surviennent entre deux SELECT.
Le paramétrage de connexion est réinitialisé au retour au pool.

Les lecteurs publics ne prennent pas ce verrou. Une erreur ou interruption à
n'importe quelle phase annule les insertions et le changement du pointeur. La
génération précédente reste stockée, et disponible si la source est toujours celle
qu'elle décrit. Les traces de progression ne remplacent pas le COMMIT : seule la
sortie finale réussie de la commande confirme une publication durable.

### Invalidation

Des triggers AFTER STATEMENT sur `forms`, `questions`, `options`, `answers`,
`answer_options`, `contributions`, `question_stats` incrémentent la révision lors
d'INSERT, UPDATE, DELETE ou TRUNCATE, dans la transaction source. Ainsi, une
correction validée rend immédiatement l'ancienne génération incompatible. Une
transaction source annulée n'invalide pas durablement la publication.

Cette approche est conservatrice : un UPDATE sans changement, ou une correction
de titre de contribution sans effet sur les agrégats, peut aussi invalider. Elle
évite de décider trop tôt quelles modifications sont statistiquement neutres.
Les écritures sources partagent la ligne de révision ; cela peut sérialiser des
écritures concurrentes. Les consultations restent de simples lectures MVCC.

La disponibilité exige la concordance corpus/révision/méthode, le nombre attendu
d'instantanés et des empreintes de lignes valides. Les valeurs nulles ou les
statistiques illisibles ne deviennent jamais zéro. Un petit `COUNT` des lignes
d'instantanés vérifie la complétude globale : il porte sur 120 petits agrégats,
pas sur les millions de réponses.

Les triggers doivent rester actifs. Une maintenance privilégiée qui désactive
les triggers, change le mode de réplication ou restaure partiellement les données
nécessite une invalidation explicite avant l'opération. Cela est documenté dans
le [guide de maintenance](statistiques-locales.md). Les changements de schéma ou
de méthode nécessitent également un traitement explicite de génération/version.

## 5. Contrats HTTP

### Formulaire enrichi

`GET /api/v1/forms/{id}` conserve identifiant, nom, nombre de questions, URL et
ordre des questions. Il ajoute :

```json
{
  "statistics_availability": {
    "status": "available",
    "reason": null,
    "generation_id": "9c733026-4a92-46dd-9b17-15827ce5ad3e",
    "calculated_at": "2026-10-20T17:49:01.165918+02:00",
    "method_version": "historical-answers-v1"
  },
  "questions": [{
    "id": "2",
    "form_id": "2",
    "prompt": "Intitulé public de la question",
    "type": "single_choice",
    "position": 1,
    "slug": "intitule-public",
    "url": "/questions/2-intitule-public",
    "answers_count": 331454,
    "statistics": {"question_id": "2", "type": "single_choice", "total_answers": 331454, "...": "autres champs QuestionStatistics existants"}
  }]
}
```

L'extrait illustre seulement les ajouts et le contexte question ; le modèle complet
reste celui d'OpenAPI. Pour une question ouverte, `statistics=null` et le compteur
est celui des réponses enregistrées. Il ne promet pas le nombre exact de textes
consultables sur la page Question, dont le seuil historique demeure inchangé.

Si indisponible : HTTP 200 documentaire, `status=unavailable`, raison `absent`,
`incompatible` ou `incomplete`, métadonnées de génération à null et tous les
compteurs/statistiques des questions à null. Titres, types, ordre et liens restent
consultables. Un formulaire inexistant garde 404.

**Trois SELECT par détail**, indépendamment de 7 ou 37 questions : formulaire,
questions, publication et instantanés. Aucun N+1, aucun texte individuel chargé.
Les BIGINT restent des chaînes JSON ; compteurs et positions restent numériques.

### Endpoints statistiques existants

- `GET /api/v1/forms/{id}/stats` : même `FormStatistics`, trois SELECT au lieu de
  cinq, plus le SET LOCAL de délai déjà existant.
- `GET /api/v1/questions/{id}/stats` : même `QuestionStatistics`, deux SELECT au
  lieu de quatre ; les types non à choix restent refusés en 400.
- Statistiques indisponibles/incomplètes : **503**, message public, aucun calcul
  de secours. Les autres erreurs SQL et délais conservent les protections existantes.

Ces endpoints partagent `read_published` / `require_published`. Le client React
valide aussi les métadonnées de disponibilité et la concordance entre compteur,
question et statistiques. Aucun sélecteur ou drapeau fonctionnel n'est introduit.
Les routes React Formulaire et Dashboard restent inchangées pour FORMS-003.

## 6. Migration et première publication sur Hal9000

### Sauvegarde préalable

Une sauvegarde fraîche a été produite **avant la migration applicative** :

- Archive : `/home/ro/postgres-backups/forms-002-20261020-174501/application.dump`.
- Format custom PostgreSQL 17, **1 736 507 728 octets**, fichier 0600, répertoire 0700.
- Empreinte SHA-256 : `1fb56b44eec7592a15171b120162f0ed2495934456b46e3852df3087fa56f493`.
- TOC lu et archive entière décodée par `pg_restore --file=/dev/null` ; reçu de
  vérification privé dans le même répertoire. Durée sauvegarde et vérification : 57,36 s.

La lisibilité complète du flux est vérifiée ; une restauration intégrale dans
une nouvelle base n'a pas été exécutée pendant ce ticket. La restauration de
secours exige un rôle autorisé et une destination isolée, sans écraser le corpus.
La sauvegarde de cluster existante du 16 octobre est conservée également.

### Exécution

1. Migration appliquée et tests réalisés d'abord dans `cahier_doleances_test`.
2. Tests backend et compatibilité TypeScript/frontend validés.
3. Migration additive `forms_statistics_v1` appliquée à la seule base applicative
   locale, après contrôle du nom de base et avec attente de verrou bornée.
4. **Une unique génération initiale réelle** exécutée, contrôlée puis publiée.
5. Deux processus de recette frais ont relu les sept formulaires et les endpoints
   statistiques, sans relancer la génération ni vider les caches PostgreSQL.

Publication : **`9c733026-4a92-46dd-9b17-15827ce5ad3e`**, révision source **0**,
méthode `historical-answers-v1`. Empreinte globale :
`c57eeeb2cf102f1127fdd1353b8c7a9832ebc6360f7a240d77f23f15a40cc252`.
Date de calcul enregistrée : début de la transaction, 20 octobre à 17:49:01,
heure locale. Durée totale avant COMMIT : **80,68 secondes** environ.

| Formulaire | Instantanés de questions | Payloads de choix |
|---|---:|---:|
| 2 | 12 | 12 |
| 4 | 33 | 8 |
| 5 | 37 | 7 |
| 7 | 8 | 1 |
| 10 | 16 | 6 |
| 11 | 7 | 7 |
| 12 | 7 | 7 |
| Total | **120** | **48** |

Les 72 questions ouvertes disposent d'un compteur persistant. La somme des tailles
PostgreSQL des payloads statistiques JSONB est **36 692 octets**, hors colonnes,
index, métadonnées et overhead des tables.

## 7. Comparaison avec les calculs historiques

Avant publication, le service historique a été exécuté dans la même vue source
sur les questions **2**, **4** et **159**, choisies pour couvrir respectivement
choix unique binaire, choix multiples et présence importante d'Autre. Les payloads
publics complets ont été comparés, pas uniquement leurs totaux : **parité exacte**.
Tous les compteurs de réponses ont aussi été comparés aux agrégats par question.
Les clés étrangères pertinentes sont présentes et validées sur la base locale.

Exemple conservé : question 159, **155 657 réponses**, **189 150 sélections
d'options**, **91 717 réponses avec Autre**, **280 867 sélections au total**,
somme des pourcentages arrondis **180,44 %**. Les catégories ne sont pas rendues
artificiellement exclusives et la somme n'est pas forcée à 100 %.

Les cas rares ne sont pas fabriqués dans le corpus : options nulles, questions
vides, contribution avec plusieurs réponses à une question, Autre seul ou associé
à une option sont validés exclusivement par fixtures dans `_test`.

## 8. Tests et performances

### Tests

| Vérification | Résultat |
|---|---|
| Backend, bases isolées `_test` | **330 tests passés**, 7 sous-tests passés, 1 test d'ingestion ignoré |
| Frontend Vitest | **132 tests passés**, 15 fichiers |
| Navigateurs ciblés Formulaires / Dashboard / Questions | **19 tests Chromium passés** |
| TypeScript | Réussi |
| Biome frontend | Réussi |
| Ruff, nouveaux services/scripts/schémas et routeurs | Réussi |
| Builds frontend normal et test, hors réseau | Réussis |
| Export OpenAPI et contrôle des types générés | Réussis |

Le test d'ingestion ignoré nécessite sa propre base dédiée ; aucun corpus de
travail n'est employé comme fixture. Les avertissements préexistants de TestClient
et des Operation ID SEO hors v1 sont conservés, sans dérive du contrat exporté.

Les nouveaux tests couvrent : disponibilité/absence/invalidation, reproductibilité
des empreintes, empreinte de ligne altérée, ligne manquante, méthode incompatible,
interruption à cinq phases (y compris après changement transactionnel du pointeur),
conservation de la précédente génération, verrou de génération concurrente,
**véritable modification source concurrente pendant une transaction REPEATABLE READ**,
compteur divergent et rattachement inter-formulaires incorrect. Un test à deux
connexions vérifie également la stabilité de la vue de lecture HTTP pendant une
écriture source concurrente, son mode READ ONLY et le rétablissement du pool.

Les tests statistiques existants ont été adaptés pour publier explicitement leurs
fixtures, en conservant leurs assertions de parité, BIGINT, arrondis, options à
zéro et contributions distinctes. Une réponse Autre seule est aussi testée.
Les captures SQL prouvent que les GET répétés n'interrogent pas les tables de
réponses pour calculer les statistiques. Les tests d'intégration hybride passent ;
seule leur vérification de version de schéma test a été mise à jour, sans modifier
le moteur.

### Mesures locales avant/après

Même famille de recette ASGI que FORMS-001, avec routes réelles et PostgreSQL local.
Aucun modèle GPU, rendu SSR ou réseau distant n'est inclus dans ces temps.

| Endpoint statistique | Avant FORMS-001 | Après précalcul | JSON avant/après |
|---|---:|---:|---:|
| Formulaire 2 `/stats` | 3 664 ms | 12,6 ms | 11 096 octets |
| Formulaire 5 `/stats` | 1 133 ms | 3,0 ms | 5 932 octets |
| Formulaire 7 `/stats` | 297–445 ms | 1,8 ms | 1 326 octets |

Le premier appel après précalcul inclut l'ouverture du pool. Les délais SQL
observés pour les trois petites lectures du formulaire 2 totalisent environ
1,5 ms, le reste incluant connexion, traitement Python et parcours ASGI.
Aucune agrégation de réponses n'est exécutée. Les JSON statistiques conservent
leur forme et leurs poids sur ces exemples.

Détail **enrichi** Formulaire, deux processus neufs, même génération :

| Formulaire | Questions | Temps observés | JSON enrichi |
|---|---:|---:|---:|
| 2 | 12 | 3,80–4,07 ms | 11 498 octets |
| 4 | 33 | 2,37–2,82 ms | 16 482 octets |
| 5 | 37 | 2,14–2,84 ms | 16 485 octets |
| 7 | 8 | 1,64 ms | 4 103 octets |
| 10 | 16 | 1,61–1,82 ms | 10 367 octets |
| 11 | 7 | 1,33–1,54 ms | 6 512 octets |
| 12 | 7 | 1,39–1,70 ms | 7 502 octets |

Les trois SELECT sont constants et les mêmes données de choix sont retrouvées
sur les contrats Formulaire et Dashboard. La cible locale de **200 ms** est atteinte
sur ces observations. Elles ne constituent ni un percentile statistique, ni une
qualification de charge, ni un test de cache disque froid. Aucune campagne lourde
ni nouvelle génération pour les mesures n'a été exécutée.

## 9. Exploitation, limites et FORMS-003

La procédure complète de recalcul après import, reprise d'échec, fraîcheur,
commandes de test et limites de transaction est dans
[Statistiques locales](statistiques-locales.md). Les anciennes générations sont
conservées ; leur purge éventuelle reste une maintenance explicite future. Les
trois tables sont gérées explicitement par la migration SQL et ne sont pas des
modèles ORM : une future migration autogénérée devra les inclure dans les
métadonnées ou les exclure de la comparaison pour éviter une proposition de
suppression involontaire.
Le recalcul peut être coûteux et mobiliser PostgreSQL : le lancer hors des
consultations sensibles, sans tâche planifiée automatique.

Les triggers d'invalidation ajoutent une écriture sur une petite ligne par
instruction source. Leur coût sur un import massif concurrent n'a pas été mesuré.
Les superutilisateurs peuvent contourner ces protections : les opérations
privilégiées doivent suivre la procédure d'invalidation. Un changement de méthode
requiert une nouvelle version et une publication explicite.

**Processus déjà lancés :** le serveur local sur le port 8000 a été constaté avec
l'ancien contrat encore importé. Il doit être redémarré pour charger ce code ;
le processus SSR existant doit également être redémarré pour prendre le client
validateur à jour. Les validations ci-dessus utilisent de nouveaux processus et
les nouvelles routes ; aucune fermeture forcée d'un processus utilisateur n'a
été effectuée.

FORMS-003 peut maintenant consommer en un appel les questions ordonnées, compteurs,
catégories, effectifs, pourcentages, liens et métadonnées de génération. Il doit
utiliser l'état de disponibilité pour distinguer null de zéro, conserver les
libellés et les définitions, et afficher les graphiques et détails proposés dans
FORMS-001. Le compteur d'une question ouverte reste un nombre de réponses
enregistrées, sans promesse sur le nombre de témoignages consultables.

La fusion des pages, le sommaire, les nouvelles visualisations, les accordéons et
la redirection Dashboard ne sont **pas** commencés ici. Aucune bibliothèque
graphique nouvelle ni modification des routes React concernées.

**FORMS-002 s'arrête après cette implémentation locale, ses validations et ce rapport.**

## Correctif après signalement : recherche hybride indisponible

Le redémarrage du service a révélé une régression non détectée par les fixtures
hybrides : le manifeste réel avait été créé sous `remove_runtime_caches`, tandis
que les fixtures fabriquaient leur manifeste directement sous la révision courante.
La migration `forms_statistics_v1` a donc provoqué `search_not_ready` malgré des
documents et embeddings inchangés.

Le lecteur public accepte maintenant explicitement cette migration additive,
en conservant les contrôles de cluster/OID/base, modèle, corpus, génération,
index et rôle READ ONLY. Aucune métadonnée RAG ni aucun embedding n'a été modifié.
Les révisions inconnues et les autres changements d'identité restent refusés.
Les gardes de maintenance/écriture restent stricts.

Un test de non-régression couvre le manifeste antérieur, la migration autorisée,
le refus d'une autre révision et d'une identité physique différente. FastAPI local
a été redémarré en conservant sa commande et sa configuration : recherche réelle
HTTP 200 avec BGE-M3, vingt résultats sur la première et la deuxième page,
retour stable au premier curseur et rendu React SSR HTTP 200 vérifiés.
Le [guide de maintenance](statistiques-locales.md#migrations-applicatives-futures-et-recherche-hybride)
définit désormais le contrôle à réaliser après chaque future migration.
