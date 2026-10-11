// Test fixture only: not an Enquêtes/Formulaire page and excluded from normal builds.
import { Link, useLoaderData } from "react-router";
import { EmptyState } from "../../app/components/layout/data-states";
import { PageContainer } from "../../app/components/layout/page-container";
import { getForm } from "../../app/lib/api.server";
import { ERROR_HEADERS, requireApiData } from "../../app/lib/api-errors";

export async function loader({ request }: { request: Request }) {
  const id = new URL(request.url).searchParams.get("id") ?? "9007199254740993";
  return requireApiData(await getForm(id, { signal: request.signal }));
}
export function headers() {
  return ERROR_HEADERS;
}
export default function ApiFixture() {
  const form = useLoaderData<typeof loader>();
  return (
    <PageContainer>
      <title>Test du chargement SSR</title>
      <meta name="robots" content="noindex" />
      <h1>Vérification du chargement</h1>
      <p>{form.name}</p>
      <p data-testid="id">{form.id}</p>
      {form.questions.length === 0 && <EmptyState />}
      <nav aria-label="Scénarios de test">
        <Link to="?_test=1&id=8">Lecture lente</Link>
        {" · "}
        <Link to="?id=503">Service indisponible</Link>
        {" · "}
        <Link to="?id=500">Erreur ponctuelle</Link>
        {" · "}
        <Link to="?id=9007199254740993">Lecture normale</Link>
        {" · "}
        <Link to="/">Accueil</Link>
      </nav>
    </PageContainer>
  );
}
