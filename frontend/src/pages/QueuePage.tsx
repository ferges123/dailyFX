import React, { useState } from 'react';
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
    mutationFn: cancelQueueTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue'] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: retryQueueTask,
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
              Trwała kolejka wykonywania zadań generowania obrazów DailyFX.
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex h-9 items-center justify-center rounded-xl border border-stone-200 bg-white px-3.5 text-xs font-semibold text-stone-700 shadow-2xs transition hover:bg-stone-50 hover:text-stone-950"
        >
          Odśwież
        </button>
      </div>

      {/* Filtry */}
      <div className="rounded-2xl border border-stone-200/60 bg-white/70 p-4 shadow-2xs backdrop-blur-md">
        <div className="flex items-center gap-1.5 text-xs font-bold text-stone-800 uppercase tracking-wider mb-3">
          <Filter size={13} />
          <span>Filtry</span>
        </div>
        <div className="flex flex-wrap gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold text-stone-500 uppercase tracking-wider">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-lg border border-stone-200 bg-white/80 px-2.5 text-xs text-stone-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">Wszystkie</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="cancel_requested">Cancel Requested</option>
              <option value="cancelled">Cancelled</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-bold text-stone-500 uppercase tracking-wider">Źródło</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="h-9 rounded-lg border border-stone-200 bg-white/80 px-2.5 text-xs text-stone-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">Wszystkie</option>
              <option value="schedule">Schedule</option>
              <option value="run_now">Run Now</option>
              <option value="studio">Studio</option>
              <option value="cli">CLI</option>
              <option value="retry">Retry</option>
            </select>
          </div>
        </div>
      </div>

      {/* Lista zadań */}
      {isLoading ? (
        <div className="flex justify-center items-center py-20 text-stone-400">
          <p className="animate-pulse text-sm font-semibold">Ładowanie zadań...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm">
          Wystąpił błąd podczas ładowania kolejki.
        </div>
      ) : (
        <div className="rounded-2xl border border-stone-200/60 bg-white/70 shadow-2xs backdrop-blur-md overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-stone-200 bg-stone-50/50">
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Task ID</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Status</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Priorytet</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Próba</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Postęp</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider">Utworzono</th>
                <th className="p-4 text-[10px] font-bold text-stone-500 uppercase tracking-wider text-right">Akcje</th>
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
                        <div className="w-16 bg-stone-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${item.progress ?? 0}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-stone-500 font-mono">{Math.round(item.progress ?? 0)}%</span>
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
                          Anuluj
                        </button>
                      )}
                      {item.status === 'running' && (
                        <button
                          onClick={() => cancelMutation.mutate(item.task_id)}
                          disabled={cancelMutation.isPending}
                          className="text-xs px-2.5 py-1 text-amber-600 hover:text-amber-700 hover:bg-amber-50 rounded-lg border border-amber-200 transition-colors"
                        >
                          Anuluj
                        </button>
                      )}
                      {(item.status === 'failed' || item.status === 'cancelled') && (
                        <button
                          onClick={() => retryMutation.mutate(item.task_id)}
                          disabled={retryMutation.isPending}
                          className="text-xs px-2.5 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg border border-blue-200 transition-colors"
                        >
                          Ponów
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-stone-400 text-xs">
                    Kolejka zadań jest obecnie pusta.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
