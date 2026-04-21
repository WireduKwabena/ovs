// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import FraudInsightsPage from "./FraudInsightsPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const emptyStats = {
  total_scans: 0,
  fraud_detected: 0,
  fraud_rate: 0,
  risk_distribution: { HIGH: 0, MEDIUM: 0, LOW: 0 },
};

const emptyConsistencyStats = {
  total_checks: 0,
  consistent_count: 0,
  consistency_rate: 0,
  average_score: 0,
  median_score: 0,
};

const emptySocialStats = {
  total_checks: 0,
  manual_review_count: 0,
  manual_review_rate: 0,
  average_score: 0,
  risk_distribution: { HIGH: 0, MEDIUM: 0, LOW: 0 },
};

const mocks = vi.hoisted(() => ({
  listFraudResults: vi.fn(),
  getFraudStatistics: vi.fn(),
  listConsistencyResults: vi.fn(),
  getConsistencyStatistics: vi.fn(),
  listSocialProfileResults: vi.fn(),
  getSocialProfileStatistics: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/fraud.service", () => ({
  fraudService: {
    listFraudResults: mocks.listFraudResults,
    getFraudStatistics: mocks.getFraudStatistics,
    listConsistencyResults: mocks.listConsistencyResults,
    getConsistencyStatistics: mocks.getConsistencyStatistics,
    listSocialProfileResults: mocks.listSocialProfileResults,
    getSocialProfileStatistics: mocks.getSocialProfileStatistics,
  },
}));

vi.mock("react-toastify", () => ({
  toast: { error: mocks.toastError },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const setupSuccessfulLoad = () => {
  mocks.listFraudResults.mockResolvedValue([]);
  mocks.getFraudStatistics.mockResolvedValue(emptyStats);
  mocks.listConsistencyResults.mockResolvedValue([]);
  mocks.getConsistencyStatistics.mockResolvedValue(emptyConsistencyStats);
  mocks.listSocialProfileResults.mockResolvedValue([]);
  mocks.getSocialProfileStatistics.mockResolvedValue(emptySocialStats);
};

const setupFailingLoad = () => {
  mocks.listFraudResults.mockRejectedValue(new Error("Server error"));
  mocks.getFraudStatistics.mockRejectedValue(new Error("Server error"));
  mocks.listConsistencyResults.mockRejectedValue(new Error("Server error"));
  mocks.getConsistencyStatistics.mockRejectedValue(new Error("Server error"));
  mocks.listSocialProfileResults.mockRejectedValue(new Error("Server error"));
  mocks.getSocialProfileStatistics.mockRejectedValue(new Error("Server error"));
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <FraudInsightsPage />
    </MemoryRouter>,
  );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FraudInsightsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows loading state on initial render before data arrives", () => {
    // Use a promise that never resolves so the component stays in loading state
    mocks.listFraudResults.mockReturnValue(new Promise(() => {}));
    mocks.getFraudStatistics.mockReturnValue(new Promise(() => {}));
    mocks.listConsistencyResults.mockReturnValue(new Promise(() => {}));
    mocks.getConsistencyStatistics.mockReturnValue(new Promise(() => {}));
    mocks.listSocialProfileResults.mockReturnValue(new Promise(() => {}));
    mocks.getSocialProfileStatistics.mockReturnValue(new Promise(() => {}));

    renderPage();
    expect(screen.getByText(/loading insights/i)).toBeTruthy();
  });

  it("renders the page heading and result sections after successful load", async () => {
    setupSuccessfulLoad();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/loading insights/i)).toBeNull();
    });

    expect(screen.getByText(/fraud & consistency insights/i)).toBeTruthy();
    expect(screen.getByText("Fraud Results")).toBeTruthy();
    expect(screen.getByText("Consistency Results")).toBeTruthy();
    expect(screen.getByText("Social Profile Results")).toBeTruthy();
  });

  it("shows an error message when the API call fails", async () => {
    setupFailingLoad();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/loading insights/i)).toBeNull();
    });

    // The component renders the error message inline (the Error.message from our mock)
    expect(screen.getByText(/server error/i)).toBeTruthy();
  });

  it("calls all six fraud service methods on mount", async () => {
    setupSuccessfulLoad();
    renderPage();

    await waitFor(() => {
      expect(mocks.listFraudResults).toHaveBeenCalledTimes(1);
    });

    expect(mocks.getFraudStatistics).toHaveBeenCalledTimes(1);
    expect(mocks.listConsistencyResults).toHaveBeenCalledTimes(1);
    expect(mocks.getConsistencyStatistics).toHaveBeenCalledTimes(1);
    expect(mocks.listSocialProfileResults).toHaveBeenCalledTimes(1);
    expect(mocks.getSocialProfileStatistics).toHaveBeenCalledTimes(1);
  });
});
