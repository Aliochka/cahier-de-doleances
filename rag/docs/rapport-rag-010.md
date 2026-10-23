# RAG-010 — Interface locale d’annotation humaine

L’interface permet d’annoter les **400 couples de développement**, correspondant
à **236 documents distincts et 20 requêtes**, sans modifier les sources RAG-009.
Aucun jugement humain n’a été simulé dans la session réelle.

## Architecture livrée

- `src/cahier_rag/annotation/session.py` : validation des références, permutation
  déterministe, progression, brouillons, jugements et persistance atomique.
- `documents.py` : lecture SQLAlchemy Core de la base RAG, transactions
  explicitement `READ ONLY`, délais de 5 s pour les requêtes et 2 s pour les
  verrous, vérification des empreintes et fermeture des connexions.
- `web.py` : application FastAPI créée explicitement, routes HTML/JSON, export,
  contrôles loopback/hôte/origine/jeton, messages d’erreur sans secrets.
- `page.html`, `ui.css`, `ui.js` : interface sans framework frontend, texte
  intégral via `textContent`, disposition sur deux colonnes sur ordinateur,
  raccourcis, notes, commentaire, navigation et consultation de la contribution.
- `cli.py` : lancement sur `127.0.0.1` uniquement, verrou de processus et arrêt
  propre du moteur SQLAlchemy.
- `evaluation/files.py` : extraction du validateur existant en fonction
  réutilisable en mémoire ; format et comportement RAG-006 inchangés.

FastAPI 0.143.0 et Uvicorn 0.35.0 sont dans l’option **`annotation`** du projet
RAG, aux versions du backend. Le moteur lexical garde ses dépendances minimales.
`httpx` 0.28.1 rejoint le groupe de test `dev`. Seul le verrou RAG est actualisé.
Les ressources HTML/CSS/JS sont incluses dans le wheel et la distribution source.

## Lancement

Depuis le dossier `rag/` :

```bash
uv sync --locked --extra annotation --dev
export RAG_DATABASE_URL='postgresql:///cahier_rag'
uv run --locked --extra annotation cahier-rag-annotate --evaluator ro
```

Ouvrir **http://127.0.0.1:8765**. Les options sont `--env-file`, `--port`,
`--seed` et `--evaluator`. Aucune option ne permet de changer l’adresse d’écoute.
Le serveur n’a pas été laissé actif à l’issue des validations.

## Session, sauvegarde et reprise

La session se crée lors du premier lancement dans
`evaluation/local/rag010/session.json`, emplacement ignoré par Git.
La graine par défaut **20261020** est enregistrée avec les empreintes du pool,
du corpus, des requêtes, de l’ordre, ainsi que l’évaluateur et la version
**`rag010-v1`**. Les requêtes sont regroupées par identifiant ; l’ordre interne
est le tri de SHA-256 `[graine, query_id, document_id]`.

Une seule réponse apparaît à la fois. Les touches 0–3 enregistrent la note et
passent à la suivante. Les raccourcis sont inactifs dans les champs de saisie.
Le retour et la liste des requêtes permettent de revoir et modifier les notes.
Le commentaire est sauvegardé après 700 ms d’inactivité et avant navigation
ou export. Un brouillon sans note reste distinct d’un jugement zéro.

Le fichier unique conserve notes, brouillons, position et révision ensemble :
écriture temporaire dans le même dossier en mode 0600, `fsync`, `os.replace`,
puis synchronisation du dossier. Aucune confirmation de succès n’est affichée
avant le retour de cette opération. Un échec bloque la navigation ; une
révision obsolète refuse les écritures concurrentes d’onglets. Le verrou CLI
interdit deux serveurs sur cette même session.

La reprise utilise exactement les mêmes paramètres et le même fichier.
Changer de graine, d’évaluateur ou de corpus est refusé. Un couple possède un
seul jugement courant ; la modification remplace sa note, sa justification et
sa date, sans doublon. L’historique complet des révisions n’est pas conservé.

## Export RAG-006

Le lien **Exporter les jugements JSON** sauvegarde d’abord le commentaire en
cours puis télécharge uniquement les couples notés. La liste contient :
`query_id`, `document_id`, `grade` (entier 0–3), `justification` facultative,
`evaluator`, `judged_at` avec fuseau et `version`.

Enregistrer dans `evaluation/local/rag010/judgments.json` puis utiliser
`cahier-rag-eval score`, comme détaillé dans le README. Les identifiants
BIGINT des documents restent des chaînes décimales à la frontière JSON.
Le test d’export réutilise le validateur RAG-006, pas une copie du contrat.
Aucune métrique ni note de pertinence n’est calculée automatiquement ici.

## Confidentialité et indépendance

Aucun moteur, rang, score ou indicateur de document aléatoire n’est transmis
à l’interface. Ces données restent dans les fichiers RAG-009 d’origine.
Les informations affichées sont uniquement le texte, le contexte et la
progression de la session.

Les lectures utilisent exclusivement la base RAG. La contribution parente
correspond aux unités déjà stockées, sans requête au corpus source ni profil
d’auteur. L’application impose un plafond de 500 unités pour cette consultation.
Elle peut donc être incomplète : cette limite est affichée et documentée.

Hôte exact, client loopback, contrôle d’origine et Fetch Metadata, jeton de
session pour les écritures, CSP, absence de cache et refus d’intégration dans
une frame protègent les routes locales. Pas de ressources distantes, de proxy,
de journal HTTP, de texte HTML interprété ni d’API externe. Les erreurs SQL et
les erreurs disque sont remplacées par des messages génériques.

## Validations

- Suite pytest complète sur les bases dédiées `cahier_doleances_test` et
  `cahier_rag_test` : **273 tests réussis**, dont **54 intégrations PostgreSQL**.
- Ruff : vérification et formatage conformes ; `uv lock --check` conforme.
- Chromium : parcours complet sur données synthétiques, notation clavier,
  absence d’interférence dans le commentaire, retour, modification, contexte
  parent, reprise après rechargement, export immédiat d’un commentaire et
  conservation du texte après erreur de sauvegarde simulée. Aucune erreur JS.
- Wheel et distribution source construits ; présence des trois ressources web
  vérifiée dans le wheel. Point d’entrée CLI et aide vérifiés.
- Pool réel : 400 couples, 20 requêtes, 20 couples par requête ; **236 documents
  distincts relus**, empreintes conformes, aucune connexion restante dans le pool.
  Une consultation de contribution parente a également réussi en lecture seule.
- **26 fichiers historiques RAG-008/007 et 5 modules gelés RAG-009** : empreintes
  inchangées. Le pool RAG-009 correspond toujours à l’empreinte de son manifeste.
- Aucun jugement réel créé, aucun texte personnel reproduit dans ce rapport.
  Toutes les modifications sont dans `rag/`. Aucun commit, push ni déploiement.

## Limites

- Un seul évaluateur et un seul serveur de session ; la machine locale et les
  extensions du navigateur restent dans le périmètre de confiance.
- Une fermeture forcée peut perdre les frappes depuis la dernière sauvegarde
  confirmée. Le navigateur avertit avant fermeture normale si une saisie ou une
  sauvegarde est en cours. Copier le fichier de session pour une sauvegarde
  indépendante reste utile.
- Un résultat ambigu d’erreur disque après remplacement mais avant `fsync` du
  dossier est signalé comme un échec ; la reprise doit vérifier l’état sur disque.
- Les contributions parentes sont limitées au stockage expérimental existant.
- Les tests HTTP émettent un avertissement de dépréciation de Starlette sur
  l’utilisation de `httpx`. Ils passent ; aucune dépendance supplémentaire
  `httpx2` n’a été introduite pour masquer cet avertissement.
- Le statut « développement non commencé » de `docs/plan-rag.md` est obsolète.
  Le code et les rapports RAG récents constituent la référence opérationnelle.
- Sans option `annotation`, les tests HTTP sont ignorés. La commande documentée
  active explicitement cette option pour tester l’interface.

Voir le [README](README.md#rag-010--annotation-humaine-locale) pour les commandes
complètes d’utilisation et d’export.
