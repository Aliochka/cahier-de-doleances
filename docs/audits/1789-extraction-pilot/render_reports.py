"""Rapports calculés depuis le registre et les contrôles, sans nouvelle extraction."""

from common import ROOT, read


def percent(value):
    return f"{100 * value:.1f}".replace(".", ",") + " %"


def render():
    register = read("data/register.json")
    evaluation = read("data/evaluation.json")
    summary = read("data/summary.json")
    by_key = {d["key"]: d for d in evaluation["documents"]}
    rows = [
        "# Registre des 30 cahiers",
        "",
        "Généré par `render_reports.py`. Sélection raisonnée, non représentative. Les sept cas hérités sont signalés ; les 23 autres sont les ajouts du pilote. Les statuts de frontières résultent d’une revue XML par Codex, pas d’une expertise humaine indépendante.",
        "",
        "Les XPath ci-dessous sont relatifs à `/TEI.2/text/body/div1`. Les références complètes, offsets, sections, dates, titres source et incertitudes sont dans [register.json](data/register.json) et [decisions.json](decisions.json). Une page `?` indique un libellé imprimé absent du `pb`, jamais remplacé par le numéro d’image.",
        "",
        "| Cahier et texte intégral | Vol. | Ordre explicite | Sélection | Pages TEI | Frontière automatique | Unités A / B |",
        "|---|---:|---|---|---|---|---:|",
    ]
    for d in register:
        e = by_key[d["key"]]
        labels = [p.get("n") or "?" for p in d["pages"]]
        pagination = (
            f"{labels[0]}–{labels[-1]}" if len(labels) > 1 else labels[0] if labels else "?"
        )
        rows.append(
            f"| [{d['title_display']}](data/parents/{d['key']}.txt) | {d['volume']} | {d['metadata']['estate'] or 'non attribué'} | {'hérité' if d['previous_audit'] else 'ajout'} | {pagination} | {'conforme' if e['automatic_parent_matches_reference'] else 'corrigée'} | {e['A']} / {e['B']} |"
        )
    rows += ["", "## Références, motifs et limites", ""]
    for d in register:
        e = by_key[d["key"]]
        paths = "; ".join(
            "`" + xp.removeprefix("/TEI.2/text/body/div1/") + "`" for xp in d["divisions"]
        )
        rows += [
            f"### {d['key']}",
            "",
            f"**{d['title_display']}**, volume {d['volume']} — [XML source figé]({d['source_url']}), [volume numérisé]({d['scan_url']}), [fragment XML de contrôle](data/parents/{d['key']}.xml).",
            "",
            f"Références : {paths}. Plage décodée du volume : `[{d['source_text_start']}, {d['source_text_end']})`. Statut : `{d['boundary_review']}`. Identifiant : `{d['id']}`.",
            "",
            f"Motif : {d['selection_reason']}.",
            "",
            f"Date de présentation : {d['metadata']['date'] or 'non extraite de manière fiable'}. Provenance : {d['metadata']['date_provenance'] or 'non renseignée'}.",
            "",
            f"Résultat : {e['automatic_units_before_review']} candidats automatiques avant revue ; {e['A']} A et {e['B']} B après revue. {e['manual_structure_decisions']} décisions de rôles/plages, hors annotations des unités de référence.",
            "",
        ]
        if d["uncertainties"]:
            rows += ["Limites : " + " ".join(d["uncertainties"]), ""]
    (ROOT / "REGISTER.md").write_text("\n".join(rows) + "\n")
    m = evaluation["aggregate_reviewed_windows"]
    timing = evaluation["timing"]
    report = [
        "# Évaluation documentaire et technique",
        "",
        "Générée depuis les résultats calculés. Référence XML revue par Codex ; cinq contrôles visuels partiels, aucune validation humaine indépendante. Les scores concernent des fenêtres de développement choisies intentionnellement, pas un échantillon représentatif ni un test aveugle.",
        "",
        "## Frontières des parents",
        "",
        f"Sur {summary['documents']} débuts présélectionnés, {summary['parents_matching_automatic_boundaries']} étendues automatiques concordent avec la référence XML ; {summary['parents_requiring_boundary_correction']} nécessite une correction (Beaurecueil). Après décision, {summary['parents_with_uncertain_boundaries_after_xml_review']} frontière de parent reste non résolue dans le périmètre TEI retenu. La complétude historique des manuscrits n’est pas mesurée.",
        "",
        "La simple prise du premier `div3` donnerait 26 étendues conformes. Trois regroupements sont nécessaires (Anjou, Mirecourt, Ferrières), et un cahier doit être coupé à l’intérieur d’une division. Le rappel de découverte des cahiers dans six volumes entiers n’est pas connu.",
        "",
        "## Avant corrections : unités et frontières",
        "",
        f"{summary['gold_A_windows']} fenêtres A entièrement annotées pour leur périmètre d’articles, {m['gold']} unités de référence ; une fenêtre B exclue. Les fenêtres sans articles sont conservées, les erreurs et unités manquées sont comptées. {m['predicted']} propositions automatiques commencent dans ces fenêtres. Leurs fins peuvent dépasser le périmètre contrôlé, ce qui ne les rend pas exactes.",
        "",
        "| Mesure | Corrects | Faux positifs | Manqués | Précision | Rappel |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, kind in [("Débuts (offset exact)", "starts"), ("Fins (offset exact)", "ends")]:
        report.append(
            f"| {label} | {m['correct_' + kind]} | {m['wrong_' + kind]} | {m['missed_' + kind]} | {percent(m[kind + '_precision'])} | {percent(m[kind + '_recall'])} |"
        )
    report += [
        f"| Unités (couple début/fin exact) | {m['correct_units']} | {m['predicted'] - m['correct_units']} | {m['gold'] - m['correct_units']} | {percent(m['unit_precision'])} | {percent(m['unit_recall'])} |",
        "",
        "Calcul : précision = corrects / propositions ; rappel = corrects / référence. Les débuts et fins sont comparés comme ensembles d’offsets. Une fusion peut avoir un début et une fin chacun présents dans la référence, mais associés à deux articles différents ; seule la mesure par couple vérifie alors la bonne unité. Les décalages de ponctuation sont comptés comme erreurs strictes, même quand le contenu lexical est proche.",
        "",
        "Les prédictions brutes ne bénéficient ni des affectations déclaratives de paragraphes ni du remplacement par les plages de référence. Les règles ont néanmoins été développées sur ces documents : ce résultat n’est pas une estimation indépendante de généralisation. Les modifications du référentiel sont documentées dans `review-log.json`.",
        "",
        "## Après revue : statut du corpus",
        "",
        f"{summary['final_article_candidates']} candidats : **{summary['A']} A ({percent(summary['A_share_of_final_candidates'])})**, **{summary['B']} B**, et **{summary['C_source_ranges_not_articles']} plages C non assimilées à des articles**. Les 30 textes parents sont conservés.",
        "",
        f"Couverture A : {summary['non_whitespace_A_characters']} caractères non blancs sur {summary['non_whitespace_parent_characters']} dans tous les parents, soit **{percent(summary['A_text_coverage_of_all_parent_text'])}**. Le dénominateur inclut titres, notes, signatures, annexes et préambules ; il ne représente pas seulement les revendications. L’indentation XML ne pèse pas dans cette mesure.",
        "",
        f"Le corps numéroté est entièrement vérifié pour {len(summary['fully_reviewed_numbered_body_documents'])} cahiers : "
        + ", ".join(summary["fully_reviewed_numbered_body_documents"])
        + ". Les autres corps numérotés ne sont vérifiés que par fenêtres. Agen tiers et Lourmarin n’ont aucun article retenu ; leur prose reste accessible dans les parents et les plages C.",
        "",
        "La correspondance de chaque A avec la référence est contrôlée automatiquement. Afficher 100 % après remplacement par cette référence serait tautologique ; aucun nouveau taux indépendant après correction n’est annoncé.",
        "",
        "## Résultats par cahier",
        "",
        "| Cahier | Candidats bruts | Après revue | A vérifiés | B non certifiés | Frontière parent |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for d in evaluation["documents"]:
        report.append(
            f"| {d['key']} | {d['automatic_units_before_review']} | {d['units_after_review']} | {d['A']} | {d['B']} | {'conforme' if d['automatic_parent_matches_reference'] else 'corrigée'} |"
        )
    report += [
        "",
        "## Suivi des propositions et exclusions",
        "",
        f"Sur {summary['raw_candidates']} propositions initiales :",
        "",
    ]
    for k, n in summary["proposal_review_outcomes"].items():
        report.append(f"- `{k}` : {n}.")
    report += [
        "",
        "Les 7 exclusions d’articles autonomes correspondent à la citation du conseil royal dans le préambule d’Agen noblesse, conservée dans le texte parent. Les 72 frontières modifiées ne désignent pas 72 articles désormais certifiés : une modification de rôle documentaire peut également affecter une proposition restant B. Les passages ajoutés ou scindés sont traçables dans les objets de référence et les relations du registre de revue.",
        "",
        "Six cas négatifs distincts sont exclus comme parents autonomes. Ils ne sont pas ajoutés au dénominateur des 30. La liste des erreurs exactes et leurs textes est conservée dans `data/boundary-errors.json` ; l’analyse des causes se trouve dans `PROBLEMS.md`.",
        "",
        "## Effort observé et durées",
        "",
        f"- Correction de frontière parent : {summary['parents_requiring_boundary_correction']}.",
        f"- Décisions déclaratives de rôles/plages documentaires : {summary['explicit_structure_decisions']}, modifiant le rôle de {summary['paragraph_roles_changed']} paragraphes.",
        f"- Unités A contrôlées dans les fenêtres : {summary['A']}.",
        f"- Parsing et calcul des positions pour les six XML : {timing['load_parse_offset_seconds']:.3f} s.",
        f"- Extraction et écritures du corpus, parsing compris : {timing['whole_run_seconds']:.3f} s ; CPU {timing['process_cpu_seconds']:.3f} s.",
        f"- Exécution mesurée : `{timing['run_started_utc']}`.",
        "- Téléchargement, revue documentaire et temps humain : hors de cette durée automatique. Aucun temps humain de validation mesuré, aucun historien intervenu.",
        "",
        "La mise au point initiale et la revue du lot n’ont pas été chronométrées séparément. Les nombres de décisions ne peuvent donc pas être convertis en heures par cahier ou en coût de traitement général. Prévoir un journal opérateur sur un prochain lot indépendant, avec tâches et durées distinctes.",
        "",
        "## Portée des contrôles",
        "",
        "La reconstruction des textes, les empreintes, les intervalles, les références XML, les parents, les notes séparées, l’ordre et les voisins passent les contrôles. Sept fautes injectées sont détectées. Les 50 fichiers des anciens audits sont inchangés. La reproductibilité des données est vérifiée sur deux exécutions, hors durées et horodatages. Ces garanties techniques n’équivalent pas à la validation documentaire des B.",
        "",
        "Les cinq contrôles image sont ponctuels, sans mesure exhaustive de CER/WER. Le taux de cahiers manquants, le nombre total d’articles réels dans les 30 parents et la fréquence des difficultés sur tout Stanford ne sont pas établis. Aucune extrapolation de précision ou de temps humain n’est justifiée.",
    ]
    (ROOT / "EVALUATION.md").write_text("\n".join(report) + "\n")


if __name__ == "__main__":
    render()
