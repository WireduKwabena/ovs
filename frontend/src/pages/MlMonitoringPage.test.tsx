// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import MlMonitoringPage from "./MlMonitoringPage";

const mocks = vi.hoisted(() => ({
  mlMonitoringService: {
    latest: vi.fn(),
    performanceSummary: vi.fn(),
    history: vi.fn(),
  },
  downloadCsvFile: vi.fn(),
  downloadJsonFile: vi.fn(),
}));

vi.mock("@/services/mlMonitoring.service", () => ({
  mlMonitoringService: mocks.mlMonitoringService,
}));

vi.mock("@/utils/csv", () => ({
  downloadCsvFile: mocks.downloadCsvFile,
  isoDateStamp: () => "2026-03-03",
}));

vi.mock("@/utils/json", () => ({
  downloadJsonFile: mocks.downloadJsonFile,
}));

describe("MlMonitoringPage export actions", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("exports latest and history metrics in CSV/JSON", async () => {
    mocks.mlMonitoringService.latest.mockResolvedValue([
      {
        id: "metric-latest-1",
        model_name: "fraud_detector",
        model_version: "v1.2.0",
        accuracy: 0.94,
        precision: 0.93,
        recall: 0.92,
        f1_score: 0.925,
        confusion_matrix: {},
        trained_at: "2026-03-01T10:00:00.000Z",
        evaluated_at: "2026-03-03T10:00:00.000Z",
      },
    ]);
    mocks.mlMonitoringService.performanceSummary.mockResolvedValue({
      total_models: 1,
      models: {
        fraud_detector: {
          version: "v1.2.0",
          accuracy: 0.94,
          precision: 0.93,
          recall: 0.92,
          f1_score: 0.925,
          last_evaluated: "2026-03-03T10:00:00.000Z",
        },
      },
    });
    mocks.mlMonitoringService.history.mockResolvedValue([
      {
        id: "metric-history-1",
        model_name: "fraud_detector",
        model_version: "v1.1.0",
        accuracy: 0.9,
        precision: 0.89,
        recall: 0.88,
        f1_score: 0.885,
        confusion_matrix: {},
        trained_at: "2026-02-20T10:00:00.000Z",
        evaluated_at: "2026-02-21T10:00:00.000Z",
      },
    ]);

    render(
      <MemoryRouter>
        <MlMonitoringPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.mlMonitoringService.latest).toHaveBeenCalledTimes(1);
      expect(mocks.mlMonitoringService.performanceSummary).toHaveBeenCalledTimes(1);
      expect(mocks.mlMonitoringService.history).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(await screen.findByRole("button", { name: /export latest csv/i }));
    fireEvent.click(await screen.findByRole("button", { name: /export latest json/i }));
    fireEvent.click(await screen.findByRole("button", { name: /export history csv/i }));
    fireEvent.click(await screen.findByRole("button", { name: /export history json/i }));

    expect(mocks.downloadCsvFile).toHaveBeenCalledTimes(2);
    expect(mocks.downloadJsonFile).toHaveBeenCalledTimes(2);
    expect(mocks.downloadCsvFile.mock.calls.map((call) => call[2])).toEqual([
      "ml-latest-metrics-2026-03-03.csv",
      "ml-history-fraud_detector-2026-03-03.csv",
    ]);
    expect(mocks.downloadJsonFile.mock.calls.map((call) => call[1])).toEqual([
      "ml-latest-metrics-2026-03-03.json",
      "ml-history-fraud_detector-2026-03-03.json",
    ]);
  });

  it("disables export buttons when no data is returned", async () => {
    mocks.mlMonitoringService.latest.mockResolvedValue([]);
    mocks.mlMonitoringService.performanceSummary.mockResolvedValue({
      total_models: 0,
      models: {},
    });
    mocks.mlMonitoringService.history.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <MlMonitoringPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.mlMonitoringService.latest).toHaveBeenCalledTimes(1);
    });

    const latestCsvButton = await screen.findByRole("button", { name: /export latest csv/i });
    const latestJsonButton = await screen.findByRole("button", { name: /export latest json/i });
    const historyCsvButton = await screen.findByRole("button", { name: /export history csv/i });
    const historyJsonButton = await screen.findByRole("button", { name: /export history json/i });

    expect((latestCsvButton as HTMLButtonElement).disabled).toBe(true);
    expect((latestJsonButton as HTMLButtonElement).disabled).toBe(true);
    expect((historyCsvButton as HTMLButtonElement).disabled).toBe(true);
    expect((historyJsonButton as HTMLButtonElement).disabled).toBe(true);
    expect(mocks.downloadCsvFile).not.toHaveBeenCalled();
    expect(mocks.downloadJsonFile).not.toHaveBeenCalled();
  });

  it("shows active model filter and clears back to all models", async () => {
    mocks.mlMonitoringService.latest.mockResolvedValue([
      {
        id: "metric-latest-fraud",
        model_name: "fraud_detector",
        model_version: "v1.2.0",
        accuracy: 0.94,
        precision: 0.93,
        recall: 0.92,
        f1_score: 0.925,
        confusion_matrix: {},
        trained_at: "2026-03-01T10:00:00.000Z",
        evaluated_at: "2026-03-03T10:00:00.000Z",
      },
      {
        id: "metric-latest-doc",
        model_name: "document_classifier",
        model_version: "v2.0.0",
        accuracy: 0.91,
        precision: 0.9,
        recall: 0.89,
        f1_score: 0.895,
        confusion_matrix: {},
        trained_at: "2026-03-01T11:00:00.000Z",
        evaluated_at: "2026-03-03T11:00:00.000Z",
      },
    ]);
    mocks.mlMonitoringService.performanceSummary.mockResolvedValue({
      total_models: 2,
      models: {
        fraud_detector: {
          version: "v1.2.0",
          accuracy: 0.94,
          precision: 0.93,
          recall: 0.92,
          f1_score: 0.925,
          last_evaluated: "2026-03-03T10:00:00.000Z",
        },
        document_classifier: {
          version: "v2.0.0",
          accuracy: 0.91,
          precision: 0.9,
          recall: 0.89,
          f1_score: 0.895,
          last_evaluated: "2026-03-03T11:00:00.000Z",
        },
      },
    });
    mocks.mlMonitoringService.history.mockImplementation(async (modelName: string) => [
      {
        id: `metric-history-${modelName}`,
        model_name: modelName,
        model_version: "v1.0.0",
        accuracy: 0.88,
        precision: 0.87,
        recall: 0.86,
        f1_score: 0.865,
        confusion_matrix: {},
        trained_at: "2026-02-20T10:00:00.000Z",
        evaluated_at: "2026-02-21T10:00:00.000Z",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/ml-monitoring?model=document_classifier"]}>
        <MlMonitoringPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.mlMonitoringService.history).toHaveBeenCalledWith("document_classifier", 20);
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /clear model filter/i })).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: /clear model filter/i }));

    await waitFor(() => {
      expect(mocks.mlMonitoringService.history).toHaveBeenLastCalledWith("fraud_detector", 20);
    });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /clear model filter/i })).toBeNull();
    });
  });
});
