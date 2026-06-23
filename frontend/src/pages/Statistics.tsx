import { useQuery } from '@tanstack/react-query';
import { getEffectStats } from '../api/client';
import { BarChart3, ThumbsUp, ThumbsDown, Play } from 'lucide-react';
import { ErrorBanner, InlineSpinner } from '../components/ErrorUI';

export function StatisticsPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['effect-stats'],
    queryFn: getEffectStats,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <InlineSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl p-4">
        <ErrorBanner error={error} />
      </div>
    );
  }

  // Sort stats by runs descending
  const sortedStats = [...(stats || [])].sort((a, b) => b.total_runs - a.total_runs);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 md:space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-800/10 text-emerald-800">
          <BarChart3 size={24} />
        </div>
        <div>
          <h1 className="text-lg font-bold text-stone-900 md:text-xl">
            Effect Statistics
          </h1>
          <p className="text-xs text-stone-500 md:text-sm">
            Track which photo effects were triggered and your ratings.
          </p>
        </div>
      </div>

      <div className="app-surface p-4 md:p-6">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-stone-200 text-[10px] font-bold text-stone-500 uppercase tracking-wider">
                <th className="pb-3 px-4">Effect</th>
                <th className="pb-3 px-4">Total Runs</th>
                <th className="pb-3 px-4">Likes</th>
                <th className="pb-3 px-4">Dislikes</th>
                <th className="pb-3 px-4">Popularity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 text-sm">
              {sortedStats.map((stat) => {
                const totalRatings = stat.likes + stat.dislikes;
                const likedPercent = totalRatings > 0 
                  ? Math.round((stat.likes / totalRatings) * 100) 
                  : 0;
                  
                return (
                  <tr key={stat.effect_id} className="hover:bg-stone-50/50 transition">
                    <td className="py-3 px-4 font-semibold text-stone-950">
                      {stat.title}
                    </td>
                    <td className="py-3 px-4 text-stone-600">
                      <span className="inline-flex items-center gap-1.5 font-medium">
                        <Play size={13} className="text-stone-400" />
                        {stat.total_runs}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-emerald-800">
                      <span className="inline-flex items-center gap-1.5 font-semibold">
                        <ThumbsUp size={13} />
                        {stat.likes}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-rose-800">
                      <span className="inline-flex items-center gap-1.5 font-semibold">
                        <ThumbsDown size={13} />
                        {stat.dislikes}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {totalRatings > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 bg-stone-200 rounded-full overflow-hidden shrink-0">
                            <div 
                              className="h-full bg-emerald-700 transition-all duration-500" 
                              style={{ width: `${likedPercent}%` }}
                            />
                          </div>
                          <span className="text-xs text-stone-500 font-semibold whitespace-nowrap">
                            {likedPercent}% liked
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-stone-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {sortedStats.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-sm text-stone-400">
                    No statistics logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
