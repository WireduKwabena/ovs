// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

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
      </Routes>
    </MemoryRouter>,
  );

describe("HomePage Get Started flow", () => {
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
});
