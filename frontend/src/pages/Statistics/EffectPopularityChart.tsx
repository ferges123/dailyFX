import { memo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Flame } from 'lucide-react';
import type * as client from '../../api/client';

interface EffectPopularityChartProps {
  stats: client.EffectStats[];
  activeTab: 'standard' | 'ai';
}

export const EffectPopularityChart = memo(function EffectPopularityChart({
  stats,
  activeTab,
}: EffectPopularityChartProps) {
  const filtered = stats
    .filter((s) => (activeTab === 'ai' ? s.effect_id.startsWith('ai_') : !s.effect_id.startsWith('ai_')))
    .filter((s) => s.total_runs > 0)
    .sort((a, b) => b.total_runs - a.total_runs)
    .slice(0, 10);

  const barColor = activeTab === 'ai' ? '#7c3aed' : '#059669';

  if (filtered.length === 0) {
    return null;
  }

  return (
    <div className="app-surface p-4 md:p-6" data-testid="effect-popularity-chart">
      <div className="mb-4 flex items-center gap-2">
        <Flame size={20} className={activeTab === 'ai' ? 'text-purple-700' : 'text-emerald-700'} />
        <div>
          <h2 className="text-sm font-bold text-stone-900 md:text-base">Popular Effects</h2>
          <p className="text-[11px] text-stone-500">Most frequently used effects in this category</p>
        </div>
      </div>
      <div className="h-56 min-w-0 md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={filtered}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: '#78716c' }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <YAxis
              type="category"
              dataKey="title"
              tick={{ fontSize: 10, fill: '#78716c' }}
              tickLine={false}
              axisLine={{ stroke: '#d6d3d1' }}
              width={100}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fafaf9',
                border: '1px solid #e7e5e4',
                borderRadius: '8px',
                fontSize: '11px',
              }}
              cursor={{ fill: '#f5f5f4', opacity: 0.5 }}
            />
            <Bar dataKey="total_runs" name="Runs" fill={barColor} radius={[0, 4, 4, 0]} barSize={12} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
});
