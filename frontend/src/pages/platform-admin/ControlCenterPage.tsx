import React from "react";
import { ExternalLink } from "lucide-react";

const ADMIN_SECTIONS = [
  { label: "Billing Subscriptions", path: "billing/subscription/" },
];

const adminBaseUrl = (
  (import.meta as { env?: Record<string, string> }).env?.VITE_DJANGO_ADMIN_URL ||
  "http://localhost:8000/admin/"
).replace(/\/?$/, "/");

const AdminControlCenterPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-6 xl:px-8">
        <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Platform Control Center</h1>
              <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                This area is reserved for platform back-office actions only. Organization
                appointment workflow, cases, users, committees, onboarding, interviews, and
                related vetting operations are intentionally excluded from the platform admin UI.
              </p>
            </div>
            <div className="rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary">
              Keep platform admin focused on subscription oversight and platform reliability.
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {ADMIN_SECTIONS.map((section) => (
            <article key={section.path} className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <h2 className="text-base font-semibold text-foreground">{section.label}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Limited platform back-office entry point for subscription administration.
              </p>
              <a
                href={`${adminBaseUrl}${section.path}`}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-accent hover:text-accent-foreground sm:w-auto"
              >
                Open
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
};

export default AdminControlCenterPage;
