import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type DashboardChartMode = 'count' | 'percentage';

interface ThroughputRow {
  name: string;
  total_candidates: number;
  invited: number;
  in_progress: number;
  completed: number;
  approved: number;
}

interface MixRow {
  name: string;
  value: number;
  fill: string;
  raw: number;
}

interface OperationsDashboardChartsSectionProps {
  chartMode: DashboardChartMode;
  onChartModeChange: (mode: DashboardChartMode) => void;
  throughputDisplayData: ThroughputRow[];
  pipelineMixDisplayData: MixRow[];
  decisionMixDisplayData: MixRow[];
}

const OperationsDashboardChartsSection: React.FC<OperationsDashboardChartsSectionProps> = ({
  chartMode,
  onChartModeChange,
  throughputDisplayData,
  pipelineMixDisplayData,
  decisionMixDisplayData,
}) => {
  return (
    <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Campaign Throughput</h2>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:gap-3">
            <div className="inline-flex rounded-lg border border-slate-700 bg-slate-100 p-0.5">
              <button
                type="button"
                onClick={() => onChartModeChange('count')}
                className={`px-2.5 py-1 text-xs rounded-md ${
                  chartMode === 'count'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-800 hover:bg-slate-100'
                }`}
              >
                Count
              </button>
              <button
                type="button"
                onClick={() => onChartModeChange('percentage')}
                className={`px-2.5 py-1 text-xs rounded-md ${
                  chartMode === 'percentage'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-800 hover:bg-slate-100'
                }`}
              >
                Percent
              </button>
            </div>
            <p className="text-xs text-slate-800">Top 8 campaigns by recency</p>
          </div>
        </div>
        {throughputDisplayData.length === 0 ? (
          <div className="py-10 text-center text-slate-800">No throughput data yet.</div>
        ) : (
          <div className="h-80 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={throughputDisplayData} margin={{ top: 10, right: 12, left: 0, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 12, fill: '#475569' }}
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={52}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#475569' }}
                  allowDecimals={chartMode === 'percentage'}
                  domain={chartMode === 'percentage' ? [0, 100] : undefined}
                />
                <Tooltip
                  formatter={(value: number) =>
                    chartMode === 'percentage' ? `${value.toFixed(2)}%` : String(value)
                  }
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar
                  dataKey="invited"
                  stackId={chartMode === 'count' ? 'pipeline' : undefined}
                  fill="#38bdf8"
                  name="Invited"
                  radius={[3, 3, 0, 0]}
                />
                <Bar dataKey="in_progress" stackId={chartMode === 'count' ? 'pipeline' : undefined} fill="#f59e0b" name="In Progress" />
                <Bar dataKey="completed" stackId={chartMode === 'count' ? 'pipeline' : undefined} fill="#14b8a6" name="Completed" />
                <Bar dataKey="approved" stackId={chartMode === 'count' ? 'pipeline' : undefined} fill="#10b981" name="Approved" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold">Pipeline Mix</h2>
        {pipelineMixDisplayData.length === 0 ? (
          <div className="py-10 text-center text-slate-800">No pipeline data yet.</div>
        ) : (
          <div className="h-60 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pipelineMixDisplayData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={85}
                  labelLine={false}
                  label={({ name, value }) =>
                    chartMode === 'percentage'
                      ? `${name} ${Number(value || 0).toFixed(0)}%`
                      : `${name} ${Number(value || 0)}`
                  }
                >
                  {pipelineMixDisplayData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, _name: string, item: { payload?: { raw?: number } }) =>
                    chartMode === 'percentage'
                      ? `${value.toFixed(2)}%`
                      : String(item?.payload?.raw ?? value)
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        <h3 className="text-sm font-semibold mt-4 text-slate-800">Decision Mix</h3>
        {decisionMixDisplayData.length === 0 ? (
          <p className="text-xs text-slate-800 mt-2">No decisions recorded yet.</p>
        ) : (
          <div className="h-44 mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={decisionMixDisplayData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={58}>
                  {decisionMixDisplayData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, _name: string, item: { payload?: { raw?: number } }) =>
                    chartMode === 'percentage'
                      ? `${value.toFixed(2)}%`
                      : String(item?.payload?.raw ?? value)
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
};

export default OperationsDashboardChartsSection;

