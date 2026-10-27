"""Décisions explicites de revue des19 écarts; ni correction ni renommage des anciens objets."""

from common import HERE, jlines, rows, write

DIAGNOSES = {
    1: (
        "rubrique absorbée",
        "Religion. est un intitulé suivi de nouveaux ordinaux; fin après p9 préférable, rubrique p10 séparée.",
        False,
    ),
    2: (
        "rubrique absorbée / portée à revoir",
        "Administration. ouvre le groupe suivant; conserver la charte p6–19 dans l’article4 sans absorber p20. Le statut hiérarchique de la charte mérite une relecture, pas un découpage sémantique.",
        True,
    ),
    3: (
        "fusion et mandat absorbé",
        "Le dixième chef s’arrête àp12; p13 annonce explicitement le onzième, et p14 est un mandat. Ancienne limite mieux étayée.",
        False,
    ),
    4: (
        "marqueur OCR non reconnu",
        "i lfl n’autorise pas à restaurer un chiffre, mais «onzième chef» et le paragraphe autonome étayent la séparation de p13; mandat p14 hors article.",
        False,
    ),
    5: (
        "fusion de trois unités",
        "La V1 absorbe z8 et36 dans le premier article; les paragraphes et repères distincts soutiennent les limites anciennes, sans corriger les chiffres.",
        False,
    ),
    6: (
        "début OCR manqué",
        "z8 ouvre un nouveau paragraphe de doléances; conserver cette étiquette littérale. La fusion avec1° puis36 est moins fidèle à la structure.",
        False,
    ),
    7: (
        "début OCR manqué et continuation",
        "36 ouvre p3; la continuation au début de p4 précède4®. L’ancienne étendue respecte cette continuation sans inventer un numéro.",
        False,
    ),
    8: (
        "ponctuation réattribuée",
        "La virgule initiale du p suivant est absorbée par4® en V1. La convention de propriété du paragraphe favorise l’ancienne fin; la ponctuation historique doit être distinguée.",
        True,
    ),
    9: (
        "ponctuation préfixe perdue",
        "Le p commence par,5®; garder la virgule avec le repère conserve la tranche source. C’est une convention explicite de frontière, pas une correction OCR.",
        True,
    ),
    10: (
        "fusion par repère illisible",
        "La V1 fusionne7® avec B®; les p7 etp8 et leurs amorces distinctes favorisent les anciennes unités. Aucun remplacement de B par8.",
        False,
    ),
    11: (
        "début OCR manqué",
        "B® est conservé littéralement; la frontière de p8 est mieux soutenue que la fusion avec7®.",
        False,
    ),
    12: (
        "fusion par repère illisible",
        "10® et Il® sont deux amorces dans deux paragraphes; l’ancienne fin de10® évite d’absorber les collecteurs.",
        False,
    ),
    13: (
        "début OCR manqué",
        "Il® reste une étiquette non restaurée; p10 forme une unité documentaire plus fidèle que sa fusion avec10®.",
        False,
    ),
    14: (
        "tiret réattribué",
        "Le tiret initial du paragraphe suivant est annexé à10° en V1. La convention XML donne l’ancienne fin.",
        True,
    ),
    15: (
        "tiret préfixe perdu",
        "-11° doit conserver son préfixe source dans la convention retenue; ne pas le laisser à10°.",
        True,
    ),
    16: (
        "virgule réattribuée",
        "La virgule de p17 est rattachée à13 par V1; préférer l’ancienne fin de p16 selon la propriété du paragraphe.",
        True,
    ),
    17: (
        "virgule préfixe / contenu incomplet",
        "Préférer le début de p17 avec sa virgule; la phrase14 se termine incomplètement avant15 dans le TEI. Réexaminer sa complétude et sa portée sur image avant une certitude historique.",
        True,
    ),
    18: (
        "rubrique absorbée",
        "Dette nationale consolidée. introduit l’article2, pas la fin de1; garder p10–11 puis rubrique séparée.",
        False,
    ),
    19: (
        "rubrique absorbée",
        "Visite des titres des créanciers de l’Etat. introduit le groupe suivant; l’ancienne fin de p13 est mieux étayée.",
        False,
    ),
}


def main():
    rs = rows(HERE / "data/segmentation-differences-19.jsonl")
    cmp = rows(HERE / "data/development-pair-comparison.jsonl")
    out = []
    for r in rs:
        cause, diagnosis, review = DIAGNOSES[r["index"]]
        main = max(
            r["v1_predictions"],
            key=lambda p: (
                min(p["end"], r["reference"]["end"]) - max(p["start"], r["reference"]["start"])
            ),
        )
        c = next(
            c
            for c in cmp
            if c["document_key"] == r["document_key"]
            and c["start"] == r["reference"]["start"]
            and c["end"] == r["reference"]["end"]
        )
        out.append(
            dict(
                index=r["index"],
                document_key=r["document_key"],
                legacy_unit_id=r["legacy_unit_id"],
                volume=r["volume"],
                original_reference_span=[r["reference"]["start"], r["reference"]["end"]],
                primary_v1_span=[main["start"], main["end"]],
                all_v1_overlapping_spans=[[u["start"], u["end"]] for u in r["v1_predictions"]],
                cause=cause,
                diagnosis=diagnosis,
                preferred="original_reference_for_TEI_documentary_boundaries",
                reference_reexamination_requested=review,
                new_regression_introduced_by_v1=r["pilot_raw_was_exact"],
                v2_matches_original=c["v2_exact"],
                reviewer="Codex source XML; not independent historical validation",
            )
        )
    assert len(out) == 19 and not any(r["new_regression_introduced_by_v1"] for r in out)
    jlines(HERE / "data/19-diagnoses.jsonl", out)
    write(
        HERE / "data/19-diagnoses-summary.json",
        dict(
            rows=19,
            new_regressions_introduced=0,
            v2_resolved=sum(r["v2_matches_original"] for r in out),
            v2_remaining=sum(not r["v2_matches_original"] for r in out),
            reference_reexamination_flags=sum(r["reference_reexamination_requested"] for r in out),
            old_files_and_ids_unchanged=True,
        ),
    )


if __name__ == "__main__":
    main()
