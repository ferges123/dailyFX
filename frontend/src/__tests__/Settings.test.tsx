import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { SettingsPage } from '../pages/Settings';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getHealth: vi.fn(),
    getDetailedHealth: vi.fn(),
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    testImmichConnection: vi.fn(),
    testOpenAIConnection: vi.fn(),
    testGeminiConnection: vi.fn(),
    testOpenRouterConnection: vi.fn(),
    testBytePlusConnection: vi.fn(),
    testLocalAIConnection: vi.fn(),
    testXiaomiConnection: vi.fn(),
  };
});

const mockSettings = {
  immich_url: 'http://immich-server',
  local_ai_base_url: 'http://local-ai:11434/v1',
  ai_vision_hourly_limit: 10,
  ai_image_hourly_limit: 5,
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

const mockHealth = { status: 'ok', version: '0.1.0', auth_enabled: false };
const mockDetailedHealth = {
  status: 'ok',
  checks: {
    scheduler: { status: 'ok', age_seconds: 15 },
    database: { status: 'ok' },
    immich: { status: 'not_configured' },
  },
};

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe('SettingsPage', () => {
  it('loads settings and renders the form', async () => {
    vi.mocked(client.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(client.getDetailedHealth).mockResolvedValue(mockDetailedHealth);
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);

    renderSettings();

    expect(await screen.findByText('Runtime Status')).toBeInTheDocument();
    expect(await screen.findByText('Immich Connection')).toBeInTheDocument();
    expect(screen.getByDisplayValue('http://immich-server')).toBeInTheDocument();
    expect(screen.getByDisplayValue('http://local-ai:11434/v1')).toBeInTheDocument();
    expect(screen.getByText('AI Budget Limits')).toBeInTheDocument();
  });

  it('shows a retryable error when the settings fetch fails initially', async () => {
    vi.mocked(client.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(client.getDetailedHealth).mockResolvedValue(mockDetailedHealth);
    vi.mocked(client.getSettings).mockRejectedValue(new client.ApiError(503, 'Settings service temporarily unavailable'));

    renderSettings();

    expect(await screen.findByText('Could not load settings')).toBeInTheDocument();
    expect(screen.getByText('Settings service temporarily unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('blocks save when settings validation fails', async () => {
    vi.mocked(client.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(client.getDetailedHealth).mockResolvedValue(mockDetailedHealth);
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.updateSettings).mockResolvedValue(mockSettings);

    renderSettings();

    fireEvent.change(await screen.findByLabelText('Immich URL'), {
      target: { value: 'ftp://bad-url.example' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Fix the highlighted settings')).toBeInTheDocument();
    expect(screen.getAllByText('Immich URL must be an absolute http:// or https:// URL.')).toHaveLength(2);
    expect(vi.mocked(client.updateSettings)).not.toHaveBeenCalled();
  });

  it('blocks save when AI limits are out of range', async () => {
    vi.mocked(client.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(client.getDetailedHealth).mockResolvedValue(mockDetailedHealth);
    vi.mocked(client.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(client.updateSettings).mockResolvedValue(mockSettings);

    renderSettings();

    fireEvent.change(await screen.findByLabelText('Vision calls per hour'), {
      target: { value: '0' },
    });
    await screen.findByDisplayValue('0');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(vi.mocked(client.updateSettings)).not.toHaveBeenCalled();
  });
});
