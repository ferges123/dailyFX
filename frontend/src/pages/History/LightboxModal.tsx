import { useEffect, useState, useRef, memo, useMemo } from 'react';
import {
  X,
  Cpu,
  Layers,
  Info,
  HardDrive,
  Calendar,
  MapPin,
  ExternalLink,
  Download,
  Share2,
  Check,
  ThumbsUp,
  ThumbsDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  type GenerationHistoryEntry,
  likeGeneration,
  dislikeGeneration,
} from '../../api/client';

import { SecureImage } from '../../components/SecureImage';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { formatDateTime } from '../datetime.utils';
import { logger } from '../../utils/logger';
import { parseFirstSourceAssetId } from '../../utils/generationMetadata';

// Format shutter speed decimal into a readable fraction
function formatShutterSpeed(
  seconds: number | string | undefined | null,
): string {
  if (seconds === undefined || seconds === null) return '';
  const s = Number(seconds);
  if (isNaN(s)) return String(seconds);
  if (s >= 0.5) return `${s.toFixed(1)}s`;
  const fraction = Math.round(1 / s);
  return `1/${fraction}s`;
}

function formatFileSize(bytes: number | undefined | null): string {
  if (bytes === undefined || bytes === null || isNaN(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  const kib = bytes / 1024;
  if (kib < 1024) return `${kib.toFixed(1)} KB`;
  const mib = kib / 1024;
  return `${mib.toFixed(1)} MB`;
}

function makeSafeFileName(title: string | null | undefined, ext = 'png') {
  const base = (title || 'dailyfx-image')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return `${base || 'dailyfx-image'}.${ext}`;
}

const SWIPE_MIN_DISTANCE = 56;
const SWIPE_HORIZONTAL_RATIO = 1.2;

interface ExifData {
  make?: string | null;
  model?: string | null;
  lensModel?: string | null;
  exposureTime?: number | string | null;
  fNumber?: number | null;
  iso?: number | null;
  focalLength?: number | null;
  fileSizeInByte?: number | null;
  exifImageWidth?: number | null;
  exifImageHeight?: number | null;
  dateTimeOriginal?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
}

interface LightboxModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string;
  entry: GenerationHistoryEntry;
  exif: ExifData | null;
  onPrev?: () => void;
  onNext?: () => void;
  hasPrev?: boolean;
  hasNext?: boolean;
}

export const LightboxModal = memo(function LightboxModal({
  isOpen,
  onClose,
  imageUrl,
  entry,
  exif,
  onPrev,
  onNext,
  hasPrev = false,
  hasNext = false,
}: LightboxModalProps) {
  const tags = useMemo(() => {
    if (!entry?.tags_json) return [];
    try {
      const parsed = JSON.parse(entry.tags_json);
      return Array.isArray(parsed) ? (parsed as string[]) : [];
    } catch {
      return [];
    }
  }, [entry?.tags_json]);

  const [isSharing, setIsSharing] = useState(false);
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied' | 'error'>(
    'idle',
  );
  const [showOriginal, setShowOriginal] = useState(false);
  const swipeStartRef = useRef<{
    x: number;
    y: number;
    pointerId: number;
  } | null>(null);
  const trapRef = useFocusTrap(isOpen);
  const qc = useQueryClient();
  const [liked, setLiked] = useState<boolean | null>(entry.liked ?? null);

  useEffect(() => {
    setLiked(entry.liked ?? null);
  }, [entry.liked]);

  const handleLike = async () => {
    try {
      const updated = await likeGeneration(entry.task_id);
      setLiked(updated.liked ?? null);
      void qc.invalidateQueries({ queryKey: ['generation-history'] });
      void qc.invalidateQueries({ queryKey: ['effect-stats'] });
    } catch (err) {
      console.error(err);
    }
  };

  const handleDislike = async () => {
    try {
      const updated = await dislikeGeneration(entry.task_id);
      setLiked(updated.liked ?? null);
      void qc.invalidateQueries({ queryKey: ['generation-history'] });
      void qc.invalidateQueries({ queryKey: ['effect-stats'] });
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    setShowOriginal(false);
  }, [imageUrl, isOpen]);

  function handleSwipeStart(event: React.PointerEvent<HTMLDivElement>) {
    if (!isOpen || event.pointerType !== 'touch' || !event.isPrimary) return;
    swipeStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function handleSwipeEnd(event: React.PointerEvent<HTMLDivElement>) {
    const start = swipeStartRef.current;
    swipeStartRef.current = null;
    if (!start || start.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture?.(event.pointerId);

    const deltaX = event.clientX - start.x;
    const deltaY = event.clientY - start.y;
    const horizontalDistance = Math.abs(deltaX);
    if (
      horizontalDistance < SWIPE_MIN_DISTANCE ||
      horizontalDistance <= Math.abs(deltaY) * SWIPE_HORIZONTAL_RATIO
    ) {
      return;
    }

    if (deltaX < 0 && onNext && hasNext) onNext();
    if (deltaX > 0 && onPrev && hasPrev) onPrev();
  }

  function handleSwipeCancel() {
    swipeStartRef.current = null;
  }

  const sourceAssetId = parseFirstSourceAssetId(entry?.source_asset_ids);
  const originalImageUrl = sourceAssetId
    ? `/api/immich/assets/${sourceAssetId}/thumbnail?size=preview`
    : null;

  // Handle Escape key and arrow keys for navigation
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      } else if (event.key === 'ArrowLeft' && onPrev && hasPrev) {
        onPrev();
      } else if (event.key === 'ArrowRight' && onNext && hasNext) {
        onNext();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onPrev, onNext, hasPrev, hasNext]);

  async function handleShare() {
    if (isSharing) return;

    const shareUrl = `${window.location.origin}/api/generation/history/${entry.task_id}/image`;

    if (typeof navigator.share === 'function') {
      setIsSharing(true);
      try {
        const response = await fetch(
          `/api/generation/history/${entry.task_id}/image`,
        );
        if (!response.ok) throw new Error('Failed to fetch image');

        const ext = entry.output_format || 'png';
        const blob = await response.blob();
        const file = new File([blob], makeSafeFileName(entry.title, ext), {
          type: blob.type || `image/${ext}`,
        });

        if (
          typeof navigator.canShare === 'function' &&
          !navigator.canShare({ files: [file] })
        ) {
          throw new Error('File sharing not supported by browser');
        }

        await navigator.share({
          files: [file],
          title: entry.title || 'DailyFX image',
        });
      } catch (error) {
        logger.warn('Native file share failed, trying URL fallback:', error);
        try {
          await navigator.share({
            title: entry.title || 'DailyFX image',
            url: shareUrl,
          });
        } catch (urlError) {
          logger.error('URL sharing failed:', urlError);
          await fallbackCopyLink(shareUrl);
        }
      } finally {
        setIsSharing(false);
      }
    } else {
      await fallbackCopyLink(shareUrl);
    }
  }

  async function fallbackCopyLink(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setShareStatus('copied');
      setTimeout(() => setShareStatus('idle'), 2000);
    } catch (err) {
      logger.error('Failed to copy link:', err);
      setShareStatus('error');
      setTimeout(() => setShareStatus('idle'), 2000);
    }
  }

  if (!isOpen) return null;

  return (
    <div
      ref={trapRef}
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-stone-100/90 p-0 md:items-center md:p-4 backdrop-blur-xl animate-fade-in"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lightbox-modal-title"
        className="relative flex w-full h-full md:h-[92vh] md:max-h-[92vh] max-w-full md:max-w-[94vw] flex-col items-stretch justify-center overflow-hidden rounded-none md:rounded-2xl border-0 md:border border-stone-200/80 bg-white/95 shadow-2xl animate-scale-in md:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Photo Canvas */}
        <div className="relative flex h-[52vh] min-h-0 md:h-full md:min-w-0 md:max-h-none flex-1 items-center justify-center bg-stone-50 p-2">
          {hasPrev && onPrev && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onPrev(); }}
              className="absolute left-2 md:left-3 top-1/2 -translate-y-1/2 z-30 inline-flex h-10 w-10 items-center justify-center rounded-full bg-black/10 text-white/80 backdrop-blur-sm transition hover:bg-black/25 hover:text-white active:scale-90"
              aria-label="Previous photo"
            >
              <ChevronLeft size={22} />
            </button>
          )}
          {hasNext && onNext && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onNext(); }}
              className="absolute right-2 md:right-3 top-1/2 -translate-y-1/2 z-30 inline-flex h-10 w-10 items-center justify-center rounded-full bg-black/10 text-white/80 backdrop-blur-sm transition hover:bg-black/25 hover:text-white active:scale-90"
              aria-label="Next photo"
            >
              <ChevronRight size={22} />
            </button>
          )}
          <div
            className="relative flex h-full w-full min-h-0 min-w-0 items-center justify-center"
            style={{ touchAction: 'pan-y' }}
            onPointerDown={handleSwipeStart}
            onPointerUp={handleSwipeEnd}
            onPointerCancel={handleSwipeCancel}
          >
            <SecureImage
              src={imageUrl}
              alt="Preview"
              className="h-full w-full rounded-lg object-contain"
              decoding="async"
            />
            {originalImageUrl && (
              <div
                className={`absolute inset-0 bg-stone-50 rounded-lg transition-opacity duration-200 pointer-events-none ${
                  showOriginal ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <SecureImage
                  src={originalImageUrl}
                  alt="Original Preview"
                  className="h-full w-full rounded-lg object-contain"
                  decoding="async"
                />
              </div>
            )}
          </div>
          {originalImageUrl && (
            <button
              type="button"
              onClick={() => setShowOriginal(!showOriginal)}
              className={`absolute bottom-4 right-4 z-30 inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold shadow-lg backdrop-blur-md transition active:scale-95 cursor-pointer ${
                showOriginal
                  ? 'border-emerald-600 bg-emerald-700 text-white hover:bg-emerald-800'
                  : 'border-stone-200 bg-white/90 text-stone-800 hover:bg-stone-100'
              }`}
            >
              <Layers size={13} />
              {showOriginal ? 'Show Effect' : 'Show Original'}
            </button>
          )}
        </div>

        {/* Premium EXIF Details Overlay Panel */}
        <div className="flex h-[48vh] md:h-auto min-h-0 w-full shrink-0 flex-col bg-stone-50 text-stone-850 select-none md:max-h-[92vh] md:w-80 md:border-l md:border-stone-200/80 border-t border-stone-200/80 md:border-t-0">
          <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-5 space-y-4">
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 mb-1">
                Image Metadata
              </h4>
              <h3
                id="lightbox-modal-title"
                className="text-sm font-bold text-stone-900 leading-snug truncate"
              >
                {entry.title || 'Untitled Image'}
              </h3>
              {entry.summary && (
                <p className="text-[11px] text-stone-600 leading-normal mt-1 max-h-32 overflow-y-auto pr-1">
                  {entry.summary}
                </p>
              )}
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[8.5px] font-medium text-emerald-700"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="h-px bg-stone-200" />

            {/* EXIF Data Fields */}
            {exif ? (
              <div className="space-y-3.5">
                {/* Camera Make & Model */}
                {(exif.make || exif.model) && (
                  <div className="flex items-start gap-2 text-xs">
                    <Cpu size={14} className="text-stone-500 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                        Camera
                      </div>
                      <div className="font-semibold text-stone-900 mt-0.5">
                        {(() => {
                          const make = exif.make || '';
                          const model = exif.model || '';
                          if (make && model) {
                            return model
                              .toLowerCase()
                              .includes(make.toLowerCase())
                              ? model
                              : `${make} ${model}`;
                          }
                          return make || model;
                        })()}
                      </div>
                    </div>
                  </div>
                )}

                {/* Lens Model */}
                {exif.lensModel && (
                  <div className="flex items-start gap-2 text-xs">
                    <Layers
                      size={14}
                      className="text-stone-500 shrink-0 mt-0.5"
                    />
                    <div>
                      <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                        Lens
                      </div>
                      <div className="font-semibold text-stone-900 mt-0.5 truncate max-w-[220px]">
                        {exif.lensModel}
                      </div>
                    </div>
                  </div>
                )}

                {/* Exposure Parameters (Shutter Speed, f-stop, ISO, Focal Length) */}
                {(exif.exposureTime ||
                  exif.fNumber ||
                  exif.iso ||
                  exif.focalLength) && (
                  <div className="flex items-start gap-2 text-xs">
                    <Info
                      size={14}
                      className="text-stone-500 shrink-0 mt-0.5"
                    />
                    <div>
                      <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                        Settings
                      </div>
                      <div className="font-semibold text-stone-700 mt-0.5 flex flex-wrap gap-x-1.5 gap-y-0.5">
                        {exif.exposureTime && (
                          <span>{formatShutterSpeed(exif.exposureTime)}</span>
                        )}
                        {exif.fNumber && <span>f/{exif.fNumber}</span>}
                        {exif.iso && <span>ISO {exif.iso}</span>}
                        {exif.focalLength && <span>{exif.focalLength}mm</span>}
                      </div>
                    </div>
                  </div>
                )}

                {/* File Info (Size & Resolution) */}
                {(exif.fileSizeInByte ||
                  exif.exifImageWidth ||
                  exif.exifImageHeight) && (
                  <div className="flex items-start gap-2 text-xs">
                    <HardDrive
                      size={14}
                      className="text-stone-500 shrink-0 mt-0.5"
                    />
                    <div>
                      <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                        File / Dimension
                      </div>
                      <div className="font-semibold text-stone-700 mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
                        {exif.fileSizeInByte && (
                          <span>{formatFileSize(exif.fileSizeInByte)}</span>
                        )}
                        {exif.exifImageWidth && exif.exifImageHeight && (
                          <span>
                            {exif.exifImageWidth} × {exif.exifImageHeight}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Date Taken */}
                {(exif.dateTimeOriginal || entry.created_at) && (
                  <div className="flex items-start gap-2 text-xs">
                    <Calendar
                      size={14}
                      className="text-stone-500 shrink-0 mt-0.5"
                    />
                    <div>
                      <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                        Captured
                      </div>
                      <div className="font-semibold text-stone-700 mt-0.5">
                        {formatDateTime(
                          exif.dateTimeOriginal || entry.created_at,
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* GPS Coordinates & Location */}
                {typeof exif.latitude === 'number' &&
                  typeof exif.longitude === 'number' && (
                    <div className="flex items-start gap-2 text-xs">
                      <MapPin
                        size={14}
                        className="text-stone-500 shrink-0 mt-0.5"
                      />
                      <div>
                        <div className="text-[9px] font-bold text-stone-500 uppercase tracking-wide">
                          Location
                        </div>                        <a
                          href={`https://www.google.com/maps/search/?api=1&query=${exif.latitude},${exif.longitude}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 mt-0.5 hover:underline"
                        >
                          <span>
                            {(() => {
                              const parts = [];
                              if (exif.city) parts.push(exif.city);
                              if (exif.state) parts.push(exif.state);
                              if (exif.country) parts.push(exif.country);
                              return parts.length > 0
                                ? parts.join(', ')
                                : `${exif.latitude.toFixed(5)}, ${exif.longitude.toFixed(5)}`;
                            })()}
                          </span>
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    </div>
                  )}
              </div>
            ) : (
              <div className="text-[10px] text-stone-500 text-center py-4 bg-stone-150/30 border border-stone-200 rounded-xl">
                No EXIF metadata found in database.
              </div>
            )}
          </div>

          {/* Lightbox Footer Actions */}
          <div className="border-t border-stone-200 bg-stone-50 p-4 md:p-5 shrink-0">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleLike();
                }}
                className={`relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-lg transition active:scale-95 ${
                  liked === true
                    ? 'bg-emerald-700 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200 hover:text-stone-850'
                }`}
                aria-label="Like image"
                title="Like image"
              >
                <ThumbsUp size={14} />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleDislike();
                }}
                className={`relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-lg transition active:scale-95 ${
                  liked === false
                    ? 'bg-rose-700 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200 hover:text-stone-850'
                }`}
                aria-label="Dislike image"
                title="Dislike image"
              >
                <ThumbsDown size={14} />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleShare();
                }}
                disabled={isSharing}
                className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-stone-100 text-stone-600 shadow-lg transition hover:bg-stone-200 hover:text-stone-850 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Share image"
                title={
                  shareStatus === 'copied'
                    ? 'Link copied!'
                    : shareStatus === 'error'
                      ? 'Failed to copy'
                      : 'Share image'
                }
              >
                {shareStatus === 'copied' ? (
                  <Check size={14} className="text-emerald-500" />
                ) : shareStatus === 'error' ? (
                  <X size={14} className="text-rose-500" />
                ) : (
                  <Share2 size={14} />
                )}
                {shareStatus === 'copied' && (
                  <span className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-sm bg-emerald-700 px-2 py-0.5 text-[10px] font-medium text-white shadow-md">
                    Copied!
                  </span>
                )}
              </button>
              <a
                href={`/api/generation/history/${entry.task_id}/image`}
                download
                className="flex h-9 flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-700 text-xs font-semibold text-white shadow-lg transition hover:bg-emerald-800 active:scale-95"
                onClick={(e) => e.stopPropagation()}
              >
                <Download size={14} />
                Download
              </a>
            </div>
          </div>
        </div>

        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-30 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-stone-100/80 text-stone-800 hover:bg-stone-200 hover:text-stone-950 shadow-md transition active:scale-90"
          aria-label="Close"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
});
