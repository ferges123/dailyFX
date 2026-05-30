import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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

describe('HistoryPage Error and Empty States', () => {
  function renderHistory() {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <HistoryPage />
      </QueryClientProvider>
    );
  }

  it('renders error state when fetching history fails', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockRejectedValue(new Error('Network error or server crash'));
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue({ albums: [], people: [] });

    renderHistory();

    expect(await screen.findByText('Failed to load history')).toBeInTheDocument();
    expect(screen.getByText('Network error or server crash')).toBeInTheDocument();
  });

  it('renders empty placeholder when history is empty', async () => {
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.getGenerationHistory).mockResolvedValue({ items: [], total: 0, latest_event_id: 0 });
    vi.mocked(client.getImmichFilterOptions).mockResolvedValue({ albums: [], people: [] });

    renderHistory();

    expect(await screen.findByText('No items found')).toBeInTheDocument();
    expect(screen.getByText('There are no generations stored in the history database yet.')).toBeInTheDocument();
  });
});
