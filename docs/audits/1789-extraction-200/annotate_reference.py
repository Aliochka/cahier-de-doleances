"""Décisions Codex depuis la source, avant prédictions ; aucune règle de segmentation appelée."""

import datetime

from common import HERE, compact, jlines, read, rows, sha, sources, write

# (first p, last p, optional exact opening, optional excluded ending).
REFERENCE = {
    "candidate-a8987424bbb5cb9fa345": dict(
        real=False,
        kind="historical_summary_1483",
        reason="Résumé sous Charles VIII, pas un cahier de1789; titre interne p57.",
    ),
    "candidate-b289035431c04956dabe": dict(
        real=False,
        kind="historical_summary_1560",
        reason="Résumé sous Charles IX, pas un cahier de1789; p61 appartient au récit.",
    ),
    "candidate-5f5cd4b2ef58f7dece46": dict(
        real=False,
        kind="missing_document_notice",
        reason="Béziers tiers: p2 déclare que le cahier manque; deux paragraphes sans revendication.",
    ),
    "candidate-506a682f65ae1e814a3a": dict(
        real=True,
        kind="corporate_cahier_attached_to_arles",
        reason="Doléances des médecins, titre p81, introduction p82, articles et signatures jusqu’àp92; p93 commence les procureurs. Sous-document revendicatif annexé au dossier d’Arles.",
        parent_p=[81, 92],
        windows=[
            dict(
                first=83,
                last=89,
                units=[
                    (83, 83, None, None),
                    (84, 84, None, "Art. 3."),
                    (84, 85, "Art. 3.", None),
                    (86, 86, None, None),
                    (87, 87, None, None),
                    (88, 88, None, "Art. 7."),
                    (88, 89, "Art. 7.", None),
                ],
            )
        ],
    ),
    "candidate-314a64454989f708a8a3": dict(
        real=True,
        kind="cahier_with_attached_local_demands",
        reason="La Rochelle tiers, corps finissant àl’article110 puis demandes de l’île de Ré jointes avant les signatures; deux divisions liées, hiérarchie d’annexe conservée.",
        windows=[
            dict(
                first=2,
                last=12,
                units=[
                    (2, 2, None, None),
                    (3, 3, None, None),
                    (4, 4, None, None),
                    (5, 5, None, None),
                    (7, 7, None, None),
                    (8, 8, None, None),
                    (9, 9, None, None),
                    (10, 10, None, "Art, 9."),
                    (10, 11, "Art, 9.", None),
                    (12, 12, None, None),
                ],
            ),
            dict(first=123, last=123, units=[(123, 123, None, None)]),
        ],
    ),
    "candidate-b11e579d4bc7daa5ad33": dict(
        real=True,
        kind="cahier",
        reason="Thionville clergé, préambule p1, articles, réserves puis signatures et copie conforme p33–35.",
        windows=[
            dict(
                first=2,
                last=14,
                units=[
                    (2, 2, None, None),
                    (3, 3, None, None),
                    (4, 4, None, None),
                    (5, 5, None, None),
                    (6, 6, None, None),
                    (7, 7, None, None),
                    (8, 8, None, None),
                    (9, 10, None, None),
                    (11, 11, None, None),
                    (12, 12, None, None),
                    (13, 13, None, None),
                    (14, 14, None, None),
                ],
            )
        ],
    ),
    "candidate-8615aa6715be49c318a9": dict(
        real=False,
        kind="internal_section_false_parent",
        reason="Doléances pour le clergé p39: section du cahier de Montargis ouvert en tête du div3, pas un cahier autonome.",
    ),
    "candidate-cd771995c951b0c35db8": dict(
        real=False,
        kind="local_section_false_parent",
        reason="Plaintes locales p228: fin du cahier de Claye ouvert p199; ne pas fabriquer un deuxième cahier.",
    ),
    "candidate-e2ed8e80bf9d0e527ede": dict(
        real=False,
        kind="missing_document_notice",
        reason="Soissons noblesse et tiers: note déclarant les documents absents; aucune transcription du cahier.",
    ),
    "candidate-35fa9083b29b304f3277": dict(
        real=True,
        kind="cahier_split_inside_division",
        reason="Vernouillet: tête du div3 jusqu’àla rédaction Laroche p317. Verrières commence au p318. L’année1739 dans la pièce suivante est conservée sans correction.",
        parent_end_p=317,
        windows=[
            dict(
                first=8,
                last=18,
                units=[
                    (8, 10, None, None),
                    (11, 12, None, None),
                    (13, 13, None, None),
                    (14, 14, None, None),
                    (15, 15, None, None),
                    (16, 16, None, None),
                    (17, 17, None, None),
                    (18, 18, None, None),
                ],
            )
        ],
    ),
    "candidate-f2f9d83b2569c0ce70ef": dict(
        real=True,
        kind="unnumbered_cahier",
        reason="Rognac: prose non numérotée, clôture25mars1789 p17, signatures p18. Pas de subdivision en articles certifiée.",
        windows=[dict(first=1, last=18, units=[])],
    ),
    "candidate-ed9e410244588392930b": dict(
        real=True,
        kind="cahier",
        reason="Vic tiers, articles puis clôture28mars1789 et copie conforme; extrait des liasses désigne la provenance et non un abrégé de cahier.",
        windows=[
            dict(
                first=1,
                last=11,
                units=[
                    (1, 1, None, None),
                    (2, 2, None, None),
                    (3, 3, None, None),
                    (4, 4, None, None),
                    (5, 6, None, None),
                    (7, 7, None, None),
                    (8, 8, None, None),
                    (9, 9, None, None),
                    (10, 10, None, None),
                    (11, 11, None, None),
                ],
            )
        ],
    ),
}
NEGATIVES = {
    "negative-v1-1": (
        "not_cahier",
        "Discours au roi et narration des notables; aucune ouverture de cahier dans la fenêtre.",
    ),
    "negative-v1-2": ("not_cahier", "Analyse historique du pouvoir royal, pas un cahier."),
    "negative-v2-1": (
        "missed_cahier",
        "Armagnac/Isle-Jourdain, titre REMONTRÂCES puis Plaintes et doléances: corps numéroté de1789 non admis; début du parent inspecté en complément.",
    ),
    "negative-v2-2": (
        "not_cahier",
        "Extrait de procès-verbal électoral de Château-Thierry, liste de scrutins.",
    ),
    "negative-v3-1": (
        "missed_cahier",
        "Mandats du tiers de Dijon: instructions numérotées de1789 sans le titre Cahier; début inspecté, absent des hypothèses admises.",
    ),
    "negative-v3-2": (
        "missed_embedded_doleances",
        "Bouvignies: procès-verbal contenant explicitement les doléances numérotées; l’exclusion globale du PV perd son corps revendicatif.",
    ),
    "negative-v4-1": (
        "not_cahier",
        "Chevannes: procès-verbal électoral qui accompagne des instructions précédentes; aucune ouverture supplémentaire.",
    ),
    "negative-v4-2": (
        "not_cahier",
        "Traité en chapitres sur les ordres religieux; statut de traité, pas nouveau cahier dans cette fenêtre.",
    ),
    "negative-v5-1": (
        "missed_cahier",
        "Saint-Pierre-le-Moutier: CAHIER est p1 et son titre p2, aucun head; début inspecté, pas d’hypothèse acceptée.",
    ),
    "negative-v5-2": (
        "not_cahier",
        "Procès-verbal de Saint-Germain-des-Prés, relations entre assemblées et députations.",
    ),
    "negative-v6-1": (
        "uncertain_memorandum",
        "Mémoire des notaires de Vitry-le-François: doléances professionnelles, mais nature de cahier autonome non établie dans le contrôle.",
    ),
    "negative-v6-2": (
        "not_cahier",
        "Procès-verbal de Chartres, liste des comparants; pas un cahier.",
    ),
}


def trimmed(s, a, b):
    while a < b and s.text[a].isspace():
        a += 1
    while b > a and s.text[b - 1].isspace():
        b -= 1
    return a, b


def main():
    assert not (HERE / "data/automatic-units.jsonl").exists(), (
        "Reference must precede prediction review"
    )
    assert not (HERE / "reference-freeze.json").exists(), "Reference already frozen"
    ss = sources()
    selected = {c["id"]: c for c in rows(HERE / "data/selection.jsonl")}
    assert set(REFERENCE) == set(read(HERE / "protocol.json")["validation_ids"])
    result = []
    for cid, decision in REFERENCE.items():
        c = selected[cid]
        s = ss[c["volume"]]
        base = c["xpath"]
        row = dict(
            candidate_id=cid,
            volume=c["volume"],
            source_xpath=base,
            **decision,
            reviewer="Codex_source_review_non_independent",
        )
        if decision["real"]:
            a, b = c["start"], c["end"]
            if "parent_p" in decision:
                i, j = decision["parent_p"]
                a = s.span(s.node(f"{base}/p[{i}]"))[0]
                b = s.span(s.node(f"{base}/p[{j}]"))[1]
            if "parent_end_p" in decision:
                b = s.span(s.node(f"{base}/p[{decision['parent_end_p']}]"))[1]
            row["parent_reference_span"] = list(trimmed(s, a, b))
        windows = decision.get("windows", [])
        if not decision["real"]:
            windows = [dict(first=None, last=None, units=[])]
        calculated = []
        for w in windows:
            if w["first"] is None:
                wa, wb = c["start"], c["end"]
            else:
                wa = s.span(s.node(f"{base}/p[{w['first']}]"))[0]
                wb = s.span(s.node(f"{base}/p[{w['last']}]"))[1]
            units = []
            for i, j, opening, ending in w["units"]:
                n1 = s.node(f"{base}/p[{i}]")
                n2 = s.node(f"{base}/p[{j}]")
                a, b = s.span(n1)[0], s.span(n2)[1]
                if opening:
                    a += s.text[a : s.span(n1)[1]].index(opening)
                if ending:
                    b = s.span(n2)[0] + s.text[s.span(n2)[0] : b].index(ending)
                a, b = trimmed(s, a, b)
                assert wa <= a < b <= wb
                units.append(
                    dict(
                        start=a,
                        end=b,
                        xml_blocks=[f"{base}/p[{p}]" for p in range(i, j + 1)],
                        text=s.text[a:b],
                        boundary_basis="source paragraphs and literal marker reviewed before predictions",
                    )
                )
            calculated.append(
                dict(
                    start=wa,
                    end=wb,
                    units=units,
                    reference_complete_within_window=True,
                    article_count=len(units),
                )
            )
        row["reference_windows"] = calculated
        result.append(row)
    jlines(HERE / "data/reference-documents.jsonl", result)
    negatives = []
    for w in rows(HERE / "data/non-detection-windows.jsonl"):
        kind, reason = NEGATIVES[w["id"]]
        negatives.append(
            dict(
                window_id=w["id"],
                volume=w["volume"],
                start=w["start"],
                end=w["end"],
                classification=kind,
                reason=reason,
                reference_basis="full six-p window read; enclosing title/first p inspected for context",
                source_xpaths=w["xpaths"],
                judge="Codex non-independent",
            )
        )
    write(HERE / "data/reference-negative.json", negatives)
    write(
        HERE / "reference-freeze.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            new_predictions_exist=False,
            files={
                p: sha((HERE / p).read_bytes())
                for p in [
                    "annotate_reference.py",
                    "data/reference-documents.jsonl",
                    "data/reference-negative.json",
                ]
            },
            scope="12 new candidates, source-only windows; 12 negative windows; not independent human",
        ),
    )
    print(
        "Reference frozen:",
        len(result),
        "parents,",
        sum(len(w["units"]) for d in result for w in d["reference_windows"]),
        "article boundaries;",
        len(negatives),
        "negative windows",
    )


if __name__ == "__main__":
    main()
