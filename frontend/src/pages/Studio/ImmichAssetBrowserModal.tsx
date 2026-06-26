import { X, Image as ImageIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getImmichAssets, getImmichAssetThumbnailUrl, type ImmichAsset } from '../../api/client';
import { InlineSpinner } from '../../components/ErrorUI';
import { InlineError } from '../../components/FormUI';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { formatDate } from '../datetime.utils';

interface ImmichAssetBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectAsset: (asset: ImmichAsset) => void;
}

export function ImmichAssetBrowserModal({
  isOpen,
  onClose,
  onSelectAsset,
}: ImmichAssetBrowserModalProps) {
  const trapRef = useFocusTrap(isOpen);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['immich-assets-studio'],
    queryFn: () => getImmichAssets({ mediaType: 'photo' }),
    enabled: isOpen,
    // Keep page bounded to 48 assets as recommended in the plan
    select: (res) => res.items.slice(0, 48),
  });

  if (!isOpen) return null;

  return (
    <div
      ref={trapRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-stone-900/40 backdrop-blur-md transition-all duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="asset-browser-title"
        className="relative w-full max-w-4xl h-[80vh] flex flex-col rounded-3xl border border-stone-200 bg-white/95 shadow-2xl backdrop-blur-xl overflow-hidden transition-all scale-100 duration-300"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-150 px-6 py-4 bg-stone-50/50">
          <div>
            <h2
              id="asset-browser-title"
              className="text-base font-bold text-stone-950 flex items-center gap-2"
            >
              <ImageIcon size={18} className="text-emerald-700" />
              Browse Immich
            </h2>
            <p className="text-xs text-stone-500 mt-0.5">
              Select an image from your library as the source for Studio effects
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-xl p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition active:scale-95"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-stone-500">
              <InlineSpinner />
              <span className="text-xs font-medium">Loading assets from Immich…</span>
            </div>
          )}

          {isError && (
            <div className="flex h-full flex-col items-center justify-center">
              <InlineError
                title="Failed to load library"
                message={error instanceof Error ? error.message : 'Unknown error occurred'}
              />
            </div>
          )}

          {!isLoading && !isError && (!data || data.length === 0) && (
            <div className="flex h-full flex-col items-center justify-center text-center p-6 border border-dashed border-stone-250 rounded-2xl bg-stone-50/50">
              <ImageIcon size={32} className="text-stone-300 mb-2" />
              <p className="text-sm font-semibold text-stone-800">No photos found</p>
              <p className="text-xs text-stone-500 mt-1">
                Your Immich library doesn't seem to contain any supported photo assets.
              </p>
            </div>
          )}

          {!isLoading && !isError && data && data.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3.5 pb-6">
              {data.map((asset) => (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => onSelectAsset(asset)}
                  className="group relative aspect-square w-full overflow-hidden rounded-2xl border border-stone-200 bg-stone-50 hover:border-emerald-700 hover:shadow-lg transition-all duration-300 cursor-pointer hover:-translate-y-0.5 active:translate-y-0 active:scale-95"
                >
                  <img
                    src={getImmichAssetThumbnailUrl(asset.id, 'preview')}
                    alt={asset.original_file_name || 'Immich photo'}
                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-108"
                    loading="lazy"
                  />

                  {/* Gradient details overlay */}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-stone-950/85 via-stone-900/40 to-transparent p-2.5 text-left opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                    <p className="text-[10px] font-bold text-white truncate leading-tight">
                      {asset.original_file_name || 'photo.jpg'}
                    </p>
                    {asset.created_at && (
                      <p className="text-[8px] text-stone-300 mt-0.5">
                        {formatDate(asset.created_at)}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
