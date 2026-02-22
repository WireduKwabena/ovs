// src/components/rubrics/RubricList.tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import type { AppDispatch, RootState } from '@/app/store';
import { fetchRubrics } from '@/store/rubricSlice';
import { Loader } from '../common/Loader';
import { Plus, FileText, Edit } from 'lucide-react';
import { Button } from '../ui/button';

export function RubricList() {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { rubrics, loading } = useSelector((state: RootState) => state.rubrics);
  const [filterStatus, setFilterStatus] = useState('active');
  
  useEffect(() => {
    dispatch(fetchRubrics({ status: filterStatus }));  // Thunk with params
  }, [filterStatus, dispatch]);
  
  const getStatusColor = (status: string) => {  // Fixed param type
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'draft': return 'bg-gray-100 text-gray-800';
      case 'archived': return 'bg-orange-100 text-orange-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader size="lg" />
      </div>
    );
  }
  
  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Vetting Rubrics</h1>
          <p className="text-gray-600 mt-2">Manage evaluation criteria and scoring rules</p>
        </div>
        <Button
          onClick={() => navigate('/rubrics/new')}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Rubric
        </Button>
      </div>
      
      {/* Filter */}
      <div className="mb-6">
        <label className="text-sm font-medium text-gray-700 mr-4">Filter by Status:
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
          <option value="all">All</option>
        </select>
        </label>
      </div>
      
      {/* Rubrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rubrics.map((rubric) => (
          <div key={rubric.id} className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            <div className="p-6">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{rubric.name}</h3>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(rubric.status ?? '')}`}>
                    {rubric.status}
                  </span>
                </div>
              </div>
              
              <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                {rubric.description || 'No description'}
              </p>
              
              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Criteria:</span>
                  <span className="font-medium">{rubric.criteria?.length || 0}</span>
                </div>
                
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Passing Score:</span>
                  <span className="font-medium">{rubric.passing_score}%</span>
                </div>
                
                {rubric.department && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Department:</span>
                    <span className="font-medium">{rubric.department}</span>
                  </div>
                )}
              </div>
              
              <div className="flex gap-2">
                <Button
                  onClick={() => navigate(`/rubrics/${rubric.id}`)}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-sm"
                >
                  View Details
                </Button>
                <Button
                  onClick={() => navigate(`/rubrics/${rubric.id}/edit`)}
                  variant="outline"
                  size="sm"
                >
                  <Edit className="w-4 h-4 mr-1" />
                  Edit
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {rubrics.length === 0 && (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No rubrics found</h3>
          <p className="text-gray-500 mb-6">Create your first rubric to get started</p>
          <Button onClick={() => navigate('/rubrics/new')} className="bg-blue-600 hover:bg-blue-700">
            <Plus className="w-4 h-4 mr-2" />
            Create Rubric
          </Button>
        </div>
      )}
    </div>
  );
}