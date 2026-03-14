import React, { useCallback, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
import { useTheme } from "@/hooks/useTheme";

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

const topNavSections = [
  { id: "audiences", label: "Who It Serves" },
  { id: "capabilities", label: "Capabilities" },
  { id: "workflow", label: "Workflow" },
  { id: "governance", label: "Governance" },
];

const heroPillars = [
  "Invitation-based candidate access",
  "AI-assisted, human reviewed vetting",
  "Approval-ready publication workflow",
];

const heroStats = [
  { value: "4", label: "Core vetting capabilities" },
  { value: "5", label: "Appointment workflow stages" },
  { value: "3", label: "Role-aware entry paths" },
];

const floatingHighlights = [
  {
    icon: ScanLine,
    title: "Document Authenticity",
    subtitle: "OCR, tamper signals, and fraud scoring.",
    className: "left-0 top-8 md:left-6",
    animationClassName: "home-floating-card-delay-0",
  },
  {
    icon: UserCheck,
    title: "AI Interviewing",
    subtitle: "Structured transcripts and rubric intelligence.",
    className: "right-0 top-40 md:right-10",
    animationClassName: "home-floating-card-delay-1",
  },
  {
    icon: Shield,
    title: "Compliance & Audit",
    subtitle: "Traceable decisions packaged for governance.",
    className: "bottom-10 left-10 md:left-20",
    animationClassName: "home-floating-card-delay-2",
  },
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  const {
    isAuthenticated,
    userType,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const startOrganizationPath = "/organization/setup?next=%2Forganization%2Fdashboard";
  const isDarkTheme = resolvedTheme === "dark";

  const scrollToSection = useCallback((sectionId: string, options?: { updateHash?: boolean }) => {
    const element = document.getElementById(sectionId);
    if (!element) {
      return;
    }

    element.scrollIntoView({ behavior: "smooth", block: "start" });
    if (options?.updateHash === false) {
      return;
    }

    if (typeof window !== "undefined" && window.history?.replaceState) {
      window.history.replaceState(null, "", `#${sectionId}`);
    }
  }, []);

  useEffect(() => {
    const hash = location.hash.replace(/^#/, "").trim();
    if (!hash) {
      return;
    }

    scrollToSection(decodeURIComponent(hash), { updateHash: false });
  }, [location.hash, scrollToSection]);

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

  const heroSectionClassName = `relative isolate overflow-hidden transition-[background-color,color] duration-300 ${
    isDarkTheme
      ? "bg-slate-950 text-white"
      : "bg-[linear-gradient(135deg,#f8fbff_0%,#e0f2fe_45%,#eef2ff_100%)] text-slate-950"
  }`;
  const heroAuraClassName = isDarkTheme
    ? "absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.22),transparent_40%),radial-gradient(circle_at_85%_20%,rgba(139,92,246,0.2),transparent_38%),radial-gradient(circle_at_60%_80%,rgba(16,185,129,0.16),transparent_32%)]"
    : "absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.24),transparent_38%),radial-gradient(circle_at_85%_20%,rgba(99,102,241,0.18),transparent_34%),radial-gradient(circle_at_60%_80%,rgba(14,165,233,0.18),transparent_30%)]";
  const heroGridClassName = isDarkTheme
    ? "absolute inset-0 opacity-20 bg-[linear-gradient(to_right,rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-size-[64px_64px]"
    : "absolute inset-0 opacity-40 bg-[linear-gradient(to_right,rgba(15,23,42,0.07)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.07)_1px,transparent_1px)] bg-size-[64px_64px]";
  const heroHeaderClassName = `sticky top-0 z-40 border-b backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-slate-950/75"
      : "border-slate-200/80 bg-white/72 shadow-[0_18px_40px_rgba(148,163,184,0.12)]"
  }`;
  const heroNavButtonClassName = `rounded-full px-4 py-2 text-sm font-medium transition ${
    isDarkTheme
      ? "text-white/80 hover:bg-white/10 hover:text-white"
      : "text-slate-700 hover:bg-slate-900/5 hover:text-slate-950"
  }`;
  const heroMobileNavButtonClassName = `shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition ${
    isDarkTheme
      ? "border-white/15 bg-white/10 text-white/85 hover:bg-white/20 hover:text-white"
      : "border-slate-300/80 bg-white/80 text-slate-700 hover:bg-white hover:text-slate-950"
  }`;
  const heroThemeToggleClassName = isDarkTheme
    ? "border-white/15 bg-white/10 text-white hover:bg-white/20 hover:text-white"
    : "border-slate-300 bg-white/80 text-slate-700 hover:bg-white hover:text-slate-950";
  const heroEyebrowClassName = `mb-5 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.32em] ${
    isDarkTheme
      ? "border-cyan-300/30 bg-cyan-400/10 text-cyan-200"
      : "border-cyan-300/70 bg-white/80 text-cyan-800 shadow-[0_10px_24px_rgba(14,165,233,0.12)]"
  }`;
  const heroHeadingClassName = `max-w-3xl text-4xl font-black leading-[0.98] tracking-[-0.04em] sm:text-5xl lg:text-7xl ${
    isDarkTheme ? "text-white" : "text-slate-950"
  }`;
  const heroBodyClassName = `mt-6 max-w-2xl text-base leading-8 sm:text-lg ${isDarkTheme ? "text-slate-200" : "text-slate-700"}`;
  const heroSupportClassName = `mt-5 max-w-2xl text-sm ${isDarkTheme ? "text-slate-300" : "text-slate-600"}`;
  const heroPillarClassName = `rounded-2xl border px-4 py-4 backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-white/5"
      : "border-white/80 bg-white/70 shadow-[0_18px_40px_rgba(148,163,184,0.16)]"
  }`;
  const heroPillarTextClassName = `text-sm font-medium leading-6 ${isDarkTheme ? "text-slate-100" : "text-slate-900"}`;
  const heroStatCardClassName = `rounded-3xl border px-5 py-5 backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-slate-950/40 shadow-[0_18px_45px_rgba(2,6,23,0.22)]"
      : "border-slate-200/80 bg-white/72 shadow-[0_18px_45px_rgba(148,163,184,0.18)]"
  }`;
  const heroStatLabelClassName = `mt-2 text-xs font-semibold uppercase tracking-[0.24em] ${isDarkTheme ? "text-slate-300" : "text-slate-600"}`;
  const heroStageShellClassName = `absolute inset-0 rounded-[36px] border backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-white/5 shadow-[0_32px_80px_rgba(2,6,23,0.45)]"
      : "border-white/85 bg-white/52 shadow-[0_34px_80px_rgba(148,163,184,0.24)]"
  }`;
  const heroStageInsetClassName = isDarkTheme
    ? "absolute inset-10 rounded-[30px] bg-gradient-to-br from-slate-900/80 via-slate-900/30 to-cyan-400/10"
    : "absolute inset-10 rounded-[30px] bg-gradient-to-br from-white/95 via-sky-50/85 to-indigo-100/60";
  const floatingHighlightCardClassName = `home-floating-card absolute w-[250px] rounded-[28px] border p-5 backdrop-blur-2xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/15 bg-white/10 shadow-[0_24px_60px_rgba(15,23,42,0.4)]"
      : "border-white/85 bg-white/78 shadow-[0_24px_60px_rgba(148,163,184,0.24)]"
  }`;
  const floatingHighlightTitleClassName = `text-lg font-semibold ${isDarkTheme ? "text-white" : "text-slate-950"}`;
  const floatingHighlightBodyClassName = `mt-2 text-sm leading-6 ${isDarkTheme ? "text-slate-200" : "text-slate-700"}`;

  return (
    <div className="min-h-screen scroll-smooth bg-background text-foreground">
      <section data-testid="homepage-hero" className={heroSectionClassName}>
        <div className={heroAuraClassName} />
        <div className={heroGridClassName} />

        <header className={heroHeaderClassName}>
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 shadow-[0_12px_30px_rgba(59,130,246,0.35)]">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDarkTheme ? "text-cyan-200" : "text-cyan-700"}`}>AI Governance</p>
                <p className={`text-lg font-bold tracking-tight ${isDarkTheme ? "text-white" : "text-slate-950"}`}>CAVP Platform</p>
              </div>
            </div>

            <div className="hidden items-center gap-2 lg:flex">
              {topNavSections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => scrollToSection(section.id)}
                  className={heroNavButtonClassName}
                >
                  {section.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <ThemeToggle
                compact
                className={heroThemeToggleClassName}
              />
              <button
                type="button"
                onClick={handleGetStarted}
                className="rounded-full bg-linear-to-r from-cyan-400 via-blue-500 to-violet-500 px-5 py-2.5 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(59,130,246,0.35)] transition hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(59,130,246,0.45)]"
              >
                Get Started
              </button>
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:hidden lg:px-8">
          <div
            aria-label="Homepage sections"
            className="flex gap-3 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {topNavSections.map((section) => (
              <button
                key={`${section.id}-mobile`}
                type="button"
                onClick={() => scrollToSection(section.id)}
                className={heroMobileNavButtonClassName}
              >
                {section.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl items-center gap-16 px-4 py-16 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-24">
          <div className="relative z-10">
            <p className={heroEyebrowClassName}>
              Vetting and Appointment Governance
            </p>
            <h1 className={heroHeadingClassName}>
              <span className="bg-linear-to-r from-cyan-300 via-blue-300 to-violet-300 bg-clip-text text-transparent">
                AI-Assisted
              </span>{" "}
              Vetting and Government Appointments
            </h1>
            <p className={heroBodyClassName}>
              Run document verification and interview intelligence with human oversight, then manage appointment approvals,
              publication, and auditability end to end.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleGetStarted}
                className="inline-flex items-center gap-2 rounded-full bg-linear-to-r from-cyan-400 via-blue-500 to-violet-500 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(59,130,246,0.4)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_48px_rgba(59,130,246,0.5)]"
              >
                Start Organization Setup
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
            <p className={heroSupportClassName}>
              Candidate onboarding is invitation-based. New organizations can create an organization administrator account, then continue with subscription and onboarding setup.
            </p>

            <div className="mt-10 grid gap-3 sm:grid-cols-3">
              {heroPillars.map((pillar) => (
                <div
                  key={pillar}
                  className={heroPillarClassName}
                >
                  <p className={heroPillarTextClassName}>{pillar}</p>
                </div>
              ))}
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {heroStats.map((stat) => (
                <div
                  key={stat.label}
                  className={heroStatCardClassName}
                >
                  <p className="bg-linear-to-r from-cyan-300 via-blue-300 to-violet-300 bg-clip-text text-4xl font-black text-transparent">
                    {stat.value}
                  </p>
                  <p className={heroStatLabelClassName}>
                    {stat.label}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative hidden min-h-[620px] lg:block">
            <div className={heroStageShellClassName} />
            <div className={heroStageInsetClassName} />

            {floatingHighlights.map((highlight, index) => (
              <article
                key={highlight.title}
                data-testid={`floating-highlight-${index + 1}`}
                className={`${floatingHighlightCardClassName} ${highlight.animationClassName} ${highlight.className}`}
              >
                <div className="mb-3 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_12px_32px_rgba(59,130,246,0.35)]">
                  <highlight.icon className="h-5 w-5" />
                </div>
                <h2 className={floatingHighlightTitleClassName}>{highlight.title}</h2>
                <p className={floatingHighlightBodyClassName}>{highlight.subtitle}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section
        id="audiences"
        className="scroll-mt-24 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,1))] py-24 text-slate-900 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,1))] dark:text-slate-50"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-700 dark:text-cyan-300">Who This Portal Serves</p>
            <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">Role-aware entry points for agencies, nominees, and the public.</h2>
            <p className="mt-4 text-base leading-8 text-slate-600 dark:text-slate-300">
              Role-aware entry points for agencies, invited nominees, and public transparency consumers.
            </p>
          </div>

          <div className="mt-14 grid gap-6 lg:grid-cols-3">
            {audienceCards.map((card) => (
              <article
                key={card.title}
                className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.08)] transition hover:-translate-y-1 hover:shadow-[0_28px_60px_rgba(15,23,42,0.12)] dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="mb-5 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_14px_36px_rgba(59,130,246,0.32)]">
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">{card.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">{card.description}</p>
                {card.title === "Public Observer" ? (
                  <div className="mt-6 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handleOpenTransparencyPortal}
                      className="inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-100 dark:border-cyan-900 dark:bg-cyan-950/40 dark:text-cyan-200"
                    >
                      Open Transparency Portal
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenGazetteFeed}
                      className="inline-flex rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                    >
                      Browse Gazette Feed
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenPublishedAppointments}
                      className="inline-flex rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-800 transition hover:bg-indigo-100 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-200"
                    >
                      Search Published Appointments
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section
        id="capabilities"
        className="scroll-mt-24 bg-white py-24 text-slate-900 dark:bg-slate-950 dark:text-slate-50"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-700 dark:text-cyan-300">Capabilities</p>
            <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">Everything you need to vet smarter and govern decisively.</h2>
            <p className="mt-4 text-base leading-8 text-slate-600 dark:text-slate-300">
              Built for high-volume vetting workflows and appointment governance with AI + human review.
            </p>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            {capabilityCards.map((card) => (
              <article
                key={card.title}
                className="rounded-[28px] border border-slate-200 bg-slate-50 p-6 shadow-[0_14px_34px_rgba(15,23,42,0.06)] transition hover:-translate-y-1 hover:shadow-[0_24px_50px_rgba(15,23,42,0.12)] dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="mb-5 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_12px_32px_rgba(59,130,246,0.3)]">
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">{card.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">{card.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section
        id="workflow"
        className="scroll-mt-24 relative overflow-hidden bg-slate-950 py-24 text-white"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.16),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.14),transparent_35%)]" />
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200">Workflow Preview</p>
            <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">From onboarding to publication, the workflow stays structured.</h2>
            <p className="mt-4 text-base leading-8 text-slate-300">
              The platform starts with vetting readiness, then carries records into approval stages, final decisions, and public publication.
            </p>
          </div>

          <div className="mt-14 grid gap-8 xl:grid-cols-[0.95fr_1.05fr]">
            <article className="rounded-4xl border border-white/10 bg-white/5 p-7 backdrop-blur-xl">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">Operating Model</p>
              <ul className="mt-6 space-y-4">
                {processSteps.map((step) => (
                  <li key={step} className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm leading-7 text-slate-100">
                    <CheckCircle2 className="mt-1 h-4 w-4 text-emerald-300" />
                    <span>{step}</span>
                  </li>
                ))}
              </ul>
            </article>

            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {workflowSteps.map((step, index) => (
                <article
                  key={step}
                  className="rounded-[28px] border border-white/10 bg-white/5 p-6 shadow-[0_16px_40px_rgba(2,6,23,0.3)] backdrop-blur-xl xl:min-h-[210px]"
                >
                  <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 text-lg font-black text-white shadow-[0_12px_30px_rgba(59,130,246,0.35)]">
                    {index + 1}
                  </div>
                  <p className="text-sm leading-7 text-slate-100">{step}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section
        id="governance"
        className="scroll-mt-24 bg-[linear-gradient(180deg,rgba(255,255,255,1),rgba(248,250,252,0.96))] py-24 text-slate-900 dark:bg-[linear-gradient(180deg,rgba(2,6,23,1),rgba(15,23,42,0.96))] dark:text-slate-50"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
            <div className="relative overflow-hidden rounded-[36px] bg-linear-to-br from-cyan-500 via-blue-600 to-violet-700 p-8 text-white shadow-[0_28px_80px_rgba(59,130,246,0.28)]">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.22),transparent_35%),radial-gradient(circle_at_80%_80%,rgba(255,255,255,0.16),transparent_32%)]" />
              <div className="relative">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-100">Governance and Security</p>
                <h2 className="mt-4 text-4xl font-black tracking-[-0.04em]">Human authority stays in control.</h2>
                <p className="mt-4 max-w-xl text-base leading-8 text-cyan-50">
                  AI outputs help reviewers move faster, but final authority remains with the responsible human actors and the approval chain.
                </p>
                <button
                  type="button"
                  onClick={handleOpenTransparencyPortal}
                  className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/20"
                >
                  Open public transparency portal
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-4">
              {governanceHighlights.map((item) => (
                <article
                  key={item.title}
                  className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_16px_40px_rgba(15,23,42,0.08)] dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="mb-4 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_12px_30px_rgba(59,130,246,0.3)]">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-white">{item.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-slate-950 py-24 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_30%,rgba(59,130,246,0.2),transparent_35%),radial-gradient(circle_at_82%_70%,rgba(139,92,246,0.18),transparent_32%)]" />
        <div className="relative mx-auto max-w-5xl px-4 text-center sm:px-6 lg:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200">
            Ready To Start
          </p>
          <h2 className="mt-4 text-4xl font-black tracking-[-0.04em] sm:text-5xl">
            Move from vetting readiness to transparent appointment outcomes.
          </h2>
          <p className="mx-auto mt-5 max-w-3xl text-base leading-8 text-slate-300">
            Keep the same invitation-based candidate flow, AI-assisted review, and governance
            safeguards while giving public observers a clean transparency surface.
          </p>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={handleGetStarted}
              className="inline-flex items-center gap-2 rounded-full bg-linear-to-r from-cyan-400 via-blue-500 to-violet-500 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(59,130,246,0.4)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_48px_rgba(59,130,246,0.5)]"
            >
              Start Organization Setup
              <ArrowRight className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleOpenTransparencyPortal}
              className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/20"
            >
              Open Transparency Portal
            </button>
          </div>
        </div>
      </section>

      <footer className="bg-slate-950 py-14 text-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 lg:grid-cols-[1.2fr_0.8fr_0.8fr] lg:px-8">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 shadow-[0_12px_30px_rgba(59,130,246,0.35)]">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">AI Governance</p>
                <p className="text-lg font-bold">CAVP Platform</p>
              </div>
            </div>
            <p className="mt-4 max-w-md text-sm leading-7 text-slate-400">
              AI-assisted vetting and appointment governance with invitation-based access, audit-ready workflows, and public transparency outputs.
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Explore</p>
            <div className="mt-4 space-y-3">
              {topNavSections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => scrollToSection(section.id)}
                  className="block text-left text-sm text-slate-300 transition hover:text-white"
                >
                  {section.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Support</p>
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              <a href="mailto:support@cavp.local" className="block transition hover:text-white">
                support@cavp.local
              </a>
              <button
                type="button"
                onClick={handleOpenTransparencyPortal}
                className="block text-left transition hover:text-white"
              >
                Open Transparency Portal
              </button>
            </div>
          </div>
        </div>
        <div className="mx-auto mt-10 max-w-7xl border-t border-white/10 px-4 pt-6 text-sm text-slate-500 sm:px-6 lg:px-8">
          © {new Date().getFullYear()} CAVP Platform
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
