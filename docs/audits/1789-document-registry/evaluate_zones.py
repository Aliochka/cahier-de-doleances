"""Référence de lecture explicite des 12 zones continues, aucun réajustement de règles."""

from lib import HERE, V2, jlines, rows, save, sources

DEFINITIONS = {
    "registry-zone-v1-1": ([], "Répertoire alphabétique de députés Q/R; aucun cahier."),
    "registry-zone-v1-2": ([], "Répertoire de curés F/G; aucun cahier."),
    "registry-zone-v2-1": (
        [
            (
                "Avallon/Aunay-la-Côte",
                "/TEI.2/text/body/div1/div2[10]/div3[5]",
                "uncertain",
                "Un titre Avallon est immédiatement suivi par la continuation Art2 et suivants du cahier Aunay-la-Côte; début Art1 manquant dans cette division. Incompatibilité titre/corps, pas de cahier complet certifié.",
            )
        ],
        "Bloc composite au titre trompeur; exclu du dénominateur des identités certaines.",
    ),
    "registry-zone-v2-2": (
        [
            (
                "Artois clergé",
                "/TEI.2/text/body/div1/div2[6]/div3[1]",
                "autonomous",
                "50 articles et signatures clergé; à partir du saut de page et Art40, texte des articles noblesse intercalé ligne à ligne. Une plage continue ne peut isoler proprement les deux colonnes.",
            )
        ],
        "Un début explicite clergé, contamination du corps par colonne noblesse; début noblesse non localisable proprement.",
    ),
    "registry-zone-v3-1": (
        [
            (
                "Officiers de Grasse",
                "/TEI.2/text/body/div1/div2[24]/div3[11]",
                "associated",
                "Doléances adressées au garde des sceaux; 13 demandes et signature Fauton d Andou.",
            )
        ],
        "Document revendicatif professionnel distinct du dossier clergé de Grasse déjà étudié.",
    ),
    "registry-zone-v3-2": (
        [
            (
                "Vred",
                "/TEI.2/text/body/div1/div2[22]/div3[29]",
                "autonomous",
                "18 demandes, arrêté du 23 mars et signatures.",
            ),
            (
                "Estrées",
                "/TEI.2/text/body/div1/div2[22]/div3[30]",
                "associated",
                "Mémoire et état de doléance: 17 demandes et signatures; unité documentaire autonome sous genre mémoire.",
            ),
        ],
        "Deux documents successifs, sans autre début interne.",
    ),
    "registry-zone-v4-1": (
        [
            (
                "Janvry",
                "/TEI.2/text/body/div1/div2[18]/div3[185]",
                "autonomous",
                "30 articles, date 14 avril, certification Thibault; note de source distincte.",
            )
        ],
        "Un cahier complet dans la fenêtre.",
    ),
    "registry-zone-v4-2": ([], "Tableau alphabétique de paroisses R/S, pas de cahier."),
    "registry-zone-v5-1": (
        [
            (
                "Mathurins",
                "/TEI.2/text/body/div1/div2[2]/div3[12]",
                "autonomous",
                "31 demandes et signatures dont Treilhard, Gaillau, Agier; note imprimée mêlée au p6.",
            )
        ],
        "Un cahier de district.",
    ),
    "registry-zone-v5-2": (
        [
            (
                "Pouvoirs clergé Saintonge",
                "/TEI.2/text/body/div1/div2[24]/div3[2]",
                "associated",
                "Pouvoirs aux représentants, exigences constitutionnelles; pièce associée sans nouveau cahier.",
            )
        ],
        "Un document associé, ne pas le compter comme cahier autonome.",
    ),
    "registry-zone-v6-1": (
        [
            (
                "Puget-lès-Lauris",
                "/TEI.2/text/body/div1/div2[17]/div3[75]",
                "autonomous",
                "Doléances du conseil du 29 mars; clôture signée et deux notes XML.",
            )
        ],
        "Un cahier.",
    ),
    "registry-zone-v6-2": (
        [
            (
                "Eguilles",
                "/TEI.2/text/body/div1/div2[17]/div3[27]",
                "autonomous",
                "26 articles, date 29 mars, signatures; article25 annonce le mémoire à joindre.",
            ),
            (
                "Goullin",
                "/TEI.2/text/body/div1/div2[17]/div3[28]",
                "associated",
                "Mémoire du chirurgien Goullin annoncé dans article25 du cahier Eguilles et signé séparément.",
            ),
        ],
        "Un cahier et son mémoire explicitement annexé; pas deux cahiers.",
    ),
}


def main():
    ss = sources()
    rr = rows(HERE / "data/registry-automatic.jsonl")
    v2 = rows(V2 / "data/v2-document-predictions.jsonl")
    out = []
    for z in rows(HERE / "data/validation-zones.jsonl"):
        items, reason = DEFINITIONS[z["id"]]
        refs = []
        for title, path, kind, note in items:
            a, b = ss[z["volume"]].span(ss[z["volume"]].node(path))
            matches = [
                r
                for r in rr
                if r["metadata"]["volume"] == z["volume"] and r["primary_anchor"] == path
            ]
            contained = [
                r["id"]
                for r in rr
                if r["metadata"]["volume"] == z["volume"]
                and r["boundaries"]["proposal"]
                and r["boundaries"]["proposal"]["start"] <= a < r["boundaries"]["proposal"]["end"]
            ]
            vp = [p for p in v2 if p["volume"] == z["volume"] and p["anchor_xpath"] == path]
            refs.append(
                dict(
                    title=title,
                    xpath=path,
                    start=a,
                    end=b,
                    kind=kind,
                    reason=note,
                    registry_direct=[r["id"] for r in matches],
                    contained_by_proposals=contained,
                    v2_classifications=[p["classification"] for p in vp],
                    v2_admitted=any(
                        p["classification"] in {"autonomous", "associated"} for p in vp
                    ),
                    boundaries_certified=False,
                )
            )
        out.append(
            dict(
                zone_id=z["id"],
                volume=z["volume"],
                start=z["start"],
                end=z["end"],
                xpaths=z["xpaths"],
                complete_start_inventory_within_zone=True,
                reference=refs,
                reason=reason,
                scope="all decoded XML paragraphs/headings in frozen continuous windows; no facsimile collation; beginnings outside windows excluded",
                reviewer="Codex non-independent exploratory source review",
            )
        )
    jlines(HERE / "data/zone-annotations.jsonl", out)
    known = [r for z in out for r in z["reference"] if r["kind"] != "uncertain"]
    uncertain = [r for z in out for r in z["reference"] if r["kind"] == "uncertain"]
    metrics = dict(
        zones=len(out),
        source_characters=sum(z["end"] - z["start"] for z in out),
        known_document_starts=len(known),
        uncertain_composites=len(uncertain),
        autonomous_starts=sum(r["kind"] == "autonomous" for r in known),
        associated_starts=sum(r["kind"] == "associated" for r in known),
        V2_admitted=sum(r["v2_admitted"] for r in known),
        registry_direct=sum(bool(r["registry_direct"]) for r in known),
        registry_contains=sum(bool(r["contained_by_proposals"]) for r in known),
        combined_direct_or_V2=sum(bool(r["registry_direct"]) or r["v2_admitted"] for r in known),
        unretrieved=[
            r["title"] for r in known if not r["registry_direct"] and not r["v2_admitted"]
        ],
        no_global_recall_estimate=True,
    )
    save(HERE / "data/zone-metrics.json", metrics)
    print(metrics)
    for r in known:
        print(
            r["title"], r["registry_direct"], r["contained_by_proposals"], r["v2_classifications"]
        )


if __name__ == "__main__":
    main()
