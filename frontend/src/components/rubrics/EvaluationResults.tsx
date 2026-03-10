// src/components/rubrics/EvaluationResults.tsx

import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { cn, getScoreColor, getScoreBg, getProgressBarColor } from '../../utils/helper';  // Centralized
import type { RubricEvaluation } from '@/types';

interface EvaluationResultsProps {
  evaluation: RubricEvaluation | null;
}

export function EvaluationResults({ evaluation }: EvaluationResultsProps) {
  if (!evaluation) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-8 text-center">
        <p className="text-slate-700">No evaluation results available</p>
      </div>
    );
  }

  const overallScore =
    typeof evaluation.overall_score === "number"
      ? evaluation.overall_score
      : typeof evaluation.total_weighted_score === "number"
        ? evaluation.total_weighted_score
        : 0;
  const passed =
    typeof evaluation.passed === "boolean"
      ? evaluation.passed
      : Boolean(evaluation.passes_threshold);
  
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Overall Score Card */}
      <div className="bg-white rounded-lg shadow-lg p-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-6">Evaluation Results</h2>
          
          <div className={cn(`inline-block p-8 rounded-2xl ${getScoreBg(overallScore)}`)}>
            <div className={cn(`text-6xl font-bold ${getScoreColor(overallScore)} mb-2`)}>
              {overallScore.toFixed(1)}%
            </div>
            <p className="text-lg text-slate-700 mb-4">Overall Score</p>
            
            {passed ? (
              <div className="inline-flex items-center gap-2 px-6 py-3 bg-green-100 text-green-800 rounded-full font-semibold">
                <CheckCircle className="w-5 h-5" />
                PASSED
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 px-6 py-3 bg-red-100 text-red-800 rounded-full font-semibold">
                <XCircle className="w-5 h-5" />
                FAILED
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Criteria Breakdown */}
      <div className="bg-white rounded-lg shadow-lg p-8">
        <h3 className="text-xl font-bold mb-6">Criteria Breakdown</h3>
        
        <div className="space-y-4">
          {Object.entries(evaluation.criteria_scores || {}).map(([criterionName, scoreData]: [string, any]) => (
            <div key={criterionName} className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-gray-900">{criterionName}</h4>
                <div className={`px-3 py-1 rounded-full text-xs font-semibold ${getScoreColor(scoreData.score)}`}>
                  {scoreData.score.toFixed(1)}%
                </div>
              </div>
              
              <div className="flex items-center justify-between text-sm text-slate-700 mb-4">
                <span>
                  {scoreData.passed ? '✓ Passed' : '✗ Not Passed'}
                </span>
                <span>Weighted: {scoreData.weighted_score.toFixed(2)}</span>
              </div>
              
              <div className="w-full bg-slate-200 rounded-full h-2 mb-4">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${getProgressBarColor(scoreData.score)}`}
                  style={{ width: `${scoreData.score}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Flags (Strings) */}
      {evaluation.flags && evaluation.flags.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h3 className="text-xl font-bold mb-4 text-red-600 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6" />
            Issues Detected ({evaluation.flags.length})
          </h3>
          
          <div className="space-y-3">
            {evaluation.flags.map((flag, index) => (
              <div key={index} className="p-4 bg-red-50 border-l-4 border-red-500 rounded">
                <div className="font-semibold text-red-900">{flag}</div>  {/* String render */}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Warnings (Strings) */}
      {evaluation.warnings && evaluation.warnings.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-8">
          <h3 className="text-xl font-bold mb-4 text-amber-700 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6" />
            Warnings ({evaluation.warnings.length})
          </h3>
          
          <div className="space-y-3">
            {evaluation.warnings.map((warning, index) => (
              <div key={index} className="p-4 bg-amber-50 border-l-4 border-yellow-500 rounded">
                <div className="font-semibold text-yellow-900">{warning}</div>  {/* String render */}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
