// src/components/admin/RealTimeAnalytics.tsx
import { useState, useEffect, useCallback } from 'react';

// Type Definitions
interface LiveInterview {
  session_id: string;
  applicant_name: string;
  current_question: number;
  duration: number;
  flags_resolved: number;
  total_flags: number;
}

interface RecentCompletion {
  session_id: string;
  applicant_name: string;
  completed_at: string;
  overall_score: number;
  recommendation: string;
}


function formatDuration(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTimeAgo(timestamp: string) {
  const seconds = Math.floor((new Date().getTime() - new Date(timestamp).getTime()) / 1000);
  
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function RealTimeAnalytics() {
  const [liveInterviews, setLiveInterviews] = useState<LiveInterview[]>([]);
  const [recentCompletions, setRecentCompletions] = useState<RecentCompletion[]>([]);

  const fetchLiveData = useCallback(async () => {
    try {
      const response = await fetch('/api/analytics/live', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      
      setLiveInterviews(data.in_progress);
      setRecentCompletions(data.recent_completions);
    } catch (error) {
      console.error('Failed to fetch live data:', error);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    (async () => {
      await fetchLiveData();
    })();

    // Poll for live updates every 5 seconds
    const interval = setInterval(fetchLiveData, 5000);
    
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
        <h2 className="text-xl font-bold text-gray-900">Live Interviews</h2>
        <span className="text-sm text-gray-600">({liveInterviews.length} active)</span>
      </div>

      {/* Active Interviews */}
      <div className="space-y-3 mb-6">
        {liveInterviews.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No active interviews</p>
        ) : (
          liveInterviews.map((interview) => (
            <div key={interview.session_id} className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-semibold text-gray-900">{interview.applicant_name}</div>
                  <div className="text-sm text-gray-600">
                    Question {interview.current_question} • {formatDuration(interview.duration)} elapsed
                  </div>
                </div>
                <span className="px-2 py-1 bg-green-600 text-white text-xs font-semibold rounded-full">
                  LIVE
                </span>
              </div>
              
              {/* Progress bar */}
              <div className="mt-3">
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>Progress</span>
                  <span>{interview.flags_resolved}/{interview.total_flags} flags resolved</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-600 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${(interview.flags_resolved / interview.total_flags) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Recent Completions */}
      <div className="border-t pt-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Recent Completions</h3>
        <div className="space-y-2">
          {recentCompletions.map((interview) => (
            <div key={interview.session_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div>
                <div className="text-sm font-medium text-gray-900">{interview.applicant_name}</div>
                <div className="text-xs text-gray-600">{formatTimeAgo(interview.completed_at)}</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-bold ${
                  interview.overall_score >= 80 ? 'text-green-600' :
                  interview.overall_score >= 60 ? 'text-yellow-600' :
                  'text-red-600'
                }`}>
                  {interview.overall_score.toFixed(0)}%
                </div>
                <div className="text-xs text-gray-600">
                  {interview.recommendation}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}