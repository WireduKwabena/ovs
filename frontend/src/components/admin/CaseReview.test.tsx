// @vitest-environment jsdom
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CaseReview } from "./CaseReview";

const getByIdMock = vi.fn();

vi.mock("@/services/application.service", () => ({
  applicationService: {
    getById: (...args: unknown[]) => getByIdMock(...args),
    update: vi.fn(),
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

describe("CaseReview", () => {
  it("renders case detail without crashing when score fields are null", async () => {
    getByIdMock.mockResolvedValueOnce({
      id: "1",
      case_id: "VET-20260306-8A650F",
      status: "pending",
      application_type: "employment",
      priority: "high",
      notes: "",
      created_at: "2026-03-06T12:00:00Z",
      updated_at: "2026-03-06T12:15:00Z",
      applicant_email: "candidate@example.com",
      applicant: {
        id: "u-1",
        full_name: "Candidate One",
        email: "candidate@example.com",
        phone_number: "",
        date_of_birth: "",
      },
      documents: [],
      consistency_score: null,
      fraud_risk_score: null,
      rubric_evaluation: null,
    });

    render(
      <MemoryRouter initialEntries={["/admin/cases/VET-20260306-8A650F"]}>
        <Routes>
          <Route path="/admin/cases/:caseId" element={<CaseReview />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getByIdMock).toHaveBeenCalledWith("VET-20260306-8A650F");
    });

    expect(await screen.findByText(/Case Review: VET-20260306-8A650F/i)).toBeTruthy();
    expect(screen.getByText("Case Summary")).toBeTruthy();
  });

  it("renders case detail with backend payload shape used by admin case API", async () => {
    getByIdMock.mockResolvedValueOnce({
      id: "c9e351ae-223a-419e-9e8e-84b5d90630e0",
      case_id: "VET-20260305-99612B",
      organization: "5b142161-9fed-4704-824c-21565b075276",
      organization_name: "Legacy Unscoped Records",
      applicant: "d4eda318-4d9b-4fdf-ba67-d39fd320b94c",
      applicant_email: "ama.mensah@example.com",
      candidate_enrollment: "06bce274-735d-4a54-8d97-4ff217567d74",
      candidate_email: "ama.mensah@example.com",
      assigned_to: "70dda22e-3dbd-44f5-a08f-0ad65fb4dd65",
      assigned_to_email: "testuser@test.com",
      position_applied: "Senior Software Engineer Candidate Vetting",
      department: "",
      job_description:
        "This campaign is to vet and employ a software engineer for our next big project",
      status: "under_review",
      priority: "medium",
      overall_score: null,
      document_authenticity_score: 92.0,
      consistency_score: 88.0,
      fraud_risk_score: 18.0,
      interview_score: null,
      red_flags_count: 0,
      requires_manual_review: false,
      notes: "",
      internal_comments: "",
      documents_uploaded: true,
      documents_verified: true,
      interview_completed: false,
      final_decision: "pending",
      decision_rationale: "",
      decided_by: null,
      decided_at: null,
      created_at: "2026-03-05T22:53:27.914946Z",
      updated_at: "2026-03-05T22:57:17.674501Z",
      submitted_at: null,
      completed_at: null,
      expected_completion_date: null,
      documents: [
        {
          id: "5e2b0f21-ad9a-441e-9fae-1c8302dfb714",
          case: "c9e351ae-223a-419e-9e8e-84b5d90630e0",
          document_type: "id_card",
          document_type_display: "National ID Card",
          file: "http://localhost:8000/media/documents/VET-20260305-99612B/ef5f7c47-dc01-40b1-a2db-572184edb2af.pdf",
          original_filename: "7.pdf",
          file_size: 99352,
          mime_type: "application/pdf",
          status: "verified",
          ocr_completed: true,
          authenticity_check_completed: true,
          fraud_check_completed: true,
          processing_error: "",
          retry_count: 0,
          extracted_text: "Placeholder OCR text for id_card",
          extracted_data: {
            pipeline: "placeholder",
            document_type: "id_card",
          },
          uploaded_at: "2026-03-05T22:55:54.155465Z",
          processed_at: "2026-03-05T22:55:54.389038Z",
          file_url: "/media/documents/VET-20260305-99612B/ef5f7c47-dc01-40b1-a2db-572184edb2af.pdf",
          verification_result: {
            id: "57606409-bafb-42d6-bb75-aad4f9ea4fda",
            document: "5e2b0f21-ad9a-441e-9fae-1c8302dfb714",
            ocr_text: "Placeholder OCR text for id_card",
            ocr_confidence: 88.0,
            ocr_language: "en",
            authenticity_score: 92.0,
            authenticity_confidence: 80.0,
            is_authentic: true,
            metadata_check_passed: true,
            visual_check_passed: true,
            tampering_detected: false,
            fraud_risk_score: 18.0,
            fraud_prediction: "legitimate",
            fraud_indicators: ["placeholder_pipeline"],
            detailed_results: {
              pipeline: "placeholder",
              document_type: "id_card",
            },
            ocr_model_version: "baseline-0.1",
            authenticity_model_version: "baseline-0.1",
            fraud_model_version: "baseline-0.1",
            created_at: "2026-03-05T22:55:54.374816Z",
            processing_time_seconds: 0.009277,
          },
        },
      ],
      rubric_evaluation: null,
      social_profile_result: null,
    });

    render(
      <MemoryRouter initialEntries={["/admin/cases/VET-20260305-99612B"]}>
        <Routes>
          <Route path="/admin/cases/:caseId" element={<CaseReview />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getByIdMock).toHaveBeenCalledWith("VET-20260305-99612B");
    });

    expect(await screen.findByText(/Case Review: VET-20260305-99612B/i)).toBeTruthy();
    expect(screen.getByText(/National ID Card/i)).toBeTruthy();
  });
});
