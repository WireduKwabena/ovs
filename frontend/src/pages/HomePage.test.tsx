// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

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
        <Route path="/organization/dashboard" element={<div>Organization Dashboard Route</div>} />
        <Route path="/workspace" element={<div>Workspace Route</div>} />
        <Route path="/candidate/access" element={<div>Candidate Access Route</div>} />
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

const LocationHashProbe = () => {
  const location = useLocation();
  return <div>Hash: {location.hash || "(none)"}</div>;
};

describe("HomePage Get Started flow", () => {
  afterEach(() => {
    cleanup();
  });

  it("routes unauthenticated users to organization bootstrap signup", () => {
    authState.isAuthenticated = false;
    authState.userType = null;
    authState.activeOrganizationId = null;
    authState.canManageActiveOrganizationGovernance = false;

    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /get started/i }));
    expect(screen.getByText("Org Signup Route")).toBeTruthy();
  });

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
    fireEvent.click(screen.getByRole("button", { name: /open transparency portal/i }));
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
});
