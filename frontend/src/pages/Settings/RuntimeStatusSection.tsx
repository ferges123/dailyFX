import { useQuery } from '@tanstack/react-query';
import { Server, RefreshCw, Database, Wifi } from 'lucide-react';
import { getHealth, getDetailedHealth } from '../../api/client';
import { ErrorBanner } from '../../components/ErrorUI';
import { StatusTile } from '../../components/StatusTile';

type RuntimeCheckTone = 'neutral' | 'success' | 'warning' | 'danger';

function runtimeTone(status: string | null | undefined): RuntimeCheckTone {
  if (!status || status === 'checking') return 'neutral';
  if (status === 'ok') return 'success';
  if (
    status === 'not_configured' ||
    status === 'key_missing' ||
    status === 'missing'
  )
    return 'warning';
  return 'danger';
}

function runtimeLabel(status: string | null | undefined): string {
  if (!status || status === 'checking') return 'Checking';
  if (status === 'ok') return 'Healthy';
  if (status === 'not_configured' || status === 'key_missing')
    return 'Not configured';
  if (status === 'missing') return 'Missing';
  if (status === 'stale') return 'Stale';
  return 'Degraded';
}

function formatAge(seconds: number | null | undefined): string | null {
  if (seconds == null) return null;
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(seconds / 3600);
  return `${hours}h ago`;
}

export function RuntimeStatusSection() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const runtimeHealth = useQuery({
    queryKey: ['health-detailed'],
    queryFn: getDetailedHealth,
    retry: false,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const runtimeChecks = runtimeHealth.data?.checks;

  return (
    <div className="app-panel grid gap-3 p-3 md:p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-stone-900">
            Runtime Status
          </div>
          <div className="text-xs text-stone-500">
            Refreshed automatically every 30 seconds.
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            health.refetch();
            runtimeHealth.refetch();
          }}
          className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-xl border border-stone-200 bg-white/80 px-3 text-xs font-semibold text-stone-600 shadow-xs transition hover:border-stone-300 hover:text-stone-900 sm:w-auto"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>
      {runtimeHealth.isError || health.isError ? (
        <ErrorBanner
          error={
            (runtimeHealth.error as Error | string | null) ??
            (health.error as Error | string | null)
          }
          title="Could not load runtime status"
          onRetry={() => {
            health.refetch();
            runtimeHealth.refetch();
          }}
        />
      ) : (
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <StatusTile
            icon={<Server size={14} />}
            label="API"
            value={
              health.isLoading
                ? 'Checking'
                : health.data?.status === 'ok'
                  ? 'Healthy'
                  : 'Degraded'
            }
            detail={health.data?.version ? `v${health.data.version}` : null}
            tone={
              health.isError
                ? 'danger'
                : health.isLoading
                  ? 'neutral'
                  : 'success'
            }
          />
          <StatusTile
            icon={<RefreshCw size={14} />}
            label="Scheduler"
            value={runtimeLabel(runtimeChecks?.scheduler?.status)}
            detail={
              formatAge(runtimeChecks?.scheduler?.age_seconds) ??
              runtimeChecks?.scheduler?.detail ??
              null
            }
            tone={runtimeTone(runtimeChecks?.scheduler?.status)}
          />
          <StatusTile
            icon={<Database size={14} />}
            label="Database"
            value={runtimeLabel(runtimeChecks?.database?.status)}
            detail={runtimeChecks?.database?.detail ?? null}
            tone={runtimeTone(runtimeChecks?.database?.status)}
          />
          <StatusTile
            icon={<Wifi size={14} />}
            label="Immich"
            value={runtimeLabel(runtimeChecks?.immich?.status)}
            detail={
              runtimeChecks?.immich?.version
                ? `v${runtimeChecks?.immich?.version}`
                : (runtimeChecks?.immich?.detail ?? null)
            }
            tone={runtimeTone(runtimeChecks?.immich?.status)}
          />
        </div>
      )}
    </div>
  );
}
