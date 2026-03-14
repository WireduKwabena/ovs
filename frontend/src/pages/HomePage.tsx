import React from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Fingerprint,
  Gavel,
  Globe2,
  Lock,
  ScanLine,
  Shield,
  UserCheck,
  Users,
} from "lucide-react";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { useAuth } from "@/hooks/useAuth";

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
      "Traceable decisions, reviewer actions, and model outputs packaged for internal governance.",
  },
];

const processSteps = [
  "Organization or agency onboarding and policy setup",
  "Candidate invitation via secure one-time access link",
  "Document + interview vetting (AI-assisted, human reviewed)",
  "Approval-chain review, final decision, and publication",
];

const workflowSteps = [
  "Position and personnel registry preparation",
  "Nomination record creation and vetting-case linkage",
  "Approval stages (intake, vetting, committee, authority)",
  "Final appointment decision and serving-state update",
  "Gazette publication, revocation controls, and audit trail",
];

const audienceCards = [
  {
    icon: Building2,
    title: "Organization / Agency",
    description:
      "Onboard your institution, configure workflow governance, and run appointments at scale.",
  },
  {
    icon: Users,
    title: "Invited Candidate",
    description:
      "Access candidate tasks through invitation links. Open self-signup is not the candidate path.",
  },
  {
    icon: Globe2,
    title: "Public Observer",
    description:
      "View published public records only. Internal vetting notes and sensitive data remain restricted.",
  },
];

const governanceHighlights = [
  {
    icon: Lock,
    title: "Step-Up Protection",
    description:
      "Sensitive actions such as appointing and publication require recent authentication checks.",
  },
  {
    icon: Shield,
    title: "AI Is Advisory Only",
    description:
      "Rubric and decision-engine outputs support reviewers; humans retain final authority.",
  },
  {
    icon: Gavel,
    title: "Traceable Decisions",
    description:
      "Lifecycle actions and governance events are logged for audit, oversight, and accountability.",
  },
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    isAuthenticated,
    userType,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const startOrganizationPath = "/organization/setup?next=%2Forganization%2Fdashboard";

  const handleGetStarted = () => {
    if (!isAuthenticated) {
      navigate("/organization/get-started?next=%2Fsubscribe");
      return;
    }

    if (userType === "applicant") {
      navigate("/candidate/access");
      return;
    }

    if (!activeOrganizationId) {
      navigate(startOrganizationPath);
      return;
    }

    if (canManageActiveOrganizationGovernance) {
      navigate("/organization/dashboard");
      return;
    }

    navigate("/workspace");
  };

  const handleOpenTransparencyPortal = () => {
    navigate("/transparency");
  };

  const handleOpenGazetteFeed = () => {
    navigate("/gazette");
  };

  const handleOpenPublishedAppointments = () => {
    navigate("/transparency#published-appointments");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-primary" />
            <span className="text-lg font-semibold tracking-tight text-foreground">CAVP Platform</span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle compact />
            <button
              type="button"
              onClick={handleGetStarted}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(6,182,212,0.14),_transparent_45%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.12),_transparent_45%)]" />
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:px-8 lg:py-28">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              Vetting and Appointment Governance
            </p>
            <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl">
              AI-Assisted Vetting and
              <span className="block text-cyan-700">Government Appointments</span>
            </h1>
            <p className="mt-6 max-w-xl text-base text-slate-700 sm:text-lg">
              Run document verification and interview intelligence with human oversight, then
              manage appointment approvals, publication, and auditability end to end.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleGetStarted}
                className="inline-flex items-center gap-2 rounded-lg bg-cyan-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800"
              >
                Start Organization Setup
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="inline-flex items-center gap-2 rounded-lg border border-cyan-200 bg-white px-5 py-3 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-50"
              >
                Internal Login
              </button>
              <button
                type="button"
                onClick={() => navigate("/candidate/access")}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
              >
                Candidate Access
              </button>
            </div>
            <p className="mt-4 text-xs text-slate-700">
              Candidate onboarding is invitation-based. New organizations can create an organization administrator account, then continue
              with subscription and onboarding setup.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-lg">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
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

      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold sm:text-3xl">Who This Portal Serves</h2>
          <p className="mt-2 text-sm text-slate-700">
            Role-aware entry points for agencies, invited nominees, and public transparency consumers.
          </p>
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {audienceCards.map((card) => (
            <article
              key={card.title}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="mb-4 inline-flex rounded-lg bg-cyan-50 p-2 text-cyan-700">
                <card.icon className="h-5 w-5" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">{card.title}</h3>
              <p className="mt-2 text-sm text-slate-700">{card.description}</p>
              {card.title === "Public Observer" ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleOpenTransparencyPortal}
                    className="inline-flex rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-100"
                  >
                    Open Transparency Portal
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenGazetteFeed}
                    className="inline-flex rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
                  >
                    Browse Gazette Feed
                  </button>
                  <button
                    type="button"
                    onClick={handleOpenPublishedAppointments}
                    className="inline-flex rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-800 transition hover:bg-indigo-100"
                  >
                    Search Published Appointments
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold sm:text-3xl">Core Capabilities</h2>
            <p className="mt-2 text-sm text-slate-700">
              Built for high-volume vetting workflows and appointment governance with AI + human review.
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
              <p className="mt-2 text-sm text-slate-700">{card.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-2">
          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-slate-900">Government Workflow Preview</h2>
            <ul className="mt-4 space-y-3">
              {workflowSteps.map((step) => (
                <li key={step} className="flex items-start gap-3 text-sm text-slate-700">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-bold text-slate-900">Governance and Security</h2>
            <div className="mt-4 space-y-4">
              {governanceHighlights.map((item) => (
                <div key={item.title} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-2 inline-flex rounded-md bg-cyan-100 p-1.5 text-cyan-800">
                    <item.icon className="h-4 w-4" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                  <p className="mt-1 text-sm text-slate-700">{item.description}</p>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={handleOpenTransparencyPortal}
              className="mt-5 inline-flex text-sm font-semibold text-cyan-700 hover:text-cyan-800"
            >
              Open public transparency portal
            </button>
          </article>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} CAVP Platform</p>
          <a
            href="mailto:support@cavp.local"
            className="font-medium text-cyan-700 hover:text-cyan-800"
          >
            support@cavp.local
          </a>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;


