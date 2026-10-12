import { lazy, Suspense, useEffect, useState } from "react";
import { css } from "../../../styled-system/css";
import type { QuestionStatistics } from "../../lib/api";

const Chart = lazy(() => import("./stats-chart"));
const number = new Intl.NumberFormat("fr-FR");
const percentage = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });

export function Statistics({ stats }: { stats: QuestionStatistics }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <section aria-labelledby="stats-title">
      <h2 id="stats-title">Résultats de la question</h2>
      <dl className={css({ display: "grid", gap: "3", mb: "6" })}>
        <div>
          <dt>Réponses enregistrées</dt>
          <dd>{number.format(stats.total_answers)}</dd>
        </div>
        <div>
          <dt>Contributions distinctes ayant répondu</dt>
          <dd>{number.format(stats.answered_contributions_count)}</dd>
        </div>
        <div>
          <dt>Sélections d’options</dt>
          <dd>{number.format(stats.total_option_selections)}</dd>
        </div>
        <div>
          <dt>Réponses avec un autre texte</dt>
          <dd>{number.format(stats.other_text_answers_count)}</dd>
        </div>
        <div>
          <dt>Total des sélections, autre texte inclus</dt>
          <dd>{number.format(stats.total_selections)}</dd>
        </div>
      </dl>
      <p>
        Les pourcentages sont calculés sur les{" "}
        {number.format(stats.total_answers)} réponses enregistrées, avec deux
        décimales au maximum. Ces nombres ne représentent pas des personnes
        distinctes.
      </p>
      {stats.type === "multi_choice" && (
        <p className={css({ mt: "3", mb: "6" })}>
          Plusieurs options peuvent être sélectionnées ; la somme des
          pourcentages peut donc dépasser 100 %.
        </p>
      )}
      {stats.total_answers === 0 && (
        <p>Aucune réponse enregistrée pour cette question.</p>
      )}
      {stats.categories.length > 0 ? (
        <>
          <section
            aria-label="Graphique des sélections"
            className={css({ my: "6", minWidth: 0 })}
            style={{ minHeight: stats.categories.length * 48 + 64 }}
          >
            {!mounted && (
              <p>
                Le graphique interactif complète le tableau ci-dessous,
                disponible sans JavaScript.
              </p>
            )}
            {mounted && (
              <Suspense
                fallback={
                  <p>
                    Chargement du graphique… Les résultats sont disponibles dans
                    le tableau.
                  </p>
                }
              >
                <Chart stats={stats} />
              </Suspense>
            )}
          </section>
          <p>Les numéros du graphique correspondent aux lignes du tableau.</p>
          <table
            className={css({
              width: "100%",
              tableLayout: "fixed",
              borderCollapse: "collapse",
              mt: "4",
              "& th, & td": {
                borderBottomWidth: "thin",
                borderColor: "border",
                py: "3",
                px: { base: "1", sm: "3" },
                textAlign: "left",
                overflowWrap: "anywhere",
                verticalAlign: "top",
              },
            })}
          >
            <caption
              className={css({
                textAlign: "left",
                fontWeight: "bold",
                mb: "3",
              })}
            >
              Sélections par option — pourcentage des réponses enregistrées
            </caption>
            <thead>
              <tr>
                <th scope="col" className={css({ width: "60%" })}>
                  Option
                </th>
                <th scope="col">Effectif</th>
                <th scope="col">Pourcentage</th>
              </tr>
            </thead>
            <tbody>
              {stats.categories.map((category, index) => (
                <tr key={category.option_id ?? category.kind}>
                  <th scope="row">
                    {index + 1}. {category.label}
                  </th>
                  <td>{number.format(category.count)}</td>
                  <td>{percentage.format(category.percentage)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p>Aucune option statistique disponible.</p>
      )}
    </section>
  );
}
