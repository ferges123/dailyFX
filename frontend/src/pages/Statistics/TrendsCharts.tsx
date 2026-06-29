import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import { getStatsTrends } from '../../api/client';
import { InlineSpinner } from '../../components/ErrorUI';
import { BarChart3, TrendingUp } from 'lucide-react';

type ViewMode = 'daily' | 'weekly';
type ChartType = 'generations' | 'ratings';

export function TrendsCharts() {
  const [viewMode, setViewMode] = useState<ViewMode>('daily');
  const [chartType, setChartType] = useState<ChartType>('generations');

  const { data: trends, isLoading, error } = useQuery({
    queryKey: ['stats-trends'],
    queryFn: getStatsTrends,
  });

  if (isLoading) {
    return (
      <div className="app-surface p-4 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <TrendingUp size={20} className="text-emerald-700" />
          <h2 className="text-lg font-bold text-stone-900">Trends</h2>
        </div>
        <div className="flex justify-center py-8">
          <InlineSpinner />
        </div>
      </div>
    );
  }

  if (error || !trends) {
    return (
      <div className="app-surface p-4 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <TrendingUp size={20} className="text-emerald-700" />
          <h2 className="text-lg font-bold text-stone-900">Trends</h2>
        </div>
        <p className="text-sm text-stone-500 text-center py-4">
          Unable to load trends data
        </p>
      </div>
    );
  }

  const data = viewMode === 'daily' ? trends.daily : trends.weekly;

  const chartData = data.map((point) => ({
    ...point,
    label: viewMode === 'daily'
      ? new Date(point.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
      : point.date,
  }));

  return (
    <div className="app-surface p-4 md:p-6">
      <div className="mb-4 grid gap-3 sm:flex sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp size={20} className="text-emerald-700" />
          <h2 className="text-lg font-bold text-stone-900">Trends</h2>
        </div>
        <div className="grid min-w-0 gap-2 sm:flex">
          <div className="grid grid-cols-2 rounded-lg bg-stone-100 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode('daily')}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                viewMode === 'daily'
                  ? 'bg-white text-stone-900 shadow-sm'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Daily
            </button>
            <button
              type="button"
              onClick={() => setViewMode('weekly')}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                viewMode === 'weekly'
                  ? 'bg-white text-stone-900 shadow-sm'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Weekly
            </button>
          </div>
          <div className="grid grid-cols-2 rounded-lg bg-stone-100 p-0.5">
            <button
              type="button"
              onClick={() => setChartType('generations')}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                chartType === 'generations'
                  ? 'bg-white text-stone-900 shadow-sm'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Generations
            </button>
            <button
              type="button"
              onClick={() => setChartType('ratings')}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                chartType === 'ratings'
                  ? 'bg-white text-stone-900 shadow-sm'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Ratings
            </button>
          </div>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-stone-400">
          <BarChart3 size={32} className="mb-2 opacity-50" />
          <p className="text-sm">No data available yet</p>
        </div>
      ) : (
        <div className="h-56 min-w-0 md:h-64">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'generations' ? (
              <BarChart data={chartData} margin={{ top: 5, right: 4, left: -18, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: '#78716c' }}
                  tickLine={false}
                  axisLine={{ stroke: '#d6d3d1' }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#78716c' }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fafaf9',
                    border: '1px solid #e7e5e4',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="accepted" name="Accepted" fill="#059669" radius={[2, 2, 0, 0]} />
                <Bar dataKey="rejected" name="Rejected" fill="#dc2626" radius={[2, 2, 0, 0]} />
                <Bar dataKey="failed" name="Failed" fill="#78716c" radius={[2, 2, 0, 0]} />
              </BarChart>
            ) : (
              <LineChart data={chartData} margin={{ top: 5, right: 4, left: -18, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: '#78716c' }}
                  tickLine={false}
                  axisLine={{ stroke: '#d6d3d1' }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#78716c' }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fafaf9',
                    border: '1px solid #e7e5e4',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Line type="monotone" dataKey="likes" name="Likes" stroke="#059669" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="dislikes" name="Dislikes" stroke="#dc2626" strokeWidth={2} dot={false} />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
