import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
    post: apiPostMock,
  },
}));

import { applicationService } from "./application.service";

describe("applicationService payload normalization", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes backend case/document shape for detail responses", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        id: "case-1",
        case_id: "VET-20260310-AAAAAA",
        applicant: "user-1",
        applicant_email: "nominee@example.gov",
        position_applied: "Director General",
        status: "document_analysis",
        priority: "high",
        created_at: "2026-03-10T09:00:00Z",
        updated_at: "2026-03-10T10:00:00Z",
        documents: [
          {
            id: "doc-1",
            document_type: "passport",
            original_filename: "passport.pdf",
            file_size: 1234,
            status: "queued",
            uploaded_at: "2026-03-10T09:30:00Z",
            verification_result: {
              id: "vr-1",
              authenticity_score: 96.2,
              authenticity_confidence: 93.4,
              is_authentic: true,
              ocr_text: "example",
            },
          },
        ],
      },
    });

    const payload = await applicationService.getById("VET-20260310-AAAAAA");

    expect(apiGetMock).toHaveBeenCalledWith("/applications/cases/VET-20260310-AAAAAA/");
    expect(payload.application_type).toBe("employment");
    expect(typeof payload.applicant).toBe("object");
    expect(payload.applicant_email).toBe("nominee@example.gov");
    expect(payload.documents[0]).toMatchObject({
      file_name: "passport.pdf",
      status: "queued",
      verification_status: "queued",
      upload_date: "2026-03-10T09:30:00Z",
      ai_confidence_score: 93.4,
    });
  });

  it("wraps plain upload response document into expected envelope", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        id: "doc-2",
        document_type: "id_card",
        original_filename: "id-card.png",
        file_size: 2048,
        status: "uploaded",
        uploaded_at: "2026-03-10T11:00:00Z",
      },
    });

    const result = await applicationService.uploadDocument("case-2", new File(["x"], "id-card.png"), "id_card");

    expect(apiPostMock).toHaveBeenCalledOnce();
    expect(result.document).toMatchObject({
      id: "doc-2",
      file_name: "id-card.png",
      status: "uploaded",
      verification_status: "uploaded",
    });
  });
});
