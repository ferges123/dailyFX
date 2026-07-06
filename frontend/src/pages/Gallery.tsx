import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Grid3X3, Search, SlidersHorizontal, X } from 'lucide-react';
import { getGenerationHistory } from '../api/client';
import { type GenerationHistoryEntry } from '../api/types';
import { SecureImage } from '../components/SecureImage';
import { LightboxModal } from './History/LightboxModal';

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
        src={entry.image_url || ''}
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
    </button>
  );
}

export function GalleryPage() {
  const [search, setSearch] = useState('');
  const [effectFilter, setEffectFilter] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [lightboxEntry, setLightboxEntry] =
    useState<GenerationHistoryEntry | null>(null);
  const [offset, setOffset] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ['generation-history', 'UPLOADED', offset, search],
    queryFn: () => getGenerationHistory('UPLOADED', offset, search, PAGE_SIZE),
    placeholderData: (prev) => prev,
  });

  const entries = useMemo(() => {
    if (!data?.items) return [];
    if (!effectFilter) return data.items;
    return data.items.filter((e) => e.generation_type === effectFilter);
  }, [data?.items, effectFilter]);

  const uniqueEffects = useMemo(() => {
    if (!data?.items) return [];
    const seen = new Set<string>();
    return data.items
      .filter((e) => {
        if (seen.has(e.generation_type)) return false;
        seen.add(e.generation_type);
        return true;
      })
      .map((e) => ({
        value: e.generation_type,
        label:
          EFFECT_LABELS[e.generation_type] ||
          e.generation_type.replace(/^ai_/, '').replace(/_/g, ' '),
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [data?.items]);

  const total = data?.total ?? 0;
  const hasMore = offset + PAGE_SIZE < total;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-stone-950">
          <Grid3X3 size={20} />
          <h2 className="text-lg font-semibold">Gallery</h2>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400"
            />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
              className="h-9 w-40 rounded-xl border border-stone-200 bg-white/80 pl-8 pr-3 text-sm text-stone-900 placeholder:text-stone-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/30"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex h-9 items-center gap-1.5 rounded-xl border px-3 text-xs font-medium transition ${
              showFilters || effectFilter
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                : 'border-stone-200 bg-white/80 text-stone-600 hover:border-stone-300'
            }`}
          >
            <SlidersHorizontal size={14} />
            Filter
            {effectFilter && (
              <span className="ml-1 rounded-full bg-emerald-600 px-1.5 py-0.5 text-[10px] text-white">
                1
              </span>
            )}
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="app-surface p-3">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setEffectFilter(null);
                setOffset(0);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                !effectFilter
                  ? 'bg-emerald-600 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              All effects
            </button>
            {uniqueEffects.map((ef) => (
              <button
                key={ef.value}
                type="button"
                onClick={() => {
                  setEffectFilter(ef.value);
                  setOffset(0);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  effectFilter === ef.value
                    ? 'bg-emerald-600 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                {ef.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-2xl bg-stone-200/60"
            />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="grid min-h-[40vh] place-items-center">
          <div className="text-center">
            <p className="text-sm font-medium text-stone-500">
              No images found
            </p>
            <p className="mt-1 text-xs text-stone-400">
              {search
                ? 'Try a different search term'
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
          {offset > 0 && (
            <button
              type="button"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="rounded-xl border border-stone-200 bg-white/80 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-300"
            >
              Previous
            </button>
          )}
          {hasMore && (
            <button
              type="button"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="rounded-xl border border-stone-200 bg-white/80 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-300"
            >
              Next
            </button>
          )}
        </div>
      )}

      <div className="text-center text-xs text-stone-400">
        {total} images
      </div>

      {lightboxEntry && (
        <LightboxModal
          isOpen={true}
          entry={lightboxEntry}
          imageUrl={lightboxEntry.image_url || ''}
          exif={null}
          onClose={() => setLightboxEntry(null)}
        />
      )}
    </div>
  );
}
