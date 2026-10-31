"""Rapports d'expérience : résultats négatifs inclus, aucun changement des règles gelées."""

import json
import re

from qcommon import HERE, jlines, read, rows


def table(headers, rs):
    def c(x):
        return str(x).replace("|", " / ").replace("\n", " ")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(c(v) for v in r) + " |" for r in rs]
    )


def put(name, text):
    lines = []
    fenced = False
    for line in text.strip().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and not line.startswith(">"):
            line = re.sub(
                r"\b(et|dans|entièrement|également|alloué|réservé|de|par|environ|Environ|version|Python|Enforcer|entre|B|C|A|lot|sur|les|des|ces|aux|ont|produit|rend|dégrade|au|tome|fichiers|cas|notices)(?=\d)",
                r"\1 ",
                line,
            )
            line = re.sub(r"(\d+)[.](\d+)(?=\s*(?:s\b|GiB\b|MiB\b|h\b|Go\b))", r"\1,\2", line)
            line = re.sub(r"(\d)(?=(?:s\b|GiB\b|MiB\b|h\b|Go\b))", r"\1 ", line)
            line = (
                line.replace("net−1", "net −1")
                .replace("**4/36", "** 4/36")
                .replace("**C est", "** C est")
                .replace("**Non", "** Non")
                .replace("**C 2", "** C 2")
                .replace("**Sur validation", "** Sur validation")
                .replace("**Très insuffisamment", "** Très insuffisamment")
                .replace("**Environ", "** Environ")
                .replace("**Techniquement", "** Techniquement")
                .replace("**Périmètres", "** Périmètres")
            )
            for before, after in {
                "GiB.72": "GiB. 72",
                ",48 appels": ", 48 appels",
                ",48 de développement": ", 48 de développement",
                ",4 essais": ", 4 essais",
                ":120 réponses": ": 120 réponses",
                ":36 feuilles": ": 36 feuilles",
                ":25 caractères": ": 25 caractères",
                ":25 réponses": ": 25 réponses",
                "; une marge": "; une marge",
                ",15 pour": ", 15 pour",
                ",13 ont": ", 13 ont",
                ",30/36": ", 30/36",
                ".13 des": ". 13 des",
                ",13,08 GiB": ", 13,08 GiB",
                ",36 cas": ", 36 cas",
                ",100 notices": ", 100 notices",
                "registre1 305": "registre 1 305",
                "dépassant24 576": "dépassant 24 576",
                "éligible986": "éligible 986",
                "tomeI": "tome I",
                "ni36 observations": "ni 36 observations",
                ",21 références": ", 21 références",
                "malgré6": "malgré 6",
                "conservateur15": "conservateur 15",
                "netC+2": "net C +2",
                "donneC−1": "donne C −1",
                "donne≈": "donne ≈ ",
                "scans.36": "scans. 36",
                "déclare14,8": "déclare 14,8",
                "conservateur32 768": "conservateur 32 768",
                "mentionne40 960": "mentionne 40 960",
                "existante32 768": "existante 32 768",
                "avec24 576": "avec 24 576",
                "checkpoint0.6B": "checkpoint 0.6B",
                "ni8B": "ni 8B",
                "durable3.11.17": "durable 3.11.17",
                "5090,32 607": "5090, 32 607",
                "capacité12.0": "capacité 12.0",
                "batch1": "batch 1",
                "PyTorch72%": "PyTorch 72 %",
                "consomme540,86": "consomme 540,86",
                "9,01min": "9,01 min",
                "À18:45:14": "À 18:45:14",
                "compactés,500": "compactés, 500",
            }.items():
                line = line.replace(before, after)
        lines.append(line)
    (HERE / name).write_text("\n".join(lines) + "\n")


def main():
    metrics = read(HERE / "data/metrics.json")
    v = metrics["validation"]["methods"]
    d = metrics["development"]["methods"]
    env = read(HERE / "data/environment.json")
    checks = read(HERE / "data/checks.json")
    windows = {w["id"]: w for w in rows(HERE / "data/windows.jsonl")}
    refs = {
        r["window_id"]: r
        for split in ["development", "validation"]
        for r in rows(HERE / f"data/reference-{split}.jsonl")
    }
    outs = {
        (r["window_id"], r["method"]): r
        for split in ["development", "validation"]
        for r in rows(HERE / f"data/{split}-outputs.jsonl")
    }
    comp = {(r["window_id"], r["method"]): r for r in rows(HERE / "data/comparison.jsonl")}
    main_table = table(
        [
            "Méthode",
            "Bornes exactes /36",
            "Débuts faux",
            "Fins fausses",
            "Corrige A",
            "Dégrade A correct",
            "Invalide",
        ],
        [
            [
                m,
                v[m]["exact"],
                v[m]["wrong_starts"],
                v[m]["wrong_ends"],
                v[m].get("corrected_initially_wrong", "—"),
                v[m].get("new_wrong_proposals_on_initially_correct", "—"),
                v[m]["invalid"],
            ]
            for m in ["A", "B", "C"]
        ],
    )
    put(
        "README.md",
        f"""
# Qwen3-14B et frontières documentaires des cahiers de 1789

**L’expérience a réellement été exécutée sur le Qwen3-14B local. La recette testée n’améliore pas les frontières par rapport aux règles actuelles. Ne pas l’utiliser pour corriger automatiquement les 1 305 notices.**

24 cas de développement, dont les 15 erreurs connues, et36 nouvelles notices (six par tome) ont été préparés. La référence des 36 cas a été rédigée et figée avant leurs inférences Qwen. Codex a réalisé les contrôles : ce n’est pas une validation humaine indépendante. Le modèle était le 14B, jamais le 0.6B.

## Résultat de validation

{main_table}

A = registre/règles existants ; B = Qwen sans proposition A ; C = Qwen avec A, sur les mêmes fenêtres. Une paire de bornes est exacte seulement si son début **et** sa fin correspondent à la référence de blocs source. Les invalides restent au dénominateur. Une proposition A existe à Santeny mais ne contient que 25 caractères blancs ; elle n’est pas comptée comme une abstention.

L’hybride conserve les deux bornes A dans31/36 cas. Il ne répare complètement aucune des cinq erreurs A et introduit une fusion au début de Gray : **bilan net−1**, critère prioritaire non satisfait. Des corrections partielles existent, mais ne donnent pas des parents fiables. Sur les 15 erreurs connues de développement, C en corrige entièrement2, B 1 ; deux des 15 ne disposent pas d’une référence complète unique dans ce contexte, leurs résultats restent non certifiés.

Aucune abstention structurée dans la campagne finale, et aucun `uncertain=true` sur les 36 nouvelles notices, malgré les erreurs. C présente également25/36 sorties dont au moins un identifiant de signature est extérieur à ses propres bornes. Des identifiants réels et un JSON valide ne constituent donc pas une validation documentaire.

## Coût et périmètre

Qwen3-14B révision `40c069824f4251a91eefaf281ebe4c544efd3e18`, NF4 double/BF16, Transformers existant, mode non-thinking, génération gloutonne, lot 1. Médiane validation : B{v["B"]["inference"]["median_seconds"]:.2f}s, C{v["C"]["inference"]["median_seconds"]:.2f}s par requête ; pic PyTorch alloué{v["C"]["inference"]["max_peak_allocated_gib"]:.2f}GiB, réservé13,08 GiB.72 appels de validation,48 de développement,4 essais initiaux conservés à part. Le GPU a été libéré à la fin.

**Aucun fichier applicatif, audit antérieur, source Stanford, index, embedding ou base n’a été modifié.** Aucun poids ni paquet téléchargé, aucun serveur déployé, aucune correction OCR. Les empreintes de{checks["previous_files_unchanged"]} fichiers antérieurs et sources de code réutilisées sont conservées et vérifiées.

## Livrables et recommandation

- [ENVIRONMENT.md](ENVIRONMENT.md) : poids, GPU, réutilisation du Python et backend.
- [PROTOCOL.md](PROTOCOL.md) : fenêtres, versions, référence et commandes.
- [EVALUATION.md](EVALUATION.md) : compteurs, coûts et limites.
- [CASES.md](CASES.md) : gains, erreurs, extraits réels et références.
- `data/*-outputs.jsonl` :120 réponses finales brutes, décisions et ressources.
- `data/reference-validation.jsonl` et `reference_decisions.json` : référence exploratoire figée.
- `data/comparison.jsonl`, `metrics.json`, `freeze.json`, `checks.json` : résultats et contrôles.

Conserver la méthode Persée–Stanford avec contrôles structurels et revue documentaire. **Ni le mode autonome, ni le vérificateur C ne justifient une généralisation.** Une éventuelle nouvelle expérience devrait être limitée, préenregistrée, séparer les deux frontières et tester la représentation des IDs et le mode de raisonnement, sur d’autres notices. Pas de nouveau modèle ni de traitement des 1 305 notices lancé ici. Les performances ne prouvent pas une incapacité générale de Qwen3 : elles concernent précisément cette recette NF4, ces instructions, ce format et ces fenêtres.

## Réponses aux neuf questions

1. **Reconnaissance correcte ?**4/36 bornes exactes sans A,30/36 avec A ; les règles en ont31/36. Beaucoup de justifications ne décrivent pas correctement les blocs sélectionnés.
2. **Mieux que les règles ?**Non sur le nouveau lot ; C perd une frontière correcte sans correction complète d’une erreur initiale.
3. **Autonome ou vérificateur ?**C est bien moins mauvais que B et recopie souvent A, mais son utilité ajoutée n’est pas démontrée sur validation.
4. **Erreurs connues corrigées ?**C 2/15 : Châtellerault clergé et Digne tiers. B 1/15.13 des 15 ont une référence de paire exacte ; deux restent hors contexte/portée incertaine. Pas de certification artificielle des autres.
5. **Nouvelles erreurs ?**Sur validation, C dégrade1 des 31 paires A exactes ; B produit26 nouvelles propositions fausses et rend1 autre cas A correct inutilisable par sortie invalide.
6. **Incertitudes reconnues ?**Très insuffisamment : aucun signal sur validation ; une incertitude C sur développement, aucune abstention structurée. Les références difficiles d’Artois, Riez et Castelnaudary ne suscitent pas l’abstention attendue.
7. **Coût local ?**Environ7–8 s par appel pour ces contextes,13,08 GiB de mémoire réservée au pic d’inférence et environ 16–17 s de chargement GPU par session, hors vérification CPU des empreintes.
8. **Passage aux 1 305 ?**Techniquement envisageable à cette taille de fenêtres, mais sans intérêt documentaire démontré. Projection arithmétique C ≈{v["C"]["inference"]["seconds_projection_1305_at_observed_median"] / 3600:.2f}h pour une passe similaire, hors revue et variation de contextes ; pas une mesure à cette échelle, aucune campagne massive autorisée ou lancée.
9. **Vérification humaine ?**Périmètres de dossiers, annexes, signatures/certifications, titres internes et homonymes, conflits entre ordres, sources intercalées, absences et toute divergence LLM/règles. Les frontières candidates ne deviennent jamais une certification historique.
""",
    )
    put(
        "ENVIRONMENT.md",
        f"""
# Installation locale et ressources

## Modèle effectivement utilisé

`rag/models/judges/qwen3-14b/40c069824f4251a91eefaf281ebe4c544efd3e18/` : huit shards Safetensors, index, configuration, tokenizer, licence Apache-2.0 et manifeste. Les poids originaux sont BF16, environ 28 Go sur disque ; la quantification n’est pas un autre checkpoint : **NF4 quatre bits, double quantification au chargement, calcul BF16**. Manifeste vérifié par `cahier_rag.judges.models.verify` avant chaque session, hash `d3fde2ccf3d22b339b8e586f488fecbc6b5b3648b4f4073f62e20fa30e09b642`.

Le registre existant déclare14,8 milliards de paramètres, huit shards et un budget conservateur32 768 tokens. La configuration locale mentionne40 960 positions ; le protocole garde la limite existante32 768, avec24 576 tokens d’entrée et512 de sortie. Aucun checkpoint0.6B ni8B chargé.

## Backend réutilisé

Le chargeur est `rag/src/cahier_rag/judges/backend.py` : `TransformersJudge`, `device_map={{"":0}}`, SDPA, `local_files_only=True`, `trust_remote_code=False`, aucun repli CPU. Il était déjà utilisé pour les juges et la génération locale décrits dans `rag/docs/rapport-rag-016.md` et les outils de génération contrainte.

L’adaptateur expérimental `constrained.py` réutilise ce chargeur, l’intégration Transformers de **LM Format Enforcer 0.11.3** et `safe_token_ids` déjà présent dans `generation/constrained/backend.py`. Seul le schéma est propre à cette tâche, avec les IDs visibles comme énumérations. Il ne contient aucune référence correcte ni information issue des annotations. XGrammar est installé mais non utilisé. Aucun fichier `rag/` modifié.

## Python existant, sans réinstallation

Les liens `rag/.venv/bin/python` et `rag/.cache/judges-venv/bin/python` pointent vers `/tmp/rag010-python/...`, désormais absent. Leurs packages restent disponibles. `bootstrap.py` utilise le CPython durable3.11.17 appelé par `.venv/bin/python`, ajoute en lecture les packages déjà installés dans `rag/.cache/judges-venv/lib/python3.11/site-packages` et `rag/src`. **Aucun lien, environnement ou paquet existant n’a été réparé/modifié.** La préparation documentaire utilise `/usr/bin/python3` et le lxml déjà disponible.

{table(["Dépendance", "Version mesurée"], list(env["libraries"].items()) + [["lm-format-enforcer", "0.11.3"], ["Python inférence", "3.11.17"], ["Driver NVIDIA", "595.99.02"], ["CUDA du driver", "13.2"], ["CUDA du PyTorch", "12.8"]])}

## GPU et précautions effectives

RTX 5090,32 607 MiB détectés. Environ234–277 MiB occupés par le bureau au départ, aucun processus de calcul GPU. Le bac à sable ne donnait pas accès aux périphériques ; les contrôles puis l’inférence ont donc été autorisés hors bac à sable. CUDA a été confirmé disponible, capacité12.0 ; ce n’était pas une panne du driver.

Les appels sont séquentiels, batch1, quatre threads CPU, plafond PyTorch72% de la mémoire GPU. Avant le chargement et chaque appel, le script vérifie les autres processus de calcul et s’arrête s’il en apparaît. Pas de service permanent, pas de modification de puissance/fréquences ni arrêt d’un service. `close()` et la sortie du processus libèrent le modèle.

La validation consomme540,86 s de génération cumulée pour les deux méthodes, environ 9,01min, plus chargement. Pic alloué12,58 GiB, pic réservé13,08 GiB mesurés par PyTorch par appel. Ce ne sont pas des mesures exhaustives de la mémoire globale NVML pendant tout le chargement. À18:45:14 en fin d’expérience, `nvidia-smi` ne montre plus que GNOME et179 MiB de mémoire occupée. Le relevé est conservé dans `data/gpu-after.json`.

Le réseau Hugging Face est désactivé (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`), la télémétrie également. Aucun modèle téléchargé. Un avertissement bitsandbytes sur des kernels CPU absents a été observé pendant l’inventaire ; l’inférence GPU s’est exécutée sans installation supplémentaire ni repli CPU.
""",
    )
    put(
        "PROTOCOL.md",
        """
# Protocole expérimental

## Données, fenêtres et intégrité

Réutilisation en lecture du registre1 305 notices, du détecteur V2 et des helpers de provenance du pilote. Stanford : six XML locaux, révision `926fd3cd986a3c3d411e93d1845fff6475cb2602`, empreintes vérifiées. Aucun nouveau corpus Persée, texte ni métadonnée collecté.

Les fenêtres sont établies **par les pages initiale et finale Persée**, avec six blocs complets autour de ces pages, sans utiliser la fin A pour choisir le contexte. Le milieu absent est déclaré avec ses positions et le nombre de blocs omis. Ce sont des fenêtres de frontière, pas des documents intégraux. Chaque bloc conserve texte exact, ID global stable, XPath, positions Unicode, tag, page et provenance de cette page ; les changements `pb` sont transmis. Aucun paragraphe trop long n’est coupé silencieusement. Le modèle refuse un contexte dépassant24 576 tokens ; aucun dépassement dans la campagne. Les XML entiers sont parsés localement pour les positions, jamais chargés dans le contexte du modèle.

`vN-bXXXXXX` désigne un bloc `head`, `p` ou `note`, ou un marqueur `pb`. Les ID incluent des balises de titre et des paragraphes, pas uniquement des articles. Le texte transmis est le flux exact reconstruit par `Source`, sans correction OCR ni normalisation ; les offsets sont des points de code Unicode dans `itertext`, pas des octets XML. Un saut de page n’est jamais une borne autorisée. Les relations parent–passage/index applicatif restent inchangées.

B reçoit titre, notice, voisins connus et blocs ; **pas la proposition A, ses XPath, scores ou annotations**. C reçoit exactement les mêmes données, plus la proposition A et la visibilité de ses extrémités. Le gabarit est celui du tokenizer Qwen, `enable_thinking=False`. L’égalité des deux contextes hors proposition A est contrôlée automatiquement.

## Développement et gel

24 cas : les 15 erreurs du registre, six contrôles conformes, Chaumont Vexin fausse absence, Artois colonnes intercalées et Eguilles/mémoire Goullin. Ces cas ne sont pas une validation indépendante.

Premiers essais non contraints sur deux cas, soit quatre réponses : trois sorties échouent au contrat d’identifiants. Elles sont conservées dans `pilot-v1-*`, avec le texte du prompt initial. Les instructions sont précisées puis le décodage contraint déjà installé est utilisé. Quatre réponses de ce second essai sont examinées ; la recette finale est conservée pour tout le lot. Aucun nouveau réglage après les lectures de validation. Le prompt n’a pas été optimisé exhaustivement sur les 24 cas : cela limite la conclusion à la recette testée.

`data/freeze.json` enregistre les octets des instructions, adaptateur, runner, préparation, sources de fenêtres et sélection. Une variable locale de lecture a été renommée avant toute lecture des nouvelles références ; ce nettoyage et le gel initial sont archivés. Les instructions, paramètres et sélection n’ont pas changé. Les fichiers de référence ont ensuite été ajoutés au gel **avant toute inférence de validation**.

## Validation nouvelle

36 notices, six par tome, tirage par empreinte déterministe avec alternance de strates simples/complexes fondées sur les statuts existants. Cadre éligible986 notices. Exclusion des 72 anciens contrôles,100 notices du registre, sources/feuilles antérieurement examinées, zones continues et références documentaires des pilotes. L’emplacement réel des 36 débuts de référence a également été contrôlé contre ces exclusions :36 feuilles nouvelles. Aucun candidat difficile remplacé.

La strate « complexe » est un indicateur technique (priorité, ambiguïté ou titre probable), pas un décompte de dossiers réellement composites. Plusieurs cas sont voisins, notamment en tomeI : ce n’est pas un échantillon aléatoire représentatif des 1 305 notices, ni36 observations historiquement indépendantes.

Codex a examiné ouvertures, clôtures et transitions dans les sources, avec les outils `reference_view.py` et inspections ponctuelles. Le milieu omis n’est pas collationné, les fac-similés ne sont pas revérifiés. Les sorties de validation Qwen n’existaient pas encore à la fixation des références. Les anciennes études restent connues ; **ce n’est ni une validation humaine indépendante ni un test aveugle intégral**.

## Politique documentaire et score

La cible est le dossier de la notice : titre propre, corps, signatures, certifications, pièces préliminaires ou annexes explicitement liées et incluses dans son périmètre. Les documents possédant une notice voisine restent séparés. Un en-tête territorial commun ne détermine pas le début du seul cahier. Les notes gardent leur nature éditoriale ; les indications comme « suivent plusieurs signatures » restent conservées dans le dossier.

Une paire est exacte si les deux ID de premier/dernier bloc correspondent à la référence ; fin **inclusive**. L’espace seul autour d’une `div` est neutralisé par projection sur les blocs non vides. Aucun ajustement a posteriori d’un ID voisin n’est accepté. Les erreurs d’un seul titre ou d’une certification comptent aussi ; les exemples distinguent leur gravité des fusions de plusieurs textes.

Sur développement,21 références de paire exacte ; Castelnaudary a une extrémité nécessaire dans le milieu omis, Riez a une portée/début non certifiée dans ce contexte, Artois mélange des colonnes. Ces trois cas sont conservés pour l’abstention, pas transformés en succès ou erreurs d’exactitude inventées. Deux des 15 anciennes erreurs appartiennent à ces cas non tranchables ; les six contrôles conformes ne sont pas réévalués comme nouvelles preuves.

Les sorties sont vérifiées : JSON sans doublon de clés, IDs présents, absence de `pb` comme borne, ordre source, schéma et abstention cohérente. La grammaire impose les IDs visibles, pas leur sens. Les invalides sont conservées et ne reçoivent pas une frontière de substitution. Le score n’utilise jamais `uncertain` comme preuve de justesse.

## Reproduction

Les grands fichiers sont livrés en gzip sans perte ; `materialize.py` les restaure dans ce dossier après vérification des empreintes. Les poids et sources locales restent à leur emplacement existant, ignorés par Git.

```sh
/usr/bin/python3 1789/archives/1789-qwen-boundaries/materialize.py
/usr/bin/python3 1789/archives/1789-qwen-boundaries/evaluate.py
/usr/bin/python3 1789/archives/1789-qwen-boundaries/test_contract.py
/usr/bin/python3 1789/archives/1789-qwen-boundaries/checks.py
```

Pour réexécuter l’inférence, uniquement GPU libre et dans le même environnement autorisé :

```sh
.venv/bin/python 1789/archives/1789-qwen-boundaries/preflight.py
.venv/bin/python 1789/archives/1789-qwen-boundaries/run_local.py development
.venv/bin/python 1789/archives/1789-qwen-boundaries/run_local.py validation
```

Le runner utilise `bootstrap.py` et les packages judges existants. Il reprend par empreintes entrée/recette et n’écrase pas les sorties ; une sortie invalide n’est pas silencieusement remplacée. Ne pas le relancer pour simplement lire les résultats. Les deux commandes de préparation de référence sont destinées au protocole initial ; `build_references.py` refuse de reconstruire une référence de validation après génération de sorties. Les fenêtres et références fournies permettent de revoir l’expérience sans nouvelle inférence.
""",
    )
    detail = []
    for label, key in [
        ("Débuts incorrects", "wrong_starts"),
        ("Fins incorrectes", "wrong_ends"),
        ("Plages tronquées", "truncated"),
        ("Plages trop larges", "overwide"),
        ("Titre d’un voisin absorbé", "neighbour_title_absorbed"),
        ("Annexe mal attribuée (cas référencés)", "annex_misattributed"),
        ("Sorties invalides", "invalid"),
        ("Abstentions", "abstentions"),
        ("Incertitude déclarée", "reported_uncertain"),
        ("Signature hors des propres bornes", "signature_consistency_failures"),
    ]:
        detail.append([label] + [v[m][key] for m in ["A", "B", "C"]])
    put(
        "EVALUATION.md",
        f"""
# Résultats mesurés

## Validation,36 cas

{main_table}

{table(["Diagnostic", "A", "B", "C"], detail)}

Les compteurs ne sont pas additifs : une plage peut être tronquée d’un côté et trop large de l’autre. « Titre d’un voisin absorbé » exige un titre documentaire visible hors de la référence ; une marge géographique seule n’est pas assimilée à la fusion d’un cahier complet. L’unique plage A sans bloc textuel est Santeny :25 caractères blancs, données exactes dans `empty-baseline-case.json`. Ce défaut du générateur ne devient pas une abstention artificielle.

Le compteur de titres visibles n’est pas un décompte exhaustif des fusions : à Gray, l’en-tête du dossier précédent est hors fenêtre, mais sa fin est absorbée, ce que confirme la lecture des signatures et du titre propre de Gray.

A 31/36 (86,1%), B 4/36 (11,1%), C 30/36 (83,3%). B dégrade26 des 31 références A correctes et donne une sortie inutilisable supplémentaire ; C en dégrade1, sans corriger entièrement une erreur A. Le critère **corrections complètes > dégradations nouvelles** échoue sur validation pour les deux variantes.

C conserve exactement les deux bornes A dans31/36 cas. Ses cinq changements n’apportent aucune paire exacte supplémentaire : Gray devient trop large ; Amont noblesse reste trop court ; Santeny est presque localisé mais les deux titres de frontière sont décalés ; clergé Paris finit au bon endroit mais absorbe Wissous/Saint-Witz ; Châteauneuf inclut encore le titre du suivant. Le cas chapitre Paris/Saint-Paul conserve l’erreur A. Ne pas confondre cette fidélité à A avec une vérification réussie.

Sur les 3 cas de référence non unique/insuffisante de développement, aucune abstention structurée. C signale une seule incertitude sur un autre cas, Uzent, mais propose tout de même une plage trop large. Aucun signal d’incertitude sur validation malgré6 propositions C inexactes et31 propositions B inexactes. La confiance déclarée n’est pas calibrée ici.

Les contrôles de signatures sont purement positionnels :25 réponses C ont au moins un ID de signature extérieur à leurs propres limites,15 pour B. Ce n’est pas une mesure exhaustive de précision des rôles, mais une contradiction vérifiable avec le contrat demandé. Les annexes n’ont des références de rôle explicites que sur quelques contrôles (notamment Eguilles/Goullin inclus, Brives/Turenne et Uzerche/annexe exclus) ; aucun taux global de qualité des annexes n’est extrapolé.

## Développement

{table(["Méthode", "Exactes /21 tranchables", "Corrige une erreur A", "Dégrade un contrôle A conforme", "Réponses invalides"], [[k, d[k]["exact"], d[k].get("corrected_initially_wrong", "—"), d[k].get("new_wrong_proposals_on_initially_correct", "—"), d[k]["invalid"]] for k in ["A", "B", "C"]])}

C corrige complètement Châtellerault clergé et Digne tiers ; B ne corrige complètement qu’un cas. Sur les 15 erreurs initialement documentées,13 ont ici une référence complète tranchée ; Castelnaudary et Riez restent explicitement limités. Le dénominateur conservateur15 n’implique pas une vérité de référence exacte créée pour ces deux cas. Artois constitue un contrôle supplémentaire de source intercalée. Les références sont dans `reference-development.jsonl`, avec diagnostics et statuts.

Ce lot est volontairement difficile et connu : son gain netC+2 ne constitue pas une validation. Le nouveau lot donneC−1. Les paramètres n’ont pas été retouchés pour transformer ce résultat.

## Tous les documents ou seulement les suspects ?

Indicateur non appris : alerte structurelle A existante ou extrémité A non représentable dans la fenêtre. Sur les 36 nouveaux cas :

{table(["Sous-lot", "Effectif", "A exact", "B exact", "C exact"], [[name, group["A"]["cases"], group["A"]["exact"], group["B"]["exact"], group["C"]["exact"]] for name, group in metrics["validation"]["structural_alert_groups"].items()])}

Sur les 5 suspects, aucune amélioration d’exactitude ; sur les 31 sans alerte, C perd une paire. Ce petit sous-lot ne valide donc pas non plus une application automatique aux seuls suspects. Une aide de lecture peut être proposée à un documentaliste, mais n’est pas une décision fiable. Les alertes déterministes de plage vide, prochain titre et signatures extérieures doivent précéder tout recours LLM.

## Temps et mémoire

{table(["Mesure validation", "B", "C"], [["Appels", 36, 36], ["Entrée min–max tokens", f"{v['B']['inference']['input_tokens_min']}–{v['B']['inference']['input_tokens_max']}", f"{v['C']['inference']['input_tokens_min']}–{v['C']['inference']['input_tokens_max']}"], ["Temps cumulé (s)", round(v["B"]["inference"]["total_seconds"], 2), round(v["C"]["inference"]["total_seconds"], 2)], ["Médiane (s)", round(v["B"]["inference"]["median_seconds"], 2), round(v["C"]["inference"]["median_seconds"], 2)], ["p95 (s)", round(v["B"]["inference"]["p95_seconds"], 2), round(v["C"]["inference"]["p95_seconds"], 2)], ["Pic alloué PyTorch (GiB)", round(v["B"]["inference"]["max_peak_allocated_gib"], 2), round(v["C"]["inference"]["max_peak_allocated_gib"], 2)], ["Pic réservé PyTorch (GiB)", 13.08, 13.08]])}

Les temps incluent génération, construction éventuelle de grammaire et analyse de la réponse, hors chargement du modèle et contrôle préalable des poids. Première requête plus coûteuse ; reprise des quatre premiers essais contraints incluse dans les 24 cas de développement, pas comptée deux fois. Quatre essais non contraints sont archivés séparément. Paramètres de génération identiques pour B/C, lots de 1, aucun dépassement de contexte, aucun OOM, aucun repli vers un autre modèle.

Une extrapolation purement arithmétique de la médiane C donne≈2,67 h pour 1 305 fenêtres similaires, sans validation humaine, assemblage ni variation de longueur. Ce n’est pas une mesure de débit sur les 1 305 notices ni une recommandation de lancement.

## Limites et interprétation

- Un seul modèle/quantification/prompt final et mode non-thinking ; pas de comparaison BF16 intégral, autre backend ou raisonnement activé. Les IDs et la lecture des longs contextes peuvent être une cause importante des échecs.
- Fenêtres de pages extrêmes : milieu explicitement omis, voisins et notices parfois mal paginés. Sur développement, une véritable extrémité nécessaire n’est pas visible et une portée Riez est incertaine. Ce n’est pas une preuve d’incapacité sémantique générale.
- Contrôle Codex, avant sorties Qwen de validation, mais sans lecteur humain indépendant, sans collation complète des corps ni nouveaux scans.36 notices stratifiées, parfois voisines : pas d’estimation statistique globale.
- Exactitude stricte des deux ID : certains échecs sont un seul titre ou une certification omise ; d’autres fusionnent réellement plusieurs documents. Les deux sont montrés dans CASES. Un gain partiel n’autorise pas l’écriture de la nouvelle plage.
- La grammaire améliore la validité du format ; elle ne corrige ni l’ordre des IDs ni leur attribution documentaire. Le plafond de 240 caractères peut fermer une justification en milieu de mot ; les réponses brutes permettent de le voir. Aucune justification n’est utilisée comme preuve de justesse.

**Décision : ne pas remplacer les frontières A par ces propositions, ni lancer un contrôle LLM massif.** Une éventuelle prochaine campagne limitée devrait changer explicitement la représentation des deux limites et comparer le mode de raisonnement sur de nouvelles références indépendantes. Elle n’a pas été commencée.
""",
    )
    selected = [
        ("development-08", "C", "Correction complète du PV et du cahier de Châtellerault"),
        ("development-13", "C", "Correction complète de la fin de Digne"),
        ("validation-02", "B", "Réussite autonome à Exmes, sans gain sur A"),
        (
            "validation-06",
            "C",
            "Dégradation nouvelle à Gray : absorption de la fin du dossier précédent",
        ),
        ("validation-04", "C", "Amélioration partielle, certification de noblesse Amont omise"),
        ("validation-17", "C", "Brives : bornes exactes mais annexe Turenne attribuée à tort"),
        ("validation-32", "C", "Fin proche mais titre du cahier Châteauneuf-le-Rouge absorbé"),
        (
            "validation-26",
            "C",
            "Santeny : A vide, Qwen localise le texte mais décale ses titres de borne",
        ),
        (
            "validation-28",
            "C",
            "Clergé Paris : fin réparée mais début fusionné avec deux autres paroisses",
        ),
        (
            "development-23",
            "C",
            "Artois : des colonnes intercalées demandent une abstention, pas une plage certifiée",
        ),
        (
            "development-24",
            "C",
            "Eguilles : périmètre du mémoire Goullin à distinguer du seul corps du cahier",
        ),
    ]
    gallery = []
    sections = []
    for key, method, title in selected:
        w = windows[key]
        r = refs[key]
        out = outs[(key, method)]
        p = out.get("parsed")
        blockmap = {b["id"]: b for b in w["blocks"]}
        ids = [r.get("start_id"), r.get("end_id")] + (
            [p.get("start_id"), p.get("end_id")] if p else []
        )
        for annexe in r.get("annexes", []) + (p or {}).get("annexes", []):
            ids.extend([annexe.get("start_id"), annexe.get("end_id")])
        excerpt = []
        for i in dict.fromkeys(x for x in ids if x):
            if i not in blockmap:
                continue
            b = blockmap[i]
            excerpt.append(
                dict(
                    id=i,
                    xpath=b["xpath"],
                    start=b["start"],
                    end=b["end"],
                    text_exact=b["text"],
                    tag=b["tag"],
                    page=b["page"],
                )
            )
        item = dict(
            window_id=key,
            method=method,
            title=title,
            document=w["title"],
            persee_id=w["persee_id"],
            source=w["source"],
            reference=r,
            baseline=w["baseline"],
            model=out,
            assessment=comp[(key, method)],
            source_blocks=excerpt,
        )
        gallery.append(item)
        endlabel = f"{r.get('start_id')} → {r.get('end_id')} ({r['status']})"
        model_label = f"{(p or {}).get('start_id')} → {(p or {}).get('end_id')}"
        sections.append(
            f"## {title}\n\n{w['title']} — [notice Persée](https://www.persee.fr/doc/{w['persee_id']}), tome{w['volume']}, pages{w['pages']}. [XML Stanford figé]({w['source']['source_url']}) ; [numérisation]({w['source']['scan_url']}).\n\nRéférence : `{endlabel}`. Modèle{method} : `{model_label}`. Exactitude : **{comp[(key, method)]['exact']}**. Diagnostic de référence : {r['reason']}\n\nSortie Qwen (JSON mis en forme ; réponse brute conservée dans les données) :\n\n```json\n{json.dumps(p if p is not None else out['raw'], ensure_ascii=False, indent=2)}\n```\n\n"
            + "\n\n".join(
                f"`{b['id']}` — `{b['xpath']}`, p.{b['page']}, source[{b['start']}:{b['end']}]. Extrait d’affichage (blancs compactés,500 premiers caractères maximum ; texte exact complet dans JSONL) :\n\n> {' '.join(b['text_exact'].split())[:500]}"
                for b in excerpt
            )
        )
    jlines(HERE / "data/gallery.jsonl", gallery)
    put(
        "CASES.md",
        "# Exemples réels : corrections et erreurs\n\nLes références et positions sont celles des sources Stanford figées. Les textes complets des blocs de ces exemples sont dans `data/gallery.jsonl`; les fenêtres exactes permettent la vérification. Aucun texte historique n’est corrigé. Les annotations sont exploratoires Codex.\n\n"
        + "\n\n".join(sections),
    )
    print("Wrote five reports and gallery")


if __name__ == "__main__":
    main()
