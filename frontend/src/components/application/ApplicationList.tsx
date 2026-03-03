// src/components/application/ApplicationList.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApplications } from '@/hooks/useApplications';  // Redux hook
import { StatusBadge } from '../common/StatusBadge';
import { Loader } from '../common/Loader';
import { FileText, Plus, Search } from 'lucide-react';
import type { ApplicationWithDocuments } from '@/types';

export function ApplicationList() {
  const navigate = useNavigate();
  const { applications, loading, refetch } = useApplications();  // From Redux
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  
  useEffect(() => {
    refetch();  // Initial fetch
  }, [refetch]);

  const filteredApplications: ApplicationWithDocuments[] = applications
    .filter((app) => {
      const matchesSearch = app.case_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           app.application_type.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFilter = filterStatus === 'all' || app.status === filterStatus;
      return matchesSearch && matchesFilter;
    }) as ApplicationWithDocuments[];
  
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
          <h1 className="text-3xl font-bold text-gray-900">My Applications</h1>
          <p className="text-slate-700 mt-2">Track and manage your vetting applications</p>
        </div>
        <button
          onClick={() => navigate('/applications/new')}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
        >
          <Plus className="w-5 h-5" />
          New Application
        </button>
      </div>
      
      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-4 h-4" />
            <input
              type="text"
              placeholder="Search by case ID or type..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <label htmlFor="filter-status"> select an option: 
          <select
            id="filter-status"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 border border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="under_review">Under Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          </label>
        </div>
      </div>
      
      {/* Applications Grid */}
      {filteredApplications.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredApplications.map((app) => (
            <div
              key={app.id}
              onClick={() => navigate(`/applications/${app.case_id}`)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  navigate(`/applications/${app.case_id}`);
                }
              }}
              role="button"
              tabIndex={0}
              className="bg-white rounded-lg shadow hover:shadow-lg transition cursor-pointer p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg text-gray-900">{app.case_id}</h3>
                  <p className="text-sm text-slate-700">{app.application_type.replace('_', ' ')}</p>
                </div>
                <StatusBadge status={app.status} />
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-700">Priority:</span>
                  <span className="font-medium capitalize">{app.priority}</span>
                </div>
                
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-700">Submitted:</span>
                  <span className="font-medium">
                    {new Date(app.created_at).toLocaleDateString()}
                  </span>
                </div>
                
                {app.documents && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">Documents:</span>
                    <span className="font-medium">{app.documents.length}</span>
                  </div>
                )}
                
                {app.consistency_score && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">Consistency:</span>
                    <span className={`font-medium ${app.consistency_score >= 85 ? 'text-green-600' : 'text-red-600'}`}>
                      {app.consistency_score.toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              
              <div className="mt-4 pt-4 border-t border-gray-200">
                <button className="w-full text-center text-blue-600 hover:text-blue-700 font-medium text-sm">
                  View Details →
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 mx-auto mb-4 text-slate-700" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No applications found</h3>
          <p className="text-slate-700 mb-6">Start your first application below</p>
          <button
            onClick={() => navigate('/applications/new')}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
          >
            <Plus className="w-5 h-5 inline mr-2" />
            Create Application
          </button>
        </div>
      )}
    </div>
  );
}

