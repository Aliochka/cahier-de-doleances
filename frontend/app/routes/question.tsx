import { useRef, useState } from "react";
import {
  data,
  Link,
  redirect,
  useNavigate,
  useNavigation,
  useRevalidator,
} from "react-router";
import { css } from "../../styled-system/css";
import { EmptyState, LoadingState } from "../components/layout/data-states";
import { PageContainer } from "../components/layout/page-container";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Tabs } from "../components/ui/tabs";
import styles from "../features/forms/results.module.css";
import { answerIds, mergeAnswers } from "../features/pagination/merge-pages";
import { useProgressivePage } from "../features/pagination/use-progressive-page";
import { Answers } from "../features/questions/answers";
import { Statistics } from "../features/questions/statistics";
import { loadSearch } from "../features/search/search-loader.server";
import { SearchPanel } from "../features/search/search-panel";
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
  const tab = url.searchParams.get("tab") ?? "answers";
  if (
    !["answers", "search"].includes(tab) ||
    url.searchParams.getAll("tab").length > 1
  )
    requireApiData(httpFailure(422));
  if (tab === "search") {
    const stats =
      question.display_mode === "choice"
        ? await getQuestionStats(question.id, { signal: request.signal })
        : null;
    const noSearchableText = !!(
      stats?.ok && stats.data.other_text_answers_count === 0
    );
    const search = await loadSearch(request, url, {
      path,
      questionId: question.id,
      enabled: !noSearchableText && (!stats || stats.ok),
    });
    if (stats && !stats.ok) search.data.failure = stats;
    return data(
      {
        question,
        path,
        tab,
        cursor: null,
        answers: null,
        stats: null,
        failure: null,
        search: search.data,
        noSearchableText,
      },
      {
        ...search.init,
        ...(stats && !stats.ok ? { status: failureStatus(stats) } : {}),
      },
    );
  }
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
      tab,
      search: null,
      noSearchableText: false,
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
  const { question, path, cursor, failure, tab } = current;
  const navigate = useNavigate();
  const navigation = useNavigation();
  const panels = useRef<HTMLDivElement>(null);
  const [pendingHeight, setPendingHeight] = useState(0);
  const destination =
    navigation.state !== "idle" && navigation.location?.pathname === path
      ? (new URLSearchParams(navigation.location.search).get("tab") ??
        "answers")
      : tab;
  const activeTab = destination === "search" ? "search" : "answers";
  const switchingTabs = activeTab !== tab;
  return (
    <PageContainer>
      <title>{`${question.prompt} — Cahier de doléances`}</title>
      <meta
        name="description"
        content={`Question du questionnaire « ${question.form.name} » du Grand Débat National : ${question.prompt}`}
      />
      <link
        rel="canonical"
        href={`https://cahierdedoleances.fr${path}${tab === "search" || cursor === null ? "" : `?${new URLSearchParams({ cursor })}`}`}
      />
      {(failure || cursor !== null || tab === "search") && (
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
      <p className={css({ textStyle: "documentMetadata", mb: "8" })}>
        {question.type === "multi_choice"
          ? "Choix multiples"
          : question.type === "single_choice"
            ? "Choix unique"
            : "Réponses textuelles"}{" "}
        · Grand Débat National
      </p>
      <Tabs.Root
        value={activeTab}
        activationMode="manual"
        navigate={({ value }) => {
          setPendingHeight(panels.current?.getBoundingClientRect().height ?? 0);
          navigate(value === "search" ? `${path}?tab=search` : path);
        }}
      >
        <Tabs.List aria-label="Consulter la question">
          <Tabs.Trigger value="answers" asChild>
            <Link to={path}>Réponse à la question</Link>
          </Tabs.Trigger>
          <Tabs.Trigger value="search" asChild>
            <Link to={`${path}?tab=search`}>Rechercher dans les réponses</Link>
          </Tabs.Trigger>
        </Tabs.List>
        <div
          ref={panels}
          style={switchingTabs ? { minHeight: pendingHeight } : undefined}
          aria-busy={switchingTabs || undefined}
        >
          <Tabs.Content value="answers">
            {activeTab === "answers" &&
              (switchingTabs ? (
                <LoadingState active />
              ) : (
                <QuestionResponses current={current} />
              ))}
          </Tabs.Content>
          <Tabs.Content value="search">
            {activeTab === "search" && switchingTabs && <LoadingState active />}
            {activeTab === "search" &&
              !switchingTabs &&
              current.search &&
              (current.noSearchableText ? (
                <EmptyState>
                  Cette question ne comporte aucun texte libre « Autre » dans
                  lequel rechercher.
                </EmptyState>
              ) : (
                <SearchPanel
                  {...current.search}
                  otherOnly={question.display_mode === "choice"}
                />
              ))}
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </PageContainer>
  );
}
function QuestionResponses({
  current,
}: {
  current: Route.ComponentProps["loaderData"];
}) {
  const { question, path, cursor, failure, stats, tab } = current;
  const revalidator = useRevalidator();
  const progressive = useProgressivePage({
    page: current.answers,
    identity: `question:${question.id}:${tab}`,
    merge: mergeAnswers,
    ids: answerIds,
  });
  const page = progressive.page;
  const retained = failure && page;
  const pageCursor = cursor;
  return (
    <>
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
    </>
  );
}
export const ErrorBoundary = SurveyRouteError;
export { apiPageHeaders as headers } from "../lib/api-errors";
