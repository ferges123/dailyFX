import { useState } from 'react';
import {
  X,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
  Folder,
  Users,
  User,
  Search,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import {
  getImmichAlbums,
  getImmichAssets,
  getImmichFilterOptions,
  getImmichAssetThumbnailUrl,
  type ImmichAsset,
  type ImmichAlbum,
  type ImmichPerson,
} from '../../api/client';
import { SecureImage } from '../../components/SecureImage';
import { InlineSpinner } from '../../components/ErrorUI';
import { InlineError } from '../../components/FormUI';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { formatDate } from '../datetime.utils';

interface ImmichAssetBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectAsset: (asset: ImmichAsset) => void;
}

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: (number | string)[] = [];
  if (totalPages <= 5) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    pages.push(1);
    if (currentPage > 3) {
      pages.push('...');
    }
    const start = Math.max(2, currentPage - 1);
    const end = Math.min(totalPages - 1, currentPage + 1);
    for (let i = start; i <= end; i++) {
      if (!pages.includes(i)) pages.push(i);
    }
    if (currentPage < totalPages - 2) {
      pages.push('...');
    }
    if (!pages.includes(totalPages)) pages.push(totalPages);
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-6 py-2">
      <button
        type="button"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
        className="flex items-center gap-1 rounded-xl border border-stone-200 px-3 py-1.5 text-xs font-semibold text-stone-600 bg-white hover:bg-stone-50 active:scale-95 transition disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100"
      >
        <ChevronLeft size={14} />
        Prev
      </button>
      {pages.map((p, idx) => {
        if (p === '...') {
          return (
            <span
              key={`dots-${idx}`}
              className="px-1.5 text-stone-400 text-xs font-medium"
            >
              ...
            </span>
          );
        }
        const isCurrent = p === currentPage;
        return (
          <button
            key={`page-${p}`}
            type="button"
            onClick={() => onPageChange(p as number)}
            className={`rounded-xl w-8 h-8 flex items-center justify-center text-xs font-bold transition active:scale-95 ${
              isCurrent
                ? 'bg-emerald-700 text-white'
                : 'border border-stone-200 text-stone-600 bg-white hover:bg-stone-50'
            }`}
          >
            {p}
          </button>
        );
      })}
      <button
        type="button"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        className="flex items-center gap-1 rounded-xl border border-stone-200 px-3 py-1.5 text-xs font-semibold text-stone-600 bg-white hover:bg-stone-50 active:scale-95 transition disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100"
      >
        Next
        <ChevronRight size={14} />
      </button>
    </div>
  );
}

export function ImmichAssetBrowserModal({
  isOpen,
  onClose,
  onSelectAsset,
}: ImmichAssetBrowserModalProps) {
  const trapRef = useFocusTrap(isOpen);

  const [activeTab, setActiveTab] = useState<'albums' | 'people'>('albums');
  const [view, setView] = useState<'albums' | 'people' | 'assets'>('albums');
  const [selectedAlbum, setSelectedAlbum] = useState<ImmichAlbum | null>(null);
  const [selectedPerson, setSelectedPerson] = useState<ImmichPerson | null>(
    null,
  );
  const [assetsSource, setAssetsSource] = useState<'album' | 'people' | null>(
    null,
  );

  const [albumsPage, setAlbumsPage] = useState(1);
  const [assetsPage, setAssetsPage] = useState(1);
  const [personSearch, setPersonSearch] = useState('');

  const [sortBy, setSortBy] = useState<
    'name' | 'count' | 'created' | 'modified'
  >('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const ALBUMS_PAGE_SIZE = 12;
  const ASSETS_PAGE_SIZE = 24;

  // Query for albums list
  const {
    data: albumsData,
    isLoading: isLoadingAlbums,
    isError: isErrorAlbums,
    error: errorAlbums,
  } = useQuery({
    queryKey: ['immich-albums-studio', albumsPage, sortBy, sortOrder],
    queryFn: () =>
      getImmichAlbums({
        page: albumsPage,
        size: ALBUMS_PAGE_SIZE,
        sortBy,
        sortOrder,
      }),
    enabled: isOpen && activeTab === 'albums' && view === 'albums',
  });

  // Query for people list
  const {
    data: filterOptionsData,
    isLoading: isLoadingPeople,
    isError: isErrorPeople,
    error: errorPeople,
  } = useQuery({
    queryKey: ['immich-people-studio'],
    queryFn: getImmichFilterOptions,
    enabled: isOpen && activeTab === 'people' && view === 'people',
  });

  const peopleList = filterOptionsData?.people ?? [];
  const filteredPeople = peopleList.filter((p) =>
    p.name.toLowerCase().includes(personSearch.toLowerCase()),
  );

  // Query for assets in selected album or selected person
  const {
    data: assetsData,
    isLoading: isLoadingAssets,
    isError: isErrorAssets,
    error: errorAssets,
  } = useQuery({
    queryKey: [
      'immich-assets-studio',
      assetsSource,
      selectedAlbum?.id,
      selectedPerson?.id,
      assetsPage,
    ],
    queryFn: () =>
      getImmichAssets({
        mediaType: 'photo',
        albumIds:
          assetsSource === 'album' && selectedAlbum
            ? [selectedAlbum.id]
            : undefined,
        personIds:
          assetsSource === 'people' && selectedPerson
            ? [selectedPerson.id]
            : undefined,
        page: assetsPage,
        size: ASSETS_PAGE_SIZE,
      }),
    enabled:
      isOpen &&
      view === 'assets' &&
      ((assetsSource === 'album' && !!selectedAlbum) ||
        (assetsSource === 'people' && !!selectedPerson)),
  });

  const handleSelectAlbum = (album: ImmichAlbum) => {
    setSelectedAlbum(album);
    setSelectedPerson(null);
    setAssetsSource('album');
    setAssetsPage(1);
    setView('assets');
  };

  const handleSelectPerson = (person: ImmichPerson) => {
    setSelectedPerson(person);
    setSelectedAlbum(null);
    setAssetsSource('people');
    setAssetsPage(1);
    setView('assets');
  };

  const handleBackFromAssets = () => {
    if (assetsSource === 'album') {
      setView('albums');
      setActiveTab('albums');
      setSelectedAlbum(null);
    } else {
      setView('people');
      setActiveTab('people');
      setSelectedPerson(null);
    }
    setAssetsSource(null);
  };

  const handleTabChange = (tab: 'albums' | 'people') => {
    setActiveTab(tab);
    setView(tab);
    setSelectedAlbum(null);
    setSelectedPerson(null);
    setAssetsSource(null);
    setAssetsPage(1);
  };

  const handleClose = () => {
    setActiveTab('albums');
    setView('albums');
    setSelectedAlbum(null);
    setSelectedPerson(null);
    setAssetsSource(null);
    setAlbumsPage(1);
    setAssetsPage(1);
    setPersonSearch('');
    setSortBy('name');
    setSortOrder('asc');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      ref={trapRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-stone-900/40 backdrop-blur-md transition-all duration-300"
        onClick={handleClose}
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
          <div className="flex items-center gap-3">
            {view === 'assets' ? (
              <button
                type="button"
                onClick={handleBackFromAssets}
                className="flex items-center gap-1 rounded-xl border border-stone-250 bg-white px-3 py-1.5 text-xs font-bold text-stone-700 hover:bg-stone-50 active:scale-95 transition"
              >
                <ChevronLeft size={14} />
                {assetsSource === 'album' ? 'Back to Albums' : 'Back to People'}
              </button>
            ) : (
              <div
                id="asset-browser-title"
                role="tablist"
                aria-label="Browser navigation tabs"
                className="flex items-center gap-1.5 p-1 rounded-2xl bg-stone-200/60 border border-stone-200"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === 'albums'}
                  onClick={() => handleTabChange('albums')}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 ${
                    activeTab === 'albums'
                      ? 'bg-white text-stone-900 shadow-sm'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  <Folder
                    size={15}
                    className={
                      activeTab === 'albums'
                        ? 'text-emerald-700'
                        : 'text-stone-400'
                    }
                  />
                  Albumy
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === 'people'}
                  onClick={() => handleTabChange('people')}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition active:scale-95 ${
                    activeTab === 'people'
                      ? 'bg-white text-stone-900 shadow-sm'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  <Users
                    size={15}
                    className={
                      activeTab === 'people'
                        ? 'text-emerald-700'
                        : 'text-stone-400'
                    }
                  />
                  Osoby
                </button>
              </div>
            )}

            {view === 'assets' && (
              <div>
                <h2
                  id="asset-browser-title"
                  className="text-base font-bold text-stone-950 flex items-center gap-2"
                >
                  <ImageIcon size={18} className="text-emerald-700" />
                  {assetsSource === 'album'
                    ? `Album: ${selectedAlbum?.album_name}`
                    : `Person: ${selectedPerson?.name}`}
                </h2>
                <p className="text-xs text-stone-500 mt-0.5">
                  Total photos:{' '}
                  {assetsSource === 'album'
                    ? selectedAlbum?.asset_count || 0
                    : selectedPerson?.asset_count || 0}
                </p>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="rounded-xl p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition active:scale-95"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col">
          {/* Albums View */}
          {view === 'albums' && (
            <div className="flex-1 flex flex-col justify-between">
              <div>
                {isLoadingAlbums && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center gap-3 text-stone-500">
                    <InlineSpinner />
                    <span className="text-xs font-medium">
                      Loading albums from Immich…
                    </span>
                  </div>
                )}

                {isErrorAlbums && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center">
                    <InlineError
                      title="Failed to load albums"
                      message={
                        errorAlbums instanceof Error
                          ? errorAlbums.message
                          : 'Unknown error occurred'
                      }
                    />
                  </div>
                )}

                {!isLoadingAlbums &&
                  !isErrorAlbums &&
                  (!albumsData || albumsData.items.length === 0) && (
                    <div className="flex min-h-[30vh] flex-col items-center justify-center text-center p-6 border border-dashed border-stone-250 rounded-2xl bg-stone-50/50">
                      <Folder size={32} className="text-stone-300 mb-2" />
                      <p className="text-sm font-semibold text-stone-800">
                        No albums found
                      </p>
                      <p className="text-xs text-stone-500 mt-1">
                        Your Immich library does not contain any albums.
                      </p>
                    </div>
                  )}

                {!isLoadingAlbums &&
                  !isErrorAlbums &&
                  albumsData &&
                  albumsData.items.length > 0 && (
                    <>
                      {/* Filter and sorting actions bar */}
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5 pb-3 border-b border-stone-150">
                        <div className="text-xs font-semibold text-stone-500">
                          Showing {albumsData.count} of {albumsData.total}{' '}
                          albums
                        </div>
                        <div className="flex items-center gap-2">
                          <label
                            htmlFor="album-sort"
                            className="text-xs font-bold text-stone-600"
                          >
                            Sort by:
                          </label>
                          <select
                            id="album-sort"
                            value={`${sortBy}-${sortOrder}`}
                            onChange={(e) => {
                              const [by, order] = e.target.value.split('-');
                              setSortBy(
                                by as 'name' | 'count' | 'created' | 'modified',
                              );
                              setSortOrder(order as 'asc' | 'desc');
                              setAlbumsPage(1);
                            }}
                            className="rounded-xl border border-stone-250 bg-white px-2.5 py-1.5 text-xs font-semibold text-stone-700 hover:border-stone-400 focus:outline-none focus:ring-1 focus:ring-emerald-700 transition cursor-pointer"
                          >
                            <option value="name-asc">Name (A-Z)</option>
                            <option value="name-desc">Name (Z-A)</option>
                            <option value="count-desc">
                              Photos Count (High to Low)
                            </option>
                            <option value="count-asc">
                              Photos Count (Low to High)
                            </option>
                            <option value="created-desc">
                              Date Created (Newest First)
                            </option>
                            <option value="created-asc">
                              Date Created (Oldest First)
                            </option>
                            <option value="modified-desc">
                              Last Photo Added (Newest First)
                            </option>
                            <option value="modified-asc">
                              Last Photo Added (Oldest First)
                            </option>
                          </select>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                        {albumsData.items.map((album) => (
                          <button
                            key={album.id}
                            type="button"
                            onClick={() => handleSelectAlbum(album)}
                            className="group relative flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white hover:border-emerald-700 hover:shadow-lg transition-all duration-300 cursor-pointer text-left hover:-translate-y-0.5 active:translate-y-0 active:scale-98"
                          >
                            <div className="aspect-video w-full overflow-hidden bg-stone-100 relative">
                              {album.thumbnail_asset_id ? (
                                <SecureImage
                                  src={getImmichAssetThumbnailUrl(
                                    album.thumbnail_asset_id,
                                    'preview',
                                  )}
                                  alt={album.album_name}
                                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                                  loading="lazy"
                                  decoding="async"
                                />
                              ) : (
                                <div className="h-full w-full flex items-center justify-center bg-stone-50 text-stone-400">
                                  <Folder size={28} />
                                </div>
                              )}
                              <div className="absolute top-2 right-2 bg-stone-900/70 backdrop-blur-md text-[10px] font-bold text-white px-2 py-0.5 rounded-full">
                                {album.asset_count}
                              </div>
                            </div>
                            <div className="p-3.5">
                              <h3 className="text-xs font-bold text-stone-850 truncate leading-tight group-hover:text-emerald-800 transition-colors">
                                {album.album_name}
                              </h3>
                            </div>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
              </div>

              {!isLoadingAlbums && !isErrorAlbums && albumsData && (
                <Pagination
                  currentPage={albumsPage}
                  totalPages={albumsData.pages}
                  onPageChange={setAlbumsPage}
                />
              )}
            </div>
          )}

          {/* People View */}
          {view === 'people' && (
            <div className="flex-1 flex flex-col justify-between">
              <div>
                {isLoadingPeople && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center gap-3 text-stone-500">
                    <InlineSpinner />
                    <span className="text-xs font-medium">
                      Loading people from Immich…
                    </span>
                  </div>
                )}

                {isErrorPeople && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center">
                    <InlineError
                      title="Failed to load people"
                      message={
                        errorPeople instanceof Error
                          ? errorPeople.message
                          : 'Unknown error occurred'
                      }
                    />
                  </div>
                )}

                {!isLoadingPeople && !isErrorPeople && (
                  <>
                    {/* Search bar */}
                    <div className="flex items-center gap-2 mb-5 pb-3 border-b border-stone-150">
                      <div className="relative flex-1">
                        <Search
                          size={16}
                          className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400"
                        />
                        <input
                          type="text"
                          value={personSearch}
                          onChange={(e) => setPersonSearch(e.target.value)}
                          placeholder="Search people by name…"
                          className="w-full rounded-xl border border-stone-250 bg-white pl-9 pr-3 py-2 text-xs font-semibold text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-1 focus:ring-emerald-700 transition"
                        />
                      </div>
                      <div className="text-xs font-semibold text-stone-500 shrink-0">
                        {filteredPeople.length}{' '}
                        {filteredPeople.length === 1 ? 'person' : 'people'}
                      </div>
                    </div>

                    {filteredPeople.length === 0 ? (
                      <div className="flex min-h-[30vh] flex-col items-center justify-center text-center p-6 border border-dashed border-stone-250 rounded-2xl bg-stone-50/50">
                        <Users size={32} className="text-stone-300 mb-2" />
                        <p className="text-sm font-semibold text-stone-800">
                          No people found
                        </p>
                        <p className="text-xs text-stone-500 mt-1">
                          {personSearch
                            ? 'No person matched your search criteria.'
                            : 'Your Immich library does not contain named people.'}
                        </p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                        {filteredPeople.map((person) => (
                          <button
                            key={person.id}
                            type="button"
                            onClick={() => handleSelectPerson(person)}
                            className="group relative flex items-center gap-3 p-3.5 rounded-2xl border border-stone-200 bg-white hover:border-emerald-700 hover:shadow-lg transition-all duration-300 cursor-pointer text-left hover:-translate-y-0.5 active:translate-y-0 active:scale-98"
                          >
                            <div className="h-10 w-10 shrink-0 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200/60 font-bold group-hover:bg-emerald-700 group-hover:text-white transition-colors duration-300">
                              <User size={20} />
                            </div>
                            <div className="min-w-0 flex-1">
                              <h3 className="text-xs font-bold text-stone-850 truncate leading-tight group-hover:text-emerald-800 transition-colors">
                                {person.name}
                              </h3>
                              <p className="text-[10px] font-semibold text-stone-500 mt-0.5">
                                {person.asset_count}{' '}
                                {person.asset_count === 1 ? 'photo' : 'photos'}
                              </p>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Assets View */}
          {view === 'assets' && (
            <div className="flex-1 flex flex-col justify-between">
              <div>
                {isLoadingAssets && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center gap-3 text-stone-500">
                    <InlineSpinner />
                    <span className="text-xs font-medium">Loading photos…</span>
                  </div>
                )}

                {isErrorAssets && (
                  <div className="flex min-h-[30vh] flex-col items-center justify-center">
                    <InlineError
                      title="Failed to load library"
                      message={
                        errorAssets instanceof Error
                          ? errorAssets.message
                          : 'Unknown error occurred'
                      }
                    />
                  </div>
                )}

                {!isLoadingAssets &&
                  !isErrorAssets &&
                  (!assetsData || assetsData.items.length === 0) && (
                    <div className="flex min-h-[30vh] flex-col items-center justify-center text-center p-6 border border-dashed border-stone-250 rounded-2xl bg-stone-50/50">
                      <ImageIcon size={32} className="text-stone-300 mb-2" />
                      <p className="text-sm font-semibold text-stone-800">
                        No photos found
                      </p>
                      <p className="text-xs text-stone-500 mt-1">
                        {assetsSource === 'album'
                          ? 'This album is empty or contains no supported photo assets.'
                          : 'No photos found for this person.'}
                      </p>
                    </div>
                  )}

                {!isLoadingAssets &&
                  !isErrorAssets &&
                  assetsData &&
                  assetsData.items.length > 0 && (
                    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3.5">
                      {assetsData.items.map((asset) => (
                        <button
                          key={asset.id}
                          type="button"
                          onClick={() => onSelectAsset(asset)}
                          className="group relative aspect-square w-full overflow-hidden rounded-2xl border border-stone-200 bg-stone-55 hover:border-emerald-700 hover:shadow-lg transition-all duration-300 cursor-pointer hover:-translate-y-0.5 active:translate-y-0 active:scale-95"
                        >
                          <SecureImage
                            src={getImmichAssetThumbnailUrl(
                              asset.id,
                              'preview',
                            )}
                            alt={asset.original_file_name || 'Immich photo'}
                            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-108"
                            loading="lazy"
                            decoding="async"
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

              {!isLoadingAssets && !isErrorAssets && assetsData && (
                <Pagination
                  currentPage={assetsPage}
                  totalPages={
                    assetsSource === 'album' && selectedAlbum
                      ? Math.ceil(selectedAlbum.asset_count / ASSETS_PAGE_SIZE)
                      : assetsSource === 'people' && selectedPerson
                      ? Math.ceil(selectedPerson.asset_count / ASSETS_PAGE_SIZE)
                      : 1
                  }
                  onPageChange={setAssetsPage}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
