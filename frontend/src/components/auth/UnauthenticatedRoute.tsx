import React from "react";
import { Navigate } from "react-router-dom";
import { Loader } from "lucide-react";
import { useSelector } from "react-redux";

import type { RootState } from "@/app/store";
import { resolveUnauthenticatedRouteRedirect } from "@/utils/authRouting";

interface UnauthenticatedRouteProps {
  children: React.ReactElement;
  allowTwoFactorChallenge?: boolean;
}

export const UnauthenticatedRoute: React.FC<UnauthenticatedRouteProps> = ({
  children,
  allowTwoFactorChallenge = false,
}) => {
  const { isAuthenticated, userType, twoFactorRequired, twoFactorToken, silentRefreshPending } = useSelector(
    (state: RootState) => state.auth,
  );
  const isRehydrated = useSelector((state: RootState) =>
    state._persist ? state._persist.rehydrated : true,
  );

  if (!isRehydrated || silentRefreshPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center" data-testid="unauth-route-loader">
        <Loader className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  const routeRedirect = resolveUnauthenticatedRouteRedirect({
    isAuthenticated,
    userType,
    allowTwoFactorChallenge,
    twoFactorRequired,
    twoFactorToken,
  });
  if (routeRedirect) {
    return <Navigate to={routeRedirect} replace />;
  }

  return children;
};
