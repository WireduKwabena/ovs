// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import PublicGazettePage from "./PublicGazettePage";

const mocks = vi.hoisted(() => ({
  listPublicTransparencyGazetteFeed: vi.fn(),
  listPublicGazetteFeed: vi.fn(),
}));

vi.mock("@/services/government.service", () => ({
  governmentService: {
    listPublicTransparencyGazetteFeed: mocks.listPublicTransparencyGazetteFeed,
    listPublicGazetteFeed: mocks.listPublicGazetteFeed,
  },
}));

const renderPage = (route = "/gazette") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/gazette" element={<PublicGazettePage />} />
      </Routes>
    </MemoryRouter>,
  );

const renderPageWithLocationProbe = (route = "/gazette") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="/gazette"
          element={
            <>
              <PublicGazettePage />
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

describe("PublicGazettePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hydrates gazette filters from the URL query string and calls the public endpoint with them", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockResolvedValue([
      {
        id: "gazette-1",
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

    renderPage("/gazette?search=finance&status=appointed");

    await waitFor(() => {
      expect(mocks.listPublicTransparencyGazetteFeed).toHaveBeenLastCalledWith({
        ordering: "-published_at",
        search: "finance",
        status: "appointed",
      });
    });

    expect(
      (screen.getByLabelText(/search gazette feed/i) as HTMLInputElement).value,
    ).toBe("finance");
    expect(
      (screen.getByLabelText(/^status$/i) as HTMLSelectElement).value,
    ).toBe("appointed");
    expect(
      await screen.findByText(
        /showing gazette records matching "finance" with status appointed\./i,
      ),
    ).toBeTruthy();
    expect(await screen.findByText(/minister of finance/i)).toBeTruthy();
  });

  it("writes and clears gazette filters in the URL query string", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockResolvedValue([]);

    renderPageWithLocationProbe();

    await screen.findByText(/government gazette feed/i);

    fireEvent.change(screen.getByLabelText(/search gazette feed/i), {
      target: { value: "justice" },
    });
    fireEvent.change(screen.getByLabelText(/^status$/i), {
      target: { value: "appointed" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await screen.findByText(
      "Location search: ?search=justice&status=appointed",
    );

    fireEvent.click(screen.getByRole("button", { name: /^clear$/i }));

    await screen.findByText("Location search: (none)");
  });

  it("applies the same filters when falling back to the legacy gazette feed", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockRejectedValue(
      new Error("modern feed unavailable"),
    );
    mocks.listPublicGazetteFeed.mockResolvedValue([
      {
        id: "gazette-1",
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
      {
        id: "gazette-2",
        position_title: "Minister of Trade",
        institution: "Ministry of Trade",
        nominee_name: "John Doe",
        nominated_by_display: "President",
        nominated_by_org: "Presidency",
        nomination_date: "2026-03-02",
        appointment_date: "2026-03-11",
        gazette_number: "GZ-13",
        gazette_date: "2026-03-13",
        status: "serving",
        publication_status: "published",
        publication_reference: "PUB-002",
        published_at: "2026-03-13T10:00:00Z",
      },
    ]);

    renderPage("/gazette?search=finance&status=appointed");

    expect(await screen.findByText(/minister of finance/i)).toBeTruthy();
    expect(screen.queryByText(/minister of trade/i)).toBeNull();
    expect(mocks.listPublicGazetteFeed).toHaveBeenCalledTimes(1);
  });

  it("preserves active filters on the transparency portal link", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockResolvedValue([]);

    renderPage("/gazette?search=finance&status=appointed");

    await screen.findByText(/government gazette feed/i);

    expect(
      screen
        .getByRole("link", { name: /^transparency portal$/i })
        .getAttribute("href"),
    ).toBe("/transparency?search=finance&status=appointed");
  });

  it("preserves active filters on published detail links", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockResolvedValue([
      {
        id: "gazette-1",
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

    renderPage("/gazette?search=finance&status=appointed");

    expect(
      (
        await screen.findByRole("link", { name: /open published detail/i })
      ).getAttribute("href"),
    ).toBe(
      "/transparency/appointments/gazette-1?search=finance&status=appointed",
    );
  });

  it("shows next-step actions when filtered gazette results are empty", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockResolvedValue([]);

    renderPage("/gazette?search=finance&status=appointed");

    expect(
      await screen.findByText(
        /no gazette records match the current filters\./i,
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /clear gazette filters/i }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: /switch to transparency portal/i })
        .getAttribute("href"),
    ).toBe("/transparency?search=finance&status=appointed");
  });

  it("shows recovery actions when the gazette feed cannot be loaded", async () => {
    mocks.listPublicTransparencyGazetteFeed.mockRejectedValue(
      new Error("modern feed unavailable"),
    );
    mocks.listPublicGazetteFeed.mockRejectedValue(
      new Error("Gazette service offline."),
    );

    renderPage("/gazette?search=finance&status=appointed");

    expect(await screen.findByText(/modern feed unavailable/i)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /retry gazette load/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /clear gazette filters/i }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: /open transparency portal/i })
        .getAttribute("href"),
    ).toBe("/transparency?search=finance&status=appointed");
  });
});
