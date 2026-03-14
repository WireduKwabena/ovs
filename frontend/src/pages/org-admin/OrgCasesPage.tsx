import React from "react";
import { useParams } from "react-router-dom";

import AdminCasesPage from "../admin/AdminCasesPage";

const OrgCasesPage: React.FC = () => {
  const { orgId } = useParams<{ orgId: string }>();
  const organizationId = String(orgId || "").trim() || null;

  return (
    <AdminCasesPage
      scope="org"
      organizationId={organizationId}
      title="Organization Cases"
      description="Review vetting cases within the currently selected organization."
      reviewPathBase={
        organizationId ? `/admin/org/${encodeURIComponent(organizationId)}/cases` : "/admin/cases"
      }
    />
  );
};

export default OrgCasesPage;
