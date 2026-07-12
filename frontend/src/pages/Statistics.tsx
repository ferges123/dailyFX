import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getEffectStats } from '../api/client';
import type * as client from '../api/client';
import { useState } from 'react';
import {
  AlertTriangle,
  ArrowUpDown,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  Play,
  Star,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { ErrorBanner, InlineSpinner } from '../components/ErrorUI';
import { TrendsCharts } from './Statistics/TrendsCharts';
import { EffectPopularityChart } from './Statistics/EffectPopularityChart';

function formatLastRun(value: string | null) {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function qualityLabel(label: client.EffectStats['quality_label']) {
  if (label === 'insufficient_data') return 'Not enough ratings';
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function qualityClass(label: client.EffectStats['quality_label']) {
  if (label === 'excellent') return 'bg-emerald-100 text-emerald-800';
  if (label === 'good') return 'bg-lime-100 text-lime-800';
  if (label === 'mixed') return 'bg-amber-100 text-amber-800';
  if (label === 'poor') return 'bg-rose-100 text-rose-800';
  return 'bg-stone-100 text-stone-600';
}

function sortStatsForQuality(a: client.EffectStats, b: client.EffectStats) {
  const aHasData = a.quality_label !== 'insufficient_data';
  const bHasData = b.quality_label !== 'insufficient_data';
  if (aHasData !== bHasData) return aHasData ? -1 : 1;
  if (b.quality_score !== a.quality_score)
    return b.quality_score - a.quality_score;
  return b.total_runs - a.total_runs;
}

type SortKey =
  | 'title'
  | 'total_runs'
  | 'like_rate'
  | 'unrated_count'
  | 'last_run_at'
  | 'quality_score';
type SortOrder = 'asc' | 'desc';

export function StatisticsPage({ defaultTab = 'ai' }: { defaultTab?: 'ai' | 'standard' } = {}) {
  const [activeTab, setActiveTab] = useState<'ai' | 'standard'>(defaultTab);

  const [sortKey, setSortKey] = useState<SortKey>('title');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');


  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
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

  const sortedStats = [...(stats || [])].sort(sortStatsForQuality);

  // Group stats
  const standardStats = sortedStats.filter(
    (stat) => !stat.effect_id.startsWith('ai_'),
  );
  const aiStats = sortedStats.filter((stat) =>
    stat.effect_id.startsWith('ai_'),
  );

  const currentStats = activeTab === 'standard' ? standardStats : aiStats;

  const desktopSortedStats = [...currentStats].sort((a, b) => {
    const valA = a[sortKey];
    const valB = b[sortKey];

    if (sortKey === 'title') {
      const titleA = a.title || '';
      const titleB = b.title || '';
      return sortOrder === 'asc'
        ? titleA.localeCompare(titleB)
        : titleB.localeCompare(titleA);
    }

    if (sortKey === 'last_run_at') {
      if (valA === null && valB === null) return 0;
      if (valA === null) return 1;
      if (valB === null) return -1;
      const timeA = new Date(valA).getTime();
      const timeB = new Date(valB).getTime();
      return sortOrder === 'asc' ? timeA - timeB : timeB - timeA;
    }

    if (sortKey === 'like_rate') {
      if (valA === null && valB === null) return 0;
      if (valA === null) return 1;
      if (valB === null) return -1;
    }

    const numA = (valA ?? 0) as number;
    const numB = (valB ?? 0) as number;

    if (numA !== numB) {
      return sortOrder === 'asc' ? numA - numB : numB - numA;
    }

    return a.title.localeCompare(b.title);
  });

  const renderHeader = (label: string, key: SortKey) => {
    const isActive = sortKey === key;
    return (
      <th className="px-4 pb-3">
        <button
          type="button"
          onClick={() => handleSort(key)}
          className="flex items-center gap-1 text-[10px] font-bold uppercase text-stone-500 hover:text-stone-800 transition-colors focus:outline-none group"
        >
          <span>{label}</span>
          <span className="text-stone-400">
            {isActive ? (
              sortOrder === 'asc' ? (
                <ChevronUp size={13} className="text-emerald-700" />
              ) : (
                <ChevronDown size={13} className="text-emerald-700" />
              )
            ) : (
              <ArrowUpDown
                size={11}
                className="opacity-40 group-hover:opacity-100 transition-opacity"
              />
            )}
          </span>
        </button>
      </th>
    );
  };

  const totalRuns = sortedStats.reduce((sum, stat) => sum + stat.total_runs, 0);
  const ratedRuns = sortedStats.reduce(
    (sum, stat) => sum + stat.rating_count,
    0,
  );
  const bestRated = sortedStats.find(
    (stat) => stat.quality_label !== 'insufficient_data',
  );
  const needsAttention = sortedStats.filter((stat) =>
    ['mixed', 'poor'].includes(stat.quality_label),
  ).length;

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

      <div className="grid grid-cols-2 gap-2.5 overflow-hidden xl:grid-cols-4">
        <div className="app-surface p-3 overflow-hidden">
          <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
            <Play size={15} />
            Total runs
          </div>
          <div className="mt-2 text-xl font-bold text-stone-950">
            {totalRuns}
          </div>
          <div className="text-xs text-stone-500">{ratedRuns} rated</div>
        </div>
        <div className="app-surface p-3 overflow-hidden">
          <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
            <ThumbsUp size={15} />
            Rated runs
          </div>
          <div className="mt-2 text-xl font-bold text-stone-950">
            {ratedRuns}
          </div>
          <div className="text-xs text-stone-500">
            {totalRuns > 0 ? Math.round((ratedRuns / totalRuns) * 100) : 0}%
            coverage
          </div>
        </div>
        <div className="app-surface p-3 overflow-hidden">
          <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
            <Star size={15} />
            Best rated
          </div>
          <div className="mt-2 truncate text-xl font-bold text-stone-950">
            {bestRated ? bestRated.title : 'None'}
          </div>
          <div className="text-xs text-stone-500">
            {bestRated?.like_rate != null
              ? `${bestRated.like_rate}% liked`
              : 'No rated effects'}
          </div>
        </div>
        <div className="app-surface p-3 overflow-hidden">
          <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
            <AlertTriangle size={15} />
            Needs attention
          </div>
          <div className="mt-2 text-xl font-bold text-stone-950">
            {needsAttention}
          </div>
          <div className="text-xs text-stone-500">Mixed or poor quality</div>
        </div>
      </div>

      <TrendsCharts />

      <EffectPopularityChart stats={stats || []} activeTab={activeTab} />

      <div className="grid gap-4">
        {/* Tabs for AI and Standard Effects */}
        <div className="flex gap-1.5 border-b border-stone-200/70 pb-2">
          <button
            type="button"
            onClick={() => setActiveTab('ai')}
            className={`flex items-center gap-2 rounded-t-xl border-b-2 px-4 py-2 text-xs font-semibold transition-all duration-200 -mb-px ${
              activeTab === 'ai'
                ? 'border-emerald-600 bg-transparent text-emerald-700'
                : 'border-transparent bg-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <span>AI</span>
            <span
              className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                activeTab === 'ai'
                  ? 'bg-purple-100 text-purple-800'
                  : 'bg-stone-100 text-stone-500'
              }`}
            >
              {aiStats.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('standard')}
            className={`flex items-center gap-2 rounded-t-xl border-b-2 px-4 py-2 text-xs font-semibold transition-all duration-200 -mb-px ${
              activeTab === 'standard'
                ? 'border-emerald-600 bg-transparent text-emerald-700'
                : 'border-transparent bg-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <span>Standard</span>
            <span
              className={`inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold rounded-full transition-colors ${
                activeTab === 'standard'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-stone-100 text-stone-500'
              }`}
            >
              {standardStats.length}
            </span>
          </button>
        </div>

        <div
          aria-label="Effect statistics mobile list"
          className="grid gap-2.5 md:hidden"
          role="list"
        >
          {currentStats.map((stat) => {
            const totalRatings = stat.likes + stat.dislikes;
            const likedPercent =
              totalRatings > 0
                ? Math.round((stat.likes / totalRatings) * 100)
                : 0;

            return (
              <article
                key={stat.effect_id}
                className="app-surface grid gap-3 p-3"
                role="listitem"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      to={`/history?search=${encodeURIComponent(stat.effect_id)}`}
                      className="block truncate text-sm font-bold text-stone-950 hover:text-emerald-800 hover:underline"
                    >
                      {stat.title}
                    </Link>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs font-semibold text-stone-500">
                      <span className="inline-flex items-center gap-1">
                        <Play size={12} className="text-stone-400" />
                        {stat.total_runs} runs
                      </span>
                      <span>{stat.unrated_count} unrated</span>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-bold ${qualityClass(stat.quality_label)}`}
                  >
                    {qualityLabel(stat.quality_label)}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-xl border border-stone-200/80 bg-white/70 p-2">
                    <div className="font-semibold text-stone-500">Rating</div>
                    <div className="mt-1 font-bold text-stone-900">
                      {stat.like_rate != null
                        ? `${stat.like_rate}% liked`
                        : 'No ratings'}
                    </div>
                  </div>
                  <div className="rounded-xl border border-stone-200/80 bg-white/70 p-2">
                    <div className="font-semibold text-stone-500">Status</div>
                    <div className="mt-1 font-bold text-stone-900">
                      {stat.uploaded_runs} uploaded
                    </div>
                  </div>
                  <div className="rounded-xl border border-stone-200/80 bg-white/70 p-2">
                    <div className="font-semibold text-stone-500">Last run</div>
                    <div className="mt-1 truncate font-bold text-stone-900">
                      {formatLastRun(stat.last_run_at)}
                    </div>
                  </div>
                </div>

                {stat.like_rate != null && (
                  <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                    <div
                      className="h-full bg-emerald-700"
                      style={{ width: `${likedPercent}%` }}
                    />
                  </div>
                )}
              </article>
            );
          })}
          {currentStats.length === 0 && (
            <div className="app-surface py-8 text-center text-sm text-stone-400">
              No statistics logged yet.
            </div>
          )}
        </div>

        <div className="app-surface hidden p-4 md:block md:p-6">
          <div className="overflow-x-auto">
            <table className="hidden w-full border-collapse text-left md:table">
              <thead>
                <tr className="border-b border-stone-200 text-[10px] font-bold uppercase text-stone-500">
                  {renderHeader('Effect', 'title')}
                  {renderHeader('Runs', 'total_runs')}
                  {renderHeader('Rating', 'like_rate')}
                  {renderHeader('Unrated', 'unrated_count')}
                  <th className="px-4 pb-3 text-[10px] font-bold uppercase text-stone-500">
                    Status mix
                  </th>
                  {renderHeader('Last run', 'last_run_at')}
                  {renderHeader('Quality', 'quality_score')}
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 text-sm">
                {desktopSortedStats.map((stat) => {
                  const totalRatings = stat.likes + stat.dislikes;
                  const likedPercent =
                    totalRatings > 0
                      ? Math.round((stat.likes / totalRatings) * 100)
                      : 0;

                  return (
                    <tr
                      key={stat.effect_id}
                      className="hover:bg-stone-50/50 transition"
                    >
                      <td className="px-4 py-3 font-semibold text-stone-950">
                        <Link
                          to={`/history?search=${encodeURIComponent(stat.effect_id)}`}
                          className="hover:text-emerald-800 hover:underline"
                        >
                          {stat.title}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-stone-600">
                        <span className="inline-flex items-center gap-1.5 font-medium">
                          <Play size={13} className="text-stone-400" />
                          {stat.total_runs}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {stat.like_rate != null ? (
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-20 shrink-0 overflow-hidden rounded-full bg-stone-200">
                              <div
                                className="h-full bg-emerald-700"
                                style={{ width: `${likedPercent}%` }}
                              />
                            </div>
                            <span className="whitespace-nowrap text-xs font-semibold text-stone-600">
                              {stat.like_rate}% liked
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-stone-400">
                            No ratings
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-stone-500">
                        {stat.unrated_count} unrated
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold">
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-emerald-800">
                            <CheckCircle2 size={12} />
                            {stat.uploaded_runs}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2 py-1 text-stone-700">
                            <Clock3 size={12} />
                            {stat.pending_review_runs}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-1 text-rose-800">
                            <ThumbsDown size={12} />
                            {stat.rejected_runs + stat.failed_runs}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-stone-500">
                        {formatLastRun(stat.last_run_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${qualityClass(stat.quality_label)}`}
                        >
                          {qualityLabel(stat.quality_label)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {currentStats.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-8 text-center text-sm text-stone-400"
                    >
                      No statistics logged yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
