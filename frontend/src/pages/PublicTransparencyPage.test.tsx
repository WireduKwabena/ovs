// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import PublicTransparencyPage from "./PublicTransparencyPage";

const mocks = vi.hoisted(() => ({
  getPublicTransparencySummary: vi.fn(),
  listPublicTransparencyAppointments: vi.fn(),
  listPublicTransparencyOpenAppointments: vi.fn(),
  listPublicTransparencyVacantPositions: vi.fn(),
  listPublicTransparencyOfficeholders: vi.fn(),
}));

vi.mock("@/services/government.service", () => ({
  governmentService: {
    getPublicTransparencySummary: mocks.getPublicTransparencySummary,
    listPublicTransparencyAppointments: mocks.listPublicTransparencyAppointments,
    listPublicTransparencyOpenAppointments: mocks.listPublicTransparencyOpenAppointments,
    listPublicTransparencyVacantPositions: mocks.listPublicTransparencyVacantPositions,
    listPublicTransparencyOfficeholders: mocks.listPublicTransparencyOfficeholders,
  },
}));

const renderPage = (route = "/transparency") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/transparency" element={<PublicTransparencyPage />} />
      </Routes>
    </MemoryRouter>,
  );

const renderPageWithLocationProbe = (route = "/transparency") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="/transparency"
          element={
            <>
              <PublicTransparencyPage />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

const LocationProbe = () => {
  const location = useLocation();
  return <div>Location search: {location.search || "(none)"}</div>;
};

describe("PublicTransparencyPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders public transparency sections from safe public endpoints", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 5,
      open_public_appointments: 2,
      public_positions: 11,
      vacant_public_positions: 4,
      active_public_officeholders: 7,
      last_published_at: "2026-03-14T08:00:00Z",
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([
      {
        id: "appointment-1",
        position_title: "Minister of Finance",
        institution: "Ministry of Finance",
        nominee_name: "Jane Doe",
        nominated_by_display: "President",
        nominated_by_org: "Presidency",
        nomination_date: "2026-03-01",
        appointment_date: "2026-03-10",
        gazette_number: "GZ-12",
        gazette_date: "2026-03-12",
        status: "appointed",
        publication_status: "published",
        publication_reference: "PUB-001",
        published_at: "2026-03-12T10:00:00Z",
      },
    ]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([
      {
        id: "appointment-2",
        position_title: "Deputy Minister",
        institution: "Ministry of Energy",
        nominee_name: "John Doe",
        nominated_by_display: "President",
        nominated_by_org: "Presidency",
        nomination_date: "2026-03-05",
        appointment_date: null,
        gazette_number: "",
        gazette_date: null,
        status: "committee_review",
        publication_status: "draft",
        publication_reference: "",
        published_at: null,
      },
    ]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([
      {
        id: "position-1",
        title: "Minister of Trade",
        branch: "executive",
        institution: "Ministry of Trade",
        appointment_authority: "President",
        confirmation_required: true,
        constitutional_basis: "Article 78",
        term_length_years: 4,
        is_vacant: true,
        current_holder_name: null,
      },
    ]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([
      {
        id: "person-1",
        full_name: "Alice Mensah",
        gender: "Female",
        bio_summary: "Public sector finance specialist.",
        academic_qualifications: ["MSc Public Policy"],
        is_active_officeholder: true,
      },
    ]);

    renderPage();

    expect(await screen.findByText(/government appointment transparency portal/i)).toBeTruthy();
    expect(await screen.findByText("5")).toBeTruthy();
    expect(await screen.findByText(/minister of finance/i)).toBeTruthy();
    expect(await screen.findByText(/deputy minister/i)).toBeTruthy();
    expect(await screen.findByText(/minister of trade/i)).toBeTruthy();
    expect(await screen.findByText(/alice mensah/i)).toBeTruthy();
    expect((await screen.findByRole("link", { name: /open published detail/i })).getAttribute("href")).toBe(
      "/transparency/appointments/appointment-1",
    );
  });

  it("shows a partial availability banner while still rendering available public sections", async () => {
    mocks.getPublicTransparencySummary.mockRejectedValue(new Error("summary unavailable"));
    mocks.listPublicTransparencyAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([
      {
        id: "person-2",
        full_name: "Kofi Owusu",
        gender: "Male",
        bio_summary: "Current officeholder.",
        academic_qualifications: [],
        is_active_officeholder: true,
      },
    ]);

    renderPage();

    expect(
      await screen.findByText(/some public transparency sections are temporarily unavailable: summary\./i),
    ).toBeTruthy();
    expect(await screen.findByText(/kofi owusu/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry transparency load/i })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /browse gazette feed/i }).some((link) => link.getAttribute("href") === "/gazette")).toBe(
      true,
    );
  });

  it("applies published appointment filters through the public search controls", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 1,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments
      .mockResolvedValueOnce([
        {
          id: "appointment-1",
          position_title: "Minister of Finance",
          institution: "Ministry of Finance",
          nominee_name: "Jane Doe",
          nominated_by_display: "President",
          nominated_by_org: "Presidency",
          nomination_date: "2026-03-01",
          appointment_date: "2026-03-10",
          gazette_number: "GZ-12",
          gazette_date: "2026-03-12",
          status: "appointed",
          publication_status: "published",
          publication_reference: "PUB-001",
          published_at: "2026-03-12T10:00:00Z",
        },
      ])
      .mockResolvedValueOnce([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText(/minister of finance/i)).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/search published appointments/i), {
      target: { value: "finance" },
    });
    fireEvent.change(screen.getByLabelText(/^status$/i), {
      target: { value: "appointed" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await waitFor(() => {
      expect(mocks.listPublicTransparencyAppointments).toHaveBeenLastCalledWith({
        ordering: "-published_at",
        search: "finance",
        status: "appointed",
      });
    });

    expect(await screen.findByText(/showing published appointments matching "finance" with status appointed\./i)).toBeTruthy();
    expect(await screen.findByText(/no published appointments match the current filters\./i)).toBeTruthy();
  });

  it("hydrates published appointment filters from the URL query string", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 0,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPage("/transparency?search=justice&status=appointed");

    await waitFor(() => {
      expect(mocks.listPublicTransparencyAppointments).toHaveBeenLastCalledWith({
        ordering: "-published_at",
        search: "justice",
        status: "appointed",
      });
    });

    expect((screen.getByLabelText(/search published appointments/i) as HTMLInputElement).value).toBe("justice");
    expect((screen.getByLabelText(/^status$/i) as HTMLSelectElement).value).toBe("appointed");
    expect(await screen.findByText(/showing published appointments matching "justice" with status appointed\./i)).toBeTruthy();
  });

  it("writes and clears published appointment filters in the URL query string", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 0,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPageWithLocationProbe();

    await screen.findByText(/government appointment transparency portal/i);

    fireEvent.change(screen.getByLabelText(/search published appointments/i), {
      target: { value: "finance" },
    });
    fireEvent.change(screen.getByLabelText(/^status$/i), {
      target: { value: "appointed" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await screen.findByText("Location search: ?search=finance&status=appointed");

    fireEvent.click(screen.getByRole("button", { name: /^clear$/i }));

    await screen.findByText("Location search: (none)");
  });

  it("preserves active published filters on gazette links", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 0,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPage("/transparency?search=finance&status=appointed");

    await screen.findByText(/government appointment transparency portal/i);

    expect(screen.getByRole("link", { name: /^gazette feed$/i }).getAttribute("href")).toBe(
      "/gazette?search=finance&status=appointed",
    );
    expect(screen.getByRole("link", { name: /view full gazette/i }).getAttribute("href")).toBe(
      "/gazette?search=finance&status=appointed",
    );
  });

  it("preserves active filters on published detail links", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 1,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([
      {
        id: "appointment-1",
        position_title: "Minister of Finance",
        institution: "Ministry of Finance",
        nominee_name: "Jane Doe",
        nominated_by_display: "President",
        nominated_by_org: "Presidency",
        nomination_date: "2026-03-01",
        appointment_date: "2026-03-10",
        gazette_number: "GZ-12",
        gazette_date: "2026-03-12",
        status: "appointed",
        publication_status: "published",
        publication_reference: "PUB-001",
        published_at: "2026-03-12T10:00:00Z",
      },
    ]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPage("/transparency?search=finance&status=appointed");

    expect((await screen.findByRole("link", { name: /open published detail/i })).getAttribute("href")).toBe(
      "/transparency/appointments/appointment-1?search=finance&status=appointed",
    );
  });

  it("shows next-step actions when filtered published results are empty", async () => {
    mocks.getPublicTransparencySummary.mockResolvedValue({
      published_appointments: 0,
      open_public_appointments: 0,
      public_positions: 0,
      vacant_public_positions: 0,
      active_public_officeholders: 0,
      last_published_at: null,
    });
    mocks.listPublicTransparencyAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyOpenAppointments.mockResolvedValue([]);
    mocks.listPublicTransparencyVacantPositions.mockResolvedValue([]);
    mocks.listPublicTransparencyOfficeholders.mockResolvedValue([]);

    renderPage("/transparency?search=finance&status=appointed");

    expect(await screen.findByText(/no published appointments match the current filters\./i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /clear published filters/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /check gazette feed instead/i }).getAttribute("href")).toBe(
      "/gazette?search=finance&status=appointed",
    );
  });
});
