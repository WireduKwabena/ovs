import api from "./api";
import { toServiceError } from "@/utils/apiError";
import type {
  VettingRubric,
  RubricCriteria,
  RubricEvaluation,
  CreateRubricData,
  PaginatedResponse,
} from "@/types";

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};


export const rubricService = {
  async getAll(params?: { status?: string; rubric_type?: string }): Promise<VettingRubric[]> {
    try {
      const queryParams: Record<string, string> = {};
      if (params?.rubric_type) {
        queryParams.rubric_type = params.rubric_type;
      }
      if (params?.status === "active") {
        queryParams.is_active = "true";
      } else if (params?.status === "archived" || params?.status === "draft") {
        queryParams.is_active = "false";
      }

      const response = await api.get<PaginatedResponse<VettingRubric> | VettingRubric[]>(
        "/rubrics/vetting-rubrics/",
        { params: queryParams },
      );
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch rubrics");
    }
  },

  async getById(id: string): Promise<VettingRubric> {
    try {
      const response = await api.get<VettingRubric>(`/rubrics/vetting-rubrics/${id}/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to fetch rubric");
    }
  },

  async create(data: CreateRubricData): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>("/rubrics/vetting-rubrics/", data);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Rubric creation failed");
    }
  },

  async update(id: string, data: Partial<CreateRubricData>): Promise<VettingRubric> {
    try {
      const response = await api.patch<VettingRubric>(`/rubrics/vetting-rubrics/${id}/`, data);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Rubric update failed");
    }
  },

  async delete(id: string): Promise<void> {
    try {
      await api.delete(`/rubrics/vetting-rubrics/${id}/`);
    } catch (error) {
      throw toServiceError(error, "Rubric deletion failed");
    }
  },

  async activate(id: string): Promise<{ message: string; rubric: VettingRubric }> {
    try {
      const response = await api.post(`/rubrics/vetting-rubrics/${id}/activate/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Rubric activation failed");
    }
  },

  async duplicate(id: string): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>(`/rubrics/vetting-rubrics/${id}/duplicate/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Rubric duplication failed");
    }
  },

  async evaluateApplication(rubricId: string, applicationId: string): Promise<RubricEvaluation> {
    try {
      const response = await api.post<RubricEvaluation>(
        `/rubrics/vetting-rubrics/${rubricId}/evaluate_application/`,
        { application_id: applicationId },
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Rubric evaluation failed");
    }
  },

  async getTemplates(): Promise<VettingRubric[]> {
    try {
      const response = await api.get<PaginatedResponse<VettingRubric> | VettingRubric[]>(
        "/rubrics/vetting-rubrics/templates/",
      );
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Templates fetch failed");
    }
  },

  async createFromTemplate(templateKey: string, overrides?: Record<string, any>): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>("/rubrics/vetting-rubrics/create_from_template/", {
        template_key: templateKey,
        overrides,
      });
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Template creation failed");
    }
  },

  async addCriteria(
    rubricId: string,
    payload: Omit<RubricCriteria, "id" | "criteria_type_display" | "scoring_method_display">,
  ): Promise<RubricCriteria> {
    try {
      const response = await api.post<RubricCriteria>(`/rubrics/vetting-rubrics/${rubricId}/criteria/`, payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Add criteria failed");
    }
  },

  async listCriteria(params?: { rubric?: string }): Promise<RubricCriteria[]> {
    try {
      const response = await api.get<PaginatedResponse<RubricCriteria> | RubricCriteria[]>(
        "/rubrics/criteria/",
        { params },
      );
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Criteria list fetch failed");
    }
  },

  async getCriteriaById(criteriaId: string): Promise<RubricCriteria> {
    try {
      const response = await api.get<RubricCriteria>(`/rubrics/criteria/${criteriaId}/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Criteria detail fetch failed");
    }
  },

  async updateCriteria(criteriaId: string, payload: Partial<RubricCriteria>): Promise<RubricCriteria> {
    try {
      const response = await api.patch<RubricCriteria>(`/rubrics/criteria/${criteriaId}/`, payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Update criteria failed");
    }
  },

  async deleteCriteria(criteriaId: string): Promise<void> {
    try {
      await api.delete(`/rubrics/criteria/${criteriaId}/`);
    } catch (error) {
      throw toServiceError(error, "Delete criteria failed");
    }
  },

  async evaluateCase(
    rubricId: string,
    caseId: string,
    runAsync = false,
  ): Promise<RubricEvaluation | { message: string }> {
    try {
      const response = await api.post<RubricEvaluation | { message: string }>(
        `/rubrics/vetting-rubrics/${rubricId}/evaluate-case/`,
        { case_id: caseId, async: runAsync },
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Evaluate case failed");
    }
  },

  async listEvaluations(params?: { case?: string; rubric?: string }): Promise<RubricEvaluation[]> {
    try {
      const response = await api.get<PaginatedResponse<RubricEvaluation> | RubricEvaluation[]>(
        "/rubrics/evaluations/",
        { params },
      );
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Evaluation list fetch failed");
    }
  },

  async getEvaluationById(evaluationId: string): Promise<RubricEvaluation> {
    try {
      const response = await api.get<RubricEvaluation>(`/rubrics/evaluations/${evaluationId}/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Evaluation detail fetch failed");
    }
  },

  async rerunEvaluation(evaluationId: string): Promise<RubricEvaluation> {
    try {
      const response = await api.post<RubricEvaluation>(`/rubrics/evaluations/${evaluationId}/rerun/`, {});
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Evaluation rerun failed");
    }
  },

  async overrideCriterion(
    evaluationId: string,
    payload: {
      criterion_id: string;
      overridden_score: number;
      justification: string;
    },
  ): Promise<{ message: string; override: Record<string, unknown> }> {
    try {
      const response = await api.post<{ message: string; override: Record<string, unknown> }>(
        `/rubrics/evaluations/${evaluationId}/override-criterion/`,
        payload,
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Override criterion failed");
    }
  },
};
