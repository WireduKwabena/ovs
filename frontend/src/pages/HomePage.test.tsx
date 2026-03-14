// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { ThemeProvider } from "@/hooks/useTheme";
import HomePage from "./HomePage";

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  userType: null as "applicant" | "internal" | "admin" | null,
  activeOrganizationId: null as string | null,
  canManageActiveOrganizationGovernance: false,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ ...authState }),
}));

const renderHome = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/organization/get-started" element={<div>Org Signup Route</div>} />
        <Route path="/login" element={<div>Login Route</div>} />
        <Route path="/organization/setup" element={<div>Organization Setup Route</div>} />
        <Route path="/admin/org/:orgId/dashboard" element={<div>Organization Dashboard Route</div>} />
        <Route path="/workspace/home" element={<div>Workspace Route</div>} />
        <Route path="/candidate/home" element={<div>Candidate Access Route</div>} />
        <Route path="/transparency" element={<div>Transparency Route</div>} />
        <Route path="/gazette" element={<div>Gazette Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

const renderHomeWithLocationProbe = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/transparency"
          element={
            <div>
              Transparency Route
              <LocationHashProbe />
            </div>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

const renderHomeAtHash = (hash: string) =>
  render(
    <MemoryRouter initialEntries={[`/${hash}`]}>
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </MemoryRouter>,
  );

const renderHomeWithTheme = () =>
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/organization/get-started" element={<div>Org Signup Route</div>} />
          <Route path="/login" element={<div>Login Route</div>} />
          <Route path="/organization/setup" element={<div>Organization Setup Route</div>} />
          <Route path="/admin/org/:orgId/dashboard" element={<div>Organization Dashboard Route</div>} />
          <Route path="/workspace/home" element={<div>Workspace Route</div>} />
          <Route path="/candidate/home" element={<div>Candidate Access Route</div>} />
          <Route path="/transparency" element={<div>Transparency Route</div>} />
          <Route path="/gazette" element={<div>Gazette Route</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );

const LocationHashProbe = () => {
  const location = useLocation();
  return <div>Hash: {location.hash || "(none)"}</div>;
};

describe("HomePage Get Started flow", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("routes unauthenticated users to organization bootstrap signup", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /get started/i }));
    expect(screen.getByText("Org Signup Route")).toBeTruthy();
  }, 10000);

  it("routes authenticated internal users without org context to organization setup", () => {
    authState.isAuthenticated = true;
    authState.userType = "internal";
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /get started/i }));
    expect(screen.getByText("Organization Setup Route")).toBeTruthy();
  });

  it("routes org-governance admins with active org to organization dashboard", () => {
    authState.isAuthenticated = true;
    authState.userType = "internal";
    authState.activeOrganizationId = "org-1";
    authState.canManageActiveOrganizationGovernance = true;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /get started/i }));
    expect(screen.getByText("Organization Dashboard Route")).toBeTruthy();
  });

  it("routes non-governance internal users with active org to shared workspace", () => {
    authState.isAuthenticated = true;
    authState.userType = "internal";
    authState.activeOrganizationId = "org-1";
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /get started/i }));
    expect(screen.getByText("Workspace Route")).toBeTruthy();
  });

  it("routes public observers to the transparency portal from the landing page", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getAllByRole("button", { name: /open transparency portal/i })[0]);
    expect(screen.getByText("Transparency Route")).toBeTruthy();
  });

  it("routes public observers to the gazette feed from the landing page", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /browse gazette feed/i }));
    expect(screen.getByText("Gazette Route")).toBeTruthy();
  });

  it("routes public observers to the published appointments section from the landing page", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHomeWithLocationProbe();
    fireEvent.click(screen.getByRole("button", { name: /search published appointments/i }));
    expect(screen.getByText("Transparency Route")).toBeTruthy();
    expect(screen.getByText("Hash: #published-appointments")).toBeTruthy();
  });

  it("smooth scrolls to homepage sections from the top navigation", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    const scrollIntoViewMock = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoViewMock;

    try {
      renderHome();
      fireEvent.click(screen.getAllByRole("button", { name: /capabilities/i })[0]);
      expect(scrollIntoViewMock).toHaveBeenCalledWith({
        behavior: "smooth",
        block: "start",
      });
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("smooth scrolls to the requested section when the homepage opens with a hash", async () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    const scrollIntoViewMock = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoViewMock;

    try {
      renderHomeAtHash("#workflow");
      await waitFor(() => {
        expect(scrollIntoViewMock).toHaveBeenCalledWith({
          behavior: "smooth",
          block: "start",
        });
      });
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("marks the requested section as active when the homepage opens with a hash", async () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    const scrollIntoViewMock = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoViewMock;

    try {
      renderHomeAtHash("#workflow");

      await waitFor(() => {
        const workflowButtons = screen.getAllByRole("button", { name: /^workflow$/i });
        expect(workflowButtons.some((button) => button.getAttribute("aria-current") === "location")).toBe(true);
      });
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("updates the active section styling when the section observer reports a new section", async () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    type ObserverEntry = { target: Element; isIntersecting: boolean; intersectionRatio: number };
    const observers: Array<{
      callback: (entries: ObserverEntry[]) => void;
      observed: Element[];
    }> = [];

    const originalIntersectionObserver = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver = class {
      private readonly entry: {
        callback: (entries: ObserverEntry[]) => void;
        observed: Element[];
      };

      constructor(
        callback: (entries: ObserverEntry[]) => void,
      ) {
        this.entry = { callback, observed: [] };
        observers.push(this.entry);
      }

      observe(element: Element) {
        this.entry.observed.push(element);
      }

      unobserve(element: Element) {
        this.entry.observed = this.entry.observed.filter((candidate) => candidate !== element);
      }

      disconnect() {
        this.entry.observed = [];
      }

      takeRecords() {
        return [];
      }
    } as unknown as typeof IntersectionObserver;

    try {
      renderHome();

      const governanceSection = screen.getByTestId("homepage-governance");
      const sectionObserver = observers.find((observer) => observer.observed.includes(governanceSection));
      expect(sectionObserver).toBeTruthy();

      sectionObserver?.callback([
        {
          target: governanceSection,
          isIntersecting: true,
          intersectionRatio: 0.72,
        },
      ]);

      await waitFor(() => {
        const governanceButtons = screen.getAllByRole("button", { name: /^governance$/i });
        expect(governanceButtons.some((button) => button.getAttribute("aria-current") === "location")).toBe(true);
      });
    } finally {
      globalThis.IntersectionObserver = originalIntersectionObserver;
    }
  });

  it("reveals homepage content blocks when the reveal observer reports them in view", async () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    const observers: Array<{
      callback: (entries: Array<{ target: Element; isIntersecting: boolean; intersectionRatio: number }>) => void;
      observed: Element[];
    }> = [];

    const originalIntersectionObserver = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver = class {
      private readonly entry: {
        callback: (entries: Array<{ target: Element; isIntersecting: boolean; intersectionRatio: number }>) => void;
        observed: Element[];
      };

      constructor(
        callback: (entries: Array<{ target: Element; isIntersecting: boolean; intersectionRatio: number }>) => void,
      ) {
        this.entry = { callback, observed: [] };
        observers.push(this.entry);
      }

      observe(element: Element) {
        this.entry.observed.push(element);
      }

      unobserve(element: Element) {
        this.entry.observed = this.entry.observed.filter((candidate) => candidate !== element);
      }

      disconnect() {
        this.entry.observed = [];
      }

      takeRecords() {
        return [];
      }
    } as unknown as typeof IntersectionObserver;

    try {
      renderHome();

      const capabilitiesHeader = screen.getByTestId("homepage-capabilities-header");
      expect(capabilitiesHeader.className).toContain("home-reveal");

      const revealObserver = observers.find((observer) => observer.observed.includes(capabilitiesHeader));
      expect(revealObserver).toBeTruthy();

      revealObserver?.callback([
        {
          target: capabilitiesHeader,
          isIntersecting: true,
          intersectionRatio: 0.68,
        },
      ]);

      await waitFor(() => {
        expect(screen.getByTestId("homepage-capabilities-header").className).toContain("home-reveal-visible");
      });
    } finally {
      globalThis.IntersectionObserver = originalIntersectionObserver;
    }
  });

  it("updates the homepage scroll progress rail as the page scroll position changes", async () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    const originalScrollY = window.scrollY;
    const scrollHeightDescriptor = Object.getOwnPropertyDescriptor(document.documentElement, "scrollHeight");
    const innerHeightDescriptor = Object.getOwnPropertyDescriptor(window, "innerHeight");

    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 2200,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 1000,
    });
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      writable: true,
      value: 0,
    });

    try {
      renderHome();

      const progressBar = screen.getByTestId("homepage-scroll-progress");
      expect(progressBar.getAttribute("style")).toContain("width: 0%");

      Object.defineProperty(window, "scrollY", {
        configurable: true,
        writable: true,
        value: 600,
      });
      fireEvent.scroll(window);

      await waitFor(() => {
        expect(progressBar.getAttribute("style")).toContain("width: 50%");
      });
    } finally {
      if (scrollHeightDescriptor) {
        Object.defineProperty(document.documentElement, "scrollHeight", scrollHeightDescriptor);
      }
      if (innerHeightDescriptor) {
        Object.defineProperty(window, "innerHeight", innerHeightDescriptor);
      }
      Object.defineProperty(window, "scrollY", {
        configurable: true,
        writable: true,
        value: originalScrollY,
      });
    }
  });

  it("renders animated floating highlights in the hero panel", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();

    const firstHighlight = screen.getByTestId("floating-highlight-1");
    const secondHighlight = screen.getByTestId("floating-highlight-2");
    const thirdHighlight = screen.getByTestId("floating-highlight-3");

    expect(firstHighlight.className).toContain("home-floating-card");
    expect(firstHighlight.className).toContain("home-floating-card-delay-0");
    expect(secondHighlight.className).toContain("home-floating-card-delay-1");
    expect(thirdHighlight.className).toContain("home-floating-card-delay-2");
  });

  it("renders the floating highlights in the mobile summary strip too", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();

    const mobileHighlightsGrid = screen.getByTestId("mobile-highlights-grid");
    expect(mobileHighlightsGrid.className).toContain("lg:hidden");

    expect(screen.getByTestId("mobile-floating-highlight-1").className).toContain("home-floating-card-delay-0");
    expect(screen.getByTestId("mobile-floating-highlight-2").className).toContain("home-floating-card-delay-1");
    expect(screen.getByTestId("mobile-floating-highlight-3").className).toContain("home-floating-card-delay-2");
  });

  it("uses tablet-friendly grids for hero summaries, audiences, and footer", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();

    const heroPillarsGrid = screen.getByTestId("hero-pillars-grid");
    const heroStatsGrid = screen.getByTestId("hero-stats-grid");
    const audienceGrid = screen.getByTestId("audience-grid");
    const footerGrid = screen.getByTestId("footer-grid");

    expect(heroPillarsGrid.className).toContain("sm:grid-cols-2");
    expect(heroPillarsGrid.className).toContain("xl:grid-cols-3");
    expect(heroStatsGrid.className).toContain("sm:grid-cols-2");
    expect(heroStatsGrid.className).toContain("xl:grid-cols-3");
    expect(audienceGrid.className).toContain("md:grid-cols-2");
    expect(audienceGrid.className).toContain("xl:grid-cols-3");
    expect(footerGrid.className).toContain("md:grid-cols-2");
    expect(footerGrid.className).toContain("lg:grid-cols-[1.2fr_0.8fr_0.8fr]");
  });

  it("renders transition dividers between the major homepage sections", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();

    expect(screen.getByTestId("homepage-section-divider-capabilities")).toBeTruthy();
    expect(screen.getByTestId("homepage-section-divider-workflow")).toBeTruthy();
    expect(screen.getByTestId("homepage-section-divider-governance")).toBeTruthy();
    expect(screen.getByTestId("homepage-section-divider-cta")).toBeTruthy();
  });

  it("updates the homepage hero surface when the theme toggle is pressed", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHomeWithTheme();

    const hero = screen.getByTestId("homepage-hero");
    const audiences = screen.getByTestId("homepage-audiences");
    const governance = screen.getByTestId("homepage-governance");
    const footer = screen.getByTestId("homepage-footer");

    expect(hero.className).toContain("bg-[linear-gradient(135deg,#f8fbff_0%,#e0f2fe_45%,#eef2ff_100%)]");
    expect(audiences.className).toContain("rgba(248,250,252,0.96)");
    expect(governance.className).toContain("rgba(255,255,255,1)");
    expect(footer.className).toContain("bg-white");

    fireEvent.click(screen.getByRole("button", { name: /switch to dark theme/i }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(screen.getByTestId("homepage-hero").className).toContain("bg-slate-950");
    expect(screen.getByTestId("homepage-audiences").className).toContain("rgba(15,23,42,0.96)");
    expect(screen.getByTestId("homepage-governance").className).toContain("rgba(2,6,23,1)");
    expect(screen.getByTestId("homepage-footer").className).toContain("bg-slate-950");
  });
});
