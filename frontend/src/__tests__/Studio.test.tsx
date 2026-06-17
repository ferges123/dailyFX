import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { StudioPage } from '../pages/StudioPage';

vi.mock('../api/client', async () => {
  return {
    getStudioModules: vi.fn(async () => [
      {
        name: 'pencil_sketch',
        label: 'Pencil Sketch',
        description: 'Sketch effect',
        display_group: 'Artistic',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
      {
        name: 'ai_anime',
        label: 'AI Anime',
        description: 'AI style',
        display_group: 'Illustration',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
    ]),
    createStudioPreview: vi.fn(),
    getApiUrl: (path: string) => path,
  };
});

// Mock URL.createObjectURL and URL.revokeObjectURL
const createObjectURLMock = vi.fn(() => 'mock-object-url');
const revokeObjectURLMock = vi.fn();
beforeEach(() => {
  window.URL.createObjectURL = createObjectURLMock;
  window.URL.revokeObjectURL = revokeObjectURLMock;
});
afterEach(() => {
  vi.clearAllMocks();
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

  it('renders source image preview and handles drag and drop', async () => {
    renderStudio();
    const dropzone = await screen.findByText('Choose image');

    // Simulate drag over
    fireEvent.dragOver(dropzone);
    
    // Simulate drop
    const file = new File(['dummy content'], 'test-image.jpg', { type: 'image/jpeg' });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file]
      }
    });

    // Expect the preview image to render using the mocked object URL
    const previewImg = await screen.findByAltText('Source preview');
    expect(previewImg).toBeInTheDocument();
    expect(previewImg).toHaveAttribute('src', 'mock-object-url');
    expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
    expect(createObjectURLMock).toHaveBeenCalledWith(file);
  });

  it('renders dropdown options grouped by display category', async () => {
    renderStudio();
    const dropdown = await screen.findByRole('combobox');
    await screen.findByText('Pencil Sketch');
    expect(dropdown.querySelector('optgroup[label="Artistic"]')).toBeInTheDocument();
    expect(dropdown.querySelector('optgroup[label="Illustration"]')).toBeInTheDocument();
  });
});
