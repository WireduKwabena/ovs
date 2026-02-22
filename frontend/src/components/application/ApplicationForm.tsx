// src/components/application/ApplicationForm.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { applicationSchema } from '@/utils/validators';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '@/app/store';
import { createApplication } from '@/store/applicationSlice';
import { Loader } from '../common/Loader';
import type { CreateApplicationData } from '@/types';

export function ApplicationForm() {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { user } = useSelector((state: RootState) => state.auth);  // For display
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateApplicationData>({
    resolver: yupResolver(applicationSchema) as any,
  });

  const onSubmit: SubmitHandler<CreateApplicationData> = async (data: CreateApplicationData) => {
    setLoading(true);
    setError(null);

    try {
      const response = await dispatch(createApplication(data)).unwrap();
      // Navigate to upload for new case
      navigate(`/applications/${response.case_id}/upload`);
    } catch (err: any) {
      setError(err.message || 'Failed to create application');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          New Vetting Application
        </h2>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded">
            {error}
          </div>
        )}

        <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Application Type *
            </label>
            <select
              {...register('application_type')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select type...</option>
              {/* From constants */}
              <option value="employment">Employment Verification</option>
              <option value="background">Background Check</option>
              <option value="credential">Credential Verification</option>
              <option value="education">Educational Verification</option>
            </select>
            {errors.application_type && (
              <p className="mt-1 text-sm text-red-600">{errors.application_type.message}</p>
            )}
          </div>

          {/* Priority */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Priority *
            </label>
            <select
              {...register('priority')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select priority...</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
            {errors.priority && (
              <p className="mt-1 text-sm text-red-600">{errors.priority.message}</p>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional Notes
            </label>
            <textarea
              {...register('notes')}
              rows={4}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Any additional information..."
            />
          </div>

          {/* Applicant Info Display */}
          <div className="p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">Applicant Information</h3>
            <div className="text-sm text-blue-800 space-y-1">
              <p><strong>Name:</strong> {(user && 'full_name' in user) ? user.full_name : 'N/A'}</p>
              <p><strong>Email:</strong> {user?.email}</p>
              <p><strong>Phone:</strong> {(user && 'phone_number' in user) ? user.phone_number : 'N/A'}</p>
            </div>
          </div>

          {/* Submit */}
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => navigate('/applications')}
              className="flex-1 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? <Loader size="sm" /> : 'Create Application'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}