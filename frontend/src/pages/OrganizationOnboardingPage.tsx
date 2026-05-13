import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Building2, Info } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const OrganizationOnboardingPage: React.FC = () => {
  const { activeOrganizationId, activeOrganization } = useAuth();

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center justify-center px-4 py-8">
      <Card className="w-full rounded-3xl border-border/60 bg-card/90 p-8 shadow-sm">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <Info className="h-3.5 w-3.5" />
              Organization Onboarding
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
                Onboarding management has been removed.
              </h1>
              <p className="max-w-xl text-sm text-muted-foreground md:text-base">
                Invitation tokens and billing-driven onboarding flows are no
                longer exposed here. Use the organization dashboard or setup
                page to continue managing the organization.
              </p>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <Button asChild className="rounded-xl">
                <Link
                  to={
                    activeOrganizationId
                      ? "/organization/dashboard"
                      : "/organization/setup"
                  }
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  {activeOrganizationId ? "Back to Dashboard" : "Open Setup"}
                </Link>
              </Button>
              <Button variant="outline" asChild className="rounded-xl">
                <Link to="/organization/setup">Open Organization Setup</Link>
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 md:min-w-64">
            <div className="flex items-center gap-3 text-sm font-medium text-foreground">
              <Building2 className="h-4 w-4 text-primary" />
              {activeOrganization?.name ?? "Organization"}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              This page now serves as a redirect-friendly notice instead of a
              token management console.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default OrganizationOnboardingPage;
