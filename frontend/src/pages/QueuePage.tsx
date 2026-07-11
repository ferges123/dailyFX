import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getQueueList, cancelQueueTask, retryQueueTask, QueueItem } from '../api/queue';

export function QueuePage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [sourceFilter, setSourceFilter] = useState<string>('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['queue', statusFilter, sourceFilter],
    queryFn: () => getQueueList({ status: statusFilter, source: sourceFilter }),
    refetchInterval: 5000, // Automatyczny refetch co 5s jako fallback
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
    <div className="p-6 bg-slate-950 text-slate-100 min-h-screen font-sans">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              Generation Queue
            </h1>
            <p className="text-slate-400 mt-1 text-sm">
              Trwała kolejka wykonywania zadań generowania obrazów DailyFX.
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-900 border border-slate-700 hover:border-slate-600 rounded-lg text-sm font-semibold transition-all shadow-sm"
          >
            Odśwież
          </button>
        </div>

        {/* Filtry */}
        <div className="flex flex-wrap gap-4 mb-6 p-4 bg-slate-900/60 border border-slate-800/80 rounded-xl">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-slate-400 font-bold uppercase tracking-wider">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
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

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-slate-400 font-bold uppercase tracking-wider">Źródło</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
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

        {/* Lista zadań */}
        {isLoading ? (
          <div className="flex justify-center items-center py-20 text-slate-400">
            <p className="animate-pulse text-sm font-semibold">Ładowanie zadań...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-950/40 border border-red-800/80 rounded-xl text-red-300 text-sm">
            Wystąpił błąd podczas ładowania kolejki.
          </div>
        ) : (
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/80">
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Task ID</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Priorytet</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Próba</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Postęp</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Utworzono</th>
                  <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-right">Akcje</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data?.items && data.items.length > 0 ? (
                  data.items.map((item: QueueItem) => (
                    <tr key={item.task_id} className="hover:bg-slate-900/30 transition-colors">
                      <td className="p-4 text-sm font-mono text-slate-300">{item.task_id}</td>
                      <td className="p-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                          item.status === 'succeeded' ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60' :
                          item.status === 'failed' ? 'bg-rose-950/40 text-rose-400 border-rose-800/60' :
                          item.status === 'running' ? 'bg-blue-950/40 text-blue-400 border-blue-800/60 animate-pulse' :
                          item.status === 'cancel_requested' ? 'bg-amber-950/40 text-amber-400 border-amber-800/60 animate-pulse' :
                          item.status === 'cancelled' ? 'bg-slate-800 text-slate-400 border-slate-700' :
                          'bg-slate-900 text-slate-300 border-slate-800'
                        }`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-slate-300 capitalize">{item.priority}</td>
                      <td className="p-4 text-sm text-slate-300">{item.attempt}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                              style={{ width: `${item.progress ?? 0}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400 font-mono">{Math.round(item.progress ?? 0)}%</span>
                        </div>
                      </td>
                      <td className="p-4 text-sm text-slate-400">{formatTime(item.created_at)}</td>
                      <td className="p-4 text-right">
                        {item.status === 'queued' && (
                          <button
                            onClick={() => cancelMutation.mutate(item.task_id)}
                            disabled={cancelMutation.isPending}
                            className="text-xs px-2.5 py-1 text-rose-400 hover:text-rose-300 hover:bg-rose-950/30 rounded border border-rose-900/40 hover:border-rose-800/60 transition-colors"
                          >
                            Anuluj
                          </button>
                        )}
                        {item.status === 'running' && (
                          <button
                            onClick={() => cancelMutation.mutate(item.task_id)}
                            disabled={cancelMutation.isPending}
                            className="text-xs px-2.5 py-1 text-amber-400 hover:text-amber-300 hover:bg-amber-950/30 rounded border border-amber-900/40 hover:border-amber-800/60 transition-colors"
                          >
                            Anuluj
                          </button>
                        )}
                        {(item.status === 'failed' || item.status === 'cancelled') && (
                          <button
                            onClick={() => retryMutation.mutate(item.task_id)}
                            disabled={retryMutation.isPending}
                            className="text-xs px-2.5 py-1 text-blue-400 hover:text-blue-300 hover:bg-blue-950/30 rounded border border-blue-900/40 hover:border-blue-800/60 transition-colors"
                          >
                            Ponów
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-500 text-sm">
                      Kolejka zadań jest obecnie pusta.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
