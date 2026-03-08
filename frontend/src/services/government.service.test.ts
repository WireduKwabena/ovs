import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
    post: apiPostMock,
  },
}));

import { GovernmentServiceError, governmentService, isRecentAuthRequiredError } from "./government.service";

describe("governmentService stage/publication API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes paginated approval stage template payloads", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        count: 1,
        results: [
          {
            id: "template-1",
            name: "Ministerial Standard",
            exercise_type: "ministerial",
            created_by: "user-1",
            created_at: "2026-03-01T00:00:00Z",
            stages: [],
          },
        ],
      },
    });

    const rows = await governmentService.listApprovalStageTemplates({
      exercise_type: "ministerial",
    });

    expect(apiGetMock).toHaveBeenCalledWith("/appointments/stage-templates/", {
      params: { exercise_type: "ministerial" },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: "template-1", exercise_type: "ministerial" });
  });

  it("sends stage-aware payload when advancing appointment lifecycle", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        id: "appointment-1",
        status: "committee_review",
      },
    });

    await governmentService.advanceAppointmentStage("appointment-1", {
      status: "committee_review",
      stage_id: "stage-2",
      reason_note: "COMMITTEE_APPROVED: quorum reached",
      evidence_links: ["https://records.gov/doc/1"],
    });

    expect(apiPostMock).toHaveBeenCalledWith(
      "/appointments/records/appointment-1/advance-stage/",
      {
        status: "committee_review",
        stage_id: "stage-2",
        reason_note: "COMMITTEE_APPROVED: quorum reached",
        evidence_links: ["https://records.gov/doc/1"],
      },
    );
  });

  it("sends appoint payload with optional stage context and evidence links", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        id: "appointment-2",
        status: "appointed",
      },
    });

    await governmentService.appoint("appointment-2", {
      stage_id: "stage-final",
      reason_note: "appointing authority decision",
      evidence_links: ["https://records.gov/final-memo"],
    });

    expect(apiPostMock).toHaveBeenCalledWith(
      "/appointments/records/appointment-2/appoint/",
      {
        stage_id: "stage-final",
        reason_note: "appointing authority decision",
        evidence_links: ["https://records.gov/final-memo"],
      },
    );
  });

  it("calls publication endpoint and returns publication state", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        id: "publication-1",
        appointment: "appointment-3",
        status: "published",
      },
    });

    const publication = await governmentService.publishAppointment("appointment-3", {
      publication_reference: "GAZ-2026-110",
      publication_document_hash: "a".repeat(64),
      gazette_number: "GN-77",
      gazette_date: "2026-03-05",
    });

    expect(apiPostMock).toHaveBeenCalledWith("/appointments/records/appointment-3/publish/", {
      publication_reference: "GAZ-2026-110",
      publication_document_hash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      gazette_number: "GN-77",
      gazette_date: "2026-03-05",
    });
    expect(publication).toMatchObject({ id: "publication-1", status: "published" });
  });

  it("returns public gazette feed arrays as-is", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: [
        {
          id: "appointment-public-1",
          position_title: "Minister of Justice",
          institution: "Ministry of Justice",
          nominee_name: "Jane Doe",
          nominated_by_display: "President",
          nominated_by_org: "Office of the President",
          appointment_date: "2026-03-05",
          gazette_number: "GN-77",
          gazette_date: "2026-03-05",
          status: "appointed",
          publication_status: "published",
          publication_reference: "GAZ-2026-110",
          published_at: "2026-03-05T10:00:00Z",
        },
      ],
    });

    const rows = await governmentService.listPublicGazetteFeed();

    expect(apiGetMock).toHaveBeenCalledWith("/appointments/records/gazette-feed/");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: "appointment-public-1", publication_status: "published" });
  });

  it("detects RECENT_AUTH_REQUIRED responses for sensitive actions", async () => {
    apiPostMock.mockRejectedValueOnce({
      response: {
        status: 403,
        data: {
          detail: {
            code: "RECENT_AUTH_REQUIRED",
            error: "Recent authentication is required for this action.",
          },
        },
      },
    });

    let capturedError: unknown = null;
    try {
      await governmentService.publishAppointment("appointment-4", {
        publication_reference: "GAZ-2026-111",
      });
    } catch (error) {
      capturedError = error;
    }

    expect(capturedError).toBeInstanceOf(GovernmentServiceError);
    expect((capturedError as GovernmentServiceError).code).toBe("RECENT_AUTH_REQUIRED");
    expect((capturedError as GovernmentServiceError).status).toBe(403);
    expect(isRecentAuthRequiredError(capturedError)).toBe(true);
  });

  it("does not mark unrelated failures as recent-auth errors", () => {
    const genericError = {
      response: {
        status: 400,
        data: {
          error: "invalid_transition",
        },
      },
    };
    expect(isRecentAuthRequiredError(genericError)).toBe(false);
  });
});
