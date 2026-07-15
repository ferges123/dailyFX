import { useState, useEffect } from 'react';
import { Loader2, AlertCircle, FileImage, RefreshCw } from 'lucide-react';
import { getScheduleDiagnostics, type ScheduleDiagnosticsResponse } from '../../api/client';
import { formatDateTime } from '../datetime.utils';

interface ScheduleDiagnosticsProps {
  scheduleId: number;
}

export function ScheduleDiagnostics({ scheduleId }: ScheduleDiagnosticsProps) {
  const [data, setData] = useState<ScheduleDiagnosticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getScheduleDiagnostics(scheduleId);
      setData(res);
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'Failed to fetch diagnostics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
  }, [scheduleId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-stone-500 text-xs justify-center">
        <Loader2 className="animate-spin text-emerald-600" size={14} />
        Loading photo diagnostics...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 py-2 px-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg text-xs">
        <AlertCircle size={14} className="shrink-0" />
        <div className="flex-1">{error}</div>
        <button
          onClick={fetchDiagnostics}
          className="text-rose-700 hover:text-rose-900 font-semibold inline-flex items-center gap-1"
        >
          <RefreshCw size={10} /> Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mt-2.5 space-y-2 border-t border-stone-100 pt-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-stone-400 uppercase tracking-wider">
          Photo pool diagnostics
        </span>
        <button
          type="button"
          onClick={fetchDiagnostics}
          className="inline-flex items-center gap-1 text-[9px] font-semibold text-stone-500 hover:text-stone-800 transition"
        >
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-5 text-center">
        <div className="rounded-lg bg-stone-50 border border-stone-200/60 p-1.5">
          <div className="text-[10px] text-stone-500">All</div>
          <div className="text-sm font-bold text-stone-800">{data.total_candidates}</div>
        </div>
        <div className="rounded-lg bg-emerald-50/50 border border-emerald-100 p-1.5">
          <div className="text-[10px] text-emerald-700">Unused</div>
          <div className="text-sm font-bold text-stone-800">{data.never_used_count}</div>
        </div>
        <div className="rounded-lg bg-amber-50/50 border border-amber-100 p-1.5">
          <div className="text-[10px] text-amber-700">Released</div>
          <div className="text-sm font-bold text-stone-800">{data.released_count}</div>
        </div>
        <div className="rounded-lg bg-blue-50/50 border border-blue-100 p-1.5">
          <div className="text-[10px] text-blue-700">Used</div>
          <div className="text-sm font-bold text-emerald-800">{data.accepted_count}</div>
        </div>
        <div className="rounded-lg bg-stone-100 border border-stone-200/50 p-1.5 opacity-60">
          <div className="text-[10px] text-stone-600">Pending</div>
          <div className="text-sm font-bold text-stone-700">{data.pending_count}</div>
        </div>
      </div>

      <div>
        <div className="text-[9.5px] font-bold text-stone-500 mb-1.5">
          Selection queue (top 10 candidates):
        </div>
        {data.selection_order.length === 0 ? (
          <div className="text-[10px] text-stone-500 italic bg-stone-50 rounded-lg p-2 text-center">
            No eligible photos in the pool (all might be pending or resources are missing).
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-stone-200 bg-white">
            <table className="w-full text-left border-collapse text-[10px]">
              <thead>
                <tr className="bg-stone-50 border-b border-stone-200 text-stone-500 font-semibold">
                  <th className="px-2 py-1 w-10 text-center">Pos.</th>
                  <th className="px-2 py-1">Photo</th>
                  <th className="px-2 py-1 w-20">Status</th>
                  <th className="px-2 py-1 w-32">Last release/use</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {data.selection_order.map((asset, idx) => {
                  const statusColors: Record<string, string> = {
                    never_used: 'text-emerald-700 bg-emerald-50 border-emerald-100',
                    released: 'text-amber-700 bg-amber-50 border-amber-100',
                    accepted: 'text-blue-700 bg-blue-50 border-blue-100',
                  };

                  return (
                    <tr key={asset.id} className="hover:bg-stone-50/50 transition">
                      <td className="px-2 py-1 text-center font-bold text-stone-400">{idx + 1}</td>
                      <td className="px-2 py-1 font-medium text-stone-800">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <FileImage size={11} className="text-stone-400 shrink-0" />
                          <span className="truncate" title={asset.original_file_name || asset.id}>
                            {asset.original_file_name || asset.id}
                          </span>
                        </div>
                      </td>
                      <td className="px-2 py-1">
                        <span className={`inline-block px-1 rounded border text-[9px] leading-3 font-medium ${statusColors[asset.status] ?? 'bg-stone-50 border-stone-200 text-stone-600'}`}>
                          {asset.status === 'never_used' ? 'new' : asset.status === 'released' ? 'released' : 'used'}
                        </span>
                      </td>
                      <td className="px-2 py-1 text-stone-500">
                        {asset.last_action_at ? formatDateTime(asset.last_action_at) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
