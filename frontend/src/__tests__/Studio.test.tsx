import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { StudioPage } from '../pages/StudioPage';

vi.mock('../api/client', async () => {
  return {
    getStudioModules: vi.fn(async () => [
      {
        name: 'pencil_sketch',
        label: 'Pencil Sketch',
        description: 'Sketch effect',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
      {
        name: 'ai_anime',
        label: 'AI Anime',
        description: 'AI style',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
    ]),
    createStudioPreview: vi.fn(),
    getApiUrl: (path: string) => path,
  };
});

function renderStudio() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <StudioPage />
    </QueryClientProvider>,
  );
}

describe('StudioPage', () => {
  it('renders upload and AI-capable effect controls', async () => {
    renderStudio();

    expect(await screen.findByText('Studio')).toBeInTheDocument();
    expect(await screen.findByText('Pencil Sketch')).toBeInTheDocument();
    expect(await screen.findByText('AI Anime')).toBeInTheDocument();
    expect(screen.getByLabelText('AI Vision metadata')).toBeInTheDocument();
    expect(screen.getByLabelText('AI prompt enrichment')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create preview/i })).toBeDisabled();
  });
});
