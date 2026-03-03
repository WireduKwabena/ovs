// src/services/rubric.service.ts (Tweaked)
import api from './api';
import type {
  VettingRubric,
  RubricCriteria,
  RubricEvaluation,
  ApiError,
  CreateRubricData,
  PaginatedResponse,
} from '@/types';

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

export const rubricService = {
  async getAll(params?: { status?: string; rubric_type?: string }): Promise<VettingRubric[]> {
    try {
      const response = await api.get<PaginatedResponse<VettingRubric> | VettingRubric[]>(
        '/rubrics/vetting-rubrics/',
        { params }
      );
      return extractResults(response.data);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch rubrics');
    }
  },

  async getById(id: number): Promise<VettingRubric> {
    try {
      const response = await api.get<VettingRubric>(`/rubrics/vetting-rubrics/${id}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Failed to fetch rubric');
    }
  },

  async create(data: CreateRubricData): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>('/rubrics/vetting-rubrics/', data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Creation failed');
    }
  },

  async update(id: number, data: Partial<VettingRubric>): Promise<VettingRubric> {
    try {
      const response = await api.patch<VettingRubric>(`/rubrics/vetting-rubrics/${id}/`, data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Update failed');
    }
  },

  async delete(id: number): Promise<void> {
    try {
      await api.delete(`/rubrics/vetting-rubrics/${id}/`);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Deletion failed');
    }
  },

  async activate(id: number): Promise<{ message: string; rubric: VettingRubric }> {
    try {
      const response = await api.post(`/rubrics/vetting-rubrics/${id}/activate/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Activation failed');
    }
  },

  async duplicate(id: number): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>(`/rubrics/vetting-rubrics/${id}/duplicate/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Duplication failed');
    }
  },

  async evaluateApplication(
    rubricId: number,
    applicationId: string
  ): Promise<RubricEvaluation> {
    try {
      const response = await api.post<RubricEvaluation>(
        `/rubrics/vetting-rubrics/${rubricId}/evaluate_application/`,
        { application_id: applicationId }
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Evaluation failed');
    }
  },

  async getTemplates(): Promise<VettingRubric[]> {  // Typed as rubrics
    try {
      const response = await api.get<PaginatedResponse<VettingRubric> | VettingRubric[]>(
        '/rubrics/vetting-rubrics/templates/'
      );
      return extractResults(response.data);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Templates fetch failed');
    }
  },

  async createFromTemplate(
    templateKey: string,
    overrides?: Record<string, any>
  ): Promise<VettingRubric> {
    try {
      const response = await api.post<VettingRubric>('/rubrics/vetting-rubrics/create_from_template/', {
        template_key: templateKey,
        overrides,
      });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Template creation failed');
    }
  },

  async addCriteria(
    rubricId: number,
    payload: Omit<RubricCriteria, 'id'>,
  ): Promise<RubricCriteria> {
    try {
      const response = await api.post<RubricCriteria>(`/rubrics/vetting-rubrics/${rubricId}/criteria/`, payload);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Add criteria failed');
    }
  },

  async listCriteria(params?: { rubric?: number | string }): Promise<RubricCriteria[]> {
    try {
      const response = await api.get<PaginatedResponse<RubricCriteria> | RubricCriteria[]>(
        '/rubrics/criteria/',
        { params },
      );
      return extractResults(response.data);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Criteria list fetch failed');
    }
  },

  async getCriteriaById(criteriaId: number | string): Promise<RubricCriteria> {
    try {
      const response = await api.get<RubricCriteria>(`/rubrics/criteria/${criteriaId}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Criteria detail fetch failed');
    }
  },

  async evaluateCase(
    rubricId: number,
    caseId: number | string,
    runAsync = false,
  ): Promise<RubricEvaluation | { message: string }> {
    try {
      const response = await api.post<RubricEvaluation | { message: string }>(
        `/rubrics/vetting-rubrics/${rubricId}/evaluate-case/`,
        { case_id: caseId, async: runAsync },
      );
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Evaluate case failed');
    }
  },

  async listEvaluations(params?: { case?: number | string; rubric?: number | string }): Promise<RubricEvaluation[]> {
    try {
      const response = await api.get<PaginatedResponse<RubricEvaluation> | RubricEvaluation[]>(
        '/rubrics/evaluations/',
        { params },
      );
      return extractResults(response.data);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Evaluation list fetch failed');
    }
  },

  async getEvaluationById(evaluationId: number | string): Promise<RubricEvaluation> {
    try {
      const response = await api.get<RubricEvaluation>(`/rubrics/evaluations/${evaluationId}/`);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Evaluation detail fetch failed');
    }
  },

  async rerunEvaluation(evaluationId: number | string): Promise<RubricEvaluation> {
    try {
      const response = await api.post<RubricEvaluation>(`/rubrics/evaluations/${evaluationId}/rerun/`, {});
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Evaluation rerun failed');
    }
  },

  async overrideCriterion(
    evaluationId: number | string,
    payload: {
      criterion_id: number | string;
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
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Override criterion failed');
    }
  },
};
