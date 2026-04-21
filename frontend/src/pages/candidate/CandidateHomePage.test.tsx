// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Avoid pulling in the full CandidateAccessPage dependency tree
vi.mock("../CandidateAccessPage", () => ({
  default: () => (
    <div data-testid="candidate-access-page">CandidateAccessPage</div>
  ),
}));

const { default: CandidateHomePage } = await import("./CandidateHomePage");

describe("CandidateHomePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("delegates rendering to CandidateAccessPage", () => {
    render(
      <MemoryRouter>
        <CandidateHomePage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("candidate-access-page")).toBeTruthy();
  });
});
