import React from "react";
import { useNavigate } from "react-router-dom";
import { useSelector } from "react-redux";
import { ArrowRight, CheckCircle2, Fingerprint, ScanLine, Shield, UserCheck } from "lucide-react";

import type { RootState } from "@/app/store";

const capabilityCards = [
  {
    icon: ScanLine,
    title: "Document Authenticity",
    description:
      "OCR, metadata analysis, tamper signals, and fraud scoring on uploaded credentials.",
  },
  {
    icon: UserCheck,
    title: "AI Interviewing",
    description:
      "Structured interview flows with transcript intelligence, rubric scoring, and red flag extraction.",
  },
  {
    icon: Fingerprint,
    title: "Identity Match",
    description:
      "Document portrait-to-live interview face similarity checks with auditable confidence traces.",
  },
  {
    icon: Shield,
    title: "Compliance & Audit",
    description:
      "Traceable decisions, reviewer actions, and model outputs packaged for HR governance.",
  },
];

const processSteps = [
  "Firm onboarding and rubric configuration",
  "Candidate invitation via secure one-time access link",
  "Document + interview vetting automation",
  "Human approval and candidate result notification",
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-cyan-700" />
            <span className="text-lg font-semibold tracking-tight">Online Vetting System</span>
          </div>
          <button
            type="button"
            onClick={() => navigate(isAuthenticated ? "/dashboard" : "/subscribe")}
            className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-cyan-800"
          >
            {isAuthenticated ? "Go to Dashboard" : "Get Started"}
          </button>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(6,182,212,0.14),_transparent_45%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.12),_transparent_45%)]" />
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:px-8 lg:py-28">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              Enterprise Vetting Automation
            </p>
            <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl">
              AI-First Vetting for
              <span className="block text-cyan-700">HR and Risk Teams</span>
            </h1>
            <p className="mt-6 max-w-xl text-base text-slate-600 sm:text-lg">
              Run document verification and live interview intelligence in one workflow,
              then finalize outcomes with human approval and complete auditability.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => navigate(isAuthenticated ? "/dashboard" : "/subscribe")}
                className="inline-flex items-center gap-2 rounded-lg bg-cyan-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800"
              >
                {isAuthenticated ? "Go to Dashboard" : "Get Started"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Operating Model
            </h2>
            <ul className="mt-5 space-y-4">
              {processSteps.map((step) => (
                <li key={step} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
                  <span className="text-sm text-slate-700">{step}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold sm:text-3xl">Core Capabilities</h2>
            <p className="mt-2 text-sm text-slate-600">
              Built for high-volume firm vetting workflows with AI + human review.
            </p>
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {capabilityCards.map((card) => (
            <article
              key={card.title}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="mb-4 inline-flex rounded-lg bg-cyan-50 p-2 text-cyan-700">
                <card.icon className="h-5 w-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">{card.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{card.description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} Online Vetting System</p>
          <a
            href="mailto:support@ovs.local"
            className="font-medium text-cyan-700 hover:text-cyan-800"
          >
            support@ovs.local
          </a>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;

