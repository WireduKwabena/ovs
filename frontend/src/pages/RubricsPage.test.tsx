// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { RubricsPage } from "./RubricsPage";

const authState = vi.hoisted(() => ({
  canManageRubrics: false,
}));

const serviceMocks = vi.hoisted(() => ({
  getAll: vi.fn(),
  delete: vi.fn(),
  duplicate: vi.fn(),
  activate: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/services/rubric.service", () => ({
  rubricService: {
    getAll: serviceMocks.getAll,
    delete: serviceMocks.delete,
    duplicate: serviceMocks.duplicate,
    activate: serviceMocks.activate,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

const sampleRubric = {
  id: "rubric-1",
  name: "Leadership Assessment",
  description: "Measures leadership evidence",
  rubric_type: "government",
  department: "Appointments",
  status: "draft",
  passing_score: 70,
  criteria: [],
  created_at: "2026-03-01T00:00:00Z",
};

describe("RubricsPage authz visibility", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authState.canManageRubrics = false;
  });

  it("renders read-only rubric view when management permission is missing", async () => {
    serviceMocks.getAll.mockResolvedValue([sampleRubric]);

    render(
      <MemoryRouter>
        <RubricsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.getAll).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/read-only rubric access/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /create rubric/i })).toBeNull();
    expect(screen.queryByTitle(/edit rubric details and criteria/i)).toBeNull();
  });

  it("shows rubric management controls for authorized actors", async () => {
    authState.canManageRubrics = true;
    serviceMocks.getAll.mockResolvedValue([sampleRubric]);

    render(
      <MemoryRouter>
        <RubricsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.getAll).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByRole("button", { name: /create rubric/i })).toBeTruthy();
    expect(screen.getByTitle(/edit rubric details and criteria/i)).toBeTruthy();
  });
});
