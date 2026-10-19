# RAG-022 — Génération documentaire locale

Le module `cahier_rag.generation` produit des réponses françaises structurées depuis les seuls contextes gelés RAG-021. Aucun moteur, reranker ou assemblage n'est relancé. Cette première version utilise un échange conversationnel système/utilisateur par requête ; elle ne gère pas encore un historique de dialogue ou des relances avec nouvelle recherche.

## Modèle et recette

- Qwen/Qwen3-14B, révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, Apache-2.0, snapshot RAG-016 existant sous `models/judges/`.
- Le README officiel local confirme instruction multilingue, dialogue et commutation thinking/non-thinking. La fenêtre conservatrice du registre est 32 768 tokens.
- Chargeur NF4 double quantification, calcul BF16, SDPA, CUDA 12.8, RTX 5090. Même pile déjà installée dans `.cache/judges-venv`, sans modifier les dépendances.
- `enable_thinking=False` dans le vrai gabarit conversationnel, seed 42, génération gloutonne (`do_sample=False`, un faisceau), batch 1, maximum 2 048 tokens générés. Pas de troncature d'entrée.
- Le prompt complet, gabarit inclus, est recompté avec le tokenizer réel de Qwen3-14B. Plafond d'entrée 24 576 ; entrée + sortie réservée ≤32 768. La recette, les versions et le hash du gabarit sont enregistrés.

Le backend réutilise le code de chargement/inférence local de RAG-016, pas ses jugements ou ses caches. Aucun téléchargement, API, service permanent ou exposition réseau. Imports lourds paresseux ; les contrats, vérifications et tests synthétiques fonctionnent sans PyTorch.

## Entrées documentaires

La préparation vérifie les artefacts RAG-021 et leurs sources, sans reconstruire les contextes. Elle conserve exactement les vingt contextes **H1+R2 / S2-P1-8192** : H1 historique, Qwen3-Reranker-4B, diversité par contribution, question et réponse.

La nouvelle présentation **`compact-fr-v1`** attribue `S01`, `S02`, etc. dans l'ordre des sources RAG-021. Ces références sont uniques **dans une réponse**, pas des identifiants globaux : leur résolution exige le plan, la requête et la table locale de citations. Chaque entrée du prompt contient seulement : référence, question, réponse/extrait exact, questionnaire, indicateur `incomplete`.

La table de correspondance hors prompt conserve la référence longue RAG-021 et **toute** la source originale : identifiants BIGINT en chaînes, provenance, rang, méthode, empreintes, positions et plages omises. Aucun SHA-256 technique, titre redondant ou identifiant de base n'est ajouté au prompt. Le texte citoyen lui-même reste inchangé.

L'interface compacte accepte une liste de passages : chaque référence courte résout une source/extrait distinct. Elle pourra donc représenter plusieurs intervalles d'une même réponse sans les fusionner. Le présent ticket conserve les passages RAG-021 existants, généralement le premier segment des réponses longues. Aucun moteur de passages n'est introduit. `incomplete=true` signale au modèle que sa synthèse doit se limiter à cet extrait.

## Prompt et contrat de sortie

Le prompt initial **`generation-fr-v1`** est versionné dans `generation/contracts.py` (`SYSTEM`), empreinté dans le plan et copié dans les rapports locaux. Il impose une synthèse documentaire, des références pour chaque affirmation substantielle, la distinction opinion/fait rapporté/synthèse, les limites du sous-ensemble sélectionné, la restitution des divergences effectivement présentes et le signalement des lacunes. Les données des sources ne sont jamais des instructions.

Sortie JSON stricte :

```json
{
  "blocks": [
    {
      "kind": "reported_opinion",
      "text": "Une réponse consultée propose un meilleur accès aux services.",
      "references": ["S01"],
      "quotes": []
    }
  ],
  "limits": ["Sous-ensemble sélectionné, non représentatif."],
  "insufficient_sources": false
}
```

Exemple synthétique de structure, pas un jugement ou texte du corpus. Types de bloc autorisés : `synthesis`, `reported_opinion`, `reported_claim`, `limitation`. Un bloc autre que `limitation` doit avoir au moins une référence. Les références sont uniques et connues. `limits` ne doit contenir que des limites documentaires.

Une citation littérale est exclusivement déclarée dans `quotes` : `{"reference":"S01","text":"passage exact"}`. La chaîne doit être une sous-chaîne exacte du passage fourni, sans correction ou ellipse. Le texte des blocs n'accepte pas les guillemets doubles/français ni les références en crochets : les citations sont structurées séparément. `answer_text` construit ensuite l'affichage en ajoutant les marqueurs et les citations déclarées, sans modifier leurs chaînes.

Le validateur refuse JSON invalide, clés dupliquées, schéma incorrect, référence inconnue/dupliquée, bloc substantiel sans référence et citation inexacte. Il n'extrait pas un JSON d'un Markdown et ne corrige aucune sortie. Les sorties brutes invalides restent auditées.

**Une référence résolue ne prouve pas que la source étaye l'affirmation.** Les paraphrases trompeuses, usages abusifs de `limitation`, citations non déclarées sous des formes non détectées, contradictions omises ou généralisations indirectes ne sont pas garantis détectables. Une sortie structurellement valide n'est pas factuellement ou sémantiquement vérifiée.

## Révision explicite après le pilote

Le pilote v1 a échoué sur ses trois sorties : un dépassement du nombre de citations et deux JSON invalides, dont une sortie arrivée à la limite de 2 048 tokens. Une inspection qualitative a aussi identifié une opposition citée comme soutien. Les sorties et le prompt v1 restent intacts dans `evaluation/local/rag022/plan`, son cache indépendant et ses rapports ; une copie des fichiers de code exacts est conservée dans `plan/code` et vérifiée contre les hashes du plan.

La recette **`generation-fr-v2`** conserve modèle, contexte et paramètres d'inférence, mais impose 2 à 4 blocs très courts, 220 mots au total, 1 à 3 références utiles par bloc et `quotes: []` pour cette expérience de paraphrase. Elle explicite le traitement des refus/réserves. Les éventuelles citations littérales restent validables par le contrat et testées synthétiquement ; une campagne qui n'en produit aucune ne valide pas leur qualité en situation réelle.

Le nouveau plan/cache est sous `evaluation/local/rag022/v2/`, sans remplacement des essais v1. Les commandes ci-dessous ciblent cette v2 par défaut. Le prompt v1 est toujours disponible via `resolve_prompt("generation-fr-v1")` ; le backend actif est v2 et ne peut pas reprendre silencieusement une recette v1.

## Plan, sauvegarde et reprise

`prepare` relit et valide les contextes gelés, puis écrit un nouveau plan : entrées compactes, tables complètes, prompts exacts, token counts, empreintes des sources, du modèle et du code. Une modification de recette ou d'entrée refuse la reprise du plan.

Le cache indépendant est `evaluation/local/rag022/v2/generation.sqlite3`, tables `generation_recipes`, `generation_attempts`, `generation_checkpoints`. Chaque tentative et son checkpoint sont écrits dans une même transaction. Les sorties valides ne sont jamais remplacées ; les sorties invalides sont conservées et ne sont pas régénérées silencieusement. Après interruption, les résultats déjà enregistrés sont réutilisés. Un calcul interrompu avant commit sera recalculé.

Une erreur locale/GPU est enregistrée et arrête la campagne. `--retry-errors` autorise explicitement une nouvelle tentative des seules erreurs d'inférence, en conservant l'ancienne tentative. Il ne répare pas un JSON invalide. Une modification importante du prompt impose une nouvelle version et un nouveau plan, pas le remplacement de v1.

Le pilote figé comporte trois intentions : `democratie-01` (thématique), `fiscalite-02` (propositions), `services_publics-06` (difficile). La campagne exige leurs trois sorties techniquement valides et doit être précédée de leur inspection qualitative. Les trois générations pilotes sont réutilisées pour la campagne de vingt : aucune inférence en double.

Depuis `rag/` :

```sh
.cache/judges-venv/bin/python -m cahier_rag.generation.cli prepare
.cache/judges-venv/bin/python -m cahier_rag.generation.cli run --stage pilot
.venv/bin/python -m cahier_rag.generation.cli report
# Examiner les trois réponses et leurs sources avant de poursuivre.
.cache/judges-venv/bin/python -m cahier_rag.generation.cli run --stage development
.venv/bin/python -m cahier_rag.generation.cli report
```

Pour suivre :

```sh
watch -n 5 cat evaluation/local/rag022/v2/plan/development-progress.json
```

`--stop-after N` permet un arrêt à un checkpoint (ex. test de reprise). `--plan CHEMIN` avant la sous-commande choisit un nouveau plan sans écraser l'existant. Conserver tous les chemins sous `evaluation/local/rag022/`, ignoré par Git.

## Audit et évaluation

Les rapports sont écrits dans `evaluation/local/rag022/v2/reports/<hash>/` (v1 reste sous `rag022/reports/`), sans écraser les précédents :

- `answers.json` : sorties brutes/structurées, réponse affichable, table de citations et informations techniques.
- `summary.json` : validité, références résolues, citations déclarées exactes, sources utilisées, insuffisances, extraits incomplets utilisés, tokens et latences par requête.
- `inspection-template.json` : grille non remplie, évaluateur non assigné, sans notes automatiques.
- `generation-fr-v2.txt` : prompt système exact ; la v1 est conservée séparément.

La grille comporte réponse à l'intention, fidélité, attribution, synthèse, désaccords, absence de généralisation, lisibilité. Les observations éventuelles de Codex doivent être identifiées comme une inspection qualitative assistée, non humaine, non notée et non exhaustive. Aucun juge RAG-017/018 ni jugement humain n'est utilisé pour régler cette recette.

Les températures et graine sont explicites, mais un recalcul sur autre matériel/version/quantification n'est pas promis identique bit à bit. Le cache validé et les exports sont reproductibles à partir des mêmes tentatives. Le temps d'inférence inclut préremplissage, décodage et contrôle de sortie ; chargement et précontrôle sont séparés.

```sh
uv run --locked --no-sync pytest
uv run --locked --no-sync ruff check .
uv lock --check
```

Résultats réels et limites : [rapport-rag-022.md](rapport-rag-022.md). Aucun lien avec le site public, aucun déploiement Wallace, aucun commit ou push automatique.
