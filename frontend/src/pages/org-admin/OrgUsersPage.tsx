import React from "react";
import { useParams } from "react-router-dom";

import AdminUsersPage from "../admin/AdminUsersPage";

const OrgUsersPage: React.FC = () => {
  const { orgId } = useParams<{ orgId: string }>();
  const organizationId = String(orgId || "").trim() || null;

  return (
    <AdminUsersPage
      scope="org"
      organizationId={organizationId}
      title="Organization Users"
      description="Manage organization member access, status, and two-factor resets."
    />
  );
};

export default OrgUsersPage;
