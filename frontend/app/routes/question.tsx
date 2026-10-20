import { data, Link, redirect, useRevalidator } from "react-router";
import { css } from "../../styled-system/css";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import styles from "../features/forms/results.module.css";
import { answerIds, mergeAnswers } from "../features/pagination/merge-pages";
import { useProgressivePage } from "../features/pagination/use-progressive-page";
import { Answers } from "../features/questions/answers";
import { Statistics } from "../features/questions/statistics";
import { SurveyRouteError } from "../features/surveys/route-error";
import { httpFailure } from "../lib/api";
import {
  getQuestion,
  getQuestionAnswers,
  getQuestionStats,
} from "../lib/api.server";
import {
  ERROR_HEADERS,
  errorMessages,
  failureStatus,
  requireApiData,
} from "../lib/api-errors";
import type { Route } from "./+types/question";

export async function loader({ request, params, url }: Route.LoaderArgs) {
  // React Router parameters occupy whole segments: split only the initial decimal ID.
  const match = /^(\d{1,19})(?:-.+)?$/.exec(params.questionKey);
  if (!match?.[1]) requireApiData(httpFailure(404));
  const id = match?.[1] ?? "";
  const question = requireApiData(
    await getQuestion(id, { signal: request.signal }),
  );
  const path = `/questions/${question.id}-${question.slug}`;
  if (url.pathname !== path) throw redirect(`${path}${url.search}`, 308);
  const cursor = url.searchParams.get("cursor");
  if (
    cursor !== null &&
    (!cursor ||
      cursor.length > 1024 ||
      url.searchParams.getAll("cursor").length > 1)
  )
    requireApiData(httpFailure(422));
  const stats =
    question.display_mode === "choice"
      ? await getQuestionStats(question.id, { signal: request.signal })
      : null;
  const loadOther = stats?.ok && stats.data.other_text_answers_count > 0;
  const answers =
    question.display_mode === "text" || loadOther
      ? await getQuestionAnswers(
          question.id,
          {
            ...(cursor === null ? {} : { cursor }),
            ...(loadOther ? { other_only: true } : {}),
          },
          { signal: request.signal },
        )
      : null;
  const failure =
    answers && !answers.ok ? answers : stats && !stats.ok ? stats : null;
  return data(
    {
      question,
      path,
      cursor,
      answers: answers?.ok ? answers.data : null,
      stats: stats?.ok ? stats.data : null,
      failure,
    },
    {
      status: failure ? failureStatus(failure) : 200,
      headers: failure
        ? ERROR_HEADERS
        : {
            "Cache-Control": "private, no-store",
            ...(cursor !== null ? { "X-Robots-Tag": "noindex, follow" } : {}),
          },
    },
  );
}

export default function Question({
  loaderData: current,
}: Route.ComponentProps) {
  const { question, path, cursor, failure, stats } = current;
  const revalidator = useRevalidator();
  const progressive = useProgressivePage({
    page: current.answers,
    identity: `question:${question.id}`,
    merge: mergeAnswers,
    ids: answerIds,
  });
  const page = progressive.page;
  const retained = failure && page;
  const pageCursor = cursor;
  return (
    <PageContainer>
      <title>{`${question.prompt} — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Question du questionnaire « ${question.form.name} » du Grand Débat National : ${question.prompt}`}
      />
      <link
        rel="canonical"
        href={`https://cahierdedoleances.fr${path}${cursor === null ? "" : `?${new URLSearchParams({ cursor })}`}`}
      />
      {(failure || cursor !== null) && (
        <meta
          name="robots"
          content={failure ? "noindex, nofollow" : "noindex, follow"}
        />
      )}
      <p className={css({ mb: "6" })}>
        <Link to={`/forms/${question.form.id}`}>
          ← Retour au formulaire : {question.form.name}
        </Link>
      </p>
      <h1 className={styles.title}>{question.prompt}</h1>
      <p className={css({ color: "muted", mb: "8" })}>
        {question.type === "multi_choice"
          ? "Choix multiples"
          : question.type === "single_choice"
            ? "Choix unique"
            : "Réponses textuelles"}{" "}
        · Grand Débat National
      </p>
      {failure && (
        <section aria-label="Erreur de chargement" className={css({ mb: "8" })}>
          <Alert variant="error" announcement="assertive">
            {errorMessages[failure.kind]}
          </Alert>
          {retained && (
            <p>Le lot précédemment consulté reste affiché ci-dessous.</p>
          )}
          <form
            method="get"
            action={path}
            onSubmit={(event) => {
              event.preventDefault();
              void revalidator.revalidate();
            }}
          >
            {cursor !== null && (
              <input type="hidden" name="cursor" value={cursor} />
            )}
            <Button type="submit" loading={revalidator.state !== "idle"}>
              Réessayer
            </Button>
          </form>
          {cursor !== null && (
            <p>
              <Link to={path}>Retour aux premières réponses</Link>
            </p>
          )}
        </section>
      )}
      {stats && <Statistics stats={stats} />}
      {page && (
        <Answers
          formId={question.form.id}
          page={page}
          otherOnly={question.display_mode === "choice"}
          path={path}
          cursor={pageCursor}
          pending={progressive.pending}
          onMore={progressive.loadMore}
        />
      )}
    </PageContainer>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
