import type { CSSProperties } from "react";
import type { FormDetail, QuestionStatistics } from "../../lib/api";
import styles from "./results.module.css";

export const palette = [
  "#203A8F",
  "#176B68",
  "#876400",
  "#71539B",
  "#A14F2B",
  "#526D37",
];
const number = new Intl.NumberFormat("fr-FR");
const percent = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });

export function isCompleteYesNo(stats: QuestionStatistics): boolean {
  return (
    stats.type === "single_choice" &&
    stats.total_answers > 0 &&
    stats.categories.length === 2 &&
    stats.categories.every((c) => c.kind === "option") &&
    new Set(
      stats.categories.map((c) => c.label.trim().toLocaleLowerCase("fr-FR")),
    ).size === 2 &&
    stats.categories.every((c) =>
      ["oui", "non"].includes(c.label.trim().toLocaleLowerCase("fr-FR")),
    ) &&
    stats.other_text_answers_count === 0 &&
    stats.total_option_selections === stats.total_answers &&
    stats.total_selections === stats.total_answers &&
    stats.categories.reduce((sum, c) => sum + c.count, 0) ===
      stats.total_answers
  );
}
function barColor(index: number): CSSProperties {
  return { "--bar-color": palette[index % palette.length] } as CSSProperties;
}

export function ResultChart({ stats }: { stats: QuestionStatistics }) {
  const binary = isCompleteYesNo(stats);
  return (
    <div className={styles.chart} data-chart-kind={binary ? "yes-no" : "bars"}>
      {stats.type === "multi_choice" && (
        <p className={styles.multiple}>Plusieurs réponses possibles</p>
      )}
      {stats.type === "multi_choice" && (
        <p className={styles.note}>
          Les pourcentages peuvent totaliser plus de 100 %.
        </p>
      )}
      {stats.total_answers === 0 && (
        <p>Aucune réponse enregistrée pour cette question.</p>
      )}
      {binary && (
        <div className={styles.proportional} aria-hidden="true">
          {stats.categories.map(
            (category, index) =>
              category.count > 0 && (
                <span
                  key={category.option_id}
                  style={{
                    ...barColor(index),
                    width: `${(category.count * 100) / stats.total_answers}%`,
                  }}
                />
              ),
          )}
        </div>
      )}
      <ul className={styles.categories} aria-label="Répartition des réponses">
        {stats.categories.map((category, index) => (
          <li
            key={category.option_id ?? category.kind}
            className={styles.category}
          >
            <div className={styles.categoryHeading}>
              <span className={styles.categoryLabel}>
                <span
                  className={styles.swatch}
                  style={barColor(index)}
                  aria-hidden="true"
                />
                {category.label}
              </span>
              <span className={styles.value}>
                {number.format(category.count)} ·{" "}
                {percent.format(category.percentage)} %
              </span>
            </div>
            {!binary && (
              <div className={styles.track} aria-hidden="true">
                <span
                  style={{
                    ...barColor(index),
                    width: `${stats.total_answers ? (category.count * 100) / stats.total_answers : 0}%`,
                  }}
                />
              </div>
            )}
            {category.kind === "other_text" && (
              <p className={styles.note}>
                Réponses comportant un champ textuel « Autre », qui peut
                accompagner une option.
              </p>
            )}
          </li>
        ))}
      </ul>
      {stats.categories.length === 0 && stats.total_answers > 0 && (
        <p>Aucune modalité statistique disponible.</p>
      )}
      <p className={styles.note}>
        Pourcentages calculés sur les {number.format(stats.total_answers)}{" "}
        réponses enregistrées.
      </p>
    </div>
  );
}

export function StatisticalDetails({
  stats,
  publication,
  questionNumber,
}: {
  stats: QuestionStatistics;
  publication?: FormDetail["statistics_availability"];
  questionNumber?: number;
}) {
  return (
    <details className={styles.details}>
      <summary>
        Voir les détails statistiques
        {questionNumber !== undefined && (
          <span className={styles.srOnly}> — question {questionNumber}</span>
        )}
      </summary>
      <div className={styles.detailsBody}>
        <table className={styles.table}>
          <caption>
            Répartition détaillée — pourcentage des réponses enregistrées
          </caption>
          <thead>
            <tr>
              <th scope="col">Modalité</th>
              <th scope="col">Effectif</th>
              <th scope="col">Pourcentage</th>
            </tr>
          </thead>
          <tbody>
            {stats.categories.map((category) => (
              <tr key={category.option_id ?? category.kind}>
                <th scope="row">{category.label}</th>
                <td>{number.format(category.count)}</td>
                <td>{percent.format(category.percentage)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className={styles.metrics}>
          {[
            ["Réponses enregistrées", stats.total_answers],
            [
              "Contributions distinctes ayant répondu",
              stats.answered_contributions_count,
            ],
            ["Sélections d’options", stats.total_option_selections],
            ["Réponses avec un autre texte", stats.other_text_answers_count],
            [
              "Total des sélections, autre texte inclus",
              stats.total_selections,
            ],
          ].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{number.format(value as number)}</dd>
            </div>
          ))}
        </dl>
        <p>
          Chaque pourcentage rapporte l’effectif de la modalité au nombre de
          lignes de réponse enregistrées pour cette question, avec un arrondi à
          deux décimales. Ces nombres ne représentent pas des personnes uniques.
        </p>
        {stats.type === "multi_choice" && (
          <p>
            Plusieurs sélections sont possibles par réponse ; leur somme peut
            dépasser 100 %.
          </p>
        )}
        <p>
          Une réponse comportant plusieurs textes « Autre » compte une seule
          fois dans cette catégorie. Elle peut aussi sélectionner une option.
        </p>
        {publication?.calculated_at && (
          <p>
            Calcul du{" "}
            <time dateTime={publication?.calculated_at}>
              {new Intl.DateTimeFormat("fr-FR", {
                dateStyle: "long",
                timeZone: "Europe/Paris",
              }).format(new Date(publication?.calculated_at))}
            </time>
            .
          </p>
        )}
        {publication?.method_version && (
          <p className={styles.note}>Méthode : {publication?.method_version}</p>
        )}
        {publication?.generation_id && (
          <p className={styles.note}>
            Génération : {publication?.generation_id}
          </p>
        )}
      </div>
    </details>
  );
}
