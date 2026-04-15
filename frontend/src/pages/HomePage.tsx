import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  getCandidatePath,
  getOrgAdminPath,
  getOrganizationSetupPath,
  getWorkspacePath,
} from "@/utils/appPaths";

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

const getHomepageScrollProgress = () => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return 0;
  }

  const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
  if (scrollableHeight <= 0) {
    return 0;
  }

  return Math.min(100, Math.max(0, (window.scrollY / scrollableHeight) * 100));
};

const getHomeSectionIdFromHash = (hash: string) => {
  const normalizedHash = hash.replace(/^#/, "").trim();
  if (!normalizedHash) {
    return null;
  }

  const decodedHash = decodeURIComponent(normalizedHash);
  return topNavSections.some((section) => section.id === decodedHash) ? decodedHash : null;
};

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  const hashSectionId = useMemo(() => getHomeSectionIdFromHash(location.hash), [location.hash]);
  const [observedSectionId, setObservedSectionId] = useState<string>(
    () => hashSectionId ?? topNavSections[0].id,
  );
  const [scrollProgress, setScrollProgress] = useState<number>(() => getHomepageScrollProgress());
  const {
    isAuthenticated,
    userType,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const startOrganizationPath = getOrganizationSetupPath("/dashboard");
  const isDarkTheme = resolvedTheme === "dark";
  const activeSectionId = hashSectionId ?? observedSectionId;

  const scrollToSection = useCallback((sectionId: string, options?: { updateHash?: boolean }) => {
    const element = document.getElementById(sectionId);
    if (!element) {
      return;
    }

    setObservedSectionId(sectionId);
    element.scrollIntoView({ behavior: "smooth", block: "start" });
    if (options?.updateHash === false) {
      return;
    }

    if (typeof window !== "undefined" && window.history?.replaceState) {
      window.history.replaceState(null, "", `#${sectionId}`);
    }
  }, []);

  useEffect(() => {
    if (!hashSectionId) {
      return;
    }

    const element = document.getElementById(hashSectionId);
    if (!element) {
      return;
    }

    element.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hashSectionId]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") {
      return;
    }

    const sectionElements = topNavSections
      .map((section) => document.getElementById(section.id))
      .filter((element): element is HTMLElement => Boolean(element));

    if (!sectionElements.length) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio);

        if (!visibleEntries.length) {
          return;
        }

          setObservedSectionId(visibleEntries[0].target.id);
      },
      {
        rootMargin: "-30% 0px -45% 0px",
        threshold: [0.2, 0.35, 0.5, 0.65],
      },
    );

    sectionElements.forEach((element) => observer.observe(element));
    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const revealElements = Array.from(document.querySelectorAll<HTMLElement>("[data-home-reveal]"));
    if (!revealElements.length) {
      return;
    }

    if (typeof IntersectionObserver === "undefined") {
      revealElements.forEach((element) => element.classList.add("home-reveal-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          entry.target.classList.add("home-reveal-visible");
          observer.unobserve(entry.target);
        });
      },
      {
        rootMargin: "0px 0px -12% 0px",
        threshold: 0.16,
      },
    );

    revealElements.forEach((element) => observer.observe(element));
    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleProgressUpdate = () => {
      setScrollProgress(getHomepageScrollProgress());
    };

    window.addEventListener("scroll", handleProgressUpdate, { passive: true });
    window.addEventListener("resize", handleProgressUpdate);

    return () => {
      window.removeEventListener("scroll", handleProgressUpdate);
      window.removeEventListener("resize", handleProgressUpdate);
    };
  }, []);

  const handleGetStarted = () => {
    if (!isAuthenticated) {
      navigate("/organization/get-started?next=%2Fsubscribe");
      return;
    }

    if (userType === "applicant") {
      navigate(getCandidatePath("home"));
      return;
    }

    if (!activeOrganizationId) {
      navigate(startOrganizationPath);
      return;
    }

    if (canManageActiveOrganizationGovernance) {
      navigate(getOrgAdminPath(activeOrganizationId, "dashboard"));
      return;
    }

    navigate(getWorkspacePath("home"));
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
    ? "home-hero-aura absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.22),transparent_40%),radial-gradient(circle_at_85%_20%,rgba(139,92,246,0.2),transparent_38%),radial-gradient(circle_at_60%_80%,rgba(16,185,129,0.16),transparent_32%)]"
    : "home-hero-aura absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.24),transparent_38%),radial-gradient(circle_at_85%_20%,rgba(99,102,241,0.18),transparent_34%),radial-gradient(circle_at_60%_80%,rgba(14,165,233,0.18),transparent_30%)]";
  const heroGridClassName = isDarkTheme
    ? "absolute inset-0 opacity-20 bg-[linear-gradient(to_right,rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-size-[64px_64px]"
    : "absolute inset-0 opacity-40 bg-[linear-gradient(to_right,rgba(15,23,42,0.07)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.07)_1px,transparent_1px)] bg-size-[64px_64px]";
  const heroHeaderClassName = `sticky top-0 z-40 border-b backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-slate-950/75"
      : "border-slate-200/80 bg-white/72 shadow-[0_18px_40px_rgba(148,163,184,0.12)]"
  }`;
  const heroNavButtonClassName = `rounded-full border border-transparent px-4 py-2 text-sm font-medium transition ${
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
  const getHeroNavButtonClassName = (sectionId: string) =>
    `${heroNavButtonClassName} ${
      activeSectionId === sectionId
        ? isDarkTheme
          ? "border-cyan-300/25 bg-[linear-gradient(135deg,rgba(34,211,238,0.18),rgba(59,130,246,0.12),rgba(167,139,250,0.16))] text-white shadow-[0_12px_28px_rgba(15,23,42,0.22)]"
          : "border-cyan-200 bg-[linear-gradient(135deg,#f0fdfa_0%,#eff6ff_52%,#eef2ff_100%)] text-slate-950 shadow-[0_12px_28px_rgba(148,163,184,0.2)]"
        : ""
    }`;
  const getHeroMobileNavButtonClassName = (sectionId: string) =>
    `${heroMobileNavButtonClassName} ${
      activeSectionId === sectionId
        ? isDarkTheme
          ? "border-cyan-300/45 bg-[linear-gradient(135deg,rgba(34,211,238,0.18),rgba(59,130,246,0.12),rgba(167,139,250,0.16))] text-white"
          : "border-cyan-400/45 bg-[linear-gradient(135deg,#ecfeff_0%,#eff6ff_52%,#eef2ff_100%)] text-cyan-900"
        : ""
    }`;
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
  const gradientSectionClassName = `scroll-mt-24 py-24 transition-[background-color,color] duration-300 ${
    isDarkTheme
      ? "bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,1))] text-slate-50"
      : "bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,1))] text-slate-900"
  }`;
  const reverseGradientSectionClassName = `scroll-mt-24 py-24 transition-[background-color,color] duration-300 ${
    isDarkTheme
      ? "bg-[linear-gradient(180deg,rgba(2,6,23,1),rgba(15,23,42,0.96))] text-slate-50"
      : "bg-[linear-gradient(180deg,rgba(255,255,255,1),rgba(248,250,252,0.96))] text-slate-900"
  }`;
  const plainSectionClassName = `scroll-mt-24 py-24 transition-[background-color,color] duration-300 ${
    isDarkTheme ? "bg-slate-950 text-slate-50" : "bg-white text-slate-900"
  }`;
  const sectionEyebrowClassName = `text-xs font-semibold uppercase tracking-[0.28em] ${
    isDarkTheme ? "text-cyan-300" : "text-cyan-700"
  }`;
  const sectionBodyClassName = `mt-4 text-base leading-8 ${isDarkTheme ? "text-slate-300" : "text-slate-600"}`;
  const sectionHeadingClassName = "mt-4 text-[2.35rem] font-black leading-[1.04] tracking-[-0.04em] md:text-[2.85rem] xl:text-[3.35rem]";
  const sectionDividerLineClassName = isDarkTheme
    ? "bg-[linear-gradient(90deg,transparent,rgba(34,211,238,0.3),rgba(129,140,248,0.32),transparent)]"
    : "bg-[linear-gradient(90deg,transparent,rgba(14,165,233,0.24),rgba(99,102,241,0.28),transparent)]";
  const sectionDividerChipClassName = isDarkTheme
    ? "border-cyan-300/20 bg-slate-900/80 text-cyan-100 shadow-[0_12px_30px_rgba(15,23,42,0.28)]"
    : "border-cyan-200/70 bg-white/90 text-slate-800 shadow-[0_12px_30px_rgba(148,163,184,0.16)]";
  const surfaceCardClassName = `rounded-[28px] border p-6 transition-[background-color,border-color,box-shadow,transform] ${
    isDarkTheme
      ? "border-slate-800 bg-slate-900 shadow-[0_18px_50px_rgba(2,6,23,0.28)] hover:-translate-y-1 hover:shadow-[0_28px_60px_rgba(2,6,23,0.34)]"
      : "border-slate-200 bg-white shadow-[0_18px_50px_rgba(15,23,42,0.08)] hover:-translate-y-1 hover:shadow-[0_28px_60px_rgba(15,23,42,0.12)]"
  }`;
  const mutedSurfaceCardClassName = `rounded-[28px] border p-6 transition-[background-color,border-color,box-shadow,transform] ${
    isDarkTheme
      ? "border-slate-800 bg-slate-900 shadow-[0_14px_34px_rgba(2,6,23,0.28)] hover:-translate-y-1 hover:shadow-[0_24px_50px_rgba(2,6,23,0.34)]"
      : "border-slate-200 bg-slate-50 shadow-[0_14px_34px_rgba(15,23,42,0.06)] hover:-translate-y-1 hover:shadow-[0_24px_50px_rgba(15,23,42,0.12)]"
  }`;
  const cardTitleClassName = `text-xl font-bold ${isDarkTheme ? "text-white" : "text-slate-900"}`;
  const cardBodyClassName = `mt-3 text-sm leading-7 ${isDarkTheme ? "text-slate-300" : "text-slate-600"}`;
  const observerCyanButtonClassName = `inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition ${
    isDarkTheme
      ? "border-cyan-900 bg-cyan-950/40 text-cyan-200 hover:bg-cyan-900/50"
      : "border-cyan-200 bg-cyan-50 text-cyan-800 hover:bg-cyan-100"
  }`;
  const observerNeutralButtonClassName = `inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition ${
    isDarkTheme
      ? "border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800"
      : "border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
  }`;
  const observerIndigoButtonClassName = `inline-flex rounded-full border px-4 py-2 text-sm font-semibold transition ${
    isDarkTheme
      ? "border-indigo-900 bg-indigo-950/40 text-indigo-200 hover:bg-indigo-900/50"
      : "border-indigo-200 bg-indigo-50 text-indigo-800 hover:bg-indigo-100"
  }`;
  const workflowSectionClassName = `scroll-mt-24 relative overflow-hidden py-24 transition-[background-color,color] duration-300 ${
    isDarkTheme
      ? "bg-slate-950 text-white"
      : "bg-[linear-gradient(180deg,rgba(239,246,255,1),rgba(224,242,254,0.88))] text-slate-950"
  }`;
  const workflowAuraClassName = isDarkTheme
    ? "absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.16),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.14),transparent_35%)]"
    : "absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.18),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(99,102,241,0.14),transparent_32%)]";
  const workflowEyebrowClassName = `text-xs font-semibold uppercase tracking-[0.28em] ${isDarkTheme ? "text-cyan-200" : "text-cyan-700"}`;
  const workflowBodyClassName = `mt-4 text-base leading-8 ${isDarkTheme ? "text-slate-300" : "text-slate-700"}`;
  const workflowOperatingCardClassName = `rounded-[2rem] border p-7 backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-white/10 bg-white/5"
      : "border-white/80 bg-white/70 shadow-[0_20px_55px_rgba(148,163,184,0.18)]"
  }`;
  const workflowListItemClassName = `flex items-start gap-3 rounded-2xl border px-4 py-4 text-sm leading-7 ${
    isDarkTheme
      ? "border-white/10 bg-white/5 text-slate-100"
      : "border-slate-200 bg-white/75 text-slate-800"
  }`;
  const workflowStepCardClassName = `rounded-[28px] border p-6 backdrop-blur-xl transition-[background-color,border-color,box-shadow] duration-300 xl:min-h-[210px] ${
    isDarkTheme
      ? "border-white/10 bg-white/5 shadow-[0_16px_40px_rgba(2,6,23,0.3)]"
      : "border-white/80 bg-white/72 shadow-[0_18px_46px_rgba(148,163,184,0.2)]"
  }`;
  const workflowStepTextClassName = `text-sm leading-7 ${isDarkTheme ? "text-slate-100" : "text-slate-800"}`;
  const governanceFeatureCardClassName = `rounded-[28px] border p-6 transition-[background-color,border-color,box-shadow] duration-300 ${
    isDarkTheme
      ? "border-slate-800 bg-slate-900 shadow-[0_16px_40px_rgba(2,6,23,0.28)]"
      : "border-slate-200 bg-white shadow-[0_16px_40px_rgba(15,23,42,0.08)]"
  }`;
  const finalCtaSectionClassName = `relative overflow-hidden py-24 transition-[background-color,color] duration-300 ${
    isDarkTheme
      ? "bg-slate-950 text-white"
      : "bg-[linear-gradient(180deg,rgba(238,242,255,1),rgba(224,231,255,0.82))] text-slate-950"
  }`;
  const finalCtaAuraClassName = isDarkTheme
    ? "absolute inset-0 bg-[radial-gradient(circle_at_18%_30%,rgba(59,130,246,0.2),transparent_35%),radial-gradient(circle_at_82%_70%,rgba(139,92,246,0.18),transparent_32%)]"
    : "absolute inset-0 bg-[radial-gradient(circle_at_18%_30%,rgba(56,189,248,0.22),transparent_35%),radial-gradient(circle_at_82%_70%,rgba(99,102,241,0.18),transparent_32%)]";
  const finalCtaEyebrowClassName = `text-xs font-semibold uppercase tracking-[0.28em] ${isDarkTheme ? "text-cyan-200" : "text-cyan-700"}`;
  const finalCtaBodyClassName = `mx-auto mt-5 max-w-3xl text-base leading-8 ${isDarkTheme ? "text-slate-300" : "text-slate-700"}`;
  const finalCtaSecondaryButtonClassName = `inline-flex items-center gap-2 rounded-full border px-6 py-3.5 text-sm font-semibold transition ${
    isDarkTheme
      ? "border-white/20 bg-white/10 text-white hover:bg-white/20"
      : "border-slate-300 bg-white/80 text-slate-900 hover:bg-white"
  }`;
  const footerClassName = `py-14 transition-[background-color,color,border-color] duration-300 ${
    isDarkTheme ? "bg-slate-950 text-white" : "border-t border-slate-200 bg-white text-slate-900"
  }`;
  const footerBrandEyebrowClassName = isDarkTheme
    ? "text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200"
    : "text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700";
  const footerBrandTitleClassName = isDarkTheme ? "text-lg font-bold text-white" : "text-lg font-bold text-slate-950";
  const footerBodyClassName = isDarkTheme ? "mt-4 max-w-md text-sm leading-7 text-slate-400" : "mt-4 max-w-md text-sm leading-7 text-slate-600";
  const footerSectionTitleClassName = isDarkTheme ? "text-sm font-semibold uppercase tracking-[0.2em] text-slate-400" : "text-sm font-semibold uppercase tracking-[0.2em] text-slate-500";
  const footerLinkClassName = isDarkTheme
    ? "block text-left text-sm text-slate-300 transition hover:text-white"
    : "block text-left text-sm text-slate-700 transition hover:text-slate-950";
  const getFooterLinkClassName = (sectionId: string) =>
    `${footerLinkClassName} ${
      activeSectionId === sectionId
        ? isDarkTheme
          ? "text-white"
          : "text-slate-950"
        : ""
    }`;
  const footerSupportGroupClassName = `mt-4 space-y-3 text-sm ${isDarkTheme ? "text-slate-300" : "text-slate-700"}`;
  const footerSupportLinkClassName = isDarkTheme ? "block transition hover:text-white" : "block transition hover:text-slate-950";
  const footerDividerClassName = `mx-auto mt-10 max-w-7xl border-t px-4 pt-6 text-sm sm:px-6 lg:px-8 ${
    isDarkTheme ? "border-white/10 text-slate-500" : "border-slate-200 text-slate-500"
  }`;
  const renderSectionDivider = (testId: string) => (
    <div data-testid={testId} aria-hidden="true" className="mb-14 flex items-center gap-4 md:mb-16">
      <div className={`h-px flex-1 ${sectionDividerLineClassName}`} />
      <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] ${sectionDividerChipClassName}`}>
        <span className="h-1.5 w-1.5 rounded-full bg-linear-to-r from-cyan-400 to-violet-500" />
        <span>Transition</span>
      </div>
      <div className={`h-px flex-1 ${sectionDividerLineClassName}`} />
    </div>
  );

  return (
    <div className="min-h-screen scroll-smooth bg-background text-foreground">
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
                  aria-current={activeSectionId === section.id ? "location" : undefined}
                  className={getHeroNavButtonClassName(section.id)}
                >
                  <span className="inline-flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`h-1.5 w-1.5 rounded-full transition ${
                        activeSectionId === section.id
                          ? "bg-current opacity-100"
                          : isDarkTheme
                            ? "bg-white/35 opacity-70"
                            : "bg-slate-400 opacity-70"
                      }`}
                    />
                    <span>{section.label}</span>
                  </span>
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
          <div
            aria-hidden="true"
            className={`h-1 w-full overflow-hidden ${
              isDarkTheme ? "bg-white/6" : "bg-slate-200/70"
            }`}
          >
            <div
              data-testid="homepage-scroll-progress"
              className="h-full rounded-full bg-linear-to-r from-cyan-400 via-blue-500 to-violet-500 transition-[width] duration-200 ease-out"
              style={{ width: `${scrollProgress}%` }}
            />
          </div>
        </header>
      <section data-testid="homepage-hero" className={heroSectionClassName}>
        <div className={heroAuraClassName} />
        <div className={heroGridClassName} />
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
                aria-current={activeSectionId === section.id ? "location" : undefined}
                className={getHeroMobileNavButtonClassName(section.id)}
              >
                <span className="inline-flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 rounded-full transition ${
                      activeSectionId === section.id
                        ? "bg-current opacity-100"
                        : isDarkTheme
                          ? "bg-white/35 opacity-70"
                          : "bg-slate-400 opacity-70"
                    }`}
                  />
                  <span>{section.label}</span>
                </span>
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

            <div data-testid="hero-pillars-grid" className="mt-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {heroPillars.map((pillar, index) => (
                <div
                  key={pillar}
                  className={`${heroPillarClassName} ${index === heroPillars.length - 1 ? "sm:col-span-2 xl:col-span-1" : ""}`}
                >
                  <p className={heroPillarTextClassName}>{pillar}</p>
                </div>
              ))}
            </div>

            <div data-testid="hero-stats-grid" className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {heroStats.map((stat, index) => (
                <div
                  key={stat.label}
                  className={`${heroStatCardClassName} ${index === heroStats.length - 1 ? "sm:col-span-2 xl:col-span-1" : ""}`}
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

            <div
              data-testid="mobile-highlights-grid"
              className="mt-10 grid gap-4 sm:grid-cols-2 lg:hidden"
            >
              {floatingHighlights.map((highlight, index) => (
                <article
                  key={`${highlight.title}-mobile`}
                  data-testid={`mobile-floating-highlight-${index + 1}`}
                  className={`${floatingHighlightCardClassName} ${highlight.animationClassName} relative inset-auto left-auto right-auto top-auto bottom-auto w-full`}
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
        data-testid="homepage-audiences"
        className={gradientSectionClassName}
      >
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div
            aria-hidden="true"
            className={`home-orb-drift pointer-events-none absolute -top-10 left-6 h-28 w-28 rounded-full blur-3xl ${
              isDarkTheme ? "bg-cyan-400/10" : "bg-cyan-300/25"
            }`}
          />
          <div
            aria-hidden="true"
            className={`home-orb-drift pointer-events-none absolute right-6 top-24 hidden h-36 w-36 rounded-full blur-3xl md:block ${
              isDarkTheme ? "bg-violet-500/10" : "bg-violet-300/25"
            }`}
          />
          <div
            data-testid="homepage-audiences-header"
            data-home-reveal
            className="home-reveal mx-auto max-w-3xl text-center"
          >
            <p className={sectionEyebrowClassName}>Who This Portal Serves</p>
            <h2 className={sectionHeadingClassName}>Role-aware entry points for agencies, nominees, and the public.</h2>
            <p className={`${sectionBodyClassName} md:text-lg`}>
              Role-aware entry points for agencies, invited nominees, and public transparency consumers.
            </p>
          </div>

          <div
            data-testid="audience-grid"
            data-home-reveal
            className="home-reveal home-reveal-delay-1 mt-14 grid gap-6 md:grid-cols-2 xl:grid-cols-3"
          >
            {audienceCards.map((card, index) => (
              <article
                key={card.title}
                className={`${surfaceCardClassName} ${index === audienceCards.length - 1 ? "md:col-span-2 xl:col-span-1" : ""}`}
              >
                <div className="mb-5 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_14px_36px_rgba(59,130,246,0.32)]">
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className={cardTitleClassName}>{card.title}</h3>
                <p className={cardBodyClassName}>{card.description}</p>
                {card.title === "Public Observer" ? (
                  <div className="mt-6 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handleOpenTransparencyPortal}
                      className={observerCyanButtonClassName}
                    >
                      Open Transparency Portal
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenGazetteFeed}
                      className={observerNeutralButtonClassName}
                    >
                      Browse Gazette Feed
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenPublishedAppointments}
                      className={observerIndigoButtonClassName}
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
        className={plainSectionClassName}
      >
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {renderSectionDivider("homepage-section-divider-capabilities")}
          <div
            aria-hidden="true"
            className={`pointer-events-none absolute inset-x-0 top-0 h-px ${
              isDarkTheme
                ? "bg-[linear-gradient(90deg,transparent,rgba(34,211,238,0.2),transparent)]"
                : "bg-[linear-gradient(90deg,transparent,rgba(14,165,233,0.25),transparent)]"
            }`}
          />
          <div
            aria-hidden="true"
            className={`home-orb-drift pointer-events-none absolute -right-6 bottom-4 hidden h-44 w-44 rounded-full blur-3xl lg:block ${
              isDarkTheme ? "bg-blue-500/10" : "bg-sky-200/40"
            }`}
          />
          <div
            data-testid="homepage-capabilities-header"
            data-home-reveal
            className="home-reveal mx-auto max-w-3xl text-center"
          >
            <p className={sectionEyebrowClassName}>Capabilities</p>
            <h2 className={sectionHeadingClassName}>Everything you need to vet smarter and govern decisively.</h2>
            <p className={`${sectionBodyClassName} md:text-lg`}>
              Built for high-volume vetting workflows and appointment governance with AI + human review.
            </p>
          </div>

          <div
            data-home-reveal
            className="home-reveal home-reveal-delay-1 mt-14 grid gap-6 md:grid-cols-2 xl:grid-cols-4"
          >
            {capabilityCards.map((card) => (
              <article
                key={card.title}
                className={mutedSurfaceCardClassName}
              >
                <div className="mb-5 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_12px_32px_rgba(59,130,246,0.3)]">
                  <card.icon className="h-5 w-5" />
                </div>
                <h3 className={cardTitleClassName}>{card.title}</h3>
                <p className={cardBodyClassName}>{card.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section
        id="workflow"
        className={workflowSectionClassName}
      >
        <div className={workflowAuraClassName} />
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {renderSectionDivider("homepage-section-divider-workflow")}
          <div
            data-testid="homepage-workflow-header"
            data-home-reveal
            className="home-reveal mx-auto max-w-3xl text-center"
          >
            <p className={workflowEyebrowClassName}>Workflow Preview</p>
            <h2 className={sectionHeadingClassName}>From onboarding to publication, the workflow stays structured.</h2>
            <p className={`${workflowBodyClassName} md:text-lg`}>
              The platform starts with vetting readiness, then carries records into approval stages, final decisions, and public publication.
            </p>
          </div>

          <div className="mt-14 grid gap-8 xl:grid-cols-[0.95fr_1.05fr]">
            <article data-home-reveal className="home-reveal home-reveal-delay-1">
              <div className={workflowOperatingCardClassName}>
                <p className={workflowEyebrowClassName}>Operating Model</p>
                <ul className="mt-6 space-y-4">
                  {processSteps.map((step) => (
                    <li key={step} className={workflowListItemClassName}>
                      <CheckCircle2 className="mt-1 h-4 w-4 text-emerald-300" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>

            <div
              data-testid="homepage-workflow-steps"
              data-home-reveal
              className="home-reveal home-reveal-delay-2 grid gap-5 md:grid-cols-2 xl:grid-cols-3"
            >
              {workflowSteps.map((step, index) => (
                <article
                  key={step}
                  className={workflowStepCardClassName}
                >
                  <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 text-lg font-black text-white shadow-[0_12px_30px_rgba(59,130,246,0.35)]">
                    {index + 1}
                  </div>
                  <p className={workflowStepTextClassName}>{step}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section
        id="governance"
        data-testid="homepage-governance"
        className={reverseGradientSectionClassName}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {renderSectionDivider("homepage-section-divider-governance")}
          <div
            data-testid="homepage-governance-grid"
            data-home-reveal
            className="home-reveal grid gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center"
          >
            <div
              className={`relative overflow-hidden rounded-[36px] p-8 shadow-[0_28px_80px_rgba(59,130,246,0.28)] transition-[background-color,box-shadow] duration-300 ${
                isDarkTheme
                  ? "bg-linear-to-br from-cyan-500 via-blue-600 to-violet-700 text-white"
                  : "bg-[linear-gradient(135deg,#ecfeff_0%,#dbeafe_52%,#ede9fe_100%)] text-slate-950 shadow-[0_26px_70px_rgba(59,130,246,0.16)]"
              }`}
            >
              <div
                className={`absolute inset-0 ${
                  isDarkTheme
                    ? "bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.22),transparent_35%),radial-gradient(circle_at_80%_80%,rgba(255,255,255,0.16),transparent_32%)]"
                    : "bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.7),transparent_34%),radial-gradient(circle_at_80%_80%,rgba(99,102,241,0.14),transparent_30%)]"
                }`}
              />
              <div className="relative">
                <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDarkTheme ? "text-cyan-100" : "text-cyan-800"}`}>Governance and Security</p>
                <h2 className={`mt-4 text-4xl font-black tracking-[-0.04em] ${isDarkTheme ? "text-white" : "text-slate-950"}`}>Human authority stays in control.</h2>
                <p className={`mt-4 max-w-xl text-base leading-8 ${isDarkTheme ? "text-cyan-50" : "text-slate-700"}`}>
                  AI outputs help reviewers move faster, but final authority remains with the responsible human actors and the approval chain.
                </p>
                <button
                  type="button"
                  onClick={handleOpenTransparencyPortal}
                  className={`mt-8 inline-flex items-center gap-2 rounded-full border px-5 py-3 text-sm font-semibold transition ${
                    isDarkTheme
                      ? "border-white/20 bg-white/10 text-white hover:bg-white/20"
                      : "border-cyan-200 bg-white/75 text-slate-900 hover:bg-white"
                  }`}
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
                  className={governanceFeatureCardClassName}
                >
                  <div className="mb-4 inline-flex rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 p-3 text-white shadow-[0_12px_30px_rgba(59,130,246,0.3)]">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <h3 className={cardTitleClassName}>{item.title}</h3>
                  <p className={cardBodyClassName}>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className={finalCtaSectionClassName}>
        <div className={finalCtaAuraClassName} />
        <div
          aria-hidden="true"
          className={`home-orb-drift pointer-events-none absolute left-8 top-10 h-24 w-24 rounded-full blur-3xl ${
            isDarkTheme ? "bg-cyan-400/15" : "bg-cyan-300/25"
          }`}
        />
        <div
          aria-hidden="true"
          className={`home-orb-drift pointer-events-none absolute bottom-12 right-10 hidden h-36 w-36 rounded-full blur-3xl md:block ${
            isDarkTheme ? "bg-violet-500/12" : "bg-indigo-300/24"
          }`}
        />
        <div
          data-testid="homepage-final-cta"
          data-home-reveal
          className="home-reveal relative mx-auto max-w-5xl px-4 text-center sm:px-6 lg:px-8"
        >
          {renderSectionDivider("homepage-section-divider-cta")}
          <p className={finalCtaEyebrowClassName}>
            Ready To Start
          </p>
          <h2 className={sectionHeadingClassName}>
            Move from vetting readiness to transparent appointment outcomes.
          </h2>
          <p className={`${finalCtaBodyClassName} md:text-lg`}>
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
              className={finalCtaSecondaryButtonClassName}
            >
              Open Transparency Portal
            </button>
          </div>
        </div>
      </section>

      <footer data-testid="homepage-footer" className={footerClassName}>
        <div
          data-testid="footer-grid"
          data-home-reveal
          className="home-reveal home-reveal-delay-1 mx-auto grid max-w-7xl gap-8 px-4 sm:px-6 md:grid-cols-2 lg:grid-cols-[1.2fr_0.8fr_0.8fr] lg:px-8"
        >
          <div className="md:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-cyan-400 via-blue-500 to-violet-500 shadow-[0_12px_30px_rgba(59,130,246,0.35)]">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className={footerBrandEyebrowClassName}>AI Governance</p>
                <p className={footerBrandTitleClassName}>CAVP Platform</p>
              </div>
            </div>
            <p className={footerBodyClassName}>
              AI-assisted vetting and appointment governance with invitation-based access, audit-ready workflows, and public transparency outputs.
            </p>
          </div>

          <div>
            <p className={footerSectionTitleClassName}>Explore</p>
            <div className="mt-4 space-y-3">
              {topNavSections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => scrollToSection(section.id)}
                  aria-current={activeSectionId === section.id ? "location" : undefined}
                  className={getFooterLinkClassName(section.id)}
                >
                  <span className="inline-flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`h-1.5 w-1.5 rounded-full transition ${
                        activeSectionId === section.id
                          ? "bg-current opacity-100"
                          : isDarkTheme
                            ? "bg-slate-500 opacity-80"
                            : "bg-slate-400 opacity-80"
                      }`}
                    />
                    <span>{section.label}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className={footerSectionTitleClassName}>Support</p>
            <div className={footerSupportGroupClassName}>
              <a href="mailto:support@cavp.local" className={footerSupportLinkClassName}>
                support@cavp.local
              </a>
              <button
                type="button"
                onClick={handleOpenTransparencyPortal}
                className={footerSupportLinkClassName}
              >
                Open Transparency Portal
              </button>
            </div>
          </div>
        </div>
        <div className={footerDividerClassName}>
          © {new Date().getFullYear()} CAVP Platform
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
