import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw,
  Search,
  Layers
} from 'lucide-react';
import {
  acceptGeneration,
  getImmichAssetDetailUrl,
  getSettings,
  rejectGeneration,
  retryGenerationAcceptance,
  getImmichFilterOptions,
  getImmichAssetExif,
} from '../../api/client';
import { SecureImage } from '../../components/SecureImage';
import { InlineSpinner, ErrorBanner } from '../../components/ErrorUI';
import { formatDateTime } from '../datetime.utils';
import { type HistoryStatusFilter } from '../history.types';
import { useNavigate, useParams } from 'react-router-dom';

import { UploadModal } from './UploadModal';
import { LightboxModal } from './LightboxModal';
import { HistoryDetailPanel } from './HistoryDetailPanel';
import { useHistoryFilters } from './useHistoryFilters';
import { useHistoryQuery } from './useHistoryQuery';
import { useHistorySelection } from './useHistorySelection';
import { useHistoryStreamSync } from './useHistoryStreamSync';

function shouldRetrySettingsQuery(failureCount: number, error: unknown) {
  if (failureCount >= 2) return false;
  if (typeof error === 'object' && error !== null && 'status' in error) {
    const status = (error as { status?: unknown }).status;
    return typeof status === 'number' ? status >= 500 : true;
  }
  return true;
}

export function HistoryPage() {
  const navigate = useNavigate();
  const { taskId } = useParams<{ taskId?: string }>();
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    retry: shouldRetrySettingsQuery,
    retryDelay: (attempt) => Math.min(150 * 2 ** attempt, 300),
    refetchOnWindowFocus: false,
  });
  const queryClient = useQueryClient();
  const historyListRef = useRef<HTMLDivElement>(null);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedHistoryTaskId, setSelectedHistoryTaskId] = useState<string | null>(taskId ?? null);

  const {
    historySearch,
    setHistorySearch,
    debouncedSearch,
    historyStatus,
    setHistoryStatus,
    statusParam,
  } = useHistoryFilters();

  const {
    historyQueryKey,
    filteredHistoryItems,
    streamCursor,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    error,
    refetch: refetchHistory,
    data,
  } = useHistoryQuery(statusParam, debouncedSearch);

  const filterOptions = useQuery({
    queryKey: ['immich-options'],
    queryFn: getImmichFilterOptions,
  });

  const sortedAlbums = useMemo(() => {
    const list = filterOptions.data?.albums ?? [];
    return [...list].sort((a, b) => a.album_name.localeCompare(b.album_name));
  }, [filterOptions.data]);

  useEffect(() => {
    setSelectedHistoryTaskId(taskId ?? null);
  }, [taskId]);

  const {
    selectedHistoryEntry,
    mobileShowDetail,
    setMobileShowDetail,
  } = useHistorySelection(filteredHistoryItems, selectedHistoryTaskId, setSelectedHistoryTaskId, !taskId);

  const dbExif = useMemo(() => {
    if (!selectedHistoryEntry?.config_json) return null;
    try {
      const config = JSON.parse(selectedHistoryEntry.config_json);
      return config.exif || null;
    } catch {
      return null;
    }
  }, [selectedHistoryEntry]);

  const sourceAssetId = useMemo(() => {
    if (!selectedHistoryEntry?.source_asset_ids) return null;
    try {
      const ids = JSON.parse(selectedHistoryEntry.source_asset_ids);
      return Array.isArray(ids) && ids.length > 0 ? ids[0] : null;
    } catch {
      return null;
    }
  }, [selectedHistoryEntry]);

  const fetchedExifQuery = useQuery({
    queryKey: ['immich-asset-exif', sourceAssetId],
    queryFn: () => getImmichAssetExif(sourceAssetId!),
    enabled: !dbExif && !!sourceAssetId,
  });

  const selectedExif = useMemo(() => {
    if (dbExif) return dbExif;
    if (fetchedExifQuery.data && Object.keys(fetchedExifQuery.data).length > 0) {
      return fetchedExifQuery.data;
    }
    return null;
  }, [dbExif, fetchedExifQuery.data]);

  // Mutations
  const acceptHistoryMutation = useMutation({
    mutationFn: async (variables: {
      taskId: string;
      create_album: boolean;
      album_name: string | null;
      album_id: string | null;
    }) =>
      acceptGeneration(variables.taskId, {
        create_album: variables.create_album,
        album_name: variables.album_name,
        album_id: variables.album_id,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['generation-history'] });
      setIsUploadModalOpen(false);
    },
  });

  const retryHistoryMutation = useMutation({
    mutationFn: retryGenerationAcceptance,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['generation-history'] });
    },
  });

  const rejectHistoryMutation = useMutation({
    mutationFn: rejectGeneration,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['generation-history'] });
    },
  });

  const { streamStatus } = useHistoryStreamSync({
    enabled: !!data,
    historyQueryKey,
    streamCursor,
    statusParam,
    debouncedSearch,
  });

  const selectedHistoryImmichUrl = useMemo(
    () => getImmichAssetDetailUrl(settings.data?.immich_url, selectedHistoryEntry?.uploaded_asset_id ?? undefined),
    [selectedHistoryEntry?.uploaded_asset_id, settings.data?.immich_url],
  );

  const sourceAssetImmichUrl = useMemo(
    () => getImmichAssetDetailUrl(settings.data?.immich_url, sourceAssetId),
    [sourceAssetId, settings.data?.immich_url],
  );

  const handleRefreshAll = async () => {
    await refetchHistory();
  };

  return (
    <section className="grid gap-4">
      {settings.isError && !settings.data && (
        <ErrorBanner
          title="History links unavailable"
          error={settings.error as Error | string | null}
          onRetry={() => settings.refetch()}
        />
      )}

      {/* Search, Filters and Refresh Bar */}
      <div className="app-panel grid gap-2 p-2 md:flex md:flex-wrap md:items-center md:gap-1.5 md:p-2">
        <div className="relative w-full min-w-0 md:flex-1">
          <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-stone-400">
            <Search size={13} />
          </span>
          <input
            type="text"
            value={historySearch}
            onChange={(event) => setHistorySearch(event.target.value)}
            placeholder="Search history..."
            className="app-control app-control-muted h-8 pl-8 pr-2.5 text-xs"
          />
        </div>
        <div className="w-full md:w-[150px] md:shrink-0">
          <select
            value={historyStatus}
            onChange={(event) => setHistoryStatus(event.target.value as HistoryStatusFilter)}
            className="app-control app-control-muted h-8 cursor-pointer px-2 text-xs"
          >
            <option value="all">All statuses</option>
            <option value="generated">Pending review</option>
            <option value="uploaded">Uploaded to Immich</option>
            <option value="failed">Failed uploads/generations</option>
            <option value="rejected">Rejected items</option>
          </select>
        </div>
        <div className="flex w-full gap-2 md:w-auto md:items-center md:gap-1.5">
          <button
            type="button"
            onClick={handleRefreshAll}
            title="Refresh history data"
            className="app-button-secondary h-8 w-full px-3 text-xs md:w-8 md:px-0"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
            <span className="md:hidden">Refresh</span>
          </button>
          <div
            className={`flex h-8 w-full items-center justify-center gap-1.5 rounded-full border px-2.5 text-[10px] md:w-auto ${
            streamStatus === 'connected'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : streamStatus === 'reconnecting'
              ? 'border-amber-200 bg-amber-50 text-amber-800'
              : 'border-stone-200 bg-stone-50 text-stone-500'
          }`}
          title="History stream connection"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                streamStatus === 'connected'
                  ? 'bg-emerald-500'
                  : streamStatus === 'reconnecting'
                  ? 'bg-amber-500'
                  : 'bg-stone-400'
              }`}
            />
            {streamStatus === 'connected' ? 'Live' : streamStatus === 'reconnecting' ? 'Reconnecting' : 'Disconnected'}
          </div>
        </div>
      </div>

      {isLoading && filteredHistoryItems.length === 0 ? (
        <div className="app-panel p-12">
          <InlineSpinner />
        </div>
      ) : isError ? (
        <div className="app-panel p-6">
          <ErrorBanner title="Failed to load history" error={error} onRetry={() => refetchHistory()} />
        </div>
      ) : filteredHistoryItems.length > 0 ? (
        <div className="grid gap-4 lg:h-168 lg:grid-cols-[330px_minmax(0,1fr)] lg:items-stretch">
          {/* Left Panel: Cards List */}
          <div
            className={`flex flex-col min-h-0 rounded-xl md:rounded-2xl border border-stone-200 bg-stone-50/60 p-1.5 md:p-2 ${
              mobileShowDetail ? 'hidden lg:flex lg:h-full' : 'flex h-152 lg:h-full'
            }`}
          >
            <div ref={historyListRef} className="flex-1 overflow-y-auto space-y-1 md:space-y-1.5 pr-1.5 custom-scrollbar">
              {filteredHistoryItems.map((item) => {
                const status = (item.status || '').toUpperCase();
                const isQueued = status === 'QUEUED';
                const isRunning = status === 'RUNNING';
                const isUploaded = status === 'UPLOADED' || Boolean(item.accepted_at);
                const isRejected = status === 'REJECTED';
                const isFailed = status === 'FAILED';
                const taskStep = item.task_step ? item.task_step.replace(/_/g, ' ') : '';

                return (
                  <button
                    key={item.task_id}
                    type="button"
                    onClick={() => {
                      setSelectedHistoryTaskId(item.task_id);
                      navigate(`/history/${item.task_id}`);
                      setMobileShowDetail(true);
                    }}
                    className={`group w-full flex gap-2.5 md:gap-3 rounded-xl border p-1.5 md:p-2 text-left transition-all duration-200 ${
                      selectedHistoryTaskId === item.task_id
                        ? 'border-emerald-500 bg-emerald-50/30 shadow-2xs'
                        : 'border-stone-200 bg-white hover:border-emerald-500/30 hover:bg-stone-50/30'
                    }`}
                  >
                    {item.image_url ? (
                      <div className="h-12 w-12 md:h-14 md:w-14 shrink-0 overflow-hidden rounded-lg bg-stone-100 border border-stone-100">
                        <SecureImage
                          src={`${item.image_url}?thumbnail=true`}
                          alt={item.title}
                          className="h-full w-full object-cover"
                        />
                      </div>
                    ) : (
                      <div className="h-12 w-12 md:h-14 md:w-14 shrink-0 overflow-hidden rounded-lg bg-stone-100 border border-stone-200 flex items-center justify-center">
                        <Layers size={16} className="text-stone-400" />
                      </div>
                    )}
                    <div className="min-w-0 flex-1 flex flex-col justify-between py-0.5">
                      <div>
                        <div className="truncate text-xs font-bold text-stone-900 group-hover:text-stone-950">
                          {item.title || 'Untitled Generation'}
                        </div>
                        <div className="truncate text-[10px] font-medium text-stone-500 mt-0.5">
                          {item.generation_type.replace(/_/g, ' ')}
                        </div>
                        {isRunning && taskStep && (
                          <div className="truncate text-[9px] font-medium text-blue-700 mt-0.5">
                            {taskStep}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center justify-between gap-1.5 text-[9px] mt-1.5">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ${
                            isUploaded
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                              : isRunning
                              ? 'bg-blue-50 text-blue-700 border border-blue-100'
                              : isQueued
                              ? 'bg-amber-50 text-amber-700 border border-amber-100'
                              : isRejected
                              ? 'bg-stone-100 text-stone-600 border border-stone-200'
                              : isFailed
                              ? 'bg-red-50/70 text-red-600 border border-red-100'
                              : 'bg-amber-50 text-amber-700 border border-amber-100'
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              isUploaded
                                ? 'bg-emerald-500'
                                : isRunning
                                ? 'bg-blue-500'
                                : isQueued
                                ? 'bg-amber-500'
                                : isRejected
                                ? 'bg-stone-400'
                                : isFailed
                                ? 'bg-red-500'
                                : 'bg-amber-500'
                            }`}
                          />
                          {isUploaded
                            ? 'Uploaded'
                            : isRunning
                            ? 'Running'
                            : isQueued
                            ? 'Queued'
                            : isRejected
                            ? 'Rejected'
                            : isFailed
                            ? 'Failed'
                            : 'Pending'}
                        </span>
                        <span className="text-stone-400 font-medium">
                          {item.created_at ? formatDateTime(item.created_at) : ''}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}

              {/* Load More Button */}
              {hasNextPage && (
                <div className="pt-2 pb-4 text-center">
                  <button
                    type="button"
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-stone-250 bg-white px-4 text-xs font-semibold text-stone-700 hover:bg-stone-50 active:scale-95 disabled:opacity-50 transition"
                  >
                    {isFetchingNextPage ? (
                      <>
                        <RefreshCw size={12} className="animate-spin text-stone-500" />
                        Loading...
                      </>
                    ) : (
                      'Load more entries'
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel: Detail Panel */}
          <HistoryDetailPanel
            entry={selectedHistoryEntry}
            selectedHistoryImmichUrl={selectedHistoryImmichUrl}
            sourceAssetImmichUrl={sourceAssetImmichUrl}
            mobileShowDetail={mobileShowDetail}
            onBackToList={() => {
              setMobileShowDetail(false);
              navigate('/history');
            }}
            onAccept={() => {
              if (selectedHistoryEntry) {
                acceptHistoryMutation.mutate({
                  taskId: selectedHistoryEntry.task_id,
                  create_album: false,
                  album_name: selectedHistoryEntry.album_name || null,
                  album_id: null,
                });
              }
            }}
            onAcceptWithOptions={() => setIsUploadModalOpen(true)}
            onReject={() => {
              if (selectedHistoryEntry) {
                rejectHistoryMutation.mutate(selectedHistoryEntry.task_id);
              }
            }}
            onRetry={() => {
              if (selectedHistoryEntry) {
                retryHistoryMutation.mutate(selectedHistoryEntry.task_id);
              }
            }}
            onOpenLightbox={(imageUrl) => {
              if (imageUrl) {
                setLightboxUrl(imageUrl);
              }
            }}
            acceptPending={acceptHistoryMutation.isPending}
            rejectPending={rejectHistoryMutation.isPending}
            retryPending={retryHistoryMutation.isPending}
          />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-24 rounded-2xl border border-stone-200 bg-white p-6 text-center">
          <Layers size={32} className="text-stone-300 mb-3" />
          <h4 className="text-sm font-bold text-stone-900">No items found</h4>
          <p className="text-xs text-stone-500 mt-1 max-w-xs">
            {historySearch.trim()
              ? 'No history matches the current search query or filter status.'
              : 'There are no generations stored in the history database yet.'}
          </p>
        </div>
      )}

      {/* destination album upload modal */}
      {selectedHistoryEntry && (
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        entry={selectedHistoryEntry}
        albums={sortedAlbums}
        isPending={acceptHistoryMutation.isPending}
        onConfirm={(variables) => {
          if (!selectedHistoryEntry) return;
          acceptHistoryMutation.mutate({
            taskId: selectedHistoryEntry.task_id,
            ...variables,
          });
        }}
      />
      )}

      {/* Advanced Lightbox with EXIF Info Overlay */}
      {lightboxUrl && selectedHistoryEntry && (
        <LightboxModal
          isOpen={!!lightboxUrl}
          onClose={() => setLightboxUrl(null)}
          imageUrl={lightboxUrl}
          entry={selectedHistoryEntry}
          exif={selectedExif}
        />
      )}
    </section>
  );
}

export default HistoryPage;
