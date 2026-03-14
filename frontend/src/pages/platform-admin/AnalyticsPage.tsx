import React from "react";
import { Link } from "react-router-dom";
import { Activity, BarChart3, Bot, Cpu, CreditCard, ShieldCheck } from "lucide-react";

import BillingHealthCard from "@/components/admin/BillingHealthCard";
import ReminderHealthCard from "@/components/admin/ReminderHealthCard";
import { getPlatformAdminPath } from "@/utils/appPaths";

const insightCards = [
  {
    title: "Billing health",
    description:
      "Track subscription failures, provider outages, and retry pressure across the platform.",
    icon: CreditCard,
    to: getPlatformAdminPath("control-center"),
    cta: "Open control center",
  },
  {
    title: "AI processing oversight",
    description:
      "Review inference stability, processing errors, and AI support-system health without stepping into appointment decisions.",
    icon: Bot,
    to: getPlatformAdminPath("ai-monitor"),
    cta: "Open AI monitor",
  },
  {
    title: "Model runtime monitoring",
    description:
      "Inspect model runtime telemetry, drift-facing signals, and technical health indicators.",
    icon: Cpu,
    to: getPlatformAdminPath("ml-monitoring"),
    cta: "Open ML monitoring",
  },
];

const PlatformAnalyticsPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-6 xl:px-8">
        <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                Platform Analytics
              </div>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground">
                Platform signals, not organization workflow reports
              </h1>
              <p className="mt-3 text-sm leading-7 text-muted-foreground sm:text-base">
                This page is reserved for SaaS-wide operational analytics. Organization-facing
                appointment exercises, interviews, rubrics, cases, offices, nominees, committees,
                onboarding, and workflow throughput are intentionally excluded from the platform
                admin surface.
              </p>
            </div>
            <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
              <p className="font-semibold">Boundary reminder</p>
              <p className="mt-1 text-sky-800">
                Platform admin observes platform health; organization admin runs organization work.
              </p>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <BillingHealthCard />
          <ReminderHealthCard />
        </div>

        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {insightCards.map(({ title, description, icon: Icon, to, cta }) => (
            <article
              key={title}
              className="rounded-2xl border border-border bg-card p-6 shadow-sm"
            >
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-foreground">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
              <Link
                to={to}
                className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:text-primary/80"
              >
                {cta}
                <BarChart3 className="h-4 w-4" />
              </Link>
            </article>
          ))}
        </section>

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Activity className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-foreground">Operational analytics</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Focus this space on service reliability, provider stability, job health, and system
              responsiveness across all organizations.
            </p>
          </article>
          <article className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-foreground">Decision boundary</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              AI and platform reporting remain decision-support only. Appointment decisions and
              organization workflow actions stay with organization governance actors.
            </p>
          </article>
          <article className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
              <CreditCard className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-foreground">Commercial oversight</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Billing incidents, subscription health, and provider escalations belong here because
              they are platform responsibilities rather than organization-owned tasks.
            </p>
          </article>
        </section>
      </div>
    </div>
  );
};

export default PlatformAnalyticsPage;
