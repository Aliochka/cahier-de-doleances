# Exécution technique sur Gavroche — 8 novembre 2026

**État final confirmé le 9 novembre 2026 à 07:48 UTC (08:48 à Paris) : les nouvelles images du commit `78cdf0a167d093c12ded146fb4b88cd081c2c987` sont actives et saines. Le stockage de 1789 est installé et vérifié ; le public accède uniquement au Grand Débat via H1. Le multicorpus et la publication historique restent désactivés.**

Les sections suivantes retracent les étapes intermédiaires et leurs arrêts. Le bilan final en fin de document prévaut sur ces états historiques. Réserve conservée : la requête très fréquente « Non », question 293, a dépassé le budget de recherche ; son statut sur l'ancienne image n'a pas été établi.

## État avant reprise du correctif de maintenance

Le code initial retenu est `469ad8640088985301dd549ad08f928e9c02c3a2`, déjà commité et propre au début de la mission. 85 tests ciblés ont réussi avant la première séquence. Aucun secret ni artefact documentaire privé n'a été ajouté au dépôt.

La conservation est terminée dans `/backups/postgresql/rollback-multicorpus-20261108T172441Z`, répertoire privé neuf. La sauvegarde PostgreSQL froide du 2 novembre n'a pas été recopiée ou modifiée. Les trois archives ont été relues et hachées :

| Archive | Octets | SHA-256 |
|---|---:|---|
| `configuration.tar` | 174 080 | `d4ffdffd0b4635dab88a150fa6ce9e787622489cfe031c7551743a19a557900b` |
| `images.tar` | 584 146 432 | `0873a3d3469336cea91f0d3a1a62e62b23ac5afcc45a219c8ef36fbe6c8faf00` |
| `model.tar` | 2 293 350 400 | `676ea08299a85539c83d5e9fa351d0ecc9d7c222ab6aae0ab9afa2268a9d1ead` |

Le reçu et l'attestation complète existent réellement ; l'exception `gavroche-cold-20261102-v1` les a acceptés. La comparaison précédant les écritures était conforme à la référence, snapshot `1155:1155:`. Les premières archives ont été réutilisées et leurs hashes revérifiés lors de la reprise autorisée par l'opérateur.

La première tentative s'est arrêtée sur une erreur dans la sonde d'exploitation : `HEALTHCHECK_HOST=localhost`, destiné au contrôle interne, avait été utilisé à tort comme domaine TLS. Caddy sert `cahierdedoleances.fr`. La sonde a été corrigée sans désactiver TLS ; l'accueil et `/healthz` ont répondu 200, puis l'opérateur a explicitement autorisé la reprise.

## Résultats de la seconde séquence

Le checkout distant a été positionné sur le SHA exact. Les images ont été construites en conservant les anciennes :

| Service | Nouvelle image construite, pas encore déployée |
|---|---|
| Backend CPU `mc-469ad8640088` | `sha256:5125817d43cbcd062df1d7eb45bfa79bb1e4d283f3c7ebba8e2a41b8f257fe7a` |
| Frontend `mc-469ad8640088` | `sha256:c336894af822895a55ce2dac98438a77313abbcea53b7ac8e671d3f6e4fc468d` |

Packaging CPU réussi : PyTorch `2.10.0+cpu`, transformers `4.57.6`, tokenizers `0.22.2`, NumPy `2.2.6`, recette `h1-public-v2-ts-rank`. Aucun modèle chargé ni embedding calculé pendant ce contrôle. Les modules documentaires/multicorpus sont importables.

Le préprovisionnement contrôlé a créé le rôle `cahier_documentary_owner`, le schéma vide `documentary` et sa seule appartenance de maintenance. L'import s'est ensuite arrêté avec `InternalError`, avant toute bascule applicative. Les contrôles en lecture seule constatent **zéro table documentaire** ; aucun document, passage, vecteur ni release historique n'a été importé.

H1 et les anciens conteneurs sont restés actifs. Les identités physiques sont inchangées ; les compteurs GDN restent 5 172 356 / 5 187 190 et les index vérifiés sont valides. Le snapshot devient `1156:1156:` après la seule transaction de préprovisionnement autorisée ; il ne faut pas fabriquer une nouvelle attestation prétendant observer `1155:1155:` après cette opération. La preuve antérieure reste datée de sa véritable comparaison avant écriture.

## Cause et correctif local

Le rôle de maintenance est configuré avec `default_transaction_read_only=on`. Le client d'import opt-in ne surchargeait pas ce réglage lorsqu'il ouvrait une session explicitement writable ; `SET LOCAL ROLE` ne désactive pas le mode lecture seule. Le cas est reproduit sur un nouveau cluster local avec la même configuration de rôle et l'erreur PostgreSQL `25006` (`read_only_sql_transaction`).

Le correctif de [production.py](../documentary/production.py) ajoute **uniquement aux connexions d'import explicitement autorisées** l'option de session `default_transaction_read_only=off`. Les connexions de lecture gardent `on` et leurs transactions explicites `READ ONLY`. Le réglage du rôle en production n'est pas changé. Les gardes de preuve, identité, rôle propriétaire, SQL documentaire et non-publication restent identiques.

Un test réel sur un PostgreSQL local isolé reproduit d'abord le refus d'origine, vérifie ensuite l'écriture documentaire autorisée, le refus d'écriture GDN, le maintien des transactions de lecture et la conservation du défaut readonly pour une connexion ordinaire. Le test d'intégration documentaire existant (migration, transfert et permissions sur des bases temporaires) passe également. Il ne s'exécute pas contre Gavroche.

La reprise de production est suspendue tant que ce correctif, son nouveau SHA et la poursuite après cette seconde erreur ne sont pas validés. Elle devra conserver les archives déjà produites et distinguer les écritures documentaires autorisées des modifications GDN. **Aucune publication ni activation du multicorpus n'est autorisée.**

Les journaux et reçus détaillés restent dans `private/search/deployment-469ad864-20261108T171700Z/` et `private/search/deployment-469ad864-20261108T173000Z/`, ignorés par Git. Le paquet source historique est conservé et vérifié dans le premier répertoire de staging de Gavroche ; aucune base de laboratoire n'est raccordée à l'application publique.

## Reprise validée avec `9064db7`

L'opérateur a validé explicitement `9064db7a35a801f96c905926101adfc28d818a90`. Le checkout distant et les nouvelles images construites portent ce SHA :

| Service | Image `mc-9064db7a35a8` construite |
|---|---|
| Backend CPU | `sha256:396e090f40ba289bacafa8ba1630c58704a70a50910d918b1edb724b047b2e61` |
| Frontend | `sha256:9f3a797ba39009b3c7d6de656e37d8061468af5c705a3cefa3b5705238af9dcb` |

Les archives existantes ont été relues et l'attestation préprovisionnement du 8 novembre à 17:32:08 UTC conservée **sans modifier sa date ni son snapshot**. Un contrôle distinct, à 17:47:57 UTC, constate le seul préprovisionnement autorisé, snapshot `1156:1156:`, et un état GDN identique à la référence. Une tentative d'authentification sudo a été interrompue avant opération ; le lanceur a ensuite été corrigé pour restaurer le terminal. Aucun changement du rôle de production n'a été nécessaire.

La migration `doc_0001` et le transfert ont installé **1 267 documents, 11 391 passages, 10 748 vecteurs et 86 341 termes lexicaux**. Le contrôle final a rencontré une seconde erreur : le garde refusait la CTE `WITH expected … SELECT …` qui vérifie les fréquences lexicales. Cette requête est exclusivement en lecture ; elle n'avait pas été incluse dans les formes autorisées du garde.

L'échec a correctement remis `representations_ready` et `statistics_ready` à false. La release demeure `verified`, `publication_authorized=false`, pointeur actif absent et zéro document public. Les anciennes images sont encore actives : **l'installation technique n'est pas achevée à ce point du journal**.

Le correctif suivant nomme cette requête de validation et autorise **uniquement son SQL exact compilé pour psycopg2**. Il n'autorise pas génériquement `WITH`, ne modifie pas le calcul des statistiques et conserve le rejet des CTE de mutation et des instructions ajoutées. Un test de transfert complet sous le véritable `ProductionDestination` (rôle readonly par défaut, propriétaire dédié, migration, décisions, représentations et vérifications) passe sur deux bases isolées, avec des vecteurs synthétiques ; aucune inférence n'est réalisée. Les fixtures de régression sont désormais isolées pour pouvoir exécuter ensemble les deux tests PostgreSQL sans contamination.

Au contrôle RO du **8 novembre à 17:57:59 UTC**, snapshot `1168:1168:`, les index GDN sont valides et les décisions sont conformes : Artois 1/2 admissibles et vectorisés, 3/4 exclus sans vecteurs ; titre validé d'Aunay-la-Côte, titre source et avertissements conservés ; 43 documents non candidats, sans droits publics. Le déploiement reste arrêté dans l'attente de la validation de ce nouveau correctif et de sa reprise. Journaux privés : `private/search/deployment-9064db7-20261108T175000Z/`.

Validation du correctif CTE : **89 tests réussis**, avec les intégrations PostgreSQL activées (`DOCUMENTARY_TEST_PG_BIN=/usr/lib/postgresql/17/bin`), aucun test ignoré. Le parcours complet sous le véritable garde passe également après simulation de l'état partiel (données présentes, préparation false) et réimport idempotent. Ces opérations sont toutes réalisées dans de nouveaux clusters temporaires locaux ; rien n'est relancé sur Gavroche pendant ces tests.

## Installation vérifiée avec `78cdf0a`

L'opérateur a approuvé le commit `78cdf0a167d093c12ded146fb4b88cd081c2c987`. L'import idempotent a été vérifié entièrement le 8 novembre à **18:11:54 UTC** : textes, identifiants, offsets Unicode, représentations, empreintes et décisions éditoriales conformes. Les représentations existantes ont été transférées, **sans calcul d'embeddings**. La compatibilité des représentations et statistiques lexicales a été vérifiée dans la locale cible `fr_FR.UTF-8`, sans reconstruire les statistiques GDN.

Une première bascule a renvoyé un 503 H1 pendant l'initialisation asynchrone : le contrôle HTTP était prêt avant le moteur. Le retour aux anciennes images a alors été effectué. Le diagnostic de la nouvelle image en conteneur éphémère sans serveur a ensuite confirmé une initialisation H1 réussie en **11,1 secondes**. La séquence d'exploitation a été corrigée pour attendre la disponibilité H1 pendant au plus 180 secondes, sans augmenter le budget de recherche et sans changer le code applicatif approuvé.

La seconde bascule a rendu H1 disponible et permis les contrôles de recherche générale et de pagination. La requête « Non », question 293, a toutefois reçu un **504 après 10,02 secondes**. Le retour arrière automatique a été bloqué par le répertoire `rollback-files` déjà créé lors du précédent retour. Un retour arrière utilisant un nouveau répertoire a été préparé, mais **l'opérateur a explicitement choisi de conserver les nouveaux conteneurs**, après consultation du site. La commande de retour arrière proposée n'a pas été exécutée.

Le [protocole principal](deploiement-multicorpus-gavroche.md) utilise désormais un répertoire neuf pour chaque retour arrière et distingue la disponibilité HTTP de celle de H1. Les archives de conservation ne sont ni écrasées ni supprimées.

## Images effectivement actives

Contrôle Docker du **9 novembre à 07:48:48 UTC** : les quatre services sont `healthy`, aucun OOM, checkout et labels des deux images applicatives conformes au SHA approuvé.

| Service | Ancienne image conservée | Image active |
|---|---|---|
| Backend | `sha256:e0c26f229536597004ef299d6e8406fb087916d0511eabe8bd02e5543070c7cd` | `sha256:0cf56991af956848df143dbe2af8c53c0cfe7618af128b1232bb1b4996874853` |
| Frontend | `sha256:73e31e5b321040259aae7769d5fc4eaebcd90c493ebdc85f1168d1313176a1eb` | `sha256:3473018c996c2c1900517fc45f8a76054dfbc12d2b744e6b33d46823f80bd9e0` |

Tags des nouvelles images : `cahier-de-doleances-app:mc-78cdf0a167d0` et `cahier-de-doleances-frontend:mc-78cdf0a167d0`. Conteneurs démarrés le 8 novembre à **18:25:32 UTC** pour le backend et **18:25:37 UTC** pour le frontend ; ils sont restés actifs après la décision de conservation.

PostgreSQL conserve l'image `sha256:30ee450c42fda0596abaf71066c1612c79a0aaa791e655e5e00ce2c1e33ab6cc`, Caddy `sha256:834468128c7696cec0ceea6172f7d692daf645ae51983ca76e39da54a97c570d`. Le conteneur PostgreSQL et son serveur tournent toujours depuis le **6 novembre à 19:59:25 UTC**. Aucun redémarrage ni changement de son image ou de ses montages n'a été effectué.

## Intégrité et non-publication finales

Contrôle SQL en transactions `READ ONLY` le **9 novembre à 07:40:33 UTC** :

| Élément | Résultat |
|---|---|
| Révisions | `documentary.alembic_version=doc_0001`, `public.rag_alembic_version=rag_0007` |
| Documents / passages / vecteurs | **1 267 / 11 391 / 10 748** |
| Population candidate / autres documents | **1 224 / 43** ; les 43 restent hors périmètre candidat/public |
| Statistiques 1789 | **86 341 termes**, population **10 748**, somme DF **1 770 363**, locale `fr_FR.UTF-8` |
| Release | `verified`, représentations/statistiques prêtes, **`publication_authorized=false`** |
| Pointeur actif / documents publics | **Aucun / zéro** |
| Artois | Passages 1/2 admissibles et vectorisés ; 3/4 exclus et sans vecteurs |
| Aunay-la-Côte | Huit passages admissibles ; titre de présentation validé, titre source et avertissement préservés |
| Index HNSW documentaire | **Aucun** |
| Journal éditorial | Le lecteur public n'a pas de droit SELECT sur `editorial_decision` |
| Maintenance | Défaut `default_transaction_read_only=on` conservé ; aucun ALTER ROLE pour le désactiver |

Les compteurs de manifeste GDN restent **5 172 356 documents / 5 187 190 segments**. L'état complet de l'espace, les recettes, empreintes, statistiques lexicales et **26 index `rag_full`/`rag_tuning`** ont été comparés à la référence : mêmes définitions, relfilenodes et validité. Cela ne constitue pas un nouveau hachage des millions d'embeddings ; aucun ordre de modification/reconstruction GDN n'a été exécuté. Les OID et les relfilenodes provenant des deux formats de relevé ont été comparés après normalisation de leurs types numériques.

Les fichiers `.env.deploy`, lecteur de recherche et publication GDN sont identiques à leurs copies de conservation. La publication conserve notamment le SHA-256 `bb117a749ded5512938d2ab701deaca6a3aa4fca8be5e08faa212fb26b79de32`. Configuration effective : **`HYBRID_SEARCH_ENABLED=true`, CPU/float32, deux threads ; `enabled=false`, `local_preview=false`, aucun jeton d'aperçu**. Aucun `activate-1789.sql`, autorisation de publication ou promotion de release n'a été exécuté.

## Vérifications publiques et exploitation

Le 9 novembre, **28 contrôles HTTP**, complétés par deux contrôles d'anciennes URL, ont réussi : accueil, santé, formulaires, questions, contributions, navigation, recherche générale, recherche par question et pagination avant/arrière sans répétition du résultat échantillonné. Les anciennes URL `?contrib=1` répondent 200, de même que les liens de questions avec leur redirection canonique.

| Sonde | Avant bascule le 8 novembre | Après, le 9 novembre |
|---|---:|---:|
| H1 « transports publics », première page de taille 1 | 1,16 s | **1,17 s** |
| H1 « vélomobile », première page de taille 1 | 0,24 s | **0,23 s** |
| Recherche par question « vélomobile », question 279 | Non mesurée | **0,04 s**, neuf réponses, recette `h1-question-lexical-v1-ts-rank` |

La recherche générale conserve `h1-public-v2-ts-rank`. Ces mesures ponctuelles ne sont pas des distributions de latence ni une nouvelle validation de pertinence. La requête très fréquente « Non », question 293, demeure un **cas de dépassement de budget observé**, non corrigé ; aucune comparaison de cette requête avec l'ancienne image n'a été réalisée, donc son caractère antérieur ou régressif n'est pas établi. L'opérateur a choisi de garder les nouvelles images avec cette réserve. Aucune optimisation de classement ni augmentation de délai n'a été appliquée.

Les API et pages de catalogue/lecture de 1789 répondent **404**, y compris avec un identifiant de document réellement présent, de faux en-têtes d'aperçu et une adresse locale usurpée. Le filtre `corpus=1789` est refusé en **422**. `/api/v1/corpora` annonce uniquement 2019 disponible/publié ; 1789 est indisponible, non publié, sans aperçu.

Les journaux bornés inspectés ne montrent pas d'erreur applicative backend/frontend/Caddy. PostgreSQL contient trois messages au même instant, le **8 novembre à 18:26:01 UTC** : un `statement timeout` et l'arrêt de deux workers parallèles ; leur horodatage coïncide avec le 504 de « Non ». Le postmaster n'a pas redémarré. Aucun autre message d'erreur n'a été relevé dans cette fenêtre inspectée.

Consommations instantanées au relevé Docker : backend environ **646 Mio**, frontend **232 Mio**, PostgreSQL **445 Mio**, Caddy **69 Mio**, sans OOM. Les connexions observées comprennent trois connexions du lecteur de recherche, quatre du compte applicatif et la connexion de contrôle de maintenance. L'état détaillé de certaines connexions n'est pas visible par ce rôle de contrôle ; ces chiffres ne sont pas un test de charge.

## État réel de fin de mission

**Application en production sur le nouveau code, H1 actif, données historiques installées et vérifiées, corpus historique inaccessible publiquement.** Les réserves connues sont le timeout de la requête fréquente et les corrections apportées à l'exploitation (attente H1, retours arrière dans un répertoire neuf). Le déploiement ne vaut ni autorisation éditoriale ni activation multicorpus.

Les preuves finales sont privées dans `private/search/deployment-78cdf0a-20261108T182000Z/` : contrôles HTTP, vérification SQL finale, relevés Docker du 9 novembre et journaux d'exploitation. Les sources/dumps, secrets, archives et journaux ne sont pas ajoutés au dépôt. La clôture du 9 novembre est **strictement en lecture seule**, sans nouvelle bascule, migration, import, calcul de vecteurs ou publication.
