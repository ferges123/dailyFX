import { memo } from 'react';
import { Layers, Loader2 } from 'lucide-react';

export interface VisionState {
  attempted?: boolean;
  succeeded?: boolean;
}

export interface TaskTraceItem {
  stage?: string;
  message?: string;
  progress?: number | null;
  timestamp?: string;
  status?: string;
  step?: string;
  details?: {
    elapsed_seconds?: number;
  };
}

export interface MetadataProvenance {
  title_source?: string;
  summary_source?: string;
  tags_source?: string;
  people_context?: {
    attempted?: boolean;
    used?: boolean;
    names?: string[];
    faces?: unknown[];
    prompt_hint?: string;
  };
  source_vision?: VisionState | null;
  photo_selection?: {
    attempted?: boolean;
    succeeded?: boolean;
    provider?: string | null;
    model?: string | null;
    candidate_asset_ids?: string[];
    selected_asset_id?: string | null;
    error?: string | null;
    fallback_reason?: string | null;
  };
  final_vision?: VisionState | null;
  exif_info?: {
    attempted?: boolean;
    embedded?: boolean;
    skip_reason?: string | null;
  };
  tag_injections?: string[];
  prompt_enrichment_context?: {
    album_name?: string | null;
    people_names?: string[];
    exif_summary?: string | null;
    context_hint?: string | null;
  } | null;
}

interface AdditionalInfoDetailsProps {
  metadataProvenance: MetadataProvenance | null;
  taskTrace: TaskTraceItem[] | null;
}


const formatVisionState = (vision: VisionState | null | undefined) => {
  if (!vision) return 'unknown';
  if (!vision.attempted) return 'not used';
  return vision.succeeded ? 'succeeded' : 'failed';
};

const formatElapsed = (
  previousTimestamp: string | undefined,
  currentTimestamp: string | undefined,
) => {
  if (!previousTimestamp || !currentTimestamp) return '';
  const previous = Date.parse(previousTimestamp);
  const current = Date.parse(currentTimestamp);
  if (Number.isNaN(previous) || Number.isNaN(current) || current <= previous)
    return '';
  const totalSeconds = Math.round((current - previous) / 1000);
  if (totalSeconds < 60) return `+${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `+${minutes}m ${String(seconds).padStart(2, '0')}s`;
};

const formatDuration = (seconds: number | null | undefined) => {
  if (seconds == null) return null;
  const totalSeconds = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  if (minutes && secs) return `${minutes} min ${secs} sec`;
  if (minutes) return `${minutes} min`;
  return `${secs} sec`;
};

export const AdditionalInfoDetails = memo(function AdditionalInfoDetails({
  metadataProvenance,
  taskTrace,
}: AdditionalInfoDetailsProps) {
  return (
    <details className="rounded-lg border border-stone-200/70 bg-stone-50/60 px-2 py-1.5 text-[9px] text-stone-700">
      <summary className="cursor-pointer list-none flex items-center justify-between gap-2 text-[7.5px] font-bold uppercase tracking-[0.12em] text-stone-400">
        <span className="inline-flex items-center gap-1.5">
          <Layers size={11} />
          Additional info
        </span>
        <span className="text-[7.5px] font-semibold text-stone-400 normal-case tracking-normal">
          Metadata provenance and timeline
        </span>
      </summary>
      <div className="mt-2 space-y-2">
        {metadataProvenance && (
          <div className="rounded-lg border border-sky-200/60 bg-sky-50/50 p-2 text-[9px] text-sky-950">
            <div className="flex items-center gap-1.5 text-[7.5px] font-bold uppercase tracking-[0.12em] text-sky-600 mb-1">
              <Layers size={11} />
              Metadata provenance
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[7.5px] font-semibold text-sky-700">
                  Title:
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white px-2 py-0.5 font-medium text-sky-900">
                  {(metadataProvenance.title_source || 'unknown').replace(
                    /_/g,
                    ' ',
                  )}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[7.5px] font-semibold text-sky-700">
                  Summary:
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white px-2 py-0.5 font-medium text-sky-900">
                  {(
                    metadataProvenance.summary_source || 'unknown'
                  ).replace(/_/g, ' ')}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[7.5px] font-semibold text-sky-700">
                  Tags:
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white px-2 py-0.5 font-medium text-sky-900">
                  {(metadataProvenance.tags_source || 'unknown').replace(
                    /_/g,
                    ' ',
                  )}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[7.5px] font-semibold text-sky-700">
                  Source Vision:
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white px-2 py-0.5 font-medium text-sky-900">
                  {formatVisionState(metadataProvenance.source_vision)}
                </span>
                <span className="text-[7.5px] font-semibold text-sky-700 ml-2">
                  Final Vision:
                </span>
                <span className="rounded-full border border-sky-200/60 bg-white px-2 py-0.5 font-medium text-sky-900">
                  {formatVisionState(metadataProvenance.final_vision)}
                </span>
              </div>
              {Array.isArray(metadataProvenance.tag_injections) &&
                metadataProvenance.tag_injections.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[7.5px] font-semibold text-sky-700">
                      Injected tags:
                    </span>
                    {metadataProvenance.tag_injections.map(
                      (tag: string) => (
                        <span
                          key={tag}
                          className="rounded-full border border-sky-200/60 bg-sky-100/70 px-2 py-0.5 font-medium text-sky-900"
                        >
                          #{tag}
                        </span>
                      ),
                    )}
                  </div>
                )}
              {metadataProvenance.prompt_enrichment_context && (
                <div className="rounded-lg border border-emerald-200/70 bg-emerald-50/60 p-2 text-[9px] text-emerald-950">
                  <div className="flex items-center gap-1.5 text-[7.5px] font-bold uppercase tracking-[0.12em] text-emerald-700 mb-1">
                    <Layers size={11} />
                    Prompt enrichment
                  </div>
                  <div className="space-y-1">
                    {metadataProvenance.prompt_enrichment_context
                      .album_name && (
                      <div>
                        <span className="font-semibold text-emerald-800">
                          Album:
                        </span>{' '}
                        {
                          metadataProvenance.prompt_enrichment_context
                            .album_name
                        }
                      </div>
                    )}
                    {Array.isArray(
                      metadataProvenance.prompt_enrichment_context
                        .people_names,
                    ) &&
                      metadataProvenance.prompt_enrichment_context
                        .people_names.length > 0 && (
                        <div>
                          <span className="font-semibold text-emerald-800">
                            People:
                          </span>{' '}
                          {metadataProvenance.prompt_enrichment_context.people_names.join(
                            ', ',
                          )}
                        </div>
                      )}
                    {metadataProvenance.prompt_enrichment_context
                      .exif_summary && (
                      <div>
                        <span className="font-semibold text-emerald-800">
                          EXIF:
                        </span>{' '}
                        {
                          metadataProvenance.prompt_enrichment_context
                            .exif_summary
                        }
                      </div>
                    )}
                    {metadataProvenance.prompt_enrichment_context
                      .context_hint && (
                      <div className="rounded-md border border-emerald-200/70 bg-white/70 p-2 text-[8.5px] leading-relaxed text-emerald-950 whitespace-pre-line">
                        {
                          metadataProvenance.prompt_enrichment_context
                            .context_hint
                        }
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {taskTrace && taskTrace.length > 0 && (
          <div className="rounded-lg border border-stone-200/70 bg-white/80 p-2 text-[9px] text-stone-800">
            <div className="flex items-center gap-1.5 text-[7.5px] font-bold uppercase tracking-[0.12em] text-stone-500 mb-1.5">
              <Layers size={11} />
              Task timeline
            </div>
            <div className="space-y-1.5">
              {taskTrace.map((item: TaskTraceItem, index: number) => (
                <div
                  key={`${item.stage || 'stage'}-${index}`}
                  className={`rounded-md border p-2 ${
                    index === taskTrace.length - 1 &&
                    String(item.status || '').toLowerCase() === 'running'
                      ? 'border-blue-200/80 bg-blue-50/70'
                      : 'border-stone-100/70 bg-stone-50/60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[7.5px] font-bold uppercase tracking-[0.12em] text-stone-400">
                        {index === taskTrace.length - 1 &&
                        String(item.status || '').toLowerCase() === 'running' ? (
                          <span className="inline-flex items-center gap-1">
                            <Loader2 size={10} className="animate-spin" />
                            {(item.stage || 'step').replace(/_/g, ' ')}
                          </span>
                        ) : (
                          (item.stage || 'step').replace(/_/g, ' ')
                        )}
                      </div>
                      <div className="text-[8.5px] font-medium text-stone-800 leading-snug">
                        {item.message || '—'}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      {item.progress !== null &&
                        item.progress !== undefined && (
                          <div className="text-[7.5px] font-semibold text-stone-500">
                            {Math.round(Number(item.progress) * 100)}%
                          </div>
                        )}
                      {item.details?.elapsed_seconds !== undefined && (
                        <div className="text-[7px] font-medium text-stone-400">
                          {formatDuration(item.details.elapsed_seconds)}
                        </div>
                      )}
                      {formatElapsed(
                        taskTrace[index - 1]?.timestamp,
                        item.timestamp,
                      ) && (
                        <div className="text-[7px] font-medium text-stone-400">
                          {formatElapsed(
                            taskTrace[index - 1]?.timestamp,
                            item.timestamp,
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  {(item.status || item.step) && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {item.status && (
                        <span className="rounded-full bg-white/90 px-1.5 py-0.5 text-[7.5px] font-semibold text-stone-500 border border-stone-200/70">
                          {String(item.status).toLowerCase()}
                        </span>
                      )}
                      {item.step && (
                        <span className="rounded-full bg-white/90 px-1.5 py-0.5 text-[7.5px] font-semibold text-stone-500 border border-stone-200/70">
                          {String(item.step).replace(/_/g, ' ')}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </details>
  );
});
