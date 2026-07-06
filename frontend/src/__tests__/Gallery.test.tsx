import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GalleryPage } from '../pages/Gallery';
import * as client from '../api/client';

vi.mock('../api/client', () => {
  return {
    getAuthToken: vi.fn(() => null),
    getGenerationHistory: vi.fn(),
    likeGeneration: vi.fn(),
    dislikeGeneration: vi.fn(),
  };
});

vi.mock('../components/SecureImage', () => {
  return {
    SecureImage: ({ src, alt, className }: { src: string; alt: string; className?: string }) => (
      <img src={src} alt={alt} className={className} />
    ),
  };
});

const animeEntry = {
  id: 1,
  task_id: 'task-anime',
  generation_type: 'ai_anime',
  status: 'UPLOADED',
  title: 'Anime Portrait',
  summary: 'Portrait stylized as anime',
  source_asset_ids: '["asset-1"]',
  output_path: '/data/task-anime.png',
  image_url: '/api/generation/history/task-anime/image',
  provider: 'openai',
  model: 'gpt-image-1',
  total_token_count: null,
  config_json: '{}',
  tags_json: '["portrait"]',
  task_step: null,
  uploaded_asset_id: 'immich-1',
  upload_status: 'SUCCESS',
  album_id: 'album-1',
  album_name: 'AI Anime',
  album_created: false,
  album_updated: true,
  accept_notes: null,
  accepted_at: '2026-01-01T12:00:00.000Z',
  output_format: 'png' as const,
  frame_count: null,
  liked: true,
  created_at: '2026-01-01T12:00:00.000Z',
  updated_at: '2026-01-01T12:00:00.000Z',
};

const comicEntry = {
  ...animeEntry,
  id: 2,
  task_id: 'task-comic',
  generation_type: 'ai_comic_book',
  title: 'Comic Frame',
  image_url: '/api/generation/history/task-comic/image',
  liked: null,
  created_at: '2026-01-02T12:00:00.000Z',
};

const secondPageEntry = {
  ...animeEntry,
  id: 3,
  task_id: 'task-polaroid',
  generation_type: 'ai_polaroid_memory',
  title: 'Polaroid Memory',
  image_url: '/api/generation/history/task-polaroid/image',
  liked: false,
  created_at: '2026-01-03T12:00:00.000Z',
};

function renderGallery() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <GalleryPage />
    </QueryClientProvider>,
  );
}

describe('GalleryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads uploaded images as thumbnails and appends the next page', async () => {
    vi.mocked(client.getGenerationHistory)
      .mockResolvedValueOnce({
        items: [animeEntry, comicEntry],
        total: 26,
        latest_event_id: 1,
      })
      .mockResolvedValueOnce({
        items: [secondPageEntry],
        total: 26,
        latest_event_id: 1,
      });

    renderGallery();

    expect(await screen.findByText('Anime Portrait')).toBeInTheDocument();
    expect(screen.getByAltText('Anime Portrait')).toHaveAttribute(
      'src',
      '/api/generation/history/task-anime/image?thumbnail=true',
    );

    fireEvent.click(screen.getByRole('button', { name: /load more/i }));

    expect(await screen.findByText('Polaroid Memory')).toBeInTheDocument();
    expect(client.getGenerationHistory).toHaveBeenLastCalledWith('UPLOADED', 24, '', 24, {
      effect: null,
      liked: null,
      sort: 'newest',
    });
  });

  it('sends gallery filters and sort to the history API', async () => {
    vi.mocked(client.getGenerationHistory).mockResolvedValue({
      items: [animeEntry, comicEntry],
      total: 2,
      latest_event_id: 1,
    });

    renderGallery();

    expect(await screen.findByText('Anime Portrait')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /filter/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Anime' }));

    await waitFor(() => {
      expect(client.getGenerationHistory).toHaveBeenLastCalledWith('UPLOADED', 0, '', 24, {
        effect: 'ai_anime',
        liked: null,
        sort: 'newest',
      });
    });

    fireEvent.click(screen.getByRole('button', { name: /favorites/i }));

    await waitFor(() => {
      expect(client.getGenerationHistory).toHaveBeenLastCalledWith('UPLOADED', 0, '', 24, {
        effect: 'ai_anime',
        liked: true,
        sort: 'newest',
      });
    });

    fireEvent.change(screen.getByLabelText('Sort gallery'), {
      target: { value: 'oldest' },
    });

    await waitFor(() => {
      expect(client.getGenerationHistory).toHaveBeenLastCalledWith('UPLOADED', 0, '', 24, {
        effect: 'ai_anime',
        liked: true,
        sort: 'oldest',
      });
    });
  });
});
