// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PublicAppointmentDetailPage from "./PublicAppointmentDetailPage";

const mocks = vi.hoisted(() => ({
  getPublicTransparencyAppointmentDetail: vi.fn(),
}));

vi.mock("@/services/government.service", () => ({
  governmentService: {
    getPublicTransparencyAppointmentDetail: mocks.getPublicTransparencyAppointmentDetail,
  },
}));

const renderAt = (route: string) =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/transparency/appointments/:appointmentId" element={<PublicAppointmentDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("PublicAppointmentDetailPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders published appointment detail from the public endpoint", async () => {
    mocks.getPublicTransparencyAppointmentDetail.mockResolvedValue({
      id: "appointment-9",
      position_title: "Minister of Justice",
      institution: "Ministry of Justice",
      nominee_name: "Ama Boateng",
      nominated_by_display: "President",
      nominated_by_org: "Presidency",
      nomination_date: "2026-02-10",
      appointment_date: "2026-02-28",
      gazette_number: "GZ-77",
      gazette_date: "2026-03-01",
      status: "appointed",
      publication_status: "published",
      publication_reference: "PUB-009",
      published_at: "2026-03-01T09:30:00Z",
    });

    renderAt("/transparency/appointments/appointment-9");

    expect(await screen.findByText(/public appointment detail/i)).toBeTruthy();
    expect(await screen.findByText(/minister of justice/i)).toBeTruthy();
    expect(await screen.findByText(/ama boateng/i)).toBeTruthy();
    expect(await screen.findByText(/pub-009/i)).toBeTruthy();
    expect(await screen.findByText(/gazette number:/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /back to published appointments/i }).getAttribute("href")).toBe(
      "/transparency#published-appointments",
    );
    expect(mocks.getPublicTransparencyAppointmentDetail).toHaveBeenCalledWith("appointment-9");
  });

  it("shows a safe error message when the published detail cannot be loaded", async () => {
    mocks.getPublicTransparencyAppointmentDetail.mockRejectedValue(new Error("Published appointment not found."));

    renderAt("/transparency/appointments/missing-record?search=justice&status=appointed");

    expect(await screen.findByText(/published appointment not found\./i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry detail load/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /back to filtered results/i }).getAttribute("href")).toBe(
      "/transparency?search=justice&status=appointed#published-appointments",
    );
    expect(screen.getByRole("link", { name: /open gazette feed/i }).getAttribute("href")).toBe(
      "/gazette?search=justice&status=appointed",
    );
  });

  it("preserves current public filters on return links", async () => {
    mocks.getPublicTransparencyAppointmentDetail.mockResolvedValue({
      id: "appointment-9",
      position_title: "Minister of Justice",
      institution: "Ministry of Justice",
      nominee_name: "Ama Boateng",
      nominated_by_display: "President",
      nominated_by_org: "Presidency",
      nomination_date: "2026-02-10",
      appointment_date: "2026-02-28",
      gazette_number: "GZ-77",
      gazette_date: "2026-03-01",
      status: "appointed",
      publication_status: "published",
      publication_reference: "PUB-009",
      published_at: "2026-03-01T09:30:00Z",
    });

    renderAt("/transparency/appointments/appointment-9?search=justice&status=appointed");

    await screen.findByText(/public appointment detail/i);

    expect(screen.getByRole("link", { name: /back to filtered results/i }).getAttribute("href")).toBe(
      "/transparency?search=justice&status=appointed#published-appointments",
    );
    expect(screen.getByRole("link", { name: /transparency portal/i }).getAttribute("href")).toBe(
      "/transparency?search=justice&status=appointed#published-appointments",
    );
    expect(screen.getByRole("link", { name: /gazette feed/i }).getAttribute("href")).toBe(
      "/gazette?search=justice&status=appointed",
    );
  });
});
