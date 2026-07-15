import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Filter, ListTodo } from 'lucide-react';
import { getQueueList, cancelQueueTask, retryQueueTask, QueueItem } from '../api/queue';

export function QueuePage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [sourceFilter, setSourceFilter] = useState<string>('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['queue', statusFilter, sourceFilter],
    queryFn: () => getQueueList({ status: statusFilter, source: sourceFilter }),
    refetchInterval: 5000,
  });

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => cancelQueueTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: (taskId: string) => retryQueueTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] });
    },
  });

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex flex-col gap-4 text-stone-800 font-sans">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-stone-200/60 bg-white/70 p-4 shadow-2xs backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700 border border-blue-100">
            <ListTodo size={22} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-900 leading-none">Generation Queue</h1>
            <p className="mt-1 text-xs text-stone-500 font-medium">
              Persistent queue for DailyFX image generation tasks.
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex h-9 items-center justify-center rounded-xl border border-stone-200 bg-white px-3.5 text-xs font-semibold text-stone-700 shadow-2xs transition hover:bg-stone-50 hover:text-stone-950"
        >
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="rounded-2xl border border-stone-200/60 bg-white/70 p-4 shadow-2xs backdrop-blur-md">
        <div className="flex items-center gap-1.5 text-xs font-bold text-stone-800 uppercase tracking-wider mb-3">
          <Filter size={13} />
          <span>Filters</span>
        </div>
        <div className="flex flex-wrap gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold text-stone-500 uppercase tracking-wider">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-lg border border-stone-200 bg-white/80 px-2.5 text-xs text-stone-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="cancel_requested">Cancel Requested</option>
              <option value="cancelled">Cancelled</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold text-stone-500 uppercase tracking-wider">Source</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="h-9 rounded-lg border border-stone-200 bg-white/80 px-2.5 text-xs text-stone-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All</option>
              <option value="schedule">Schedule</option>
              <option value="run_now">Run Now</option>
              <option value="studio">Studio</option>
              <option value="cli">CLI</option>
              <option value="retry">Retry</option>
            </select>
          </div>
        </div>
      </div>

      {/* Task list */}
      {isLoading ? (
        <div className="flex justify-center items-center py-20 text-stone-400">
          <p className="animate-pulse text-sm font-semibold">Loading tasks...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm">
          An error occurred while loading the queue.
        </div>
      ) : (
        <>
          {/* Desktop Table View */}
          <div className="hidden md:block rounded-2xl border border-stone-200/60 bg-white/70 shadow-2xs backdrop-blur-md overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-stone-200 bg-stone-50/50">
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Task ID</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Status</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Priority</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Attempt</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Progress</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Created</th>
                  <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {data?.items && data.items.length > 0 ? (
                  data.items.map((item: QueueItem) => (
                    <tr key={item.task_id} className="hover:bg-stone-50/40 transition-colors">
                      <td className="p-4 text-xs font-mono text-stone-700">{item.task_id}</td>
                      <td className="p-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                          item.status === 'succeeded' ? 'bg-emerald-50 text-emerald-700 border-emerald-200/60' :
                          item.status === 'failed' ? 'bg-red-50 text-red-700 border-red-200/60' :
                          item.status === 'running' ? 'bg-blue-50 text-blue-700 border-blue-200/60 animate-pulse' :
                          item.status === 'cancel_requested' ? 'bg-amber-50 text-amber-700 border-amber-200/60 animate-pulse' :
                          item.status === 'cancelled' ? 'bg-stone-50 text-stone-600 border-stone-200' :
                          'bg-stone-50 text-stone-600 border-stone-200'
                        }`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="p-4 text-xs text-stone-600 capitalize">{item.priority}</td>
                      <td className="p-4 text-xs text-stone-600">{item.attempt}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          {(() => {
                            const pct = item.progress != null
                              ? (item.progress <= 1.0 ? item.progress * 100 : item.progress)
                              : 0;
                            return (
                              <>
                                <div className="w-16 bg-stone-200 rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="text-[10px] text-stone-500 font-mono">{Math.round(pct)}%</span>
                              </>
                            );
                          })()}
                        </div>
                      </td>
                      <td className="p-4 text-xs text-stone-500">{formatTime(item.created_at)}</td>
                      <td className="p-4 text-right">
                        {item.status === 'queued' && (
                          <button
                            onClick={() => cancelMutation.mutate(item.task_id)}
                            disabled={cancelMutation.isPending}
                            className="text-xs px-2.5 py-1 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg border border-red-200 transition-colors"
                          >
                            Cancel
                          </button>
                        )}
                        {item.status === 'running' && (
                          <button
                            onClick={() => cancelMutation.mutate(item.task_id)}
                            disabled={cancelMutation.isPending}
                            className="text-xs px-2.5 py-1 text-amber-600 hover:text-amber-700 hover:bg-amber-50 rounded-lg border border-amber-200 transition-colors"
                          >
                            Cancel
                          </button>
                        )}
                        {(item.status === 'failed' || item.status === 'cancelled') && (
                          <button
                            onClick={() => retryMutation.mutate(item.task_id)}
                            disabled={retryMutation.isPending}
                            className="text-xs px-2.5 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg border border-blue-200 transition-colors"
                          >
                            Retry
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-stone-400 text-xs">
                      The task queue is currently empty.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List View */}
          <div className="grid gap-3 md:hidden" aria-label="Generation queue mobile list">
            {data?.items && data.items.length > 0 ? (
              data.items.map((item: QueueItem) => (
                <div key={item.task_id} className="app-surface p-4 flex flex-col gap-3">
                  <div className="flex justify-between items-start gap-2">
                    <span className="font-mono text-xs text-stone-700 truncate max-w-[180px]">{item.task_id}</span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                      item.status === 'succeeded' ? 'bg-emerald-50 text-emerald-700 border-emerald-200/60' :
                      item.status === 'failed' ? 'bg-red-50 text-red-700 border-red-200/60' :
                      item.status === 'running' ? 'bg-blue-50 text-blue-700 border-blue-200/60 animate-pulse' :
                      item.status === 'cancel_requested' ? 'bg-amber-50 text-amber-700 border-amber-200/60 animate-pulse' :
                      item.status === 'cancelled' ? 'bg-stone-50 text-stone-600 border-stone-200' :
                      'bg-stone-50 text-stone-600 border-stone-200'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-stone-500">
                    <span>Priority: <span className="font-semibold text-stone-700 capitalize">{item.priority}</span></span>
                    <span>Attempt: <span className="font-semibold text-stone-700">{item.attempt}</span></span>
                  </div>
                  {/* Progress bar */}
                  <div className="flex items-center gap-2">
                    {(() => {
                      const pct = item.progress != null
                        ? (item.progress <= 1.0 ? item.progress * 100 : item.progress)
                        : 0;
                      return (
                        <>
                          <div className="flex-1 bg-stone-200 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-stone-500 font-mono">{Math.round(pct)}%</span>
                        </>
                      );
                    })()}
                  </div>
                  <div className="text-[11px] text-stone-500">
                    Created: {formatTime(item.created_at)}
                  </div>
                  {/* Mobile Actions */}
                  <div className="flex justify-end gap-2 border-t border-stone-100 pt-3">
                    {item.status === 'queued' && (
                      <button
                        onClick={() => cancelMutation.mutate(item.task_id)}
                        disabled={cancelMutation.isPending}
                        className="w-full text-xs py-1.5 text-center text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg border border-red-200 transition-colors"
                      >
                        Cancel
                      </button>
                    )}
                    {item.status === 'running' && (
                      <button
                        onClick={() => cancelMutation.mutate(item.task_id)}
                        disabled={cancelMutation.isPending}
                        className="w-full text-xs py-1.5 text-center text-amber-600 hover:text-amber-700 hover:bg-amber-50 rounded-lg border border-amber-200 transition-colors"
                      >
                        Cancel
                      </button>
                    )}
                    {(item.status === 'failed' || item.status === 'cancelled') && (
                      <button
                        onClick={() => retryMutation.mutate(item.task_id)}
                        disabled={retryMutation.isPending}
                        className="w-full text-xs py-1.5 text-center text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg border border-blue-200 transition-colors"
                      >
                        Retry
                      </button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="app-surface p-8 text-center text-stone-400 text-xs">
                The task queue is currently empty.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
