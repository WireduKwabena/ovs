// src/services/rubric.service.ts (Tweaked)
import api from './api';
import type { VettingRubric, RubricEvaluation, ApiError, CreateRubricData } from '@/types';

export const rubricService = {
  async getAll(params?: { status?: string; rubric_type?: string }): Promise<VettingRubric[]> {
    try {
      const response = await api.get<VettingRubric[]>('/rubrics/vetting-rubrics/', { params });
      return response.data;
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
      const response = await api.get<VettingRubric[]>('/rubrics/vetting-rubrics/templates/');
      return response.data;
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
};