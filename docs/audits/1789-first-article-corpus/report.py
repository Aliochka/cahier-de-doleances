"""Reports from actual exports and integrity checks; no invented human decisions."""

import json

from build import HERE, load, rows


def main():
    q = load(HERE / "data/quality.json")
    units = sum([rows(HERE / f"data/units-{k}.jsonl.gz") for k in "ABC"], [])
    parents = rows(HERE / "data/parents.jsonl.gz")
    examples = []
    for status in "ABC":
        u = next(u for u in units if u["status"] == status and u["text"].strip())
        examples.append(
            {
                k: u[k]
                for k in [
                    "id",
                    "parent_id",
                    "type",
                    "status",
                    "start",
                    "end",
                    "parent_start",
                    "parent_end",
                    "text_spans",
                    "xml_blocks",
                    "pages",
                    "legacy_unit_ids",
                ]
            }
        )
        examples[-1]["text_excerpt_exact_prefix"] = u["text"][:800]
        examples[-1]["excerpt_only"] = True
    (HERE / "data/small-examples.json").write_text(
        json.dumps(examples, ensure_ascii=False, indent=2) + "\n"
    )
    table = ["| Tome | Cahiers |", "| --- | ---: |"] + [
        f"| {v} | {n} |" for v, n in q["by_volume"].items()
    ]
    selected = ["| Tome | Dossier | Articles A/B | Origine |", "| --- | --- | ---: | --- |"]
    for p in parents:
        a = sum(
            u["parent_id"] == p["id"] and u["type"] == "article" and u["status"] == "A"
            for u in units
        )
        b = sum(
            u["parent_id"] == p["id"] and u["type"] == "article" and u["status"] == "B"
            for u in units
        )
        selected.append(
            f"| {p['volume']} | {p['metadata']['title']} | {a}/{b} | {p['boundary_origin']} |"
        )
    human = q["human_activity"]
    human_summary = f"{human['examined_documents']} dossiers examinés dans l’outil : validés humainement : {human['human_validated']} ; incertains : {human['uncertain']} ; bloqués : {human['blocked']}. La validation des parents ne certifie pas chaque article."
    withheld_rows = load(HERE / "data/withheld.json")
    selection = {r["document_id"]: r for r in load(HERE / "data/selection.json")}
    withheld_text = (
        "; ".join(
            selection[r["document_id"]]["title"] + " (" + r["status"] + ")" for r in withheld_rows
        )
        or "Aucun"
    )
    ferrieres = next((p for p in parents if p["persee_id"].endswith("_4_1_2175")), None)
    ferrieres_text = (
        "Ferrières : correction humaine intégrée jusqu’aux signatures, bloc v4-b013967 ; Commerce et Justices seigneuriales sont conservés."
        if ferrieres
        and ferrieres["boundary_status"] == "human_validated"
        and ferrieres["end"] == 5034046
        else "Ferrières : vérifier la fin trop courte héritée du registre ; voir QUALITY.md."
    )
    table_text = "\n".join(table)
    selected_text = "\n".join(selected)
    (HERE / "README.md").write_text(f"""# Premier corpus d’articles de 1789 et vérification locale

**L’outil est utilisable et le corpus est produit : {len(parents)} parents, {q["articles_total"]} articles, {q["units_by_type"]["section"]} sections et {q["units_by_type"]["technical_passage"]} passages techniques. {human_summary}**

Lancer l’outil depuis la racine du dépôt :

```sh
/usr/bin/python3 docs/tools/1789-document-review/server.py
```

Ouvrir http://127.0.0.1:1789. [Mode d’emploi](../../tools/1789-document-review/README.md).

## Constitution du lot

24 dossiers du pilote et six références documentaires corrigées ou complexes des audits ultérieurs. Sélection intentionnelle, pas un nouvel échantillon de validation statistique. Cinq dossiers par volume, ordres et longueurs variés, numérotations irrégulières (Lawastine, Ribaucourt, Flines), annexes/suppléments (Colmar, Mirecourt), certifications, et corrections de Gray, Châtellerault, Digne, Santeny, Châteauneuf. Aubervilliers apporte un contrôle supplémentaire de rapprochement fort. Les motifs et anciens IDs figurent dans `data/selection.json`.

Aucun nouveau détecteur. Les notices du registre restent intactes. Les références Codex établies lors de l’expérience Qwen sont réutilisées **sans lire les sorties du modèle et sans nouvelle inférence**. Elles priment sur le registre ; les références vérifiées du registre priment ensuite sur les parents hérités du pilote. Cette hiérarchie est explicite dans `reviewlib.Store.base`, et chaque export conserve la frontière automatique originale. Elle ne certifie pas l’absence de toute contradiction documentaire.

{table_text}

## Résultats effectivement produits

- **{q["articles_total"]} articles : {q["articles_codex_examined"]} A examinés dans les transcriptions, {q["articles_proposed"]} B proposés.** {q["articles_uncertain_fraction"] * 100:.1f} % restent non certifiés individuellement ; ce n’est pas un taux d’erreur mesuré.
- {q["units_by_type"]["section"]} sections B dont la portée reste proposée ; les titres initiaux du document ne sont pas assimilés à des sections autonomes.
- {q["units_by_type"]["technical_passage"]} passages C, compléments techniques du texte parent, sans prétention à une revendication historique autonome. Ils comprennent aussi titres, préambules, blancs, notes et signatures ; ils ne sont pas tous destinés à la recherche.
- Cinq anciennes références d’articles demandant un réexamen dans les diagnostics V2 restent B malgré leur antériorité. Aucun ancien identifiant n’est écrasé.
- {q["human_validated_parents"]} parents validés humainement dans cet export ; {q["withheld"]} dossier(s) non exporté(s). Les références Codex restent traçables. **La validation du parent ne valide pas automatiquement ses articles.**
- Dossiers retenus hors export : {withheld_text}.
- {ferrieres_text}

Le segmenteur V2 et ses rôles XML sont réutilisés. Les références d’articles examinées sont conservées séparément des propositions brutes ; les propositions qui les recouvrent ne sont pas cumulées avec elles. Le texte restant est conservé en C, et non transformé arbitrairement en articles. Aucun nouvel examen individuel de ces {q["articles_total"]} unités n’est revendiqué.

## Contrôles et limites

[QUALITY.md](QUALITY.md) détaille les invariants et tests. Tous les caractères de chaque parent sélectionné sont couverts exactement une fois par les plages des unités. Chaque parent correspond à sa tranche Stanford exacte. Ce contrôle matériel ne garantit pas que les frontières B ou les périmètres hérités sont historiquement parfaits. **Un réexamen a notamment retrouvé une fin trop courte à Ferrières dans la référence du registre : voir le point de contrôle documenté dans QUALITY.md.** {ferrieres_text}

L’interface a été testée à 320, 375, 768 et 1280 px, avec agrandissement du texte à 200 %, navigation clavier, sélection, enregistrement et reprise. Les essais ont exclusivement utilisé des journaux temporaires synthétiques. Le journal réel est maintenant pris en compte : **{human_summary}** L’outil a enregistré {human["events"]} événements et environ {human["measured_active_seconds"]:.0f} secondes d’activité de navigation déclarée ; ce compteur n’est pas une mesure indépendante du travail humain. Son empreinte est conservée dans `source-manifest.json`, sans exporter les noms et remarques du journal privé.

**Aucun changement applicatif, PostgreSQL, index ou embedding. Aucun LLM appelé, aucun corpus téléchargé, aucune correction OCR.** {q["prior_files_unchanged"]} fichiers antérieurs/sources contrôlés inchangés. Les services de test sont des serveurs de boucle locale, pas des déploiements.

## Données et reproduction

[DATA.md](DATA.md) décrit les exports, identifiants et relations. Pour régénérer :

```sh
/usr/bin/python3 docs/audits/1789-first-article-corpus/build.py
/usr/bin/python3 docs/audits/1789-first-article-corpus/verify.py
/usr/bin/python3 docs/audits/1789-first-article-corpus/report.py
```

Les corpus complets locaux `data/parents.jsonl.gz`, `units-A.jsonl.gz`, `units-B.jsonl.gz`, `units-C.jsonl.gz` et les propositions brutes sont **exclus de Git**, conformément au nettoyage des gros artefacts. Ils existent sur cette machine et sont régénérables avec les sources/références locales. Les rapports, scripts, sélection, correspondances et empreintes restent versionnables ; `data/extraction-manifest.json` conserve leurs tailles et SHA-256. Aucun lien externe de sauvegarde n’est inventé. Les journaux humains doivent être sauvegardés séparément.

`prepare.py` reproduit la sélection initiale ; ne pas le relancer pour enregistrer des décisions. Une modification du lot nécessite une nouvelle version explicitement documentée. Les anciens audits et leurs IDs restent inchangés. Les transcriptions Stanford et les métadonnées Persée gardent leurs provenances et conditions distinctes ; cet outil ne vaut pas autorisation de republication. Aucune publication sur le site n’est effectuée.

## Réponses aux dix questions

1. **Vérifier sans XML ?** Oui, panneaux de blocs, pages, titres, voisins du contexte, liens source et contexte extensible.
2. **Corriger ?** Oui, choix d’un bloc existant pour chaque extrémité ; une limite interne à un bloc reste signalée, jamais fabriquée.
3. **Conservation des décisions ?** Journal append-only, horodaté, lié aux empreintes, historique et contrôle de concurrence ; reprise après redémarrage. La validation exige une action explicite de l’utilisateur.
4. **Dossiers préparés ?** 30, cinq par volume, accessibles parmi les 1 305 notices.
5. **Articles ?** {q["articles_total"]}, dont {q["articles_codex_examined"]} examinés antérieurement par Codex et {q["articles_proposed"]} proposés.
6. **Part incertaine ?** {q["articles_uncertain_fraction"] * 100:.1f} % des articles sont B. Les A ne sont pas des validations humaines ; sections B et passages C sont séparés.
7. **Parents intégraux ?** Oui pour les périmètres sélectionnés, avec notes, signatures et annexes présentes dans ces plages. Cela ne prouve pas la complétude historique de l’édition ni la justesse absolue du dossier.
8. **Retour au contexte ?** ID parent/version de périmètre, offsets Unicode relatifs, XPath/blocs, pages, provenance et voisins techniques disponibles.
9. **Freins à l’indexation ?** Le dossier incertain reste exclu ; les parents exportés ont leur statut explicite. B non examinés, rôle de certaines annexes et rubriques, OCR et textes de paratexte. Un essai isolé est possible en filtrant les types/statuts/`search_eligible`, sans prétendre à un corpus certifié. Aucun embedding produit ici.
10. **Étendre aux 1 305 ?** Vérifier les priorités, traiter les limites internes/composites, enregistrer les décisions, étendre explicitement le lot puis régénérer et contrôler. Garder un contrôle indépendant d’articles et de parents séparé, sauvegarder les journaux et gérer les versions ; pas de généralisation automatique.

## Dossiers et articles

{selected_text}
""")
    print("Reports and small exact-prefix examples written")


if __name__ == "__main__":
    main()
