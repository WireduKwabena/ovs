// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { cleanup, render, waitFor } from "@testing-library/react";

import { ApplicationsPage } from "./ApplicationsPage";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  authState: {
    isHrOrAdmin: false,
    isApplicant: false,
    isAdmin: false,
  },
}));

vi.mock("@/hooks/useApplications", () => ({
  useApplications: () => ({
    applications: [],
    loading: false,
    refetch: mocks.refetch,
  }),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.authState,
}));

const renderPage = (route = "/applications") => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ApplicationsPage />
    </MemoryRouter>,
  );
};

describe("ApplicationsPage scope fetching", () => {
  afterEach(() => {
    cleanup();
    mocks.refetch.mockReset();
    mocks.authState.isHrOrAdmin = false;
    mocks.authState.isApplicant = false;
    mocks.authState.isAdmin = false;
  });

  it("fetches applicant scope as mine", async () => {
    mocks.authState.isApplicant = true;

    renderPage("/applications");

    await waitFor(() => {
      expect(mocks.refetch).toHaveBeenCalledWith({ scope: "mine" });
    });
  });

  it("fetches admin scope as all", async () => {
    mocks.authState.isHrOrAdmin = true;
    mocks.authState.isAdmin = true;

    renderPage("/applications");

    await waitFor(() => {
      expect(mocks.refetch).toHaveBeenCalledWith({ scope: "all" });
    });
  });

  it("fetches hr scope as assigned by default", async () => {
    mocks.authState.isHrOrAdmin = true;

    renderPage("/applications");

    await waitFor(() => {
      expect(mocks.refetch).toHaveBeenCalledWith({ scope: "assigned" });
    });
  });

  it("fetches hr scope as all when scope query is set", async () => {
    mocks.authState.isHrOrAdmin = true;

    renderPage("/applications?scope=all");

    await waitFor(() => {
      expect(mocks.refetch).toHaveBeenCalledWith({ scope: "all" });
    });
  });
});

