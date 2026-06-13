import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { HistoryPage } from '../pages/History/HistoryPage';
import * as client from '../api/client';

// Mock the client functions
vi.mock('../api/client', () => {
  return {
    getSettings: vi.fn(),
    getGenerationHistory: vi.fn(),
    getImmichFilterOptions: vi.fn(),
    getImmichAssetExif: vi.fn(),
    acceptGeneration: vi.fn(),
    rejectGeneration: vi.fn(),
    retryGenerationAcceptance: vi.fn(),
    clearRejectedCache: vi.fn(),
    clearGenerationCache: vi.fn(),
    getImmichAssetDetailUrl: vi.fn((base, id) => id ? `${base}/photos/${id}` : null),
  };
});

vi.mock('../api/generationStream', () => {
  return {
    openGenerationStream: vi.fn(() => ({ close: vi.fn() })),
  };
});

const mockSettings = {
  immich_url: 'http://immich-server',
  local_ai_base_url: 'http://local-ai:11434/v1',
  ai_vision_hourly_limit: 10,
  ai_image_hourly_limit: 10,
  debug_mode: false,
  favorite_albums_json: null,
  ai_custom_prompt: null,
  immich_api_key_masked: '***',
  openai_api_key_masked: null,
  gemini_api_key_masked: null,
  openrouter_api_key_masked: null,
  byteplus_api_key_masked: null,
  xiaomi_api_key_masked: null,
  local_ai_api_key_masked: null,
};

const mockHistoryItem1 = {
  id: 1,
  task_id: 'man-1',
  generation_type: 'instafilter',
  status: 'PENDING_REVIEW',
  title: 'Mayfair Sunset',
  summary: 'Beautiful sunset with orange filter',
  source_asset_ids: '["asset-1"]',
  output_path: '/data/man-1.png',
  image_url: '/api/generation/history/man-1/image',
  provider: 'local',
  model: 'pilgram',
  tags_json: '["sunset", "nature"]',
  created_at: '2026-05-27T10:00:00.000Z',
  album_name: 'AI Sunset',
  album_id: null,
  album_created: false,
  album_updated: false,
  accept_notes: null,
  accepted_at: null,
  uploaded_asset_id: null,
  upload_status: null,
  updated_at: '2026-05-27T10:00:00.000Z',
  config_json: JSON.stringify({
    metadata_provenance: {
      title_source: 'final_vision',
      summary_source: 'final_vision',
      tags_source: 'final_vision',
      tag_injections: ['AI', 'Anime'],
    },
    task_trace: [
      { stage: 'start', message: 'Generation started', step: 'running', status: 'running', progress: 0, timestamp: '2026-05-27T10:00:00.000Z' },
      { stage: 'final_vision', message: 'Analyzing final generated image with AI', step: 'analyzing_final_image', status: 'running', progress: 0.7, timestamp: '2026-05-27T10:00:12.000Z' },
    ],
  }),
  task_step: null,
  total_token_count: null,
};

const mockHistoryItem2 = {
  id: 2,
  task_id: 'man-2',
  generation_type: 'ai_anime',
  status: 'UPLOADED',
  title: 'Anime Portrait',
  summary: 'Portrait stylized as anime',
  source_asset_ids: '["asset-2"]',
  output_path: '/data/man-2.png',
  image_url: '/api/generation/history/man-2/image',
  provider: 'openai',
  model: 'gpt-image-1',
  tags_json: '["portrait", "anime"]',
  created_at: '2026-05-27T11:00:00.000Z',
  album_name: 'AI Anime',
  album_id: 'album-2',
  album_created: false,
  album_updated: true,
  accept_notes: null,
  accepted_at: '2026-05-27T11:05:00.000Z',
  uploaded_asset_id: 'immich-asset-2',
  upload_status: 'SUCCESS',
  updated_at: '2026-05-27T11:05:00.000Z',
  config_json: '{}',
  task_step: null,
  total_token_count: null,
};

const mockQueuedHistoryItem = {
  id: 3,
  task_id: 'man-3',
  generation_type: 'schedule_run',
  status: 'QUEUED',
  title: 'Queued: Morning run',
  summary: 'Waiting for the worker to start this scheduled run.',
  source_asset_ids: '[]',
  output_path: null,
  image_url: null,
  provider: null,
  model: null,
  tags_json: null,
  created_at: '2026-05-27T12:00:00.000Z',
  album_name: 'AI Photos',
  album_id: null,
  album_created: false,
  album_updated: false,
  accept_notes: null,
  accepted_at: null,
  uploaded_asset_id: null,
  upload_status: null,
  updated_at: '2026-05-27T12:00:00.000Z',
  config_json: JSON.stringify({ schedule_id: 1, album_name: 'AI Photos' }),
  task_step: 'queued',
  total_token_count: null,
};

const mockHistoryPage = {
  items: [mockHistoryItem1, mockHistoryItem2],
  total: 2,
  latest_event_id: 10,
};

const mockQueuedHistoryPage = {
  items: [mockQueuedHistoryItem, mockHistoryItem1],
  total: 2,
  latest_event_id: 11,
};

const mockFilterOptions = {
  albums: [
    { id: 'album-1', album_name: 'AI Sunset', asset_count: 5, thumbnail_asset_id: null },
    { id: 'album-2', album_name: 'AI Anime', asset_count: 10, thumbnail_asset_id: null },
  ],
  people: [],
};

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.acceptGeneration).mockResolvedValue(mockHistoryItem1);
    vi.mocked(client.rejectGeneration).mockResolvedValue(mockHistoryItem1);
    vi.mocked(client.getImmichAssetExif).mockResolvedValue({});
  });

  function renderHistory(path = '/history') {
    window.history.pushState({}, '', path);
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <HistoryPage />
        </BrowserRouter>
      </QueryClientProvider>
    );
  }

  it('renders history entries list and displays selected details', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    // Verify list rendering
    expect(await screen.findByText('Mayfair Sunset')).toBeInTheDocument();
    expect(screen.getByText('Anime Portrait')).toBeInTheDocument();

    // Verify detail panel displays selected item 1 by default
    expect(screen.getByText('"Beautiful sunset with orange filter"')).toBeInTheDocument();
    expect(screen.getByText('#sunset')).toBeInTheDocument();
    expect(screen.getByText('#nature')).toBeInTheDocument();
    expect(screen.getByText('Metadata provenance')).toBeInTheDocument();
    expect(screen.getByText('Title:')).toBeInTheDocument();
    expect(screen.getByText('Task timeline')).toBeInTheDocument();
    expect(screen.getByText('Generation started')).toBeInTheDocument();
    expect(screen.getByText('+12s')).toBeInTheDocument();
  });

  it('renders queued run-now tasks in history immediately', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockQueuedHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    expect(await screen.findByText('Queued: Morning run')).toBeInTheDocument();
    expect(screen.getAllByText('Queued').length).toBeGreaterThan(0);
    expect(screen.getByText('This task is queued and waiting for the worker to start it.')).toBeInTheDocument();
  });

  it('keeps history usable when settings cannot be loaded initially', async () => {
    vi.mocked(client.getSettings).mockRejectedValue(new Error('Settings unavailable'));
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    expect(await screen.findByText('History links unavailable')).toBeInTheDocument();
    expect(screen.getByText('Settings unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('Mayfair Sunset').length).toBeGreaterThan(0);
  });

  it('switches selected entry when card is clicked', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    const secondCard = await screen.findByText('Anime Portrait');
    fireEvent.click(secondCard);

    // Displays second card details
    expect(screen.getByText('"Portrait stylized as anime"')).toBeInTheDocument();
    expect(screen.getByText('#portrait')).toBeInTheDocument();
    expect(screen.getByText('#anime')).toBeInTheDocument();
    expect(screen.queryByText('"Beautiful sunset with orange filter"')).not.toBeInTheDocument();
    expect(window.location.pathname).toBe('/history/man-2');
  });

  it('keeps a direct history detail route selected', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory('/history/man-2');

    expect(await screen.findByText('Mayfair Sunset')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/history/man-2');
  });

  it('calls acceptGeneration when Accept button is clicked', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    const acceptButton = await screen.findByRole('button', { name: 'Accept' });
    fireEvent.click(acceptButton);

    await waitFor(() => {
      expect(client.acceptGeneration).toHaveBeenCalledWith('man-1', {
        create_album: false,
        album_name: 'AI Sunset',
        album_id: null,
      });
    });
  });

  it('calls rejectGeneration when Reject button is clicked', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    const rejectButton = await screen.findByRole('button', { name: 'Reject' });
    fireEvent.click(rejectButton);

    await waitFor(() => {
      expect(vi.mocked(client.rejectGeneration)).toHaveBeenCalled();
      expect(vi.mocked(client.rejectGeneration).mock.calls[0][0]).toBe('man-1');
    });
  });

  it('opens custom upload modal and submits custom destination options', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue(mockHistoryPage);
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue(mockFilterOptions);

    renderHistory();

    // Click "Accept..." to open modal
    const acceptMoreButton = await screen.findByRole('button', { name: 'Accept...' });
    fireEvent.click(acceptMoreButton);

    // Verify modal elements are visible
    expect(screen.getByText('Upload Destination Album')).toBeInTheDocument();

    // Choose existing album option
    const existingOptionLabel = screen.getByText('Add to existing album');
    fireEvent.click(existingOptionLabel);

    // Select the existing album
    const select = screen.getAllByRole('combobox')[1];
    fireEvent.change(select, { target: { value: 'album-2' } });

    // Submit the modal form
    const confirmButton = screen.getByRole('button', { name: 'Confirm Upload' });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(client.acceptGeneration).toHaveBeenCalledWith('man-1', {
        create_album: false,
        album_name: 'AI Anime',
        album_id: 'album-2',
      });
    });
  });
});
