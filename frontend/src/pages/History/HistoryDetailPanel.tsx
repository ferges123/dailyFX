import { useState, useEffect, memo, useMemo } from 'react';
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  AlertTriangle,
  Check,
  FolderPlus,
  XCircle,
  CloudUpload,
  Layers,
  HelpCircle,
  ZoomIn,
  Download,
  Loader2,
} from 'lucide-react';
import { type GenerationHistoryEntry } from '../../api/client';
import { SecureImage } from '../../components/SecureImage';
import { formatDateTime } from '../datetime.utils';
import {
  AdditionalInfoDetails,
  type TaskTraceItem,
} from './AdditionalInfoDetails';
import { parseFirstSourceAssetId } from '../../utils/generationMetadata';
import { appendQueryParam } from '../../utils/url';

interface HistoryDetailPanelProps {
  entry: GenerationHistoryEntry | null;
  selectedHistoryImmichUrl: string | null;
  sourceAssetImmichUrl: string | null;
  mobileShowDetail: boolean;
  onBackToList: () => void;
  onAccept: () => void;
  onAcceptWithOptions: () => void;
  onReject: () => void;
  onRetry: () => void;
  onOpenLightbox: (imageUrl: string) => void;
  acceptPending: boolean;
  rejectPending: boolean;
  retryPending: boolean;
}

export const HistoryDetailPanel = memo(function HistoryDetailPanel({
  entry,
  selectedHistoryImmichUrl,
  sourceAssetImmichUrl,
  mobileShowDetail,
  onBackToList,
  onAccept,
  onAcceptWithOptions,
  onReject,
  onRetry,
  onOpenLightbox,
  acceptPending,
  rejectPending,
  retryPending,
}: HistoryDetailPanelProps) {
  const [showOriginal, setShowOriginal] = useState(false);

  useEffect(() => {
    setShowOriginal(false);
  }, [entry]);

  const sourceAssetId = useMemo(
    () => parseFirstSourceAssetId(entry?.source_asset_ids),
    [entry?.source_asset_ids],
  );

  const metadataProvenance = useMemo(() => {
    if (!entry?.config_json) return null;
    try {
      const config = JSON.parse(entry.config_json);
      return config.metadata_provenance ?? null;
    } catch {
      return null;
    }
  }, [entry?.config_json]);

  const taskTrace = useMemo(() => {
    if (!entry?.config_json) return null;
    try {
      const config = JSON.parse(entry.config_json);
      return Array.isArray(config.task_trace)
        ? (config.task_trace as TaskTraceItem[])
        : null;
    } catch {
      return null;
    }
  }, [entry?.config_json]);

  const latestTaskTrace = useMemo(() => {
    if (!taskTrace || taskTrace.length === 0) return null;
    return taskTrace[taskTrace.length - 1];
  }, [taskTrace]);

  const latestTaskTraceStatus = (latestTaskTrace?.status || '')
    .toString()
    .toLowerCase();
  const isTraceRunning =
    latestTaskTraceStatus === 'running' ||
    latestTaskTraceStatus === 'in_progress' ||
    latestTaskTraceStatus === 'queued';

  const tags = useMemo(() => {
    if (!entry?.tags_json) return [];
    try {
      const parsed = JSON.parse(entry.tags_json);
      return Array.isArray(parsed) ? (parsed as string[]) : [];
    } catch {
      return [];
    }
  }, [entry?.tags_json]);

  if (!entry) {
    return (
      <div
        className={`app-panel-soft flex-1 flex flex-col items-center justify-center border-2 border-dashed border-stone-200 text-stone-400 p-8 ${
          mobileShowDetail ? 'flex min-h-80' : 'hidden lg:flex'
        }`}
      >
        <HelpCircle size={32} className="mb-2.5 text-stone-300 animate-pulse" />
        <span className="text-sm font-semibold">Select a history entry</span>
        <p className="text-xs text-stone-400 mt-1 max-w-xs text-center">
          Pick any generated item from the list to view its AI prompts, tags,
          metadata, and upload control options.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`app-panel flex flex-col min-h-0 overflow-y-auto p-3 md:p-4 lg:h-full ${
        mobileShowDetail ? 'flex' : 'hidden lg:flex'
      }`}
    >
      {/* Mobile Back Button */}
      <button
        type="button"
        onClick={onBackToList}
        className="lg:hidden inline-flex items-center gap-1.5 self-start border-b border-stone-200/50 pb-2 md:pb-3 text-xs font-semibold text-stone-600 hover:text-stone-900"
      >
        <ArrowLeft size={14} />
        Back to list
      </button>

      <div className="flex-1 space-y-1.5 md:space-y-2.5">
        {/* Header Information */}
        <div className="space-y-1">
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-extrabold text-stone-900 text-xs leading-tight min-w-0 flex-1">
              {entry.title || 'Untitled Generation'}
            </h3>
            <span className="app-chip shrink-0 px-2 py-0.5 text-[8px] uppercase tracking-wide">
              {entry.generation_type.replace(/_/g, ' ')}
            </span>
          </div>
          {entry.summary && (
            <p className="rounded-xl border border-stone-100 bg-stone-50/60 p-2 text-[10px] leading-normal italic text-stone-600">
              "{entry.summary}"
            </p>
          )}
          {/* AI Tags List */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-0.5">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-emerald-100/60 bg-emerald-50 px-1.5 py-0.5 text-[8.5px] font-medium text-emerald-700"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
          {/* Original image link */}
          {sourceAssetImmichUrl && (
            <div className="flex items-center gap-1.5 text-[9.5px] text-stone-500 font-medium pt-0.5">
              <span>Source photo:</span>
              <a
                href={sourceAssetImmichUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-emerald-200/60 bg-emerald-50 px-2 py-0.5 text-[9.5px] font-semibold text-emerald-800 transition hover:bg-emerald-100"
              >
                <ExternalLink size={10} />
                View original in Immich
              </a>
              {sourceAssetId && (
                <button
                  type="button"
                  onClick={() => setShowOriginal(!showOriginal)}
                  className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[9.5px] font-semibold transition cursor-pointer ${
                    showOriginal
                      ? 'border-emerald-600 bg-emerald-800 text-white hover:bg-emerald-900'
                      : 'border-emerald-250 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                  }`}
                >
                  {showOriginal ? 'Show Effect' : 'Show Original'}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-3 gap-1.5 rounded-xl border border-stone-100/80 bg-white/70 p-1.5 text-[9.5px]">
          <div>
            <span className="text-[7.5px] font-bold uppercase tracking-wider text-stone-400 block mb-0.5">
              System Status
            </span>
            <span
              className={`font-semibold capitalize ${
                entry.status === 'UPLOADED'
                  ? 'text-emerald-700'
                  : entry.status === 'RUNNING'
                    ? 'text-blue-700'
                    : entry.status === 'FAILED'
                      ? 'text-red-600'
                      : 'text-amber-700'
              }`}
            >
              {entry.status.toLowerCase().replace(/_/g, ' ')}
            </span>
            {entry.status === 'RUNNING' && entry.task_step && (
              <span className="mt-1 block text-[9px] font-medium text-blue-600">
                Current step: {entry.task_step.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <div>
            <span className="text-[7.5px] font-bold uppercase tracking-wider text-stone-400 block mb-0.5">
              Image provider
            </span>
            <span className="font-semibold text-stone-700 truncate block">
              {entry.provider
                ? entry.provider.replace(/_/g, ' ')
                : entry.status === 'RUNNING'
                  ? '-'
                  : entry.status === 'QUEUED'
                    ? 'Queued'
                    : 'Local Engine'}
            </span>
          </div>
          <div>
            <span className="text-[7.5px] font-bold uppercase tracking-wider text-stone-400 block mb-0.5">
              Created At
            </span>
            <span className="font-semibold text-stone-700 block truncate">
              {entry.created_at ? formatDateTime(entry.created_at) : '—'}
            </span>
          </div>
        </div>

        {latestTaskTrace && (
          <div
            className={`rounded-xl border px-3 py-2 text-[10px] font-medium ${
              isTraceRunning
                ? 'border-blue-200 bg-blue-50/70 text-blue-800'
                : latestTaskTraceStatus === 'failed'
                  ? 'border-red-200 bg-red-50/70 text-red-800'
                  : 'border-emerald-200 bg-emerald-50/70 text-emerald-800'
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5 inline-flex shrink-0 items-center justify-center">
                {isTraceRunning ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : latestTaskTraceStatus === 'failed' ? (
                  <XCircle size={12} />
                ) : (
                  <Check size={12} />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-semibold">
                    {isTraceRunning
                      ? 'Task is still running'
                      : latestTaskTraceStatus === 'failed'
                        ? 'Task trace failed'
                        : 'Task trace completed'}
                  </span>
                  <span className="rounded-full border border-current/15 bg-white/70 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide">
                    {(latestTaskTrace.stage || 'step').replace(/_/g, ' ')}
                  </span>
                  {latestTaskTrace.progress !== null &&
                    latestTaskTrace.progress !== undefined && (
                      <span className="text-[9px] font-semibold opacity-80">
                        {Math.round(Number(latestTaskTrace.progress) * 100)}%
                      </span>
                    )}
                </div>
                <div className="mt-0.5 text-[9px] leading-snug">
                  {latestTaskTrace.message || 'No status message available.'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Image Section */}
        {entry.status === 'RUNNING' && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/70 px-3 py-2 text-[10px] font-medium text-blue-800">
            Generation is still running.
            {entry.task_step
              ? ` Current step: ${entry.task_step.replace(/_/g, ' ')}`
              : ''}
          </div>
        )}
        {entry.status === 'QUEUED' && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-[10px] font-medium text-amber-800">
            This task is queued and waiting for the worker to start it.
          </div>
        )}
        {entry.image_url ? (
          <div className="relative group max-w-full overflow-hidden rounded-xl md:rounded-2xl border border-stone-200 bg-stone-100 shadow-[0_12px_26px_rgba(36,29,16,0.06)]">
            {/* Base: Generated image */}
            <SecureImage
              src={appendQueryParam(entry.image_url, 'thumbnail', 'true')}
              alt={entry.title}
              className="w-full max-h-[220px] md:max-h-[320px] cursor-zoom-in object-contain mx-auto transition-transform duration-500 ease-out group-hover:scale-[1.015]"
              onClick={() => onOpenLightbox(entry.image_url ?? '')}
            />
            {/* Overlay: Original image */}
            {sourceAssetId && (
              <div
                className={`absolute inset-0 bg-stone-100 transition-opacity duration-200 pointer-events-none ${
                  showOriginal ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <SecureImage
                  src={`/api/immich/assets/${sourceAssetId}/thumbnail?size=preview`}
                  alt="Original"
                  className="w-full h-full object-contain mx-auto"
                />
              </div>
            )}
            {/* Centered Zoom Icon Overlay */}
            <div className="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center pointer-events-none">
              <div className="bg-white/20 backdrop-blur-md border border-white/30 text-white p-2 rounded-full shadow-lg">
                <ZoomIn size={14} />
              </div>
            </div>
            {/* Floating Download Button */}
            <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
              <a
                href={entry.image_url}
                download
                className="pointer-events-auto flex items-center justify-center rounded-xl border border-white/10 bg-stone-900/80 p-1.5 text-white shadow-md transition hover:bg-stone-950 active:scale-95"
                title="Download image"
                onClick={(e) => e.stopPropagation()}
              >
                <Download size={13} />
              </a>
            </div>
          </div>
        ) : (
          <div className="flex h-24 flex-col items-center justify-center rounded-xl border border-dashed border-stone-200 bg-stone-50 text-stone-400">
            <Layers size={20} className="mb-1.5" />
            <span className="text-[11px]">No preview image available</span>
          </div>
        )}

        {/* Detail Page Action Buttons */}
        <div className="space-y-2">
          {/* PENDING REVIEW ACTIONS */}
          {entry.status === 'PENDING_REVIEW' && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onAccept}
                disabled={acceptPending}
                title={
                  entry.album_name
                    ? `Accept and upload to "${entry.album_name}"`
                    : 'Accept and upload'
                }
                className="flex-1 inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-emerald-800 px-3 text-xs font-bold text-white hover:bg-emerald-950 disabled:bg-stone-200 transition active:scale-98 shadow-xs cursor-pointer"
              >
                <Check size={14} />
                Accept
              </button>
              <button
                type="button"
                onClick={onAcceptWithOptions}
                disabled={acceptPending}
                title="Accept with custom album options"
                className="flex-1 inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-stone-250 bg-stone-50 px-3 text-xs font-semibold text-stone-700 hover:bg-stone-100 transition active:scale-98 cursor-pointer"
              >
                <FolderPlus size={14} />
                Accept...
              </button>
              <button
                type="button"
                onClick={onReject}
                disabled={rejectPending}
                className="flex-1 inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 text-xs font-semibold text-red-600 hover:bg-red-50 hover:border-red-300 transition active:scale-98 cursor-pointer"
              >
                <XCircle size={14} />
                Reject
              </button>
            </div>
          )}

          {/* FAILED / RETRY ACTIONS */}
          {entry.status === 'FAILED' && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={onRetry}
                disabled={retryPending}
                className="w-full inline-flex h-8 items-center justify-center gap-2 rounded-lg bg-amber-700 px-4 text-xs font-semibold text-white hover:bg-amber-850 disabled:bg-stone-200 transition active:scale-98 cursor-pointer"
              >
                <RefreshCw
                  size={14}
                  className={retryPending ? 'animate-spin' : ''}
                />
                {retryPending
                  ? 'Retrying Upload...'
                  : '🔄 Retry Upload to Immich'}
              </button>
              <p className="text-[10px] text-red-600 font-medium bg-red-50/70 border border-red-100 p-2 rounded-lg leading-relaxed flex items-start gap-1">
                <AlertTriangle size={12} className="shrink-0 mt-0.5" />
                <span>
                  <strong>Error Details:</strong>{' '}
                  {entry.accept_notes || 'Unknown execution failure.'}
                </span>
              </p>
            </div>
          )}

          {/* REJECTED ACTIONS */}
          {entry.status === 'REJECTED' && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={onAcceptWithOptions}
                disabled={acceptPending}
                className="w-full inline-flex h-8 items-center justify-center gap-2 rounded-lg border border-emerald-600 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 px-4 text-xs font-semibold transition active:scale-98 cursor-pointer"
              >
                <CloudUpload size={14} />
                Reconsider & Upload to Immich
              </button>
              <div className="text-[10px] text-stone-500 bg-stone-50 border border-stone-100 p-2 rounded-lg text-center">
                This item was marked as rejected but remains stored in your
                database.
              </div>
            </div>
          )}

          <AdditionalInfoDetails
            metadataProvenance={metadataProvenance}
            taskTrace={taskTrace}
          />

          {/* UPLOADED ACTIONS */}
          {entry.status === 'UPLOADED' && (
            <div className="space-y-2">
              <div className="flex gap-2">
                {selectedHistoryImmichUrl && (
                  <a
                    href={selectedHistoryImmichUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-8 flex-1 items-center justify-center gap-2 rounded-lg bg-stone-100 px-4 text-xs font-semibold text-stone-800 hover:bg-stone-200 border border-stone-200 transition"
                  >
                    <ExternalLink size={13} />
                    View in Immich Library
                  </a>
                )}
                {entry.accept_notes && (
                  <button
                    type="button"
                    onClick={onRetry}
                    disabled={retryPending}
                    className="inline-flex h-8 items-center justify-center rounded-lg border border-stone-300 bg-white px-4 text-xs font-medium text-stone-700 hover:bg-stone-50 hover:border-stone-400 transition cursor-pointer"
                    title="Retry album allocation or tags application"
                  >
                    <RefreshCw
                      size={13}
                      className={retryPending ? 'animate-spin' : ''}
                    />
                    Retry Tags/Album
                  </button>
                )}
              </div>

              {entry.album_name && (
                <div className="flex items-center gap-1.5 text-xs text-stone-500 font-medium">
                  <span>Target Album:</span>
                  <span className="rounded-sm bg-emerald-50 border border-emerald-150 px-2 py-0.5 text-emerald-850 font-semibold">
                    {entry.album_name}
                  </span>
                </div>
              )}

              {/* Display Warnings / Details of Album/Tagging failure if present */}
              {entry.accept_notes && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-[11px] text-amber-900 leading-relaxed">
                  <div className="font-semibold flex items-center gap-1.5 mb-1 text-amber-955">
                    <AlertTriangle size={13} className="text-amber-600" />
                    Upload Warnings
                  </div>
                  {entry.accept_notes.split('\n').map((line, idx) => (
                    <div key={idx}>• {line}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});
