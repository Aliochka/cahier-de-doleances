# Statistiques persistantes — maintenance locale FORMS-002

Périmètre : Hal9000. Aucune commande ne cible Wallace. La base applicative reste
`cahier_doleances_local` ; la base RAG et les embeddings ne sont pas utilisés.

## Installation et lecture

La migration applicative `forms_statistics_v1`, après `remove_runtime_caches`,
ajoute les tables de génération et les triggers d'invalidation. Elle a été
appliquée localement le 20 octobre 2026, après sauvegarde. Les migrations
historiques et les tables de contributions restent inchangées.

Sur une autre installation locale autorisée, vérifier la cible et une sauvegarde
avant `alembic upgrade head`. Le fichier `.env` applicatif doit désigner la base
locale ; ne jamais copier des URL ou mots de passe dans une commande publiée.

Les dépendances Python existantes suffisent : aucun extra GPU ou service de cache
n'est nécessaire. Les GET lisent PostgreSQL directement dans une transaction REPEATABLE READ en
lecture seule, sans calcul ni cache
mémoire à chauffer. Un redémarrage conserve les instantanés.

## Recalcul explicite après import ou correction

1. Terminer et valider les transactions d'import/correction.
2. Garder les triggers `statistics_source_changed` actifs. Les modifications des
   tables sources invalident automatiquement l'ancienne publication.
3. Depuis la racine du dépôt, avec le `.env` local :

```bash
env -u TEST_DATABASE_URL .venv/bin/python scripts/generate_statistics.py
```

La commande refuse les hôtes distants et les bases autres que
`cahier_doleances_local` ou les bases locales terminées par `_test`.
Elle utilise une transaction `REPEATABLE READ`, un verrou transactionnel de
maintenance non bloquant, une limite SQL de dix minutes par instruction et une
attente de verrou de cinq secondes. Aucun GET public ne peut déclencher ce calcul.

Les phases `source`, `aggregated`, `validated`, `prepared`, `published` sont
annoncées. `published` annonce la modification du pointeur dans la transaction ;
**seule la sortie finale JSON et le code de sortie 0 confirment le COMMIT réussi**.
La sortie contient UUID, empreinte, compteurs, échantillon historique et durée,
sans texte citoyen ni identité personnelle.

Le calcul contrôle les rattachements réponse/question/formulaire et option/réponse,
la forme des champs Autre et les compteurs existants. Les clés étrangères actives
et validées garantissent également l'existence des parents. Les compteurs absents
pour une question réellement vide sont acceptés après recomptage à zéro ; une
absence avec des réponses ou un compteur divergent bloque la publication.

Les réponses de toutes les questions sont agrégées en lot. Les modalités à zéro
restent présentes. La méthode et l'arrondi historiques sont réutilisés ; un petit
échantillon représentatif est recalculé par le service historique et comparé
avant publication. La totalité des numérateurs et dénominateurs d'une question
provient du même snapshot transactionnel.

## Fraîcheur et erreurs

La ligne `statistics_source` contient un UUID de corpus, une révision et le
pointeur publié. Les INSERT/UPDATE/DELETE/TRUNCATE de `forms`, `questions`,
`options`, `answers`, `answer_options`, `contributions` et `question_stats`
incrémentent la révision dans la transaction qui les effectue. Une mise à jour
sans changement effectif peut invalider par prudence. Les comptes/auteurs et les
marque-pages ne nécessitent pas de recalcul statistique.

Une publication n'est disponible que si UUID de corpus, révision et version de
méthode concordent. Les lecteurs vérifient aussi la complétude des lignes et les
empreintes des instantanés consultés. Après une modification source validée,
les statistiques restent indisponibles jusqu'à une nouvelle publication explicite.

- Formulaire documentaire : HTTP 200, `statistics_availability.status=unavailable`,
  compteurs et statistiques à null, questions et navigation conservées.
- API exclusivement statistique : HTTP 503, sans calcul de secours.
- Une vraie absence de réponses reste zéro dans une génération disponible.

En cas d'interruption ou d'erreur, la transaction est annulée ; les lignes
préparées et le pointeur ne sont pas publiés. L'ancienne génération reste stockée,
et disponible seulement si elle correspond encore à la source. Corriger la cause
puis relancer la commande complète ; aucune reprise d'un demi-calcul n'est faite.
Le verrou est libéré automatiquement à la fin de la transaction ou de la connexion.

Si une écriture concurrente change la source pendant le calcul, le verrou final
sur la révision provoque un échec de sérialisation ou un refus de publication.
Attendre la fin de l'import puis relancer. Un second générateur échoue immédiatement.
Les lectures publiques restent de simples SELECT MVCC, sans verrou de maintenance.

**Maintenance privilégiée :** ne pas désactiver les triggers, utiliser
`session_replication_role=replica`, restaurer partiellement les tables sources ou
modifier le schéma en supposant que l'invalidation fonctionnera encore. Pour une
telle opération exceptionnelle, invalider explicitement la publication avant
l'opération (`UPDATE statistics_source SET revision=revision+1 WHERE id=1`),
contrôler les compteurs, réactiver les protections puis recalculer. Ces opérations
ne sont jamais déclenchées par l'application publique.

Les anciennes générations sont conservées. Aucun nettoyage automatique ni tâche
planifiée n'est introduit. Leur suppression éventuelle relève d'une maintenance
explicite qui conserve la génération publiée.

## Vérification sans nouveau calcul

```bash
env -u TEST_DATABASE_URL .venv/bin/python scripts/smoke_form_statistics.py
```

La recette lit les sept formulaires, leurs 120 questions, les sept sorties
statistiques et trois questions représentatives. Elle vérifie l'ordre, les IDs
chaînes, les mêmes données sur les deux contrats, la génération unique, trois
SELECT par formulaire enrichi et l'absence de lectures des tables de réponses.
Elle utilise des connexions strictement READ ONLY et ne charge pas BGE-M3.

Lancer une seconde fois ce script démarre un nouveau processus et confirme la
persistance sans cache Python ; cela ne génère pas une nouvelle publication.
La mesure est HTTP ASGI locale avec les routes réelles, sans middleware global,
rendu SSR ni réseau distant. Ne pas l'interpréter comme une garantie sous charge.

Tests d'écriture uniquement sur bases isolées migrées :

```bash
ALEMBIC_DATABASE_URL=postgresql:///cahier_doleances_test .venv/bin/alembic upgrade head
TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_TEST_DATABASE_URL=postgresql:///cahier_doleances_test \
RAG_STORAGE_TEST_DATABASE_URL=postgresql:///cahier_rag_test \
  .venv/bin/pytest tests -q
```

Après mise à jour du code, redémarrer les processus FastAPI et SSR existants.
Leurs modules importés ne changent pas automatiquement. Depuis FORMS-003, la page
Formulaire consomme directement le contrat enrichi et affiche questions et résultats.
L'ancienne URL Dashboard redirige en HTTP 308 sans appel statistique. Les endpoints
statistiques restent disponibles pour les autres consommateurs. Voir les rapports
[FORMS-002](rapport-forms-002.md) et [FORMS-003](rapport-forms-003.md).

## Migrations applicatives futures et recherche hybride

Le manifeste d'indexation conserve la révision applicative au moment de sa
création. Une migration indépendante des réponses peut donc changer Alembic sans
invalider les embeddings. La lecture publique autorise désormais explicitement
`remove_runtime_caches` → `forms_statistics_v1` dans
`compatible_source_identity` (`rag/src/cahier_rag/search/service/reader.py`).
Les identités de cluster, OID et nom de base restent identiques et obligatoires ;
les autres contrôles du corpus, des index et du rôle lecteur restent inchangés.
Les gardes d'écriture/maintenance RAG ne sont pas assouplis.

Pour chaque nouvelle migration :

1. Examiner son effet sur les réponses, questions, formulaires, liens historiques
   et la représentation produite par l'extracteur documentaire.
2. Si elle est additive et indépendante de ce contrat, déclarer explicitement
   la compatibilité entre la **révision enregistrée dans le manifeste** et la
   nouvelle révision. Ajouter seulement la dernière transition Alembic ne suffit
   pas si le manifeste est plus ancien. Ne pas réécrire le manifeste pour contourner
   un contrôle.
3. Si elle change le contrat documentaire ou les données indexées, conserver le
   refus et prévoir l'adaptation appropriée ; ne pas la classer compatible par défaut.
4. Tester un manifeste antérieur face au schéma migré, avec refus des révisions
   inconnues, bases/OID/clusters différents et régressions de permissions.
5. Après migration locale, redémarrer et effectuer une recherche avec le véritable
   BGE-M3, les deux bases, une pagination et un contrôle des liens, en plus des tests
   `_test`. Des fixtures indexées directement sous la nouvelle révision ne couvrent
   pas ce scénario de mise à niveau.

Évolution recommandée : introduire une version explicite du **contrat d'extraction
source**, distincte de la révision Alembic générale. Cela permettrait de conserver
la recherche pendant les migrations sans rapport avec ses données. Cette évolution
nécessite son propre contrat et des tests de compatibilité ; elle n'est pas
introduite dans le correctif ponctuel.
