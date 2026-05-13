import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { RegisterForm } from "@/components/auth/RegisterForm";

export const RegisterPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const orgSlug = String(searchParams.get("org") || "").trim();

  useEffect(() => {
    if (orgSlug) {
      sessionStorage.setItem("organization_slug", orgSlug);
    }
  }, [orgSlug]);

  return <RegisterForm />;
};

export default RegisterPage;
