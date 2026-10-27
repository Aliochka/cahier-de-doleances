"""Réexamen source des erreurs connues; ce lot reste du développement, sans indépendance revendiquée."""

from qcommon import HERE, REG, jlines, rows

PAIRS = {
    1: (
        "v1-b015190",
        "v1-b015231",
        "Aix clergé: fin certification De Crouseilhes avant pouvoirs noblesse.",
    ),
    3: (
        "v2-b007532",
        "v2-b007671",
        "Berry noblesse: exclut notice du clergé absent, inclut derniers voeux signés.",
    ),
    5: (
        "v2-b013117",
        "v2-b013226",
        "Cambrai noblesse: dossier précédé du discours et suivi du discours de clôture annoncé dans titre; le commerce intrusif rend le corps à revoir.",
    ),
    6: (
        "v2-b013846",
        "v2-b013894",
        "Castelmoron clergé: pouvoirs préliminaires et cahier complet signé, avant noblesse.",
    ),
    8: (
        "v2-b018316",
        "v2-b018412",
        "Châtellerault clergé: PV introductif et cahier, signatures avant noblesse absente.",
    ),
    9: (
        "v2-b019473",
        "v2-b019510",
        "Chaumont Vexin noblesse: cahier dans p2 après absence du clergé, avec comparants jusqu au tiers suivant.",
    ),
    10: (
        "v3-b005690",
        "v3-b005705",
        "Boussignies/Bouvignies: fin signatures avant Doléances Sin-Lebled.",
    ),
    13: (
        "v3-b009162",
        "v3-b009417",
        "Digne tiers: signature Trabue avant doléances locales séparées.",
    ),
    14: (
        "v3-b009704",
        "v3-b009895",
        "Barcelonnette tiers: début Rédaction, situation géographique intégrée; fin certification avant cahiers particuliers.",
    ),
    15: (
        "v4-b006874",
        "v4-b006892",
        "Uzent: plan à la suite du cahier, pas le cahier Vicdessos; ne pas transformer cet extrait/plan en cahier intégral.",
    ),
    16: (
        "v4-b018047",
        "v4-b018052",
        "Marolles: courrier et signatures avant cahier Marolles-en-Hurepoix distinct.",
    ),
    18: (
        "v5-b010310",
        "v5-b010436",
        "Ploërmel: cahier et minute signée Tuault, avant délibération Pontivy1788.",
    ),
    20: (
        "v6-b002628",
        "v6-b002713",
        "Magistrats Valenciennes: deux parties et approbation Waroquet, avant habitants.",
    ),
    21: (
        "v6-b002714",
        "v6-b002991",
        "Habitants Valenciennes: rédaction, parties et signatures, indication éditoriale avant mémoire Donnain.",
    ),
    24: (
        "v6-b008136",
        "v6-b008180",
        "Eguilles: cahier avec mémoire Goullin explicitement joint (article25), sans notice METS distincte retrouvée; choix de dossier explicite, à confirmer indépendamment.",
    ),
}


def main():
    old = {r["persee_id"]: r for r in rows(REG / "data/annotations.jsonl")}
    out = []
    for w in rows(HERE / "data/windows.jsonl"):
        if w["split"] != "development":
            continue
        i = int(w["id"].split("-")[-1])
        blocks = {b["id"]: b for b in w["blocks"]}
        entry = dict(
            window_id=w["id"],
            persee_id=w["persee_id"],
            volume=w["volume"],
            title=w["title"],
            known_initial_boundary_incorrect=(
                old.get(w["persee_id"], {}).get("boundary_judgment") == "incorrect"
            ),
            reviewer="Codex development control, not independent human",
            status="established",
        )
        if i == 7:
            entry.update(
                status="outside_context",
                start_id="v2-b014122",
                end_id=None,
                reason="Castelnaudary: début et fin de notice visibles mais fin propre du cahier noblesse au milieu omis; la dernière page contient déjà le PV du tiers. Aucune fin unique certifiée depuis cette fenêtre.",
            )
        elif i == 12:
            entry.update(
                status="uncertain_scope",
                start_id=None,
                end_id="v3-b009128",
                reason="Riez: doléances particulières dans Digne à339 puis cahier de chambre ecclésiastique à340-346; titre principal dans le milieu omis. Portée des préliminaires non certifiée; abstention attendue.",
            )
        elif i == 23:
            entry.update(
                status="uncertain_source",
                start_id=None,
                end_id=None,
                reason="Artois clergé/noblesse: colonnes intercalées dans des p; aucune plage contiguë fidèle pour un seul cahier. Abstention attendue.",
            )
        elif i in PAIRS:
            a, b, why = PAIRS[i]
            entry.update(start_id=a, end_id=b, reason=why)
        else:
            r = old[w["persee_id"]]["reference_boundary"]
            bs = [
                b
                for b in w["blocks"]
                if b["tag"] != "pb" and r["start"] <= b["start"] and b["end"] <= r["end"]
            ]
            entry.update(
                start_id=bs[0]["id"],
                end_id=bs[-1]["id"],
                reason="Référence de frontières conforme héritée du registre, projection déterministe sur blocs exacts; pas une validation inédite.",
            )
        if entry["status"] == "established":
            a, b = blocks[entry["start_id"]], blocks[entry["end_id"]]
            entry.update(
                start=a["start"],
                end=b["end"],
                start_xpath=a["xpath"],
                end_xpath=b["xpath"],
                source_sha256=w["source"]["source_sha256"],
            )
        if i == 24:
            entry["annexes"] = [
                dict(start_id="v6-b008170", end_id="v6-b008180", relation="included")
            ]
            entry["main_end_id"] = "v6-b008169"
        out.append(entry)
    jlines(HERE / "data/reference-development.jsonl", out)
    print(
        "Development references",
        len(out),
        "unique exact",
        sum(r["status"] == "established" for r in out),
    )


if __name__ == "__main__":
    main()
