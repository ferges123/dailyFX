import { Database, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  clearOfflineImageCaches,
  clearOfflineStorage,
  isPersistableQuery,
} from '../../offline/storage';

function formatBytes(bytes: number | undefined): string {
  if (bytes == null) return 'Unavailable';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function OfflineStorageSection() {
  const queryClient = useQueryClient();
  const [usage, setUsage] = useState<number>();
  const [quota, setQuota] = useState<number>();
  const [cleared, setCleared] = useState(false);

  const refreshEstimate = () => {
    void navigator.storage?.estimate().then((estimate) => {
      setUsage(estimate.usage);
      setQuota(estimate.quota);
    });
  };

  useEffect(() => {
    refreshEstimate();
  }, []);

  const handleClear = async () => {
    await clearOfflineStorage().catch(() => undefined);
    clearOfflineImageCaches();
    queryClient.removeQueries({
      predicate: (query) => isPersistableQuery(query.queryKey),
    });
    setCleared(true);
    refreshEstimate();
  };

  return (
    <div className="app-panel grid gap-3 p-3 md:p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-stone-900">
            <Database size={15} />
            Offline data
          </div>
          <p className="mt-1 text-xs leading-5 text-stone-500">
            Saved Gallery/History metadata and image cache used when the server
            is unavailable.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleClear()}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl border border-red-200 bg-white/80 px-3 text-xs font-semibold text-red-700 transition hover:border-red-300 hover:bg-red-50"
        >
          <Trash2 size={14} />
          Clear
        </button>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
        <span>Used: {formatBytes(usage)}</span>
        <span>Quota: {formatBytes(quota)}</span>
        {cleared && (
          <span className="font-semibold text-emerald-700">Cleared</span>
        )}
      </div>
    </div>
  );
}
