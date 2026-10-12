import { Link } from "react-router";
import { css } from "../../../styled-system/css";
import { RouteErrorState } from "../../components/layout/data-states";
import { PageContainer } from "../../components/layout/page-container";

export function SurveyRouteError({ error }: { error: unknown }) {
  return (
    <PageContainer>
      <RouteErrorState error={error} showLoading={false} />
      <p className={css({ mt: "6" })}>
        <Link to="/enquetes">Retour aux enquêtes</Link>
      </p>
    </PageContainer>
  );
}
