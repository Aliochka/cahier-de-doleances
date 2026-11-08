# Exécution technique sur Gavroche — 8 novembre 2026

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
