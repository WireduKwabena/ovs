// src/components/application/ApplicationDetails.tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '@/app/store';
import { fetchCaseById } from '@/store/applicationSlice';
import { applicationService } from '@/services/application.service';
import { Loader } from '../common/Loader';
import { FileText,  TrendingUp, Shield } from 'lucide-react';
import { getScoreColor, getProgressBarColor } from '@/utils/helper';  // Moved helpers
import { StatusBadge } from '../common/StatusBadge';
import { ProgressBar } from '../common/ProgressBar';
import type { VerificationStatusResponse } from '@/types';

export function ApplicationDetails() {
  const { caseId } = useParams<{ caseId: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { currentCase, loading } = useSelector((state: RootState) => state.applications);
  const [verificationStatus, setVerificationStatus] = useState<VerificationStatusResponse | null>(null);

  const loadVerificationStatus = useCallback(async () => {
    if (!caseId) {
      return;
    }

    try {
      const data = await applicationService.getVerificationStatus(caseId);  // Service
      setVerificationStatus(data as unknown as VerificationStatusResponse);
    } catch (error) {
      console.error('Failed to load verification status:', error);
    }
  }, [caseId]);
  
  useEffect(() => {
    if (caseId) {
      dispatch(fetchCaseById(caseId));  // Redux fetch
    }
  }, [caseId, dispatch]);
  
  useEffect(() => {
    if (caseId) {
      const initialFetchTimer = setTimeout(() => {
        void loadVerificationStatus();
      }, 0);
      const interval = setInterval(() => {
        void loadVerificationStatus();
      }, 10000);  // Poll
      return () => {
        clearTimeout(initialFetchTimer);
        clearInterval(interval);
      };
    }
  }, [caseId, loadVerificationStatus]);
  
  if (loading || !currentCase) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader size="lg" />
      </div>
    );
  }
  
  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{currentCase.case_id}</h1>
            <p className="text-slate-700 mt-2">{currentCase.application_type.replace('_', ' ')}</p>
          </div>
          <StatusBadge status={currentCase.status} />
        </div>
        
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-center">
            <Shield className="w-4 h-4 mr-2 text-slate-700" />
            <span className="text-slate-700">Priority: <span className="font-medium capitalize">{currentCase.priority}</span></span>
          </div>
          <div className="flex items-center">
            <FileText className="w-4 h-4 mr-2 text-slate-700" />
            <span className="text-slate-700">Submitted: {new Date(currentCase.created_at).toLocaleDateString()}</span>
          </div>
          <div className="flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-slate-700" />
            <span className="text-slate-700">Documents: {currentCase.documents?.length || 0}</span>
          </div>
        </div>
      </div>
      
      {/* Verification Status */}
      {verificationStatus && (
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4">Verification Status</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Documents */}
            <div className="border rounded-lg p-4">
              <h3 className="font-semibold mb-2">Documents ({verificationStatus.documents.length})</h3>
              <div className="space-y-2">
                {verificationStatus.documents.map((doc, index) => (
                  <div key={index} className="flex items-center justify-between text-sm">
                    <span>{doc.document_type}</span>
                    <StatusBadge status={doc.verification_status as any} />
                  </div>
                ))}
              </div>
            </div>
            
            {/* Consistency */}
            {verificationStatus.consistency_check && (
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold mb-2">Consistency Check</h3>
                <div className="flex items-center justify-between mb-2">
                  <span>Score:</span>
                  <span className={getScoreColor(verificationStatus.consistency_check.overall_score)}>
                    {verificationStatus.consistency_check.overall_score.toFixed(1)}%
                  </span>
                </div>
                <ProgressBar 
                  value={verificationStatus.consistency_check.overall_score} 
                  color={getProgressBarColor(verificationStatus.consistency_check.overall_score)} 
                />
                <p className="text-sm mt-2 text-slate-700">
                  {verificationStatus.consistency_check.recommendation}
                </p>
              </div>
            )}
            
            {/* Fraud */}
            {verificationStatus.fraud_detection && (
              <div className="border rounded-lg p-4">
                <h3 className="font-semibold mb-2">Fraud Detection</h3>
                <div className="flex items-center justify-between mb-2">
                  <span>Risk Level:</span>
                  <StatusBadge status={verificationStatus.fraud_detection.risk_level.toLowerCase() as any} />
                </div>
                <ProgressBar 
                  value={(1 - verificationStatus.fraud_detection.fraud_probability) * 100} 
                  color={getProgressBarColor((1 - verificationStatus.fraud_detection.fraud_probability) * 100)} 
                />
                <p className="text-sm mt-2 text-slate-700">
                  {verificationStatus.fraud_detection.recommendation}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Overall Scores */}
      {verificationStatus?.overall_scores && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4">Overall Scores</h2>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-slate-700 mb-1">Consistency Score</p>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-slate-200 rounded-full h-3">
                  <div 
                    className="bg-blue-600 h-3 rounded-full"
                    style={{ width: `${verificationStatus.overall_scores.consistency || 0}%` }}
                  />
                </div>
                <span className="font-semibold">
                  {verificationStatus.overall_scores.consistency?.toFixed(1) || 0}%
                </span>
              </div>
            </div>
            
            <div>
              <p className="text-sm text-slate-700 mb-1">Fraud Risk Score</p>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-slate-200 rounded-full h-3">
                  <div 
                    className="bg-purple-600 h-3 rounded-full"
                    style={{ width: `${(1 - (verificationStatus.overall_scores.fraud_risk || 0)) * 100}%` }}
                  />
                </div>
                <span className="font-semibold">
                  {((1 - (verificationStatus.overall_scores.fraud_risk || 0)) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

