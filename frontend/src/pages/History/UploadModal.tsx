import { useEffect, useState, memo } from 'react';
import { X, FolderPlus, ChevronDown } from 'lucide-react';
import { type GenerationHistoryEntry } from '../../api/client';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface AlbumOption {
  id: string;
  album_name: string;
  asset_count: number;
}

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  entry: GenerationHistoryEntry;
  albums: AlbumOption[];
  onConfirm: (variables: {
    create_album: boolean;
    album_name: string | null;
    album_id: string | null;
  }) => void;
  isPending: boolean;
}

export const UploadModal = memo(function UploadModal({
  isOpen,
  onClose,
  entry,
  albums,
  onConfirm,
  isPending,
}: UploadModalProps) {
  const [targetAlbumType, setTargetAlbumType] = useState<
    'existing' | 'new' | 'none'
  >('none');
  const [selectedAlbumId, setSelectedAlbumId] = useState<string>('');
  const [newAlbumName, setNewAlbumName] = useState<string>('');
  const trapRef = useFocusTrap(isOpen);

  // Auto-initialize album selection when modal opens or active entry changes
  useEffect(() => {
    if (isOpen) {
      const defaultAlbumName = entry.album_name || '';
      if (!defaultAlbumName) {
        setTargetAlbumType('none');
        setSelectedAlbumId('');
        setNewAlbumName('');
      } else {
        const existing = albums.find(
          (a) => a.album_name.toLowerCase() === defaultAlbumName.toLowerCase(),
        );
        if (existing) {
          setTargetAlbumType('existing');
          setSelectedAlbumId(existing.id);
          setNewAlbumName('');
        } else {
          setTargetAlbumType('new');
          setNewAlbumName(defaultAlbumName);
          setSelectedAlbumId('');
        }
      }
    }
  }, [isOpen, entry, albums]);

  if (!isOpen) return null;

  const isConfirmDisabled =
    isPending ||
    (targetAlbumType === 'existing' && !selectedAlbumId) ||
    (targetAlbumType === 'new' && !newAlbumName.trim());

  const handleConfirm = () => {
    onConfirm({
      create_album: targetAlbumType === 'new',
      album_name:
        targetAlbumType === 'new'
          ? newAlbumName
          : targetAlbumType === 'existing'
            ? (albums.find((a) => a.id === selectedAlbumId)?.album_name ?? null)
            : null,
      album_id: targetAlbumType === 'existing' ? selectedAlbumId : null,
    });
  };

  return (
    <div
      ref={trapRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-modal-title"
        className="w-full max-w-md rounded-2xl bg-white border border-stone-200 shadow-2xl p-6 relative animate-scale-in"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute top-4 right-4 p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-50 transition"
        >
          <X size={16} />
        </button>

        <h3 id="upload-modal-title" className="text-base font-bold text-stone-900 flex items-center gap-2">
          <FolderPlus size={18} className="text-emerald-700" />
          Upload Destination Album
        </h3>
        <p className="text-xs text-stone-500 mt-1.5">
          Specify which album in Immich this generated image should be
          associated with.
        </p>

        <div className="mt-4 space-y-4">
          {/* Radio Group Options */}
          <div className="grid gap-2">
            <label
              className={`flex items-center gap-2.5 rounded-xl border p-3 cursor-pointer transition ${
                targetAlbumType === 'none'
                  ? 'border-emerald-500 bg-emerald-50/20 text-emerald-950 font-bold'
                  : 'border-stone-200 text-stone-700 hover:bg-stone-50'
              }`}
            >
              <input
                type="radio"
                name="albumType"
                checked={targetAlbumType === 'none'}
                onChange={() => setTargetAlbumType('none')}
                className="accent-emerald-700"
              />
              <div className="text-xs">
                <div>No album association</div>
                <div className="text-[10px] text-stone-400 font-normal mt-0.5">
                  Upload only to main Immich timeline
                </div>
              </div>
            </label>

            <label
              className={`flex items-center gap-2.5 rounded-xl border p-3 cursor-pointer transition ${
                targetAlbumType === 'existing'
                  ? 'border-emerald-500 bg-emerald-50/20 text-emerald-950 font-bold'
                  : 'border-stone-200 text-stone-700 hover:bg-stone-50'
              }`}
            >
              <input
                type="radio"
                name="albumType"
                checked={targetAlbumType === 'existing'}
                onChange={() => setTargetAlbumType('existing')}
                className="accent-emerald-700"
              />
              <div className="text-xs">
                <div>Add to existing album</div>
                <div className="text-[10px] text-stone-400 font-normal mt-0.5">
                  Select one of your existing Immich library albums
                </div>
              </div>
            </label>

            <label
              className={`flex items-center gap-2.5 rounded-xl border p-3 cursor-pointer transition ${
                targetAlbumType === 'new'
                  ? 'border-emerald-500 bg-emerald-50/20 text-emerald-950 font-bold'
                  : 'border-stone-200 text-stone-700 hover:bg-stone-50'
              }`}
            >
              <input
                type="radio"
                name="albumType"
                checked={targetAlbumType === 'new'}
                onChange={() => setTargetAlbumType('new')}
                className="accent-emerald-700"
              />
              <div className="text-xs">
                <div>Create new album</div>
                <div className="text-[10px] text-stone-400 font-normal mt-0.5">
                  Create a brand new album in Immich for this asset
                </div>
              </div>
            </label>
          </div>

          {/* Album Selection Dynamic Fields */}
          {targetAlbumType === 'existing' && (
            <div className="space-y-1.5 animate-slide-down">
              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">
                Select existing Immich album
              </span>
              <div className="relative">
                <select
                  value={selectedAlbumId}
                  onChange={(e) => setSelectedAlbumId(e.target.value)}
                  className="w-full h-9 pl-3 pr-8 text-xs bg-white rounded-lg border border-stone-300 focus:outline-hidden focus:border-emerald-600 appearance-none"
                >
                  <option value="">-- Choose an album --</option>
                  {albums.map((album) => (
                    <option key={album.id} value={album.id}>
                      {album.album_name} ({album.asset_count} photos)
                    </option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="absolute right-2.5 top-2.5 pointer-events-none text-stone-500"
                />
              </div>
            </div>
          )}

          {targetAlbumType === 'new' && (
            <div className="space-y-1.5 animate-slide-down">
              <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">
                New Album Title
              </span>
              <input
                type="text"
                value={newAlbumName}
                onChange={(e) => setNewAlbumName(e.target.value)}
                placeholder="Enter new album name"
                className="w-full h-9 px-3 text-xs bg-white rounded-lg border border-stone-300 focus:outline-hidden focus:border-emerald-600"
              />
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2.5 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 h-9 rounded-lg border border-stone-300 text-xs font-semibold text-stone-600 hover:bg-stone-50 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isConfirmDisabled}
              onClick={handleConfirm}
              className="flex-1 h-9 rounded-lg bg-emerald-800 text-xs font-semibold text-white hover:bg-emerald-950 disabled:bg-stone-200 transition"
            >
              {isPending ? 'Uploading...' : 'Confirm Upload'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});
