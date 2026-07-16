import { useState, useEffect } from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { getScheduleDiagnostics, type ScheduleDiagnosticsResponse } from '../../api/client';

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

      <div className="grid grid-cols-3 gap-1.5 text-center">
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
    </div>
  );
}

