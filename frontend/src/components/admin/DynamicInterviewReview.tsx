// frontend/src/components/admin/DynamicInterviewReview.tsx
import { useEffect, useState, useCallback } from 'react';
import { MessageCircle, TrendingUp, AlertTriangle } from 'lucide-react';

// Type Definitions
interface Inconsistency {
  issue: string;
  severity: 'low' | 'medium' | 'high';
}

interface Exchange {
  id: number;
  question_intent: string;
  question_text: string;
  response_quality_score: number;
  transcript: string;
  sentiment: 'confident' | 'nervous' | 'neutral';
  confidence_level: number;
  relevance_score: number;
  key_points_extracted: string[];
  inconsistencies_detected: Inconsistency[];
}

interface Session {
  session_id: string;
  overall_score: number;
  confidence_score: number;
  consistency_score: number;
  completeness_score: number;
  interview_summary: string;
  recommendations: 'Strongly Recommend' | 'Recommend' | 'Do Not Recommend';
  exchanges: Exchange[];
  red_flags: string[];
}

interface DynamicInterviewReviewProps {
  sessionId: string;
}

export function DynamicInterviewReview({ sessionId }: DynamicInterviewReviewProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSession = useCallback(async () => {
    try {
      const response = await fetch(`/api/interviews/dynamic/${sessionId}/`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      setSession(data);
    } catch (error) {
      console.error('Error fetching session:', error);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  if (loading) {
    return <div className="flex items-center justify-center h-96">Loading...</div>;
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-red-500">
          Failed to load session data. Please try again later.
        </div>
      </div>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-amber-700';
    return 'text-red-600';
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:p-8">
      {/* Header */}
      <div className="mb-8 rounded-2xl bg-linear-to-r from-blue-600 to-purple-600 p-6 text-white shadow-2xl sm:p-8">
        <h1 className="mb-2 text-3xl font-bold sm:text-4xl">AI Interview Analysis</h1>
        <p className="text-base text-blue-100 sm:text-lg">
          Session: {session.session_id} • {session.exchanges.length} Questions Asked
        </p>
      </div>

      {/* Score Cards */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 sm:gap-6 xl:grid-cols-4">
          <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="text-sm text-slate-700 mb-2">Overall Score</div>
          <div className={`text-4xl font-bold ${getScoreColor(session.overall_score)}`}>
            {session.overall_score.toFixed(1)}
          </div>
          <div className="text-xs text-slate-700 mt-1">out of 100</div>
        </div>
        
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="text-sm text-slate-700 mb-2">Confidence</div>
          <div className={`text-4xl font-bold ${getScoreColor(session.confidence_score)}`}>
            {session.confidence_score.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-700 mt-1">speech clarity</div>
        </div>
        
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="text-sm text-slate-700 mb-2">Consistency</div>
          <div className={`text-4xl font-bold ${getScoreColor(session.consistency_score)}`}>
            {session.consistency_score.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-700 mt-1">across responses</div>
        </div>
        
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="text-sm text-slate-700 mb-2">Completeness</div>
          <div className={`text-4xl font-bold ${getScoreColor(session.completeness_score)}`}>
            {session.completeness_score.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-700 mt-1">information provided</div>
        </div>
      </div>

      {/* AI Summary */}
      <div className="mb-8 rounded-2xl bg-white p-6 shadow-xl sm:p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
          <TrendingUp className="text-blue-600" size={28} />
          AI Analysis Summary
        </h2>
        <div className="prose max-w-none">
          <p className="text-slate-800 text-lg leading-relaxed whitespace-pre-wrap">
            {session.interview_summary}
          </p>
        </div>
        
        <div className="mt-6 p-6 bg-linear-to-r from-blue-50 to-purple-50 rounded-xl">
          <div className="text-lg font-bold text-gray-900 mb-2">
            Recommendation: <span className={session.recommendations === 'Strongly Recommend' || session.recommendations === 'Recommend' ? 'text-green-600' : 'text-red-600'}>
              {session.recommendations}
            </span>
          </div>
        </div>
      </div>

      {/* Conversation Flow */}
      <div className="mb-8 rounded-2xl bg-white p-6 shadow-xl sm:p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-3">
          <MessageCircle className="text-purple-600" size={28} />
          Dynamic Question Flow
        </h2>
        
        <div className="space-y-6">
          {session.exchanges.map((exchange, index) => (
            <div key={exchange.id} className="border-l-4 border-purple-500 pl-6 py-4">
              <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-100 text-purple-700 rounded-full flex items-center justify-center font-bold">
                    {index + 1}
                  </div>
                  <div>
                    <div className="text-sm text-slate-700 uppercase tracking-wide font-semibold">
                      AI Generated • {exchange.question_intent}
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mt-1">
                      {exchange.question_text}
                    </h3>
                  </div>
                </div>
                <div className="text-left lg:text-right">
                  <div className={`text-2xl font-bold ${getScoreColor(exchange.response_quality_score)}`}>
                    {exchange.response_quality_score.toFixed(1)}
                  </div>
                  <div className="text-xs text-slate-700">Quality</div>
                </div>
              </div>
               
              <div className="bg-slate-100 rounded-lg p-4 mb-3">
                <div className="text-sm font-medium text-slate-800 mb-2">Response:</div>
                <p className="text-slate-700 italic">&quot;{exchange.transcript}&quot;</p>
              </div>
               
              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <span className="font-medium text-slate-800">Sentiment:</span>
                  <span className={`ml-2 ${exchange.sentiment === 'confident' ? 'text-green-700' : exchange.sentiment === 'nervous' ? 'text-amber-700' : 'text-slate-700'}`}>
                    {exchange.sentiment}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-slate-800">Confidence:</span>
                  <span className="ml-2 text-blue-600">{exchange.confidence_level.toFixed(1)}%</span>
                </div>
                <div>
                  <span className="font-medium text-slate-800">Relevance:</span>
                  <span className="ml-2 text-purple-600">{exchange.relevance_score.toFixed(1)}%</span>
                </div>
              </div>
              
              {exchange.key_points_extracted && exchange.key_points_extracted.length > 0 && (
                <div className="mt-3 bg-green-50 rounded-lg p-3">
                  <div className="text-sm font-medium text-green-800 mb-1">Key Points:</div>
                  <ul className="text-sm text-green-700 space-y-1">
                    {exchange.key_points_extracted.map((point, i) => (
                      <li key={i}>• {point}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {exchange.inconsistencies_detected && exchange.inconsistencies_detected.length > 0 && (
                <div className="mt-3 bg-red-50 rounded-lg p-3">
                  <div className="text-sm font-medium text-red-800 mb-1 flex items-center gap-2">
                    <AlertTriangle size={16} />
                    Inconsistencies Detected:
                  </div>
                  <ul className="text-sm text-red-700 space-y-1">
                    {exchange.inconsistencies_detected.map((inc, i) => (
                      <li key={i}>• {inc.issue} (Severity: {inc.severity})</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Red Flags */}
      {session.red_flags && session.red_flags.length > 0 && (
        <div className="rounded-2xl border-2 border-red-200 bg-red-50 p-6 sm:p-8">
          <h2 className="text-2xl font-bold text-red-900 mb-4 flex items-center gap-3">
            <AlertTriangle className="text-red-600" size={28} />
            Red Flags Identified
          </h2>
          <ul className="space-y-3">
            {session.red_flags.map((flag, index) => (
              <li key={index} className="flex items-start gap-3 text-red-800">
                <span className="text-red-600 font-bold text-xl">•</span>
                <span className="text-lg">{flag}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
