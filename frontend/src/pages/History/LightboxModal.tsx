import { useEffect, useState, memo } from 'react';
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
} from 'lucide-react';
import { type GenerationHistoryEntry } from '../../api/client';
import { SecureImage } from '../../components/SecureImage';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { formatDateTime } from '../datetime.utils';
import { logger } from '../../utils/logger';

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
}

export const LightboxModal = memo(function LightboxModal({
  isOpen,
  onClose,
  imageUrl,
  entry,
  exif,
}: LightboxModalProps) {
  const [isSharing, setIsSharing] = useState(false);
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied' | 'error'>(
    'idle',
  );
  const [showOriginal, setShowOriginal] = useState(false);
  const trapRef = useFocusTrap(isOpen);

  useEffect(() => {
    setShowOriginal(false);
  }, [imageUrl, isOpen]);

  const sourceAssetId = (() => {
    if (!entry?.source_asset_ids) return null;
    try {
      const ids = JSON.parse(entry.source_asset_ids);
      return Array.isArray(ids) && ids.length > 0 ? ids[0] : null;
    } catch {
      return null;
    }
  })();
  const originalImageUrl = sourceAssetId
    ? `/api/immich/assets/${sourceAssetId}/thumbnail?size=preview`
    : null;

  // Handle Escape key to close lightbox
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

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
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/98 p-3 md:items-center md:p-4 backdrop-blur-xl animate-fade-in"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lightbox-modal-title"
        className="relative flex w-full max-w-[94vw] flex-col items-stretch justify-center overflow-hidden rounded-2xl border border-stone-800 bg-stone-950/80 shadow-2xl animate-scale-in md:max-h-[92vh] md:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Photo Canvas */}
        <div className="relative flex max-h-[52vh] flex-1 items-center justify-center bg-stone-950 p-2 md:max-h-[85vh]">
          <SecureImage
            src={imageUrl}
            alt="Preview"
            className="max-h-full max-w-full rounded-lg object-contain"
          />
          {originalImageUrl && (
            <div
              className={`absolute inset-0 flex items-center justify-center bg-stone-950 transition-opacity duration-200 pointer-events-none ${
                showOriginal ? 'opacity-100' : 'opacity-0'
              }`}
            >
              <SecureImage
                src={originalImageUrl}
                alt="Original Preview"
                className="max-h-full max-w-full rounded-lg object-contain"
              />
            </div>
          )}
          {originalImageUrl && (
            <button
              type="button"
              onClick={() => setShowOriginal(!showOriginal)}
              className={`absolute bottom-4 right-4 z-30 inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold shadow-lg backdrop-blur-md transition active:scale-95 cursor-pointer ${
                showOriginal
                  ? 'border-emerald-600 bg-emerald-800 text-white hover:bg-emerald-900'
                  : 'border-white/10 bg-stone-900/80 text-white hover:bg-stone-955'
              }`}
            >
              <Layers size={13} />
              {showOriginal ? 'Show Effect' : 'Show Original'}
            </button>
          )}
        </div>

        {/* Premium EXIF Details Overlay Panel */}
        <div className="flex max-h-[48vh] min-h-0 w-full shrink-0 flex-col overflow-y-auto bg-stone-900 p-4 text-stone-200 select-none md:max-h-[92vh] md:w-80 md:p-5">
          <div className="space-y-4">
            <div>
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">
                Image Metadata
              </h4>
              <h3
                id="lightbox-modal-title"
                className="text-sm font-bold text-white leading-snug truncate"
              >
                {entry.title || 'Untitled Image'}
              </h3>
              {entry.summary && (
                <p className="text-[11px] text-stone-400 leading-normal mt-1 max-h-16 overflow-y-auto pr-1">
                  {entry.summary}
                </p>
              )}
            </div>

            <div className="h-px bg-stone-800" />

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
                      <div className="font-semibold text-white mt-0.5">
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
                      <div className="font-semibold text-white mt-0.5 truncate max-w-[220px]">
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
                      <div className="font-semibold text-stone-300 mt-0.5 flex flex-wrap gap-x-1.5 gap-y-0.5">
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
                      <div className="font-semibold text-stone-300 mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
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
                      <div className="font-semibold text-stone-300 mt-0.5">
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
                        </div>
                        <a
                          href={`https://www.google.com/maps/search/?api=1&query=${exif.latitude},${exif.longitude}`}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 mt-0.5 hover:underline"
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
              <div className="text-[10px] text-stone-500 text-center py-4 bg-stone-950/20 border border-stone-850/50 rounded-xl">
                No EXIF metadata found in database.
              </div>
            )}
          </div>

          {/* Lightbox Footer Actions */}
          <div className="sticky bottom-0 mt-4 border-t border-stone-800 bg-stone-900 pt-4 md:mt-0">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleShare();
                }}
                disabled={isSharing}
                className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-stone-800 text-white shadow-lg transition hover:bg-stone-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
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
                  <span className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-sm bg-emerald-800 px-2 py-0.5 text-[10px] font-medium text-white shadow-md">
                    Copied!
                  </span>
                )}
              </button>
              <a
                href={`/api/generation/history/${entry.task_id}/image`}
                download
                className="flex h-9 flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-800 text-xs font-semibold text-white shadow-lg transition hover:bg-emerald-900 active:scale-95"
                onClick={(e) => e.stopPropagation()}
              >
                <Download size={14} />
                Download Full-Res {(entry.output_format || 'png').toUpperCase()}
              </a>
            </div>
          </div>
        </div>

        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-30 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-black/55 text-white hover:bg-white hover:text-stone-900 shadow-md transition active:scale-90"
          aria-label="Close"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
});
