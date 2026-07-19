import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  Grid3X3,
  Heart,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';
import { getGenerationHistory } from '../api/client';
import { type GenerationHistoryEntry } from '../api/types';
import { SecureImage } from '../components/SecureImage';
import { SearchInput } from '../components/SearchInput';
import { LightboxModal } from './History/LightboxModal';
import { useDebounce } from './History/useDebounce';
import { useSelectedExif } from '../hooks/useSelectedExif';
import { appendQueryParam } from '../utils/url';

const PAGE_SIZE = 24;

const EFFECT_LABELS: Record<string, string> = {
  ai_anime: 'Anime',
  ai_caricature: 'Caricature',
  ai_claymation: 'Claymation',
  ai_comic_book: 'Comic Book',
  ai_cyberpunk: 'Cyberpunk',
  ai_fantasy_hero: 'Fantasy Hero',
  ai_polaroid_memory: 'Polaroid',
  ai_superhero: 'Superhero',
  ai_vintage_film: 'Vintage Film',
  ai_80s_action_movie: '80s Action',
  ai_magazine_cover_no_text: 'Magazine',
  ai_low_poly_3d: 'Low Poly 3D',
  ai_celebrity_mugshot: 'Celebrity Mugshot',
  ai_gangster_mugshot: 'Gangster Mugshot',
  ai_mugshot: 'Mugshot',
  ai_ancient_statue: 'Ancient Statue',
  ai_pixel_rpg_8bit: 'Pixel Art',
  ai_royal_portrait: 'Royal Portrait',
  ai_caveman: 'Caveman',
  ai_corporate_headshot: 'Corporate',
  ai_film_contact_sheet: 'Film Sheet',
  ai_fairytale_storybook: 'Fairytale',
  ai_yearbook_90s: '90s Yearbook',
  ai_snow_globe: 'Snow Globe',
  ai_editorial_black_white: 'Editorial B&W',
  ai_miniature_train_set: 'Miniature',
  ai_ukiyo_e_print: 'Ukiyo-e',
};

function GalleryCard({
  entry,
  onClick,
}: {
  entry: GenerationHistoryEntry;
  onClick: () => void;
}) {
  const label =
    EFFECT_LABELS[entry.generation_type] ||
    entry.generation_type.replace(/^ai_/, '').replace(/_/g, ' ');

  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative aspect-square overflow-hidden rounded-2xl border border-stone-200/60 bg-stone-100 shadow-xs transition-all hover:shadow-lg hover:shadow-stone-200/50 hover:scale-[1.02]"
    >
      <SecureImage
        src={entry.image_url ? appendQueryParam(entry.image_url, 'thumbnail', 'true') : ''}
        alt={entry.title}
        className="h-full w-full object-cover"
        loading="lazy"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="absolute bottom-0 left-0 right-0 p-3 opacity-0 transition-opacity group-hover:opacity-100">
        <p className="text-sm font-semibold text-white drop-shadow-md line-clamp-1">
          {entry.title}
        </p>
        <p className="mt-0.5 text-xs text-white/80 drop-shadow-md">{label}</p>
      </div>
      <div className="absolute top-2 right-2">
        <span className="inline-block rounded-full bg-black/40 px-2 py-0.5 text-[10px] font-medium text-white/90 backdrop-blur-sm">
          {label}
        </span>
      </div>
      {entry.liked === true && (
        <div className="absolute left-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-600 text-white shadow-md">
          <Heart size={13} fill="currentColor" />
        </div>
      )}
    </button>
  );
}

export function GalleryPage() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [effectFilter, setEffectFilter] = useState<string | null>(null);
  const [likedFilter, setLikedFilter] = useState<boolean | null>(null);
  const [sort, setSort] = useState<'newest' | 'oldest'>('newest');
  const [showFilters, setShowFilters] = useState(false);
  const [lightboxEntry, setLightboxEntry] =
    useState<GenerationHistoryEntry | null>(null);

  const { selectedExif } = useSelectedExif(
    lightboxEntry?.config_json,
    lightboxEntry?.source_asset_ids,
  );
  const [offset, setOffset] = useState(0);
  const [loadedEntries, setLoadedEntries] = useState<GenerationHistoryEntry[]>(
    [],
  );

  const filters = useMemo(
    () => ({
      effect: effectFilter,
      liked: likedFilter,
      sort,
    }),
    [effectFilter, likedFilter, sort],
  );

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: [
      'generation-history',
      'gallery',
      'UPLOADED',
      offset,
      debouncedSearch,
      filters,
    ],
    queryFn: () =>
      getGenerationHistory('UPLOADED', offset, debouncedSearch, PAGE_SIZE, filters),
  });

  useEffect(() => {
    setOffset(0);
    setLoadedEntries([]);
  }, [debouncedSearch, effectFilter, likedFilter, sort]);

  useEffect(() => {
    if (!data?.items) return;
    setLoadedEntries((prev) => {
      if (offset === 0) return data.items;
      const seen = new Set(prev.map((entry) => entry.task_id));
      return [
        ...prev,
        ...data.items.filter((entry) => !seen.has(entry.task_id)),
      ];
    });
  }, [data?.items, offset]);

  const entries = loadedEntries;

  const uniqueEffects = useMemo(() => {
    const known = Object.entries(EFFECT_LABELS).map(([value, label]) => ({
      value,
      label,
    }));
    const seen = new Set<string>();
    return [
      ...known,
      ...entries.map((entry) => ({
        value: entry.generation_type,
        label:
          EFFECT_LABELS[entry.generation_type] ||
          entry.generation_type.replace(/^ai_/, '').replace(/_/g, ' '),
      })),
    ]
      .filter((effect) => {
        if (seen.has(effect.value)) return false;
        seen.add(effect.value);
        return true;
      })
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [entries]);

  const total = data?.total ?? 0;
  const hasMore = offset + PAGE_SIZE < total;
  const activeFilterCount =
    Number(Boolean(effectFilter)) + Number(likedFilter === true);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-stone-950">
          <Grid3X3 size={20} />
          <h2 className="text-lg font-semibold">Gallery</h2>
          <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-500">
            {total} images
          </span>
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
          <label className="sr-only" htmlFor="gallery-sort">
            Sort gallery
          </label>
          <select
            id="gallery-sort"
            aria-label="Sort gallery"
            value={sort}
            onChange={(e) => setSort(e.target.value as 'newest' | 'oldest')}
            className="app-control app-control-muted h-9 w-auto px-3 text-xs font-medium"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
          <div className="w-40">
            <SearchInput
              value={search}
              onSearch={setSearch}
              onClear={() => setSearch('')}
              placeholder="Search..."
              aria-label="Search gallery"
              iconSize={14}
              inputClassName="app-control app-control-muted h-9 pl-9 pr-8 text-sm"
            />
          </div>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            aria-pressed={showFilters}
            className={`app-button-secondary h-9 px-3 text-xs ${
              showFilters || activeFilterCount > 0
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:border-emerald-400 hover:bg-emerald-100'
                : ''
            }`}
          >
            <SlidersHorizontal size={14} />
            Filter
            {activeFilterCount > 0 && (
              <span className="ml-1 inline-flex items-center justify-center rounded-full bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="app-panel grid gap-3 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setEffectFilter(null);
              }}
              aria-pressed={!effectFilter}
              className={`inline-flex h-8 items-center rounded-lg px-3 text-xs font-semibold transition ${
                !effectFilter
                  ? 'bg-emerald-600 text-white shadow-xs hover:bg-emerald-700'
                  : 'border border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50'
              }`}
            >
              All effects
            </button>
            <button
              type="button"
              onClick={() =>
                setLikedFilter((current) => (current === true ? null : true))
              }
              aria-pressed={likedFilter === true}
              className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition ${
                likedFilter === true
                  ? 'bg-emerald-600 text-white shadow-xs hover:bg-emerald-700'
                  : 'border border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50'
              }`}
            >
              <Heart
                size={12}
                fill={likedFilter === true ? 'currentColor' : 'none'}
              />
              Favorites
            </button>
            {(effectFilter || likedFilter === true || search) && (
              <button
                type="button"
                onClick={() => {
                  setEffectFilter(null);
                  setLikedFilter(null);
                  setSearch('');
                }}
                className="app-button-ghost h-8 px-3 text-xs"
              >
                Reset
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {uniqueEffects.map((ef) => {
              const active = effectFilter === ef.value;
              return (
                <button
                  key={ef.value}
                  type="button"
                  onClick={() => {
                    setEffectFilter(ef.value);
                  }}
                  aria-pressed={active}
                  className={`inline-flex h-7 items-center rounded-full px-3 text-[11px] font-semibold transition ${
                    active
                      ? 'bg-emerald-600 text-white shadow-xs hover:bg-emerald-700'
                      : 'border border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50'
                  }`}
                >
                  {ef.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {isLoading && entries.length === 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-2xl bg-stone-200/60"
            />
          ))}
        </div>
      ) : isError ? (
        <div className="grid min-h-[40vh] place-items-center">
          <div className="text-center">
            <AlertCircle className="mx-auto text-red-500" size={24} />
            <p className="mt-2 text-sm font-medium text-stone-700">
              Could not load gallery
            </p>
            <p className="mt-1 max-w-sm text-xs text-stone-400">
              {error instanceof Error
                ? error.message
                : 'The gallery request failed.'}
            </p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="app-button-secondary mt-3 px-3 py-2 text-xs"
            >
              <RefreshCw size={13} />
              Retry
            </button>
          </div>
        </div>
      ) : entries.length === 0 ? (
        <div className="grid min-h-[40vh] place-items-center">
          <div className="text-center">
            <p className="text-sm font-medium text-stone-500">
              No images found
            </p>
            <p className="mt-1 text-xs text-stone-400">
              {search || effectFilter || likedFilter === true
                ? 'Try a different search term or filter'
                : 'Generate some images in Studio or Schedules'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {entries.map((entry) => (
            <GalleryCard
              key={entry.task_id}
              entry={entry}
              onClick={() => setLightboxEntry(entry)}
            />
          ))}
        </div>
      )}

      {(hasMore || offset > 0) && entries.length > 0 && (
        <div className="flex justify-center gap-2 pt-2">
          {hasMore && (
            <button
              type="button"
              disabled={isFetching}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="app-button-secondary h-9 px-4 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isFetching ? 'Loading...' : 'Load more'}
            </button>
          )}
        </div>
      )}

      {lightboxEntry && (() => {
        const currentIdx = entries.findIndex((e) => e.task_id === lightboxEntry.task_id);
        const hasPrev = currentIdx > 0;
        const hasNext = currentIdx < entries.length - 1;
        return (
          <LightboxModal
            isOpen={true}
            entry={lightboxEntry}
            imageUrl={lightboxEntry.image_url || ''}
            exif={selectedExif}
            onClose={() => setLightboxEntry(null)}
            onPrev={hasPrev ? () => setLightboxEntry(entries[currentIdx - 1]) : undefined}
            onNext={hasNext ? () => setLightboxEntry(entries[currentIdx + 1]) : undefined}
            hasPrev={hasPrev}
            hasNext={hasNext}
          />
        );
      })()}
    </div>
  );
}
